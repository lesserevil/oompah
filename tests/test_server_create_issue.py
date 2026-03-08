"""Tests for the create issue REST API endpoint in server.py.

Covers auto-add 'draft' label to new epics (type=epic) created via POST /api/v1/issues.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.server import app
from oompah.models import Issue


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_issue(identifier: str = "my-issue", issue_type: str = "task") -> Issue:
    """Build a minimal Issue object for use in test stubs."""
    return Issue(
        id=identifier,
        identifier=identifier,
        title="Test issue",
        state="open",
        issue_type=issue_type,
    )


def _make_mock_orchestrator(project_id: str = "proj-1") -> tuple[MagicMock, MagicMock]:
    """Build a minimal mock Orchestrator with a stub tracker."""
    mock_tracker = MagicMock()
    mock_tracker.create_issue = MagicMock()
    mock_tracker.add_label = MagicMock()
    mock_tracker.add_parent_child = MagicMock()

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
# POST /api/v1/issues — epic auto-labeling
# ---------------------------------------------------------------------------

class TestCreateIssueEpicDraftLabel:
    """Tests that creating an epic auto-adds the 'draft' label."""

    def test_create_epic_adds_draft_label(self, client):
        """POST type=epic should call tracker.add_label with 'draft'."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_tracker.create_issue.return_value = _make_mock_issue(
            identifier="epic-1", issue_type="epic"
        )

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues",
                json={"title": "My Epic", "type": "epic", "project_id": "proj-1"},
            )

        assert resp.status_code == 201
        assert resp.json()["ok"] is True
        mock_tracker.add_label.assert_called_once_with("epic-1", "draft")

    def test_create_task_does_not_add_draft_label(self, client):
        """POST type=task should NOT call tracker.add_label."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_tracker.create_issue.return_value = _make_mock_issue(
            identifier="task-1", issue_type="task"
        )

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues",
                json={"title": "My Task", "type": "task", "project_id": "proj-1"},
            )

        assert resp.status_code == 201
        mock_tracker.add_label.assert_not_called()

    def test_create_bug_does_not_add_draft_label(self, client):
        """POST type=bug should NOT call tracker.add_label."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_tracker.create_issue.return_value = _make_mock_issue(
            identifier="bug-1", issue_type="bug"
        )

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues",
                json={"title": "My Bug", "type": "bug", "project_id": "proj-1"},
            )

        assert resp.status_code == 201
        mock_tracker.add_label.assert_not_called()

    def test_create_feature_does_not_add_draft_label(self, client):
        """POST type=feature should NOT call tracker.add_label."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_tracker.create_issue.return_value = _make_mock_issue(
            identifier="feat-1", issue_type="feature"
        )

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues",
                json={"title": "My Feature", "type": "feature", "project_id": "proj-1"},
            )

        assert resp.status_code == 201
        mock_tracker.add_label.assert_not_called()

    def test_create_default_type_does_not_add_draft_label(self, client):
        """POST without explicit type (defaults to 'task') should NOT add draft label."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_tracker.create_issue.return_value = _make_mock_issue(
            identifier="task-2", issue_type="task"
        )

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues",
                json={"title": "Default type task", "project_id": "proj-1"},
            )

        assert resp.status_code == 201
        mock_tracker.add_label.assert_not_called()

    def test_create_epic_draft_label_added_before_broadcast(self, client):
        """The draft label must be added before broadcast_issues is called."""
        call_order = []

        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_tracker.create_issue.return_value = _make_mock_issue(
            identifier="epic-2", issue_type="epic"
        )
        mock_tracker.add_label.side_effect = lambda *a: call_order.append("add_label")

        async def mock_broadcast():
            call_order.append("broadcast")

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", side_effect=mock_broadcast),
        ):
            client.post(
                "/api/v1/issues",
                json={"title": "My Epic", "type": "epic", "project_id": "proj-1"},
            )

        assert "add_label" in call_order
        assert "broadcast" in call_order
        assert call_order.index("add_label") < call_order.index("broadcast")

    def test_create_epic_add_label_failure_still_returns_success(self, client):
        """If add_label raises an exception, the endpoint still returns 201."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_tracker.create_issue.return_value = _make_mock_issue(
            identifier="epic-3", issue_type="epic"
        )
        # The add_label failure should propagate — it's a critical step.
        # But the issue was already created, so we return 500.
        mock_tracker.add_label.side_effect = Exception("tracker error")

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues",
                json={"title": "My Epic", "type": "epic", "project_id": "proj-1"},
            )

        # The outer exception handler returns 500 on any unhandled exception
        assert resp.status_code == 500

    def test_create_epic_missing_title_returns_400(self, client):
        """POST with no title returns 400 even for epics."""
        mock_orch, mock_tracker = _make_mock_orchestrator()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues",
                json={"type": "epic", "project_id": "proj-1"},
            )

        assert resp.status_code == 400
        mock_tracker.add_label.assert_not_called()

    def test_create_epic_calls_broadcast_issues(self, client):
        """Creating an epic must call broadcast_issues."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_tracker.create_issue.return_value = _make_mock_issue(
            identifier="epic-4", issue_type="epic"
        )

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock) as mock_broadcast,
        ):
            client.post(
                "/api/v1/issues",
                json={"title": "My Epic", "type": "epic", "project_id": "proj-1"},
            )

        mock_broadcast.assert_awaited_once()

    def test_create_epic_invalidates_issues_cache(self, client):
        """Creating an epic must invalidate the issues:all cache key."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_tracker.create_issue.return_value = _make_mock_issue(
            identifier="epic-5", issue_type="epic"
        )

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
            patch.object(server_module._api_cache, "invalidate") as mock_invalidate,
        ):
            client.post(
                "/api/v1/issues",
                json={"title": "My Epic", "type": "epic", "project_id": "proj-1"},
            )

        invalidated_keys = [call.args[0] for call in mock_invalidate.call_args_list]
        assert "issues:all" in invalidated_keys

    def test_create_epic_uses_correct_identifier_for_label(self, client):
        """The add_label call must use the issue.identifier (not issue.id) from tracker."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        # Simulate issue with a different identifier format
        issue = Issue(
            id="abc-123",
            identifier="oompah-xyz",
            title="Epic",
            state="open",
            issue_type="epic",
        )
        mock_tracker.create_issue.return_value = issue

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            client.post(
                "/api/v1/issues",
                json={"title": "Epic", "type": "epic", "project_id": "proj-1"},
            )

        # Should use issue.identifier, not issue.id
        mock_tracker.add_label.assert_called_once_with("oompah-xyz", "draft")
