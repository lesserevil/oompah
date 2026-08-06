"""REST contract tests for the canonical task decision projection."""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.models import Issue
from oompah.work_decision import PermittedAction, WorkDecision
from oompah.work_decision_projection import project_work_decision
from oompah.workflow_contract import TaskDisposition, WorkflowOwner
from oompah.workflow_reasons import AlertSeverity


def _issue() -> Issue:
    return Issue(
        id="id-1",
        identifier="TASK-1",
        title="Task",
        state="Open",
        project_id="project-a",
    )


def _projection() -> dict:
    return project_work_decision(
        WorkDecision(
            project_id="project-a",
            task_id="TASK-1",
            status="Open",
            disposition=TaskDisposition.RUNNABLE,
            reason_code="dispatch.eligible",
            responsible_owner=WorkflowOwner.DISPATCHER,
            unmet_prerequisites=(),
            evidence_revision="evidence-1",
            next_reassessment_at="2026-08-06T05:00:00+00:00",
            permitted_actions=(PermittedAction.CLAIM_IMPLEMENTATION,),
            action_required=False,
            alert_level=AlertSeverity.NONE,
        )
    )


class _StubOrchestrator:
    def __init__(self, issue: Issue, decision: dict):
        self.tracker = MagicMock()
        self.tracker.fetch_issue_detail.return_value = issue
        self._decision = decision

    def _tracker_for_project(self, project_id: str):
        assert project_id == "project-a"
        return self.tracker

    def work_decision_projection(self, project_id, task_id, task=None):
        assert (project_id, task_id) == ("project-a", "TASK-1")
        return self._decision


def test_work_decision_endpoint_matches_shared_projection(monkeypatch) -> None:
    issue = _issue()
    decision = _projection()
    orch = _StubOrchestrator(issue, decision)
    monkeypatch.setattr(server_module, "_get_orchestrator", lambda: orch)
    monkeypatch.setattr(server_module, "_http_credentials", None)

    client = TestClient(server_module.app, raise_server_exceptions=False)
    response = client.get(
        "/api/v1/projects/project-a/tasks/TASK-1/work-decision"
    )

    assert response.status_code == 200
    assert response.json() == {"work_decision": decision}


def test_board_and_detail_helper_read_the_same_decision(monkeypatch) -> None:
    issue = _issue()
    decision = _projection()
    orch = _StubOrchestrator(issue, decision)

    board_value = server_module._work_decision_for_task(
        orch, issue.project_id, issue.identifier, issue
    )
    detail_value = server_module._work_decision_for_task(
        orch, issue.project_id, issue.identifier, issue
    )

    assert board_value == detail_value == decision
