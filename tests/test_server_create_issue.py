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
    """Tests that creating an epic does NOT auto-add the 'draft' label (OOMPAH-171)."""

    def test_create_epic_does_not_add_draft_label(self, client):
        """POST type=epic must NOT call tracker.add_label with 'draft' (OOMPAH-171)."""
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
                json={"title": "My Epic", "type": "epic", "project_id": "proj-1", "description": "Test epic"},
            )

        assert resp.status_code == 201
        assert resp.json()["ok"] is True
        # Automatic draft labeling was removed in OOMPAH-171
        mock_tracker.add_label.assert_not_called()

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
                json={"title": "My Task", "type": "task", "project_id": "proj-1", "description": "Test task"},
            )

        assert resp.status_code == 201
        mock_tracker.add_label.assert_not_called()

    def test_create_child_passes_parent_at_creation(self, client):
        """POST parent_id should pass parent into create_issue, not link afterward."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_tracker.create_issue.return_value = _make_mock_issue(
            identifier="task-child", issue_type="task"
        )

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues",
                json={
                    "title": "Child task",
                    "type": "task",
                    "project_id": "proj-1",
                    "parent_id": "TASK-1",
                    "description": "Child task description",
                },
            )

        assert resp.status_code == 201
        assert mock_tracker.create_issue.call_args.kwargs["parent"] == "TASK-1"
        mock_tracker.add_parent_child.assert_not_called()

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
                json={"title": "My Bug", "type": "bug", "project_id": "proj-1", "description": "Test bug"},
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
                json={"title": "My Feature", "type": "feature", "project_id": "proj-1", "description": "Test feature"},
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
                json={"title": "Default type task", "project_id": "proj-1", "description": "Default type description"},
            )

        assert resp.status_code == 201
        mock_tracker.add_label.assert_not_called()

    def test_create_epic_calls_broadcast_without_draft_label(self, client):
        """Creating an epic calls broadcast_issues without adding any draft label (OOMPAH-171)."""
        call_order = []

        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_tracker.create_issue.return_value = _make_mock_issue(
            identifier="epic-2", issue_type="epic"
        )

        async def mock_broadcast():
            call_order.append("broadcast")

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", side_effect=mock_broadcast),
        ):
            resp = client.post(
                "/api/v1/issues",
                json={"title": "My Epic", "type": "epic", "project_id": "proj-1", "description": "Epic description"},
            )

        assert resp.status_code == 201
        assert "broadcast" in call_order
        # No draft label should have been added (OOMPAH-171)
        mock_tracker.add_label.assert_not_called()

    def test_create_epic_returns_201_on_success(self, client):
        """Creating an epic returns 201 with ok=True; no draft label side-effects (OOMPAH-171)."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_tracker.create_issue.return_value = _make_mock_issue(
            identifier="epic-3", issue_type="epic"
        )

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues",
                json={"title": "My Epic", "type": "epic", "project_id": "proj-1", "description": "Epic description"},
            )

        # Epic creation succeeds without any add_label call (OOMPAH-171)
        assert resp.status_code == 201
        assert resp.json()["ok"] is True
        mock_tracker.add_label.assert_not_called()

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
                json={"title": "My Epic", "type": "epic", "project_id": "proj-1", "description": "Epic description"},
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
                json={"title": "My Epic", "type": "epic", "project_id": "proj-1", "description": "Epic description"},
            )

        invalidated_keys = [call.args[0] for call in mock_invalidate.call_args_list]
        assert "issues:all" in invalidated_keys

    def test_create_epic_with_custom_identifier_does_not_add_label(self, client):
        """Epic creation with any identifier must NOT call add_label (OOMPAH-171)."""
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
            resp = client.post(
                "/api/v1/issues",
                json={"title": "Epic", "type": "epic", "project_id": "proj-1", "description": "Epic description"},
            )

        assert resp.status_code == 201
        # Automatic draft labeling was removed in OOMPAH-171
        mock_tracker.add_label.assert_not_called()


# ---------------------------------------------------------------------------
# POST /api/v1/issues — priority normalization
# ---------------------------------------------------------------------------

class TestCreateIssuePriority:
    """Tests that tracker-neutral priority names are normalized before persistence."""

    @pytest.mark.parametrize(
        ("priority_name", "expected_priority"),
        [("high", 1), ("medium", 2), ("low", 3)],
    )
    def test_named_priority_passed_to_tracker_as_int(
        self, client, priority_name, expected_priority
    ):
        """POST priority=high/medium/low should not reach trackers as raw strings."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_tracker.create_issue.return_value = _make_mock_issue("T-101")

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues",
                json={
                    "title": "Prioritized task",
                    "project_id": "proj-1",
                    "priority": priority_name,
                    "description": "Prioritized task description",
                },
            )

        assert resp.status_code == 201
        assert mock_tracker.create_issue.call_args.kwargs["priority"] == expected_priority


# ---------------------------------------------------------------------------
# POST /api/v1/issues — source_task_id metadata (TASK-460.3 AC#2)
# ---------------------------------------------------------------------------

class TestCreateIssueSourceTaskId:
    """Tests that source_task_id is prepended to description across tracker backends."""

    def test_source_task_id_prepended_to_description(self, client):
        """When source_task_id is given, 'Triggered by: X' is prepended to description."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_tracker.create_issue.return_value = _make_mock_issue("T-99")

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues",
                json={
                    "title": "Follow-up",
                    "project_id": "proj-1",
                    "source_task_id": "TASK-42",
                    "description": "More context here.",
                },
            )

        assert resp.status_code == 201
        call_kwargs = mock_tracker.create_issue.call_args.kwargs
        description = call_kwargs.get("description", "")
        assert description.startswith("Triggered by: TASK-42")
        assert "More context here." in description

    def test_source_task_id_used_as_description_when_no_description_given(self, client):
        """When source_task_id is given but no description, description is just the header."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_tracker.create_issue.return_value = _make_mock_issue("T-100")

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues",
                json={
                    "title": "Follow-up no desc",
                    "project_id": "proj-1",
                    "source_task_id": "TASK-55",
                },
            )

        assert resp.status_code == 201
        call_kwargs = mock_tracker.create_issue.call_args.kwargs
        description = call_kwargs.get("description", "")
        assert description == "Triggered by: TASK-55"

    def test_no_source_task_id_does_not_alter_description(self, client):
        """Without source_task_id, description is passed through unchanged."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_tracker.create_issue.return_value = _make_mock_issue("T-101")

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues",
                json={
                    "title": "Plain task",
                    "project_id": "proj-1",
                    "description": "Original description.",
                },
            )

        assert resp.status_code == 201
        call_kwargs = mock_tracker.create_issue.call_args.kwargs
        description = call_kwargs.get("description", "")
        assert description == "Original description."
        assert "Triggered by" not in description

    def test_empty_source_task_id_does_not_alter_description(self, client):
        """An empty string source_task_id is treated as absent."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_tracker.create_issue.return_value = _make_mock_issue("T-102")

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues",
                json={
                    "title": "Empty source",
                    "project_id": "proj-1",
                    "source_task_id": "",
                    "description": "My description.",
                },
            )

        assert resp.status_code == 201
        call_kwargs = mock_tracker.create_issue.call_args.kwargs
        description = call_kwargs.get("description", "")
        assert "Triggered by" not in description
        assert description == "My description."

    def test_source_task_id_works_with_github_style_identifier(self, client):
        """GitHub-style identifiers (owner/repo#123) are preserved as-is in description."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_tracker.create_issue.return_value = _make_mock_issue("T-103")

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues",
                json={
                    "title": "GH follow-up",
                    "project_id": "proj-1",
                    "source_task_id": "example-org/oompah-tasks#99",
                    "description": "Detail.",
                },
            )

        assert resp.status_code == 201
        call_kwargs = mock_tracker.create_issue.call_args.kwargs
        description = call_kwargs.get("description", "")
        assert "Triggered by: example-org/oompah-tasks#99" in description
