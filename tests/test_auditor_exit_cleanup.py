"""Regressions for completion-auditor in-memory claim cleanup."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from oompah.config import ServiceConfig
from oompah.models import Issue, RunningEntry
from oompah.orchestrator import Orchestrator
from oompah.statuses import IN_VALIDATION


def _orchestrator(tmp_path) -> Orchestrator:
    project_store = MagicMock()
    project_store.list_all.return_value = []
    return Orchestrator(
        config=ServiceConfig(duplicate_preflight_max_agents=0),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        state_path=str(tmp_path / "state.json"),
    )


def _issue() -> Issue:
    return Issue(
        id="issue-1",
        identifier="OOMPAH-593",
        title="Audit cleanup regression",
        description="Prove a completed auditor does not retain its branch claim.",
        state=IN_VALIDATION,
        project_id="project-1",
        branch_name="task-branch",
    )


@pytest.mark.asyncio
async def test_auditor_exit_releases_claimed_issue_and_branch(tmp_path):
    orch = _orchestrator(tmp_path)
    issue = _issue()
    entry = RunningEntry(
        worker_task=MagicMock(),
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        is_auditor=True,
        audit_id="audit-1",
        audit_attempt_id="attempt-1",
        branch_key="task-branch",
    )
    orch.state.running[issue.id] = entry
    orch.state.claimed.add(issue.id)
    orch.state.claimed_issues[issue.id] = issue
    orch._audit_branch_claims[entry.branch_key] = entry.audit_attempt_id

    assert orch._audit_branch_busy(issue, entry.branch_key)

    with (
        patch.object(orch, "_fire_task_cost_record"),
        patch.object(orch, "_fire_telemetry_comment"),
        patch.object(orch, "_finish_audit_attempt", return_value=True),
        patch.object(orch, "_post_comment"),
    ):
        await orch._on_worker_exit(issue.id, "stalled", "provider stalled")

    assert issue.id not in orch.state.running
    assert issue.id not in orch.state.claimed
    assert issue.id not in orch.state.claimed_issues
    assert entry.branch_key not in orch._audit_branch_claims
    assert not orch._audit_branch_busy(issue, entry.branch_key)


def test_audit_branch_gate_prunes_orphaned_claim_but_keeps_active_claim(tmp_path):
    orch = _orchestrator(tmp_path)
    issue = _issue()
    orch.state.claimed_issues[issue.id] = issue

    assert not orch._audit_branch_busy(issue, "task-branch")
    assert issue.id not in orch.state.claimed_issues

    orch.state.claimed.add(issue.id)
    orch.state.claimed_issues[issue.id] = issue

    assert orch._audit_branch_busy(issue, "task-branch")
    assert issue.id in orch.state.claimed_issues
