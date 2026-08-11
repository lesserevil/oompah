"""Deterministic lifecycle/admission races for completion auditors."""

from __future__ import annotations

import asyncio
import copy
import threading
from concurrent.futures import Future as ConcurrentFuture
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from oompah import server as server_module
from oompah.acp_agent import AcpAgentSession
from oompah.agent import AgentSession
from oompah.api_agent import ApiAgentSession
from oompah.auditor_dispatch import AuditDispatchPlan, AuditorDispatchLane
from oompah.config import ServiceConfig
from oompah.models import AgentProfile, Issue, ModelProvider, RunningEntry
from oompah.orchestrator import (
    DispatchTarget,
    Orchestrator,
    UnadmittedAuditRollbackOutcome,
    _AuditCandidateScan,
)
from oompah.roles import Candidate
from oompah.statuses import IN_VALIDATION
from oompah.terminal_audit import (
    ContributorIdentity,
    EvidenceFingerprint,
    OverrideRecord,
    RequestState,
    TargetState,
    TerminalAuditRecord,
    Verdict,
)
from oompah.terminal_audit_metadata import (
    TerminalAuditMetadata,
    TerminalAuditMetadataStore,
)


class _MemoryAuditStore:
    """Apply real metadata updaters while keeping the race test in memory."""

    def __init__(self, document: TerminalAuditMetadata) -> None:
        self.document = document

    def read(self, _identifier: str) -> TerminalAuditMetadata:
        return self.document

    def update(self, _identifier: str, updater):
        self.document = updater(self.document)
        return self.document


class _TransientFailureAuditStore(_MemoryAuditStore):
    def __init__(self, document: TerminalAuditMetadata) -> None:
        super().__init__(document)
        self.fail_updates = 1

    def update(self, identifier: str, updater):
        if self.fail_updates:
            self.fail_updates -= 1
            raise OSError("transient metadata outage")
        return super().update(identifier, updater)


class _DurableAuditTracker:
    """Shared tracker metadata that survives orchestrator replacement."""

    def __init__(self, issues: list[Issue]) -> None:
        self._lock = threading.Lock()
        self._issues = {issue.identifier: issue for issue in issues}
        self._metadata: dict[str, dict] = {}
        self.comments: list[tuple[str, str]] = []

    def get_metadata(self, identifier: str) -> dict:
        with self._lock:
            return copy.deepcopy(self._metadata.get(identifier, {}))

    def set_metadata_field(self, identifier: str, key: str, value) -> None:
        with self._lock:
            self._metadata.setdefault(identifier, {})[key] = copy.deepcopy(value)

    def fetch_issues_by_states(self, states: list[str]) -> list[Issue]:
        wanted = {state.strip().casefold() for state in states}
        with self._lock:
            return [
                replace(issue)
                for issue in self._issues.values()
                if issue.state.strip().casefold() in wanted
            ]

    def fetch_issue_states_by_ids(self, issue_ids: list[str]) -> list[Issue]:
        wanted = set(issue_ids)
        with self._lock:
            return [
                replace(issue)
                for issue in self._issues.values()
                if issue.id in wanted
            ]

    def fetch_comments(self, _identifier: str) -> list:
        return []

    def add_comment(self, identifier: str, text: str, **_kwargs) -> dict:
        with self._lock:
            self.comments.append((identifier, text))
            return {"id": str(len(self.comments)), "text": text}


class _DispatchAdmissionBarrier:
    """Pause one dispatch exactly as it enters the final admission lock."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._dispatch_enters = 0
        self.reached = threading.Event()
        self.release_gate = threading.Event()

    def __enter__(self):
        self.acquire()
        return self

    def acquire(self, blocking: bool = True) -> bool:
        if threading.current_thread().name == "audit-dispatch":
            self._dispatch_enters += 1
            # First acquisition is the early blocked-state read.  The second
            # is the final worker-task/RunningEntry admission transaction.
            if self._dispatch_enters == 2:
                self.reached.set()
                if not self.release_gate.wait(timeout=3):
                    raise AssertionError("final admission barrier was not released")
        return self._lock.acquire(blocking=blocking)

    def release(self) -> None:
        self._lock.release()

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        self.release()


class _EagerFirstTurnTask:
    """Minimal scheduler double that advances a coroutine inside create_task."""

    def __init__(self, coroutine) -> None:
        self.coroutine = coroutine
        self.coroutine.send(None)
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True
        self.coroutine.close()

    def done(self) -> bool:
        return False


def _orchestrator(tmp_path) -> Orchestrator:
    project_store = MagicMock()
    project_store.list_all.return_value = []
    project_store.get.return_value = SimpleNamespace(paused=False)
    return Orchestrator(
        config=ServiceConfig(duplicate_preflight_max_agents=0),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        state_path=str(tmp_path / "state.json"),
    )


def _issue() -> Issue:
    return Issue(
        id="issue-1",
        identifier="OOMPAH-854",
        title="Fence auditor admission",
        description="Exercise the lifecycle/provider admission boundary.",
        state=IN_VALIDATION,
        project_id="project-1",
        branch_name="epic-branch",
    )


def _plan() -> AuditDispatchPlan:
    return AuditDispatchPlan(
        audit_id="audit-1",
        project_id="project-1",
        task_id="OOMPAH-854",
        attempt_id="attempt-1",
        target_state=TargetState.DONE,
        evidence_fingerprint=EvidenceFingerprint("a" * 64),
        candidate=Candidate(provider_id="provider-1", model="model-1"),
        rotation_count=0,
        branch_key="epic-branch",
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def _persisted_store(plan: AuditDispatchPlan) -> _MemoryAuditStore:
    record = TerminalAuditRecord(
        audit_id=plan.audit_id,
        project_id="project-1",
        task_id="OOMPAH-854",
        request_state=RequestState.PENDING,
        target_state=plan.target_state,
        evidence_fingerprint=plan.evidence_fingerprint,
        attempts=[],
        created_at=plan.created_at,
    )
    persisted = AuditorDispatchLane.persist_plan(record, plan)
    return _MemoryAuditStore(
        TerminalAuditMetadata(
            pending_chain=[persisted],
            attempt_history=[persisted.attempts[-1]],
        )
    )


def _tracker(issue: Issue) -> MagicMock:
    tracker = MagicMock()
    tracker.fetch_issue_states_by_ids.return_value = [issue]
    return tracker


def _record_queued_metric(orch: Orchestrator, plan: AuditDispatchPlan) -> None:
    orch._terminal_audit_metrics.record_queued(
        "project-1",
        "OOMPAH-854",
        plan.audit_id,
        attempts=0,
    )


def _run_dispatch_in_thread(
    orch: Orchestrator,
    issue: Issue,
    plan: AuditDispatchPlan,
) -> tuple[threading.Thread, list[bool]]:
    result: list[bool] = []

    def _run() -> None:
        result.append(asyncio.run(orch._dispatch(issue, 0, auditor_plan=plan)))

    thread = threading.Thread(target=_run, name="audit-dispatch")
    thread.start()
    return thread, result


def test_quiesce_wins_at_final_admission_and_restores_exact_attempt(tmp_path) -> None:
    """A fence installed at the real boundary prevents task/provider admission."""

    orch = _orchestrator(tmp_path)
    issue = _issue()
    plan = _plan()
    store = _persisted_store(plan)
    barrier = _DispatchAdmissionBarrier()
    orch._provider_admission_lock = barrier
    orch._audit_branch_claims[plan.branch_key] = plan.attempt_id
    _record_queued_metric(orch, plan)

    with (
        patch.object(orch, "_tracker_for_issue", return_value=_tracker(issue)),
        patch.object(orch, "_audit_store", return_value=store),
        patch.object(orch, "_run_worker", new_callable=AsyncMock) as worker,
    ):
        thread, result = _run_dispatch_in_thread(orch, issue, plan)
        assert barrier.reached.wait(timeout=3)
        orch.quiesce()
        barrier.release_gate.set()
        thread.join(timeout=3)

    assert not thread.is_alive()
    assert result == [False]
    worker.assert_not_awaited()
    assert issue.id not in orch.state.running
    assert issue.id not in orch.state.claimed
    assert plan.branch_key not in orch._audit_branch_claims
    record = store.document.pending_chain[0]
    assert record.request_state == RequestState.PENDING
    assert record.attempts == []
    assert store.document.attempt_history == []

    audit_metrics = orch.get_snapshot()["terminal_audit"]
    assert audit_metrics["queued"] == 1
    assert audit_metrics["running"] == 0


def test_owner_override_wins_registration_generation_barrier(tmp_path) -> None:
    """A pre-publication override rejects the gated auditor without an attempt."""

    orch = _orchestrator(tmp_path)
    issue = _issue()
    plan = _plan()
    store = _persisted_store(plan)
    orch._audit_branch_claims[plan.branch_key] = plan.attempt_id
    _record_queued_metric(orch, plan)
    reached_registration = threading.Event()
    release_registration = threading.Event()
    original_register = orch._register_running_entry

    def _register(issue_id: str, entry: RunningEntry) -> bool:
        reached_registration.set()
        assert release_registration.wait(timeout=3)
        return original_register(issue_id, entry)

    with (
        patch.object(orch, "_tracker_for_issue", return_value=_tracker(issue)),
        patch.object(orch, "_audit_store", return_value=store),
        patch.object(orch, "_register_running_entry", side_effect=_register),
        patch.object(orch, "_run_worker", new_callable=AsyncMock) as worker,
    ):
        dispatch_thread, result = _run_dispatch_in_thread(orch, issue, plan)
        assert reached_registration.wait(timeout=3)
        # No RunningEntry exists at this point, which was the old authority
        # gap.  The shared generation still advances and wins the final CAS.
        orch._revoke_auditor_authority(issue.project_id, issue.identifier)
        release_registration.set()
        dispatch_thread.join(timeout=3)

    assert not dispatch_thread.is_alive()
    assert result == [False]
    worker.assert_not_awaited()
    assert issue.id not in orch.state.running
    assert issue.id not in orch.state.claimed
    assert plan.branch_key not in orch._audit_branch_claims
    record = store.document.pending_chain[0]
    assert record.request_state == RequestState.PENDING
    assert record.attempts == []
    assert store.document.attempt_history == []


@pytest.mark.asyncio
async def test_worker_task_creation_failure_restores_exact_unadmitted_audit(
    tmp_path,
) -> None:
    """A failed final create_task cannot retain claims or consume retry budget."""

    orch = _orchestrator(tmp_path)
    issue = _issue()
    plan = _plan()
    store = _persisted_store(plan)
    orch._audit_branch_claims[plan.branch_key] = plan.attempt_id
    _record_queued_metric(orch, plan)

    with (
        patch.object(orch, "_tracker_for_issue", return_value=_tracker(issue)),
        patch.object(orch, "_audit_store", return_value=store),
        patch.object(orch, "_run_worker", new_callable=AsyncMock) as worker,
        patch(
            "oompah.orchestrator.asyncio.create_task",
            side_effect=RuntimeError("event loop rejected worker task"),
        ),
    ):
        admitted = await orch._dispatch(issue, 0, auditor_plan=plan)

    assert admitted is False
    worker.assert_not_awaited()
    assert issue.id not in orch.state.running
    assert issue.id not in orch.state.claimed
    assert plan.branch_key not in orch._audit_branch_claims
    record = store.document.pending_chain[0]
    assert record.request_state == RequestState.PENDING
    assert record.attempts == []
    assert store.document.attempt_history == []
    audit_metrics = orch.get_snapshot()["terminal_audit"]
    assert audit_metrics["queued"] == 1
    assert audit_metrics["running"] == 0


@pytest.mark.asyncio
async def test_worker_task_creation_cancelled_error_rolls_back_before_reraising(
    tmp_path,
) -> None:
    """BaseException cancellation follows the same exact admission rollback."""

    orch = _orchestrator(tmp_path)
    issue = _issue()
    plan = _plan()
    store = _persisted_store(plan)
    orch._audit_branch_claims[plan.branch_key] = plan.attempt_id

    with (
        patch.object(orch, "_tracker_for_issue", return_value=_tracker(issue)),
        patch.object(orch, "_audit_store", return_value=store),
        patch.object(orch, "_run_worker", new_callable=AsyncMock) as worker,
        patch(
            "oompah.orchestrator.asyncio.create_task",
            side_effect=asyncio.CancelledError(),
        ),
    ):
        with pytest.raises(asyncio.CancelledError):
            await orch._dispatch(issue, 0, auditor_plan=plan)

    worker.assert_not_awaited()
    assert issue.id not in orch.state.running
    assert issue.id not in orch.state.claimed
    assert plan.branch_key not in orch._audit_branch_claims
    assert store.document.pending_chain[0].request_state == RequestState.PENDING
    assert store.document.pending_chain[0].attempts == []


@pytest.mark.asyncio
async def test_eager_worker_scheduler_cannot_run_before_running_entry_publication(
    tmp_path,
) -> None:
    """The raw worker stays behind its gate during reentrant task creation."""

    orch = _orchestrator(tmp_path)
    issue = _issue()
    plan = _plan()
    orch._audit_branch_claims[plan.branch_key] = plan.attempt_id
    worker = AsyncMock()
    eager_tasks: list[_EagerFirstTurnTask] = []

    def _create_eager(coroutine, **_kwargs):
        task = _EagerFirstTurnTask(coroutine)
        eager_tasks.append(task)
        assert issue.id not in orch.state.running
        worker.assert_not_awaited()
        return task

    with (
        patch.object(orch, "_tracker_for_issue", return_value=_tracker(issue)),
        patch.object(orch, "_run_worker", worker),
        patch("oompah.orchestrator.asyncio.create_task", side_effect=_create_eager),
    ):
        admitted = await orch._dispatch(issue, 0, auditor_plan=plan)

    assert admitted is True
    assert orch.state.running[issue.id].worker_task is eager_tasks[0]
    worker.assert_not_awaited()
    entry = orch.state.running.pop(issue.id)
    entry.worker_task.cancel()


def test_quiesce_waits_for_winning_running_entry_publication(tmp_path) -> None:
    """If admission wins first, quiesce cannot return on a half-published run."""

    orch = _orchestrator(tmp_path)
    issue = _issue()
    plan = _plan()
    store = _persisted_store(plan)
    _record_queued_metric(orch, plan)
    publish_entered = threading.Event()
    release_publish = threading.Event()
    quiesce_started = threading.Event()
    quiesce_returned = threading.Event()
    original_register = orch._register_running_entry

    def _register(issue_id: str, entry: RunningEntry) -> bool:
        publish_entered.set()
        assert release_publish.wait(timeout=3)
        return original_register(issue_id, entry)

    def _quiesce() -> None:
        quiesce_started.set()
        orch.quiesce()
        quiesce_returned.set()

    with (
        patch.object(orch, "_tracker_for_issue", return_value=_tracker(issue)),
        patch.object(orch, "_audit_store", return_value=store),
        patch.object(orch, "_register_running_entry", side_effect=_register),
        patch.object(orch, "_run_worker", new_callable=AsyncMock),
    ):
        dispatch_thread, result = _run_dispatch_in_thread(orch, issue, plan)
        assert publish_entered.wait(timeout=3)
        quiesce_thread = threading.Thread(target=_quiesce, name="quiesce")
        quiesce_thread.start()
        assert quiesce_started.wait(timeout=3)
        assert not quiesce_returned.is_set()
        release_publish.set()
        dispatch_thread.join(timeout=3)
        quiesce_thread.join(timeout=3)

    assert result == [True]
    assert quiesce_returned.is_set()
    assert issue.id in orch.state.running
    assert orch.state.running[issue.id].audit_attempt_id == plan.attempt_id
    assert store.document.pending_chain[0].request_state == RequestState.IN_PROGRESS
    audit_metrics = orch.get_snapshot()["terminal_audit"]
    assert audit_metrics["queued"] == 0
    assert audit_metrics["running"] == 1


def test_restart_api_claim_wins_before_drain_task_starts(tmp_path) -> None:
    """The synchronous HTTP claim is itself a provider-admission fence."""

    orch = _orchestrator(tmp_path)
    issue = _issue()
    plan = _plan()
    store = _persisted_store(plan)
    barrier = _DispatchAdmissionBarrier()
    orch._provider_admission_lock = barrier
    orch._audit_branch_claims[plan.branch_key] = plan.attempt_id
    _record_queued_metric(orch, plan)
    original_orchestrator = server_module._orchestrator

    with (
        patch.object(orch, "_tracker_for_issue", return_value=_tracker(issue)),
        patch.object(orch, "_audit_store", return_value=store),
        patch.object(orch, "_run_worker", new_callable=AsyncMock) as worker,
        patch.object(orch, "graceful_restart", new_callable=AsyncMock) as restart,
    ):
        dispatch_thread, result = _run_dispatch_in_thread(orch, issue, plan)
        assert barrier.reached.wait(timeout=3)
        try:
            server_module._orchestrator = orch
            response = TestClient(server_module.app).post(
                "/api/v1/orchestrator/restart",
                json={"drain_timeout_s": 30},
            )
        finally:
            server_module._orchestrator = original_orchestrator
            barrier.release_gate.set()
        dispatch_thread.join(timeout=3)

    assert response.status_code == 200
    assert response.json()["coalesced"] is False
    restart.assert_awaited_once()
    assert orch._restart_in_progress is True
    assert orch._restart_drain_started is False
    assert orch._dispatch_is_blocked(issue) is True
    assert result == [False]
    worker.assert_not_awaited()
    record = store.document.pending_chain[0]
    assert record.request_state == RequestState.PENDING
    assert record.attempts == []
    audit_metrics = orch.get_snapshot()["terminal_audit"]
    assert audit_metrics["queued"] == 1
    assert audit_metrics["running"] == 0


def test_stop_wins_at_final_admission_and_restores_attempt(tmp_path) -> None:
    """A concurrent service stop cannot admit a late auditor."""

    orch = _orchestrator(tmp_path)
    issue = _issue()
    plan = _plan()
    store = _persisted_store(plan)
    barrier = _DispatchAdmissionBarrier()
    orch._provider_admission_lock = barrier
    orch._audit_branch_claims[plan.branch_key] = plan.attempt_id

    with (
        patch.object(orch, "_tracker_for_issue", return_value=_tracker(issue)),
        patch.object(orch, "_audit_store", return_value=store),
        patch.object(orch, "_run_worker", new_callable=AsyncMock) as worker,
    ):
        dispatch_thread, result = _run_dispatch_in_thread(orch, issue, plan)
        assert barrier.reached.wait(timeout=3)
        stop_thread = threading.Thread(
            target=lambda: asyncio.run(orch.stop()),
            name="orchestrator-stop",
        )
        stop_thread.start()
        stop_thread.join(timeout=3)
        barrier.release_gate.set()
        dispatch_thread.join(timeout=3)

    assert not stop_thread.is_alive()
    assert not dispatch_thread.is_alive()
    assert orch._stopping is True
    assert result == [False]
    worker.assert_not_awaited()
    record = store.document.pending_chain[0]
    assert record.request_state == RequestState.PENDING
    assert record.attempts == []


@pytest.mark.asyncio
async def test_unpause_during_restart_drain_cannot_reopen_admission(tmp_path) -> None:
    """A delayed resume cannot clear an active restart's admission fence."""

    orch = _orchestrator(tmp_path)
    issue = _issue()
    worker_task = MagicMock()
    worker_task.done.return_value = False
    orch.state.running[issue.id] = RunningEntry(
        worker_task=worker_task,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        run_id="draining-run",
    )
    drain_waiting = asyncio.Event()
    release_drain = asyncio.Event()

    async def _hold_drain(_delay: float) -> None:
        drain_waiting.set()
        await release_drain.wait()

    with patch("oompah.orchestrator.asyncio.sleep", side_effect=_hold_drain):
        restart_task = asyncio.create_task(
            orch.graceful_restart(drain_timeout_s=30),
        )
        await asyncio.wait_for(drain_waiting.wait(), timeout=3)

        assert orch._restart_in_progress is True
        assert orch._restart_drain_started is True
        assert orch._paused is True
        assert orch._quiesced is True
        assert orch.unpause() is False
        assert orch._paused is True
        assert orch._quiesced is True
        assert orch._dispatch_is_blocked(issue) is True

        orch.state.running.clear()
        release_drain.set()
        await asyncio.wait_for(restart_task, timeout=3)

    assert orch._restart_requested is True
    assert orch._stopping is True


@pytest.mark.asyncio
async def test_cancelled_direct_restart_restores_full_admission_state(tmp_path) -> None:
    """Direct restart cancellation cannot leave pause or restart ownership behind."""

    orch = _orchestrator(tmp_path)
    issue = _issue()
    worker_task = MagicMock()
    worker_task.done.return_value = False
    orch.state.running[issue.id] = RunningEntry(
        worker_task=worker_task,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        run_id="cancelled-drain-run",
    )
    drain_waiting = asyncio.Event()

    async def _hold_drain(_delay: float) -> None:
        drain_waiting.set()
        await asyncio.Event().wait()

    with patch("oompah.orchestrator.asyncio.sleep", side_effect=_hold_drain):
        restart_task = asyncio.create_task(orch.graceful_restart(drain_timeout_s=30))
        await asyncio.wait_for(drain_waiting.wait(), timeout=3)
        restart_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await restart_task

    assert orch._restart_in_progress is False
    assert orch._restart_drain_scheduled is False
    assert orch._restart_drain_started is False
    assert orch._restart_drain_task is None
    assert orch._restart_drain_owner is None
    assert orch._paused is False
    assert orch._quiesced is False
    assert orch._stopping is False
    assert orch._restart_requested is False
    assert orch.unpause() is True


@pytest.mark.asyncio
async def test_cancelled_restart_preserves_intervening_quiesce_fence(
    tmp_path,
) -> None:
    """Cancellation cannot replay lifecycle state older than quiesce."""

    orch = _orchestrator(tmp_path)
    issue = _issue()
    worker_task = MagicMock()
    worker_task.done.return_value = False
    orch.state.running[issue.id] = RunningEntry(
        worker_task=worker_task,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        run_id="cancelled-drain-after-quiesce",
    )
    drain_waiting = asyncio.Event()

    async def _hold_drain(_delay: float) -> None:
        drain_waiting.set()
        await asyncio.Event().wait()

    with patch("oompah.orchestrator.asyncio.sleep", side_effect=_hold_drain):
        restart_task = asyncio.create_task(orch.graceful_restart(drain_timeout_s=30))
        await asyncio.wait_for(drain_waiting.wait(), timeout=3)
        owned_generation = orch._provider_admission_generation
        orch.quiesce()
        quiesced_generation = orch._provider_admission_generation
        assert quiesced_generation == owned_generation + 1

        restart_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await restart_task

    assert orch._restart_in_progress is False
    assert orch._restart_drain_task is None
    assert orch._quiesced is True
    assert orch._paused is True
    assert orch._provider_admission_generation == quiesced_generation
    assert orch._dispatch_is_blocked(issue) is True


@pytest.mark.asyncio
async def test_restart_auditor_retirement_task_creation_failure_closes_coroutine(
    tmp_path,
) -> None:
    """Restart staging cannot leak an unowned retirement coroutine."""

    orch = _orchestrator(tmp_path)
    issue = _issue()
    plan = _plan()
    worker_task = MagicMock()
    worker_task.done.return_value = False
    entry = RunningEntry(
        worker_task=worker_task,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        is_auditor=True,
        audit_id=plan.audit_id,
        audit_attempt_id=plan.attempt_id,
        branch_key=plan.branch_key,
        run_id="restart-retirement-creation-failure",
        auditor_authority_generation=orch._auditor_authority_generation(
            issue.project_id,
            issue.identifier,
        ),
    )
    orch._register_running_entry(issue.id, entry)
    loop = asyncio.get_running_loop()
    rejected_coroutines = []

    def reject_retirement(coroutine, **_kwargs):
        rejected_coroutines.append(coroutine)
        raise RuntimeError("injected restart retirement creation failure")

    with patch.object(loop, "create_task", side_effect=reject_retirement):
        with pytest.raises(
            RuntimeError,
            match="injected restart retirement creation failure",
        ):
            await orch.graceful_restart(drain_timeout_s=0)

    assert len(rejected_coroutines) == 1
    assert rejected_coroutines[0].cr_frame is None
    assert orch._current_running_entry(issue.id) is entry
    assert orch._restart_in_progress is False
    assert orch._restart_drain_task is None
    assert orch._quiesced is True
    assert orch._dispatch_is_blocked(issue) is True


def test_resume_api_rejects_active_restart_fence(tmp_path) -> None:
    """The operator endpoint reports the restart-owned resume rejection."""

    orch = _orchestrator(tmp_path)
    with orch._provider_admission_lock:
        orch._restart_in_progress = True
        orch._restart_drain_started = True
        orch._restart_request_id = "restart-draining"
        orch._paused = True
        orch._quiesced = True
    original_orchestrator = server_module._orchestrator
    try:
        server_module._orchestrator = orch
        response = TestClient(server_module.app).post(
            "/api/v1/orchestrator/resume",
        )
    finally:
        server_module._orchestrator = original_orchestrator

    assert response.status_code == 409
    assert response.json()["restart_request_id"] == "restart-draining"
    assert orch._paused is True
    assert orch._quiesced is True


@pytest.mark.asyncio
async def test_preclaimed_restart_has_one_matching_drain_owner(tmp_path) -> None:
    """An API preclaim starts once; duplicate matching starters coalesce."""

    orch = _orchestrator(tmp_path)
    request_id = "restart-preclaimed"
    with orch._provider_admission_lock:
        orch._restart_in_progress = True
        orch._restart_drain_started = False
        orch._restart_request_id = request_id
        orch._restart_requested_at = datetime.now(timezone.utc).isoformat()
        orch._restart_initial_running = 0

    await asyncio.gather(
        orch.graceful_restart(drain_timeout_s=0, request_id=request_id),
        orch.graceful_restart(drain_timeout_s=0, request_id=request_id),
    )

    assert orch._restart_drain_started is True
    shutdown_events = []
    while not orch._dispatch_queue.empty():
        event = orch._dispatch_queue.get_nowait()
        if event.event_type.value == "shutdown":
            shutdown_events.append(event)
    assert len(shutdown_events) == 1


@pytest.mark.parametrize("fence", ["quiesce", "pause", "project_pause"])
def test_existing_lifecycle_fence_keeps_audit_queued_without_attempt(
    tmp_path,
    fence: str,
) -> None:
    """Startup/retry while paused or quiesced never consumes an audit attempt."""

    orch = _orchestrator(tmp_path)
    issue = _issue()
    plan = _plan()
    store = _persisted_store(plan)
    orch._audit_branch_claims[plan.branch_key] = plan.attempt_id
    if fence == "project_pause":
        orch.project_store.get.return_value = SimpleNamespace(paused=True)
    else:
        getattr(orch, fence)()

    with (
        patch.object(orch, "_audit_store", return_value=store),
        patch.object(orch, "_run_worker", new_callable=AsyncMock) as worker,
    ):
        admitted = asyncio.run(orch._dispatch(issue, 0, auditor_plan=plan))

    assert admitted is False
    worker.assert_not_awaited()
    assert issue.id not in orch.state.running
    record = store.document.pending_chain[0]
    assert record.request_state == RequestState.PENDING
    assert record.attempts == []
    assert store.document.attempt_history == []


@pytest.mark.asyncio
async def test_quiesce_during_setup_restores_attempt_at_provider_boundary(
    tmp_path,
) -> None:
    """An admitted setup fenced before provider start is not a failed attempt."""

    orch = _orchestrator(tmp_path)
    issue = _issue()
    plan = _plan()
    store = _persisted_store(plan)
    task = MagicMock()
    task.done.return_value = True
    entry = RunningEntry(
        worker_task=task,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        is_auditor=True,
        audit_id=plan.audit_id,
        audit_attempt_id=plan.attempt_id,
        branch_key=plan.branch_key,
        run_id="run-1",
    )
    orch.state.running[issue.id] = entry
    orch.state.claimed.add(issue.id)
    orch.state.claimed_issues[issue.id] = issue
    orch._audit_branch_claims[plan.branch_key] = plan.attempt_id

    orch.quiesce()
    assert orch._provider_launch_blocked(issue, "run-1") is True
    assert entry.provider_started is False
    assert entry.forced_exit_reason == "lifecycle_drain_before_launch"

    with (
        patch.object(orch, "_audit_store", return_value=store),
        patch.object(orch, "_managed_processes", return_value={}),
        patch.object(orch, "_fire_task_cost_record"),
        patch.object(orch, "_fire_telemetry_comment"),
        patch.object(orch, "_remove_audit_workspace"),
    ):
        await orch._on_worker_exit(
            issue.id,
            "interrupted",
            "provider did not start",
            run_id="run-1",
        )

    assert issue.id not in orch.state.running
    assert issue.id not in orch.state.claimed
    assert plan.branch_key not in orch._audit_branch_claims
    record = store.document.pending_chain[0]
    assert record.request_state == RequestState.PENDING
    assert record.attempts == []
    assert store.document.attempt_history == []


@pytest.mark.parametrize("provider_kind", ["api", "acp", "cli"])
@pytest.mark.asyncio
async def test_provider_start_handshake_rechecks_fence_before_task_publication(
    tmp_path,
    provider_kind: str,
) -> None:
    """Every provider path loses cleanly when quiesce wins phase two."""

    orch = _orchestrator(tmp_path)
    issue = _issue()
    worker_task = MagicMock()
    worker_task.done.return_value = False
    entry = RunningEntry(
        worker_task=worker_task,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        run_id=f"{provider_kind}-run",
    )
    orch.state.running[issue.id] = entry
    starts: list[str] = []

    async def _start() -> str:
        starts.append(provider_kind)
        return provider_kind

    assert orch._provider_launch_blocked(issue, entry.run_id) is False
    reserved_generation = entry.provider_admission_generation
    orch.quiesce()
    assert orch._provider_admission_generation != reserved_generation

    provider_task = orch._publish_provider_start(issue, entry.run_id, _start)
    await asyncio.sleep(0)

    assert provider_task is None
    assert starts == []
    assert entry.provider_start_task is None
    assert entry.provider_started is False


def test_global_pause_wins_final_provider_contact_admission(tmp_path) -> None:
    """A pause after setup but before the contact CAS denies transport."""

    orch = _orchestrator(tmp_path)
    issue = _issue()
    task = MagicMock()
    task.done.return_value = False
    entry = RunningEntry(
        worker_task=task,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        provider_id="provider-1",
        model_name="model-1",
        run_id="pause-contact-race",
    )
    orch.state.running[issue.id] = entry
    entered_policy = threading.Event()
    release_policy = threading.Event()
    result: list[str | None] = []

    def _block_policy(_entry, _candidate):
        entered_policy.set()
        assert release_policy.wait(timeout=3)
        return Candidate("provider-1", "model-1"), None

    with (
        patch.object(
            orch,
            "_contributor_contact_authority_error",
            side_effect=_block_policy,
        ),
        patch.object(
            orch,
            "_refresh_audit_budget_admission",
            return_value=(None, None),
        ),
    ):
        contact = threading.Thread(
            target=lambda: result.append(
                orch._begin_provider_contact(
                    issue,
                    entry.run_id,
                    transport="API",
                    contributor_candidate=Candidate("provider-1", "model-1"),
                )
            ),
            name="provider-contact",
        )
        contact.start()
        assert entered_policy.wait(timeout=3)
        orch.pause()
        release_policy.set()
        contact.join(timeout=3)

    assert not contact.is_alive()
    assert result and "blocked" in (result[0] or "")
    assert entry.provider_contact_permitted is False
    assert entry.provider_started is False


def test_project_pause_wins_final_provider_contact_admission(tmp_path) -> None:
    """A project pause that wins slow setup denies its provider transport."""

    orch = _orchestrator(tmp_path)
    issue = _issue()
    task = MagicMock()
    task.done.return_value = False
    entry = RunningEntry(
        worker_task=task,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        provider_id="provider-1",
        model_name="model-1",
        run_id="project-pause-contact-race",
    )
    orch.state.running[issue.id] = entry
    project_paused = threading.Event()
    orch.project_store.get.side_effect = lambda _project_id: SimpleNamespace(
        paused=project_paused.is_set()
    )
    entered_policy = threading.Event()
    release_policy = threading.Event()
    result: list[str | None] = []

    def _block_policy(_entry, _candidate):
        entered_policy.set()
        assert release_policy.wait(timeout=3)
        return Candidate("provider-1", "model-1"), None

    with (
        patch.object(
            orch,
            "_contributor_contact_authority_error",
            side_effect=_block_policy,
        ),
        patch.object(
            orch,
            "_refresh_audit_budget_admission",
            return_value=(None, None),
        ),
    ):
        contact = threading.Thread(
            target=lambda: result.append(
                orch._begin_provider_contact(
                    issue,
                    entry.run_id,
                    transport="API",
                    contributor_candidate=Candidate("provider-1", "model-1"),
                )
            ),
            name="provider-contact",
        )
        contact.start()
        assert entered_policy.wait(timeout=3)
        project_paused.set()
        release_policy.set()
        contact.join(timeout=3)

    assert not contact.is_alive()
    assert result and "blocked" in (result[0] or "")
    assert entry.provider_contact_permitted is False
    assert entry.provider_started is False


@pytest.mark.asyncio
async def test_contact_permit_wins_retirement_accounting_over_unadmitted_rollback(
    tmp_path,
) -> None:
    """Retirement treats a granted permit as spend-bearing before Popen."""

    orch = _orchestrator(tmp_path)
    issue = _issue()
    plan = _plan()
    task = MagicMock()
    task.done.return_value = True
    entry = RunningEntry(
        worker_task=task,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        is_auditor=True,
        audit_id=plan.audit_id,
        audit_attempt_id=plan.attempt_id,
        branch_key=plan.branch_key,
        provider_id=plan.candidate.provider_id,
        model_name=plan.candidate.model,
        run_id="permit-wins-retirement",
    )
    orch.state.running[issue.id] = entry
    orch.state.claimed.add(issue.id)
    orch.state.claimed_issues[issue.id] = issue
    orch._audit_branch_claims[plan.branch_key] = plan.attempt_id

    with (
        patch.object(orch, "_auditor_contact_authority_error", return_value=None),
        patch.object(
            orch,
            "_refresh_audit_budget_admission",
            return_value=(("reservation",), None),
        ),
        patch.object(orch, "_mark_audit_budget_started", return_value=True),
    ):
        assert (
            orch._begin_provider_contact(
                issue,
                entry.run_id,
                transport="API",
            )
            is None
        )

    assert entry.provider_contact_permitted is True
    assert entry.provider_started is True

    with (
        patch.object(orch, "_managed_processes", return_value={}),
        patch.object(orch, "_reconcile_audit_budget_spend", return_value=True) as reconcile,
        patch.object(orch, "_release_audit_budget_reservation", return_value=True) as release,
        patch.object(
            orch,
            "_secure_unadmitted_auditor_exit_guaranteed",
            new_callable=AsyncMock,
        ) as rollback,
        patch.object(orch, "_fire_task_cost_record"),
        patch.object(orch, "_fire_telemetry_comment"),
    ):
        terminated = await orch._terminate_running(
            issue.id,
            cleanup_workspace=False,
        )

    assert terminated is True
    rollback.assert_not_awaited()
    reconcile.assert_called_once_with(
        orch._audit_reservation_key_for_issue(issue),
        actual_cost=None,
    )
    release.assert_called_once_with(orch._audit_reservation_key_for_issue(issue))


@pytest.mark.asyncio
async def test_published_provider_start_is_visible_before_quiesce_returns(
    tmp_path,
) -> None:
    """A winning phase-two task is published before the fence can observe it."""

    orch = _orchestrator(tmp_path)
    issue = _issue()
    worker_task = MagicMock()
    worker_task.done.return_value = False
    entry = RunningEntry(
        worker_task=worker_task,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        run_id="published-run",
    )
    orch.state.running[issue.id] = entry
    started = asyncio.Event()
    release = asyncio.Event()

    async def _start() -> str:
        started.set()
        await release.wait()
        return "started"

    assert orch._provider_launch_blocked(issue, entry.run_id) is False
    provider_task = orch._publish_provider_start(issue, entry.run_id, _start)
    assert provider_task is not None
    assert entry.provider_start_task is provider_task
    orch.quiesce()
    await asyncio.wait_for(started.wait(), timeout=3)
    # Publication won before quiesce, but this dummy start function never
    # crosses the later provider-contact callback.
    assert entry.provider_contact_permitted is False
    assert entry.provider_started is False
    assert issue.id in orch.state.running
    release.set()
    assert await provider_task == "started"


@pytest.mark.asyncio
async def test_eager_api_provider_task_waits_for_publication_gate(tmp_path) -> None:
    """An API transport cannot start reentrantly before task publication."""

    orch = _orchestrator(tmp_path)
    issue = _issue()
    worker_task = MagicMock()
    worker_task.done.return_value = False
    entry = RunningEntry(
        worker_task=worker_task,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        run_id="eager-api-provider",
    )
    orch.state.running[issue.id] = entry
    session = ApiAgentSession(
        base_url="https://provider.invalid/v1",
        api_key="test-key",
        model="test-model",
        workspace_path=str(tmp_path),
    )
    session.run_task = AsyncMock(return_value="done")

    assert orch._provider_launch_blocked(issue, entry.run_id) is False

    def _create_eager(coroutine, **_kwargs):
        task = _EagerFirstTurnTask(coroutine)
        assert entry.provider_start_task is None
        session.run_task.assert_not_awaited()
        return task

    with patch(
        "oompah.orchestrator.asyncio.create_task",
        side_effect=_create_eager,
    ):
        provider_task = orch._publish_provider_start(
            issue,
            entry.run_id,
            lambda: session.run_task("prompt"),
        )

    assert provider_task is entry.provider_start_task
    session.run_task.assert_not_awaited()
    provider_task.cancel()


@pytest.mark.asyncio
async def test_provider_task_creation_failure_rolls_back_published_audit(
    tmp_path,
) -> None:
    """Phase-two task creation is part of the exact audit admission."""

    orch = _orchestrator(tmp_path)
    issue = _issue()
    plan = _plan()
    store = _persisted_store(plan)
    worker_task = MagicMock()
    worker_task.done.return_value = False
    entry = RunningEntry(
        worker_task=worker_task,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        is_auditor=True,
        audit_id=plan.audit_id,
        audit_attempt_id=plan.attempt_id,
        branch_key=plan.branch_key,
        run_id="provider-create-failure",
    )
    orch.state.running[issue.id] = entry
    orch.state.claimed.add(issue.id)
    orch.state.claimed_issues[issue.id] = issue
    orch._audit_branch_claims[plan.branch_key] = plan.attempt_id
    orch._dispatch_loop = asyncio.get_running_loop()
    orch.state.max_concurrent_agents = 1
    _record_queued_metric(orch, plan)
    orch._terminal_audit_metrics.record_running(
        issue.project_id,
        issue.identifier,
        plan.audit_id,
        attempts=1,
    )
    orch._record_terminal_audit_stage_wake(
        project_id=issue.project_id or "legacy",
        task_id="AUDIT-WAKE",
        audit_id="audit-successor",
    )
    dispatched = asyncio.Event()

    async def _scan(**_kwargs) -> dict[str, float]:
        if orch._available_slots() > 0:
            orch._retire_terminal_audit_stage_wake(
                project_id=issue.project_id or "legacy",
                task_id="AUDIT-WAKE",
                expected_audit_id="audit-successor",
                reason="test_dispatch",
            )
            dispatched.set()
        return {}

    async def _must_not_start() -> None:
        raise AssertionError("provider transport started")

    assert orch._provider_launch_blocked(issue, entry.run_id) is False
    real_create_task = asyncio.create_task

    def _reject_provider_task(coroutine, **kwargs):
        if str(kwargs.get("name") or "").startswith("provider-start-"):
            raise RuntimeError("event loop rejected provider task")
        return real_create_task(coroutine, **kwargs)

    with (
        patch.object(orch, "_audit_store", return_value=store),
        patch.object(orch, "_dispatch_audit_lane", side_effect=_scan) as scan,
        patch(
            "oompah.orchestrator.asyncio.create_task",
            side_effect=_reject_provider_task,
        ),
    ):
        orch._wake_terminal_audit_continuation_lane_on_loop()
        first_owner = orch._terminal_audit_continuation_future
        assert first_owner is not None
        await asyncio.wait_for(first_owner, timeout=1)
        assert scan.await_count == 1
        assert not dispatched.is_set()

        provider_task = orch._publish_provider_start(
            issue,
            entry.run_id,
            _must_not_start,
        )
        await asyncio.wait_for(dispatched.wait(), timeout=1)
        await asyncio.sleep(0)

    assert provider_task is None
    assert scan.await_count == 2
    assert orch._terminal_audit_stage_wakes_snapshot() == {}
    assert issue.id not in orch.state.running
    assert issue.id not in orch.state.claimed
    assert plan.branch_key not in orch._audit_branch_claims
    record = store.document.pending_chain[0]
    assert record.request_state == RequestState.PENDING
    assert record.attempts == []
    assert store.document.attempt_history == []
    audit_metrics = orch.get_snapshot()["terminal_audit"]
    assert audit_metrics["queued"] == 1
    assert audit_metrics["running"] == 0


@pytest.mark.asyncio
async def test_provider_task_creation_cancelled_error_rolls_back_before_reraising(
    tmp_path,
) -> None:
    orch = _orchestrator(tmp_path)
    issue = _issue()
    plan = _plan()
    store = _persisted_store(plan)
    worker_task = MagicMock()
    worker_task.done.return_value = False
    entry = RunningEntry(
        worker_task=worker_task,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        is_auditor=True,
        audit_id=plan.audit_id,
        audit_attempt_id=plan.attempt_id,
        branch_key=plan.branch_key,
        run_id="provider-create-cancelled",
    )
    orch.state.running[issue.id] = entry
    orch.state.claimed.add(issue.id)
    orch.state.claimed_issues[issue.id] = issue
    orch._audit_branch_claims[plan.branch_key] = plan.attempt_id
    assert orch._provider_launch_blocked(issue, entry.run_id) is False

    with (
        patch.object(orch, "_audit_store", return_value=store),
        patch.object(orch, "_remove_audit_workspace"),
        patch(
            "oompah.orchestrator.asyncio.create_task",
            side_effect=asyncio.CancelledError(),
        ),
    ):
        with pytest.raises(asyncio.CancelledError):
            orch._publish_provider_start(issue, entry.run_id, AsyncMock())

    assert issue.id not in orch.state.running
    assert issue.id not in orch.state.claimed
    assert plan.branch_key not in orch._audit_branch_claims
    assert store.document.pending_chain[0].request_state == RequestState.PENDING
    assert store.document.pending_chain[0].attempts == []


@pytest.mark.asyncio
async def test_cancel_at_initial_tracker_refresh_restores_audit_attempt(
    tmp_path,
) -> None:
    """Cancellation at the first awaited refresh still compensates the plan."""

    orch = _orchestrator(tmp_path)
    issue = _issue()
    plan = _plan()
    store = _persisted_store(plan)
    orch._audit_branch_claims[plan.branch_key] = plan.attempt_id
    refresh_started = threading.Event()
    release_refresh = threading.Event()
    tracker = _tracker(issue)

    def blocked_refresh(_issue_ids):
        refresh_started.set()
        assert release_refresh.wait(timeout=3)
        return [issue]

    tracker.fetch_issue_states_by_ids.side_effect = blocked_refresh
    with (
        patch.object(orch, "_tracker_for_issue", return_value=tracker),
        patch.object(orch, "_audit_store", return_value=store),
        patch.object(orch, "_run_worker", new_callable=AsyncMock) as worker,
    ):
        dispatch_task = asyncio.create_task(
            orch._dispatch(issue, 0, auditor_plan=plan)
        )
        await asyncio.to_thread(refresh_started.wait)
        dispatch_task.cancel()
        release_refresh.set()
        with pytest.raises(asyncio.CancelledError):
            await dispatch_task

    worker.assert_not_awaited()
    assert issue.id not in orch.state.running
    assert issue.id not in orch.state.claimed
    assert plan.branch_key not in orch._audit_branch_claims
    record = store.document.pending_chain[0]
    assert record.request_state == RequestState.PENDING
    assert record.attempts == []
    assert store.document.attempt_history == []


@pytest.mark.asyncio
async def test_audit_lane_repeated_cancel_waits_for_fallback_thread_start(
    tmp_path,
) -> None:
    """Nested cancellation cannot strand the lane's persisted launch plan."""

    orch = _orchestrator(tmp_path)
    issue = _issue()
    seed = _plan()
    record = TerminalAuditRecord(
        audit_id=seed.audit_id,
        project_id=issue.project_id,
        task_id=issue.identifier,
        request_state=RequestState.PENDING,
        target_state=seed.target_state,
        evidence_fingerprint=seed.evidence_fingerprint,
        attempts=[],
        created_at=seed.created_at,
    )
    store = _MemoryAuditStore(
        TerminalAuditMetadata(pending_chain=[record], attempt_history=[])
    )
    selector = MagicMock()
    selector.select_candidates.return_value = ([seed.candidate], None)
    tracker = _tracker(issue)
    tracker.get_metadata.return_value = {}
    orch._dispatch = AsyncMock(side_effect=asyncio.CancelledError())
    fallback_scheduled = asyncio.Event()
    allow_fallback_thread = asyncio.Event()
    real_to_thread = asyncio.to_thread

    async def controlled_to_thread(func, /, *args, **kwargs):
        if getattr(func, "__name__", "") == (
            "_restore_or_defer_unadmitted_audit_attempt"
        ):
            fallback_scheduled.set()
            await allow_fallback_thread.wait()
        return await real_to_thread(func, *args, **kwargs)

    with (
        patch.object(
            orch,
            "_fetch_audit_candidates",
            return_value=_AuditCandidateScan((issue,)),
        ),
        patch.object(orch, "_audit_store", return_value=store),
        patch.object(
            orch,
            "_prepare_audit_selector",
            new=AsyncMock(return_value=(selector, None)),
        ),
        patch.object(
            orch,
            "_terminal_audit_validation_configuration_error",
            return_value=None,
        ),
        patch.object(orch, "_clear_terminal_audit_validation_configuration"),
        patch.object(orch, "_revisionless_archive_evidence", return_value=None),
        patch.object(orch, "_bind_audit_record_revision", return_value=record),
        patch.object(orch, "_tracker_for_issue", return_value=tracker),
        patch("oompah.orchestrator.asyncio.to_thread", side_effect=controlled_to_thread),
    ):
        lane_task = asyncio.create_task(orch._dispatch_audit_lane())
        await asyncio.wait_for(fallback_scheduled.wait(), timeout=3)
        lane_task.cancel()
        await asyncio.sleep(0)
        lane_task.cancel()
        await asyncio.sleep(0)
        allow_fallback_thread.set()
        with pytest.raises(asyncio.CancelledError):
            await lane_task

    persisted = store.document.pending_chain[0]
    assert persisted.request_state == RequestState.PENDING
    assert persisted.attempts == []
    assert store.document.attempt_history == []
    assert orch._audit_branch_claims == {}


async def _assert_cancelled_real_transport_is_unadmitted(
    tmp_path,
    *,
    provider_kind: str,
    start,
    start_mock: AsyncMock,
) -> None:
    orch = _orchestrator(tmp_path)
    issue = _issue()
    plan = _plan()
    store = _persisted_store(plan)
    worker_task = MagicMock()
    worker_task.done.return_value = False
    entry = RunningEntry(
        worker_task=worker_task,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        is_auditor=True,
        audit_id=plan.audit_id,
        audit_attempt_id=plan.attempt_id,
        branch_key=plan.branch_key,
        run_id=f"{provider_kind}-cancel-before-first-turn",
    )
    orch.state.running[issue.id] = entry
    orch.state.claimed.add(issue.id)
    orch.state.claimed_issues[issue.id] = issue
    orch._audit_branch_claims[plan.branch_key] = plan.attempt_id
    assert orch._provider_launch_blocked(issue, entry.run_id) is False
    provider_task = orch._publish_provider_start(issue, entry.run_id, start)
    assert provider_task is not None
    provider_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await provider_task
    assert entry.provider_started is False

    with (
        patch.object(orch, "_audit_store", return_value=store),
        patch.object(orch, "_managed_processes", return_value={}),
        patch.object(orch, "_fire_task_cost_record"),
        patch.object(orch, "_fire_telemetry_comment"),
        patch.object(orch, "_remove_audit_workspace"),
    ):
        await orch._on_worker_exit(
            issue.id,
            "cancelled",
            "worker cancelled before provider first turn",
            run_id=entry.run_id,
        )

    start_mock.assert_not_awaited()
    assert issue.id not in orch.state.running
    assert issue.id not in orch.state.claimed
    assert plan.branch_key not in orch._audit_branch_claims
    record = store.document.pending_chain[0]
    assert record.request_state == RequestState.PENDING
    assert record.attempts == []
    assert store.document.attempt_history == []


@pytest.mark.asyncio
async def test_cancel_before_api_provider_first_turn_is_unadmitted(tmp_path) -> None:
    session = ApiAgentSession(
        base_url="https://provider.invalid/v1",
        api_key="test-key",
        model="test-model",
        workspace_path=str(tmp_path),
    )
    session.run_task = AsyncMock(return_value="done")
    await _assert_cancelled_real_transport_is_unadmitted(
        tmp_path,
        provider_kind="api",
        start=lambda: session.run_task("prompt"),
        start_mock=session.run_task,
    )


@pytest.mark.asyncio
async def test_cancel_before_acp_provider_first_turn_is_unadmitted(tmp_path) -> None:
    session = AcpAgentSession(
        workspace_path=str(tmp_path),
        prompt="prompt",
        backend_name="claude",
    )
    session.run_task = AsyncMock(return_value="done")
    await _assert_cancelled_real_transport_is_unadmitted(
        tmp_path,
        provider_kind="acp",
        start=session.run_task,
        start_mock=session.run_task,
    )


@pytest.mark.asyncio
async def test_cancel_before_cli_provider_first_turn_is_unadmitted(tmp_path) -> None:
    session = AgentSession(command="true", workspace_path=str(tmp_path))
    session.start = AsyncMock(return_value=None)
    await _assert_cancelled_real_transport_is_unadmitted(
        tmp_path,
        provider_kind="cli",
        start=session.start,
        start_mock=session.start,
    )


def _register_provider_wiring_entry(
    orch: Orchestrator,
    issue: Issue,
    run_id: str,
) -> RunningEntry:
    task = MagicMock()
    task.done.return_value = False
    entry = RunningEntry(
        worker_task=task,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        run_id=run_id,
    )
    orch.state.running[issue.id] = entry
    return entry


def _provider_wiring_focus() -> SimpleNamespace:
    return SimpleNamespace(
        name="general",
        role="Generalist",
        model=None,
        model_role=None,
        allow_image_output=False,
        render=lambda _project: "focus",
    )


@pytest.mark.asyncio
async def test_real_api_worker_routes_session_through_publication_gate(tmp_path) -> None:
    orch = _orchestrator(tmp_path)
    issue = _issue()
    run_id = "real-api-wiring"
    _register_provider_wiring_entry(orch, issue, run_id)
    provider = ModelProvider(
        id="api-provider",
        name="API Provider",
        base_url="https://provider.invalid/v1",
        api_key="test-key",
        models=["test-model"],
        default_model="test-model",
    )
    target = DispatchTarget(
        role_name="fast",
        provider=provider,
        model="test-model",
        candidate_key="api-provider/test-model",
        source="test",
    )
    profile = AgentProfile(
        name="default", command="agent", mode="api", model="test-model"
    )
    tracker = MagicMock()
    tracker.fetch_comments.return_value = []
    tracker.fetch_memories.return_value = {}
    session = MagicMock()
    session.run_task = AsyncMock(return_value=MagicMock())
    orch._tracker_for_issue = MagicMock(return_value=tracker)
    orch._create_workspace_for_issue = MagicMock(
        return_value=(str(tmp_path), None)
    )
    orch._post_comment = MagicMock()
    orch._clear_handoff_labels = MagicMock()
    orch._resolve_capabilities = MagicMock(return_value=[])
    orch._agent_action_policy = MagicMock()
    orch._provider_launch_blocked = MagicMock(return_value=False)
    orch._publish_provider_start = MagicMock(side_effect=asyncio.CancelledError())
    orch._on_worker_exit = AsyncMock()

    with (
        patch(
            "oompah.orchestrator.select_focus_async",
            AsyncMock(return_value=_provider_wiring_focus()),
        ),
        patch(
            "oompah.orchestrator.render_prompt",
            return_value=SimpleNamespace(text="prompt", parts=None, elided=[]),
        ),
        patch.object(
            orch,
            "_reserve_auditor_for_contributor",
            new=AsyncMock(return_value=([target], None)),
        ),
        patch.object(
            orch,
            "_stage_work_contributor_launch",
            new=AsyncMock(return_value=None),
        ),
        patch("oompah.orchestrator.ApiAgentSession", return_value=session),
    ):
        with pytest.raises(asyncio.CancelledError):
            await orch._run_api_worker(
                issue,
                attempt=None,
                profile=profile,
                provider=provider,
                target=target,
                run_id=run_id,
            )

    published_issue, published_run, start = orch._publish_provider_start.call_args.args
    assert published_issue is issue
    assert published_run == run_id
    await start()
    session.run_task.assert_awaited_once()


@pytest.mark.asyncio
async def test_real_acp_worker_routes_session_through_publication_gate(tmp_path) -> None:
    orch = _orchestrator(tmp_path)
    issue = _issue()
    run_id = "real-acp-wiring"
    _register_provider_wiring_entry(orch, issue, run_id)
    provider = ModelProvider(
        id="acp-provider",
        name="ACP Provider",
        base_url="",
        api_key="",
        models=[],
        default_model=None,
        provider_type="acp",
        backend="claude",
        mode="acp",
        billing_model="subscription",
    )
    target = DispatchTarget(
        role_name="fast",
        provider=provider,
        model="sonnet",
        candidate_key="acp-provider/sonnet",
        source="test",
    )
    profile = AgentProfile(
        name="default", command="agent", mode="acp", model="sonnet"
    )
    tracker = MagicMock()
    tracker.fetch_comments.return_value = []
    tracker.fetch_memories.return_value = {}
    session = MagicMock()
    session.run_task = AsyncMock(return_value="succeeded")
    orch._tracker_for_issue = MagicMock(return_value=tracker)
    orch._create_workspace_for_issue = MagicMock(
        return_value=(str(tmp_path), None)
    )
    orch._post_comment = MagicMock()
    orch._clear_handoff_labels = MagicMock()
    orch._resolve_capabilities = MagicMock(return_value=[])
    orch._agent_action_policy = MagicMock()
    orch._issue_task_handoff_token = MagicMock(return_value=None)
    orch._provider_launch_blocked = MagicMock(return_value=False)
    orch._publish_provider_start = MagicMock(side_effect=asyncio.CancelledError())
    orch._on_worker_exit = AsyncMock()

    with (
        patch(
            "oompah.orchestrator.select_focus_async",
            AsyncMock(return_value=_provider_wiring_focus()),
        ),
        patch(
            "oompah.orchestrator.render_prompt",
            return_value=SimpleNamespace(text="prompt", parts=None, elided=[]),
        ),
        patch.object(
            orch,
            "_reserve_auditor_for_contributor",
            new=AsyncMock(return_value=([target], None)),
        ),
        patch.object(
            orch,
            "_stage_work_contributor_launch",
            new=AsyncMock(return_value=None),
        ),
        patch("oompah.acp_tools.build_tool_catalog", return_value={}),
        patch("oompah.acp_agent.AcpAgentSession", return_value=session),
        patch.dict("os.environ", {"OOMPAH_AGENT_LOG_DIR": str(tmp_path)}),
    ):
        with pytest.raises(asyncio.CancelledError):
            await orch._run_acp_worker(
                issue,
                attempt=None,
                profile=profile,
                target=target,
                run_id=run_id,
            )

    published_issue, published_run, start = orch._publish_provider_start.call_args.args
    assert published_issue is issue
    assert published_run == run_id
    assert start is session.run_task


@pytest.mark.asyncio
async def test_real_cli_worker_routes_session_through_publication_gate(tmp_path) -> None:
    orch = _orchestrator(tmp_path)
    issue = _issue()
    run_id = "real-cli-wiring"
    _register_provider_wiring_entry(orch, issue, run_id)
    profile = AgentProfile(name="default", mode="cli", command="agent")
    session = MagicMock()
    session.start = AsyncMock(return_value=None)
    orch._create_workspace_for_issue = MagicMock(
        return_value=(str(tmp_path), None)
    )
    orch._issue_task_handoff_token = MagicMock(return_value=None)
    orch._provider_launch_blocked = MagicMock(return_value=False)
    orch._publish_provider_start = MagicMock(side_effect=asyncio.CancelledError())
    orch._on_worker_exit = AsyncMock()

    with patch("oompah.orchestrator.AgentSession", return_value=session):
        with pytest.raises(asyncio.CancelledError):
            await orch._run_cli_worker(
                issue,
                attempt=None,
                profile=profile,
                run_id=run_id,
            )

    published_issue, published_run, start = orch._publish_provider_start.call_args.args
    assert published_issue is issue
    assert published_run == run_id
    assert start is session.start


@pytest.mark.asyncio
async def test_pause_termination_restores_pre_provider_attempt(tmp_path) -> None:
    """Pause cleanup cannot turn a never-started auditor into a failed try."""

    orch = _orchestrator(tmp_path)
    issue = _issue()
    plan = _plan()
    store = _persisted_store(plan)
    task = MagicMock()
    task.done.return_value = True
    entry = RunningEntry(
        worker_task=task,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        is_auditor=True,
        audit_id=plan.audit_id,
        audit_attempt_id=plan.attempt_id,
        branch_key=plan.branch_key,
        run_id="run-1",
    )
    orch.state.running[issue.id] = entry
    orch.state.claimed.add(issue.id)
    orch.state.claimed_issues[issue.id] = issue
    orch._audit_branch_claims[plan.branch_key] = plan.attempt_id
    with orch._provider_admission_lock:
        orch._paused = True

    with (
        patch.object(orch, "_audit_store", return_value=store),
        patch.object(orch, "_managed_processes", return_value={}),
        patch.object(orch, "_fire_task_cost_record"),
        patch.object(orch, "_fire_telemetry_comment"),
        patch.object(orch, "_remove_audit_workspace"),
    ):
        terminated = await orch._terminate_running(
            issue.id,
            cleanup_workspace=False,
        )

    assert terminated is True
    assert issue.id not in orch.state.running
    assert issue.id not in orch.state.claimed
    assert plan.branch_key not in orch._audit_branch_claims
    record = store.document.pending_chain[0]
    assert record.request_state == RequestState.PENDING
    assert record.attempts == []
    assert store.document.attempt_history == []


@pytest.mark.asyncio
async def test_termination_secures_live_auditor_before_cancellation(
    tmp_path,
) -> None:
    """Caller cancellation cannot precede durable audit rollback authority."""

    orch = _orchestrator(tmp_path)
    issue = _issue()
    plan = _plan()
    store = _persisted_store(plan)
    worker_release = asyncio.Event()
    provider_release = asyncio.Event()
    worker_task = asyncio.create_task(worker_release.wait())
    provider_start_task = asyncio.create_task(provider_release.wait())
    entry = RunningEntry(
        worker_task=worker_task,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        is_auditor=True,
        audit_id=plan.audit_id,
        audit_attempt_id=plan.attempt_id,
        branch_key=plan.branch_key,
        run_id="cancelled-live-audit-termination",
    )
    entry.provider_start_task = provider_start_task
    entry.provider_admission_generation = orch._provider_admission_generation
    orch.state.running[issue.id] = entry
    orch.state.claimed.add(issue.id)
    orch.state.claimed_issues[issue.id] = issue
    orch._audit_branch_claims[plan.branch_key] = plan.attempt_id

    recovery_started = threading.Event()
    release_recovery = threading.Event()
    workspace_cleanup_started = threading.Event()
    release_workspace_cleanup = threading.Event()
    real_secure = orch._secure_unadmitted_auditor_exit
    provider_starts: list[str] = []

    async def attempted_provider_start() -> None:
        provider_starts.append("started")

    def blocking_secure(recovery_entry, *, reason):
        recovery_started.set()
        assert release_recovery.wait(timeout=3)
        return real_secure(recovery_entry, reason=reason)

    def blocking_workspace_cleanup(_entry) -> None:
        workspace_cleanup_started.set()
        assert release_workspace_cleanup.wait(timeout=3)

    managed_processes = MagicMock(return_value={})
    with (
        patch.object(orch, "_audit_store", return_value=store),
        patch.object(
            orch,
            "_secure_unadmitted_auditor_exit",
            side_effect=blocking_secure,
        ),
        patch.object(orch, "_managed_processes", managed_processes),
        patch.object(orch, "_fire_task_cost_record"),
        patch.object(orch, "_fire_telemetry_comment"),
        patch.object(
            orch,
            "_remove_audit_workspace",
            side_effect=blocking_workspace_cleanup,
        ),
    ):
        termination = asyncio.create_task(
            orch._terminate_running(issue.id, cleanup_workspace=False)
        )
        assert await asyncio.to_thread(recovery_started.wait, 3)

        # Recovery is blocked, so neither the live worker nor its provider
        # setup task may have been cancelled and no process cleanup may start.
        assert worker_task.done() is False
        assert provider_start_task.done() is False
        assert managed_processes.call_count == 0
        assert entry.provider_start_task is None
        assert entry.provider_admission_generation is None
        assert entry.retirement_pending is True
        assert orch.state.running[issue.id] is entry
        # Exercise the real two-phase admission API while the durable CAS is
        # blocked.  Retirement authority must prevent setup from reserving a
        # new generation or publishing transport for this exact runtime.
        assert orch._provider_launch_blocked(issue, entry.run_id) is True
        assert (
            orch._publish_provider_start(
                issue,
                entry.run_id,
                attempted_provider_start,
            )
            is None
        )
        await asyncio.sleep(0)
        assert provider_starts == []

        termination.cancel()
        await asyncio.sleep(0)
        assert termination.done() is False
        assert worker_task.done() is False
        assert provider_start_task.done() is False
        release_recovery.set()
        assert await asyncio.to_thread(workspace_cleanup_started.wait, 3)

        # A second cancellation after durable recovery and process/task
        # reaping must still wait for workspace cleanup and the final visible
        # runtime/claim retirement commit.
        assert worker_task.cancelled() is True
        assert provider_start_task.cancelled() is True
        assert orch.state.running[issue.id] is entry
        assert issue.id in orch.state.claimed
        assert entry.retirement_pending is True
        assert orch._provider_launch_blocked(issue, entry.run_id) is True
        assert (
            orch._publish_provider_start(
                issue,
                entry.run_id,
                attempted_provider_start,
            )
            is None
        )
        await asyncio.sleep(0)
        assert provider_starts == []
        termination.cancel()
        await asyncio.sleep(0)
        assert termination.done() is False
        release_workspace_cleanup.set()
        with pytest.raises(asyncio.CancelledError):
            await termination

    assert worker_task.cancelled() is True
    assert provider_start_task.cancelled() is True
    assert issue.id not in orch.state.running
    assert entry.retirement_pending is False
    assert plan.branch_key not in orch._audit_branch_claims
    record = store.document.pending_chain[0]
    assert record.request_state == RequestState.PENDING
    assert record.attempts == []
    assert store.document.attempt_history == []


@pytest.mark.asyncio
async def test_pre_first_turn_retirement_cancellation_releases_parent_fence(
    tmp_path,
) -> None:
    """A cancelled cleanup child cannot leak callback suppression."""

    orch = _orchestrator(tmp_path)
    issue = _issue()
    plan = _plan()
    store = _persisted_store(plan)
    worker_task = MagicMock()
    worker_task.done.return_value = True
    entry = RunningEntry(
        worker_task=worker_task,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        is_auditor=True,
        audit_id=plan.audit_id,
        audit_attempt_id=plan.attempt_id,
        branch_key=plan.branch_key,
        run_id="cancel-retirement-before-first-turn",
    )
    orch.state.running[issue.id] = entry
    orch.state.claimed.add(issue.id)
    orch.state.claimed_issues[issue.id] = issue
    orch._audit_branch_claims[plan.branch_key] = plan.attempt_id

    loop = asyncio.get_running_loop()
    real_create_task = loop.create_task
    retirement_children: list[asyncio.Task] = []

    def create_cancelled_child(coro, **kwargs):
        task = real_create_task(coro, **kwargs)
        retirement_children.append(task)
        task.cancel()
        return task

    with patch.object(loop, "create_task", side_effect=create_cancelled_child):
        with pytest.raises(asyncio.CancelledError):
            await orch._terminate_running(issue.id, cleanup_workspace=False)

    assert len(retirement_children) == 1
    assert retirement_children[0].cancelled() is True
    assert orch._termination_owned(issue.id, entry) is False
    assert orch.state.running[issue.id] is entry
    assert issue.id in orch.state.claimed
    assert entry.retirement_pending is True

    provider_starts: list[str] = []

    async def attempted_provider_start() -> None:
        provider_starts.append("started")

    assert orch._provider_launch_blocked(issue, entry.run_id) is True
    assert (
        orch._publish_provider_start(
            issue,
            entry.run_id,
            attempted_provider_start,
        )
        is None
    )
    await asyncio.sleep(0)
    assert provider_starts == []

    # Once the abandoned parent's callback-suppression fence is gone, the
    # worker-exit callback can acquire rollback ownership and finish the exact
    # retained runtime without reopening provider admission.
    with (
        patch.object(orch, "_audit_store", return_value=store),
        patch.object(orch, "_managed_processes", return_value={}),
        patch.object(orch, "_fire_task_cost_record"),
        patch.object(orch, "_fire_telemetry_comment"),
        patch.object(orch, "_remove_audit_workspace"),
    ):
        await orch._on_worker_exit(
            issue.id,
            "cancelled",
            "retirement child cancelled before first turn",
            run_id=entry.run_id,
        )

    assert issue.id not in orch.state.running
    assert issue.id not in orch.state.claimed
    assert plan.branch_key not in orch._audit_branch_claims
    record = store.document.pending_chain[0]
    assert record.request_state == RequestState.PENDING
    assert record.attempts == []
    assert store.document.attempt_history == []


@pytest.mark.asyncio
async def test_old_retirement_owner_does_not_suppress_replacement_exit(
    tmp_path,
) -> None:
    """Post-removal telemetry for an old run cannot hide its replacement."""

    orch = _orchestrator(tmp_path)
    issue = _issue()
    worker_task = MagicMock()
    worker_task.done.return_value = True
    old_entry = RunningEntry(
        worker_task=worker_task,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        run_id="old-runtime",
    )
    replacement = RunningEntry(
        worker_task=worker_task,
        identifier=issue.identifier,
        issue=replace(issue),
        session=None,
        retry_attempt=1,
        started_at=datetime.now(timezone.utc),
        run_id="replacement-runtime",
        authority_revoked=True,
    )
    orch.state.running[issue.id] = old_entry
    orch.state.claimed.add(issue.id)
    orch.state.claimed_issues[issue.id] = issue
    replacement_exited: list[str] = []

    def replace_and_exit_during_old_telemetry(completed_entry) -> None:
        assert completed_entry is old_entry
        assert issue.id not in orch.state.running
        assert orch._termination_owned(issue.id, old_entry) is True
        orch._register_running_entry(issue.id, replacement)
        orch.state.claimed.add(issue.id)
        orch.state.claimed_issues[issue.id] = replacement.issue
        assert orch._termination_owned(issue.id, replacement) is False

        # The revoked replacement exit has no yielding cleanup. Advance it
        # synchronously while the old child is paused in its telemetry call,
        # making the old owner's still-live lease deterministic.
        replacement_exit = orch._on_worker_exit(
            issue.id,
            "authority_revoked",
            "replacement retired independently",
            run_id=replacement.run_id,
        )
        with pytest.raises(StopIteration):
            replacement_exit.send(None)
        replacement_exited.append(replacement.run_id)

    with (
        patch.object(orch, "_managed_processes", return_value={}),
        patch.object(
            orch,
            "_fire_task_cost_record",
            side_effect=replace_and_exit_during_old_telemetry,
        ),
        patch.object(orch, "_fire_telemetry_comment"),
        patch.object(orch, "_notify_observers"),
        patch.object(orch, "_post_event"),
    ):
        assert await orch._terminate_running(
            issue.id,
            cleanup_workspace=False,
        )

    assert replacement_exited == [replacement.run_id]
    assert issue.id not in orch.state.running
    assert issue.id not in orch.state.claimed
    assert orch._termination_owned(issue.id, old_entry) is False


@pytest.mark.asyncio
async def test_scheduled_old_retirement_does_not_deduplicate_replacement(
    tmp_path,
) -> None:
    """An old scheduled key cannot discard replacement retirement authority."""

    orch = _orchestrator(tmp_path)
    issue = _issue()
    worker_task = MagicMock()
    worker_task.done.return_value = True
    old_entry = RunningEntry(
        worker_task=worker_task,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        run_id="old-scheduled-runtime",
    )
    replacement = RunningEntry(
        worker_task=worker_task,
        identifier=issue.identifier,
        issue=replace(issue),
        session=None,
        retry_attempt=1,
        started_at=datetime.now(timezone.utc),
        # Deliberately reuse the logical run string: object identity must keep
        # the replacement's scheduler authority distinct from the stale key.
        run_id="old-scheduled-runtime",
        authority_revoked=True,
    )
    orch._register_running_entry(issue.id, old_entry)
    orch.state.claimed.add(issue.id)
    orch.state.claimed_issues[issue.id] = issue
    old_key = orch._termination_owner_key(issue.id, old_entry)
    replacement_key = orch._termination_owner_key(issue.id, replacement)
    assert replacement_key != old_key
    replacement_retired = asyncio.Event()

    def replace_and_schedule_during_old_telemetry(completed_entry) -> None:
        if completed_entry is replacement:
            replacement_retired.set()
            return

        assert completed_entry is old_entry
        assert issue.id not in orch.state.running
        assert orch._termination_owned(issue.id, old_entry) is True
        assert orch._scheduled_termination_entries.get(old_key) is old_entry

        # Publish B through the production runtime registry while A's parent
        # still owns both its callback lease and scheduled key.  Scheduling B
        # here is causal: the event loop cannot release A's stale key before
        # this synchronous barrier has admitted B's exact key.
        orch._register_running_entry(issue.id, replacement)
        orch.state.claimed.add(issue.id)
        orch.state.claimed_issues[issue.id] = replacement.issue
        orch._schedule_running_termination(
            issue.id,
            cleanup_workspace=False,
            task_name_prefix="retire-replacement",
        )
        assert orch._scheduled_termination_entries.get(old_key) is old_entry
        assert (
            orch._scheduled_termination_entries.get(replacement_key)
            is replacement
        )

    with (
        patch.object(orch, "_managed_processes", return_value={}),
        patch.object(
            orch,
            "_fire_task_cost_record",
            side_effect=replace_and_schedule_during_old_telemetry,
        ),
        patch.object(orch, "_fire_telemetry_comment"),
        patch.object(orch, "_notify_observers"),
        patch.object(orch, "_post_event"),
    ):
        orch._schedule_running_termination(
            issue.id,
            cleanup_workspace=False,
            task_name_prefix="retire-old",
        )
        await asyncio.wait_for(replacement_retired.wait(), timeout=1)
        deadline = asyncio.get_running_loop().time() + 1
        while asyncio.get_running_loop().time() < deadline:
            if not orch._scheduled_termination_entries:
                break
            await asyncio.sleep(0.001)

    assert issue.id not in orch.state.running
    assert issue.id not in orch.state.claimed
    assert orch._scheduled_termination_entries == {}
    assert orch._terminating_worker_owners == {}
    assert orch._termination_pending_baselines == {}
    assert orch._termination_child_owned_keys == set()


@pytest.mark.asyncio
async def test_scheduled_retirement_captures_entry_before_first_turn(tmp_path) -> None:
    """A queued retirement for A cannot acquire authority over replacement B."""

    orch = _orchestrator(tmp_path)
    issue = _issue()
    worker_task = MagicMock()
    worker_task.done.return_value = True
    old_entry = RunningEntry(
        worker_task=worker_task,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        run_id="queued-old-runtime",
    )
    replacement = RunningEntry(
        worker_task=worker_task,
        identifier=issue.identifier,
        issue=replace(issue),
        session=None,
        retry_attempt=1,
        started_at=datetime.now(timezone.utc),
        run_id="queued-replacement-runtime",
    )
    orch._register_running_entry(issue.id, old_entry)
    old_key = orch._termination_owner_key(issue.id, old_entry)

    # _schedule_running_termination publishes its exact key synchronously but
    # the created task cannot take its first turn until this test yields.
    orch._schedule_running_termination(
        issue.id,
        cleanup_workspace=False,
        expected_entry=old_entry,
    )
    assert orch._scheduled_termination_entries.get(old_key) is old_entry
    orch._register_running_entry(issue.id, replacement)
    for _ in range(10):
        if old_key not in orch._scheduled_termination_entries:
            break
        await asyncio.sleep(0)

    assert orch._current_running_entry(issue.id) is replacement
    assert replacement.retirement_pending is False
    assert old_key not in orch._scheduled_termination_entries
    assert orch._terminating_worker_owners == {}


@pytest.mark.asyncio
async def test_scheduled_retirement_creation_failure_releases_exact_key(
    tmp_path,
) -> None:
    """Failure to create the scheduled task cannot leak its strong entry key."""

    orch = _orchestrator(tmp_path)
    issue = _issue()
    worker_task = MagicMock()
    worker_task.done.return_value = True
    entry = RunningEntry(
        worker_task=worker_task,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        run_id="schedule-creation-failure",
    )
    orch._register_running_entry(issue.id, entry)

    with patch(
        "oompah.orchestrator.asyncio.create_task",
        side_effect=RuntimeError("injected task creation failure"),
    ):
        with pytest.raises(RuntimeError, match="injected task creation failure"):
            orch._schedule_running_termination(
                issue.id,
                cleanup_workspace=False,
            )

    assert orch._current_running_entry(issue.id) is entry
    assert orch._scheduled_termination_entries == {}
    assert orch._terminating_worker_owners == {}


@pytest.mark.asyncio
async def test_retirement_child_creation_failure_restores_exact_entry_fence(
    tmp_path,
) -> None:
    """Inner task rejection closes its coroutine and releases all ownership."""

    orch = _orchestrator(tmp_path)
    issue = _issue()
    worker_task = MagicMock()
    worker_task.done.return_value = True
    entry = RunningEntry(
        worker_task=worker_task,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        run_id="retirement-child-creation-failure",
    )
    orch._register_running_entry(issue.id, entry)
    loop = asyncio.get_running_loop()
    rejected_coroutines = []

    def reject_child(coroutine, **_kwargs):
        rejected_coroutines.append(coroutine)
        raise RuntimeError("injected retirement child creation failure")

    with patch.object(loop, "create_task", side_effect=reject_child):
        with pytest.raises(
            RuntimeError,
            match="injected retirement child creation failure",
        ):
            await orch._terminate_running(
                issue.id,
                cleanup_workspace=False,
                expected_entry=entry,
            )

    assert len(rejected_coroutines) == 1
    assert rejected_coroutines[0].cr_frame is None
    assert orch._current_running_entry(issue.id) is entry
    assert entry.retirement_pending is False
    assert orch._terminating_worker_owners == {}
    assert orch._termination_pending_baselines == {}
    assert orch._termination_child_owned_keys == set()


@pytest.mark.asyncio
async def test_concurrent_retirement_parents_release_only_their_owner(
    tmp_path,
) -> None:
    """One parent finishing cannot release a concurrent parent's fence."""

    orch = _orchestrator(tmp_path)
    issue = _issue()
    worker_task = MagicMock()
    worker_task.done.return_value = True
    entry = RunningEntry(
        worker_task=worker_task,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        run_id="concurrent-retirement-runtime",
        authority_revoked=True,
    )
    orch.state.running[issue.id] = entry
    orch.state.claimed.add(issue.id)
    orch.state.claimed_issues[issue.id] = issue
    child_started = asyncio.Event()
    release_child = asyncio.Event()
    child_count = 0

    async def controlled_retirement(
        _issue_id,
        _cleanup_workspace,
        *,
        expected_entry,
        coordinator=None,
        **_kwargs,
    ) -> bool:
        nonlocal child_count
        child_count += 1
        assert expected_entry is entry
        child_started.set()
        await release_child.wait()
        return False

    with patch.object(
        orch,
        "_terminate_running_once",
        side_effect=controlled_retirement,
    ):
        first_parent = asyncio.create_task(
            orch._terminate_running(issue.id, cleanup_workspace=False)
        )
        await child_started.wait()
        second_parent = asyncio.create_task(
            orch._terminate_running(issue.id, cleanup_workspace=False)
        )
        await asyncio.sleep(0)

        owner_key = orch._termination_owner_key(issue.id, entry)
        assert len(orch._terminating_worker_owners[owner_key]) == 2
        # Both parents share one child, while independently retaining the
        # callback-suppression lease until they observe its result.
        await orch._on_worker_exit(
            issue.id,
            "authority_revoked",
            "retirement child still running",
            run_id=entry.run_id,
        )
        assert orch.state.running[issue.id] is entry

        release_child.set()
        assert await first_parent is False
        assert await second_parent is False
        assert child_count == 1

    assert orch._termination_owned(issue.id, entry) is False
    assert orch._termination_pending_baselines == {}
    assert orch._termination_child_owned_keys == set()
    with (
        patch.object(orch, "_managed_processes", return_value={}),
        patch.object(orch, "_notify_observers"),
    ):
        await orch._on_worker_exit(
            issue.id,
            "authority_revoked",
            "all retirement parents finished",
            run_id=entry.run_id,
        )
    assert issue.id not in orch.state.running
    assert issue.id not in orch.state.claimed


@pytest.mark.asyncio
async def test_graceful_restart_cancellation_waits_for_auditor_retirement(
    tmp_path,
) -> None:
    """Restart cancellation cannot detach setup-only auditor recovery."""

    orch = _orchestrator(tmp_path)
    issue = _issue()
    plan = _plan()
    store = _persisted_store(plan)
    worker_release = asyncio.Event()
    provider_release = asyncio.Event()
    worker_task = asyncio.create_task(worker_release.wait())
    provider_start_task = asyncio.create_task(provider_release.wait())
    entry = RunningEntry(
        worker_task=worker_task,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        is_auditor=True,
        audit_id=plan.audit_id,
        audit_attempt_id=plan.attempt_id,
        branch_key=plan.branch_key,
        run_id="cancelled-graceful-audit-retirement",
    )
    entry.provider_start_task = provider_start_task
    entry.provider_admission_generation = orch._provider_admission_generation
    orch.state.running[issue.id] = entry
    orch.state.claimed.add(issue.id)
    orch.state.claimed_issues[issue.id] = issue
    orch._audit_branch_claims[plan.branch_key] = plan.attempt_id

    recovery_started = threading.Event()
    release_recovery = threading.Event()
    real_secure = orch._secure_unadmitted_auditor_exit

    def blocking_secure(recovery_entry, *, reason):
        recovery_started.set()
        assert release_recovery.wait(timeout=3)
        return real_secure(recovery_entry, reason=reason)

    with (
        patch.object(orch, "_audit_store", return_value=store),
        patch.object(
            orch,
            "_secure_unadmitted_auditor_exit",
            side_effect=blocking_secure,
        ),
        patch.object(orch, "_managed_processes", return_value={}),
        patch.object(orch, "_fire_task_cost_record"),
        patch.object(orch, "_fire_telemetry_comment"),
        patch.object(orch, "_remove_audit_workspace"),
    ):
        restart = asyncio.create_task(orch.graceful_restart(drain_timeout_s=0))
        assert await asyncio.to_thread(recovery_started.wait, 3)

        restart.cancel()
        await asyncio.sleep(0)
        assert restart.done() is False
        assert worker_task.done() is False
        assert provider_start_task.done() is False
        assert orch.state.running[issue.id] is entry
        assert entry.provider_start_task is None
        assert entry.provider_admission_generation is None

        release_recovery.set()
        with pytest.raises(asyncio.CancelledError):
            await restart

    assert worker_task.cancelled() is True
    assert provider_start_task.cancelled() is True
    assert issue.id not in orch.state.running
    assert plan.branch_key not in orch._audit_branch_claims
    record = store.document.pending_chain[0]
    assert record.request_state == RequestState.PENDING
    assert record.attempts == []
    assert store.document.attempt_history == []


@pytest.mark.parametrize("conflict", ["replacement", "result", "override"])
def test_unadmitted_rollback_loses_durable_cas_conflicts(
    tmp_path,
    conflict: str,
) -> None:
    """Replacement, result, and owner override authority all beat rollback."""

    orch = _orchestrator(tmp_path)
    issue = _issue()
    plan = _plan()
    store = _persisted_store(plan)
    target = store.document.pending_chain[0]
    attempt = target.attempts[-1]

    if conflict == "replacement":
        replacement = TerminalAuditRecord(
            audit_id="audit-replacement",
            project_id=target.project_id,
            task_id=target.task_id,
            request_state=RequestState.PENDING,
            target_state=target.target_state,
            evidence_fingerprint=EvidenceFingerprint("b" * 64),
            attempts=[],
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        store.document = replace(
            store.document,
            pending_chain=[target, replacement],
        )
    elif conflict == "result":
        verdict_attempt = replace(attempt, verdict=Verdict.PASS)
        store.document = replace(
            store.document,
            pending_chain=[replace(target, attempts=[verdict_attempt])],
            attempt_history=[verdict_attempt],
        )
    else:
        override = OverrideRecord(
            override_id="override-1",
            project_id=target.project_id,
            task_id=target.task_id,
            target_state=target.target_state,
            evidence_fingerprint=target.evidence_fingerprint,
            authorized_by=ContributorIdentity("project-owner", source="github"),
            reason="Owner accepted the exact evidence while launch was pending.",
            created_at=datetime.now(timezone.utc).isoformat(),
        ).to_dict()
        override["applied"] = False
        store.document = replace(
            store.document,
            unknown_fields={
                **store.document.unknown_fields,
                "oompah.terminal_override_records": [override],
            },
        )

    before = store.document.to_dict()
    with patch.object(orch, "_audit_store", return_value=store):
        restored = orch._restore_unadmitted_audit_attempt(
            issue,
            plan.audit_id,
            plan.attempt_id,
        )

    assert restored is UnadmittedAuditRollbackOutcome.SUPERSEDED
    assert store.document.to_dict() == before


def test_unadmitted_rollback_ignores_override_from_older_workflow_revision(
    tmp_path,
) -> None:
    orch = _orchestrator(tmp_path)
    issue = _issue()
    plan = _plan()
    store = _persisted_store(plan)
    target = replace(
        store.document.pending_chain[0],
        workflow_revision="workflow-revision-v2",
    )
    override = OverrideRecord(
        override_id="override-v1",
        project_id=target.project_id,
        task_id=target.task_id,
        target_state=target.target_state,
        evidence_fingerprint=target.evidence_fingerprint,
        authorized_by=ContributorIdentity("project-owner", source="github"),
        reason="Owner accepted the earlier workflow generation.",
        workflow_revision="workflow-revision-v1",
    ).to_dict()
    override["applied"] = True
    store.document = replace(
        store.document,
        pending_chain=[target],
        unknown_fields={
            **store.document.unknown_fields,
            "oompah.terminal_override_records": [override],
        },
    )

    with patch.object(orch, "_audit_store", return_value=store):
        restored = orch._restore_unadmitted_audit_attempt(
            issue,
            plan.audit_id,
            plan.attempt_id,
        )

    assert restored is UnadmittedAuditRollbackOutcome.RESTORED
    current = store.document.pending_chain[0]
    assert current.request_state is RequestState.PENDING
    assert current.attempts == []


def test_ambiguous_unadmitted_cas_is_journaled_and_recovered_after_restart(
    tmp_path,
) -> None:
    """Malformed authority cannot be mistaken for a safe superseding result."""

    first = _orchestrator(tmp_path)
    issue = _issue()
    plan = _plan()
    store = _persisted_store(plan)
    store.document = replace(
        store.document,
        unknown_fields={"oompah.terminal_override_records": "malformed"},
    )
    entry = RunningEntry(
        worker_task=MagicMock(),
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        is_auditor=True,
        audit_id=plan.audit_id,
        audit_attempt_id=plan.attempt_id,
        branch_key=plan.branch_key,
        run_id="ambiguous-audit-cas",
    )
    first._audit_branch_claims[plan.branch_key] = plan.attempt_id

    with patch.object(first, "_audit_store", return_value=store):
        outcome = first._restore_unadmitted_audit_attempt(
            issue,
            plan.audit_id,
            plan.attempt_id,
        )
        secured = first._secure_unadmitted_auditor_exit(
            entry,
            reason="malformed override metadata",
        )

    assert outcome is UnadmittedAuditRollbackOutcome.AMBIGUOUS
    assert secured is True
    assert plan.attempt_id in first._pending_audit_rollbacks
    assert plan.attempt_id in first._durable_audit_rollback_attempt_ids
    assert first._audit_branch_claims[plan.branch_key] == plan.attempt_id
    assert store.document.pending_chain[0].request_state == RequestState.IN_PROGRESS

    store.document = replace(store.document, unknown_fields={})
    replacement = _orchestrator(tmp_path)
    assert plan.attempt_id in replacement._pending_audit_rollbacks
    with patch.object(replacement, "_audit_store", return_value=store):
        replacement._retry_pending_audit_rollbacks()

    assert replacement._pending_audit_rollbacks == {}
    assert plan.branch_key not in replacement._audit_branch_claims
    recovered = store.document.pending_chain[0]
    assert recovered.request_state == RequestState.PENDING
    assert recovered.attempts == []
    assert store.document.attempt_history == []


def test_unadmitted_done_rollback_preserves_later_merged_request_and_budget(
    tmp_path,
) -> None:
    """Canonical Done->Merged chains roll back the exact first audit only."""

    orch = _orchestrator(tmp_path)
    issue = _issue()
    plan = _plan()
    store = _persisted_store(plan)
    done = store.document.pending_chain[0]
    merged = TerminalAuditRecord(
        audit_id="audit-merged",
        project_id=done.project_id,
        task_id=done.task_id,
        request_state=RequestState.PENDING,
        target_state=TargetState.MERGED,
        evidence_fingerprint=done.evidence_fingerprint,
        attempts=[],
        created_at=plan.created_at,
    )
    store.document = replace(store.document, pending_chain=[done, merged])
    orch._terminal_audit_metrics.record_queued(
        done.project_id,
        done.task_id,
        done.audit_id,
    )
    orch._terminal_audit_metrics.record_running(
        done.project_id,
        done.task_id,
        done.audit_id,
        attempts=1,
    )

    with patch.object(orch, "_audit_store", return_value=store):
        restored = orch._restore_unadmitted_audit_attempt(
            issue,
            plan.audit_id,
            plan.attempt_id,
        )

    assert restored is UnadmittedAuditRollbackOutcome.RESTORED
    restored_done, preserved_merged = store.document.pending_chain
    assert restored_done.request_state == RequestState.PENDING
    assert restored_done.attempts == []
    assert preserved_merged == merged
    assert store.document.attempt_history == []


def test_unadmitted_rollback_store_outage_retains_authority_across_restart(
    tmp_path,
) -> None:
    """A metadata outage cannot rotate an unlaunched audit after restart."""

    first = _orchestrator(tmp_path)
    issue = _issue()
    plan = _plan()
    initial = _persisted_store(plan).document
    store = _TransientFailureAuditStore(initial)
    first._audit_branch_claims[plan.branch_key] = plan.attempt_id

    with patch.object(first, "_audit_store", return_value=store):
        restored = first._restore_or_defer_unadmitted_audit_attempt(
            issue,
            plan.audit_id,
            plan.attempt_id,
            plan.branch_key,
            reason="injected pre-launch store outage",
        )

    assert restored is UnadmittedAuditRollbackOutcome.AMBIGUOUS
    assert first._audit_branch_claims[plan.branch_key] == plan.attempt_id
    assert plan.attempt_id in first._pending_audit_rollbacks
    record = store.document.pending_chain[0]
    assert record.request_state == RequestState.IN_PROGRESS
    assert [attempt.attempt_id for attempt in record.attempts] == [plan.attempt_id]

    replacement = _orchestrator(tmp_path)
    assert replacement._audit_branch_claims[plan.branch_key] == plan.attempt_id
    assert plan.attempt_id in replacement._pending_audit_rollbacks
    with patch.object(replacement, "_audit_store", return_value=store):
        replacement._retry_pending_audit_rollbacks()

    assert replacement._pending_audit_rollbacks == {}
    assert plan.branch_key not in replacement._audit_branch_claims
    restored_record = store.document.pending_chain[0]
    assert restored_record.request_state == RequestState.PENDING
    assert restored_record.attempts == []
    assert store.document.attempt_history == []
    metrics = replacement._terminal_audit_metrics.snapshot()
    assert metrics["queued"] == 1
    assert metrics["running"] == 0
    assert replacement._terminal_audit_metrics.pending_entries()[0]["attempts"] == 0

    selector = MagicMock()
    selector.select_candidates.return_value = ([plan.candidate], None)
    lane = AuditorDispatchLane(
        selector,
        max_attempts=1,
        id_factory=lambda: "attempt-after-restart",
    )
    next_plan, reason = lane.plan(
        restored_record,
        contributors=[],
        branch_key=plan.branch_key,
    )
    assert reason is None
    assert next_plan is not None
    assert next_plan.rotation_count == 0


def test_unadmitted_rollback_uses_fallback_when_service_state_save_fails(
    tmp_path,
) -> None:
    """The exact free-attempt owner survives failure of the primary journal."""

    first = _orchestrator(tmp_path)
    issue = _issue()
    plan = _plan()
    store = _TransientFailureAuditStore(_persisted_store(plan).document)
    first._audit_branch_claims[plan.branch_key] = plan.attempt_id

    with (
        patch.object(first, "_audit_store", return_value=store),
        patch.object(first, "_save_state", return_value=False),
    ):
        restored = first._restore_or_defer_unadmitted_audit_attempt(
            issue,
            plan.audit_id,
            plan.attempt_id,
            plan.branch_key,
            reason="metadata and primary journal outage",
        )

    assert restored is UnadmittedAuditRollbackOutcome.AMBIGUOUS
    assert first._audit_rollback_fallback_path.endswith(
        ".unadmitted-audit-rollbacks.json"
    )

    replacement = _orchestrator(tmp_path)
    assert replacement._audit_branch_claims[plan.branch_key] == plan.attempt_id
    assert plan.attempt_id in replacement._pending_audit_rollbacks

    with patch.object(replacement, "_audit_store", return_value=store):
        replacement._retry_pending_audit_rollbacks()

    assert replacement._pending_audit_rollbacks == {}
    assert plan.branch_key not in replacement._audit_branch_claims
    record = store.document.pending_chain[0]
    assert record.request_state == RequestState.PENDING
    assert record.attempts == []
    assert store.document.attempt_history == []

    final_restart = _orchestrator(tmp_path)
    assert final_restart._pending_audit_rollbacks == {}
    assert plan.branch_key not in final_restart._audit_branch_claims


def test_worker_exit_retains_auditor_when_both_rollback_journals_fail(
    tmp_path,
) -> None:
    """Cleanup cannot forget the sole owner of an unpersisted rollback."""

    orch = _orchestrator(tmp_path)
    issue = _issue()
    plan = _plan()
    store = _TransientFailureAuditStore(_persisted_store(plan).document)
    worker_task = MagicMock()
    worker_task.done.return_value = True
    entry = RunningEntry(
        worker_task=worker_task,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        is_auditor=True,
        audit_id=plan.audit_id,
        audit_attempt_id=plan.attempt_id,
        branch_key=plan.branch_key,
        run_id="unpersisted-audit-exit",
    )
    orch.state.running[issue.id] = entry
    orch.state.claimed.add(issue.id)
    orch.state.claimed_issues[issue.id] = issue
    orch._audit_branch_claims[plan.branch_key] = plan.attempt_id

    with (
        patch.object(orch, "_audit_store", return_value=store),
        patch.object(orch, "_save_audit_rollback_fallback", return_value=False),
        patch.object(orch, "_save_state", return_value=False),
    ):
        asyncio.run(
            orch._on_worker_exit(
                issue.id,
                "interrupted",
                "provider did not start",
                run_id=entry.run_id,
            )
        )

    assert orch.state.running[issue.id] is entry
    assert entry.retirement_pending is True
    assert orch._audit_rollback_persistence_failed is True
    assert orch._quiesced is True
    assert orch._dispatch_is_blocked(issue) is True
    with (
        patch.object(orch, "_save_audit_rollback_fallback", return_value=False),
        patch.object(orch, "_save_state", return_value=False),
    ):
        assert orch.unpause() is False
    assert plan.attempt_id in orch._pending_audit_rollbacks
    assert plan.attempt_id not in orch._durable_audit_rollback_attempt_ids
    assert orch._audit_branch_claims[plan.branch_key] == plan.attempt_id
    persisted = store.document.pending_chain[0]
    assert persisted.request_state == RequestState.IN_PROGRESS
    assert [attempt.attempt_id for attempt in persisted.attempts] == [
        plan.attempt_id
    ]


@pytest.mark.asyncio
async def test_cancelled_stop_owner_is_replaced_without_losing_live_rollback_owner(
    tmp_path,
) -> None:
    """The process stop boundary survives a transient dual-journal outage."""

    orch = _orchestrator(tmp_path)
    issue = _issue()
    plan = _plan()
    store = _TransientFailureAuditStore(_persisted_store(plan).document)
    worker_release = asyncio.Event()
    worker_task = asyncio.create_task(worker_release.wait())
    entry = RunningEntry(
        worker_task=worker_task,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        is_auditor=True,
        audit_id=plan.audit_id,
        audit_attempt_id=plan.attempt_id,
        branch_key=plan.branch_key,
        run_id="ordinary-stop-audit-owner",
    )
    orch.state.running[issue.id] = entry
    orch.state.claimed.add(issue.id)
    orch.state.claimed_issues[issue.id] = issue
    orch._audit_branch_claims[plan.branch_key] = plan.attempt_id

    fallback_calls = 0
    state_calls = 0
    real_fallback_save = orch._save_audit_rollback_fallback
    real_state_save = orch._save_state

    def fail_first_fallback(snapshot):
        nonlocal fallback_calls
        fallback_calls += 1
        if fallback_calls == 1:
            return False
        return real_fallback_save(snapshot)

    def fail_first_state(**updates):
        nonlocal state_calls
        if "terminal_audit_unadmitted_rollbacks" in updates:
            state_calls += 1
            if state_calls == 1:
                return False
        return real_state_save(**updates)

    retry_observations: list[tuple[bool, bool, bool, bool]] = []
    original_sleep = asyncio.sleep

    async def observe_retry_delay(_delay: float) -> None:
        retry_observations.append(
            (
                orch.state.running.get(issue.id) is entry,
                worker_task.done(),
                orch._quiesced,
                orch._stopping,
            )
        )
        await original_sleep(0)

    cancelled_stop_owner: ConcurrentFuture[None] = ConcurrentFuture()
    cancelled_stop_owner.cancel()
    from oompah.server import _await_fail_closed_orchestrator_stop

    with (
        patch.object(orch, "_audit_store", return_value=store),
        patch.object(
            orch,
            "_save_audit_rollback_fallback",
            side_effect=fail_first_fallback,
        ),
        patch.object(orch, "_save_state", side_effect=fail_first_state),
        patch.object(orch, "_managed_processes", return_value={}),
        patch.object(orch, "_fire_task_cost_record"),
        patch.object(orch, "_fire_telemetry_comment"),
        patch.object(orch, "_remove_audit_workspace"),
        patch.object(
            orch,
            "stop_threadsafe",
            return_value=cancelled_stop_owner,
        ),
        patch("oompah.orchestrator.asyncio.sleep", side_effect=observe_retry_delay),
    ):
        await _await_fail_closed_orchestrator_stop(orch)

    assert retry_observations == [(True, False, True, False)]
    assert fallback_calls >= 2
    assert state_calls >= 2
    assert worker_task.cancelled() is True
    assert issue.id not in orch.state.running
    assert issue.id not in orch.state.claimed
    assert plan.branch_key not in orch._audit_branch_claims
    assert orch._stopping is True
    recovered = store.document.pending_chain[0]
    assert recovered.request_state == RequestState.PENDING
    assert recovered.attempts == []
    assert store.document.attempt_history == []


def test_dual_journal_failure_can_recover_authority_across_restart(tmp_path) -> None:
    """Recovered storage can durably carry the exact free attempt to restart."""

    first = _orchestrator(tmp_path)
    issue = _issue()
    plan = _plan()
    store = _TransientFailureAuditStore(_persisted_store(plan).document)
    entry = RunningEntry(
        worker_task=MagicMock(),
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        is_auditor=True,
        audit_id=plan.audit_id,
        audit_attempt_id=plan.attempt_id,
        branch_key=plan.branch_key,
        run_id="recoverable-audit-exit",
    )
    first._audit_branch_claims[plan.branch_key] = plan.attempt_id

    with (
        patch.object(first, "_audit_store", return_value=store),
        patch.object(first, "_save_audit_rollback_fallback", return_value=False),
        patch.object(first, "_save_state", return_value=False),
    ):
        assert first._secure_unadmitted_auditor_exit(
            entry,
            reason="injected total journal outage",
        ) is False

    assert first._audit_rollback_persistence_failed is True
    assert first._persist_pending_audit_rollbacks() is True
    assert first._audit_rollback_persistence_failed is False
    assert plan.attempt_id in first._durable_audit_rollback_attempt_ids

    replacement = _orchestrator(tmp_path)
    assert plan.attempt_id in replacement._pending_audit_rollbacks
    assert replacement._audit_branch_claims[plan.branch_key] == plan.attempt_id
    with patch.object(replacement, "_audit_store", return_value=store):
        replacement._retry_pending_audit_rollbacks()

    assert replacement._pending_audit_rollbacks == {}
    assert plan.branch_key not in replacement._audit_branch_claims
    recovered = store.document.pending_chain[0]
    assert recovered.request_state == RequestState.PENDING
    assert recovered.attempts == []
    assert store.document.attempt_history == []


def test_snapshot_reconciles_auditor_metrics_from_retry_attempt(tmp_path) -> None:
    """Running audit metrics read the real RunningEntry retry field."""

    orch = _orchestrator(tmp_path)
    issue = _issue()
    plan = _plan()
    worker_task = MagicMock()
    worker_task.done.return_value = False
    orch.state.running[issue.id] = RunningEntry(
        worker_task=worker_task,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=2,
        started_at=datetime.now(timezone.utc),
        is_auditor=True,
        audit_id=plan.audit_id,
        audit_attempt_id=plan.attempt_id,
        run_id="retry-metric-run",
    )

    snapshot = orch.get_snapshot()["terminal_audit"]

    assert snapshot["running"] == 1
    metric_key = (issue.project_id, issue.identifier, plan.audit_id)
    assert orch._terminal_audit_metrics._running[metric_key]["attempts"] == 2


def test_two_audits_survive_canonical_restart_and_admit_once_on_new_orchestrator(
    tmp_path,
) -> None:
    """A fresh scheduler recovers durable audits once across repeated scans."""

    issues = [
        _issue(),
        replace(
            _issue(),
            id="issue-2",
            identifier="OOMPAH-855",
            branch_name="epic-branch-2",
        ),
    ]
    plans = [
        _plan(),
        replace(
            _plan(),
            audit_id="audit-2",
            task_id="OOMPAH-855",
            attempt_id="attempt-2",
            branch_key="epic-branch-2",
        ),
    ]
    tracker = _DurableAuditTracker(issues)
    project = SimpleNamespace(
        id="project-1",
        paused=False,
        to_safe_dict=lambda: {"id": "project-1", "paused": False},
    )
    project_store = MagicMock()
    project_store.list_all.return_value = [project]
    project_store.get.return_value = project
    metadata_lock = threading.RLock()
    project_store.project_write_lock.side_effect = lambda _project_id: metadata_lock
    durable_store = TerminalAuditMetadataStore(
        tracker,
        project_store,
        "project-1",
    )
    for issue, plan in zip(issues, plans, strict=True):
        pending = TerminalAuditRecord(
            audit_id=plan.audit_id,
            project_id="project-1",
            task_id=issue.identifier,
            request_state=RequestState.PENDING,
            target_state=plan.target_state,
            evidence_fingerprint=plan.evidence_fingerprint,
            attempts=[],
            created_at=plan.created_at,
        )
        persisted = AuditorDispatchLane.persist_plan(pending, plan)
        durable_store.write(
            issue.identifier,
            TerminalAuditMetadata(
                pending_chain=[persisted],
                attempt_history=[persisted.attempts[-1]],
            ),
        )

    old = Orchestrator(
        config=ServiceConfig(duplicate_preflight_max_agents=0),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        state_path=str(tmp_path / "state.json"),
    )
    for index, (issue, plan) in enumerate(zip(issues, plans, strict=True), start=1):
        worker_task = MagicMock()
        worker_task.done.return_value = True
        old.state.running[issue.id] = RunningEntry(
            worker_task=worker_task,
            identifier=issue.identifier,
            issue=issue,
            session=None,
            retry_attempt=0,
            started_at=datetime.now(timezone.utc),
            is_auditor=True,
            audit_id=plan.audit_id,
            audit_attempt_id=plan.attempt_id,
            branch_key=plan.branch_key,
            run_id=f"old-audit-run-{index}",
        )
        old.state.claimed.add(issue.id)
        old.state.claimed_issues[issue.id] = issue
        old._audit_branch_claims[plan.branch_key] = plan.attempt_id
        assert old._provider_launch_blocked(issue, f"old-audit-run-{index}") is False

    original_orchestrator = server_module._orchestrator
    client = TestClient(server_module.app)
    try:
        server_module._orchestrator = old
        claimed = client.post(
            "/api/v1/orchestrator/restart",
            json={"claim_only": True},
        )
        request_id = claimed.json()["restart_request_id"]
        # Exercise the actual restart cutoff with both setup-only RunningEntry
        # objects still published.  The restart itself, not a manually-invoked
        # worker-exit callback, must recover their audit authority.
        with patch.object(old, "_tracker_for_issue", return_value=tracker):
            asyncio.run(
                old.graceful_restart(
                    drain_timeout_s=0,
                    request_id=request_id,
                )
            )
    finally:
        server_module._orchestrator = original_orchestrator

    assert old.wants_restart is True
    for issue in issues:
        recovered = durable_store.read(issue.identifier)
        assert recovered.pending_chain[0].request_state == RequestState.PENDING
        assert recovered.pending_chain[0].attempts == []

    fresh = Orchestrator(
        config=ServiceConfig(duplicate_preflight_max_agents=0),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        state_path=str(tmp_path / "state.json"),
    )
    assert fresh is not old
    assert fresh._paused is False
    selector = MagicMock()
    selector.select_candidates.return_value = ([plans[0].candidate], None)
    provider_release = asyncio.Event()
    provider_started = {issue.identifier: asyncio.Event() for issue in issues}
    provider_start_count = {issue.identifier: 0 for issue in issues}

    async def _exercise_fresh_scheduler() -> None:
        async def _provider_transport(identifier: str) -> None:
            provider_start_count[identifier] += 1
            provider_started[identifier].set()
            await provider_release.wait()

        async def _run_auditor(
            issue: Issue,
            _attempt: int | None,
            _profile,
            *,
            run_id: str | None = None,
            auditor_plan: AuditDispatchPlan | None = None,
        ) -> None:
            assert auditor_plan is not None
            assert fresh._provider_launch_blocked(issue, run_id) is False
            task = fresh._publish_provider_start(
                issue,
                run_id,
                lambda: _provider_transport(issue.identifier),
            )
            assert task is not None
            await task

        with (
            patch.object(fresh, "_tracker_for_project", return_value=tracker),
            patch.object(fresh, "_tracker_for_issue", return_value=tracker),
            patch.object(
                fresh,
                "_prepare_audit_selector",
                new=AsyncMock(return_value=(selector, None)),
            ),
            patch.object(
                fresh,
                "_terminal_audit_validation_configuration_error",
                return_value=None,
            ),
            patch.object(fresh, "_clear_terminal_audit_validation_configuration"),
            patch.object(fresh, "_revisionless_archive_evidence", return_value=None),
            patch.object(
                fresh,
                "_bind_audit_record_revision",
                side_effect=lambda _issue, record: record,
            ),
            patch.object(fresh, "_run_worker", side_effect=_run_auditor),
            patch.object(fresh, "_post_comment"),
            patch.object(fresh, "_announce_coordination_start"),
        ):
            await fresh._dispatch_audit_lane()
            await asyncio.gather(
                *(
                    asyncio.wait_for(event.wait(), timeout=3)
                    for event in provider_started.values()
                )
            )
            # This is a new durable scan, not a replay of manually constructed
            # plans.  Active attempt IDs must make both rows ineligible.
            await fresh._dispatch_audit_lane()
            assert provider_start_count == {
                "OOMPAH-854": 1,
                "OOMPAH-855": 1,
            }
            provider_release.set()
            await asyncio.gather(
                *(entry.worker_task for entry in fresh.state.running.values())
            )

    asyncio.run(_exercise_fresh_scheduler())

    assert provider_start_count == {"OOMPAH-854": 1, "OOMPAH-855": 1}
    for issue in issues:
        persisted = durable_store.read(issue.identifier).pending_chain[0]
        assert persisted.request_state == RequestState.IN_PROGRESS
        assert len(persisted.attempts) == 1


def test_fresh_startup_from_persisted_pause_rolls_auditor_back_to_queue(
    tmp_path,
) -> None:
    """A new process honors persisted pause before auditor admission."""

    first = _orchestrator(tmp_path)
    first.pause()
    assert first._load_state()["paused"] is True

    fresh = _orchestrator(tmp_path)
    assert fresh is not first
    assert fresh._paused is True
    assert fresh._quiesced is False
    issue = _issue()
    plan = _plan()
    store = _persisted_store(plan)
    fresh._audit_branch_claims[plan.branch_key] = plan.attempt_id
    _record_queued_metric(fresh, plan)

    with (
        patch.object(fresh, "_audit_store", return_value=store),
        patch.object(fresh, "_run_worker", new_callable=AsyncMock) as worker,
    ):
        admitted = asyncio.run(
            fresh._dispatch(issue, 0, auditor_plan=plan),
        )

    assert admitted is False
    worker.assert_not_awaited()
    assert issue.id not in fresh.state.running
    assert plan.branch_key not in fresh._audit_branch_claims
    record = store.document.pending_chain[0]
    assert record.request_state == RequestState.PENDING
    assert record.attempts == []
    assert store.document.attempt_history == []
    audit_metrics = fresh.get_snapshot()["terminal_audit"]
    assert audit_metrics["queued"] == 1
    assert audit_metrics["running"] == 0
