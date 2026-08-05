from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from oompah.native_validation_guard import install_native_validation_guard, main
from oompah.validation_resource_lease import (
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
        check=False,
        timeout=5,
    )

    assert completed.returncode == 0
    assert lease.status().owner_count == 0


@pytest.mark.parametrize("command", ["pnpm", "yarn"])
def test_native_node_test_runner_waits_for_validation_capacity(
    tmp_path: Path,
    command: str,
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
    process = subprocess.Popen(
        [command, "test"],
        env={**os.environ, **guarded},
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
    process = subprocess.Popen(["make", "test"], env={**os.environ, **guarded})
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
        "oompah.native_validation_guard.os.execve",
        lambda *_args: pytest.fail("cancelled native command reached execve"),
    )
    monkeypatch.setattr(sys, "argv", [str(guard_make), "test"])

    with pytest.raises(RuntimeError, match="withdrawn before exec"):
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
        )
        try:
            _wait_until(lambda: lease.status().waiter_count == 1)
            assert marker.exists() is False
        finally:
            gate.release()

        assert process.wait(timeout=5) == 0
    assert marker.exists() is True
