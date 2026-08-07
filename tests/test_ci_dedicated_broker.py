"""Dedicated self-hosted CI validation admission and lifecycle tests."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from oompah.validation_resource_lease import (
    ValidationLeaseOwner,
    ValidationResourceLease,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BROKER = REPOSITORY_ROOT / "scripts" / "ci-dedicated-broker.py"
pytestmark = pytest.mark.timeout(30)


def _wait_until(predicate, *, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("condition did not become true")


def _write_test(directory: Path, body: str) -> Path:
    directory.mkdir(parents=True)
    test_file = directory / "test_ci_payload.py"
    test_file.write_text(body, encoding="utf-8")
    return test_file


def _broker_command(
    tmp_path: Path,
    test_path: Path,
    *,
    artifact_name: str = "artifacts",
    run_id: str = "run-42",
    run_attempt: str = "3",
    job_id: str = "test:python-3.13",
    timeout_seconds: float = 30.0,
) -> tuple[list[str], Path, Path]:
    database = tmp_path / "validation.sqlite3"
    artifacts = tmp_path / artifact_name
    command = [
        sys.executable,
        str(BROKER),
        "--lease-db",
        str(database),
        "--artifact-dir",
        str(artifacts),
        "--project-id",
        "proj-ci",
        "--run-id",
        run_id,
        "--run-attempt",
        run_attempt,
        "--job-id",
        job_id,
        "--run-as",
        f"{os.geteuid()}:{os.getegid()}",
        "--timeout-seconds",
        str(timeout_seconds),
        str(test_path),
    ]
    return command, database, artifacts


def _environment() -> dict[str, str]:
    return {**os.environ, "PYTHONPATH": str(REPOSITORY_ROOT)}


def test_broker_waits_for_shared_capacity_and_uses_stable_run_authority(
    tmp_path: Path,
) -> None:
    test_file = _write_test(tmp_path / "payload", "def test_ok():\n    assert True\n")
    command, database, artifacts = _broker_command(tmp_path, test_file)
    lease = ValidationResourceLease(database, poll_seconds=0.01)
    blocker = lease.acquire(
        ValidationLeaseOwner.exact_gate(
            project_id="other-project",
            task_id="exact-gate",
            authority_generation="head-sha",
        )
    )
    broker = subprocess.Popen(
        command,
        cwd=REPOSITORY_ROOT,
        env=_environment(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        _wait_until(lambda: lease.status().waiter_count == 1)
        assert lease.status().owner_count == 1
        blocker.release()
        _wait_until(
            lambda: bool(
                lease.status().owners and lease.status().owners[0]["child_pid"]
            )
        )
        owner = lease.status().owners[0]
        assert owner["project_id"] == "proj-ci"
        assert owner["task_id"] == "github-actions:test:python-3.13"
        assert owner["authority_generation"] == "run-42:3"
        assert owner["child_pid"] is not None
        stdout, stderr = broker.communicate(timeout=20)
    finally:
        blocker.release()
        if broker.poll() is None:
            broker.kill()
            broker.wait(timeout=5)
    assert broker.returncode == 0, (stdout, stderr)
    assert lease.status().owner_count == 0
    assert json.loads((artifacts / "broker-result.json").read_text())["status"] == (
        "completed"
    )


def test_concurrent_dedicated_runs_never_exceed_capacity(tmp_path: Path) -> None:
    body = "import time\ndef test_slow():\n    time.sleep(0.4)\n"
    test_one = _write_test(tmp_path / "one", body)
    test_two = _write_test(tmp_path / "two", body)
    command_one, database, _ = _broker_command(
        tmp_path,
        test_one,
        artifact_name="artifacts-one",
        job_id="test:python-3.11",
    )
    command_two, _, _ = _broker_command(
        tmp_path,
        test_two,
        artifact_name="artifacts-two",
        job_id="test:python-3.12",
    )
    lease = ValidationResourceLease(database, poll_seconds=0.01)
    processes = [
        subprocess.Popen(
            command,
            cwd=REPOSITORY_ROOT,
            env=_environment(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for command in (command_one, command_two)
    ]
    maximum_owners = 0
    try:
        _wait_until(lambda: lease.status().owner_count + lease.status().waiter_count == 2)
        while any(process.poll() is None for process in processes):
            maximum_owners = max(maximum_owners, lease.status().owner_count)
            time.sleep(0.02)
        results = [process.communicate(timeout=5) for process in processes]
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
    assert maximum_owners == 1
    assert [process.returncode for process in processes] == [0, 0], results
    assert lease.status().owner_count == 0


def test_signal_cancellation_terminates_tree_and_releases_capacity(
    tmp_path: Path,
) -> None:
    test_file = _write_test(
        tmp_path / "payload",
        "import time\ndef test_slow():\n    time.sleep(60)\n",
    )
    command, database, artifacts = _broker_command(tmp_path, test_file)
    lease = ValidationResourceLease(database, poll_seconds=0.01)
    broker = subprocess.Popen(
        command,
        cwd=REPOSITORY_ROOT,
        env=_environment(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    _wait_until(
        lambda: bool(
            lease.status().owners and lease.status().owners[0]["child_pid"]
        )
    )
    broker.send_signal(signal.SIGTERM)
    stdout, stderr = broker.communicate(timeout=20)
    assert broker.returncode == 128 + signal.SIGTERM, (stdout, stderr)
    _wait_until(lambda: lease.status().owner_count == 0)
    result = json.loads((artifacts / "broker-result.json").read_text())
    assert result["status"] == "cancelled"


def test_broker_death_does_not_orphan_capacity_or_pytest(tmp_path: Path) -> None:
    test_file = _write_test(
        tmp_path / "payload",
        "import time\ndef test_slow():\n    time.sleep(60)\n",
    )
    command, database, _ = _broker_command(tmp_path, test_file)
    lease = ValidationResourceLease(database, poll_seconds=0.01)
    broker = subprocess.Popen(
        command,
        cwd=REPOSITORY_ROOT,
        env=_environment(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _wait_until(
        lambda: bool(
            lease.status().owners and lease.status().owners[0]["child_pid"]
        )
    )
    child_pid = int(lease.status().owners[0]["child_pid"])
    broker.kill()
    broker.wait(timeout=5)
    _wait_until(lambda: lease.status().owner_count == 0)
    with pytest.raises(ProcessLookupError):
        os.kill(child_pid, 0)


def test_timeout_terminates_pytest_and_releases_capacity(tmp_path: Path) -> None:
    test_file = _write_test(
        tmp_path / "payload",
        "import time\ndef test_slow():\n    time.sleep(60)\n",
    )
    command, database, artifacts = _broker_command(
        tmp_path,
        test_file,
        timeout_seconds=1.0,
    )
    completed = subprocess.run(
        command,
        cwd=REPOSITORY_ROOT,
        env=_environment(),
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert completed.returncode == 124, completed
    assert ValidationResourceLease(database).status().owner_count == 0
    result = json.loads((artifacts / "broker-result.json").read_text())
    assert result["status"] == "timed_out"


def test_full_failure_diagnostics_are_durable_but_console_is_bounded(
    tmp_path: Path,
) -> None:
    marker = "failure-detail-" * 10_000
    test_file = _write_test(
        tmp_path / "payload",
        f"def test_failure():\n    assert False, {marker!r}\n",
    )
    command, database, artifacts = _broker_command(tmp_path, test_file)
    completed = subprocess.run(
        command,
        cwd=REPOSITORY_ROOT,
        env=_environment(),
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert completed.returncode == 1
    assert len(completed.stdout.encode()) <= 34 * 1024
    assert (artifacts / "pytest-full.log").stat().st_size > 100_000
    assert marker in (artifacts / "pytest-full.log").read_text()
    junit = (artifacts / "test-results.xml").read_text()
    assert "test_failure" in junit
    assert ValidationResourceLease(database).status().owner_count == 0


def test_pytest_runs_with_private_non_root_identity_environment(
    tmp_path: Path,
) -> None:
    test_file = _write_test(
        tmp_path / "payload",
        f"""import os
import subprocess
from pathlib import Path

def test_identity():
    assert os.geteuid() != 0
    assert os.environ["USER"] == "oompah-ci"
    assert Path(os.environ["HOME"]).is_dir()
    assert str(Path(os.environ["HOME"]).parent) == str(Path(os.environ["TMPDIR"]).parent)
    assert subprocess.run(
        ["git", "-C", {str(REPOSITORY_ROOT)!r}, "rev-parse", "--is-inside-work-tree"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip() == "true"
""",
    )
    command, _, artifacts = _broker_command(tmp_path, test_file)
    completed = subprocess.run(
        command,
        cwd=REPOSITORY_ROOT,
        env=_environment(),
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert completed.returncode == 0, completed
    result = json.loads((artifacts / "broker-result.json").read_text())
    assert result["run_as_uid"] == os.geteuid()
    assert result["run_as_uid"] != 0


def test_workflow_brokers_pytest_and_always_uploads_diagnostics() -> None:
    workflow = (REPOSITORY_ROOT / ".github/workflows/ci-dedicated.yml").read_text()
    assert "scripts/ci-dedicated-broker.py" in workflow
    assert "--lease-db \"$OOMPAH_VALIDATION_RESOURCE_DB\"" in workflow
    assert "--run-id \"$GITHUB_RUN_ID\"" in workflow
    assert "--run-attempt \"$GITHUB_RUN_ATTEMPT\"" in workflow
    assert "--run-as \"$(id -u nobody):" in workflow
    assert "run: pytest -v" not in workflow
    assert "uses: actions/upload-artifact@v4" in workflow
    assert "if: always()" in workflow
    assert "if-no-files-found: error" in workflow


def test_workflow_provisions_and_asserts_a_supported_node() -> None:
    workflow = (REPOSITORY_ROOT / ".github/workflows/ci-dedicated.yml").read_text()
    assert "uses: actions/setup-node@v4" in workflow
    assert 'node-version: "22"' in workflow
    assert "major < 20" in workflow
    assert 'require("node:assert/strict")' in workflow
