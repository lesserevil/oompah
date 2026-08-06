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
import os
import secrets
import select
import shlex
import shutil
import socket
import stat
import struct
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path
from types import SimpleNamespace
from typing import Mapping

from oompah.validation_resource_lease import (
    ValidationLeaseOwner,
    ValidationResourceLease,
    _is_dynamic_loader_environment_name,
    _terminate_exact_process_group,
    is_heavyweight_validation_command,
)


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
_PROVIDER_LAUNCHER_NAME = "oompah-validation-provider"
_SUPERVISOR_LAUNCHER_NAME = "oompah-validation-supervisor"
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
        raw = json.loads((root / _CONFIG_NAME).read_text(encoding="utf-8"))
        creator = raw["creator"]
        bootstrap = raw["provider_bootstrap"]
        parent_pid = _process_parent_id(peer_pid)
        arguments = tuple(
            os.fsdecode(value)
            for value in Path(f"/proc/{peer_pid}/cmdline").read_bytes().split(b"\0")
            if value
        )
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
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
        validation_lease: ValidationResourceLease,
        owner: ValidationLeaseOwner,
        timeout_seconds: float,
    ) -> None:
        self.root = root
        self.socket_path = root / _BROKER_SOCKET_NAME
        self.validation_lease = validation_lease
        self.owner = owner
        self.timeout_seconds = max(float(timeout_seconds), 1.0)
        self._stop = threading.Event()
        self._boundary_lock = threading.Lock()
        self._handler_lock = threading.Lock()
        self._handler_threads: set[threading.Thread] = set()
        self._handler_connections: set[socket.socket] = set()
        self._boundaries: deque[tuple[float, str, str]] = deque()
        self._seen_boundary_groups: set[str] = set()
        self._bound_item_ids: set[str] = set()
        self._provider_identity: tuple[int, int] | None = None
        self._capability_secret: bytes | None = None
        self._capability_identity: tuple[int, int] | None = None
        # Keep one broker-owned reference for the whole session. Besides
        # cleanup ownership, this pins the anonymous inode so the device/inode
        # authentication tuple cannot be recycled after a provider closes its
        # inherited copy.
        self._capability_fd: int | None = None
        self._listener = socket.socket(socket.AF_UNIX, _BROKER_SOCKET_TYPE)
        self.socket_path.unlink(missing_ok=True)
        self._listener.bind(str(self.socket_path))
        self.socket_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
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
            config = json.loads(
                (self.root / _CONFIG_NAME).read_text(encoding="utf-8")
            )
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
        if (
            provider_identity is None
            or secret is None
            or capability_identity is None
            or not _process_descends_from(peer_pid, provider_identity)
            or not _peer_capability_descriptor_matches(
                peer_pid,
                capability_identity,
            )
        ):
            raise RuntimeError("native validation provider capability is unavailable")
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

                def cancelled() -> bool:
                    return (
                        self._stop.is_set()
                        or (self.root / _CANCELLATION_NAME).exists()
                        or _process_start_ticks(peer_pid) != peer_start_ticks
                    )

                handle = self.validation_lease.acquire(
                    self.owner,
                    is_cancelled=cancelled,
                )
                if cancelled():
                    raise RuntimeError("native validation authority was withdrawn")
                handle.attach_process(
                    SimpleNamespace(pid=peer_pid),
                    timeout_seconds=self.timeout_seconds,
                )
                if cancelled():
                    raise RuntimeError("native validation authority was withdrawn")
                descriptor = handle.pass_fds[0]
                _start_validation_lease_supervisor(
                    self.root,
                    peer_pid=peer_pid,
                    peer_start_ticks=peer_start_ticks,
                    lease_descriptor=descriptor,
                    timeout_seconds=self.timeout_seconds,
                )
                connection.sendmsg(
                    [b"LEASE\n"],
                    [
                        (
                            socket.SOL_SOCKET,
                            socket.SCM_RIGHTS,
                            array.array("i", [descriptor]),
                        )
                    ],
                )
                handle.relinquish_transferred_descriptor()
                descriptor_transferred = True
            except Exception:
                with contextlib.suppress(OSError):
                    connection.sendall(b"DENIED\n")
            finally:
                if handle is not None and not descriptor_transferred:
                    handle.release()

    def stop(self) -> None:
        # Stop accepting first, then close every tracked peer before taking
        # the publication lock. A REGISTER send blocked inside that critical
        # section is thereby interrupted and can release the lock; a send that
        # completed first is the fully accepted side of the race.
        with contextlib.suppress(OSError):
            self._listener.close()
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
        for handler in handlers:
            if handler is not threading.current_thread():
                handler.join()
        with self._handler_lock:
            self._handler_connections.difference_update(connections)
            self._handler_threads.difference_update(handlers)
        if descriptor is not None:
            with contextlib.suppress(OSError):
                os.close(descriptor)

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
            return True


def _start_native_validation_broker(
    root: Path,
    *,
    validation_lease: ValidationResourceLease,
    owner: ValidationLeaseOwner,
    timeout_seconds: float,
) -> _NativeValidationLeaseBroker:
    broker = _NativeValidationLeaseBroker(
        root,
        validation_lease=validation_lease,
        owner=owner,
        timeout_seconds=timeout_seconds,
    )
    with _BROKER_REGISTRY_LOCK:
        previous = _BROKER_REGISTRY.setdefault(root.resolve(), broker)
    if previous is not broker:
        broker.stop()
        raise RuntimeError("native validation broker already exists")
    return broker


def _stop_native_validation_broker(root: Path) -> None:
    with _BROKER_REGISTRY_LOCK:
        broker = _BROKER_REGISTRY.pop(root.resolve(), None)
    if broker is not None:
        broker.stop()


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
    validation_lease: ValidationResourceLease,
    owner: ValidationLeaseOwner,
    timeout_seconds: float,
    provider_bootstrap_entrypoint: str | os.PathLike[str] | None = None,
    provider_bootstrap_interpreter: str | os.PathLike[str] | None = None,
    provider_bootstrap_entrypoint_identity: tuple[int, int] | None = None,
    provider_bootstrap_entrypoint_fd: int | None = None,
    provider_untrusted_roots: tuple[str | os.PathLike[str], ...] = (),
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
    original_path = str(guarded.get("PATH") or os.defpath)
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
    untrusted_roots = tuple(
        Path(candidate).resolve() for candidate in provider_untrusted_roots
    )

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
        "broker_socket": str(root / _BROKER_SOCKET_NAME),
        "cancellation_path": str(root / _CANCELLATION_NAME),
        "untrusted_executable_roots": [str(candidate) for candidate in untrusted_roots],
        "creator": {
            "pid": creator_pid,
            "start_ticks": creator_start_ticks,
        },
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
    config_path.write_text(json.dumps(config, sort_keys=True), encoding="utf-8")
    config_path.chmod(0o400)

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
    broker = _start_native_validation_broker(
        root,
        validation_lease=validation_lease,
        owner=owner,
        timeout_seconds=timeout_seconds,
    )
    try:
        if provider_bootstrap_entrypoint is None:
            capability_descriptor = broker.issue_local_test_capability()
            guarded[_CAPABILITY_FD_ENV] = str(capability_descriptor)
    except BaseException:
        # Installation has not returned an owner capable of retiring this
        # root. Do not strand its broker listener/thread after bootstrap fails.
        _stop_native_validation_broker(root)
        raise
    return guarded, root


def _load_invocation_config(argv0: str) -> tuple[dict[str, object], Path]:
    guard_bin = Path(os.path.abspath(argv0)).parent
    config_path = guard_bin.parent / _CONFIG_NAME
    # Reject a shell-selected lookalike config.  The service creates this file
    # owner-readable and immutable to the sandboxed agent.
    mode = stat.S_IMODE(config_path.stat().st_mode)
    if mode != stat.S_IRUSR:
        raise RuntimeError(
            "native validation guard configuration has unsafe permissions"
        )
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise RuntimeError("native validation guard configuration is invalid")
    return raw, guard_bin


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
    client = socket.socket(socket.AF_UNIX, _BROKER_SOCKET_TYPE)
    try:
        client.connect(raw_path)
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


def _capability_secret() -> bytes:
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
    proof = _capability_proof(
        _capability_secret(),
        nonce=nonce,
        peer_pid=os.getpid(),
        peer_start_ticks=start_ticks,
        request=request,
    )
    client.sendall(f"PROVE {proof}\n".encode("ascii"))


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

    if len(sys.argv) != 6:
        raise RuntimeError("native validation supervisor arguments are invalid")
    peer_pid = int(sys.argv[1])
    peer_start_ticks = int(sys.argv[2])
    lease_descriptor = int(sys.argv[3])
    deadline_at = float(sys.argv[4])
    ready_descriptor = int(sys.argv[5])
    pidfd = -1
    try:
        if not hasattr(os, "pidfd_open"):
            raise RuntimeError("native validation pidfd supervision is unavailable")
        pidfd = os.pidfd_open(peer_pid)
        if _process_start_ticks(peer_pid) != peer_start_ticks:
            raise RuntimeError("native validation supervised peer changed identity")
        os.write(ready_descriptor, b"READY\n")
        os.close(ready_descriptor)
        ready_descriptor = -1
        cancellation_path = Path(str(config.get("cancellation_path") or ""))
        while (
            _process_start_ticks(peer_pid) == peer_start_ticks
            and not cancellation_path.exists()
            and time.time() < deadline_at
        ):
            time.sleep(0.05)
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
    finally:
        if ready_descriptor >= 0:
            with contextlib.suppress(OSError):
                os.close(ready_descriptor)
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
) -> None:
    read_descriptor, write_descriptor = os.pipe2(os.O_CLOEXEC)
    process: subprocess.Popen[bytes] | None = None
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
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            pass_fds=(lease_descriptor, write_descriptor),
            start_new_session=True,
        )
        os.close(write_descriptor)
        write_descriptor = -1
        readable, _, _ = select.select([read_descriptor], [], [], 2.0)
        if not readable or os.read(read_descriptor, 16) != b"READY\n":
            raise RuntimeError("native validation lease supervisor did not start")
        threading.Thread(target=process.wait, daemon=True).start()
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


def _runtime_root_is_referenced(runtime_root: Path) -> bool:
    """Return whether a same-user live process still references a guard root.

    Guard directories are tiny, while deleting one too early turns a missing
    BASH_ENV file into an unguarded delayed command.  Read failures for a
    same-user process therefore retain the directory rather than guessing.
    """

    needle = os.fsencode(str(runtime_root.resolve()))
    proc = Path("/proc")
    try:
        entries = tuple(proc.iterdir())
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
        try:
            environment = (entry / "environ").read_bytes()
            command_line = (entry / "cmdline").read_bytes()
        except FileNotFoundError:
            continue
        except OSError:
            return True
        if needle in environment or needle in command_line:
            return True
        for link_name in ("cwd", "exe", "root"):
            try:
                linked = os.fsencode(os.readlink(entry / link_name))
            except FileNotFoundError:
                continue
            except OSError:
                return True
            if needle in linked:
                return True
        try:
            descriptors = tuple((entry / "fd").iterdir())
        except FileNotFoundError:
            continue
        except OSError:
            return True
        for descriptor in descriptors:
            try:
                linked = os.fsencode(os.readlink(descriptor))
            except FileNotFoundError:
                continue
            except OSError:
                return True
            if needle in linked:
                return True
    return False


def _lease_and_owner_from_runtime_root(
    root: Path,
) -> tuple[ValidationResourceLease, ValidationLeaseOwner]:
    config_path = root / _CONFIG_NAME
    mode = stat.S_IMODE(config_path.stat().st_mode)
    if mode != stat.S_IRUSR:
        raise RuntimeError(
            "native validation guard configuration has unsafe permissions"
        )
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("owner"), dict):
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
        raw = json.loads((root / _CONFIG_NAME).read_text(encoding="utf-8"))
        creator = raw.get("creator") if isinstance(raw, dict) else None
        if not isinstance(creator, dict):
            return False
        return _process_start_ticks(int(creator["pid"])) == int(
            creator["start_ticks"]
        )
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
        return False


def retire_native_validation_guard(
    runtime_root: str | os.PathLike[str],
    *,
    validation_lease: ValidationResourceLease | None = None,
    owner: ValidationLeaseOwner | None = None,
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
    (root / _CANCELLATION_NAME).touch(mode=0o600, exist_ok=True)
    _stop_native_validation_broker(root)
    if validation_lease is None or owner is None:
        try:
            validation_lease, owner = _lease_and_owner_from_runtime_root(root)
        except (OSError, RuntimeError, ValueError, json.JSONDecodeError):
            return False
    validation_lease.cancel_owner(owner)
    if _runtime_root_is_referenced(root):
        return False
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
    "cleanup_retired_native_validation_guards",
    "consume_native_validation_boundary",
    "install_native_validation_guard",
    "main",
    "native_validation_provider_launcher",
    "retire_native_validation_guard",
]
