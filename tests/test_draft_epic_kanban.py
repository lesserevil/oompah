"""Tests for draft epic kanban visibility.

Covers:
  (1) Server-side: api_issues() includes draft epics in column data
      (issue_type='epic', labels=['draft']).
  (2) Non-draft epics are still included in the response (they appear
      as swimlane headers on the frontend, but the API returns all issues).
  (3) The issue entry for a draft epic includes the labels field with 'draft'.
  (4) Label API endpoints (POST /api/v1/issues/{id}/labels and
      DELETE /api/v1/issues/{id}/labels/{label}).
  (5) tracker.add_label() and tracker.remove_label() calls.

See issue: oompah-bnm
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.server import app
from oompah.models import Issue
from oompah.tracker import BeadsTracker, TrackerError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_issue(
    *,
    id: str,
    identifier: str,
    title: str = "Test Issue",
    issue_type: str = "task",
    state: str = "open",
    labels: list[str] | None = None,
    priority: int = 2,
    parent_id: str | None = None,
    project_id: str | None = "proj-1",
) -> Issue:
    """Convenience factory for Issue objects."""
    return Issue(
        id=id,
        identifier=identifier,
        title=title,
        issue_type=issue_type,
        state=state,
        labels=labels or [],
        priority=priority,
        parent_id=parent_id,
        project_id=project_id,
    )


def _make_orch_with_issues(issues: list[Issue]) -> MagicMock:
    """Return a mock Orchestrator whose tracker returns the given issues."""
    mock_tracker = MagicMock()
    mock_tracker.fetch_all_issues.return_value = issues

    mock_orch = MagicMock()
    mock_orch.project_store.list_all.return_value = []
    mock_orch.tracker = mock_tracker
    return mock_orch


def _make_mock_orchestrator(project_id: str = "proj-1") -> tuple[MagicMock, MagicMock]:
    """Build a minimal mock Orchestrator with a stub tracker for label API tests."""
    mock_tracker = MagicMock()
    mock_tracker.add_label = MagicMock()
    mock_tracker.remove_label = MagicMock()

    mock_orch = MagicMock()
    mock_orch._tracker_for_project = MagicMock(return_value=mock_tracker)

    return mock_orch, mock_tracker


def _all_entries(data: dict) -> list[dict]:
    """Flatten the column-grouped response into a flat list of entries."""
    return [entry for col in data.values() for entry in col]


def _find_entry(data: dict, identifier: str) -> dict | None:
    """Find a single entry by identifier from the column-grouped response."""
    for entry in _all_entries(data):
        if entry.get("identifier") == identifier:
            return entry
    return None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_api_cache():
    """Clear the server-side API cache before each test."""
    server_module._api_cache.clear()
    yield
    server_module._api_cache.clear()


@pytest.fixture()
def client():
    """Return a TestClient backed by the FastAPI app."""
    return TestClient(app, raise_server_exceptions=False)


# ===========================================================================
# 1. api_issues() includes draft epics in column data
# ===========================================================================

class TestApiIssuesDraftEpicInColumns:
    """Verify that draft epics (issue_type='epic', labels=['draft']) appear
    in the api_issues response column data."""

    def test_draft_epic_appears_in_response(self, client):
        """A draft epic must be included in the API response."""
        issues = [
            _make_issue(id="e1", identifier="EPIC-1", issue_type="epic",
                        labels=["draft"], state="open"),
        ]
        mock_orch = _make_orch_with_issues(issues)

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = client.get("/api/v1/issues")

        assert resp.status_code == 200
        entry = _find_entry(resp.json(), "EPIC-1")
        assert entry is not None, "Draft epic must appear in API response"

    def test_draft_epic_in_correct_state_column(self, client):
        """A draft epic in 'open' state must appear in the 'open' column."""
        issues = [
            _make_issue(id="e1", identifier="EPIC-OPEN", issue_type="epic",
                        labels=["draft"], state="open"),
        ]
        mock_orch = _make_orch_with_issues(issues)

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = client.get("/api/v1/issues")

        data = resp.json()
        assert "open" in data
        identifiers = [e["identifier"] for e in data["open"]]
        assert "EPIC-OPEN" in identifiers

    def test_draft_epic_in_deferred_column(self, client):
        """A draft epic in 'deferred' state must appear in the 'deferred' column."""
        issues = [
            _make_issue(id="e1", identifier="EPIC-DEF", issue_type="epic",
                        labels=["draft"], state="deferred"),
        ]
        mock_orch = _make_orch_with_issues(issues)

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = client.get("/api/v1/issues")

        data = resp.json()
        assert "deferred" in data
        identifiers = [e["identifier"] for e in data["deferred"]]
        assert "EPIC-DEF" in identifiers

    def test_draft_epic_in_in_progress_column(self, client):
        """A draft epic in 'in_progress' state must appear in the 'in_progress' column."""
        issues = [
            _make_issue(id="e1", identifier="EPIC-IP", issue_type="epic",
                        labels=["draft"], state="in_progress"),
        ]
        mock_orch = _make_orch_with_issues(issues)

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = client.get("/api/v1/issues")

        data = resp.json()
        assert "in_progress" in data
        identifiers = [e["identifier"] for e in data["in_progress"]]
        assert "EPIC-IP" in identifiers

    def test_draft_epic_in_closed_column(self, client):
        """A draft epic in 'closed' state must appear in the 'closed' column."""
        issues = [
            _make_issue(id="e1", identifier="EPIC-CL", issue_type="epic",
                        labels=["draft"], state="closed"),
        ]
        mock_orch = _make_orch_with_issues(issues)

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = client.get("/api/v1/issues")

        data = resp.json()
        assert "closed" in data
        identifiers = [e["identifier"] for e in data["closed"]]
        assert "EPIC-CL" in identifiers

    def test_draft_epic_has_issue_type_epic(self, client):
        """The entry for a draft epic must have issue_type='epic'."""
        issues = [
            _make_issue(id="e1", identifier="EPIC-1", issue_type="epic",
                        labels=["draft"], state="open"),
        ]
        mock_orch = _make_orch_with_issues(issues)

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = client.get("/api/v1/issues")

        entry = _find_entry(resp.json(), "EPIC-1")
        assert entry["issue_type"] == "epic"

    def test_multiple_draft_epics_in_different_columns(self, client):
        """Multiple draft epics across different states should appear in their respective columns."""
        issues = [
            _make_issue(id="e1", identifier="EPIC-A", issue_type="epic",
                        labels=["draft"], state="open"),
            _make_issue(id="e2", identifier="EPIC-B", issue_type="epic",
                        labels=["draft"], state="in_progress"),
            _make_issue(id="e3", identifier="EPIC-C", issue_type="epic",
                        labels=["draft"], state="closed"),
        ]
        mock_orch = _make_orch_with_issues(issues)

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = client.get("/api/v1/issues")

        data = resp.json()
        assert _find_entry(data, "EPIC-A") is not None
        assert _find_entry(data, "EPIC-B") is not None
        assert _find_entry(data, "EPIC-C") is not None


# ===========================================================================
# 2. Non-draft epics are still included in the response
# ===========================================================================

class TestApiIssuesNonDraftEpicIncluded:
    """Non-draft epics appear as swimlane headers on the frontend.
    The API must still return them."""

    def test_non_draft_epic_appears_in_response(self, client):
        """A plain epic (no 'draft' label) must still be in the API response."""
        issues = [
            _make_issue(id="e1", identifier="EPIC-PLAIN", issue_type="epic",
                        labels=[], state="open"),
        ]
        mock_orch = _make_orch_with_issues(issues)

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = client.get("/api/v1/issues")

        assert resp.status_code == 200
        entry = _find_entry(resp.json(), "EPIC-PLAIN")
        assert entry is not None, "Non-draft epic must appear in API response"
        assert entry["issue_type"] == "epic"
        assert "draft" not in entry["labels"]

    def test_both_draft_and_non_draft_epics_in_same_column(self, client):
        """Both draft and non-draft epics in 'open' state appear together."""
        issues = [
            _make_issue(id="e1", identifier="EPIC-DRAFT", issue_type="epic",
                        labels=["draft"], state="open"),
            _make_issue(id="e2", identifier="EPIC-NODRAFT", issue_type="epic",
                        labels=[], state="open"),
        ]
        mock_orch = _make_orch_with_issues(issues)

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = client.get("/api/v1/issues")

        data = resp.json()
        identifiers = [e["identifier"] for e in data.get("open", [])]
        assert "EPIC-DRAFT" in identifiers
        assert "EPIC-NODRAFT" in identifiers

    def test_non_draft_epic_with_other_labels(self, client):
        """An epic with labels but not 'draft' is still a non-draft epic."""
        issues = [
            _make_issue(id="e1", identifier="EPIC-LABELED", issue_type="epic",
                        labels=["planning", "team:alpha"], state="open"),
        ]
        mock_orch = _make_orch_with_issues(issues)

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = client.get("/api/v1/issues")

        entry = _find_entry(resp.json(), "EPIC-LABELED")
        assert entry is not None
        assert entry["issue_type"] == "epic"
        assert "draft" not in entry["labels"]
        assert "planning" in entry["labels"]

    def test_non_draft_epic_has_children_counts(self, client):
        """Non-draft epics should have children_counts when they have child issues."""
        issues = [
            _make_issue(id="e1", identifier="EPIC-PARENT", issue_type="epic",
                        labels=[], state="open"),
            _make_issue(id="t1", identifier="TASK-1", issue_type="task",
                        state="open", parent_id="e1"),
            _make_issue(id="t2", identifier="TASK-2", issue_type="task",
                        state="closed", parent_id="e1"),
        ]
        mock_orch = _make_orch_with_issues(issues)

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = client.get("/api/v1/issues")

        entry = _find_entry(resp.json(), "EPIC-PARENT")
        assert entry is not None
        assert "children_counts" in entry
        assert entry["children_counts"]["open"] == 1
        assert entry["children_counts"]["closed"] == 1


# ===========================================================================
# 3. Draft epic entry includes labels field with 'draft'
# ===========================================================================

class TestDraftEpicLabelsField:
    """Verify the labels field is correctly serialized for draft epics."""

    def test_draft_epic_has_draft_in_labels(self, client):
        """The labels list for a draft epic must include 'draft'."""
        issues = [
            _make_issue(id="e1", identifier="EPIC-D", issue_type="epic",
                        labels=["draft"], state="open"),
        ]
        mock_orch = _make_orch_with_issues(issues)

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = client.get("/api/v1/issues")

        entry = _find_entry(resp.json(), "EPIC-D")
        assert entry is not None
        assert isinstance(entry["labels"], list)
        assert "draft" in entry["labels"]

    def test_draft_epic_with_multiple_labels_preserves_all(self, client):
        """A draft epic with multiple labels must preserve all of them."""
        issues = [
            _make_issue(id="e1", identifier="EPIC-ML", issue_type="epic",
                        labels=["draft", "urgent", "team:beta"], state="open"),
        ]
        mock_orch = _make_orch_with_issues(issues)

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = client.get("/api/v1/issues")

        entry = _find_entry(resp.json(), "EPIC-ML")
        assert entry is not None
        assert "draft" in entry["labels"]
        assert "urgent" in entry["labels"]
        assert "team:beta" in entry["labels"]

    def test_labels_is_list_even_when_empty(self, client):
        """An issue with no labels must still have labels as an empty list."""
        issues = [
            _make_issue(id="t1", identifier="TASK-NOLABEL", issue_type="task",
                        labels=[], state="open"),
        ]
        mock_orch = _make_orch_with_issues(issues)

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = client.get("/api/v1/issues")

        entry = _find_entry(resp.json(), "TASK-NOLABEL")
        assert entry is not None
        assert isinstance(entry["labels"], list)
        assert entry["labels"] == []

    def test_labels_field_present_for_every_issue(self, client):
        """Every issue in the response must include the 'labels' field."""
        issues = [
            _make_issue(id="e1", identifier="E-1", issue_type="epic", labels=["draft"]),
            _make_issue(id="e2", identifier="E-2", issue_type="epic", labels=[]),
            _make_issue(id="t1", identifier="T-1", issue_type="task", labels=[]),
            _make_issue(id="b1", identifier="B-1", issue_type="bug", labels=["critical"]),
        ]
        mock_orch = _make_orch_with_issues(issues)

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = client.get("/api/v1/issues")

        entries = _all_entries(resp.json())
        for entry in entries:
            assert "labels" in entry, f"Issue {entry['identifier']} missing 'labels' field"
            assert isinstance(entry["labels"], list), (
                f"labels for {entry['identifier']} must be a list"
            )

    def test_draft_label_not_on_non_draft_epic(self, client):
        """A non-draft epic must NOT have 'draft' in labels."""
        issues = [
            _make_issue(id="e1", identifier="EPIC-ND", issue_type="epic",
                        labels=[], state="open"),
        ]
        mock_orch = _make_orch_with_issues(issues)

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = client.get("/api/v1/issues")

        entry = _find_entry(resp.json(), "EPIC-ND")
        assert entry is not None
        assert "draft" not in entry["labels"]

    def test_task_with_draft_label_is_not_draft_epic(self, client):
        """A task with 'draft' label has issue_type='task', not 'epic'."""
        issues = [
            _make_issue(id="t1", identifier="TASK-D", issue_type="task",
                        labels=["draft"], state="open"),
        ]
        mock_orch = _make_orch_with_issues(issues)

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = client.get("/api/v1/issues")

        entry = _find_entry(resp.json(), "TASK-D")
        assert entry is not None
        assert entry["issue_type"] == "task"
        assert "draft" in entry["labels"]


# ===========================================================================
# 4. Label API endpoints
# ===========================================================================

class TestLabelApiAddEndpoint:
    """Tests for POST /api/v1/issues/{id}/labels."""

    def test_add_label_returns_201(self, client):
        """POST with valid label returns 201."""
        mock_orch, mock_tracker = _make_mock_orchestrator()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues/issue-1/labels",
                json={"label": "draft", "project_id": "proj-1"},
            )

        assert resp.status_code == 201
        assert resp.json() == {"ok": True}

    def test_add_label_calls_tracker(self, client):
        """POST calls tracker.add_label with correct args."""
        mock_orch, mock_tracker = _make_mock_orchestrator()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            client.post(
                "/api/v1/issues/issue-abc/labels",
                json={"label": "draft", "project_id": "proj-1"},
            )

        mock_tracker.add_label.assert_called_once_with("issue-abc", "draft")

    def test_add_label_broadcasts_issues(self, client):
        """POST must call broadcast_issues for live updates."""
        mock_orch, _ = _make_mock_orchestrator()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock) as mock_bc,
        ):
            client.post(
                "/api/v1/issues/issue-1/labels",
                json={"label": "draft", "project_id": "proj-1"},
            )

        mock_bc.assert_awaited_once()

    def test_add_label_invalidates_cache(self, client):
        """POST must invalidate the issues:all cache key."""
        mock_orch, _ = _make_mock_orchestrator()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
            patch.object(server_module._api_cache, "invalidate") as mock_inv,
        ):
            client.post(
                "/api/v1/issues/issue-1/labels",
                json={"label": "draft", "project_id": "proj-1"},
            )

        inv_keys = [c.args[0] for c in mock_inv.call_args_list]
        assert "issues:all" in inv_keys

    def test_add_label_invalidates_detail_cache(self, client):
        """POST must invalidate detail cache for the specific issue."""
        mock_orch, _ = _make_mock_orchestrator()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
            patch.object(server_module._api_cache, "invalidate_prefix") as mock_inv_pre,
        ):
            client.post(
                "/api/v1/issues/issue-xyz/labels",
                json={"label": "draft", "project_id": "proj-1"},
            )

        prefixes = [c.args[0] for c in mock_inv_pre.call_args_list]
        assert any("issue-xyz" in p for p in prefixes)

    def test_add_label_missing_label_returns_400(self, client):
        """POST without label key returns 400."""
        mock_orch, _ = _make_mock_orchestrator()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues/issue-1/labels",
                json={"project_id": "proj-1"},
            )

        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "validation"

    def test_add_label_empty_label_returns_400(self, client):
        """POST with empty/whitespace label returns 400."""
        mock_orch, _ = _make_mock_orchestrator()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues/issue-1/labels",
                json={"label": "   ", "project_id": "proj-1"},
            )

        assert resp.status_code == 400

    def test_add_label_tracker_error_returns_500(self, client):
        """If tracker.add_label raises, endpoint returns 500."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_tracker.add_label.side_effect = Exception("boom")

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues/issue-1/labels",
                json={"label": "draft", "project_id": "proj-1"},
            )

        assert resp.status_code == 500
        assert resp.json()["error"]["code"] == "label_failed"


class TestLabelApiRemoveEndpoint:
    """Tests for DELETE /api/v1/issues/{id}/labels/{label}."""

    def test_remove_label_returns_200(self, client):
        """DELETE returns 200 ok:True."""
        mock_orch, mock_tracker = _make_mock_orchestrator()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.delete(
                "/api/v1/issues/issue-1/labels/draft",
                params={"project_id": "proj-1"},
            )

        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

    def test_remove_label_calls_tracker(self, client):
        """DELETE calls tracker.remove_label with correct args."""
        mock_orch, mock_tracker = _make_mock_orchestrator()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            client.delete(
                "/api/v1/issues/issue-abc/labels/urgent",
                params={"project_id": "proj-1"},
            )

        mock_tracker.remove_label.assert_called_once_with("issue-abc", "urgent")

    def test_remove_label_broadcasts_issues(self, client):
        """DELETE must call broadcast_issues."""
        mock_orch, _ = _make_mock_orchestrator()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock) as mock_bc,
        ):
            client.delete(
                "/api/v1/issues/issue-1/labels/draft",
                params={"project_id": "proj-1"},
            )

        mock_bc.assert_awaited_once()

    def test_remove_label_invalidates_cache(self, client):
        """DELETE must invalidate issues:all cache."""
        mock_orch, _ = _make_mock_orchestrator()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
            patch.object(server_module._api_cache, "invalidate") as mock_inv,
        ):
            client.delete(
                "/api/v1/issues/issue-1/labels/draft",
                params={"project_id": "proj-1"},
            )

        inv_keys = [c.args[0] for c in mock_inv.call_args_list]
        assert "issues:all" in inv_keys

    def test_remove_label_invalidates_detail_cache(self, client):
        """DELETE must invalidate the detail cache for the issue."""
        mock_orch, _ = _make_mock_orchestrator()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
            patch.object(server_module._api_cache, "invalidate_prefix") as mock_inv_pre,
        ):
            client.delete(
                "/api/v1/issues/issue-xyz/labels/draft",
                params={"project_id": "proj-1"},
            )

        prefixes = [c.args[0] for c in mock_inv_pre.call_args_list]
        assert any("issue-xyz" in p for p in prefixes)

    def test_remove_label_tracker_error_returns_500(self, client):
        """If tracker.remove_label raises, endpoint returns 500."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_tracker.remove_label.side_effect = Exception("boom")

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.delete(
                "/api/v1/issues/issue-1/labels/draft",
                params={"project_id": "proj-1"},
            )

        assert resp.status_code == 500
        assert resp.json()["error"]["code"] == "label_failed"

    def test_remove_label_url_encoded_label(self, client):
        """DELETE handles hyphenated label names in the URL path."""
        mock_orch, mock_tracker = _make_mock_orchestrator()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.delete(
                "/api/v1/issues/issue-1/labels/needs-review",
                params={"project_id": "proj-1"},
            )

        assert resp.status_code == 200
        mock_tracker.remove_label.assert_called_once_with("issue-1", "needs-review")


# ===========================================================================
# 5. tracker.add_label() and tracker.remove_label() calls
# ===========================================================================

class TestTrackerAddLabel:
    """Tests for BeadsTracker.add_label()."""

    def _tracker(self):
        return BeadsTracker(active_states=["open"], terminal_states=["closed"])

    @patch.object(BeadsTracker, "_run_bd")
    def test_add_label_calls_bd_label_add(self, mock_run_bd):
        """add_label must call _run_bd with ['label', 'add', identifier, label]."""
        mock_run_bd.return_value = []
        tracker = self._tracker()
        tracker.add_label("issue-1", "draft")
        mock_run_bd.assert_called_once_with(["label", "add", "issue-1", "draft"])

    @patch.object(BeadsTracker, "_run_bd")
    def test_add_label_with_various_labels(self, mock_run_bd):
        """add_label works with different label values."""
        mock_run_bd.return_value = []
        tracker = self._tracker()

        tracker.add_label("issue-1", "draft")
        tracker.add_label("issue-2", "urgent")
        tracker.add_label("issue-3", "team:alpha")

        assert mock_run_bd.call_args_list == [
            call(["label", "add", "issue-1", "draft"]),
            call(["label", "add", "issue-2", "urgent"]),
            call(["label", "add", "issue-3", "team:alpha"]),
        ]

    @patch.object(BeadsTracker, "_run_bd")
    def test_add_label_propagates_tracker_error(self, mock_run_bd):
        """If _run_bd raises TrackerError, add_label propagates it."""
        mock_run_bd.side_effect = TrackerError("bd command failed")
        tracker = self._tracker()

        with pytest.raises(TrackerError, match="bd command failed"):
            tracker.add_label("issue-1", "draft")


class TestTrackerRemoveLabel:
    """Tests for BeadsTracker.remove_label()."""

    def _tracker(self):
        return BeadsTracker(active_states=["open"], terminal_states=["closed"])

    @patch.object(BeadsTracker, "_run_bd")
    def test_remove_label_calls_bd_label_remove(self, mock_run_bd):
        """remove_label must call _run_bd with ['label', 'remove', identifier, label]."""
        mock_run_bd.return_value = []
        tracker = self._tracker()
        tracker.remove_label("issue-1", "draft")
        mock_run_bd.assert_called_once_with(["label", "remove", "issue-1", "draft"])

    @patch.object(BeadsTracker, "_run_bd")
    def test_remove_label_with_various_labels(self, mock_run_bd):
        """remove_label works with different label values."""
        mock_run_bd.return_value = []
        tracker = self._tracker()

        tracker.remove_label("issue-1", "draft")
        tracker.remove_label("issue-2", "urgent")

        assert mock_run_bd.call_args_list == [
            call(["label", "remove", "issue-1", "draft"]),
            call(["label", "remove", "issue-2", "urgent"]),
        ]

    @patch.object(BeadsTracker, "_run_bd")
    def test_remove_label_swallows_tracker_error(self, mock_run_bd):
        """If _run_bd raises TrackerError, remove_label swallows it (label may not exist)."""
        mock_run_bd.side_effect = TrackerError("label not found")
        tracker = self._tracker()

        # Should NOT raise
        tracker.remove_label("issue-1", "nonexistent-label")

    @patch.object(BeadsTracker, "_run_bd")
    def test_remove_label_does_not_swallow_other_exceptions(self, mock_run_bd):
        """remove_label only swallows TrackerError, not other exceptions."""
        mock_run_bd.side_effect = RuntimeError("unexpected")
        tracker = self._tracker()

        with pytest.raises(RuntimeError, match="unexpected"):
            tracker.remove_label("issue-1", "draft")


# ===========================================================================
# 6. Edge cases
# ===========================================================================

class TestDraftEpicEdgeCases:
    """Edge cases for draft epic kanban visibility."""

    def test_archived_draft_epic_excluded(self, client):
        """An archived draft epic (archive:yes label) must be excluded."""
        issues = [
            _make_issue(id="e1", identifier="EPIC-ARCH", issue_type="epic",
                        labels=["draft", "archive:yes"], state="closed"),
        ]
        mock_orch = _make_orch_with_issues(issues)

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = client.get("/api/v1/issues")

        assert resp.status_code == 200
        entry = _find_entry(resp.json(), "EPIC-ARCH")
        assert entry is None, "Archived draft epic must be excluded"

    def test_empty_issues_returns_empty_response(self, client):
        """No issues → empty dict response."""
        mock_orch = _make_orch_with_issues([])

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = client.get("/api/v1/issues")

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)
        assert _all_entries(data) == []

    def test_mixed_issue_types_all_present(self, client):
        """All issue types (epic, task, bug, feature) appear in response."""
        issues = [
            _make_issue(id="e1", identifier="E-1", issue_type="epic", labels=["draft"]),
            _make_issue(id="e2", identifier="E-2", issue_type="epic", labels=[]),
            _make_issue(id="t1", identifier="T-1", issue_type="task"),
            _make_issue(id="b1", identifier="B-1", issue_type="bug"),
            _make_issue(id="f1", identifier="F-1", issue_type="feature"),
        ]
        mock_orch = _make_orch_with_issues(issues)

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = client.get("/api/v1/issues")

        entries = _all_entries(resp.json())
        identifiers = {e["identifier"] for e in entries}
        assert identifiers == {"E-1", "E-2", "T-1", "B-1", "F-1"}

    def test_draft_epic_sorted_by_priority(self, client):
        """Draft epics respect priority sorting within their column."""
        issues = [
            _make_issue(id="e1", identifier="EPIC-LOW", issue_type="epic",
                        labels=["draft"], state="open", priority=3),
            _make_issue(id="e2", identifier="EPIC-HIGH", issue_type="epic",
                        labels=["draft"], state="open", priority=0),
            _make_issue(id="t1", identifier="TASK-MED", issue_type="task",
                        state="open", priority=2),
        ]
        mock_orch = _make_orch_with_issues(issues)

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = client.get("/api/v1/issues")

        open_col = resp.json().get("open", [])
        ids = [e["identifier"] for e in open_col]
        # Priority 0 (high) should come before priority 2, then 3
        assert ids.index("EPIC-HIGH") < ids.index("TASK-MED") < ids.index("EPIC-LOW")

    def test_draft_epic_has_children_counts(self, client):
        """A draft epic can have child issues and children_counts."""
        issues = [
            _make_issue(id="e1", identifier="EPIC-DRAFT-PARENT", issue_type="epic",
                        labels=["draft"], state="open"),
            _make_issue(id="t1", identifier="CHILD-1", issue_type="task",
                        state="in_progress", parent_id="e1"),
        ]
        mock_orch = _make_orch_with_issues(issues)

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = client.get("/api/v1/issues")

        entry = _find_entry(resp.json(), "EPIC-DRAFT-PARENT")
        assert entry is not None
        assert "children_counts" in entry
        assert entry["children_counts"]["in_progress"] == 1

    def test_issue_entry_has_all_required_fields(self, client):
        """Every issue entry has id, identifier, title, state, labels, issue_type, parent_id, project_id."""
        issues = [
            _make_issue(id="e1", identifier="EPIC-1", issue_type="epic",
                        labels=["draft"], state="open", parent_id=None, project_id="proj-1"),
        ]
        mock_orch = _make_orch_with_issues(issues)

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = client.get("/api/v1/issues")

        entry = _find_entry(resp.json(), "EPIC-1")
        assert entry is not None
        required = {"id", "identifier", "title", "state", "labels", "issue_type",
                     "parent_id", "project_id", "description", "priority"}
        missing = required - set(entry.keys())
        assert not missing, f"Missing fields: {missing}"
