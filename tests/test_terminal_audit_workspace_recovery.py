"""Regression coverage for terminal-audit workspace and exhaustion routing."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from oompah.archived_evidence_collector import SafetyFailureMode
from oompah.models import Issue
from oompah.orchestrator import Orchestrator
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
    orchestrator.terminal_transition_coordinator = SimpleNamespace(
        apply_audit_result=AsyncMock(
            return_value=SimpleNamespace(success=True, applied_status="Needs Human")
        )
    )
    orchestrator._record_audit_outcome_ownership = MagicMock()
    orchestrator._audit_metrics = {"exhaustion_count": 0, "last_error": None}
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
