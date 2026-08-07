"""Durable host capacity for heavyweight validation commands.

The coordination database is the durable source of queue and ownership
metadata.  A POSIX ``flock`` on each configured capacity slot is the execution
fence: it is inherited by the validation subprocess, so loss of the service
process cannot make a still-running command disappear from capacity.
"""

from __future__ import annotations

import contextlib
import ctypes
import logging
import os
import re
import shlex
import signal
import shutil
import sqlite3
import stat
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Iterator, Mapping

try:  # pragma: no cover - the service runtime is POSIX-only today
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]


logger = logging.getLogger(__name__)

_ABSOLUTE_LIGHTWEIGHT_INSPECTION_TOOLS = frozenset(
    {
        "awk",
        "cat",
        "cut",
        "diff",
        "find",
        "git",
        "grep",
        "head",
        "jq",
        "ls",
        "pwd",
        "rg",
        "sed",
        "stat",
        "tail",
        "wc",
    }
)
_OPAQUE_SHELL_EXECUTORS = frozenset(
    {
        ".",
        "awk",
        "eval",
        "parallel",
        "source",
        "xargs",
    }
)
_SHELL_CONTROL_WORDS = frozenset(
    {
        "case",
        "do",
        "done",
        "elif",
        "else",
        "esac",
        "fi",
        "for",
        "function",
        "if",
        "select",
        "then",
        "until",
        "while",
    }
)
_VALIDATION_GUARD_ENV_NAMES = frozenset(
    {
        "BASHOPTS",
        "BASH_ENV",
        "BASH_XTRACEFD",
        "ENV",
        "HOME",
        "OOMPAH_NATIVE_VALIDATION_BASH_ARGV0",
        "OOMPAH_NATIVE_VALIDATION_BOUNDARY_GROUP",
        "OOMPAH_NATIVE_VALIDATION_CAPABILITY_FD",
        "OOMPAH_NATIVE_VALIDATION_GUARD",
        "PATH",
        "PROMPT_COMMAND",
        "PS4",
        "PYTEST_ADDOPTS",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD",
        "PYTEST_PLUGINS",
        "PYTHONHOME",
        "PYTHONPATH",
        "PYTHONSTARTUP",
        "MAKEFILES",
        "MAKEFLAGS",
        "GNUMAKEFLAGS",
        "MFLAGS",
        "NODE_OPTIONS",
        "NODE_PATH",
        "NPM_CONFIG_SCRIPT_SHELL",
        "PNPM_SCRIPT_SHELL",
        "RIPGREP_CONFIG_PATH",
        "RUBYLIB",
        "RUBYOPT",
        "RUSTC_WRAPPER",
        "RUSTC_WORKSPACE_WRAPPER",
        "RUSTC",
        "RUSTDOC",
        "RUSTFLAGS",
        "CARGO_BUILD_RUSTC",
        "CARGO_BUILD_RUSTC_WRAPPER",
        "CARGO_BUILD_RUSTC_WORKSPACE_WRAPPER",
        "CARGO_BUILD_RUSTDOC",
        "CARGO_BUILD_RUSTDOCFLAGS",
        "CARGO_BUILD_RUSTFLAGS",
        "CARGO_ENCODED_RUSTFLAGS",
        "CARGO_ENCODED_RUSTDOCFLAGS",
        "CARGO_HOME",
        "SHELL",
        "SHELLOPTS",
        "YARN_SCRIPT_SHELL",
        "ZDOTDIR",
        "npm_config_script_shell",
    }
)
_SHELL_ENVIRONMENT_MUTATORS = frozenset(
    {
        "declare",
        "env",
        "export",
        "local",
        "printf",
        "readonly",
        "typeset",
        "unset",
    }
)
_LIGHTWEIGHT_COMMAND_NAMES = _ABSOLUTE_LIGHTWEIGHT_INSPECTION_TOOLS | frozenset(
    {
        ":",
        "echo",
        "false",
        "printf",
        "sleep",
        "test",
        "true",
    }
)
_LIGHTWEIGHT_SHELL_BUILTINS = frozenset(
    {":", "echo", "false", "printf", "test", "true"}
)

_DYNAMIC_LOADER_ENVIRONMENT_NAMES = frozenset(
    {
        # AIX and HP-UX equivalents of the ELF and Mach-O loader controls.
        "LDR_CNTRL",
        "LDR_PRELOAD",
        "LDR_PRELOAD64",
        "LIBPATH",
        "SHLIB_PATH",
    }
)


def _is_dynamic_loader_environment_name(name: str) -> bool:
    """Return whether *name* can alter a process before its entry point.

    ELF and Mach-O loaders expose families of ``LD_*`` and ``DYLD_*``
    controls, including preload, audit, and library-search hooks.  Matching
    the families avoids leaving a platform-specific spelling as an execution
    path before the validation shim or a supposedly lightweight executable
    gets control.
    """

    normalized = str(name).removesuffix("+")
    return (
        normalized in _DYNAMIC_LOADER_ENVIRONMENT_NAMES
        or normalized.startswith("LD_")
        or normalized.startswith("DYLD_")
        or normalized.startswith("_RLD_")
    )


def _is_validation_guard_environment_name(name: str) -> bool:
    """Return whether changing *name* can execute before a nested guard."""

    normalized = str(name).removesuffix("+")
    return (
        _is_dynamic_loader_environment_name(normalized)
        or normalized in _VALIDATION_GUARD_ENV_NAMES
        or normalized.startswith("BASH_FUNC_")
        or (
            normalized.startswith("CARGO_TARGET_")
            and normalized.endswith(
                ("_LINKER", "_RUNNER", "_RUSTFLAGS", "_RUSTDOCFLAGS")
            )
        )
    )


_CLASSIFIED_COMMAND_NAMES = frozenset(
    {
        "bash",
        "cargo",
        "dash",
        "make",
        "node",
        "nox",
        "npm",
        "perl",
        "pnpm",
        "py.test",
        "pytest",
        "python",
        "python3",
        "ruby",
        "sh",
        "tox",
        "uv",
        "yarn",
        "zsh",
    }
)
_CANCELLED_OWNER_RETENTION_SECONDS = 24 * 60 * 60
_CANCELLED_OWNER_LIMIT = 1024

VALIDATION_KIND_EXACT_GATE = "exact_gate"
VALIDATION_KIND_AUDITOR = "auditor"
VALIDATION_KIND_WORKER = "worker"
EXACT_GATE_PRIORITY = 20
AUDITOR_PRIORITY = 10
WORKER_PRIORITY = 0
_SCHEMA_VERSION = 1


class ValidationLeaseError(RuntimeError):
    """Base class for validation-capacity failures."""


class ValidationLeaseCancelled(ValidationLeaseError):
    """Raised when authority is withdrawn while a caller is queued."""


@dataclass(frozen=True)
class ValidationLeaseOwner:
    """Trusted identity attached to one validation request."""

    kind: str
    project_id: str
    task_id: str
    authority_generation: str
    priority: int

    def __post_init__(self) -> None:
        if self.kind not in {
            VALIDATION_KIND_EXACT_GATE,
            VALIDATION_KIND_AUDITOR,
            VALIDATION_KIND_WORKER,
        }:
            raise ValueError(f"unsupported validation owner kind: {self.kind!r}")
        if not all(
            str(value or "").strip()
            for value in (self.project_id, self.task_id, self.authority_generation)
        ):
            raise ValueError("validation lease owner metadata must be complete")

    @classmethod
    def exact_gate(
        cls,
        *,
        project_id: str,
        task_id: str,
        authority_generation: str,
    ) -> "ValidationLeaseOwner":
        return cls(
            kind=VALIDATION_KIND_EXACT_GATE,
            project_id=project_id,
            task_id=task_id,
            authority_generation=authority_generation,
            priority=EXACT_GATE_PRIORITY,
        )

    @classmethod
    def auditor(
        cls,
        *,
        project_id: str,
        task_id: str,
        authority_generation: str,
    ) -> "ValidationLeaseOwner":
        return cls(
            kind=VALIDATION_KIND_AUDITOR,
            project_id=project_id,
            task_id=task_id,
            authority_generation=authority_generation,
            priority=AUDITOR_PRIORITY,
        )

    @classmethod
    def worker(
        cls,
        *,
        project_id: str,
        task_id: str,
        authority_generation: str,
    ) -> "ValidationLeaseOwner":
        return cls(
            kind=VALIDATION_KIND_WORKER,
            project_id=project_id,
            task_id=task_id,
            authority_generation=authority_generation,
            priority=WORKER_PRIORITY,
        )


@dataclass(frozen=True)
class ValidationLeaseStatus:
    """Authoritative, cross-process validation-capacity snapshot."""

    capacity: int
    owner_count: int
    waiter_count: int
    oldest_waiter_age_seconds: float
    owners: tuple[dict[str, object], ...]
    waiters: tuple[dict[str, object], ...]

    @property
    def available_capacity(self) -> int:
        return max(self.capacity - self.owner_count, 0)

    def to_dict(self) -> dict[str, object]:
        legacy_provider_bootstrap_owner_count = sum(
            1
            for owner in self.owners
            if owner.get("process_role") == "legacy_provider_bootstrap"
        )
        return {
            "capacity": self.capacity,
            "available_capacity": self.available_capacity,
            "owner_count": self.owner_count,
            "waiter_count": self.waiter_count,
            "oldest_waiter_age_seconds": self.oldest_waiter_age_seconds,
            "owners": list(self.owners),
            "waiters": list(self.waiters),
            "legacy_provider_bootstrap_owner_count": (
                legacy_provider_bootstrap_owner_count
            ),
            # A normal capacity wait is activity, not an actionable warning.
            "status": (
                "action_required"
                if legacy_provider_bootstrap_owner_count
                else "busy"
                if self.waiter_count or self.owner_count
                else "idle"
            ),
        }


def _process_start_ticks(pid: int) -> int | None:
    """Return Linux process start ticks, which fence PID reuse."""

    try:
        raw = Path(f"/proc/{int(pid)}/stat").read_text(encoding="utf-8")
        return int(raw[raw.rfind(")") + 2 :].split()[19])
    except (OSError, ValueError, IndexError):
        return None


def _process_stat(pid: int) -> tuple[str, int, int] | None:
    """Return state, process-group id, and start ticks for one Linux PID."""

    try:
        raw = Path(f"/proc/{int(pid)}/stat").read_text(encoding="utf-8")
        fields = raw[raw.rfind(")") + 2 :].split()
        return fields[0], int(fields[2]), int(fields[19])
    except (OSError, ValueError, IndexError):
        return None


def _process_identity_alive(pid: object, start_ticks: object) -> bool:
    try:
        expected = int(start_ticks)
        current = _process_start_ticks(int(pid))
    except (TypeError, ValueError):
        return False
    return current is not None and current == expected


def _process_parent_identity(pid: int) -> tuple[int, int] | None:
    """Return the exact current parent PID/start-tick identity."""

    try:
        raw = Path(f"/proc/{int(pid)}/stat").read_text(encoding="utf-8")
        fields = raw[raw.rfind(")") + 2 :].split()
        parent_pid = int(fields[1])
    except (OSError, ValueError, IndexError):
        return None
    parent_ticks = _process_start_ticks(parent_pid)
    if parent_ticks is None:
        return None
    return parent_pid, parent_ticks


def _is_legacy_provider_bootstrap_snapshot(
    arguments: tuple[str, ...],
    environment: dict[str, str],
    entrypoint_prefix: bytes,
    *,
    entrypoint_matches_operator: bool,
    interpreter_matches_operator: bool,
    parent_matches_operator: bool,
    bootstrap_is_task_writable: bool,
) -> bool:
    return (
        len(arguments) >= 4
        and os.path.basename(arguments[0]) == "node"
        and arguments[2] == "exec"
        and "--experimental-json" in arguments[3:]
        and entrypoint_prefix.startswith(b"#!/usr/bin/env node")
        and environment.get("CODEX_INTERNAL_ORIGINATOR_OVERRIDE") == "codex_sdk_ts"
        and entrypoint_matches_operator
        and interpreter_matches_operator
        and parent_matches_operator
        and not bootstrap_is_task_writable
    )


def _path_is_within(path: Path, roots: Iterable[Path]) -> bool:
    return any(path == root or root in path.parents for root in roots)


def _trusted_codex_bootstrap_identity(
) -> tuple[Path, tuple[int, int], Path, tuple[int, int]] | None:
    """Resolve the operator's current Codex launcher and Node identities."""

    try:
        from agents.extensions.experimental.codex.exec import find_codex_path

        entrypoint = Path(find_codex_path()).resolve(strict=True)
        interpreter_raw = shutil.which(
            "node",
            path=str(os.environ.get("PATH") or os.defpath),
        )
        if not interpreter_raw:
            return None
        interpreter = Path(interpreter_raw).resolve(strict=True)
        entrypoint_stat = entrypoint.stat()
        interpreter_stat = interpreter.stat()
    except Exception:  # noqa: BLE001 - optional observability must fail closed
        return None
    return (
        entrypoint,
        (int(entrypoint_stat.st_dev), int(entrypoint_stat.st_ino)),
        interpreter,
        (int(interpreter_stat.st_dev), int(interpreter_stat.st_ino)),
    )


def _legacy_provider_bootstrap_process(
    pid: object,
    start_ticks: object,
    trusted_identity: tuple[Path, tuple[int, int], Path, tuple[int, int]] | None,
    trusted_parent_identity: tuple[int, int] | None,
) -> bool:
    """Recognize a pre-fix Codex provider root holding a command lease.

    This is observability only; it never terminates a process or releases a
    fence.  The exact PID/start-tick pair is checked before and after reading
    procfs.  The SDK origin marker plus the npm Node/``codex exec`` invocation
    shape distinguish the long-lived provider root from ordinary Node tests.
    """

    try:
        normalized_pid = int(pid)
        expected_ticks = int(start_ticks)
    except (TypeError, ValueError):
        return False
    if not _process_identity_alive(normalized_pid, expected_ticks):
        return False
    if trusted_identity is None:
        return False
    (
        trusted_entrypoint,
        trusted_entrypoint_identity,
        trusted_interpreter,
        trusted_interpreter_identity,
    ) = trusted_identity
    try:
        arguments = tuple(
            value.decode("utf-8", errors="replace")
            for value in Path(f"/proc/{normalized_pid}/cmdline").read_bytes().split(b"\0")
            if value
        )
        environment: dict[str, str] = {}
        for item in Path(f"/proc/{normalized_pid}/environ").read_bytes().split(
            b"\0"
        ):
            key, separator, value = item.partition(b"=")
            if separator and key:
                environment[key.decode("utf-8", errors="replace")] = value.decode(
                    "utf-8", errors="replace"
                )
        entrypoint = Path(arguments[1]).resolve(strict=True)
        interpreter = Path(f"/proc/{normalized_pid}/exe").resolve(strict=True)
        cwd = Path(f"/proc/{normalized_pid}/cwd").resolve(strict=True)
        entrypoint_stat = entrypoint.stat()
        interpreter_stat = interpreter.stat()
        with entrypoint.open("rb") as stream:
            entrypoint_prefix = stream.read(128)
    except (OSError, IndexError, ValueError):
        return False
    unsafe_roots = {
        Path("/tmp").resolve(),
        Path("/var/tmp").resolve(),
        Path(tempfile.gettempdir()).resolve(),
        (Path.home() / ".oompah" / "workspaces").resolve(),
        (Path.home() / ".oompah" / "worktrees").resolve(),
        cwd,
    }
    for name in ("TMPDIR", "TMP", "TEMP"):
        for source in (os.environ, environment):
            value = source.get(name)
            if value:
                unsafe_roots.add(Path(value).expanduser().resolve())
    entrypoint_matches_operator = (
        entrypoint == trusted_entrypoint
        and (int(entrypoint_stat.st_dev), int(entrypoint_stat.st_ino))
        == trusted_entrypoint_identity
    )
    interpreter_matches_operator = (
        interpreter == trusted_interpreter
        and (int(interpreter_stat.st_dev), int(interpreter_stat.st_ino))
        == trusted_interpreter_identity
    )
    parent_identity = _process_parent_identity(normalized_pid)
    parent_matches_operator = (
        parent_identity is not None
        and (
            parent_identity == trusted_parent_identity
            or parent_identity[0] == 1
        )
    )
    return _process_identity_alive(
        normalized_pid, expected_ticks
    ) and _is_legacy_provider_bootstrap_snapshot(
        arguments,
        environment,
        entrypoint_prefix,
        entrypoint_matches_operator=entrypoint_matches_operator,
        interpreter_matches_operator=interpreter_matches_operator,
        parent_matches_operator=parent_matches_operator,
        bootstrap_is_task_writable=(
            _path_is_within(entrypoint, unsafe_roots)
            or _path_is_within(interpreter, unsafe_roots)
        ),
    )


def _pidfd_open(pid: int) -> int:
    """Open a Linux pidfd even on Python builds that omit ``os.pidfd_open``."""

    native = getattr(os, "pidfd_open", None)
    if callable(native):
        return int(native(pid, 0))
    libc = ctypes.CDLL(None, use_errno=True)
    function = libc.pidfd_open
    function.argtypes = (ctypes.c_int, ctypes.c_uint)
    function.restype = ctypes.c_int
    descriptor = int(function(int(pid), 0))
    if descriptor < 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))
    return descriptor


def _pidfd_send_signal(pidfd: int, signum: int) -> None:
    """Signal the exact process referenced by a Linux pidfd."""

    native = getattr(signal, "pidfd_send_signal", None)
    if callable(native):
        native(pidfd, signum)
        return
    libc = ctypes.CDLL(None, use_errno=True)
    function = libc.pidfd_send_signal
    function.argtypes = (
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_uint,
    )
    function.restype = ctypes.c_int
    if int(function(int(pidfd), int(signum), None, 0)) < 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))


def _process_group_members(pid: int) -> tuple[tuple[int, int], ...] | None:
    """Snapshot observable PID/start identities for one numeric PGID."""

    try:
        entries = tuple(Path("/proc").iterdir())
    except OSError:
        return None
    members: dict[int, int] = {}
    for entry in entries:
        if not entry.name.isdigit():
            continue
        member_pid = int(entry.name)
        member_stat = _process_stat(member_pid)
        if member_stat is None and entry.exists():
            return None
        if member_stat is not None and member_stat[1] == pid:
            members[member_pid] = member_stat[2]
    return tuple(sorted(members.items()))


def _process_group_exists(pid: int) -> bool:
    """Probe PGID existence without granting numeric signal authority."""

    try:
        os.killpg(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


def _live_process_group_members(
    snapshot: tuple[tuple[int, int], ...],
) -> tuple[tuple[int, int], ...] | None:
    """Return exact non-zombie identities from one fenced group snapshot."""

    live: list[tuple[int, int]] = []
    for member_pid, member_ticks in snapshot:
        member_stat = _process_stat(member_pid)
        if member_stat is None:
            if Path(f"/proc/{member_pid}").exists():
                return None
            continue
        if member_stat[2] == member_ticks and member_stat[0] != "Z":
            live.append((member_pid, member_ticks))
    return tuple(live)


def _original_process_group_snapshot(
    pid: int,
    start_ticks: int,
) -> tuple[bool, tuple[tuple[int, int], ...]]:
    """Return whether one exact process-group generation is gone.

    Linux reserves a process-group id while any member remains.  Therefore a
    different process generation at the leader PID proves the original group
    already ended; otherwise every process still carrying that PGID belongs to
    the original generation. A final kernel PGID existence probe closes the
    race where a member forks after ``/proc`` enumeration and its parent exits
    before being statted.
    """

    leader_before = _process_stat(pid)
    if leader_before is None and Path(f"/proc/{pid}").exists():
        return False, ()
    if leader_before is not None and leader_before[2] != start_ticks:
        return True, ()
    member_snapshot = _process_group_members(pid)
    if member_snapshot is None:
        return False, ()
    members = dict(member_snapshot)
    leader_after = _process_stat(pid)
    if leader_after is None and Path(f"/proc/{pid}").exists():
        return False, ()
    if leader_after is not None and leader_after[2] != start_ticks:
        return True, ()
    if leader_after is not None and leader_after[2] == start_ticks:
        # The attached root remains part of this authority generation even if
        # task code moved it out of its original process group.
        members[pid] = start_ticks
    live_members = _live_process_group_members(tuple(sorted(members.items())))
    if live_members is None:
        return False, ()
    if live_members:
        return False, live_members
    if (
        leader_after is not None
        and leader_after[2] == start_ticks
        and leader_after[0] == "Z"
    ):
        # Exited processes have already closed every inherited lease/root
        # descriptor before becoming zombies. A zombie group leader can keep
        # the numeric PGID visible until its parent calls wait(), creating a
        # teardown deadlock when that parent is itself waiting for retirement.
        # Confirm with a second complete snapshot: a live member that forked
        # during the first enumeration then appears and keeps the group fenced.
        confirmation = _process_group_members(pid)
        if confirmation is None:
            return False, ()
        confirmed_live = _live_process_group_members(confirmation)
        if confirmed_live is None:
            return False, ()
        if not confirmed_live:
            return True, ()
        return False, confirmed_live
    if not members and leader_before is None and leader_after is None:
        return (False, ()) if _process_group_exists(pid) else (True, ())
    return False, ()


def _signal_exact_process_group_member(
    member_pid: int,
    member_start_ticks: int,
    *,
    group_pid: int,
    leader_start_ticks: int,
    signum: int,
) -> bool:
    """Signal only the pidfd-pinned identity observed in the original group."""

    try:
        pidfd = _pidfd_open(member_pid)
    except (OSError, ProcessLookupError):
        return True
    try:
        member_stat = _process_stat(member_pid)
        if member_stat is None or member_stat[2] != member_start_ticks:
            return True
        if member_stat[0] == "Z":
            return True
        if member_pid == group_pid:
            if member_start_ticks != leader_start_ticks:
                return True
        elif member_stat[1] != group_pid:
            # A detached descendant is outside the original process group.
            # Revoking the shared flock later is sufficient; do not signal it.
            return True
        try:
            _pidfd_send_signal(pidfd, signum)
        except (OSError, ProcessLookupError, PermissionError):
            return False
        return True
    finally:
        os.close(pidfd)


def _terminate_exact_process_group(
    pid: object,
    start_ticks: object,
    *,
    grace_seconds: float = 0.25,
) -> bool:
    """Terminate and prove empty only one identity-fenced process group."""

    try:
        normalized_pid = int(pid)
        expected_ticks = int(start_ticks)
    except (TypeError, ValueError):
        return False
    if normalized_pid <= 1 or normalized_pid == os.getpid() or expected_ticks <= 0:
        return False
    gone, members = _original_process_group_snapshot(
        normalized_pid,
        expected_ticks,
    )
    if gone:
        return True
    if not members:
        return False
    term_sent = all(
        _signal_exact_process_group_member(
            member_pid,
            member_ticks,
            group_pid=normalized_pid,
            leader_start_ticks=expected_ticks,
            signum=signal.SIGTERM,
        )
        for member_pid, member_ticks in members
    )
    if not term_sent:
        return False
    grace_deadline = time.monotonic() + max(float(grace_seconds), 0.0)
    # A full process-group snapshot scans all of /proc. Repeating that scan at
    # 100 Hz makes cancellation latency grow with every unrelated process on
    # a busy agent host. TERM has already been sent to every exact member in
    # the fenced snapshot; wait out the short grace interval and take one new
    # complete snapshot to close the concurrent-fork race.
    remaining_grace = grace_deadline - time.monotonic()
    if remaining_grace > 0:
        time.sleep(remaining_grace)

    # The leader may have honored TERM while a child ignored it.  Re-enumerate
    # the original PGID and SIGKILL every exact remaining identity.  Repeat to
    # cover children forked by a member between the first snapshot and signal.
    kill_deadline = time.monotonic() + max(float(grace_seconds), 0.5)
    while True:
        gone, members = _original_process_group_snapshot(
            normalized_pid,
            expected_ticks,
        )
        if gone:
            return True
        if not members:
            return False
        if not all(
            _signal_exact_process_group_member(
                member_pid,
                member_ticks,
                group_pid=normalized_pid,
                leader_start_ticks=expected_ticks,
                signum=signal.SIGKILL,
            )
            for member_pid, member_ticks in members
        ):
            return False
        if time.monotonic() >= kill_deadline:
            return False
        # Each scan is O(total host processes), while SIGKILL prevents an
        # already-signalled member from doing more work. A 50 ms cadence is
        # both bounded and avoids turning large hosts into procfs scan storms.
        time.sleep(0.05)


def _remove_shell_line_continuations(command: str) -> str:
    """Remove active backslash-newline pairs before command tokenization."""

    normalized: list[str] = []
    quote: str | None = None
    index = 0
    while index < len(command):
        character = command[index]
        if quote == "'":
            normalized.append(character)
            if character == "'":
                quote = None
            index += 1
            continue
        if character == "\\":
            if command.startswith("\r\n", index + 1):
                index += 3
                continue
            if index + 1 < len(command) and command[index + 1] in "\r\n":
                index += 2
                continue
            normalized.append(character)
            if index + 1 < len(command):
                normalized.append(command[index + 1])
                index += 2
            else:
                index += 1
            continue
        normalized.append(character)
        if character == quote:
            quote = None
        elif quote is None and character in {"'", '"'}:
            quote = character
        index += 1
    return "".join(normalized)


def _shell_dollar_starts_expansion(command: str, index: int) -> bool:
    return index + 1 < len(command) and (
        command[index + 1].isalnum()
        or command[index + 1] in "_{[(*@#?$!-\"'"
    )


def _shell_has_active_backtick(command: str) -> bool:
    """Return whether command substitution uses an unquoted backtick."""

    quote: str | None = None
    index = 0
    while index < len(command):
        character = command[index]
        if character == "\\" and quote != "'":
            index += 2
            continue
        if character == "'":
            quote = None if quote == "'" else ("'" if quote is None else quote)
        elif character == '"':
            quote = None if quote == '"' else ('"' if quote is None else quote)
        elif character == "`" and quote != "'":
            return True
        index += 1
    return False


def _shell_has_active_ansi_c_quote(command: str) -> bool:
    """Return whether Bash ANSI-C ``$'...'`` quoting is active."""

    quote: str | None = None
    index = 0
    while index < len(command):
        character = command[index]
        if quote == "'":
            if character == "'":
                quote = None
            index += 1
            continue
        if character == "\\":
            index += 2
            continue
        if quote == '"':
            if character == '"':
                quote = None
            index += 1
            continue
        if (
            character == "$"
            and index + 1 < len(command)
            and command[index + 1] == "'"
        ):
            return True
        if character in {"'", '"'}:
            quote = character
        index += 1
    return False


def _shell_has_active_extglob(command: str) -> bool:
    """Return whether an unquoted Bash extglob opener is present."""

    quote: str | None = None
    index = 0
    while index < len(command):
        character = command[index]
        if character == "\\" and quote != "'":
            index += 2
            continue
        if character == "'":
            quote = None if quote == "'" else ("'" if quote is None else quote)
        elif character == '"':
            quote = None if quote == '"' else ('"' if quote is None else quote)
        elif (
            quote is None
            and character in "@+!?*"
            and index + 1 < len(command)
            and command[index + 1] == "("
        ):
            return True
        index += 1
    return False


def _shell_unresolved_syntax_flags(command: str) -> list[bool]:
    """Record tokens with active expansion or redirection syntax."""

    flags: list[bool] = []
    token_started = False
    token_has_expansion = False
    quote: str | None = None
    index = 0

    def finish_token() -> None:
        nonlocal token_started, token_has_expansion
        if token_started:
            flags.append(token_has_expansion)
            token_started = False
            token_has_expansion = False

    while index < len(command):
        character = command[index]
        if quote is not None:
            token_started = True
            if character == quote:
                quote = None
            elif character == "\\" and quote == '"':
                index += 1
                if index >= len(command):
                    raise ValueError("No escaped character")
            elif quote == '"' and (
                character == "`"
                or (
                    character == "$"
                    and _shell_dollar_starts_expansion(command, index)
                )
            ):
                token_has_expansion = True
            index += 1
            continue
        if character in {"'", '"'}:
            token_started = True
            quote = character
            index += 1
            continue
        if character == "\\":
            token_started = True
            index += 2
            if index > len(command):
                raise ValueError("No escaped character")
            continue
        if character.isspace():
            finish_token()
            index += 1
            continue
        if character in ";&|()":
            finish_token()
            while index < len(command) and command[index] in ";&|()":
                index += 1
            flags.append(False)
            continue
        token_started = True
        if (
            character in "*?[{<>`"
            or (
                character == "$"
                and _shell_dollar_starts_expansion(command, index)
            )
        ):
            token_has_expansion = True
        index += 1
    if quote is not None:
        raise ValueError("No closing quotation")
    finish_token()
    return flags


def _shell_segments(
    command: str,
) -> list[tuple[str | None, list[str], list[bool]]]:
    """Tokenize top-level shell commands and retain their control operators."""

    # A literal newline is a shell command boundary just like ``;``.  shlex
    # otherwise treats it as ordinary whitespace, which let a light first
    # command hide a heavyweight command on the following line.
    continued = _remove_shell_line_continuations(command)
    normalized = continued.replace("\r\n", "\n").replace("\r", "\n").replace(
        "\n", ";"
    )
    lexer = shlex.shlex(
        normalized,
        posix=True,
        punctuation_chars=";&|()",
    )
    lexer.whitespace_split = True
    lexer.commenters = ""
    tokens = list(lexer)
    expansion_flags = _shell_unresolved_syntax_flags(normalized)
    if len(tokens) != len(expansion_flags):
        raise ValueError("shell token provenance cannot be resolved")
    segments: list[tuple[str | None, list[str], list[bool]]] = []
    current: list[str] = []
    current_expansion_flags: list[bool] = []
    pending_operator: str | None = None
    for token, token_has_expansion in zip(tokens, expansion_flags, strict=True):
        if token and all(character in ";&|()" for character in token):
            if current:
                segments.append((pending_operator, current, current_expansion_flags))
                current = []
                current_expansion_flags = []
                pending_operator = token
            elif pending_operator is None:
                pending_operator = token
            else:
                # Preserve adjacent control tokens as an opaque operator.  The
                # stateful classifier below will fail closed rather than
                # flattening a subshell, pipeline, or compound-list boundary.
                pending_operator += token
        else:
            current.append(token)
            current_expansion_flags.append(token_has_expansion)
    if current:
        segments.append((pending_operator, current, current_expansion_flags))
    return segments


def _command_tokens(tokens: list[str]) -> list[str]:
    """Remove common non-executing wrappers from one shell segment."""

    index = 0
    while index < len(tokens):
        assignment = tokens[index].partition("=")
        if assignment[1] and assignment[0].replace("_", "a").isalnum():
            index += 1
            continue

        executable = os.path.basename(tokens[index])
        if executable == "env":
            index += 1
            env_value_options = {
                "-u",
                "--unset",
                "-C",
                "--chdir",
                "-S",
                "--split-string",
            }
            while index < len(tokens):
                option = tokens[index]
                if option in {"-S", "--split-string"} or option.startswith(
                    ("-S", "--split-string=")
                ):
                    # env reparses this opaque value into a command. Mark it
                    # heavy rather than allowing quoting or PATH changes to
                    # bypass classification and the native PATH shims.
                    return ["__oompah_opaque_env_split_string__"]
                if option in env_value_options:
                    index += 2
                elif option.startswith("-") or "=" in option:
                    index += 1
                else:
                    break
            continue
        if executable == "command":
            index += 1
            while index < len(tokens) and tokens[index].startswith("-"):
                index += 1
            continue
        if executable == "exec":
            index += 1
            while index < len(tokens) and tokens[index].startswith("-"):
                option = tokens[index]
                index += 1
                if option in {"-a", "--argv0"}:
                    index += 1
            continue
        if executable in {"nice", "ionice", "stdbuf"}:
            index += 1
            while index < len(tokens) and tokens[index].startswith("-"):
                option = tokens[index]
                index += 1
                if option in {"-n", "--adjustment", "-c", "--class", "-p", "--pid"}:
                    index += 1
            continue
        if executable == "time":
            index += 1
            time_value_options = {"-f", "--format", "-o", "--output"}
            while index < len(tokens) and tokens[index].startswith("-"):
                option = tokens[index]
                index += 1
                if (
                    option.partition("=")[0] in time_value_options
                    and "=" not in option
                ):
                    index += 1
            continue
        if executable == "timeout":
            index += 1
            while index < len(tokens) and tokens[index].startswith("-"):
                option = tokens[index]
                index += 1
                if option in {"-k", "--kill-after", "-s", "--signal"}:
                    index += 1
            if index < len(tokens):
                index += 1  # duration
            continue
        if executable == "setsid":
            index += 1
            while index < len(tokens) and tokens[index].startswith("-"):
                index += 1
            continue
        break
    if index < len(tokens) and os.path.basename(tokens[index]) == "uv":
        index += 1
        uv_global_value_options = {
            "--allow-insecure-host",
            "--cache-dir",
            "--color",
            "--config-file",
            "--directory",
            "--project",
            "--python-preference",
        }
        while index < len(tokens) and tokens[index] != "run":
            option = tokens[index]
            if not option.startswith("-"):
                return tokens[index - 1 :]
            index += 1
            if (
                option.partition("=")[0] in uv_global_value_options
                and "=" not in option
            ):
                index += 1
        if index >= len(tokens):
            return tokens[index:]
        index += 1
        uv_value_options = {
            "--directory",
            "--env-file",
            "--extra",
            "--group",
            "--index",
            "--no-extra",
            "--no-group",
            "--only-group",
            "--package",
            "--python",
            "--project",
            "--with",
            "--with-editable",
            "--with-requirements",
        }
        while index < len(tokens) and tokens[index].startswith("-"):
            option = tokens[index].partition("=")[0]
            index += 1
            if option in uv_value_options and "=" not in tokens[index - 1]:
                index += 1
    elif (
        index + 1 < len(tokens)
        and os.path.basename(tokens[index]) in {"pipenv", "poetry"}
        and tokens[index + 1] == "run"
    ):
        index += 2
    return tokens[index:]


def _env_split_string_command(tokens: list[str]) -> str | None:
    """Recover a literal GNU ``env -S`` command for policy comparison.

    The heavyweight classifier intentionally treats split-string input as
    opaque because ``env`` reparses it.  When the shell tokenizer already gave
    us a literal value, however, recursively parsing that value lets reuse
    policy recognize a configured gate hidden only by this wrapper.  Dynamic
    or malformed forms remain opaque and therefore fail closed.
    """

    if _command_tokens(tokens) != ["__oompah_opaque_env_split_string__"]:
        return None
    for index, token in enumerate(tokens):
        if os.path.basename(token) != "env":
            continue
        cursor = index + 1
        while cursor < len(tokens):
            option = tokens[cursor]
            split_value = ""
            remaining_index = cursor + 1
            if option in {"-S", "--split-string"}:
                if remaining_index >= len(tokens):
                    return None
                split_value = tokens[remaining_index]
                remaining_index += 1
            elif option.startswith("--split-string="):
                split_value = option.partition("=")[2]
            elif option.startswith("-S") and option != "-S":
                split_value = option[2:]
            if split_value:
                return " ".join([split_value, *tokens[remaining_index:]]).strip()
            cursor += 1
    return None


def _aligned_shell_syntax_flags(
    tokens: list[str],
    command_tokens: list[str],
    unresolved_syntax_flags: list[bool] | None,
) -> list[bool] | None:
    """Align pre-expansion shell syntax provenance with normalized argv."""

    if unresolved_syntax_flags is None:
        return [False] * len(command_tokens)
    if len(unresolved_syntax_flags) != len(tokens):
        return None
    command_flags: list[bool] = []
    source_index = 0
    for command_token in command_tokens:
        while source_index < len(tokens) and tokens[source_index] != command_token:
            source_index += 1
        if source_index >= len(tokens):
            return None
        command_flags.append(unresolved_syntax_flags[source_index])
        source_index += 1
    return command_flags


def _make_segment_is_heavy(tokens: list[str]) -> bool:
    command_tokens = _command_tokens(tokens)
    if not command_tokens or os.path.basename(command_tokens[0]) != "make":
        return False
    arguments = command_tokens[1:]
    # A named target is never intrinsically lightweight: GNU Make parses the
    # task-controlled Makefile before selecting it, and both parse-time
    # ``$(shell ...)`` expressions and the target recipe can launch arbitrary
    # validation work.  Options such as --eval, --file, --directory,
    # --include-dir, and --jobs expose the same surface.  Only Make's own
    # standalone informational modes bypass capacity.
    return not (
        bool(arguments)
        and all(
            argument in {"-h", "--help", "-v", "--version"}
            for argument in arguments
        )
    )


def _pytest_invocation(tokens: list[str]) -> tuple[int, int] | None:
    """Return the pytest token and first-argument indices, if present."""

    command_tokens = _command_tokens(tokens)
    if not command_tokens:
        return None
    if os.path.basename(command_tokens[0]) in {"pytest", "py.test"}:
        return 0, 1
    python_executable = os.path.basename(command_tokens[0])
    if python_executable == "python" or (
        python_executable.startswith("python")
        and python_executable[6:].replace(".", "").isdigit()
    ):
        index = 1
        value_options = {"-W", "-X", "--check-hash-based-pycs"}
        while index < len(command_tokens):
            option = command_tokens[index]
            if option == "-m":
                if (
                    index + 1 < len(command_tokens)
                    and command_tokens[index + 1] == "pytest"
                ):
                    return index + 1, index + 2
                return None
            if option in value_options:
                index += 2
                continue
            if (
                option.startswith(("-W", "-X"))
                and option not in {"-W", "-X"}
            ) or option.startswith("--check-hash-based-pycs="):
                index += 1
                continue
            if option.startswith("-") and option != "--":
                index += 1
                continue
            return None
    return None


_PYTEST_CONFIGURATION_NAMES = (
    "pytest.ini",
    ".pytest.ini",
    "pyproject.toml",
    "tox.ini",
    "setup.cfg",
)


def _pytest_effective_configuration_is_untrusted(
    arguments: list[str],
    working_directory: str | os.PathLike[str] | None,
) -> bool:
    """Fence pytest when its discovery path can load task-controlled code.

    Pytest imports ``conftest.py`` and plugins named by persisted configuration
    before a focused selector or informational option makes the run look
    bounded.  Do not parse those files: their contents can change after this
    classification and before pytest opens them.
    """

    try:
        invocation_directory = Path(working_directory or os.getcwd()).resolve()
        roots = {invocation_directory}
        for argument in arguments:
            if argument.startswith("-"):
                continue
            selector = argument.partition("::")[0]
            if not selector:
                continue
            candidate = Path(selector)
            if not candidate.is_absolute():
                candidate = invocation_directory / candidate
            candidate = candidate.resolve()
            roots.add(candidate if candidate.is_dir() else candidate.parent)
        inspected: set[Path] = set()
        for root in roots:
            for directory in (root, *root.parents):
                if directory in inspected:
                    continue
                inspected.add(directory)
                if (directory / "conftest.py").exists() or any(
                    (directory / name).exists()
                    for name in _PYTEST_CONFIGURATION_NAMES
                ):
                    return True
    except OSError:
        return True
    return False


def _pytest_segment_is_heavy(
    tokens: list[str],
    *,
    working_directory: str | os.PathLike[str] | None,
) -> bool:
    command_tokens = _command_tokens(tokens)
    invocation = _pytest_invocation(command_tokens)
    if invocation is None:
        return False
    _, first_argument = invocation
    arguments = command_tokens[first_argument:]
    if any(argument.startswith("@") for argument in arguments):
        # Pytest expands response files after this classifier runs.  Their
        # task-controlled contents can replace a seemingly focused ``.py``
        # selector with an xdist or full-suite invocation.
        return True
    provenance_options = {
        "-c",
        "-o",
        "-p",
        "--config-file",
        "--confcutdir",
        "--override-ini",
        "--pdbcls",
        "--rootdir",
    }
    if any(
        argument in provenance_options
        or any(
            argument.startswith(prefix)
            for prefix in (
                "-c=",
                "-o=",
                "-p=",
                "--config-file=",
                "--confcutdir=",
                "--override-ini=",
                "--pdbcls=",
                "--rootdir=",
            )
        )
        or (argument.startswith("-c") and argument != "-c")
        or (argument.startswith("-o") and argument != "-o")
        or (argument.startswith("-p") and argument != "-p")
        for argument in arguments
    ):
        return True
    if _pytest_effective_configuration_is_untrusted(
        arguments,
        working_directory,
    ):
        return True
    if any(argument in {"--help", "-h", "--version"} for argument in arguments):
        return False
    # A focused file or node can still import the application, load plugins,
    # start subprocesses, or otherwise contend with an exact gate.  The
    # classifier runs before pytest expands selectors, so every real pytest
    # invocation participates in the shared lane.  Help/version are the only
    # pytest forms intentionally kept outside it.
    return True


def _pytest_segment_is_full_suite(tokens: list[str]) -> bool:
    """Return whether a pytest invocation has no focused test selector.

    Pytest flags may still narrow collection (for example ``-k``), but an
    option-only invocation starts from the entire configured collection and is
    therefore a full-suite run for gate-reuse policy.  Explicit files, node
    IDs, or package selectors stay focused.  The conventional repository test
    root is equivalent to an unqualified invocation.
    """

    command_tokens = _command_tokens(tokens)
    invocation = _pytest_invocation(command_tokens)
    if invocation is None:
        return False
    _, first_argument = invocation
    arguments = command_tokens[first_argument:]
    if any(argument in {"--help", "-h", "--version"} for argument in arguments):
        return False

    value_options = {
        "-c",
        "-k",
        "-m",
        "-n",
        "-o",
        "-p",
        "-W",
        "--basetemp",
        "--capture",
        "--code-highlight",
        "--color",
        "--confcutdir",
        "--cov",
        "--cov-config",
        "--cov-context",
        "--cov-report",
        "--deselect",
        "--dist",
        "--doctest-glob",
        "--durations",
        "--durations-min",
        "--ignore",
        "--ignore-glob",
        "--import-mode",
        "--junit-prefix",
        "--junitxml",
        "--log-cli-format",
        "--log-cli-level",
        "--log-file",
        "--log-file-format",
        "--log-file-level",
        "--log-format",
        "--log-level",
        "--max-worker-restart",
        "--maxfail",
        "--override-ini",
        "--rootdir",
        "--show-capture",
        "--tb",
        "--timeout",
        "--tx",
    }
    attached_short_value_options = {"-c", "-k", "-m", "-n", "-o", "-p", "-W"}
    selectors: list[str] = []
    index = 0
    options_finished = False
    while index < len(arguments):
        argument = arguments[index]
        if not options_finished and argument == "--":
            options_finished = True
            index += 1
            continue
        if not options_finished and argument.startswith("-"):
            option = argument.partition("=")[0]
            if option in value_options and "=" not in argument:
                index += 2
                continue
            if any(
                argument.startswith(prefix) and argument != prefix
                for prefix in attached_short_value_options
            ):
                index += 1
                continue
            index += 1
            continue
        selectors.append(argument)
        index += 1

    if not selectors:
        return True
    normalized_selectors = {
        selector.replace("\\", "/").rstrip("/") or "."
        for selector in selectors
    }
    return normalized_selectors <= {".", "./tests", "tests"}


def _unittest_arguments(tokens: list[str]) -> list[str] | None:
    """Return arguments after ``python -m unittest``, if present."""

    command_tokens = _command_tokens(tokens)
    if not command_tokens:
        return None
    python_executable = os.path.basename(command_tokens[0])
    if not (
        python_executable == "python"
        or (
            python_executable.startswith("python")
            and python_executable[6:].replace(".", "").isdigit()
        )
    ):
        return None
    try:
        module_index = command_tokens.index("-m", 1)
    except ValueError:
        return None
    if (
        module_index + 1 >= len(command_tokens)
        or command_tokens[module_index + 1] != "unittest"
    ):
        return None
    return command_tokens[module_index + 2 :]


def _unittest_segment_is_heavy(tokens: list[str]) -> bool:
    """Return whether one segment invokes an unbounded unittest run."""

    arguments = _unittest_arguments(tokens)
    if arguments is None:
        return False
    if any(argument in {"--help", "-h", "--version"} for argument in arguments):
        return False
    # unittest selectors are executable test code even when they name one
    # method.  Keep all actual runner invocations behind the shared lane.
    return True


def _unittest_segment_is_full_suite(tokens: list[str]) -> bool:
    """Return whether unittest starts with discovery rather than named tests."""

    arguments = _unittest_arguments(tokens)
    if arguments is None or any(
        argument in {"--help", "-h", "--version"} for argument in arguments
    ):
        return False
    if "discover" in arguments:
        return True
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument == "-k":
            index += 2
            continue
        if argument.startswith("-k") and argument != "-k":
            index += 1
            continue
        if argument.startswith("-"):
            index += 1
            continue
        return False
    return True


def _npm_segment_is_heavy(tokens: list[str]) -> bool:
    """Fail closed for package-manager commands that can execute project code."""

    command_tokens = _command_tokens(tokens)
    if not command_tokens:
        return False
    package_manager = os.path.basename(command_tokens[0])
    if package_manager not in {"npm", "pnpm", "yarn"}:
        return False
    arguments = command_tokens[1:]
    # Script names, unknown commands, exec/dlx/explore, lifecycle aliases, and
    # option ordering all depend on task-controlled package metadata or can
    # launch an arbitrary executable.  Only bare and standalone informational
    # invocations are demonstrably incapable of running project code.
    return not (
        not arguments
        or all(
            argument in {"-h", "--help", "-v", "--version"}
            for argument in arguments
        )
    )


def _npm_segment_is_full_suite(tokens: list[str]) -> bool:
    """Return whether a package-manager command selects a test script."""

    command_tokens = _command_tokens(tokens)
    if not command_tokens:
        return False
    package_manager = os.path.basename(command_tokens[0])
    if package_manager not in {"npm", "pnpm", "yarn"}:
        return False
    index = 1
    value_options = {
        "--cache",
        "--loglevel",
        "--prefix",
        "--registry",
        "--userconfig",
        "--workspace",
        "--filter",
        "-C",
        "-w",
    }
    while index < len(command_tokens) and command_tokens[index].startswith("-"):
        option = command_tokens[index]
        index += 1
        if option.partition("=")[0] in value_options and "=" not in option:
            index += 1
    if index >= len(command_tokens):
        return False
    subcommand = command_tokens[index]
    if subcommand in {"t", "test", "tst"} or subcommand.startswith("test:"):
        return True
    return (
        subcommand in {"run", "run-script"}
        and index + 1 < len(command_tokens)
        and (
            command_tokens[index + 1] == "test"
            or command_tokens[index + 1].startswith("test:")
        )
    )


_CARGO_LIGHTWEIGHT_SUBCOMMANDS = frozenset(
    {
        "build",
        "check",
        "help",
        "locate-project",
        "metadata",
        "pkgid",
        "read-manifest",
        "tree",
        "verify-project",
        "version",
    }
)


def _cargo_effective_config_is_untrusted(
    environment: Mapping[str, str] | None,
    working_directory: str | os.PathLike[str] | None,
) -> bool:
    """Return whether Cargo can read persisted configuration for this cwd.

    Cargo configuration can replace rustc, install wrappers, or define aliases
    that execute arbitrary programs.  Its hierarchical lookup is broader than
    a repository root, so conservatively fence a Cargo command whenever an
    effective ``.cargo/config`` file exists.  This deliberately does not parse
    the file: even currently-benign task-writable configuration can change
    between classification and Cargo opening it.
    """

    try:
        current = Path(working_directory or os.getcwd()).resolve()
    except (OSError, RuntimeError):
        return True

    config_directories = [
        directory / ".cargo" for directory in (current, *current.parents)
    ]
    if environment:
        cargo_home = str(environment.get("CARGO_HOME") or "").strip()
        home = str(environment.get("HOME") or "").strip()
        if cargo_home:
            config_directories.append(Path(cargo_home).expanduser())
        elif home:
            config_directories.append(Path(home).expanduser() / ".cargo")

    seen: set[Path] = set()
    for directory in config_directories:
        for name in ("config.toml", "config"):
            candidate = directory / name
            if candidate in seen:
                continue
            seen.add(candidate)
            try:
                if candidate.exists() or candidate.is_symlink():
                    return True
            except OSError:
                # An unreadable or unstable lookup cannot prove that Cargo
                # will run without persisted execution hooks.
                return True
    return False


def _cargo_segment_is_heavy(
    tokens: list[str],
    *,
    environment: Mapping[str, str] | None,
    working_directory: str | os.PathLike[str] | None,
) -> bool:
    """Fail closed for Cargo execution hooks and unrecognized subcommands."""

    command_tokens = _command_tokens(tokens)
    if not command_tokens or os.path.basename(command_tokens[0]) != "cargo":
        return False
    if _cargo_effective_config_is_untrusted(environment, working_directory):
        return True
    if any(
        argument == "--config"
        or argument.startswith("--config=")
        or argument == "-C"
        or (argument.startswith("-C") and len(argument) > 2)
        for argument in command_tokens[1:]
    ):
        # These global options may occur after the subcommand as well as before
        # it, and can select task-controlled configuration outside the cwd.
        return True
    index = 1
    if index < len(command_tokens) and command_tokens[index].startswith("+"):
        index += 1
    value_options = {
        "--color",
        "--config",
        "--lockfile-path",
        "--manifest-path",
        "--target-dir",
        "-C",
    }
    while index < len(command_tokens) and command_tokens[index].startswith("-"):
        option = command_tokens[index]
        option_name = option.partition("=")[0]
        index += 1
        if option_name in value_options and "=" not in option:
            index += 1
    if index >= len(command_tokens):
        return False
    subcommand = command_tokens[index]
    if subcommand == "test":
        return True
    if subcommand == "nextest":
        return True
    # Cargo aliases and external subcommands share the same argv surface as
    # built-ins.  Only a small, explicit set can bypass the capacity fence.
    return subcommand not in _CARGO_LIGHTWEIGHT_SUBCOMMANDS


def _cargo_segment_is_full_suite(tokens: list[str]) -> bool:
    """Return whether one segment selects Cargo's test runner."""

    command_tokens = _command_tokens(tokens)
    if not command_tokens or os.path.basename(command_tokens[0]) != "cargo":
        return False
    index = 1
    if index < len(command_tokens) and command_tokens[index].startswith("+"):
        index += 1
    value_options = {
        "--color",
        "--config",
        "--lockfile-path",
        "--manifest-path",
        "--target-dir",
        "-C",
    }
    while index < len(command_tokens) and command_tokens[index].startswith("-"):
        option = command_tokens[index]
        index += 1
        if option.partition("=")[0] in value_options and "=" not in option:
            index += 1
    if index >= len(command_tokens):
        return False
    if command_tokens[index] == "test":
        return True
    return (
        command_tokens[index] == "nextest"
        and index + 1 < len(command_tokens)
        and command_tokens[index + 1] in {"run", "test"}
    )


def _find_segment_is_heavy(tokens: list[str]) -> bool:
    """Fail closed for commands executed through find action predicates."""

    command_tokens = _command_tokens(tokens)
    if not command_tokens or os.path.basename(command_tokens[0]) != "find":
        return False
    return any(
        token in {"-exec", "-execdir", "-ok", "-okdir"}
        for token in command_tokens[1:]
    )


def _sed_script_can_execute(script: str) -> bool:
    """Recognize GNU sed script surfaces that can execute a command."""

    # GNU sed accepts both /regexp/ addresses and alternate-delimiter
    # ``\cregexpc`` addresses.  GNU address modifiers precede optional
    # whitespace and negation, so consume those before inspecting the command.
    # Restrict candidates to command/address boundaries so substitution
    # delimiters are not mistaken for addresses.
    for address_start in range(len(script)):
        prefix = script[:address_start].rstrip()
        if prefix and prefix[-1] not in ";,\n{}":
            continue
        if script[address_start] == "/":
            delimiter = "/"
            cursor = address_start + 1
        elif script[address_start] == "\\" and address_start + 1 < len(script):
            delimiter = script[address_start + 1]
            cursor = address_start + 2
        else:
            continue
        if delimiter.isspace() or delimiter == "\\":
            continue
        while cursor < len(script):
            if script[cursor] == "\\":
                cursor += 2
                continue
            if script[cursor] != delimiter:
                cursor += 1
                continue
            cursor += 1
            while cursor < len(script) and script[cursor] in "IiMm":
                cursor += 1
            while cursor < len(script) and script[cursor].isspace():
                cursor += 1
            if cursor < len(script) and script[cursor] == "!":
                cursor += 1
                while cursor < len(script) and script[cursor].isspace():
                    cursor += 1
            if cursor < len(script) and script[cursor] == "e" and (
                cursor + 1 == len(script)
                or script[cursor + 1].isspace()
                or script[cursor + 1] in ";}"
            ):
                return True
            break
    # ``e`` is both a standalone GNU extension (optionally after an address)
    # and a substitution flag.  The latter needs delimiter-aware scanning so
    # an ordinary ``s/before/after/`` is not rejected merely for containing an
    # ``e`` in its pattern or replacement.
    if re.search(r"(?:^|[;\n{}]|\d|\$|/|!)\s*e(?=\s|$|[;}])", script):
        return True
    index = 0
    while index + 1 < len(script):
        if script[index] != "s" or script[index + 1].isalnum():
            index += 1
            continue
        delimiter = script[index + 1]
        if delimiter.isspace() or delimiter == "\\":
            index += 1
            continue
        cursor = index + 2
        for _part in range(2):
            while cursor < len(script):
                if script[cursor] == "\\":
                    cursor += 2
                    continue
                if script[cursor] == delimiter:
                    cursor += 1
                    break
                cursor += 1
            else:
                # An incomplete substitution is rejected by sed itself and
                # cannot reach an execution flag.
                return False
        flags_start = cursor
        while cursor < len(script) and script[cursor] not in ";\n":
            cursor += 1
        if "e" in script[flags_start:cursor]:
            return True
        index = cursor + 1
    return False


def _sed_segment_is_heavy(
    tokens: list[str],
    *,
    unquoted_expansion_flags: list[bool] | None = None,
) -> bool:
    """Fail closed for sed programs that can execute or load opaque scripts."""

    command_tokens = _command_tokens(tokens)
    if not command_tokens or os.path.basename(command_tokens[0]) != "sed":
        return False
    command_expansion_flags = _aligned_shell_syntax_flags(
        tokens,
        command_tokens,
        unquoted_expansion_flags,
    )
    if command_expansion_flags is None:
        return True

    def program_is_opaque(program: str, program_index: int) -> bool:
        return command_expansion_flags[program_index] or (
            unquoted_expansion_flags is None
            and ("$" in program or "`" in program)
        )

    scripts: list[str] = []
    program_supplied = False
    option_parsing = True
    index = 1
    while index < len(command_tokens):
        argument = command_tokens[index]
        if option_parsing and argument == "--":
            option_parsing = False
            index += 1
            continue
        if option_parsing and command_expansion_flags[index]:
            # Before ``--``, GNU option permutation can reinterpret any
            # expanded token as -e/-f or another execution-bearing option.
            return True
        option_name, option_separator, option_value = argument.partition("=")
        abbreviated_file = (
            len(option_name) >= len("--fi")
            and "--file".startswith(option_name)
        )
        abbreviated_expression = (
            len(option_name) >= len("--e")
            and "--expression".startswith(option_name)
        )
        if option_parsing and (argument == "-f" or abbreviated_file):
            return True
        if option_parsing and (
            argument == "-e" or (abbreviated_expression and not option_separator)
        ):
            if index + 1 >= len(command_tokens):
                return True
            expression = command_tokens[index + 1]
            if program_is_opaque(expression, index + 1):
                return True
            scripts.append(expression)
            program_supplied = True
            index += 2
            continue
        if option_parsing and abbreviated_expression and option_separator:
            expression = option_value
            if program_is_opaque(expression, index):
                return True
            scripts.append(expression)
            program_supplied = True
            index += 1
            continue
        if option_parsing and argument.startswith("-e") and argument != "-e":
            expression = argument[2:]
            if program_is_opaque(expression, index):
                return True
            scripts.append(expression)
            program_supplied = True
            index += 1
            continue
        if option_parsing and argument.startswith("-"):
            # Short-option clusters can end in ``e`` with the expression in
            # the remainder of that argv or the next argv (for example
            # ``-ne1e make`` and ``-ne '1e make'``). A clustered ``f`` can
            # similarly load a task-controlled opaque program.
            if not argument.startswith("--"):
                short_options = argument[1:]
                if "f" in short_options:
                    return True
                if "e" in short_options:
                    expression = short_options.partition("e")[2]
                    if expression:
                        if program_is_opaque(expression, index):
                            return True
                        scripts.append(expression)
                        program_supplied = True
                        index += 1
                    elif index + 1 >= len(command_tokens):
                        return True
                    else:
                        expression = command_tokens[index + 1]
                        if program_is_opaque(expression, index + 1):
                            return True
                        scripts.append(expression)
                        program_supplied = True
                        index += 2
                    continue
            index += 1
            continue
        if not program_supplied:
            if program_is_opaque(argument, index):
                return True
            scripts.append(argument)
            program_supplied = True
        index += 1
    return any(_sed_script_can_execute(script) for script in scripts)


def _git_config_key_can_execute(key: str) -> bool:
    normalized_key = str(key).strip().casefold()
    return (
        normalized_key.startswith(
            (
                "alias.",
                "diff.",
                "include.",
                "includeif.",
                "pager.",
                "pretty.",
            )
        )
        or normalized_key
        in {
            "core.askpass",
            "core.alternaterefscommand",
            "core.editor",
            "core.fsmonitor",
            "core.gitproxy",
            "core.hookspath",
            "core.pager",
            "core.sshcommand",
            "credential.helper",
            "diff.external",
            "format.pretty",
            "gpg.program",
            "gpg.ssh.program",
            "log.showsignature",
            "sequence.editor",
        }
        or (
            normalized_key.startswith(("credential.", "filter.", "merge."))
            and normalized_key.endswith(
                (".helper", ".clean", ".smudge", ".process", ".driver")
            )
        )
    )


def _git_environment_has_dynamic_config(
    environment: Mapping[str, str] | None,
) -> bool:
    """Return whether Git's environment config can execute or is malformed.

    Git's numbered config environment is used by the test harness for inert
    URL rewrites, so its mere presence cannot turn every inspection command
    into a heavyweight command.  Parse a complete, bounded sequence and allow
    only keys that cannot select an executable helper. Any malformed,
    incomplete, or extra numbered entry fails closed; persistent configuration
    files are resolved and inspected separately.
    """

    if not environment:
        return False
    indexed_names = {
        name
        for name in environment
        if name.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_"))
    }
    raw_count = environment.get("GIT_CONFIG_COUNT")
    if raw_count is None:
        return bool(indexed_names)
    try:
        count = int(raw_count)
    except (TypeError, ValueError):
        return True
    if count < 0 or count > 10_000:
        return True
    expected_names = {
        name
        for index in range(count)
        for name in (f"GIT_CONFIG_KEY_{index}", f"GIT_CONFIG_VALUE_{index}")
    }
    if indexed_names != expected_names:
        return True
    for index in range(count):
        key = str(environment[f"GIT_CONFIG_KEY_{index}"]).strip()
        value = str(environment[f"GIT_CONFIG_VALUE_{index}"]).strip()
        if not key or _git_config_key_can_execute(key) or value.startswith("!"):
            return True
    return False


_GIT_CONFIG_MAX_BYTES = 1024 * 1024
_GIT_POINTER_MAX_BYTES = 4096
_GIT_SYSTEM_CONFIG_PATHS = (
    Path("/etc/gitconfig"),
    Path("/usr/local/etc/gitconfig"),
)
_GIT_SCOPE_ENV_NAMES = frozenset(
    {
        "GIT_COMMON_DIR",
        "GIT_CONFIG_GLOBAL",
        "GIT_CONFIG_NOSYSTEM",
        "GIT_CONFIG_SYSTEM",
        "GIT_DIR",
        "GIT_WORK_TREE",
        "HOME",
        "XDG_CONFIG_HOME",
    }
)
_GIT_EXECUTION_ENV_NAMES = frozenset(
    {
        "GIT_CONFIG_PARAMETERS",
        "GIT_EXTERNAL_DIFF",
        "GIT_PAGER",
        "PAGER",
    }
)
_GIT_TRACE_ENV_NAMES = frozenset(
    {
        "GIT_TRACE",
        "GIT_TRACE_CURL",
        "GIT_TRACE_PACKET",
        "GIT_TRACE_PACK_ACCESS",
        "GIT_TRACE_PERFORMANCE",
        "GIT_TRACE_SETUP",
        "GIT_TRACE2",
        "GIT_TRACE2_EVENT",
        "GIT_TRACE2_PERF",
    }
)


class _GitConfigurationUnresolved(RuntimeError):
    """Raised when a Git configuration scope cannot be proven safe."""


def _read_bounded_git_file(
    path: Path,
    *,
    maximum_bytes: int,
    required: bool,
) -> str | None:
    """Read one regular Git metadata file without returning its contents."""

    descriptor = -1
    try:
        descriptor = os.open(
            path,
            os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0),
        )
        with os.fdopen(descriptor, "rb", closefd=True) as stream:
            descriptor = -1
            metadata = os.fstat(stream.fileno())
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > maximum_bytes:
                raise _GitConfigurationUnresolved(
                    "Git configuration metadata is not a bounded regular file"
                )
            payload = stream.read(maximum_bytes + 1)
    except FileNotFoundError:
        if required:
            raise _GitConfigurationUnresolved(
                "selected Git configuration metadata does not exist"
            )
        return None
    except OSError as exc:
        raise _GitConfigurationUnresolved(
            "Git configuration metadata cannot be inspected"
        ) from exc
    finally:
        if descriptor >= 0:
            with contextlib.suppress(OSError):
                os.close(descriptor)
    if len(payload) > maximum_bytes or b"\0" in payload:
        raise _GitConfigurationUnresolved(
            "Git configuration metadata is not safely bounded"
        )
    try:
        return payload.decode("utf-8")
    except UnicodeError as exc:
        raise _GitConfigurationUnresolved(
            "Git configuration metadata cannot be decoded safely"
        ) from exc


def _git_config_file_can_execute(path: Path, *, required: bool = False) -> bool:
    try:
        content = _read_bounded_git_file(
            path,
            maximum_bytes=_GIT_CONFIG_MAX_BYTES,
            required=required,
        )
    except _GitConfigurationUnresolved:
        return True
    if content is None:
        return False
    section = ""
    for raw_line in content.splitlines():
        if raw_line.rstrip().endswith("\\"):
            return True
        line = raw_line.strip()
        if not line or line.startswith(("#", ";")):
            continue
        if line.startswith("["):
            section_end = line.find("]")
            if section_end < 0:
                return True
            trailer = line[section_end + 1 :].strip()
            if trailer and not trailer.startswith(("#", ";")):
                return True
            raw_section = line[1:section_end].strip()
            if not raw_section:
                return True
            section_name, separator, subsection = raw_section.partition(" ")
            section = section_name.casefold()
            if separator:
                normalized_subsection = subsection.strip().strip('"').casefold()
                section = f"{section}.{normalized_subsection}"
            continue
        key_prefix = line.partition("=")[0].strip()
        if not key_prefix or not section:
            return True
        key = key_prefix.split(maxsplit=1)[0]
        if section and _git_config_key_can_execute(f"{section}.{key}"):
            return True
    return False


def _git_path_has_unresolved_shell_syntax(value: str) -> bool:
    return not value or "\0" in value or value.startswith("~") or any(
        marker in value for marker in ("$", "`", "*", "?", "[", "]", "{")
    )


def _resolve_git_directory(
    value: str | os.PathLike[str],
    *,
    relative_to: Path | None,
) -> Path:
    raw = os.fspath(value)
    if _git_path_has_unresolved_shell_syntax(raw):
        raise _GitConfigurationUnresolved("Git directory path is dynamic")
    candidate = Path(raw)
    if not candidate.is_absolute():
        if relative_to is None:
            raise _GitConfigurationUnresolved("relative Git path has no base")
        candidate = relative_to / candidate
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise _GitConfigurationUnresolved("Git directory cannot be resolved") from exc
    if not resolved.is_dir():
        raise _GitConfigurationUnresolved("Git directory is not a directory")
    return resolved


def _resolve_git_config_path(value: str, *, relative_to: Path | None) -> Path:
    if value == os.devnull:
        return Path(os.devnull)
    if _git_path_has_unresolved_shell_syntax(value):
        raise _GitConfigurationUnresolved("Git configuration path is dynamic")
    candidate = Path(value)
    if not candidate.is_absolute():
        if relative_to is None:
            raise _GitConfigurationUnresolved(
                "relative Git configuration path has no base"
            )
        candidate = relative_to / candidate
    return candidate.resolve(strict=False)


def _discover_git_directory(current: Path) -> Path | None:
    git_entry: Path | None = None
    for candidate in (current, *current.parents):
        possible = candidate / ".git"
        try:
            possible.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise _GitConfigurationUnresolved(
                "Git repository metadata cannot be inspected"
            ) from exc
        git_entry = possible
        break
    if git_entry is None:
        return None
    if git_entry.is_dir():
        return _resolve_git_directory(git_entry, relative_to=None)
    marker = _read_bounded_git_file(
        git_entry,
        maximum_bytes=_GIT_POINTER_MAX_BYTES,
        required=True,
    )
    assert marker is not None
    prefix = "gitdir:"
    marker = marker.strip()
    if not marker.casefold().startswith(prefix):
        raise _GitConfigurationUnresolved("Git worktree pointer is malformed")
    raw_git_dir = marker[len(prefix) :].strip()
    return _resolve_git_directory(raw_git_dir, relative_to=git_entry.parent)


def _git_directory_config_can_execute(
    git_dir: Path,
    *,
    common_directory: Path | None,
) -> bool:
    common_dir = git_dir
    if common_directory is not None:
        common_dir = common_directory
    else:
        common_marker = _read_bounded_git_file(
            git_dir / "commondir",
            maximum_bytes=_GIT_POINTER_MAX_BYTES,
            required=False,
        )
        if common_marker is not None:
            common_dir = _resolve_git_directory(
                common_marker.strip(),
                relative_to=git_dir,
            )
    return _git_config_file_can_execute(
        common_dir / "config"
    ) or _git_config_file_can_execute(git_dir / "config.worktree")


def _git_invocation_scope(
    tokens: list[str],
    environment: Mapping[str, str] | None,
    working_directory: str | os.PathLike[str] | None,
) -> tuple[dict[str, str], Path | None]:
    """Apply command-local assignments and ``env`` scope mutations."""

    effective = {str(key): str(value) for key, value in (environment or {}).items()}
    current = (
        _resolve_git_directory(working_directory, relative_to=Path.cwd())
        if working_directory is not None
        else None
    )
    git_index = next(
        (
            index
            for index, token in enumerate(tokens)
            if os.path.basename(token) == "git"
        ),
        len(tokens),
    )
    inside_env = False
    index = 0
    while index < git_index:
        token = tokens[index]
        if os.path.basename(token) == "env":
            inside_env = True
            index += 1
            continue
        name, separator, value = token.partition("=")
        if separator and name in (
            _GIT_SCOPE_ENV_NAMES
            | _GIT_EXECUTION_ENV_NAMES
            | _GIT_TRACE_ENV_NAMES
        ):
            effective[name] = value
            index += 1
            continue
        if not inside_env:
            index += 1
            continue
        if token == "--":
            inside_env = False
            index += 1
            continue
        if token in {"-u", "--unset"}:
            if index + 1 >= git_index:
                raise _GitConfigurationUnresolved("env unset has no variable")
            effective.pop(tokens[index + 1], None)
            index += 2
            continue
        if token.startswith("--unset="):
            name = token.partition("=")[2]
            if not name:
                raise _GitConfigurationUnresolved("env unset has no variable")
            effective.pop(name, None)
            index += 1
            continue
        if token.startswith("-u") and token != "-u":
            effective.pop(token[2:], None)
            index += 1
            continue
        if token in {"-C", "--chdir"}:
            if index + 1 >= git_index:
                raise _GitConfigurationUnresolved("env chdir has no directory")
            current = _resolve_git_directory(
                tokens[index + 1],
                relative_to=current,
            )
            index += 2
            continue
        if token.startswith("--chdir="):
            current = _resolve_git_directory(
                token.partition("=")[2],
                relative_to=current,
            )
            index += 1
            continue
        if token.startswith("-C") and token != "-C":
            current = _resolve_git_directory(token[2:], relative_to=current)
            index += 1
            continue
        if token.startswith("-"):
            raise _GitConfigurationUnresolved("env option scope is ambiguous")
        index += 1
    return effective, current


def _git_environment_can_execute(environment: Mapping[str, str]) -> bool:
    if any(
        name in environment and str(environment[name]).strip()
        for name in _GIT_EXECUTION_ENV_NAMES
    ):
        return True
    return any(
        name in environment and str(environment[name]).lstrip().startswith("|")
        for name in _GIT_TRACE_ENV_NAMES
    )


def _is_git_scope_environment_name(name: str) -> bool:
    return (
        name == "CDPATH"
        or name
        in (
            _GIT_SCOPE_ENV_NAMES
            | _GIT_EXECUTION_ENV_NAMES
            | _GIT_TRACE_ENV_NAMES
        )
        or re.fullmatch(r"GIT_CONFIG_(?:COUNT|KEY_\d+|VALUE_\d+)", name)
        is not None
    )


def _git_configuration_scope_can_execute(
    command_tokens: list[str],
    *,
    environment: Mapping[str, str],
    working_directory: Path | None,
) -> bool:
    """Inspect every persistent config file selected by this Git invocation."""

    try:
        current = working_directory
        effective_environment = dict(environment)
        explicit_git_dir: Path | None = None
        explicit_work_tree: Path | None = None
        git_dir_selected = False
        work_tree_selected = False
        index = 1
        while index < len(command_tokens):
            argument = command_tokens[index]
            if argument == "-C":
                if index + 1 >= len(command_tokens):
                    raise _GitConfigurationUnresolved("Git -C has no directory")
                directory = command_tokens[index + 1]
                if directory:
                    current = _resolve_git_directory(directory, relative_to=current)
                index += 2
                continue
            if argument.startswith("-C") and argument != "-C":
                directory = argument[2:]
                if not directory:
                    raise _GitConfigurationUnresolved("Git -C has no directory")
                current = _resolve_git_directory(directory, relative_to=current)
                index += 1
                continue
            option_name, separator, option_value = argument.partition("=")
            if option_name in {"--git-dir", "--work-tree"}:
                if not separator:
                    if index + 1 >= len(command_tokens):
                        raise _GitConfigurationUnresolved(
                            f"Git {option_name} has no path"
                        )
                    option_value = command_tokens[index + 1]
                    index += 1
                selected = _resolve_git_directory(option_value, relative_to=current)
                if option_name == "--git-dir":
                    explicit_git_dir = selected
                    git_dir_selected = True
                else:
                    explicit_work_tree = selected
                    work_tree_selected = True
                index += 1
                continue
            if not argument.startswith("-"):
                break
            if argument in {"-c", "--namespace", "--super-prefix"}:
                index += 2
            else:
                index += 1

        if not git_dir_selected and "GIT_DIR" in effective_environment:
            explicit_git_dir = _resolve_git_directory(
                effective_environment["GIT_DIR"],
                relative_to=current,
            )
            git_dir_selected = True
        if not work_tree_selected and "GIT_WORK_TREE" in effective_environment:
            explicit_work_tree = _resolve_git_directory(
                effective_environment["GIT_WORK_TREE"],
                relative_to=current,
            )
            work_tree_selected = True

        common_directory = None
        if "GIT_COMMON_DIR" in effective_environment:
            common_directory = _resolve_git_directory(
                effective_environment["GIT_COMMON_DIR"],
                relative_to=current,
            )

        config_paths: list[tuple[Path, bool]] = []
        if "GIT_CONFIG_NOSYSTEM" not in effective_environment:
            if "GIT_CONFIG_SYSTEM" in effective_environment:
                config_paths.append(
                    (
                        _resolve_git_config_path(
                            effective_environment["GIT_CONFIG_SYSTEM"],
                            relative_to=current,
                        ),
                        True,
                    )
                )
            else:
                config_paths.extend((path, False) for path in _GIT_SYSTEM_CONFIG_PATHS)

        if "GIT_CONFIG_GLOBAL" in effective_environment:
            config_paths.append(
                (
                    _resolve_git_config_path(
                        effective_environment["GIT_CONFIG_GLOBAL"],
                        relative_to=current,
                    ),
                    True,
                )
            )
        else:
            home = None
            if "HOME" in effective_environment:
                home = _resolve_git_directory(
                    effective_environment["HOME"],
                    relative_to=None,
                )
                config_paths.append((home / ".gitconfig", False))
            if "XDG_CONFIG_HOME" in effective_environment:
                xdg_config = _resolve_git_directory(
                    effective_environment["XDG_CONFIG_HOME"],
                    relative_to=None,
                )
            elif home is not None:
                xdg_config = home / ".config"
            else:
                xdg_config = None
            if xdg_config is not None:
                config_paths.append((xdg_config / "git" / "config", False))

        if any(
            _git_config_file_can_execute(path, required=required)
            for path, required in config_paths
            if path != Path(os.devnull)
        ):
            return True

        repository_directories: set[Path] = set()
        if explicit_git_dir is not None:
            repository_directories.add(explicit_git_dir)
        elif current is not None:
            discovered = _discover_git_directory(current)
            if discovered is not None:
                repository_directories.add(discovered)
        if explicit_work_tree is not None and explicit_git_dir is None:
            discovered = _discover_git_directory(explicit_work_tree)
            if discovered is not None:
                repository_directories.add(discovered)
        return any(
            _git_directory_config_can_execute(
                git_dir,
                common_directory=common_directory,
            )
            for git_dir in repository_directories
        )
    except (OSError, _GitConfigurationUnresolved):
        return True


def _git_segment_is_heavy(
    tokens: list[str],
    *,
    environment: Mapping[str, str] | None = None,
    working_directory: str | os.PathLike[str] | None = None,
) -> bool:
    """Reject Git configuration and helper paths that can execute code."""

    command_tokens = _command_tokens(tokens)
    if not command_tokens or os.path.basename(command_tokens[0]) != "git":
        return False
    if any(
        re.fullmatch(r"GIT_CONFIG_(?:COUNT|KEY_\d+|VALUE_\d+)", token.partition("=")[0])
        is not None
        for token in tokens
        if "=" in token
    ):
        return True
    try:
        effective_environment, effective_working_directory = _git_invocation_scope(
            tokens,
            environment,
            working_directory,
        )
    except (OSError, _GitConfigurationUnresolved):
        return True
    if _git_environment_has_dynamic_config(effective_environment):
        return True
    if _git_environment_can_execute(effective_environment):
        return True
    if _git_configuration_scope_can_execute(
        command_tokens,
        environment=effective_environment,
        working_directory=effective_working_directory,
    ):
        return True
    safe_subcommands = {
        "blame",
        "cat-file",
        "check-ref-format",
        "count-objects",
        "describe",
        "diff",
        "diff-files",
        "diff-index",
        "diff-tree",
        "for-each-ref",
        "grep",
        "log",
        "ls-files",
        "ls-tree",
        "merge-base",
        "name-rev",
        "rev-list",
        "rev-parse",
        "shortlog",
        "show",
        "show-ref",
        "status",
        "version",
        "whatchanged",
    }
    value_options = {
        "-C",
        "--git-dir",
        "--namespace",
        "--super-prefix",
        "--work-tree",
    }
    subcommand: str | None = None
    index = 1
    while index < len(command_tokens):
        argument = command_tokens[index]
        if argument == "-c":
            if index + 1 >= len(command_tokens):
                return True
            setting = command_tokens[index + 1]
            key, separator, value = setting.partition("=")
            if (
                not separator
                or _git_config_key_can_execute(key)
                or value.startswith("!")
            ):
                return True
            index += 2
            continue
        if argument.startswith("-c") and argument != "-c":
            return True
        if argument in {"--config-env", "--exec-path", "--paginate", "-p"}:
            return True
        if argument.startswith(("--config-env=", "--exec-path=")):
            return True
        if argument in value_options:
            if index + 1 >= len(command_tokens):
                return True
            index += 2
            continue
        if any(argument.startswith(f"{option}=") for option in value_options):
            index += 1
            continue
        if argument in {"--no-pager", "--literal-pathspecs", "--version"}:
            index += 1
            continue
        if argument.startswith("-"):
            index += 1
            continue
        subcommand = argument
        break
    if subcommand is None:
        return False
    subcommand_arguments = command_tokens[index + 1 :]
    special_read_only = (
        subcommand == "branch"
        and not any(
            value == "--edit-description"
            or value.startswith("--edit-description=")
            for value in subcommand_arguments
        )
    ) or (
        subcommand == "tag"
        and (
            not subcommand_arguments
            or subcommand_arguments[0] in {"-l", "--list"}
        )
        and not any(
            value
            in {
                "-a",
                "--annotate",
                "-s",
                "--sign",
                "-u",
                "--local-user",
                "-v",
                "--verify",
            }
            for value in subcommand_arguments
        )
    ) or (
        subcommand == "remote"
        and (
            not subcommand_arguments
            or all(value in {"-v", "--verbose"} for value in subcommand_arguments)
            or subcommand_arguments[0] == "get-url"
        )
    ) or (
        subcommand == "reflog"
        and (
            not subcommand_arguments
            or subcommand_arguments[0] == "show"
        )
    ) or (
        subcommand == "worktree"
        and bool(subcommand_arguments)
        and subcommand_arguments[0] == "list"
    )
    if subcommand not in safe_subcommands and not special_read_only:
        # Unknown names are resolved through Git's external ``git-<name>``
        # helper mechanism; known transport/credential/editing commands also
        # have executable helper surfaces.  Only built-in inspection commands
        # are safe to bypass the lease.
        return True
    if any(
        argument
        in {
            "--ext-diff",
            "--filters",
            "--open-files-in-pager",
            "--show-signature",
            "--textconv",
        }
        or argument.startswith("--open-files-in-pager=")
        or "%G" in argument
        or "%(signature" in argument
        for argument in subcommand_arguments
    ):
        return True
    return False


def _rg_segment_is_heavy(tokens: list[str]) -> bool:
    """Reject ripgrep surfaces that execute external helper programs."""

    command_tokens = _command_tokens(tokens)
    if not command_tokens or os.path.basename(command_tokens[0]) != "rg":
        return False
    for argument in command_tokens[1:]:
        if (
            argument in {"--pre", "--hostname-bin", "--search-zip"}
            or argument.startswith(("--pre=", "--hostname-bin="))
            or (
                argument.startswith("-")
                and not argument.startswith("--")
                and "z" in argument[1:]
            )
        ):
            return True
    return False


def _nested_shell_command(tokens: list[str]) -> str | None:
    """Return a command passed to a POSIX shell's ``-c`` option."""

    command_tokens = _command_tokens(tokens)
    if not command_tokens or os.path.basename(command_tokens[0]) not in {
        "bash",
        "dash",
        "sh",
        "zsh",
    }:
        return None
    index = 1
    value_options = {"-O", "+O", "-o", "+o", "--init-file", "--rcfile"}
    while index < len(command_tokens):
        option = command_tokens[index]
        if option in value_options:
            index += 2
            continue
        if option == "-c" or (
            option.startswith(("-", "+"))
            and not option.startswith("--")
            and "c" in option[1:]
        ):
            if index + 1 < len(command_tokens):
                return command_tokens[index + 1]
            return None
        if not option.startswith(("-", "+")):
            return None
        index += 1
    return None


def _nested_shell_startup_is_heavy(tokens: list[str]) -> bool:
    """Fence nested shells that can execute user startup files before ``-c``."""

    command_tokens = _command_tokens(tokens)
    if not command_tokens:
        return False
    executable = os.path.basename(command_tokens[0])
    if executable not in {"bash", "dash", "sh", "zsh"}:
        return False
    option_arguments: list[str] = []
    index = 1
    while index < len(command_tokens):
        argument = command_tokens[index]
        if argument == "--" or not argument.startswith(("-", "+")):
            break
        option_arguments.append(argument)
        if argument in {"--init-file", "--rcfile"}:
            return True
        if argument.startswith(("--init-file=", "--rcfile=")):
            return True
        if argument in {"-O", "+O", "-o", "+o"}:
            index += 2
            continue
        if argument in {"-c", "+c", "--command"} or (
            not argument.startswith(("--", "++"))
            and "c" in argument[1:]
        ):
            break
        index += 1

    short_flags = "".join(
        argument[1:]
        for argument in option_arguments
        if argument.startswith("-") and not argument.startswith("--")
    )
    if executable == "bash":
        login = "l" in short_flags or "--login" in option_arguments
        interactive = "i" in short_flags
        no_profile = "--noprofile" in option_arguments
        no_rc = "--norc" in option_arguments
        return (login and not no_profile) or (interactive and not no_rc)
    if executable in {"dash", "sh"}:
        return "l" in short_flags or "--login" in option_arguments

    # zsh reads $ZDOTDIR/.zshenv even for a non-interactive ``-c`` command.
    # ``-f``/NO_RCS is its explicit user-startup disable boundary.
    return not (
        "f" in short_flags
        or "--no-rcs" in option_arguments
        or "--norcs" in option_arguments
    )


_CARGO_RUNNER_ENVIRONMENT_NAMES = frozenset(
    {
        "CARGO_BUILD_RUSTC",
        "CARGO_BUILD_RUSTC_WRAPPER",
        "CARGO_BUILD_RUSTC_WORKSPACE_WRAPPER",
        "CARGO_BUILD_RUSTDOC",
        "CARGO_BUILD_RUSTDOCFLAGS",
        "CARGO_BUILD_RUSTFLAGS",
        "CARGO_ENCODED_RUSTFLAGS",
        "CARGO_ENCODED_RUSTDOCFLAGS",
        "CARGO_HOME",
        "RUSTC",
        "RUSTC_WRAPPER",
        "RUSTC_WORKSPACE_WRAPPER",
        "RUSTDOC",
        "RUSTFLAGS",
    }
)
_RUNNER_ENVIRONMENT_NAMES = {
    "make": frozenset({"GNUMAKEFLAGS", "MAKEFILES", "MAKEFLAGS", "MFLAGS"}),
    "pytest": frozenset(
        {"PYTEST_ADDOPTS", "PYTEST_DISABLE_PLUGIN_AUTOLOAD", "PYTEST_PLUGINS"}
    ),
    "py.test": frozenset(
        {"PYTEST_ADDOPTS", "PYTEST_DISABLE_PLUGIN_AUTOLOAD", "PYTEST_PLUGINS"}
    ),
    "npm": frozenset(
        {
            "NODE_OPTIONS",
            "NODE_PATH",
            "NPM_CONFIG_SCRIPT_SHELL",
            "PNPM_SCRIPT_SHELL",
            "YARN_SCRIPT_SHELL",
            "npm_config_script_shell",
        }
    ),
    "pnpm": frozenset(
        {
            "NODE_OPTIONS",
            "NODE_PATH",
            "NPM_CONFIG_SCRIPT_SHELL",
            "PNPM_SCRIPT_SHELL",
            "YARN_SCRIPT_SHELL",
            "npm_config_script_shell",
        }
    ),
    "yarn": frozenset(
        {
            "NODE_OPTIONS",
            "NODE_PATH",
            "NPM_CONFIG_SCRIPT_SHELL",
            "PNPM_SCRIPT_SHELL",
            "YARN_SCRIPT_SHELL",
            "npm_config_script_shell",
        }
    ),
    "node": frozenset({"NODE_OPTIONS", "NODE_PATH"}),
    "rg": frozenset({"RIPGREP_CONFIG_PATH"}),
    "ruby": frozenset({"RUBYLIB", "RUBYOPT"}),
    "cargo": _CARGO_RUNNER_ENVIRONMENT_NAMES,
}
_PYTHON_RUNNER_ENVIRONMENT_NAMES = frozenset(
    {
        "PYTEST_ADDOPTS",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD",
        "PYTEST_PLUGINS",
        "PYTHONHOME",
        "PYTHONPATH",
        "PYTHONSTARTUP",
    }
)


def _runner_environment_is_heavy(
    command_tokens: list[str],
    environment: Mapping[str, str] | None,
) -> bool:
    """Reject inherited runner options that can widen work or import code."""

    if not command_tokens or not environment:
        return False
    executable = os.path.basename(command_tokens[0])
    names = _RUNNER_ENVIRONMENT_NAMES.get(executable, frozenset())
    if executable == "python" or (
        executable.startswith("python")
        and executable[6:].replace(".", "").isdigit()
    ):
        names = names | _PYTHON_RUNNER_ENVIRONMENT_NAMES
    if any(str(environment.get(name) or "").strip() for name in names):
        return True
    return executable == "cargo" and any(
        _is_validation_guard_environment_name(name) and str(value).strip()
        for name, value in environment.items()
        if str(name).startswith("CARGO_TARGET_")
    )


def _opaque_script_segment_is_heavy(tokens: list[str]) -> bool:
    """Fail closed for configured script entrypoints we cannot inspect."""

    command_tokens = _command_tokens(tokens)
    if not command_tokens:
        return False
    executable = os.path.basename(command_tokens[0])
    if executable in {"bash", "dash", "sh", "zsh"}:
        # Shell -c input is recursively classified by _nested_shell_command.
        if any(
            item in {"-c", "+c", "--command"}
            or (
                item.startswith(("-", "+"))
                and not item.startswith(("--", "++"))
                and "c" in item[1:]
            )
            for item in command_tokens[1:]
        ):
            return False
        arguments = [
            item
            for item in command_tokens[1:]
            if not item.startswith(("-", "+"))
        ]
        if any(item in {"--help", "--version"} for item in command_tokens[1:]):
            return False
        # A bare shell or -s reads opaque code from stdin (including a
        # preceding pipeline), so absence of a script argument is not proof of
        # bounded work.
        return True
    if executable == "python" or (
        executable.startswith("python")
        and executable[6:].replace(".", "").isdigit()
    ):
        arguments = command_tokens[1:]
        if any(item in {"-h", "--help", "-V", "--version"} for item in arguments):
            return False
        if any(item == "-c" or item.startswith("-c") for item in arguments):
            return True
        if "-m" in arguments:
            module_index = arguments.index("-m")
            module = arguments[module_index + 1] if module_index + 1 < len(arguments) else ""
            # The dedicated classifiers decide whether explicit pytest and
            # unittest selectors are bounded. Other modules are opaque code.
            return module not in {"pytest", "unittest"}
        skip_next = False
        for item in arguments:
            if skip_next:
                skip_next = False
                continue
            if item in {"-W", "-X", "--check-hash-based-pycs"}:
                skip_next = True
                continue
            if item == "-" or not item.startswith("-"):
                return True
        # Bare Python (possibly with flags) executes opaque stdin.
        return True
    if executable in {"node", "perl", "ruby"}:
        arguments = command_tokens[1:]
        if executable == "ruby":
            # Ruby's -v/--version mode continues into -e or a script.  It is
            # informational only when it is the complete invocation.
            if len(arguments) == 1 and arguments[0] in {
                "-h",
                "--help",
                "-v",
                "-V",
                "--version",
            }:
                return False
            return True
        if any(item in {"-h", "--help", "-v", "-V", "--version"} for item in arguments):
            return False
        eval_options = {"-e", "--eval"} if executable == "node" else {"-e"}
        if any(
            item in eval_options
            or any(item.startswith(option) and item != option for option in eval_options)
            for item in arguments
        ):
            return True
        # Option-only and bare forms can execute opaque stdin too. Help and
        # version invocations were handled above.
        return True
    return False


def _guard_environment_mutation_is_heavy(tokens: list[str]) -> bool:
    """Fail closed when shell syntax can weaken the native guard boundary."""

    if any(
        "=" in token
        and _is_validation_guard_environment_name(token.partition("=")[0])
        for token in tokens
    ):
        return True
    command_tokens = _command_tokens(tokens)
    if not command_tokens:
        return False
    if os.path.basename(command_tokens[0]) == "printf":
        for argument in command_tokens[1:]:
            if argument == "--":
                break
            if (
                argument == "-v"
                or argument.startswith("-v")
                or argument == "--variable"
                or argument.startswith("--variable=")
            ):
                # printf -v persists a shell variable assignment and preserves
                # an existing export attribute.  Its formatting language and
                # indirect destination make later Git scope too ambiguous to
                # model safely; fence all such mutations, not just guard vars.
                return True
    # ``env -i`` and Bash ``exec -c`` discard the complete inherited
    # environment, including both BASH_ENV and the guard marker.  Compact env
    # spellings are deliberately normalized here instead of relying on the
    # generic wrapper parser.
    if any(os.path.basename(token) == "env" for token in tokens) and any(
        argument == "--ignore-environment"
        or (
            argument.startswith("-")
            and not argument.startswith("--")
            and "i" in argument[1:]
        )
        for argument in tokens
    ):
        return True
    # GNU env and Bash exec can replace argv[0].  In particular, ``-bash``
    # turns an otherwise non-login ``bash -c`` into a login shell that reads
    # HOME profiles before BASH_ENV.  The argv-zero provenance is not visible
    # in the recursively classified payload, so fence every such wrapper.
    if any(os.path.basename(token) == "env" for token in tokens) and any(
        argument in {"-a", "--argv0"}
        or argument.startswith(("-a=", "--argv0="))
        or (argument.startswith("-a") and argument != "-a")
        for argument in tokens
    ):
        return True
    if any(os.path.basename(token) == "exec" for token in tokens) and any(
        argument in {"-a", "--argv0"}
        or argument.startswith(("-a=", "--argv0="))
        or (argument.startswith("-a") and argument != "-a")
        for argument in tokens
    ):
        return True
    if any(os.path.basename(token) == "exec" for token in tokens) and any(
        argument.startswith("-")
        and not argument.startswith("--")
        and "c" in argument[1:]
        for argument in tokens
    ):
        return True
    if any(os.path.basename(token) == "command" for token in tokens) and any(
        argument.startswith("-")
        and not argument.startswith("--")
        and "p" in argument[1:]
        for argument in tokens
    ):
        return True

    mutator_index = next(
        (
            index
            for index, token in enumerate(tokens)
            if os.path.basename(token) in _SHELL_ENVIRONMENT_MUTATORS
        ),
        None,
    )
    if mutator_index is None:
        return False
    arguments = tokens[mutator_index + 1 :]
    if any("$" in argument or "`" in argument for argument in arguments):
        return True
    for index, argument in enumerate(arguments):
        candidates = {
            argument,
            argument.partition("=")[0].removesuffix("+"),
        }
        if argument.startswith("--unset="):
            candidates.add(argument.partition("=")[2])
        elif argument.startswith("-u") and argument != "-u":
            candidates.add(argument[2:])
        elif argument in {"-u", "--unset"} and index + 1 < len(arguments):
            candidates.add(arguments[index + 1].partition("=")[0])
        if any(_is_validation_guard_environment_name(name) for name in candidates):
            return True
    return False


def _persistent_shell_scope_mutation(
    tokens: list[str],
    environment: Mapping[str, str] | None,
    working_directory: str | os.PathLike[str] | None,
) -> tuple[dict[str, str] | None, Path | None] | None:
    """Apply deterministic shell state used by a later Git segment."""

    if not tokens:
        return None
    assignments: list[tuple[str, str]] = []
    for token in tokens:
        name, separator, value = token.partition("=")
        if not separator or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) is None:
            assignments = []
            break
        assignments.append((name, value))
    if assignments:
        if environment is None:
            raise _GitConfigurationUnresolved(
                "shell assignment has no complete environment baseline"
            )
        effective = {
            str(key): str(value) for key, value in environment.items()
        }
        for name, value in assignments:
            if not _is_git_scope_environment_name(name):
                raise _GitConfigurationUnresolved(
                    "non-Git persistent shell assignment is not modeled"
                )
            if name not in effective:
                # An assignment-only command preserves an existing export
                # attribute, but a newly created shell variable is not
                # exported unless shell options or prior state say otherwise.
                # Neither is visible here, so the later Git scope is opaque.
                raise _GitConfigurationUnresolved(
                    "shell assignment export state cannot be resolved"
                )
            effective[name] = value
        current = (
            _resolve_git_directory(working_directory, relative_to=Path.cwd())
            if working_directory is not None
            else None
        )
        return effective, current
    executable = os.path.basename(tokens[0])
    if executable not in {"cd", "export", "unset"}:
        return None
    current = (
        _resolve_git_directory(working_directory, relative_to=Path.cwd())
        if working_directory is not None
        else None
    )
    effective = (
        {str(key): str(value) for key, value in environment.items()}
        if environment is not None
        else None
    )
    if executable == "cd":
        arguments = list(tokens[1:])
        while arguments and arguments[0] in {"-L", "-P"}:
            arguments.pop(0)
        if arguments and arguments[0] == "--":
            arguments.pop(0)
        if len(arguments) > 1 or (arguments and arguments[0] == "-"):
            raise _GitConfigurationUnresolved("shell cd scope is ambiguous")
        if arguments:
            destination = arguments[0]
        elif effective is not None and effective.get("HOME"):
            destination = effective["HOME"]
        else:
            raise _GitConfigurationUnresolved("shell cd has no known destination")
        if (
            effective is not None
            and effective.get("CDPATH")
            and not Path(destination).is_absolute()
            and not destination.startswith(("./", "../"))
        ):
            raise _GitConfigurationUnresolved("shell CDPATH scope is ambiguous")
        changed = _resolve_git_directory(destination, relative_to=current)
        if not os.access(changed, os.X_OK):
            raise _GitConfigurationUnresolved("shell cd destination is inaccessible")
        return effective, changed

    if effective is None:
        raise _GitConfigurationUnresolved(
            "shell environment mutation has no complete baseline"
        )
    arguments = list(tokens[1:])
    remove = False
    if executable == "export":
        if arguments and arguments[0] == "-n":
            remove = True
            arguments.pop(0)
        if arguments and arguments[0] == "--":
            arguments.pop(0)
        if not arguments:
            raise _GitConfigurationUnresolved("shell export scope is ambiguous")
        for argument in arguments:
            name, separator, value = argument.partition("=")
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) is None:
                raise _GitConfigurationUnresolved("shell export name is invalid")
            if not _is_git_scope_environment_name(name):
                raise _GitConfigurationUnresolved(
                    "non-Git shell export scope is not modeled"
                )
            if remove:
                effective.pop(name, None)
            elif separator:
                effective[name] = value
            elif name not in effective:
                raise _GitConfigurationUnresolved(
                    "shell export value cannot be resolved"
                )
        return effective, current

    if arguments and arguments[0] in {"-v", "--"}:
        arguments.pop(0)
    if arguments and arguments[0] == "-f":
        raise _GitConfigurationUnresolved("shell function unset is ambiguous")
    for name in arguments:
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) is None:
            raise _GitConfigurationUnresolved("shell unset name is invalid")
        if not _is_git_scope_environment_name(name):
            raise _GitConfigurationUnresolved(
                "non-Git shell unset scope is not modeled"
            )
        effective.pop(name, None)
    return effective, current


def _is_persistent_shell_scope_mutation(tokens: list[str]) -> bool:
    if not tokens:
        return False
    if os.path.basename(tokens[0]) in {"cd", "export", "unset"}:
        return True
    return all(
        bool(separator)
        and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) is not None
        for name, separator, _value in (token.partition("=") for token in tokens)
    )


def _known_shell_command_status(tokens: list[str]) -> bool | None:
    """Return the deterministic status of shell builtins used for branching."""

    command_tokens = _command_tokens(tokens)
    if command_tokens in (["true"], [":"]):
        return True
    if command_tokens == ["false"]:
        return False
    return None


def _combined_shell_status(
    operator: str | None,
    previous_status: bool | None,
    command_status: bool | None,
) -> bool | None:
    """Apply POSIX AND-OR list truth tables to an abstract command status."""

    if operator in {None, ";"}:
        return command_status
    if operator == "&&":
        if previous_status is False or command_status is False:
            return False
        if previous_status is True:
            return command_status
        return None
    if operator == "||":
        if previous_status is True or command_status is True:
            return True
        if previous_status is False:
            return command_status
        return None
    return None


def is_heavyweight_validation_command(
    command: str,
    *,
    executable_search_path: str | None = None,
    untrusted_executable_roots: tuple[str | os.PathLike[str], ...] = (),
    command_environment: Mapping[str, str] | None = None,
    working_directory: str | os.PathLike[str] | None = None,
) -> bool:
    """Classify auditor shell input, with heavyweight evidence winning.

    Non-test inspection commands bypass the lease.  Once a command invokes a
    known test runner, ambiguous syntax is treated as heavyweight.  Every
    top-level shell segment is examined, preventing a light prefix/suffix from
    hiding a full suite (for example ``echo ready; make test``).
    """

    raw_input = str(command or "").strip()
    if _shell_has_active_ansi_c_quote(raw_input):
        return True
    raw = _remove_shell_line_continuations(raw_input).strip()
    if _shell_has_active_ansi_c_quote(raw):
        return True
    if not raw:
        return False
    # These constructs execute text or files that cannot be proven by parsing
    # the visible command argv.  Treat them as capacity-bearing rather than
    # letting an absolute non-Bash descendant or dynamic command bypass native
    # PATH/BASH_ENV interception.
    if any(marker in raw for marker in ("$(", "<(", ">(", "<<")):
        return True
    if _shell_has_active_backtick(raw):
        return True
    if _shell_has_active_extglob(raw):
        return True
    try:
        segments = _shell_segments(raw)
    except ValueError:
        # Classification is a pre-execution trust boundary.  If POSIX shlex
        # and the quote/expansion provenance model disagree or cannot parse a
        # Bash extension, no literal substring fallback can prove the argv
        # that the shell will execute.  Own capacity conservatively.
        return True
    scope_environment = (
        {str(key): str(value) for key, value in command_environment.items()}
        if command_environment is not None
        else None
    )
    if scope_environment is not None and any(
        _is_dynamic_loader_environment_name(name)
        and str(value).strip()
        for name, value in scope_environment.items()
    ):
        # A caller that has not sanitized inherited loader controls cannot
        # safely launch even the first otherwise-lightweight executable.
        return True
    if scope_environment is not None and any(
        str(name).startswith("BASH_FUNC_") for name in scope_environment
    ):
        # Bash imports exported functions before BASH_ENV.  The classifier
        # cannot prove that a harmless-looking command name still resolves to
        # an executable rather than a task-supplied function body.
        return True
    scope_working_directory: str | os.PathLike[str] | None = working_directory
    shell_status: bool | None = None
    shell_scope_mutated = False
    for operator, tokens, unquoted_expansion_flags in segments:
        if not tokens:
            continue
        executes: bool | None
        if operator in {None, ";"}:
            executes = True
        elif operator == "&&":
            executes = shell_status if shell_status is not None else None
        elif operator == "||":
            executes = not shell_status if shell_status is not None else None
        else:
            executes = None
            if shell_scope_mutated or _is_persistent_shell_scope_mutation(tokens):
                return True
        if executes is False:
            continue
        if _is_persistent_shell_scope_mutation(tokens) and executes is None:
            # Whether the state change runs depends on an opaque command's
            # status.  A later segment can therefore observe either scope.
            return True
        if shell_scope_mutated and operator == "||":
            # A fallback after cd/export/assignment can run specifically when
            # that mutation failed, in which case it observes the old scope.
            return True
        if tokens[0] in _SHELL_CONTROL_WORDS:
            return True
        if _guard_environment_mutation_is_heavy(tokens):
            return True
        try:
            scope_mutation = _persistent_shell_scope_mutation(
                tokens,
                scope_environment,
                scope_working_directory,
            )
        except (OSError, _GitConfigurationUnresolved):
            return True
        if scope_mutation is not None:
            scope_environment, scope_working_directory = scope_mutation
            shell_scope_mutated = True
            shell_status = _combined_shell_status(operator, shell_status, None)
            continue
        command_tokens = _command_tokens(tokens)
        if command_tokens == ["__oompah_opaque_env_split_string__"]:
            return True
        if command_tokens:
            executable_name = os.path.basename(command_tokens[0])
            classified_command = (
                executable_name in _CLASSIFIED_COMMAND_NAMES
                or executable_name in {"find", "git", "rg"}
                or (
                    executable_name.startswith("python")
                    and executable_name[6:].replace(".", "").isdigit()
                )
            )
            if classified_command:
                command_syntax_flags = _aligned_shell_syntax_flags(
                    tokens,
                    command_tokens,
                    unquoted_expansion_flags,
                )
                if command_syntax_flags is None or any(command_syntax_flags):
                    # Shell expansion or redirection can rewrite a seemingly
                    # bounded argv into a full-suite or executable-helper
                    # invocation.  Quoted literals retain false provenance.
                    return True
        if _nested_shell_startup_is_heavy(tokens):
            return True
        if _runner_environment_is_heavy(command_tokens, scope_environment):
            return True
        if (
            _make_segment_is_heavy(tokens)
            or _pytest_segment_is_heavy(
                tokens,
                working_directory=scope_working_directory,
            )
            or _unittest_segment_is_heavy(tokens)
            or _npm_segment_is_heavy(tokens)
            or _cargo_segment_is_heavy(
                tokens,
                environment=scope_environment,
                working_directory=scope_working_directory,
            )
            or _find_segment_is_heavy(tokens)
            or _sed_segment_is_heavy(
                tokens,
                unquoted_expansion_flags=unquoted_expansion_flags,
            )
            or _git_segment_is_heavy(
                tokens,
                environment=scope_environment,
                working_directory=scope_working_directory,
            )
            or _rg_segment_is_heavy(tokens)
            or _opaque_script_segment_is_heavy(tokens)
        ):
            return True
        if command_tokens:
            executable_name = os.path.basename(command_tokens[0])
            if executable_name in _OPAQUE_SHELL_EXECUTORS:
                return True
            if "$" in command_tokens[0] or "`" in command_tokens[0]:
                return True
            if executable_name in {"export", "unset"} and any(
                _is_validation_guard_environment_name(
                    argument.partition("=")[0]
                )
                for argument in command_tokens[1:]
            ):
                return True
        nested_command = _nested_shell_command(command_tokens)
        if nested_command is not None and is_heavyweight_validation_command(
            nested_command,
            executable_search_path=executable_search_path,
            untrusted_executable_roots=untrusted_executable_roots,
            command_environment=scope_environment,
            working_directory=scope_working_directory,
        ):
            return True
        if command_tokens and os.path.basename(command_tokens[0]) in {"tox", "nox"}:
            return True
        if command_tokens:
            executable = command_tokens[0]
            executable_name = os.path.basename(executable)
            if (
                executable_search_path is not None
                and "/" not in executable
                and executable_name not in _LIGHTWEIGHT_SHELL_BUILTINS
            ):
                if any(
                    not part or not Path(part).is_absolute()
                    for part in executable_search_path.split(os.pathsep)
                ):
                    return True
                resolved = shutil.which(
                    executable,
                    path=executable_search_path,
                )
                if not resolved:
                    return True
                try:
                    selected_path = Path(resolved).absolute()
                    resolved_path = Path(resolved).resolve(strict=True)
                    resolved_stat = resolved_path.stat()
                    untrusted_roots = tuple(
                        Path(root).resolve()
                        for root in untrusted_executable_roots
                    )
                except OSError:
                    return True
                if (
                    not stat.S_ISREG(resolved_stat.st_mode)
                    or resolved_stat.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
                    or os.access(selected_path, os.W_OK)
                    or os.access(selected_path.parent, os.W_OK)
                    or os.access(resolved_path.parent, os.W_OK)
                    or any(
                        selected_path == root
                        or root in selected_path.parents
                        or resolved_path == root
                        or root in resolved_path.parents
                        for root in untrusted_roots
                    )
                ):
                    return True
            # Project-local and absolute launchers are opaque before they run.
            # They may be configured full-suite wrappers (for example
            # ``./ci/test.sh``), so managed validation must fail closed.  The
            # normal bounded inspection tools are invoked by name and remain
            # outside this branch.
            if executable.startswith(("./", "../")):
                return True
            if os.path.isabs(executable):
                trusted_system_tool = (
                    os.path.dirname(os.path.normpath(executable))
                    in {"/bin", "/usr/bin", "/usr/local/bin"}
                    and os.path.basename(executable)
                    in _ABSOLUTE_LIGHTWEIGHT_INSPECTION_TOOLS
                )
                if not trusted_system_tool:
                    return True
            elif "/" in executable:
                return True
            elif (
                executable_name not in _LIGHTWEIGHT_COMMAND_NAMES
                and executable_name not in _CLASSIFIED_COMMAND_NAMES
                and not (
                    executable_name.startswith("python")
                    and executable_name[6:].replace(".", "").isdigit()
                )
            ):
                # A task can prepend a writable directory to PATH and invoke a
                # project-owned test wrapper by a harmless-looking bare name.
                # Only the small explicit inspection/builtin set is provably
                # bounded before exec; unknown commands own capacity.
                return True
        shell_status = _combined_shell_status(
            operator,
            shell_status,
            _known_shell_command_status(tokens),
        )
    return False


def is_full_suite_validation_command(
    command: str,
    *,
    configured_command: str = "",
) -> bool:
    """Return whether auditor shell input launches a full-suite validation.

    Evidence reuse deliberately requires byte-for-byte equality (after outer
    whitespace trimming) with the configured command.  Observability has a
    different job: it must recognize that wrappers, chains, and the project's
    serial Make target still consume a full-suite lane.  Keep that semantic
    classification here beside the shell parser without weakening the exact
    quality-gate evidence key.
    """

    raw = str(command or "").strip()
    if not raw:
        return False
    configured = str(configured_command or "").strip()
    if configured and raw == configured:
        return True

    try:
        segments = _shell_segments(raw)
        configured_segments = _shell_segments(configured) if configured else []
    except ValueError:
        lowered = raw.casefold()
        return "make test" in lowered or "make\ttest" in lowered

    configured_tokens: list[str] | None = None
    if len(configured_segments) == 1:
        _operator, configured_segment_tokens, configured_flags = (
            configured_segments[0]
        )
        configured_tokens = _command_tokens(configured_segment_tokens)
        aligned_configured_flags = _aligned_shell_syntax_flags(
            configured_segment_tokens,
            configured_tokens,
            configured_flags,
        )
        if aligned_configured_flags is None or any(aligned_configured_flags):
            # Only exact-string equality above may reuse a configured command
            # whose argv depends on shell expansion.
            configured_tokens = None

    for _operator, tokens, unresolved_syntax_flags in segments:
        env_split_command = _env_split_string_command(tokens)
        if env_split_command is not None and is_full_suite_validation_command(
            env_split_command,
            configured_command=configured,
        ):
            return True
        command_tokens = _command_tokens(tokens)
        if not command_tokens:
            continue
        command_flags = _aligned_shell_syntax_flags(
            tokens,
            command_tokens,
            unresolved_syntax_flags,
        )
        if command_flags is None or any(command_flags):
            # Dynamic argv is already heavyweight at the execution boundary.
            # It cannot be proven focused, so reuse policy must treat it as a
            # potentially full-suite invocation and require the explicit
            # distinct-mode escape.
            return True
        if configured_tokens and command_tokens == configured_tokens:
            return True

        nested_command = _nested_shell_command(command_tokens)
        if nested_command is not None and is_full_suite_validation_command(
            nested_command,
            configured_command=configured,
        ):
            return True

        if _pytest_segment_is_full_suite(command_tokens):
            return True
        if _unittest_segment_is_full_suite(command_tokens):
            return True
        if _npm_segment_is_full_suite(command_tokens) or (
            _cargo_segment_is_full_suite(command_tokens)
        ):
            return True
        if os.path.basename(command_tokens[0]) in {"tox", "nox"}:
            return True

        if os.path.basename(command_tokens[0]) != "make":
            continue
        targets: list[str] = []
        skip_next = False
        for argument in command_tokens[1:]:
            if skip_next:
                skip_next = False
                continue
            if argument == "--":
                continue
            if argument in {
                "-C",
                "--directory",
                "-f",
                "--file",
                "-I",
                "--include-dir",
            }:
                skip_next = True
                continue
            if argument.startswith("-") or "=" in argument:
                continue
            targets.append(argument)
        if any(
            target in {"test", "test-serial", "test-all", "tests"}
            for target in targets
        ):
            return True
    return False


def is_focused_validation_command(command: str) -> bool:
    """Return true only for provably selector-scoped heavyweight validation."""

    raw = str(command or "").strip()
    if not raw:
        return False
    try:
        segments = _shell_segments(raw)
    except ValueError:
        return False
    saw_focused = False
    for _operator, tokens, unresolved_syntax_flags in segments:
        env_split_command = _env_split_string_command(tokens)
        if env_split_command is not None:
            if not is_focused_validation_command(env_split_command):
                return False
            saw_focused = True
            continue
        command_tokens = _command_tokens(tokens)
        if not command_tokens:
            continue
        command_flags = _aligned_shell_syntax_flags(
            tokens,
            command_tokens,
            unresolved_syntax_flags,
        )
        if command_flags is None or any(command_flags):
            return False
        nested_command = _nested_shell_command(command_tokens)
        if nested_command is not None:
            if is_heavyweight_validation_command(nested_command):
                if not is_focused_validation_command(nested_command):
                    return False
                saw_focused = True
            continue
        if not is_heavyweight_validation_command(shlex.join(tokens)):
            continue
        pytest_invocation = _pytest_invocation(command_tokens)
        if pytest_invocation is not None:
            if _pytest_segment_is_full_suite(command_tokens):
                return False
            saw_focused = True
            continue
        unittest_arguments = _unittest_arguments(command_tokens)
        if unittest_arguments is not None:
            if _unittest_segment_is_full_suite(command_tokens):
                return False
            saw_focused = True
            continue
        return False
    return saw_focused


def contains_configured_validation_command(
    command: str,
    *,
    configured_command: str,
) -> bool:
    """Return whether shell input contains the configured gate invocation.

    This comparison is stricter than full-suite classification but normalizes
    non-semantic process wrappers such as ``env``, ``timeout``, and ``bash -c``.
    It prevents a reused exact gate from being rerun merely by changing its
    superficial shell spelling.  It is not used for evidence identity, which
    remains exact-string keyed.
    """

    raw = str(command or "").strip()
    configured = str(configured_command or "").strip()
    if not raw or not configured:
        return False
    if raw == configured:
        return True
    try:
        configured_segments = _shell_segments(configured)
        segments = _shell_segments(raw)
    except ValueError:
        return False
    if len(configured_segments) != 1:
        return False
    _operator, configured_segment_tokens, configured_flags = configured_segments[0]
    configured_tokens = _command_tokens(configured_segment_tokens)
    if not configured_tokens:
        return False
    aligned_configured_flags = _aligned_shell_syntax_flags(
        configured_segment_tokens,
        configured_tokens,
        configured_flags,
    )
    if aligned_configured_flags is None or any(aligned_configured_flags):
        return False
    for _operator, tokens, unresolved_syntax_flags in segments:
        env_split_command = _env_split_string_command(tokens)
        if env_split_command is not None and contains_configured_validation_command(
            env_split_command,
            configured_command=configured,
        ):
            return True
        command_tokens = _command_tokens(tokens)
        command_flags = _aligned_shell_syntax_flags(
            tokens,
            command_tokens,
            unresolved_syntax_flags,
        )
        if command_flags is None or any(command_flags):
            continue
        if command_tokens == configured_tokens:
            return True
        nested_command = _nested_shell_command(command_tokens)
        if nested_command is not None and contains_configured_validation_command(
            nested_command,
            configured_command=configured,
        ):
            return True
    return False


@dataclass(frozen=True)
class ValidationCommandClassification:
    """One normalized command classification shared by policy and leasing."""

    heavyweight: bool
    scope: str
    contains_configured: bool = False

    @property
    def focused(self) -> bool:
        return self.scope == "focused"

    @property
    def full_suite(self) -> bool:
        return self.scope == "full"

    @property
    def opaque(self) -> bool:
        return self.scope == "opaque"


def _validation_context_is_opaque(
    command: str,
    *,
    executable_search_path: str | None,
    untrusted_executable_roots: tuple[str | os.PathLike[str], ...],
    command_environment: Mapping[str, str] | None,
    working_directory: str | os.PathLike[str] | None,
) -> bool:
    """Return whether context prevents a semantic focused/full verdict."""

    try:
        segments = _shell_segments(str(command or ""))
        untrusted_roots = tuple(
            Path(root).resolve() for root in untrusted_executable_roots
        )
    except (OSError, ValueError):
        return True
    for _operator, tokens, unresolved_syntax_flags in segments:
        # The normalized executable argv deliberately omits leading
        # assignments.  Preserve their provenance here: runner controls and
        # PATH changes make a syntactically focused command semantically
        # opaque, and expansion-bearing assignments cannot be resolved before
        # the shell evaluates them.
        if any(unresolved_syntax_flags):
            return True
        for token in tokens:
            name, separator, value = token.partition("=")
            if (
                separator
                and name.replace("_", "a").isalnum()
                and _is_validation_guard_environment_name(name)
                and value.strip()
            ):
                return True
        if _guard_environment_mutation_is_heavy(tokens):
            return True
        command_tokens = _command_tokens(tokens)
        if not command_tokens:
            continue
        command_flags = _aligned_shell_syntax_flags(
            tokens,
            command_tokens,
            unresolved_syntax_flags,
        )
        if command_flags is None or any(command_flags):
            return True
        if _runner_environment_is_heavy(command_tokens, command_environment):
            return True
        nested_command = _nested_shell_command(command_tokens)
        if nested_command is not None and _validation_context_is_opaque(
            nested_command,
            executable_search_path=executable_search_path,
            untrusted_executable_roots=untrusted_executable_roots,
            command_environment=command_environment,
            working_directory=working_directory,
        ):
            return True
        executable = command_tokens[0]
        executable_name = os.path.basename(executable)
        if executable_search_path is not None and "/" not in executable:
            if any(
                not part or not Path(part).is_absolute()
                for part in executable_search_path.split(os.pathsep)
            ):
                return True
            resolved = shutil.which(executable, path=executable_search_path)
            if not resolved:
                return True
            try:
                selected_path = Path(resolved).absolute()
                resolved_path = Path(resolved).resolve(strict=True)
                resolved_stat = resolved_path.stat()
            except OSError:
                return True
            if (
                not stat.S_ISREG(resolved_stat.st_mode)
                or resolved_stat.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
                or any(
                    selected_path == root
                    or root in selected_path.parents
                    or resolved_path == root
                    or root in resolved_path.parents
                    for root in untrusted_roots
                )
            ):
                return True
        elif executable.startswith(("./", "../")) or "/" in executable:
            try:
                selected_path = Path(executable)
                if not selected_path.is_absolute():
                    selected_path = (
                        Path(working_directory or os.getcwd()) / selected_path
                    )
                resolved_path = selected_path.resolve(strict=True)
                resolved_stat = resolved_path.stat()
            except OSError:
                return True
            if (
                not stat.S_ISREG(resolved_stat.st_mode)
                or resolved_stat.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
                or any(
                    resolved_path == root or root in resolved_path.parents
                    for root in untrusted_roots
                )
            ):
                return True
        elif (
            executable_name not in _LIGHTWEIGHT_COMMAND_NAMES
            and executable_name not in _CLASSIFIED_COMMAND_NAMES
            and executable_name not in {"find", "git", "rg"}
            and not (
                executable_name.startswith("python")
                and executable_name[6:].replace(".", "").isdigit()
            )
        ):
            return True
    return False


def classify_validation_command(
    command: str,
    *,
    configured_command: str = "",
    executable_search_path: str | None = None,
    untrusted_executable_roots: tuple[str | os.PathLike[str], ...] = (),
    command_environment: Mapping[str, str] | None = None,
    working_directory: str | os.PathLike[str] | None = None,
) -> ValidationCommandClassification:
    """Classify once for capacity, gate-reuse policy, and telemetry."""

    heavyweight = is_heavyweight_validation_command(
        command,
        executable_search_path=executable_search_path,
        untrusted_executable_roots=untrusted_executable_roots,
        command_environment=command_environment,
        working_directory=working_directory,
    )
    if not heavyweight:
        return ValidationCommandClassification(False, "light")
    configured = contains_configured_validation_command(
        command,
        configured_command=configured_command,
    )
    if _validation_context_is_opaque(
        command,
        executable_search_path=executable_search_path,
        untrusted_executable_roots=untrusted_executable_roots,
        command_environment=command_environment,
        working_directory=working_directory,
    ):
        scope = "opaque"
    elif is_full_suite_validation_command(
        command,
        configured_command=configured_command,
    ):
        scope = "full"
    elif is_focused_validation_command(command):
        scope = "focused"
    else:
        scope = "opaque"
    return ValidationCommandClassification(
        True,
        scope,
        contains_configured=configured,
    )


def auditor_validation_owner(
    action_policy: object,
    audit_target: object,
) -> ValidationLeaseOwner | None:
    """Build trusted lease identity only for a completion-auditor session."""

    if getattr(action_policy, "auditor_session", False) is not True:
        return None

    def value(name: str) -> str:
        if isinstance(audit_target, dict):
            return str(audit_target.get(name) or "").strip()
        return str(getattr(audit_target, name, "") or "").strip()

    project_id = value("project_id") or str(
        getattr(action_policy, "project_id", "") or ""
    ).strip()
    task_id = value("task_id") or str(
        getattr(action_policy, "task_identifier", "") or ""
    ).strip()
    generation = value("attempt_id") or value("audit_id")
    if not all((project_id, task_id, generation)):
        return None
    return ValidationLeaseOwner.auditor(
        project_id=project_id,
        task_id=task_id,
        authority_generation=generation,
    )


def managed_agent_validation_owner(
    action_policy: object,
    audit_target: object,
    *,
    project_id: object,
    task_id: object,
    authority_generation: object | None = None,
) -> ValidationLeaseOwner | None:
    """Build trusted auditor or implementation-worker lease identity.

    Auditor attempt identity remains authoritative when present.  Ordinary
    managed workers use their server-issued project/task scope and an opaque
    per-session generation.  Unmanaged/standalone callers intentionally get
    no identity; service call sites decide whether that is a fail-closed error.
    """

    auditor = auditor_validation_owner(action_policy, audit_target)
    if auditor is not None:
        return auditor
    normalized_project = str(project_id or "").strip()
    normalized_task = str(task_id or "").strip()
    if not normalized_project or not normalized_task:
        return None
    generation = str(authority_generation or "").strip() or uuid.uuid4().hex
    return ValidationLeaseOwner.worker(
        project_id=normalized_project,
        task_id=normalized_task,
        authority_generation=generation,
    )


class ValidationLeaseHandle:
    """One fenced capacity slot.  Release is token-checked and idempotent."""

    def __init__(
        self,
        manager: "ValidationResourceLease",
        *,
        token: str,
        slot: int,
        lock_fd: int,
    ) -> None:
        self._manager = manager
        self.token = token
        self.slot = slot
        self._lock_fd = lock_fd
        self._released = False
        self._release_lock = threading.Lock()

    @property
    def pass_fds(self) -> tuple[int, ...]:
        return (self._lock_fd,) if self._lock_fd >= 0 else ()

    def attach_process(self, process: object, *, timeout_seconds: float) -> None:
        pid = int(getattr(process, "pid"))
        start_ticks = _process_start_ticks(pid)
        if start_ticks is None:
            raise ValidationLeaseError(
                "cannot fence validation subprocess identity"
            )
        self._manager._attach_process(
            self.token,
            pid=pid,
            start_ticks=start_ticks,
            deadline_at=time.time() + max(float(timeout_seconds), 1.0),
        )

    def release(self) -> bool:
        with self._release_lock:
            if self._released:
                return False
            try:
                return self._manager._release(
                    self.token,
                    self.slot,
                    self._lock_fd,
                )
            except Exception:  # noqa: BLE001 - release must never mask a result
                logger.exception(
                    "Unable to finalize validation lease release token=%s slot=%s",
                    self.token,
                    self.slot,
                )
                # Close this process's duplicate without an explicit LOCK_UN:
                # a background descendant may still hold the inherited open
                # file description and must continue fencing capacity.
                with contextlib.suppress(OSError):
                    os.close(self._lock_fd)
                return False
            finally:
                self._lock_fd = -1
                self._released = True

    def relinquish_transferred_descriptor(self) -> None:
        """Close this process's copy after transferring the fence descriptor.

        ``SCM_RIGHTS`` gives the receiver a duplicate of the same open file
        description.  Calling :meth:`release` here would explicitly unlock it
        for both processes and delete the durable owner before the receiver can
        exec.  Closing only the sender copy leaves the receiver and its future
        descendants as the kernel authority for the slot.
        """

        with self._release_lock:
            if self._released:
                raise ValidationLeaseError(
                    "validation fence descriptor was already finalized"
                )
            descriptor = self._lock_fd
            self._lock_fd = -1
            self._released = True
        if descriptor < 0:
            raise ValidationLeaseError("validation fence descriptor is unavailable")
        os.close(descriptor)

    def __enter__(self) -> "ValidationLeaseHandle":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.release()


class ValidationResourceLease:
    """Process-safe, durable and fair heavyweight-validation capacity."""

    def __init__(
        self,
        state_path: str | Path,
        *,
        capacity: int = 1,
        aging_seconds: float = 30.0,
        poll_seconds: float = 0.05,
    ) -> None:
        if fcntl is None:
            raise ValidationLeaseError("validation leases require POSIX flock support")
        self.state_path = Path(state_path).expanduser().resolve()
        self.state_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.capacity = max(int(capacity), 1)
        self.aging_seconds = max(float(aging_seconds), 0.01)
        self.poll_seconds = max(float(poll_seconds), 0.01)
        # Capture operator executable identities before any managed task can
        # run. A later path replacement must not redefine what an old provider
        # process is trusted to be.
        self._trusted_codex_bootstrap_identity = (
            _trusted_codex_bootstrap_identity()
        )
        service_start_ticks = _process_start_ticks(os.getpid())
        self._trusted_provider_parent_identity = (
            (os.getpid(), service_start_ticks)
            if service_start_ticks is not None
            else None
        )
        self._slot_dir = self.state_path.with_suffix(self.state_path.suffix + ".locks")
        self._slot_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._slot_dir.chmod(0o700)
        self._initialize()
        self.state_path.chmod(0o600)

    @contextlib.contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Yield one transactional connection and close it deterministically."""

        connection = sqlite3.connect(self.state_path, timeout=10.0)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA busy_timeout = 10000")
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        """Initialize atomically, quarantining unreadable SQLite state.

        The slot flocks remain the execution fence, so replacing corrupt
        metadata cannot grant a slot that a surviving validation process still
        owns. A separate bootstrap flock prevents two restarting service
        processes from racing the quarantine/creation sequence.
        """

        init_path = self.state_path.with_suffix(
            self.state_path.suffix + ".initialize.lock"
        )
        init_fd = os.open(init_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(init_fd, fcntl.LOCK_EX)
            try:
                self._initialize_schema()
                return
            except sqlite3.DatabaseError as exc:
                quarantine = self.state_path.with_name(
                    f"{self.state_path.name}.corrupt-{time.time_ns()}-{uuid.uuid4().hex}"
                )
                moved = False
                for suffix in ("", "-wal", "-shm", "-journal"):
                    source = Path(f"{self.state_path}{suffix}")
                    if not source.exists():
                        continue
                    os.replace(source, Path(f"{quarantine}{suffix}"))
                    moved = True
                if not moved:
                    raise
                directory_fd = os.open(self.state_path.parent, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
                logger.error(
                    "Quarantined corrupt validation lease database at %s: %s",
                    quarantine,
                    exc,
                )
                self._initialize_schema()
        finally:
            with contextlib.suppress(OSError):
                fcntl.flock(init_fd, fcntl.LOCK_UN)
            os.close(init_fd)

    def _initialize_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS waiters (
                    token TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    authority_generation TEXT NOT NULL,
                    priority INTEGER NOT NULL,
                    queued_at REAL NOT NULL,
                    requester_pid INTEGER NOT NULL,
                    requester_start_ticks INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS owners (
                    slot INTEGER PRIMARY KEY,
                    token TEXT UNIQUE NOT NULL,
                    kind TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    authority_generation TEXT NOT NULL,
                    priority INTEGER NOT NULL,
                    acquired_at REAL NOT NULL,
                    requester_pid INTEGER NOT NULL,
                    requester_start_ticks INTEGER NOT NULL,
                    child_pid INTEGER,
                    child_start_ticks INTEGER,
                    deadline_at REAL
                );
                CREATE TABLE IF NOT EXISTS project_turns (
                    project_id TEXT PRIMARY KEY,
                    last_grant INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS cancelled_owners (
                    kind TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    authority_generation TEXT NOT NULL,
                    cancelled_at REAL NOT NULL,
                    PRIMARY KEY (
                        kind, project_id, task_id, authority_generation
                    )
                );
                """
            )
            existing = connection.execute(
                "SELECT value FROM schema_meta WHERE key = 'version'"
            ).fetchone()
            if existing is not None and int(existing["value"]) != _SCHEMA_VERSION:
                raise ValidationLeaseError("unsupported validation lease schema version")
            connection.execute(
                "INSERT OR REPLACE INTO schema_meta(key, value) VALUES('version', ?)",
                (str(_SCHEMA_VERSION),),
            )
            connection.execute(
                "INSERT OR IGNORE INTO schema_meta(key, value) VALUES('grant_sequence', '0')"
            )
            configured = {
                "capacity": str(self.capacity),
                "aging_seconds": repr(self.aging_seconds),
            }
            active_count = int(
                connection.execute(
                    "SELECT (SELECT COUNT(*) FROM owners) + (SELECT COUNT(*) FROM waiters)"
                ).fetchone()[0]
            )
            for key, expected in configured.items():
                row = connection.execute(
                    "SELECT value FROM schema_meta WHERE key = ?", (key,)
                ).fetchone()
                if row is None:
                    connection.execute(
                        "INSERT INTO schema_meta(key, value) VALUES(?, ?)",
                        (key, expected),
                    )
                elif row["value"] != expected:
                    if active_count:
                        raise ValidationLeaseError(
                            f"validation lease {key} differs across live processes"
                        )
                    connection.execute(
                        "UPDATE schema_meta SET value = ? WHERE key = ?",
                        (expected, key),
                    )

    def _slot_path(self, slot: int) -> Path:
        return self._slot_dir / f"slot-{slot}.lock"

    def _try_lock_slots(self) -> dict[int, int]:
        available: dict[int, int] = {}
        for slot in range(self.capacity):
            fd = os.open(self._slot_path(slot), os.O_RDWR | os.O_CREAT, 0o600)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                os.close(fd)
            else:
                available[slot] = fd
        return available

    @staticmethod
    def _close_slot_locks(slot_fds: Iterable[int]) -> None:
        for fd in slot_fds:
            with contextlib.suppress(OSError):
                fcntl.flock(fd, fcntl.LOCK_UN)
            with contextlib.suppress(OSError):
                os.close(fd)

    def _terminate_expired_children(self) -> None:
        now = time.time()
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT slot, child_pid, child_start_ticks FROM owners
                   WHERE deadline_at IS NOT NULL AND deadline_at <= ?""",
                (now,),
            ).fetchall()
        for row in rows:
            pid = row["child_pid"]
            if pid is None:
                continue
            _terminate_exact_process_group(pid, row["child_start_ticks"])

    @staticmethod
    def _owner_alive(row: sqlite3.Row) -> bool:
        if _process_identity_alive(row["child_pid"], row["child_start_ticks"]):
            return True
        return _process_identity_alive(
            row["requester_pid"], row["requester_start_ticks"]
        )

    def _reconcile_locked(
        self,
        connection: sqlite3.Connection,
        available_slots: set[int],
    ) -> None:
        waiter_rows = connection.execute(
            "SELECT token, requester_pid, requester_start_ticks FROM waiters"
        ).fetchall()
        for row in waiter_rows:
            if not _process_identity_alive(
                row["requester_pid"], row["requester_start_ticks"]
            ):
                connection.execute("DELETE FROM waiters WHERE token = ?", (row["token"],))

        owner_rows = connection.execute("SELECT * FROM owners").fetchall()
        for row in owner_rows:
            slot = int(row["slot"])
            # Successfully taking the kernel slot proves that neither the
            # requester nor any descendant still owns the execution fence.
            # This is stronger than process identity and also repairs a stale
            # durable row after a transient release-persistence failure.
            if slot in available_slots:
                connection.execute("DELETE FROM owners WHERE slot = ?", (slot,))

    def _select_waiter(
        self,
        rows: list[sqlite3.Row],
        now: float,
        project_turns: dict[str, int],
    ) -> sqlite3.Row | None:
        if not rows:
            return None

        def sort_key(row: sqlite3.Row) -> tuple[int, int, float, str]:
            age_boost = int(max(now - float(row["queued_at"]), 0.0) / self.aging_seconds)
            effective_priority = int(row["priority"]) + age_boost
            return (
                -effective_priority,
                project_turns.get(str(row["project_id"]), -1),
                float(row["queued_at"]),
                str(row["token"]),
            )

        return min(rows, key=sort_key)

    def _try_acquire(self, token: str) -> ValidationLeaseHandle | None:
        self._terminate_expired_children()
        available = self._try_lock_slots()
        if not available:
            return None
        chosen_fd: int | None = None
        chosen_slot: int | None = None
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                self._reconcile_locked(connection, set(available))
                waiter = connection.execute(
                    "SELECT * FROM waiters WHERE token = ?", (token,)
                ).fetchone()
                if waiter is None:
                    connection.rollback()
                    return None
                if self._identity_cancelled_locked(connection, waiter):
                    connection.execute("DELETE FROM waiters WHERE token = ?", (token,))
                    connection.commit()
                    return None
                candidate = self._select_waiter(
                    connection.execute("SELECT * FROM waiters").fetchall(),
                    time.time(),
                    {
                        str(row["project_id"]): int(row["last_grant"])
                        for row in connection.execute(
                            "SELECT project_id, last_grant FROM project_turns"
                        )
                    },
                )
                if candidate is None or candidate["token"] != token:
                    connection.rollback()
                    return None
                occupied = {
                    int(row["slot"])
                    for row in connection.execute("SELECT slot FROM owners")
                }
                free_slots = sorted(set(available) - occupied)
                if not free_slots:
                    connection.rollback()
                    return None
                chosen_slot = free_slots[0]
                chosen_fd = available.pop(chosen_slot)
                now = time.time()
                connection.execute(
                    """INSERT INTO owners(
                           slot, token, kind, project_id, task_id,
                           authority_generation, priority, acquired_at,
                           requester_pid, requester_start_ticks
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        chosen_slot,
                        token,
                        waiter["kind"],
                        waiter["project_id"],
                        waiter["task_id"],
                        waiter["authority_generation"],
                        waiter["priority"],
                        now,
                        waiter["requester_pid"],
                        waiter["requester_start_ticks"],
                    ),
                )
                connection.execute("DELETE FROM waiters WHERE token = ?", (token,))
                sequence = int(
                    connection.execute(
                        "SELECT value FROM schema_meta WHERE key = 'grant_sequence'"
                    ).fetchone()["value"]
                ) + 1
                connection.execute(
                    "UPDATE schema_meta SET value = ? WHERE key = 'grant_sequence'",
                    (str(sequence),),
                )
                connection.execute(
                    """INSERT INTO project_turns(project_id, last_grant)
                       VALUES(?, ?) ON CONFLICT(project_id) DO UPDATE SET
                       last_grant = excluded.last_grant""",
                    (waiter["project_id"], sequence),
                )
                connection.commit()
            assert chosen_slot is not None and chosen_fd is not None
            return ValidationLeaseHandle(
                self,
                token=token,
                slot=chosen_slot,
                lock_fd=chosen_fd,
            )
        finally:
            self._close_slot_locks(available.values())

    def acquire(
        self,
        owner: ValidationLeaseOwner,
        *,
        is_cancelled: Callable[[], bool] | None = None,
        on_wait: Callable[[], object] | None = None,
        wait_timeout_seconds: float | None = None,
    ) -> ValidationLeaseHandle:
        """Queue durably and wait without consuming command runtime timeout."""

        token = uuid.uuid4().hex
        requester_pid = os.getpid()
        requester_start_ticks = _process_start_ticks(requester_pid)
        if requester_start_ticks is None:
            raise ValidationLeaseError("cannot fence validation requester identity")
        queued_at = time.time()
        queued_monotonic = time.monotonic()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._prune_cancelled_locked(connection)
            if self._identity_cancelled_locked(connection, owner):
                raise ValidationLeaseCancelled(
                    "validation authority was withdrawn before capacity acquisition"
                )
            connection.execute(
                """INSERT INTO waiters(
                       token, kind, project_id, task_id, authority_generation,
                       priority, queued_at, requester_pid, requester_start_ticks
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    token,
                    owner.kind,
                    owner.project_id,
                    owner.task_id,
                    owner.authority_generation,
                    owner.priority,
                    queued_at,
                    requester_pid,
                    requester_start_ticks,
                ),
            )
        try:
            while True:
                if is_cancelled is not None:
                    try:
                        cancelled = bool(is_cancelled())
                    except Exception:
                        cancelled = True
                    if cancelled:
                        raise ValidationLeaseCancelled(
                            "validation authority withdrawn while waiting for capacity"
                        )
                if (
                    wait_timeout_seconds is not None
                    and time.monotonic() - queued_monotonic
                    >= max(float(wait_timeout_seconds), 0.0)
                ):
                    raise ValidationLeaseCancelled(
                        "validation capacity wait timed out"
                    )
                handle = self._try_acquire(token)
                if handle is not None:
                    if self._owner_cancelled(owner):
                        handle.release()
                        raise ValidationLeaseCancelled(
                            "validation authority withdrawn while acquiring capacity"
                        )
                    return handle
                with self._connect() as connection:
                    still_queued = connection.execute(
                        "SELECT 1 FROM waiters WHERE token = ?",
                        (token,),
                    ).fetchone()
                if still_queued is None:
                    raise ValidationLeaseCancelled(
                        "validation authority withdrawn while waiting for capacity"
                    )
                if on_wait is not None:
                    try:
                        on_wait()
                    except Exception:  # noqa: BLE001 - telemetry is advisory
                        logger.debug(
                            "Validation capacity wait observer failed",
                            exc_info=True,
                        )
                time.sleep(self.poll_seconds)
        except BaseException:
            with self._connect() as connection:
                connection.execute("DELETE FROM waiters WHERE token = ?", (token,))
            raise

    def _attach_process(
        self,
        token: str,
        *,
        pid: int,
        start_ticks: int,
        deadline_at: float,
    ) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                """UPDATE owners SET child_pid = ?, child_start_ticks = ?,
                       deadline_at = ? WHERE token = ?
                       AND NOT EXISTS (
                           SELECT 1 FROM cancelled_owners AS cancelled
                           WHERE cancelled.kind = owners.kind
                             AND cancelled.project_id = owners.project_id
                             AND cancelled.task_id = owners.task_id
                             AND cancelled.authority_generation =
                                 owners.authority_generation
                       )""",
                (pid, start_ticks, deadline_at, token),
            )
            if cursor.rowcount != 1:
                raise ValidationLeaseCancelled(
                    "validation authority was withdrawn before process attachment"
                )

    @staticmethod
    def _identity_values(owner: object) -> tuple[str, str, str, str]:
        def value(name: str) -> str:
            if isinstance(owner, sqlite3.Row):
                return str(owner[name])
            return str(getattr(owner, name))

        return (
            value("kind"),
            value("project_id"),
            value("task_id"),
            value("authority_generation"),
        )

    def _identity_cancelled_locked(
        self,
        connection: sqlite3.Connection,
        owner: object,
    ) -> bool:
        return connection.execute(
            """SELECT 1 FROM cancelled_owners
               WHERE kind = ? AND project_id = ? AND task_id = ?
                 AND authority_generation = ?""",
            self._identity_values(owner),
        ).fetchone() is not None

    def _owner_cancelled(self, owner: ValidationLeaseOwner) -> bool:
        with self._connect() as connection:
            return self._identity_cancelled_locked(connection, owner)

    @staticmethod
    def _prune_cancelled_locked(connection: sqlite3.Connection) -> None:
        connection.execute(
            """DELETE FROM cancelled_owners AS cancelled
               WHERE cancelled.cancelled_at < ?
                 AND NOT EXISTS (
                     SELECT 1 FROM owners
                     WHERE owners.kind = cancelled.kind
                       AND owners.project_id = cancelled.project_id
                       AND owners.task_id = cancelled.task_id
                       AND owners.authority_generation =
                           cancelled.authority_generation
                 )
                 AND NOT EXISTS (
                     SELECT 1 FROM waiters
                     WHERE waiters.kind = cancelled.kind
                       AND waiters.project_id = cancelled.project_id
                       AND waiters.task_id = cancelled.task_id
                       AND waiters.authority_generation =
                           cancelled.authority_generation
                 )""",
            (time.time() - _CANCELLED_OWNER_RETENTION_SECONDS,),
        )
        connection.execute(
            """DELETE FROM cancelled_owners
               WHERE rowid IN (
                   SELECT cancelled.rowid FROM cancelled_owners AS cancelled
                   WHERE NOT EXISTS (
                       SELECT 1 FROM owners
                       WHERE owners.kind = cancelled.kind
                         AND owners.project_id = cancelled.project_id
                         AND owners.task_id = cancelled.task_id
                         AND owners.authority_generation =
                             cancelled.authority_generation
                   )
                     AND NOT EXISTS (
                       SELECT 1 FROM waiters
                       WHERE waiters.kind = cancelled.kind
                         AND waiters.project_id = cancelled.project_id
                         AND waiters.task_id = cancelled.task_id
                         AND waiters.authority_generation =
                             cancelled.authority_generation
                   )
                   ORDER BY cancelled.cancelled_at DESC
                   LIMIT -1 OFFSET ?
               )""",
            (_CANCELLED_OWNER_LIMIT,),
        )

    def _release(self, token: str, slot: int, lock_fd: int) -> bool:
        """Drop a fence without letting metadata errors leak capacity.

        Close the requester's descriptor first.  If a background descendant
        inherited it, the immediate non-blocking probe will fail and the
        durable owner row deliberately remains visible until the descendant
        exits.  Otherwise the probe itself is proof that deleting the row is
        safe.  A transient SQLite error cannot leak the raw descriptor or
        override the completed command result; later status/acquire
        reconciliation repairs the stale row from the same kernel proof.
        """

        # Do not call LOCK_UN here.  The descriptor was deliberately inherited
        # by the attached validation tree; closing our copy preserves the
        # flock until the last background descendant exits.
        with contextlib.suppress(OSError):
            os.close(lock_fd)
        available = self._try_lock_slots()
        try:
            if slot not in available:
                return False
            try:
                with self._connect() as connection:
                    cursor = connection.execute(
                        "DELETE FROM owners WHERE token = ?", (token,)
                    )
                    return cursor.rowcount == 1
            except (OSError, sqlite3.Error):
                logger.exception(
                    "Validation lease metadata release will be reconciled "
                    "from the kernel fence token=%s slot=%s",
                    token,
                    slot,
                )
                return False
        finally:
            self._close_slot_locks(available.values())

    def cancel_owner(self, owner: ValidationLeaseOwner) -> int:
        """Cancel matching queued/running native validation work.

        Queue waiters observe their session cancellation callback and remove
        their own row.  Attached commands are process-group leaders, so this
        method can terminate only the exact durable owner generation without
        touching unrelated validation work.
        """

        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._prune_cancelled_locked(connection)
            connection.execute(
                """INSERT INTO cancelled_owners(
                       kind, project_id, task_id, authority_generation,
                       cancelled_at
                   ) VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(
                       kind, project_id, task_id, authority_generation
                   ) DO UPDATE SET cancelled_at = excluded.cancelled_at""",
                (*self._identity_values(owner), time.time()),
            )
            rows = connection.execute(
                """SELECT slot, child_pid, child_start_ticks FROM owners
                   WHERE kind = ? AND project_id = ? AND task_id = ?
                     AND authority_generation = ?""",
                (
                    owner.kind,
                    owner.project_id,
                    owner.task_id,
                    owner.authority_generation,
                ),
            ).fetchall()
            cancelled_waiters = connection.execute(
                """DELETE FROM waiters
                   WHERE kind = ? AND project_id = ? AND task_id = ?
                     AND authority_generation = ?""",
                (
                    owner.kind,
                    owner.project_id,
                    owner.task_id,
                    owner.authority_generation,
                ),
            ).rowcount
        for row in rows:
            pid = row["child_pid"]
            if pid is None:
                continue
            _terminate_exact_process_group(pid, row["child_start_ticks"])
        return len(rows) + int(cancelled_waiters or 0)

    def cancel_exact_owner_process(
        self,
        owner: ValidationLeaseOwner,
        *,
        requester_pid: int,
        requester_start_ticks: int,
        child_pid: int,
        child_start_ticks: int,
    ) -> bool:
        """Atomically cancel one health-advertised attached owner process.

        Recovery requests originate from a status snapshot that can become
        stale before the operator posts it.  Select and fence the complete
        process identity under the same write transaction that records the
        generation cancellation.  Requiring exactly one row for the owner
        generation prevents both an ABA replacement and an overlapping
        same-generation process from being retired by stale evidence.
        """

        expected_identity = (
            int(requester_pid),
            int(requester_start_ticks),
            int(child_pid),
            int(child_start_ticks),
        )
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._prune_cancelled_locked(connection)
            rows = connection.execute(
                """SELECT requester_pid, requester_start_ticks,
                          child_pid, child_start_ticks
                   FROM owners
                   WHERE kind = ? AND project_id = ? AND task_id = ?
                     AND authority_generation = ?""",
                self._identity_values(owner),
            ).fetchall()
            if len(rows) != 1:
                connection.rollback()
                return False
            row = rows[0]
            actual_identity = (
                int(row["requester_pid"]),
                int(row["requester_start_ticks"]),
                int(row["child_pid"]) if row["child_pid"] is not None else 0,
                (
                    int(row["child_start_ticks"])
                    if row["child_start_ticks"] is not None
                    else 0
                ),
            )
            if actual_identity != expected_identity:
                connection.rollback()
                return False
            connection.execute(
                """INSERT INTO cancelled_owners(
                       kind, project_id, task_id, authority_generation,
                       cancelled_at
                   ) VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(
                       kind, project_id, task_id, authority_generation
                   ) DO UPDATE SET cancelled_at = excluded.cancelled_at""",
                (*self._identity_values(owner), time.time()),
            )
            connection.commit()
        _terminate_exact_process_group(child_pid, child_start_ticks)
        return True

    def status(self) -> ValidationLeaseStatus:
        """Read fresh durable state and remove provably dead records."""

        self._terminate_expired_children()
        available = self._try_lock_slots()
        try:
            with self._connect() as connection:
                connection.execute("BEGIN")
                owner_rows = connection.execute(
                    "SELECT * FROM owners ORDER BY slot"
                ).fetchall()
                waiter_rows = connection.execute(
                    "SELECT * FROM waiters ORDER BY queued_at, token"
                ).fetchall()
                connection.commit()
            needs_reconciliation = any(
                not _process_identity_alive(
                    row["requester_pid"], row["requester_start_ticks"]
                )
                for row in waiter_rows
            ) or any(
                int(row["slot"]) in available
                for row in owner_rows
            )
            if needs_reconciliation:
                with self._connect() as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    self._reconcile_locked(connection, set(available))
                    owner_rows = connection.execute(
                        "SELECT * FROM owners ORDER BY slot"
                    ).fetchall()
                    waiter_rows = connection.execute(
                        "SELECT * FROM waiters ORDER BY queued_at, token"
                    ).fetchall()
                    connection.commit()
        finally:
            self._close_slot_locks(available.values())
        now = time.time()

        def owner_dict(row: sqlite3.Row) -> dict[str, object]:
            owner = {
                "slot": int(row["slot"]),
                "kind": str(row["kind"]),
                "project_id": str(row["project_id"]),
                "task_id": str(row["task_id"]),
                "authority_generation": str(row["authority_generation"]),
                "age_seconds": max(now - float(row["acquired_at"]), 0.0),
                "requester_pid": int(row["requester_pid"]),
                "requester_start_ticks": int(row["requester_start_ticks"]),
                "child_pid": (
                    int(row["child_pid"]) if row["child_pid"] is not None else None
                ),
                "child_start_ticks": (
                    int(row["child_start_ticks"])
                    if row["child_start_ticks"] is not None
                    else None
                ),
                "deadline_at": row["deadline_at"],
            }
            if (
                row["child_pid"] is not None
                and row["child_start_ticks"] is not None
                and int(row["requester_pid"]) == int(row["child_pid"])
                and int(row["requester_start_ticks"])
                == int(row["child_start_ticks"])
                and _legacy_provider_bootstrap_process(
                    row["child_pid"],
                    row["child_start_ticks"],
                    self._trusted_codex_bootstrap_identity,
                    self._trusted_provider_parent_identity,
                )
            ):
                owner["process_role"] = "legacy_provider_bootstrap"
                if str(row["kind"]) == VALIDATION_KIND_WORKER:
                    expected_owner = {
                        "kind": str(row["kind"]),
                        "project_id": str(row["project_id"]),
                        "task_id": str(row["task_id"]),
                        "authority_generation": str(
                            row["authority_generation"]
                        ),
                        "requester_pid": int(row["requester_pid"]),
                        "requester_start_ticks": int(
                            row["requester_start_ticks"]
                        ),
                        "child_pid": int(row["child_pid"]),
                        "child_start_ticks": int(row["child_start_ticks"]),
                    }
                    owner.update(
                        {
                            "recovery_action": "claim_task_directly",
                            "recovery_preserves_worktree": True,
                            "recovery_request": {
                                "method": "POST",
                                "endpoint": (
                                    "/api/v1/projects/"
                                    f"{row['project_id']}/tasks/"
                                    f"{row['task_id']}/owner-claim"
                                ),
                                "body": {
                                    "expected_validation_owner": expected_owner,
                                },
                            },
                        }
                    )
            return owner

        def waiter_dict(row: sqlite3.Row) -> dict[str, object]:
            return {
                "kind": str(row["kind"]),
                "project_id": str(row["project_id"]),
                "task_id": str(row["task_id"]),
                "authority_generation": str(row["authority_generation"]),
                "age_seconds": max(now - float(row["queued_at"]), 0.0),
                "priority": int(row["priority"]),
            }

        oldest_age = max(
            (now - float(row["queued_at"]) for row in waiter_rows),
            default=0.0,
        )
        return ValidationLeaseStatus(
            capacity=self.capacity,
            owner_count=len(owner_rows),
            waiter_count=len(waiter_rows),
            oldest_waiter_age_seconds=max(oldest_age, 0.0),
            owners=tuple(owner_dict(row) for row in owner_rows),
            waiters=tuple(waiter_dict(row) for row in waiter_rows),
        )
