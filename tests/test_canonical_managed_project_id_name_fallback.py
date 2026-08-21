"""Tests for _canonical_managed_project_id project-name fallback (OOMPAH-1256).

Verifies that _canonical_managed_project_id gracefully resolves human-readable
project names (e.g. "coroot") to their canonical internal IDs (e.g. "proj-ed624f39")
so that callers who only have the project name do not raise ProjectError("Unknown project").

This is particularly important for the add-comment API endpoint which uses
_canonical_managed_project_id to validate project IDs before resolving trackers.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.models import Issue, Project
from oompah.projects import ProjectError, ProjectStore
from oompah.server import app, _canonical_managed_project_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_project(project_id: str, name: str) -> Project:
    return Project(
        id=project_id,
        name=name,
        repo_url=f"https://example.com/{name}.git",
        repo_path=f"/tmp/{name}",
    )


def _make_mock_store(*projects: Project) -> MagicMock:
    """Return a MagicMock ProjectStore that supports get() and find_by_name()."""
    store = MagicMock(spec=ProjectStore)
    id_map = {p.id: p for p in projects}
    name_map = {p.name: p for p in projects}
    store.get.side_effect = lambda pid: id_map.get(pid)
    store.find_by_name.side_effect = lambda name: name_map.get(name)
    store.list_all.return_value = list(projects)
    return store


# ---------------------------------------------------------------------------
# _canonical_managed_project_id — name-based fallback
# ---------------------------------------------------------------------------

class TestCanonicalManagedProjectIdNameFallback:
    """_canonical_managed_project_id should resolve project names when ID lookup fails."""

    def test_canonical_id_lookup_succeeds(self):
        """Canonical project ID resolves without touching find_by_name."""
        project = _make_project("proj-ed624f39", "coroot")
        store = _make_mock_store(project)
        orch = MagicMock()
        orch.project_store = store

        result = _canonical_managed_project_id(orch, "proj-ed624f39")
        
        assert result == "proj-ed624f39"
        store.find_by_name.assert_not_called()

    def test_name_fallback_resolves_canonical_id(self):
        """When ID lookup returns None, fall back to find_by_name."""
        project = _make_project("proj-ed624f39", "coroot")
        store = _make_mock_store(project)
        orch = MagicMock()
        orch.project_store = store

        result = _canonical_managed_project_id(orch, "coroot")
        
        assert result == "proj-ed624f39"
        store.find_by_name.assert_called_once_with("coroot")

    def test_unknown_project_raises_project_error(self):
        """Both ID and name lookups failing raises ProjectError."""
        project = _make_project("proj-ed624f39", "coroot")
        store = _make_mock_store(project)
        orch = MagicMock()
        orch.project_store = store

        with pytest.raises(ProjectError, match="Unknown project"):
            _canonical_managed_project_id(orch, "nonexistent")

    def test_empty_project_store_returns_requested(self):
        """Empty project store (legacy mode) returns the requested ID unchanged."""
        store = _make_mock_store()  # No projects
        orch = MagicMock()
        orch.project_store = store

        result = _canonical_managed_project_id(orch, "anything")
        
        assert result == "anything"

    def test_empty_string_returns_empty(self):
        """Empty project_id is returned as-is."""
        store = _make_mock_store()
        orch = MagicMock()
        orch.project_store = store

        result = _canonical_managed_project_id(orch, "")
        
        assert result == ""

    def test_none_project_id_returns_empty(self):
        """None project_id is returned as empty string."""
        store = _make_mock_store()
        orch = MagicMock()
        orch.project_store = store

        result = _canonical_managed_project_id(orch, None)
        
        assert result == ""


# ---------------------------------------------------------------------------
# POST /api/v1/issues/{id}/comments — project name accepted as project_id
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    return TestClient(app, raise_server_exceptions=False)


class TestAddCommentProjectNameFallback:
    """POST /api/v1/issues/{id}/comments with project_id=<name> should not raise Unknown project."""

    def _make_orch(self, project_id: str, project_name: str):
        mock_tracker = MagicMock()
        mock_tracker.add_comment.return_value = {
            "id": "comment-1",
            "text": "Test comment",
            "author": "user",
        }

        # Create a mock orchestrator that accepts both ID and name
        mock_orch = MagicMock()
        project = _make_project(project_id, project_name)
        store = _make_mock_store(project)
        mock_orch.project_store = store
        mock_orch._tracker_for_project.return_value = mock_tracker
        
        return mock_orch, mock_tracker

    def test_add_comment_with_project_name_succeeds(self, client):
        """Passing a project name as project_id should succeed (HTTP 201)."""
        mock_orch, mock_tracker = self._make_orch("proj-ed624f39", "coroot")

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = client.post(
                "/api/v1/issues/issue-1/comments",
                json={
                    "text": "Test comment",
                    "project_id": "coroot",
                },
            )

        assert resp.status_code == 201

    def test_add_comment_with_canonical_id_succeeds(self, client):
        """Passing a canonical project ID should succeed (HTTP 201)."""
        mock_orch, mock_tracker = self._make_orch("proj-ed624f39", "coroot")

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = client.post(
                "/api/v1/issues/issue-1/comments",
                json={
                    "text": "Test comment",
                    "project_id": "proj-ed624f39",
                },
            )

        assert resp.status_code == 201

    def test_add_comment_with_unknown_project_returns_500(self, client):
        """Passing an unknown project ID/name should return HTTP 500."""
        mock_orch, _ = self._make_orch("proj-ed624f39", "coroot")

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = client.post(
                "/api/v1/issues/issue-1/comments",
                json={
                    "text": "Test comment",
                    "project_id": "totally-unknown",
                },
            )

        assert resp.status_code == 500
        body = resp.json()
        assert "Unknown project" in body["error"]["message"]
