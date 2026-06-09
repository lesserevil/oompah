"""Tests for project-scoped Backlog task ids in dashboard display."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.models import Issue, Project
from oompah.server import app


@pytest.fixture(autouse=True)
def clear_api_state():
    with server_module._issues_snapshot_lock:
        server_module._issues_refresh_task = None
        server_module._issues_snapshot.update(
            {
                "data": None,
                "orch_id": None,
                "created_at_monotonic": 0.0,
                "created_at_wall": None,
                "duration_ms": None,
                "issue_count": 0,
                "error": None,
            }
        )
    server_module._api_cache.clear()
    yield
    with server_module._issues_snapshot_lock:
        server_module._issues_refresh_task = None
        server_module._issues_snapshot.update(
            {
                "data": None,
                "orch_id": None,
                "created_at_monotonic": 0.0,
                "created_at_wall": None,
                "duration_ms": None,
                "issue_count": 0,
                "error": None,
            }
        )
    server_module._api_cache.clear()


@pytest.fixture()
def api_client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(scope="module")
def dashboard_script() -> str:
    html = (
        Path(__file__).resolve().parents[1]
        / "oompah"
        / "templates"
        / "dashboard.html"
    ).read_text()
    start = html.index("<script>") + len("<script>")
    end = html.rindex("</script>")
    return html[start:end]


def _make_project(project_id: str = "proj-1", name: str = "ProjectName") -> Project:
    return Project(
        id=project_id,
        name=name,
        repo_url="https://example.invalid/repo.git",
        repo_path="/tmp/repo",
    )


def _make_issue(
    identifier: str = "TASK-1234",
    *,
    issue_id: str | None = None,
    issue_type: str = "task",
    parent_id: str | None = None,
) -> Issue:
    return Issue(
        id=issue_id or identifier,
        identifier=identifier,
        title="Test task",
        description="A task",
        state="open",
        priority=2,
        issue_type=issue_type,
        parent_id=parent_id,
        labels=[],
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )


def _make_orch(project: Project, tracker: MagicMock) -> MagicMock:
    orch = MagicMock()
    orch.project_store.list_all.return_value = [project]
    orch._tracker_for_project.return_value = tracker
    orch.tracker = tracker
    return orch


def test_display_identifier_formats_backlog_task_ids_with_project_name():
    assert server_module._display_identifier("TASK-1234", "ProjectName") == (
        "ProjectName-1234"
    )
    assert server_module._display_identifier("bug-1234", "ProjectName") == "bug-1234"
    assert (
        server_module._display_identifier("TASK-TASK-", "ProjectName")
        == "TASK-TASK-"
    )
    assert server_module._display_identifier("TASK-1234", None) == "TASK-1234"


def test_api_issues_includes_project_scoped_display_identifier(api_client):
    project = _make_project()
    issue = _make_issue("TASK-1234")
    tracker = MagicMock()
    tracker.fetch_all_issues.return_value = [issue]
    orch = _make_orch(project, tracker)

    with patch.object(server_module, "_get_orchestrator", return_value=orch):
        resp = api_client.get("/api/v1/issues")

    assert resp.status_code == 200
    entry = resp.json()["Open"][0]
    assert entry["identifier"] == "TASK-1234"
    assert entry["project_id"] == "proj-1"
    assert entry["project_name"] == "ProjectName"
    assert entry["display_identifier"] == "ProjectName-1234"


def test_websocket_issue_payload_includes_same_display_identifier_shape():
    project = _make_project()
    issue = _make_issue("TASK-1234")
    tracker = MagicMock()
    tracker.fetch_all_issues.return_value = [issue]
    orch = _make_orch(project, tracker)

    data = server_module._fetch_and_serialize_issues(orch)

    entry = data["Open"][0]
    assert entry["identifier"] == "TASK-1234"
    assert entry["project_name"] == "ProjectName"
    assert entry["display_identifier"] == "ProjectName-1234"


def test_detail_endpoint_includes_display_identifier_for_parent_and_children(api_client):
    project = _make_project()
    parent = _make_issue("TASK-1234", issue_id="parent", issue_type="epic")
    child = _make_issue("TASK-1235", issue_id="child")
    tracker = MagicMock()
    tracker.fetch_issue_detail.return_value = parent
    tracker.fetch_children.return_value = [child]
    tracker.fetch_comments.return_value = []
    orch = _make_orch(project, tracker)

    with patch.object(server_module, "_get_orchestrator", return_value=orch):
        resp = api_client.get(
            "/api/v1/issues/TASK-1234/detail",
            params={"project_id": "proj-1"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["identifier"] == "TASK-1234"
    assert body["display_identifier"] == "ProjectName-1234"
    assert body["project_name"] == "ProjectName"
    assert body["children"][0]["identifier"] == "TASK-1235"
    assert body["children"][0]["display_identifier"] == "ProjectName-1235"


def test_dashboard_uses_display_identifier_for_visible_task_labels(dashboard_script):
    assert "function issueDisplayIdentifier(issue)" in dashboard_script
    assert r"raw.match(/^TASK-(\d+(?:\.\d+)*)$/i)" in dashboard_script
    assert '<span class="card-identifier">${esc(displayIdentifier)}</span>' in (
        dashboard_script
    )
    assert (
        "document.getElementById('detail-panel-title').textContent = "
        "detailDisplayIdentifier;"
    ) in dashboard_script
    assert "esc(issueDisplayIdentifier(issue))" in dashboard_script
    assert "const epicDisplayIdentifier = issueDisplayIdentifier(epic);" in (
        dashboard_script
    )


def test_dashboard_keeps_raw_identifier_for_actions(dashboard_script):
    assert "card.dataset.id = issue.identifier;" in dashboard_script
    assert "openDetailPanel(issue.identifier);" in dashboard_script
    assert "e.dataTransfer.setData('text/plain', issue.identifier);" in dashboard_script
    assert "data-id=\"${esc(issue.identifier)}\"" in dashboard_script
