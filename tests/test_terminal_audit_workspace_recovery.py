"""Regression coverage for terminal-audit workspace and exhaustion routing."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from oompah.models import Issue
from oompah.orchestrator import Orchestrator
from oompah.terminal_audit import (
    AuditAttempt,
    EvidenceFingerprint,
    FailureClassification,
    RequestState,
    TargetState,
    TerminalAuditRecord,
    Verdict,
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

