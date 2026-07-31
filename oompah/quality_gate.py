"""Persistent, single-flight quality gates for review-ready branch heads."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import signal
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from oompah.client_auth import agent_environment

logger = logging.getLogger(__name__)

_EVIDENCE_VERSION = 2


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

    # Class-level tracking of active process groups for graceful shutdown.
    # Maps pid -> process object for cleanup on orchestrator stop.
    _active_processes: dict[int, subprocess.Popen[str]] = {}
    # Keep generation and snapshot ownership beside the process itself.  A
    # task may be reopened while an old gate is still running; generation
    # scoping ensures cancellation cannot terminate a replacement gate.
    _active_generations: dict[int, str | None] = {}
    _active_snapshots: dict[int, Path] = {}
    _processes_lock = threading.Lock()

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
        self._key_locks: dict[str, threading.Lock] = {}

    @classmethod
    def _terminate_active_processes(
        cls,
        *,
        generation: str | None = None,
    ) -> int:
        """Terminate active process groups owned by *generation*.

        Keeping this operation centralized makes shutdown and task-specific
        cancellation use the same process-group and snapshot cleanup rules.
        """
        with cls._processes_lock:
            processes = [
                (pid, process)
                for pid, process in cls._active_processes.items()
                if generation is None
                or cls._active_generations.get(pid) == generation
            ]
            for _pid, process in processes:
                # The run thread uses this marker to return a non-cached
                # interruption instead of recording a false CI failure.
                setattr(process, "_oompah_interrupted", True)

        terminated_count = 0
        for pid, process in processes:
            try:
                os.killpg(pid, signal.SIGTERM)
                terminated_count += 1
            except ProcessLookupError:
                pass
            except OSError as exc:
                logger.warning(
                    "Failed to terminate quality gate process group %d: %s",
                    pid,
                    exc,
                )
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                except OSError as exc:
                    logger.warning(
                        "Failed to kill quality gate process group %d: %s",
                        pid,
                        exc,
                    )
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    logger.warning(
                        "Quality gate process group %d did not stop after SIGKILL",
                        pid,
                    )
            with cls._processes_lock:
                cls._active_processes.pop(pid, None)
                cls._active_generations.pop(pid, None)
                cls._active_snapshots.pop(pid, None)

        if terminated_count:
            logger.info(
                "Interrupted %d active quality gate process group(s)",
                terminated_count,
            )
        return terminated_count

    @classmethod
    def cleanup_active_processes(cls) -> int:
        """Terminate all active quality gate process groups.

        Called during orchestrator shutdown to ensure process groups are
        cleaned up before leases become reclaimable. Returns count terminated.
        """
        return cls._terminate_active_processes()

    @classmethod
    def cancel_generation(cls, generation: str) -> int:
        """Cancel only gates belonging to one exact task generation."""
        return cls._terminate_active_processes(generation=str(generation))

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
    def _resolve_commit(repo_path: str, commit: str) -> str:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", f"{commit}^{{commit}}"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        )
        return result.stdout.strip()

    @staticmethod
    def _create_snapshot(repo_path: str, head_sha: str) -> Path:
        """Materialize *head_sha* in a private detached worktree.

        The task worktree is only used to resolve and validate the commit.
        Git then materializes that immutable object in a gate-owned checkout,
        so later task-agent edits cannot change the command's inputs.
        """
        snapshot = Path(
            tempfile.mkdtemp(prefix=".oompah-quality-gate-")
        )
        try:
            subprocess.run(
                [
                    "git",
                    "-C",
                    repo_path,
                    "worktree",
                    "add",
                    "--detach",
                    str(snapshot),
                    head_sha,
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=60,
            )
            if BranchQualityGate._head_sha(str(snapshot)) != head_sha:
                raise RuntimeError(
                    "quality gate snapshot checked out a different commit"
                )
            return snapshot
        except BaseException:
            shutil.rmtree(snapshot, ignore_errors=True)
            raise

    @staticmethod
    def _remove_snapshot(repo_path: str, snapshot: Path) -> None:
        """Remove exactly the detached worktree owned by one gate."""
        # Prefer the task checkout used for creation, but fall back to the
        # snapshot itself if an operator reassigned or removed that checkout
        # while the gate was running.  This avoids leaving a stale worktree
        # registration behind while still limiting removal to this path.
        commands = (
            [
                "git",
                "-C",
                repo_path,
                "worktree",
                "remove",
                "--force",
                str(snapshot),
            ],
            [
                "git",
                "-C",
                str(snapshot),
                "worktree",
                "remove",
                "--force",
                str(snapshot),
            ],
        )
        for command in commands:
            try:
                removed = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=60,
                )
            except (OSError, subprocess.TimeoutExpired):
                continue
            if removed.returncode == 0 or not snapshot.exists():
                break
        # Git may already have removed the registration while the process was
        # being cancelled.  The path is still gate-owned and safe to remove.
        shutil.rmtree(snapshot, ignore_errors=True)

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
            (
                str(_EVIDENCE_VERSION),
                repo_identity,
                target_branch,
                work_branch,
                head_sha,
                command,
            )
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
            {"version": _EVIDENCE_VERSION, "results": entries},
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
        with self._lock:
            # Reload while holding the state lock: gates for different heads
            # are intentionally allowed to overlap, so retaining a caller's
            # pre-execution dictionary could otherwise drop another result.
            entries = self._load()
            entries[key] = {
                **asdict(result),
                "recorded_at": time.time(),
                "repo_identity": repo_identity,
                "target_branch": target_branch,
                "work_branch": work_branch,
            }
            # Old outcomes are only an optimization and can be discarded
            # safely, but active subprocesses never rely on this evidence file.
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

    def _key_lock(self, key: str) -> threading.Lock:
        """Return the single-flight lock for one exact evidence key."""
        with self._lock:
            return self._key_locks.setdefault(key, threading.Lock())

    def run(
        self,
        *,
        repo_path: str,
        repo_identity: str,
        target_branch: str,
        work_branch: str,
        command: str,
        retry_forced: bool = False,
        expected_head_sha: str | None = None,
        generation: str | None = None,
        is_current: Callable[[], bool] | None = None,
    ) -> QualityGateResult:
        """Return passing evidence or execute the configured full check.
        
        When retry_forced=True, bypasses cache for failed/timed_out/error
        results and re-executes. Passed results remain cached and reusable.
        """
        command = str(command or "").strip()
        if not command:
            return QualityGateResult(
                status="not_configured",
                head_sha=self._head_sha(repo_path),
                command="",
            )

        # Serialize only identical evidence keys. Different exact heads must
        # be able to run concurrently so a replacement generation never waits
        # behind (or shares state with) an obsolete gate.
        try:
            observed_head = self._head_sha(repo_path)
            head_sha = (
                self._resolve_commit(repo_path, expected_head_sha)
                if expected_head_sha
                else observed_head
            )
            if expected_head_sha and observed_head != head_sha:
                return QualityGateResult(
                    status="stale_head",
                    head_sha=observed_head,
                    command=command,
                    output_tail=(
                        f"Expected task head {head_sha}, but worktree is "
                        f"at {observed_head}."
                    ),
                )
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
        with self._key_lock(key):
            try:
                with self._lock:
                    entries = self._load()
            except OSError:
                entries = {}
            cached = entries.get(key)
            if isinstance(cached, dict) and cached.get("status"):
                cached_status = str(cached["status"])
                # On forced retry, skip cache for failed/timed_out/error.
                # Reuse passed results regardless of retry_forced flag.
                if retry_forced and cached_status in {"failed", "timed_out", "error"}:
                    # Fall through to re-execute instead of returning cached result
                    pass
                else:
                    return QualityGateResult(
                        status=cached_status,
                        head_sha=head_sha,
                        command=command,
                        duration_seconds=float(cached.get("duration_seconds", 0) or 0),
                        output_tail=str(cached.get("output_tail", "") or ""),
                        cached=True,
                    )

            started = time.monotonic()
            process: subprocess.Popen[str] | None = None
            snapshot: Path | None = None
            monitor_stop = threading.Event()
            monitor: threading.Thread | None = None
            try:
                snapshot = self._create_snapshot(repo_path, head_sha)
                if self._head_sha(str(snapshot)) != head_sha:
                    return QualityGateResult(
                        status="stale_head",
                        head_sha=head_sha,
                        command=command,
                        output_tail="Quality gate snapshot changed before spawn.",
                    )
                process = subprocess.Popen(  # noqa: S602 - operator-owned command
                    command,
                    cwd=snapshot,
                    env=agent_environment(),
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    start_new_session=True,
                )
                # Track process group for graceful shutdown cleanup
                with self._processes_lock:
                    owned_generation = (
                        str(generation)
                        if generation is not None
                        else f"pid:{process.pid}"
                    )
                    self._active_processes[process.pid] = process
                    self._active_generations[process.pid] = owned_generation
                    self._active_snapshots[process.pid] = snapshot

                if is_current is not None:
                    def _monitor_gate_authority() -> None:
                        while not monitor_stop.wait(0.1):
                            try:
                                current = bool(is_current())
                            except Exception as exc:  # noqa: BLE001
                                logger.warning(
                                    "Quality gate authority check failed: %s",
                                    exc,
                                )
                                current = False
                            if not current:
                                self.cancel_generation(owned_generation)
                                return

                    monitor = threading.Thread(
                        target=_monitor_gate_authority,
                        name=f"quality-gate-watch-{process.pid}",
                        daemon=True,
                    )
                    monitor.start()
                stdout, stderr = process.communicate(timeout=self.timeout_seconds)
                duration = time.monotonic() - started
                combined = "\n".join(
                    part for part in (stdout, stderr) if part
                )
                output_tail = combined.encode("utf-8", errors="replace")[
                    -self.output_tail_bytes :
                ].decode("utf-8", errors="replace")
                with self._processes_lock:
                    interrupted = bool(
                        getattr(process, "_oompah_interrupted", False)
                    )
                    self._active_processes.pop(process.pid, None)
                if interrupted:
                    return QualityGateResult(
                        status="interrupted",
                        head_sha=head_sha,
                        command=command,
                        duration_seconds=duration,
                        output_tail=output_tail,
                    )
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
                assert process is not None
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except OSError:
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
                with self._processes_lock:
                    interrupted = bool(
                        getattr(process, "_oompah_interrupted", False)
                    )
                    self._active_processes.pop(process.pid, None)
                if interrupted:
                    return QualityGateResult(
                        status="interrupted",
                        head_sha=head_sha,
                        command=command,
                        duration_seconds=duration,
                        output_tail=combined[-self.output_tail_bytes :],
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
            finally:
                monitor_stop.set()
                if monitor is not None and monitor is not threading.current_thread():
                    monitor.join(timeout=1)
                if process is not None:
                    with self._processes_lock:
                        self._active_processes.pop(process.pid, None)
                        self._active_generations.pop(process.pid, None)
                        self._active_snapshots.pop(process.pid, None)
                if snapshot is not None:
                    self._remove_snapshot(repo_path, snapshot)

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
