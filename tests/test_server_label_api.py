"""Tests for the label management REST API endpoints in server.py.

Covers:
  (1) Successful add label (POST /api/v1/issues/{identifier}/labels)
  (2) Successful remove label (DELETE /api/v1/issues/{identifier}/labels/{label})
  (3) broadcast_issues called after label change
  (4) Cache invalidation after label change
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.server import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_orchestrator(project_id: str = "proj-1") -> MagicMock:
    """Build a minimal mock Orchestrator with a stub tracker."""
    mock_tracker = MagicMock()
    mock_tracker.add_label = MagicMock()
    mock_tracker.remove_label = MagicMock()

    mock_orch = MagicMock()
    mock_orch._tracker_for_project = MagicMock(return_value=mock_tracker)

    return mock_orch, mock_tracker


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    """Return a TestClient backed by the FastAPI app."""
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# POST /api/v1/issues/{identifier}/labels
# ---------------------------------------------------------------------------

class TestAddLabelEndpoint:
    """Tests for the POST label endpoint."""

    def test_add_label_success(self, client):
        """POST with a valid label returns 201 ok:True."""
        mock_orch, mock_tracker = _make_mock_orchestrator()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues/my-issue/labels",
                json={"label": "draft", "project_id": "proj-1"},
            )

        assert resp.status_code == 201
        assert resp.json() == {"ok": True}
        mock_tracker.add_label.assert_called_once_with("my-issue", "draft")

    def test_add_label_missing_label_field_returns_400(self, client):
        """POST without 'label' key returns 400 validation error."""
        mock_orch, _ = _make_mock_orchestrator()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues/my-issue/labels",
                json={"project_id": "proj-1"},
            )

        assert resp.status_code == 400
        data = resp.json()
        assert data["error"]["code"] == "validation"

    def test_add_label_empty_label_returns_400(self, client):
        """POST with empty label string returns 400 validation error."""
        mock_orch, _ = _make_mock_orchestrator()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues/my-issue/labels",
                json={"label": "   ", "project_id": "proj-1"},
            )

        assert resp.status_code == 400

    def test_add_label_calls_broadcast_issues(self, client):
        """POST label endpoint must call broadcast_issues after the change."""
        mock_orch, _ = _make_mock_orchestrator()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock) as mock_broadcast,
        ):
            client.post(
                "/api/v1/issues/my-issue/labels",
                json={"label": "draft", "project_id": "proj-1"},
            )

        mock_broadcast.assert_awaited_once()

    def test_add_label_invalidates_issues_cache(self, client):
        """POST label endpoint must invalidate the issues:all cache key."""
        mock_orch, _ = _make_mock_orchestrator()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
            patch.object(server_module._api_cache, "invalidate") as mock_invalidate,
        ):
            client.post(
                "/api/v1/issues/my-issue/labels",
                json={"label": "draft", "project_id": "proj-1"},
            )

        invalidated_keys = [call.args[0] for call in mock_invalidate.call_args_list]
        assert "issues:all" in invalidated_keys

    def test_add_label_invalidates_detail_cache(self, client):
        """POST label endpoint must invalidate the detail cache for the issue."""
        mock_orch, _ = _make_mock_orchestrator()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
            patch.object(server_module._api_cache, "invalidate_prefix") as mock_inv_prefix,
        ):
            client.post(
                "/api/v1/issues/my-issue/labels",
                json={"label": "draft", "project_id": "proj-1"},
            )

        called_with = [call.args[0] for call in mock_inv_prefix.call_args_list]
        assert any("my-issue" in k for k in called_with)

    def test_add_label_tracker_error_returns_500(self, client):
        """If tracker.add_label raises, endpoint returns 500."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_tracker.add_label.side_effect = Exception("tracker down")

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues/my-issue/labels",
                json={"label": "draft", "project_id": "proj-1"},
            )

        assert resp.status_code == 500
        assert resp.json()["error"]["code"] == "label_failed"


# ---------------------------------------------------------------------------
# DELETE /api/v1/issues/{identifier}/labels/{label}
# ---------------------------------------------------------------------------

class TestRemoveLabelEndpoint:
    """Tests for the DELETE label endpoint."""

    def test_remove_label_success(self, client):
        """DELETE returns 200 ok:True and calls tracker.remove_label."""
        mock_orch, mock_tracker = _make_mock_orchestrator()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.delete(
                "/api/v1/issues/my-issue/labels/draft",
                params={"project_id": "proj-1"},
            )

        assert resp.status_code == 200
        assert resp.json() == {"ok": True}
        mock_tracker.remove_label.assert_called_once_with("my-issue", "draft")

    def test_remove_label_calls_broadcast_issues(self, client):
        """DELETE label endpoint must call broadcast_issues after the change."""
        mock_orch, _ = _make_mock_orchestrator()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock) as mock_broadcast,
        ):
            client.delete(
                "/api/v1/issues/my-issue/labels/draft",
                params={"project_id": "proj-1"},
            )

        mock_broadcast.assert_awaited_once()

    def test_remove_label_invalidates_issues_cache(self, client):
        """DELETE label endpoint must invalidate the issues:all cache key."""
        mock_orch, _ = _make_mock_orchestrator()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
            patch.object(server_module._api_cache, "invalidate") as mock_invalidate,
        ):
            client.delete(
                "/api/v1/issues/my-issue/labels/draft",
                params={"project_id": "proj-1"},
            )

        invalidated_keys = [call.args[0] for call in mock_invalidate.call_args_list]
        assert "issues:all" in invalidated_keys

    def test_remove_label_invalidates_detail_cache(self, client):
        """DELETE label endpoint must invalidate the detail cache for the issue."""
        mock_orch, _ = _make_mock_orchestrator()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
            patch.object(server_module._api_cache, "invalidate_prefix") as mock_inv_prefix,
        ):
            client.delete(
                "/api/v1/issues/my-issue/labels/draft",
                params={"project_id": "proj-1"},
            )

        called_with = [call.args[0] for call in mock_inv_prefix.call_args_list]
        assert any("my-issue" in k for k in called_with)

    def test_remove_label_tracker_error_returns_500(self, client):
        """If tracker.remove_label raises, endpoint returns 500."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_tracker.remove_label.side_effect = Exception("tracker down")

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.delete(
                "/api/v1/issues/my-issue/labels/draft",
                params={"project_id": "proj-1"},
            )

        assert resp.status_code == 500
        assert resp.json()["error"]["code"] == "label_failed"

    def test_remove_label_url_encoded_label(self, client):
        """DELETE should handle hyphenated label names in the URL path."""
        mock_orch, mock_tracker = _make_mock_orchestrator()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.delete(
                "/api/v1/issues/my-issue/labels/ci-fix",
                params={"project_id": "proj-1"},
            )

        assert resp.status_code == 200
        mock_tracker.remove_label.assert_called_once_with("my-issue", "ci-fix")
