"""Regressions for forced completion-auditor termination cleanup."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

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
