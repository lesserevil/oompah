"""Tests for server-side hide_merged (in-flight tree-traversal) filter.

Ported from dashboard.html _computeInFlightShowSet / _isIndividuallyInFlight /
applyHideMergedFilter JS logic.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.server import app
from oompah.models import Issue


# ---------------------------------------------------------------------------
# Helper factories
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
    branch_name: str | None = None,
    has_open_review: bool = False,
) -> Issue:
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
        branch_name=branch_name,
        # Note: Issue model may not have has_open_review directly; the API
        # computes it from unmerged_branches. For testing, we patch the
        # orchestrator's _unmerged_review_branches to control the signal.
    )


def _make_orch_with_issues(
    issues: list[Issue],
    unmerged_branches: set[str] | None = None,
) -> MagicMock:
    mock_tracker = MagicMock()
    mock_tracker.fetch_all_issues.return_value = issues

    mock_orch = MagicMock()
    mock_orch.project_store.list_all.return_value = []
    mock_orch.tracker = mock_tracker
    mock_orch._unmerged_review_branches = unmerged_branches or set()
    return mock_orch


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_api_cache():
    server_module._api_cache.clear()
    yield
    server_module._api_cache.clear()


@pytest.fixture()
def api_client():
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Unit tests for the helper functions (can run without the full API)
# ---------------------------------------------------------------------------

class TestIsIndividuallyInflight:
    """Unit tests for _is_individually_inflight()."""

    def _call(self, entry: dict) -> bool:
        return server_module._is_individually_inflight(entry)

    def test_open_returns_true(self):
        assert self._call({"id": "t1", "state": "open", "has_open_review": False}) is True

    def test_in_progress_returns_true(self):
        assert self._call({"id": "t1", "state": "in_progress", "has_open_review": False}) is True

    def test_closed_with_open_review_returns_true(self):
        assert self._call({"id": "t1", "state": "closed", "has_open_review": True}) is True

    def test_closed_without_open_review_returns_false(self):
        assert self._call({"id": "t1", "state": "closed", "has_open_review": False}) is False

    def test_deferred_returns_false(self):
        assert self._call({"id": "t1", "state": "deferred", "has_open_review": False}) is False

    def test_state_is_case_insensitive(self):
        assert self._call({"id": "t1", "state": "OPEN", "has_open_review": False}) is True
        assert self._call({"id": "t1", "state": "IN_PROGRESS", "has_open_review": False}) is True

    def test_state_whitespace_trimmed(self):
        assert self._call({"id": "t1", "state": "  open  ", "has_open_review": False}) is True

    def test_missing_state_returns_false(self):
        assert self._call({"id": "t1"}) is False

    def test_none_entry_returns_false(self):
        assert self._call(None) is False


class TestComputeInflightShowSet:
    """Unit tests for _compute_inflight_show_set()."""

    def _call(self, entries: list[dict]) -> set[str]:
        return server_module._compute_inflight_show_set(entries)

    def test_leaf_inflight_shows_parent_in_show_set(self):
        """Leaf task that is in-flight causes its parent epic to be in the show-set."""
        entries = [
            {"id": "e1", "identifier": "E-1", "state": "open", "has_open_review": False, "parent_id": None},
            {"id": "t1", "identifier": "T-1", "state": "in_progress", "has_open_review": False, "parent_id": "e1"},
        ]
        show = self._call(entries)
        # t1 is individually in-flight, e1 is in show-set because its subtree has in-flight
        assert "t1" in show
        assert "e1" in show

    def test_parent_inflight_shows_all_children(self):
        """Epic in-flight shows all its descendants (even if descendants are closed)."""
        entries = [
            {"id": "e1", "identifier": "E-1", "state": "in_progress", "has_open_review": False, "parent_id": None},
            {"id": "t1", "identifier": "T-1", "state": "closed", "has_open_review": False, "parent_id": "e1"},
        ]
        show = self._call(entries)
        assert "e1" in show
        assert "t1" in show

    def test_all_closed_no_inflight_shows_nothing(self):
        """When everything is closed and no ancestor has in-flight subtree, nothing shows."""
        entries = [
            {"id": "e1", "identifier": "E-1", "state": "closed", "has_open_review": False, "parent_id": None},
            {"id": "t1", "identifier": "T-1", "state": "closed", "has_open_review": False, "parent_id": "e1"},
        ]
        show = self._call(entries)
        assert show == set()

    def test_cycle_guard_no_infinite_loop(self):
        """Mutual-parent references are guarded against infinite recursion."""
        entries = [
            {"id": "e1", "identifier": "E-1", "state": "closed", "has_open_review": False, "parent_id": "t1"},
            {"id": "t1", "identifier": "T-1", "state": "closed", "has_open_review": False, "parent_id": "e1"},
        ]
        # Should terminate without error
        show = self._call(entries)
        assert isinstance(show, set)

    def test_deep_hierarchy_walks_up_to_root(self):
        """A deeply nested in-flight issue causes all ancestors to be in show-set."""
        entries = [
            {"id": "e1", "identifier": "E-1", "state": "open", "has_open_review": False, "parent_id": None},
            {"id": "t1", "identifier": "T-1", "state": "closed", "has_open_review": False, "parent_id": "e1"},
            {"id": "t2", "identifier": "T-2", "state": "in_progress", "has_open_review": False, "parent_id": "t1"},
        ]
        show = self._call(entries)
        assert "t2" in show   # individually in-flight
        assert "t1" in show   # subtree has in-flight
        assert "e1" in show   # subtree has in-flight

    def test_closed_with_open_review_is_individually_inflight(self):
        """Closed issue with open review counts as in-flight."""
        entries = [
            {"id": "t1", "identifier": "T-1", "state": "closed", "has_open_review": True, "parent_id": None},
        ]
        show = self._call(entries)
        assert "t1" in show


# ---------------------------------------------------------------------------
# API integration tests for hide_merged query param
# ---------------------------------------------------------------------------

class TestApiIssuesHideMerged:
    """Tests for /api/v1/issues?hide_merged=true filtering."""

    def test_no_hide_merged_returns_all_unchanged(self, api_client):
        """Without hide_merged param, API returns all issues unchanged."""
        issues = [
            _make_issue(id="e1", identifier="E-1", state="closed"),
            _make_issue(id="t1", identifier="T-1", state="closed", parent_id="e1"),
        ]
        mock_orch = _make_orch_with_issues(issues)

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = api_client.get("/api/v1/issues")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["closed"]) == 2

    def test_hide_merged_false_returns_all_unchanged(self, api_client):
        """With hide_merged=false, API returns all issues (backwards-compat)."""
        issues = [
            _make_issue(id="e1", identifier="E-1", state="closed"),
            _make_issue(id="t1", identifier="T-1", state="closed", parent_id="e1"),
        ]
        mock_orch = _make_orch_with_issues(issues)

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = api_client.get("/api/v1/issues?hide_merged=false")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["closed"]) == 2

    def test_hide_merged_true_filters_closed_column(self, api_client):
        """hide_merged=true removes closed issues not in any in-flight tree."""
        issues = [
            _make_issue(id="e1", identifier="E-1", state="closed"),
            _make_issue(id="t1", identifier="T-1", state="closed", parent_id="e1"),
        ]
        mock_orch = _make_orch_with_issues(issues)

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = api_client.get("/api/v1/issues?hide_merged=true")

        assert resp.status_code == 200
        data = resp.json()
        # All-closed, no in-flight ancestor -> closed column empty
        assert len(data["closed"]) == 0
        # Response should still have a closed key (possibly empty list)
        assert "closed" in data

    def test_hide_merged_true_shows_open_ancestor_of_closed_leaf(self, api_client):
        """If a closed child has an in-flight ancestor, the ancestor's epic stays visible."""
        issues = [
            _make_issue(id="e1", identifier="E-1", state="open"),
            _make_issue(id="t1", identifier="T-1", state="closed", parent_id="e1"),
        ]
        mock_orch = _make_orch_with_issues(issues)

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = api_client.get("/api/v1/issues?hide_merged=true")

        assert resp.status_code == 200
        data = resp.json()
        # e1 is in-flight (open) -> kept; t1 is closed but ancestor in-flight -> kept
        closed_ids = [e["id"] for e in data["closed"]]
        open_ids = [e["id"] for e in data["open"]]
        assert "e1" in open_ids
        assert "e1" in closed_ids or "t1" in closed_ids

    def test_hide_merged_true_shows_closed_issue_with_open_review(self, api_client):
        """Closed issue with an open PR (has_open_review) is kept."""
        issues = [
            _make_issue(id="t1", identifier="T-1", state="closed"),
        ]
        # Patch unmerged_branches so has_open_review is True for t1
        mock_orch = _make_orch_with_issues(issues, unmerged_branches={"T-1"})

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = api_client.get("/api/v1/issues?hide_merged=true")

        assert resp.status_code == 200
        data = resp.json()
        # t1 has open review -> should be in show-set
        assert len(data["closed"]) == 1

    def test_hide_merged_preserves_non_closed_columns(self, api_client):
        """hide_merged only filters the 'closed' column; others pass through."""
        issues = [
            _make_issue(id="e1", identifier="E-1", state="open"),
            _make_issue(id="t1", identifier="T-1", state="in_progress", parent_id="e1"),
            _make_issue(id="t2", identifier="T-2", state="closed", parent_id="e1"),
        ]
        mock_orch = _make_orch_with_issues(issues)

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = api_client.get("/api/v1/issues?hide_merged=true")

        assert resp.status_code == 200
        data = resp.json()
        assert "open" in data
        assert "in_progress" in data
        # deferred column won't exist if there are no deferred issues
        assert len(data["open"]) == 1
        assert len(data["in_progress"]) == 1

    def test_hide_merged_with_project_filter(self, api_client):
        """hide_merged composes correctly with project_id filter."""
        issues = [
            _make_issue(id="e1", identifier="E-1", state="closed", project_id="proj-1"),
            _make_issue(id="t1", identifier="T-1", state="in_progress", parent_id="e1", project_id="proj-1"),
            _make_issue(id="e2", identifier="E-2", state="closed", project_id="proj-2"),
        ]
        mock_orch = _make_orch_with_issues(issues)

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = api_client.get("/api/v1/issues?hide_merged=true&project_id=proj-1")

        assert resp.status_code == 200
        data = resp.json()
        # Only proj-1 issues should be returned
        all_ids = {e["id"] for col in data.values() for e in col}
        assert "e1" in all_ids or "t1" in all_ids
        assert "e2" not in all_ids