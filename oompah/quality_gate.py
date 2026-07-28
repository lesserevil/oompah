"""Persistent, single-flight quality gates for review-ready branch heads."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import signal
import subprocess
import tempfile
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class QualityGateResult:
    """Outcome of checking one exact branch head with one exact command."""

    status: str
    head_sha: str
    command: str
    duration_seconds: float = 0.0
    output_tail: str = ""
    cached: bool = False

    @property
    def passed(self) -> bool:
        return self.status in {"passed", "not_configured"}


class BranchQualityGate:
    """Run and persist full branch checks without duplicate concurrent work.

    Outcomes are keyed by repository identity, target branch, work branch,
    exact head SHA, and command. Any new commit, rebase, target, or command
    therefore invalidates them naturally. A process-wide lock makes concurrent
    readiness sweeps single-flight; persisted results make readiness recovery
    safe across service restarts.
    """

    def __init__(
        self,
        state_path: str,
        *,
        timeout_seconds: int = 3600,
        output_tail_bytes: int = 16 * 1024,
    ) -> None:
        self.state_path = Path(state_path)
        self.timeout_seconds = max(int(timeout_seconds), 1)
        self.output_tail_bytes = max(int(output_tail_bytes), 1024)
        self._lock = threading.Lock()

    @staticmethod
    def _head_sha(repo_path: str) -> str:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        )
        return result.stdout.strip()

    @staticmethod
    def _evidence_key(
        *,
        repo_identity: str,
        target_branch: str,
        work_branch: str,
        head_sha: str,
        command: str,
    ) -> str:
        payload = "\0".join(
            (repo_identity, target_branch, work_branch, head_sha, command)
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _load(self) -> dict[str, dict]:
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        entries = raw.get("results", {}) if isinstance(raw, dict) else {}
        if not entries and isinstance(raw, dict):
            entries = raw.get("passed", {})
        return entries if isinstance(entries, dict) else {}

    def _save(self, entries: dict[str, dict]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            {"version": 1, "results": entries},
            indent=2,
            sort_keys=True,
        ) + "\n"
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{self.state_path.name}.",
            dir=self.state_path.parent,
            text=True,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self.state_path)
        finally:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass

    def _store_result(
        self,
        entries: dict[str, dict],
        key: str,
        result: QualityGateResult,
        *,
        repo_identity: str,
        target_branch: str,
        work_branch: str,
    ) -> None:
        entries[key] = {
            **asdict(result),
            "recorded_at": time.time(),
            "repo_identity": repo_identity,
            "target_branch": target_branch,
            "work_branch": work_branch,
        }
        # Old outcomes are only an optimization and can be discarded safely.
        if len(entries) > 500:
            newest = sorted(
                entries.items(),
                key=lambda item: float(item[1].get("recorded_at", 0) or 0),
                reverse=True,
            )[:500]
            entries.clear()
            entries.update(newest)
        try:
            self._save(entries)
        except OSError as exc:
            logger.warning("Failed to persist branch quality evidence: %s", exc)

    def run(
        self,
        *,
        repo_path: str,
        repo_identity: str,
        target_branch: str,
        work_branch: str,
        command: str,
    ) -> QualityGateResult:
        """Return passing evidence or execute the configured full check."""
        command = str(command or "").strip()
        if not command:
            return QualityGateResult(
                status="not_configured",
                head_sha=self._head_sha(repo_path),
                command="",
            )

        # Keep the check itself under the lock. Full gates are deliberately
        # serialized: they are expensive, and this guarantees that concurrent
        # readiness sweeps cannot launch duplicate checks for the same head.
        with self._lock:
            try:
                head_sha = self._head_sha(repo_path)
            except (OSError, subprocess.SubprocessError) as exc:
                return QualityGateResult(
                    status="error",
                    head_sha="",
                    command=command,
                    output_tail=f"Could not resolve branch HEAD: {exc}",
                )
            key = self._evidence_key(
                repo_identity=repo_identity,
                target_branch=target_branch,
                work_branch=work_branch,
                head_sha=head_sha,
                command=command,
            )
            entries = self._load()
            cached = entries.get(key)
            if isinstance(cached, dict) and cached.get("status"):
                return QualityGateResult(
                    status=str(cached["status"]),
                    head_sha=head_sha,
                    command=command,
                    duration_seconds=float(cached.get("duration_seconds", 0) or 0),
                    output_tail=str(cached.get("output_tail", "") or ""),
                    cached=True,
                )

            started = time.monotonic()
            try:
                process = subprocess.Popen(  # noqa: S602 - operator-owned command
                    command,
                    cwd=repo_path,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    start_new_session=True,
                )
                stdout, stderr = process.communicate(timeout=self.timeout_seconds)
                duration = time.monotonic() - started
                combined = "\n".join(
                    part for part in (stdout, stderr) if part
                )
                output_tail = combined.encode("utf-8", errors="replace")[
                    -self.output_tail_bytes :
                ].decode("utf-8", errors="replace")
                if process.returncode != 0:
                    result = QualityGateResult(
                        status="failed",
                        head_sha=head_sha,
                        command=command,
                        duration_seconds=duration,
                        output_tail=output_tail,
                    )
                    self._store_result(
                        entries,
                        key,
                        result,
                        repo_identity=repo_identity,
                        target_branch=target_branch,
                        work_branch=work_branch,
                    )
                    return result
            except subprocess.TimeoutExpired as exc:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except (OSError, UnboundLocalError):
                    pass
                stdout, stderr = process.communicate()
                duration = time.monotonic() - started
                combined = "\n".join(
                    str(part or "")
                    for part in (
                        stdout or exc.stdout,
                        stderr or exc.stderr,
                    )
                    if part
                )
                result = QualityGateResult(
                    status="timed_out",
                    head_sha=head_sha,
                    command=command,
                    duration_seconds=duration,
                    output_tail=combined[-self.output_tail_bytes :],
                )
                self._store_result(
                    entries,
                    key,
                    result,
                    repo_identity=repo_identity,
                    target_branch=target_branch,
                    work_branch=work_branch,
                )
                return result
            except OSError as exc:
                result = QualityGateResult(
                    status="error",
                    head_sha=head_sha,
                    command=command,
                    duration_seconds=time.monotonic() - started,
                    output_tail=str(exc),
                )
                self._store_result(
                    entries,
                    key,
                    result,
                    repo_identity=repo_identity,
                    target_branch=target_branch,
                    work_branch=work_branch,
                )
                return result

            result = QualityGateResult(
                status="passed",
                head_sha=head_sha,
                command=command,
                duration_seconds=duration,
                output_tail=output_tail,
            )
            self._store_result(
                entries,
                key,
                result,
                repo_identity=repo_identity,
                target_branch=target_branch,
                work_branch=work_branch,
            )
            return result
