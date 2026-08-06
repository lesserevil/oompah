"""Persistent, single-flight quality gates for review-ready branch heads."""

from __future__ import annotations

import hashlib
from importlib import metadata
import json
import logging
import math
import os
import re
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Callable
from urllib.parse import unquote, urlparse

from oompah.validation_resource_lease import (
    ValidationLeaseCancelled,
    ValidationLeaseError,
    ValidationLeaseOwner,
    ValidationResourceLease,
)

logger = logging.getLogger(__name__)

_EVIDENCE_VERSION = 2
_OOMPAH_652_SAFETY_HEAD = "ec0ec7d89fb8804571fcf7e780558e6d979b73ea"

_SANDBOX_RUN_ROOT = Path("/oompah-gate")


class _SandboxUnavailable(RuntimeError):
    """Raised when the operator cannot create the required OS boundary."""


class _TrustedRuntimeCorruption(RuntimeError):
    """Raised when the operator's installed source mapping is not trusted."""


def _declared_editable_oompah_source() -> Path | None:
    """Return the declared local source of the trusted editable install.

    The source is read from the trusted interpreter's distribution metadata,
    not from candidate files.  A missing source directory is returned as a
    path too, allowing the gate to distinguish a poisoned mapping from a
    package that was installed non-editably.
    """
    try:
        direct_url = metadata.distribution("oompah").read_text("direct_url.json")
    except (metadata.PackageNotFoundError, OSError):
        return None
    if not direct_url:
        return None
    try:
        install_metadata = json.loads(direct_url)
    except json.JSONDecodeError:
        return None
    if not isinstance(install_metadata, dict):
        return None
    directory_info = install_metadata.get("dir_info")
    if not isinstance(directory_info, dict) or directory_info.get("editable") is not True:
        return None
    source_url = install_metadata.get("url")
    if not isinstance(source_url, str):
        return None
    try:
        parsed = urlparse(source_url)
    except ValueError:
        return None
    if parsed.scheme != "file" or parsed.netloc not in {"", "localhost"}:
        return None
    try:
        return Path(unquote(parsed.path)).resolve(strict=False)
    except OSError:
        return None


def _editable_oompah_source() -> Path | None:
    """Return an existing local editable source, for runtime projection."""
    source = _declared_editable_oompah_source()
    return source if source is not None and source.is_dir() else None


def _validate_trusted_runtime_source(
    runtime_prefix: Path,
    candidate_snapshot: Path,
) -> Path | None:
    """Validate the editable source visible to the trusted runtime.

    A normal operator install maps ``<service-checkout>/.venv`` back to its
    sibling checkout (or another deployed package checkout when the venv is
    stored separately).  The only other acceptable mapping is the immutable
    snapshot itself, useful when a gate is deliberately launched from a
    candidate-projected runtime.  Any other worktree indicates that a task
    setup command rewrote the service environment, so fail as executor
    corruption before candidate code runs.
    """
    actual = _declared_editable_oompah_source()
    if actual is None:
        return None
    expected_roots = {
        runtime_prefix.parent.resolve(strict=False),
        # In a normal service process this is the deployed package checkout.
        # Keeping it as an allowed root also makes the check correct when the
        # operator stores the venv outside the checkout.
        Path(__file__).resolve().parent.parent,
    }
    candidate = candidate_snapshot.resolve(strict=False)
    if actual not in expected_roots | {candidate}:
        raise _TrustedRuntimeCorruption(
            "trusted editable source mapping is inconsistent: "
            f"expected one of {sorted(str(path) for path in expected_roots)} "
            f"or immutable candidate {candidate}; "
            f"actual {actual}. Repair or replace the service test runtime "
            "before rerunning the branch gate."
        )
    return actual


@dataclass(frozen=True)
class QualityGateResult:
    """Outcome of checking one exact branch head with one exact command."""

    status: str
    head_sha: str
    command: str
    duration_seconds: float = 0.0
    output_tail: str = ""
    cached: bool = False
    recorded_at: float | None = None

    @property
    def passed(self) -> bool:
        return self.status in {"passed", "not_configured"}


@dataclass(frozen=True)
class AuditorQualityEvidenceProof:
    """Proof that an auditor ran the configured gate on the exact candidate.

    Every compatibility dimension used by the normal evidence key is explicit,
    and the independently observed detached-worktree head/fingerprint prevent a
    caller from relabeling a successful but different auditor command.
    """

    repo_identity: str
    target_branch: str
    work_branch: str
    head_sha: str
    workspace_head_sha: str
    command: str
    configured_command: str
    evidence_fingerprint: str
    expected_evidence_fingerprint: str
    detached_workspace: bool


@dataclass(frozen=True)
class QualityGateOwner:
    """Exact authority that owns one branch-quality gate attempt.

    A process generation is not sufficient ownership evidence on its own: a
    stale caller can otherwise cancel a different task that happens to reuse
    the same generation value.  Keep the project, task, exact head, and
    authority generation together so cancellation and observability can make
    the same comparison.
    """

    project_id: str
    task_id: str
    head_sha: str
    authority_generation: str

    @property
    def complete(self) -> bool:
        return all(
            str(value or "").strip()
            for value in (
                self.project_id,
                self.task_id,
                self.head_sha,
                self.authority_generation,
            )
        )

    @property
    def key(self) -> str:
        """Return a collision-resistant in-process identity for this owner."""
        return "\0".join(
            (
                str(self.project_id),
                str(self.task_id),
                str(self.head_sha).strip().lower(),
                str(self.authority_generation),
            )
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "project_id": str(self.project_id),
            "task_id": str(self.task_id),
            "head_sha": str(self.head_sha),
            "authority_generation": str(self.authority_generation),
        }


@dataclass
class _KeyLockEntry:
    """One in-process single-flight lock plus its current users."""

    lock: threading.Lock
    users: int = 0


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
    _active_owners: dict[int, QualityGateOwner | None] = {}
    _active_snapshots: dict[int, Path] = {}
    # Durable tombstones for cancelled generations: set before the gate
    # spawns so that pre-spawn authority withdrawals (during snapshot
    # creation or between Popen and registration) are guaranteed to stop
    # the gate even if the process is not yet in _active_generations.
    # Protected by _processes_lock.  A tombstone is retained until every
    # caller that had entered ``run`` for that generation has left it.  This
    # is deliberately not a per-call finally cleanup: another same-generation
    # caller may still be waiting on the evidence-key lock.
    _cancelled_generations: set[str] = set()
    _cancelled_owner_keys: set[str] = set()
    _generation_run_counts: dict[str, int] = {}
    _owner_run_counts: dict[str, int] = {}
    # Cancel-before-spawn has no running caller to release the tombstone. Keep
    # those records in LRU order so abandoned generations cannot grow this
    # process-wide registry without bound.
    _cancelled_generation_order: dict[str, None] = {}
    _cancelled_owner_order: dict[str, None] = {}
    _MAX_CANCELLED_GENERATIONS = 1024
    _processes_lock = threading.Lock()

    def __init__(
        self,
        state_path: str,
        *,
        timeout_seconds: int = 3600,
        output_tail_bytes: int = 16 * 1024,
        safety_head: str = _OOMPAH_652_SAFETY_HEAD,
        sandbox_launcher: Callable[[str, str, Path], list[str]] | None = None,
        validation_lease: ValidationResourceLease | None = None,
    ) -> None:
        self.state_path = Path(state_path)
        self.timeout_seconds = max(int(timeout_seconds), 1)
        self.output_tail_bytes = max(int(output_tail_bytes), 1024)
        self.safety_head = safety_head
        self._sandbox_launcher = sandbox_launcher or self._sandbox_command
        self.validation_lease = validation_lease
        self._lock = threading.Lock()
        self._key_locks: dict[str, _KeyLockEntry] = {}

    @classmethod
    def _terminate_active_processes(
        cls,
        *,
        generation: str | None = None,
        owner: QualityGateOwner | None = None,
    ) -> int:
        """Terminate active process groups owned by *generation* or *owner*.

        When *generation* is given, the generation is also added to
        _cancelled_generations so that gates not yet spawned (during snapshot
        creation or between Popen and registration) also see the cancellation
        on their next barrier check.

        Keeping this operation centralized makes shutdown and task-specific
        cancellation use the same process-group and snapshot cleanup rules.
        """
        with cls._processes_lock:
            processes = [
                (pid, process)
                for pid, process in cls._active_processes.items()
                if (
                    generation is None
                    and owner is None
                )
                or (
                    owner is not None
                    and cls._active_owners.get(pid) is not None
                    and cls._active_owners[pid].key == owner.key
                )
                or (
                    owner is None
                    and generation is not None
                    and cls._active_owners.get(pid) is None
                    and cls._active_generations.get(pid) == generation
                )
            ]
            if owner is not None and not processes:
                logger.warning(
                    "Quality gate cancellation owner matched no active gate: "
                    "requested=%s active=%s",
                    owner.to_dict(),
                    [
                        active_owner.to_dict()
                        for active_owner in cls._active_owners.values()
                        if active_owner is not None
                    ],
                )
            for _pid, process in processes:
                # The run thread uses this marker to return a non-cached
                # interruption instead of recording a false CI failure.
                setattr(process, "_oompah_interrupted", True)
            # Record a durable tombstone so that gates currently between
            # pre-spawn barrier checks (snapshot creation, Popen-to-
            # registration window) also stop on their next check.
            if owner is not None:
                cls._mark_owner_cancelled_locked(owner)
            elif generation is not None:
                cls._mark_generation_cancelled_locked(generation)

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
                cls._active_owners.pop(pid, None)
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
    def cancel_generation(
        cls,
        generation: str | None = None,
        *,
        owner: QualityGateOwner | None = None,
        project_id: str | None = None,
        task_id: str | None = None,
        head_sha: str | None = None,
        authority_generation: str | None = None,
    ) -> int:
        """Cancel one exact owner, or a legacy unowned generation.

        Sets a durable tombstone so that gates currently between pre-spawn
        barrier checks (during snapshot creation or between Popen and
        registration) also stop when they next reach a check point.
        """
        if owner is not None or any(
            value is not None
            for value in (project_id, task_id, head_sha, authority_generation)
        ):
            if owner is None:
                owner = QualityGateOwner(
                    project_id=str(project_id or ""),
                    task_id=str(task_id or ""),
                    head_sha=str(head_sha or ""),
                    authority_generation=str(
                        authority_generation or generation or ""
                    ),
                )
            return cls.cancel_owner(owner)
        if not str(generation or "").strip():
            logger.warning(
                "Rejected generationless quality gate cancellation request"
            )
            return 0
        return cls._terminate_active_processes(generation=str(generation))

    @classmethod
    def cancel_owner(
        cls,
        owner: QualityGateOwner | None = None,
        *,
        project_id: str | None = None,
        task_id: str | None = None,
        head_sha: str | None = None,
        authority_generation: str | None = None,
    ) -> int:
        """Cancel one exact project/task/head/authority gate owner.

        Missing ownership evidence is rejected rather than interpreted as a
        broadcast.  Full orchestrator shutdown must use
        :meth:`cleanup_active_processes`, the only unrestricted cleanup path.
        """
        if owner is None:
            owner = QualityGateOwner(
                project_id=str(project_id or ""),
                task_id=str(task_id or ""),
                head_sha=str(head_sha or ""),
                authority_generation=str(authority_generation or ""),
            )
        if not owner.complete:
            logger.warning(
                "Rejected quality gate cancellation without exact ownership: %s",
                owner.to_dict(),
            )
            return 0
        return cls._terminate_active_processes(owner=owner)

    @classmethod
    def active_state(cls) -> list[dict[str, object]]:
        """Return active gate ownership for health/state consumers."""
        with cls._processes_lock:
            rows: list[dict[str, object]] = []
            for pid in sorted(cls._active_processes):
                owner = cls._active_owners.get(pid)
                row: dict[str, object] = {
                    "pid": pid,
                    "status": "running",
                    "generation": cls._active_generations.get(pid),
                }
                row.update(
                    owner.to_dict()
                    if owner is not None
                    else {
                        "project_id": None,
                        "task_id": None,
                        "head_sha": None,
                        "authority_generation": None,
                    }
                )
                rows.append(row)
            return rows

    @classmethod
    def _generation_is_cancelled(
        cls,
        generation: str,
        owner_key: str | None = None,
    ) -> bool:
        """Return True when a generation or exact owner was tombstoned."""
        with cls._processes_lock:
            if owner_key is not None:
                return owner_key in cls._cancelled_owner_keys
            return generation in cls._cancelled_generations

    @classmethod
    def _mark_generation_cancelled_locked(cls, generation: str) -> None:
        """Tombstone *generation* while holding ``_processes_lock``."""
        cls._cancelled_generations.add(generation)
        cls._cancelled_generation_order.pop(generation, None)
        cls._cancelled_generation_order[generation] = None
        cls._prune_cancelled_generations_locked()

    @classmethod
    def _prune_cancelled_generations_locked(cls) -> None:
        """Bound inactive cancel-before-spawn tombstones by LRU age."""
        while len(cls._cancelled_generation_order) > cls._MAX_CANCELLED_GENERATIONS:
            oldest = next(iter(cls._cancelled_generation_order))
            if oldest not in cls._cancelled_generations:
                cls._cancelled_generation_order.pop(oldest, None)
                continue
            if cls._generation_run_counts.get(oldest, 0) > 0:
                # Active/waiting callers must keep their cancellation fence.
                # Move it behind inactive candidates and stop if all entries
                # are active; normal completion will release it later.
                cls._cancelled_generation_order.pop(oldest)
                cls._cancelled_generation_order[oldest] = None
                if all(
                    cls._generation_run_counts.get(generation, 0) > 0
                    for generation in cls._cancelled_generation_order
                ):
                    return
                continue
            cls._cancelled_generation_order.pop(oldest, None)
            cls._cancelled_generations.discard(oldest)

    @classmethod
    def _mark_owner_cancelled_locked(cls, owner: QualityGateOwner) -> None:
        """Tombstone one exact owner while holding ``_processes_lock``."""
        key = owner.key
        cls._cancelled_owner_keys.add(key)
        cls._cancelled_owner_order.pop(key, None)
        cls._cancelled_owner_order[key] = None
        while len(cls._cancelled_owner_order) > cls._MAX_CANCELLED_GENERATIONS:
            oldest = next(iter(cls._cancelled_owner_order))
            if cls._owner_run_counts.get(oldest, 0) > 0:
                cls._cancelled_owner_order.pop(oldest, None)
                cls._cancelled_owner_order[oldest] = None
                if all(
                    cls._owner_run_counts.get(item, 0) > 0
                    for item in cls._cancelled_owner_order
                ):
                    return
                continue
            cls._cancelled_owner_order.pop(oldest, None)
            cls._cancelled_owner_keys.discard(oldest)

    @classmethod
    def _register_generation(cls, generation: str) -> None:
        """Record a caller before it can wait behind a single-flight lock."""
        with cls._processes_lock:
            cls._generation_run_counts[generation] = (
                cls._generation_run_counts.get(generation, 0) + 1
            )

    @classmethod
    def _register_owner(cls, owner: QualityGateOwner) -> None:
        """Record an exact owner before waiting on a single-flight lock."""
        with cls._processes_lock:
            cls._owner_run_counts[owner.key] = (
                cls._owner_run_counts.get(owner.key, 0) + 1
            )

    @classmethod
    def _release_generation(cls, generation: str) -> None:
        """Release one caller and retire a cancelled generation when it is idle."""
        with cls._processes_lock:
            remaining = cls._generation_run_counts.get(generation, 0) - 1
            if remaining > 0:
                cls._generation_run_counts[generation] = remaining
                return
            cls._generation_run_counts.pop(generation, None)
            cls._cancelled_generations.discard(generation)
            cls._cancelled_generation_order.pop(generation, None)

    @classmethod
    def _release_owner(cls, owner: QualityGateOwner) -> None:
        """Release one exact owner and retire its cancellation tombstone."""
        with cls._processes_lock:
            key = owner.key
            remaining = cls._owner_run_counts.get(key, 0) - 1
            if remaining > 0:
                cls._owner_run_counts[key] = remaining
                return
            cls._owner_run_counts.pop(key, None)
            cls._cancelled_owner_keys.discard(key)
            cls._cancelled_owner_order.pop(key, None)

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

    def _verify_isolation_contract(
        self,
        repo_path: str,
        head_sha: str,
        *,
        require_source_head_match: bool,
    ) -> tuple[bool, str]:
        """Verify the candidate is based on the deployed lifecycle contract.

        The quality gate runs in a disposable worktree. Candidate code cannot be trusted
        to implement its own containment boundary. A same-UID process with access to the
        source tree can read absolute canonical paths, connect to localhost:8090, or
        signal the operator service regardless of environment variables or marker strings.

        The OS sandbox is the containment boundary; the candidate is expressly
        allowed to evolve its Makefile and test runner.  This preflight only
        establishes that a recovered branch has been rebased onto the durable,
        operator-configured lifecycle base.  All checks happen before Popen,
        so a rejected candidate command never gets a chance to inspect or
        signal the operator service.

        Returns:
            (is_compliant, reason) — True if the branch contains OOMPAH-652 safety head
            in its ancestry, False if the branch needs rebase.
        """
        safety_head = self.safety_head
        if not isinstance(safety_head, str) or len(safety_head) != 40:
            return False, "Configured lifecycle safety head is not a full commit SHA"
        try:
            int(safety_head, 16)
        except ValueError:
            return False, "Configured lifecycle safety head is not a full commit SHA"

        # Verify git repository exists and is valid
        repo_path_obj = Path(repo_path)
        if not (repo_path_obj / ".git").exists():
            return False, "Not a git repository (required for ancestry verification)"

        try:
            # Check the exact candidate commit, rather than the source
            # checkout's HEAD.  Review gates may archive a verified remote
            # commit directly from the managed repository when the original
            # task checkout no longer exists.
            result = subprocess.run(
                ["git", "merge-base", "--is-ancestor", safety_head, head_sha],
                cwd=repo_path,
                capture_output=True,
                timeout=5,
            )
            # merge-base --is-ancestor exits 0 if ancestor exists, non-zero otherwise.
            if result.returncode == 0 and require_source_head_match:
                dirty = subprocess.run(
                    [
                        "git",
                        "diff",
                        "--quiet",
                        "HEAD",
                        "--",
                    ],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if dirty.returncode not in {0, 1}:
                    return False, "Cannot inspect quality-gate worktree state"
                if dirty.returncode == 1:
                    return (
                        False,
                        "The quality-gate worktree has uncommitted changes. "
                        "Commit and push the repair before rerunning the exact "
                        "review-head gate.",
                    )
                return True, ""
            if result.returncode == 0:
                # The candidate will be produced solely by ``git archive`` of
                # ``head_sha``.  Untracked files and changes in the managed
                # repository's unrelated checkout cannot enter that clean,
                # immutable snapshot.
                return True, ""
            return (
                False,
                f"Branch does not contain the deployed OOMPAH-652 isolation "
                f"contract (commit {safety_head}). This branch was likely "
                "created before the safety prerequisite was merged. Rebase "
                "to the current base before rerunning the gate; see "
                "OOMPAH-652 and OOMPAH-655 for lifecycle isolation details.",
            )
        except subprocess.TimeoutExpired:
            return False, "Git ancestry check timed out (git repository may be corrupted)"
        except OSError as exc:
            return False, f"Cannot verify git ancestry: {exc}"

    @staticmethod
    def _gate_run_root() -> Path:
        """Create an operator-owned, private root for one candidate command."""
        root = Path(tempfile.mkdtemp(prefix="oompah-quality-gate-"))
        os.chmod(root, 0o700)
        for relative in ("home", "tmp", "cache", "config", "data", "lifecycle"):
            path = root / relative
            path.mkdir(mode=0o700)
        return root

    @staticmethod
    def _cleanup_gate_run_root(root: Path) -> None:
        """Remove only a root created by :meth:`_gate_run_root`."""
        try:
            resolved = root.resolve(strict=False)
            temp_root = Path(tempfile.gettempdir()).resolve()
            if (
                resolved.parent != temp_root
                or not resolved.name.startswith("oompah-quality-gate-")
                or root.is_symlink()
                or not root.exists()
                or root.stat().st_uid != os.getuid()
            ):
                logger.warning("Refusing to remove unexpected gate root %s", root)
                return
            shutil.rmtree(root)
        except FileNotFoundError:
            pass
        except OSError as exc:
            logger.warning("Failed to clean quality gate root %s: %s", root, exc)

    @staticmethod
    def _snapshot_candidate_worktree(
        repo_path: str,
        run_root: Path,
        head_sha: str = "HEAD",
    ) -> Path:
        """Archive the exact candidate head into a disposable gate workspace.

        A candidate command must never receive a writable bind of the service's
        live worktree.  ``git archive`` takes only tracked files at ``head_sha``;
        this excludes operator .env/PID/log files and all other untracked
        state.  The archive is extracted with tar's data filter so a malicious
        symlink cannot escape the private run root.
        """
        snapshot = run_root / "workspace"
        archive_path = run_root / "candidate.tar"
        try:
            archive = subprocess.run(
                [
                    "git",
                    "archive",
                    "--format=tar",
                    f"--output={archive_path}",
                    head_sha,
                ],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise _SandboxUnavailable(
                f"cannot create an immutable candidate snapshot: {exc}"
            ) from exc
        if archive.returncode != 0:
            detail = (archive.stderr or archive.stdout).strip()[-500:]
            raise _SandboxUnavailable(
                "cannot create an immutable candidate snapshot"
                + (f": {detail}" if detail else "")
            )
        try:
            snapshot.mkdir(mode=0o700)
            with tarfile.open(archive_path) as candidate_archive:
                for member in candidate_archive:
                    member_path = PurePosixPath(member.name)
                    if (
                        not member_path.parts
                        or member_path.is_absolute()
                        or ".." in member_path.parts
                        or member.isdev()
                        or member.isfifo()
                    ):
                        raise tarfile.TarError(
                            f"unsafe member in candidate archive: {member.name!r}"
                        )
                    if member.issym() or member.islnk():
                        link_path = PurePosixPath(member.linkname)
                        if link_path.is_absolute() or ".." in link_path.parts:
                            raise tarfile.TarError(
                                "unsafe link in candidate archive: "
                                f"{member.name!r} -> {member.linkname!r}"
                            )
                    # Oompah supports Python 3.11, whose early releases did
                    # not accept ``filter``.  We apply the same validation
                    # above, then use an explicit compatibility filter where
                    # the newer tarfile API is available.
                    try:
                        candidate_archive.extract(
                            member, path=snapshot, filter="fully_trusted"
                        )
                    except TypeError:
                        candidate_archive.extract(member, path=snapshot)
            archive_path.unlink()
            # Preserve exact-revision tests without exposing the service's
            # live object database, worktree metadata, remotes, or hooks.  A
            # shallow local fetch copies only the candidate commit into this
            # disposable repository; reset populates the index but never
            # replaces the archive contents validated above.
            commands = (
                ("git", "init", "--quiet"),
                (
                    "git",
                    "fetch",
                    "--quiet",
                    "--depth=1",
                    "--no-tags",
                    str(Path(repo_path).resolve()),
                    str(head_sha),
                ),
            )
            for command in commands:
                completed = subprocess.run(
                    command,
                    cwd=snapshot,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if completed.returncode != 0:
                    detail = (completed.stderr or completed.stdout).strip()[-500:]
                    raise tarfile.TarError(
                        "cannot create private exact-head Git metadata"
                        + (f": {detail}" if detail else "")
                    )
            private_head = subprocess.run(
                ["git", "rev-parse", "FETCH_HEAD"],
                cwd=snapshot,
                capture_output=True,
                text=True,
                check=True,
                timeout=15,
            ).stdout.strip()
            for command in (
                ("git", "update-ref", "refs/heads/quality-gate", private_head),
                ("git", "symbolic-ref", "HEAD", "refs/heads/quality-gate"),
                ("git", "reset", "--mixed", "--quiet", private_head),
            ):
                subprocess.run(
                    command,
                    cwd=snapshot,
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=15,
                )
            (snapshot / ".git" / "FETCH_HEAD").unlink(missing_ok=True)
        except (OSError, tarfile.TarError) as exc:
            raise _SandboxUnavailable(
                f"cannot prepare an immutable candidate snapshot: {exc}"
            ) from exc
        except subprocess.SubprocessError as exc:
            raise _SandboxUnavailable(
                f"cannot prepare private exact-head Git metadata: {exc}"
            ) from exc
        return snapshot

    @staticmethod
    def _quality_gate_environment(run_root: Path) -> dict[str, str]:
        """Build the complete server-owned lifecycle environment for a gate."""
        # Do not inherit the server environment wholesale.  In particular,
        # inherited OOMPAH/PIP/UV variables can point at operator state even
        # when the corresponding filesystem paths are hidden.  Keep only
        # display/locale settings plus a path backed by the sandbox's /usr.
        environment = {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin"}
        for key in ("LANG", "LC_ALL", "LC_CTYPE", "TERM"):
            value = os.environ.get(key)
            if value:
                environment[key] = value
        # The host root is bound at _SANDBOX_RUN_ROOT.  Export only that
        # sandbox-visible path: a host tempfile path would be inaccessible
        # after /tmp and /home are hidden by bubblewrap.
        private_tmp = _SANDBOX_RUN_ROOT / "tmp"
        private_lifecycle = _SANDBOX_RUN_ROOT / "lifecycle"
        private_home = _SANDBOX_RUN_ROOT / "home"
        # Bind-and-close allocation is the portable interface available to the
        # existing Makefile contract.  The candidate still cannot select the
        # operator's configured port because this value is server-generated.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            private_port = str(listener.getsockname()[1])

        environment.update(
            {
                "OOMPAH_PYTEST_GATE": "1",
                "OOMPAH_PYTEST_RUN_ROOT": str(_SANDBOX_RUN_ROOT),
                "OOMPAH_PYTEST_TEMP_ROOT": str(private_tmp),
                "OOMPAH_TEMP_ROOT": str(private_tmp),
                "OOMPAH_TEST_SERVER_PORT": private_port,
                "OOMPAH_SERVER_PORT": private_port,
                "OOMPAH_TEST_PID_FILE": str(private_lifecycle / ".oompah.pid"),
                "OOMPAH_TEST_PID_META_FILE": str(
                    private_lifecycle / ".oompah.pid.meta"
                ),
                "HOME": str(private_home),
                "TMPDIR": str(private_tmp),
                "TMP": str(private_tmp),
                "TEMP": str(private_tmp),
                "XDG_CACHE_HOME": str(_SANDBOX_RUN_ROOT / "cache"),
                "XDG_CONFIG_HOME": str(_SANDBOX_RUN_ROOT / "config"),
                "XDG_DATA_HOME": str(_SANDBOX_RUN_ROOT / "data"),
                "PYTHONPYCACHEPREFIX": str(
                    _SANDBOX_RUN_ROOT / "cache" / "pycache"
                ),
            }
        )
        return environment

    @staticmethod
    def _sandbox_command(
        command: str,
        repo_path: str,
        run_root: Path,
    ) -> list[str]:
        """Return a bubblewrap command with host lifecycle state hidden.

        The candidate command runs in a private mount, PID, and network
        namespace.  The repository and one operator-created run root are the
        only task-owned paths made visible.  If bubblewrap or unprivileged
        namespaces are unavailable, the caller fails closed before starting
        candidate code.
        """
        bubblewrap = shutil.which("bwrap")
        if not bubblewrap:
            raise _SandboxUnavailable(
                "bubblewrap is not installed; refusing to run an unsandboxed gate"
            )

        probe = subprocess.run(
            [
                bubblewrap,
                "--die-with-parent",
                "--new-session",
                "--unshare-user",
                "--unshare-pid",
                "--unshare-net",
                "--cap-add",
                "CAP_NET_ADMIN",
                "--proc",
                "/proc",
                "--dev",
                "/dev",
                "--ro-bind",
                "/usr",
                "/usr",
                "--symlink",
                "usr/bin",
                "/bin",
                # The ELF dynamic loader lives at /lib64/ld-linux-*.so on many
                # distributions where /lib64 -> usr/lib64.  Without this
                # symlink in the probe namespace, execvp /bin/sh fails with
                # "No such file or directory" even though /usr is bound.
                "--symlink",
                "usr/lib64",
                "/lib64",
                "/bin/sh",
                "-c",
                # Verify that /bin/sh runs and the network namespace was
                # created (lo exists).  Do not require ip link set to
                # succeed: on kernel 6.x the loopback carries
                # netns-immutable and starts UP without an explicit set,
                # so ip link set lo up returns EPERM even though the
                # interface is already functional.
                "ip link show lo >/dev/null 2>&1",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if probe.returncode != 0:
            detail = (probe.stderr or probe.stdout).strip()[-500:]
            raise _SandboxUnavailable(
                "bubblewrap cannot create the required OS namespaces"
                + (f": {detail}" if detail else "")
            )

        repo = Path(repo_path).resolve()
        if not repo.is_dir() or repo.is_symlink():
            raise _SandboxUnavailable("quality-gate worktree is not a real directory")

        # Start from an empty root rather than a read-only host root.  Candidate
        # code receives only a disposable source snapshot, its private gate
        # state, and the runtime needed to execute the configured command.
        args = [
            bubblewrap,
            "--die-with-parent",
            "--new-session",
            "--unshare-user",
            "--unshare-pid",
            "--unshare-net",
            "--cap-add",
            "CAP_NET_ADMIN",
            "--tmpfs",
            "/",
            "--dir",
            "/usr",
            "--ro-bind",
            "/usr",
            "/usr",
            "--symlink",
            "usr/bin",
            "/bin",
            "--symlink",
            "usr/sbin",
            "/sbin",
            "--symlink",
            "usr/lib",
            "/lib",
            "--symlink",
            "usr/lib64",
            "/lib64",
            "--dir",
            "/dev",
            "--dev",
            "/dev",
            "--dir",
            "/proc",
            "--proc",
            "/proc",
            "--dir",
            "/tmp",
            "--tmpfs",
            "/tmp",
            "--dir",
            "/var",
            "--dir",
            "/var/tmp",
            "--tmpfs",
            "/var/tmp",
            "--dir",
            "/home",
            "--tmpfs",
            "/home",
        ]

        # bwrap's bind destinations must already exist.  Do not inherit an
        # arbitrary directory tree simply to make the worktree path available.
        created_dirs = {
            Path("/"),
            Path("/usr"),
            Path("/dev"),
            Path("/proc"),
            Path("/tmp"),
            Path("/var"),
            Path("/var/tmp"),
            Path("/home"),
        }

        def add_destination(path: Path) -> None:
            current = Path("/")
            for part in path.parts[1:]:
                current /= part
                if current not in created_dirs:
                    args.extend(["--dir", str(current)])
                    created_dirs.add(current)

        # Make's trusted test virtualenv comes from the server process, not the
        # candidate checkout.  It is mounted read-only in the snapshot.  Its
        # Python base installation is also mapped at the path recorded by the
        # virtualenv, without exposing the rest of the operator's home.
        runtime_binds: list[str] = []
        runtime_prefix = Path(sys.prefix).resolve()
        runtime_python = runtime_prefix / "bin" / "python"
        if not runtime_python.exists():
            raise _TrustedRuntimeCorruption(
                "trusted quality-gate Python is unavailable at "
                f"{runtime_python}; replace the operator test runtime before "
                "rerunning the branch gate."
            )
        declared_editable_source = _validate_trusted_runtime_source(
            runtime_prefix, repo
        )
        if runtime_python.exists():
            add_destination(repo / ".venv")
            base_prefix = Path(sys.base_prefix).resolve()
            python_destination = base_prefix
            try:
                link_target = os.readlink(runtime_python)
            except OSError:
                link_target = ""
            if link_target.startswith("/"):
                python_destination = Path(link_target).parent.parent
            add_destination(python_destination)
            runtime_checkout = runtime_prefix.parent
            if runtime_prefix != base_prefix and runtime_checkout != repo:
                # Editable console launchers retain the trusted environment's
                # absolute shebang and source path.  Map those paths to the
                # candidate snapshot and the same read-only runtime, never to
                # the operator checkout, so packaging/CLI tests exercise this
                # exact head without mutating the trusted virtualenv.
                add_destination(runtime_checkout)
                add_destination(runtime_prefix)
                runtime_binds.extend(
                    [
                        "--bind",
                        str(repo),
                        str(runtime_checkout),
                        "--ro-bind",
                        str(runtime_prefix),
                        str(runtime_prefix),
                    ]
                )
            # An editable install may point at a deployed checkout stored
            # separately from the venv.  Project that declared source to the
            # immutable candidate too, so console scripts cannot import an
            # older service/task checkout.  The source mapping was validated
            # above before this bind is constructed.
            editable_source = _editable_oompah_source() or declared_editable_source
            if editable_source and editable_source not in {
                runtime_checkout,
                repo,
            }:
                add_destination(editable_source)
                runtime_binds.extend(
                    [
                        "--bind",
                        str(repo),
                        str(editable_source),
                    ]
                )
            runtime_binds.extend(
                [
                    "--ro-bind",
                    str(runtime_prefix),
                    str(repo / ".venv"),
                    "--ro-bind",
                    str(base_prefix),
                    str(python_destination),
                ]
            )
            # Overlay writable sentinel files over the read-only venv mount so
            # Make skips uv-based setup steps inside the gate.  Git archive
            # stamps every file in the snapshot with the commit timestamp,
            # which can be newer than the sentinel files in the ro-mounted
            # venv; Make then tries to rebuild them by running uv, which is
            # unavailable in the sandbox PATH.  Creating fresh sentinels in
            # run_root and binding them over the venv paths ensures Make sees
            # setup as current without any uv invocation or write access.
            for _sentinel_name in (".uv-setup", ".uv-test-setup"):
                _writable_sentinel = run_root / _sentinel_name
                _writable_sentinel.touch()
                runtime_binds.extend(
                    [
                        "--bind",
                        str(_writable_sentinel),
                        str(repo / ".venv" / _sentinel_name),
                    ]
                )
            # Also bind the operator venv at its original absolute path so
            # that entry-point scripts (e.g. the ``oompah`` console-script)
            # whose shebangs reference that absolute path can execute inside
            # the sandbox.  Without this, the shebang
            # ``#!/path/to/operator/.venv/bin/python3`` resolves to a path
            # that is not visible in the sandbox, causing subprocess calls to
            # the binary entry point to fail with ENOENT.  The venv is still
            # mounted read-only; no operator state is writable.
            if runtime_prefix != (repo / ".venv").resolve():
                add_destination(runtime_prefix)
                runtime_binds.extend(
                    [
                        "--ro-bind",
                        str(runtime_prefix),
                        str(runtime_prefix),
                    ]
                )

        add_destination(repo)
        add_destination(_SANDBOX_RUN_ROOT)
        args.extend(
            [
                "--bind",
                str(repo),
                str(repo),
                "--bind",
                str(run_root),
                str(_SANDBOX_RUN_ROOT),
                *runtime_binds,
                "--chdir",
                str(repo),
                # bwrap leaves loopback in its default state in the new network
                # namespace.  Attempt to bring it up explicitly for
                # compatibility with older kernels; on kernel 6.x the
                # interface carries netns-immutable and is already UP, so
                # ip link set returns EPERM — ignore the error and proceed.
                "/bin/sh",
                "-c",
                'ip link set lo up 2>/dev/null || true; exec "$@"',
                "oompah-gate-bootstrap",
                "/bin/sh",
                "-c",
                command,
            ]
        )
        return args

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

    @staticmethod
    def _decode_evidence_result(
        entry: object,
        *,
        repo_identity: str,
        target_branch: str,
        work_branch: str,
        head_sha: str,
        command: str,
    ) -> QualityGateResult | None:
        """Decode one exact-key entry or fail closed to a cache miss."""

        if not isinstance(entry, dict):
            return None
        status = str(entry.get("status", "") or "").strip()
        if not status:
            return None
        expected_identity = {
            "repo_identity": repo_identity,
            "target_branch": target_branch,
            "work_branch": work_branch,
            "head_sha": head_sha,
            "command": command,
        }
        for field_name, expected in expected_identity.items():
            actual = str(entry.get(field_name, "") or "").strip()
            if field_name == "head_sha":
                actual = actual.lower()
                expected = expected.lower()
            if actual != expected:
                return None

        raw_recorded_at = entry.get("recorded_at")
        if isinstance(raw_recorded_at, bool):
            return None
        try:
            recorded_at = float(raw_recorded_at)
        except (TypeError, ValueError):
            return None
        if (
            not math.isfinite(recorded_at)
            or recorded_at <= 0
            or recorded_at > time.time()
        ):
            return None

        raw_duration = entry.get("duration_seconds", 0)
        try:
            duration = float(raw_duration or 0)
        except (TypeError, ValueError):
            duration = 0.0
        if not math.isfinite(duration) or duration < 0:
            duration = 0.0
        return QualityGateResult(
            status=status,
            head_sha=head_sha,
            command=command,
            duration_seconds=duration,
            output_tail=str(entry.get("output_tail", "") or ""),
            cached=True,
            recorded_at=recorded_at,
        )

    def record_compatible_auditor_pass(
        self,
        proof: AuditorQualityEvidenceProof,
        *,
        duration_seconds: float = 0.0,
        output_tail: str = "",
    ) -> bool:
        """Persist independently-run auditor evidence only when exactly equal.

        This is deliberately stricter than ordinary cache lookup.  Missing or
        mismatched command, head, branch, repository, fingerprint, or detached
        workspace proof returns ``False`` and leaves the exact gate to run.
        """

        values = (
            proof.repo_identity,
            proof.target_branch,
            proof.work_branch,
            proof.head_sha,
            proof.workspace_head_sha,
            proof.command,
            proof.configured_command,
            proof.evidence_fingerprint,
            proof.expected_evidence_fingerprint,
        )
        if not proof.detached_workspace or not all(
            str(value or "").strip() for value in values
        ):
            return False
        head = proof.head_sha.strip().lower()
        if not re.fullmatch(r"[0-9a-f]{40,64}", head):
            return False
        if proof.workspace_head_sha.strip().lower() != head:
            return False
        command = proof.command.strip()
        if command != proof.configured_command.strip():
            return False
        if (
            proof.evidence_fingerprint.strip()
            != proof.expected_evidence_fingerprint.strip()
        ):
            return False

        key = self._evidence_key(
            repo_identity=proof.repo_identity,
            target_branch=proof.target_branch,
            work_branch=proof.work_branch,
            head_sha=head,
            command=command,
        )
        result = QualityGateResult(
            status="passed",
            head_sha=head,
            command=command,
            duration_seconds=max(float(duration_seconds), 0.0),
            output_tail=str(output_tail or ""),
        )
        with self._key_lock(key):
            self._store_result(
                {},
                key,
                result,
                repo_identity=proof.repo_identity,
                target_branch=proof.target_branch,
                work_branch=proof.work_branch,
            )
        return True

    def lookup(
        self,
        *,
        repo_identity: str,
        target_branch: str,
        work_branch: str,
        head_sha: str,
        command: str,
    ) -> QualityGateResult | None:
        """Return durable evidence for one exact head without executing it.

        Terminal-audit prompt construction must be able to inspect the
        authoritative integration gate without acquiring validation capacity or
        spawning candidate code.  The lookup is deliberately exact-keyed: a
        missing, malformed, different-head, or different-command entry is a
        cache miss and therefore cannot suppress an auditor-requested gate.
        """

        command = str(command or "").strip()
        head = str(head_sha or "").strip().lower()
        if not command or not re.fullmatch(r"[0-9a-f]{40,64}", head):
            return None
        repository = str(repo_identity or "").strip()
        target = str(target_branch or "").strip()
        branch = str(work_branch or "").strip()
        if not repository or not target or not branch:
            return None
        key = self._evidence_key(
            repo_identity=repository,
            target_branch=target,
            work_branch=branch,
            head_sha=head,
            command=command,
        )
        try:
            with self._lock:
                entry = self._load().get(key)
        except OSError:
            return None
        return self._decode_evidence_result(
            entry,
            repo_identity=repository,
            target_branch=target,
            work_branch=branch,
            head_sha=head,
            command=command,
        )

    @contextmanager
    def _key_lock(self, key: str):
        """Yield a single-flight lock and discard it once its last user leaves."""
        with self._lock:
            entry = self._key_locks.get(key)
            if entry is None:
                entry = _KeyLockEntry(lock=threading.Lock())
                self._key_locks[key] = entry
            entry.users += 1
        entry.lock.acquire()
        try:
            yield
        finally:
            entry.lock.release()
            with self._lock:
                entry.users -= 1
                if (
                    entry.users == 0
                    and self._key_locks.get(key) is entry
                ):
                    self._key_locks.pop(key, None)

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
        require_source_head_match: bool = True,
        generation: str | None = None,
        owner: QualityGateOwner | None = None,
        is_current: Callable[[], bool] | None = None,
    ) -> QualityGateResult:
        """Return passing evidence or execute the configured full check.

        When retry_forced=True, bypasses cache for failed/timed_out/error
        results and re-executes. Passed results remain cached and reusable.

        ``owner`` binds cancellation to the exact project/task/head and
        authority generation.  ``generation`` remains a compatibility path
        for legacy unowned callers; production orchestration passes ``owner``.

        Pre-spawn barriers
        ------------------
        Two deterministic checkpoints prevent stale gate spawns:

        1. Before snapshot creation: checks tombstone + is_current.
        2. After snapshot creation, before Popen: checks tombstone + is_current.

        A third barrier closes the Popen-to-registration window: after
        registering the process, the code re-checks the tombstone under the
        same lock and immediately kills+marks-interrupted any process that
        was cancelled between Popen and registration.
        """
        command = str(command or "").strip()
        if not command:
            return QualityGateResult(
                status="not_configured",
                head_sha=self._head_sha(repo_path),
                command="",
            )

        owned_generation = str(generation) if generation is not None else None
        owned_owner = owner if owner is not None and owner.complete else None
        if owner is not None and owned_owner is None:
            logger.warning(
                "Quality gate refused incomplete owner metadata: %s",
                owner.to_dict(),
            )
            return QualityGateResult(
                status="infrastructure_error",
                head_sha="",
                command=command,
                output_tail="Quality gate owner metadata is incomplete.",
            )
        owner_key = owned_owner.key if owned_owner is not None else None
        # Register before resolving the head or waiting on the evidence key.
        # A cancellation that arrives while a second caller waits on that key
        # must remain authoritative until that waiter has observed it.
        if owned_owner is not None:
            owned_generation = owned_owner.authority_generation
            self._register_owner(owned_owner)
        elif owned_generation is not None:
            self._register_generation(owned_generation)

        def _release_owned_generation() -> None:
            if owned_owner is not None:
                self._release_owner(owned_owner)
            elif owned_generation is not None:
                self._release_generation(owned_generation)

        # Serialize only identical evidence keys. Different exact heads must
        # be able to run concurrently so a replacement generation never waits
        # behind (or shares state with) an obsolete gate.
        try:
            observed_head = (
                self._head_sha(repo_path)
                if require_source_head_match or not expected_head_sha
                else ""
            )
            head_sha = (
                self._resolve_commit(repo_path, expected_head_sha)
                if expected_head_sha
                else observed_head
            )
            if (
                expected_head_sha
                and require_source_head_match
                and observed_head != head_sha
            ):
                _release_owned_generation()
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
            _release_owned_generation()
            return QualityGateResult(
                status="infrastructure_error",
                head_sha="",
                command=command,
                output_tail=(
                    "Candidate CI was not run because the submitted exact "
                    f"commit is unavailable in the managed repository: {exc}"
                ),
            )

        if (
            owned_owner is not None
            and owned_owner.head_sha.strip().lower() != head_sha.strip().lower()
        ):
            _release_owned_generation()
            logger.warning(
                "Quality gate refused owner/head mismatch owner=%s resolved_head=%s",
                owned_owner.to_dict(),
                head_sha,
            )
            return QualityGateResult(
                status="infrastructure_error",
                head_sha=head_sha,
                command=command,
                output_tail=(
                    "Quality gate owner metadata does not match the exact "
                    "resolved candidate head."
                ),
            )

        # Fail closed before candidate code starts when the required lifecycle
        # isolation contract is absent, while retaining main's exact-head and
        # generation-aware launch sequencing.
        is_compliant, reason = self._verify_isolation_contract(
            repo_path,
            head_sha,
            require_source_head_match=require_source_head_match,
        )
        if not is_compliant:
            _release_owned_generation()
            return QualityGateResult(
                status="needs_rebase",
                head_sha=head_sha,
                command=command,
                output_tail=reason,
            )

        key = self._evidence_key(
            repo_identity=repo_identity,
            target_branch=target_branch,
            work_branch=work_branch,
            head_sha=head_sha,
            command=command,
        )

        def _load_reusable_result() -> tuple[
            dict[str, dict[str, object]], QualityGateResult | None
        ]:
            try:
                with self._lock:
                    loaded = self._load()
            except OSError:
                loaded = {}
            cached_result = self._decode_evidence_result(
                loaded.get(key),
                repo_identity=repo_identity,
                target_branch=target_branch,
                work_branch=work_branch,
                head_sha=head_sha,
                command=command,
            )
            if cached_result is None:
                return loaded, None
            if retry_forced and cached_result.status in {
                "failed",
                "timed_out",
                "error",
            }:
                return loaded, None
            return loaded, cached_result

        # Fast cache lookup does not consume host capacity.  Crucially, the
        # evidence key is released before a lease wait: a successful auditor
        # owns that lease while synchronously recording compatible evidence
        # under this same key.
        with self._key_lock(key):
            entries, cached_result = _load_reusable_result()
            if cached_result is not None:
                _release_owned_generation()
                return cached_result

        validation_handle = None
        if self.validation_lease is not None:
            validation_owner = ValidationLeaseOwner.exact_gate(
                project_id=(
                    owned_owner.project_id
                    if owned_owner is not None
                    else repo_identity
                ),
                task_id=(
                    owned_owner.task_id
                    if owned_owner is not None
                    else work_branch
                ),
                authority_generation=(
                    owned_owner.authority_generation
                    if owned_owner is not None
                    else f"{head_sha}:{key}"
                ),
            )

            def _lease_wait_cancelled() -> bool:
                if (
                    owned_generation is not None
                    and self._generation_is_cancelled(
                        owned_generation,
                        owner_key,
                    )
                ):
                    return True
                if is_current is None:
                    return False
                try:
                    return not bool(is_current())
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "Quality gate lease authority check failed: %s",
                        exc,
                    )
                    return True

            try:
                validation_handle = self.validation_lease.acquire(
                    validation_owner,
                    is_cancelled=_lease_wait_cancelled,
                )
            except ValidationLeaseCancelled as exc:
                _release_owned_generation()
                return QualityGateResult(
                    status="interrupted",
                    head_sha=head_sha,
                    command=command,
                    output_tail=str(exc),
                )
            except (OSError, sqlite3.Error, ValidationLeaseError) as exc:
                _release_owned_generation()
                return QualityGateResult(
                    status="infrastructure_error",
                    head_sha=head_sha,
                    command=command,
                    output_tail=(
                        "Exact quality gate could not acquire host "
                        f"validation capacity: {exc}"
                    ),
                )

        # The auditor may have published a PASS while this gate waited.  Take
        # the single-flight key only after capacity, reload durable evidence,
        # and avoid executing the exact command twice.
        with self._key_lock(key):
            entries, cached_result = _load_reusable_result()
            if cached_result is not None:
                if validation_handle is not None:
                    validation_handle.release()
                _release_owned_generation()
                return cached_result

            started = time.monotonic()
            process: subprocess.Popen[str] | None = None
            run_root = self._gate_run_root()
            snapshot: Path | None = None
            monitor_stop = threading.Event()
            monitor: threading.Thread | None = None
            try:
                # --- Barrier 1: before snapshot creation ---
                # Check authority before creating the immutable archive.
                # cancel_generation() may have been called while we were
                # waiting in the key lock or the evidence load above.
                if owned_generation is not None and self._generation_is_cancelled(
                    owned_generation,
                    owner_key,
                ):
                    return QualityGateResult(
                        status="interrupted",
                        head_sha=head_sha,
                        command=command,
                        duration_seconds=time.monotonic() - started,
                        output_tail="Gate cancelled before snapshot creation.",
                    )
                if is_current is not None:
                    try:
                        authority_ok = bool(is_current())
                    except Exception as exc:  # noqa: BLE001
                        authority_ok = False
                        logger.warning(
                            "Quality gate pre-spawn authority check failed: %s", exc
                        )
                    if not authority_ok:
                        return QualityGateResult(
                            status="interrupted",
                            head_sha=head_sha,
                            command=command,
                            duration_seconds=time.monotonic() - started,
                            output_tail="Gate authority withdrawn before snapshot creation.",
                        )

                try:
                    snapshot = self._snapshot_candidate_worktree(
                        repo_path, run_root, head_sha
                    )
                except _SandboxUnavailable as exc:
                    return QualityGateResult(
                        status="needs_rebase",
                        head_sha=head_sha,
                        command=command,
                        output_tail=(
                            "OS-enforced quality-gate sandbox is unavailable; "
                            f"refusing to execute candidate code: {exc}"
                        ),
                    )

                # --- Barrier 2: after snapshot, before Popen ---
                # cancel_generation() may have arrived during the up-to-60s
                # archive creation above.  Check again before spawning.
                if owned_generation is not None and self._generation_is_cancelled(
                    owned_generation,
                    owner_key,
                ):
                    return QualityGateResult(
                        status="interrupted",
                        head_sha=head_sha,
                        command=command,
                        duration_seconds=time.monotonic() - started,
                        output_tail="Gate cancelled after snapshot creation, before spawn.",
                    )
                if is_current is not None:
                    try:
                        authority_ok = bool(is_current())
                    except Exception as exc:  # noqa: BLE001
                        authority_ok = False
                        logger.warning(
                            "Quality gate pre-spawn authority check failed: %s", exc
                        )
                    if not authority_ok:
                        return QualityGateResult(
                            status="interrupted",
                            head_sha=head_sha,
                            command=command,
                            duration_seconds=time.monotonic() - started,
                            output_tail="Gate authority withdrawn after snapshot, before spawn.",
                        )

                try:
                    sandboxed_command = self._sandbox_launcher(
                        command,
                        str(snapshot),
                        run_root,
                    )
                except _TrustedRuntimeCorruption as exc:
                    return QualityGateResult(
                        status="infrastructure_error",
                        head_sha=head_sha,
                        command=command,
                        output_tail=(
                            "Trusted quality-gate runtime corruption detected; "
                            f"candidate CI was not run: {exc}"
                        ),
                    )
                except _SandboxUnavailable as exc:
                    return QualityGateResult(
                        status="needs_rebase",
                        head_sha=head_sha,
                        command=command,
                        output_tail=(
                            "OS-enforced quality-gate sandbox is unavailable; "
                            f"refusing to execute candidate code: {exc}"
                        ),
                    )
                process = subprocess.Popen(  # noqa: S602 - operator-owned command
                    sandboxed_command,
                    cwd=str(snapshot),
                    env=self._quality_gate_environment(run_root),
                    shell=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    start_new_session=True,
                    pass_fds=(
                        validation_handle.pass_fds
                        if validation_handle is not None
                        else ()
                    ),
                )
                if validation_handle is not None:
                    try:
                        validation_handle.attach_process(
                            process,
                            timeout_seconds=self.timeout_seconds,
                        )
                    except ValidationLeaseError:
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except OSError:
                            pass
                        process.communicate()
                        raise
                # Track process group for graceful shutdown cleanup.
                # --- Barrier 3: Popen-to-registration window ---
                # Re-check the tombstone under the lock immediately after
                # registration so that cancel_generation() calls that arrived
                # between Popen and here are caught and the just-spawned
                # process is killed before the monitor thread starts.
                with self._processes_lock:
                    if owned_generation is None:
                        owned_generation = f"pid:{process.pid}"
                    self._active_processes[process.pid] = process
                    self._active_generations[process.pid] = owned_generation
                    self._active_owners[process.pid] = owned_owner
                    self._active_snapshots[process.pid] = snapshot
                    # Check tombstone under the same lock that cancel_generation
                    # uses to add to _cancelled_generations and mark _interrupted.
                    post_spawn_cancelled = (
                        owner_key in self._cancelled_owner_keys
                        if owner_key is not None
                        else owned_generation in self._cancelled_generations
                    )
                    if post_spawn_cancelled:
                        setattr(process, "_oompah_interrupted", True)

                if post_spawn_cancelled:
                    # Kill the just-spawned process; the normal flow will
                    # see _oompah_interrupted=True and return interrupted.
                    try:
                        os.killpg(process.pid, signal.SIGTERM)
                    except (ProcessLookupError, OSError):
                        pass

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
                                if owned_owner is not None:
                                    self.cancel_owner(owned_owner)
                                else:
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
            except (OSError, sqlite3.Error, ValidationLeaseError) as exc:
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
                        self._active_owners.pop(process.pid, None)
                        self._active_snapshots.pop(process.pid, None)
                if validation_handle is not None:
                    validation_handle.release()
                # A cancelled generation remains fenced until every caller
                # already registered for it has crossed the barrier.  This
                # prevents one interrupted caller from clearing the tombstone
                # while another is still waiting on this evidence-key lock.
                _release_owned_generation()
                self._cleanup_gate_run_root(run_root)

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
