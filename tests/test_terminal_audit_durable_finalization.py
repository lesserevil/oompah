"""End-to-end restart coverage for durable terminal-audit finalization."""

from __future__ import annotations

import asyncio
import copy
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from oompah.models import Issue
from oompah.orchestrator import Orchestrator
from oompah.roles import Candidate
from oompah.statuses import IN_VALIDATION, MERGED
from oompah.terminal_audit import (
    AuditAttempt,
    ContributorIdentity,
    EvidenceFingerprint,
    RequestState,
    TargetState,
    TerminalAuditRecord,
    Verdict,
)
from oompah.terminal_audit_metadata import TerminalAuditMetadataStore
from oompah.terminal_audit_workflow import TerminalAuditWorkflow
from oompah.terminal_transition_coordinator import (
    AuditResult,
    ResultOutcome,
    TerminalTransitionCoordinator,
)
from oompah.workflow_jobs import WorkflowJobState, WorkflowJobStore
from oompah.workflow_jobs import WorkflowFailureCategory


PROJECT_ID = "proj-durable"
TASK_ID = "TASK-1"


class _ProjectLocks:
    def __init__(self) -> None:
        self._lock = threading.RLock()

    def project_write_lock(self, _project_id: str) -> threading.RLock:
        return self._lock


class _Tracker:
    def __init__(self) -> None:
        self.metadata: dict[str, dict] = {}
        self.status = "In Review"

    def get_metadata(self, identifier: str) -> dict:
        return copy.deepcopy(self.metadata.get(identifier, {}))

    def set_metadata_field(self, identifier: str, key: str, value) -> None:
        self.metadata.setdefault(identifier, {})[key] = copy.deepcopy(value)

    def update_issue(self, _identifier: str, **changes) -> None:
        if "status" in changes:
            self.status = changes["status"]

    def add_comment(self, _identifier: str, _text: str, author: str = "oompah") -> dict:
        return {"author": author}

    def fetch_issue_detail(self, identifier: str) -> Issue:
        return Issue(
            id=identifier,
            identifier=identifier,
            title="Durable finalization",
            state=self.status,
            project_id=PROJECT_ID,
        )

    def fetch_issue_states_by_ids(self, issue_ids: list[str]) -> list[Issue]:
        return [self.fetch_issue_detail(identifier) for identifier in issue_ids]


def _result(record, attempt_id: str) -> AuditResult:
    return AuditResult(
        audit_id=record.audit_id,
        target_state=record.target_state,
        evidence_fingerprint=record.evidence_fingerprint,
        verdict=Verdict.PASS,
        message="exact PASS",
        attempt_id=attempt_id,
    )


def _orchestrator(
    tracker: _Tracker,
    coordinator: TerminalTransitionCoordinator,
    store: WorkflowJobStore,
    workflow: TerminalAuditWorkflow,
) -> Orchestrator:
    orchestrator = Orchestrator.__new__(Orchestrator)
    orchestrator.workflow_job_store = store
    orchestrator.terminal_audit_workflow = workflow
    orchestrator.terminal_transition_coordinator = coordinator
    orchestrator._running_values_snapshot = lambda: []
    orchestrator._tracker_for_project = lambda _project_id: tracker
    orchestrator._record_audit_outcome_ownership = MagicMock()
    return orchestrator


def test_done_to_merged_survives_pre_apply_crash_and_one_provider_retry(
    tmp_path,
) -> None:
    tracker = _Tracker()
    locks = _ProjectLocks()
    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=locks,
        post_comments=False,
    )
    fingerprint = EvidenceFingerprint("a" * 64)
    issue = tracker.fetch_issue_detail(TASK_ID)
    staged = asyncio.run(
        coordinator.request_transition(
            issue,
            TargetState.MERGED,
            ContributorIdentity("worker", "oompah"),
            PROJECT_ID,
            fingerprint,
        )
    )
    assert staged.queued_targets == [TargetState.DONE, TargetState.MERGED]
    assert tracker.status == IN_VALIDATION

    metadata = TerminalAuditMetadataStore(tracker, locks, PROJECT_ID)
    done_record, merged_record = metadata.read(TASK_ID).pending_chain
    db_path = str(tmp_path / "workflow.sqlite3")
    store = WorkflowJobStore(db_path)
    workflow = TerminalAuditWorkflow(store, retry_delay_seconds=0)
    done_job = workflow.start(
        done_record,
        attempt_id="done-attempt-1",
        candidate=Candidate("provider-a", "model-a"),
    )
    assert done_job is not None
    workflow.mark_finalizing(
        done_job,
        done_record,
        result=_result(done_record, "done-attempt-1"),
        attempt_id="done-attempt-1",
        lease_token=done_job.lease_token,
    )

    # Crash before coordinator application: reopen both durable components
    # and let the replay lane consume the exact typed result.
    store.close()
    reopened_store = WorkflowJobStore(db_path)
    reopened_workflow = TerminalAuditWorkflow(reopened_store, retry_delay_seconds=0)
    orchestrator = _orchestrator(
        tracker, coordinator, reopened_store, reopened_workflow
    )
    assert asyncio.run(orchestrator._replay_terminal_audit_finalizations()) == 1
    assert tracker.status == IN_VALIDATION
    assert (
        reopened_store.list_jobs(task_id=TASK_ID)[0].state is WorkflowJobState.COMPLETED
    )

    # The Merged target starts, is killed once before producing a result, and
    # is recovered as exactly one fresh provider attempt.
    merged_record = metadata.read(TASK_ID).pending_chain[1]
    first_merge_job = reopened_workflow.start(
        merged_record,
        attempt_id="merge-attempt-1",
        candidate=Candidate("provider-a", "model-a"),
    )
    assert first_merge_job is not None
    reopened_workflow.recover(merged_record, active_attempt_ids=set())
    second_merge_job = reopened_workflow.start(
        merged_record,
        attempt_id="merge-attempt-2",
        candidate=Candidate("provider-b", "model-b"),
    )
    assert second_merge_job is not None
    assert second_merge_job.attempts == 2
    finalizing = reopened_workflow.mark_finalizing(
        second_merge_job,
        merged_record,
        result=_result(merged_record, "merge-attempt-2"),
        attempt_id="merge-attempt-2",
        lease_token=second_merge_job.lease_token,
    )

    # Crash after coordinator application but before workflow acknowledgement.
    applied = asyncio.run(
        coordinator.apply_audit_result(
            tracker.fetch_issue_detail(TASK_ID),
            _result(merged_record, "merge-attempt-2"),
            PROJECT_ID,
        )
    )
    assert applied.success and applied.applied_status == MERGED
    assert reopened_store.get(finalizing.job_id).state is WorkflowJobState.RUNNING
    assert asyncio.run(orchestrator._replay_terminal_audit_finalizations()) == 1

    completed = reopened_store.get(finalizing.job_id)
    assert completed.state is WorkflowJobState.COMPLETED
    assert completed.result_transition["idempotent"] is True
    assert tracker.status == MERGED
    assert all(
        record.request_state is RequestState.COMPLETED
        for record in metadata.read(TASK_ID).pending_chain
    )
    reopened_store.close()


def test_structured_nonterminal_outcome_requeues_instead_of_completing(
    tmp_path,
) -> None:
    store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    workflow = TerminalAuditWorkflow(store, retry_delay_seconds=0)
    record = SimpleNamespace(
        audit_id="audit-1",
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        target_state=TargetState.DONE,
        evidence_fingerprint=EvidenceFingerprint("b" * 64),
        request_state=RequestState.PENDING,
    )
    job = workflow.start(
        record,
        attempt_id="attempt-1",
        candidate=Candidate("provider-a", "model-a"),
    )
    assert job is not None
    result = _result(record, "attempt-1")
    finalizing = workflow.mark_finalizing(
        job,
        record,
        result=result,
        attempt_id="attempt-1",
        lease_token=job.lease_token,
    )
    orchestrator = Orchestrator.__new__(Orchestrator)
    orchestrator.terminal_audit_workflow = workflow

    orchestrator._finish_terminal_audit_workflow(
        Issue(id=TASK_ID, identifier=TASK_ID, title="Task"),
        result,
        ResultOutcome(success=True, audit_id="audit-1", applied_status=None),
        finalizing,
    )

    assert store.get(job.job_id).state is WorkflowJobState.RETRY_WAIT
    store.close()


def test_revoked_replacement_result_cancels_exact_finalization(tmp_path) -> None:
    store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    workflow = TerminalAuditWorkflow(store, retry_delay_seconds=0)
    record = TerminalAuditRecord(
        audit_id="audit-old",
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        target_state=TargetState.DONE,
        evidence_fingerprint=EvidenceFingerprint("c" * 64),
        request_state=RequestState.PENDING,
    )
    job = workflow.start(
        record,
        attempt_id="attempt-old",
        candidate=Candidate("provider-a", "model-a"),
    )
    assert job is not None
    audit_result = _result(record, "attempt-old")
    finalizing = workflow.mark_finalizing(
        job,
        record,
        result=audit_result,
        attempt_id="attempt-old",
        lease_token=job.lease_token,
    )
    orchestrator = Orchestrator.__new__(Orchestrator)
    orchestrator.terminal_audit_workflow = workflow

    orchestrator._finish_terminal_audit_workflow(
        Issue(id=TASK_ID, identifier=TASK_ID, title="Task"),
        audit_result,
        ResultOutcome(
            success=False,
            audit_id="audit-old",
            reason="evidence fingerprint does not match audit",
        ),
        finalizing,
    )

    assert store.get(job.job_id).state is WorkflowJobState.CANCELLED
    store.close()


def test_callback_requires_exact_running_entry_and_lease_identity(tmp_path) -> None:
    store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    workflow = TerminalAuditWorkflow(store)
    record = TerminalAuditRecord(
        audit_id="audit-1",
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        target_state=TargetState.DONE,
        evidence_fingerprint=EvidenceFingerprint("f" * 64),
        request_state=RequestState.PENDING,
    )
    job = workflow.start(
        record,
        attempt_id="attempt-1",
        candidate=Candidate("provider-a", "model-a"),
    )
    assert job is not None
    issue = Issue(
        id=TASK_ID,
        identifier=TASK_ID,
        title="Task",
        state=IN_VALIDATION,
        project_id=PROJECT_ID,
    )
    entry = SimpleNamespace(
        is_auditor=True,
        audit_id="audit-1",
        audit_attempt_id="attempt-1",
        audit_workflow_job_id=job.job_id,
        audit_workflow_lease_token=job.lease_token,
    )
    orchestrator = Orchestrator.__new__(Orchestrator)
    orchestrator.workflow_job_store = store
    orchestrator.terminal_audit_workflow = workflow
    orchestrator._current_running_entry = lambda _issue_id: entry

    late = _result(record, "attempt-late")
    assert orchestrator._begin_terminal_audit_finalization(issue, late) is None
    assert store.get(job.job_id).state is WorkflowJobState.RUNNING
    replacement = AuditResult(
        audit_id="audit-1",
        target_state=TargetState.MERGED,
        evidence_fingerprint=record.evidence_fingerprint,
        verdict=Verdict.PASS,
        attempt_id="attempt-1",
    )
    assert orchestrator._begin_terminal_audit_finalization(issue, replacement) is None
    assert store.get(job.job_id).phase == "running"

    finalizing = orchestrator._begin_terminal_audit_finalization(
        issue, _result(record, "attempt-1")
    )
    assert finalizing is not None
    assert finalizing.phase == "finalizing"
    store.close()


def test_dynamic_policy_denial_durably_retries_only_its_attempt(tmp_path) -> None:
    store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    workflow = TerminalAuditWorkflow(store, retry_delay_seconds=0)
    fingerprint = EvidenceFingerprint("d" * 64)
    attempt = AuditAttempt(
        attempt_id="attempt-1",
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.IN_PROGRESS,
        provider_id="provider-a",
        model="model-a",
    )
    record = TerminalAuditRecord(
        audit_id="audit-1",
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.IN_PROGRESS,
        attempts=[attempt],
    )
    job = workflow.start(
        record,
        attempt_id="attempt-1",
        candidate=Candidate("provider-a", "model-a"),
    )
    assert job is not None
    issue = Issue(
        id=TASK_ID,
        identifier=TASK_ID,
        title="Task",
        state=IN_VALIDATION,
        project_id=PROJECT_ID,
    )
    entry = SimpleNamespace(
        issue=issue,
        identifier=TASK_ID,
        audit_id="audit-1",
        audit_attempt_id="attempt-1",
        audit_workflow_job_id=job.job_id,
        audit_workflow_lease_token=job.lease_token,
    )
    audit_store = MagicMock()
    audit_store.read.return_value = SimpleNamespace(pending_chain=[record])
    orchestrator = Orchestrator.__new__(Orchestrator)
    orchestrator.workflow_job_store = store
    orchestrator.terminal_audit_workflow = workflow
    orchestrator._backoff_delay = lambda _attempt: 0

    with (
        patch.object(orchestrator, "_audit_store", return_value=audit_store),
        patch.object(orchestrator, "_audit_update_record", return_value=True),
    ):
        assert (
            orchestrator._finish_audit_attempt(
                entry, "auditor_policy_denial_exhausted", "dynamic command denied"
            )
            is True
        )

    retried = store.get(job.job_id)
    assert retried.state is WorkflowJobState.RETRY_WAIT
    assert retried.failure_category is WorkflowFailureCategory.POLICY
    store.close()


def test_completed_result_is_acknowledged_during_ordinary_worker_exit(tmp_path) -> None:
    store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    workflow = TerminalAuditWorkflow(store)
    fingerprint = EvidenceFingerprint("e" * 64)
    record = TerminalAuditRecord(
        audit_id="audit-1",
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.IN_PROGRESS,
    )
    job = workflow.start(
        record,
        attempt_id="attempt-1",
        candidate=Candidate("provider-a", "model-a"),
    )
    assert job is not None
    finalizing = workflow.mark_finalizing(
        job,
        record,
        result=_result(record, "attempt-1"),
        attempt_id="attempt-1",
        lease_token=job.lease_token,
    )
    completed_record = TerminalAuditRecord(
        audit_id=record.audit_id,
        project_id=record.project_id,
        task_id=record.task_id,
        target_state=record.target_state,
        evidence_fingerprint=record.evidence_fingerprint,
        request_state=RequestState.COMPLETED,
    )
    issue = Issue(
        id=TASK_ID,
        identifier=TASK_ID,
        title="Task",
        state="Done",
        project_id=PROJECT_ID,
    )
    entry = SimpleNamespace(
        issue=issue,
        identifier=TASK_ID,
        audit_id="audit-1",
        audit_attempt_id="attempt-1",
        audit_workflow_job_id=finalizing.job_id,
        audit_workflow_lease_token=finalizing.lease_token,
    )
    audit_store = MagicMock()
    audit_store.read.return_value = SimpleNamespace(pending_chain=[completed_record])
    orchestrator = Orchestrator.__new__(Orchestrator)
    orchestrator.workflow_job_store = store
    orchestrator.terminal_audit_workflow = workflow

    with patch.object(orchestrator, "_audit_store", return_value=audit_store):
        assert orchestrator._finish_audit_attempt(entry, "terminated", None) is False

    assert store.get(job.job_id).state is WorkflowJobState.COMPLETED
    store.close()


def test_finalization_replay_precedes_pause_and_capacity_gates() -> None:
    orchestrator = Orchestrator.__new__(Orchestrator)
    orchestrator._audit_metrics = {}
    orchestrator._replay_terminal_audit_finalizations = AsyncMock(return_value=1)
    orchestrator._dispatch_is_blocked = MagicMock(return_value=True)
    orchestrator._is_rate_limited = MagicMock(return_value=False)

    result = asyncio.run(orchestrator._dispatch_audit_lane())

    assert result == {"audit_dispatch": 0.0, "audit_scan": 0.0}
    orchestrator._replay_terminal_audit_finalizations.assert_awaited_once()
    assert orchestrator._audit_metrics["finalizations_replayed"] == 1
