"""Durable host capacity for heavyweight validation commands.

The coordination database is the durable source of queue and ownership
metadata.  A POSIX ``flock`` on each configured capacity slot is the execution
fence: it is inherited by the validation subprocess, so loss of the service
process cannot make a still-running command disappear from capacity.
"""

from __future__ import annotations

import contextlib
import logging
import os
import shlex
import signal
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

try:  # pragma: no cover - the service runtime is POSIX-only today
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]


logger = logging.getLogger(__name__)

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
        return {
            "capacity": self.capacity,
            "available_capacity": self.available_capacity,
            "owner_count": self.owner_count,
            "waiter_count": self.waiter_count,
            "oldest_waiter_age_seconds": self.oldest_waiter_age_seconds,
            "owners": list(self.owners),
            "waiters": list(self.waiters),
            # A normal capacity wait is activity, not an actionable warning.
            "status": "busy" if self.waiter_count or self.owner_count else "idle",
        }


def _process_start_ticks(pid: int) -> int | None:
    """Return Linux process start ticks, which fence PID reuse."""

    try:
        raw = Path(f"/proc/{int(pid)}/stat").read_text(encoding="utf-8")
        return int(raw[raw.rfind(")") + 2 :].split()[19])
    except (OSError, ValueError, IndexError):
        return None


def _process_identity_alive(pid: object, start_ticks: object) -> bool:
    try:
        expected = int(start_ticks)
        current = _process_start_ticks(int(pid))
    except (TypeError, ValueError):
        return False
    return current is not None and current == expected


def _shell_segments(command: str) -> list[list[str]]:
    """Tokenize top-level shell commands without executing shell syntax."""

    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()")
    lexer.whitespace_split = True
    lexer.commenters = ""
    tokens = list(lexer)
    segments: list[list[str]] = []
    current: list[str] = []
    for token in tokens:
        if token and all(character in ";&|()" for character in token):
            if current:
                segments.append(current)
                current = []
        else:
            current.append(token)
    if current:
        segments.append(current)
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


def _make_segment_is_heavy(tokens: list[str]) -> bool:
    command_tokens = _command_tokens(tokens)
    if not command_tokens or os.path.basename(command_tokens[0]) != "make":
        return False
    targets: list[str] = []
    skip_next = False
    for argument in command_tokens[1:]:
        if skip_next:
            skip_next = False
            continue
        if argument == "--":
            continue
        if argument in {"-C", "--directory", "-f", "--file", "-I", "--include-dir"}:
            skip_next = True
            continue
        if argument.startswith("-") or "=" in argument:
            continue
        targets.append(argument)
    if not targets and any(
        argument in {"-h", "--help", "-v", "--version"}
        for argument in command_tokens[1:]
    ):
        return False
    return not targets or any(
        target not in {"help", "check-secrets"} for target in targets
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


def _pytest_segment_is_heavy(tokens: list[str]) -> bool:
    command_tokens = _command_tokens(tokens)
    invocation = _pytest_invocation(command_tokens)
    if invocation is None:
        return False
    _, first_argument = invocation
    arguments = command_tokens[first_argument:]
    if any(argument in {"--help", "-h", "--version"} for argument in arguments):
        return False
    positionals: list[str] = []
    skip_next = False
    options_with_values = {
        "-k",
        "-m",
        "-c",
        "--confcutdir",
        "--rootdir",
        "--basetemp",
        "--maxfail",
        "--tb",
        "--capture",
        "--log-level",
    }
    for argument in arguments:
        if skip_next:
            skip_next = False
            continue
        if argument in options_with_values:
            skip_next = True
            continue
        if argument.startswith("-"):
            continue
        positionals.append(argument)

    # No selector, a directory selector, or an opaque selector may cover the
    # full suite.  Only explicit Python test files/node ids are demonstrably
    # focused and may bypass the host lease.
    if not positionals:
        return True
    if not all("::" in item or item.endswith(".py") for item in positionals):
        return True
    if any(any(marker in item for marker in "*?[]{}") for item in positionals):
        # Classification happens before the shell expands selectors.  A
        # syntactically single ``tests/test_*.py`` token can therefore become
        # the complete test tree at execution time and must fail closed.
        return True
    # A handful of broad subsystem files caused the production collision that
    # introduced this lane.  Syntax alone cannot prove file size, so bypass is
    # deliberately narrow: one explicit file or node.  Multiple files are a
    # suite, even when each positional happens to end in ``.py``.
    return len(positionals) > 1


def _unittest_segment_is_heavy(tokens: list[str]) -> bool:
    """Return whether one segment invokes an unbounded unittest run."""

    command_tokens = _command_tokens(tokens)
    if not command_tokens:
        return False
    python_executable = os.path.basename(command_tokens[0])
    if not (
        python_executable == "python"
        or (
            python_executable.startswith("python")
            and python_executable[6:].replace(".", "").isdigit()
        )
    ):
        return False
    try:
        module_index = command_tokens.index("-m", 1)
    except ValueError:
        return False
    if (
        module_index + 1 >= len(command_tokens)
        or command_tokens[module_index + 1] != "unittest"
    ):
        return False
    arguments = command_tokens[module_index + 2 :]
    if any(argument in {"--help", "-h", "--version"} for argument in arguments):
        return False
    positionals = [argument for argument in arguments if not argument.startswith("-")]
    if not positionals or positionals[0] == "discover":
        return True
    if any(any(marker in item for marker in "*?[]{}") for item in positionals):
        return True
    return len(positionals) > 1


def _npm_segment_is_heavy(tokens: list[str]) -> bool:
    """Return whether one segment invokes an npm/pnpm/yarn test script."""

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


def _cargo_segment_is_heavy(tokens: list[str]) -> bool:
    """Return whether one segment invokes Cargo's test runner."""

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


def is_heavyweight_validation_command(command: str) -> bool:
    """Classify auditor shell input, with heavyweight evidence winning.

    Non-test inspection commands bypass the lease.  Once a command invokes a
    known test runner, ambiguous syntax is treated as heavyweight.  Every
    top-level shell segment is examined, preventing a light prefix/suffix from
    hiding a full suite (for example ``echo ready; make test``).
    """

    raw = str(command or "").strip()
    if not raw:
        return False
    try:
        segments = _shell_segments(raw)
    except ValueError:
        lowered = raw.casefold()
        return any(
            marker in lowered
            for marker in ("pytest", "py.test", "make test", "npm test", "cargo test")
        )
    for tokens in segments:
        if (
            _make_segment_is_heavy(tokens)
            or _pytest_segment_is_heavy(tokens)
            or _unittest_segment_is_heavy(tokens)
            or _npm_segment_is_heavy(tokens)
            or _cargo_segment_is_heavy(tokens)
        ):
            return True
        command_tokens = _command_tokens(tokens)
        nested_command = _nested_shell_command(command_tokens)
        if nested_command is not None and is_heavyweight_validation_command(
            nested_command
        ):
            return True
        if command_tokens and os.path.basename(command_tokens[0]) in {"tox", "nox"}:
            return True
    return False


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
            removed = self._manager._release(self.token, self._lock_fd)
            self._released = True
            return removed

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
        self._slot_dir = self.state_path.with_suffix(self.state_path.suffix + ".locks")
        self._slot_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._slot_dir.chmod(0o700)
        self._initialize()
        self.state_path.chmod(0o600)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.state_path, timeout=10.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

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
                os.set_inheritable(fd, True)
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
                """SELECT child_pid, child_start_ticks FROM owners
                   WHERE deadline_at IS NOT NULL AND deadline_at <= ?""",
                (now,),
            ).fetchall()
        for row in rows:
            pid = row["child_pid"]
            if not _process_identity_alive(pid, row["child_start_ticks"]):
                continue
            try:
                os.killpg(int(pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                continue
            deadline = time.monotonic() + 0.25
            while (
                time.monotonic() < deadline
                and _process_identity_alive(pid, row["child_start_ticks"])
            ):
                time.sleep(0.01)
            if _process_identity_alive(pid, row["child_start_ticks"]):
                with contextlib.suppress(ProcessLookupError, PermissionError):
                    os.killpg(int(pid), signal.SIGKILL)

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
            # A live, identity-matched owner is authoritative.  A dead owner
            # may be removed only while this process holds the kernel slot,
            # proving neither it nor a descendant retained the execution lock.
            if slot in available_slots and not self._owner_alive(row):
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
                    return handle
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
                       deadline_at = ? WHERE token = ?""",
                (pid, start_ticks, deadline_at, token),
            )
            if cursor.rowcount != 1:
                raise ValidationLeaseError("validation lease ownership was lost")

    def _release(self, token: str, lock_fd: int) -> bool:
        # Delete durable authority before dropping the kernel fence. If the
        # database is temporarily unavailable the handle remains retryable and
        # capacity cannot be exposed while a stale live owner row remains.
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM owners WHERE token = ?", (token,)
            )
            removed = cursor.rowcount == 1
        self._close_slot_locks((lock_fd,))
        return removed

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
                int(row["slot"]) in available and not self._owner_alive(row)
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
            return {
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
