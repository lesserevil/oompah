"""Regression coverage for terminal-audit workspace and exhaustion routing."""

from __future__ import annotations

import asyncio
import copy
import threading
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from oompah.archived_evidence_collector import SafetyFailureMode
from oompah.models import Issue
from oompah.orchestrator import Orchestrator, _AuditCandidateScan
from oompah.projects import ProjectError
from oompah.roles import Candidate
from oompah.terminal_audit import (
    AuditAttempt,
    EvidenceFingerprint,
    FailureClassification,
    RequestState,
    TargetState,
    TerminalAuditRecord,
    Verdict,
    compute_issue_evidence_fingerprint,
)
from oompah.terminal_audit_metadata import (
    METADATA_KEY,
    TerminalAuditMetadata,
    TerminalAuditMetadataStore,
)
from oompah.terminal_audit_workflow import TerminalAuditWorkflow
from oompah.workflow_jobs import WorkflowJobState, WorkflowJobStore


def _record(*, infrastructure_attempts: bool) -> TerminalAuditRecord:
    fingerprint = EvidenceFingerprint("a" * 64)
    attempts = (
        [
            AuditAttempt(
                attempt_id="attempt-1",
                target_state=TargetState.ARCHIVED,
                evidence_fingerprint=fingerprint,
                request_state=RequestState.PENDING,
                failure_classification=FailureClassification.INFRASTRUCTURE_ERROR,
                failure_reason=(
                    "git worktree add failed: invalid reference: "
                    "origin/epic-EXOCOMP-2"
                ),
                ended_at="2026-07-31T00:01:00+00:00",
            )
        ]
        if infrastructure_attempts
        else []
    )
    return TerminalAuditRecord(
        audit_id="audit-1",
        project_id="proj-1",
        task_id="TASK-1",
        target_state=TargetState.ARCHIVED,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.PENDING,
        attempts=attempts,
        previous_state="Merged",
    )


def _orchestrator() -> Orchestrator:
    orchestrator = Orchestrator.__new__(Orchestrator)
    # The dispatch lane retries a durable, pre-admission rollback journal
    # before inspecting records.  This fixture deliberately bypasses
    # ``Orchestrator.__init__`` so model the empty recovered-journal state
    # explicitly rather than skipping that lifecycle fence.
    orchestrator._audit_rollback_persistence_failed = False
    orchestrator._audit_rollback_lock = threading.RLock()
    orchestrator._pending_audit_rollbacks = {}
    orchestrator._maintenance_cursors = {}
    # The fixture bypasses Orchestrator.__init__, so model the service-state
    # transaction lock required by durable maintenance cursor updates.
    orchestrator._state_io_lock = threading.RLock()
    orchestrator._save_state = MagicMock(return_value=True)
    orchestrator.terminal_audit_workflow = MagicMock()
    orchestrator.terminal_audit_workflow.finalizing_jobs.return_value = []
    orchestrator.terminal_transition_coordinator = SimpleNamespace(
        apply_audit_result=AsyncMock(
            return_value=SimpleNamespace(success=True, applied_status="Needs Human")
        )
    )
    orchestrator._record_audit_outcome_ownership = MagicMock()
    orchestrator._audit_reservation_key_for_issue = MagicMock(
        return_value="audit-reservation-key"
    )
    orchestrator._reconcile_and_release_audit_budget = MagicMock(return_value=True)
    orchestrator._reconcile_audit_budget_reservations = MagicMock()
    orchestrator._audit_metrics = {
        "dispatch_count": 0,
        "rotation_count": 0,
        "exhaustion_count": 0,
        "in_progress_count": 0,
        "last_error": None,
    }
    return orchestrator


def test_workspace_failure_exhaustion_is_not_reported_as_no_auditor() -> None:
    orchestrator = _orchestrator()
    issue = Issue(
        id="TASK-1",
        identifier="TASK-1",
        title="Task",
        project_id="proj-1",
    )

    asyncio.run(
        orchestrator._route_no_auditor(
            issue,
            _record(infrastructure_attempts=True),
            "Audit reached the maximum of 3 attempts.",
        )
    )

    result = orchestrator.terminal_transition_coordinator.apply_audit_result.await_args.args[1]
    assert result.verdict == Verdict.NEEDS_HUMAN
    assert result.failure_classification == FailureClassification.INFRASTRUCTURE_ERROR
    assert "rearm this terminal audit" in result.message
    assert "move the task back to Open" not in result.message
    orchestrator._audit_reservation_key_for_issue.assert_called_once_with(issue)
    orchestrator._reconcile_and_release_audit_budget.assert_called_once_with(
        "audit-reservation-key"
    )


def test_genuine_candidate_exhaustion_remains_no_auditor() -> None:
    orchestrator = _orchestrator()
    issue = Issue(
        id="TASK-1",
        identifier="TASK-1",
        title="Task",
        project_id="proj-1",
    )

    asyncio.run(
        orchestrator._route_no_auditor(
            issue,
            _record(infrastructure_attempts=False),
            "Auditor role has no candidates.",
        )
    )

    result = orchestrator.terminal_transition_coordinator.apply_audit_result.await_args.args[1]
    assert result.verdict == Verdict.FAIL
    assert result.failure_classification == FailureClassification.NO_AUDITOR
    orchestrator._audit_reservation_key_for_issue.assert_called_once_with(issue)
    orchestrator._reconcile_and_release_audit_budget.assert_called_once_with(
        "audit-reservation-key"
    )


def test_restarted_legacy_binding_failure_exhausts_durably_without_workspace() -> None:
    """An unreachable legacy revision consumes a bounded recovery budget."""

    issue = Issue(
        id="TASK-1",
        identifier="TASK-1",
        title="Task",
        state="In Validation",
        project_id="proj-1",
    )
    issue.source_sha = "c" * 40
    legacy_record = TerminalAuditRecord.from_dict(
        replace(
            _record(infrastructure_attempts=False),
            evidence_fingerprint=compute_issue_evidence_fingerprint(
                issue,
                "proj-1",
            ),
        ).to_dict()
    )
    metadata = {
        METADATA_KEY: TerminalAuditMetadata(pending_chain=[legacy_record]).to_dict()
    }
    metadata_lock = threading.Lock()
    tracker = MagicMock()

    def _get_metadata(_identifier: str):
        with metadata_lock:
            return copy.deepcopy(metadata)

    def _set_metadata_field(_identifier: str, key: str, value):
        with metadata_lock:
            metadata[key] = copy.deepcopy(value)

    tracker.get_metadata.side_effect = _get_metadata
    tracker.set_metadata_field.side_effect = _set_metadata_field

    project = SimpleNamespace(id="proj-1", default_branch="main")
    project_store = MagicMock()
    project_store.get.return_value = project
    project_store.resolve_audit_revision.side_effect = ProjectError(
        f"terminal audit revision is unavailable: {'c' * 40}"
    )
    project_store.project_write_lock.return_value = threading.RLock()
    store = TerminalAuditMetadataStore(tracker, project_store, "proj-1")

    orchestrator = _orchestrator()
    orchestrator.project_store = project_store
    orchestrator.config = SimpleNamespace(
        audit_priority=0,
        audit_lane_scan_limit=0,
        audit_max_attempts=2,
        audit_attempt_ttl=60,
    )
    orchestrator._tick_pool = None
    orchestrator._dispatch_is_blocked = MagicMock(return_value=False)
    orchestrator._is_rate_limited = MagicMock(return_value=False)
    orchestrator._available_slots = MagicMock(return_value=1)
    orchestrator._fetch_audit_candidates = MagicMock(
        return_value=_AuditCandidateScan((issue,))
    )
    orchestrator._audit_store = MagicMock(return_value=store)
    orchestrator._uncommitted_terminal_result_intents = MagicMock(return_value=0)
    orchestrator._refresh_terminal_audit_health = MagicMock()
    orchestrator._refresh_terminal_audit_validation_configuration_alerts = MagicMock()
    orchestrator._terminal_audit_validation_configuration_error = MagicMock(
        return_value=None
    )
    orchestrator._clear_terminal_audit_validation_configuration = MagicMock()
    orchestrator._prepare_audit_selector = AsyncMock(
        return_value=(MagicMock(), None)
    )
    orchestrator._running_values_snapshot = MagicMock(return_value=[])
    orchestrator._audit_branch_busy = MagicMock(return_value=False)
    orchestrator._backoff_delay = MagicMock(return_value=0)
    orchestrator._dispatch = AsyncMock()

    # Each call represents a fresh post-restart scan reading only durable
    # metadata. Two failures consume the budget; the third scan routes the
    # exhausted record without trying the unreachable object again.
    asyncio.run(orchestrator._dispatch_audit_lane())
    first_restart = store.read(issue.identifier).pending_chain[0]
    assert len(first_restart.attempts) == 1
    assert first_restart.selected_sha is None

    asyncio.run(orchestrator._dispatch_audit_lane())
    second_restart = store.read(issue.identifier).pending_chain[0]
    assert len(second_restart.attempts) == 2
    assert all(
        attempt.failure_classification
        == FailureClassification.INFRASTRUCTURE_ERROR
        for attempt in second_restart.attempts
    )

    asyncio.run(orchestrator._dispatch_audit_lane())

    result = (
        orchestrator.terminal_transition_coordinator.apply_audit_result.await_args.args[
            1
        ]
    )
    assert result.verdict == Verdict.NEEDS_HUMAN
    assert result.failure_classification == FailureClassification.INFRASTRUCTURE_ERROR
    assert project_store.resolve_audit_revision.call_count == 2
    project_store.create_detached_audit_worktree.assert_not_called()
    orchestrator._dispatch.assert_not_awaited()


def test_legacy_unbound_record_rejects_resolvable_changed_evidence() -> None:
    """A restart must not attach current E2 authority to an E1 record."""

    stale_issue = Issue(
        id="TASK-1",
        identifier="TASK-1",
        title="Task",
        description="E1 requirements",
        project_id="proj-1",
    )
    stale_issue.source_sha = "b" * 40
    current_issue = Issue(
        id="TASK-1",
        identifier="TASK-1",
        title="Task",
        description="E2 requirements",
        project_id="proj-1",
    )
    current_issue.source_sha = "c" * 40
    record = TerminalAuditRecord(
        audit_id="audit-e1",
        project_id="proj-1",
        task_id="TASK-1",
        target_state=TargetState.DONE,
        evidence_fingerprint=compute_issue_evidence_fingerprint(
            stale_issue,
            "proj-1",
        ),
    )
    orchestrator = _orchestrator()
    orchestrator.project_store = MagicMock()
    orchestrator.project_store.get.return_value = SimpleNamespace(
        id="proj-1",
        default_branch="main",
    )
    orchestrator.project_store.resolve_audit_revision.return_value = "c" * 40

    with pytest.raises(ProjectError, match="evidence fingerprint is stale"):
        orchestrator._bind_audit_record_revision(current_issue, record)

    orchestrator.project_store.resolve_audit_revision.assert_not_called()


@pytest.mark.parametrize(
    "record_project_id,record_task_id",
    [("foreign-project", "TASK-1"), ("proj-1", "FOREIGN-1")],
)
def test_legacy_unbound_record_requires_exact_issue_scope(
    record_project_id: str,
    record_task_id: str,
) -> None:
    issue = Issue(
        id="TASK-1",
        identifier="TASK-1",
        title="Task",
        project_id="proj-1",
    )
    record = TerminalAuditRecord(
        audit_id="audit-foreign",
        project_id=record_project_id,
        task_id=record_task_id,
        target_state=TargetState.DONE,
        evidence_fingerprint=compute_issue_evidence_fingerprint(issue, "proj-1"),
    )
    orchestrator = _orchestrator()
    orchestrator.project_store = MagicMock()

    with pytest.raises(ProjectError, match="scope does not match"):
        orchestrator._bind_audit_record_revision(issue, record)

    orchestrator.project_store.resolve_audit_revision.assert_not_called()


def test_auditor_cleanup_targets_attempt_workspace_only() -> None:
    orchestrator = Orchestrator.__new__(Orchestrator)
    orchestrator.project_store = MagicMock()
    issue = Issue(
        id="TASK-1",
        identifier="TASK-1",
        title="Task",
        project_id="proj-1",
    )
    entry = SimpleNamespace(
        issue=issue,
        identifier="TASK-1",
        audit_attempt_id="attempt-1",
    )

    orchestrator._remove_audit_workspace(entry)

    orchestrator.project_store.remove_worktree.assert_called_once_with(
        "proj-1",
        "TASK-1--terminal-audit-attempt-1",
    )


def _metadata_archive_orchestrator(*, comments: list[dict], active_claim: bool = False):
    orchestrator = Orchestrator.__new__(Orchestrator)
    tracker = MagicMock()
    tracker.fetch_comments.return_value = comments
    tracker.fetch_issue_detail.return_value = Issue(
        id="OOMPAH-775",
        identifier="OOMPAH-775",
        title="Canonical task",
        state="Open",
    )
    tracker.fetch_children.return_value = []
    orchestrator._tracker_for_issue = MagicMock(return_value=tracker)
    orchestrator._running_values_snapshot = MagicMock(return_value=())
    orchestrator._has_live_owner_claim = MagicMock(return_value=active_claim)
    orchestrator.state = SimpleNamespace(claimed=set(), retry_attempts={})
    orchestrator._retry_dispatching = {}
    orchestrator._audit_reservation_key_for_issue = MagicMock(
        return_value="metadata-audit-reservation-key"
    )
    orchestrator._reconcile_and_release_audit_budget = MagicMock(return_value=True)
    orchestrator.config = SimpleNamespace(
        tracker_terminal_states=["Done", "Merged", "Archived"]
    )
    return orchestrator


def _metadata_issue_and_record():
    issue = Issue(
        id="OOMPAH-803",
        identifier="OOMPAH-803",
        title="Route status writes",
        description=(
            "Triggered by: OOMPAH-775\n\n"
            "Migrate status writers through TaskTransitionService."
        ),
        state="In Validation",
        project_id="proj-1",
        branch_name="OOMPAH-803",
    )
    record = TerminalAuditRecord(
        audit_id="audit-803",
        project_id="proj-1",
        task_id="OOMPAH-803",
        target_state=TargetState.ARCHIVED,
        evidence_fingerprint=compute_issue_evidence_fingerprint(issue, "proj-1"),
        request_state=RequestState.PENDING,
        previous_state="Backlog",
    )
    return issue, record


def test_metadata_archive_binding_remains_revisionless_after_exact_binding() -> None:
    issue, record = _metadata_issue_and_record()
    orchestrator = _orchestrator()
    orchestrator.project_store = MagicMock()

    bound = orchestrator._bind_audit_record_revision(issue, record)

    assert bound == record
    assert bound.selected_ref is None
    assert bound.selected_sha is None
    orchestrator.project_store.resolve_audit_revision.assert_not_called()


def test_oompah_803_metadata_archive_preflight_passes_without_revision() -> None:
    orchestrator = _metadata_archive_orchestrator(
        comments=[
            {
                "text": (
                    "Archiving as an exact duplicate of the earlier, more "
                    "actionable OOMPAH-775."
                )
            }
        ]
    )
    issue, record = _metadata_issue_and_record()

    snapshot = orchestrator._revisionless_archive_evidence(issue, record)

    assert snapshot is not None
    assert snapshot.passed()
    assert snapshot.failure_modes == []
    source_comment = orchestrator._revisionless_archive_source_comment(issue, snapshot)
    assert source_comment is not None
    assert "OOMPAH-775" in source_comment["text"]
    assert "Canonical task" in source_comment["text"]


def test_running_auditors_own_scheduler_claim_does_not_invalidate_preflight() -> None:
    orchestrator = _metadata_archive_orchestrator(
        comments=[{"text": "Archiving as an exact duplicate of OOMPAH-775."}]
    )
    issue, record = _metadata_issue_and_record()
    orchestrator.state.claimed.add(issue.id)
    orchestrator._running_values_snapshot.return_value = (
        SimpleNamespace(issue=issue, is_auditor=True),
    )

    snapshot = orchestrator._revisionless_archive_evidence(issue, record)

    assert snapshot is not None
    assert snapshot.passed()
    assert SafetyFailureMode.ACTIVE_CLAIM.value not in snapshot.failure_modes


def test_missing_archive_reason_fails_as_actionable_evidence() -> None:
    orchestrator = _metadata_archive_orchestrator(comments=[])
    issue, record = _metadata_issue_and_record()

    snapshot = orchestrator._revisionless_archive_evidence(issue, record)

    assert snapshot is not None
    assert not snapshot.passed()
    assert SafetyFailureMode.NO_DISPOSITION_REASON.value in snapshot.failure_modes


def test_missing_replacement_fails_as_actionable_evidence() -> None:
    orchestrator = _metadata_archive_orchestrator(
        comments=[{"text": "Archiving as an exact duplicate of OOMPAH-775."}]
    )
    orchestrator._tracker_for_issue.return_value.fetch_issue_detail.return_value = None
    issue, record = _metadata_issue_and_record()

    snapshot = orchestrator._revisionless_archive_evidence(issue, record)

    assert snapshot is not None
    assert not snapshot.passed()
    assert SafetyFailureMode.DUPLICATE_NO_SOURCE.value in snapshot.failure_modes


def test_active_claim_blocks_revisionless_archive() -> None:
    orchestrator = _metadata_archive_orchestrator(
        comments=[{"text": "Archiving as an exact duplicate of OOMPAH-775."}],
        active_claim=True,
    )
    issue, record = _metadata_issue_and_record()

    snapshot = orchestrator._revisionless_archive_evidence(issue, record)

    assert snapshot is not None
    assert not snapshot.passed()
    assert SafetyFailureMode.ACTIVE_CLAIM.value in snapshot.failure_modes


def test_open_review_blocks_revisionless_archive() -> None:
    orchestrator = _metadata_archive_orchestrator(
        comments=[{"text": "Archiving as an exact duplicate of OOMPAH-775."}]
    )
    issue, record = _metadata_issue_and_record()
    issue.review_url = "https://example.test/reviews/803"
    record.evidence_fingerprint = compute_issue_evidence_fingerprint(issue, "proj-1")

    snapshot = orchestrator._revisionless_archive_evidence(issue, record)

    assert snapshot is not None
    assert not snapshot.passed()
    assert SafetyFailureMode.OPEN_REVIEW.value in snapshot.failure_modes


def test_unsafe_metadata_archive_is_not_recorded_as_transport_failure() -> None:
    orchestrator = _metadata_archive_orchestrator(comments=[])
    orchestrator.terminal_transition_coordinator = SimpleNamespace(
        apply_audit_result=AsyncMock(
            return_value=SimpleNamespace(success=True, applied_status="Backlog")
        )
    )
    orchestrator._record_audit_outcome_ownership = MagicMock()
    orchestrator._audit_reservation_key_for_issue = MagicMock(
        return_value="metadata-audit-reservation-key"
    )
    orchestrator._reconcile_and_release_audit_budget = MagicMock(return_value=True)
    orchestrator._audit_metrics = {"last_error": None}
    issue, record = _metadata_issue_and_record()
    snapshot = orchestrator._revisionless_archive_evidence(issue, record)
    assert snapshot is not None

    asyncio.run(
        orchestrator._route_unsafe_metadata_archive(issue, record, snapshot)
    )

    result = orchestrator.terminal_transition_coordinator.apply_audit_result.await_args.args[1]
    assert result.verdict == Verdict.FAIL
    assert result.failure_classification == FailureClassification.UNSAFE_ARCHIVE
    assert result.failure_classification != FailureClassification.INFRASTRUCTURE_ERROR
    orchestrator._audit_reservation_key_for_issue.assert_called_once_with(issue)
    orchestrator._reconcile_and_release_audit_budget.assert_called_once_with(
        "metadata-audit-reservation-key"
    )


def test_unsafe_metadata_archive_retires_pre_materialized_durable_job(
    tmp_path,
) -> None:
    orchestrator = _metadata_archive_orchestrator(comments=[])
    orchestrator.terminal_transition_coordinator = SimpleNamespace(
        apply_audit_result=AsyncMock(
            return_value=SimpleNamespace(success=True, applied_status="Backlog")
        )
    )
    orchestrator._record_audit_outcome_ownership = MagicMock()
    orchestrator._audit_metrics = {"last_error": None}
    issue, record = _metadata_issue_and_record()
    snapshot = orchestrator._revisionless_archive_evidence(issue, record)
    assert snapshot is not None and not snapshot.passed()

    store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    workflow = TerminalAuditWorkflow(store)
    orchestrator.terminal_audit_workflow = workflow
    queued = workflow.ensure(record)

    asyncio.run(orchestrator._route_unsafe_metadata_archive(issue, record, snapshot))

    assert store.get(queued.job_id).state is WorkflowJobState.CANCELLED
    assert not [
        job
        for job in store.list_jobs(project_id="proj-1", task_id="OOMPAH-803")
        if job.state
        in {
            WorkflowJobState.QUEUED,
            WorkflowJobState.RUNNING,
            WorkflowJobState.RETRY_WAIT,
        }
    ]
    store.close()


def test_safe_revisionless_archive_restarts_with_one_durable_attempt(
    tmp_path,
) -> None:
    orchestrator = _metadata_archive_orchestrator(
        comments=[
            {
                "text": (
                    "Archiving as an exact duplicate of the earlier, more "
                    "actionable OOMPAH-775."
                )
            }
        ]
    )
    issue, record = _metadata_issue_and_record()
    snapshot = orchestrator._revisionless_archive_evidence(issue, record)
    assert snapshot is not None and snapshot.passed()

    db_path = str(tmp_path / "workflow.sqlite3")
    store = WorkflowJobStore(db_path)
    workflow = TerminalAuditWorkflow(store)
    queued = workflow.ensure(record)
    store.close()

    reopened_store = WorkflowJobStore(db_path)
    reopened = TerminalAuditWorkflow(reopened_store)
    duplicate_metadata_identity = replace(record, audit_id="audit-803-reconciled")
    replayed = reopened.ensure(duplicate_metadata_identity)
    running = reopened.start(
        record,
        attempt_id="attempt-803",
        candidate=Candidate("provider-a", "model-a"),
    )

    assert replayed.job_id == queued.job_id
    assert running is not None
    assert running.attempts == 1
    assert (
        reopened.start(
            duplicate_metadata_identity,
            attempt_id="attempt-803-duplicate",
            candidate=Candidate("provider-b", "model-b"),
        )
        is None
    )
    assert len(
        reopened_store.list_jobs(project_id="proj-1", task_id="OOMPAH-803")
    ) == 1
    reopened_store.close()
