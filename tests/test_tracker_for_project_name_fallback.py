"""Tests for _tracker_for_project project-name fallback (OOMPAH-161).

Verifies that _tracker_for_project in Orchestrator gracefully resolves
human-readable project names (e.g. "coroot") to their canonical internal
IDs (e.g. "proj-ed624f39") so that callers who only have the project name
do not raise ProjectError("Unknown project: coroot").
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.models import Issue, Project
from oompah.orchestrator import Orchestrator
from oompah.projects import ProjectError, ProjectStore
from oompah.server import app


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
    return store


# ---------------------------------------------------------------------------
# Orchestrator._tracker_for_project — name-based fallback
# ---------------------------------------------------------------------------

class TestTrackerForProjectNameFallback:
    """_tracker_for_project should resolve project names when ID lookup fails."""

    def _make_orch_with_project(self, project_id: str, name: str):
        """Return a minimal Orchestrator-like object with the name-fallback logic."""
        project = _make_project(project_id, name)
        store = _make_mock_store(project)

        # We test via a real Orchestrator instance with a patched project_store
        # and _new_tracker_for_project so we never touch git or the network.
        orch = MagicMock(spec=Orchestrator)
        orch.project_store = store
        orch._project_trackers = {}
        fake_tracker = MagicMock()
        orch._new_tracker_for_project.return_value = fake_tracker

        # Bind the real method to the mock instance
        orch._tracker_for_project = Orchestrator._tracker_for_project.__get__(
            orch, type(orch)
        )
        return orch, fake_tracker, project

    def test_id_lookup_succeeds(self):
        """Canonical project ID resolves without touching find_by_name."""
        orch, fake_tracker, project = self._make_orch_with_project(
            "proj-ed624f39", "coroot"
        )
        result = orch._tracker_for_project("proj-ed624f39")
        assert result is fake_tracker
        orch.project_store.find_by_name.assert_not_called()

    def test_name_fallback_resolves_tracker(self):
        """When ID lookup returns None, fall back to find_by_name."""
        orch, fake_tracker, project = self._make_orch_with_project(
            "proj-ed624f39", "coroot"
        )
        result = orch._tracker_for_project("coroot")
        assert result is fake_tracker
        orch.project_store.find_by_name.assert_called_once_with("coroot")

    def test_name_fallback_caches_by_canonical_id(self):
        """After name-based resolution, the tracker is cached under the canonical ID."""
        orch, fake_tracker, project = self._make_orch_with_project(
            "proj-ed624f39", "coroot"
        )
        orch._tracker_for_project("coroot")
        # The cache must use the canonical ID so a subsequent call by ID is fast.
        assert "proj-ed624f39" in orch._project_trackers
        assert orch._project_trackers["proj-ed624f39"] is fake_tracker

    def test_unknown_project_raises_project_error(self):
        """Both ID and name lookups failing raises ProjectError."""
        orch, _, _ = self._make_orch_with_project("proj-ed624f39", "coroot")
        with pytest.raises(ProjectError, match="Unknown project: nonexistent"):
            orch._tracker_for_project("nonexistent")

    def test_cached_id_skips_store_lookup(self):
        """Subsequent calls with the same ID hit the cache without calling the store."""
        orch, fake_tracker, project = self._make_orch_with_project(
            "proj-ed624f39", "coroot"
        )
        # Warm the cache
        orch._tracker_for_project("proj-ed624f39")
        orch.project_store.get.reset_mock()

        result = orch._tracker_for_project("proj-ed624f39")
        assert result is fake_tracker
        orch.project_store.get.assert_not_called()


# ---------------------------------------------------------------------------
# POST /api/v1/issues — project name accepted as project_id
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    return TestClient(app, raise_server_exceptions=False)


class TestCreateIssueProjectNameFallback:
    """POST /api/v1/issues with project_id=<name> should not raise Unknown project."""

    def _make_orch(self, project_id: str, project_name: str):
        mock_tracker = MagicMock()
        mock_tracker.create_issue.return_value = Issue(
            id="task-1",
            identifier="task-1",
            title="Test",
            state="open",
            issue_type="task",
        )
        mock_tracker.add_label = MagicMock()

        mock_orch = MagicMock()
        # Simulate name-aware _tracker_for_project: only the canonical ID works,
        # but the name resolves to the same tracker.
        def tracker_for(pid):
            if pid in (project_id, project_name):
                return mock_tracker
            from oompah.projects import ProjectError
            raise ProjectError(f"Unknown project: {pid}")

        mock_orch._tracker_for_project.side_effect = tracker_for
        return mock_orch, mock_tracker

    def test_create_issue_with_project_name_returns_201(self, client):
        """Passing a project name as project_id should succeed (HTTP 201)."""
        mock_orch, mock_tracker = self._make_orch("proj-ed624f39", "coroot")

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues",
                json={"title": "Test task", "project_id": "coroot", "description": "Test task description"},
            )

        assert resp.status_code == 201
        assert resp.json()["ok"] is True

    def test_create_issue_with_unknown_project_returns_500(self, client):
        """Passing an unknown project ID/name should return HTTP 500."""
        mock_orch, _ = self._make_orch("proj-ed624f39", "coroot")

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues",
                json={"title": "Test task", "project_id": "totally-unknown", "description": "Test task description"},
            )

        assert resp.status_code == 500
        body = resp.json()
        assert "Unknown project" in body["error"]["message"]
