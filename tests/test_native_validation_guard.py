from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from oompah.native_validation_guard import install_native_validation_guard
from oompah.validation_resource_lease import (
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
