"""Focused coverage for the shared heavyweight-validation lane."""

from __future__ import annotations

import os
import shlex
import sqlite3
import subprocess
import sys
import threading
import time
import types
from pathlib import Path

import pytest

from oompah import validation_resource_lease as validation_lease_module
from oompah.api_agent import _exec_run_command
from oompah.auditor import check_auditor_command
from oompah.tool_liveness import ToolLivenessMonitor
from oompah.validation_resource_lease import (
    AUDITOR_PRIORITY,
    EXACT_GATE_PRIORITY,
    VALIDATION_KIND_AUDITOR,
    VALIDATION_KIND_WORKER,
    WORKER_PRIORITY,
    ValidationLeaseCancelled,
    ValidationLeaseOwner,
    ValidationResourceLease,
    is_heavyweight_validation_command,
    managed_agent_validation_owner,
)


def _wait_for(predicate, timeout: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition did not become true")


def _gate_owner(project: str, task: str) -> ValidationLeaseOwner:
    return ValidationLeaseOwner.exact_gate(
        project_id=project,
        task_id=task,
        authority_generation=f"generation-{task}",
    )


def _audit_owner(project: str, task: str) -> ValidationLeaseOwner:
    return ValidationLeaseOwner.auditor(
        project_id=project,
        task_id=task,
        authority_generation=f"attempt-{task}",
    )


def _worker_owner(project: str, task: str) -> ValidationLeaseOwner:
    return ValidationLeaseOwner.worker(
        project_id=project,
        task_id=task,
        authority_generation=f"worker-{task}",
    )


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("make test", True),
        ("make", True),
        ("make -C . test-serial", True),
        ("make test-unit", True),
        ("make check-secrets", False),
        ("make --help", False),
        ("pytest --help", False),
        ("pytest --version", False),
        ("python -m pytest --help", False),
        ("python -m unittest --help", False),
        ("echo ready; make test", True),
        ("echo ready\nmake test", True),
        ("./ci/test.sh", True),
        (".venv/bin/python -m pytest tests/test_one.py", True),
        ("make test && git status --short", True),
        ("pytest", True),
        ("uv run pytest -q", True),
        ("uv run --python 3.12 pytest -q", True),
        ("PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q", True),
        ("timeout 10s python -m pytest tests/", True),
        ("bash -lc 'python -m pytest tests/'", True),
        ("exec pytest", True),
        ("exec -a validation pytest", True),
        ("time -p pytest", True),
        ("/usr/bin/time -f %E pytest", True),
        ("bash -ce 'pytest'", True),
        ("sh -ec 'pytest tests/'", True),
        ("bash --noprofile -O extglob -c 'make test'", True),
        ("bash -o errexit -ce 'cargo test'", True),
        ("uv --directory . run pytest -q", True),
        ("uv --allow-insecure-host example.com run --group test pytest", True),
        ("uv --project=. run python -m pytest tests/", True),
        ("python -m pytest tests/", True),
        ("python -I -m pytest tests/", True),
        ("python3.12 -X dev -W error -m pytest -q", True),
        (
            "python -m pytest -q tests/test_acp_backends.py tests/test_providers.py "
            "tests/test_providers_ui.py tests/test_acp_agent.py "
            "tests/test_orchestrator_handlers.py",
            True,
        ),
        ("tox -q", True),
        ("pytest tests/test_one.py", True),
        ("pytest tests/test_*.py", True),
        ("pytest 'tests/test_{one,two}.py'", True),
        ("pytest 'tests/test_[ab].py'", True),
        ("pytest tests/test_one.py tests/test_two.py", True),
        ("pytest tests/test_one.py::test_case", True),
        ("pytest -k exact_case", True),
        ("pytest tests/test_one.py -k exact_case", True),
        ("pytest tests/test_one.py -n auto", True),
        ("pytest tests/test_one.py --numprocesses=4", True),
        ("pytest --collect-only", True),
        ("pytest --collect-only tests/test_one.py", True),
        (
            "pytest --collect-only tests/test_one.py tests/test_two.py",
            True,
        ),
        ("npm test", True),
        ("npm --prefix web test -- --runInBand", True),
        ("npm --workspace web t", True),
        ("npm run test:unit", True),
        ("npm run build", False),
        ("pnpm test", True),
        ("pnpm --filter web test", True),
        ("pnpm run test:unit", True),
        ("yarn test", True),
        ("yarn run test", True),
        ("python -m unittest discover", True),
        ("python -I -m unittest discover -s tests", True),
        ("python -m unittest tests.test_one.TestCase.test_case", True),
        ("cargo test", True),
        ("cargo +nightly --color always test --workspace", True),
        ("cargo --config net.retry=2 test", True),
        ("cargo nextest run", True),
        ("cargo build", False),
        ("rg pytest tests", False),
        ("/usr/bin/rg pytest tests", False),
        ("./rg pytest tests", True),
        ("/workspace/bin/rg pytest tests", True),
        ("python ci/test.py", True),
        ("python ci/test", True),
        ("bash ci/test.sh", True),
        ("printf 'make test\\n' | bash", True),
        ("bash -s", True),
        ("printf 'make test\\n' | bash -h", True),
        ("python", True),
        ("node --input-type=module -", True),
        ("perl -", True),
        ("ruby -", True),
        ("python --version", False),
        ("bash --version", False),
        ("node --version", False),
        ("env -S 'python -m pytest'", True),
        ("env -S 'bash -c \"make test\"'", True),
        ("env --split-string='python -m pytest'", True),
        ("python -c \"__import__('pytest').main([])\"", True),
        ("python -c \"__import__('subprocess').run(['make','test'])\"", True),
        ("node -e \"require('child_process').execSync('npm test')\"", True),
        ("perl -e 'system q(make test)'", True),
        ("ruby -e 'system %q(make test)'", True),
        ("exec rg pytest tests", False),
        ("time git status --short", False),
        ("bash -ce 'echo pytest'", False),
        ("echo make test", False),
        ("git status --short", False),
    ],
)
def test_classifier_is_heavy_first_and_inspection_only_checks_bypass(command, expected):
    assert is_heavyweight_validation_command(command) is expected


@pytest.mark.parametrize(
    "command",
    [
        "make test",
        "make test-serial",
        "pytest",
        "pytest tests/test_one.py",
        "pytest tests/test_one.py::test_case",
        "py.test tests/test_*.py",
        "python -m pytest",
        "python -m pytest tests/test_one.py::test_case",
        "python -m unittest discover",
        "python -m unittest tests.test_one.TestCase.test_case",
        "npm test",
        "pnpm test",
        "yarn test",
    ],
)
def test_heavy_auditor_contract_commands_acquire_before_popen(
    tmp_path,
    monkeypatch,
    command,
):
    events: list[str] = []

    class FakeHandle:
        pass_fds: tuple[int, ...] = ()

        def attach_process(self, process, *, timeout_seconds):
            events.append("attach")

        def release(self):
            events.append("release")

    class FakeLease:
        def acquire(self, owner, *, is_cancelled=None):
            events.append("acquire")
            return FakeHandle()

    class FakeProcess:
        pid = os.getpid()
        returncode = 0

        def __init__(self, *_args, **_kwargs):
            events.append("popen")

        def communicate(self, timeout=None):
            return "", ""

    monkeypatch.setattr("oompah.api_agent.subprocess.Popen", FakeProcess)

    assert check_auditor_command(command) is None
    assert is_heavyweight_validation_command(command) is True
    result = _exec_run_command(
        tmp_path,
        {"command": command},
        timeout=2,
        validation_lease=FakeLease(),
        validation_owner=_audit_owner("project", "audit"),
        require_validation_lease=True,
    )

    assert result == "exit_code: 0"
    assert events == ["acquire", "popen", "attach", "release"]


def test_managed_owner_uses_audit_attempt_before_worker_scope():
    owner = managed_agent_validation_owner(
        types.SimpleNamespace(auditor_session=True),
        {
            "project_id": "audit-project",
            "task_id": "AUDIT-1",
            "attempt_id": "attempt-7",
        },
        project_id="worker-project",
        task_id="WORK-1",
        authority_generation="worker-generation",
    )

    assert owner is not None
    assert owner.kind == VALIDATION_KIND_AUDITOR
    assert owner.project_id == "audit-project"
    assert owner.task_id == "AUDIT-1"
    assert owner.authority_generation == "attempt-7"


def test_gate_and_auditor_never_overlap_and_wait_does_not_start_tool_timeout(tmp_path):
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    gate = lease.acquire(_gate_owner("p1", "gate"))
    makefile = tmp_path / "Makefile"
    marker = tmp_path / "started"
    makefile.write_text(f"test:\n\t@touch {marker}\n", encoding="utf-8")
    monitor = ToolLivenessMonitor()
    result: list[str] = []
    worker = threading.Thread(
        target=lambda: result.append(
            _exec_run_command(
                tmp_path,
                {"command": "make test"},
                timeout=2,
                tool_liveness=monitor,
                validation_lease=lease,
                validation_owner=_audit_owner("p1", "audit"),
            )
        )
    )
    worker.start()
    _wait_for(lambda: lease.status().waiter_count == 1)

    assert not marker.exists()
    waiting = monitor.snapshot()
    assert waiting is not None
    assert waiting.phase == "waiting_for_capacity"
    assert waiting.protects_from_stall is True
    assert waiting.deadline_exceeded is False
    gate.release()
    worker.join(timeout=3)

    assert not worker.is_alive()
    assert marker.exists()
    assert result and "exit_code: 0" in result[0]
    assert lease.status().owner_count == 0


def test_heavy_command_observes_cancellation_after_capacity_acquisition(tmp_path):
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    makefile = tmp_path / "Makefile"
    started = tmp_path / "started"
    makefile.write_text(
        f"test:\n\t@touch {started}\n\t@sleep 30\n",
        encoding="utf-8",
    )
    cancelled = threading.Event()
    results: list[str] = []
    worker = threading.Thread(
        target=lambda: results.append(
            _exec_run_command(
                tmp_path,
                {"command": "make test"},
                timeout=60,
                validation_lease=lease,
                validation_owner=_audit_owner("p1", "audit"),
                lease_cancelled=cancelled.is_set,
            )
        )
    )
    worker.start()
    _wait_for(lambda: started.exists() and lease.status().owner_count == 1)

    cancelled.set()
    worker.join(timeout=3)

    assert worker.is_alive() is False
    assert results == [
        "Error: validation authority withdrawn while command was running"
    ]
    assert lease.status().owner_count == 0


def test_cancellation_between_acquire_and_popen_never_launches_command(
    tmp_path,
    monkeypatch,
):
    cancelled = threading.Event()
    released: list[bool] = []

    class FakeHandle:
        pass_fds: tuple[int, ...] = ()

        def release(self):
            released.append(True)

    class FakeLease:
        def acquire(self, _owner, *, is_cancelled=None):
            cancelled.set()
            return FakeHandle()

    def forbidden_popen(*_args, **_kwargs):
        raise AssertionError("cancelled command reached Popen")

    monkeypatch.setattr("oompah.api_agent.subprocess.Popen", forbidden_popen)

    result = _exec_run_command(
        tmp_path,
        {"command": "make test"},
        timeout=5,
        validation_lease=FakeLease(),
        validation_owner=_audit_owner("p1", "audit"),
        lease_cancelled=cancelled.is_set,
    )

    assert result == "Error: validation authority withdrawn before command launch"
    assert released == [True]


def test_release_metadata_failure_does_not_leak_flock_or_mask_result(
    tmp_path,
    monkeypatch,
):
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    handle = lease.acquire(_gate_owner("p1", "first"))
    real_connect = lease._connect

    def fail_connect():
        raise sqlite3.OperationalError("transient release failure")

    monkeypatch.setattr(lease, "_connect", fail_connect)
    assert handle.release() is False
    monkeypatch.setattr(lease, "_connect", real_connect)

    with lease.acquire(
        _gate_owner("p2", "replacement"),
        wait_timeout_seconds=1,
    ):
        assert lease.status().owner_count == 1


def test_release_preserves_owner_while_background_descendant_holds_flock(tmp_path):
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    handle = lease.acquire(_gate_owner("p1", "shell"))
    inherited_fd = handle.pass_fds[0]
    launcher = (
        "import os, subprocess, sys; "
        "fd=int(sys.argv[1]); "
        "subprocess.Popen(['sleep', '0.5'], pass_fds=(fd,)); "
        "os._exit(0)"
    )
    shell = subprocess.Popen(
        [sys.executable, "-c", launcher, str(inherited_fd)],
        pass_fds=handle.pass_fds,
        start_new_session=True,
    )
    handle.attach_process(shell, timeout_seconds=5)
    assert shell.wait(timeout=2) == 0

    assert handle.release() is False
    assert lease.status().owner_count == 1

    with lease.acquire(
        _gate_owner("p2", "after-descendant"),
        wait_timeout_seconds=2,
    ):
        assert lease.status().owner_count == 1


def test_expired_detached_descendant_is_not_killed_via_stale_group_id(tmp_path):
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    handle = lease.acquire(_gate_owner("p1", "shell"))
    inherited_fd = handle.pass_fds[0]
    pid_path = tmp_path / "descendant.pid"
    launcher = (
        "import os, pathlib, subprocess, sys; "
        "fd=int(sys.argv[1]); "
        "child=subprocess.Popen(['sleep', '0.3'], pass_fds=(fd,), start_new_session=True); "
        "pathlib.Path(sys.argv[2]).write_text(str(child.pid)); "
        "os._exit(0)"
    )
    leader = subprocess.Popen(
        [sys.executable, "-c", launcher, str(inherited_fd), str(pid_path)],
        pass_fds=handle.pass_fds,
        start_new_session=True,
    )
    handle.attach_process(leader, timeout_seconds=0.05)
    assert leader.wait(timeout=2) == 0
    _wait_for(pid_path.exists)
    assert handle.release() is False
    time.sleep(0.06)

    descendant_pid = int(pid_path.read_text(encoding="utf-8"))
    # Once the recorded leader exits, neither its old PGID nor a locked slot
    # proves ownership of a detached descendant. Capacity remains fenced until
    # that descendant closes the inherited descriptor naturally.
    assert Path(f"/proc/{descendant_pid}").exists()

    with lease.acquire(
        _gate_owner("p2", "after-expiry"),
        wait_timeout_seconds=2,
    ):
        assert lease.status().owner_count == 1


def test_expired_stale_child_identity_never_calls_killpg(tmp_path, monkeypatch):
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    handle = lease.acquire(_gate_owner("p1", "stale-child"))
    child = subprocess.Popen(["true"], start_new_session=True)
    handle.attach_process(child, timeout_seconds=0.05)
    assert child.wait(timeout=2) == 0
    time.sleep(0.06)

    monkeypatch.setattr(
        "oompah.validation_resource_lease.os.killpg",
        lambda *_args: pytest.fail("stale process group was signaled"),
    )
    assert lease.status().owner_count == 1
    handle.release()


def test_cancel_owner_terminates_only_matching_attached_process_group(tmp_path):
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    owner = _audit_owner("p1", "audit")
    handle = lease.acquire(owner)
    process = subprocess.Popen(
        ["sleep", "30"],
        pass_fds=handle.pass_fds,
        start_new_session=True,
    )
    handle.attach_process(process, timeout_seconds=60)

    assert lease.cancel_owner(owner) == 1
    assert process.wait(timeout=3) != 0
    handle.release()
    assert lease.status().owner_count == 0


def test_cancel_owner_withdraws_matching_waiter_without_callback(tmp_path):
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    held = lease.acquire(_gate_owner("p1", "gate"))
    owner = _audit_owner("p1", "audit")
    errors: list[str] = []

    def wait() -> None:
        try:
            lease.acquire(owner)
        except ValidationLeaseCancelled as exc:
            errors.append(str(exc))

    waiter = threading.Thread(target=wait)
    waiter.start()
    _wait_for(lambda: lease.status().waiter_count == 1)

    assert lease.cancel_owner(owner) == 1
    waiter.join(timeout=3)

    assert waiter.is_alive() is False
    assert errors == ["validation authority withdrawn while waiting for capacity"]
    held.release()


def test_cancel_owner_durably_fences_acquire_to_attach_race(tmp_path):
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    owner = _audit_owner("p1", "attach-race")
    handle = lease.acquire(owner)

    assert lease.cancel_owner(owner) == 1
    with pytest.raises(
        ValidationLeaseCancelled,
        match="withdrawn before process attachment",
    ):
        handle.attach_process(
            types.SimpleNamespace(pid=os.getpid()),
            timeout_seconds=5,
        )
    handle.release()

    restarted = ValidationResourceLease(
        tmp_path / "lease.sqlite3",
        poll_seconds=0.01,
    )
    with pytest.raises(
        ValidationLeaseCancelled,
        match="withdrawn before capacity acquisition",
    ):
        restarted.acquire(owner)


def test_cancel_pruning_never_removes_an_active_owner_tombstone(
    tmp_path,
    monkeypatch,
):
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    owner = _audit_owner("p1", "active-cancel")
    handle = lease.acquire(owner)
    assert lease.cancel_owner(owner) == 1
    monkeypatch.setattr(
        "oompah.validation_resource_lease._CANCELLED_OWNER_RETENTION_SECONDS",
        0,
    )
    monkeypatch.setattr(
        "oompah.validation_resource_lease._CANCELLED_OWNER_LIMIT",
        1,
    )
    for index in range(5):
        lease.cancel_owner(_audit_owner("other", f"cancel-{index}"))

    with pytest.raises(
        ValidationLeaseCancelled,
        match="withdrawn before process attachment",
    ):
        handle.attach_process(
            types.SimpleNamespace(pid=os.getpid()),
            timeout_seconds=5,
        )
    handle.release()


def test_slot_probe_descriptors_are_not_ambiently_inheritable(tmp_path):
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    available = lease._try_lock_slots()
    try:
        assert available
        assert all(os.get_inheritable(fd) is False for fd in available.values())
    finally:
        lease._close_slot_locks(available.values())


@pytest.mark.parametrize(
    "command",
    [
        (
            "python -m pytest -q tests/test_acp_backends.py tests/test_providers.py "
            "tests/test_providers_ui.py tests/test_acp_agent.py "
            "tests/test_orchestrator_handlers.py"
        ),
        "pytest tests/test_one.py::test_case",
        "python -m pytest tests/test_one.py",
        "/usr/bin/python -m pytest tests/test_one.py::test_case",
        "python -m unittest tests.test_one.TestCase.test_case",
    ],
)
def test_worker_validation_queues_behind_gate_at_worker_priority(
    tmp_path,
    monkeypatch,
    command,
):
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    gate = lease.acquire(_gate_owner("p1", "gate"))
    process_started = threading.Event()

    class FakeProcess:
        pid = os.getpid()
        returncode = 0

        def __init__(self, *_args, **_kwargs):
            process_started.set()

        def communicate(self, timeout=None):
            return "", ""

    monkeypatch.setattr("oompah.api_agent.subprocess.Popen", FakeProcess)
    results: list[str] = []
    worker = threading.Thread(
        target=lambda: results.append(
            _exec_run_command(
                tmp_path,
                {"command": command},
                timeout=2,
                validation_lease=lease,
                validation_owner=_worker_owner("p2", "worker"),
                require_validation_lease=True,
            )
        )
    )
    worker.start()
    _wait_for(lambda: lease.status().waiter_count == 1)

    status = lease.status()
    assert process_started.is_set() is False
    assert status.waiters[0]["kind"] == VALIDATION_KIND_WORKER
    assert status.waiters[0]["priority"] == WORKER_PRIORITY
    assert WORKER_PRIORITY < AUDITOR_PRIORITY < EXACT_GATE_PRIORITY

    gate.release()
    worker.join(timeout=3)
    assert worker.is_alive() is False
    assert process_started.is_set() is True
    assert results == ["exit_code: 0"]


def test_focused_pytest_waits_for_exact_gate_before_real_process_start(tmp_path):
    marker = tmp_path / "focused-test-started"
    target = tmp_path / "target_test.py"
    target.write_text(
        "import os\n"
        "from pathlib import Path\n\n"
        "def test_runs_once():\n"
        "    marker_path = Path(os.environ['OOMPAH_FOCUSED_MARKER'])\n"
        "    with marker_path.open('x', encoding='utf-8') as marker:\n"
        "        marker.write(str(os.getpid()))\n",
        encoding="utf-8",
    )
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    gate = lease.acquire(_gate_owner("p1", "exact-gate"))
    command = (
        f"{shlex.quote(sys.executable)} -m pytest {shlex.quote(target.name)} -q"
    )
    result: list[str] = []
    worker = threading.Thread(
        target=lambda: result.append(
            _exec_run_command(
                tmp_path,
                {"command": command},
                timeout=10,
                env_overrides={"OOMPAH_FOCUSED_MARKER": str(marker)},
                validation_lease=lease,
                validation_owner=_worker_owner("p2", "focused"),
            )
        )
    )
    worker.start()
    _wait_for(lambda: lease.status().waiter_count == 1)

    assert marker.exists() is False
    assert worker.is_alive() is True

    gate.release()
    worker.join(timeout=10)

    assert worker.is_alive() is False
    assert result and "exit_code: 0" in result[0]
    assert marker.read_text(encoding="utf-8").isdigit()
    assert lease.status().owner_count == 0


def test_non_test_inspection_runs_without_validation_capacity(tmp_path):
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    gate = lease.acquire(_gate_owner("p1", "exact-gate"))

    result = _exec_run_command(
        tmp_path,
        {"command": "printf inspection"},
        timeout=2,
        validation_lease=lease,
        validation_owner=_worker_owner("p2", "inspection"),
    )

    assert "stdout:\ninspection" in result
    assert "exit_code: 0" in result
    assert lease.status().owner_count == 1
    assert lease.status().waiter_count == 0
    gate.release()


def test_capacity_is_process_safe_across_independent_instances(tmp_path):
    state_path = tmp_path / "lease.sqlite3"
    first = ValidationResourceLease(state_path, capacity=1, poll_seconds=0.01)
    second = ValidationResourceLease(state_path, capacity=1, poll_seconds=0.01)
    held = first.acquire(_gate_owner("p1", "one"))
    acquired = threading.Event()

    def waiter() -> None:
        with second.acquire(_gate_owner("p2", "two")):
            acquired.set()

    thread = threading.Thread(target=waiter)
    thread.start()
    _wait_for(lambda: first.status().waiter_count == 1)
    assert acquired.is_set() is False
    held.release()
    thread.join(timeout=3)
    assert acquired.is_set() is True


def test_status_is_authoritative_activity_not_an_alert(tmp_path):
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    held = lease.acquire(_gate_owner("p1", "gate"))
    cancelled = threading.Event()

    def wait() -> None:
        with pytest.raises(ValidationLeaseCancelled):
            lease.acquire(
                _worker_owner("p2", "worker"),
                is_cancelled=cancelled.is_set,
            )

    thread = threading.Thread(target=wait)
    thread.start()
    _wait_for(lambda: lease.status().waiter_count == 1)

    snapshot = lease.status().to_dict()
    assert snapshot["status"] == "busy"
    assert snapshot["available_capacity"] == 0
    assert snapshot["owner_count"] == 1
    assert snapshot["waiter_count"] == 1
    assert "alert" not in snapshot

    cancelled.set()
    thread.join(timeout=3)
    held.release()


def test_status_marks_legacy_provider_root_and_safe_recovery_action(
    tmp_path,
    monkeypatch,
):
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    held = lease.acquire(_worker_owner("project", "TASK-1"))
    held.attach_process(types.SimpleNamespace(pid=os.getpid()), timeout_seconds=30)
    monkeypatch.setattr(
        validation_lease_module,
        "_legacy_provider_bootstrap_process",
        lambda _pid, _ticks, _trusted, _parent: True,
    )

    snapshot = lease.status().to_dict()

    assert snapshot["status"] == "action_required"
    assert snapshot["legacy_provider_bootstrap_owner_count"] == 1
    assert snapshot["owners"][0]["process_role"] == "legacy_provider_bootstrap"
    assert snapshot["owners"][0]["recovery_action"] == "claim_task_directly"
    assert snapshot["owners"][0]["recovery_preserves_worktree"] is True
    recovery = snapshot["owners"][0]["recovery_request"]
    assert recovery["method"] == "POST"
    assert recovery["endpoint"] == (
        "/api/v1/projects/project/tasks/TASK-1/owner-claim"
    )
    expected = recovery["body"]["expected_validation_owner"]
    assert expected["kind"] == "worker"
    assert expected["project_id"] == "project"
    assert expected["task_id"] == "TASK-1"
    assert expected["authority_generation"] == "worker-TASK-1"
    assert expected["requester_pid"] == os.getpid()
    assert expected["child_pid"] == os.getpid()
    held.release()


def test_exact_owner_cancellation_rejects_same_generation_aba_replacement(
    tmp_path,
):
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    owner = _worker_owner("project", "TASK-1")
    held = lease.acquire(owner)
    held.attach_process(types.SimpleNamespace(pid=os.getpid()), timeout_seconds=30)
    advertised = lease.status().owners[0]
    replacement_identity = {
        "requester_pid": int(advertised["requester_pid"]) + 101,
        "requester_start_ticks": int(advertised["requester_start_ticks"]) + 101,
        "child_pid": int(advertised["child_pid"]) + 101,
        "child_start_ticks": int(advertised["child_start_ticks"]) + 101,
    }
    with lease._connect() as connection:
        connection.execute(
            """UPDATE owners SET requester_pid = ?, requester_start_ticks = ?,
                      child_pid = ?, child_start_ticks = ?
               WHERE token = ?""",
            (*replacement_identity.values(), held.token),
        )

    cancelled = lease.cancel_exact_owner_process(
        owner,
        requester_pid=int(advertised["requester_pid"]),
        requester_start_ticks=int(advertised["requester_start_ticks"]),
        child_pid=int(advertised["child_pid"]),
        child_start_ticks=int(advertised["child_start_ticks"]),
    )

    assert cancelled is False
    with lease._connect() as connection:
        current = connection.execute(
            "SELECT requester_pid, child_pid FROM owners WHERE token = ?",
            (held.token,),
        ).fetchone()
        tombstones = connection.execute(
            "SELECT COUNT(*) FROM cancelled_owners"
        ).fetchone()[0]
    assert dict(current) == {
        "requester_pid": replacement_identity["requester_pid"],
        "child_pid": replacement_identity["child_pid"],
    }
    assert tombstones == 0
    held.release()


def test_legacy_auditor_owner_does_not_advertise_direct_claim_recovery(
    tmp_path,
    monkeypatch,
):
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    held = lease.acquire(_audit_owner("project", "TASK-1"))
    held.attach_process(types.SimpleNamespace(pid=os.getpid()), timeout_seconds=30)
    monkeypatch.setattr(
        validation_lease_module,
        "_legacy_provider_bootstrap_process",
        lambda _pid, _ticks, _trusted, _parent: True,
    )

    owner = lease.status().to_dict()["owners"][0]

    assert owner["process_role"] == "legacy_provider_bootstrap"
    assert "recovery_action" not in owner
    assert "recovery_request" not in owner
    held.release()


@pytest.mark.parametrize(
    (
        "arguments",
        "environment",
        "prefix",
        "entrypoint_matches_operator",
        "interpreter_matches_operator",
        "parent_matches_operator",
        "bootstrap_is_task_writable",
        "expected",
    ),
    [
        (
            ("node", "/operator/codex", "exec", "--experimental-json"),
            {"CODEX_INTERNAL_ORIGINATOR_OVERRIDE": "codex_sdk_ts"},
            b"#!/usr/bin/env node\n",
            True,
            True,
            True,
            False,
            True,
        ),
        (
            ("node", "/workspace/test.js", "exec", "--experimental-json"),
            {"CODEX_INTERNAL_ORIGINATOR_OVERRIDE": "codex_sdk_ts"},
            b"#!/usr/bin/env node\n",
            False,
            True,
            True,
            True,
            False,
        ),
        (
            ("node", "/operator/codex", "exec", "--version"),
            {"CODEX_INTERNAL_ORIGINATOR_OVERRIDE": "codex_sdk_ts"},
            b"#!/usr/bin/env node\n",
            True,
            True,
            True,
            False,
            False,
        ),
        (
            ("node", "/workspace/codex", "exec", "--experimental-json"),
            {"CODEX_INTERNAL_ORIGINATOR_OVERRIDE": "codex_sdk_ts"},
            b"#!/usr/bin/env node\n",
            True,
            True,
            True,
            True,
            False,
        ),
        (
            ("node", "/operator/codex", "exec", "--experimental-json"),
            {"CODEX_INTERNAL_ORIGINATOR_OVERRIDE": "codex_sdk_ts"},
            b"#!/usr/bin/env node\n",
            True,
            True,
            False,
            False,
            False,
        ),
    ],
)
def test_legacy_provider_root_detection_is_specific(
    arguments,
    environment,
    prefix,
    entrypoint_matches_operator,
    interpreter_matches_operator,
    parent_matches_operator,
    bootstrap_is_task_writable,
    expected,
):
    assert (
        validation_lease_module._is_legacy_provider_bootstrap_snapshot(
            arguments,
            environment,
            prefix,
            entrypoint_matches_operator=entrypoint_matches_operator,
            interpreter_matches_operator=interpreter_matches_operator,
            parent_matches_operator=parent_matches_operator,
            bootstrap_is_task_writable=bootstrap_is_task_writable,
        )
        is expected
    )


def test_same_project_cannot_monopolize_equal_priority_queue(tmp_path):
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    held = lease.acquire(_gate_owner("blocker", "held"))
    order: list[str] = []

    def run(project: str, task: str) -> None:
        with lease.acquire(_gate_owner(project, task)):
            order.append(task)
            time.sleep(0.02)

    threads = [
        threading.Thread(target=run, args=("p1", "p1-first")),
        threading.Thread(target=run, args=("p1", "p1-second")),
        threading.Thread(target=run, args=("p2", "p2-first")),
    ]
    for thread in threads:
        thread.start()
        _wait_for(lambda: lease.status().waiter_count == threads.index(thread) + 1)
    held.release()
    for thread in threads:
        thread.join(timeout=3)

    assert order == ["p1-first", "p2-first", "p1-second"]


def test_queue_prioritizes_exact_gate_then_auditor_then_worker(tmp_path):
    lease = ValidationResourceLease(
        tmp_path / "lease.sqlite3",
        aging_seconds=60,
        poll_seconds=0.01,
    )
    held = lease.acquire(_gate_owner("blocker", "held"))
    order: list[str] = []

    def run(owner: ValidationLeaseOwner, label: str) -> None:
        with lease.acquire(owner):
            order.append(label)

    requests = [
        (_worker_owner("worker-project", "worker"), "worker"),
        (_audit_owner("audit-project", "audit"), "audit"),
        (_gate_owner("gate-project", "gate"), "gate"),
    ]
    threads: list[threading.Thread] = []
    for owner, label in requests:
        thread = threading.Thread(target=run, args=(owner, label))
        threads.append(thread)
        thread.start()
        _wait_for(lambda: lease.status().waiter_count == len(threads))

    held.release()
    for thread in threads:
        thread.join(timeout=3)

    assert order == ["gate", "audit", "worker"]


def test_exact_gate_has_priority_but_aging_prevents_auditor_starvation(tmp_path):
    lease = ValidationResourceLease(
        tmp_path / "lease.sqlite3",
        aging_seconds=0.01,
        poll_seconds=0.005,
    )
    held = lease.acquire(_gate_owner("blocker", "held"))
    order: list[str] = []

    def run(owner: ValidationLeaseOwner, label: str) -> None:
        with lease.acquire(owner):
            order.append(label)

    auditor = threading.Thread(target=run, args=(_audit_owner("p1", "audit"), "audit"))
    auditor.start()
    _wait_for(lambda: lease.status().waiter_count == 1)
    # Ten aging intervals erase the exact gate's initial ten-point advantage.
    time.sleep(0.12)
    exact = threading.Thread(target=run, args=(_gate_owner("p2", "gate"), "gate"))
    exact.start()
    _wait_for(lambda: lease.status().waiter_count == 2)
    held.release()
    auditor.join(timeout=3)
    exact.join(timeout=3)

    assert order == ["audit", "gate"]


def test_wait_cancellation_removes_durable_waiter(tmp_path):
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    held = lease.acquire(_gate_owner("p1", "held"))
    cancelled = threading.Event()
    errors: list[BaseException] = []

    def wait() -> None:
        try:
            lease.acquire(_audit_owner("p1", "audit"), is_cancelled=cancelled.is_set)
        except BaseException as exc:  # test captures the worker exception
            errors.append(exc)

    thread = threading.Thread(target=wait)
    thread.start()
    _wait_for(lambda: lease.status().waiter_count == 1)
    cancelled.set()
    thread.join(timeout=3)

    assert len(errors) == 1
    assert isinstance(errors[0], ValidationLeaseCancelled)
    assert lease.status().waiter_count == 0
    held.release()


def test_requester_crash_is_recovered_without_manual_state_edit(tmp_path):
    state_path = tmp_path / "lease.sqlite3"
    script = """
import os, sys
from oompah.validation_resource_lease import ValidationLeaseOwner, ValidationResourceLease
lease = ValidationResourceLease(sys.argv[1], poll_seconds=0.01)
lease.acquire(ValidationLeaseOwner.exact_gate(project_id='p', task_id='dead', authority_generation='g'))
os._exit(0)
"""
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).parents[1])}
    subprocess.run(
        [sys.executable, "-c", script, str(state_path)],
        cwd=Path(__file__).parents[1],
        env=env,
        check=True,
        timeout=5,
    )

    restarted = ValidationResourceLease(state_path, poll_seconds=0.01)
    with restarted.acquire(
        _gate_owner("p", "replacement"),
        wait_timeout_seconds=1,
    ):
        assert restarted.status().owner_count == 1


def test_restart_observes_child_that_inherited_kernel_fence(tmp_path):
    state_path = tmp_path / "lease.sqlite3"
    script = """
import os, subprocess, sys
from oompah.validation_resource_lease import ValidationLeaseOwner, ValidationResourceLease
lease = ValidationResourceLease(sys.argv[1], poll_seconds=0.01)
handle = lease.acquire(ValidationLeaseOwner.exact_gate(project_id='p', task_id='old', authority_generation='g'))
child = subprocess.Popen(['sleep', '0.5'], pass_fds=handle.pass_fds, start_new_session=True)
handle.attach_process(child, timeout_seconds=5)
os._exit(0)
"""
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).parents[1])}
    subprocess.run(
        [sys.executable, "-c", script, str(state_path)],
        cwd=Path(__file__).parents[1],
        env=env,
        check=True,
        timeout=5,
    )
    restarted = ValidationResourceLease(state_path, poll_seconds=0.01)

    assert restarted.status().owner_count == 1
    with pytest.raises(ValidationLeaseCancelled, match="timed out"):
        restarted.acquire(
            _gate_owner("p", "new"),
            wait_timeout_seconds=0.1,
        )
    time.sleep(0.5)
    with restarted.acquire(
        _gate_owner("p", "new"),
        wait_timeout_seconds=1,
    ):
        assert restarted.status().owner_count == 1


def test_corrupt_database_is_quarantined_before_fresh_initialization(tmp_path):
    state_path = tmp_path / "lease.sqlite3"
    state_path.write_bytes(b"not a sqlite database")

    lease = ValidationResourceLease(state_path, poll_seconds=0.01)

    quarantined = list(tmp_path.glob("lease.sqlite3.corrupt-*"))
    assert len(quarantined) == 1
    assert quarantined[0].read_bytes() == b"not a sqlite database"
    with lease.acquire(_gate_owner("p", "after-corruption")):
        assert lease.status().owner_count == 1


def test_capacity_greater_than_one_allows_exact_number_of_owners(tmp_path):
    lease = ValidationResourceLease(
        tmp_path / "lease.sqlite3",
        capacity=2,
        poll_seconds=0.01,
    )
    first = lease.acquire(_gate_owner("p1", "one"))
    second = lease.acquire(_gate_owner("p2", "two"))
    acquired = threading.Event()

    def take_third() -> None:
        with lease.acquire(_gate_owner("p3", "three")):
            acquired.set()

    waiter = threading.Thread(target=take_third)
    waiter.start()
    _wait_for(lambda: lease.status().waiter_count == 1)
    assert lease.status().owner_count == 2
    assert acquired.is_set() is False
    first.release()
    waiter.join(timeout=3)
    assert waiter.is_alive() is False
    assert acquired.is_set() is True
    second.release()


def test_expired_attached_process_group_is_terminated(tmp_path):
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    handle = lease.acquire(_gate_owner("p", "expiring"))
    child = subprocess.Popen(
        ["sleep", "30"],
        pass_fds=handle.pass_fds,
        start_new_session=True,
    )
    handle.attach_process(child, timeout_seconds=0.05)

    _wait_for(
        lambda: (
            lease.status().owner_count >= 0
            and child.poll() is not None
        ),
        timeout=3,
    )

    assert child.returncode is not None
    handle.release()


def test_simultaneous_multiprocess_acquisition_has_no_lost_owner_update(tmp_path):
    state_path = tmp_path / "lease.sqlite3"
    script = """
import sys, time
from oompah.validation_resource_lease import ValidationLeaseOwner, ValidationResourceLease
lease = ValidationResourceLease(sys.argv[1], poll_seconds=0.005)
owner = ValidationLeaseOwner.worker(project_id='p', task_id=sys.argv[2], authority_generation=sys.argv[2])
with lease.acquire(owner, wait_timeout_seconds=5):
    started = time.time()
    time.sleep(0.08)
    ended = time.time()
print(f'{started},{ended}', flush=True)
"""
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).parents[1])}
    processes = [
        subprocess.Popen(
            [sys.executable, "-c", script, str(state_path), f"worker-{index}"],
            cwd=Path(__file__).parents[1],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for index in range(4)
    ]
    intervals: list[tuple[float, float]] = []
    for process in processes:
        stdout, stderr = process.communicate(timeout=10)
        assert process.returncode == 0, stderr
        start, end = stdout.strip().split(",")
        intervals.append((float(start), float(end)))

    ordered = sorted(intervals)
    assert all(
        current[1] <= following[0]
        for current, following in zip(ordered, ordered[1:])
    )
    assert ValidationResourceLease(state_path).status().owner_count == 0


def test_restart_observes_waiter_and_allows_it_to_continue(tmp_path):
    state_path = tmp_path / "lease.sqlite3"
    held = ValidationResourceLease(state_path, poll_seconds=0.01).acquire(
        _gate_owner("p1", "held")
    )
    script = """
import sys
from oompah.validation_resource_lease import ValidationLeaseOwner, ValidationResourceLease
lease = ValidationResourceLease(sys.argv[1], poll_seconds=0.01)
owner = ValidationLeaseOwner.worker(project_id='p2', task_id='waiting', authority_generation='waiting')
with lease.acquire(owner, wait_timeout_seconds=5):
    print('acquired', flush=True)
"""
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).parents[1])}
    waiter = subprocess.Popen(
        [sys.executable, "-c", script, str(state_path)],
        cwd=Path(__file__).parents[1],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    _wait_for(lambda: ValidationResourceLease(state_path).status().waiter_count == 1)

    restarted = ValidationResourceLease(state_path, poll_seconds=0.01)
    assert restarted.status().owner_count == 1
    assert restarted.status().waiter_count == 1
    held.release()
    stdout, stderr = waiter.communicate(timeout=5)
    assert waiter.returncode == 0, stderr
    assert stdout.strip() == "acquired"


def test_successful_heavy_command_reports_auditor_evidence(tmp_path):
    (tmp_path / "Makefile").write_text(
        "test:\n\t@true\nfail:\n\t@false\n",
        encoding="utf-8",
    )
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    observed: list[tuple[str, Path]] = []

    success = _exec_run_command(
        tmp_path,
        {"command": "make test"},
        timeout=5,
        validation_lease=lease,
        validation_owner=_audit_owner("p", "audit"),
        successful_validation_handler=lambda command, workspace: observed.append(
            (command, workspace)
        ),
    )
    failure = _exec_run_command(
        tmp_path,
        {"command": "make fail"},
        timeout=5,
        validation_lease=lease,
        validation_owner=_audit_owner("p", "audit"),
        successful_validation_handler=lambda command, workspace: observed.append(
            (command, workspace)
        ),
    )

    assert "exit_code: 0" in success
    assert "exit_code: 2" in failure
    assert observed == [("make test", tmp_path)]
