"""Regression tests: draft-epic dashboard UI removed (OOMPAH-171).

After OOMPAH-171, the dashboard must NOT contain any draft-epic specific:
- CSS classes (.draft-epic-badge, .swimlane-draft-badge)
- JavaScript functions (hasDraftLabel, toggleEpicDraft)
- HTML controls (Mark as Draft / Finalize buttons, swimlane-draft-badge spans)
- Logic branches (hasDraftLabel checks in shouldShowIssueAsWorkCard / isEpicMergeFlowCard)

The API must still work correctly for issues that carry a 'draft' label as a
generic label — this file covers server-side regression coverage.

See issue: OOMPAH-171
"""

from __future__ import annotations

import os
import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.server import app
from oompah.models import Issue


# ---------------------------------------------------------------------------
# HTML loading helpers
# ---------------------------------------------------------------------------

def _load_dashboard_html() -> str:
    template_path = os.path.join(
        os.path.dirname(__file__), os.pardir, "oompah", "templates", "dashboard.html"
    )
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()


def _extract_script(html: str) -> str:
    matches = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    return max(matches, key=len) if matches else ""


# ---------------------------------------------------------------------------
# Fixtures
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


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# CSS regression tests
# ---------------------------------------------------------------------------

class TestDraftEpicCSSRemoved:
    """The .draft-epic-badge and .swimlane-draft-badge CSS must be gone."""

    def test_draft_epic_badge_css_absent(self):
        html = _load_dashboard_html()
        assert ".draft-epic-badge" not in html, (
            ".draft-epic-badge CSS must be removed (OOMPAH-171)"
        )

    def test_swimlane_draft_badge_css_absent(self):
        html = _load_dashboard_html()
        assert ".swimlane-draft-badge" not in html, (
            ".swimlane-draft-badge CSS must be removed (OOMPAH-171)"
        )


# ---------------------------------------------------------------------------
# JavaScript function regression tests
# ---------------------------------------------------------------------------

class TestDraftEpicJSRemoved:
    """hasDraftLabel() and toggleEpicDraft() JS functions must be absent."""

    def test_has_draft_label_function_absent(self):
        html = _load_dashboard_html()
        script = _extract_script(html)
        assert "hasDraftLabel" not in script, (
            "hasDraftLabel() JS function must be removed (OOMPAH-171)"
        )

    def test_toggle_epic_draft_function_absent(self):
        html = _load_dashboard_html()
        script = _extract_script(html)
        assert "toggleEpicDraft" not in script, (
            "toggleEpicDraft() JS function must be removed (OOMPAH-171)"
        )

    def test_should_show_issue_no_has_draft_check(self):
        html = _load_dashboard_html()
        script = _extract_script(html)
        # shouldShowIssueAsWorkCard must not call hasDraftLabel
        assert "hasDraftLabel" not in script, (
            "shouldShowIssueAsWorkCard must not call hasDraftLabel (OOMPAH-171)"
        )

    def test_is_epic_merge_flow_no_draft_check(self):
        html = _load_dashboard_html()
        script = _extract_script(html)
        # isEpicMergeFlowCard must not reference hasDraftLabel
        assert "hasDraftLabel" not in script, (
            "isEpicMergeFlowCard must not reference hasDraftLabel (OOMPAH-171)"
        )

    def test_draft_epic_badge_html_variable_absent(self):
        html = _load_dashboard_html()
        script = _extract_script(html)
        assert "draftEpicBadgeHtml" not in script, (
            "draftEpicBadgeHtml variable must be removed (OOMPAH-171)"
        )


# ---------------------------------------------------------------------------
# HTML control regression tests
# ---------------------------------------------------------------------------

class TestDraftEpicHTMLControlsRemoved:
    """Mark as Draft / Finalize buttons and swimlane-draft-badge spans must be absent."""

    def test_mark_as_draft_button_absent(self):
        html = _load_dashboard_html()
        assert "Mark as Draft" not in html, (
            "'Mark as Draft' button must be removed (OOMPAH-171)"
        )

    def test_finalize_button_absent(self):
        html = _load_dashboard_html()
        # "Finalize" should not appear as a draft-lifecycle control
        # (it should only appear in merge/other contexts if at all)
        assert "Finalize" not in html, (
            "'Finalize' draft button must be removed (OOMPAH-171)"
        )

    def test_swimlane_draft_badge_span_absent(self):
        html = _load_dashboard_html()
        assert "swimlane-draft-badge" not in html, (
            "swimlane-draft-badge span must be removed (OOMPAH-171)"
        )

    def test_draft_epic_badge_span_absent(self):
        html = _load_dashboard_html()
        assert "draft-epic-badge" not in html, (
            "draft-epic-badge span must be removed (OOMPAH-171)"
        )


# ---------------------------------------------------------------------------
# Server API regression tests: labels still work as generic labels
# ---------------------------------------------------------------------------

class TestEpicLabelAPIStillWorks:
    """The label API endpoints must still function for generic label use."""

    def test_add_label_endpoint_returns_200(self, client):
        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_tracker.add_label.return_value = None

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues/OOMPAH-1/labels",
                json={"label": "needs-review", "project_id": "proj-1"},
            )

        assert resp.status_code in (200, 201), resp.text
        mock_tracker.add_label.assert_called_once_with("OOMPAH-1", "needs-review")

    def test_remove_label_endpoint_returns_200(self, client):
        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_tracker.remove_label.return_value = None

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.delete(
                "/api/v1/issues/OOMPAH-1/labels/needs-review",
                params={"project_id": "proj-1"},
            )

        assert resp.status_code == 200, resp.text
        mock_tracker.remove_label.assert_called_once_with("OOMPAH-1", "needs-review")

    def test_api_returns_labels_field_for_epic(self, client):
        """API response must include labels so the frontend can display them."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        epic = _make_issue(identifier="OOMPAH-10", issue_type="epic", labels=["team:alpha"])
        mock_tracker.fetch_all_issues.return_value = [epic]

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = client.get("/api/v1/issues")

        assert resp.status_code == 200, resp.text
        # The API returns a board format: {"Open": [...], "In Progress": [...], ...}
        all_issues = _all_issues_from_board(resp.json())
        epic_entry = next((i for i in all_issues if i.get("identifier") == "OOMPAH-10"), None)
        assert epic_entry is not None
        assert "labels" in epic_entry

    def test_create_epic_does_not_auto_add_draft_label(self, client):
        """Creating an epic must NOT automatically add 'draft' label (OOMPAH-171)."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_tracker.create_issue.return_value = _make_issue(
            identifier="OOMPAH-NEW", issue_type="epic"
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
        # No automatic draft label
        mock_tracker.add_label.assert_not_called()
