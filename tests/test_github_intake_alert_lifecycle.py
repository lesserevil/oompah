"""Tests for GitHub issue intake dashboard alert lifecycle."""

from __future__ import annotations

from unittest.mock import MagicMock

from oompah.config import ServiceConfig
from oompah.models import Project
from oompah.orchestrator import Orchestrator


def _project(name: str = "trickle") -> Project:
    return Project(
        id=f"proj-{name}",
        name=name,
        repo_url=f"https://github.com/example-org/{name}.git",
        repo_path=f"/tmp/{name}",
        tracker_kind="oompah_md",
        tracker_owner="example-org",
        tracker_repo=name,
        github_issue_intake_enabled=True,
    )


def _orchestrator(tmp_path, projects: list[Project]) -> Orchestrator:
    project_store = MagicMock()
    project_store.list_all.return_value = list(projects)
    project_store.get.side_effect = lambda project_id: next(
        (project for project in projects if project.id == project_id),
        None,
    )
    return Orchestrator(
        config=ServiceConfig(),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        state_path=str(tmp_path / "state.json"),
    )


def test_github_intake_auth_alert_clears_after_success(tmp_path, monkeypatch):
    project = _project("trickle")
    orch = _orchestrator(tmp_path, [project])
    orch._alerts = [
        {
            "level": "error",
            "source": "github_intake_auth:trickle",
            "message": "stale auth failure",
        },
        {
            "level": "warning",
            "source": "other",
            "message": "keep me",
        },
    ]

    def poll_success(call_orch, call_project):
        assert call_orch is orch
        assert call_project is project
        return 0

    def sync_success(call_orch, call_project):
        assert call_orch is orch
        assert call_project is project
        return {"scanned": 1, "commented": 0, "closed": 0, "errors": 0}

    monkeypatch.setattr(
        "oompah.orchestrator.poll_github_issue_intake_project",
        poll_success,
    )
    monkeypatch.setattr(
        "oompah.orchestrator.sync_github_issue_intake_statuses_for_project",
        sync_success,
    )

    orch._sync_github_issue_intake_pass()

    assert [alert.get("source") for alert in orch._alerts] == ["other"]
    assert orch._maintenance_status["github_issue_intake"]["errors"] == 0
