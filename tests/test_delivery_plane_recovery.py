"""Regression coverage for integration delivery recovery and authority fences."""

from __future__ import annotations

from unittest import mock

from oompah.config import ServiceConfig
from oompah.integration import IntegrationRecord
from oompah.models import Issue, Project
from oompah.orchestrator import Orchestrator
from oompah.statuses import DONE, NEEDS_REBASE, READY_TO_INTEGRATE


def _issue(
    *,
    identifier: str = "TASK-1",
    state: str = READY_TO_INTEGRATE,
    integration_state: str = "blocked",
    last_error: str | None = None,
) -> Issue:
    return Issue(
        id=identifier.lower(),
        identifier=identifier,
        title="Delivery task",
        state=state,
        parent_id="EPIC-1",
        integration=IntegrationRecord(
            state=integration_state,
            task_branch=f"epic-EPIC-1--task-{identifier}",
            head_sha="a" * 40,
            last_error=last_error,
        ),
    )


def _make_harness(tmp_path, issue: Issue):
    project = Project(
        id="proj-1",
        name="Recovery project",
        repo_url="https://github.com/org/repo.git",
        repo_path=str(tmp_path / "repo"),
        default_branch="main",
    )
    tracker = mock.MagicMock()
    tracker.fetch_issues_by_states.return_value = [issue]
    tracker.fetch_all_issues.return_value = [issue]
    tracker.fetch_issue_detail.return_value = issue
    project_store = mock.MagicMock()
    project_store.list_all.return_value = [project]
    project_store.get.side_effect = lambda project_id: (
        project if project_id == project.id else None
    )
    orchestrator = Orchestrator(
        config=ServiceConfig(),
        workflow_path=str(tmp_path / "WORKFLOW.md"),
        project_store=project_store,
        state_path=str(tmp_path / "service-state.json"),
    )
    orchestrator._project_trackers[project.id] = tracker
    return orchestrator, project, tracker


def _blocked_row(orchestrator: Orchestrator, project: Project, issue: Issue):
    row = orchestrator.integration_queue.enqueue(
        project_id=project.id,
        epic_id=issue.parent_id or "EPIC-1",
        task_id=issue.identifier,
        task_branch=issue.integration.task_branch,
        head_sha=issue.integration.head_sha,
    )
    claimed = orchestrator.integration_queue.claim_next(
        project_id=project.id,
        epic_id=issue.parent_id or "EPIC-1",
        lease_owner="worker-1",
        dependency_map={issue.identifier: ()},
        satisfied=set(),
    )
    assert claimed is not None
    assert orchestrator.integration_queue.fail(
        project.id,
        issue.identifier,
        lease_owner="worker-1",
        error="stale integration failure",
    )
    return row


def _close(orchestrator: Orchestrator) -> None:
    orchestrator.integration_queue.close()
    orchestrator.coordination_store.close()
    orchestrator._tick_pool.shutdown(wait=True, cancel_futures=True)
    orchestrator._refresh_pool.shutdown(wait=True, cancel_futures=True)


def test_ready_retry_metadata_rearms_identical_blocked_queue_row(tmp_path):
    issue = _issue(integration_state="ready")
    orchestrator, project, _tracker = _make_harness(tmp_path, issue)
    try:
        _blocked_row(orchestrator, project, issue)

        orchestrator._sync_ready_integration_submissions()

        row = orchestrator.integration_queue.items(project_id=project.id)[0]
        assert row.state == "ready"
        assert row.retry_forced is True
        assert not any(
            alert.get("source") == "integration_delivery:proj-1:TASK-1"
            for alert in orchestrator._alerts
        )
    finally:
        _close(orchestrator)


def test_blocked_row_alerts_clear_after_row_and_scan_recover(tmp_path):
    issue = _issue(last_error="old merge conflict")
    orchestrator, project, tracker = _make_harness(tmp_path, issue)
    try:
        _blocked_row(orchestrator, project, issue)
        orchestrator._audit_blocked_integration_rows(project.id, tracker)
        assert any(
            alert.get("source") == "integration_delivery:proj-1:TASK-1"
            for alert in orchestrator._alerts
        )

        tracker.fetch_all_issues.side_effect = RuntimeError("tracker offline")
        orchestrator._audit_blocked_integration_rows(project.id, tracker)
        assert any(
            alert.get("source") == "integration_delivery_scan:proj-1"
            for alert in orchestrator._alerts
        )

        issue.state = NEEDS_REBASE
        tracker.fetch_all_issues.side_effect = None
        tracker.fetch_all_issues.return_value = [issue]
        orchestrator._audit_blocked_integration_rows(project.id, tracker)
        assert not any(
            str(alert.get("source", "")).startswith("integration_delivery")
            for alert in orchestrator._alerts
        )

        assert orchestrator.integration_queue.cancel(
            project.id,
            issue.identifier,
            reason="repair superseded",
        )
        orchestrator._audit_blocked_integration_rows(project.id, tracker)
        assert not any(
            str(alert.get("source", "")).startswith("integration_delivery")
            for alert in orchestrator._alerts
        )
    finally:
        _close(orchestrator)


def test_terminal_task_retires_active_row_and_invalidates_lease(tmp_path):
    issue = _issue(state=DONE, integration_state="ready")
    orchestrator, project, _tracker = _make_harness(tmp_path, issue)
    try:
        orchestrator.integration_queue.enqueue(
            project_id=project.id,
            epic_id="EPIC-1",
            task_id=issue.identifier,
            task_branch=issue.integration.task_branch,
            head_sha=issue.integration.head_sha,
        )
        claimed = orchestrator.integration_queue.claim_next(
            project_id=project.id,
            epic_id="EPIC-1",
            lease_owner="stale-worker",
            dependency_map={issue.identifier: ()},
            satisfied=set(),
        )
        assert claimed is not None

        assert (
            orchestrator._retire_inactive_integration_rows(
                project.id,
                [issue],
                [claimed],
            )
            == 1
        )
        row = orchestrator.integration_queue.items(project_id=project.id)[0]
        assert row.state == "cancelled"
        assert not orchestrator.integration_queue.fail(
            project.id,
            issue.identifier,
            lease_owner="stale-worker",
            error="late conflict",
        )
    finally:
        _close(orchestrator)


def test_exact_ready_submission_is_required_for_executor_authority(tmp_path):
    issue = _issue(integration_state="ready")
    orchestrator, project, tracker = _make_harness(tmp_path, issue)
    try:
        row = orchestrator.integration_queue.enqueue(
            project_id=project.id,
            epic_id="EPIC-1",
            task_id=issue.identifier,
            task_branch=issue.integration.task_branch,
            head_sha=issue.integration.head_sha,
        )
        assert orchestrator._integration_task_still_ready(row)

        issue.state = DONE
        assert not orchestrator._integration_task_still_ready(row)
        issue.state = READY_TO_INTEGRATE
        issue.integration = IntegrationRecord(
            state="ready",
            task_branch=row.task_branch,
            head_sha="b" * 40,
        )
        assert not orchestrator._integration_task_still_ready(row)
        tracker.fetch_issue_detail.return_value = None
        assert not orchestrator._integration_task_still_ready(row)
    finally:
        _close(orchestrator)
