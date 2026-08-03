"""Regressions for forced completion-auditor termination cleanup."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from oompah.config import ServiceConfig
from oompah.models import Issue, RunningEntry
from oompah.orchestrator import Orchestrator
from oompah.statuses import IN_VALIDATION
from oompah.terminal_audit import (
    AuditAttempt,
    FailureClassification,
    RequestState,
    TargetState,
    TerminalAuditRecord,
    Verdict,
    compute_evidence_fingerprint,
)


def _orchestrator(tmp_path) -> Orchestrator:
    project_store = MagicMock()
    project_store.list_all.return_value = []
    return Orchestrator(
        config=ServiceConfig(duplicate_preflight_max_agents=0),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        state_path=str(tmp_path / "state.json"),
    )


def _entry(attempt_id: str = "attempt-1") -> RunningEntry:
    issue = Issue(
        id="issue-1",
        identifier="OOMPAH-591",
        title="Audit termination cleanup regression",
        description="Prove forced termination releases only its own branch fence.",
        state=IN_VALIDATION,
        project_id="project-1",
        branch_name="task-branch",
    )
    task = MagicMock()
    task.done.return_value = True
    return RunningEntry(
        worker_task=task,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        is_auditor=True,
        audit_id="audit-1",
        audit_attempt_id=attempt_id,
        branch_key="task-branch",
    )


def _terminate(orch: Orchestrator) -> bool:
    with (
        patch.object(orch, "_fire_task_cost_record"),
        patch.object(orch, "_fire_telemetry_comment"),
    ):
        return asyncio.run(
            orch._terminate_running("issue-1", cleanup_workspace=False)
        )


def test_forced_auditor_termination_releases_all_runtime_claims(tmp_path) -> None:
    orch = _orchestrator(tmp_path)
    entry = _entry()
    orch.state.running[entry.issue.id] = entry
    orch.state.claimed.add(entry.issue.id)
    orch.state.claimed_issues[entry.issue.id] = entry.issue
    orch._audit_branch_claims[entry.branch_key] = entry.audit_attempt_id

    assert _terminate(orch) is True

    assert entry.issue.id not in orch.state.running
    assert entry.issue.id not in orch.state.claimed
    assert entry.issue.id not in orch.state.claimed_issues
    assert entry.branch_key not in orch._audit_branch_claims
    assert not orch._audit_branch_busy(entry.issue, entry.branch_key)


def test_forced_termination_does_not_release_replacement_auditor_claim(
    tmp_path,
) -> None:
    orch = _orchestrator(tmp_path)
    stale = _entry("attempt-old")
    orch.state.running[stale.issue.id] = stale
    orch.state.claimed.add(stale.issue.id)
    orch.state.claimed_issues[stale.issue.id] = stale.issue
    orch._audit_branch_claims[stale.branch_key] = "attempt-new"

    assert _terminate(orch) is True

    assert orch._audit_branch_claims[stale.branch_key] == "attempt-new"


def test_owner_authority_revocation_fences_live_auditor(tmp_path) -> None:
    orch = _orchestrator(tmp_path)
    entry = _entry()
    orch.state.running[entry.issue.id] = entry

    with patch.object(orch, "_schedule_running_termination") as terminate:
        orch._revoke_auditor_authority("project-1", entry.identifier)

    assert entry.authority_revoked is True
    assert entry.forced_exit_reason == "authority_revoked"
    terminate.assert_called_once_with(
        entry.issue.id,
        cleanup_workspace=False,
        task_name_prefix="retire-revoked-auditor",
    )


def test_uncommitted_normal_exit_is_a_finalization_failure(tmp_path) -> None:
    orch = _orchestrator(tmp_path)
    entry = _entry()
    fingerprint = compute_evidence_fingerprint(
        "requirements",
        "project-1",
        entry.identifier,
    )
    attempt = AuditAttempt(
        attempt_id=entry.audit_attempt_id,
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        provider_id="provider-a",
        model="model-a",
        request_state=RequestState.IN_PROGRESS,
    )
    record = TerminalAuditRecord(
        audit_id=entry.audit_id,
        project_id="project-1",
        task_id=entry.identifier,
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.IN_PROGRESS,
        attempts=[attempt],
    )
    store = MagicMock()
    store.read.return_value = MagicMock(pending_chain=[record])

    with (
        patch.object(orch, "_audit_store", return_value=store),
        patch.object(orch, "_audit_update_record", return_value=True),
        patch("oompah.orchestrator.AuditorDispatchLane.finish_attempt") as finish,
    ):
        finish.return_value = record
        assert orch._finish_audit_attempt(entry, "normal", None) is True

    assert finish.call_args.kwargs["failure_classification"] == (
        FailureClassification.FINALIZATION_FAILURE
    )


def test_structured_nonterminal_result_owns_attempt_classification(tmp_path) -> None:
    orch = _orchestrator(tmp_path)
    entry = _entry()
    fingerprint = compute_evidence_fingerprint(
        "requirements",
        "project-1",
        entry.identifier,
    )
    attempt = AuditAttempt(
        attempt_id=entry.audit_attempt_id,
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.IN_PROGRESS,
        verdict=Verdict.ERROR,
        failure_classification=FailureClassification.INFRASTRUCTURE_ERROR,
    )
    record = TerminalAuditRecord(
        audit_id=entry.audit_id,
        project_id="project-1",
        task_id=entry.identifier,
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.IN_PROGRESS,
        attempts=[attempt],
    )
    store = MagicMock()
    store.read.return_value = MagicMock(pending_chain=[record])

    with (
        patch.object(orch, "_audit_store", return_value=store),
        patch("oompah.orchestrator.AuditorDispatchLane.finish_attempt") as finish,
    ):
        assert orch._finish_audit_attempt(entry, "normal", None) is False

    finish.assert_not_called()
