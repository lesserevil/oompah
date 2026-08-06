from __future__ import annotations

import array
import contextlib
import json
import os
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from oompah import native_validation_guard as guard_module
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
    ValidationResourceLease,
)


def _wait_until(predicate, *, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition did not become true")


def _guard_pass_fds(environment: dict[str, str]) -> tuple[int, ...]:
    raw = environment.get("OOMPAH_NATIVE_VALIDATION_CAPABILITY_FD", "")
    return (int(raw),) if raw else ()


def _test_native_broker(
    tmp_path: Path,
    *,
    task_id: str,
) -> tuple[guard_module._NativeValidationLeaseBroker, Path]:
    root = tmp_path / task_id.lower()
    root.mkdir()
    (root / guard_module._CONFIG_NAME).write_text("{}", encoding="utf-8")
    broker = guard_module._NativeValidationLeaseBroker(
        root,
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
                    root / guard_module._BROKER_SOCKET_NAME
                ),
            },
            pass_fds=(spoofed,),
            check=False,
            capture_output=True,
            timeout=5,
        )

        assert completed.returncode == 0
        assert completed.stdout == b"DENIED\n"
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

    assert root.resolve() not in guard_module._BROKER_REGISTRY
    assert not any(
        thread.is_alive()
        and thread.name == "native-validation-broker-BOOTSTRAP-FAILURE"
        for thread in threading.enumerate()
    )


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
        client.connect(str(root / guard_module._BROKER_SOCKET_NAME))
        _wait_until(lambda: len(broker._handler_threads) == 1)
        handlers = tuple(broker._handler_threads)

        broker.stop()

        assert all(handler.is_alive() is False for handler in handlers)
        assert broker._handler_threads == set()
        assert broker._handler_connections == set()
    finally:
        client.close()
        broker.stop()


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
    real_bin = tmp_path / "real-bin"
    real_bin.mkdir()
    real_make = real_bin / "make"
    real_make.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
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

    completed = subprocess.run(
        ["make", "help"],
        env={**os.environ, **guarded},
        pass_fds=_guard_pass_fds(guarded),
        check=False,
        timeout=5,
    )

    assert completed.returncode == 0
    assert lease.status().owner_count == 0


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
    assert lease.status().owner_count == 0


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
    assert lease.status().owner_count == 0


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
    assert lease.status().owner_count == 0


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
    assert lease.status().owner_count == 0


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

    first = subprocess.Popen(
        ["/bin/bash", "-c", "printf first"],
        env={**os.environ, **guarded},
        pass_fds=_guard_pass_fds(guarded),
        stdout=subprocess.PIPE,
        text=True,
    )
    second = subprocess.Popen(
        ["/bin/bash", "-c", "printf second"],
        env={**os.environ, **guarded},
        pass_fds=_guard_pass_fds(guarded),
        stdout=subprocess.PIPE,
        text=True,
    )

    assert first.communicate(timeout=5)[0] == "first"
    assert second.communicate(timeout=5)[0] == "second"
    assert first.returncode == 0
    assert second.returncode == 0
    assert consume_native_validation_boundary(root, "printf first", "item-1") is True
    assert consume_native_validation_boundary(root, "printf second", "item-2") is True
    assert consume_native_validation_boundary(root, "printf first", "item-3") is False


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
    assert lease.status().owner_count == 0


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
    outer = subprocess.Popen(
        [
            "/bin/bash",
            "-c",
            "(sleep 0.25; /bin/bash -c "
            "': > \"$OOMPAH_TEST_NATIVE_MARKER\"') &",
        ],
        env={**os.environ, **guarded},
        pass_fds=_guard_pass_fds(guarded),
    )
    assert outer.wait(timeout=5) == 0

    assert retire_native_validation_guard(
        root,
        validation_lease=lease,
        owner=owner,
    ) is False
    time.sleep(0.5)

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
    assert lease.status().owner_count == 0


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
        _wait_until(lambda: lease.status().waiter_count == 1)
        assert marker.exists() is False
    finally:
        gate.release()

    assert process.wait(timeout=5) == 0
    assert marker.exists() is True
    assert lease.status().owner_count == 0


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
        "subprocess.Popen(['make', 'test'], env=os.environ.copy(), "
        "stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); "
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

    _wait_until(lambda: pid_path.exists() and lease.status().owner_count == 1)
    heavy_pid = int(pid_path.read_text(encoding="utf-8").strip())
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
        "setsid bash -c 'trap \"\" TERM; sleep 30' &\n"
        "printf '%s' \"$!\" > \"$OOMPAH_TEST_DESCENDANT_PID\"\n"
        "exit 0\n",
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
    _wait_until(descendant_pid_path.exists)
    descendant_pid = int(descendant_pid_path.read_text(encoding="utf-8"))

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
        "setsid bash -c 'trap \"\" TERM; sleep 30' &\n"
        "printf '%s' \"$!\" > \"$OOMPAH_TEST_DESCENDANT_PID\"\n"
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
    _wait_until(descendant_pid_path.exists)
    descendant_pid = int(descendant_pid_path.read_text(encoding="utf-8"))
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
    _wait_until(child_pid_path.exists)
    child_pid = int(child_pid_path.read_text(encoding="utf-8"))
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

    with pytest.raises(RuntimeError, match="broker denied execution"):
        main()

    assert lease.status().owner_count == 0


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
