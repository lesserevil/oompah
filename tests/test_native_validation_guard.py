from __future__ import annotations

import array
import contextlib
import errno
import json
import os
import shlex
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from oompah import native_validation_guard as guard_module
from oompah.api_agent import _validation_reuse_policy_decision
from oompah.native_validation_guard import (
    cleanup_retired_native_validation_guards,
    consume_native_validation_boundary,
    install_native_validation_guard,
    main,
    retire_native_validation_guard,
)
from oompah.validation_resource_lease import (
    ValidationLeaseCancelled,
    ValidationLeaseHandle,
    ValidationLeaseOwner,
    ValidationCommandClassification,
    ValidationResourceLease,
    is_heavyweight_validation_command,
)


def _wait_until(predicate, *, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition did not become true")


def _wait_for_pid(path: Path, *, timeout: float = 5.0) -> int:
    """Return a positive PID only after its producer has finished publishing it."""

    deadline = time.monotonic() + timeout
    last_value = "<missing>"
    while time.monotonic() < deadline:
        try:
            last_value = path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            last_value = "<missing>"
        if last_value.isascii() and last_value.isdigit():
            pid = int(last_value)
            if pid > 0 and Path(f"/proc/{pid}").exists():
                return pid
        time.sleep(0.01)
    raise AssertionError(
        f"{path} did not contain a complete live PID (last value: {last_value!r})"
    )


def _guard_pass_fds(environment: dict[str, str]) -> tuple[int, ...]:
    raw = environment.get("OOMPAH_NATIVE_VALIDATION_CAPABILITY_FD", "")
    return (int(raw),) if raw else ()


def _open_fd_snapshot() -> set[str]:
    return set(os.listdir("/proc/self/fd"))


def _open_fd_targets(descriptors: set[str]) -> dict[str, str]:
    targets: dict[str, str] = {}
    for descriptor in descriptors:
        try:
            targets[descriptor] = os.readlink(f"/proc/self/fd/{descriptor}")
        except OSError:
            targets[descriptor] = "<closed>"
    return targets


@pytest.fixture
def fake_operator_home(monkeypatch: pytest.MonkeyPatch):
    """Provide a private passwd home below only trusted real-home ancestors."""

    real_home = Path(guard_module.pwd.getpwuid(os.geteuid()).pw_dir)
    operator_home = Path(
        tempfile.mkdtemp(prefix=".nvh-", dir=real_home)
    )
    operator_home.chmod(0o700)
    monkeypatch.setattr(
        guard_module.pwd,
        "getpwuid",
        lambda _uid: SimpleNamespace(pw_dir=str(operator_home)),
    )
    try:
        yield operator_home
    finally:
        shutil.rmtree(operator_home, ignore_errors=True)


def _test_native_broker(
    tmp_path: Path,
    *,
    task_id: str,
) -> tuple[guard_module._NativeValidationLeaseBroker, Path]:
    root = tmp_path / task_id.lower()
    root.mkdir()
    config_path = root / guard_module._CONFIG_NAME
    config_path.write_text("{}", encoding="utf-8")
    config_path.chmod(0o400)
    socket_path, socket_cleanup_dir = (
        guard_module.create_native_validation_broker_socket(
            runtime_root=root,
            untrusted_roots=(),
        )
    )
    broker = guard_module._NativeValidationLeaseBroker(
        root,
        socket_path=socket_path or root / guard_module._BROKER_SOCKET_NAME,
        socket_cleanup_dir=socket_cleanup_dir,
        validation_lease=ValidationResourceLease(
            tmp_path / f"{task_id.lower()}.sqlite3",
            poll_seconds=0.01,
        ),
        owner=ValidationLeaseOwner.worker(
            project_id="project",
            task_id=task_id,
            authority_generation="generation",
        ),
        timeout_seconds=10,
    )
    return broker, root


def test_long_guard_root_uses_explicit_short_broker_socket(tmp_path: Path) -> None:
    """Deep worktree paths use the supplied protected short socket."""

    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    owner = ValidationLeaseOwner.worker(
        project_id="project",
        task_id="TASK-LONG-ROOT",
        authority_generation="generation",
    )
    runtime_root = tmp_path / ("deep-" * 20) / "guard"
    socket_path, socket_dir = guard_module.create_native_validation_broker_socket(
        runtime_root=runtime_root,
        untrusted_roots=(),
    )
    assert socket_path is not None and socket_dir is not None
    guarded, root = install_native_validation_guard(
        {"PATH": os.environ.get("PATH", os.defpath)},
        runtime_root=runtime_root,
        broker_socket=socket_path,
        broker_socket_cleanup_dir=socket_dir,
        validation_lease=lease,
        owner=owner,
        timeout_seconds=10,
    )
    try:
        config = json.loads((root / guard_module._CONFIG_NAME).read_text("utf-8"))
        assert config["broker_socket"] == str(socket_path)
        assert config["broker_socket_cleanup_dir"] == str(socket_dir)
        assert socket_path.exists()
        assert stat.S_IMODE(socket_dir.stat().st_mode) == 0o700
        with guard_module._broker_socket(config):
            pass
        assert guarded["OOMPAH_NATIVE_VALIDATION_GUARD"] == str(
            root / "validation-guard-bin"
        )
    finally:
        retired = retire_native_validation_guard(
            root,
            validation_lease=lease,
            owner=owner,
        )
        if retired:
            assert not socket_path.exists()
            assert not socket_dir.exists()
        else:
            guard_module._retire_configured_broker_socket(root)
            shutil.rmtree(socket_dir, ignore_errors=True)


def test_long_guard_root_automatically_uses_short_broker_socket(
    tmp_path: Path,
) -> None:
    """The generic installer must not regress to a deep local AF_UNIX path."""

    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    owner = ValidationLeaseOwner.worker(
        project_id="project",
        task_id="TASK-LONG-AUTOMATIC",
        authority_generation="generation",
    )
    runtime_root = tmp_path / ("project-harness-root-" * 12) / "guard"
    guarded, root = install_native_validation_guard(
        {"PATH": os.environ.get("PATH", os.defpath)},
        runtime_root=runtime_root,
        validation_lease=lease,
        owner=owner,
        timeout_seconds=10,
    )
    socket_path: Path | None = None
    socket_dir: Path | None = None
    try:
        config = json.loads((root / guard_module._CONFIG_NAME).read_text("utf-8"))
        socket_path = Path(config["broker_socket"])
        socket_dir = Path(config["broker_socket_cleanup_dir"])
        assert socket_path.parent == socket_dir
        assert socket_dir.parent == guard_module._operator_broker_socket_parent()
        assert len(os.fsencode(str(socket_path))) < 100
        assert socket_path.exists()
        assert guarded["OOMPAH_NATIVE_VALIDATION_GUARD"] == str(
            root / "validation-guard-bin"
        )
    finally:
        retired = retire_native_validation_guard(
            root,
            validation_lease=lease,
            owner=owner,
        )
        if retired:
            assert socket_path is not None and socket_dir is not None
            assert not socket_path.exists()
            assert not socket_dir.exists()
        elif socket_path is not None and socket_dir is not None:
            guard_module._retire_configured_broker_socket(root)
            shutil.rmtree(socket_dir, ignore_errors=True)


def test_operator_broker_socket_parent_ignores_isolated_worker_home(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An xdist/task HOME override cannot deepen or relocate the endpoint."""

    monkeypatch.setenv("HOME", str(tmp_path / ("isolated-home-" * 12)))
    expected_home = Path(
        guard_module.pwd.getpwuid(os.geteuid()).pw_dir
    ).resolve()

    assert guard_module._operator_broker_socket_parent() == (
        expected_home / ".oompah" / "native-validation-sockets"
    )


def test_operator_broker_socket_parent_rejects_relative_passwd_home(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        guard_module.pwd,
        "getpwuid",
        lambda _uid: SimpleNamespace(pw_dir="relative/operator-home"),
    )

    with pytest.raises(RuntimeError, match="account home path is unsafe"):
        guard_module._prepare_operator_broker_socket_parent()


def test_operator_broker_socket_parent_rejects_symlink_component(
    fake_operator_home: Path,
) -> None:
    target = fake_operator_home / "redirected-oompah"
    target.mkdir(mode=0o700)
    (fake_operator_home / ".oompah").symlink_to(target, target_is_directory=True)

    with pytest.raises(RuntimeError, match="directory is unsafe"):
        guard_module._prepare_operator_broker_socket_parent()


def test_operator_broker_socket_parent_rejects_unsafe_home_mode(
    fake_operator_home: Path,
) -> None:
    fake_operator_home.chmod(0o770)
    try:
        with pytest.raises(RuntimeError, match="directory is unsafe"):
            guard_module._prepare_operator_broker_socket_parent()
    finally:
        fake_operator_home.chmod(0o700)


def test_operator_broker_socket_parent_rejects_foreign_owned_home(
    fake_operator_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_lstat = Path.lstat

    def foreign_home_lstat(path: Path):
        info = real_lstat(path)
        if path == fake_operator_home:
            return SimpleNamespace(
                st_mode=info.st_mode,
                st_uid=os.geteuid() + 1,
            )
        return info

    with monkeypatch.context() as isolated:
        isolated.setattr(Path, "lstat", foreign_home_lstat)
        with pytest.raises(RuntimeError, match="directory is unsafe"):
            guard_module._prepare_operator_broker_socket_parent()


def test_operator_broker_socket_parent_tightens_owned_scoped_directories(
    fake_operator_home: Path,
) -> None:
    oompah_root = fake_operator_home / ".oompah"
    oompah_root.mkdir(mode=0o755)

    socket_parent = guard_module._prepare_operator_broker_socket_parent()

    assert stat.S_IMODE(oompah_root.stat().st_mode) == 0o700
    assert stat.S_IMODE(socket_parent.stat().st_mode) == 0o700


def test_external_broker_socket_rejects_tampered_private_child(
    tmp_path: Path,
    fake_operator_home: Path,
) -> None:
    runtime_root = tmp_path / ("deep-" * 24)
    socket_path, cleanup_dir = guard_module.create_native_validation_broker_socket(
        runtime_root=runtime_root,
        untrusted_roots=(),
    )
    assert socket_path is not None and cleanup_dir is not None
    cleanup_dir.chmod(0o770)
    try:
        assert (
            guard_module._validated_external_broker_socket(
                socket_path,
                cleanup_dir,
            )
            is None
        )
        guard_module._cleanup_validated_external_broker_socket(
            socket_path,
            cleanup_dir,
        )
        assert cleanup_dir.exists()
    finally:
        cleanup_dir.chmod(0o700)
        shutil.rmtree(cleanup_dir, ignore_errors=True)


def test_opaque_process_baseline_is_immutable_within_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A later opaque generation cannot become trusted by another install."""

    first = ((101, 1_001),)
    later = (*first, (202, 2_002))
    scans: list[Path] = []

    def scan(proc_root: Path) -> tuple[tuple[int, int], ...]:
        scans.append(proc_root)
        return first if len(scans) == 1 else later

    monkeypatch.setattr(guard_module, "_OPAQUE_PROCESS_BASELINE_OWNER_PID", None)
    monkeypatch.setattr(guard_module, "_OPAQUE_PROCESS_BASELINE_CACHE", None)
    monkeypatch.setattr(guard_module, "_scan_opaque_same_user_processes", scan)

    assert guard_module._opaque_same_user_process_baseline() == first
    assert guard_module._opaque_same_user_process_baseline() == first
    assert scans == [Path("/proc")]


def test_process_ancestry_baseline_is_immutable_within_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = ((303, 3_003),)
    later = (*first, (404, 4_004))
    scans: list[Path] = []

    def scan(proc_root: Path) -> tuple[tuple[int, int], ...]:
        scans.append(proc_root)
        return first if len(scans) == 1 else later

    monkeypatch.setattr(
        guard_module,
        "_PROCESS_ANCESTRY_BASELINE_OWNER_PID",
        None,
    )
    monkeypatch.setattr(
        guard_module,
        "_PROCESS_ANCESTRY_BASELINE_CACHE",
        None,
    )
    monkeypatch.setattr(guard_module, "_scan_same_user_process_identities", scan)

    assert guard_module._process_ancestry_baseline() == first
    assert guard_module._process_ancestry_baseline() == first
    assert scans == [Path("/proc")]


def test_opaque_process_baseline_resets_after_fork(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A child cannot inherit its parent's trusted opaque generations or lock."""

    parent_lock = threading.Lock()
    parent_lock.acquire()
    monkeypatch.setattr(
        guard_module,
        "_OPAQUE_PROCESS_BASELINE_LOCK",
        parent_lock,
    )
    monkeypatch.setattr(
        guard_module,
        "_OPAQUE_PROCESS_BASELINE_OWNER_PID",
        os.getpid(),
    )
    monkeypatch.setattr(
        guard_module,
        "_OPAQUE_PROCESS_BASELINE_CACHE",
        ((101, 1_001),),
    )
    monkeypatch.setattr(
        guard_module,
        "_PROCESS_ANCESTRY_BASELINE_OWNER_PID",
        os.getpid(),
    )
    monkeypatch.setattr(
        guard_module,
        "_PROCESS_ANCESTRY_BASELINE_CACHE",
        ((303, 3_003),),
    )

    guard_module._reset_opaque_process_baseline_after_fork()

    assert guard_module._OPAQUE_PROCESS_BASELINE_LOCK is not parent_lock
    assert guard_module._OPAQUE_PROCESS_BASELINE_LOCK.acquire(blocking=False)
    guard_module._OPAQUE_PROCESS_BASELINE_LOCK.release()
    assert guard_module._OPAQUE_PROCESS_BASELINE_OWNER_PID is None
    assert guard_module._OPAQUE_PROCESS_BASELINE_CACHE is None
    assert guard_module._PROCESS_ANCESTRY_BASELINE_OWNER_PID is None
    assert guard_module._PROCESS_ANCESTRY_BASELINE_CACHE is None


@pytest.mark.parametrize("failure", ["broker_bind", "config_write"])
def test_automatic_deep_socket_cleanup_on_install_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    """Automatic deep-root children never survive a failed installation."""

    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    owner = ValidationLeaseOwner.worker(
        project_id="project",
        task_id="TASK-DEEP-FAIL",
        authority_generation="generation",
    )
    captured: dict[str, Path] = {}
    real_create = guard_module.create_native_validation_broker_socket

    def capture_socket(**kwargs):
        socket_path, cleanup_dir = real_create(**kwargs)
        assert socket_path is not None and cleanup_dir is not None
        captured["socket"] = socket_path
        captured["cleanup"] = cleanup_dir
        captured["parent"] = cleanup_dir.parent
        captured["parent_mode"] = stat.S_IMODE(cleanup_dir.parent.stat().st_mode)
        captured["cleanup_mode"] = stat.S_IMODE(cleanup_dir.stat().st_mode)
        return socket_path, cleanup_dir

    monkeypatch.setattr(
        guard_module,
        "create_native_validation_broker_socket",
        capture_socket,
    )
    if failure == "broker_bind":
        monkeypatch.setattr(
            guard_module,
            "_start_native_validation_broker",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("bind failed")),
        )
    else:
        original_write_text = Path.write_text

        def fail_config_write(path: Path, data: str, *args, **kwargs):
            if path.name == guard_module._CONFIG_NAME:
                raise OSError("config write failed")
            return original_write_text(path, data, *args, **kwargs)

        monkeypatch.setattr(Path, "write_text", fail_config_write)

    with pytest.raises(OSError):
        install_native_validation_guard(
            {"PATH": os.environ.get("PATH", os.defpath)},
            runtime_root=tmp_path / ("deep-" * 20) / "guard",
            validation_lease=lease,
            owner=owner,
            timeout_seconds=10,
        )

    assert captured["parent_mode"] == 0o700
    assert captured["cleanup_mode"] == 0o700
    assert not captured["socket"].exists()
    assert not captured["cleanup"].exists()


def test_broker_descriptor_reply_rejects_extra_descriptors(tmp_path: Path) -> None:
    sender, receiver = socket.socketpair(
        socket.AF_UNIX,
        guard_module._BROKER_SOCKET_TYPE,
    )
    first = os.open(tmp_path / "first", os.O_CREAT | os.O_RDWR, 0o600)
    second = os.open(tmp_path / "second", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        sender.sendmsg(
            [b"LEASE\n"],
            [
                (
                    socket.SOL_SOCKET,
                    socket.SCM_RIGHTS,
                    array.array("i", [first, second]),
                )
            ],
        )
        with pytest.raises(RuntimeError, match="descriptor reply is invalid"):
            guard_module._receive_single_descriptor(
                receiver,
                expected_payload=b"LEASE\n",
            )
    finally:
        sender.close()
        receiver.close()
        os.close(first)
        os.close(second)


def test_broker_descriptor_reply_accepts_exact_one_and_two_descriptors(
    tmp_path: Path,
) -> None:
    """The real Unix transport preserves the exact SCM_RIGHTS descriptor count."""

    first = os.open(tmp_path / "first", os.O_CREAT | os.O_RDWR, 0o600)
    second = os.open(tmp_path / "second", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        for payload, descriptors in (
            (b"LEASE\n", (first,)),
            (b"CAPABILITY-DIRECT\n", (first, second)),
        ):
            sender, receiver = socket.socketpair(
                socket.AF_UNIX,
                guard_module._BROKER_SOCKET_TYPE,
            )
            received: tuple[int, ...] = ()
            try:
                sender.sendmsg(
                    [payload],
                    [
                        (
                            socket.SOL_SOCKET,
                            socket.SCM_RIGHTS,
                            array.array("i", descriptors),
                        )
                    ],
                )
                received = guard_module._receive_descriptors(
                    receiver,
                    expected_payload=payload,
                    expected_count=len(descriptors),
                )
                assert len(received) == len(descriptors)
                assert all(
                    os.fstat(descriptor).st_ino
                    in {os.fstat(first).st_ino, os.fstat(second).st_ino}
                    for descriptor in received
                )
            finally:
                for descriptor in received:
                    with contextlib.suppress(OSError):
                        os.close(descriptor)
                sender.close()
                receiver.close()
    finally:
        os.close(first)
        os.close(second)


def test_broker_descriptor_reply_preserves_bounded_supervisor_failure() -> None:
    sender, receiver = socket.socketpair(
        socket.AF_UNIX,
        guard_module._BROKER_SOCKET_TYPE,
    )
    try:
        sender.sendall(b"DENIED UNSUPPORTED\n")
        with pytest.raises(RuntimeError, match="pidfd supervision is unavailable"):
            guard_module._receive_single_descriptor(
                receiver,
                expected_payload=b"LEASE\n",
            )
    finally:
        sender.close()
        receiver.close()


@pytest.mark.parametrize(
    ("args", "authority", "classification"),
    [
        (
            {},
            "stale_authority",
            ValidationCommandClassification(True, "full", contains_configured=True),
        ),
        ({}, "reuse_authoritative_gate", None),
        (
            {},
            "reuse_authoritative_gate",
            ValidationCommandClassification(True, "full"),
        ),
    ],
    ids=["stale-authority", "unavailable-classification", "distinct-mode-required"],
)
def test_reuse_policy_denials_have_typed_broker_outcomes(
    args: dict[str, str],
    authority: str,
    classification: ValidationCommandClassification | None,
) -> None:
    """Policy prose must never decide whether a native denial is policy."""

    _decision, denial, _justification = _validation_reuse_policy_decision(
        args,
        {"decision": "reuse_authoritative_gate", "command": "make test"},
        lambda: authority,
        classification=classification,
    )

    assert denial is not None
    assert guard_module._broker_denial_response(
        guard_module._reuse_policy_denied(denial)
    ) == b"DENIED POLICY\n"


@pytest.mark.parametrize(
    ("error", "expected_packet"),
    [
        (AttributeError("pidfd_open"), b"DENIED UNSUPPORTED\n"),
        (OSError(errno.ENOSYS, "not implemented"), b"DENIED UNSUPPORTED\n"),
        (OSError(errno.EOPNOTSUPP, "not supported"), b"DENIED UNSUPPORTED\n"),
        (OSError(errno.ESRCH, "gone"), b"DENIED IDENTITY\n"),
        (OSError(errno.EMFILE, "too many files"), b"DENIED TRANSPORT\n"),
        (OSError(errno.EPERM, "not permitted"), b"DENIED TRANSPORT\n"),
    ],
)
def test_pidfd_setup_failure_keeps_platform_peer_and_transport_distinct(
    error: BaseException,
    expected_packet: bytes,
) -> None:
    assert guard_module._broker_denial_response(
        guard_module._pidfd_supervision_failure(error)
    ) == expected_packet


def test_broker_descriptor_reply_rejects_truncated_payload(tmp_path: Path) -> None:
    sender, receiver = socket.socketpair(
        socket.AF_UNIX,
        guard_module._BROKER_SOCKET_TYPE,
    )
    descriptor = os.open(tmp_path / "lease", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        sender.sendmsg(
            [b"LEASE\n" + (b"x" * 256)],
            [
                (
                    socket.SOL_SOCKET,
                    socket.SCM_RIGHTS,
                    array.array("i", [descriptor]),
                )
            ],
        )
        with pytest.raises(RuntimeError, match="descriptor reply is invalid"):
            guard_module._receive_single_descriptor(
                receiver,
                expected_payload=b"LEASE\n",
            )
    finally:
        sender.close()
        receiver.close()
        os.close(descriptor)


def test_broker_packet_rejects_unexpected_descriptor(tmp_path: Path) -> None:
    sender, receiver = socket.socketpair(
        socket.AF_UNIX,
        guard_module._BROKER_SOCKET_TYPE,
    )
    descriptor = os.open(tmp_path / "unexpected", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        sender.sendmsg(
            [b"LEASE\n"],
            [
                (
                    socket.SOL_SOCKET,
                    socket.SCM_RIGHTS,
                    array.array("i", [descriptor]),
                )
            ],
        )
        with pytest.raises(RuntimeError, match="packet is malformed"):
            guard_module._recv_packet(receiver, 32)
    finally:
        sender.close()
        receiver.close()
        os.close(descriptor)


def test_libc_memfd_capability_is_immutable_without_python_wrappers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A minimal Python build still creates a kernel-sealed capability."""

    monkeypatch.delattr(guard_module.os, "memfd_create", raising=False)
    for name in (
        "F_ADD_SEALS",
        "F_GET_SEALS",
        "F_SEAL_SEAL",
        "F_SEAL_SHRINK",
        "F_SEAL_GROW",
        "F_SEAL_WRITE",
    ):
        monkeypatch.delattr(guard_module.fcntl, name, raising=False)

    secret = b"s" * 32
    descriptor = guard_module._sealed_capability_descriptor(secret)
    try:
        assert os.pread(descriptor, len(secret), 0) == secret
        assert guard_module._capability_descriptor_identity(descriptor)
        with pytest.raises(OSError):
            os.pwrite(descriptor, b"x", 0)
        with pytest.raises(OSError):
            os.ftruncate(descriptor, 0)
        assert os.pread(descriptor, len(secret), 0) == secret
    finally:
        os.close(descriptor)


def test_native_supervisor_uses_libc_pidfd_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Minimal Python builds can still pin the supervisor's peer identity."""

    monkeypatch.delattr(guard_module.os, "pidfd_open", raising=False)
    descriptor = guard_module._pidfd_open(os.getpid())
    try:
        assert os.fstat(descriptor)
    finally:
        os.close(descriptor)


def test_supervisor_start_tick_mismatch_reports_typed_identity_without_ack_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Startup identity loss must not wait for an observer ACK that cannot exist."""

    ready_read, ready_write = os.pipe()
    status_read, status_write = os.pipe()
    acknowledgement_read, acknowledgement_write = os.pipe()
    lease_descriptor = os.open(os.devnull, os.O_RDONLY)
    pidfd_descriptor = os.open(os.devnull, os.O_RDONLY)
    result: list[int] = []
    monkeypatch.setattr(
        guard_module.sys,
        "argv",
        [
            "supervisor",
            "123",
            "456",
            str(lease_descriptor),
            repr(time.time() + 60),
            str(ready_write),
            str(status_write),
            str(acknowledgement_read),
        ],
    )
    monkeypatch.setattr(guard_module, "_pidfd_open", lambda _pid: pidfd_descriptor)
    monkeypatch.setattr(guard_module, "_process_start_ticks", lambda _pid: 999)
    worker = threading.Thread(
        target=lambda: result.append(guard_module._supervise_validation_lease({})),
        daemon=True,
    )
    try:
        worker.start()
        worker.join(timeout=1)

        assert worker.is_alive() is False
        assert result == [1]
        assert os.read(ready_read, 32) == guard_module._SUPERVISOR_IDENTITY_LOST
        assert os.read(status_read, 32) == b""
    finally:
        for descriptor in (
            ready_read,
            ready_write,
            status_read,
            status_write,
            acknowledgement_read,
            acknowledgement_write,
            lease_descriptor,
            pidfd_descriptor,
        ):
            with contextlib.suppress(OSError):
                os.close(descriptor)


def test_supervisor_startup_identity_packet_reaches_caller_as_typed_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The bounded startup reader maps identity loss instead of generic EOF."""

    class IdentityLostProcess:
        def poll(self) -> int | None:
            return None

        def kill(self) -> None:
            return None

        def wait(self, timeout: float | None = None) -> int:
            return 0

    def start_identity_lost_process(arguments, **_kwargs) -> IdentityLostProcess:
        ready_descriptor = int(arguments[5])
        os.write(ready_descriptor, guard_module._SUPERVISOR_IDENTITY_LOST)
        return IdentityLostProcess()

    monkeypatch.setattr(guard_module.subprocess, "Popen", start_identity_lost_process)
    lease_descriptor = os.open(tmp_path / "lease", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        with pytest.raises(RuntimeError, match="supervised peer changed identity"):
            guard_module._start_validation_lease_supervisor(
                tmp_path,
                peer_pid=123,
                peer_start_ticks=456,
                lease_descriptor=lease_descriptor,
                timeout_seconds=10,
                terminal_handler=lambda _outcome: None,
            )
    finally:
        with contextlib.suppress(OSError):
            os.close(lease_descriptor)


def test_broker_rejects_copied_secret_in_distinct_sealed_memfd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A peer cannot replace the issued object with an immutable clone."""

    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    owner = ValidationLeaseOwner.worker(
        project_id="project",
        task_id="TASK-SPOOF",
        authority_generation="generation",
    )
    guarded, root = install_native_validation_guard(
        {"PATH": os.environ.get("PATH", os.defpath)},
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=owner,
        timeout_seconds=10,
    )
    issued = int(guarded[guard_module._CAPABILITY_FD_ENV])
    secret = os.pread(issued, 32, 0)
    spoofed = guard_module._sealed_capability_descriptor(secret)
    monkeypatch.setattr(guard_module, "_peer_is_guard_launcher", lambda *_args: True)
    script = (
        "import os, socket, sys\n"
        "kind = getattr(socket, 'SOCK_SEQPACKET', socket.SOCK_STREAM)\n"
        "client = socket.socket(socket.AF_UNIX, kind)\n"
        "client.connect(os.environ['OOMPAH_TEST_BROKER_SOCKET'])\n"
        "client.sendall(b'OBSERVE 1:1 ' + (b'0' * 64) + b'\\n')\n"
        "sys.stdout.buffer.write(client.recv(32))\n"
    )
    try:
        completed = subprocess.run(
            [sys.executable, "-c", script],
            env={
                **os.environ,
                guard_module._CAPABILITY_FD_ENV: str(spoofed),
                "OOMPAH_TEST_BROKER_SOCKET": str(
                    json.loads(
                        (root / guard_module._CONFIG_NAME).read_text("utf-8")
                    )["broker_socket"]
                ),
            },
            pass_fds=(spoofed,),
            check=False,
            capture_output=True,
            timeout=5,
        )

        assert completed.returncode == 0
        assert completed.stdout == b"DENIED TRANSPORT\n"
        assert lease.status().owner_count == 0
    finally:
        os.close(spoofed)
        assert retire_native_validation_guard(
            root,
            validation_lease=lease,
            owner=owner,
        ) is True


def test_local_capability_bootstrap_failure_stops_broker_thread(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed install cannot strand an unreachable listener or thread."""

    root = tmp_path / "guard"
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    brokers: list[guard_module._NativeValidationLeaseBroker] = []
    real_start = guard_module._start_native_validation_broker

    def capture_broker(*args, **kwargs):
        broker = real_start(*args, **kwargs)
        brokers.append(broker)
        return broker

    monkeypatch.setattr(
        guard_module,
        "_start_native_validation_broker",
        capture_broker,
    )
    monkeypatch.setattr(
        guard_module,
        "_sealed_capability_descriptor",
        lambda _secret: (_ for _ in ()).throw(RuntimeError("no sealed memfd")),
    )

    with pytest.raises(RuntimeError, match="no sealed memfd"):
        install_native_validation_guard(
            {"PATH": os.environ.get("PATH", os.defpath)},
            runtime_root=root,
            validation_lease=lease,
            owner=ValidationLeaseOwner.worker(
                project_id="project",
                task_id="BOOTSTRAP-FAILURE",
                authority_generation="generation",
            ),
            timeout_seconds=10,
        )

    assert len(brokers) == 1
    assert root.resolve() not in guard_module._BROKER_REGISTRY
    assert brokers[0]._thread.is_alive() is False


def test_normal_retirement_removes_registry_and_joins_broker_thread(
    tmp_path: Path,
) -> None:
    """A normally retired guard leaves no live in-process broker authority."""

    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    owner = ValidationLeaseOwner.worker(
        project_id="project",
        task_id="NORMAL-RETIREMENT",
        authority_generation="generation",
    )
    _guarded, root = install_native_validation_guard(
        {"PATH": os.environ.get("PATH", os.defpath)},
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=owner,
        timeout_seconds=10,
    )
    with guard_module._BROKER_REGISTRY_LOCK:
        broker = guard_module._BROKER_REGISTRY[root.resolve()]

    assert retire_native_validation_guard(
        root,
        validation_lease=lease,
        owner=owner,
    ) is True
    with guard_module._BROKER_REGISTRY_LOCK:
        assert root.resolve() not in guard_module._BROKER_REGISTRY
    assert broker._thread.is_alive() is False


def test_registration_and_retirement_publish_capability_atomically(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    broker, _ = _test_native_broker(tmp_path, task_id="REGISTER-RACE")
    send_entered = threading.Event()
    release_send = threading.Event()
    connection_closed = threading.Event()
    sent_descriptors: list[int] = []
    created_descriptors: list[int] = []
    registration_errors: list[BaseException] = []

    class BlockingConnection:
        def sendmsg(self, _payload, ancillary) -> int:
            send_entered.set()
            assert release_send.wait(timeout=5)
            if connection_closed.is_set():
                raise OSError("registration connection retired")
            sent_descriptors.extend(ancillary[0][2])
            return len(_payload[0])

        def shutdown(self, _how: int) -> None:
            connection_closed.set()
            release_send.set()

        def close(self) -> None:
            connection_closed.set()
            release_send.set()

    connection = BlockingConnection()
    with broker._handler_lock:
        broker._handler_connections.add(connection)  # type: ignore[arg-type]

    monkeypatch.setattr(
        guard_module,
        "_provider_registration_is_trusted",
        lambda *_args: True,
    )
    real_sealed_descriptor = guard_module._sealed_capability_descriptor

    def record_descriptor(secret: bytes) -> int:
        descriptor = real_sealed_descriptor(secret)
        created_descriptors.append(descriptor)
        return descriptor

    monkeypatch.setattr(
        guard_module,
        "_sealed_capability_descriptor",
        record_descriptor,
    )

    def register() -> None:
        try:
            broker._register_provider(
                connection,  # type: ignore[arg-type]
                peer_pid=os.getpid(),
                peer_start_ticks=guard_module._process_start_ticks(os.getpid()) or 1,
            )
        except BaseException as exc:  # pragma: no cover - asserted below
            registration_errors.append(exc)

    registration = threading.Thread(target=register)
    registration.start()
    try:
        assert send_entered.wait(timeout=5)
        broker.stop()
    finally:
        release_send.set()
        registration.join(timeout=5)
        broker.stop()

    assert registration.is_alive() is False
    assert len(registration_errors) == 1
    assert str(registration_errors[0]) == "registration connection retired"
    assert sent_descriptors == []
    assert len(created_descriptors) == 1
    with pytest.raises(OSError):
        os.fstat(created_descriptors[0])
    assert broker._provider_identity is None
    assert broker._capability_identity is None
    assert broker._capability_fd is None


def test_broker_stop_closes_and_joins_blocked_request_handlers(
    tmp_path: Path,
) -> None:
    broker, root = _test_native_broker(tmp_path, task_id="BLOCKED-HANDLER")
    client = socket.socket(socket.AF_UNIX, guard_module._BROKER_SOCKET_TYPE)
    try:
        client.connect(str(broker.socket_path))
        _wait_until(lambda: len(broker._handler_threads) == 1)
        handlers = tuple(broker._handler_threads)

        broker.stop()

        assert all(handler.is_alive() is False for handler in handlers)
        assert broker._handler_threads == set()
        assert broker._handler_connections == set()
    finally:
        client.close()
        broker.stop()


@pytest.mark.parametrize("actor", ["handler", "observer", "publisher", "supervisor"])
def test_retirement_retries_until_every_live_broker_actor_quiesces(
    tmp_path: Path,
    actor: str,
) -> None:
    """A live broker actor retains its guard root across durable retries."""

    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    owner = ValidationLeaseOwner.worker(
        project_id="project",
        task_id=f"RETRY-{actor.upper()}",
        authority_generation="generation",
    )
    _guarded, root = install_native_validation_guard(
        {"PATH": os.environ.get("PATH", os.defpath)},
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=owner,
        timeout_seconds=10,
    )
    with guard_module._BROKER_REGISTRY_LOCK:
        broker = guard_module._BROKER_REGISTRY[root.resolve()]
    entered = threading.Event()
    release = threading.Event()
    retired = False

    def block() -> None:
        entered.set()
        assert release.wait(timeout=5)

    blocked = threading.Thread(target=block, daemon=True)
    blocked.start()
    assert entered.wait(timeout=5)

    class BlockingSupervisor:
        alive = True

        def poll(self) -> int | None:
            return None if self.alive else 0

        def wait(self, timeout: float | None = None) -> int:
            if self.alive:
                raise subprocess.TimeoutExpired("supervisor", timeout)
            return 0

    supervisor = BlockingSupervisor()
    if actor == "publisher":
        run = guard_module._NativeValidationRun(
            command="make test",
            command_identity="0" * 64,
            invocation_id="invocation",
            scope="full",
            started_at=time.monotonic(),
        )
        with broker._boundary_lock:
            broker._validation_runs["123:456"] = run

        def hold_callback_lock() -> None:
            with run.callback_lock:
                entered.set()
                assert release.wait(timeout=5)

        # Replace the generic blocker with the lock holder that makes the
        # terminal publisher remain alive during the first retirement pass.
        release.set()
        blocked.join(timeout=5)
        release.clear()
        entered.clear()
        blocked = threading.Thread(target=hold_callback_lock, daemon=True)
        blocked.start()
        assert entered.wait(timeout=5)
    elif actor == "handler":
        with broker._handler_lock:
            broker._handler_threads.add(blocked)
    elif actor == "observer":
        with broker._handler_lock:
            broker._supervisor_observers.add(blocked)
    else:
        with broker._handler_lock:
            broker._supervisor_processes.add(supervisor)  # type: ignore[arg-type]

    try:
        assert retire_native_validation_guard(
            root,
            validation_lease=lease,
            owner=owner,
        ) is False
        assert root.is_dir()
        with guard_module._BROKER_REGISTRY_LOCK:
            assert guard_module._BROKER_REGISTRY[root.resolve()] is broker

        if actor == "supervisor":
            supervisor.alive = False
        release.set()
        blocked.join(timeout=5)
        assert blocked.is_alive() is False
        if actor == "publisher":
            _wait_until(
                lambda: not any(
                    publisher.is_alive()
                    for publisher in broker._lifecycle_publishers
                )
            )

        assert retire_native_validation_guard(
            root,
            validation_lease=lease,
            owner=owner,
        ) is True
        retired = True
        with guard_module._BROKER_REGISTRY_LOCK:
            assert root.resolve() not in guard_module._BROKER_REGISTRY
    finally:
        release.set()
        blocked.join(timeout=5)
        if not retired:
            retire_native_validation_guard(
                root,
                validation_lease=lease,
                owner=owner,
            )


def test_register_provider_closes_descriptor_when_identity_validation_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    broker, _ = _test_native_broker(tmp_path, task_id="REGISTER-IDENTITY")
    descriptor = os.open(
        tmp_path / "register-capability",
        os.O_CREAT | os.O_RDWR,
        0o600,
    )
    monkeypatch.setattr(
        guard_module,
        "_provider_registration_is_trusted",
        lambda *_args: True,
    )
    monkeypatch.setattr(
        guard_module,
        "_sealed_capability_descriptor",
        lambda _secret: descriptor,
    )
    monkeypatch.setattr(
        guard_module,
        "_capability_descriptor_identity",
        lambda _descriptor: (_ for _ in ()).throw(RuntimeError("bad identity")),
    )
    try:
        with pytest.raises(RuntimeError, match="bad identity"):
            broker._register_provider(
                object(),  # type: ignore[arg-type]
                peer_pid=os.getpid(),
                peer_start_ticks=guard_module._process_start_ticks(os.getpid()) or 1,
            )
        with pytest.raises(OSError):
            os.fstat(descriptor)
    finally:
        with contextlib.suppress(OSError):
            os.close(descriptor)
        broker.stop()


def test_local_capability_closes_descriptor_when_identity_validation_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    broker, _ = _test_native_broker(tmp_path, task_id="LOCAL-IDENTITY")
    descriptor = os.open(tmp_path / "local-capability", os.O_CREAT | os.O_RDWR, 0o600)
    monkeypatch.setattr(
        guard_module,
        "_sealed_capability_descriptor",
        lambda _secret: descriptor,
    )
    monkeypatch.setattr(
        guard_module,
        "_capability_descriptor_identity",
        lambda _descriptor: (_ for _ in ()).throw(RuntimeError("bad identity")),
    )
    try:
        with pytest.raises(RuntimeError, match="bad identity"):
            broker.issue_local_test_capability()
        with pytest.raises(OSError):
            os.fstat(descriptor)
    finally:
        with contextlib.suppress(OSError):
            os.close(descriptor)
        broker.stop()


def test_provider_registration_closes_all_descriptors_after_partial_inherit_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = os.open(tmp_path / "first-provider-fd", os.O_CREAT | os.O_RDWR, 0o600)
    second = os.open(tmp_path / "second-provider-fd", os.O_CREAT | os.O_RDWR, 0o600)

    class RegistrationClient:
        def sendall(self, payload: bytes) -> None:
            assert payload == b"REGISTER\n"

    monkeypatch.setattr(
        guard_module,
        "_broker_socket",
        lambda _config: contextlib.nullcontext(RegistrationClient()),
    )
    monkeypatch.setattr(
        guard_module,
        "_receive_descriptors",
        lambda *_args, **_kwargs: (first, second),
    )
    real_set_inheritable = os.set_inheritable
    calls: list[int] = []

    def fail_second(descriptor: int, inheritable: bool) -> None:
        calls.append(descriptor)
        if len(calls) == 2:
            raise OSError("second descriptor rejected")
        real_set_inheritable(descriptor, inheritable)

    monkeypatch.setattr(guard_module.os, "set_inheritable", fail_second)
    try:
        with pytest.raises(OSError, match="second descriptor rejected"):
            guard_module._register_native_validation_provider(
                {
                    "provider_bootstrap": {
                        "command": guard_module._PROVIDER_LAUNCHER_NAME,
                    }
                }
            )

        assert calls == [first, second]
        with pytest.raises(OSError):
            os.fstat(first)
        with pytest.raises(OSError):
            os.fstat(second)
    finally:
        for descriptor in (first, second):
            with contextlib.suppress(OSError):
                os.close(descriptor)


def test_light_native_command_does_not_hold_validation_capacity(tmp_path: Path) -> None:
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    makefile_side_effect = tmp_path / "makefile-was-parsed"
    (tmp_path / "Makefile").write_text(
        f"$(shell touch {shlex.quote(str(makefile_side_effect))})\n",
        encoding="utf-8",
    )
    original_path = os.environ.get("PATH", os.defpath)
    assert is_heavyweight_validation_command(
        "make --help",
        executable_search_path=original_path,
        working_directory=tmp_path,
    ) is False
    guarded, _ = install_native_validation_guard(
        {"PATH": original_path},
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=ValidationLeaseOwner.worker(
            project_id="project",
            task_id="TASK-1",
            authority_generation="generation",
        ),
        timeout_seconds=10,
    )

    completed = subprocess.run(
        # A named ``help`` target still parses a task-controlled Makefile and
        # can execute parse-time shell expressions, so it is correctly
        # capacity-bearing.  GNU Make's standalone informational flag is the
        # actual light invocation covered by this regression.
        ["make", "--help"],
        cwd=tmp_path,
        env={**os.environ, **guarded},
        pass_fds=_guard_pass_fds(guarded),
        check=False,
        timeout=5,
    )

    assert completed.returncode == 0
    assert makefile_side_effect.exists() is False
    _wait_until(lambda: lease.status().owner_count == 0)


def test_native_reuse_policy_denies_exact_and_allows_structured_distinct_mode(
    tmp_path: Path,
) -> None:
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    real_bin = tmp_path / "real-bin"
    real_bin.mkdir()
    marker = tmp_path / "make-ran"
    real_make = real_bin / "make"
    real_make.write_text(
        '#!/bin/sh\nprintf "%s\\n" "$*" >> "$OOMPAH_TEST_NATIVE_MARKER"\n',
        encoding="utf-8",
    )
    real_make.chmod(0o700)
    real_pytest = real_bin / "pytest"
    real_pytest.write_text(
        '#!/bin/sh\nprintf "pytest %s\\n" "$*" >> '
        '"$OOMPAH_TEST_NATIVE_MARKER"\n',
        encoding="utf-8",
    )
    real_pytest.chmod(0o700)
    authority = {"state": "reuse_authoritative_gate"}
    telemetry: list[dict[str, str]] = []
    owner = ValidationLeaseOwner.auditor(
        project_id="project",
        task_id="AUDIT-REUSE",
        authority_generation="attempt-1",
    )
    guarded, root = install_native_validation_guard(
        {"PATH": f"{real_bin}{os.pathsep}{os.environ.get('PATH', os.defpath)}"},
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=owner,
        timeout_seconds=10,
        validation_reuse_policy={
            "decision": "reuse_authoritative_gate",
            "command": "make test",
            "attempt_id": "attempt-1",
        },
        validation_reuse_authority_check=lambda: authority["state"],
        validation_reuse_policy_handler=lambda **values: telemetry.append(values),
    )
    environment = {
        **os.environ,
        **guarded,
        "OOMPAH_TEST_NATIVE_MARKER": str(marker),
    }

    try:
        exact = subprocess.run(
            ["/bin/bash", "-c", "make test"],
            env=environment,
            pass_fds=_guard_pass_fds(guarded),
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        focused = subprocess.run(
            ["/bin/bash", "-c", "pytest tests/test_one.py -q"],
            env=environment,
            pass_fds=_guard_pass_fds(guarded),
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        distinct = subprocess.run(
            [
                "/bin/bash",
                "-c",
                "OOMPAH_VALIDATION_MODE=task_required_distinct "
                "OOMPAH_VALIDATION_JUSTIFICATION='serial race coverage' "
                "make test-serial",
            ],
            env=environment,
            pass_fds=_guard_pass_fds(guarded),
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        disguised_exact = subprocess.run(
            [
                "/bin/bash",
                "-c",
                "OOMPAH_VALIDATION_MODE=task_required_distinct "
                "OOMPAH_VALIDATION_JUSTIFICATION='still exact' make test",
            ],
            env=environment,
            pass_fds=_guard_pass_fds(guarded),
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        authority["state"] = "full_gate_required"
        required_again = subprocess.run(
            ["/bin/bash", "-c", "make test"],
            env=environment,
            pass_fds=_guard_pass_fds(guarded),
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )

        assert exact.returncode != 0
        assert focused.returncode == 0
        assert distinct.returncode == 0
        assert disguised_exact.returncode != 0
        assert required_again.returncode == 0
        assert marker.read_text(encoding="utf-8").splitlines() == [
            "pytest tests/test_one.py -q",
            "test-serial",
            "test",
        ]
        assert [entry["decision"] for entry in telemetry] == [
            "denied_reused_gate",
            "allowed_distinct_mode",
            "denied_reused_gate",
            "allowed_gate_now_required",
        ]
        assert telemetry[1]["justification"] == "serial race coverage"
        assert all(entry["invocation_id"] for entry in telemetry)
    finally:
        assert retire_native_validation_guard(
            root,
            validation_lease=lease,
            owner=owner,
        ) is True


@pytest.mark.parametrize(
    "policy_assignments",
    [
        (
            "OOMPAH_VALIDATION_MODE=$MODE "
            "OOMPAH_VALIDATION_JUSTIFICATION='literal reason'"
        ),
        (
            "OOMPAH_VALIDATION_MODE=task_required_distinct "
            "OOMPAH_VALIDATION_JUSTIFICATION='$WHY'"
        ),
        (
            "OOMPAH_VALIDATION_MODE=task_required_distinct "
            "OOMPAH_VALIDATION_JUSTIFICATION='$(make test)'"
        ),
        (
            "OOMPAH_VALIDATION_MODE=task_required_distinct "
            "OOMPAH_VALIDATION_JUSTIFICATION='$((1 + 1))'"
        ),
        (
            "OOMPAH_VALIDATION_MODE=task_required_distinct "
            "OOMPAH_VALIDATION_JUSTIFICATION='`make test`'"
        ),
        (
            "OOMPAH_VALIDATION_MODE=task_required_distinct "
            "OOMPAH_VALIDATION_JUSTIFICATION='reason*'"
        ),
    ],
)
def test_native_distinct_policy_rejects_nonliteral_structured_fields(
    tmp_path: Path,
    policy_assignments: str,
) -> None:
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    real_bin = tmp_path / "real-bin"
    real_bin.mkdir()
    marker = tmp_path / "make-ran"
    real_make = real_bin / "make"
    real_make.write_text(
        '#!/bin/sh\n: > "$OOMPAH_TEST_NATIVE_MARKER"\n',
        encoding="utf-8",
    )
    real_make.chmod(0o700)
    owner = ValidationLeaseOwner.auditor(
        project_id="project",
        task_id="AUDIT-LITERAL",
        authority_generation="attempt-1",
    )
    guarded, root = install_native_validation_guard(
        {"PATH": f"{real_bin}{os.pathsep}{os.environ.get('PATH', os.defpath)}"},
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=owner,
        timeout_seconds=10,
        validation_reuse_policy={
            "decision": "reuse_authoritative_gate",
            "command": "make test",
            "attempt_id": "attempt-1",
        },
        validation_reuse_authority_check=lambda: "reuse_authoritative_gate",
    )
    try:
        completed = subprocess.run(
            ["/bin/bash", "-c", f"{policy_assignments} make test-serial"],
            env={
                **os.environ,
                **guarded,
                "MODE": "task_required_distinct",
                "WHY": "expanded reason",
                "OOMPAH_TEST_NATIVE_MARKER": str(marker),
            },
            pass_fds=_guard_pass_fds(guarded),
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )

        assert completed.returncode != 0
        assert marker.exists() is False
        assert lease.status().owner_count == 0
    finally:
        assert retire_native_validation_guard(
            root,
            validation_lease=lease,
            owner=owner,
        ) is True


@pytest.mark.parametrize("prep_surface", ["lifecycle", "supervisor"])
def test_native_rechecks_reuse_authority_after_blocking_launch_prep(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    prep_surface: str,
) -> None:
    lease = ValidationResourceLease(
        tmp_path / "lease.sqlite3",
        capacity=1,
        poll_seconds=0.01,
    )
    gate = lease.acquire(
        ValidationLeaseOwner.exact_gate(
            project_id="project",
            task_id="GATE-1",
            authority_generation="gate-generation",
        )
    )
    real_bin = tmp_path / "real-bin"
    real_bin.mkdir()
    marker = tmp_path / "make-ran"
    real_make = real_bin / "make"
    real_make.write_text(
        '#!/bin/sh\n: > "$OOMPAH_TEST_NATIVE_MARKER"\n',
        encoding="utf-8",
    )
    real_make.chmod(0o700)
    authority = {"state": "reuse_authoritative_gate"}
    telemetry: list[dict[str, str]] = []
    lifecycle: list[dict[str, object]] = []
    prep_started = threading.Event()
    release_prep = threading.Event()

    def record_lifecycle(**values) -> None:
        lifecycle.append(values)
        if values["phase"] == "started" and prep_surface == "lifecycle":
            prep_started.set()
            assert release_prep.wait(timeout=5)

    if prep_surface == "supervisor":
        real_start_supervisor = guard_module._start_validation_lease_supervisor

        def blocking_start_supervisor(*args, **kwargs):
            prep_started.set()
            assert release_prep.wait(timeout=5)
            return real_start_supervisor(*args, **kwargs)

        monkeypatch.setattr(
            guard_module,
            "_start_validation_lease_supervisor",
            blocking_start_supervisor,
        )
    owner = ValidationLeaseOwner.auditor(
        project_id="project",
        task_id="AUDIT-QUEUED",
        authority_generation="attempt-1",
    )
    guarded, root = install_native_validation_guard(
        {"PATH": f"{real_bin}{os.pathsep}{os.environ.get('PATH', os.defpath)}"},
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=owner,
        timeout_seconds=10,
        validation_reuse_policy={
            "decision": "reuse_authoritative_gate",
            "command": "make test",
            "attempt_id": "attempt-1",
        },
        validation_reuse_authority_check=lambda: authority["state"],
        validation_reuse_policy_handler=lambda **values: telemetry.append(values),
        validation_command_handler=record_lifecycle,
    )
    environment = {
        **os.environ,
        **guarded,
        "OOMPAH_TEST_NATIVE_MARKER": str(marker),
    }
    completed: list[subprocess.CompletedProcess[str]] = []
    command = (
        "OOMPAH_VALIDATION_MODE=task_required_distinct "
        "OOMPAH_VALIDATION_JUSTIFICATION='serial race coverage' "
        "make test-serial"
    )
    worker = threading.Thread(
        target=lambda: completed.append(
            subprocess.run(
                ["/bin/bash", "-c", command],
                env=environment,
                pass_fds=_guard_pass_fds(guarded),
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
        ),
    )
    try:
        worker.start()
        _wait_until(lambda: lease.status().waiter_count == 1)
        gate.release()
        assert prep_started.wait(timeout=5)
        authority["state"] = "stale_authority"
        release_prep.set()
        worker.join(timeout=5)

        assert worker.is_alive() is False
        assert completed and completed[0].returncode != 0
        assert marker.exists() is False
        _wait_until(lambda: lease.status().owner_count == 0)
        assert [entry["decision"] for entry in telemetry] == [
            "denied_stale_authority",
        ]
        assert [entry["phase"] for entry in lifecycle] == [
            "started",
            "completed",
        ]
        assert lifecycle[1]["outcome"] == "authority_withdrawn"
        assert lifecycle[0]["invocation_id"] == lifecycle[1]["invocation_id"]
    finally:
        release_prep.set()
        gate.release()
        assert retire_native_validation_guard(
            root,
            validation_lease=lease,
            owner=owner,
        ) is True


def test_native_terminal_publication_before_transfer_prevents_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    real_bin = tmp_path / "real-bin"
    real_bin.mkdir()
    marker = tmp_path / "make-ran"
    real_make = real_bin / "make"
    real_make.write_text(
        '#!/bin/sh\n: > "$OOMPAH_TEST_NATIVE_MARKER"\n',
        encoding="utf-8",
    )
    real_make.chmod(0o700)
    owner = ValidationLeaseOwner.auditor(
        project_id="project",
        task_id="AUDIT-TERMINAL-WINS",
        authority_generation="attempt-1",
    )
    lifecycle: list[dict[str, object]] = []
    prep_started = threading.Event()
    publish_terminal = threading.Event()

    def terminal_before_transfer(*_args, terminal_handler, **_kwargs):
        prep_started.set()
        assert publish_terminal.wait(timeout=5)
        publication = terminal_handler("transport_error")
        if publication is not None:
            publication()
        observer = threading.Thread(target=lambda: None, daemon=True)
        observer.start()
        return observer

    monkeypatch.setattr(
        guard_module,
        "_start_validation_lease_supervisor",
        terminal_before_transfer,
    )
    guarded, root = install_native_validation_guard(
        {"PATH": f"{real_bin}{os.pathsep}{os.environ.get('PATH', os.defpath)}"},
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=owner,
        timeout_seconds=10,
        validation_command_handler=lambda **values: lifecycle.append(values),
    )
    completed: list[subprocess.CompletedProcess[str]] = []
    worker = threading.Thread(
        target=lambda: completed.append(
            subprocess.run(
                ["/bin/bash", "-c", "make test-serial"],
                env={
                    **os.environ,
                    **guarded,
                    "OOMPAH_TEST_NATIVE_MARKER": str(marker),
                },
                pass_fds=_guard_pass_fds(guarded),
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
        )
    )
    try:
        worker.start()
        assert prep_started.wait(timeout=5)
        publish_terminal.set()
        worker.join(timeout=5)

        assert worker.is_alive() is False
        assert completed and completed[0].returncode != 0
        assert marker.exists() is False
        _wait_until(lambda: lease.status().owner_count == 0)
        assert [entry["phase"] for entry in lifecycle] == [
            "started",
            "completed",
        ]
        assert lifecycle[1]["outcome"] == "transport_error"
        assert lifecycle[0]["invocation_id"] == lifecycle[1]["invocation_id"]
    finally:
        publish_terminal.set()
        assert retire_native_validation_guard(
            root,
            validation_lease=lease,
            owner=owner,
        ) is True


def test_native_supervisor_timeout_records_actual_terminal_reason(
    tmp_path: Path,
) -> None:
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    real_bin = tmp_path / "real-bin"
    real_bin.mkdir()
    real_make = real_bin / "make"
    real_make.write_text("#!/bin/sh\nsleep 10\n", encoding="utf-8")
    real_make.chmod(0o700)
    owner = ValidationLeaseOwner.auditor(
        project_id="project",
        task_id="AUDIT-TIMEOUT",
        authority_generation="attempt-1",
    )
    lifecycle: list[dict[str, object]] = []
    guarded, root = install_native_validation_guard(
        {"PATH": f"{real_bin}{os.pathsep}{os.environ.get('PATH', os.defpath)}"},
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=owner,
        timeout_seconds=1,
        validation_command_handler=lambda **values: lifecycle.append(values),
    )
    retired = False
    try:
        completed = subprocess.run(
            ["/bin/bash", "-c", "make test-serial"],
            env={**os.environ, **guarded},
            pass_fds=_guard_pass_fds(guarded),
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )

        assert completed.returncode != 0
        _wait_until(lambda: len(lifecycle) == 2)
        _wait_until(lambda: lease.status().owner_count == 0)
        assert [entry["phase"] for entry in lifecycle] == [
            "started",
            "completed",
        ]
        assert lifecycle[1]["outcome"] == "timed_out"
        assert lifecycle[1]["succeeded"] is False
        assert lifecycle[0]["invocation_id"] == lifecycle[1]["invocation_id"]
        observed = list(lifecycle)
        assert retire_native_validation_guard(
            root,
            validation_lease=lease,
            owner=owner,
        ) is True
        retired = True
        assert lifecycle == observed
    finally:
        if not retired:
            retire_native_validation_guard(
                root,
                validation_lease=lease,
                owner=owner,
            )


def test_native_explicit_withdrawal_records_terminal_reason(tmp_path: Path) -> None:
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    real_bin = tmp_path / "real-bin"
    real_bin.mkdir()
    real_make = real_bin / "make"
    real_make.write_text("#!/bin/sh\nsleep 10\n", encoding="utf-8")
    real_make.chmod(0o700)
    owner = ValidationLeaseOwner.auditor(
        project_id="project",
        task_id="AUDIT-WITHDRAWN",
        authority_generation="attempt-1",
    )
    lifecycle: list[dict[str, object]] = []
    guarded, root = install_native_validation_guard(
        {"PATH": f"{real_bin}{os.pathsep}{os.environ.get('PATH', os.defpath)}"},
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=owner,
        timeout_seconds=10,
        validation_command_handler=lambda **values: lifecycle.append(values),
    )
    process = subprocess.Popen(
        ["/bin/bash", "-c", "make test-serial"],
        env={**os.environ, **guarded},
        pass_fds=_guard_pass_fds(guarded),
    )
    retired = False
    try:
        _wait_until(
            lambda: lifecycle and lifecycle[0].get("phase") == "started"
        )
        (root / guard_module._CANCELLATION_NAME).touch(mode=0o600)

        assert process.wait(timeout=5) != 0
        _wait_until(lambda: len(lifecycle) == 2)
        _wait_until(lambda: lease.status().owner_count == 0)
        assert [entry["phase"] for entry in lifecycle] == [
            "started",
            "completed",
        ]
        assert lifecycle[1]["outcome"] == "authority_withdrawn"
        assert lifecycle[0]["invocation_id"] == lifecycle[1]["invocation_id"]
        observed = list(lifecycle)
        assert retire_native_validation_guard(
            root,
            validation_lease=lease,
            owner=owner,
        ) is True
        retired = True
        assert lifecycle == observed
    finally:
        with contextlib.suppress(ProcessLookupError):
            process.kill()
        with contextlib.suppress(subprocess.TimeoutExpired):
            process.wait(timeout=1)
        if not retired:
            retire_native_validation_guard(
                root,
                validation_lease=lease,
                owner=owner,
            )


def test_native_transport_failure_records_terminal_reason(tmp_path: Path) -> None:
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    real_bin = tmp_path / "real-bin"
    real_bin.mkdir()
    marker = tmp_path / "make-ran"
    real_make = real_bin / "make"
    real_make.write_text(
        '#!/bin/sh\n: > "$OOMPAH_TEST_NATIVE_MARKER"\n',
        encoding="utf-8",
    )
    real_make.chmod(0o700)
    owner = ValidationLeaseOwner.auditor(
        project_id="project",
        task_id="AUDIT-TRANSPORT",
        authority_generation="attempt-1",
    )
    lifecycle: list[dict[str, object]] = []
    started_callback = threading.Event()
    release_callback = threading.Event()

    def record_lifecycle(**values) -> None:
        lifecycle.append(values)
        if values["phase"] == "started":
            started_callback.set()
            assert release_callback.wait(timeout=5)

    guarded, root = install_native_validation_guard(
        {"PATH": f"{real_bin}{os.pathsep}{os.environ.get('PATH', os.defpath)}"},
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=owner,
        timeout_seconds=10,
        validation_command_handler=record_lifecycle,
    )
    process = subprocess.Popen(
        ["/bin/bash", "-c", "make test-serial"],
        env={
            **os.environ,
            **guarded,
            "OOMPAH_TEST_NATIVE_MARKER": str(marker),
        },
        pass_fds=_guard_pass_fds(guarded),
    )
    retired = False
    try:
        assert started_callback.wait(timeout=5)
        process.kill()
        process.wait(timeout=5)
        release_callback.set()

        _wait_until(lambda: len(lifecycle) == 2)
        _wait_until(lambda: lease.status().owner_count == 0)
        assert marker.exists() is False
        assert [entry["phase"] for entry in lifecycle] == [
            "started",
            "completed",
        ]
        assert lifecycle[1]["outcome"] == "transport_error"
        assert lifecycle[0]["invocation_id"] == lifecycle[1]["invocation_id"]
        observed = list(lifecycle)
        assert retire_native_validation_guard(
            root,
            validation_lease=lease,
            owner=owner,
        ) is True
        retired = True
        assert lifecycle == observed
    finally:
        release_callback.set()
        with contextlib.suppress(ProcessLookupError):
            process.kill()
        with contextlib.suppress(subprocess.TimeoutExpired):
            process.wait(timeout=1)
        if not retired:
            retire_native_validation_guard(
                root,
                validation_lease=lease,
                owner=owner,
            )


def test_native_post_transfer_cleanup_preserves_transport_reason(
    tmp_path: Path,
) -> None:
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    real_bin = tmp_path / "real-bin"
    real_bin.mkdir()
    marker = tmp_path / "make-ran"
    real_make = real_bin / "make"
    real_make.write_text(
        '#!/bin/sh\n: > "$OOMPAH_TEST_NATIVE_MARKER"\nsleep 10\n',
        encoding="utf-8",
    )
    real_make.chmod(0o700)
    owner = ValidationLeaseOwner.auditor(
        project_id="project",
        task_id="AUDIT-POST-TRANSFER",
        authority_generation="attempt-1",
    )
    lifecycle: list[dict[str, object]] = []
    guarded, root = install_native_validation_guard(
        {"PATH": f"{real_bin}{os.pathsep}{os.environ.get('PATH', os.defpath)}"},
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=owner,
        timeout_seconds=10,
        validation_command_handler=lambda **values: lifecycle.append(values),
    )
    process = subprocess.Popen(
        ["/bin/bash", "-c", "make test-serial"],
        env={
            **os.environ,
            **guarded,
            "OOMPAH_TEST_NATIVE_MARKER": str(marker),
        },
        pass_fds=_guard_pass_fds(guarded),
    )
    retired = False
    try:
        _wait_until(marker.exists)
        assert retire_native_validation_guard(
            root,
            validation_lease=lease,
            owner=owner,
            terminal_outcome="transport_error",
        ) is True
        retired = True

        assert process.wait(timeout=5) != 0
        _wait_until(lambda: lease.status().owner_count == 0)
        assert [entry["phase"] for entry in lifecycle] == [
            "started",
            "completed",
        ]
        assert lifecycle[1]["outcome"] == "transport_error"
        assert lifecycle[0]["invocation_id"] == lifecycle[1]["invocation_id"]
    finally:
        with contextlib.suppress(ProcessLookupError):
            process.kill()
        with contextlib.suppress(subprocess.TimeoutExpired):
            process.wait(timeout=1)
        if not retired:
            retire_native_validation_guard(
                root,
                validation_lease=lease,
                owner=owner,
                terminal_outcome="transport_error",
            )


def test_native_natural_exit_awaiting_item_records_stream_error_on_cleanup(
    tmp_path: Path,
) -> None:
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    real_bin = tmp_path / "real-bin"
    real_bin.mkdir()
    real_make = real_bin / "make"
    real_make.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    real_make.chmod(0o700)
    owner = ValidationLeaseOwner.auditor(
        project_id="project",
        task_id="AUDIT-EXITED-AWAITING-ITEM",
        authority_generation="attempt-1",
    )
    lifecycle: list[dict[str, object]] = []
    guarded, root = install_native_validation_guard(
        {"PATH": f"{real_bin}{os.pathsep}{os.environ.get('PATH', os.defpath)}"},
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=owner,
        timeout_seconds=10,
        validation_command_handler=lambda **values: lifecycle.append(values),
    )
    completed = subprocess.run(
        ["/bin/bash", "-c", "make test-serial"],
        env={**os.environ, **guarded},
        pass_fds=_guard_pass_fds(guarded),
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    retired = False
    try:
        assert completed.returncode == 0
        with guard_module._BROKER_REGISTRY_LOCK:
            broker = guard_module._BROKER_REGISTRY[root.resolve()]

        def supervisor_observed_exit() -> bool:
            with broker._boundary_lock:
                runs = tuple(broker._validation_runs.values())
            return bool(runs) and all(
                run.supervisor_outcome == "exited" for run in runs
            )

        _wait_until(supervisor_observed_exit)
        assert retire_native_validation_guard(
            root,
            validation_lease=lease,
            owner=owner,
        ) is True
        retired = True

        assert [entry["phase"] for entry in lifecycle] == [
            "started",
            "completed",
        ]
        assert lifecycle[1]["outcome"] == "stream_error"
        assert lifecycle[0]["invocation_id"] == lifecycle[1]["invocation_id"]
        assert lease.status().owner_count == 0
    finally:
        if not retired:
            retire_native_validation_guard(
                root,
                validation_lease=lease,
                owner=owner,
            )


@pytest.mark.parametrize(
    "failure_surface",
    ["second_pipe", "third_pipe", "observer_start"],
)
@pytest.mark.timeout(15)
def test_native_supervisor_setup_failure_restores_fd_baseline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_surface: str,
) -> None:
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    real_bin = tmp_path / "real-bin"
    real_bin.mkdir()
    marker = tmp_path / "make-ran"
    real_make = real_bin / "make"
    real_make.write_text(
        '#!/bin/sh\n: > "$OOMPAH_TEST_NATIVE_MARKER"\n',
        encoding="utf-8",
    )
    real_make.chmod(0o700)
    owner = ValidationLeaseOwner.auditor(
        project_id="project",
        task_id=f"AUDIT-FD-{failure_surface}",
        authority_generation="attempt-1",
    )
    guarded, root = install_native_validation_guard(
        {"PATH": f"{real_bin}{os.pathsep}{os.environ.get('PATH', os.defpath)}"},
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=owner,
        timeout_seconds=10,
    )
    baseline = _open_fd_snapshot()
    if failure_surface in {"second_pipe", "third_pipe"}:
        real_pipe2 = guard_module.os.pipe2
        calls = 0
        fail_at = 2 if failure_surface == "second_pipe" else 3

        def fail_pipe(flags: int) -> tuple[int, int]:
            nonlocal calls
            calls += 1
            if calls == fail_at:
                raise OSError(f"injected {failure_surface} failure")
            return real_pipe2(flags)

        monkeypatch.setattr(guard_module.os, "pipe2", fail_pipe)
    else:
        real_thread_start = guard_module.threading.Thread.start

        def fail_observer_start(thread: threading.Thread) -> None:
            if thread.name.startswith("native-validation-supervisor-status-"):
                raise RuntimeError("injected observer start failure")
            real_thread_start(thread)

        monkeypatch.setattr(
            guard_module.threading.Thread,
            "start",
            fail_observer_start,
        )
    try:
        completed = subprocess.run(
            ["/bin/bash", "-c", "make test-serial"],
            env={
                **os.environ,
                **guarded,
                "OOMPAH_TEST_NATIVE_MARKER": str(marker),
            },
            pass_fds=_guard_pass_fds(guarded),
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )

        assert completed.returncode != 0
        assert marker.exists() is False
        _wait_until(lambda: lease.status().owner_count == 0)
        try:
            _wait_until(lambda: _open_fd_snapshot() == baseline)
        except AssertionError:
            current = _open_fd_snapshot()
            pytest.fail(
                "native supervisor setup leaked descriptors: "
                f"added={_open_fd_targets(current - baseline)!r} "
                f"removed={_open_fd_targets(baseline - current)!r}"
            )
    finally:
        monkeypatch.undo()
        assert retire_native_validation_guard(
            root,
            validation_lease=lease,
            owner=owner,
        ) is True


def test_native_blocked_started_callback_serializes_retirement(
    tmp_path: Path,
) -> None:
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    real_bin = tmp_path / "real-bin"
    real_bin.mkdir()
    real_make = real_bin / "make"
    real_make.write_text("#!/bin/sh\nsleep 10\n", encoding="utf-8")
    real_make.chmod(0o700)
    owner = ValidationLeaseOwner.auditor(
        project_id="project",
        task_id="AUDIT-RETIRE-RACE",
        authority_generation="attempt-1",
    )
    lifecycle: list[dict[str, object]] = []
    started_callback = threading.Event()
    release_callback = threading.Event()

    def record_lifecycle(**values) -> None:
        lifecycle.append(values)
        if values["phase"] == "started":
            started_callback.set()
            assert release_callback.wait(timeout=5)

    guarded, root = install_native_validation_guard(
        {"PATH": f"{real_bin}{os.pathsep}{os.environ.get('PATH', os.defpath)}"},
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=owner,
        timeout_seconds=10,
        validation_command_handler=record_lifecycle,
    )
    process = subprocess.Popen(
        ["/bin/bash", "-c", "make test-serial"],
        env={**os.environ, **guarded},
        pass_fds=_guard_pass_fds(guarded),
    )
    retirement_started = threading.Event()
    retirement_result: list[bool] = []

    def retire() -> None:
        retirement_started.set()
        retirement_result.append(
            retire_native_validation_guard(
                root,
                validation_lease=lease,
                owner=owner,
            )
        )

    retirement = threading.Thread(target=retire)
    try:
        assert started_callback.wait(timeout=5)
        retirement.start()
        assert retirement_started.wait(timeout=5)
        assert len(lifecycle) == 1
        release_callback.set()
        retirement.join(timeout=5)

        assert retirement.is_alive() is False
        assert process.wait(timeout=5) != 0
        assert [entry["phase"] for entry in lifecycle] == [
            "started",
            "completed",
        ]
        assert lifecycle[1]["outcome"] == "authority_withdrawn"
        assert lifecycle[0]["invocation_id"] == lifecycle[1]["invocation_id"]
        assert len(retirement_result) == 1
        _wait_until(lambda: lease.status().owner_count == 0)
    finally:
        release_callback.set()
        with contextlib.suppress(ProcessLookupError):
            process.kill()
        with contextlib.suppress(subprocess.TimeoutExpired):
            process.wait(timeout=1)
        if retirement.is_alive():
            retirement.join(timeout=5)
        if root.exists():
            retire_native_validation_guard(
                root,
                validation_lease=lease,
                owner=owner,
            )


def test_native_item_completion_and_stop_publish_one_terminal_event(
    tmp_path: Path,
) -> None:
    """A direct completion owns publication before retirement can observe it."""

    broker, _ = _test_native_broker(tmp_path, task_id="ITEM-STOP-RACE")
    lifecycle: list[dict[str, object]] = []
    completed_entered = threading.Event()
    release_completed = threading.Event()

    def record_lifecycle(**values) -> None:
        lifecycle.append(values)
        if values["phase"] == "completed":
            completed_entered.set()
            assert release_completed.wait(timeout=5)

    broker.validation_command_handler = record_lifecycle
    group = "321:654"
    item_id = "item-321"
    broker._start_validation_lifecycle(
        group,
        command="make test",
        command_identity="f" * 64,
        classification=ValidationCommandClassification(True, "full"),
        invocation_id="item-stop-race",
    )
    with broker._boundary_lock:
        broker._boundary_items[group] = item_id
    completion_results: list[bool] = []
    stop_results: list[bool] = []
    completion = threading.Thread(
        target=lambda: completion_results.append(
            broker.complete_validation_item(
                "f" * 64,
                item_id,
                succeeded=True,
                outcome="passed",
            )
        )
    )
    stop = threading.Thread(target=lambda: stop_results.append(broker.stop()))
    try:
        completion.start()
        assert completed_entered.wait(timeout=5)
        stop.start()
        stop.join(timeout=5)

        assert stop.is_alive() is False
        assert stop_results == [False]
        assert completion.is_alive() is True
        assert [entry["phase"] for entry in lifecycle] == ["started", "completed"]

        release_completed.set()
        completion.join(timeout=5)

        assert completion.is_alive() is False
        assert completion_results == [True]
        assert [entry["phase"] for entry in lifecycle] == ["started", "completed"]
        assert broker.stop() is True
    finally:
        release_completed.set()
        completion.join(timeout=5)
        stop.join(timeout=5)
        broker.stop()


def test_native_indefinite_started_callback_keeps_retirement_bounded(
    tmp_path: Path,
) -> None:
    """A stuck telemetry consumer defers cleanup rather than deadlocking it."""

    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    real_bin = tmp_path / "real-bin"
    real_bin.mkdir()
    real_make = real_bin / "make"
    real_make.write_text("#!/bin/sh\nsleep 10\n", encoding="utf-8")
    real_make.chmod(0o700)
    owner = ValidationLeaseOwner.auditor(
        project_id="project",
        task_id="AUDIT-INDEFINITE-CALLBACK",
        authority_generation="attempt-1",
    )
    lifecycle: list[dict[str, object]] = []
    started_callback = threading.Event()
    release_callback = threading.Event()

    def record_lifecycle(**values) -> None:
        lifecycle.append(values)
        if values["phase"] == "started":
            started_callback.set()
            # Deliberately no timeout: this models an indefinitely blocked
            # consumer while the test controls when it can make progress.
            release_callback.wait()

    guarded, root = install_native_validation_guard(
        {"PATH": f"{real_bin}{os.pathsep}{os.environ.get('PATH', os.defpath)}"},
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=owner,
        timeout_seconds=10,
        validation_command_handler=record_lifecycle,
    )
    process = subprocess.Popen(
        ["/bin/bash", "-c", "make test-serial"],
        env={**os.environ, **guarded},
        pass_fds=_guard_pass_fds(guarded),
    )
    try:
        assert started_callback.wait(timeout=5)
        started_at = time.monotonic()
        assert retire_native_validation_guard(
            root,
            validation_lease=lease,
            owner=owner,
        ) is False
        assert time.monotonic() - started_at < 3
        assert root.exists()
        _wait_until(lambda: lease.status().owner_count == 0)

        release_callback.set()
        assert process.wait(timeout=5) != 0
        _wait_until(lambda: [entry["phase"] for entry in lifecycle] == [
            "started",
            "completed",
        ])
        assert retire_native_validation_guard(
            root,
            validation_lease=lease,
            owner=owner,
        ) is True
    finally:
        release_callback.set()
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        if root.exists():
            retire_native_validation_guard(
                root,
                validation_lease=lease,
                owner=owner,
            )


def test_native_reuse_policy_fails_closed_when_live_authority_raises(
    tmp_path: Path,
) -> None:
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    real_bin = tmp_path / "real-bin"
    real_bin.mkdir()
    marker = tmp_path / "make-ran"
    real_make = real_bin / "make"
    real_make.write_text(
        '#!/bin/sh\n: > "$OOMPAH_TEST_NATIVE_MARKER"\n',
        encoding="utf-8",
    )
    real_make.chmod(0o700)
    owner = ValidationLeaseOwner.auditor(
        project_id="project",
        task_id="AUDIT-STALE",
        authority_generation="attempt-1",
    )

    def unavailable_authority() -> str:
        raise RuntimeError("tracker unavailable")

    guarded, root = install_native_validation_guard(
        {"PATH": f"{real_bin}{os.pathsep}{os.environ.get('PATH', os.defpath)}"},
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=owner,
        timeout_seconds=10,
        validation_reuse_policy={
            "decision": "reuse_authoritative_gate",
            "command": "make test",
            "attempt_id": "attempt-1",
        },
        validation_reuse_authority_check=unavailable_authority,
    )
    try:
        completed = subprocess.run(
            ["/bin/bash", "-c", "make test"],
            env={
                **os.environ,
                **guarded,
                "OOMPAH_TEST_NATIVE_MARKER": str(marker),
            },
            pass_fds=_guard_pass_fds(guarded),
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )

        assert completed.returncode != 0
        assert marker.exists() is False
        assert lease.status().owner_count == 0
    finally:
        assert retire_native_validation_guard(
            root,
            validation_lease=lease,
            owner=owner,
        ) is True


def test_absolute_bash_env_unset_heavy_command_waits_for_validation_capacity(
    tmp_path: Path,
) -> None:
    """Absolute tools cannot bypass the guard by removing its environment."""
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    gate = lease.acquire(
        ValidationLeaseOwner.exact_gate(
            project_id="project",
            task_id="GATE-1",
            authority_generation="gate-generation",
        )
    )
    marker = tmp_path / "absolute-command-started"
    absolute_tools = tmp_path / "absolute-tools"
    absolute_tools.mkdir()
    absolute_python = absolute_tools / "python"
    absolute_python.write_text(
        '#!/bin/sh\n: > "$OOMPAH_TEST_NATIVE_MARKER"\n',
        encoding="utf-8",
    )
    absolute_python.chmod(0o700)
    guarded, _ = install_native_validation_guard(
        {"PATH": os.environ.get("PATH", os.defpath)},
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=ValidationLeaseOwner.worker(
            project_id="project",
            task_id="TASK-1",
            authority_generation="generation",
        ),
        timeout_seconds=10,
    )
    guarded["OOMPAH_TEST_NATIVE_MARKER"] = str(marker)

    process = subprocess.Popen(
        [
            "/bin/bash",
            "-lc",
            (
                "env -u OOMPAH_NATIVE_VALIDATION_GUARD "
                f"{shlex.quote(str(absolute_python))} -m pytest "
                "tests/test_one.py tests/test_two.py"
            ),
        ],
        env={**os.environ, **guarded},
        pass_fds=_guard_pass_fds(guarded),
    )
    try:
        _wait_until(lambda: lease.status().waiter_count == 1)
        status = lease.status()
        assert status.owner_count == 1
        assert status.owners[0]["task_id"] == "GATE-1"
        assert status.waiters[0]["task_id"] == "TASK-1"
        assert marker.exists() is False
    finally:
        gate.release()

    assert process.wait(timeout=5) == 0
    assert marker.exists() is True
    # The absolute Bash returns after its heavy descendant exits, while the
    # independent supervisor retains its duplicate until it has observed that
    # exact process group quiescent.  That asynchronous retirement is the
    # safety fence which prevents a briefly escaped descendant from releasing
    # capacity early, so assert the durable postcondition rather than a
    # scheduler-timing-dependent instant immediately after wait().
    _wait_until(lambda: lease.status().owner_count == 0)


def test_run_tests_sh_waits_for_validation_capacity(
    tmp_path: Path,
) -> None:
    """A Codex-style ``scripts/run-tests.sh serial`` launch cannot bypass.

    The live OOMPAH-577 escape used the script's ``/usr/bin/env bash`` shebang
    below an absolute provider shell.  It must remain behind the exact-gate
    owner before its three-file pytest invocation can reach the interpreter.
    """

    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    gate = lease.acquire(
        ValidationLeaseOwner.exact_gate(
            project_id="project",
            task_id="GATE-1",
            authority_generation="gate-generation",
        )
    )
    marker = tmp_path / "pytest-started"
    tools = tmp_path / "tools"
    tools.mkdir()
    python = tools / "python"
    python.write_text(
        '#!/bin/sh\n: > "$OOMPAH_TEST_NATIVE_MARKER"\n',
        encoding="utf-8",
    )
    python.chmod(0o700)
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    run_tests = scripts / "run-tests.sh"
    run_tests.write_text(
        "#!/usr/bin/env bash\n"
        "exec python -m pytest "
        "tests/test_terminal_transition_coordinator.py "
        "tests/test_orchestrator_handlers.py "
        "tests/test_delivery_plane_recovery.py\n",
        encoding="utf-8",
    )
    run_tests.chmod(0o700)
    # The guard owns a Unix-domain broker socket.  Pytest's descriptive
    # per-test directory here is long enough to exceed sockaddr_un.sun_path
    # before the route itself can be exercised, so keep only this disposable
    # runtime root short.
    runtime_parent = Path(tempfile.mkdtemp(prefix="oompah-846-"))
    guarded, root = install_native_validation_guard(
        {"PATH": f"{tools}{os.pathsep}{os.environ.get('PATH', os.defpath)}"},
        runtime_root=runtime_parent / "guard",
        validation_lease=lease,
        owner=ValidationLeaseOwner.worker(
            project_id="project",
            task_id="TASK-577",
            authority_generation="generation",
        ),
        timeout_seconds=10,
    )
    process = subprocess.Popen(
        ["/bin/bash", "-lc", "scripts/run-tests.sh serial"],
        cwd=tmp_path,
        env={
            **os.environ,
            **guarded,
            "OOMPAH_TEST_NATIVE_MARKER": str(marker),
        },
        pass_fds=_guard_pass_fds(guarded),
    )
    try:
        _wait_until(lambda: lease.status().waiter_count == 1)
        status = lease.status()
        assert status.owner_count == 1
        assert status.owners[0]["task_id"] == "GATE-1"
        assert status.waiters[0]["task_id"] == "TASK-577"
        assert marker.exists() is False
    finally:
        gate.release()

    try:
        assert process.wait(timeout=5) == 0
        assert marker.exists() is True
        _wait_until(lambda: lease.status().owner_count == 0)
    finally:
        try:
            time.sleep(0.5)
            retire_native_validation_guard(
                root,
                validation_lease=lease,
                owner=ValidationLeaseOwner.worker(
                    project_id="project",
                    task_id="TASK-577",
                    authority_generation="generation",
                ),
            )
        finally:
            shutil.rmtree(runtime_parent, ignore_errors=True)


def test_abs_make_waits_for_validation_capacity(tmp_path: Path) -> None:
    """A sandbox's absolute ``/usr/bin/make test`` remains brokered.

    OOMPAH-643 used this form below the Codex sandbox's absolute Bash, with a
    PATH assignment that intentionally omitted the task virtualenv.  The
    BASH_ENV boundary must classify that outer command before the absolute
    Make executable can start its parallel pytest descendants.
    """

    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    gate = lease.acquire(
        ValidationLeaseOwner.exact_gate(
            project_id="project",
            task_id="GATE-1",
            authority_generation="gate-generation",
        )
    )
    marker = tmp_path / "make-started"
    (tmp_path / "Makefile").write_text(
        f"test:\n\t@touch {shlex.quote(str(marker))}\n",
        encoding="utf-8",
    )
    owner = ValidationLeaseOwner.worker(
        project_id="project",
        task_id="TASK-643",
        authority_generation="generation",
    )
    runtime_parent = Path(tempfile.mkdtemp(prefix="oompah-846-"))
    guarded, root = install_native_validation_guard(
        {"PATH": os.environ.get("PATH", os.defpath)},
        runtime_root=runtime_parent / "guard",
        validation_lease=lease,
        owner=owner,
        timeout_seconds=10,
    )
    process = subprocess.Popen(
        [
            "/bin/bash",
            "-c",
            'PATH="/usr/local/bin:/usr/bin:/bin" /usr/bin/make test',
        ],
        cwd=tmp_path,
        env={**os.environ, **guarded},
        pass_fds=_guard_pass_fds(guarded),
    )
    try:
        _wait_until(lambda: lease.status().waiter_count == 1)
        status = lease.status()
        assert status.owner_count == 1
        assert status.owners[0]["task_id"] == "GATE-1"
        assert status.waiters[0]["task_id"] == "TASK-643"
        assert marker.exists() is False
    finally:
        gate.release()

    try:
        assert process.wait(timeout=5) == 0
        assert marker.exists() is True
        _wait_until(lambda: lease.status().owner_count == 0)
    finally:
        try:
            time.sleep(0.5)
            retire_native_validation_guard(
                root,
                validation_lease=lease,
                owner=owner,
            )
        finally:
            shutil.rmtree(runtime_parent, ignore_errors=True)


def test_absolute_login_shell_cannot_run_task_home_profile_before_guard(
    tmp_path: Path,
) -> None:
    """The provider's absolute Bash cannot execute a task-controlled profile."""

    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    task_home = tmp_path / "task-home"
    task_home.mkdir()
    profile_marker = tmp_path / "profile-ran"
    heavy_marker = tmp_path / "profile-heavy-command-ran"
    resolution_marker = tmp_path / "profile-command-resolution"
    task_bin = tmp_path / "task-bin"
    task_bin.mkdir()
    task_probe = task_bin / "validation-profile-probe"
    task_probe.write_text("#!/bin/sh\nprintf task-profile\n", encoding="utf-8")
    task_probe.chmod(0o700)
    task_make = task_bin / "make"
    task_make.write_text(
        f'#!/bin/sh\n: > "{heavy_marker}"\n',
        encoding="utf-8",
    )
    task_make.chmod(0o700)
    (task_home / ".bash_profile").write_text(
        (
            f': > "{profile_marker}"\n'
            f'export PATH="{task_bin}:$PATH"\n'
            f'command -v validation-profile-probe > "{resolution_marker}"\n'
            "make test\n"
        ),
        encoding="utf-8",
    )
    guarded, root = install_native_validation_guard(
        {
            "HOME": str(task_home),
            "PATH": os.environ.get("PATH", os.defpath),
        },
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=ValidationLeaseOwner.worker(
            project_id="project",
            task_id="TASK-1",
            authority_generation="generation",
        ),
        timeout_seconds=10,
    )

    completed = subprocess.run(
        ["/bin/bash", "-lc", "printf trusted"],
        env={**os.environ, **guarded},
        pass_fds=_guard_pass_fds(guarded),
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )

    assert completed.returncode == 0
    assert completed.stdout == "trusted"
    assert guarded["HOME"] == str(root / guard_module._NATIVE_HOME_NAME)
    assert guarded["HOME"] != str(task_home)
    assert list(Path(guarded["HOME"]).iterdir()) == []
    assert profile_marker.exists() is False
    assert heavy_marker.exists() is False
    assert resolution_marker.exists() is False
    _wait_until(lambda: lease.status().owner_count == 0)


def test_native_guard_preserves_only_service_trusted_codex_home(
    tmp_path: Path,
    monkeypatch,
) -> None:
    trusted_codex_home = tmp_path / "trusted-codex-home"
    task_codex_home = tmp_path / "task-codex-home"
    monkeypatch.setenv("CODEX_HOME", str(trusted_codex_home))
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)

    guarded, root = install_native_validation_guard(
        {
            "CODEX_HOME": str(task_codex_home),
            "HOME": str(tmp_path / "task-home"),
            "PATH": os.environ.get("PATH", os.defpath),
        },
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=ValidationLeaseOwner.worker(
            project_id="project",
            task_id="TASK-1",
            authority_generation="generation",
        ),
        timeout_seconds=10,
    )

    assert guarded["CODEX_HOME"] == str(trusted_codex_home)
    assert guarded["CODEX_HOME"] != str(task_codex_home)
    assert guarded["HOME"] == str(root / guard_module._NATIVE_HOME_NAME)


def test_nested_home_login_shell_waits_before_task_profile_startup(
    tmp_path: Path,
) -> None:
    """Inline HOME cannot move nested login startup ahead of the lease."""

    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    gate = lease.acquire(
        ValidationLeaseOwner.exact_gate(
            project_id="project",
            task_id="GATE-1",
            authority_generation="gate-generation",
        )
    )
    task_home = tmp_path / "nested-task-home"
    task_home.mkdir()
    profile_marker = tmp_path / "nested-profile-ran"
    heavy_marker = tmp_path / "nested-profile-heavy-command-ran"
    task_bin = tmp_path / "nested-task-bin"
    task_bin.mkdir()
    task_make = task_bin / "make"
    task_make.write_text(
        f'#!/bin/sh\n: > "{heavy_marker}"\n',
        encoding="utf-8",
    )
    task_make.chmod(0o700)
    (task_home / ".bash_profile").write_text(
        (
            f': > "{profile_marker}"\n'
            f'export PATH="{task_bin}:$PATH"\n'
            "make test\n"
        ),
        encoding="utf-8",
    )
    guarded, _ = install_native_validation_guard(
        {"PATH": os.environ.get("PATH", os.defpath)},
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=ValidationLeaseOwner.worker(
            project_id="project",
            task_id="TASK-1",
            authority_generation="generation",
        ),
        timeout_seconds=10,
    )
    command = (
        f"HOME={shlex.quote(str(task_home))} "
        "bash -lc 'printf trusted'"
    )
    process = subprocess.Popen(
        ["/bin/bash", "-c", command],
        env={**os.environ, **guarded},
        pass_fds=_guard_pass_fds(guarded),
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        _wait_until(lambda: lease.status().waiter_count == 1)
        assert profile_marker.exists() is False
        assert heavy_marker.exists() is False
    finally:
        gate.release()

    assert process.communicate(timeout=5)[0] == "trusted"
    assert process.returncode == 0
    assert profile_marker.exists() is True
    assert heavy_marker.exists() is True
    _wait_until(lambda: lease.status().owner_count == 0)


def test_absolute_bash_light_command_restores_guard_for_descendants(
    tmp_path: Path,
) -> None:
    """The one-shot Bash hook leaves every later absolute Bash guarded."""
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    observed_bash_env = tmp_path / "observed-bash-env"
    guarded, root = install_native_validation_guard(
        {"PATH": os.environ.get("PATH", os.defpath)},
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=ValidationLeaseOwner.worker(
            project_id="project",
            task_id="TASK-1",
            authority_generation="generation",
        ),
        timeout_seconds=10,
    )
    guarded["OOMPAH_TEST_BASH_ENV_MARKER"] = str(observed_bash_env)

    command = (
        "/bin/bash -c "
        "'printf \"%s\" \"$BASH_ENV\" > "
        "\"$OOMPAH_TEST_BASH_ENV_MARKER\"'"
    )
    completed = subprocess.run(
        [
            "/bin/bash",
            "-c",
            command,
        ],
        env={**os.environ, **guarded},
        pass_fds=_guard_pass_fds(guarded),
        check=False,
        timeout=5,
    )

    assert completed.returncode == 0
    assert observed_bash_env.read_text(encoding="utf-8") == guarded["BASH_ENV"]
    assert not guarded["BASH_ENV"].endswith("validation-guard-bash-reentry")
    assert consume_native_validation_boundary(root, command, "item-1") is True
    assert consume_native_validation_boundary(root, command, "item-1") is False
    _wait_until(lambda: lease.status().owner_count == 0)


@pytest.mark.timeout(20)
def test_parallel_native_command_boundaries_are_consumed_independently(
    tmp_path: Path,
) -> None:
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    guarded, root = install_native_validation_guard(
        {"PATH": os.environ.get("PATH", os.defpath)},
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=ValidationLeaseOwner.worker(
            project_id="project",
            task_id="TASK-1",
            authority_generation="generation",
        ),
        timeout_seconds=10,
    )

    processes: list[subprocess.Popen[str]] = []
    try:
        first = subprocess.Popen(
            ["/bin/bash", "-c", "printf first"],
            env={**os.environ, **guarded},
            pass_fds=_guard_pass_fds(guarded),
            stdout=subprocess.PIPE,
            text=True,
        )
        processes.append(first)
        second = subprocess.Popen(
            ["/bin/bash", "-c", "printf second"],
            env={**os.environ, **guarded},
            pass_fds=_guard_pass_fds(guarded),
            stdout=subprocess.PIPE,
            text=True,
        )
        processes.append(second)

        assert first.communicate(timeout=5)[0] == "first"
        assert second.communicate(timeout=5)[0] == "second"
        assert first.returncode == 0
        assert second.returncode == 0
        assert (
            consume_native_validation_boundary(root, "printf first", "item-1")
            is True
        )
        assert (
            consume_native_validation_boundary(root, "printf second", "item-2")
            is True
        )
        assert (
            consume_native_validation_boundary(root, "printf first", "item-3")
            is False
        )
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
            try:
                process.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)


def test_late_background_boundary_cannot_spoof_later_item(tmp_path: Path) -> None:
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    guarded, root = install_native_validation_guard(
        {"PATH": os.environ.get("PATH", os.defpath)},
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=ValidationLeaseOwner.worker(
            project_id="project",
            task_id="TASK-1",
            authority_generation="generation",
        ),
        timeout_seconds=10,
    )

    command = "bash -c \"sleep 0.2; bash -c 'printf nested >/dev/null'\" &"
    outer = subprocess.run(
        [
            "/bin/bash",
            "-c",
            command,
        ],
        env={**os.environ, **guarded},
        pass_fds=_guard_pass_fds(guarded),
        check=False,
        timeout=5,
    )

    assert outer.returncode == 0
    assert consume_native_validation_boundary(root, command, "item-1") is True
    time.sleep(0.4)
    assert consume_native_validation_boundary(root, command, "item-2") is False
    assert consume_native_validation_boundary(
        root,
        "printf nested >/dev/null",
        "item-3",
    ) is False


def test_cross_session_capability_cannot_forge_boundary(tmp_path: Path) -> None:
    first_lease = ValidationResourceLease(
        tmp_path / "first.sqlite3", poll_seconds=0.01
    )
    second_lease = ValidationResourceLease(
        tmp_path / "second.sqlite3", poll_seconds=0.01
    )
    first, _first_root = install_native_validation_guard(
        {"PATH": os.environ.get("PATH", os.defpath)},
        runtime_root=tmp_path / "first-guard",
        validation_lease=first_lease,
        owner=ValidationLeaseOwner.worker(
            project_id="project",
            task_id="TASK-1",
            authority_generation="first",
        ),
        timeout_seconds=10,
    )
    second, second_root = install_native_validation_guard(
        {"PATH": os.environ.get("PATH", os.defpath)},
        runtime_root=tmp_path / "second-guard",
        validation_lease=second_lease,
        owner=ValidationLeaseOwner.worker(
            project_id="project",
            task_id="TASK-2",
            authority_generation="second",
        ),
        timeout_seconds=10,
    )
    forged = dict(second)
    forged["OOMPAH_NATIVE_VALIDATION_CAPABILITY_FD"] = first[
        "OOMPAH_NATIVE_VALIDATION_CAPABILITY_FD"
    ]

    completed = subprocess.run(
        ["/bin/bash", "-c", "printf forged"],
        env={**os.environ, **forged},
        pass_fds=_guard_pass_fds(forged),
        check=False,
        timeout=5,
    )

    assert completed.returncode != 0
    assert consume_native_validation_boundary(
        second_root,
        "printf forged",
        "forged-item",
    ) is False


def test_absolute_bash_reentry_preserves_exact_flags_and_argv(tmp_path: Path) -> None:
    """The BASH_ENV boundary replays the kernel argv without string joining."""

    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    output = tmp_path / "bash-argv"
    guarded, _ = install_native_validation_guard(
        {"PATH": os.environ.get("PATH", os.defpath)},
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=ValidationLeaseOwner.worker(
            project_id="project",
            task_id="TASK-1",
            authority_generation="generation",
        ),
        timeout_seconds=10,
    )
    guarded["OOMPAH_TEST_BASH_ARGV"] = str(output)

    completed = subprocess.run(
        [
            "/bin/bash",
            "-eu",
            "-O",
            "nullglob",
            "-c",
            'printf "%s|%s|%s" "$0" "$1" "$(shopt -q nullglob; printf %s $?)" '
            '> "$OOMPAH_TEST_BASH_ARGV"',
            "chosen-argv-zero",
            "one argument",
        ],
        env={**os.environ, **guarded},
        pass_fds=_guard_pass_fds(guarded),
        check=False,
        timeout=5,
    )

    assert completed.returncode == 0
    assert output.read_text(encoding="utf-8") == "chosen-argv-zero|one argument|0"
    _wait_until(lambda: lease.status().owner_count == 0)


def test_absolute_bash_reentry_preserves_process_argv_zero(tmp_path: Path) -> None:
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    output = tmp_path / "bash-argv-zero"
    guarded, _ = install_native_validation_guard(
        {"PATH": os.environ.get("PATH", os.defpath)},
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=ValidationLeaseOwner.worker(
            project_id="project",
            task_id="TASK-1",
            authority_generation="generation",
        ),
        timeout_seconds=10,
    )
    guarded["OOMPAH_TEST_BASH_ARGV"] = str(output)

    completed = subprocess.run(
        [
            "custom-native-bash",
            "-c",
            'printf "%s" "$0" > "$OOMPAH_TEST_BASH_ARGV"',
        ],
        executable="/bin/bash",
        env={**os.environ, **guarded},
        pass_fds=_guard_pass_fds(guarded),
        check=False,
        timeout=5,
    )

    assert completed.returncode == 0
    assert output.read_text(encoding="utf-8") == "custom-native-bash"


def test_absolute_non_bash_descendant_is_classified_before_spawn(
    tmp_path: Path,
) -> None:
    """An absolute /bin/sh child cannot escape the guarded outer Bash."""

    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    gate = lease.acquire(
        ValidationLeaseOwner.exact_gate(
            project_id="project",
            task_id="GATE-1",
            authority_generation="gate-generation",
        )
    )
    marker = tmp_path / "non-bash-descendant"
    guarded, _ = install_native_validation_guard(
        {"PATH": os.environ.get("PATH", os.defpath)},
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=ValidationLeaseOwner.worker(
            project_id="project",
            task_id="TASK-1",
            authority_generation="generation",
        ),
        timeout_seconds=10,
    )
    guarded["OOMPAH_TEST_NATIVE_MARKER"] = str(marker)
    command = '/bin/sh -c \'/usr/bin/touch "$OOMPAH_TEST_NATIVE_MARKER"\''
    process = subprocess.Popen(
        ["/bin/bash", "-c", command],
        env={**os.environ, **guarded},
        pass_fds=_guard_pass_fds(guarded),
    )
    try:
        _wait_until(lambda: lease.status().waiter_count == 1)
        assert marker.exists() is False
    finally:
        gate.release()

    assert process.wait(timeout=5) == 0
    assert marker.exists() is True


def test_guard_environment_mutation_fails_closed_to_capacity(tmp_path: Path) -> None:
    """A command cannot drop BASH_ENV before capacity classification."""

    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    gate = lease.acquire(
        ValidationLeaseOwner.exact_gate(
            project_id="project",
            task_id="GATE-1",
            authority_generation="gate-generation",
        )
    )
    marker = tmp_path / "mutated-guard"
    guarded, _ = install_native_validation_guard(
        {"PATH": os.environ.get("PATH", os.defpath)},
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=ValidationLeaseOwner.worker(
            project_id="project",
            task_id="TASK-1",
            authority_generation="generation",
        ),
        timeout_seconds=10,
    )
    guarded["OOMPAH_TEST_NATIVE_MARKER"] = str(marker)
    process = subprocess.Popen(
        [
            "/bin/bash",
            "-c",
            'unset BASH_ENV; : > "$OOMPAH_TEST_NATIVE_MARKER"',
        ],
        env={**os.environ, **guarded},
        pass_fds=_guard_pass_fds(guarded),
    )
    try:
        _wait_until(lambda: lease.status().waiter_count == 1)
        assert marker.exists() is False
    finally:
        gate.release()

    assert process.wait(timeout=5) == 0
    assert marker.exists() is True


def test_inherited_dynamic_loader_controls_are_removed_before_native_provider(
    tmp_path: Path,
) -> None:
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    guarded, _ = install_native_validation_guard(
        {
            "PATH": os.environ.get("PATH", os.defpath),
            "LD_PRELOAD": "/task/hook.so",
            "LD_AUDIT": "/task/audit.so",
            "LD_LIBRARY_PATH": "/task/lib",
            "DYLD_INSERT_LIBRARIES": "/task/hook.dylib",
            "_RLD_LIST": "/task/tru64-hook.so",
            "LDR_CNTRL": "LOADPUBLIC@PREREAD_SHLIB",
            "LDR_PRELOAD": "/task/aix-hook.so",
            "LIBPATH": "/task/aix-lib",
            "SHLIB_PATH": "/task/hpux-lib",
        },
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=ValidationLeaseOwner.worker(
            project_id="project",
            task_id="TASK-1",
            authority_generation="generation",
        ),
        timeout_seconds=10,
    )

    assert all(
        name not in guarded
        for name in (
            "LD_PRELOAD",
            "LD_AUDIT",
            "LD_LIBRARY_PATH",
            "DYLD_INSERT_LIBRARIES",
            "_RLD_LIST",
            "LDR_CNTRL",
            "LDR_PRELOAD",
            "LIBPATH",
            "SHLIB_PATH",
        )
    )


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="ELF loader test")
def test_inline_ld_preload_constructor_waits_for_validation_capacity(
    tmp_path: Path,
) -> None:
    """A loader constructor cannot run before the shell command owns capacity."""

    compiler = shutil.which("cc")
    if compiler is None:
        pytest.skip("C compiler is unavailable")
    source = tmp_path / "loader-hook.c"
    library = tmp_path / "loader-hook.so"
    marker = tmp_path / "loader-constructor-ran"
    source.write_text(
        """
#include <fcntl.h>
#include <stdlib.h>
#include <unistd.h>

__attribute__((constructor)) static void oompah_test_mark(void) {
    const char *path = getenv("OOMPAH_TEST_LOADER_MARKER");
    if (path == NULL) return;
    int fd = open(path, O_WRONLY | O_CREAT | O_APPEND, 0600);
    if (fd < 0) return;
    (void)write(fd, "x", 1);
    (void)close(fd);
}
""",
        encoding="utf-8",
    )
    subprocess.run(
        [compiler, "-shared", "-fPIC", "-o", str(library), str(source)],
        check=True,
        timeout=10,
    )

    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    gate = lease.acquire(
        ValidationLeaseOwner.exact_gate(
            project_id="project",
            task_id="GATE-1",
            authority_generation="gate-generation",
        )
    )
    guarded, _ = install_native_validation_guard(
        {"PATH": os.environ.get("PATH", os.defpath)},
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=ValidationLeaseOwner.worker(
            project_id="project",
            task_id="TASK-1",
            authority_generation="generation",
        ),
        timeout_seconds=10,
    )
    guarded["OOMPAH_TEST_LOADER_MARKER"] = str(marker)
    command = f"LD_PRELOAD={shlex.quote(str(library))} /usr/bin/printf trusted"
    process = subprocess.Popen(
        ["/bin/bash", "-c", command],
        env=guarded,
        pass_fds=_guard_pass_fds(guarded),
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        _wait_until(lambda: lease.status().waiter_count == 1)
        assert marker.exists() is False
    finally:
        gate.release()

    assert process.communicate(timeout=5)[0] == "trusted"
    assert process.returncode == 0
    assert marker.exists() is True


def test_bare_task_path_wrapper_fails_closed_to_capacity(tmp_path: Path) -> None:
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    gate = lease.acquire(
        ValidationLeaseOwner.exact_gate(
            project_id="project",
            task_id="GATE-1",
            authority_generation="gate-generation",
        )
    )
    marker = tmp_path / "bare-path-wrapper"
    task_bin = tmp_path / "task-bin"
    task_bin.mkdir()
    wrapper = task_bin / "ci-check"
    wrapper.write_text(
        '#!/bin/sh\n: > "$OOMPAH_TEST_NATIVE_MARKER"\n',
        encoding="utf-8",
    )
    wrapper.chmod(0o700)
    guarded, _ = install_native_validation_guard(
        {"PATH": f"{task_bin}{os.pathsep}{os.environ.get('PATH', os.defpath)}"},
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=ValidationLeaseOwner.worker(
            project_id="project",
            task_id="TASK-1",
            authority_generation="generation",
        ),
        timeout_seconds=10,
    )
    guarded["OOMPAH_TEST_NATIVE_MARKER"] = str(marker)
    process = subprocess.Popen(
        ["/bin/bash", "-c", "ci-check"],
        env={**os.environ, **guarded},
        pass_fds=_guard_pass_fds(guarded),
    )
    try:
        _wait_until(lambda: lease.status().waiter_count == 1)
        assert marker.exists() is False
    finally:
        gate.release()

    assert process.wait(timeout=5) == 0
    assert marker.exists() is True


def test_task_path_inspection_lookalike_waits_before_spawn(tmp_path: Path) -> None:
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    gate = lease.acquire(
        ValidationLeaseOwner.exact_gate(
            project_id="project",
            task_id="GATE-1",
            authority_generation="gate-generation",
        )
    )
    task_bin = tmp_path / "task-bin"
    task_bin.mkdir()
    marker = tmp_path / "fake-git-started"
    fake_git = task_bin / "git"
    fake_git.write_text(
        '#!/bin/sh\n: > "$OOMPAH_TEST_NATIVE_MARKER"\n',
        encoding="utf-8",
    )
    fake_git.chmod(0o700)
    guarded, _ = install_native_validation_guard(
        {"PATH": f"{task_bin}{os.pathsep}{os.environ.get('PATH', os.defpath)}"},
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=ValidationLeaseOwner.worker(
            project_id="project",
            task_id="TASK-1",
            authority_generation="generation",
        ),
        timeout_seconds=10,
        provider_untrusted_roots=(task_bin,),
    )
    guarded["OOMPAH_TEST_NATIVE_MARKER"] = str(marker)
    process = subprocess.Popen(
        ["/bin/bash", "-c", "git status --short"],
        env={**os.environ, **guarded},
        pass_fds=_guard_pass_fds(guarded),
    )
    try:
        _wait_until(lambda: lease.status().waiter_count == 1)
        assert marker.exists() is False
    finally:
        gate.release()

    assert process.wait(timeout=5) == 0
    assert marker.exists() is True


def test_retired_guard_blocks_delayed_background_descendant(tmp_path: Path) -> None:
    """Session cleanup retains a referenced fail-closed cancellation hook."""

    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    marker = tmp_path / "delayed-descendant"
    owner = ValidationLeaseOwner.worker(
        project_id="project",
        task_id="TASK-1",
        authority_generation="generation",
    )
    guarded, root = install_native_validation_guard(
        {"PATH": os.environ.get("PATH", os.defpath)},
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=owner,
        timeout_seconds=10,
    )
    guarded["OOMPAH_TEST_NATIVE_MARKER"] = str(marker)
    delayed_code = (
        "import os, subprocess, time; "
        "time.sleep(1); "
        "subprocess.run(['/bin/bash', '-c', "
        "': > \"$OOMPAH_TEST_NATIVE_MARKER\"'], env=os.environ.copy())"
    )
    launcher_code = (
        "import os, subprocess, sys; "
        f"subprocess.Popen([sys.executable, '-c', {delayed_code!r}], "
        "env=os.environ.copy(), start_new_session=True, close_fds=True)"
    )
    outer = subprocess.Popen(
        [sys.executable, "-c", launcher_code],
        env={**os.environ, **guarded},
        pass_fds=_guard_pass_fds(guarded),
    )
    assert outer.wait(timeout=5) == 0

    assert retire_native_validation_guard(
        root,
        validation_lease=lease,
        owner=owner,
    ) is False
    time.sleep(1.25)

    assert marker.exists() is False
    assert retire_native_validation_guard(root) is True
    assert root.exists() is False


def test_guard_install_skips_missing_path_directories(tmp_path: Path) -> None:
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3")
    real_bin = tmp_path / "real-bin"
    real_bin.mkdir()
    versioned_python = real_bin / "python3.11"
    versioned_python.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    versioned_python.chmod(0o700)
    missing_bin = tmp_path / "missing-bin"

    guarded, root = install_native_validation_guard(
        {"PATH": f"{missing_bin}{os.pathsep}{real_bin}"},
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=ValidationLeaseOwner.worker(
            project_id="project",
            task_id="TASK-1",
            authority_generation="generation",
        ),
        timeout_seconds=10,
    )

    guard_bin = root / "validation-guard-bin"
    assert (guard_bin / "python3.11").is_symlink()
    assert guarded["PATH"].endswith(
        f"{os.pathsep}{missing_bin}{os.pathsep}{real_bin}"
    )


def test_runtime_root_scan_retains_guard_when_process_is_opaque(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unreadable same-user process cannot authorize guard deletion."""

    root = tmp_path / "guard"
    root.mkdir()
    proc_root = tmp_path / "proc"
    process = proc_root / str(os.getpid() + 10_000)
    process.mkdir(parents=True)
    process_start_ticks = 123_456
    (process / "stat").write_text(
        f"{process.name} (opaque) "
        + " ".join(["S", *(["1"] * 18), str(process_start_ticks)])
        + "\n",
        encoding="utf-8",
    )
    real_read_bytes = Path.read_bytes

    def deny_process_environment(path: Path) -> bytes:
        if path == process / "environ":
            raise PermissionError("opaque same-user process")
        return real_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", deny_process_environment)

    assert guard_module._runtime_root_is_referenced(
        root,
        proc_root=proc_root,
    ) is True
    assert guard_module._runtime_root_is_referenced(
        root,
        proc_root=proc_root,
        opaque_process_baseline=frozenset(
            {(int(process.name), process_start_ticks)}
        ),
    ) is False


def test_runtime_root_scan_ignores_concurrent_unrelated_opaque_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A new sibling worker can descend from a proven pre-guard generation."""

    root = tmp_path / "guard"
    root.mkdir()
    proc_root = tmp_path / "proc"
    ancestor_pid, ancestor_ticks = 41_001, 410_001
    child_pid, child_ticks = 41_002, 410_002
    creator_ancestor_pid, creator_ancestor_ticks = 41_010, 410_010
    creator_pid, creator_ticks = 41_011, 410_011

    def write_process(pid: int, *, parent: int, ticks: int) -> Path:
        process = proc_root / str(pid)
        process.mkdir(parents=True)
        fields = ["S", str(parent), *("1" for _ in range(17)), str(ticks)]
        (process / "stat").write_text(
            f"{pid} (fixture) " + " ".join(fields) + "\n",
            encoding="utf-8",
        )
        return process

    write_process(ancestor_pid, parent=1, ticks=ancestor_ticks)
    write_process(
        creator_ancestor_pid,
        parent=1,
        ticks=creator_ancestor_ticks,
    )
    write_process(
        creator_pid,
        parent=creator_ancestor_pid,
        ticks=creator_ticks,
    )
    ancestry_baseline = frozenset(
        guard_module._process_ancestry_baseline(
            proc_root,
            creator_pid=creator_pid,
        )
    )
    assert (ancestor_pid, ancestor_ticks) in ancestry_baseline
    assert (creator_ancestor_pid, creator_ancestor_ticks) not in ancestry_baseline
    assert (child_pid, child_ticks) not in ancestry_baseline
    child = write_process(child_pid, parent=ancestor_pid, ticks=child_ticks)
    real_read_bytes = Path.read_bytes

    def deny_child_environment(path: Path) -> bytes:
        if path == child / "environ":
            raise PermissionError("concurrent sibling worker is opaque")
        return real_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", deny_child_environment)

    assert guard_module._runtime_root_is_referenced(
        root,
        proc_root=proc_root,
        process_ancestry_baseline=ancestry_baseline,
        guarded_process_identities=frozenset({(51_001, 510_001)}),
    ) is False


def test_runtime_root_scan_rejects_reparenting_to_pre_guard_subreaper(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An ancestor subreaper cannot launder a guarded descendant's origin."""

    root = tmp_path / "guard"
    root.mkdir()
    proc_root = tmp_path / "proc"
    subreaper_pid, subreaper_ticks = 41_101, 411_001
    creator_pid, creator_ticks = 41_102, 411_002
    child_pid, child_ticks = 41_103, 411_003

    def write_process(
        pid: int,
        *,
        parent: int,
        group: int,
        ticks: int,
    ) -> Path:
        process = proc_root / str(pid)
        process.mkdir(parents=True)
        fields = [
            "S",
            str(parent),
            str(group),
            *("1" for _ in range(16)),
            str(ticks),
        ]
        (process / "stat").write_text(
            f"{pid} (fixture) " + " ".join(fields) + "\n",
            encoding="utf-8",
        )
        return process

    write_process(
        subreaper_pid,
        parent=1,
        group=subreaper_pid,
        ticks=subreaper_ticks,
    )
    write_process(
        creator_pid,
        parent=subreaper_pid,
        group=creator_pid,
        ticks=creator_ticks,
    )
    ancestry_baseline = frozenset(
        guard_module._process_ancestry_baseline(
            proc_root,
            creator_pid=creator_pid,
        )
    )
    assert (subreaper_pid, subreaper_ticks) not in ancestry_baseline
    child = write_process(
        child_pid,
        # The post-baseline guarded child detached, then its creator exited.
        # Linux has adopted it to the pre-existing ancestor subreaper.
        parent=subreaper_pid,
        group=child_pid,
        ticks=child_ticks,
    )
    real_read_bytes = Path.read_bytes

    def deny_child_environment(path: Path) -> bytes:
        if path == child / "environ":
            raise PermissionError("reparented guarded child is opaque")
        return real_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", deny_child_environment)

    assert guard_module._runtime_root_is_referenced(
        root,
        proc_root=proc_root,
        process_ancestry_baseline=ancestry_baseline,
        guarded_process_identities=frozenset({(creator_pid, creator_ticks)}),
    ) is True


def test_runtime_root_scan_retains_opaque_process_with_broken_ancestry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A detached/reparented opaque generation remains fail closed."""

    root = tmp_path / "guard"
    root.mkdir()
    proc_root = tmp_path / "proc"
    process_pid, process_ticks = 42_001, 420_001
    process = proc_root / str(process_pid)
    process.mkdir(parents=True)
    fields = ["S", "1", *("1" for _ in range(17)), str(process_ticks)]
    (process / "stat").write_text(
        f"{process_pid} (orphan) " + " ".join(fields) + "\n",
        encoding="utf-8",
    )
    real_read_bytes = Path.read_bytes

    def deny_process_environment(path: Path) -> bytes:
        if path == process / "environ":
            raise PermissionError("orphan is opaque")
        return real_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", deny_process_environment)

    assert guard_module._runtime_root_is_referenced(
        root,
        proc_root=proc_root,
        process_ancestry_baseline=frozenset({(41_001, 410_001)}),
    ) is True


def test_runtime_root_scan_ignores_opaque_zombie(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unreaped process has already closed every guard reference."""

    root = tmp_path / "guard"
    root.mkdir()
    proc_root = tmp_path / "proc"
    process_pid, process_ticks = 42_101, 421_001
    process = proc_root / str(process_pid)
    process.mkdir(parents=True)
    fields = ["Z", "1", *("1" for _ in range(17)), str(process_ticks)]
    (process / "stat").write_text(
        f"{process_pid} (zombie) " + " ".join(fields) + "\n",
        encoding="utf-8",
    )
    real_read_bytes = Path.read_bytes

    def deny_process_environment(path: Path) -> bytes:
        if path == process / "environ":
            raise PermissionError("zombie proc entry is opaque")
        return real_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", deny_process_environment)

    assert guard_module._runtime_root_is_referenced(
        root,
        proc_root=proc_root,
    ) is False


def test_runtime_root_scan_retains_opaque_member_of_guarded_process_group(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A baseline ancestor cannot launder this guard's exact command PGID."""

    root = tmp_path / "guard"
    root.mkdir()
    proc_root = tmp_path / "proc"
    ancestor_pid, ancestor_ticks = 43_001, 430_001
    child_pid, child_ticks = 43_002, 430_002
    group_pid, group_ticks = 44_001, 440_001

    def write_process(
        pid: int,
        *,
        parent: int,
        group: int,
        ticks: int,
    ) -> Path:
        process = proc_root / str(pid)
        process.mkdir(parents=True)
        fields = [
            "S",
            str(parent),
            str(group),
            *("1" for _ in range(16)),
            str(ticks),
        ]
        (process / "stat").write_text(
            f"{pid} (fixture) " + " ".join(fields) + "\n",
            encoding="utf-8",
        )
        return process

    write_process(
        ancestor_pid,
        parent=1,
        group=ancestor_pid,
        ticks=ancestor_ticks,
    )
    write_process(group_pid, parent=1, group=group_pid, ticks=group_ticks)
    child = write_process(
        child_pid,
        parent=ancestor_pid,
        group=group_pid,
        ticks=child_ticks,
    )
    real_read_bytes = Path.read_bytes

    def deny_child_environment(path: Path) -> bytes:
        if path == child / "environ":
            raise PermissionError("guarded group member is opaque")
        return real_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", deny_child_environment)

    assert guard_module._runtime_root_is_referenced(
        root,
        proc_root=proc_root,
        process_ancestry_baseline=frozenset(
            {(ancestor_pid, ancestor_ticks)}
        ),
        guarded_process_group_identities=frozenset({(group_pid, group_ticks)}),
    ) is True


def test_opaque_process_scan_records_exact_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proc_root = tmp_path / "proc"
    process = proc_root / str(os.getpid() + 20_000)
    process.mkdir(parents=True)
    process_start_ticks = 234_567
    (process / "stat").write_text(
        f"{process.name} (opaque scan) "
        + " ".join(["S", *(["1"] * 18), str(process_start_ticks)])
        + "\n",
        encoding="utf-8",
    )
    real_read_bytes = Path.read_bytes

    def deny_process_environment(path: Path) -> bytes:
        if path == process / "environ":
            raise PermissionError("opaque same-user process")
        return real_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", deny_process_environment)

    assert guard_module._scan_opaque_same_user_processes(proc_root) == (
        (int(process.name), process_start_ticks),
    )


def test_tampered_config_cannot_inject_opaque_retirement_baseline(
    tmp_path: Path,
) -> None:
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    owner = ValidationLeaseOwner.worker(
        project_id="project",
        task_id="TASK-CONFIG-BASELINE",
        authority_generation="generation",
    )
    _guarded, root = install_native_validation_guard(
        {"PATH": os.environ.get("PATH", os.defpath)},
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=owner,
        timeout_seconds=10,
    )
    config_path = root / guard_module._CONFIG_NAME
    config_path.chmod(0o600)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["opaque_process_baseline"] = [[os.getpid(), 1]]
    config_path.write_text(json.dumps(config, sort_keys=True), encoding="utf-8")

    try:
        assert guard_module._configured_opaque_process_baseline(root) is None
        assert retire_native_validation_guard(
            root,
            validation_lease=lease,
            owner=owner,
        ) is False
        assert root.exists()
    finally:
        config_path.chmod(0o400)
        retire_native_validation_guard(
            root,
            validation_lease=lease,
            owner=owner,
        )


def test_symlinked_config_retains_guard_fail_closed(tmp_path: Path) -> None:
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    owner = ValidationLeaseOwner.worker(
        project_id="project",
        task_id="TASK-CONFIG-SYMLINK",
        authority_generation="generation",
    )
    _guarded, root = install_native_validation_guard(
        {"PATH": os.environ.get("PATH", os.defpath)},
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=owner,
        timeout_seconds=10,
    )
    config_path = root / guard_module._CONFIG_NAME
    backup_path = root / "validation-guard.backup.json"
    config_path.rename(backup_path)
    config_path.symlink_to(backup_path.name)

    try:
        with pytest.raises(RuntimeError, match="configuration is unavailable"):
            guard_module._load_verified_guard_config(root)
        assert retire_native_validation_guard(
            root,
            validation_lease=lease,
            owner=owner,
        ) is False
        assert root.exists()
    finally:
        config_path.unlink(missing_ok=True)
        backup_path.rename(config_path)
        retire_native_validation_guard(
            root,
            validation_lease=lease,
            owner=owner,
        )


def test_creator_death_cleanup_fences_and_removes_orphaned_guard(
    tmp_path: Path,
) -> None:
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    parent = tmp_path / "guards"
    root = parent / "oompah-codex-validation-orphan"
    _guarded, _ = install_native_validation_guard(
        {"PATH": os.environ.get("PATH", os.defpath)},
        runtime_root=root,
        validation_lease=lease,
        owner=ValidationLeaseOwner.worker(
            project_id="project",
            task_id="TASK-1",
            authority_generation="generation",
        ),
        timeout_seconds=10,
    )
    config_path = root / "validation-guard.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["creator"]["start_ticks"] += 1
    config_path.chmod(0o600)
    config_path.write_text(json.dumps(config, sort_keys=True), encoding="utf-8")
    config_path.chmod(0o400)

    assert cleanup_retired_native_validation_guards(parent) == 1
    assert root.exists() is False


def test_cleanup_preserves_guard_owned_by_active_creator(tmp_path: Path) -> None:
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    parent = tmp_path / "guards"
    root = parent / "oompah-codex-validation-active"
    owner = ValidationLeaseOwner.worker(
        project_id="project",
        task_id="TASK-1",
        authority_generation="generation",
    )
    install_native_validation_guard(
        {"PATH": os.environ.get("PATH", os.defpath)},
        runtime_root=root,
        validation_lease=lease,
        owner=owner,
        timeout_seconds=10,
    )

    assert cleanup_retired_native_validation_guards(parent) == 0
    assert root.is_dir()
    assert retire_native_validation_guard(
        root,
        validation_lease=lease,
        owner=owner,
    ) is True


def test_retirement_retries_transient_proc_reference(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    root = tmp_path / "guard"
    owner = ValidationLeaseOwner.worker(
        project_id="project",
        task_id="TASK-TRANSIENT-PROC",
        authority_generation="generation",
    )
    install_native_validation_guard(
        {"PATH": os.environ.get("PATH", os.defpath)},
        runtime_root=root,
        validation_lease=lease,
        owner=owner,
        timeout_seconds=10,
    )
    observations = iter((True, False))
    calls = 0

    def transient_reference(*_args, **_kwargs) -> bool:
        nonlocal calls
        calls += 1
        return next(observations)

    monkeypatch.setattr(
        guard_module,
        "_runtime_root_is_referenced",
        transient_reference,
    )

    assert retire_native_validation_guard(
        root,
        validation_lease=lease,
        owner=owner,
    ) is True
    assert calls == 2
    assert root.exists() is False


def test_retirement_retries_durable_owner_cancellation_after_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    parent = tmp_path / "guards"
    root = parent / "oompah-codex-validation-retry"
    owner = ValidationLeaseOwner.worker(
        project_id="project",
        task_id="TASK-1",
        authority_generation="generation",
    )
    install_native_validation_guard(
        {"PATH": os.environ.get("PATH", os.defpath)},
        runtime_root=root,
        validation_lease=lease,
        owner=owner,
        timeout_seconds=10,
    )
    monkeypatch.setattr(
        lease,
        "cancel_owner",
        lambda _owner: (_ for _ in ()).throw(RuntimeError("temporary database error")),
    )

    with pytest.raises(RuntimeError, match="temporary database error"):
        retire_native_validation_guard(
            root,
            validation_lease=lease,
            owner=owner,
        )

    assert (root / "cancelled").exists()
    assert cleanup_retired_native_validation_guards(parent) == 1
    assert root.exists() is False


def test_heavy_shim_uses_operator_broker_not_configured_database(
    tmp_path: Path,
) -> None:
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    real_bin = tmp_path / "real-bin"
    real_bin.mkdir()
    marker = tmp_path / "brokered"
    real_make = real_bin / "make"
    real_make.write_text(
        '#!/bin/sh\n: > "$OOMPAH_TEST_NATIVE_MARKER"\n',
        encoding="utf-8",
    )
    real_make.chmod(0o700)
    owner = ValidationLeaseOwner.worker(
        project_id="project",
        task_id="TASK-1",
        authority_generation="generation",
    )
    guarded, root = install_native_validation_guard(
        {"PATH": f"{real_bin}{os.pathsep}{os.environ.get('PATH', os.defpath)}"},
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=owner,
        timeout_seconds=10,
    )
    config_path = root / "validation-guard.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["state_path"] = "/proc/oompah-unwritable/validation.sqlite3"
    config_path.chmod(0o600)
    config_path.write_text(json.dumps(config, sort_keys=True), encoding="utf-8")
    config_path.chmod(0o400)
    guarded["OOMPAH_TEST_NATIVE_MARKER"] = str(marker)

    completed = subprocess.run(
        ["make", "test"],
        env={**os.environ, **guarded},
        pass_fds=_guard_pass_fds(guarded),
        check=False,
        timeout=5,
    )

    assert completed.returncode == 0
    assert marker.exists()
    assert retire_native_validation_guard(
        root,
        validation_lease=lease,
        owner=owner,
    ) is True


def _native_node_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    real_bin = tmp_path / "real-bin"
    real_bin.mkdir()
    marker = tmp_path / "node-started"
    real_node = real_bin / "node"
    real_node.write_text(
        "#!/bin/sh\n"
        "if [ -n \"${OOMPAH_TEST_DESCENDANT_MARKER:-}\" ]; then\n"
        "  exec make test\n"
        "fi\n"
        ": > \"$OOMPAH_TEST_NATIVE_MARKER\"\n",
        encoding="utf-8",
    )
    real_node.chmod(0o700)
    trusted_entrypoint = tmp_path / "trusted-codex.js"
    trusted_entrypoint.write_text("// trusted provider entrypoint\n", encoding="utf-8")
    return real_bin, marker, trusted_entrypoint


def test_direct_provider_install_requires_pinned_entrypoint_fd(
    tmp_path: Path,
) -> None:
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    provider = tmp_path / "direct-provider"
    provider.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    provider.chmod(0o700)
    provider_stat = provider.stat()

    with pytest.raises(RuntimeError, match="requires a pinned entrypoint"):
        install_native_validation_guard(
            {"PATH": os.environ.get("PATH", os.defpath)},
            runtime_root=tmp_path / "guard",
            validation_lease=lease,
            owner=ValidationLeaseOwner.worker(
                project_id="project",
                task_id="TASK-1",
                authority_generation="generation",
            ),
            timeout_seconds=10,
            provider_bootstrap_entrypoint=provider,
            provider_bootstrap_entrypoint_identity=(
                int(provider_stat.st_dev),
                int(provider_stat.st_ino),
            ),
        )


def test_direct_provider_launcher_registers_session_capability(tmp_path: Path) -> None:
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    owner = ValidationLeaseOwner.worker(
        project_id="project",
        task_id="TASK-1",
        authority_generation="generation",
    )
    provider = tmp_path / "direct-provider"
    provider.write_text(
        "#!/bin/sh\n/bin/bash -c 'printf direct'\n",
        encoding="utf-8",
    )
    provider.chmod(0o700)
    provider_stat = provider.stat()
    provider_fd = os.open(provider, os.O_RDONLY | os.O_CLOEXEC)
    try:
        guarded, root = install_native_validation_guard(
            {"PATH": os.environ.get("PATH", os.defpath)},
            runtime_root=tmp_path / "guard",
            validation_lease=lease,
            owner=owner,
            timeout_seconds=10,
            provider_bootstrap_entrypoint=provider,
            provider_bootstrap_entrypoint_identity=(
                int(provider_stat.st_dev),
                int(provider_stat.st_ino),
            ),
            provider_bootstrap_entrypoint_fd=provider_fd,
        )

        completed = subprocess.run(
            [guard_module.native_validation_provider_launcher(root), "exec"],
            env={**os.environ, **guarded},
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )

        assert completed.returncode == 0
        assert completed.stdout == "direct"
        assert consume_native_validation_boundary(
            root,
            "printf direct",
            "direct-item",
        ) is True
        assert retire_native_validation_guard(
            root,
            validation_lease=lease,
            owner=owner,
        ) is True
    finally:
        os.close(provider_fd)


def test_guard_path_in_spoofed_provider_argv_does_not_grant_trust(
    tmp_path: Path,
) -> None:
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    owner = ValidationLeaseOwner.worker(
        project_id="project",
        task_id="TASK-1",
        authority_generation="generation",
    )
    guarded, root = install_native_validation_guard(
        {"PATH": os.environ.get("PATH", os.defpath)},
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=owner,
        timeout_seconds=10,
    )
    spoofed_argv0 = root / "validation-guard-bin" / "make"
    process = subprocess.Popen(
        [str(spoofed_argv0), "-c", "import time; time.sleep(30)"],
        executable=sys.executable,
        env={
            **os.environ,
            "OOMPAH_NATIVE_VALIDATION_GUARD": str(spoofed_argv0.parent),
        },
    )
    try:
        assert guard_module._peer_is_guard_launcher(process.pid, root) is False
    finally:
        process.terminate()
        process.wait(timeout=5)
    assert retire_native_validation_guard(
        root,
        validation_lease=lease,
        owner=owner,
    ) is True


def test_supervisor_termination_delegates_with_exact_start_ticks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[int, int, float]] = []

    def terminate_exact(pid: int, start_ticks: int, *, grace_seconds: float) -> bool:
        calls.append((pid, start_ticks, grace_seconds))
        return True

    monkeypatch.setattr(
        guard_module,
        "_terminate_exact_process_group",
        terminate_exact,
    )

    assert guard_module._terminate_supervised_process_group(123, 456) is True
    assert calls == [(123, 456, 0.5)]


def test_trusted_provider_node_bootstrap_does_not_lease_entire_session(
    tmp_path: Path,
) -> None:
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    gate = lease.acquire(
        ValidationLeaseOwner.exact_gate(
            project_id="project",
            task_id="GATE-1",
            authority_generation="gate-generation",
        )
    )
    real_bin, marker, trusted_entrypoint = _native_node_fixture(tmp_path)
    guarded, _ = install_native_validation_guard(
        {"PATH": f"{real_bin}{os.pathsep}{os.environ.get('PATH', os.defpath)}"},
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=ValidationLeaseOwner.worker(
            project_id="project",
            task_id="TASK-1",
            authority_generation="generation",
        ),
        timeout_seconds=10,
        provider_bootstrap_entrypoint=trusted_entrypoint,
        provider_bootstrap_interpreter=real_bin / "node",
    )
    guarded["OOMPAH_TEST_NATIVE_MARKER"] = str(marker)

    completed = subprocess.run(
        ["node", str(trusted_entrypoint), "exec"],
        env={**os.environ, **guarded},
        pass_fds=_guard_pass_fds(guarded),
        check=False,
        timeout=5,
    )

    assert completed.returncode == 0
    assert marker.exists() is True
    status = lease.status()
    assert status.owner_count == 1
    assert status.waiter_count == 0
    assert status.owners[0]["task_id"] == "GATE-1"
    gate.release()


def test_trusted_bootstrap_retains_guard_for_heavy_descendant(tmp_path: Path) -> None:
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    gate = lease.acquire(
        ValidationLeaseOwner.exact_gate(
            project_id="project",
            task_id="GATE-1",
            authority_generation="gate-generation",
        )
    )
    real_bin, marker, trusted_entrypoint = _native_node_fixture(tmp_path)
    descendant_marker = tmp_path / "descendant-started"
    real_make = real_bin / "make"
    real_make.write_text(
        '#!/bin/sh\n: > "$OOMPAH_TEST_DESCENDANT_MARKER"\n',
        encoding="utf-8",
    )
    real_make.chmod(0o700)
    guarded, _ = install_native_validation_guard(
        {"PATH": f"{real_bin}{os.pathsep}{os.environ.get('PATH', os.defpath)}"},
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=ValidationLeaseOwner.worker(
            project_id="project",
            task_id="TASK-1",
            authority_generation="generation",
        ),
        timeout_seconds=10,
        provider_bootstrap_entrypoint=trusted_entrypoint,
        provider_bootstrap_interpreter=real_bin / "node",
    )
    guarded["OOMPAH_TEST_NATIVE_MARKER"] = str(marker)
    guarded["OOMPAH_TEST_DESCENDANT_MARKER"] = str(descendant_marker)

    process = subprocess.Popen(
        ["node", str(trusted_entrypoint), "exec"],
        env={**os.environ, **guarded},
        pass_fds=_guard_pass_fds(guarded),
    )
    try:
        _wait_until(lambda: lease.status().waiter_count == 1)
        status = lease.status()
        assert status.owner_count == 1
        assert status.owners[0]["task_id"] == "GATE-1"
        assert status.waiters[0]["task_id"] == "TASK-1"
        assert descendant_marker.exists() is False
    finally:
        gate.release()

    assert process.wait(timeout=5) == 0
    assert descendant_marker.exists() is True
    _wait_until(lambda: lease.status().owner_count == 0)


def test_trusted_bootstrap_ignores_task_path_node_lookalike(tmp_path: Path) -> None:
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    trusted_bin, trusted_marker, trusted_entrypoint = _native_node_fixture(tmp_path)
    task_bin = tmp_path / "task-bin"
    task_bin.mkdir()
    task_marker = tmp_path / "task-node-started"
    task_node = task_bin / "node"
    task_node.write_text(
        '#!/bin/sh\n: > "$OOMPAH_TEST_TASK_NODE_MARKER"\n',
        encoding="utf-8",
    )
    task_node.chmod(0o700)
    guarded, _ = install_native_validation_guard(
        {
            "PATH": (
                f"{task_bin}{os.pathsep}{trusted_bin}{os.pathsep}"
                f"{os.environ.get('PATH', os.defpath)}"
            )
        },
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=ValidationLeaseOwner.worker(
            project_id="project",
            task_id="TASK-1",
            authority_generation="generation",
        ),
        timeout_seconds=10,
        provider_bootstrap_entrypoint=trusted_entrypoint,
        provider_bootstrap_interpreter=trusted_bin / "node",
    )
    guarded["OOMPAH_TEST_NATIVE_MARKER"] = str(trusted_marker)
    guarded["OOMPAH_TEST_TASK_NODE_MARKER"] = str(task_marker)

    completed = subprocess.run(
        ["node", str(trusted_entrypoint), "exec"],
        env={**os.environ, **guarded},
        pass_fds=_guard_pass_fds(guarded),
        check=False,
        timeout=5,
    )

    assert completed.returncode == 0
    assert trusted_marker.exists() is True
    assert task_marker.exists() is False
    assert lease.status().owner_count == 0


def test_provider_bootstrap_executables_cannot_be_task_writable(tmp_path: Path) -> None:
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    task_root = tmp_path / "workspace"
    task_root.mkdir()
    task_bin, _marker, task_entrypoint = _native_node_fixture(task_root)

    with pytest.raises(RuntimeError, match="task-writable"):
        install_native_validation_guard(
            {"PATH": str(task_bin)},
            runtime_root=tmp_path / "guard",
            validation_lease=lease,
            owner=ValidationLeaseOwner.worker(
                project_id="project",
                task_id="TASK-1",
                authority_generation="generation",
            ),
            timeout_seconds=10,
            provider_bootstrap_entrypoint=task_entrypoint,
            provider_bootstrap_interpreter=task_bin / "node",
            provider_untrusted_roots=(task_root,),
        )


def test_provider_bootstrap_install_rejects_entrypoint_inode_replacement(
    tmp_path: Path,
) -> None:
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    trusted_bin, _marker, trusted_entrypoint = _native_node_fixture(tmp_path)
    original_stat = trusted_entrypoint.stat()
    replacement = tmp_path / "replacement-codex.js"
    replacement.write_text("// replacement provider entrypoint\n", encoding="utf-8")
    replacement.replace(trusted_entrypoint)

    with pytest.raises(RuntimeError, match="entrypoint identity changed"):
        install_native_validation_guard(
            {"PATH": str(trusted_bin)},
            runtime_root=tmp_path / "guard",
            validation_lease=lease,
            owner=ValidationLeaseOwner.worker(
                project_id="project",
                task_id="TASK-1",
                authority_generation="generation",
            ),
            timeout_seconds=10,
            provider_bootstrap_entrypoint=trusted_entrypoint,
            provider_bootstrap_interpreter=trusted_bin / "node",
            provider_bootstrap_entrypoint_identity=(
                int(original_stat.st_dev),
                int(original_stat.st_ino),
            ),
        )


@pytest.mark.parametrize(
    "attack",
    ["lookalike", "wrong-parent", "replaced-entrypoint", "parent-ticks"],
)
def test_task_controlled_provider_bootstrap_shape_cannot_bypass_validation(
    tmp_path: Path,
    attack: str,
) -> None:
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    gate = lease.acquire(
        ValidationLeaseOwner.exact_gate(
            project_id="project",
            task_id="GATE-1",
            authority_generation="gate-generation",
        )
    )
    real_bin, marker, trusted_entrypoint = _native_node_fixture(tmp_path)
    lookalike = tmp_path / "lookalike-codex.js"
    lookalike.write_text("// task-controlled lookalike\n", encoding="utf-8")
    owner = ValidationLeaseOwner.worker(
        project_id="project",
        task_id="TASK-1",
        authority_generation="generation",
    )
    guarded, root = install_native_validation_guard(
        {"PATH": f"{real_bin}{os.pathsep}{os.environ.get('PATH', os.defpath)}"},
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=owner,
        timeout_seconds=10,
        provider_bootstrap_entrypoint=trusted_entrypoint,
        provider_bootstrap_interpreter=real_bin / "node",
    )
    guarded["OOMPAH_TEST_NATIVE_MARKER"] = str(marker)
    if attack == "lookalike":
        process = subprocess.Popen(
            ["node", str(lookalike), "exec"],
            env={**os.environ, **guarded},
            pass_fds=_guard_pass_fds(guarded),
        )
    elif attack == "wrong-parent":
        guarded["OOMPAH_TEST_ENTRYPOINT"] = str(trusted_entrypoint)
        process = subprocess.Popen(
            ["/bin/sh", "-c", 'node "$OOMPAH_TEST_ENTRYPOINT" exec'],
            env={**os.environ, **guarded},
            pass_fds=_guard_pass_fds(guarded),
        )
    else:
        if attack == "replaced-entrypoint":
            replacement = tmp_path / "replacement-codex.js"
            replacement.write_text("// replacement provider entrypoint\n", encoding="utf-8")
            replacement.replace(trusted_entrypoint)
        else:
            config_path = (
                Path(guarded["OOMPAH_NATIVE_VALIDATION_GUARD"]).parent
                / "validation-guard.json"
            )
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["provider_bootstrap"]["parent_start_ticks"] += 1
            config_path.chmod(0o600)
            config_path.write_text(json.dumps(config, sort_keys=True), encoding="utf-8")
            config_path.chmod(0o400)
        process = subprocess.Popen(
            ["node", str(trusted_entrypoint), "exec"],
            env={**os.environ, **guarded},
            pass_fds=_guard_pass_fds(guarded),
        )
    try:
        # A process that merely imitates the provider's argv shape never gets
        # its sealed session capability. Denial is stronger than admitting it
        # to the capacity queue: no task-controlled code executes at all.
        assert process.wait(timeout=5) != 0
        assert marker.exists() is False
        status = lease.status()
        assert status.owner_count == 1
        assert status.waiter_count == 0
    finally:
        gate.release()
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        assert retire_native_validation_guard(
            root,
            validation_lease=lease,
            owner=owner,
        ) is True


@pytest.mark.parametrize(
    ("command", "arguments", "environment_update"),
    [
        ("make", ["--eval=$(shell make test)", "help"], {}),
        ("pytest", ["-p=task_plugin", "test_one.py"], {}),
        ("pytest", ["@payload.py"], {}),
        ("npm", ["run", "--silent", "test"], {}),
        ("pnpm", ["exec", "make", "test"], {}),
        ("yarn", ["arbitrary-script"], {}),
        ("rg", ["--hostname-bin=/task/hostname", "pattern", "."], {}),
        ("rg", ["--search-zip", "pattern", "."], {}),
        ("ruby", ["-v", "-e", "system('make test')"], {}),
        ("ruby", ["--version"], {"RUBYOPT": "-r/task/hook.rb"}),
    ],
)
def test_native_runner_execution_surface_waits_for_validation_capacity(
    tmp_path: Path,
    command: str,
    arguments: list[str],
    environment_update: dict[str, str],
) -> None:
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    execution_directory = tmp_path / "execution"
    execution_directory.mkdir()
    gate = lease.acquire(
        ValidationLeaseOwner.exact_gate(
            project_id="project",
            task_id="GATE-1",
            authority_generation="gate-generation",
        )
    )
    marker = tmp_path / "started"
    real_bin = tmp_path / "real-bin"
    real_bin.mkdir()
    real_executable = real_bin / command
    real_executable.write_text(
        "#!/bin/sh\n: > \"$OOMPAH_TEST_NATIVE_MARKER\"\n",
        encoding="utf-8",
    )
    real_executable.chmod(0o700)
    guarded, _ = install_native_validation_guard(
        {"PATH": f"{real_bin}{os.pathsep}{os.environ.get('PATH', os.defpath)}"},
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=ValidationLeaseOwner.auditor(
            project_id="project",
            task_id="AUDIT-1",
            authority_generation="audit-generation",
        ),
        timeout_seconds=10,
    )
    guarded["OOMPAH_TEST_NATIVE_MARKER"] = str(marker)
    guarded.update(environment_update)
    process = subprocess.Popen(
        [command, *arguments],
        cwd=execution_directory,
        env={**os.environ, **guarded},
        pass_fds=_guard_pass_fds(guarded),
    )
    try:
        _wait_until(lambda: lease.status().waiter_count == 1)
        assert marker.exists() is False
    finally:
        gate.release()

    assert process.wait(timeout=5) == 0
    assert marker.exists() is True


def test_native_heavy_child_retains_lane_after_launcher_crash(tmp_path: Path) -> None:
    """The actual command, not its service/SDK launcher, owns the flock."""

    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    pid_path = tmp_path / "heavy.pid"
    real_bin = tmp_path / "real-bin"
    real_bin.mkdir()
    real_make = real_bin / "make"
    real_make.write_text(
        "#!/bin/sh\necho $$ > \"$OOMPAH_TEST_HEAVY_PID\"\nsleep 30\n",
        encoding="utf-8",
    )
    real_make.chmod(0o700)
    guarded, _ = install_native_validation_guard(
        {"PATH": f"{real_bin}{os.pathsep}{os.environ.get('PATH', os.defpath)}"},
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=ValidationLeaseOwner.worker(
            project_id="project",
            task_id="TASK-1",
            authority_generation="generation",
        ),
        timeout_seconds=20,
    )
    guarded["OOMPAH_TEST_HEAVY_PID"] = str(pid_path)
    launcher_code = (
        "import os, pathlib, subprocess, time; "
        # The provider's nested launcher deliberately uses Python's default
        # close_fds boundary.  The descended trusted shim must recover its
        # sealed capability through the broker rather than treating a closed
        # inherited descriptor as permission to bypass or as a spurious
        # validation failure.
        "subprocess.Popen(['make', 'test'], env=os.environ.copy(), "
        "stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True); "
        "p=pathlib.Path(os.environ['OOMPAH_TEST_HEAVY_PID']); "
        "deadline=time.monotonic()+3; "
        "\nwhile not p.exists() and time.monotonic() < deadline: time.sleep(.01)"
    )
    launcher = subprocess.run(
        [sys.executable, "-c", launcher_code],
        env={**os.environ, **guarded},
        pass_fds=_guard_pass_fds(guarded),
        check=False,
        timeout=5,
    )
    assert launcher.returncode == 0

    _wait_until(lambda: lease.status().owner_count == 1)
    heavy_pid = _wait_for_pid(pid_path)
    owner = lease.status().owners[0]
    assert owner["child_pid"] == heavy_pid

    acquired = threading.Event()

    def wait_for_lane() -> None:
        handle = lease.acquire(
            ValidationLeaseOwner.exact_gate(
                project_id="project",
                task_id="GATE-1",
                authority_generation="gate-generation",
            )
        )
        acquired.set()
        handle.release()

    waiter = threading.Thread(target=wait_for_lane)
    waiter.start()
    _wait_until(lambda: lease.status().waiter_count == 1)
    assert acquired.is_set() is False

    os.killpg(heavy_pid, signal.SIGTERM)
    waiter.join(timeout=5)
    assert waiter.is_alive() is False
    assert acquired.is_set() is True
    assert lease.status().owner_count == 0


def test_detached_heavy_descendant_retains_native_capacity_until_exit(
    tmp_path: Path,
) -> None:
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    real_bin = tmp_path / "real-bin"
    real_bin.mkdir()
    descendant_pid_path = tmp_path / "detached.pid"
    real_make = real_bin / "make"
    real_make.write_text(
        "#!/bin/bash\n"
        "setsid bash -c 'printf \"%s\" \"$BASHPID\" > "
        '"$OOMPAH_TEST_DESCENDANT_PID"; '
        "trap \"\" TERM; while :; do sleep 1; done' &\n"
        # ``$!`` identifies the transient setsid launcher, which may fork when
        # it is already a process-group leader.  Wait for the inner shell to
        # publish its own PID only after setsid has created the detached
        # session.  This is a readiness handshake, not a scheduling delay.
        "for _attempt in {1..500}; do\n"
        "  if [[ -s \"$OOMPAH_TEST_DESCENDANT_PID\" ]]; then exit 0; fi\n"
        "  sleep 0.01\n"
        "done\n"
        "exit 1\n",
        encoding="utf-8",
    )
    real_make.chmod(0o700)
    guarded, _ = install_native_validation_guard(
        {"PATH": f"{real_bin}{os.pathsep}{os.environ.get('PATH', os.defpath)}"},
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=ValidationLeaseOwner.worker(
            project_id="project",
            task_id="TASK-1",
            authority_generation="generation",
        ),
        timeout_seconds=10,
    )
    guarded["OOMPAH_TEST_DESCENDANT_PID"] = str(descendant_pid_path)

    completed = subprocess.run(
        ["make", "test"],
        env={**os.environ, **guarded},
        pass_fds=_guard_pass_fds(guarded),
        check=False,
        timeout=5,
    )
    assert completed.returncode == 0
    descendant_pid = _wait_for_pid(descendant_pid_path)
    descendant_start_ticks = guard_module._process_start_ticks(descendant_pid)
    assert descendant_start_ticks is not None
    assert os.getpgid(descendant_pid) == descendant_pid
    assert os.getsid(descendant_pid) == descendant_pid

    try:
        with pytest.raises(ValidationLeaseCancelled, match="timed out"):
            lease.acquire(
                ValidationLeaseOwner.exact_gate(
                    project_id="project",
                    task_id="GATE-1",
                    authority_generation="gate-generation",
                ),
                wait_timeout_seconds=0.2,
            )
        assert (
            guard_module._process_start_ticks(descendant_pid)
            == descendant_start_ticks
        )
    finally:
        assert guard_module._terminate_supervised_process_group(
            descendant_pid,
            descendant_start_ticks,
        )
    _wait_until(lambda: not Path(f"/proc/{descendant_pid}").exists())
    with lease.acquire(
        ValidationLeaseOwner.exact_gate(
            project_id="project",
            task_id="GATE-1",
            authority_generation="gate-generation",
        ),
        wait_timeout_seconds=2,
    ):
        assert lease.status().owner_count == 1


@pytest.mark.parametrize("withdrawal", ["expired", "cancelled"])
def test_withdrawn_owner_remains_fenced_by_detached_descendant(
    tmp_path: Path,
    withdrawal: str,
) -> None:
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    real_bin = tmp_path / "real-bin"
    real_bin.mkdir()
    descendant_pid_path = tmp_path / "detached.pid"
    real_make = real_bin / "make"
    real_make.write_text(
        "#!/bin/bash\n"
        "setsid bash -c 'printf \"%s\" \"$BASHPID\" > \"$OOMPAH_TEST_DESCENDANT_PID\"; "
        "trap \"\" TERM; sleep 30' &\n"
        "sleep 30\n",
        encoding="utf-8",
    )
    real_make.chmod(0o700)
    guarded, root = install_native_validation_guard(
        {"PATH": f"{real_bin}{os.pathsep}{os.environ.get('PATH', os.defpath)}"},
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=ValidationLeaseOwner.worker(
            project_id="project",
            task_id="TASK-1",
            authority_generation="generation",
        ),
        timeout_seconds=1,
    )
    guarded["OOMPAH_TEST_DESCENDANT_PID"] = str(descendant_pid_path)
    process = subprocess.Popen(
        ["make", "test"],
        env={**os.environ, **guarded},
        pass_fds=_guard_pass_fds(guarded),
    )
    descendant_pid = _wait_for_pid(descendant_pid_path)

    def descendant_is_detached() -> bool:
        try:
            return (
                os.getpgid(descendant_pid) == descendant_pid
                and os.getsid(descendant_pid) == descendant_pid
            )
        except ProcessLookupError:
            return False

    # ``setsid`` may fork when its caller is already a process-group leader.
    # The inner shell publishes its own PID only after it owns the detached
    # session, so the cancellation below cannot accidentally target the
    # transient ``setsid`` parent instead of the inherited-descriptor holder.
    _wait_until(descendant_is_detached)
    if withdrawal == "cancelled":
        (root / "cancelled").touch()

    try:
        assert process.wait(timeout=3) != 0
        with pytest.raises(ValidationLeaseCancelled, match="timed out"):
            lease.acquire(
                ValidationLeaseOwner.exact_gate(
                    project_id="project",
                    task_id="GATE-1",
                    authority_generation="gate-generation",
                ),
                wait_timeout_seconds=0.2,
            )
        assert Path(f"/proc/{descendant_pid}").exists()
    finally:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(descendant_pid, signal.SIGKILL)
    _wait_until(lambda: not Path(f"/proc/{descendant_pid}").exists())
    with lease.acquire(
        ValidationLeaseOwner.exact_gate(
            project_id="project",
            task_id="GATE-1",
            authority_generation="gate-generation",
        ),
        wait_timeout_seconds=2,
    ):
        assert lease.status().owner_count == 1


def test_term_ignoring_same_group_child_is_gone_before_capacity_reuse(
    tmp_path: Path,
) -> None:
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    owner = ValidationLeaseOwner.worker(
        project_id="project",
        task_id="TASK-1",
        authority_generation="generation",
    )
    real_bin = tmp_path / "real-bin"
    real_bin.mkdir()
    child_pid_path = tmp_path / "same-group-child.pid"
    real_make = real_bin / "make"
    real_make.write_text(
        "#!/bin/bash\n"
        "bash -c 'trap \"\" TERM; while :; do sleep 1; done' &\n"
        "printf '%s' \"$!\" > \"$OOMPAH_TEST_CHILD_PID\"\n"
        "wait \"$!\"\n",
        encoding="utf-8",
    )
    real_make.chmod(0o700)
    guarded, root = install_native_validation_guard(
        {"PATH": f"{real_bin}{os.pathsep}{os.environ.get('PATH', os.defpath)}"},
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=owner,
        timeout_seconds=1,
    )
    guarded["OOMPAH_TEST_CHILD_PID"] = str(child_pid_path)
    process = subprocess.Popen(
        ["make", "test"],
        env={**os.environ, **guarded},
        pass_fds=_guard_pass_fds(guarded),
    )
    child_pid = _wait_for_pid(child_pid_path)
    assert os.getpgid(child_pid) == process.pid
    child_existed_at_reuse: list[bool] = []
    errors: list[BaseException] = []

    def wait_for_capacity() -> None:
        try:
            with lease.acquire(
                ValidationLeaseOwner.exact_gate(
                    project_id="project",
                    task_id="GATE-1",
                    authority_generation="gate-generation",
                ),
                wait_timeout_seconds=5,
            ):
                child_existed_at_reuse.append(Path(f"/proc/{child_pid}").exists())
        except BaseException as exc:  # pragma: no cover - surfaced below
            errors.append(exc)

    waiter = threading.Thread(target=wait_for_capacity)
    waiter.start()
    try:
        assert process.wait(timeout=5) != 0
        waiter.join(timeout=5)
        assert waiter.is_alive() is False
        assert errors == []
        assert child_existed_at_reuse == [False]
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        with contextlib.suppress(ProcessLookupError):
            os.kill(child_pid, signal.SIGKILL)
    assert retire_native_validation_guard(
        root,
        validation_lease=lease,
        owner=owner,
    ) is True


def test_native_command_timeout_begins_after_capacity_acquisition(tmp_path: Path) -> None:
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    gate = lease.acquire(
        ValidationLeaseOwner.exact_gate(
            project_id="project",
            task_id="GATE-1",
            authority_generation="gate-generation",
        )
    )
    real_bin = tmp_path / "real-bin"
    real_bin.mkdir()
    real_make = real_bin / "make"
    real_make.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    real_make.chmod(0o700)
    guarded, _ = install_native_validation_guard(
        {"PATH": f"{real_bin}{os.pathsep}{os.environ.get('PATH', os.defpath)}"},
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=ValidationLeaseOwner.auditor(
            project_id="project",
            task_id="AUDIT-1",
            authority_generation="audit-generation",
        ),
        timeout_seconds=0.2,
    )
    process = subprocess.Popen(
        ["make", "test"],
        env={**os.environ, **guarded},
        pass_fds=_guard_pass_fds(guarded),
        start_new_session=True,
    )
    _wait_until(lambda: lease.status().waiter_count == 1)
    time.sleep(0.3)
    gate.release()

    assert process.wait(timeout=5) == 0


def test_native_launcher_ignores_candidate_pythonpath_poisoning(tmp_path: Path) -> None:
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    poison_root = tmp_path / "poison"
    poison_package = poison_root / "oompah"
    poison_package.mkdir(parents=True)
    marker = tmp_path / "poisoned"
    (poison_package / "__init__.py").write_text("", encoding="utf-8")
    (poison_package / "native_validation_guard.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).touch()\n"
        "raise RuntimeError('candidate module loaded')\n",
        encoding="utf-8",
    )
    real_bin = tmp_path / "real-bin"
    real_bin.mkdir()
    real_make = real_bin / "make"
    real_make.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    real_make.chmod(0o700)
    guarded, _ = install_native_validation_guard(
        {
            "PATH": f"{real_bin}{os.pathsep}{os.environ.get('PATH', os.defpath)}",
            "PYTHONPATH": str(poison_root),
        },
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=ValidationLeaseOwner.worker(
            project_id="project",
            task_id="TASK-1",
            authority_generation="generation",
        ),
        timeout_seconds=10,
    )

    completed = subprocess.run(
        ["make", "help"],
        env={**os.environ, **guarded},
        pass_fds=_guard_pass_fds(guarded),
        check=False,
        timeout=5,
    )

    assert completed.returncode == 0
    assert marker.exists() is False


def test_native_shell_entrypoint_fences_path_reassignment_and_local_wrapper(
    tmp_path: Path,
) -> None:
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    gate = lease.acquire(
        ValidationLeaseOwner.exact_gate(
            project_id="project",
            task_id="GATE-1",
            authority_generation="gate-generation",
        )
    )
    marker = tmp_path / "started"
    script = tmp_path / "ci" / "test.sh"
    script.parent.mkdir()
    script.write_text(f"#!/bin/sh\ntouch {marker}\n", encoding="utf-8")
    script.chmod(0o700)
    guarded, _ = install_native_validation_guard(
        {"PATH": os.environ.get("PATH", os.defpath)},
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=ValidationLeaseOwner.worker(
            project_id="project",
            task_id="TASK-1",
            authority_generation="generation",
        ),
        timeout_seconds=10,
    )
    process = subprocess.Popen(
        [guarded["SHELL"], "-lc", "PATH=/usr/bin:/bin; ./ci/test.sh"],
        cwd=tmp_path,
        env={**os.environ, **guarded},
        pass_fds=_guard_pass_fds(guarded),
    )
    try:
        _wait_until(lambda: lease.status().waiter_count == 1)
        assert marker.exists() is False
    finally:
        gate.release()

    assert process.wait(timeout=5) == 0
    assert marker.exists() is True


def test_native_capacity_wait_observes_session_cancellation(tmp_path: Path) -> None:
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    gate = lease.acquire(
        ValidationLeaseOwner.exact_gate(
            project_id="project",
            task_id="GATE-1",
            authority_generation="gate-generation",
        )
    )
    real_bin = tmp_path / "real-bin"
    real_bin.mkdir()
    real_make = real_bin / "make"
    real_make.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    real_make.chmod(0o700)
    guarded, root = install_native_validation_guard(
        {"PATH": f"{real_bin}{os.pathsep}{os.environ.get('PATH', os.defpath)}"},
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=ValidationLeaseOwner.auditor(
            project_id="project",
            task_id="AUDIT-1",
            authority_generation="audit-generation",
        ),
        timeout_seconds=10,
    )
    process = subprocess.Popen(
        ["make", "test"],
        env={**os.environ, **guarded},
        pass_fds=_guard_pass_fds(guarded),
    )
    _wait_until(lambda: lease.status().waiter_count == 1)

    (root / "cancelled").touch()

    assert process.wait(timeout=5) != 0
    _wait_until(lambda: lease.status().waiter_count == 0)
    gate.release()


def test_native_post_attach_cancellation_exits_without_self_stopping(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    real_bin = tmp_path / "real-bin"
    real_bin.mkdir()
    real_make = real_bin / "make"
    real_make.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    real_make.chmod(0o700)
    guarded, root = install_native_validation_guard(
        {"PATH": f"{real_bin}{os.pathsep}{os.environ.get('PATH', os.defpath)}"},
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=ValidationLeaseOwner.auditor(
            project_id="project",
            task_id="AUDIT-1",
            authority_generation="audit-generation",
        ),
        timeout_seconds=10,
    )
    guard_make = Path(guarded["PATH"].split(os.pathsep, 1)[0]) / "make"
    real_attach = ValidationLeaseHandle.attach_process

    def attach_then_cancel(self, process, *, timeout_seconds):
        real_attach(self, process, timeout_seconds=timeout_seconds)
        (root / "cancelled").touch()

    monkeypatch.setattr(ValidationLeaseHandle, "attach_process", attach_then_cancel)
    monkeypatch.setattr("oompah.native_validation_guard.os.getpgrp", os.getpid)
    monkeypatch.setattr(
        "oompah.native_validation_guard._peer_is_guard_launcher",
        lambda *_args: True,
    )
    monkeypatch.setattr(
        "oompah.native_validation_guard._peer_guard_invocation",
        lambda *_args: ("make test", dict(os.environ), tmp_path),
    )
    monkeypatch.setattr(
        "oompah.native_validation_guard._process_group_id",
        lambda _pid: os.getpid(),
    )
    monkeypatch.setattr(
        "oompah.native_validation_guard.os.execve",
        lambda *_args: pytest.fail("cancelled native command reached execve"),
    )
    monkeypatch.setenv(
        "OOMPAH_NATIVE_VALIDATION_CAPABILITY_FD",
        guarded["OOMPAH_NATIVE_VALIDATION_CAPABILITY_FD"],
    )
    monkeypatch.setattr(sys, "argv", [str(guard_make), "test"])

    with pytest.raises(RuntimeError, match="authority was withdrawn"):
        main()

    _wait_until(lambda: lease.status().owner_count == 0)


def test_native_stdin_shell_waits_for_validation_capacity(tmp_path: Path) -> None:
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    gate = lease.acquire(
        ValidationLeaseOwner.exact_gate(
            project_id="project",
            task_id="GATE-1",
            authority_generation="gate-generation",
        )
    )
    marker = tmp_path / "started"
    script_input = tmp_path / "stdin.sh"
    script_input.write_text(f"touch {marker}\n", encoding="utf-8")
    guarded, _ = install_native_validation_guard(
        {"PATH": os.environ.get("PATH", os.defpath)},
        runtime_root=tmp_path / "guard",
        validation_lease=lease,
        owner=ValidationLeaseOwner.worker(
            project_id="project",
            task_id="TASK-1",
            authority_generation="generation",
        ),
        timeout_seconds=10,
    )
    with script_input.open("r", encoding="utf-8") as stdin:
        process = subprocess.Popen(
            ["bash", "-s"],
            stdin=stdin,
            env={**os.environ, **guarded},
            pass_fds=_guard_pass_fds(guarded),
        )
        try:
            _wait_until(lambda: lease.status().waiter_count == 1)
            assert marker.exists() is False
        finally:
            gate.release()

        assert process.wait(timeout=5) == 0
    assert marker.exists() is True
