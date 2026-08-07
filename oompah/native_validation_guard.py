"""Command-scoped validation leases for native agent shell surfaces.

Native Codex sessions execute commands below the SDK-owned CLI process, so
the service cannot pass a lease descriptor directly to those grandchildren.
This module installs small PATH shims for known validation launchers.  A shim
classifies the *actual command invocation*, acquires capacity only for a heavy
invocation, attaches the durable record to its own exact process identity,
and then ``exec``s the real executable while both it and an operator
supervisor retain the flock descriptor.

The resulting kernel ownership is independent of the oompah service.  The
descriptor follows the heavyweight process tree, including descendants that
detach from the original process group, so capacity cannot be reused while
such work remains alive.  A tiny supervisor survives service loss and safely
terminates the exact original process-group generation when authority ends.
"""

from __future__ import annotations

import array
import contextlib
import ctypes
import errno
import fcntl
import hashlib
import hmac
import json
import logging
import os
import pwd
import secrets
import select
import shlex
import shutil
import socket
import stat
import struct
import subprocess
import sys
import tempfile
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Mapping

from oompah.validation_resource_lease import (
    ValidationCommandClassification,
    ValidationLeaseOwner,
    ValidationResourceLease,
    _is_dynamic_loader_environment_name,
    _pidfd_open,
    _terminate_exact_process_group,
    classify_validation_command,
    is_heavyweight_validation_command,
)


logger = logging.getLogger(__name__)


_CONFIG_NAME = "validation-guard.json"
_GUARD_ENV = "OOMPAH_NATIVE_VALIDATION_GUARD"
_BASH_ENV_NAME = "validation-guard-bash-env"
_BASH_REENTRY_NAME = "validation-guard-bash-reentry"
_NATIVE_HOME_NAME = "validation-command-home"
_BROKER_SOCKET_NAME = "validation-lease.sock"
_BROKER_SOCKET_TYPE = getattr(socket, "SOCK_SEQPACKET", socket.SOCK_STREAM)
_CANCELLATION_NAME = "cancelled"
_BASH_ARGV0_ENV = "OOMPAH_NATIVE_VALIDATION_BASH_ARGV0"
_BOUNDARY_GROUP_ENV = "OOMPAH_NATIVE_VALIDATION_BOUNDARY_GROUP"
_CAPABILITY_FD_ENV = "OOMPAH_NATIVE_VALIDATION_CAPABILITY_FD"
_VALIDATION_MODE_ENV = "OOMPAH_VALIDATION_MODE"
_VALIDATION_JUSTIFICATION_ENV = "OOMPAH_VALIDATION_JUSTIFICATION"
NATIVE_VALIDATION_DISTINCT_MODE_INSTRUCTION = (
    "For a task-required full-suite mode that is genuinely distinct from the "
    "reused exact gate, invoke the native shell command with both structured "
    "fields as leading assignments: OOMPAH_VALIDATION_MODE="
    "task_required_distinct OOMPAH_VALIDATION_JUSTIFICATION='<specific reason>' "
    "<command>. While the supplied passing authority remains current, the exact "
    "configured gate is denied even with those fields."
)
_PROVIDER_LAUNCHER_NAME = "oompah-validation-provider"
_SUPERVISOR_LAUNCHER_NAME = "oompah-validation-supervisor"
_SUPERVISOR_READY = b"READY\n"
_SUPERVISOR_UNSUPPORTED = b"UNSUPPORTED\n"
_SUPERVISOR_IDENTITY_LOST = b"IDENTITY-LOST\n"
_SUPERVISOR_TRANSPORT_FAILURE = b"TRANSPORT-FAILURE\n"
_BROKER_DENIAL_MESSAGES = {
    b"DENIED AUTHORITY\n": "native validation authority was withdrawn",
    b"DENIED POLICY\n": "native validation lease broker denied execution",
    b"DENIED TRANSPORT\n": "native validation lease broker is unavailable",
    b"DENIED UNSUPPORTED\n": "native validation pidfd supervision is unavailable",
    b"DENIED IDENTITY\n": "native validation supervised peer changed identity",
}
# Python builds may omit Linux's memfd/seal wrappers even when the running
# libc and kernel provide them.  These values are part of Linux's stable UAPI
# (linux/memfd.h and linux/fcntl.h), not implementation-private CPython data.
_LINUX_MFD_CLOEXEC = 0x0001
_LINUX_MFD_ALLOW_SEALING = 0x0002
_LINUX_F_ADD_SEALS = 1033
_LINUX_F_GET_SEALS = 1034
_LINUX_F_SEAL_SEAL = 0x0001
_LINUX_F_SEAL_SHRINK = 0x0002
_LINUX_F_SEAL_GROW = 0x0004
_LINUX_F_SEAL_WRITE = 0x0008
_REQUIRED_CAPABILITY_SEALS = (
    _LINUX_F_SEAL_SEAL
    | _LINUX_F_SEAL_SHRINK
    | _LINUX_F_SEAL_GROW
    | _LINUX_F_SEAL_WRITE
)
_UNTRUSTED_SHELL_STARTUP_ENV_NAMES = frozenset(
    {
        "BASHOPTS",
        "BASH_ENV",
        "BASH_XTRACEFD",
        "ENV",
        "PROMPT_COMMAND",
        "PS4",
        "SHELLOPTS",
        "ZDOTDIR",
    }
)
_WRAPPED_COMMANDS = frozenset(
    {
        "bash",
        "cargo",
        "dash",
        "make",
        "node",
        "nox",
        "npm",
        "pnpm",
        "py.test",
        "pytest",
        "perl",
        "rg",
        "ruby",
        "sh",
        "tox",
        "uv",
        "yarn",
        "zsh",
    }
)

_BROKER_REGISTRY: dict[Path, "_NativeValidationLeaseBroker"] = {}
_BROKER_REGISTRY_LOCK = threading.Lock()
_OPAQUE_PROCESS_BASELINE_LOCK = threading.Lock()
_OPAQUE_PROCESS_BASELINE_OWNER_PID: int | None = None
_OPAQUE_PROCESS_BASELINE_CACHE: tuple[tuple[int, int], ...] | None = None


def _reset_opaque_process_baseline_after_fork() -> None:
    """Discard parent synchronization state and baselines in a forked child."""

    global _OPAQUE_PROCESS_BASELINE_LOCK
    global _OPAQUE_PROCESS_BASELINE_OWNER_PID
    global _OPAQUE_PROCESS_BASELINE_CACHE
    _OPAQUE_PROCESS_BASELINE_LOCK = threading.Lock()
    _OPAQUE_PROCESS_BASELINE_OWNER_PID = None
    _OPAQUE_PROCESS_BASELINE_CACHE = None


if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_reset_opaque_process_baseline_after_fork)


def _broker_socket_path(
    root: Path,
    requested_path: str | os.PathLike[str] | None,
) -> Path:
    """Resolve a broker socket without weakening filesystem access controls.

    The normal per-guard socket is preferred.  Deep task roots can exceed the
    Unix-domain path limit, in which case the Codex runtime creates a random
    child below its short, operator-owned socket directory and passes it here.
    Do not silently fall back to an abstract socket: an abstract name is not
    protected by the guard directory's filesystem permissions and may also be
    unavailable across a sandbox namespace boundary.
    """

    candidate = root / _BROKER_SOCKET_NAME if requested_path is None else Path(
        requested_path
    )
    if not candidate.is_absolute() or candidate.name != _BROKER_SOCKET_NAME:
        raise RuntimeError("native validation broker socket path is invalid")
    if len(os.fsencode(str(candidate))) >= 100:
        raise RuntimeError("native validation broker socket path is too long")
    if requested_path is None and candidate.parent != root:
        raise RuntimeError("native validation broker socket escaped guard root")
    return candidate


def _operator_broker_socket_parent() -> Path:
    """Return the raw passwd-home-derived socket parent independently of HOME.

    Worker and test sandboxes intentionally replace ``HOME``. Resolving the
    account home from the effective UID keeps this endpoint operator-owned and
    short instead of moving it below a deep task path. Keep the path unresolved
    so callers can reject symlinks instead of erasing their evidence.
    """

    operator_home = Path(pwd.getpwuid(os.geteuid()).pw_dir)
    if (
        not operator_home.is_absolute()
        or Path(os.path.normpath(str(operator_home))) != operator_home
    ):
        raise RuntimeError("operator account home path is unsafe")
    return operator_home / ".oompah" / "native-validation-sockets"


def _validate_trusted_directory(
    path: Path,
    *,
    operator_owned: bool,
    private: bool = False,
) -> os.stat_result:
    """Validate one path component without following a symlink."""

    try:
        info = path.lstat()
    except OSError as exc:
        raise RuntimeError(f"native validation directory is unavailable: {path}") from exc
    mode = stat.S_IMODE(info.st_mode)
    expected_owners = {os.geteuid()} if operator_owned else {0, os.geteuid()}
    if (
        stat.S_ISLNK(info.st_mode)
        or not stat.S_ISDIR(info.st_mode)
        or int(info.st_uid) not in expected_owners
        or mode & (stat.S_IWGRP | stat.S_IWOTH)
        or (private and mode != 0o700)
    ):
        raise RuntimeError(f"native validation directory is unsafe: {path}")
    return info


def _operator_home_path() -> Path:
    """Return and verify the raw effective-account home path and its ancestors."""

    socket_parent = _operator_broker_socket_parent()
    operator_home = socket_parent.parent.parent
    current = Path(operator_home.anchor)
    for part in operator_home.parts[1:]:
        current /= part
        _validate_trusted_directory(
            current,
            operator_owned=current == operator_home,
        )
    _validate_trusted_directory(operator_home, operator_owned=True)
    return operator_home


def _tighten_private_operator_directory(path: Path) -> None:
    """Set 0700 through a no-follow descriptor, never through a broad path."""

    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise RuntimeError(f"native validation directory is unsafe: {path}") from exc
    try:
        info = os.fstat(descriptor)
        if (
            not stat.S_ISDIR(info.st_mode)
            or int(info.st_uid) != os.geteuid()
        ):
            raise RuntimeError(f"native validation directory is unsafe: {path}")
        os.fchmod(descriptor, 0o700)
        if stat.S_IMODE(os.fstat(descriptor).st_mode) != 0o700:
            raise RuntimeError(
                f"native validation directory permissions are unsafe: {path}"
            )
    finally:
        os.close(descriptor)


def _prepare_operator_broker_socket_parent() -> Path:
    """Create only dedicated operator directories and return a verified parent."""

    operator_home = _operator_home_path()
    current = operator_home
    for name in (".oompah", "native-validation-sockets"):
        child = current / name
        _validate_trusted_directory(current, operator_owned=True)
        try:
            child.mkdir(mode=0o700)
        except FileExistsError:
            pass
        _tighten_private_operator_directory(child)
        _validate_trusted_directory(child, operator_owned=True, private=True)
        current = child
    return current


def _verified_operator_broker_socket_parent() -> Path:
    """Revalidate the complete existing socket boundary without creating it."""

    operator_home = _operator_home_path()
    oompah_root = operator_home / ".oompah"
    socket_parent = _operator_broker_socket_parent()
    _validate_trusted_directory(
        oompah_root,
        operator_owned=True,
        private=True,
    )
    _validate_trusted_directory(
        socket_parent,
        operator_owned=True,
        private=True,
    )
    return socket_parent


def _proc_entry_start_ticks(entry: Path) -> int | None:
    """Return one proc entry's immutable process-generation identifier."""

    try:
        raw = (entry / "stat").read_text(encoding="utf-8")
        return int(raw[raw.rfind(")") + 2 :].split()[19])
    except (OSError, ValueError, IndexError):
        return None


def _scan_opaque_same_user_processes(
    proc_root: Path,
) -> tuple[tuple[int, int], ...]:
    """Return exact generations of same-user processes hidden by procfs."""

    identities: set[tuple[int, int]] = set()
    try:
        entries = tuple(proc_root.iterdir())
    except OSError:
        return ()
    for entry in entries:
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        try:
            if entry.stat().st_uid != os.geteuid():
                continue
            (entry / "environ").read_bytes()
            (entry / "cmdline").read_bytes()
            for link_name in ("cwd", "exe", "root"):
                os.readlink(entry / link_name)
            tuple((entry / "fd").iterdir())
        except FileNotFoundError:
            continue
        except PermissionError:
            start_ticks = _proc_entry_start_ticks(entry)
            if start_ticks is not None:
                identities.add((int(entry.name), start_ticks))
        except OSError:
            continue
    return tuple(sorted(identities))


def _opaque_same_user_process_baseline(
    proc_root: Path = Path("/proc"),
) -> tuple[tuple[int, int], ...]:
    """Snapshot pre-existing same-user processes hidden by proc permissions.

    Such a process cannot have inherited a guard that does not exist yet.
    Recording its exact PID generation keeps unrelated long-lived sessions
    from retaining every future guard, while any process that becomes opaque
    after installation remains an unknown reference and therefore fails
    closed during retirement.

    The real procfs snapshot is immutable for this process lifetime. Repeated
    guard installations therefore cannot absorb a process that became opaque
    after the first guard was installed, and avoid repeatedly walking every
    same-user descriptor. A forked child rejects the inherited cache by owner
    PID and takes its own baseline before installing its first guard.
    """

    if proc_root != Path("/proc"):
        return _scan_opaque_same_user_processes(proc_root)
    current_pid = os.getpid()
    global _OPAQUE_PROCESS_BASELINE_OWNER_PID
    global _OPAQUE_PROCESS_BASELINE_CACHE
    with _OPAQUE_PROCESS_BASELINE_LOCK:
        if (
            _OPAQUE_PROCESS_BASELINE_OWNER_PID != current_pid
            or _OPAQUE_PROCESS_BASELINE_CACHE is None
        ):
            _OPAQUE_PROCESS_BASELINE_CACHE = _scan_opaque_same_user_processes(
                proc_root
            )
            _OPAQUE_PROCESS_BASELINE_OWNER_PID = current_pid
        return _OPAQUE_PROCESS_BASELINE_CACHE


def _validated_external_broker_socket(
    socket_path: Path,
    cleanup_dir: Path,
) -> tuple[Path, Path] | None:
    """Validate one random external socket child before unlinking it."""

    try:
        raw_socket = Path(socket_path)
        raw_cleanup = Path(cleanup_dir)
        expected_parent = _verified_operator_broker_socket_parent()
        if (
            not raw_socket.is_absolute()
            or not raw_cleanup.is_absolute()
            or raw_cleanup.parent != expected_parent
            or raw_socket.parent != raw_cleanup
            or raw_socket.name != _BROKER_SOCKET_NAME
            or not raw_cleanup.name.startswith("nv-")
        ):
            return None
        _validate_trusted_directory(
            raw_cleanup,
            operator_owned=True,
            private=True,
        )
        try:
            socket_info = raw_socket.lstat()
        except FileNotFoundError:
            socket_info = None
        if socket_info is not None and (
            stat.S_ISLNK(socket_info.st_mode)
            or not stat.S_ISSOCK(socket_info.st_mode)
            or int(socket_info.st_uid) != os.geteuid()
            or stat.S_IMODE(socket_info.st_mode)
            & (stat.S_IWGRP | stat.S_IWOTH)
        ):
            return None
    except (OSError, RuntimeError):
        return None
    return raw_socket, raw_cleanup


def _cleanup_validated_external_broker_socket(
    socket_path: Path,
    cleanup_dir: Path,
) -> None:
    """Remove only one validated random operator-owned socket child."""

    validated = _validated_external_broker_socket(socket_path, cleanup_dir)
    if validated is None:
        return
    resolved_socket, resolved_cleanup = validated
    with contextlib.suppress(OSError):
        resolved_socket.unlink()
    with contextlib.suppress(OSError):
        resolved_cleanup.rmdir()


def create_native_validation_broker_socket(
    *,
    runtime_root: str | os.PathLike[str],
    untrusted_roots: tuple[Path, ...],
) -> tuple[Path | None, Path | None]:
    """Return a local socket or a random protected endpoint for a deep root."""

    root = Path(runtime_root).resolve()
    local_socket = root / _BROKER_SOCKET_NAME
    if len(os.fsencode(str(local_socket))) < 100:
        return None, None
    parent = _operator_broker_socket_parent()
    if any(parent == root or root in parent.parents for root in untrusted_roots):
        raise RuntimeError("native validation broker socket parent is task-writable")
    parent = _prepare_operator_broker_socket_parent()
    if any(parent == root or root in parent.parents for root in untrusted_roots):
        raise RuntimeError("native validation broker socket parent is task-writable")
    cleanup_dir = Path(tempfile.mkdtemp(prefix="nv-", dir=parent))
    _validate_trusted_directory(
        cleanup_dir,
        operator_owned=True,
    )
    _tighten_private_operator_directory(cleanup_dir)
    _validate_trusted_directory(
        cleanup_dir,
        operator_owned=True,
        private=True,
    )
    socket_path = cleanup_dir / _BROKER_SOCKET_NAME
    if len(os.fsencode(str(socket_path))) >= 100:
        shutil.rmtree(cleanup_dir, ignore_errors=True)
        raise RuntimeError("native validation broker socket path is too long")
    if _validated_external_broker_socket(socket_path, cleanup_dir) is None:
        shutil.rmtree(cleanup_dir, ignore_errors=True)
        raise RuntimeError("native validation broker socket boundary is unsafe")
    return socket_path, cleanup_dir


def _peer_is_guard_launcher(peer_pid: int, root: Path) -> bool:
    """Verify that a broker peer is executing this root's trusted shim.

    Merely finding a guard path somewhere in ``cmdline`` is not sufficient:
    provider-controlled code can choose its own argv, inherit the provider
    capability descriptor, and place that path in an unrelated argument.  The
    generated launcher always runs as ``<trusted-python> -I <guard-shim> ...``;
    require that exact kernel argv shape and executable identity.
    """

    try:
        arguments = tuple(
            os.fsdecode(value)
            for value in Path(f"/proc/{peer_pid}/cmdline").read_bytes().split(b"\0")
            if value
        )
        environment = {
            os.fsdecode(key): os.fsdecode(value)
            for item in Path(f"/proc/{peer_pid}/environ").read_bytes().split(b"\0")
            if item
            for key, separator, value in (item.partition(b"="),)
            if separator
        }
        interpreter_stat = Path(f"/proc/{peer_pid}/exe").stat()
        trusted_interpreter_stat = Path(sys.executable).resolve(strict=True).stat()
        guard_bin = (root / "validation-guard-bin").resolve(strict=True)
        canonical_launcher = (guard_bin / "oompah-validation-guard").resolve(
            strict=True
        )
        invoked_launcher = Path(arguments[2])
        invoked_parent = invoked_launcher.parent.resolve(strict=True)
        invoked_target = invoked_launcher.resolve(strict=True)
    except (IndexError, OSError):
        return False
    return (
        environment.get(_GUARD_ENV) == str(guard_bin)
        and len(arguments) >= 3
        and arguments[1] == "-I"
        and invoked_launcher.is_absolute()
        and invoked_parent == guard_bin
        and invoked_target == canonical_launcher
        and (
            int(interpreter_stat.st_dev),
            int(interpreter_stat.st_ino),
        )
        == (
            int(trusted_interpreter_stat.st_dev),
            int(trusted_interpreter_stat.st_ino),
        )
    )


def _process_group_id(pid: int) -> int | None:
    try:
        raw = Path(f"/proc/{int(pid)}/stat").read_text(encoding="utf-8")
        return int(raw[raw.rfind(")") + 2 :].split()[2])
    except (OSError, ValueError, IndexError):
        return None


def _process_parent_id(pid: int) -> int | None:
    try:
        raw = Path(f"/proc/{int(pid)}/stat").read_text(encoding="utf-8")
        return int(raw[raw.rfind(")") + 2 :].split()[1])
    except (OSError, ValueError, IndexError):
        return None


def _process_session_id(pid: int) -> int | None:
    try:
        raw = Path(f"/proc/{int(pid)}/stat").read_text(encoding="utf-8")
        return int(raw[raw.rfind(")") + 2 :].split()[3])
    except (OSError, ValueError, IndexError):
        return None


def _process_descends_from(
    pid: int,
    ancestor: tuple[int, int],
) -> bool:
    """Prove a live same-UID peer descends from the registered provider."""

    current = int(pid)
    seen: set[int] = set()
    while current > 1 and current not in seen:
        seen.add(current)
        if current == ancestor[0]:
            return _process_start_ticks(current) == ancestor[1]
        try:
            if Path(f"/proc/{current}").stat().st_uid != os.geteuid():
                return False
        except OSError:
            return False
        parent = _process_parent_id(current)
        if parent is None:
            return False
        current = parent
    return False


def _decode_boundary_group(value: str) -> tuple[int, int] | None:
    parts = str(value).split(":", 1)
    if (
        len(parts) != 2
        or not all(part.isdigit() for part in parts)
        or any(int(part) <= 0 for part in parts)
    ):
        return None
    return int(parts[0]), int(parts[1])


def _provider_registration_is_trusted(peer_pid: int, root: Path) -> bool:
    """Recognize only the exact service-spawned configured provider."""

    try:
        raw = _load_verified_guard_config(root)
        creator = raw["creator"]
        bootstrap = raw["provider_bootstrap"]
        parent_pid = _process_parent_id(peer_pid)
        arguments = tuple(
            os.fsdecode(value)
            for value in Path(f"/proc/{peer_pid}/cmdline").read_bytes().split(b"\0")
            if value
        )
    except (KeyError, OSError, RuntimeError, TypeError, ValueError):
        return False
    if (
        not isinstance(creator, dict)
        or not isinstance(bootstrap, dict)
        or not _peer_is_guard_launcher(peer_pid, root)
    ):
        return False
    expected_parent = int(creator.get("pid") or 0)
    if (
        parent_pid != expected_parent
        or _process_start_ticks(expected_parent)
        != int(creator.get("start_ticks") or 0)
    ):
        return False
    command = str(bootstrap.get("command") or "")
    expected_launcher = str(root / "validation-guard-bin" / command)
    if len(arguments) < 4 or arguments[2] != expected_launcher:
        return False
    if command == _PROVIDER_LAUNCHER_NAME:
        return arguments[3] == str(bootstrap.get("subcommand") or "")
    return (
        len(arguments) >= 5
        and arguments[3] == str(bootstrap.get("entrypoint") or "")
        and arguments[4] == str(bootstrap.get("subcommand") or "")
    )


def _capability_proof(
    secret: bytes,
    *,
    nonce: bytes,
    peer_pid: int,
    peer_start_ticks: int,
    request: bytes,
) -> str:
    message = b"\0".join(
        (
            nonce,
            str(peer_pid).encode("ascii"),
            str(peer_start_ticks).encode("ascii"),
            request,
        )
    )
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def _linux_fcntl_value(name: str, fallback: int) -> int:
    value = getattr(fcntl, name, None)
    if value is not None:
        return int(value)
    if not sys.platform.startswith("linux"):
        raise RuntimeError("native validation capability sealing is unavailable")
    return fallback


def _create_linux_memfd(name: str, flags: int) -> int:
    """Create a memfd even when the host Python omits ``os.memfd_create``.

    Native validation already relies on Linux ``/proc`` and ``SO_PEERCRED``.
    Calling the stable libc entry point on that same platform preserves the
    anonymous, sealable kernel object instead of weakening the capability to
    a task-reopenable temporary file.
    """

    create = getattr(os, "memfd_create", None)
    if create is not None:
        return int(create(name, flags))
    if not sys.platform.startswith("linux"):
        raise RuntimeError("native validation capability memfd is unavailable")
    try:
        libc_create = ctypes.CDLL(None, use_errno=True).memfd_create
    except (AttributeError, OSError) as exc:
        raise RuntimeError(
            "native validation capability memfd is unavailable"
        ) from exc
    libc_create.argtypes = (ctypes.c_char_p, ctypes.c_uint)
    libc_create.restype = ctypes.c_int
    while True:
        descriptor = int(libc_create(os.fsencode(name), int(flags)))
        if descriptor >= 0:
            return descriptor
        error = ctypes.get_errno()
        if error != errno.EINTR:
            raise OSError(error, os.strerror(error))


def _capability_descriptor_identity(descriptor: int) -> tuple[int, int]:
    """Return the identity of an exact immutable capability memfd.

    A regular read-only descriptor is insufficient: same-UID task code could
    reopen its ``/proc/self/fd`` link writable or replace the descriptor with
    another file containing a copied secret.  Requiring the complete seal set
    prevents mutation, while the broker's device/inode comparison rejects a
    different sealed memfd containing copied bytes.
    """

    get_seals = _linux_fcntl_value("F_GET_SEALS", _LINUX_F_GET_SEALS)
    try:
        seals = int(fcntl.fcntl(descriptor, get_seals))
        descriptor_stat = os.fstat(descriptor)
    except OSError as exc:
        raise RuntimeError(
            "native validation provider capability is not a sealed memfd"
        ) from exc
    if seals & _REQUIRED_CAPABILITY_SEALS != _REQUIRED_CAPABILITY_SEALS:
        raise RuntimeError(
            "native validation provider capability is not immutable"
        )
    return int(descriptor_stat.st_dev), int(descriptor_stat.st_ino)


def _peer_capability_descriptor_matches(
    peer_pid: int,
    expected_identity: tuple[int, int],
) -> bool:
    """Prove a peer inherited the broker-issued capability object itself."""

    descriptor = -1
    try:
        if peer_pid == os.getpid():
            # The production peer is always a child shim. Keeping the direct
            # integration-test mode exact avoids relying on whether libc's
            # relocated setenv storage is reflected in /proc/self/environ.
            environment = dict(os.environ)
        else:
            environment = {
                os.fsdecode(key): os.fsdecode(value)
                for item in Path(f"/proc/{peer_pid}/environ").read_bytes().split(
                    b"\0"
                )
                if item
                for key, separator, value in (item.partition(b"="),)
                if separator
            }
        raw_descriptor = environment.get(_CAPABILITY_FD_ENV, "")
        if not raw_descriptor.isdigit():
            return False
        descriptor = os.open(
            f"/proc/{peer_pid}/fd/{int(raw_descriptor)}",
            os.O_RDONLY | getattr(os, "O_CLOEXEC", 0),
        )
        return _capability_descriptor_identity(descriptor) == expected_identity
    except (OSError, RuntimeError, ValueError):
        return False
    finally:
        if descriptor >= 0:
            with contextlib.suppress(OSError):
                os.close(descriptor)


def _peer_capability_descriptor_is_missing(peer_pid: int) -> bool:
    """Return whether the declared capability descriptor was closed in transit.

    Recovery is an availability path only for a descendant that inherited the
    capability variable but lost the actual descriptor to ``close_fds``.  A
    present descriptor with the wrong immutable identity is an active forgery,
    not a recoverable absence, and must remain fail-closed.
    """

    try:
        if peer_pid == os.getpid():
            raw_descriptor = os.environ.get(_CAPABILITY_FD_ENV, "")
        else:
            environment = {
                os.fsdecode(key): os.fsdecode(value)
                for item in Path(f"/proc/{peer_pid}/environ").read_bytes().split(
                    b"\0"
                )
                if item
                for key, separator, value in (item.partition(b"="),)
                if separator
            }
            raw_descriptor = environment.get(_CAPABILITY_FD_ENV, "")
        raw_descriptor = raw_descriptor.strip()
        if not raw_descriptor:
            return True
        if not raw_descriptor.isdigit():
            return False
        os.stat(f"/proc/{peer_pid}/fd/{int(raw_descriptor)}")
    except FileNotFoundError:
        return True
    except OSError:
        return False
    return False


def _sealed_capability_descriptor(secret: bytes) -> int:
    flags = getattr(os, "MFD_CLOEXEC", _LINUX_MFD_CLOEXEC) | getattr(
        os, "MFD_ALLOW_SEALING", _LINUX_MFD_ALLOW_SEALING
    )
    descriptor = _create_linux_memfd("oompah-validation-capability", flags)
    try:
        os.write(descriptor, secret)
        os.lseek(descriptor, 0, os.SEEK_SET)
        seals = (
            getattr(fcntl, "F_SEAL_SEAL", _LINUX_F_SEAL_SEAL)
            | getattr(fcntl, "F_SEAL_SHRINK", _LINUX_F_SEAL_SHRINK)
            | getattr(fcntl, "F_SEAL_GROW", _LINUX_F_SEAL_GROW)
            | getattr(fcntl, "F_SEAL_WRITE", _LINUX_F_SEAL_WRITE)
        )
        if seals != _REQUIRED_CAPABILITY_SEALS:
            raise RuntimeError("native validation capability seals are invalid")
        fcntl.fcntl(
            descriptor,
            _linux_fcntl_value("F_ADD_SEALS", _LINUX_F_ADD_SEALS),
            seals,
        )
        _capability_descriptor_identity(descriptor)
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _recv_packet(sock: socket.socket, size: int) -> bytes:
    payload, ancillary, message_flags, _address = sock.recvmsg(size, 0)
    if ancillary or message_flags & (
        getattr(socket, "MSG_CTRUNC", 0) | getattr(socket, "MSG_TRUNC", 0)
    ):
        raise RuntimeError("native validation broker packet is malformed")
    return payload


def _command_identity(value: str) -> str:
    return hashlib.sha256(str(value).strip().encode("utf-8")).hexdigest()


def _shim_command_text(command: str, arguments: list[str]) -> str:
    """Recover the provider-visible command from an intercepted shell argv."""

    if command in {"bash", "dash", "sh", "zsh"}:
        index = 0
        value_options = {"-O", "+O", "-o", "+o", "--init-file", "--rcfile"}
        while index < len(arguments):
            option = arguments[index]
            if option in value_options:
                index += 2
                continue
            if option == "-c" or (
                option.startswith(("-", "+"))
                and not option.startswith("--")
                and "c" in option[1:]
            ):
                if index + 1 < len(arguments):
                    return arguments[index + 1]
                break
            if not option.startswith(("-", "+")):
                break
            index += 1
    return shlex.join([command, *(str(value) for value in arguments)])


def _native_validation_policy_args(
    command: str,
    environment: Mapping[str, str],
) -> dict[str, str]:
    """Recover the native shell's structured validation-policy fields.

    The Codex CLI has a native shell surface rather than oompah's JSON tool
    schema. Its equivalent structured fields are two leading environment
    assignments. Parse only literal assignments; dynamic shell input never
    grants the distinct-mode exception and therefore fails closed.
    """

    values = {
        "validation_mode": str(environment.get(_VALIDATION_MODE_ENV) or "").strip(),
        "validation_justification": str(
            environment.get(_VALIDATION_JUSTIFICATION_ENV) or ""
        ).strip(),
    }
    invalid_fields: set[str] = set()

    def accept_literal(field: str, value: str) -> None:
        # These fields are policy data, not shell programs. Reject every
        # expansion-bearing spelling even when quoting would make a character
        # literal in one shell layer; nested shells must not reinterpret it.
        if any(character in value for character in "$`*?[]{}<>~!"):
            invalid_fields.add(field)
            return
        values[field] = value.strip()

    for field in tuple(values):
        accept_literal(field, values[field])

    def result() -> dict[str, str]:
        for field in invalid_fields:
            values[field] = ""
        return {"command": str(command or ""), **values}

    try:
        tokens = shlex.split(str(command or ""), posix=True)
    except ValueError:
        return result()
    index = 0
    if tokens and os.path.basename(tokens[0]) == "env":
        index = 1
        while index < len(tokens) and tokens[index].startswith("-"):
            option = tokens[index]
            index += 1
            if option in {"-u", "--unset", "-C", "--chdir"}:
                index += 1
    while index < len(tokens):
        name, separator, value = tokens[index].partition("=")
        if not separator or not name.replace("_", "a").isalnum():
            break
        if name == _VALIDATION_MODE_ENV:
            accept_literal("validation_mode", value)
        elif name == _VALIDATION_JUSTIFICATION_ENV:
            accept_literal("validation_justification", value)
        index += 1
    return result()


def _peer_guard_invocation(
    peer_pid: int,
    root: Path,
) -> tuple[str, dict[str, str], Path]:
    """Read the authenticated shim peer's exact command and environment."""

    try:
        arguments = [
            os.fsdecode(value)
            for value in Path(f"/proc/{peer_pid}/cmdline").read_bytes().split(b"\0")
            if value
        ]
        environment = {
            os.fsdecode(key): os.fsdecode(value)
            for item in Path(f"/proc/{peer_pid}/environ").read_bytes().split(b"\0")
            if item
            for key, separator, value in (item.partition(b"="),)
            if separator
        }
        working_directory = Path(f"/proc/{peer_pid}/cwd").resolve(strict=True)
        invoked_launcher = Path(arguments[2])
        guard_bin = (root / "validation-guard-bin").resolve(strict=True)
        if (
            not invoked_launcher.is_absolute()
            or invoked_launcher.parent.resolve(strict=True) != guard_bin
            or invoked_launcher.resolve(strict=True)
            != (guard_bin / "oompah-validation-guard").resolve(strict=True)
        ):
            raise RuntimeError("native validation launcher identity changed")
        command = invoked_launcher.name
        command_text = _shim_command_text(command, arguments[3:])
    except (IndexError, OSError) as exc:
        raise RuntimeError("native validation command identity is unavailable") from exc
    return command_text, environment, working_directory


@dataclass
class _NativeValidationRun:
    command: str
    command_identity: str
    invocation_id: str
    scope: str
    started_at: float
    callback_lock: Any = field(default_factory=threading.Lock, repr=False)
    state_lock: Any = field(default_factory=threading.Lock, repr=False)
    launch_state: str = "preparing"
    supervisor_outcome: str = ""
    cleanup_outcome: str = ""
    terminal_outcome: str = ""
    terminal_succeeded: bool = False
    # A terminal lifecycle callback is owned by exactly one caller.  The
    # synchronous item-completion path and the bounded retirement path both
    # take this state while holding ``state_lock``; a second contender must
    # retain the guard root rather than publish a duplicate completion.
    terminal_publication_state: str = "unclaimed"
    # Retirement may move a blocked terminal callback off the broker thread.
    # Keep the publisher associated with this exact run until a later bounded
    # retirement pass observes that it has exited.  Otherwise a caller could
    # delete the executable guard root while that daemon is still executing
    # user supplied lifecycle code.
    terminal_publisher: threading.Thread | None = field(default=None, repr=False)


class _BrokerRequestFailure(RuntimeError):
    """A typed, bounded rejection that can cross the broker socket."""

    denial_packet = b"DENIED TRANSPORT\n"


class _BrokerPolicyDenied(_BrokerRequestFailure):
    denial_packet = b"DENIED POLICY\n"


class _BrokerAuthorityDenied(_BrokerRequestFailure):
    denial_packet = b"DENIED AUTHORITY\n"


class _BrokerUnsupported(_BrokerRequestFailure):
    denial_packet = b"DENIED UNSUPPORTED\n"


class _BrokerIdentityLost(_BrokerRequestFailure):
    denial_packet = b"DENIED IDENTITY\n"


class _BrokerTransportFailure(_BrokerRequestFailure):
    denial_packet = b"DENIED TRANSPORT\n"


def _broker_denial_response(error: BaseException) -> bytes:
    """Return the typed wire outcome; untyped failures are transport faults."""

    if isinstance(error, _BrokerRequestFailure):
        return error.denial_packet
    return _BrokerTransportFailure.denial_packet


def _reuse_policy_denied(denial: str) -> _BrokerPolicyDenied:
    """Represent a live reusable-gate denial without parsing its prose."""

    return _BrokerPolicyDenied(denial)


def _pidfd_supervision_failure(error: BaseException) -> _BrokerRequestFailure:
    """Classify pidfd setup failures without confusing platform and peer state."""

    if isinstance(error, AttributeError):
        return _BrokerUnsupported("native validation pidfd supervision is unavailable")
    if isinstance(error, OSError):
        # ENOSYS proves that this kernel lacks pidfds. EOPNOTSUPP is the
        # equivalent platform-level refusal on systems that expose the call
        # through libc but do not implement the feature. Other errors say
        # something about this peer or local transport, not support.
        if error.errno in {errno.ENOSYS, errno.EOPNOTSUPP, errno.ENOTSUP}:
            return _BrokerUnsupported("native validation pidfd supervision is unavailable")
        if error.errno == errno.ESRCH:
            return _BrokerIdentityLost(
                "native validation supervised peer changed identity"
            )
    return _BrokerTransportFailure("native validation pidfd supervision failed")


class _NativeValidationLeaseBroker:
    """Operator-side lease broker for sandboxed native command shims.

    Codex command processes can read the guard root but cannot safely receive
    write access to the service's global validation database.  A per-session
    Unix socket keeps all trusted SQLite work in the orchestrator process. It
    transfers the acquired kernel flock descriptor to both a supervisor and
    the heavyweight command, whose descendants inherit the same open-file
    description and therefore retain capacity even after detaching.
    """

    def __init__(
        self,
        root: Path,
        *,
        socket_path: Path,
        socket_cleanup_dir: Path | None = None,
        validation_lease: ValidationResourceLease,
        owner: ValidationLeaseOwner,
        timeout_seconds: float,
        validation_reuse_policy: Mapping[str, Any] | None = None,
        validation_reuse_authority_check: Callable[[], object] | None = None,
        validation_reuse_policy_handler: Callable[..., object] | None = None,
        validation_command_handler: Callable[..., object] | None = None,
        executable_search_path: str | None = None,
        untrusted_executable_roots: tuple[str | os.PathLike[str], ...] = (),
    ) -> None:
        self.root = root
        if socket_cleanup_dir is not None:
            validated_socket = _validated_external_broker_socket(
                socket_path,
                socket_cleanup_dir,
            )
            if validated_socket is None:
                raise RuntimeError(
                    "native validation broker socket boundary is unsafe"
                )
            socket_path, socket_cleanup_dir = validated_socket
        elif socket_path.parent != root:
            raise RuntimeError("native validation broker socket escaped guard root")
        self.socket_path = socket_path
        self.socket_cleanup_dir = socket_cleanup_dir
        self.validation_lease = validation_lease
        self.owner = owner
        self.timeout_seconds = max(float(timeout_seconds), 1.0)
        self.validation_reuse_policy = (
            dict(validation_reuse_policy)
            if isinstance(validation_reuse_policy, Mapping)
            else None
        )
        self.validation_reuse_authority_check = validation_reuse_authority_check
        self.validation_reuse_policy_handler = validation_reuse_policy_handler
        self.validation_command_handler = validation_command_handler
        self.executable_search_path = executable_search_path
        self.untrusted_executable_roots = tuple(untrusted_executable_roots)
        self._stop = threading.Event()
        self._cleanup_requested = threading.Event()
        self._requested_cleanup_outcome = ""
        self._boundary_lock = threading.Lock()
        self._handler_lock = threading.Lock()
        self._handler_threads: set[threading.Thread] = set()
        self._handler_connections: set[socket.socket] = set()
        self._boundaries: deque[tuple[float, str, str]] = deque()
        self._seen_boundary_groups: set[str] = set()
        self._bound_item_ids: set[str] = set()
        self._boundary_items: dict[str, str] = {}
        self._validation_runs: dict[str, _NativeValidationRun] = {}
        self._supervisor_observers: set[threading.Thread] = set()
        self._supervisor_processes: set[subprocess.Popen[bytes]] = set()
        self._lifecycle_publishers: set[threading.Thread] = set()
        self._provider_identity: tuple[int, int] | None = None
        self._capability_secret: bytes | None = None
        self._capability_identity: tuple[int, int] | None = None
        # Keep one broker-owned reference for the whole session. Besides
        # cleanup ownership, this pins the anonymous inode so the device/inode
        # authentication tuple cannot be recycled after a provider closes its
        # inherited copy.
        self._capability_fd: int | None = None
        self._listener = socket.socket(socket.AF_UNIX, _BROKER_SOCKET_TYPE)
        if self.socket_path.exists() or self.socket_path.is_symlink():
            self._listener.close()
            raise RuntimeError("native validation broker socket already exists")
        if self.socket_cleanup_dir is not None and (
            _validated_external_broker_socket(
                self.socket_path,
                self.socket_cleanup_dir,
            )
            is None
        ):
            self._listener.close()
            raise RuntimeError("native validation broker socket boundary is unsafe")
        try:
            self._listener.bind(str(self.socket_path))
            os.chmod(
                self.socket_path,
                stat.S_IRUSR | stat.S_IWUSR,
                follow_symlinks=False,
            )
            socket_info = self.socket_path.lstat()
            if (
                not stat.S_ISSOCK(socket_info.st_mode)
                or int(socket_info.st_uid) != os.geteuid()
                or stat.S_IMODE(socket_info.st_mode) != 0o600
            ):
                raise RuntimeError("native validation broker socket is unsafe")
        except BaseException:
            self._listener.close()
            with contextlib.suppress(OSError):
                self.socket_path.unlink()
            raise
        self._listener.listen()
        self._listener.settimeout(0.2)
        self._thread = threading.Thread(
            target=self._serve,
            name=f"native-validation-broker-{owner.task_id}",
            daemon=True,
        )
        self._thread.start()

    def _serve(self) -> None:
        while not self._stop.is_set():
            try:
                connection, _ = self._listener.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            handler = threading.Thread(
                target=self._run_handler,
                args=(connection,),
                name=f"native-validation-request-{self.owner.task_id}",
                daemon=True,
            )
            with self._handler_lock:
                if self._stop.is_set():
                    connection.close()
                    return
                self._handler_connections.add(connection)
                self._handler_threads.add(handler)
                try:
                    handler.start()
                except BaseException:
                    self._handler_connections.discard(connection)
                    self._handler_threads.discard(handler)
                    connection.close()
                    raise

    def _run_handler(self, connection: socket.socket) -> None:
        try:
            self._handle(connection)
        finally:
            with self._handler_lock:
                self._handler_connections.discard(connection)
                self._handler_threads.discard(threading.current_thread())

    def _register_provider(
        self,
        connection: socket.socket,
        *,
        peer_pid: int,
        peer_start_ticks: int,
    ) -> None:
        if not _provider_registration_is_trusted(peer_pid, self.root):
            raise RuntimeError("native validation provider registration is invalid")
        secret = secrets.token_bytes(32)
        descriptor = _sealed_capability_descriptor(secret)
        direct_descriptor = -1
        response = b"CAPABILITY\n"
        claimed = False
        registered = False
        close_descriptor = True
        try:
            capability_identity = _capability_descriptor_identity(descriptor)
            config = _load_verified_guard_config(self.root)
            bootstrap = config.get("provider_bootstrap")
            if (
                isinstance(bootstrap, dict)
                and bootstrap.get("command") == _PROVIDER_LAUNCHER_NAME
            ):
                source_fd = int(bootstrap.get("source_fd") or -1)
                if source_fd < 0:
                    raise RuntimeError(
                        "native validation direct provider descriptor is unavailable"
                    )
                direct_descriptor = os.dup(source_fd)
                direct_stat = os.fstat(direct_descriptor)
                if (
                    int(direct_stat.st_dev)
                    != int(bootstrap.get("entrypoint_device") or -1)
                    or int(direct_stat.st_ino)
                    != int(bootstrap.get("entrypoint_inode") or -1)
                ):
                    raise RuntimeError(
                        "native validation direct provider descriptor changed"
                    )
                response = b"CAPABILITY-DIRECT\n"
            with self._boundary_lock:
                if self._stop.is_set():
                    raise RuntimeError(
                        "native validation broker stopped during registration"
                    )
                if self._provider_identity is not None:
                    raise RuntimeError(
                        "native validation provider was already registered"
                    )
                self._provider_identity = (peer_pid, peer_start_ticks)
                self._capability_secret = secret
                self._capability_identity = capability_identity
                self._capability_fd = descriptor
                claimed = True
                close_descriptor = False
                # Publication and stop are one critical section: either the
                # capability reply is accepted before retirement begins, or a
                # stopped broker sends no capability at all.
                sent = connection.sendmsg(
                    [response],
                    [
                        (
                            socket.SOL_SOCKET,
                            socket.SCM_RIGHTS,
                            array.array(
                                "i",
                                [
                                    descriptor,
                                    *(
                                        (direct_descriptor,)
                                        if direct_descriptor >= 0
                                        else ()
                                    ),
                                ],
                            ),
                        )
                    ],
                )
                if sent != len(response):
                    raise RuntimeError(
                        "native validation capability reply was incomplete"
                    )
                registered = True
        finally:
            if claimed and not registered:
                with self._boundary_lock:
                    if (
                        self._provider_identity == (peer_pid, peer_start_ticks)
                        and self._capability_fd == descriptor
                    ):
                        self._provider_identity = None
                        self._capability_secret = None
                        self._capability_identity = None
                        self._capability_fd = None
                        close_descriptor = True
            if close_descriptor:
                with contextlib.suppress(OSError):
                    os.close(descriptor)
            if direct_descriptor >= 0:
                with contextlib.suppress(OSError):
                    os.close(direct_descriptor)

    def issue_local_test_capability(self) -> int:
        """Issue a descriptor only for direct guard integration tests.

        Managed production sessions always register their exact provider
        launcher instead. The no-bootstrap install mode exists solely for the
        guard's subprocess-level regression suite.
        """

        creator_start = _process_start_ticks(os.getpid())
        if creator_start is None:
            raise RuntimeError("native validation test capability is unavailable")
        secret = secrets.token_bytes(32)
        descriptor = _sealed_capability_descriptor(secret)
        published = False
        try:
            capability_identity = _capability_descriptor_identity(descriptor)
            os.set_inheritable(descriptor, True)
            with self._boundary_lock:
                if self._stop.is_set():
                    raise RuntimeError(
                        "native validation broker stopped during registration"
                    )
                if self._provider_identity is not None:
                    raise RuntimeError(
                        "native validation provider was already registered"
                    )
                self._provider_identity = (os.getpid(), creator_start)
                self._capability_secret = secret
                self._capability_identity = capability_identity
                self._capability_fd = descriptor
                published = True
            return descriptor
        finally:
            if not published:
                with contextlib.suppress(OSError):
                    os.close(descriptor)

    def _authenticate_boundary_request(
        self,
        connection: socket.socket,
        *,
        request: bytes,
        peer_pid: int,
        peer_start_ticks: int,
    ) -> None:
        with self._boundary_lock:
            provider_identity = self._provider_identity
            secret = self._capability_secret
            capability_identity = self._capability_identity
            capability_descriptor = self._capability_fd
        if (
            provider_identity is None
            or secret is None
            or capability_identity is None
            or not _process_descends_from(peer_pid, provider_identity)
        ):
            raise RuntimeError("native validation provider capability is unavailable")
        inherited_capability = _peer_capability_descriptor_matches(
            peer_pid,
            capability_identity,
        )
        if not inherited_capability:
            # A provider can legitimately start a child with ``close_fds``.
            # That must not turn the already-installed, exact guard boundary
            # into an availability failure: the child still reaches this
            # immutable launcher, whose kernel executable identity and
            # provider ancestry are both verified above.  Reissue only a
            # duplicate of the broker-held sealed memfd to that exact shim,
            # then require the ordinary nonce proof below.  A same-UID peer
            # cannot request this recovery merely by knowing the socket path:
            # _handle and this branch both require the root's trusted shim and
            # live descent from the registered provider generation.
            if (
                capability_descriptor is None
                or not _peer_capability_descriptor_is_missing(peer_pid)
                or not _peer_is_guard_launcher(
                    peer_pid,
                    self.root,
                )
            ):
                raise RuntimeError(
                    "native validation provider capability is unavailable"
                )
            duplicate_descriptor = os.dup(capability_descriptor)
            try:
                connection.sendall(b"RECOVER\n")
                sent = connection.sendmsg(
                    [b"CAPABILITY\n"],
                    [
                        (
                            socket.SOL_SOCKET,
                            socket.SCM_RIGHTS,
                            array.array("i", [duplicate_descriptor]),
                        )
                    ],
                )
                if sent != len(b"CAPABILITY\n"):
                    raise RuntimeError(
                        "native validation capability recovery was incomplete"
                    )
            finally:
                with contextlib.suppress(OSError):
                    os.close(duplicate_descriptor)
        nonce = secrets.token_bytes(32)
        connection.sendall(b"CHALLENGE " + nonce.hex().encode("ascii") + b"\n")
        proof_packet = _recv_packet(connection, 128)
        if (
            len(proof_packet) != len(b"PROVE ") + 64 + 1
            or not proof_packet.endswith(b"\n")
        ):
            raise RuntimeError("native validation capability proof is malformed")
        proof = proof_packet[:-1]
        expected = _capability_proof(
            secret,
            nonce=nonce,
            peer_pid=peer_pid,
            peer_start_ticks=peer_start_ticks,
            request=request,
        ).encode("ascii")
        if not hmac.compare_digest(proof, b"PROVE " + expected):
            raise RuntimeError("native validation capability proof is invalid")
        if _process_start_ticks(peer_pid) != peer_start_ticks:
            raise RuntimeError("native validation peer identity changed")

    def _handle(self, connection: socket.socket) -> None:
        handle = None
        descriptor_transferred = False
        lifecycle_group: str | None = None
        lifecycle_run: _NativeValidationRun | None = None
        supervisor_observer: threading.Thread | None = None
        failure_outcome = "transport_error"
        with connection:
            try:
                request = _recv_packet(connection, 256)
                if not request.endswith(b"\n") or b"\n" in request[:-1]:
                    raise RuntimeError("invalid native validation broker request")
                if not hasattr(socket, "SO_PEERCRED"):
                    raise RuntimeError("native validation peer fencing is unavailable")
                credentials = connection.getsockopt(
                    socket.SOL_SOCKET,
                    socket.SO_PEERCRED,
                    struct.calcsize("3i"),
                )
                peer_pid, peer_uid, _peer_gid = struct.unpack("3i", credentials)
                if peer_uid != os.geteuid():
                    raise RuntimeError("native validation peer identity is invalid")
                peer_start_ticks = _process_start_ticks(peer_pid)
                if peer_start_ticks is None or not _peer_is_guard_launcher(
                    peer_pid, self.root
                ):
                    raise RuntimeError("native validation peer is unavailable")
                if request == b"REGISTER\n":
                    self._register_provider(
                        connection,
                        peer_pid=peer_pid,
                        peer_start_ticks=peer_start_ticks,
                    )
                    return
                request_parts = request.rstrip(b"\n").split(b" ")
                if (
                    len(request_parts) != 3
                    or request_parts[0] not in {b"ACQUIRE", b"OBSERVE"}
                    or len(request_parts[1]) > 128
                    or len(request_parts[2]) != 64
                ):
                    raise RuntimeError("invalid native validation broker request")
                request_kind, boundary_group_raw, command_identity_raw = request_parts
                try:
                    boundary_group = boundary_group_raw.decode("ascii")
                    command_identity = command_identity_raw.decode("ascii")
                    int(command_identity, 16)
                except (UnicodeDecodeError, ValueError) as exc:
                    raise RuntimeError(
                        "invalid native validation command identity"
                    ) from exc
                self._authenticate_boundary_request(
                    connection,
                    request=request,
                    peer_pid=peer_pid,
                    peer_start_ticks=peer_start_ticks,
                )
                command, command_environment, working_directory = (
                    _peer_guard_invocation(
                        peer_pid,
                        self.root,
                    )
                )
                if _command_identity(command) != command_identity:
                    raise RuntimeError("native validation command identity changed")
                peer_process_group = _process_group_id(peer_pid)
                if peer_process_group is None:
                    raise RuntimeError("native validation peer group is unavailable")
                group_identity = _decode_boundary_group(boundary_group)
                if group_identity is None:
                    raise RuntimeError("native validation boundary group is invalid")
                with self._boundary_lock:
                    boundary_seen = boundary_group in self._seen_boundary_groups
                    if not boundary_seen:
                        if group_identity != (peer_pid, peer_start_ticks):
                            raise RuntimeError(
                                "native validation boundary owner is invalid"
                            )
                        if peer_process_group != peer_pid:
                            raise RuntimeError(
                                "native validation boundary lacks a dedicated group"
                            )
                        self._seen_boundary_groups.add(boundary_group)
                        self._boundaries.append(
                            (time.monotonic(), boundary_group, command_identity)
                        )
                    elif (
                        peer_process_group != group_identity[0]
                        or _process_start_ticks(group_identity[0])
                        != group_identity[1]
                    ):
                        raise RuntimeError(
                            "native validation nested boundary identity changed"
                        )
                if request_kind == b"OBSERVE":
                    connection.sendall(b"OBSERVED\n")
                    return
                if peer_process_group != peer_pid:
                    raise RuntimeError(
                        "native validation peer is not process-group fenced"
                    )

                # The shim's context-aware classifier has already established
                # that ACQUIRE is heavyweight. Recheck live reusable-gate
                # authority in the trusted broker immediately before capacity
                # acquisition so the native subscription path has the same
                # exact/full/focused policy as bridged command tools.
                from oompah.api_agent import _validation_reuse_policy_decision

                policy_args = _native_validation_policy_args(
                    command,
                    command_environment,
                )
                classification = classify_validation_command(
                    command,
                    configured_command=str(
                        (self.validation_reuse_policy or {}).get("command") or ""
                    ),
                    executable_search_path=self.executable_search_path,
                    untrusted_executable_roots=self.untrusted_executable_roots,
                    command_environment=command_environment,
                    working_directory=working_directory,
                )
                if not classification.heavyweight:
                    raise RuntimeError(
                        "native validation classification changed across boundary"
                    )
                validation_invocation_id = secrets.token_hex(16)

                def reuse_policy_snapshot() -> tuple[str, str | None, str]:
                    return _validation_reuse_policy_decision(
                        policy_args,
                        self.validation_reuse_policy,
                        self.validation_reuse_authority_check,
                        classification=classification,
                    )

                def record_reuse_policy(
                    snapshot: tuple[str, str | None, str],
                ) -> None:
                    decision, _denial, justification = snapshot
                    if decision and callable(self.validation_reuse_policy_handler):
                        try:
                            self.validation_reuse_policy_handler(
                                command=command,
                                decision=decision,
                                justification=justification,
                                invocation_id=validation_invocation_id,
                            )
                        except Exception:
                            # Telemetry can never weaken policy enforcement.
                            logger.debug(
                                "Native validation reuse telemetry failed",
                                exc_info=True,
                            )

                initial_policy = reuse_policy_snapshot()
                denial = initial_policy[1]
                if denial is not None:
                    record_reuse_policy(initial_policy)
                    raise _reuse_policy_denied(denial)

                def cancellation_outcome() -> str:
                    if self._cleanup_requested.is_set():
                        return self._requested_cleanup_outcome or "transport_error"
                    if self._stop.is_set() or (
                        self.root / _CANCELLATION_NAME
                    ).exists():
                        return "authority_withdrawn"
                    if _process_start_ticks(peer_pid) != peer_start_ticks:
                        return "transport_error"
                    return ""

                def cancelled() -> bool:
                    return bool(cancellation_outcome())

                handle = self.validation_lease.acquire(
                    self.owner,
                    is_cancelled=cancelled,
                )
                if cancelled():
                    raise _BrokerAuthorityDenied(
                        "native validation authority was withdrawn"
                    )
                handle.attach_process(
                    SimpleNamespace(pid=peer_pid),
                    timeout_seconds=self.timeout_seconds,
                )
                if cancelled():
                    raise _BrokerAuthorityDenied(
                        "native validation authority was withdrawn"
                    )
                pretransfer_policy = reuse_policy_snapshot()
                denial = pretransfer_policy[1]
                if denial is not None:
                    record_reuse_policy(pretransfer_policy)
                    raise _reuse_policy_denied(denial)
                descriptor = handle.pass_fds[0]
                lifecycle_run = self._start_validation_lifecycle(
                    boundary_group,
                    command=command,
                    command_identity=command_identity,
                    classification=classification,
                    invocation_id=validation_invocation_id,
                )
                lifecycle_group = boundary_group
                pending_cancellation = cancellation_outcome()
                if pending_cancellation:
                    failure_outcome = pending_cancellation
                    raise _BrokerAuthorityDenied(
                        "native validation launch was cancelled"
                    )
                supervisor_observer = _start_validation_lease_supervisor(
                    self.root,
                    peer_pid=peer_pid,
                    peer_start_ticks=peer_start_ticks,
                    lease_descriptor=descriptor,
                    timeout_seconds=self.timeout_seconds,
                    terminal_handler=lambda outcome: (
                        self._claim_supervisor_terminal(
                            boundary_group,
                            outcome,
                        )
                    ),
                )
                with self._handler_lock:
                    self._supervisor_observers.add(supervisor_observer)
                    supervisor_process = getattr(
                        supervisor_observer,
                        "_native_validation_supervisor_process",
                        None,
                    )
                    if isinstance(supervisor_process, subprocess.Popen):
                        self._supervisor_processes.add(supervisor_process)
                pending_cancellation = cancellation_outcome()
                if pending_cancellation:
                    failure_outcome = pending_cancellation
                    raise _BrokerAuthorityDenied(
                        "native validation launch was cancelled"
                    )
                if lifecycle_run is None:
                    raise RuntimeError("native validation lifecycle is unavailable")
                # Take the last potentially blocking authority sample before
                # entering the linearization lock. Terminal publication and
                # descriptor delivery then share one state transition;
                # whichever side owns the lock first is definitive.
                transfer_policy = reuse_policy_snapshot()
                transfer_error = ""
                with lifecycle_run.state_lock:
                    if lifecycle_run.launch_state == "terminated":
                        failure_outcome = (
                            lifecycle_run.terminal_outcome
                            or lifecycle_run.cleanup_outcome
                            or (
                                self._requested_cleanup_outcome
                                if self._cleanup_requested.is_set()
                                else "transport_error"
                            )
                        )
                        transfer_error = (
                            "native validation terminated before descriptor transfer"
                        )
                    elif self._cleanup_requested.is_set():
                        failure_outcome = (
                            self._requested_cleanup_outcome or "transport_error"
                        )
                        lifecycle_run.launch_state = "terminated"
                        lifecycle_run.cleanup_outcome = failure_outcome
                        lifecycle_run.terminal_outcome = failure_outcome
                        transfer_error = (
                            "native validation terminated before descriptor transfer"
                        )
                    else:
                        denial = transfer_policy[1]
                        if denial is not None:
                            failure_outcome = "authority_withdrawn"
                            lifecycle_run.launch_state = "terminated"
                            lifecycle_run.terminal_outcome = failure_outcome
                            transfer_error = denial
                        else:
                            try:
                                sent = connection.sendmsg(
                                    [b"LEASE\n"],
                                    [
                                        (
                                            socket.SOL_SOCKET,
                                            socket.SCM_RIGHTS,
                                            array.array("i", [descriptor]),
                                        )
                                    ],
                                )
                                if sent != len(b"LEASE\n"):
                                    raise RuntimeError(
                                        "native validation lease descriptor "
                                        "transfer was incomplete"
                                    )
                            except Exception:
                                failure_outcome = (
                                    self._requested_cleanup_outcome
                                    if self._cleanup_requested.is_set()
                                    else "transport_error"
                                )
                                lifecycle_run.launch_state = "terminated"
                                lifecycle_run.terminal_outcome = failure_outcome
                                raise
                            lifecycle_run.launch_state = "transferred"
                            descriptor_transferred = True
                if transfer_error:
                    if transfer_policy[1] is not None:
                        record_reuse_policy(transfer_policy)
                        raise _reuse_policy_denied(transfer_error)
                    raise _BrokerTransportFailure(transfer_error)
                # Allowed policy telemetry is immutable only after the kernel
                # accepted the LEASE descriptor transfer.
                record_reuse_policy(transfer_policy)
                handle.relinquish_transferred_descriptor()
            except Exception as exc:
                defer_to_cleanup_supervisor = (
                    self._cleanup_requested.is_set()
                    and supervisor_observer is not None
                )
                if (
                    lifecycle_group is not None
                    and not descriptor_transferred
                    and not defer_to_cleanup_supervisor
                ):
                    self._complete_validation_group(
                        lifecycle_group,
                        succeeded=False,
                        outcome=failure_outcome,
                    )
                with contextlib.suppress(OSError):
                    connection.sendall(_broker_denial_response(exc))
            finally:
                if handle is not None and not descriptor_transferred:
                    handle.release()

    def _notify_validation_lifecycle(
        self,
        *,
        command: str,
        phase: str,
        succeeded: bool,
        outcome: str,
        duration_seconds: float,
        invocation_id: str,
        validation_scope: str,
    ) -> None:
        handler = self.validation_command_handler
        if not callable(handler):
            return
        try:
            handler(
                command=command,
                phase=phase,
                succeeded=succeeded,
                outcome=outcome,
                duration_seconds=max(float(duration_seconds), 0.0),
                invocation_id=invocation_id,
                validation_scope=validation_scope,
            )
        except Exception:
            logger.debug(
                "Native validation lifecycle telemetry failed",
                exc_info=True,
            )

    def _start_validation_lifecycle(
        self,
        boundary_group: str,
        *,
        command: str,
        command_identity: str,
        classification: ValidationCommandClassification,
        invocation_id: str,
    ) -> _NativeValidationRun:
        run = _NativeValidationRun(
            command=command,
            command_identity=command_identity,
            invocation_id=invocation_id,
            scope=classification.scope,
            started_at=time.monotonic(),
        )
        # Publish while owning this invocation's callback lock. A concurrent
        # retirement can claim the run, but its completion callback cannot
        # overtake a blocked started callback.
        with run.callback_lock:
            with self._boundary_lock:
                if boundary_group in self._validation_runs:
                    raise RuntimeError("native validation lifecycle already started")
                self._validation_runs[boundary_group] = run
            self._notify_validation_lifecycle(
                command=command,
                phase="started",
                succeeded=False,
                outcome="running",
                duration_seconds=0.0,
                invocation_id=invocation_id,
                validation_scope=classification.scope,
            )
        return run

    def _claim_supervisor_terminal(
        self,
        boundary_group: str,
        outcome: str,
    ) -> Callable[[], bool] | None:
        """Claim one terminal cause and return its post-ACK publication."""

        with self._boundary_lock:
            run = self._validation_runs.get(boundary_group)
        if run is None:
            return None
        with run.state_lock:
            run.supervisor_outcome = outcome
            if (
                outcome == "exited"
                or run.terminal_outcome
                or run.terminal_publication_state != "unclaimed"
            ):
                return None
            resolved_outcome = outcome
            if (
                outcome == "authority_withdrawn"
                and (
                    run.cleanup_outcome
                    or (
                        self._requested_cleanup_outcome
                        if self._cleanup_requested.is_set()
                        else ""
                    )
                )
                not in {"", "authority_withdrawn"}
            ):
                resolved_outcome = (
                    run.cleanup_outcome or self._requested_cleanup_outcome
                )
            run.launch_state = "terminated"
            run.terminal_outcome = resolved_outcome
            run.terminal_publication_state = "publishing"
        # Remove the run from item-completion contention before acknowledging
        # the supervisor. A concurrent item that already captured ``run`` will
        # observe terminal_outcome under state_lock and cannot publish a generic
        # command result over this exact supervisor cause.
        with self._boundary_lock:
            if self._validation_runs.get(boundary_group) is not run:
                return None
            self._validation_runs.pop(boundary_group, None)
            self._boundary_items.pop(boundary_group, None)

        def publish_terminal() -> bool:
            # Publication is deliberately outside the ACK boundary. The
            # callback lock preserves started-before-completed ordering, while
            # a blocked or failing telemetry consumer cannot delay mandatory
            # process termination or lease release.
            try:
                with run.callback_lock:
                    self._notify_validation_lifecycle(
                        command=run.command,
                        phase="completed",
                        succeeded=False,
                        outcome=resolved_outcome,
                        duration_seconds=time.monotonic() - run.started_at,
                        invocation_id=run.invocation_id,
                        validation_scope=run.scope,
                    )
            finally:
                with run.state_lock:
                    run.terminal_publication_state = "published"
            return True

        return publish_terminal

    def _complete_validation_group(
        self,
        boundary_group: str,
        *,
        succeeded: bool,
        outcome: str,
        callback_timeout_seconds: float | None = None,
    ) -> bool:
        with self._boundary_lock:
            run = self._validation_runs.get(boundary_group)
        if run is None:
            return False
        with run.state_lock:
            if not run.terminal_outcome:
                run.launch_state = "terminated"
                run.terminal_outcome = outcome
                run.terminal_succeeded = succeeded
            outcome = run.terminal_outcome
            succeeded = run.terminal_succeeded
            # This is the sole terminal-publication ownership transfer for
            # both direct item completion and bounded retirement.  In
            # particular, a synchronous caller cannot read ``None`` and then
            # publish while stop installs a daemon publisher for the same
            # invocation.
            if run.terminal_publication_state != "unclaimed":
                return False
            run.terminal_publication_state = "publishing"

        def finish() -> None:
            # Keep publication linearized to this exact run. A new command
            # cannot replace a group identity, but checking identity here
            # makes delayed daemon completion harmless under concurrent
            # retirement retries.
            with self._boundary_lock:
                if self._validation_runs.get(boundary_group) is run:
                    self._validation_runs.pop(boundary_group, None)
                    self._boundary_items.pop(boundary_group, None)
            with run.state_lock:
                run.terminal_publication_state = "published"

        def publish() -> None:
            # A terminal event must wait behind its own started event. This is
            # intentionally a separate function so retirement can let an
            # uncooperative telemetry callback finish in a daemon publisher
            # instead of acquiring callback_lock without a bound.
            with run.callback_lock:
                self._notify_validation_lifecycle(
                    command=run.command,
                    phase="completed",
                    succeeded=succeeded,
                    outcome=outcome,
                    duration_seconds=time.monotonic() - run.started_at,
                    invocation_id=run.invocation_id,
                    validation_scope=run.scope,
                )

        if callback_timeout_seconds is None:
            try:
                publish()
            finally:
                finish()
            return True

        # A prior retirement may already have moved this completion into a
        # daemon. Never start a second terminal publisher for the same
        # invocation, and never discard the first while it is alive.
        def publish_and_finish() -> None:
            try:
                publish()
            finally:
                finish()

        publisher = threading.Thread(
            target=publish_and_finish,
            name=f"native-validation-lifecycle-completed-{boundary_group}",
            daemon=True,
        )
        with run.state_lock:
            # Ownership was claimed above under the same lock.  Recording the
            # daemon is bookkeeping for bounded retirement, not a second
            # ownership decision.
            run.terminal_publisher = publisher
        with self._handler_lock:
            self._lifecycle_publishers.add(publisher)
        publisher.start()
        publisher.join(timeout=max(float(callback_timeout_seconds), 0.0))
        with self._handler_lock:
            self._lifecycle_publishers.intersection_update(
                thread
                for thread in self._lifecycle_publishers
                if thread.is_alive()
            )
        if not publisher.is_alive():
            with run.state_lock:
                if run.terminal_publisher is publisher:
                    run.terminal_publisher = None
        return not publisher.is_alive()

    def complete_validation_item(
        self,
        command_identity: str,
        item_id: str,
        *,
        succeeded: bool,
        outcome: str,
    ) -> bool:
        with self._boundary_lock:
            boundary_group = next(
                (
                    group
                    for group, bound_item_id in self._boundary_items.items()
                    if bound_item_id == item_id
                    and (
                        self._validation_runs.get(group).command_identity
                        if self._validation_runs.get(group) is not None
                        else ""
                    )
                    == command_identity
                ),
                None,
            )
        if boundary_group is None:
            return False
        with self._boundary_lock:
            run = self._validation_runs.get(boundary_group)
        if run is None:
            return False
        with run.state_lock:
            if run.terminal_outcome:
                return False
            run.launch_state = "terminated"
            run.terminal_outcome = outcome
            run.terminal_succeeded = succeeded
        return self._complete_validation_group(
            boundary_group,
            succeeded=succeeded,
            outcome=outcome,
        )

    def stop(self, *, cleanup_outcome: str = "authority_withdrawn") -> bool:
        # Stop accepting first, then close every tracked peer before taking
        # the publication lock. A REGISTER send blocked inside that critical
        # section is thereby interrupted and can release the lock; a send that
        # completed first is the fully accepted side of the race.
        normalized_cleanup = str(cleanup_outcome or "").strip().casefold()
        if normalized_cleanup not in {
            "authority_withdrawn",
            "session_error",
            "stream_error",
            "timed_out",
            "transport_error",
        }:
            normalized_cleanup = "transport_error"
        # Publish the cause before disturbing any transport. A handler whose
        # sendmsg is interrupted can then retain the operator/session reason
        # instead of mislabelling cleanup as an independent transport fault.
        self._requested_cleanup_outcome = normalized_cleanup
        self._cleanup_requested.set()
        with contextlib.suppress(OSError):
            self._listener.close()
        # A cancelled session must not leave a connectable endpoint behind.
        # Its random directory carries no executable guard state and can be
        # removed as soon as the endpoint is unlinked; descendants already
        # fail closed when their next connection cannot resolve the socket.
        external_socket = (
            _validated_external_broker_socket(
                self.socket_path,
                self.socket_cleanup_dir,
            )
            if self.socket_cleanup_dir is not None
            else None
        )
        if self.socket_path.parent == self.root or external_socket is not None:
            with contextlib.suppress(OSError):
                self.socket_path.unlink()
        if external_socket is not None:
            with contextlib.suppress(OSError):
                external_socket[1].rmdir()
        if self._thread is not threading.current_thread():
            self._thread.join()
        with self._handler_lock:
            connections = tuple(self._handler_connections)
            handlers = tuple(self._handler_threads)
        for connection in connections:
            with contextlib.suppress(OSError):
                connection.shutdown(socket.SHUT_RDWR)
            with contextlib.suppress(OSError):
                connection.close()
        with self._boundary_lock:
            self._stop.set()
            descriptor = self._capability_fd
            self._capability_fd = None
            self._provider_identity = None
            self._capability_secret = None
            self._capability_identity = None
            cleanup_runs = tuple(self._validation_runs.values())
        # Close peers before taking a run's linearization lock so a blocked
        # descriptor send is interrupted. Preparing runs are then atomically
        # terminated before the cancellation fence wakes their supervisors.
        for run in cleanup_runs:
            with run.state_lock:
                run.cleanup_outcome = normalized_cleanup
                if run.launch_state == "preparing" and not run.terminal_outcome:
                    run.launch_state = "terminated"
        with contextlib.suppress(OSError):
            (self.root / _CANCELLATION_NAME).touch(mode=0o600, exist_ok=True)
        handler_deadline = time.monotonic() + 0.5
        for handler in handlers:
            if handler is not threading.current_thread():
                handler.join(
                    timeout=max(handler_deadline - time.monotonic(), 0.0)
                )
        with self._handler_lock:
            self._handler_connections.difference_update(connections)
            self._handler_threads.difference_update(
                handler for handler in handlers if not handler.is_alive()
            )
            handlers_exited = not self._handler_threads
            supervisor_observers = tuple(self._supervisor_observers)
        # Each supervisor claims timeout/withdrawal/transport status before
        # releasing its descriptor. Give those short claim/ACK phases one
        # shared bounded drain window before assigning the retirement fallback.
        # The observer may remain alive only in post-claim lifecycle telemetry;
        # retirement must never wait indefinitely for that user callback.
        observer_deadline = time.monotonic() + 0.5
        for observer in supervisor_observers:
            if observer is not threading.current_thread():
                observer.join(
                    timeout=max(observer_deadline - time.monotonic(), 0.0)
                )
        with self._handler_lock:
            self._supervisor_observers.difference_update(
                observer for observer in supervisor_observers if not observer.is_alive()
            )
            observers_exited = not self._supervisor_observers
            supervisor_processes = tuple(self._supervisor_processes)
        # A guard root contains executable shims. Do not scan or delete it
        # until every locally-started supervisor has exited; before exec its
        # /proc references can otherwise race the scan. This wait is bounded:
        # an uncooperative supervisor retains the root for a later retry.
        supervisor_deadline = time.monotonic() + 2.0
        supervisors_exited = True
        for process in supervisor_processes:
            if process.poll() is not None:
                continue
            try:
                process.wait(
                    timeout=max(supervisor_deadline - time.monotonic(), 0.0)
                )
            except subprocess.TimeoutExpired:
                supervisors_exited = False
        with self._handler_lock:
            self._supervisor_processes.difference_update(
                process
                for process in supervisor_processes
                if process.poll() is not None
            )
            supervisors_exited = (
                supervisors_exited and not self._supervisor_processes
            )
        with self._boundary_lock:
            lifecycle_groups = tuple(self._validation_runs)
        publication_deadline = time.monotonic() + 0.5
        callbacks_published = True
        for boundary_group in lifecycle_groups:
            with self._boundary_lock:
                run = self._validation_runs.get(boundary_group)
            if run is None:
                continue
            with run.state_lock:
                outcome = run.terminal_outcome
                if not outcome:
                    outcome = (
                        normalized_cleanup
                        if run.supervisor_outcome != "exited"
                        or normalized_cleanup != "authority_withdrawn"
                        else "stream_error"
                    )
                    run.launch_state = "terminated"
                    run.terminal_outcome = outcome
                    run.terminal_succeeded = False
                succeeded = run.terminal_succeeded
            callbacks_published = self._complete_validation_group(
                boundary_group,
                succeeded=succeeded,
                outcome=outcome,
                # Never let a user telemetry callback extend retirement.
                # The daemon publisher preserves started-before-completed; a
                # false return keeps this guard root for durable retry.
                callback_timeout_seconds=max(
                    publication_deadline - time.monotonic(),
                    0.0,
                ),
            ) and callbacks_published
        with self._handler_lock:
            lifecycle_publishers = tuple(self._lifecycle_publishers)
        for publisher in lifecycle_publishers:
            if publisher is threading.current_thread():
                continue
            publisher.join(
                timeout=max(publication_deadline - time.monotonic(), 0.0)
            )
        with self._handler_lock:
            self._lifecycle_publishers.difference_update(
                publisher
                for publisher in lifecycle_publishers
                if not publisher.is_alive()
            )
            callbacks_published = (
                not self._lifecycle_publishers and callbacks_published
            )
        if descriptor is not None:
            with contextlib.suppress(OSError):
                os.close(descriptor)
        # A false return deliberately leaves the broker registered. The next
        # durable retirement retry can re-close peers and verify every actor
        # has quiesced before the guard root becomes deletable.
        return (
            handlers_exited
            and observers_exited
            and supervisors_exited
            and callbacks_published
        )

    def consume_recent_boundary(
        self,
        command_identity: str,
        item_id: str,
        *,
        max_age_seconds: float = 5.0,
    ) -> bool:
        cutoff = time.monotonic() - max(float(max_age_seconds), 0.1)
        with self._boundary_lock:
            if not item_id or item_id in self._bound_item_ids:
                return False
            while self._boundaries and self._boundaries[0][0] < cutoff:
                self._boundaries.popleft()
            match = next(
                (
                    boundary
                    for boundary in self._boundaries
                    if boundary[2] == command_identity
                ),
                None,
            )
            if match is None:
                return False
            # One provider command can legitimately contain nested guarded
            # shells in one process group. Coalesce only that group's proof;
            # receipts from genuinely parallel command groups must remain for
            # their own command_execution items.
            _timestamp, boundary_group, _identity = match
            self._boundaries = deque(
                boundary
                for boundary in self._boundaries
                if boundary[1] != boundary_group
            )
            self._bound_item_ids.add(item_id)
            self._boundary_items[boundary_group] = item_id
            return True


def _start_native_validation_broker(
    root: Path,
    *,
    socket_path: Path,
    socket_cleanup_dir: Path | None = None,
    validation_lease: ValidationResourceLease,
    owner: ValidationLeaseOwner,
    timeout_seconds: float,
    validation_reuse_policy: Mapping[str, Any] | None = None,
    validation_reuse_authority_check: Callable[[], object] | None = None,
    validation_reuse_policy_handler: Callable[..., object] | None = None,
    validation_command_handler: Callable[..., object] | None = None,
    executable_search_path: str | None = None,
    untrusted_executable_roots: tuple[str | os.PathLike[str], ...] = (),
) -> _NativeValidationLeaseBroker:
    broker = _NativeValidationLeaseBroker(
        root,
        socket_path=socket_path,
        socket_cleanup_dir=socket_cleanup_dir,
        validation_lease=validation_lease,
        owner=owner,
        timeout_seconds=timeout_seconds,
        validation_reuse_policy=validation_reuse_policy,
        validation_reuse_authority_check=validation_reuse_authority_check,
        validation_reuse_policy_handler=validation_reuse_policy_handler,
        validation_command_handler=validation_command_handler,
        executable_search_path=executable_search_path,
        untrusted_executable_roots=untrusted_executable_roots,
    )
    with _BROKER_REGISTRY_LOCK:
        previous = _BROKER_REGISTRY.setdefault(root.resolve(), broker)
    if previous is not broker:
        broker.stop(cleanup_outcome="transport_error")
        raise RuntimeError("native validation broker already exists")
    return broker


def _stop_native_validation_broker(
    root: Path,
    *,
    cleanup_outcome: str = "authority_withdrawn",
) -> bool:
    with _BROKER_REGISTRY_LOCK:
        resolved_root = root.resolve()
        broker = _BROKER_REGISTRY.get(resolved_root)
    if broker is not None:
        stopped = broker.stop(cleanup_outcome=cleanup_outcome)
        if stopped:
            with _BROKER_REGISTRY_LOCK:
                if _BROKER_REGISTRY.get(resolved_root) is broker:
                    _BROKER_REGISTRY.pop(resolved_root, None)
        return stopped
    return True


def consume_native_validation_boundary(
    runtime_root: str | os.PathLike[str],
    command: str,
    item_id: str,
) -> bool:
    """Consume proof that this exact provider command reached the guard."""

    with _BROKER_REGISTRY_LOCK:
        broker = _BROKER_REGISTRY.get(Path(runtime_root).resolve())
    return broker is not None and broker.consume_recent_boundary(
        _command_identity(command),
        str(item_id),
    )


def complete_native_validation_command(
    runtime_root: str | os.PathLike[str],
    command: str,
    item_id: str,
    *,
    succeeded: bool,
    outcome: str,
) -> bool:
    """Complete lifecycle telemetry for a bound native command item."""

    with _BROKER_REGISTRY_LOCK:
        broker = _BROKER_REGISTRY.get(Path(runtime_root).resolve())
    return broker is not None and broker.complete_validation_item(
        _command_identity(command),
        str(item_id),
        succeeded=bool(succeeded),
        outcome=str(outcome or ""),
    )


def native_validation_provider_launcher(
    runtime_root: str | os.PathLike[str],
) -> str:
    """Return the trusted direct-provider launcher installed in this root."""

    return str(
        Path(runtime_root).resolve()
        / "validation-guard-bin"
        / _PROVIDER_LAUNCHER_NAME
    )


def _python_command_names(search_path: str) -> set[str]:
    """Return interpreter names present on PATH that the classifier knows."""

    names = {"python", "python3"}
    for raw_directory in search_path.split(os.pathsep):
        directory = Path(raw_directory or ".")
        try:
            entries = tuple(directory.iterdir())
        except OSError:
            # PATH commonly retains optional package-manager directories that
            # are absent on a particular host (for example /snap/bin on a
            # GitHub runner).  Command discovery must tolerate those stale
            # entries just like shutil.which does.
            continue
        for entry in entries:
            name = entry.name
            suffix = name[6:] if name.startswith("python") else ""
            if suffix and suffix.replace(".", "").isdigit():
                names.add(name)
    return names


def install_native_validation_guard(
    environment: Mapping[str, str],
    *,
    runtime_root: str | os.PathLike[str],
    broker_socket: str | os.PathLike[str] | None = None,
    broker_socket_cleanup_dir: str | os.PathLike[str] | None = None,
    validation_lease: ValidationResourceLease,
    owner: ValidationLeaseOwner,
    timeout_seconds: float,
    provider_bootstrap_entrypoint: str | os.PathLike[str] | None = None,
    provider_bootstrap_interpreter: str | os.PathLike[str] | None = None,
    provider_bootstrap_entrypoint_identity: tuple[int, int] | None = None,
    provider_bootstrap_entrypoint_fd: int | None = None,
    provider_untrusted_roots: tuple[str | os.PathLike[str], ...] = (),
    validation_reuse_policy: Mapping[str, Any] | None = None,
    validation_reuse_authority_check: Callable[[], object] | None = None,
    validation_reuse_policy_handler: Callable[..., object] | None = None,
    validation_command_handler: Callable[..., object] | None = None,
) -> tuple[dict[str, str], Path]:
    """Return an environment whose validation launchers are command guarded.

    Configuration is stored beside the shims in an operator-created directory
    rather than trusted from shell-set environment fields.  The sole marker in
    the environment names the guard directory; every shim derives the config
    path from its own invocation path and fails closed if it is unavailable.
    """

    guarded = {
        str(name): str(value)
        for name, value in environment.items()
        if str(name) not in _UNTRUSTED_SHELL_STARTUP_ENV_NAMES
        and not str(name).startswith("BASH_FUNC_")
        and not _is_dynamic_loader_environment_name(str(name))
    }
    # These are per-command policy inputs, never ambient provider authority.
    # A model must opt into a distinct run on the exact native invocation.
    guarded.pop(_VALIDATION_MODE_ENV, None)
    guarded.pop(_VALIDATION_JUSTIFICATION_ENV, None)
    original_path = str(guarded.get("PATH") or os.defpath)
    untrusted_roots = tuple(
        Path(candidate).resolve() for candidate in provider_untrusted_roots
    )
    root = Path(runtime_root).resolve()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    root.chmod(0o700)
    guard_bin = root / "validation-guard-bin"
    guard_bin.mkdir(mode=0o700, parents=True, exist_ok=False)
    native_home = root / _NATIVE_HOME_NAME
    native_home.mkdir(mode=0o700, exist_ok=False)
    bash_env = root / _BASH_ENV_NAME
    bash_reentry_env = root / _BASH_REENTRY_NAME
    creator_pid = os.getpid()
    creator_start_ticks = _process_start_ticks(creator_pid)
    if creator_start_ticks is None:
        raise RuntimeError("cannot fence native validation guard creator")
    config = {
        "state_path": str(validation_lease.state_path),
        "capacity": validation_lease.capacity,
        "aging_seconds": validation_lease.aging_seconds,
        "poll_seconds": validation_lease.poll_seconds,
        # The runtime clock begins only after the command owns capacity.  Guard
        # installation happens before model reasoning and must not consume it.
        "timeout_seconds": max(float(timeout_seconds), 1.0),
        "path": original_path,
        "shell": str(guarded.get("SHELL") or "/bin/sh"),
        "bash_env": str(bash_env),
        "bash_reentry_env": str(bash_reentry_env),
        "cancellation_path": str(root / _CANCELLATION_NAME),
        "untrusted_executable_roots": [str(candidate) for candidate in untrusted_roots],
        "creator": {
            "pid": creator_pid,
            "start_ticks": creator_start_ticks,
        },
        "opaque_process_baseline": [
            [pid, start_ticks]
            for pid, start_ticks in _opaque_same_user_process_baseline()
        ],
        "owner": {
            "kind": owner.kind,
            "project_id": owner.project_id,
            "task_id": owner.task_id,
            "authority_generation": owner.authority_generation,
            "priority": owner.priority,
        },
    }
    if (
        provider_bootstrap_entrypoint is None
        and provider_bootstrap_interpreter is not None
    ):
        raise RuntimeError(
            "native provider bootstrap interpreter requires an entrypoint"
        )
    if (
        provider_bootstrap_entrypoint is None
        and (
            provider_bootstrap_entrypoint_identity is not None
            or provider_bootstrap_entrypoint_fd is not None
        )
    ):
        raise RuntimeError(
            "native provider bootstrap identity requires an entrypoint"
        )
    if provider_bootstrap_entrypoint is not None:
        entrypoint = Path(provider_bootstrap_entrypoint).resolve(strict=True)
        interpreter = (
            Path(provider_bootstrap_interpreter).resolve(strict=True)
            if provider_bootstrap_interpreter is not None
            else None
        )
        for trusted_path in (
            entrypoint,
            *((interpreter,) if interpreter is not None else ()),
        ):
            if any(
                trusted_path == untrusted_root
                or untrusted_root in trusted_path.parents
                for untrusted_root in untrusted_roots
            ):
                raise RuntimeError(
                    "native provider bootstrap executable is task-writable"
                )
        entrypoint_stat = (
            os.fstat(provider_bootstrap_entrypoint_fd)
            if provider_bootstrap_entrypoint_fd is not None
            else entrypoint.stat()
        )
        interpreter_stat = interpreter.stat() if interpreter is not None else None
        if interpreter is None and provider_bootstrap_entrypoint_fd is None:
            raise RuntimeError(
                "native direct provider bootstrap requires a pinned entrypoint "
                "descriptor"
            )
        if (
            provider_bootstrap_entrypoint_identity is not None
            and (
                int(entrypoint_stat.st_dev),
                int(entrypoint_stat.st_ino),
            )
            != tuple(int(value) for value in provider_bootstrap_entrypoint_identity)
        ):
            raise RuntimeError(
                "native provider bootstrap entrypoint identity changed"
            )
        config["provider_bootstrap"] = {
            # The Codex npm launcher uses ``#!/usr/bin/env node``.  Its first
            # process therefore resolves through the guarded PATH before the
            # provider has started.  Permit only that exact operator-installed
            # entrypoint, only for the ``exec`` provider subcommand, and only
            # when it is spawned directly by this exact service process.
            "command": (
                "node" if interpreter is not None else _PROVIDER_LAUNCHER_NAME
            ),
            "entrypoint": str(entrypoint),
            "entrypoint_device": int(entrypoint_stat.st_dev),
            "entrypoint_inode": int(entrypoint_stat.st_ino),
            "parent_pid": creator_pid,
            "parent_start_ticks": creator_start_ticks,
            "subcommand": "exec",
        }
        if provider_bootstrap_entrypoint_fd is not None:
            config["provider_bootstrap"]["source_fd"] = int(
                provider_bootstrap_entrypoint_fd
            )
        if interpreter is not None and interpreter_stat is not None:
            config["provider_bootstrap"].update(
                {
                    "interpreter": str(interpreter),
                    "interpreter_device": int(interpreter_stat.st_dev),
                    "interpreter_inode": int(interpreter_stat.st_ino),
                }
            )
    config_path = root / _CONFIG_NAME

    launcher = guard_bin / "oompah-validation-guard"
    trusted_source_root = str(Path(__file__).resolve().parents[1])
    launcher.write_text(
        # Isolated mode ignores PYTHONPATH and the candidate working directory.
        # Insert only the deployed package root before importing the guard.
        f"#!{sys.executable} -I\n"
        "import sys\n"
        f"sys.path.insert(0, {trusted_source_root!r})\n"
        "from oompah.native_validation_guard import main\n"
        "raise SystemExit(main())\n",
        encoding="utf-8",
    )
    launcher.chmod(stat.S_IRUSR | stat.S_IXUSR)
    for command in sorted(
        _WRAPPED_COMMANDS
        | _python_command_names(original_path)
        | {_PROVIDER_LAUNCHER_NAME, _SUPERVISOR_LAUNCHER_NAME}
    ):
        (guard_bin / command).symlink_to(launcher.name)

    # Codex's native command runner currently launches every command through
    # an absolute non-interactive Bash below the SDK process.  BASH_ENV is the
    # only boundary reached before Bash evaluates its command or script.  Read
    # the kernel-owned argv vector rather than rebuilding ``bash -c`` from
    # BASH_EXECUTION_STRING: the latter loses option flags and argv boundaries.
    # The marker check also makes a retained hook fail closed after its session
    # authority has been withdrawn.
    guard_bash = shlex.quote(str(guard_bin / "bash"))
    cancellation = shlex.quote(str(root / _CANCELLATION_NAME))
    bash_env.write_text(
        f"if [ -e {cancellation} ]; then\n"
        "  exit 125\n"
        "fi\n"
        "if [ -n \"${OOMPAH_NATIVE_VALIDATION_GUARD:-}\" ]; then\n"
        "  _oompah_validation_argv=()\n"
        "  while IFS= read -r -d '' _oompah_validation_arg; do\n"
        "    _oompah_validation_argv+=(\"$_oompah_validation_arg\")\n"
        "  done < /proc/$$/cmdline\n"
        "  if [ \"${#_oompah_validation_argv[@]}\" -lt 1 ]; then\n"
        "    exit 125\n"
        "  fi\n"
        f"  export {_BASH_ARGV0_ENV}=\"${{_oompah_validation_argv[0]}}\"\n"
        f"  exec {guard_bash} \"${{_oompah_validation_argv[@]:1}}\"\n"
        "fi\n",
        encoding="utf-8",
    )
    bash_env.chmod(stat.S_IRUSR)
    # The real Bash exec must not source the primary hook recursively.  This
    # one-shot hook restores the primary path in its own environment before
    # the command runs, so every absolute Bash descendant is guarded again.
    bash_reentry_env.write_text(
        f"export BASH_ENV={shlex.quote(str(bash_env))}\n",
        encoding="utf-8",
    )
    bash_reentry_env.chmod(stat.S_IRUSR)

    guarded["PATH"] = f"{guard_bin}{os.pathsep}{original_path}"
    # Absolute Bash login shells read HOME/.bash_profile before BASH_ENV, which
    # is otherwise the earliest interception point available below the Codex
    # provider.  Never let a task-supplied HOME run startup code before the
    # command reaches the classifier and (when heavy) the lease boundary.
    # Codex configuration/authentication has its own canonical override, so
    # preserve that location explicitly while HOME becomes an operator-owned,
    # empty directory outside every task-writable root.
    trusted_codex_home = str(os.environ.get("CODEX_HOME") or "").strip()
    if not trusted_codex_home:
        trusted_codex_home = str(Path.home() / ".codex")
    guarded["CODEX_HOME"] = trusted_codex_home
    guarded["HOME"] = str(native_home)
    # zsh resolves its user startup directory independently of HOME when this
    # variable is present.  Pin it to the same empty trusted directory rather
    # than retaining a task-controlled override.
    guarded["ZDOTDIR"] = str(native_home)
    # Codex's native command runner consults SHELL for compound invocations.
    # Pointing it at the trusted wrapper lets the wrapper classify the complete
    # shell program before any absolute/project-local child can bypass PATH.
    guarded["SHELL"] = str(guard_bin / "bash")
    guarded["BASH_ENV"] = str(bash_env)
    guarded[_GUARD_ENV] = str(guard_bin)
    guarded.pop(_BOUNDARY_GROUP_ENV, None)
    guarded.pop(_CAPABILITY_FD_ENV, None)
    automatic_cleanup_dir: Path | None = None
    socket_path = root / _BROKER_SOCKET_NAME
    try:
        if broker_socket is None:
            broker_socket, cleanup_dir = create_native_validation_broker_socket(
                runtime_root=root,
                untrusted_roots=untrusted_roots,
            )
            automatic_cleanup_dir = cleanup_dir
        else:
            cleanup_dir = (
                Path(broker_socket_cleanup_dir)
                if broker_socket_cleanup_dir is not None
                else None
            )
        if broker_socket is not None:
            socket_path = Path(broker_socket)
        socket_path = _broker_socket_path(root, broker_socket)
        if cleanup_dir is None:
            if socket_path.parent != root:
                raise RuntimeError("native validation broker socket escaped guard root")
        else:
            validated_external = _validated_external_broker_socket(
                socket_path,
                cleanup_dir,
            )
            if validated_external is None:
                raise RuntimeError(
                    "native validation broker cleanup directory is invalid"
                )
            socket_path, cleanup_dir = validated_external
        config["broker_socket"] = str(socket_path)
        if cleanup_dir is not None:
            config["broker_socket_cleanup_dir"] = str(cleanup_dir)
        broker = _start_native_validation_broker(
            root,
            socket_path=socket_path,
            socket_cleanup_dir=cleanup_dir,
            validation_lease=validation_lease,
            owner=owner,
            timeout_seconds=timeout_seconds,
            validation_reuse_policy=validation_reuse_policy,
            validation_reuse_authority_check=validation_reuse_authority_check,
            validation_reuse_policy_handler=validation_reuse_policy_handler,
            validation_command_handler=validation_command_handler,
            executable_search_path=original_path,
            untrusted_executable_roots=provider_untrusted_roots,
        )
        # Bind the protected endpoint before its path becomes visible in the
        # immutable config.  No command process receives this environment
        # until this function returns, so there is no pre-config consumer.
        config_path.write_text(json.dumps(config, sort_keys=True), encoding="utf-8")
        config_path.chmod(0o400)
        if provider_bootstrap_entrypoint is None:
            capability_descriptor = broker.issue_local_test_capability()
            guarded[_CAPABILITY_FD_ENV] = str(capability_descriptor)
    except BaseException:
        # Installation has not returned an owner capable of retiring this
        # root. Do not strand its broker listener/thread after bootstrap fails.
        _stop_native_validation_broker(root, cleanup_outcome="transport_error")
        if automatic_cleanup_dir is not None:
            _cleanup_validated_external_broker_socket(
                socket_path,
                automatic_cleanup_dir,
            )
        raise
    return guarded, root


def _load_verified_guard_config(root: Path) -> dict[str, object]:
    """Load one immutable, owner-only regular guard configuration."""

    config_path = root / _CONFIG_NAME
    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(config_path, flags)
    except OSError as exc:
        raise RuntimeError(
            "native validation guard configuration is unavailable"
        ) from exc
    try:
        info = os.fstat(descriptor)
        if (
            not stat.S_ISREG(info.st_mode)
            or int(info.st_uid) != os.geteuid()
            or stat.S_IMODE(info.st_mode) != stat.S_IRUSR
            or int(info.st_nlink) != 1
        ):
            raise RuntimeError(
                "native validation guard configuration has unsafe permissions"
            )
        with os.fdopen(os.dup(descriptor), encoding="utf-8") as config_file:
            raw = json.load(config_file)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "native validation guard configuration is invalid"
        ) from exc
    finally:
        os.close(descriptor)
    if not isinstance(raw, dict):
        raise RuntimeError("native validation guard configuration is invalid")
    return raw


def _load_invocation_config(argv0: str) -> tuple[dict[str, object], Path]:
    guard_bin = Path(os.path.abspath(argv0)).parent
    # Reject a shell-selected lookalike config.  The service creates this file
    # owner-readable and immutable to the sandboxed agent.
    return _load_verified_guard_config(guard_bin.parent), guard_bin


def _real_executable(command: str, search_path: str, guard_bin: Path) -> str:
    clean_path = os.pathsep.join(
        part
        for part in search_path.split(os.pathsep)
        if Path(part or ".").resolve() != guard_bin.resolve()
    )
    resolved = shutil.which(command, path=clean_path)
    if not resolved:
        raise RuntimeError(f"guarded executable is unavailable: {command}")
    return resolved


def _process_start_ticks(pid: int) -> int | None:
    """Return Linux process start ticks for exact bootstrap-parent fencing."""

    try:
        raw = Path(f"/proc/{int(pid)}/stat").read_text(encoding="utf-8")
        return int(raw[raw.rfind(")") + 2 :].split()[19])
    except (OSError, ValueError, IndexError):
        return None


def _trusted_provider_bootstrap_interpreter(
    command: str,
    arguments: list[str],
    config: Mapping[str, object],
) -> str | None:
    """Recognize only the exact service-launched Codex npm bootstrap.

    A path/argv match alone would let a task launch the installed Codex entry
    point and escape command-scoped validation.  The direct parent PID and
    Linux start ticks bind this exception to the service process that created
    the read-only guard configuration.  All provider descendants and
    task-controlled lookalikes continue through normal heavyweight
    classification.
    """

    raw = config.get("provider_bootstrap")
    if not isinstance(raw, dict) or command != str(raw.get("command") or ""):
        return None
    if len(arguments) < 2 or arguments[1] != str(raw.get("subcommand") or ""):
        return None
    try:
        expected_parent = int(raw["parent_pid"])
        expected_ticks = int(raw["parent_start_ticks"])
        expected_device = int(raw["entrypoint_device"])
        expected_inode = int(raw["entrypoint_inode"])
        expected_entrypoint = Path(str(raw["entrypoint"])).resolve(strict=True)
        expected_interpreter = Path(str(raw["interpreter"])).resolve(strict=True)
        invoked_entrypoint = Path(arguments[0]).resolve(strict=True)
        invoked_stat = invoked_entrypoint.stat()
        interpreter_stat = expected_interpreter.stat()
        expected_interpreter_device = int(raw["interpreter_device"])
        expected_interpreter_inode = int(raw["interpreter_inode"])
    except (KeyError, OSError, TypeError, ValueError):
        return None
    parent_pid = os.getppid()
    trusted = (
        parent_pid == expected_parent
        and _process_start_ticks(parent_pid) == expected_ticks
        and invoked_entrypoint == expected_entrypoint
        and int(invoked_stat.st_dev) == expected_device
        and int(invoked_stat.st_ino) == expected_inode
        and int(interpreter_stat.st_dev) == expected_interpreter_device
        and int(interpreter_stat.st_ino) == expected_interpreter_inode
    )
    return str(expected_interpreter) if trusted else None


def _receive_descriptors(
    client: socket.socket,
    *,
    expected_payload: bytes,
    expected_count: int,
) -> tuple[int, ...]:
    descriptor_size = array.array("i", [0]).itemsize
    ancillary_size = socket.CMSG_SPACE(descriptor_size * expected_count)
    flags = getattr(socket, "MSG_CMSG_CLOEXEC", 0)
    payload, ancillary, message_flags, _address = client.recvmsg(
        64,
        ancillary_size,
        flags,
    )
    descriptors: list[int] = []
    malformed = bool(
        message_flags
        & (getattr(socket, "MSG_CTRUNC", 0) | getattr(socket, "MSG_TRUNC", 0))
    )
    for level, kind, data in ancillary:
        if level != socket.SOL_SOCKET or kind != socket.SCM_RIGHTS:
            malformed = True
            continue
        values = array.array("i")
        if not data or len(data) % values.itemsize:
            malformed = True
            continue
        values.frombytes(data[: len(data) - (len(data) % values.itemsize)])
        descriptors.extend(values)
    denial = _BROKER_DENIAL_MESSAGES.get(payload)
    if denial is not None and not descriptors and not malformed:
        raise RuntimeError(denial)
    if (
        payload != expected_payload
        or len(descriptors) != expected_count
        or malformed
    ):
        for descriptor in descriptors:
            with contextlib.suppress(OSError):
                os.close(descriptor)
        raise RuntimeError("native validation broker descriptor reply is invalid")
    return tuple(descriptors)


def _receive_single_descriptor(
    client: socket.socket,
    *,
    expected_payload: bytes,
) -> int:
    return _receive_descriptors(
        client,
        expected_payload=expected_payload,
        expected_count=1,
    )[0]


def _broker_socket(config: Mapping[str, object]) -> socket.socket:
    raw_path = str(config.get("broker_socket") or "").strip()
    if not raw_path:
        raise RuntimeError("native validation lease broker is unavailable")
    socket_path = Path(raw_path)
    raw_cleanup = str(config.get("broker_socket_cleanup_dir") or "").strip()
    if raw_cleanup:
        if _validated_external_broker_socket(
            socket_path,
            Path(raw_cleanup),
        ) != (socket_path, Path(raw_cleanup)):
            raise RuntimeError("native validation broker socket boundary is unsafe")
    else:
        cancellation_path = Path(str(config.get("cancellation_path") or ""))
        if (
            not socket_path.is_absolute()
            or cancellation_path.name != _CANCELLATION_NAME
            or socket_path != cancellation_path.parent / _BROKER_SOCKET_NAME
        ):
            raise RuntimeError("native validation broker socket boundary is unsafe")
    client = socket.socket(socket.AF_UNIX, _BROKER_SOCKET_TYPE)
    try:
        client.connect(str(socket_path))
    except BaseException:
        client.close()
        raise
    return client


def _register_native_validation_provider(
    config: Mapping[str, object],
) -> tuple[int, int | None]:
    bootstrap = config.get("provider_bootstrap")
    direct = (
        isinstance(bootstrap, dict)
        and bootstrap.get("command") == _PROVIDER_LAUNCHER_NAME
    )
    descriptors: tuple[int, ...] = ()
    try:
        with _broker_socket(config) as client:
            client.sendall(b"REGISTER\n")
            descriptors = _receive_descriptors(
                client,
                expected_payload=(
                    b"CAPABILITY-DIRECT\n" if direct else b"CAPABILITY\n"
                ),
                expected_count=2 if direct else 1,
            )
        for descriptor in descriptors:
            os.set_inheritable(descriptor, True)
        return descriptors[0], descriptors[1] if direct else None
    except BaseException:
        for descriptor in descriptors:
            with contextlib.suppress(OSError):
                os.close(descriptor)
        raise


def _capability_secret(descriptor: int | None = None) -> bytes:
    if descriptor is None:
        raw_descriptor = os.environ.get(_CAPABILITY_FD_ENV, "").strip()
        try:
            descriptor = int(raw_descriptor)
        except ValueError as exc:
            raise RuntimeError(
                "native validation provider capability is unavailable"
            ) from exc
    try:
        _capability_descriptor_identity(descriptor)
        secret = os.pread(descriptor, 32, 0)
    except (OSError, RuntimeError) as exc:
        raise RuntimeError(
            "native validation provider capability is unavailable"
        ) from exc
    if len(secret) != 32:
        raise RuntimeError("native validation provider capability is invalid")
    return secret


def _begin_boundary_request(
    client: socket.socket,
    *,
    request_kind: str,
    boundary_group: str,
    command_identity: str,
) -> None:
    request = (
        f"{request_kind} {boundary_group} {command_identity}\n".encode("ascii")
    )
    client.sendall(request)
    challenge_packet = _recv_packet(client, 128)
    recovered_capability = -1
    if challenge_packet == b"RECOVER\n":
        recovered_capability = _receive_single_descriptor(
            client,
            expected_payload=b"CAPABILITY\n",
        )
        challenge_packet = _recv_packet(client, 128)
    prefix = b"CHALLENGE "
    if (
        len(challenge_packet) != len(prefix) + 64 + 1
        or not challenge_packet.startswith(prefix)
        or not challenge_packet.endswith(b"\n")
    ):
        raise RuntimeError("native validation broker challenge is invalid")
    challenge = challenge_packet[:-1]
    try:
        nonce = bytes.fromhex(challenge[len(prefix) :].decode("ascii"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise RuntimeError("native validation broker challenge is invalid") from exc
    if len(nonce) != 32:
        raise RuntimeError("native validation broker challenge is invalid")
    start_ticks = _process_start_ticks(os.getpid())
    if start_ticks is None:
        raise RuntimeError("native validation peer identity is unavailable")
    try:
        proof = _capability_proof(
            _capability_secret(
                recovered_capability if recovered_capability >= 0 else None
            ),
            nonce=nonce,
            peer_pid=os.getpid(),
            peer_start_ticks=start_ticks,
            request=request,
        )
        client.sendall(f"PROVE {proof}\n".encode("ascii"))
    finally:
        if recovered_capability >= 0:
            with contextlib.suppress(OSError):
                os.close(recovered_capability)


def _request_native_validation_lease(
    config: Mapping[str, object],
    boundary_group: str,
    command_identity: str,
) -> int:
    """Wait for and inherit the brokered lease's open-file description."""

    with _broker_socket(config) as client:
        _begin_boundary_request(
            client,
            request_kind="ACQUIRE",
            boundary_group=boundary_group,
            command_identity=command_identity,
        )
        return _receive_single_descriptor(
            client,
            expected_payload=b"LEASE\n",
        )


def _report_native_validation_boundary(
    config: Mapping[str, object],
    boundary_group: str,
    command_identity: str,
) -> None:
    """Prove that a light provider command crossed the trusted shim boundary."""

    with _broker_socket(config) as client:
        _begin_boundary_request(
            client,
            request_kind="OBSERVE",
            boundary_group=boundary_group,
            command_identity=command_identity,
        )
        response = _recv_packet(client, 32)
    if response != b"OBSERVED\n":
        raise RuntimeError("native validation lease broker denied execution")


def _launch_direct_provider(config: Mapping[str, object]) -> int:
    raw = config.get("provider_bootstrap")
    if not isinstance(raw, dict) or raw.get("command") != _PROVIDER_LAUNCHER_NAME:
        raise RuntimeError("native validation direct provider is unavailable")
    try:
        entrypoint = Path(str(raw["entrypoint"])).resolve(strict=True)
        expected_device = int(raw["entrypoint_device"])
        expected_inode = int(raw["entrypoint_inode"])
    except (KeyError, OSError, TypeError, ValueError) as exc:
        raise RuntimeError(
            "native validation direct provider identity is invalid"
        ) from exc
    capability_descriptor = -1
    descriptor = -1
    try:
        capability_descriptor, registered_descriptor = (
            _register_native_validation_provider(config)
        )
        if registered_descriptor is None:
            raise RuntimeError(
                "native validation direct provider descriptor is unavailable"
            )
        descriptor = registered_descriptor
        actual = os.fstat(descriptor)
        if (
            int(actual.st_dev) != expected_device
            or int(actual.st_ino) != expected_inode
        ):
            raise RuntimeError("native validation direct provider identity changed")
        child_env = dict(os.environ)
        child_env[_CAPABILITY_FD_ENV] = str(capability_descriptor)
        os.set_inheritable(capability_descriptor, True)
        os.set_inheritable(descriptor, True)
        os.execve(
            f"/proc/{os.getpid()}/fd/{descriptor}",
            [str(entrypoint), *sys.argv[1:]],
            child_env,
        )
    finally:
        if descriptor >= 0:
            with contextlib.suppress(OSError):
                os.close(descriptor)
        if capability_descriptor >= 0:
            with contextlib.suppress(OSError):
                os.close(capability_descriptor)
    return 1


def _terminate_supervised_process_group(
    peer_pid: int,
    peer_start_ticks: int,
) -> bool:
    """Terminate only the exact supervised process-group generation.

    The numeric PID is never used as signal authority by itself. The shared
    helper enumerates the original group generation, signals only pidfd-pinned
    member identities, and proves that generation empty before returning.
    """

    return _terminate_exact_process_group(
        peer_pid,
        peer_start_ticks,
        grace_seconds=0.5,
    )


def _supervise_validation_lease(config: Mapping[str, object]) -> int:
    """Enforce authority withdrawal independently of the service process."""

    if len(sys.argv) != 8:
        raise RuntimeError("native validation supervisor arguments are invalid")
    peer_pid = int(sys.argv[1])
    peer_start_ticks = int(sys.argv[2])
    lease_descriptor = int(sys.argv[3])
    deadline_at = float(sys.argv[4])
    ready_descriptor = int(sys.argv[5])
    status_descriptor = int(sys.argv[6])
    acknowledgement_descriptor = int(sys.argv[7])
    pidfd = -1
    terminal_reported = False

    def report_terminal(outcome: str) -> None:
        nonlocal acknowledgement_descriptor
        nonlocal terminal_reported, status_descriptor
        if terminal_reported:
            return
        terminal_reported = True
        with contextlib.suppress(OSError):
            os.write(status_descriptor, f"{outcome}\n".encode("ascii"))
        with contextlib.suppress(OSError):
            os.close(status_descriptor)
        status_descriptor = -1
        # Process death is what lets the SDK publish item.completed. Keep the
        # supervised generation alive until the operator has committed this
        # more specific cause, so generic command failure cannot win merely
        # because its event thread was scheduled first. An operator crash
        # closes the other pipe end and yields EOF, preserving independent
        # fail-closed termination rather than stranding the supervisor.
        with contextlib.suppress(OSError):
            os.read(acknowledgement_descriptor, 16)
        with contextlib.suppress(OSError):
            os.close(acknowledgement_descriptor)
        acknowledgement_descriptor = -1

    try:
        try:
            pidfd = _pidfd_open(peer_pid)
        except (AttributeError, OSError) as exc:
            # The parent needs a bounded, typed diagnosis rather than an
            # ambiguous EOF which would otherwise be reported as a malformed
            # SCM_RIGHTS reply by the guarded client. In particular, ESRCH is
            # peer identity loss, while descriptor pressure and permission
            # failures are transport failures rather than lack of support.
            failure = _pidfd_supervision_failure(exc)
            packet = {
                _BrokerUnsupported: _SUPERVISOR_UNSUPPORTED,
                _BrokerIdentityLost: _SUPERVISOR_IDENTITY_LOST,
            }.get(type(failure), _SUPERVISOR_TRANSPORT_FAILURE)
            with contextlib.suppress(OSError):
                os.write(ready_descriptor, packet)
            raise failure from exc
        if _process_start_ticks(peer_pid) != peer_start_ticks:
            # This check follows pidfd acquisition: the numeric PID still
            # exists, but it is no longer the generation authorised by the
            # broker. Report it on the startup pipe and exit directly. Do not
            # use report_terminal here: the parent cannot send an ACK until it
            # has received startup readiness and started its observer.
            with contextlib.suppress(OSError):
                os.write(ready_descriptor, _SUPERVISOR_IDENTITY_LOST)
            with contextlib.suppress(OSError):
                os.close(ready_descriptor)
            ready_descriptor = -1
            # No terminal observer exists on this startup path. Close both
            # ends owned by the supervisor so ``finally`` cannot enter the
            # ACK protocol that only starts after READY reaches the parent.
            with contextlib.suppress(OSError):
                os.close(status_descriptor)
            status_descriptor = -1
            with contextlib.suppress(OSError):
                os.close(acknowledgement_descriptor)
            acknowledgement_descriptor = -1
            return 1
        os.write(ready_descriptor, _SUPERVISOR_READY)
        os.close(ready_descriptor)
        ready_descriptor = -1
        cancellation_path = Path(str(config.get("cancellation_path") or ""))
        while (
            _process_start_ticks(peer_pid) == peer_start_ticks
            and not cancellation_path.exists()
            and time.time() < deadline_at
        ):
            time.sleep(0.05)
        if _process_start_ticks(peer_pid) != peer_start_ticks:
            report_terminal("exited")
        elif cancellation_path.exists():
            report_terminal("authority_withdrawn")
        else:
            report_terminal("timed_out")
        while not _terminate_supervised_process_group(
            peer_pid,
            peer_start_ticks,
        ):
            # Never release the transferred flock on incomplete process-group
            # evidence. A later snapshot may prove the group empty or allow an
            # exact remaining member to be pidfd-signalled safely.
            time.sleep(0.05)
        # Close only this supervisor's duplicate. The heavyweight command and
        # every descendant that inherited its open-file description continue
        # owning the kernel fence until their own execution actually ends.
    except BaseException:
        report_terminal("transport_error")
        raise
    finally:
        if status_descriptor >= 0:
            report_terminal("transport_error")
        if ready_descriptor >= 0:
            with contextlib.suppress(OSError):
                os.close(ready_descriptor)
        if acknowledgement_descriptor >= 0:
            with contextlib.suppress(OSError):
                os.close(acknowledgement_descriptor)
        if pidfd >= 0:
            with contextlib.suppress(OSError):
                os.close(pidfd)
        with contextlib.suppress(OSError):
            os.close(lease_descriptor)
    return 0


def _start_validation_lease_supervisor(
    root: Path,
    *,
    peer_pid: int,
    peer_start_ticks: int,
    lease_descriptor: int,
    timeout_seconds: float,
    terminal_handler: Callable[[str], Callable[[], object] | None],
) -> threading.Thread:
    read_descriptor, write_descriptor = os.pipe2(os.O_CLOEXEC)
    try:
        status_read_descriptor, status_write_descriptor = os.pipe2(os.O_CLOEXEC)
    except BaseException:
        os.close(read_descriptor)
        os.close(write_descriptor)
        raise
    try:
        acknowledgement_read_descriptor, acknowledgement_write_descriptor = (
            os.pipe2(os.O_CLOEXEC)
        )
    except BaseException:
        os.close(read_descriptor)
        os.close(write_descriptor)
        os.close(status_read_descriptor)
        os.close(status_write_descriptor)
        raise
    process: subprocess.Popen[bytes] | None = None
    observer: threading.Thread | None = None
    observer_started = False
    try:
        deadline_at = time.time() + max(float(timeout_seconds), 1.0)
        process = subprocess.Popen(
            [
                str(root / "validation-guard-bin" / _SUPERVISOR_LAUNCHER_NAME),
                str(peer_pid),
                str(peer_start_ticks),
                str(lease_descriptor),
                repr(deadline_at),
                str(write_descriptor),
                str(status_write_descriptor),
                str(acknowledgement_read_descriptor),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            pass_fds=(
                lease_descriptor,
                write_descriptor,
                status_write_descriptor,
                acknowledgement_read_descriptor,
            ),
            start_new_session=True,
        )
        os.close(write_descriptor)
        write_descriptor = -1
        os.close(status_write_descriptor)
        status_write_descriptor = -1
        os.close(acknowledgement_read_descriptor)
        acknowledgement_read_descriptor = -1
        readable, _, _ = select.select([read_descriptor], [], [], 2.0)
        ready_packet = os.read(read_descriptor, 16) if readable else b""
        if ready_packet == _SUPERVISOR_UNSUPPORTED:
            raise _BrokerUnsupported("native validation pidfd supervision is unavailable")
        if ready_packet == _SUPERVISOR_IDENTITY_LOST:
            raise _BrokerIdentityLost(
                "native validation supervised peer changed identity"
            )
        if ready_packet == _SUPERVISOR_TRANSPORT_FAILURE:
            raise _BrokerTransportFailure(
                "native validation pidfd supervision failed"
            )
        if ready_packet != _SUPERVISOR_READY:
            raise RuntimeError("native validation lease supervisor did not start")
        threading.Thread(target=process.wait, daemon=True).start()

        def observe_terminal() -> None:
            publication: Callable[[], object] | None = None
            try:
                packet = os.read(status_read_descriptor, 64)
                outcome = packet.decode("ascii", errors="replace").strip()
                if outcome not in {
                    "authority_withdrawn",
                    "exited",
                    "timed_out",
                    "transport_error",
                }:
                    outcome = "transport_error"
                publication = terminal_handler(outcome)
            finally:
                # Only the atomic terminal claim is inside the ACK boundary.
                # User lifecycle publication follows ACK, so it cannot keep a
                # withdrawn/timed-out command alive or retain its lease.
                with contextlib.suppress(OSError):
                    os.write(acknowledgement_write_descriptor, b"ACK\n")
                with contextlib.suppress(OSError):
                    os.close(acknowledgement_write_descriptor)
                with contextlib.suppress(OSError):
                    os.close(status_read_descriptor)
            if publication is not None:
                publication()

        observer = threading.Thread(
            target=observe_terminal,
            name=f"native-validation-supervisor-status-{peer_pid}",
            daemon=True,
        )
        observer.start()
        observer_started = True
        setattr(observer, "_native_validation_supervisor_process", process)
        return observer
    except BaseException:
        if process is not None and process.poll() is None:
            process.kill()
            with contextlib.suppress(Exception):
                process.wait(timeout=1)
        raise
    finally:
        os.close(read_descriptor)
        if write_descriptor >= 0:
            os.close(write_descriptor)
        if status_write_descriptor >= 0:
            os.close(status_write_descriptor)
        if acknowledgement_read_descriptor >= 0:
            os.close(acknowledgement_read_descriptor)
        if not observer_started:
            os.close(status_read_descriptor)
            os.close(acknowledgement_write_descriptor)


def main() -> int:
    """Shim entry point.  Successful execution never returns."""

    command = Path(sys.argv[0]).name
    invocation = shlex.join([command, *(str(value) for value in sys.argv[1:])])
    config, guard_bin = _load_invocation_config(sys.argv[0])
    if command == _SUPERVISOR_LAUNCHER_NAME:
        return _supervise_validation_lease(config)
    if command == _PROVIDER_LAUNCHER_NAME:
        return _launch_direct_provider(config)
    search_path = str(config.get("path") or os.defpath)
    child_env = dict(os.environ)
    original_bash_argv0 = child_env.pop(_BASH_ARGV0_ENV, None)
    cancellation_raw = str(config.get("cancellation_path") or "").strip()
    if not cancellation_raw:
        raise RuntimeError("native validation cancellation fence is unavailable")
    cancellation_path = Path(cancellation_raw)

    def _cancelled() -> bool:
        return cancellation_path.exists() or os.getppid() == 1

    if _cancelled():
        raise RuntimeError("native validation authority was withdrawn before launch")
    if (
        command == "bash"
        and child_env.get(_GUARD_ENV)
        and child_env.get("BASH_ENV")
    ):
        reentry_path = str(config.get("bash_reentry_env") or "").strip()
        if not reentry_path:
            raise RuntimeError("native Bash validation re-entry hook is unavailable")
        child_env["BASH_ENV"] = reentry_path

    bootstrap_interpreter = _trusted_provider_bootstrap_interpreter(
        command,
        sys.argv[1:],
        config,
    )
    if bootstrap_interpreter is not None:
        # Keep the guarded PATH/SHELL in the provider environment: only its
        # bootstrap is exempt.  Genuine commands launched by the provider must
        # still resolve through these shims and acquire capacity themselves.
        # Execute the pre-resolved operator interpreter, never a PATH-selected
        # task lookalike.
        capability_descriptor, direct_descriptor = (
            _register_native_validation_provider(config)
        )
        if direct_descriptor is not None:
            os.close(direct_descriptor)
            raise RuntimeError(
                "native validation provider registration returned an "
                "unexpected direct descriptor"
            )
        child_env[_CAPABILITY_FD_ENV] = str(capability_descriptor)
        os.set_inheritable(capability_descriptor, True)
        os.execve(bootstrap_interpreter, [command, *sys.argv[1:]], child_env)

    executable = _real_executable(command, search_path, guard_bin)
    command_identity = _command_identity(_shim_command_text(command, sys.argv[1:]))

    # Give each provider command one stable identity before it reports the
    # boundary. Nested guarded Bash descendants inherit the value, allowing
    # the broker to coalesce their proof without discarding receipts from
    # genuinely parallel commands. This grouping token does not grant lease
    # authority; the broker independently fences heavyweight peer PID/start
    # identity and process-group leadership.
    inherited_group = child_env.get(_BOUNDARY_GROUP_ENV)
    if inherited_group is None:
        start_ticks = _process_start_ticks(os.getpid())
        if start_ticks is None:
            raise RuntimeError("native validation boundary identity is unavailable")
        boundary_group = f"{os.getpid()}:{start_ticks}"
        child_env[_BOUNDARY_GROUP_ENV] = boundary_group
        if os.getpgrp() != os.getpid():
            os.setpgid(0, 0)
        if os.getpgrp() != os.getpid():
            raise RuntimeError(
                "native validation boundary lacks a dedicated process group"
            )
    else:
        group_identity = _decode_boundary_group(inherited_group)
        if group_identity is None or os.getpgrp() != group_identity[0]:
            raise RuntimeError(
                "native validation boundary group is invalid"
            )
        boundary_group = inherited_group

    raw_untrusted_roots = config.get("untrusted_executable_roots")
    untrusted_executable_roots = (
        tuple(str(value) for value in raw_untrusted_roots)
        if isinstance(raw_untrusted_roots, list)
        else ()
    )
    if not is_heavyweight_validation_command(
        invocation,
        executable_search_path=search_path,
        untrusted_executable_roots=untrusted_executable_roots,
        command_environment=child_env,
        working_directory=Path.cwd(),
    ):
        if _cancelled():
            raise RuntimeError("native validation authority was withdrawn before exec")
        _report_native_validation_boundary(
            config,
            boundary_group,
            command_identity,
        )
        if _cancelled():
            raise RuntimeError("native validation authority was withdrawn before exec")
        child_env.pop(_VALIDATION_MODE_ENV, None)
        child_env.pop(_VALIDATION_JUSTIFICATION_ENV, None)
        os.execve(
            executable,
            [
                original_bash_argv0
                if command == "bash" and original_bash_argv0 is not None
                else command,
                *sys.argv[1:],
            ],
            child_env,
        )

    # The outer heavy launcher owns capacity for its whole process tree. Strip
    # the shim directory only now so make/tox/npm descendants cannot queue
    # recursively behind their own parent's lease.
    child_env["PATH"] = search_path
    child_env["SHELL"] = str(config.get("shell") or "/bin/sh")
    child_env.pop(_GUARD_ENV, None)

    lease_descriptor = _request_native_validation_lease(
        config,
        boundary_group,
        command_identity,
    )
    try:
        if _cancelled():
            raise RuntimeError("native validation authority was withdrawn before exec")
        child_env.pop(_VALIDATION_MODE_ENV, None)
        child_env.pop(_VALIDATION_JUSTIFICATION_ENV, None)
        os.set_inheritable(lease_descriptor, True)
        raw_capability_descriptor = child_env.pop(_CAPABILITY_FD_ENV, "")
        with contextlib.suppress(OSError, ValueError):
            os.close(int(raw_capability_descriptor))
        os.execve(
            executable,
            [
                original_bash_argv0
                if command == "bash" and original_bash_argv0 is not None
                else command,
                *sys.argv[1:],
            ],
            child_env,
        )
    finally:
        with contextlib.suppress(OSError):
            os.close(lease_descriptor)
    return 1  # pragma: no cover - os.execve replaces this process


def _runtime_root_is_referenced(
    runtime_root: Path,
    *,
    proc_root: Path = Path("/proc"),
    opaque_process_baseline: frozenset[tuple[int, int]] = frozenset(),
) -> bool:
    """Return whether a same-user live process still references a guard root.

    Guard directories are tiny, while deleting one too early turns a missing
    BASH_ENV file into an unguarded delayed command.  Read failures for a
    same-user process therefore retain the directory rather than guessing.
    """

    needle = os.fsencode(str(runtime_root.resolve()))
    try:
        entries = tuple(proc_root.iterdir())
    except OSError:
        return True
    for entry in entries:
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        try:
            if entry.stat().st_uid != os.geteuid():
                continue
        except OSError:
            continue
        process_identity = (
            int(entry.name),
            _proc_entry_start_ticks(entry),
        )
        known_opaque = (
            process_identity[1] is not None
            and (process_identity[0], process_identity[1])
            in opaque_process_baseline
        )
        environment = b""
        try:
            environment = (entry / "environ").read_bytes()
        except FileNotFoundError:
            continue
        except PermissionError:
            if not known_opaque:
                return True
        except OSError:
            return True
        command_line = b""
        try:
            command_line = (entry / "cmdline").read_bytes()
        except FileNotFoundError:
            continue
        except PermissionError:
            if not known_opaque:
                return True
        except OSError:
            return True
        if needle in environment or needle in command_line:
            return True
        for link_name in ("cwd", "exe", "root"):
            try:
                linked = os.fsencode(os.readlink(entry / link_name))
            except FileNotFoundError:
                continue
            except PermissionError:
                if known_opaque:
                    continue
                return True
            except OSError:
                return True
            if needle in linked:
                return True
        try:
            descriptors = tuple((entry / "fd").iterdir())
        except FileNotFoundError:
            continue
        except PermissionError:
            if known_opaque:
                continue
            return True
        except OSError:
            return True
        for descriptor in descriptors:
            try:
                linked = os.fsencode(os.readlink(descriptor))
            except FileNotFoundError:
                continue
            except PermissionError:
                if known_opaque:
                    continue
                return True
            except OSError:
                return True
            if needle in linked:
                return True
    return False


def _configured_opaque_process_baseline(
    root: Path,
) -> frozenset[tuple[int, int]] | None:
    """Load the immutable pre-install opaque process generations."""

    try:
        raw = _load_verified_guard_config(root)
        values = raw.get("opaque_process_baseline")
        if values is None:
            return frozenset()
        if not isinstance(values, list) or any(
            not isinstance(value, list)
            or len(value) != 2
            or any(
                not isinstance(item, int)
                or isinstance(item, bool)
                or item <= 0
                for item in value
            )
            for value in values
        ):
            return None
        return frozenset((value[0], value[1]) for value in values)
    except (OSError, RuntimeError, TypeError, ValueError):
        return None


def _lease_and_owner_from_runtime_root(
    root: Path,
) -> tuple[ValidationResourceLease, ValidationLeaseOwner]:
    raw = _load_verified_guard_config(root)
    if not isinstance(raw.get("owner"), dict):
        raise RuntimeError("native validation guard recovery metadata is invalid")
    owner_raw = raw["owner"]
    assert isinstance(owner_raw, dict)
    owner = ValidationLeaseOwner(
        kind=str(owner_raw.get("kind") or ""),
        project_id=str(owner_raw.get("project_id") or ""),
        task_id=str(owner_raw.get("task_id") or ""),
        authority_generation=str(owner_raw.get("authority_generation") or ""),
        priority=int(owner_raw.get("priority") or 0),
    )
    lease = ValidationResourceLease(
        str(raw.get("state_path") or ""),
        capacity=int(raw.get("capacity") or 1),
        aging_seconds=float(raw.get("aging_seconds") or 30.0),
        poll_seconds=float(raw.get("poll_seconds") or 0.05),
    )
    return lease, owner


def _runtime_root_creator_alive(root: Path) -> bool:
    try:
        raw = _load_verified_guard_config(root)
        creator = raw.get("creator")
        if not isinstance(creator, dict):
            return False
        return _process_start_ticks(int(creator["pid"])) == int(
            creator["start_ticks"]
        )
    except (KeyError, OSError, RuntimeError, TypeError, ValueError):
        return False


def _retire_configured_broker_socket(root: Path) -> None:
    """Remove an external per-install socket directory after guard retirement."""

    try:
        config = _load_verified_guard_config(root)
        validated_external = _validated_external_broker_socket(
            Path(str(config.get("broker_socket") or "")),
            Path(str(config.get("broker_socket_cleanup_dir") or "")),
        )
        if validated_external is None:
            return
        socket_path, cleanup_dir = validated_external
    except (OSError, RuntimeError, TypeError, ValueError):
        return
    _cleanup_validated_external_broker_socket(socket_path, cleanup_dir)


def retire_native_validation_guard(
    runtime_root: str | os.PathLike[str],
    *,
    validation_lease: ValidationResourceLease | None = None,
    owner: ValidationLeaseOwner | None = None,
    terminal_outcome: str = "authority_withdrawn",
) -> bool:
    """Withdraw one guard and remove it only after descendants are gone.

    A detached child can outlive the provider turn.  The cancellation marker
    keeps its inherited PATH/BASH_ENV hooks fail closed; the durable owner
    cancellation fences queued or attached heavyweight commands.  Retaining a
    referenced directory is intentional and safe to retry later.
    """

    root = Path(runtime_root).resolve()
    if not root.is_dir():
        return True
    # Let the live broker publish the exact cleanup cause before it creates
    # the cancellation fence. Otherwise its supervisor can observe that fence
    # first and collapse transport/session cleanup into authority withdrawal.
    supervisors_exited = _stop_native_validation_broker(
        root,
        cleanup_outcome=terminal_outcome,
    )
    (root / _CANCELLATION_NAME).touch(mode=0o600, exist_ok=True)
    if validation_lease is None or owner is None:
        try:
            validation_lease, owner = _lease_and_owner_from_runtime_root(root)
        except (OSError, RuntimeError, ValueError, json.JSONDecodeError):
            return False
    validation_lease.cancel_owner(owner)
    if not supervisors_exited:
        return False
    opaque_process_baseline = _configured_opaque_process_baseline(root)
    if opaque_process_baseline is None:
        return False
    if _runtime_root_is_referenced(
        root,
        opaque_process_baseline=opaque_process_baseline,
    ):
        return False
    _retire_configured_broker_socket(root)
    shutil.rmtree(root)
    return not root.exists()


def cleanup_retired_native_validation_guards(
    parent: str | os.PathLike[str],
) -> int:
    """Remove cancelled guard roots whose last descendant has exited."""

    removed = 0
    root = Path(parent).resolve()
    try:
        candidates = tuple(root.glob("oompah-codex-validation-*"))
    except OSError:
        return 0
    for candidate in candidates:
        if (
            not (candidate / _CANCELLATION_NAME).exists()
            and _runtime_root_creator_alive(candidate)
        ):
            continue
        try:
            removed += int(retire_native_validation_guard(candidate))
        except OSError:
            continue
    return removed


__all__ = [
    "NATIVE_VALIDATION_DISTINCT_MODE_INSTRUCTION",
    "cleanup_retired_native_validation_guards",
    "complete_native_validation_command",
    "consume_native_validation_boundary",
    "create_native_validation_broker_socket",
    "install_native_validation_guard",
    "main",
    "native_validation_provider_launcher",
    "retire_native_validation_guard",
]
