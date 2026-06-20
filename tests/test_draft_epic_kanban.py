"""Tests for draft epic kanban visibility.

Covers:
  (1) Server-side: api_issues() includes draft epics in column data
      (issue_type='epic', labels=['draft']).
  (2) Non-draft epics are still included in the response (they appear
      as swimlane headers on the frontend, but the API returns all issues).
  (3) The issue entry for a draft epic includes the labels field with 'draft'.
  (4) Label API endpoints (POST /api/v1/issues/{id}/labels and
      DELETE /api/v1/issues/{id}/labels/{label}).
  (5) Edge cases for draft epic visibility.

See issue: oompah-bnm
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.server import app
from oompah.models import Issue


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
    board = server_module._fetch_and_serialize_issues(mock_orch)
    server_module._set_issues_snapshot(board, duration_ms=0, orch_id=id(mock_orch))
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
    _clear_issue_snapshot()
    server_module._api_cache.clear()
    yield
    _clear_issue_snapshot()
    server_module._api_cache.clear()


def _clear_issue_snapshot() -> None:
    task = getattr(server_module, "_issues_refresh_task", None)
    if task is not None and not task.done():
        task.cancel()
    server_module._issues_refresh_task = None
    with server_module._issues_snapshot_lock:
        server_module._issues_snapshot["data"] = None
        server_module._issues_snapshot["orch_id"] = None
        server_module._issues_snapshot["created_at_monotonic"] = 0.0
        server_module._issues_snapshot["created_at_wall"] = None
        server_module._issues_snapshot["duration_ms"] = None
        server_module._issues_snapshot["issue_count"] = 0
        server_module._issues_snapshot["error"] = None


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
        assert "Open" in data
        identifiers = [e["identifier"] for e in data["Open"]]
        assert "EPIC-OPEN" in identifiers

    def test_draft_epic_in_legacy_deferred_column(self, client):
        """A legacy 'deferred' draft epic appears in the 'backlog' column."""
        issues = [
            _make_issue(id="e1", identifier="EPIC-DEF", issue_type="epic",
                        labels=["draft"], state="deferred"),
        ]
        mock_orch = _make_orch_with_issues(issues)

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = client.get("/api/v1/issues")

        data = resp.json()
        assert "Backlog" in data
        identifiers = [e["identifier"] for e in data["Backlog"]]
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
        assert "In Progress" in data
        identifiers = [e["identifier"] for e in data["In Progress"]]
        assert "EPIC-IP" in identifiers

    def test_draft_epic_in_legacy_closed_column(self, client):
        """A legacy 'closed' draft epic appears in the 'done' column."""
        issues = [
            _make_issue(id="e1", identifier="EPIC-CL", issue_type="epic",
                        labels=["draft"], state="closed"),
        ]
        mock_orch = _make_orch_with_issues(issues)

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = client.get("/api/v1/issues")

        data = resp.json()
        assert "Done" in data
        identifiers = [e["identifier"] for e in data["Done"]]
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
        identifiers = [e["identifier"] for e in data.get("Open", [])]
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
        assert entry["children_counts"]["Open"] == 1
        assert entry["children_counts"]["Done"] == 1


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
# 4. Edge cases
# ===========================================================================

class TestDraftEpicEdgeCases:
    """Edge cases for draft epic kanban visibility."""

    def test_archived_draft_epic_in_archived_column(self, client):
        """An archived draft epic (archive:yes label) appears in archived."""
        issues = [
            _make_issue(id="e1", identifier="EPIC-ARCH", issue_type="epic",
                        labels=["draft", "archive:yes"], state="closed"),
        ]
        mock_orch = _make_orch_with_issues(issues)

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = client.get("/api/v1/issues")

        assert resp.status_code == 200
        data = resp.json()
        entry = _find_entry(data, "EPIC-ARCH")
        assert entry is not None
        assert entry in data["Archived"]

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

        open_col = resp.json().get("Open", [])
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
        assert entry["children_counts"]["In Progress"] == 1

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
