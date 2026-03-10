"""Tests for the issue detail REST API endpoint in server.py.

Covers:
  (1) GET /api/v1/issues/{identifier}/detail with project_id returns detail
  (2) GET /api/v1/issues/{identifier}/detail without project_id searches all projects
  (3) Without project_id, returns 404 if issue not found in any project
  (4) With project_id, returns 503 if tracker raises
  (5) Caching behavior for detail endpoint
  (6) _find_tracker_for_issue helper: legacy mode (no projects)
  (7) _find_tracker_for_issue helper: multi-project search
  (8) _find_tracker_for_issue helper: returns None when not found
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.server import app, _find_tracker_for_issue
from oompah.models import Issue


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_issue(
    identifier: str = "my-issue",
    issue_type: str = "task",
    title: str = "Test Issue",
) -> Issue:
    """Build a minimal Issue object for use in test stubs."""
    return Issue(
        id=identifier,
        identifier=identifier,
        title=title,
        state="open",
        issue_type=issue_type,
        description="A test issue",
        priority=2,
        labels=["draft"],
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )


def _make_mock_orchestrator(project_id: str = "proj-1") -> tuple[MagicMock, MagicMock]:
    """Build a minimal mock Orchestrator with a stub tracker."""
    mock_tracker = MagicMock()
    mock_tracker.fetch_issue_detail = MagicMock()
    mock_tracker.fetch_comments = MagicMock(return_value=[])
    mock_tracker.fetch_children = MagicMock(return_value=[])

    mock_project = MagicMock()
    mock_project.id = project_id

    mock_orch = MagicMock()
    mock_orch._tracker_for_project = MagicMock(return_value=mock_tracker)
    mock_orch.project_store.list_all = MagicMock(return_value=[mock_project])
    mock_orch.tracker = mock_tracker  # legacy fallback

    return mock_orch, mock_tracker


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    """Return a TestClient backed by the FastAPI app."""
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# GET /api/v1/issues/{identifier}/detail with project_id
# ---------------------------------------------------------------------------

class TestIssueDetailWithProjectId:
    """Tests for the detail endpoint when project_id is provided."""

    def test_returns_200_with_valid_project_id(self, client):
        """GET with project_id returns 200 and issue data."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        issue = _make_mock_issue()
        mock_tracker.fetch_issue_detail.return_value = issue

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module._api_cache, "get", return_value=None),
            patch.object(server_module._api_cache, "set"),
        ):
            resp = client.get(
                "/api/v1/issues/my-issue/detail",
                params={"project_id": "proj-1"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["identifier"] == "my-issue"
        assert data["title"] == "Test Issue"
        assert data["project_id"] == "proj-1"

    def test_returns_404_when_issue_not_found(self, client):
        """GET with project_id returns 404 when tracker returns None."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_tracker.fetch_issue_detail.return_value = None

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module._api_cache, "get", return_value=None),
        ):
            resp = client.get(
                "/api/v1/issues/missing-issue/detail",
                params={"project_id": "proj-1"},
            )

        assert resp.status_code == 404
        data = resp.json()
        assert data["error"]["code"] == "issue_not_found"

    def test_includes_comments_in_response(self, client):
        """GET detail always includes comments in the response."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        issue = _make_mock_issue()
        mock_tracker.fetch_issue_detail.return_value = issue
        mock_tracker.fetch_comments.return_value = [{"id": 1, "text": "hello"}]

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module._api_cache, "get", return_value=None),
            patch.object(server_module._api_cache, "set"),
        ):
            resp = client.get(
                "/api/v1/issues/my-issue/detail",
                params={"project_id": "proj-1"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "comments" in data
        assert data["comments"] == [{"id": 1, "text": "hello"}]

    def test_returns_children_for_epic(self, client):
        """GET detail for an epic includes children array."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        issue = _make_mock_issue(issue_type="epic")
        child = _make_mock_issue(identifier="child-1", title="Child Issue")
        mock_tracker.fetch_issue_detail.return_value = issue
        mock_tracker.fetch_children.return_value = [child]

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module._api_cache, "get", return_value=None),
            patch.object(server_module._api_cache, "set"),
        ):
            resp = client.get(
                "/api/v1/issues/my-issue/detail",
                params={"project_id": "proj-1"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "children" in data
        assert len(data["children"]) == 1
        assert data["children"][0]["identifier"] == "child-1"

    def test_cache_hit_returns_cached_response(self, client):
        """GET detail returns cached data without calling tracker."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        cached_data = {"id": "cached", "identifier": "my-issue", "from_cache": True}

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module._api_cache, "get", return_value=cached_data),
        ):
            resp = client.get(
                "/api/v1/issues/my-issue/detail",
                params={"project_id": "proj-1"},
            )

        assert resp.status_code == 200
        assert resp.json()["from_cache"] is True
        mock_tracker.fetch_issue_detail.assert_not_called()


# ---------------------------------------------------------------------------
# GET /api/v1/issues/{identifier}/detail without project_id
# ---------------------------------------------------------------------------

class TestIssueDetailWithoutProjectId:
    """Tests for the detail endpoint when project_id is NOT provided."""

    def test_returns_200_by_searching_all_projects(self, client):
        """GET without project_id searches all projects and returns the issue."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        issue = _make_mock_issue()
        mock_tracker.fetch_issue_detail.return_value = issue

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module._api_cache, "get", return_value=None),
            patch.object(server_module._api_cache, "set"),
        ):
            resp = client.get("/api/v1/issues/my-issue/detail")

        assert resp.status_code == 200
        data = resp.json()
        assert data["identifier"] == "my-issue"
        assert data["title"] == "Test Issue"

    def test_returns_404_when_not_found_in_any_project(self, client):
        """GET without project_id returns 404 if issue not found in any project."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_tracker.fetch_issue_detail.return_value = None

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module._api_cache, "get", return_value=None),
        ):
            resp = client.get("/api/v1/issues/missing-issue/detail")

        assert resp.status_code == 404
        data = resp.json()
        assert data["error"]["code"] == "issue_not_found"

    def test_project_id_resolved_from_search_is_included_in_response(self, client):
        """When project_id is resolved by search, it appears in the response body."""
        mock_orch, mock_tracker = _make_mock_orchestrator(project_id="proj-99")
        issue = _make_mock_issue()
        mock_tracker.fetch_issue_detail.return_value = issue

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module._api_cache, "get", return_value=None),
            patch.object(server_module._api_cache, "set"),
        ):
            resp = client.get("/api/v1/issues/my-issue/detail")

        assert resp.status_code == 200
        data = resp.json()
        # The resolved project_id should be in the response
        assert data["project_id"] == "proj-99"

    def test_does_not_raise_503_on_missing_project_id(self, client):
        """Calling without project_id must NOT return 503 (the old bug)."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        issue = _make_mock_issue()
        mock_tracker.fetch_issue_detail.return_value = issue

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module._api_cache, "get", return_value=None),
            patch.object(server_module._api_cache, "set"),
        ):
            resp = client.get("/api/v1/issues/my-issue/detail")

        # Must NOT be 503 (the old "project_id is required" error)
        assert resp.status_code != 503

    def test_cache_hit_returns_cached_response_without_project_id(self, client):
        """GET detail returns cached data even without project_id in the URL."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        cached_data = {"id": "cached", "identifier": "my-issue", "from_cache": True}

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module._api_cache, "get", return_value=cached_data),
        ):
            resp = client.get("/api/v1/issues/my-issue/detail")

        assert resp.status_code == 200
        assert resp.json()["from_cache"] is True
        mock_tracker.fetch_issue_detail.assert_not_called()


# ---------------------------------------------------------------------------
# _find_tracker_for_issue helper tests
# ---------------------------------------------------------------------------

class TestFindTrackerForIssue:
    """Unit tests for the _find_tracker_for_issue helper function."""

    def test_legacy_mode_returns_tracker_when_issue_found(self):
        """When no projects configured, uses orch.tracker in legacy mode."""
        mock_tracker = MagicMock()
        mock_tracker.fetch_issue_detail.return_value = _make_mock_issue()

        mock_orch = MagicMock()
        mock_orch.project_store.list_all.return_value = []
        mock_orch.tracker = mock_tracker

        tracker, project_id = _find_tracker_for_issue(mock_orch, "my-issue")

        assert tracker is mock_tracker
        assert project_id is None

    def test_legacy_mode_returns_none_when_issue_not_found(self):
        """When no projects and issue not found in legacy tracker, returns None."""
        mock_tracker = MagicMock()
        mock_tracker.fetch_issue_detail.return_value = None

        mock_orch = MagicMock()
        mock_orch.project_store.list_all.return_value = []
        mock_orch.tracker = mock_tracker

        tracker, project_id = _find_tracker_for_issue(mock_orch, "missing")

        assert tracker is None
        assert project_id is None

    def test_multi_project_finds_issue_in_first_matching_project(self):
        """With multiple projects, returns tracker from first project that has the issue."""
        mock_tracker_1 = MagicMock()
        mock_tracker_1.fetch_issue_detail.return_value = None  # not found in proj-1

        mock_tracker_2 = MagicMock()
        mock_tracker_2.fetch_issue_detail.return_value = _make_mock_issue()  # found in proj-2

        mock_project_1 = MagicMock()
        mock_project_1.id = "proj-1"
        mock_project_2 = MagicMock()
        mock_project_2.id = "proj-2"

        def _tracker_for_project(pid):
            return mock_tracker_1 if pid == "proj-1" else mock_tracker_2

        mock_orch = MagicMock()
        mock_orch.project_store.list_all.return_value = [mock_project_1, mock_project_2]
        mock_orch._tracker_for_project.side_effect = _tracker_for_project

        tracker, project_id = _find_tracker_for_issue(mock_orch, "my-issue")

        assert tracker is mock_tracker_2
        assert project_id == "proj-2"

    def test_multi_project_returns_none_when_not_found_in_any(self):
        """With multiple projects, returns (None, None) if no project has the issue."""
        mock_tracker = MagicMock()
        mock_tracker.fetch_issue_detail.return_value = None

        mock_project = MagicMock()
        mock_project.id = "proj-1"

        mock_orch = MagicMock()
        mock_orch.project_store.list_all.return_value = [mock_project]
        mock_orch._tracker_for_project.return_value = mock_tracker

        tracker, project_id = _find_tracker_for_issue(mock_orch, "missing-issue")

        assert tracker is None
        assert project_id is None

    def test_continues_search_when_tracker_raises(self):
        """If a tracker raises on fetch_issue_detail, the search continues to next project."""
        mock_tracker_1 = MagicMock()
        mock_tracker_1.fetch_issue_detail.side_effect = Exception("tracker down")

        mock_tracker_2 = MagicMock()
        mock_tracker_2.fetch_issue_detail.return_value = _make_mock_issue()

        mock_project_1 = MagicMock()
        mock_project_1.id = "proj-1"
        mock_project_2 = MagicMock()
        mock_project_2.id = "proj-2"

        def _tracker_for_project(pid):
            return mock_tracker_1 if pid == "proj-1" else mock_tracker_2

        mock_orch = MagicMock()
        mock_orch.project_store.list_all.return_value = [mock_project_1, mock_project_2]
        mock_orch._tracker_for_project.side_effect = _tracker_for_project

        tracker, project_id = _find_tracker_for_issue(mock_orch, "my-issue")

        assert tracker is mock_tracker_2
        assert project_id == "proj-2"
