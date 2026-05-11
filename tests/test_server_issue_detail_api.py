"""Tests for the issue detail / comments REST API endpoints in server.py.

Regression test for oompah-0gd: GET /api/v1/issues/{identifier}/detail
must NOT require project_id — it should fall back to searching all projects
when the query param is missing. Same for GET .../comments.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.server import app
from oompah.models import Issue


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_issue(identifier: str = "abc-1") -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title="Test issue",
        description="An issue",
        state="open",
        priority=2,
        issue_type="task",
        labels=[],
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )


def _make_project(pid: str, name: str = "P"):
    p = MagicMock()
    p.id = pid
    p.name = name
    return p


def _make_orch(*, projects=None, trackers_by_pid=None, legacy_tracker=None):
    """Build a minimal mock orchestrator.

    projects: list of mock projects
    trackers_by_pid: dict pid -> mock tracker
    legacy_tracker: tracker returned when no projects configured
    """
    orch = MagicMock()
    orch.project_store.list_all.return_value = projects or []
    if trackers_by_pid is not None:
        def _tracker_for(pid):
            if pid in trackers_by_pid:
                return trackers_by_pid[pid]
            raise KeyError(pid)
        orch._tracker_for_project.side_effect = _tracker_for
    orch.tracker = legacy_tracker or MagicMock()
    return orch


@pytest.fixture()
def client():
    server_module._api_cache.invalidate_prefix("detail:")
    server_module._api_cache.invalidate_prefix("comments:")
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# _find_tracker_for_issue helper
# ---------------------------------------------------------------------------


class TestFindTrackerForIssue:
    def test_with_explicit_project_id(self):
        issue = _make_mock_issue("abc-1")
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = issue
        orch = _make_orch(trackers_by_pid={"proj-1": tracker})

        t, pid, found = server_module._find_tracker_for_issue(orch, "abc-1", "proj-1")
        assert t is tracker
        assert pid == "proj-1"
        assert found is issue
        tracker.fetch_issue_detail.assert_called_once_with("abc-1")

    def test_search_all_projects_finds_match_in_second(self):
        issue = _make_mock_issue("xyz-9")
        t1 = MagicMock()
        t1.fetch_issue_detail.return_value = None  # not in proj-1
        t2 = MagicMock()
        t2.fetch_issue_detail.return_value = issue  # found in proj-2

        orch = _make_orch(
            projects=[_make_project("proj-1"), _make_project("proj-2")],
            trackers_by_pid={"proj-1": t1, "proj-2": t2},
        )

        t, pid, found = server_module._find_tracker_for_issue(orch, "xyz-9", None)
        assert t is t2
        assert pid == "proj-2"
        assert found is issue

    def test_search_all_projects_not_found(self):
        t1 = MagicMock()
        t1.fetch_issue_detail.return_value = None
        orch = _make_orch(
            projects=[_make_project("proj-1")],
            trackers_by_pid={"proj-1": t1},
        )
        t, pid, found = server_module._find_tracker_for_issue(orch, "nope", None)
        assert t is None
        assert pid is None
        assert found is None

    def test_legacy_mode_no_projects(self):
        legacy = MagicMock()
        issue = _make_mock_issue("a-1")
        legacy.fetch_issue_detail.return_value = issue
        orch = _make_orch(projects=[], legacy_tracker=legacy)
        t, pid, found = server_module._find_tracker_for_issue(orch, "a-1", None)
        assert t is legacy
        assert pid is None
        assert found is issue

    def test_tracker_exception_is_swallowed(self):
        t1 = MagicMock()
        t1.fetch_issue_detail.side_effect = RuntimeError("bd broken")
        t2 = MagicMock()
        t2.fetch_issue_detail.return_value = _make_mock_issue("a-1")
        orch = _make_orch(
            projects=[_make_project("proj-1"), _make_project("proj-2")],
            trackers_by_pid={"proj-1": t1, "proj-2": t2},
        )
        t, pid, found = server_module._find_tracker_for_issue(orch, "a-1", None)
        assert t is t2
        assert pid == "proj-2"
        assert found is not None


# ---------------------------------------------------------------------------
# GET /api/v1/issues/{identifier}/detail
# ---------------------------------------------------------------------------


class TestIssueDetailEndpointProjectIdOptional:
    def test_missing_project_id_searches_all_projects(self, client):
        """Regression for oompah-0gd: no project_id should NOT return 503."""
        issue = _make_mock_issue("abc-1")
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = issue
        tracker.fetch_comments.return_value = []

        orch = _make_orch(
            projects=[_make_project("proj-1")],
            trackers_by_pid={"proj-1": tracker},
        )
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get("/api/v1/issues/abc-1/detail")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["identifier"] == "abc-1"
        assert body["project_id"] == "proj-1"

    def test_with_explicit_project_id_works(self, client):
        issue = _make_mock_issue("abc-1")
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = issue
        tracker.fetch_comments.return_value = []
        orch = _make_orch(
            projects=[_make_project("proj-1")],
            trackers_by_pid={"proj-1": tracker},
        )
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get("/api/v1/issues/abc-1/detail?project_id=proj-1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["project_id"] == "proj-1"

    def test_not_found_returns_404(self, client):
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = None
        orch = _make_orch(
            projects=[_make_project("proj-1")],
            trackers_by_pid={"proj-1": tracker},
        )
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get("/api/v1/issues/nope/detail")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "issue_not_found"

    def test_no_error_about_project_id_required(self, client):
        """Make sure we never echo 'project_id is required' for the detail endpoint."""
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = None
        orch = _make_orch(
            projects=[_make_project("proj-1")],
            trackers_by_pid={"proj-1": tracker},
        )
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get("/api/v1/issues/abc-1/detail")
        # Could be 404 (not found) but never a 5xx with the legacy message
        assert resp.status_code != 503
        assert "project_id is required" not in resp.text


# ---------------------------------------------------------------------------
# GET /api/v1/issues/{identifier}/comments
# ---------------------------------------------------------------------------


class TestCommentsEndpointProjectIdOptional:
    def test_missing_project_id_searches_all_projects(self, client):
        issue = _make_mock_issue("abc-1")
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = issue
        tracker.fetch_comments.return_value = [{"author": "a", "text": "hi"}]
        orch = _make_orch(
            projects=[_make_project("proj-1")],
            trackers_by_pid={"proj-1": tracker},
        )
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get("/api/v1/issues/abc-1/comments")
        assert resp.status_code == 200, resp.text
        assert resp.json() == [{"author": "a", "text": "hi"}]

    def test_not_found_returns_404(self, client):
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = None
        orch = _make_orch(
            projects=[_make_project("proj-1")],
            trackers_by_pid={"proj-1": tracker},
        )
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get("/api/v1/issues/nope/comments")
        assert resp.status_code == 404
