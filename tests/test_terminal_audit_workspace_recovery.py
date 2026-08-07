"""Regression coverage for terminal-audit workspace and exhaustion routing."""

from __future__ import annotations

import asyncio
import copy
import threading
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from oompah.models import Issue
from oompah.orchestrator import Orchestrator
from oompah.projects import ProjectError
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
        audit_attempt_ttl_seconds=60,
    )
    orchestrator._tick_pool = None
    orchestrator._dispatch_is_blocked = MagicMock(return_value=False)
    orchestrator._is_rate_limited = MagicMock(return_value=False)
    orchestrator._available_slots = MagicMock(return_value=1)
    orchestrator._fetch_audit_candidates = MagicMock(return_value=[issue])
    orchestrator._audit_store = MagicMock(return_value=store)
    orchestrator._uncommitted_terminal_result_intents = MagicMock(return_value=0)
    orchestrator._refresh_terminal_audit_health = MagicMock()
    orchestrator._audit_selector = MagicMock(return_value=MagicMock())
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
