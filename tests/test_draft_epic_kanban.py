"""Regression tests: draft-epic kanban server-side behavior (OOMPAH-171).

After OOMPAH-171:
- Creating an epic must NOT auto-add the 'draft' label
- The API must still return labels and issue_type for all issues
- Label API endpoints must still work for generic use
- Issues carrying a 'draft' label from before migration remain valid via API

See issue: OOMPAH-171
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

def _make_mock_orchestrator():
    mock_tracker = MagicMock()
    mock_tracker.fetch_all_issues.return_value = []
    mock_tracker.get_issue.return_value = None
    mock_tracker.create_issue.return_value = None
    mock_orch = MagicMock()
    mock_orch.tracker = mock_tracker
    # Ensure project_store reports no projects so code uses legacy orch.tracker path
    mock_orch.project_store.list_all.return_value = []
    # Ensure _tracker_for_project returns our mock_tracker for explicit project_id lookups
    mock_orch._tracker_for_project.return_value = mock_tracker
    return mock_orch, mock_tracker


def _make_issue(**kwargs) -> Issue:
    defaults = dict(
        id="issue-1",
        identifier="OOMPAH-1",
        title="Test issue",
        state="open",
        issue_type="task",
        labels=[],
    )
    defaults.update(kwargs)
    return Issue(**defaults)


def _all_issues_from_board(board: dict) -> list:
    """Flatten the issue board (state → issues) into a single list."""
    result = []
    for val in board.values():
        if isinstance(val, list):
            result.extend(val)
    return result


def _populate_snapshot(mock_orch) -> None:
    """Pre-populate the issues snapshot from mock_orch so GET /api/v1/issues works.

    The issues endpoint returns from the cached snapshot; tests that use it
    must pre-populate the snapshot synchronously before making the request.
    """
    board = server_module._fetch_and_serialize_issues(mock_orch)
    server_module._set_issues_snapshot(board, duration_ms=0, orch_id=id(mock_orch))


@pytest.fixture(autouse=True)
def clear_issues_snapshot():
    """Clear the issues snapshot before and after each test."""
    server_module._issues_snapshot.clear()
    if server_module._issues_refresh_task is not None:
        server_module._issues_refresh_task = None
    server_module._api_cache.clear()
    yield
    server_module._issues_snapshot.clear()
    if server_module._issues_refresh_task is not None:
        server_module._issues_refresh_task = None
    server_module._api_cache.clear()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# No auto-draft on epic create
# ---------------------------------------------------------------------------

class TestNoAutoDraftOnCreate:
    """Epic creation must NOT automatically add the draft label (OOMPAH-171)."""

    def test_create_epic_no_draft_label(self, client):
        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_tracker.create_issue.return_value = _make_issue(
            identifier="OOMPAH-E1", issue_type="epic"
        )

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues",
                json={"title": "New Epic", "type": "epic", "project_id": "proj-1"},
            )

        assert resp.status_code == 201
        mock_tracker.add_label.assert_not_called()

    def test_create_task_no_draft_label(self, client):
        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_tracker.create_issue.return_value = _make_issue(
            identifier="OOMPAH-T1", issue_type="task"
        )

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues",
                json={"title": "New Task", "type": "task", "project_id": "proj-1"},
            )

        assert resp.status_code == 201
        mock_tracker.add_label.assert_not_called()


# ---------------------------------------------------------------------------
# Legacy draft epics remain valid via API
# ---------------------------------------------------------------------------

class TestLegacyDraftEpicCompatibility:
    """Issues that already have 'draft' label must still appear in API responses."""

    def test_legacy_draft_epic_appears_in_issues_api(self, client):
        mock_orch, mock_tracker = _make_mock_orchestrator()
        legacy_epic = _make_issue(
            identifier="OOMPAH-OLD",
            issue_type="epic",
            labels=["draft"],  # pre-migration label
        )
        mock_tracker.fetch_all_issues.return_value = [legacy_epic]
        _populate_snapshot(mock_orch)

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = client.get("/api/v1/issues")

        assert resp.status_code == 200
        # API returns board format: {"Open": [...], "In Progress": [...], ...}
        all_issues = _all_issues_from_board(resp.json())
        entry = next((i for i in all_issues if i.get("identifier") == "OOMPAH-OLD"), None)
        assert entry is not None, "Legacy draft epic must appear in API response"
        assert entry.get("issue_type") == "epic"

    def test_legacy_draft_epic_labels_field_preserved(self, client):
        mock_orch, mock_tracker = _make_mock_orchestrator()
        legacy_epic = _make_issue(
            identifier="OOMPAH-OLD2",
            issue_type="epic",
            labels=["draft"],
        )
        mock_tracker.fetch_all_issues.return_value = [legacy_epic]
        _populate_snapshot(mock_orch)

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = client.get("/api/v1/issues")

        # API returns board format: {"Open": [...], "In Progress": [...], ...}
        all_issues = _all_issues_from_board(resp.json())
        entry = next((i for i in all_issues if i.get("identifier") == "OOMPAH-OLD2"), None)
        assert entry is not None
        assert "labels" in entry


# ---------------------------------------------------------------------------
# Label API endpoints — generic use
# ---------------------------------------------------------------------------

class TestLabelAPIEndpoints:
    """Label endpoints must still work for generic labels (not draft-specific)."""

    def test_add_label_post_returns_success(self, client):
        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_tracker.add_label.return_value = None

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues/OOMPAH-1/labels",
                json={"label": "priority:high", "project_id": "proj-1"},
            )

        assert resp.status_code in (200, 201)

    def test_remove_label_delete_returns_success(self, client):
        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_tracker.remove_label.return_value = None

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.delete(
                "/api/v1/issues/OOMPAH-1/labels/priority:high",
                params={"project_id": "proj-1"},
            )

        assert resp.status_code == 200

    def test_issues_api_returns_issue_type_field(self, client):
        """issue_type field must be in API response so frontend can distinguish epics."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        epic = _make_issue(identifier="OOMPAH-E2", issue_type="epic")
        mock_tracker.fetch_all_issues.return_value = [epic]
        _populate_snapshot(mock_orch)

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = client.get("/api/v1/issues")

        assert resp.status_code == 200
        # API returns board format: {"Open": [...], "In Progress": [...], ...}
        all_issues = _all_issues_from_board(resp.json())
        entry = next((i for i in all_issues if i.get("identifier") == "OOMPAH-E2"), None)
        assert entry is not None
        assert "issue_type" in entry
        assert entry["issue_type"] == "epic"
