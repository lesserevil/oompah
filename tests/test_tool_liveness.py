"""Regression tests for bounded ACP tool liveness supervision."""

from __future__ import annotations

import asyncio
import threading
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

from oompah.config import ServiceConfig
from oompah.models import Issue, LiveSession, RunningEntry
from oompah.api_agent import _exec_run_command
from oompah.orchestrator import Orchestrator
from oompah.tool_liveness import ToolLivenessMonitor
from oompah.validation_resource_lease import ValidationLeaseOwner


class _LiveProcess:
    def __init__(self, returncode=None):
        self.returncode = returncode

    def poll(self):
        return self.returncode


def _running_entry(monitor=None) -> RunningEntry:
    issue = Issue(
        id="issue-1",
        identifier="OOMPAH-648-test",
        title="tool liveness",
        description="Test command liveness without relying on a five-minute wait.",
        state="In Progress",
        project_id="project",
    )
    session = LiveSession(
        session_id="acp-test",
        thread_id="acp",
        turn_id="1",
        last_event="acp_tool_use",
        # The event is deliberately older than the generic stall threshold.
        last_timestamp=datetime.now(timezone.utc) - timedelta(minutes=10),
        tool_liveness=monitor,
    )
    return RunningEntry(
        worker_task=MagicMock(),
        identifier=issue.identifier,
        issue=issue,
        session=session,
        retry_attempt=0,
        started_at=session.last_timestamp,
        authority_generation="native-session",
    )


def test_live_bounded_command_protects_silent_session_from_generic_stall():
    monitor = ToolLivenessMonitor()
    invocation_id = monitor.start(tool_name="run_command", timeout_s=720)
    monitor.attach_process(invocation_id, _LiveProcess())

    protected, reason = Orchestrator._tool_stall_status(_running_entry(monitor))

    assert protected is True
    assert reason is None


def test_capacity_wait_protects_stall_without_consuming_command_deadline():
    monitor = ToolLivenessMonitor()
    invocation_id = monitor.start_waiting(tool_name="run_command")

    protected, reason = Orchestrator._tool_stall_status(_running_entry(monitor))
    waiting = monitor.snapshot()

    assert protected is True
    assert reason is None
    assert waiting is not None
    assert waiting.phase == "waiting_for_capacity"
    assert waiting.deadline_exceeded is False

    monitor.start_runtime(invocation_id, timeout_s=0)
    monitor.attach_process(invocation_id, _LiveProcess())
    protected, reason = Orchestrator._tool_stall_status(_running_entry(monitor))

    assert protected is False
    assert reason == "run_command command timed out after 0s"


def test_exited_child_does_not_protect_silent_session():
    monitor = ToolLivenessMonitor()
    invocation_id = monitor.start(tool_name="run_command", timeout_s=720)
    monitor.attach_process(invocation_id, _LiveProcess(returncode=1))

    protected, reason = Orchestrator._tool_stall_status(_running_entry(monitor))

    assert protected is False
    assert reason is None


def test_session_cancellation_is_visible_to_queued_tool_work():
    monitor = ToolLivenessMonitor()

    assert monitor.is_cancelled() is False
    monitor.request_cancel()
    assert monitor.is_cancelled() is True


def test_command_deadline_has_precise_diagnostic_and_never_bypasses_recovery():
    monitor = ToolLivenessMonitor()
    invocation_id = monitor.start(tool_name="run_command", timeout_s=0)
    monitor.attach_process(invocation_id, _LiveProcess())

    protected, reason = Orchestrator._tool_stall_status(_running_entry(monitor))

    assert protected is False
    assert reason == "run_command command timed out after 0s"


def test_prompt_or_editor_silence_has_no_tool_liveness_exemption():
    entry = _running_entry()
    entry.session.last_event = "acp_text"

    protected, reason = Orchestrator._tool_stall_status(entry)

    assert protected is False
    assert reason is None


def test_completion_removes_command_from_supervision():
    monitor = ToolLivenessMonitor()
    invocation_id = monitor.start(tool_name="run_command", timeout_s=720)
    monitor.attach_process(invocation_id, _LiveProcess())
    before = monitor.snapshot()
    assert before is not None

    monitor.heartbeat(invocation_id)
    after = monitor.snapshot()
    assert after is not None
    assert after.last_heartbeat_monotonic >= before.last_heartbeat_monotonic

    monitor.complete(invocation_id)

    assert monitor.snapshot() is None


def test_exited_child_enters_result_pending_until_provider_acknowledges():
    monitor = ToolLivenessMonitor(result_delivery_timeout_s=30)
    invocation_id = monitor.start(
        tool_name="run_command",
        timeout_s=720,
        result_delivery_required=True,
    )
    monitor.attach_process(invocation_id, _LiveProcess(returncode=0))

    snapshot = monitor.snapshot()

    assert snapshot is not None
    assert snapshot.phase == "result_pending"
    assert snapshot.protects_from_stall is True
    assert monitor.result_delivered() == invocation_id
    assert monitor.snapshot() is None
    assert monitor.metrics() == {
        "running": 0,
        "result_pending": 0,
        "result_delivered": 1,
        "provider_stalled": 0,
    }


def test_child_exit_concurrent_with_stall_scan_has_one_delivery_owner():
    """Child exit and reconciliation may race without duplicating delivery."""

    monitor = ToolLivenessMonitor(result_delivery_timeout_s=30)
    invocation_id = monitor.start(
        tool_name="run_command",
        timeout_s=720,
        result_delivery_required=True,
    )
    monitor.attach_process(invocation_id, _LiveProcess(returncode=0))
    start = threading.Barrier(3)
    snapshots: list = []
    pending_ids: list[str | None] = []

    def scan() -> None:
        start.wait()
        for _ in range(100):
            snapshots.extend(monitor.snapshots())

    def bridge() -> None:
        start.wait()
        for _ in range(100):
            pending_ids.append(monitor.result_pending(invocation_id))

    threads = [threading.Thread(target=scan), threading.Thread(target=bridge)]
    for thread in threads:
        thread.start()
    start.wait()
    for thread in threads:
        thread.join(timeout=2)
        assert not thread.is_alive()

    assert any(snapshot.phase == "result_pending" for snapshot in snapshots)
    assert any(value == invocation_id for value in pending_ids)

    acknowledgements = [monitor.result_delivered() for _ in range(8)]
    assert [value for value in acknowledgements if value is not None] == [
        invocation_id
    ]
    assert monitor.snapshot() is None
    assert monitor.metrics()["result_delivered"] == 1


def test_result_delivery_deadline_is_precise_and_recoverable():
    monitor = ToolLivenessMonitor(result_delivery_timeout_s=0)
    invocation_id = monitor.start(
        tool_name="run_command",
        timeout_s=720,
        result_delivery_required=True,
    )
    monitor.attach_process(invocation_id, _LiveProcess(returncode=0))
    entry = _running_entry(monitor)

    protected, reason = Orchestrator._tool_stall_status(entry)

    assert protected is False
    assert reason == "run_command result delivery timed out after 0s"
    assert monitor.snapshot() is not None
    assert monitor.snapshot().phase == "provider_stalled"


def test_public_state_exposes_pending_liveness_without_provider_details():
    monitor = ToolLivenessMonitor()
    invocation_id = monitor.start(
        tool_name="run_command",
        timeout_s=720,
        result_delivery_required=True,
    )
    monitor.attach_process(invocation_id, _LiveProcess(returncode=0))
    entry = _running_entry(monitor)

    state = Orchestrator._tool_liveness_state(entry)

    assert state["phase"] == "result_pending"
    assert state["metrics"]["result_pending"] == 1
    assert "provider-private" not in repr(state)


def test_command_result_stays_owned_until_bounded_api_bridge_ack(tmp_path):
    monitor = ToolLivenessMonitor(result_delivery_timeout_s=30)
    result = _exec_run_command(
        tmp_path,
        {
            "command": (
                "sleep 0.05; python -c \"print('x' * 1500000)\"; "
                "exit 0"
            )
        },
        timeout=2,
        tool_liveness=monitor,
        result_delivery_required=True,
    )

    assert len(result) < 65_000
    pending = monitor.snapshot()
    assert pending is not None
    assert pending.phase == "result_pending"
    assert monitor.result_delivered() is not None
    assert monitor.snapshot() is None


def test_failing_command_uses_the_same_exactly_once_delivery_path(tmp_path):
    monitor = ToolLivenessMonitor()
    result = _exec_run_command(
        tmp_path,
        {"command": "echo failure >&2; exit 7"},
        timeout=2,
        tool_liveness=monitor,
        result_delivery_required=True,
    )

    assert "exit_code: 7" in result
    assert monitor.snapshot() is not None
    assert monitor.result_delivered() is not None
    assert monitor.result_delivered() is None
    assert monitor.metrics()["result_delivered"] == 1


def test_concurrent_commands_are_isolated_and_deadline_wins():
    monitor = ToolLivenessMonitor()
    live_id = monitor.start(tool_name="run_command", timeout_s=720)
    expired_id = monitor.start(tool_name="run_command", timeout_s=0)
    monitor.attach_process(live_id, _LiveProcess())
    monitor.attach_process(expired_id, _LiveProcess())

    snapshots = monitor.snapshots()

    assert len(snapshots) == 2
    assert monitor.snapshot().invocation_id == expired_id


def _orchestrator(tmp_path, *, stall_timeout_ms=300_000) -> Orchestrator:
    project_store = MagicMock()
    project_store.list_all.return_value = []
    return Orchestrator(
        config=ServiceConfig(
            stall_timeout_ms=stall_timeout_ms,
            duplicate_preflight_max_agents=0,
        ),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        state_path=str(tmp_path / "state.json"),
    )


def test_reconcile_keeps_live_silent_command_running_past_stall_threshold(tmp_path):
    monitor = ToolLivenessMonitor()
    invocation_id = monitor.start(tool_name="run_command", timeout_s=720)
    monitor.attach_process(invocation_id, _LiveProcess())
    orch = _orchestrator(tmp_path, stall_timeout_ms=1)
    entry = _running_entry(monitor)
    orch.state.running[entry.issue.id] = entry
    orch._fetch_running_states = MagicMock(return_value={})
    orch._terminate_running = AsyncMock()

    asyncio.run(orch._reconcile())

    orch._terminate_running.assert_not_awaited()


def test_reconcile_keeps_native_session_queued_for_validation_capacity(tmp_path):
    orch = _orchestrator(tmp_path, stall_timeout_ms=1)
    entry = _running_entry()
    orch.state.running[entry.issue.id] = entry
    orch._fetch_running_states = MagicMock(return_value={})
    orch._terminate_running = AsyncMock()
    held = orch.validation_resource_lease.acquire(
        ValidationLeaseOwner.exact_gate(
            project_id="other-project",
            task_id="GATE-1",
            authority_generation="gate-generation",
        )
    )
    completed = threading.Event()

    def wait_for_capacity() -> None:
        with orch.validation_resource_lease.acquire(
            ValidationLeaseOwner.worker(
                project_id="project",
                task_id=entry.identifier,
                authority_generation="native-session",
            )
        ):
            completed.set()

    waiter = threading.Thread(target=wait_for_capacity)
    waiter.start()
    deadline = time.monotonic() + 3
    while (
        time.monotonic() < deadline
        and orch.validation_resource_lease.status().waiter_count != 1
    ):
        time.sleep(0.01)

    asyncio.run(orch._reconcile())

    orch._terminate_running.assert_not_awaited()
    held.release()
    waiter.join(timeout=3)
    assert completed.is_set() is True


def test_stale_native_generation_does_not_protect_replacement_worker(tmp_path):
    orch = _orchestrator(tmp_path, stall_timeout_ms=1)
    entry = _running_entry()
    entry.authority_generation = "replacement-generation"
    stale = orch.validation_resource_lease.acquire(
        ValidationLeaseOwner.worker(
            project_id="project",
            task_id=entry.identifier,
            authority_generation="old-generation",
        )
    )
    try:
        assert orch._validation_capacity_protects_stall(entry) is False
    finally:
        stale.release()


def test_auditor_capacity_liveness_matches_audit_attempt_generation(tmp_path):
    orch = _orchestrator(tmp_path, stall_timeout_ms=1)
    entry = _running_entry()
    entry.is_auditor = True
    entry.audit_attempt_id = "audit-attempt"
    entry.authority_generation = "worker-generation"
    handle = orch.validation_resource_lease.acquire(
        ValidationLeaseOwner.auditor(
            project_id="project",
            task_id=entry.identifier,
            authority_generation="audit-attempt",
        )
    )
    try:
        assert orch._validation_capacity_protects_stall(entry) is True
    finally:
        handle.release()


def test_reconcile_recovers_exited_silent_child(tmp_path):
    monitor = ToolLivenessMonitor()
    invocation_id = monitor.start(tool_name="run_command", timeout_s=720)
    monitor.attach_process(invocation_id, _LiveProcess(returncode=1))
    orch = _orchestrator(tmp_path, stall_timeout_ms=1)
    entry = _running_entry(monitor)
    orch.state.running[entry.issue.id] = entry
    orch._fetch_running_states = MagicMock(return_value={})
    orch._terminate_running = AsyncMock(return_value=False)

    asyncio.run(orch._reconcile())

    orch._terminate_running.assert_awaited_once_with(
        entry.issue.id,
        cleanup_workspace=False,
    )


def test_reconcile_uses_command_timeout_even_when_generic_stall_disabled(tmp_path):
    monitor = ToolLivenessMonitor()
    invocation_id = monitor.start(tool_name="run_command", timeout_s=0)
    monitor.attach_process(invocation_id, _LiveProcess())
    orch = _orchestrator(tmp_path, stall_timeout_ms=0)
    entry = _running_entry(monitor)
    orch.state.running[entry.issue.id] = entry
    orch._fetch_running_states = MagicMock(return_value={})
    orch._terminate_running = AsyncMock(return_value=False)

    asyncio.run(orch._reconcile())

    orch._terminate_running.assert_awaited_once_with(
        entry.issue.id,
        cleanup_workspace=False,
    )


def test_command_executor_reports_live_child_and_clears_it_on_completion(tmp_path):
    monitor = ToolLivenessMonitor()
    result: list[str] = []
    worker = threading.Thread(
        target=lambda: result.append(
            _exec_run_command(
                tmp_path,
                {"command": "sleep 0.25"},
                timeout=2,
                tool_liveness=monitor,
            )
        )
    )
    worker.start()
    deadline = time.monotonic() + 2
    snapshot = None
    while time.monotonic() < deadline:
        snapshot = monitor.snapshot()
        if snapshot is not None and snapshot.process_alive:
            break
        time.sleep(0.01)

    assert snapshot is not None
    assert snapshot.process_alive is True
    worker.join(timeout=2)
    assert result and "exit_code: 0" in result[0]
    assert monitor.snapshot() is None


def test_command_executor_returns_command_specific_timeout(tmp_path):
    monitor = ToolLivenessMonitor()

    result = _exec_run_command(
        tmp_path,
        {"command": "sleep 1"},
        timeout=0.05,
        tool_liveness=monitor,
    )

    assert result == "Error: command timed out after 0.05s"
    assert monitor.snapshot() is None


# ---------------------------------------------------------------------------
# Interactive git command rejection tests (OOMPAH-681)
# ---------------------------------------------------------------------------


def test_interactive_rebase_rejected_before_execution(tmp_path):
    """``git rebase -i`` should be rejected before subprocess execution."""
    result = _exec_run_command(
        tmp_path,
        {"command": "git rebase -i main"},
        timeout=2,
    )

    assert "Error: git rebase -i" in result
    assert "GIT_SEQUENCE_EDITOR" in result


def test_git_add_patch_rejected_before_execution(tmp_path):
    """``git add -p`` should be rejected before subprocess execution."""
    result = _exec_run_command(
        tmp_path,
        {"command": "git add -p"},
        timeout=2,
    )

    assert "Error: git add -p" in result


def test_git_commit_without_message_rejected_before_execution(tmp_path):
    """``git commit`` without -m should be rejected before subprocess execution."""
    result = _exec_run_command(
        tmp_path,
        {"command": "git commit"},
        timeout=2,
    )

    assert "Error: git commit without -m/-F" in result


def test_git_commit_with_message_allowed(tmp_path):
    """``git commit -m "msg"`` is allowed but may fail due to git not being set up."""
    # This will likely fail because git isn't configured, but it should pass
    # the validation and attempt execution.
    result = _exec_run_command(
        tmp_path,
        {"command": "git commit -m 'test message' 2>&1 || true"},
        timeout=2,
    )

    # Should not be rejected by the validation layer
    assert "Error: git commit without -m/-F" not in result


def test_non_git_commands_pass_validation(tmp_path):
    """Non-git commands should pass the validation layer."""
    result = _exec_run_command(
        tmp_path,
        {"command": "echo 'hello world'"},
        timeout=2,
    )

    assert "Error: git" not in result
    assert "hello world" in result


def test_git_merge_without_no_edit_rejected(tmp_path):
    """``git merge`` without --no-edit should be rejected."""
    result = _exec_run_command(
        tmp_path,
        {"command": "git merge main"},
        timeout=2,
    )

    assert "Error: git merge" in result or "Error:" in result
