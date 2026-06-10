"""Tests for the POST /api/v1/issues/{identifier}/dependencies endpoint.

Covers:
  (1) Successful add_dependency call returns 201 ok:True
  (2) Missing depends_on returns 400
  (3) Empty depends_on returns 400
  (4) Invalid request body returns 400
  (5) issue_key body field overrides path identifier (GitHub slash identifiers)
  (6) issue_key query param overrides path identifier
  (7) project_id provided: uses _get_tracker directly
  (8) No project_id: falls back to _find_tracker_for_issue
  (9) Issue not found when no project_id returns 404
  (10) managed_repo resolves tracker
  (11) managed_repo with invalid format returns 400
  (12) managed_repo not found returns 404
  (13) Tracker error returns 500
  (14) broadcast_issues is called
  (15) Cache is invalidated
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.models import Issue
from oompah.server import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_orchestrator(project_id: str = "proj-1") -> tuple[MagicMock, MagicMock]:
    """Build a minimal mock Orchestrator with a stub tracker."""
    mock_tracker = MagicMock()
    mock_tracker.add_dependency = MagicMock()
    mock_tracker.fetch_issue_detail = MagicMock(
        return_value=Issue(
            id="TASK-1",
            identifier="TASK-1",
            title="Test",
            state="open",
        )
    )

    mock_project = MagicMock()
    mock_project.id = project_id

    mock_orch = MagicMock()
    mock_orch._tracker_for_project = MagicMock(return_value=mock_tracker)
    mock_orch.project_store.list_all = MagicMock(return_value=[mock_project])
    mock_orch.tracker = mock_tracker

    return mock_orch, mock_tracker


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client():
    """Return a TestClient backed by the FastAPI app."""
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# POST /api/v1/issues/{identifier}/dependencies
# ---------------------------------------------------------------------------


class TestAddDependencyEndpoint:
    """Tests for POST /api/v1/issues/{identifier}/dependencies."""

    def test_add_dependency_success(self, client):
        """POST with valid depends_on returns 201 ok:True."""
        mock_orch, mock_tracker = _make_mock_orchestrator()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues/TASK-2/dependencies",
                json={"depends_on": "TASK-1", "project_id": "proj-1"},
            )

        assert resp.status_code == 201
        assert resp.json() == {"ok": True}
        mock_tracker.add_dependency.assert_called_once_with("TASK-2", "TASK-1")

    def test_missing_depends_on_returns_400(self, client):
        """POST without depends_on returns 400 validation error."""
        mock_orch, _ = _make_mock_orchestrator()

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = client.post(
                "/api/v1/issues/TASK-2/dependencies",
                json={"project_id": "proj-1"},
            )

        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "validation"

    def test_empty_depends_on_returns_400(self, client):
        """POST with empty depends_on returns 400 validation error."""
        mock_orch, _ = _make_mock_orchestrator()

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = client.post(
                "/api/v1/issues/TASK-2/dependencies",
                json={"depends_on": "  ", "project_id": "proj-1"},
            )

        assert resp.status_code == 400

    def test_invalid_json_returns_400(self, client):
        """POST with non-JSON body returns 400."""
        mock_orch, _ = _make_mock_orchestrator()

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = client.post(
                "/api/v1/issues/TASK-2/dependencies",
                content=b"not json",
                headers={"Content-Type": "application/json"},
            )

        assert resp.status_code == 400

    def test_non_dict_body_returns_400(self, client):
        """POST with a JSON array body returns 400."""
        mock_orch, _ = _make_mock_orchestrator()

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = client.post(
                "/api/v1/issues/TASK-2/dependencies",
                json=["bad", "body"],
            )

        assert resp.status_code == 400

    def test_issue_key_body_overrides_path_identifier(self, client):
        """issue_key in body is used as canonical identifier."""
        mock_orch, mock_tracker = _make_mock_orchestrator()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues/placeholder/dependencies",
                json={
                    "depends_on": "TASK-1",
                    "issue_key": "owner/repo#42",
                    "project_id": "proj-1",
                },
            )

        assert resp.status_code == 201
        mock_tracker.add_dependency.assert_called_once_with("owner/repo#42", "TASK-1")

    def test_issue_key_query_param_overrides_path_identifier(self, client):
        """issue_key query param is used as canonical identifier."""
        mock_orch, mock_tracker = _make_mock_orchestrator()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues/placeholder/dependencies?issue_key=owner%2Frepo%2342",
                json={"depends_on": "TASK-1", "project_id": "proj-1"},
            )

        assert resp.status_code == 201
        mock_tracker.add_dependency.assert_called_once_with("owner/repo#42", "TASK-1")

    def test_with_project_id_uses_tracker_directly(self, client):
        """When project_id is given, _get_tracker is called without search."""
        mock_orch, mock_tracker = _make_mock_orchestrator()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues/TASK-2/dependencies",
                json={"depends_on": "TASK-1", "project_id": "proj-1"},
            )

        assert resp.status_code == 201
        mock_orch._tracker_for_project.assert_called_with("proj-1")

    def test_no_project_id_falls_back_to_search(self, client):
        """Without project_id, _find_tracker_for_issue is used."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_issue = Issue(id="TASK-2", identifier="TASK-2", title="T", state="open")

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(
                server_module,
                "_find_tracker_for_issue",
                return_value=(mock_tracker, "proj-1", mock_issue),
            ),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues/TASK-2/dependencies",
                json={"depends_on": "TASK-1"},
            )

        assert resp.status_code == 201
        mock_tracker.add_dependency.assert_called_once_with("TASK-2", "TASK-1")

    def test_issue_not_found_without_project_id_returns_404(self, client):
        """Returns 404 when issue not found in any project."""
        mock_orch, _ = _make_mock_orchestrator()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(
                server_module,
                "_find_tracker_for_issue",
                return_value=(None, None, None),
            ),
        ):
            resp = client.post(
                "/api/v1/issues/TASK-999/dependencies",
                json={"depends_on": "TASK-1"},
            )

        assert resp.status_code == 404
        body = resp.json()
        assert body["error"]["code"] == "issue_not_found"

    def test_managed_repo_resolves_tracker(self, client):
        """managed_repo is accepted as an alternative to project_id."""
        mock_orch, mock_tracker = _make_mock_orchestrator()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(
                server_module,
                "_get_tracker_for_managed_repo",
                return_value=(mock_tracker, "proj-1"),
            ),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues/TASK-2/dependencies",
                json={
                    "depends_on": "TASK-1",
                    "managed_repo": "owner/repo",
                },
            )

        assert resp.status_code == 201

    def test_managed_repo_invalid_format_returns_400(self, client):
        """managed_repo without slash returns 400."""
        mock_orch, _ = _make_mock_orchestrator()

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = client.post(
                "/api/v1/issues/TASK-2/dependencies",
                json={
                    "depends_on": "TASK-1",
                    "managed_repo": "noslash",
                },
            )

        assert resp.status_code == 400

    def test_managed_repo_not_found_returns_404(self, client):
        """managed_repo pointing to unknown project returns 404."""
        mock_orch, _ = _make_mock_orchestrator()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(
                server_module,
                "_get_tracker_for_managed_repo",
                side_effect=ValueError("not found"),
            ),
        ):
            resp = client.post(
                "/api/v1/issues/TASK-2/dependencies",
                json={
                    "depends_on": "TASK-1",
                    "managed_repo": "owner/unknown",
                },
            )

        assert resp.status_code == 404

    def test_tracker_error_returns_500(self, client):
        """Tracker exceptions are caught and returned as 500."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_tracker.add_dependency.side_effect = RuntimeError("disk full")

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues/TASK-2/dependencies",
                json={"depends_on": "TASK-1", "project_id": "proj-1"},
            )

        assert resp.status_code == 500
        body = resp.json()
        assert body["error"]["code"] == "dependency_failed"

    def test_broadcast_issues_called_on_success(self, client):
        """broadcast_issues is called after a successful dependency add."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        broadcast_mock = AsyncMock()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", broadcast_mock),
        ):
            resp = client.post(
                "/api/v1/issues/TASK-2/dependencies",
                json={"depends_on": "TASK-1", "project_id": "proj-1"},
            )

        assert resp.status_code == 201
        broadcast_mock.assert_called_once()

    def test_cache_invalidated_on_success(self, client):
        """Cache is invalidated after a successful dependency add."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        invalidated: list[str] = []

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
            patch.object(
                server_module._api_cache,
                "invalidate",
                side_effect=lambda k: invalidated.append(k),
            ),
        ):
            resp = client.post(
                "/api/v1/issues/TASK-2/dependencies",
                json={"depends_on": "TASK-1", "project_id": "proj-1"},
            )

        assert resp.status_code == 201
        assert any("issues:all" in k for k in invalidated)
