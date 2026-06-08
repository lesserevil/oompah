"""Tests for the release-picks REST API endpoints in server.py (TASK-456.1).

Covers:
  GET /api/v1/issues/{identifier}/release-picks
    - Returns 200 with normalised release-pick data
    - Returns 404 when issue not found
    - Returns 503 on unexpected errors
    - Passes project to enable validation when project_id supplied

  PATCH /api/v1/issues/{identifier}/release-picks
    - Returns 400 on missing project_id
    - Returns 400 on invalid JSON
    - Returns 400 when neither 'branch' nor 'backports' supplied
    - Returns 400 on branch validation failure
    - Returns 200 with updated data on single-entry update
    - Returns 200 with updated data on bulk update
    - Returns 404 when project not found
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.server import app
from oompah.models import Issue, Project


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _make_issue(identifier: str = "TASK-1") -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title="A task",
        description="",
        state="open",
        priority=2,
        issue_type="task",
        labels=[],
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )


def _make_tracker(meta: dict | None = None) -> MagicMock:
    tracker = MagicMock()
    tracker.get_metadata = MagicMock(return_value=meta or {})
    tracker.set_metadata_field = MagicMock()
    tracker.fetch_issue_detail = MagicMock(return_value=None)
    return tracker


def _make_project(pid: str = "proj-1") -> MagicMock:
    project = MagicMock(spec=Project)
    project.id = pid
    project.name = "Test Project"
    project.branches = ["release/*", "main"]
    project.default_branch = "main"
    project.matches_branch = MagicMock(side_effect=lambda b: b.startswith("release/") or b == "main")
    return project


def _make_orchestrator(
    *,
    tracker: MagicMock | None = None,
    issue: Issue | None = None,
    project: MagicMock | None = None,
    project_id: str = "proj-1",
) -> MagicMock:
    t = tracker or _make_tracker()
    p = project or _make_project(project_id)
    orch = MagicMock()
    orch._tracker_for_project = MagicMock(return_value=t)
    orch.project_store.list_all = MagicMock(return_value=[p])
    orch.project_store.get = MagicMock(return_value=p)
    # Wire fetch_issue_detail so _find_tracker_for_issue works
    t.fetch_issue_detail = MagicMock(return_value=issue)
    return orch, t, p


@pytest.fixture()
def client():
    server_module._api_cache.invalidate_prefix("detail:")
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# GET /api/v1/issues/{identifier}/release-picks
# ---------------------------------------------------------------------------


class TestGetReleasePicksEndpoint:
    def test_returns_200_with_empty_picks(self, client):
        issue = _make_issue("TASK-1")
        orch, tracker, project = _make_orchestrator(issue=issue)

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get(
                "/api/v1/issues/TASK-1/release-picks",
                params={"project_id": "proj-1"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["identifier"] == "TASK-1"
        assert data["backports"] == []
        assert data["backport_of"] is None

    def test_returns_normalised_backports(self, client):
        meta = {
            "oompah.backports": [
                {
                    "branch": "release/1.0",
                    "status": "pr_open",
                    "task_id": "TASK-1.1",
                    "pr_url": "https://github.com/org/repo/pull/42",
                }
            ]
        }
        issue = _make_issue("TASK-1")
        orch, tracker, project = _make_orchestrator(issue=issue)
        tracker.get_metadata = MagicMock(return_value=meta)

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get(
                "/api/v1/issues/TASK-1/release-picks",
                params={"project_id": "proj-1"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["backports"]) == 1
        entry = data["backports"][0]
        assert entry["branch"] == "release/1.0"
        assert entry["status"] == "pr_open"
        assert entry["task_id"] == "TASK-1.1"
        assert entry["pr_url"] == "https://github.com/org/repo/pull/42"
        assert entry["pr_id"] == "42"
        assert entry["is_valid"] is True

    def test_returns_backport_of(self, client):
        meta = {"oompah.backport_of": "TASK-100"}
        issue = _make_issue("TASK-100.1")
        orch, tracker, project = _make_orchestrator(issue=issue)
        tracker.get_metadata = MagicMock(return_value=meta)

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get(
                "/api/v1/issues/TASK-100.1/release-picks",
                params={"project_id": "proj-1"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["backport_of"]["source"] == "TASK-100"
        assert data["backport_of"]["status"] == "waiting"

    def test_returns_404_when_issue_not_found(self, client):
        orch, tracker, project = _make_orchestrator(issue=None)

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get(
                "/api/v1/issues/TASK-MISSING/release-picks",
                params={"project_id": "proj-1"},
            )

        assert resp.status_code == 404
        data = resp.json()
        assert data["error"]["code"] == "issue_not_found"

    def test_returns_503_on_unexpected_error(self, client):
        with patch.object(server_module, "_get_orchestrator", side_effect=RuntimeError("boom")):
            resp = client.get("/api/v1/issues/TASK-1/release-picks")

        assert resp.status_code == 503

    def test_works_without_project_id(self, client):
        """Should search all projects when project_id is omitted."""
        issue = _make_issue("TASK-2")
        orch, tracker, project = _make_orchestrator(issue=issue)

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get("/api/v1/issues/TASK-2/release-picks")

        assert resp.status_code == 200
        data = resp.json()
        assert data["identifier"] == "TASK-2"

    def test_validation_marks_invalid_branch(self, client):
        meta = {"oompah.backports": ["bad-branch"]}
        issue = _make_issue("TASK-3")
        orch, tracker, project = _make_orchestrator(issue=issue)
        tracker.get_metadata = MagicMock(return_value=meta)
        # Project only matches "release/*"
        project.matches_branch = MagicMock(side_effect=lambda b: b.startswith("release/"))

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get(
                "/api/v1/issues/TASK-3/release-picks",
                params={"project_id": "proj-1"},
            )

        assert resp.status_code == 200
        entry = resp.json()["backports"][0]
        assert entry["is_valid"] is False
        assert entry["validation_error"] is not None


# ---------------------------------------------------------------------------
# PATCH /api/v1/issues/{identifier}/release-picks
# ---------------------------------------------------------------------------


class TestPatchReleasePicksEndpoint:
    def test_returns_400_when_no_project_id(self, client):
        resp = client.patch(
            "/api/v1/issues/TASK-1/release-picks",
            json={"branch": "release/1.0"},
        )
        assert resp.status_code == 400
        data = resp.json()
        assert "project_id" in data["error"]["message"]

    def test_returns_400_on_invalid_json(self, client):
        resp = client.patch(
            "/api/v1/issues/TASK-1/release-picks",
            data="not-json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400

    def test_returns_400_when_no_branch_or_backports(self, client):
        orch, tracker, project = _make_orchestrator(issue=_make_issue("TASK-1"))

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.patch(
                "/api/v1/issues/TASK-1/release-picks",
                json={"project_id": "proj-1", "status": "waiting"},
            )

        assert resp.status_code == 400
        assert "branch" in resp.json()["error"]["message"]

    def test_single_entry_update_returns_200(self, client):
        issue = _make_issue("TASK-5")
        orch, tracker, project = _make_orchestrator(issue=issue)

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.patch(
                "/api/v1/issues/TASK-5/release-picks",
                json={
                    "project_id": "proj-1",
                    "branch": "release/1.0",
                    "status": "waiting",
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["identifier"] == "TASK-5"
        assert len(data["backports"]) == 1
        assert data["backports"][0]["branch"] == "release/1.0"

    def test_single_entry_with_all_fields(self, client):
        issue = _make_issue("TASK-6")
        orch, tracker, project = _make_orchestrator(issue=issue)

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.patch(
                "/api/v1/issues/TASK-6/release-picks",
                json={
                    "project_id": "proj-1",
                    "branch": "release/2.0",
                    "status": "pr_open",
                    "task_id": "TASK-6.1",
                    "pr_url": "https://github.com/org/repo/pull/88",
                },
            )

        assert resp.status_code == 200
        entry = resp.json()["backports"][0]
        assert entry["status"] == "pr_open"
        assert entry["task_id"] == "TASK-6.1"
        assert entry["pr_url"] == "https://github.com/org/repo/pull/88"
        assert entry["pr_id"] == "88"

    def test_bulk_update_returns_200(self, client):
        issue = _make_issue("TASK-7")
        orch, tracker, project = _make_orchestrator(issue=issue)

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.patch(
                "/api/v1/issues/TASK-7/release-picks",
                json={
                    "project_id": "proj-1",
                    "backports": [
                        {"branch": "release/1.0", "status": "waiting"},
                        {"branch": "release/2.0", "status": "task_created"},
                    ],
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["backports"]) == 2

    def test_bulk_update_returns_400_when_not_list(self, client):
        orch, tracker, project = _make_orchestrator(issue=_make_issue("TASK-8"))

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.patch(
                "/api/v1/issues/TASK-8/release-picks",
                json={"project_id": "proj-1", "backports": "not-a-list"},
            )

        assert resp.status_code == 400
        assert "backports" in resp.json()["error"]["message"]

    def test_single_entry_validation_failure_returns_400(self, client):
        issue = _make_issue("TASK-9")
        orch, tracker, project = _make_orchestrator(issue=issue)
        # Project only allows "release/*"
        project.matches_branch = MagicMock(side_effect=lambda b: b.startswith("release/"))

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.patch(
                "/api/v1/issues/TASK-9/release-picks",
                json={"project_id": "proj-1", "branch": "bad-branch"},
            )

        assert resp.status_code == 400
        data = resp.json()
        assert data["error"]["code"] == "validation"

    def test_bulk_validation_failure_returns_400(self, client):
        issue = _make_issue("TASK-10")
        orch, tracker, project = _make_orchestrator(issue=issue)
        project.matches_branch = MagicMock(side_effect=lambda b: b.startswith("release/"))

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.patch(
                "/api/v1/issues/TASK-10/release-picks",
                json={
                    "project_id": "proj-1",
                    "backports": [
                        {"branch": "release/1.0"},
                        {"branch": "bad-branch"},
                    ],
                },
            )

        assert resp.status_code == 400

    def test_returns_404_when_project_not_found(self, client):
        orch = MagicMock()
        orch._tracker_for_project = MagicMock(side_effect=Exception("Unknown project"))
        orch.project_store.get = MagicMock(return_value=None)

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.patch(
                "/api/v1/issues/TASK-11/release-picks",
                json={"project_id": "nonexistent", "branch": "release/1.0"},
            )

        assert resp.status_code == 404

    def test_set_metadata_field_called_on_write(self, client):
        issue = _make_issue("TASK-12")
        orch, tracker, project = _make_orchestrator(issue=issue)

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.patch(
                "/api/v1/issues/TASK-12/release-picks",
                json={"project_id": "proj-1", "branch": "release/3.0"},
            )

        assert resp.status_code == 200
        tracker.set_metadata_field.assert_called_once()
        call_args = tracker.set_metadata_field.call_args
        assert call_args[0][1] == "oompah.backports"
