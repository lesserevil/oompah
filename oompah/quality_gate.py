"""Persistent, single-flight quality gates for review-ready branch heads."""

from __future__ import annotations

import ctypes
import errno
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
import stat
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Iterator
from urllib.parse import unquote, urlparse

from oompah.validation_resource_lease import (
    ValidationLeaseCancelled,
    ValidationLeaseError,
    ValidationLeaseOwner,
    ValidationResourceLease,
)
from oompah.venv_safety import (
    VenvSafetyError,
    ensure_worktree_venv,
    worktree_venv_lock,
)

logger = logging.getLogger(__name__)

_EVIDENCE_VERSION = 2
_PROTECTED_WORKFLOW_PROVENANCE_VERSION = 1
_PROTECTED_WORKFLOW_ATTESTED_STATUS = "attested_passed"
_OOMPAH_652_SAFETY_HEAD = "ec0ec7d89fb8804571fcf7e780558e6d979b73ea"

_SANDBOX_RUN_ROOT = Path("/oompah-gate")
_SANDBOX_TMP_ROOT = Path("/tmp/oompah-gate")
_SANDBOX_TRUSTED_HOME_ROOT = Path("/home/oompah")
_SANDBOX_WORKER_HOME_ROOT = _SANDBOX_TRUSTED_HOME_ROOT / "pytest-workers" / "session"
_SANDBOX_HOME = _SANDBOX_TRUSTED_HOME_ROOT
_GATE_CONTAINER_PREFIX = "oompah-quality-gate-"
_GATE_MUTABLE_ROOT_NAME = "run"
_GATE_IDENTITY_ROOT_NAME = "identity"
_GATE_TRUSTED_HOME_ROOT_NAME = "trusted-home"
_GATE_ROOT_PREFIX = _GATE_CONTAINER_PREFIX
_GATE_ROOT_OWNER_FILE = ".oompah-gate-owner.json"
_GATE_ROOT_MAX_AGE_SECONDS = 24 * 60 * 60
_GATE_ROOT_SCAVENGE_LIMIT = 256
_GATE_ROOT_DISCOVERY_ENTRY_LIMIT = 4096
_GATE_ROOT_DISCOVERY_SECONDS = 1.0
_GATE_CLEANUP_MAX_DEPTH = 256
_GATE_CLEANUP_MAX_OPERATIONS = 32_768
_GATE_CLEANUP_SLICE_SECONDS = 1.0
_GATE_DEFERRED_CLEANUP_LIMIT = 256
_GATE_CLEANUP_RETRY_INITIAL_SECONDS = 0.05
_GATE_CLEANUP_RETRY_MAX_SECONDS = 5.0
_GATE_CLEANUP_RETRY_WARNING_ATTEMPT = 8
_GATE_REMOVAL_REMOVED = "removed"
_GATE_REMOVAL_PROGRESS = "progress"
_GATE_REMOVAL_INCOMPLETE = "incomplete"
_GATE_REMOVAL_UNSAFE = "unsafe"
_GATE_ROOT_NAME_PATTERN = rf"{re.escape(_GATE_CONTAINER_PREFIX)}[a-z0-9_]{{8}}"
_GATE_ROOT_NAME_RE = re.compile(rf"^{_GATE_ROOT_NAME_PATTERN}$")
_GATE_ROOT_QUARANTINE_PATTERN = re.compile(
    rf"^\.(?P<root>{_GATE_ROOT_NAME_PATTERN})"
    r"\.scavenge-[1-9][0-9]*-[1-9][0-9]*$"
)
_GATE_SIDECAR_CLAIM_PATTERN = re.compile(
    rf"^\.(?P<root>{_GATE_ROOT_NAME_PATTERN})"
    r"\.sidecar-reap-(?P<device>[1-9][0-9]*)-(?P<inode>[1-9][0-9]*)"
    r"-(?P<claimant>[1-9][0-9]*)-(?P<nonce>[1-9][0-9]*)$"
)
_GATE_SIDECAR_SWAP_PATTERN = re.compile(
    rf"^\.(?P<root>{_GATE_ROOT_NAME_PATTERN})"
    r"\.sidecar-swap-(?P<device>[1-9][0-9]*)-(?P<inode>[1-9][0-9]*)"
    r"-(?P<claimant>[1-9][0-9]*)-(?P<nonce>[1-9][0-9]*)"
    r"-(?P<placeholder_device>[1-9][0-9]*)"
    r"-(?P<placeholder_inode>[1-9][0-9]*)"
    r"-[1-9][0-9]*-[1-9][0-9]*$"
)
_RENAME_NOREPLACE = 1
_RENAME_EXCHANGE = 2
_AT_EMPTY_PATH = 0x1000


def _gate_sidecar_candidate_root_name(name: str) -> str | None:
    suffix_length = len(_GATE_ROOT_OWNER_FILE)
    if (
        name.startswith(".")
        and name.endswith(_GATE_ROOT_OWNER_FILE)
        and _GATE_ROOT_NAME_RE.fullmatch(name[1:-suffix_length]) is not None
    ):
        return name[1:-suffix_length]
    claim_match = _GATE_SIDECAR_CLAIM_PATTERN.fullmatch(name)
    if claim_match is not None:
        return claim_match.group("root")
    swap_match = _GATE_SIDECAR_SWAP_PATTERN.fullmatch(name)
    return swap_match.group("root") if swap_match is not None else None


def _rename_noreplace_at(
    source_dir_fd: int,
    source_name: str,
    destination_dir_fd: int,
    destination_name: str,
) -> None:
    """Atomically rename one Linux pathname without replacing another."""
    try:
        function = ctypes.CDLL(None, use_errno=True).renameat2
    except AttributeError as exc:
        raise OSError(errno.ENOSYS, "renameat2 is unavailable") from exc
    function.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    )
    function.restype = ctypes.c_int
    if (
        function(
            source_dir_fd,
            os.fsencode(source_name),
            destination_dir_fd,
            os.fsencode(destination_name),
            _RENAME_NOREPLACE,
        )
        != 0
    ):
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))


def _rename_exchange_at(
    left_dir_fd: int,
    left_name: str,
    right_dir_fd: int,
    right_name: str,
) -> None:
    """Atomically exchange two Linux pathnames."""
    function = ctypes.CDLL(None, use_errno=True).renameat2
    function.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    )
    function.restype = ctypes.c_int
    if (
        function(
            left_dir_fd,
            os.fsencode(left_name),
            right_dir_fd,
            os.fsencode(right_name),
            _RENAME_EXCHANGE,
        )
        != 0
    ):
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))


def _unlink_at(directory_fd: int, name: str) -> None:
    """Invoke unlinkat directly after an atomic namespace capture."""
    function = ctypes.CDLL(None, use_errno=True).unlinkat
    function.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int)
    function.restype = ctypes.c_int
    if function(directory_fd, os.fsencode(name), 0) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))


def _link_descriptor_at(source_fd: int, destination_dir_fd: int, name: str) -> None:
    """Publish one unnamed inode without reopening it through a pathname."""
    function = ctypes.CDLL(None, use_errno=True).linkat
    function.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
    )
    function.restype = ctypes.c_int
    if (
        function(
            source_fd,
            b"",
            destination_dir_fd,
            os.fsencode(name),
            _AT_EMPTY_PATH,
        )
        != 0
    ):
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))


def _capture_and_unlink_gate_sidecar_at(
    parent_descriptor: int,
    claimed_name: str,
    expected_descriptor: int,
    root_name: str,
) -> str:
    """Atomically capture a name before deleting only its expected inode."""
    claim_match = _GATE_SIDECAR_CLAIM_PATTERN.fullmatch(claimed_name)
    if claim_match is None or claim_match.group("root") != root_name:
        return _GATE_REMOVAL_UNSAFE
    expected_metadata = os.fstat(expected_descriptor)
    expected_identity = (
        int(expected_metadata.st_dev),
        int(expected_metadata.st_ino),
    )
    placeholder_descriptor = os.open(
        ".",
        os.O_RDWR | getattr(os, "O_TMPFILE", 0),
        0o000,
        dir_fd=parent_descriptor,
    )
    exchanged = False
    swap_name: str | None = None
    placeholder_identity: tuple[int, int] | None = None
    try:
        placeholder_metadata = os.fstat(placeholder_descriptor)
        placeholder_identity = (
            int(placeholder_metadata.st_dev),
            int(placeholder_metadata.st_ino),
        )
        swap_name = (
            f".{root_name}.sidecar-swap-{expected_identity[0]}"
            f"-{expected_identity[1]}-{claim_match.group('claimant')}"
            f"-{claim_match.group('nonce')}-{placeholder_identity[0]}"
            f"-{placeholder_identity[1]}-{os.getpid()}-{time.time_ns()}"
        )
        _link_descriptor_at(placeholder_descriptor, parent_descriptor, swap_name)
        _rename_exchange_at(
            parent_descriptor,
            claimed_name,
            parent_descriptor,
            swap_name,
        )
        exchanged = True
        captured = os.stat(
            swap_name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
        installed = os.stat(
            claimed_name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
        captured_identity = (int(captured.st_dev), int(captured.st_ino))
        installed_identity = (int(installed.st_dev), int(installed.st_ino))
        if (
            captured_identity != expected_identity
            or installed_identity != placeholder_identity
        ):
            # Restore the atomically captured replacement without deleting it.
            if (
                captured_identity != placeholder_identity
                and installed_identity == placeholder_identity
            ):
                _rename_exchange_at(
                    parent_descriptor,
                    claimed_name,
                    parent_descriptor,
                    swap_name,
                )
                exchanged = False
            return _GATE_REMOVAL_UNSAFE

        # Delete the known placeholder first.  If the process crashes after
        # exchange, the expected inode remains under a recognizable claim.
        _unlink_at(parent_descriptor, claimed_name)
        if os.fstat(placeholder_descriptor).st_nlink != 0:
            return _GATE_REMOVAL_INCOMPLETE
        _unlink_at(parent_descriptor, swap_name)
        exchanged = False
        return (
            _GATE_REMOVAL_REMOVED
            if os.fstat(expected_descriptor).st_nlink == 0
            else _GATE_REMOVAL_INCOMPLETE
        )
    finally:
        os.close(placeholder_descriptor)
        if not exchanged and placeholder_identity is not None:
            for cleanup_name in (swap_name,):
                if cleanup_name is None:
                    continue
                try:
                    remaining = os.stat(
                        cleanup_name,
                        dir_fd=parent_descriptor,
                        follow_symlinks=False,
                    )
                    if (
                        int(remaining.st_dev),
                        int(remaining.st_ino),
                    ) == placeholder_identity:
                        _unlink_at(parent_descriptor, cleanup_name)
                except OSError:
                    pass


class _SandboxUnavailable(RuntimeError):
    """Raised when the operator cannot create the required OS boundary."""


class _TrustedRuntimeCorruption(RuntimeError):
    """Raised when the operator's installed source mapping is not trusted."""


class QualityGateEvidenceUnavailable(RuntimeError):
    """Raised when persisted quality-gate duration evidence cannot be read."""


class QualityGateEvidenceCorrupt(RuntimeError):
    """Raised when persisted quality-gate duration evidence is malformed."""


@dataclass(frozen=True)
class QualityGateDurationEvidence:
    """Duration high-water values plus the state-file load disposition."""

    durations: dict[tuple[str, str], int]
    load_status: str
    error: str | None = None


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
    if (
        not isinstance(directory_info, dict)
        or directory_info.get("editable") is not True
    ):
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


def _repair_trusted_runtime_source(runtime_prefix: Path) -> bool:
    """Repair a poisoned canonical service runtime when it is provably safe.

    A linked task worktree is never repair authority.  Only the primary Git
    checkout may repoint its own conventional ``.venv``, and the currently
    loaded quality-gate implementation must itself come from that checkout.
    The setup helper takes the same cross-worktree flock used by Make.
    """

    runtime = runtime_prefix.resolve(strict=False)
    service_checkout = runtime.parent.resolve(strict=False)
    loaded_checkout = Path(__file__).resolve().parent.parent
    if (
        runtime.name != ".venv"
        or not (service_checkout / ".git").is_dir()
        or loaded_checkout != service_checkout
    ):
        return False
    uv = shutil.which("uv")
    if not uv:
        return False
    try:
        ensure_worktree_venv(
            checkout=service_checkout,
            requested_venv=runtime,
            uv=uv,
            extra="dev",
        )
    except (OSError, VenvSafetyError) as exc:
        logger.warning("Automatic trusted-runtime repair failed: %s", exc)
        return False
    return True


def _validate_or_repair_trusted_runtime_source(
    runtime_prefix: Path,
    candidate_snapshot: Path,
) -> Path | None:
    """Observe one coherent mapping, repairing canonical corruption once."""

    try:
        with worktree_venv_lock(runtime_prefix.parent, exclusive=False):
            return _validate_trusted_runtime_source(runtime_prefix, candidate_snapshot)
    except _TrustedRuntimeCorruption:
        if not _repair_trusted_runtime_source(runtime_prefix):
            raise
    with worktree_venv_lock(runtime_prefix.parent, exclusive=False):
        return _validate_trusted_runtime_source(runtime_prefix, candidate_snapshot)


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
    cancellation: dict[str, str] | None = None
    return_code: int | None = None
    terminating_signal: int | None = None
    interrupted: bool = False
    interruption_source: str | None = None
    owner: dict[str, str] | None = None
    authority_generation: str | None = None

    @property
    def passed(self) -> bool:
        return self.status in {"passed", "not_configured"}

    @property
    def exit_description(self) -> str:
        """Return a concise truthful description of process termination."""

        if self.terminating_signal is not None:
            try:
                signal_name = signal.Signals(self.terminating_signal).name
            except ValueError:
                signal_name = f"signal {self.terminating_signal}"
            return f"terminated by {signal_name} (return code {self.return_code})"
        if self.return_code is not None:
            return f"exited with return code {self.return_code}"
        return "ended without subprocess exit evidence"


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
class ProtectedWorkflowStepProof:
    """One configured command-bearing step observed in a protected CI job."""

    name: str
    number: int
    status: str
    conclusion: str


@dataclass(frozen=True)
class ProtectedWorkflowJobProof:
    """Immutable successful-job identity within a protected workflow run."""

    name: str
    job_id: int
    run_attempt: int
    head_sha: str
    status: str
    conclusion: str
    check_run_id: int
    check_status: str
    check_conclusion: str
    check_head_sha: str
    app_id: int
    app_slug: str
    required_steps: tuple[ProtectedWorkflowStepProof, ...]


@dataclass(frozen=True)
class ProtectedWorkflowQualityEvidenceProof:
    """Verified protected-workflow provenance bound to one audit revision.

    The forge adapter and orchestrator establish this proof before import.
    Durable storage keeps it distinct from a locally executed branch-gate
    result, and consumption requires both current operator trust and current
    terminal-audit fingerprints.
    """

    repo_identity: str
    repository: str
    target_branch: str
    work_branch: str
    head_sha: str
    head_tree_sha: str
    base_sha: str
    merge_sha: str
    merge_tree_sha: str
    merge_parent_shas: tuple[str, ...]
    command: str
    task_audit_fingerprint: str
    trust_config_fingerprint: str
    workflow_id: int
    workflow_path: str
    workflow_blob_sha: str
    checkout_mode: str
    event: str
    app_id: int
    app_slug: str
    required_jobs: tuple[str, ...]
    required_steps: tuple[str, ...]
    jobs: tuple[ProtectedWorkflowJobProof, ...]
    pull_request_number: int
    run_id: int
    run_attempt: int
    run_head_sha: str
    run_status: str
    run_conclusion: str
    check_suite_id: int
    check_suite_status: str
    check_suite_conclusion: str
    check_suite_head_sha: str
    check_suite_app_id: int
    schema_version: int = _PROTECTED_WORKFLOW_PROVENANCE_VERSION


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
        values = tuple(
            str(value or "").strip()
            for value in (
                self.project_id,
                self.task_id,
                self.head_sha,
                self.authority_generation,
            )
        )
        return all(values) and all(len(value) <= 512 for value in values)

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
    _active_registration_tokens: dict[int, object | None] = {}
    # The active-process registry is process-wide, so retain the callback
    # beside its exact pid.  Class-level cancellation can then publish the
    # removal through the gate instance that registered it without guessing
    # which orchestrator owns another concurrent gate.
    _active_state_callbacks: dict[int, Callable[[], None]] = {}
    _active_gate_root_identities: dict[str, tuple[int, int]] = {}
    _deferred_gate_cleanups: dict[
        str,
        tuple[Path, Path, tuple[int, int], int, float],
    ] = {}
    _deferred_gate_cleanup_overflow = False
    _deferred_gate_cleanup_overflow_generation = 0
    _gate_namespace_generation = 0
    _deferred_gate_discovery: Iterator[os.DirEntry[str]] | None = None
    _deferred_gate_discovery_root: Path | None = None
    _deferred_gate_discovery_baseline: int | None = None
    _deferred_gate_discovery_unresolved = False
    _deferred_gate_discovery_made_progress = False
    _deferred_gate_discovery_attempts = 0
    _deferred_gate_discovery_retry_at = 0.0
    _deferred_gate_sidecar_phase = "collect"
    _deferred_gate_sidecar_cursor: str | None = None
    _deferred_gate_sidecar_candidates: dict[str, Path] = {}
    _deferred_gate_sidecar_protected: set[str] = set()
    _deferred_gate_cleanup_thread: threading.Thread | None = None
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
        active_state_changed: Callable[[], None] | None = None,
    ) -> None:
        self.state_path = Path(state_path)
        self.timeout_seconds = max(int(timeout_seconds), 1)
        self.output_tail_bytes = max(int(output_tail_bytes), 1024)
        self.safety_head = safety_head
        # Preserve the three-argument injected-launcher contract used by
        # tests and downstream embedders.  Only the built-in launcher needs
        # the fourth, server-owned trusted-home capability.
        self._sandbox_launcher = sandbox_launcher
        self.validation_lease = validation_lease
        self._active_state_changed = active_state_changed
        self._lock = threading.Lock()
        self._key_locks: dict[str, _KeyLockEntry] = {}
        self._scavenge_stale_gate_roots()

    @staticmethod
    def _notify_active_state_changed(
        callbacks: tuple[Callable[[], None], ...],
    ) -> None:
        """Invoke registry listeners without affecting gate execution."""

        for callback in callbacks:
            try:
                callback()
            except Exception:  # noqa: BLE001 - advisory publication is isolated
                logger.exception("Quality gate active-state callback failed")

    @classmethod
    def _remove_active_process_locked(
        cls,
        pid: int,
        *,
        expected_process: subprocess.Popen[str],
        expected_registration_token: object | None,
    ) -> Callable[[], None] | None:
        """CAS-remove one exact registry row while holding the process lock."""

        if (
            cls._active_processes.get(pid) is not expected_process
            or cls._active_registration_tokens.get(pid)
            is not expected_registration_token
        ):
            return None
        cls._active_processes.pop(pid, None)
        cls._active_generations.pop(pid, None)
        cls._active_owners.pop(pid, None)
        cls._active_snapshots.pop(pid, None)
        cls._active_registration_tokens.pop(pid, None)
        callback = cls._active_state_callbacks.pop(pid, None)
        return callback

    @classmethod
    def _register_active_process_locked(
        cls,
        process: subprocess.Popen[str],
        *,
        generation: str | None,
        owner: QualityGateOwner | None,
        snapshot: Path,
        callback: Callable[[], None] | None,
        registration_token: object,
    ) -> tuple[Callable[[], None], ...]:
        """Register one process and return displaced/new edge callbacks."""

        callbacks: list[Callable[[], None]] = []
        if process.pid in cls._active_processes:
            displaced = cls._active_state_callbacks.get(process.pid)
            if displaced is not None:
                callbacks.append(displaced)
        cls._active_processes[process.pid] = process
        cls._active_generations[process.pid] = generation
        cls._active_owners[process.pid] = owner
        cls._active_snapshots[process.pid] = snapshot
        cls._active_registration_tokens[process.pid] = registration_token
        if callback is not None:
            cls._active_state_callbacks[process.pid] = callback
            callbacks.append(callback)
        else:
            cls._active_state_callbacks.pop(process.pid, None)
        return tuple(callbacks)

    @classmethod
    def _signal_active_process_group(
        cls,
        pid: int,
        process: subprocess.Popen[str],
        registration_token: object | None,
        signal_number: int,
    ) -> bool:
        """Signal only while *pid* still names the selected registration."""

        with cls._processes_lock:
            if (
                cls._active_processes.get(pid) is not process
                or cls._active_registration_tokens.get(pid)
                is not registration_token
            ):
                return False
            try:
                return_code = process.poll()
            except (AttributeError, OSError, ValueError):
                # A registry entry without verifiable Popen liveness is not
                # authority to signal a numeric PID that may have been reused.
                return False
            if return_code is not None:
                return False
            os.killpg(pid, signal_number)
            return True

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
                (pid, process, cls._active_registration_tokens.get(pid))
                for pid, process in cls._active_processes.items()
                if (generation is None and owner is None)
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
            for _pid, process, _registration_token in processes:
                # The run thread uses this marker to return a non-cached
                # interruption instead of recording a false CI failure.
                setattr(process, "_oompah_interrupted", True)
                setattr(
                    process,
                    "_oompah_interruption_source",
                    (
                        "owner_cancellation"
                        if owner is not None
                        else "generation_cancellation"
                        if generation is not None
                        else "service_shutdown"
                    ),
                )
            # Record a durable tombstone so that gates currently between
            # pre-spawn barrier checks (snapshot creation, Popen-to-
            # registration window) also stop on their next check.
            if owner is not None:
                cls._mark_owner_cancelled_locked(owner)
            elif generation is not None:
                cls._mark_generation_cancelled_locked(generation)

        terminated_count = 0
        for pid, process, registration_token in processes:
            try:
                if cls._signal_active_process_group(
                    pid,
                    process,
                    registration_token,
                    signal.SIGTERM,
                ):
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
                    cls._signal_active_process_group(
                        pid,
                        process,
                        registration_token,
                        signal.SIGKILL,
                    )
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
                callback = cls._remove_active_process_locked(
                    pid,
                    expected_process=process,
                    expected_registration_token=registration_token,
                )
            if callback is not None:
                cls._notify_active_state_changed((callback,))

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
                    authority_generation=str(authority_generation or generation or ""),
                )
            return cls.cancel_owner(owner)
        if not str(generation or "").strip():
            logger.warning("Rejected generationless quality gate cancellation request")
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
            return (
                False,
                "Git ancestry check timed out (git repository may be corrupted)",
            )
        except OSError as exc:
            return False, f"Cannot verify git ancestry: {exc}"

    @staticmethod
    def _gate_identity_files(run_root: Path) -> dict[str, Path]:
        """Return validated server-owned identity files for one gate."""
        root = run_root.resolve(strict=True)
        container = root.parent
        temp_root = Path(tempfile.gettempdir()).resolve()
        if (
            root.name != _GATE_MUTABLE_ROOT_NAME
            or container.parent != temp_root
            or _GATE_ROOT_NAME_RE.fullmatch(container.name) is None
            or run_root.is_symlink()
            or container.is_symlink()
            or container.stat().st_uid != os.geteuid()
        ):
            raise _SandboxUnavailable("quality-gate identity root is not trusted")
        identity_root = container / _GATE_IDENTITY_ROOT_NAME
        try:
            identity_metadata = identity_root.stat(follow_symlinks=False)
        except OSError as exc:
            raise _SandboxUnavailable(
                "quality-gate identity database is unavailable"
            ) from exc
        if (
            identity_root.is_symlink()
            or not identity_root.is_dir()
            or identity_metadata.st_uid != os.geteuid()
            or identity_metadata.st_mode & 0o777 != 0o500
        ):
            raise _SandboxUnavailable("quality-gate identity database is not immutable")
        files = {
            "passwd": identity_root / "passwd",
            "group": identity_root / "group",
            "nsswitch.conf": identity_root / "nsswitch.conf",
        }
        for path in files.values():
            try:
                metadata = path.stat(follow_symlinks=False)
            except OSError as exc:
                raise _SandboxUnavailable(
                    "quality-gate identity database is unavailable"
                ) from exc
            if (
                path.is_symlink()
                or not path.is_file()
                or metadata.st_uid != os.geteuid()
                or metadata.st_mode & 0o222
            ):
                raise _SandboxUnavailable(
                    "quality-gate identity database is not immutable"
                )
        return files

    @staticmethod
    def _gate_process_identity(pid: int) -> tuple[str, int | None]:
        """Return ``(alive|dead|unknown, start_ticks)`` for one Linux PID."""
        try:
            raw = Path(f"/proc/{int(pid)}/stat").read_text(encoding="utf-8")
        except FileNotFoundError:
            return "dead", None
        except OSError:
            return "unknown", None
        try:
            return "alive", int(raw[raw.rfind(")") + 2 :].split()[19])
        except (ValueError, IndexError):
            return "unknown", None

    @staticmethod
    def _gate_root_owner_path(root: Path) -> Path:
        # Keep liveness evidence beside, never inside, the candidate-writable
        # bind.  The hidden host-temp parent is absent from the bwrap sandbox.
        return root.parent / f".{root.name}{_GATE_ROOT_OWNER_FILE}"

    @classmethod
    def _claim_gate_root_owner_retry(cls, root: Path) -> bool:
        """Persist immediate terminal-unlink authority in an inode claim."""
        sidecar = cls._gate_root_owner_path(root)
        parent_descriptor: int | None = None
        sidecar_descriptor: int | None = None
        claimed_name: str | None = None
        claimed = False
        try:
            parent_descriptor = os.open(
                sidecar.parent,
                os.O_RDONLY
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_NOFOLLOW", 0),
            )
            sidecar_descriptor = os.open(
                sidecar.name,
                getattr(os, "O_PATH", os.O_RDONLY)
                | getattr(os, "O_NOFOLLOW", 0)
                | getattr(os, "O_NONBLOCK", 0),
                dir_fd=parent_descriptor,
            )
            metadata = os.fstat(sidecar_descriptor)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid():
                return False
            identity = (int(metadata.st_dev), int(metadata.st_ino))
            claimed_name = (
                f".{root.name}.sidecar-reap-{identity[0]}-{identity[1]}"
                f"-{os.getpid()}-{time.time_ns()}"
            )
            with cls._processes_lock:
                try:
                    _rename_noreplace_at(
                        parent_descriptor,
                        sidecar.name,
                        parent_descriptor,
                        claimed_name,
                    )
                except OSError as exc:
                    if exc.errno in {errno.EEXIST, errno.ELOOP, errno.ENOTDIR}:
                        raise
                    # A no-clobber hard link is a second durable publication
                    # protocol when renameat2 fails transiently.  Discovery
                    # converts the canonical twin into another recognizable
                    # claim before removing either link.
                    os.link(
                        sidecar.name,
                        claimed_name,
                        src_dir_fd=parent_descriptor,
                        dst_dir_fd=parent_descriptor,
                        follow_symlinks=False,
                    )
                claimed = True
                cls._gate_namespace_generation += 1
                final_metadata = os.stat(
                    claimed_name,
                    dir_fd=parent_descriptor,
                    follow_symlinks=False,
                )
                if (
                    int(final_metadata.st_dev),
                    int(final_metadata.st_ino),
                ) != identity:
                    return False
                # The recognizable name is the durable retry authorization.
                claimed = False
                return True
        except OSError:
            return False
        finally:
            if claimed and parent_descriptor is not None and claimed_name is not None:
                with cls._processes_lock:
                    try:
                        os.stat(
                            sidecar.name,
                            dir_fd=parent_descriptor,
                            follow_symlinks=False,
                        )
                    except FileNotFoundError:
                        try:
                            _rename_noreplace_at(
                                parent_descriptor,
                                claimed_name,
                                parent_descriptor,
                                sidecar.name,
                            )
                            cls._gate_namespace_generation += 1
                        except OSError:
                            pass
                    except OSError:
                        pass
            if sidecar_descriptor is not None:
                os.close(sidecar_descriptor)
            if parent_descriptor is not None:
                os.close(parent_descriptor)

    @classmethod
    def _unlink_gate_root_owner(cls, root: Path) -> bool:
        try:
            cls._gate_root_owner_path(root).unlink(missing_ok=True)
        except OSError as exc:
            # The root lifecycle has already completed.  A sidecar failure is
            # separately age-bounded by the startup scavenger and must not
            # turn successful root cleanup into a false failure.
            logger.warning("Failed to remove gate-root owner sidecar %s: %s", root, exc)
            cls._claim_gate_root_owner_retry(root)
            cls._request_deferred_gate_discovery()
            return False
        return True

    @staticmethod
    def _prepare_gate_container_removal(container: Path) -> bool:
        """Repair candidate-controlled directory modes without following links."""
        try:
            metadata = container.stat(follow_symlinks=False)
        except OSError:
            return False
        if (
            not stat.S_ISDIR(metadata.st_mode)
            or stat.S_ISLNK(metadata.st_mode)
            or metadata.st_uid != os.geteuid()
        ):
            return False
        try:
            container.chmod(0o700, follow_symlinks=False)
            for current_root, directory_names, _file_names in os.walk(
                container,
                topdown=True,
                followlinks=False,
            ):
                current = Path(current_root)
                current_metadata = current.stat(follow_symlinks=False)
                if (
                    not stat.S_ISDIR(current_metadata.st_mode)
                    or stat.S_ISLNK(current_metadata.st_mode)
                    or current_metadata.st_uid != os.geteuid()
                ):
                    return False
                current.chmod(0o700, follow_symlinks=False)
                for name in directory_names:
                    child = current / name
                    child_metadata = child.stat(follow_symlinks=False)
                    if stat.S_ISDIR(child_metadata.st_mode):
                        if child_metadata.st_uid != os.geteuid():
                            return False
                        child.chmod(0o700, follow_symlinks=False)
        except OSError:
            return False
        return True

    @staticmethod
    def _restore_gate_identity_mode_at(container_descriptor: int) -> bool:
        """Restore identity mode relative to an already verified container."""
        identity_descriptor: int | None = None
        try:
            identity_descriptor = os.open(
                _GATE_IDENTITY_ROOT_NAME,
                os.O_RDONLY
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=container_descriptor,
            )
            metadata = os.fstat(identity_descriptor)
            if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.geteuid():
                return False
            os.fchmod(identity_descriptor, 0o500)
        except OSError:
            return False
        finally:
            if identity_descriptor is not None:
                os.close(identity_descriptor)
        return True

    @classmethod
    def _restore_gate_identity_mode(cls, container: Path) -> bool:
        """Restore identity mode below one no-follow container path."""
        container_descriptor: int | None = None
        try:
            container_descriptor = os.open(
                container,
                os.O_RDONLY
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_NOFOLLOW", 0),
            )
            return cls._restore_gate_identity_mode_at(container_descriptor)
        except OSError:
            return False
        finally:
            if container_descriptor is not None:
                os.close(container_descriptor)

    @staticmethod
    def _remove_gate_tree_at(
        parent_descriptor: int,
        name: str,
        expected_identity: tuple[int, int],
        root_descriptor: int,
    ) -> str:
        """Delete one opened tree without following a substituted path.

        The caller retains both the parent and exact root descriptors across
        the quarantine rename.  Every child directory is opened with
        ``O_NOFOLLOW`` and revalidated before its name is removed; the root
        name is likewise compared with the retained inode immediately before
        the final ``rmdir``.
        """

        try:
            root_metadata = os.fstat(root_descriptor)
            initial_root = os.stat(
                name,
                dir_fd=parent_descriptor,
                follow_symlinks=False,
            )
        except OSError:
            return _GATE_REMOVAL_INCOMPLETE
        if (
            not stat.S_ISDIR(root_metadata.st_mode)
            or root_metadata.st_uid != os.geteuid()
            or (int(root_metadata.st_dev), int(root_metadata.st_ino))
            != expected_identity
        ):
            return _GATE_REMOVAL_UNSAFE
        if (int(initial_root.st_dev), int(initial_root.st_ino)) != expected_identity:
            return _GATE_REMOVAL_UNSAFE
        root_device = int(root_metadata.st_dev)
        # Each frame records the opened child's name and inode plus its exact
        # parent inode.  We retain only the current directory FD, then ascend
        # through ``..`` and verify the parent identity before removing the
        # child name.  Depth is capped; at the cap, a verified child is moved
        # to the retained root as a new work item.  Candidate-controlled depth
        # therefore cannot consume recursion, descriptors, or unbounded frames.
        frames: list[tuple[str, tuple[int, int], tuple[int, int]]] = []
        directory_descriptor: int | None = None
        try:
            directory_descriptor = os.dup(root_descriptor)
        except OSError:
            return _GATE_REMOVAL_INCOMPLETE
        operation_count = 0
        made_progress = False
        deadline = time.monotonic() + _GATE_CLEANUP_SLICE_SECONDS
        try:
            while True:
                if made_progress and (
                    operation_count >= _GATE_CLEANUP_MAX_OPERATIONS
                    or time.monotonic() >= deadline
                ):
                    return _GATE_REMOVAL_PROGRESS
                operation_count += 1
                directory_metadata = os.fstat(directory_descriptor)
                if (
                    not stat.S_ISDIR(directory_metadata.st_mode)
                    or directory_metadata.st_uid != os.geteuid()
                    or int(directory_metadata.st_dev) != root_device
                ):
                    return _GATE_REMOVAL_UNSAFE
                directory_identity = (
                    int(directory_metadata.st_dev),
                    int(directory_metadata.st_ino),
                )
                os.fchmod(directory_descriptor, 0o700)

                selected: str | None = None
                identity_present = False
                scan_descriptor = os.open(
                    ".",
                    os.O_RDONLY
                    | getattr(os, "O_DIRECTORY", 0)
                    | getattr(os, "O_NOFOLLOW", 0),
                    dir_fd=directory_descriptor,
                )
                try:
                    with os.scandir(scan_descriptor) as entries:
                        for entry in entries:
                            if (
                                directory_identity == expected_identity
                                and entry.name == _GATE_IDENTITY_ROOT_NAME
                            ):
                                identity_present = True
                                continue
                            selected = entry.name
                            break
                finally:
                    os.close(scan_descriptor)
                if selected is None and identity_present:
                    selected = _GATE_IDENTITY_ROOT_NAME

                if selected is not None:
                    selected_metadata = os.stat(
                        selected,
                        dir_fd=directory_descriptor,
                        follow_symlinks=False,
                    )
                    if (
                        selected_metadata.st_uid != os.geteuid()
                        or int(selected_metadata.st_dev) != root_device
                    ):
                        return _GATE_REMOVAL_UNSAFE
                    path_descriptor: int | None = None
                    child_descriptor: int | None = None
                    try:
                        path_descriptor = os.open(
                            selected,
                            getattr(os, "O_PATH", os.O_RDONLY)
                            | (
                                getattr(os, "O_DIRECTORY", 0)
                                if stat.S_ISDIR(selected_metadata.st_mode)
                                else 0
                            )
                            | getattr(os, "O_NOFOLLOW", 0),
                            dir_fd=directory_descriptor,
                        )
                        path_metadata = os.fstat(path_descriptor)
                        selected_identity = (
                            int(path_metadata.st_dev),
                            int(path_metadata.st_ino),
                        )
                        if (
                            selected_identity
                            != (
                                int(selected_metadata.st_dev),
                                int(selected_metadata.st_ino),
                            )
                            or int(path_metadata.st_dev) != root_device
                            or path_metadata.st_uid != os.geteuid()
                        ):
                            return _GATE_REMOVAL_UNSAFE
                        if stat.S_ISDIR(path_metadata.st_mode):
                            if len(frames) >= _GATE_CLEANUP_MAX_DEPTH:
                                queue_name = (
                                    f".oompah-cleanup-{os.getpid()}-{time.time_ns()}"
                                )
                                os.rename(
                                    selected,
                                    queue_name,
                                    src_dir_fd=directory_descriptor,
                                    dst_dir_fd=root_descriptor,
                                )
                                queued = os.stat(
                                    queue_name,
                                    dir_fd=root_descriptor,
                                    follow_symlinks=False,
                                )
                                if (
                                    int(queued.st_dev),
                                    int(queued.st_ino),
                                ) != selected_identity:
                                    return _GATE_REMOVAL_UNSAFE
                                made_progress = True
                                continue
                            # O_PATH bypasses candidate-controlled 000 modes.
                            # Chmod through the retained descriptor, then open
                            # ``.`` relative to that same inode for traversal.
                            os.chmod(f"/proc/self/fd/{path_descriptor}", 0o700)
                            child_descriptor = os.open(
                                ".",
                                os.O_RDONLY
                                | getattr(os, "O_DIRECTORY", 0)
                                | getattr(os, "O_NOFOLLOW", 0),
                                dir_fd=path_descriptor,
                            )
                            child_metadata = os.fstat(child_descriptor)
                            if (
                                int(child_metadata.st_dev),
                                int(child_metadata.st_ino),
                            ) != selected_identity:
                                return _GATE_REMOVAL_UNSAFE
                            os.fchmod(child_descriptor, 0o700)
                            frames.append(
                                (selected, selected_identity, directory_identity)
                            )
                            os.close(directory_descriptor)
                            directory_descriptor = child_descriptor
                            child_descriptor = None
                        else:
                            final_entry = os.stat(
                                selected,
                                dir_fd=directory_descriptor,
                                follow_symlinks=False,
                            )
                            if (
                                int(final_entry.st_dev),
                                int(final_entry.st_ino),
                            ) != selected_identity:
                                return _GATE_REMOVAL_UNSAFE
                            os.unlink(selected, dir_fd=directory_descriptor)
                            made_progress = True
                    finally:
                        if child_descriptor is not None:
                            os.close(child_descriptor)
                        if path_descriptor is not None:
                            os.close(path_descriptor)
                    continue

                if not frames:
                    break
                leaf_name, leaf_identity, parent_identity = frames.pop()
                if directory_identity != leaf_identity:
                    return _GATE_REMOVAL_UNSAFE
                parent_of_leaf = os.open(
                    "..",
                    os.O_RDONLY
                    | getattr(os, "O_DIRECTORY", 0)
                    | getattr(os, "O_NOFOLLOW", 0),
                    dir_fd=directory_descriptor,
                )
                try:
                    parent_metadata = os.fstat(parent_of_leaf)
                    if (
                        int(parent_metadata.st_dev),
                        int(parent_metadata.st_ino),
                    ) != parent_identity:
                        return _GATE_REMOVAL_UNSAFE
                    final_leaf = os.stat(
                        leaf_name,
                        dir_fd=parent_of_leaf,
                        follow_symlinks=False,
                    )
                    if (
                        int(final_leaf.st_dev),
                        int(final_leaf.st_ino),
                    ) != leaf_identity:
                        return _GATE_REMOVAL_UNSAFE
                    os.rmdir(leaf_name, dir_fd=parent_of_leaf)
                    made_progress = True
                    os.close(directory_descriptor)
                    directory_descriptor = parent_of_leaf
                    parent_of_leaf = -1
                finally:
                    if parent_of_leaf >= 0:
                        os.close(parent_of_leaf)

            final_root = os.stat(
                name,
                dir_fd=parent_descriptor,
                follow_symlinks=False,
            )
            if (int(final_root.st_dev), int(final_root.st_ino)) != expected_identity:
                return _GATE_REMOVAL_UNSAFE
            os.rmdir(name, dir_fd=parent_descriptor)
        except OSError as exc:
            # Every retry reopens and revalidates the exact quarantine inode.
            # A transient descriptor, signal, or filesystem failure therefore
            # pauses progress safely instead of orphaning a partially reaped
            # tree.  Explicit inode/device/ownership mismatches return UNSAFE.
            if exc.errno in {errno.ELOOP, errno.ENOTDIR}:
                return _GATE_REMOVAL_UNSAFE
            return _GATE_REMOVAL_PROGRESS if made_progress else _GATE_REMOVAL_INCOMPLETE
        finally:
            if directory_descriptor is not None:
                os.close(directory_descriptor)
        return _GATE_REMOVAL_REMOVED

    @classmethod
    def _register_gate_root(cls, root: Path) -> tuple[int, int]:
        metadata = root.stat()
        identity = (int(metadata.st_dev), int(metadata.st_ino))
        with cls._processes_lock:
            cls._active_gate_root_identities[str(root)] = identity
            cls._note_gate_namespace_change(root.name)
        return identity

    @classmethod
    def _note_gate_namespace_change(cls, root_name: str) -> None:
        """Record one root publication while ``_processes_lock`` is held."""
        cls._gate_namespace_generation += 1
        if cls._deferred_gate_sidecar_phase == "verify" and any(
            _gate_sidecar_candidate_root_name(candidate_name) == root_name
            for candidate_name in cls._deferred_gate_sidecar_candidates
        ):
            # A matching root changed after verification began.  Protect only
            # that bounded-batch candidate; unrelated gate churn must not
            # invalidate absence proofs for every orphan sidecar.
            cls._deferred_gate_sidecar_protected.add(root_name)

    @classmethod
    def _forget_gate_root(cls, root: Path) -> None:
        with cls._processes_lock:
            if cls._active_gate_root_identities.pop(str(root), None) is not None:
                match = _GATE_ROOT_QUARANTINE_PATTERN.fullmatch(root.name)
                root_name = match.group("root") if match is not None else root.name
                cls._note_gate_namespace_change(root_name)

    @classmethod
    def _deferred_gate_cleanup_slice(
        cls,
        quarantine: Path,
        expected_identity: tuple[int, int],
    ) -> str:
        """Run one bounded removal slice for an already-authorized quarantine."""
        parent_descriptor: int | None = None
        root_descriptor: int | None = None
        try:
            parent_descriptor = os.open(
                quarantine.parent,
                os.O_RDONLY
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_NOFOLLOW", 0),
            )
            root_descriptor = os.open(
                quarantine.name,
                os.O_RDONLY
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=parent_descriptor,
            )
            metadata = os.fstat(root_descriptor)
            if (int(metadata.st_dev), int(metadata.st_ino)) != expected_identity:
                return _GATE_REMOVAL_UNSAFE
            return cls._remove_gate_tree_at(
                parent_descriptor,
                quarantine.name,
                expected_identity,
                root_descriptor,
            )
        except FileNotFoundError:
            # A missing name does not prove that the expected inode was
            # deleted; a same-UID namespace racer may have renamed it away.
            # Preserve the sidecar as durable evidence and stop this claim.
            return _GATE_REMOVAL_UNSAFE
        except OSError as exc:
            if exc.errno in {errno.ELOOP, errno.ENOTDIR}:
                # A non-directory or symlink at the durable quarantine name
                # is a namespace substitution, not a transient open failure.
                return _GATE_REMOVAL_UNSAFE
            return _GATE_REMOVAL_INCOMPLETE
        finally:
            if root_descriptor is not None:
                os.close(root_descriptor)
            if parent_descriptor is not None:
                os.close(parent_descriptor)

    @classmethod
    def _probe_discovered_gate_cleanup(
        cls,
        root: Path,
        quarantine: Path,
        expected_identity: tuple[int, int],
    ) -> str:
        """Run one bounded durable-overflow slice outside the resident queue."""
        with cls._processes_lock:
            try:
                metadata = quarantine.stat(follow_symlinks=False)
            except FileNotFoundError:
                return _GATE_REMOVAL_UNSAFE
            except OSError as exc:
                return (
                    _GATE_REMOVAL_UNSAFE
                    if exc.errno in {errno.ELOOP, errno.ENOTDIR}
                    else _GATE_REMOVAL_INCOMPLETE
                )
            if (int(metadata.st_dev), int(metadata.st_ino)) != expected_identity:
                return _GATE_REMOVAL_UNSAFE
            if str(quarantine) in cls._active_gate_root_identities:
                return _GATE_REMOVAL_INCOMPLETE
            cls._active_gate_root_identities[str(quarantine)] = expected_identity
            cls._note_gate_namespace_change(root.name)
        try:
            result = cls._deferred_gate_cleanup_slice(
                quarantine,
                expected_identity,
            )
        except Exception:  # noqa: BLE001 - preserve durable evidence on failure
            logger.exception(
                "Deferred quality-gate discovery probe crashed for %s",
                quarantine,
            )
            result = _GATE_REMOVAL_UNSAFE
        finally:
            with cls._processes_lock:
                if (
                    cls._active_gate_root_identities.get(str(quarantine))
                    == expected_identity
                ):
                    cls._active_gate_root_identities.pop(str(quarantine), None)
                    cls._note_gate_namespace_change(root.name)
        if result == _GATE_REMOVAL_REMOVED:
            cls._unlink_gate_root_owner(root)
        return result

    @classmethod
    def _discover_deferred_gate_cleanups(cls) -> bool:
        """Advance one bounded, generation-fenced maintenance pass."""
        temp_root = Path(tempfile.gettempdir()).resolve()

        def reset_scan(*, discard_batch: bool) -> None:
            with cls._processes_lock:
                if cls._deferred_gate_discovery is not None:
                    cls._deferred_gate_discovery.close()
                cls._deferred_gate_discovery = None
                cls._deferred_gate_discovery_baseline = None
                cls._deferred_gate_discovery_unresolved = False
                cls._deferred_gate_discovery_made_progress = False
                cls._deferred_gate_sidecar_protected.clear()
                if discard_batch:
                    cls._deferred_gate_sidecar_candidates.clear()
                    cls._deferred_gate_sidecar_phase = "collect"
                    cls._deferred_gate_sidecar_cursor = None

        with cls._processes_lock:
            if cls._deferred_gate_discovery_root != temp_root:
                if cls._deferred_gate_discovery is not None:
                    cls._deferred_gate_discovery.close()
                cls._deferred_gate_discovery = None
                cls._deferred_gate_discovery_baseline = None
                cls._deferred_gate_discovery_root = temp_root
                cls._deferred_gate_discovery_unresolved = False
                cls._deferred_gate_discovery_made_progress = False
                cls._deferred_gate_discovery_attempts = 0
                cls._deferred_gate_discovery_retry_at = 0.0
                cls._deferred_gate_sidecar_phase = "collect"
                cls._deferred_gate_sidecar_cursor = None
                cls._deferred_gate_sidecar_candidates.clear()
                cls._deferred_gate_sidecar_protected.clear()
            if cls._deferred_gate_discovery is None:
                try:
                    cls._deferred_gate_discovery = os.scandir(temp_root)
                except OSError:
                    return False
                cls._deferred_gate_discovery_baseline = (
                    cls._deferred_gate_cleanup_overflow_generation
                )
            entries = cls._deferred_gate_discovery
            baseline = cls._deferred_gate_discovery_baseline
            sidecar_phase = cls._deferred_gate_sidecar_phase
            sidecar_cursor = cls._deferred_gate_sidecar_cursor
        if baseline is None:
            reset_scan(discard_batch=True)
            return False

        deadline = time.monotonic() + _GATE_ROOT_DISCOVERY_SECONDS
        inspected = 0
        try:
            while (
                inspected < _GATE_ROOT_DISCOVERY_ENTRY_LIMIT
                and time.monotonic() < deadline
            ):
                try:
                    entry = next(entries)
                except StopIteration:
                    entries.close()
                    with cls._processes_lock:
                        if cls._deferred_gate_discovery is entries:
                            cls._deferred_gate_discovery = None
                            cls._deferred_gate_discovery_baseline = None
                        generation_is_current = (
                            baseline == cls._deferred_gate_cleanup_overflow_generation
                        )
                        unresolved = cls._deferred_gate_discovery_unresolved
                        made_progress = cls._deferred_gate_discovery_made_progress
                        cls._deferred_gate_discovery_unresolved = False
                        cls._deferred_gate_discovery_made_progress = False
                        if unresolved and not made_progress:
                            cls._deferred_gate_discovery_attempts += 1
                            retry_delay = min(
                                _GATE_CLEANUP_RETRY_INITIAL_SECONDS
                                * (
                                    2
                                    ** min(
                                        cls._deferred_gate_discovery_attempts - 1,
                                        16,
                                    )
                                ),
                                _GATE_CLEANUP_RETRY_MAX_SECONDS,
                            )
                            cls._deferred_gate_discovery_retry_at = (
                                time.monotonic() + retry_delay
                            )
                        else:
                            cls._deferred_gate_discovery_attempts = 0
                            cls._deferred_gate_discovery_retry_at = 0.0
                    if not generation_is_current:
                        reset_scan(discard_batch=True)
                        return False
                    if sidecar_phase == "collect":
                        with cls._processes_lock:
                            if cls._deferred_gate_sidecar_candidates:
                                cls._deferred_gate_sidecar_phase = "verify"
                                cls._deferred_gate_sidecar_protected.clear()
                                return False
                            cls._deferred_gate_sidecar_cursor = None
                        return not unresolved

                    with cls._processes_lock:
                        sidecars = tuple(cls._deferred_gate_sidecar_candidates.items())
                        protected = frozenset(cls._deferred_gate_sidecar_protected)
                    for sidecar_name, sidecar in sidecars:
                        root_name = _gate_sidecar_candidate_root_name(sidecar_name)
                        if root_name is None:
                            continue
                        claim_match = _GATE_SIDECAR_CLAIM_PATTERN.fullmatch(
                            sidecar_name
                        )
                        swap_match = _GATE_SIDECAR_SWAP_PATTERN.fullmatch(sidecar_name)
                        if root_name in protected:
                            if claim_match is not None or swap_match is not None:
                                # A claim or interrupted exchange owns the only
                                # sidecar name. Keep the persistent pass alive
                                # until its matching root/quarantine disappears.
                                with cls._processes_lock:
                                    cls._deferred_gate_discovery_unresolved = True
                            continue
                        if swap_match is not None:
                            sidecar_result = cls._recover_gate_sidecar_swap(
                                sidecar,
                                swap_match,
                            )
                        elif claim_match is not None:
                            sidecar_result = cls._recover_gate_sidecar_claim(
                                sidecar,
                                claim_match,
                                expected_namespace_generation=None,
                                require_sidecar_batch=True,
                                report_status=True,
                            )
                        else:
                            sidecar_result = cls._remove_orphan_gate_sidecar(
                                sidecar,
                                root_name,
                                now=time.time(),
                                expected_namespace_generation=None,
                                require_sidecar_batch=True,
                                report_status=True,
                            )
                        if swap_match is not None and sidecar_result in {
                            _GATE_REMOVAL_REMOVED,
                            _GATE_REMOVAL_PROGRESS,
                        }:
                            # The original claim can sort before the swap name.
                            # Restart collection so cursor pagination cannot
                            # strand the now-recoverable predecessor.
                            reset_scan(discard_batch=True)
                            return False
                        with cls._processes_lock:
                            if sidecar_result == _GATE_REMOVAL_REMOVED:
                                cls._deferred_gate_discovery_made_progress = True
                            elif sidecar_result == _GATE_REMOVAL_INCOMPLETE:
                                cls._deferred_gate_discovery_unresolved = True
                    with cls._processes_lock:
                        cls._deferred_gate_sidecar_cursor = max(
                            (name for name, _path in sidecars),
                            default=cls._deferred_gate_sidecar_cursor,
                        )
                        cls._deferred_gate_sidecar_candidates.clear()
                        cls._deferred_gate_sidecar_protected.clear()
                        cls._deferred_gate_sidecar_phase = "collect"
                    return False

                inspected += 1
                candidate = Path(entry.path)
                if _GATE_ROOT_NAME_RE.fullmatch(candidate.name) is not None:
                    if sidecar_phase == "verify":
                        with cls._processes_lock:
                            if any(
                                _gate_sidecar_candidate_root_name(name)
                                == candidate.name
                                for name in cls._deferred_gate_sidecar_candidates
                            ):
                                cls._deferred_gate_sidecar_protected.add(candidate.name)
                    stale_identity = cls._stale_gate_root(
                        candidate,
                        now=time.time(),
                    )
                    if stale_identity is not None:
                        cls._remove_stale_gate_root(candidate, stale_identity)
                    continue

                quarantine_match = _GATE_ROOT_QUARANTINE_PATTERN.fullmatch(
                    candidate.name
                )
                if quarantine_match is not None:
                    if sidecar_phase == "verify":
                        root_name = quarantine_match.group("root")
                        with cls._processes_lock:
                            if any(
                                _gate_sidecar_candidate_root_name(name) == root_name
                                for name in cls._deferred_gate_sidecar_candidates
                            ):
                                cls._deferred_gate_sidecar_protected.add(root_name)
                    abandoned = cls._abandoned_gate_quarantine(
                        candidate,
                        now=time.time(),
                        allow_current_owner=True,
                    )
                    if abandoned is None:
                        continue
                    root_name, identity = abandoned
                    root = candidate.parent / root_name
                    if cls._schedule_deferred_gate_cleanup(
                        root,
                        candidate,
                        identity,
                        from_discovery=True,
                    ):
                        continue
                    probe_result = cls._probe_discovered_gate_cleanup(
                        root,
                        candidate,
                        identity,
                    )
                    with cls._processes_lock:
                        if probe_result in {
                            _GATE_REMOVAL_REMOVED,
                            _GATE_REMOVAL_PROGRESS,
                        }:
                            cls._deferred_gate_discovery_made_progress = True
                        if probe_result in {
                            _GATE_REMOVAL_PROGRESS,
                            _GATE_REMOVAL_INCOMPLETE,
                        }:
                            cls._deferred_gate_discovery_unresolved = True
                    continue

                if sidecar_phase != "collect":
                    continue
                if _gate_sidecar_candidate_root_name(candidate.name) is None or (
                    sidecar_cursor is not None and candidate.name <= sidecar_cursor
                ):
                    continue
                with cls._processes_lock:
                    sidecars = cls._deferred_gate_sidecar_candidates
                    if candidate.name in sidecars:
                        continue
                    if len(sidecars) < _GATE_DEFERRED_CLEANUP_LIMIT:
                        sidecars[candidate.name] = candidate
                        continue
                    largest = max(sidecars)
                    if candidate.name < largest:
                        sidecars.pop(largest)
                        sidecars[candidate.name] = candidate
        except OSError:
            reset_scan(discard_batch=True)
            return False
        return False

    @classmethod
    def _remove_orphan_gate_sidecar(
        cls,
        sidecar: Path,
        root_name: str,
        *,
        now: float,
        expected_namespace_generation: int | None,
        require_sidecar_batch: bool = False,
        report_status: bool = False,
    ) -> bool | str:
        """Atomically claim one old owner record before inode-fenced removal."""

        def outcome(status: str) -> bool | str:
            return status if report_status else status == _GATE_REMOVAL_REMOVED

        if _GATE_ROOT_NAME_RE.fullmatch(root_name) is None:
            return outcome(_GATE_REMOVAL_UNSAFE)
        root = sidecar.parent / root_name
        parent_descriptor: int | None = None
        sidecar_descriptor: int | None = None
        claimed_name: str | None = None
        claimed = False
        identity: tuple[int, int] | None = None
        try:
            parent_descriptor = os.open(
                sidecar.parent,
                os.O_RDONLY
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_NOFOLLOW", 0),
            )
            with cls._processes_lock:
                if (
                    expected_namespace_generation is not None
                    and cls._gate_namespace_generation != expected_namespace_generation
                ):
                    return outcome(_GATE_REMOVAL_INCOMPLETE)
                if require_sidecar_batch and (
                    cls._deferred_gate_sidecar_phase != "verify"
                    or sidecar.name not in cls._deferred_gate_sidecar_candidates
                    or root_name in cls._deferred_gate_sidecar_protected
                ):
                    return outcome(_GATE_REMOVAL_INCOMPLETE)
                if str(root) in cls._active_gate_root_identities:
                    return outcome(_GATE_REMOVAL_INCOMPLETE)
                for active_path in cls._active_gate_root_identities:
                    match = _GATE_ROOT_QUARANTINE_PATTERN.fullmatch(
                        Path(active_path).name
                    )
                    if match is not None and match.group("root") == root_name:
                        return outcome(_GATE_REMOVAL_INCOMPLETE)
                try:
                    os.stat(
                        root.name,
                        dir_fd=parent_descriptor,
                        follow_symlinks=False,
                    )
                except FileNotFoundError:
                    pass
                else:
                    return outcome(_GATE_REMOVAL_INCOMPLETE)
                sidecar_descriptor = os.open(
                    sidecar.name,
                    getattr(os, "O_PATH", os.O_RDONLY)
                    | getattr(os, "O_NOFOLLOW", 0)
                    | getattr(os, "O_NONBLOCK", 0),
                    dir_fd=parent_descriptor,
                )
                metadata = os.fstat(sidecar_descriptor)
                if (
                    not stat.S_ISREG(metadata.st_mode)
                    or metadata.st_uid != os.getuid()
                    or (
                        not require_sidecar_batch
                        and now - metadata.st_mtime < _GATE_ROOT_MAX_AGE_SECONDS
                    )
                ):
                    return outcome(_GATE_REMOVAL_UNSAFE)
                identity = (int(metadata.st_dev), int(metadata.st_ino))
                claimed_name = (
                    f".{root_name}.sidecar-reap-{identity[0]}-{identity[1]}"
                    f"-{os.getpid()}-{time.time_ns()}"
                )
                _rename_noreplace_at(
                    parent_descriptor,
                    sidecar.name,
                    parent_descriptor,
                    claimed_name,
                )
                claimed = True
                cls._gate_namespace_generation += 1
                final_metadata = os.stat(
                    claimed_name,
                    dir_fd=parent_descriptor,
                    follow_symlinks=False,
                )
                if (
                    int(final_metadata.st_dev),
                    int(final_metadata.st_ino),
                ) != identity:
                    return outcome(_GATE_REMOVAL_UNSAFE)
                # From this point onward the durable claim/exchange protocol
                # owns recovery.  The outer canonical rollback must never
                # rename a post-exchange placeholder into owner authority.
                claimed = False
                removal = _capture_and_unlink_gate_sidecar_at(
                    parent_descriptor,
                    claimed_name,
                    sidecar_descriptor,
                    root_name,
                )
                cls._gate_namespace_generation += 1
                return outcome(removal)
        except FileNotFoundError:
            return outcome(_GATE_REMOVAL_UNSAFE)
        except OSError as exc:
            return outcome(
                _GATE_REMOVAL_UNSAFE
                if exc.errno in {errno.ELOOP, errno.ENOTDIR}
                else _GATE_REMOVAL_INCOMPLETE
            )
        finally:
            if claimed and parent_descriptor is not None and claimed_name is not None:
                with cls._processes_lock:
                    try:
                        os.stat(
                            sidecar.name,
                            dir_fd=parent_descriptor,
                            follow_symlinks=False,
                        )
                    except FileNotFoundError:
                        try:
                            _rename_noreplace_at(
                                parent_descriptor,
                                claimed_name,
                                parent_descriptor,
                                sidecar.name,
                            )
                            cls._gate_namespace_generation += 1
                        except OSError:
                            pass
                    except OSError:
                        pass
            if sidecar_descriptor is not None:
                os.close(sidecar_descriptor)
            if parent_descriptor is not None:
                os.close(parent_descriptor)

    @classmethod
    def _recover_gate_sidecar_claim(
        cls,
        claim: Path,
        claim_match: re.Match[str],
        *,
        expected_namespace_generation: int | None,
        require_sidecar_batch: bool = False,
        report_status: bool = False,
    ) -> bool | str:
        """Inode-fence one verified interrupted claim before terminal removal."""

        def outcome(status: str) -> bool | str:
            return status if report_status else status == _GATE_REMOVAL_REMOVED

        root_name = claim_match.group("root")
        canonical_name = f".{root_name}{_GATE_ROOT_OWNER_FILE}"
        parent_descriptor: int | None = None
        claim_descriptor: int | None = None
        try:
            parent_descriptor = os.open(
                claim.parent,
                os.O_RDONLY
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_NOFOLLOW", 0),
            )
            claim_descriptor = os.open(
                claim.name,
                getattr(os, "O_PATH", os.O_RDONLY)
                | getattr(os, "O_NOFOLLOW", 0)
                | getattr(os, "O_NONBLOCK", 0),
                dir_fd=parent_descriptor,
            )
            metadata = os.fstat(claim_descriptor)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid():
                return outcome(_GATE_REMOVAL_UNSAFE)
            expected_identity = (
                int(claim_match.group("device")),
                int(claim_match.group("inode")),
            )
            if (int(metadata.st_dev), int(metadata.st_ino)) != expected_identity:
                # A forged name or source substitution is evidence, not
                # lifecycle authority. Never promote it to the canonical
                # sidecar path or unlink it automatically.
                return outcome(_GATE_REMOVAL_UNSAFE)
            with cls._processes_lock:
                if (
                    expected_namespace_generation is not None
                    and cls._gate_namespace_generation != expected_namespace_generation
                ):
                    return outcome(_GATE_REMOVAL_INCOMPLETE)
                if not require_sidecar_batch or (
                    cls._deferred_gate_sidecar_phase != "verify"
                    or claim.name not in cls._deferred_gate_sidecar_candidates
                    or root_name in cls._deferred_gate_sidecar_protected
                ):
                    return outcome(_GATE_REMOVAL_UNSAFE)
                root = claim.parent / root_name
                if str(root) in cls._active_gate_root_identities:
                    return outcome(_GATE_REMOVAL_INCOMPLETE)
                for active_path in cls._active_gate_root_identities:
                    match = _GATE_ROOT_QUARANTINE_PATTERN.fullmatch(
                        Path(active_path).name
                    )
                    if match is not None and match.group("root") == root_name:
                        return outcome(_GATE_REMOVAL_INCOMPLETE)
                try:
                    os.stat(
                        root_name,
                        dir_fd=parent_descriptor,
                        follow_symlinks=False,
                    )
                except FileNotFoundError:
                    pass
                else:
                    return outcome(_GATE_REMOVAL_INCOMPLETE)
                try:
                    canonical_metadata = os.stat(
                        canonical_name,
                        dir_fd=parent_descriptor,
                        follow_symlinks=False,
                    )
                except FileNotFoundError:
                    pass
                else:
                    if (
                        int(canonical_metadata.st_dev),
                        int(canonical_metadata.st_ino),
                    ) != expected_identity:
                        return outcome(_GATE_REMOVAL_UNSAFE)
                    canonical_claim_name = (
                        f".{root_name}.sidecar-reap-{expected_identity[0]}"
                        f"-{expected_identity[1]}-{os.getpid()}-{time.time_ns()}"
                    )
                    _rename_noreplace_at(
                        parent_descriptor,
                        canonical_name,
                        parent_descriptor,
                        canonical_claim_name,
                    )
                    cls._gate_namespace_generation += 1
                    canonical_claim_metadata = os.stat(
                        canonical_claim_name,
                        dir_fd=parent_descriptor,
                        follow_symlinks=False,
                    )
                    if (
                        int(canonical_claim_metadata.st_dev),
                        int(canonical_claim_metadata.st_ino),
                    ) != expected_identity:
                        return outcome(_GATE_REMOVAL_UNSAFE)

                recheck_name = (
                    f".{root_name}.sidecar-reap-{expected_identity[0]}"
                    f"-{expected_identity[1]}-{os.getpid()}-{time.time_ns()}"
                )
                _rename_noreplace_at(
                    parent_descriptor,
                    claim.name,
                    parent_descriptor,
                    recheck_name,
                )
                cls._gate_namespace_generation += 1
                final_metadata = os.stat(
                    recheck_name,
                    dir_fd=parent_descriptor,
                    follow_symlinks=False,
                )
                if (
                    int(final_metadata.st_dev),
                    int(final_metadata.st_ino),
                ) != expected_identity:
                    return outcome(_GATE_REMOVAL_UNSAFE)
                removal = _capture_and_unlink_gate_sidecar_at(
                    parent_descriptor,
                    recheck_name,
                    claim_descriptor,
                    root_name,
                )
                cls._gate_namespace_generation += 1
                return outcome(removal)
        except FileNotFoundError:
            return outcome(_GATE_REMOVAL_UNSAFE)
        except OSError as exc:
            return outcome(
                _GATE_REMOVAL_UNSAFE
                if exc.errno in {errno.ELOOP, errno.ENOTDIR}
                else _GATE_REMOVAL_INCOMPLETE
            )
        finally:
            if claim_descriptor is not None:
                os.close(claim_descriptor)
            if parent_descriptor is not None:
                os.close(parent_descriptor)

    @classmethod
    def _recover_gate_sidecar_swap(
        cls,
        swap: Path,
        swap_match: re.Match[str],
    ) -> str:
        """Restore or finish one identity-encoded exchange crash state."""
        root_name = swap_match.group("root")
        expected_identity = (
            int(swap_match.group("device")),
            int(swap_match.group("inode")),
        )
        placeholder_identity = (
            int(swap_match.group("placeholder_device")),
            int(swap_match.group("placeholder_inode")),
        )
        original_name = (
            f".{root_name}.sidecar-reap-{expected_identity[0]}"
            f"-{expected_identity[1]}-{swap_match.group('claimant')}"
            f"-{swap_match.group('nonce')}"
        )
        parent_descriptor: int | None = None
        swap_descriptor: int | None = None
        original_descriptor: int | None = None
        placeholder_descriptor: int | None = None
        try:
            parent_descriptor = os.open(
                swap.parent,
                os.O_RDONLY
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_NOFOLLOW", 0),
            )
            swap_descriptor = os.open(
                swap.name,
                getattr(os, "O_PATH", os.O_RDONLY)
                | getattr(os, "O_NOFOLLOW", 0)
                | getattr(os, "O_NONBLOCK", 0),
                dir_fd=parent_descriptor,
            )
            swap_metadata = os.fstat(swap_descriptor)
            if (
                not stat.S_ISREG(swap_metadata.st_mode)
                or swap_metadata.st_uid != os.getuid()
            ):
                return _GATE_REMOVAL_UNSAFE
            swap_identity = (
                int(swap_metadata.st_dev),
                int(swap_metadata.st_ino),
            )
            try:
                original_descriptor = os.open(
                    original_name,
                    getattr(os, "O_PATH", os.O_RDONLY)
                    | getattr(os, "O_NOFOLLOW", 0)
                    | getattr(os, "O_NONBLOCK", 0),
                    dir_fd=parent_descriptor,
                )
            except FileNotFoundError:
                original_identity = None
            else:
                original_metadata = os.fstat(original_descriptor)
                original_identity = (
                    int(original_metadata.st_dev),
                    int(original_metadata.st_ino),
                )

            with cls._processes_lock:
                if (
                    swap_identity == expected_identity
                    and original_identity == placeholder_identity
                ):
                    _rename_exchange_at(
                        parent_descriptor,
                        original_name,
                        parent_descriptor,
                        swap.name,
                    )
                    cls._gate_namespace_generation += 1
                    swap_identity = placeholder_identity
                    original_identity = expected_identity
                    placeholder_descriptor = original_descriptor
                elif swap_identity == expected_identity and original_identity is None:
                    _rename_noreplace_at(
                        parent_descriptor,
                        swap.name,
                        parent_descriptor,
                        original_name,
                    )
                    cls._gate_namespace_generation += 1
                    return _GATE_REMOVAL_PROGRESS

                if swap_identity != placeholder_identity:
                    return _GATE_REMOVAL_UNSAFE
                if placeholder_descriptor is None:
                    placeholder_descriptor = swap_descriptor
                if original_identity not in {expected_identity, None}:
                    return _GATE_REMOVAL_UNSAFE
                current = os.stat(
                    swap.name,
                    dir_fd=parent_descriptor,
                    follow_symlinks=False,
                )
                if (
                    int(current.st_dev),
                    int(current.st_ino),
                ) != placeholder_identity:
                    return _GATE_REMOVAL_UNSAFE
                _unlink_at(parent_descriptor, swap.name)
                cls._gate_namespace_generation += 1
                return (
                    _GATE_REMOVAL_REMOVED
                    if os.fstat(placeholder_descriptor).st_nlink == 0
                    else _GATE_REMOVAL_INCOMPLETE
                )
        except FileNotFoundError:
            return _GATE_REMOVAL_REMOVED
        except OSError as exc:
            return (
                _GATE_REMOVAL_UNSAFE
                if exc.errno in {errno.ELOOP, errno.ENOTDIR}
                else _GATE_REMOVAL_INCOMPLETE
            )
        finally:
            if original_descriptor is not None:
                os.close(original_descriptor)
            if swap_descriptor is not None:
                os.close(swap_descriptor)
            if parent_descriptor is not None:
                os.close(parent_descriptor)

    @classmethod
    def _request_deferred_gate_discovery(cls) -> bool:
        """Ensure one process-wide worker completes bounded startup discovery."""
        with cls._processes_lock:
            cls._deferred_gate_cleanup_overflow = True
            cls._deferred_gate_cleanup_overflow_generation += 1
            cls._deferred_gate_discovery_attempts = 0
            cls._deferred_gate_discovery_retry_at = 0.0
            if cls._deferred_gate_cleanup_thread is not None:
                return True
            thread = threading.Thread(
                target=cls._run_deferred_gate_cleanups,
                name="quality-gate-cleanup-reaper",
                daemon=True,
            )
            cls._deferred_gate_cleanup_thread = thread
            try:
                thread.start()
            except RuntimeError:
                cls._deferred_gate_cleanup_thread = None
                return False
            return True

    @classmethod
    def _run_deferred_gate_cleanups(cls) -> None:
        """Serially drain bounded cleanup slices outside the gate result path."""
        while True:
            sleep_seconds = 0.01
            with cls._processes_lock:
                pending_count = len(cls._deferred_gate_cleanups)
                discover_overflow = (
                    cls._deferred_gate_cleanup_overflow
                    and cls._deferred_gate_discovery_retry_at <= time.monotonic()
                )
                overflow_pending = cls._deferred_gate_cleanup_overflow
                discovery_retry_at = cls._deferred_gate_discovery_retry_at
                if pending_count == 0 and not overflow_pending:
                    cls._deferred_gate_cleanup_thread = None
                    return
            if pending_count == 0 and not discover_overflow:
                time.sleep(max(min(discovery_retry_at - time.monotonic(), 0.25), 0.01))
                continue
            if discover_overflow:
                with cls._processes_lock:
                    overflow_generation = cls._deferred_gate_cleanup_overflow_generation
                discovery_complete = cls._discover_deferred_gate_cleanups()
                with cls._processes_lock:
                    if (
                        discovery_complete
                        and cls._deferred_gate_cleanup_overflow_generation
                        == overflow_generation
                    ):
                        cls._deferred_gate_cleanup_overflow = False
                    if (
                        not cls._deferred_gate_cleanups
                        and not cls._deferred_gate_cleanup_overflow
                    ):
                        cls._deferred_gate_cleanup_thread = None
                        return
                    pending_count = len(cls._deferred_gate_cleanups)
                if pending_count == 0:
                    if not discovery_complete:
                        time.sleep(sleep_seconds)
                    continue
            with cls._processes_lock:
                now = time.monotonic()
                selected = next(
                    (
                        (key, cleanup)
                        for key, cleanup in cls._deferred_gate_cleanups.items()
                        if cleanup[4] <= now
                    ),
                    None,
                )
                if selected is None:
                    next_retry = min(
                        cleanup[4] for cleanup in cls._deferred_gate_cleanups.values()
                    )
                    sleep_seconds = max(
                        min(next_retry - now, 0.25),
                        0.01,
                    )
                else:
                    key, cleanup = selected
                    root, quarantine, identity, attempts, _retry_at = cleanup
            if selected is None:
                time.sleep(sleep_seconds)
                continue
            try:
                result = cls._deferred_gate_cleanup_slice(quarantine, identity)
            except Exception:  # noqa: BLE001 - a dead reaper must fail closed
                logger.exception(
                    "Deferred quality-gate cleanup crashed for %s",
                    quarantine,
                )
                result = _GATE_REMOVAL_UNSAFE
            unlink_owner = False
            with cls._processes_lock:
                current = cls._deferred_gate_cleanups.get(key)
                if current != cleanup:
                    continue
                if result in {
                    _GATE_REMOVAL_PROGRESS,
                    _GATE_REMOVAL_INCOMPLETE,
                }:
                    if result == _GATE_REMOVAL_PROGRESS:
                        attempts = 0
                        retry_delay = 0.0
                    else:
                        attempts += 1
                        retry_delay = min(
                            _GATE_CLEANUP_RETRY_INITIAL_SECONDS
                            * (2 ** min(attempts - 1, 16)),
                            _GATE_CLEANUP_RETRY_MAX_SECONDS,
                        )
                    cls._deferred_gate_cleanups.pop(key, None)
                    cls._deferred_gate_cleanups[key] = (
                        root,
                        quarantine,
                        identity,
                        attempts,
                        time.monotonic() + retry_delay,
                    )
                else:
                    cls._deferred_gate_cleanups.pop(key, None)
                    if (
                        cls._active_gate_root_identities.pop(str(quarantine), None)
                        is not None
                    ):
                        cls._note_gate_namespace_change(root.name)
                    unlink_owner = result == _GATE_REMOVAL_REMOVED
            if unlink_owner:
                cls._unlink_gate_root_owner(root)
            if result == _GATE_REMOVAL_INCOMPLETE:
                if attempts == _GATE_CLEANUP_RETRY_WARNING_ATTEMPT:
                    logger.warning(
                        "Deferred quality-gate cleanup remains transient after "
                        "%d attempts; backing off retries for %s",
                        attempts,
                        quarantine,
                    )
                time.sleep(min(retry_delay, 0.25))
            elif result == _GATE_REMOVAL_PROGRESS:
                time.sleep(0)
            elif result == _GATE_REMOVAL_UNSAFE:
                logger.warning(
                    "Deferred quality-gate cleanup stopped at an unsafe boundary: %s",
                    quarantine,
                )

    @classmethod
    def _schedule_deferred_gate_cleanup(
        cls,
        root: Path,
        quarantine: Path,
        expected_identity: tuple[int, int],
        *,
        transfer_from: Path | None = None,
        from_discovery: bool = False,
    ) -> bool:
        """Queue one exact root for serial, bounded, convergent cleanup."""
        key = f"{quarantine}:{expected_identity[0]}:{expected_identity[1]}"
        with cls._processes_lock:
            previous_cleanup = cls._deferred_gate_cleanups.get(key)
            previous_quarantine_identity = cls._active_gate_root_identities.get(
                str(quarantine)
            )
            previous_overflow = cls._deferred_gate_cleanup_overflow
            previous_overflow_generation = (
                cls._deferred_gate_cleanup_overflow_generation
            )
            previous_namespace_generation = cls._gate_namespace_generation
            try:
                metadata = quarantine.stat(follow_symlinks=False)
            except OSError:
                return False
            if (int(metadata.st_dev), int(metadata.st_ino)) != expected_identity:
                return False
            if transfer_from is not None:
                if (
                    cls._active_gate_root_identities.get(str(transfer_from))
                    != expected_identity
                ):
                    return False
                cls._active_gate_root_identities.pop(str(transfer_from), None)
                cls._note_gate_namespace_change(root.name)
            if (
                key not in cls._deferred_gate_cleanups
                and len(cls._deferred_gate_cleanups) >= _GATE_DEFERRED_CLEANUP_LIMIT
            ):
                # The exact quarantine and sidecar are the durable overflow
                # queue.  The one reaper discovers them after an in-memory
                # slot frees, without retaining another candidate-sized path.
                if from_discovery:
                    # The running persistent scan already owns this durable
                    # artifact.  Its one-item probe path must advance past it
                    # even while every resident slot is permanently transient.
                    return False
                cls._deferred_gate_cleanup_overflow = True
                cls._deferred_gate_cleanup_overflow_generation += 1
                cls._deferred_gate_discovery_attempts = 0
                cls._deferred_gate_discovery_retry_at = 0.0
            else:
                cls._deferred_gate_cleanups[key] = (
                    root,
                    quarantine,
                    expected_identity,
                    0,
                    0.0,
                )
                cls._active_gate_root_identities[str(quarantine)] = expected_identity
            if cls._deferred_gate_cleanup_thread is None:
                thread = threading.Thread(
                    target=cls._run_deferred_gate_cleanups,
                    name="quality-gate-cleanup-reaper",
                    daemon=True,
                )
                cls._deferred_gate_cleanup_thread = thread
                try:
                    # Publish and start under one lock acquisition.  The new
                    # worker may run immediately, but waits for this lock before
                    # consuming the queue, so no accepted item can be stranded
                    # behind an unstarted published thread.
                    thread.start()
                except RuntimeError:
                    cls._deferred_gate_cleanup_thread = None
                    if previous_cleanup is None:
                        cls._deferred_gate_cleanups.pop(key, None)
                    else:
                        cls._deferred_gate_cleanups[key] = previous_cleanup
                    if previous_quarantine_identity is None:
                        cls._active_gate_root_identities.pop(str(quarantine), None)
                    else:
                        cls._active_gate_root_identities[str(quarantine)] = (
                            previous_quarantine_identity
                        )
                    cls._deferred_gate_cleanup_overflow = previous_overflow
                    cls._deferred_gate_cleanup_overflow_generation = (
                        previous_overflow_generation
                    )
                    cls._gate_namespace_generation = previous_namespace_generation
                    if transfer_from is not None:
                        cls._active_gate_root_identities[str(transfer_from)] = (
                            expected_identity
                        )
                    return False
        return True

    @classmethod
    def _write_gate_root_owner(cls, root: Path) -> None:
        process_state, start_ticks = cls._gate_process_identity(os.getpid())
        if process_state != "alive" or start_ticks is None:
            raise OSError("cannot record quality-gate process identity")
        root_metadata = root.stat()
        payload = json.dumps(
            {
                "pid": os.getpid(),
                "process_start_ticks": start_ticks,
                "root_device": int(root_metadata.st_dev),
                "root_inode": int(root_metadata.st_ino),
                "created_at": time.time(),
            },
            sort_keys=True,
        ).encode("utf-8")
        owner_path = cls._gate_root_owner_path(root)
        descriptor = os.open(
            owner_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o400,
        )
        try:
            os.fchmod(descriptor, 0o400)
            remaining = memoryview(payload)
            while remaining:
                written = os.write(descriptor, remaining)
                if written <= 0:
                    raise OSError("cannot write quality-gate owner metadata")
                remaining = remaining[written:]
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    @classmethod
    def _stale_gate_root(
        cls,
        root: Path,
        *,
        now: float,
    ) -> tuple[int, int] | None:
        root_descriptor: int | None = None
        try:
            root_descriptor = os.open(
                root,
                os.O_RDONLY
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_NOFOLLOW", 0),
            )
            metadata = os.fstat(root_descriptor)
            if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.getuid():
                return None
            identity = (int(metadata.st_dev), int(metadata.st_ino))
            with cls._processes_lock:
                if str(root) in cls._active_gate_root_identities:
                    # Process memory, unlike files below either bind, cannot
                    # be backdated or replaced by the candidate harness.
                    return None

            owner_path = cls._gate_root_owner_path(root)
            try:
                owner_descriptor = os.open(
                    owner_path,
                    os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
                )
            except OSError:
                return (
                    identity
                    if now - metadata.st_mtime >= _GATE_ROOT_MAX_AGE_SECONDS
                    else None
                )
            try:
                owner_metadata = os.fstat(owner_descriptor)
                if (
                    not stat.S_ISREG(owner_metadata.st_mode)
                    or owner_metadata.st_uid != os.getuid()
                    or owner_metadata.st_size > 4096
                ):
                    return (
                        identity
                        if now - owner_metadata.st_mtime >= _GATE_ROOT_MAX_AGE_SECONDS
                        else None
                    )
                payload = os.read(owner_descriptor, 4097)
            finally:
                os.close(owner_descriptor)
            try:
                owner = json.loads(payload.decode("utf-8"))
                pid = int(owner["pid"])
                expected_ticks = int(owner["process_start_ticks"])
                owner_identity = (
                    int(owner["root_device"]),
                    int(owner["root_inode"]),
                )
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                return (
                    identity
                    if now - owner_metadata.st_mtime >= _GATE_ROOT_MAX_AGE_SECONDS
                    else None
                )
            if owner_identity != identity:
                # A structurally valid sidecar is an inode capability, not
                # generic permission to delete whatever later occupies its
                # generated-looking path.
                return None
            process_state, actual_ticks = cls._gate_process_identity(pid)
            if process_state == "unknown":
                return None
            if process_state == "dead" or actual_ticks != expected_ticks:
                return identity
            return None
        except OSError:
            return None
        finally:
            if root_descriptor is not None:
                os.close(root_descriptor)

    @classmethod
    def _remove_stale_gate_root(
        cls,
        root: Path,
        expected_identity: tuple[int, int],
        *,
        allow_active_owner: bool = False,
    ) -> str:
        """Quarantine and remove only the exact inode classified stale."""
        with cls._processes_lock:
            active_identity = cls._active_gate_root_identities.get(str(root))
            active_authorized = (
                active_identity == expected_identity
                if allow_active_owner
                else active_identity is None
            )
            if not active_authorized:
                return _GATE_REMOVAL_UNSAFE
        parent_descriptor: int | None = None
        root_descriptor: int | None = None
        quarantine_published = False
        quarantine_name = f".{root.name}.scavenge-{os.getpid()}-{time.time_ns()}"
        try:
            parent_descriptor = os.open(
                root.parent,
                os.O_RDONLY
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_NOFOLLOW", 0),
            )
            root_descriptor = os.open(
                root.name,
                os.O_RDONLY
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=parent_descriptor,
            )
            current = os.fstat(root_descriptor)
            if (int(current.st_dev), int(current.st_ino)) != expected_identity:
                return _GATE_REMOVAL_UNSAFE
            with cls._processes_lock:
                active_identity = cls._active_gate_root_identities.get(str(root))
                active_authorized = (
                    active_identity == expected_identity
                    if allow_active_owner
                    else active_identity is None
                )
                if not active_authorized:
                    return _GATE_REMOVAL_UNSAFE
                os.rename(
                    root.name,
                    quarantine_name,
                    src_dir_fd=parent_descriptor,
                    dst_dir_fd=parent_descriptor,
                )
                quarantine_published = True
                cls._note_gate_namespace_change(root.name)
            quarantined = os.stat(
                quarantine_name,
                dir_fd=parent_descriptor,
                follow_symlinks=False,
            )
            if (int(quarantined.st_dev), int(quarantined.st_ino)) != expected_identity:
                if not root.exists():
                    with cls._processes_lock:
                        os.rename(
                            quarantine_name,
                            root.name,
                            src_dir_fd=parent_descriptor,
                            dst_dir_fd=parent_descriptor,
                        )
                        cls._note_gate_namespace_change(root.name)
                return _GATE_REMOVAL_UNSAFE
            removal = cls._remove_gate_tree_at(
                parent_descriptor,
                quarantine_name,
                expected_identity,
                root_descriptor,
            )
            if removal != _GATE_REMOVAL_REMOVED:
                if removal in {
                    _GATE_REMOVAL_PROGRESS,
                    _GATE_REMOVAL_INCOMPLETE,
                }:
                    scheduled = cls._schedule_deferred_gate_cleanup(
                        root,
                        root.parent / quarantine_name,
                        expected_identity,
                        transfer_from=root if allow_active_owner else None,
                    )
                    if scheduled:
                        return _GATE_REMOVAL_INCOMPLETE
                try:
                    current_quarantine = os.stat(
                        quarantine_name,
                        dir_fd=parent_descriptor,
                        follow_symlinks=False,
                    )
                    if (
                        int(current_quarantine.st_dev),
                        int(current_quarantine.st_ino),
                    ) == expected_identity:
                        restored = (
                            cls._restore_gate_identity_mode_at(root_descriptor)
                            if allow_active_owner
                            else True
                        )
                        if restored:
                            try:
                                os.stat(
                                    root.name,
                                    dir_fd=parent_descriptor,
                                    follow_symlinks=False,
                                )
                            except FileNotFoundError:
                                with cls._processes_lock:
                                    os.rename(
                                        quarantine_name,
                                        root.name,
                                        src_dir_fd=parent_descriptor,
                                        dst_dir_fd=parent_descriptor,
                                    )
                                    cls._note_gate_namespace_change(root.name)
                        elif allow_active_owner:
                            # Partial fd-relative deletion can remove the
                            # identity capability before the final root rmdir
                            # fails.  Keep that inode under its recognizable
                            # quarantine name for restart scavenging instead of
                            # restoring an invalid active container.
                            cls._forget_gate_root(root)
                except OSError:
                    pass
                logger.warning("Failed to remove quarantined gate root %s", root)
                return _GATE_REMOVAL_UNSAFE
            if allow_active_owner:
                cls._forget_gate_root(root)
            cls._unlink_gate_root_owner(root)
            return _GATE_REMOVAL_REMOVED
        except OSError:
            if quarantine_published:
                if cls._schedule_deferred_gate_cleanup(
                    root,
                    root.parent / quarantine_name,
                    expected_identity,
                    transfer_from=root if allow_active_owner else None,
                ):
                    return _GATE_REMOVAL_INCOMPLETE
                if allow_active_owner:
                    with cls._processes_lock:
                        if (
                            cls._active_gate_root_identities.get(str(root))
                            == expected_identity
                        ):
                            cls._active_gate_root_identities.pop(str(root), None)
                            cls._note_gate_namespace_change(root.name)
                cls._request_deferred_gate_discovery()
                return _GATE_REMOVAL_INCOMPLETE
            return _GATE_REMOVAL_UNSAFE
        finally:
            if root_descriptor is not None:
                os.close(root_descriptor)
            if parent_descriptor is not None:
                os.close(parent_descriptor)

    @classmethod
    def _abandoned_gate_quarantine(
        cls,
        quarantine: Path,
        *,
        now: float,
        allow_current_owner: bool = False,
    ) -> tuple[str, tuple[int, int]] | None:
        """Identify an aged quarantine left by a hard service crash.

        A stale root is atomically renamed before recursive deletion.  If the
        service dies between those operations, the next generation must be
        able to finish cleanup without treating an arbitrary dot-directory as
        operator-owned.  Require the exact generated name, the external owner
        record, its inode binding, and a dead/reused owner identity.
        """
        match = _GATE_ROOT_QUARANTINE_PATTERN.fullmatch(quarantine.name)
        if match is None:
            return None
        root_name = match.group("root")
        root = quarantine.parent / root_name
        quarantine_descriptor: int | None = None
        owner_descriptor: int | None = None
        try:
            quarantine_descriptor = os.open(
                quarantine,
                os.O_RDONLY
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_NOFOLLOW", 0),
            )
            metadata = os.fstat(quarantine_descriptor)
            if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.getuid():
                return None
            identity = (int(metadata.st_dev), int(metadata.st_ino))
            with cls._processes_lock:
                if (
                    str(root) in cls._active_gate_root_identities
                    or str(quarantine) in cls._active_gate_root_identities
                    or identity in cls._active_gate_root_identities.values()
                ):
                    return None

            try:
                owner_descriptor = os.open(
                    cls._gate_root_owner_path(root),
                    os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
                )
            except OSError:
                # The atomic rename itself is durable ownership evidence.  A
                # missing sidecar must not make an exact aged quarantine
                # immortal after a crash during metadata cleanup.
                return (
                    (root_name, identity)
                    if now - metadata.st_mtime >= _GATE_ROOT_MAX_AGE_SECONDS
                    else None
                )
            owner_metadata = os.fstat(owner_descriptor)
            if (
                not stat.S_ISREG(owner_metadata.st_mode)
                or owner_metadata.st_uid != os.getuid()
                or owner_metadata.st_size > 4096
            ):
                return (
                    (root_name, identity)
                    if now - owner_metadata.st_mtime >= _GATE_ROOT_MAX_AGE_SECONDS
                    else None
                )
            payload = os.read(owner_descriptor, 4097)
            try:
                owner = json.loads(payload.decode("utf-8"))
                owner_identity = (
                    int(owner["root_device"]),
                    int(owner["root_inode"]),
                )
                pid = int(owner["pid"])
                expected_ticks = int(owner["process_start_ticks"])
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                return (
                    (root_name, identity)
                    if now - owner_metadata.st_mtime >= _GATE_ROOT_MAX_AGE_SECONDS
                    else None
                )
            if owner_identity != identity:
                # Preserve a replacement at the quarantine name.  A valid
                # sidecar authorizes only its recorded inode, even after age.
                return None
            process_state, actual_ticks = cls._gate_process_identity(pid)
            if process_state == "unknown":
                return None
            if process_state == "alive" and actual_ticks == expected_ticks:
                return (
                    (root_name, identity)
                    if allow_current_owner and pid == os.getpid()
                    else None
                )
            return root_name, identity
        except OSError:
            return None
        finally:
            if owner_descriptor is not None:
                os.close(owner_descriptor)
            if quarantine_descriptor is not None:
                os.close(quarantine_descriptor)

    @classmethod
    def _remove_abandoned_gate_quarantine(
        cls,
        quarantine: Path,
        root_name: str,
        expected_identity: tuple[int, int],
    ) -> bool:
        """Reclaim one exact abandoned quarantine with restart-safe fencing."""
        root = quarantine.parent / root_name
        with cls._processes_lock:
            if (
                str(root) in cls._active_gate_root_identities
                or str(quarantine) in cls._active_gate_root_identities
                or expected_identity in cls._active_gate_root_identities.values()
            ):
                return False
        parent_descriptor: int | None = None
        quarantine_descriptor: int | None = None
        claimed_name = f".{root_name}.scavenge-{os.getpid()}-{time.time_ns()}"
        try:
            parent_descriptor = os.open(
                quarantine.parent,
                os.O_RDONLY
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_NOFOLLOW", 0),
            )
            quarantine_descriptor = os.open(
                quarantine.name,
                os.O_RDONLY
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=parent_descriptor,
            )
            current = os.fstat(quarantine_descriptor)
            if (int(current.st_dev), int(current.st_ino)) != expected_identity:
                return False
            with cls._processes_lock:
                if (
                    str(root) in cls._active_gate_root_identities
                    or str(quarantine) in cls._active_gate_root_identities
                    or expected_identity in cls._active_gate_root_identities.values()
                ):
                    return False
                os.rename(
                    quarantine.name,
                    claimed_name,
                    src_dir_fd=parent_descriptor,
                    dst_dir_fd=parent_descriptor,
                )
                cls._note_gate_namespace_change(root_name)
            claimed = os.stat(
                claimed_name,
                dir_fd=parent_descriptor,
                follow_symlinks=False,
            )
            if (int(claimed.st_dev), int(claimed.st_ino)) != expected_identity:
                try:
                    with cls._processes_lock:
                        os.rename(
                            claimed_name,
                            quarantine.name,
                            src_dir_fd=parent_descriptor,
                            dst_dir_fd=parent_descriptor,
                        )
                        cls._note_gate_namespace_change(root_name)
                except OSError:
                    pass
                return False
            removal = cls._remove_gate_tree_at(
                parent_descriptor,
                claimed_name,
                expected_identity,
                quarantine_descriptor,
            )
            if removal != _GATE_REMOVAL_REMOVED:
                if removal in {
                    _GATE_REMOVAL_PROGRESS,
                    _GATE_REMOVAL_INCOMPLETE,
                } and cls._schedule_deferred_gate_cleanup(
                    root,
                    quarantine.parent / claimed_name,
                    expected_identity,
                ):
                    return False
                try:
                    current_claimed = os.stat(
                        claimed_name,
                        dir_fd=parent_descriptor,
                        follow_symlinks=False,
                    )
                    if (
                        int(current_claimed.st_dev),
                        int(current_claimed.st_ino),
                    ) == expected_identity:
                        try:
                            os.stat(
                                quarantine.name,
                                dir_fd=parent_descriptor,
                                follow_symlinks=False,
                            )
                        except FileNotFoundError:
                            with cls._processes_lock:
                                os.rename(
                                    claimed_name,
                                    quarantine.name,
                                    src_dir_fd=parent_descriptor,
                                    dst_dir_fd=parent_descriptor,
                                )
                                cls._note_gate_namespace_change(root_name)
                except OSError:
                    pass
                return False
            return True
        except OSError:
            return False
        finally:
            if quarantine_descriptor is not None:
                os.close(quarantine_descriptor)
            if parent_descriptor is not None:
                os.close(parent_descriptor)

    @classmethod
    def _scavenge_abandoned_gate_quarantines(
        cls,
        temp_root: Path,
        *,
        now: float,
    ) -> tuple[int, bool]:
        """Bound recovery of roots already renamed for deletion."""
        removed = 0
        matched = 0
        inspected = 0
        complete = True
        deadline = time.monotonic() + _GATE_ROOT_DISCOVERY_SECONDS
        try:
            for quarantine in temp_root.iterdir():
                if (
                    inspected >= _GATE_ROOT_DISCOVERY_ENTRY_LIMIT
                    or matched >= _GATE_ROOT_SCAVENGE_LIMIT
                    or time.monotonic() >= deadline
                ):
                    complete = False
                    break
                inspected += 1
                if _GATE_ROOT_QUARANTINE_PATTERN.fullmatch(quarantine.name) is None:
                    continue
                matched += 1
                abandoned = cls._abandoned_gate_quarantine(quarantine, now=now)
                if abandoned is None:
                    continue
                root_name, identity = abandoned
                if cls._remove_abandoned_gate_quarantine(
                    quarantine,
                    root_name,
                    identity,
                ):
                    cls._unlink_gate_root_owner(temp_root / root_name)
                    removed += 1
        except OSError:
            complete = False
        return removed, complete

    @classmethod
    def _scavenge_orphan_gate_sidecars(
        cls,
        temp_root: Path,
        *,
        now: float,
    ) -> tuple[int, bool]:
        """Age-bound external owner records whose exact root no longer exists."""
        entries: list[Path] = []
        inspected = 0
        deadline = time.monotonic() + _GATE_ROOT_DISCOVERY_SECONDS
        with cls._processes_lock:
            namespace_generation = cls._gate_namespace_generation
        try:
            iterator = iter(temp_root.iterdir())
            while (
                inspected < _GATE_ROOT_DISCOVERY_ENTRY_LIMIT
                and time.monotonic() < deadline
            ):
                try:
                    path = next(iterator)
                except StopIteration:
                    break
                entries.append(path)
                inspected += 1
            else:
                # Sidecars may authorize quarantines anywhere in the temp
                # directory.  If the bounded snapshot is incomplete, retain
                # all sidecars rather than deleting authority on partial data.
                return 0, False
        except OSError:
            return 0, False
        claims_present = any(
            _GATE_SIDECAR_CLAIM_PATTERN.fullmatch(path.name) is not None
            or _GATE_SIDECAR_SWAP_PATTERN.fullmatch(path.name) is not None
            for path in entries
        )
        candidates = [
            path
            for path in entries
            if path.name.startswith(".")
            and path.name.endswith(_GATE_ROOT_OWNER_FILE)
            and _GATE_ROOT_NAME_RE.fullmatch(path.name[1 : -len(_GATE_ROOT_OWNER_FILE)])
            is not None
        ]
        quarantined_roots = {
            match.group("root")
            for path in entries
            if (match := _GATE_ROOT_QUARANTINE_PATTERN.fullmatch(path.name))
        }
        removed = 0
        suffix_length = len(_GATE_ROOT_OWNER_FILE)
        for sidecar in candidates[:_GATE_ROOT_SCAVENGE_LIMIT]:
            root_name = sidecar.name[1:-suffix_length]
            root = temp_root / root_name
            with cls._processes_lock:
                root_is_active = str(root) in cls._active_gate_root_identities
            if (
                _GATE_ROOT_NAME_RE.fullmatch(root_name) is None
                or root.exists()
                or root_is_active
                or root_name in quarantined_roots
            ):
                continue
            if cls._remove_orphan_gate_sidecar(
                sidecar,
                root_name,
                now=now,
                expected_namespace_generation=namespace_generation,
            ):
                removed += 1
        with cls._processes_lock:
            complete = (
                cls._gate_namespace_generation == namespace_generation
                and not claims_present
            )
        return removed, complete

    @classmethod
    def _scavenge_stale_gate_roots(cls) -> int:
        """Bound cleanup of roots abandoned by a dead service generation."""
        temp_root = Path(tempfile.gettempdir()).resolve()
        removed = 0
        matched = 0
        inspected = 0
        roots_complete = True
        deadline = time.monotonic() + _GATE_ROOT_DISCOVERY_SECONDS
        now = time.time()
        try:
            for root in temp_root.iterdir():
                if (
                    inspected >= _GATE_ROOT_DISCOVERY_ENTRY_LIMIT
                    or matched >= _GATE_ROOT_SCAVENGE_LIMIT
                    or time.monotonic() >= deadline
                ):
                    roots_complete = False
                    break
                inspected += 1
                if _GATE_ROOT_NAME_RE.fullmatch(root.name) is None:
                    continue
                matched += 1
                stale_identity = cls._stale_gate_root(root, now=now)
                if stale_identity is None:
                    continue
                if (
                    cls._remove_stale_gate_root(root, stale_identity)
                    == _GATE_REMOVAL_REMOVED
                ):
                    removed += 1
        except OSError:
            roots_complete = False
        quarantines_removed, quarantines_complete = (
            cls._scavenge_abandoned_gate_quarantines(
                temp_root,
                now=now,
            )
        )
        sidecars_removed, sidecars_complete = cls._scavenge_orphan_gate_sidecars(
            temp_root,
            now=now,
        )
        if removed:
            logger.info("Scavenged %d stale quality-gate root(s)", removed)
        if quarantines_removed:
            logger.info(
                "Scavenged %d abandoned quality-gate quarantine(s)",
                quarantines_removed,
            )
        if sidecars_removed:
            logger.info(
                "Scavenged %d orphan quality-gate owner sidecar(s)",
                sidecars_removed,
            )
        if not (roots_complete and quarantines_complete and sidecars_complete):
            # The bounded synchronous pass keeps gate construction latency
            # fixed. A single process-wide worker resumes persistent passes so
            # entries beyond either cap cannot starve across repeated starts.
            cls._request_deferred_gate_discovery()
        return removed + quarantines_removed

    @classmethod
    def _gate_run_root(cls) -> Path:
        """Create one liveness-owned container for all candidate capabilities."""
        container = Path(tempfile.mkdtemp(prefix=_GATE_CONTAINER_PREFIX))
        try:
            os.chmod(container, 0o700)
            root = container / _GATE_MUTABLE_ROOT_NAME
            root.mkdir(mode=0o700)
            for relative in ("home", "tmp", "cache", "config", "data", "lifecycle"):
                path = root / relative
                path.mkdir(mode=0o700)

            trusted_home = container / _GATE_TRUSTED_HOME_ROOT_NAME
            trusted_home.mkdir(mode=0o700)
            worker_parent = trusted_home / "pytest-workers"
            worker_parent.mkdir(mode=0o700)
            (worker_parent / "session").mkdir(mode=0o700)

            # Keep the synthetic identity beside, never below, either writable
            # candidate capability.  It is exposed only through read-only /etc
            # binds constructed by _sandbox_command.
            identity_root = container / _GATE_IDENTITY_ROOT_NAME
            identity_root.mkdir(mode=0o700)
            identity_payloads = {
                "passwd": (
                    f"oompah:x:{os.geteuid()}:{os.getegid()}:"
                    f"Oompah Quality Gate:{_SANDBOX_HOME}:/bin/sh\n"
                ),
                "group": f"oompah:x:{os.getegid()}:\n",
                "nsswitch.conf": "passwd: files\ngroup: files\nshadow: files\n",
            }
            for name, payload in identity_payloads.items():
                destination = identity_root / name
                destination.write_text(payload, encoding="utf-8")
                destination.chmod(0o444)
            identity_root.chmod(0o500)

            cls._write_gate_root_owner(container)
            cls._register_gate_root(container)
            return root
        except Exception:
            cls._forget_gate_root(container)
            cls._unlink_gate_root_owner(container)
            identity_root = container / _GATE_IDENTITY_ROOT_NAME
            if identity_root.exists():
                identity_root.chmod(0o700)
            shutil.rmtree(container, ignore_errors=True)
            raise

    @classmethod
    def _cleanup_gate_run_root(cls, root: Path) -> None:
        """Remove the exact container created by :meth:`_gate_run_root`."""
        container = root.parent
        try:
            resolved = root.resolve(strict=False)
            temp_root = Path(tempfile.gettempdir()).resolve()
            container = resolved.parent
            if (
                resolved.name != _GATE_MUTABLE_ROOT_NAME
                or container.parent != temp_root
                or _GATE_ROOT_NAME_RE.fullmatch(container.name) is None
                or root.is_symlink()
                or container.is_symlink()
                or container.stat().st_uid != os.geteuid()
            ):
                logger.warning("Refusing to remove unexpected gate root %s", root)
                return
            identity_root = container / _GATE_IDENTITY_ROOT_NAME
            identity_info = identity_root.stat(follow_symlinks=False)
            if (
                identity_root.is_symlink()
                or not identity_root.is_dir()
                or identity_info.st_uid != os.geteuid()
                or identity_info.st_mode & 0o777 != 0o500
            ):
                logger.warning("Refusing to remove untrusted gate identity %s", root)
                return
            with cls._processes_lock:
                expected_identity = cls._active_gate_root_identities.get(str(container))
            if expected_identity is None:
                logger.warning(
                    "Refusing to remove unowned gate container %s", container
                )
                return
            removal = cls._remove_stale_gate_root(
                container,
                expected_identity,
                allow_active_owner=True,
            )
            if removal == _GATE_REMOVAL_UNSAFE:
                logger.warning(
                    "Failed to clean exact quality gate container %s", container
                )
        except FileNotFoundError:
            cls._forget_gate_root(container)
            cls._unlink_gate_root_owner(container)
        except OSError as exc:
            logger.warning("Failed to clean quality gate root %s: %s", root, exc)

    @classmethod
    def _gate_trusted_home_root(cls, run_root: Path) -> Path:
        """Return the server-owned HOME capability beside candidate state.

        The candidate's general writable state is mounted at
        :data:`_SANDBOX_RUN_ROOT`.  Native-validation guard ownership cannot
        be trusted anywhere below that mount, so allocate a unique sibling
        and expose only this otherwise-empty directory at a distinct mount.
        This protects guard state from the nested managed-Codex task sandbox;
        the outer exact-gate candidate remains the in-process test harness and
        necessarily writes the guard while exercising it.
        """
        resolved_run_root = run_root.resolve(strict=True)
        container = resolved_run_root.parent
        temp_root = Path(tempfile.gettempdir()).resolve()
        root = container / _GATE_TRUSTED_HOME_ROOT_NAME
        resolved = root.resolve(strict=True)
        worker_root = resolved / "pytest-workers" / "session"
        if (
            resolved_run_root.name != _GATE_MUTABLE_ROOT_NAME
            or container.parent != temp_root
            or _GATE_ROOT_NAME_RE.fullmatch(container.name) is None
            or run_root.is_symlink()
            or container.is_symlink()
            or root.is_symlink()
            or not resolved.is_dir()
            or resolved.parent != container
            or resolved == resolved_run_root
            or resolved_run_root in resolved.parents
            or resolved in resolved_run_root.parents
            or resolved.stat().st_uid != os.getuid()
            or not worker_root.is_dir()
        ):
            raise OSError("trusted gate HOME overlaps candidate run state")
        return resolved

    @classmethod
    def _cleanup_gate_trusted_home_root(cls, root: Path) -> None:
        """Leave trusted HOME cleanup to its liveness-owned container."""
        # This capability must never outlive the run root, but independently
        # deleting or unregistering it would split one atomic lifecycle unit.
        # _cleanup_gate_run_root validates and removes the entire container.
        return None

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
    def _quality_gate_environment(
        run_root: Path,
        trusted_home_root: Path,
        *,
        sandbox_visible: bool = True,
    ) -> dict[str, str]:
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
        # Built-in bwrap exposes stable sandbox paths and keeps high-churn
        # pytest state on private tmpfs.  Injected three-argument launchers run
        # on the host, so materialize every path below this gate's container.
        visible_run_root = (
            _SANDBOX_RUN_ROOT if sandbox_visible else run_root.resolve(strict=True)
        )
        visible_home_root = (
            _SANDBOX_TRUSTED_HOME_ROOT
            if sandbox_visible
            else trusted_home_root.resolve(strict=True)
        )
        visible_worker_home_root = visible_home_root / "pytest-workers" / "session"
        private_tmp = _SANDBOX_TMP_ROOT if sandbox_visible else visible_run_root / "tmp"
        private_lifecycle = visible_run_root / "lifecycle"
        if (
            trusted_home_root.resolve(strict=True) == run_root.resolve(strict=True)
            or run_root.resolve(strict=True)
            in trusted_home_root.resolve(strict=True).parents
            or trusted_home_root.resolve(strict=True)
            in run_root.resolve(strict=True).parents
        ):
            raise OSError("trusted gate HOME overlaps candidate run state")
        # Bind-and-close allocation is the portable interface available to the
        # existing Makefile contract.  The candidate still cannot select the
        # operator's configured port because this value is server-generated.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            private_port = str(listener.getsockname()[1])

        environment.update(
            {
                "OOMPAH_PYTEST_GATE": "1",
                "OOMPAH_PYTEST_RUN_ROOT": str(visible_run_root),
                "OOMPAH_PYTEST_CANDIDATE_RUN_ROOT": str(visible_run_root),
                "OOMPAH_PYTEST_TRUSTED_HOME_ROOT": str(visible_home_root),
                "OOMPAH_PYTEST_WORKER_HOME_ROOT": str(visible_worker_home_root),
                "OOMPAH_PYTEST_TEMP_ROOT": str(private_tmp),
                "OOMPAH_TEMP_ROOT": str(private_tmp),
                "OOMPAH_TEST_SERVER_PORT": private_port,
                "OOMPAH_SERVER_PORT": private_port,
                "OOMPAH_TEST_PID_FILE": str(private_lifecycle / ".oompah.pid"),
                "OOMPAH_TEST_PID_META_FILE": str(
                    private_lifecycle / ".oompah.pid.meta"
                ),
                "HOME": str(visible_home_root),
                "TMPDIR": str(private_tmp),
                "TMP": str(private_tmp),
                "TEMP": str(private_tmp),
                "XDG_CACHE_HOME": str(private_tmp / "cache"),
                "XDG_CONFIG_HOME": str(private_tmp / "config"),
                "XDG_DATA_HOME": str(private_tmp / "data"),
                "PYTHONPYCACHEPREFIX": str(private_tmp / "pycache"),
            }
        )
        return environment

    @staticmethod
    def _sandbox_command(
        command: str,
        repo_path: str,
        run_root: Path,
        trusted_home_root: Path,
    ) -> list[str]:
        """Return a bubblewrap command with host lifecycle state hidden.

        The candidate command runs in a private mount, PID, and network
        namespace.  The repository, one general run root, and one otherwise
        empty trusted-HOME capability are the only writable host paths made
        visible.  If bubblewrap or unprivileged namespaces are unavailable,
        the caller fails closed before starting candidate code.
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
        identity_files = BranchQualityGate._gate_identity_files(run_root)
        trusted_home = trusted_home_root.resolve(strict=True)
        resolved_run_root = run_root.resolve(strict=True)
        if (
            trusted_home_root.is_symlink()
            or not trusted_home.is_dir()
            or trusted_home.parent != resolved_run_root.parent
            or trusted_home.name != _GATE_TRUSTED_HOME_ROOT_NAME
            or trusted_home == resolved_run_root
            or resolved_run_root in trusted_home.parents
            or trusted_home in resolved_run_root.parents
            or trusted_home.stat().st_uid != os.getuid()
        ):
            raise _SandboxUnavailable(
                "trusted quality-gate HOME overlaps candidate run state"
            )

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
            str(_SANDBOX_TMP_ROOT),
            "--dir",
            str(_SANDBOX_TMP_ROOT / "cache"),
            "--dir",
            str(_SANDBOX_TMP_ROOT / "config"),
            "--dir",
            str(_SANDBOX_TMP_ROOT / "data"),
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
            "--dir",
            str(_SANDBOX_HOME),
            "--dir",
            "/etc",
            "--ro-bind",
            str(identity_files["passwd"]),
            "/etc/passwd",
            "--ro-bind",
            str(identity_files["group"]),
            "/etc/group",
            "--ro-bind",
            str(identity_files["nsswitch.conf"]),
            "/etc/nsswitch.conf",
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
            _SANDBOX_HOME,
            Path("/etc"),
            _SANDBOX_TMP_ROOT,
            _SANDBOX_TMP_ROOT / "cache",
            _SANDBOX_TMP_ROOT / "config",
            _SANDBOX_TMP_ROOT / "data",
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
        # Make owns the corresponding lock exclusively while inspecting or
        # repairing editable metadata. A gate waits for that bounded repair,
        # and a canonical service checkout can safely repair a stale mapping
        # once before candidate authority is consumed.
        declared_editable_source = _validate_or_repair_trusted_runtime_source(
            runtime_prefix,
            repo,
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
        add_destination(_SANDBOX_TRUSTED_HOME_ROOT)
        args.extend(
            [
                "--bind",
                str(repo),
                str(repo),
                "--bind",
                str(run_root),
                str(_SANDBOX_RUN_ROOT),
                "--bind",
                str(trusted_home_root),
                str(_SANDBOX_TRUSTED_HOME_ROOT),
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

    @staticmethod
    def _completed_duration_seconds(raw: object) -> int | None:
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            return None
        duration = float(raw)
        if not math.isfinite(duration) or duration <= 0:
            return None
        return max(1, int(math.ceil(duration)))

    @classmethod
    def _durations_from_entries(
        cls,
        entries: dict[str, dict],
    ) -> dict[tuple[str, str], int]:
        observed: dict[tuple[str, str], int] = {}
        for raw in entries.values():
            if not isinstance(raw, dict):
                continue
            status = str(raw.get("status") or "")
            if status not in {"passed", "failed"}:
                continue
            # Legacy failed rows did not preserve the raw subprocess exit.
            # Some of those rows may therefore be externally-terminated gates
            # misclassified as candidate failures.  Do not use them as proof
            # that the command completed or as runtime high-water evidence.
            if status == "failed":
                return_code = raw.get("return_code")
                if (
                    isinstance(return_code, bool)
                    or not isinstance(return_code, int)
                    or return_code <= 0
                ):
                    continue
            repo_identity = str(raw.get("repo_identity") or "").strip()
            command = str(raw.get("command") or "").strip()
            seconds = cls._completed_duration_seconds(raw.get("duration_seconds"))
            if not repo_identity or not command or seconds is None:
                continue
            key = (repo_identity, command)
            observed[key] = max(observed.get(key, 0), seconds)
        return observed

    @classmethod
    def _decode_duration_high_water(
        cls,
        raw: object,
    ) -> dict[tuple[str, str], int]:
        if raw is None:
            return {}
        if not isinstance(raw, list):
            raise ValueError("duration_high_water_seconds must be a list")
        observed: dict[tuple[str, str], int] = {}
        for item in raw:
            if not isinstance(item, dict):
                raise ValueError("duration high-water entries must be objects")
            repo_identity = item.get("repo_identity")
            command = item.get("command")
            raw_seconds = item.get("seconds")
            if not isinstance(repo_identity, str) or not repo_identity.strip():
                raise ValueError("duration high-water repository identity is invalid")
            if not isinstance(command, str) or not command.strip():
                raise ValueError("duration high-water command is invalid")
            if (
                isinstance(raw_seconds, bool)
                or not isinstance(raw_seconds, int)
                or raw_seconds <= 0
            ):
                raise ValueError(
                    "duration high-water seconds must be a positive integer"
                )
            key = (repo_identity.strip(), command.strip())
            observed[key] = max(observed.get(key, 0), raw_seconds)
        return observed

    def _load_state(
        self,
        *,
        strict: bool,
    ) -> tuple[dict[str, dict], dict[tuple[str, str], int], str]:
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}, {}, "absent"
        except OSError as exc:
            if strict:
                raise QualityGateEvidenceUnavailable(
                    f"quality-gate evidence is unavailable ({type(exc).__name__})"
                ) from exc
            return {}, {}, "unavailable"
        except json.JSONDecodeError as exc:
            if strict:
                raise QualityGateEvidenceCorrupt(
                    "quality-gate evidence is not valid JSON"
                ) from exc
            return {}, {}, "corrupt"
        if not isinstance(raw, dict):
            if strict:
                raise QualityGateEvidenceCorrupt(
                    "quality-gate evidence root must be an object"
                )
            return {}, {}, "corrupt"
        load_status = "available"
        entries = raw.get("results", {}) if isinstance(raw, dict) else {}
        if not entries and isinstance(raw, dict):
            entries = raw.get("passed", {})
        if not isinstance(entries, dict):
            if strict:
                raise QualityGateEvidenceCorrupt(
                    "quality-gate results must be an object"
                )
            entries = {}
            load_status = "corrupt"
        elif any(
            not isinstance(key, str) or not isinstance(value, dict)
            for key, value in entries.items()
        ):
            if strict:
                raise QualityGateEvidenceCorrupt(
                    "quality-gate result entries must be named objects"
                )
            entries = {
                key: value
                for key, value in entries.items()
                if isinstance(key, str) and isinstance(value, dict)
            }
            load_status = "corrupt"
        try:
            high_water = self._decode_duration_high_water(
                raw.get("duration_high_water_seconds")
            )
        except ValueError as exc:
            if strict:
                raise QualityGateEvidenceCorrupt(str(exc)) from exc
            high_water = {}
            load_status = "corrupt"
        for key, seconds in self._durations_from_entries(entries).items():
            high_water[key] = max(high_water.get(key, 0), seconds)
        return entries, high_water, load_status

    def _load(self) -> dict[str, dict]:
        entries, _high_water, _load_status = self._load_state(strict=False)
        return entries

    def observed_command_durations_seconds(self) -> QualityGateDurationEvidence:
        """Return conservative completed runtimes by repository and command.

        Passed and ordinary failed gates both ran to a real completion and are
        useful duration evidence. Timed-out/interrupted/infrastructure results
        are excluded because their elapsed value is a lifecycle bound rather
        than evidence of how long the command needs to finish.
        """

        try:
            with self._lock:
                _entries, observed, load_status = self._load_state(strict=True)
        except QualityGateEvidenceCorrupt as exc:
            return QualityGateDurationEvidence({}, "corrupt", str(exc))
        except QualityGateEvidenceUnavailable as exc:
            return QualityGateDurationEvidence({}, "unavailable", str(exc))
        return QualityGateDurationEvidence(observed, load_status)

    def _save(
        self,
        entries: dict[str, dict],
        duration_high_water: dict[tuple[str, str], int] | None = None,
    ) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        high_water = (
            duration_high_water
            if duration_high_water is not None
            else self._durations_from_entries(entries)
        )
        serialized_high_water = [
            {
                "repo_identity": repo_identity,
                "command": command,
                "seconds": seconds,
            }
            for (repo_identity, command), seconds in sorted(high_water.items())
        ]
        payload = (
            json.dumps(
                {
                    "version": _EVIDENCE_VERSION,
                    "results": entries,
                    "duration_high_water_seconds": serialized_high_water,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
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
            entries, duration_high_water, _load_status = self._load_state(strict=False)
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
            completed_verdict = result.status == "passed" or (
                result.status == "failed"
                and result.return_code is not None
                and result.return_code > 0
            )
            if completed_verdict:
                seconds = self._completed_duration_seconds(result.duration_seconds)
                if seconds is not None:
                    duration_key = (repo_identity.strip(), result.command.strip())
                    if all(duration_key):
                        duration_high_water[duration_key] = max(
                            duration_high_water.get(duration_key, 0),
                            seconds,
                        )
            try:
                self._save(entries, duration_high_water)
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
        # Protected-workflow attestations are deliberately not ordinary cache
        # results.  A normal lookup or run must execute locally unless it sees
        # an ordinary result; only the separately bound lookup below may turn
        # an attestation into a runtime PASS.
        if not status or status == _PROTECTED_WORKFLOW_ATTESTED_STATUS:
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

        raw_return_code = entry.get("return_code")
        return_code = (
            raw_return_code
            if isinstance(raw_return_code, int)
            and not isinstance(raw_return_code, bool)
            else None
        )
        raw_terminating_signal = entry.get("terminating_signal")
        terminating_signal = (
            raw_terminating_signal
            if isinstance(raw_terminating_signal, int)
            and not isinstance(raw_terminating_signal, bool)
            and raw_terminating_signal > 0
            else None
        )
        if return_code is not None and return_code < 0:
            expected_signal = -return_code
            if terminating_signal not in {None, expected_signal}:
                return None
            terminating_signal = expected_signal
        elif terminating_signal is not None:
            # A signal is only meaningful for Python's negative subprocess
            # return-code convention.  Reject inconsistent evidence rather
            # than presenting fabricated termination provenance.
            return None

        raw_owner = entry.get("owner")
        evidence_owner: dict[str, str] | None = None
        if isinstance(raw_owner, dict):
            expected_owner_fields = {
                "project_id",
                "task_id",
                "head_sha",
                "authority_generation",
            }
            if expected_owner_fields.issubset(raw_owner):
                decoded_owner = {
                    field_name: str(raw_owner.get(field_name) or "")
                    for field_name in expected_owner_fields
                }
                if all(decoded_owner.values()) and all(
                    len(value) <= 512 for value in decoded_owner.values()
                ):
                    evidence_owner = decoded_owner
        raw_generation = entry.get("authority_generation")
        authority_generation = (
            str(raw_generation)
            if (
                isinstance(raw_generation, str)
                and raw_generation
                and len(raw_generation) <= 512
            )
            else None
        )
        if evidence_owner is not None:
            if evidence_owner["head_sha"].strip().lower() != head_sha.lower():
                return None
            owner_generation = evidence_owner["authority_generation"]
            if (
                authority_generation is not None
                and authority_generation != owner_generation
            ):
                return None
            authority_generation = owner_generation
        raw_interrupted = entry.get("interrupted", False)
        interrupted = raw_interrupted if isinstance(raw_interrupted, bool) else False
        raw_interruption_source = entry.get("interruption_source")
        interruption_source = (
            str(raw_interruption_source)
            if isinstance(raw_interruption_source, str) and raw_interruption_source
            else None
        )
        raw_cancellation = entry.get("cancellation")
        cancellation = (
            {
                str(key): str(value)
                for key, value in raw_cancellation.items()
                if isinstance(key, str) and isinstance(value, str)
            }
            if isinstance(raw_cancellation, dict)
            else None
        )
        return QualityGateResult(
            status=status,
            head_sha=head_sha,
            command=command,
            duration_seconds=duration,
            output_tail=str(entry.get("output_tail", "") or ""),
            cached=True,
            recorded_at=recorded_at,
            cancellation=cancellation,
            return_code=return_code,
            terminating_signal=terminating_signal,
            interrupted=interrupted,
            interruption_source=interruption_source,
            owner=evidence_owner,
            authority_generation=authority_generation,
        )

    @staticmethod
    def _protected_workflow_provenance_from_proof(
        proof: ProtectedWorkflowQualityEvidenceProof,
    ) -> dict[str, object] | None:
        """Canonicalize a complete verified proof or reject it fail-closed."""

        if not isinstance(proof, ProtectedWorkflowQualityEvidenceProof):
            return None
        if (
            isinstance(proof.schema_version, bool)
            or proof.schema_version != _PROTECTED_WORKFLOW_PROVENANCE_VERSION
        ):
            return None

        bounded_strings = (
            proof.repo_identity,
            proof.repository,
            proof.target_branch,
            proof.work_branch,
            proof.command,
            proof.workflow_path,
            proof.checkout_mode,
            proof.event,
            proof.app_slug,
        )
        if any(
            not isinstance(value, str)
            or not value
            or value != value.strip()
            or len(value) > 4096
            or any(ord(character) < 32 or ord(character) == 127 for character in value)
            for value in bounded_strings
        ):
            return None
        if (
            proof.repository != proof.repository.lower()
            or re.fullmatch(
                r"[a-z0-9_.-]+/[a-z0-9_.-]+",
                proof.repository,
            )
            is None
        ):
            return None
        workflow_path = PurePosixPath(proof.workflow_path)
        if (
            workflow_path.is_absolute()
            or ".." in workflow_path.parts
            or not proof.workflow_path.startswith(".github/workflows/")
            or workflow_path.suffix not in {".yml", ".yaml"}
            or str(workflow_path) != proof.workflow_path
        ):
            return None
        if proof.event != "pull_request" or proof.checkout_mode not in {
            "explicit_review_head",
            "merge_tree_equivalent",
        }:
            return None
        if re.fullmatch(r"[a-z0-9][a-z0-9-]{0,99}", proof.app_slug) is None:
            return None

        if (
            not isinstance(proof.merge_parent_shas, tuple)
            or len(proof.merge_parent_shas) != 2
        ):
            return None
        git_hashes = (
            proof.head_sha,
            proof.head_tree_sha,
            proof.base_sha,
            proof.merge_sha,
            proof.merge_tree_sha,
            proof.run_head_sha,
            proof.check_suite_head_sha,
            proof.workflow_blob_sha,
            *proof.merge_parent_shas,
        )
        if any(
            not isinstance(value, str)
            or value != value.strip().lower()
            or re.fullmatch(r"[0-9a-f]{40,64}", value) is None
            for value in git_hashes
        ):
            return None
        if proof.merge_parent_shas != (proof.base_sha, proof.head_sha):
            return None
        if (
            proof.checkout_mode == "merge_tree_equivalent"
            and proof.head_tree_sha != proof.merge_tree_sha
        ):
            return None
        if proof.run_head_sha not in {proof.head_sha, proof.merge_sha}:
            return None
        if (
            proof.run_status != "completed"
            or proof.run_conclusion != "success"
            or proof.check_suite_status != "completed"
            or proof.check_suite_conclusion != "success"
            or proof.check_suite_head_sha != proof.run_head_sha
            or proof.check_suite_app_id != proof.app_id
        ):
            return None

        fingerprints = (
            proof.task_audit_fingerprint,
            proof.trust_config_fingerprint,
        )
        if any(
            not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None
            for value in fingerprints
        ):
            return None
        positive_integers = (
            proof.workflow_id,
            proof.app_id,
            proof.pull_request_number,
            proof.run_id,
            proof.run_attempt,
            proof.check_suite_id,
            proof.check_suite_app_id,
        )
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value <= 0
            for value in positive_integers
        ):
            return None

        if not isinstance(proof.required_jobs, tuple) or not proof.required_jobs:
            return None
        if any(
            not isinstance(name, str)
            or not name
            or name != name.strip()
            or len(name) > 255
            or any(ord(character) < 32 or ord(character) == 127 for character in name)
            for name in proof.required_jobs
        ):
            return None
        if proof.required_jobs != tuple(sorted(proof.required_jobs)) or len(
            proof.required_jobs
        ) != len(set(proof.required_jobs)):
            return None
        if not isinstance(proof.required_steps, tuple) or not proof.required_steps:
            return None
        if any(
            not isinstance(name, str)
            or not name
            or name != name.strip()
            or len(name) > 255
            or any(ord(character) < 32 or ord(character) == 127 for character in name)
            for name in proof.required_steps
        ):
            return None
        if proof.required_steps != tuple(sorted(proof.required_steps)) or len(
            proof.required_steps
        ) != len(set(proof.required_steps)):
            return None
        if not isinstance(proof.jobs, tuple) or len(proof.jobs) != len(
            proof.required_jobs
        ):
            return None
        canonical_jobs: list[dict[str, object]] = []
        for job in proof.jobs:
            if not isinstance(job, ProtectedWorkflowJobProof):
                return None
            if (
                not isinstance(job.name, str)
                or not job.name
                or job.name != job.name.strip()
                or len(job.name) > 255
                or job.status != "completed"
                or job.conclusion != "success"
                or job.run_attempt != proof.run_attempt
                or job.head_sha != proof.run_head_sha
                or job.check_status != "completed"
                or job.check_conclusion != "success"
                or job.check_head_sha != proof.run_head_sha
                or job.app_id != proof.app_id
                or job.app_slug != proof.app_slug
            ):
                return None
            if any(
                isinstance(value, bool) or not isinstance(value, int) or value <= 0
                for value in (
                    job.job_id,
                    job.run_attempt,
                    job.check_run_id,
                    job.app_id,
                )
            ):
                return None
            if not isinstance(job.required_steps, tuple) or len(
                job.required_steps
            ) != len(proof.required_steps):
                return None
            canonical_steps: list[dict[str, object]] = []
            for step in job.required_steps:
                if (
                    not isinstance(step, ProtectedWorkflowStepProof)
                    or step.name not in proof.required_steps
                    or step.status != "completed"
                    or step.conclusion != "success"
                    or isinstance(step.number, bool)
                    or not isinstance(step.number, int)
                    or step.number <= 0
                ):
                    return None
                canonical_steps.append(
                    {
                        "conclusion": step.conclusion,
                        "name": step.name,
                        "number": step.number,
                        "status": step.status,
                    }
                )
            canonical_steps.sort(key=lambda item: str(item["name"]))
            if tuple(
                str(item["name"]) for item in canonical_steps
            ) != proof.required_steps or len(
                {int(item["number"]) for item in canonical_steps}
            ) != len(canonical_steps):
                return None
            canonical_jobs.append(
                {
                    "app_id": job.app_id,
                    "app_slug": job.app_slug,
                    "check_conclusion": job.check_conclusion,
                    "check_head_sha": job.check_head_sha,
                    "check_run_id": job.check_run_id,
                    "check_status": job.check_status,
                    "conclusion": job.conclusion,
                    "head_sha": job.head_sha,
                    "job_id": job.job_id,
                    "name": job.name,
                    "run_attempt": job.run_attempt,
                    "status": job.status,
                    "required_steps": canonical_steps,
                }
            )
        canonical_jobs.sort(key=lambda item: str(item["name"]))
        if tuple(str(item["name"]) for item in canonical_jobs) != proof.required_jobs:
            return None
        if len({int(item["job_id"]) for item in canonical_jobs}) != len(
            canonical_jobs
        ) or len({int(item["check_run_id"]) for item in canonical_jobs}) != len(
            canonical_jobs
        ):
            return None

        return {
            "app_id": proof.app_id,
            "app_slug": proof.app_slug,
            "base_sha": proof.base_sha,
            "check_suite_id": proof.check_suite_id,
            "check_suite_app_id": proof.check_suite_app_id,
            "check_suite_conclusion": proof.check_suite_conclusion,
            "check_suite_head_sha": proof.check_suite_head_sha,
            "check_suite_status": proof.check_suite_status,
            "checkout_mode": proof.checkout_mode,
            "command": proof.command,
            "event": proof.event,
            "head_sha": proof.head_sha,
            "head_tree_sha": proof.head_tree_sha,
            "jobs": canonical_jobs,
            "merge_parent_shas": list(proof.merge_parent_shas),
            "merge_sha": proof.merge_sha,
            "merge_tree_sha": proof.merge_tree_sha,
            "pull_request_number": proof.pull_request_number,
            "repo_identity": proof.repo_identity,
            "repository": proof.repository,
            "required_jobs": list(proof.required_jobs),
            "required_steps": list(proof.required_steps),
            "run_attempt": proof.run_attempt,
            "run_conclusion": proof.run_conclusion,
            "run_head_sha": proof.run_head_sha,
            "run_id": proof.run_id,
            "run_status": proof.run_status,
            "schema_version": proof.schema_version,
            "target_branch": proof.target_branch,
            "task_audit_fingerprint": proof.task_audit_fingerprint,
            "trust_config_fingerprint": proof.trust_config_fingerprint,
            "work_branch": proof.work_branch,
            "workflow_blob_sha": proof.workflow_blob_sha,
            "workflow_id": proof.workflow_id,
            "workflow_path": proof.workflow_path,
        }

    @classmethod
    def _decode_protected_workflow_attestation(
        cls,
        entry: object,
        *,
        repo_identity: str,
        target_branch: str,
        work_branch: str,
        head_sha: str,
        command: str,
        task_audit_fingerprint: str,
        trust_config_fingerprint: str,
    ) -> QualityGateResult | None:
        """Decode a locally stored attestation only under current bindings."""

        if not isinstance(entry, dict) or set(entry) != {
            "command",
            "duration_seconds",
            "head_sha",
            "output_tail",
            "protected_workflow_provenance",
            "protected_workflow_provenance_fingerprint",
            "recorded_at",
            "repo_identity",
            "status",
            "target_branch",
            "work_branch",
        }:
            return None
        if entry.get("status") != _PROTECTED_WORKFLOW_ATTESTED_STATUS:
            return None
        if entry.get("duration_seconds") != 0.0:
            return None
        expected_identity = {
            "repo_identity": repo_identity,
            "target_branch": target_branch,
            "work_branch": work_branch,
            "head_sha": head_sha,
            "command": command,
        }
        if any(entry.get(name) != value for name, value in expected_identity.items()):
            return None
        provenance = entry.get("protected_workflow_provenance")
        if not isinstance(provenance, dict):
            return None
        expected_provenance_fields = {
            "app_id",
            "app_slug",
            "base_sha",
            "check_suite_id",
            "check_suite_app_id",
            "check_suite_conclusion",
            "check_suite_head_sha",
            "check_suite_status",
            "checkout_mode",
            "command",
            "event",
            "head_sha",
            "head_tree_sha",
            "jobs",
            "merge_parent_shas",
            "merge_sha",
            "merge_tree_sha",
            "pull_request_number",
            "repo_identity",
            "repository",
            "required_jobs",
            "required_steps",
            "run_attempt",
            "run_conclusion",
            "run_head_sha",
            "run_id",
            "run_status",
            "schema_version",
            "target_branch",
            "task_audit_fingerprint",
            "trust_config_fingerprint",
            "work_branch",
            "workflow_blob_sha",
            "workflow_id",
            "workflow_path",
        }
        if set(provenance) != expected_provenance_fields:
            return None
        raw_jobs = provenance.get("jobs")
        raw_required_jobs = provenance.get("required_jobs")
        raw_required_steps = provenance.get("required_steps")
        raw_merge_parents = provenance.get("merge_parent_shas")
        if (
            not isinstance(raw_jobs, list)
            or not isinstance(raw_required_jobs, list)
            or not isinstance(raw_required_steps, list)
            or not isinstance(raw_merge_parents, list)
        ):
            return None
        try:
            proof = ProtectedWorkflowQualityEvidenceProof(
                repo_identity=provenance["repo_identity"],
                repository=provenance["repository"],
                target_branch=provenance["target_branch"],
                work_branch=provenance["work_branch"],
                head_sha=provenance["head_sha"],
                head_tree_sha=provenance["head_tree_sha"],
                base_sha=provenance["base_sha"],
                merge_sha=provenance["merge_sha"],
                merge_tree_sha=provenance["merge_tree_sha"],
                merge_parent_shas=tuple(raw_merge_parents),
                command=provenance["command"],
                task_audit_fingerprint=provenance["task_audit_fingerprint"],
                trust_config_fingerprint=provenance["trust_config_fingerprint"],
                workflow_id=provenance["workflow_id"],
                workflow_path=provenance["workflow_path"],
                workflow_blob_sha=provenance["workflow_blob_sha"],
                checkout_mode=provenance["checkout_mode"],
                event=provenance["event"],
                app_id=provenance["app_id"],
                app_slug=provenance["app_slug"],
                required_jobs=tuple(raw_required_jobs),
                required_steps=tuple(raw_required_steps),
                jobs=tuple(
                    ProtectedWorkflowJobProof(
                        name=raw_job["name"],
                        job_id=raw_job["job_id"],
                        run_attempt=raw_job["run_attempt"],
                        head_sha=raw_job["head_sha"],
                        status=raw_job["status"],
                        conclusion=raw_job["conclusion"],
                        check_run_id=raw_job["check_run_id"],
                        check_status=raw_job["check_status"],
                        check_conclusion=raw_job["check_conclusion"],
                        check_head_sha=raw_job["check_head_sha"],
                        app_id=raw_job["app_id"],
                        app_slug=raw_job["app_slug"],
                        required_steps=tuple(
                            ProtectedWorkflowStepProof(
                                name=raw_step["name"],
                                number=raw_step["number"],
                                status=raw_step["status"],
                                conclusion=raw_step["conclusion"],
                            )
                            for raw_step in raw_job["required_steps"]
                            if isinstance(raw_step, dict)
                            and set(raw_step)
                            == {"conclusion", "name", "number", "status"}
                        ),
                    )
                    for raw_job in raw_jobs
                    if isinstance(raw_job, dict)
                    and set(raw_job)
                    == {
                        "app_id",
                        "app_slug",
                        "check_conclusion",
                        "check_head_sha",
                        "check_run_id",
                        "check_status",
                        "conclusion",
                        "head_sha",
                        "job_id",
                        "name",
                        "run_attempt",
                        "status",
                        "required_steps",
                    }
                ),
                pull_request_number=provenance["pull_request_number"],
                run_id=provenance["run_id"],
                run_attempt=provenance["run_attempt"],
                run_head_sha=provenance["run_head_sha"],
                run_status=provenance["run_status"],
                run_conclusion=provenance["run_conclusion"],
                check_suite_id=provenance["check_suite_id"],
                check_suite_status=provenance["check_suite_status"],
                check_suite_conclusion=provenance["check_suite_conclusion"],
                check_suite_head_sha=provenance["check_suite_head_sha"],
                check_suite_app_id=provenance["check_suite_app_id"],
                schema_version=provenance["schema_version"],
            )
        except (KeyError, TypeError, ValueError):
            return None
        canonical = cls._protected_workflow_provenance_from_proof(proof)
        if canonical is None or canonical != provenance:
            return None
        if (
            provenance["task_audit_fingerprint"] != task_audit_fingerprint
            or provenance["trust_config_fingerprint"] != trust_config_fingerprint
        ):
            return None
        provenance_fingerprint = hashlib.sha256(
            json.dumps(
                canonical,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        if (
            entry.get("protected_workflow_provenance_fingerprint")
            != provenance_fingerprint
        ):
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
        return QualityGateResult(
            status="passed",
            head_sha=head_sha,
            command=command,
            duration_seconds=0.0,
            output_tail=str(entry.get("output_tail") or ""),
            cached=True,
            recorded_at=recorded_at,
        )

    def import_protected_workflow_pass(
        self,
        proof: ProtectedWorkflowQualityEvidenceProof,
        *,
        output_tail: str = "",
    ) -> bool:
        """Persist a verified protected-workflow pass as distinct evidence."""

        provenance = self._protected_workflow_provenance_from_proof(proof)
        if provenance is None:
            return False
        key = self._evidence_key(
            repo_identity=proof.repo_identity,
            target_branch=proof.target_branch,
            work_branch=proof.work_branch,
            head_sha=proof.head_sha,
            command=proof.command,
        )
        provenance_fingerprint = hashlib.sha256(
            json.dumps(
                provenance,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        with self._key_lock(key):
            try:
                with self._lock:
                    entries, duration_high_water, _status = self._load_state(
                        strict=True
                    )
                    existing = entries.get(key)
                    ordinary = self._decode_evidence_result(
                        existing,
                        repo_identity=proof.repo_identity,
                        target_branch=proof.target_branch,
                        work_branch=proof.work_branch,
                        head_sha=proof.head_sha,
                        command=proof.command,
                    )
                    if ordinary is not None and ordinary.status == "passed":
                        return True
                    if isinstance(existing, dict):
                        existing_status = existing.get("status")
                        if existing_status == _PROTECTED_WORKFLOW_ATTESTED_STATUS:
                            existing_provenance = existing.get(
                                "protected_workflow_provenance"
                            )
                            existing_fingerprint = existing.get(
                                "protected_workflow_provenance_fingerprint"
                            )
                            if (
                                existing_provenance == provenance
                                and existing_fingerprint == provenance_fingerprint
                            ):
                                # An identical import is a no-op so its durable
                                # timestamp remains stable across retries, but
                                # only after the complete serialized row has
                                # passed the same strict decoder as lookup.
                                return (
                                    self._decode_protected_workflow_attestation(
                                        existing,
                                        repo_identity=proof.repo_identity,
                                        target_branch=proof.target_branch,
                                        work_branch=proof.work_branch,
                                        head_sha=proof.head_sha,
                                        command=proof.command,
                                        task_audit_fingerprint=(
                                            proof.task_audit_fingerprint
                                        ),
                                        trust_config_fingerprint=(
                                            proof.trust_config_fingerprint
                                        ),
                                    )
                                    is not None
                                )
                            if not isinstance(existing_provenance, dict):
                                return False
                            stored_audit = existing_provenance.get(
                                "task_audit_fingerprint"
                            )
                            stored_trust = existing_provenance.get(
                                "trust_config_fingerprint"
                            )
                            if not isinstance(stored_audit, str) or not isinstance(
                                stored_trust, str
                            ):
                                return False
                            if (
                                self._decode_protected_workflow_attestation(
                                    existing,
                                    repo_identity=proof.repo_identity,
                                    target_branch=proof.target_branch,
                                    work_branch=proof.work_branch,
                                    head_sha=proof.head_sha,
                                    command=proof.command,
                                    task_audit_fingerprint=stored_audit,
                                    trust_config_fingerprint=stored_trust,
                                )
                                is None
                            ):
                                return False
                        elif existing_status not in {
                            "failed",
                            "timed_out",
                            "error",
                            "infrastructure_error",
                            "interrupted",
                        }:
                            # Do not erase an unknown or malformed local PASS.
                            return False
                    entries[key] = {
                        "command": proof.command,
                        "duration_seconds": 0.0,
                        "head_sha": proof.head_sha,
                        "output_tail": str(output_tail or "")[
                            -self.output_tail_bytes :
                        ],
                        "protected_workflow_provenance": provenance,
                        "protected_workflow_provenance_fingerprint": (
                            provenance_fingerprint
                        ),
                        "recorded_at": time.time(),
                        "repo_identity": proof.repo_identity,
                        "status": _PROTECTED_WORKFLOW_ATTESTED_STATUS,
                        "target_branch": proof.target_branch,
                        "work_branch": proof.work_branch,
                    }
                    if len(entries) > 500:
                        entries = dict(
                            sorted(
                                entries.items(),
                                key=lambda item: float(
                                    item[1].get("recorded_at", 0) or 0
                                ),
                                reverse=True,
                            )[:500]
                        )
                    self._save(entries, duration_high_water)
            except (
                OSError,
                OverflowError,
                QualityGateEvidenceCorrupt,
                QualityGateEvidenceUnavailable,
                TypeError,
                ValueError,
            ):
                return False
        return True

    def lookup_protected_workflow_pass(
        self,
        *,
        repo_identity: str,
        target_branch: str,
        work_branch: str,
        head_sha: str,
        command: str,
        task_audit_fingerprint: str,
        trust_config_fingerprint: str,
    ) -> QualityGateResult | None:
        """Locally consume an attestation under exact current audit/trust bindings."""

        values = (
            repo_identity,
            target_branch,
            work_branch,
            command,
        )
        if any(
            not isinstance(value, str) or not value or value != value.strip()
            for value in values
        ):
            return None
        if (
            not isinstance(head_sha, str)
            or head_sha != head_sha.strip().lower()
            or re.fullmatch(r"[0-9a-f]{40,64}", head_sha) is None
            or not isinstance(task_audit_fingerprint, str)
            or re.fullmatch(r"[0-9a-f]{64}", task_audit_fingerprint) is None
            or not isinstance(trust_config_fingerprint, str)
            or re.fullmatch(r"[0-9a-f]{64}", trust_config_fingerprint) is None
        ):
            return None
        key = self._evidence_key(
            repo_identity=repo_identity,
            target_branch=target_branch,
            work_branch=work_branch,
            head_sha=head_sha,
            command=command,
        )
        try:
            with self._lock:
                entries, _duration_high_water, _status = self._load_state(strict=True)
                entry = entries.get(key)
        except (
            OSError,
            QualityGateEvidenceCorrupt,
            QualityGateEvidenceUnavailable,
        ):
            return None
        return self._decode_protected_workflow_attestation(
            entry,
            repo_identity=repo_identity,
            target_branch=target_branch,
            work_branch=work_branch,
            head_sha=head_sha,
            command=command,
            task_audit_fingerprint=task_audit_fingerprint,
            trust_config_fingerprint=trust_config_fingerprint,
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

        if isinstance(duration_seconds, bool) or not isinstance(
            duration_seconds,
            (int, float),
        ):
            return False
        normalized_duration = float(duration_seconds)
        if not math.isfinite(normalized_duration) or normalized_duration < 0:
            return False

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
            duration_seconds=normalized_duration,
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
                if entry.users == 0 and self._key_locks.get(key) is entry:
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
        force_recheck: bool = False,
        expected_head_sha: str | None = None,
        require_source_head_match: bool = True,
        generation: str | None = None,
        owner: QualityGateOwner | None = None,
        is_current: Callable[[], bool] | None = None,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> QualityGateResult:
        """Return passing evidence or execute the configured full check.

        When retry_forced=True, bypasses cached candidate failures and
        timeouts. Runner/infrastructure outcomes are always re-executed;
        passed results remain cached and reusable. ``force_recheck`` also
        bypasses a cached pass when external base-generation evidence changed
        while the candidate head remained immutable.

        ``owner`` binds cancellation to the exact project/task/head and
        authority generation.  ``generation`` remains a compatibility path
        for legacy unowned callers; production orchestration passes ``owner``.

        Pre-spawn barriers
        ------------------
        Two deterministic checkpoints prevent stale gate spawns:

        1. Before snapshot creation: checks tombstone + local cancellation +
           full ``is_current`` revalidation.
        2. After snapshot creation, before Popen: repeats those checks.

        A third barrier closes the Popen-to-registration window: after
        registering the process, the code re-checks the tombstone under the
        same lock and immediately kills+marks-interrupted any process that
        was cancelled between Popen and registration.

        ``is_cancelled`` is the bounded, local predicate used in the 50/100ms
        capacity and process-monitor loops.  ``is_current`` may perform full
        tracker, dependency, and remote-head revalidation, so it is used only
        at the deterministic external-execution barriers and after PASS.
        """
        command = str(command or "").strip()
        if not command:
            return QualityGateResult(
                status="not_configured",
                head_sha=self._head_sha(repo_path),
                command="",
            )

        owned_generation = str(generation) if generation is not None else None
        if owned_generation is not None and len(owned_generation) > 512:
            return QualityGateResult(
                status="infrastructure_error",
                head_sha="",
                command=command,
                output_tail="Quality gate authority generation is too large.",
            )
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

        def _owned_result(
            *,
            status: str,
            head_sha: str,
            duration_seconds: float = 0.0,
            output_tail: str = "",
            cancellation: dict[str, str] | None = None,
            return_code: int | None = None,
            interrupted: bool = False,
            interruption_source: str | None = None,
        ) -> QualityGateResult:
            """Build one result with bounded, exact attempt provenance."""

            normalized_return_code = (
                return_code
                if isinstance(return_code, int) and not isinstance(return_code, bool)
                else None
            )
            return QualityGateResult(
                status=status,
                head_sha=head_sha,
                command=command,
                duration_seconds=duration_seconds,
                output_tail=str(output_tail or "")[-self.output_tail_bytes :],
                cancellation=cancellation,
                return_code=normalized_return_code,
                terminating_signal=(
                    -normalized_return_code
                    if normalized_return_code is not None and normalized_return_code < 0
                    else None
                ),
                interrupted=bool(interrupted),
                interruption_source=(
                    str(interruption_source)[:128] if interruption_source else None
                ),
                owner=(owned_owner.to_dict() if owned_owner is not None else None),
                authority_generation=(
                    str(owned_generation) if owned_generation is not None else None
                ),
            )

        def _local_authority_cancelled() -> bool:
            """Return local cancellation without tracker or forge I/O."""

            if owned_generation is not None and self._generation_is_cancelled(
                owned_generation,
                owner_key,
            ):
                return True
            if is_cancelled is None:
                return False
            try:
                return bool(is_cancelled())
            except Exception as exc:  # noqa: BLE001 - cancellation fails closed
                logger.warning(
                    "Quality gate local authority check failed: %s",
                    exc,
                )
                return True

        def _full_authority_is_current(*, boundary: str) -> bool:
            """Run the local fence and optional expensive boundary CAS."""

            if _local_authority_cancelled():
                return False
            if is_current is None:
                return True
            try:
                return bool(is_current())
            except Exception as exc:  # noqa: BLE001 - authority fails closed
                logger.warning(
                    "Quality gate %s authority check failed: %s",
                    boundary,
                    exc,
                )
                return False

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
            if force_recheck:
                return loaded, None
            if cached_result is None:
                return loaded, None
            # Runner/infrastructure termination is diagnostic evidence, not a
            # reusable verdict about candidate code.  Legacy failed rows also
            # lack enough exit evidence to prove that the command completed,
            # so rerun them once under the structured schema.
            if (
                cached_result.status
                in {
                    "infrastructure_error",
                    "error",
                    "interrupted",
                }
                or (
                    cached_result.status == "failed"
                    and (
                        cached_result.return_code is None
                        or cached_result.return_code <= 0
                    )
                )
                or (
                    cached_result.status == "timed_out"
                    and (
                        cached_result.return_code is None
                        or cached_result.interruption_source != "timeout"
                    )
                )
            ):
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
        validation_owner = None

        def _lease_cancellation() -> dict[str, str] | None:
            if self.validation_lease is None or validation_owner is None:
                return None
            try:
                return self.validation_lease.cancellation_for(validation_owner)
            except (AttributeError, OSError, sqlite3.Error, ValidationLeaseError):
                # Lightweight test/legacy lease facades may not expose
                # cancellation provenance.  They remain usable; only the
                # durable lease can turn an external process stop into a
                # retryable scheduling outcome.
                return None

        if self.validation_lease is not None:
            validation_owner = ValidationLeaseOwner.exact_gate(
                project_id=(
                    owned_owner.project_id if owned_owner is not None else repo_identity
                ),
                task_id=(
                    owned_owner.task_id if owned_owner is not None else work_branch
                ),
                authority_generation=(
                    owned_owner.authority_generation
                    if owned_owner is not None
                    else f"{head_sha}:{key}"
                ),
            )

            def _lease_wait_cancelled() -> bool:
                return _local_authority_cancelled()

            try:
                validation_handle = self.validation_lease.acquire(
                    validation_owner,
                    is_cancelled=_lease_wait_cancelled,
                )
            except ValidationLeaseCancelled as exc:
                cancellation = _lease_cancellation()
                _release_owned_generation()
                return _owned_result(
                    status="interrupted",
                    head_sha=head_sha,
                    output_tail=str(exc),
                    cancellation=cancellation,
                    interrupted=True,
                    interruption_source="validation_lease_cancellation",
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
            registration_token: object | None = None
            run_root: Path | None = None
            trusted_home_root: Path | None = None
            snapshot: Path | None = None
            monitor_stop = threading.Event()
            monitor: threading.Thread | None = None
            try:
                run_root = self._gate_run_root()
                trusted_home_root = self._gate_trusted_home_root(run_root)
                # --- Barrier 1: before snapshot creation ---
                # Check authority before creating the immutable archive.
                # cancel_generation() may have been called while we were
                # waiting in the key lock or the evidence load above.
                if owned_generation is not None and self._generation_is_cancelled(
                    owned_generation,
                    owner_key,
                ):
                    return _owned_result(
                        status="interrupted",
                        head_sha=head_sha,
                        duration_seconds=time.monotonic() - started,
                        output_tail="Gate cancelled before snapshot creation.",
                        interrupted=True,
                        interruption_source=(
                            "owner_cancellation"
                            if owned_owner is not None
                            else "generation_cancellation"
                        ),
                    )
                if not _full_authority_is_current(boundary="pre-snapshot"):
                    return _owned_result(
                        status="interrupted",
                        head_sha=head_sha,
                        duration_seconds=time.monotonic() - started,
                        output_tail="Gate authority withdrawn before snapshot creation.",
                        interrupted=True,
                        interruption_source="authority_withdrawn",
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
                    return _owned_result(
                        status="interrupted",
                        head_sha=head_sha,
                        duration_seconds=time.monotonic() - started,
                        output_tail="Gate cancelled after snapshot creation, before spawn.",
                        interrupted=True,
                        interruption_source=(
                            "owner_cancellation"
                            if owned_owner is not None
                            else "generation_cancellation"
                        ),
                    )
                if not _full_authority_is_current(boundary="pre-spawn"):
                    return _owned_result(
                        status="interrupted",
                        head_sha=head_sha,
                        duration_seconds=time.monotonic() - started,
                        output_tail="Gate authority withdrawn after snapshot, before spawn.",
                        interrupted=True,
                        interruption_source="authority_withdrawn",
                    )

                try:
                    sandbox_visible_environment = True
                    if self._sandbox_launcher is None:
                        sandboxed_command = self._sandbox_command(
                            command,
                            str(snapshot),
                            run_root,
                            trusted_home_root,
                        )
                    else:
                        sandbox_visible_environment = False
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
                    env=self._quality_gate_environment(
                        run_root,
                        trusted_home_root,
                        sandbox_visible=sandbox_visible_environment,
                    ),
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
                    registration_token = object()
                    active_state_callbacks = self._register_active_process_locked(
                        process,
                        generation=owned_generation,
                        owner=owned_owner,
                        snapshot=snapshot,
                        callback=self._active_state_changed,
                        registration_token=registration_token,
                    )
                    # Check tombstone under the same lock that cancel_generation
                    # uses to add to _cancelled_generations and mark _interrupted.
                    post_spawn_cancelled = (
                        owner_key in self._cancelled_owner_keys
                        if owner_key is not None
                        else owned_generation in self._cancelled_generations
                    )
                    if post_spawn_cancelled:
                        setattr(process, "_oompah_interrupted", True)
                        setattr(
                            process,
                            "_oompah_interruption_source",
                            (
                                "owner_cancellation"
                                if owned_owner is not None
                                else "generation_cancellation"
                            ),
                        )

                self._notify_active_state_changed(active_state_callbacks)

                if post_spawn_cancelled:
                    # Kill the just-spawned process; the normal flow will
                    # see _oompah_interrupted=True and return interrupted.
                    try:
                        self._signal_active_process_group(
                            process.pid,
                            process,
                            registration_token,
                            signal.SIGTERM,
                        )
                    except (ProcessLookupError, OSError):
                        pass

                if is_cancelled is not None:

                    def _monitor_gate_authority() -> None:
                        while not monitor_stop.wait(0.1):
                            if _local_authority_cancelled():
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
                combined = "\n".join(part for part in (stdout, stderr) if part)
                output_tail = combined.encode("utf-8", errors="replace")[
                    -self.output_tail_bytes :
                ].decode("utf-8", errors="replace")
                with self._processes_lock:
                    interrupted = bool(getattr(process, "_oompah_interrupted", False))
                cancellation = _lease_cancellation()
                interrupted = interrupted or cancellation is not None
                return_code = process.returncode
                if interrupted:
                    return _owned_result(
                        status="interrupted",
                        head_sha=head_sha,
                        duration_seconds=duration,
                        output_tail=output_tail,
                        cancellation=cancellation,
                        return_code=return_code,
                        interrupted=True,
                        interruption_source=(
                            "validation_lease_cancellation"
                            if cancellation is not None
                            else str(
                                getattr(
                                    process,
                                    "_oompah_interruption_source",
                                    "owner_cancellation",
                                )
                            )
                        ),
                    )
                if return_code is not None and return_code < 0:
                    result = _owned_result(
                        status="infrastructure_error",
                        head_sha=head_sha,
                        duration_seconds=duration,
                        output_tail=output_tail,
                        return_code=return_code,
                        interrupted=True,
                        interruption_source="external_signal",
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
                if return_code is None:
                    result = _owned_result(
                        status="infrastructure_error",
                        head_sha=head_sha,
                        duration_seconds=duration,
                        output_tail=output_tail,
                        interrupted=True,
                        interruption_source="missing_exit_status",
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
                if return_code != 0:
                    result = _owned_result(
                        status="failed",
                        head_sha=head_sha,
                        duration_seconds=duration,
                        output_tail=output_tail,
                        return_code=return_code,
                        interruption_source="process_exit",
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
                if not _full_authority_is_current(boundary="post-pass"):
                    return _owned_result(
                        status="interrupted",
                        head_sha=head_sha,
                        duration_seconds=duration,
                        output_tail=(
                            output_tail
                            or "Gate authority changed after the command passed."
                        ),
                        return_code=return_code,
                        interrupted=True,
                        interruption_source="authority_withdrawn",
                    )
            except subprocess.TimeoutExpired as exc:
                assert process is not None
                try:
                    if registration_token is not None:
                        self._signal_active_process_group(
                            process.pid,
                            process,
                            registration_token,
                            signal.SIGKILL,
                        )
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
                    interrupted = bool(getattr(process, "_oompah_interrupted", False))
                cancellation = _lease_cancellation()
                interrupted = interrupted or cancellation is not None
                return_code = process.returncode
                if interrupted:
                    return _owned_result(
                        status="interrupted",
                        head_sha=head_sha,
                        duration_seconds=duration,
                        output_tail=combined[-self.output_tail_bytes :],
                        cancellation=cancellation,
                        return_code=return_code,
                        interrupted=True,
                        interruption_source=(
                            "validation_lease_cancellation"
                            if cancellation is not None
                            else str(
                                getattr(
                                    process,
                                    "_oompah_interruption_source",
                                    "owner_cancellation",
                                )
                            )
                        ),
                    )
                result = _owned_result(
                    status="timed_out",
                    head_sha=head_sha,
                    duration_seconds=duration,
                    output_tail=combined[-self.output_tail_bytes :],
                    return_code=return_code,
                    interruption_source="timeout",
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
            except ValidationLeaseCancelled as exc:
                return _owned_result(
                    status="interrupted",
                    head_sha=head_sha,
                    duration_seconds=time.monotonic() - started,
                    output_tail=str(exc),
                    cancellation=_lease_cancellation(),
                    return_code=(process.returncode if process is not None else None),
                    interrupted=True,
                    interruption_source="validation_lease_cancellation",
                )
            except (OSError, sqlite3.Error, ValidationLeaseError) as exc:
                result = _owned_result(
                    status="error",
                    head_sha=head_sha,
                    duration_seconds=time.monotonic() - started,
                    output_tail=str(exc),
                    return_code=(process.returncode if process is not None else None),
                    interruption_source="runner_error",
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
                if process is not None and registration_token is not None:
                    with self._processes_lock:
                        callback = self._remove_active_process_locked(
                            process.pid,
                            expected_process=process,
                            expected_registration_token=registration_token,
                        )
                    if callback is not None:
                        self._notify_active_state_changed((callback,))
                if validation_handle is not None:
                    validation_handle.release()
                # A cancelled generation remains fenced until every caller
                # already registered for it has crossed the barrier.  This
                # prevents one interrupted caller from clearing the tombstone
                # while another is still waiting on this evidence-key lock.
                _release_owned_generation()
                if trusted_home_root is not None:
                    self._cleanup_gate_trusted_home_root(trusted_home_root)
                if run_root is not None:
                    self._cleanup_gate_run_root(run_root)

            result = _owned_result(
                status="passed",
                head_sha=head_sha,
                duration_seconds=duration,
                output_tail=output_tail,
                return_code=(process.returncode if process is not None else 0),
                interruption_source="process_exit",
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
