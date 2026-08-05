"""Focused coverage for the shared heavyweight-validation lane."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
import types
from pathlib import Path

import pytest

from oompah.api_agent import _exec_run_command
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
        ("echo ready; make test", True),
        ("make test && git status --short", True),
        ("pytest", True),
        ("uv run pytest -q", True),
        ("uv run --python 3.12 pytest -q", True),
        ("PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q", True),
        ("timeout 10s python -m pytest tests/", True),
        ("bash -lc 'python -m pytest tests/'", True),
        ("python -m pytest tests/", True),
        (
            "python -m pytest -q tests/test_acp_backends.py tests/test_providers.py "
            "tests/test_providers_ui.py tests/test_acp_agent.py "
            "tests/test_orchestrator_handlers.py",
            True,
        ),
        ("tox -q", True),
        ("pytest tests/test_one.py", False),
        ("pytest tests/test_one.py tests/test_two.py", True),
        ("pytest tests/test_one.py::test_case", False),
        ("pytest -k exact_case", True),
        ("pytest tests/test_one.py -k exact_case", False),
        ("pytest --collect-only", False),
        ("rg pytest tests", False),
        ("echo make test", False),
        ("git status --short", False),
    ],
)
def test_classifier_is_heavy_first_and_focused_checks_bypass(command, expected):
    assert is_heavyweight_validation_command(command) is expected


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
    assert monitor.snapshot() is None
    gate.release()
    worker.join(timeout=3)

    assert not worker.is_alive()
    assert marker.exists()
    assert result and "exit_code: 0" in result[0]
    assert lease.status().owner_count == 0


def test_five_file_worker_pytest_queues_behind_gate_at_worker_priority(
    tmp_path,
    monkeypatch,
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
    command = (
        "python -m pytest -q tests/test_acp_backends.py tests/test_providers.py "
        "tests/test_providers_ui.py tests/test_acp_agent.py "
        "tests/test_orchestrator_handlers.py"
    )
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
