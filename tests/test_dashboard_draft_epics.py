"""Tests for draft epic visibility in the flat kanban view.

Covers:
  1. renderFlatView() filter logic — draft epics pass through, non-draft epics are excluded
  2. col-count reflects only the filtered (non-draft-epic) set
  3. createCard() Draft Epic badge — HTML structure, CSS class, condition, accessibility
  4. .draft-epic-badge CSS styling (distinct from .merged-badge)
  5. Server-side API data shape — labels and issue_type are included so the
     frontend filter can work correctly
  6. Edge cases — missing labels, epic without draft, non-epic with draft, etc.

See issue: oompah-14u
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
# Helpers — load dashboard.html and extract the JS <script> block
# ---------------------------------------------------------------------------

def _load_dashboard_html() -> str:
    """Load dashboard HTML from the templates directory."""
    template_path = os.path.join(
        os.path.dirname(__file__), os.pardir, "oompah", "templates", "dashboard.html"
    )
    with open(template_path, "r") as f:
        return f.read()


def _extract_script(html: str) -> str:
    """Extract the main (largest) <script> block from the dashboard HTML."""
    matches = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    assert matches, "Could not find any <script> block in dashboard HTML"
    return max(matches, key=len)


def _extract_renderFlatView(script: str) -> str:
    """Extract the body of renderFlatView from the script."""
    match = re.search(
        r"function renderFlatView\(.*?\)\s*\{(.*?)(?=\nfunction |\Z)",
        script,
        re.DOTALL,
    )
    assert match, "Could not find renderFlatView function in script"
    return match.group(1)


def _extract_createCard(script: str) -> str:
    """Extract the body of createCard from the script."""
    match = re.search(
        r"function createCard\(.*?\)\s*\{(.*?)(?=\nfunction |\Z)",
        script,
        re.DOTALL,
    )
    assert match, "Could not find createCard function in script"
    return match.group(1)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def html():
    return _load_dashboard_html()


@pytest.fixture(scope="module")
def script(html):
    return _extract_script(html)


@pytest.fixture(scope="module")
def render_flat_body(script):
    return _extract_renderFlatView(script)


@pytest.fixture(scope="module")
def create_card_body(script):
    return _extract_createCard(script)


@pytest.fixture(autouse=True)
def clear_api_cache():
    """Clear the server-side API cache before each test to prevent cross-test contamination."""
    server_module._api_cache.clear()
    yield
    server_module._api_cache.clear()


@pytest.fixture()
def api_client():
    """TestClient for FastAPI app."""
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Helper: build a minimal mock Orchestrator with stubbed fetch_all_issues
# ---------------------------------------------------------------------------

def _make_orch_with_issues(issues: list[Issue]) -> MagicMock:
    """Return a mock Orchestrator whose tracker returns the given issues."""
    mock_tracker = MagicMock()
    mock_tracker.fetch_all_issues.return_value = issues

    mock_orch = MagicMock()
    # For _fetch_all_issues: orch.project_store.list_all() returns no projects → legacy mode
    mock_orch.project_store.list_all.return_value = []
    mock_orch.tracker = mock_tracker
    return mock_orch


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


# ===========================================================================
# 1. renderFlatView() filter — draft epics pass through
# ===========================================================================

class TestRenderFlatViewFilter:
    """Verify the filter expression in renderFlatView allows draft epics through."""

    def test_filter_excludes_non_draft_epics(self, render_flat_body):
        """The filter must exclude plain epics (no 'draft' label)."""
        # The filter line must have: issue_type !== 'epic' OR includes('draft')
        assert re.search(
            r"filter\(.*issue_type\s*!==\s*['\"]epic['\"]",
            render_flat_body,
        ), "renderFlatView must filter out non-draft epics via issue_type !== 'epic'"

    def test_filter_includes_draft_epics_via_or_clause(self, render_flat_body):
        """The filter must allow through epics that include the 'draft' label."""
        assert "draft" in render_flat_body, (
            "renderFlatView filter must reference 'draft' to pass draft epics through"
        )
        # The OR branch should include draft label check
        assert re.search(
            r"issue_type\s*!==\s*['\"]epic['\"].*\|\|.*draft",
            render_flat_body,
            re.DOTALL,
        ), "renderFlatView filter must OR-include draft epics"

    def test_filter_uses_labels_includes_pattern(self, render_flat_body):
        """The filter must use .includes('draft') on labels array."""
        assert re.search(
            r"labels.*\|\|\s*\[\s*\]\)\.includes\(['\"]draft['\"]\)",
            render_flat_body,
        ) or re.search(
            r"labels.*includes\(['\"]draft['\"]\)",
            render_flat_body,
        ), "renderFlatView filter must use .includes('draft') on labels array"

    def test_filter_handles_missing_labels_with_default_array(self, render_flat_body):
        """The filter must use (labels || []) to safely handle issues without labels."""
        assert re.search(
            r"\(.*labels\s*\|\|\s*\[\s*\]\)",
            render_flat_body,
        ), "renderFlatView filter must use '|| []' to handle missing labels"

    def test_filter_named_issues_variable(self, render_flat_body):
        """The filtered result must be stored in a variable named 'issues'."""
        assert re.search(
            r"(?:const|let|var)\s+issues\s*=\s*allInCol\.filter\(",
            render_flat_body,
        ), "renderFlatView must store filtered issues in 'const issues = allInCol.filter(...)'"

    def test_filter_correct_full_expression(self, render_flat_body):
        """The exact filter expression must match the spec."""
        # Expected: filter(i => i.issue_type !== 'epic' || (i.labels || []).includes('draft'))
        assert re.search(
            r"filter\(\s*i\s*=>\s*i\.issue_type\s*!==\s*['\"]epic['\"]"
            r"\s*\|\|\s*\(i\.labels\s*\|\|\s*\[\s*\]\)\.includes\(['\"]draft['\"]\)\s*\)",
            render_flat_body,
        ), (
            "renderFlatView filter must be: "
            "filter(i => i.issue_type !== 'epic' || (i.labels || []).includes('draft'))"
        )

    def test_col_count_uses_issues_length(self, render_flat_body):
        """The column count badge must reflect issues.length (filtered count)."""
        assert re.search(
            r"col-count.*\$\{issues\.length\}",
            render_flat_body,
        ) or re.search(
            r"\$\{issues\.length\}.*col-count",
            render_flat_body,
        ), "col-count must display issues.length (filtered count including draft epics)"

    def test_non_draft_epics_excluded_semantically(self, render_flat_body):
        """Confirm the filter semantics: epic without draft → excluded; epic with draft → included."""
        # The filter is: issue_type !== 'epic' || (labels||[]).includes('draft')
        # For a plain epic (issue_type='epic', labels=[]):
        #   false || false → false → excluded ✓
        # For a draft epic (issue_type='epic', labels=['draft']):
        #   false || true → true → included ✓
        # For a task (issue_type='task'):
        #   true → true → included ✓
        # This test confirms the filter expression encodes these semantics by
        # looking at the whole filter line (not just up to the first closing paren)
        filter_match = re.search(
            r"const\s+issues\s*=\s*allInCol\.filter\((.*?)\)\s*;",
            render_flat_body,
            re.DOTALL,
        )
        assert filter_match, "Could not find 'const issues = allInCol.filter(...)' statement"
        expr = filter_match.group(1)
        # Must contain the exclusive-or pattern (not-epic OR has-draft)
        assert "!== 'epic'" in expr or '!== "epic"' in expr, (
            "Filter must use issue_type !== 'epic'"
        )
        assert "draft" in expr, (
            "Filter must reference 'draft' for the draft epic exception"
        )


# ===========================================================================
# 2. col-count correctness
# ===========================================================================

class TestColCount:
    """Verify that the col-count reflects the filtered set, not the raw set."""

    def test_col_count_placed_in_column_header(self, render_flat_body):
        """col-count span must appear in the column-header template."""
        assert re.search(
            r"column-header.*col-count",
            render_flat_body,
            re.DOTALL,
        ), "col-count must be inside column-header"

    def test_col_count_bound_to_issues_not_allInCol(self, render_flat_body):
        """col-count must display issues.length, NOT allInCol.length."""
        # allInCol.length would be wrong — non-draft epics would inflate the count
        assert "allInCol.length" not in render_flat_body or (
            render_flat_body.index("issues.length") < render_flat_body.index("allInCol.length")
        ), (
            "col-count must NOT use allInCol.length — it must use issues.length "
            "so non-draft epics do not inflate the count"
        )

    def test_col_count_is_filtered_issues_length(self, render_flat_body):
        """col-count must use the filtered `issues` variable."""
        # Find col-count in the HTML template within renderFlatView
        col_count_match = re.search(
            r"col-count[^<]*\$\{(\w+)\.length\}",
            render_flat_body,
        )
        assert col_count_match, "Could not find col-count with template literal"
        var_name = col_count_match.group(1)
        assert var_name == "issues", (
            f"col-count uses '{var_name}.length' but must use 'issues.length' "
            "(the filtered list, not the raw allInCol)"
        )


# ===========================================================================
# 3. createCard() Draft Epic Badge — condition and HTML
# ===========================================================================

class TestCreateCardDraftEpicBadge:
    """Verify that createCard() generates the Draft Epic badge correctly."""

    def test_draftEpicBadgeHtml_variable_declared(self, create_card_body):
        """createCard must declare a draftEpicBadgeHtml variable."""
        assert "draftEpicBadgeHtml" in create_card_body, (
            "createCard must define draftEpicBadgeHtml"
        )

    def test_draftEpicBadgeHtml_condition_checks_issue_type_epic(self, create_card_body):
        """draftEpicBadgeHtml condition must check issue_type === 'epic'."""
        badge_match = re.search(
            r"(?:const|let|var)\s+draftEpicBadgeHtml\s*=\s*(.*?);",
            create_card_body,
            re.DOTALL,
        )
        assert badge_match, "Could not find draftEpicBadgeHtml declaration"
        condition = badge_match.group(1)
        assert re.search(r"issue_type\s*===\s*['\"]epic['\"]", condition), (
            "draftEpicBadgeHtml must check issue_type === 'epic'"
        )

    def test_draftEpicBadgeHtml_condition_checks_draft_label(self, create_card_body):
        """draftEpicBadgeHtml condition must check for 'draft' in labels."""
        badge_match = re.search(
            r"(?:const|let|var)\s+draftEpicBadgeHtml\s*=\s*(.*?);",
            create_card_body,
            re.DOTALL,
        )
        assert badge_match
        condition = badge_match.group(1)
        assert "draft" in condition, (
            "draftEpicBadgeHtml must check labels for 'draft'"
        )

    def test_draftEpicBadgeHtml_handles_missing_labels(self, create_card_body):
        """draftEpicBadgeHtml condition must use (issue.labels || []) for safety."""
        badge_match = re.search(
            r"(?:const|let|var)\s+draftEpicBadgeHtml\s*=\s*(.*?);",
            create_card_body,
            re.DOTALL,
        )
        assert badge_match
        condition = badge_match.group(1)
        assert "|| []" in condition or "||[]" in condition, (
            "draftEpicBadgeHtml must use (issue.labels || []) to handle null/undefined labels"
        )

    def test_draftEpicBadgeHtml_contains_Draft_Epic_text(self, create_card_body):
        """The badge HTML must contain the text 'Draft Epic'."""
        assert "Draft Epic" in create_card_body, (
            "createCard must produce a badge with the text 'Draft Epic'"
        )

    def test_draftEpicBadgeHtml_uses_draft_epic_badge_class(self, create_card_body):
        """The badge HTML must use the CSS class 'draft-epic-badge'."""
        assert "draft-epic-badge" in create_card_body, (
            "createCard must use CSS class 'draft-epic-badge'"
        )

    def test_draftEpicBadgeHtml_has_aria_label(self, create_card_body):
        """The badge span must include aria-label for accessibility."""
        badge_match = re.search(
            r"(?:const|let|var)\s+draftEpicBadgeHtml\s*=\s*(.*?);",
            create_card_body,
            re.DOTALL,
        )
        assert badge_match
        badge_code = badge_match.group(1)
        assert "aria-label" in badge_code, (
            "draft-epic-badge span must include aria-label for accessibility"
        )

    def test_draftEpicBadgeHtml_rendered_in_card_innerHTML(self, create_card_body):
        """draftEpicBadgeHtml must be interpolated into card.innerHTML."""
        inner_html_match = re.search(
            r"card\.innerHTML\s*=\s*`(.*?)`\s*;",
            create_card_body,
            re.DOTALL,
        )
        assert inner_html_match, "Could not find card.innerHTML template"
        inner_html = inner_html_match.group(1)
        assert "${draftEpicBadgeHtml}" in inner_html, (
            "draftEpicBadgeHtml must be interpolated in card.innerHTML"
        )

    def test_draftEpicBadgeHtml_inside_card_id_left(self, create_card_body):
        """draftEpicBadgeHtml must appear inside the card-id-left span."""
        inner_html_match = re.search(
            r"card\.innerHTML\s*=\s*`(.*?)`\s*;",
            create_card_body,
            re.DOTALL,
        )
        assert inner_html_match
        inner_html = inner_html_match.group(1)
        # Find card-id-left and priority-badge positions; draftEpicBadgeHtml must be between them
        left_pos = inner_html.find("card-id-left")
        draft_pos = inner_html.find("${draftEpicBadgeHtml}")
        priority_pos = inner_html.find("priority-badge")
        assert left_pos != -1, "card-id-left must be in card.innerHTML"
        assert draft_pos != -1, "draftEpicBadgeHtml must be in card.innerHTML"
        assert priority_pos != -1, "priority-badge must be in card.innerHTML"
        assert left_pos < draft_pos < priority_pos, (
            "draftEpicBadgeHtml must appear inside card-id-left, before priority-badge"
        )

    def test_draftEpicBadgeHtml_alongside_mergedBadgeHtml(self, create_card_body):
        """Both draftEpicBadgeHtml and mergedBadgeHtml must appear in card.innerHTML."""
        inner_html_match = re.search(
            r"card\.innerHTML\s*=\s*`(.*?)`\s*;",
            create_card_body,
            re.DOTALL,
        )
        assert inner_html_match
        inner_html = inner_html_match.group(1)
        assert "${draftEpicBadgeHtml}" in inner_html, "draftEpicBadgeHtml missing from card.innerHTML"
        assert "${mergedBadgeHtml}" in inner_html, "mergedBadgeHtml missing from card.innerHTML"

    def test_draftEpicBadgeHtml_is_empty_for_non_epic(self, create_card_body):
        """draftEpicBadgeHtml ternary must produce empty string for non-epics."""
        # The ternary should be: (condition) ? '<badge>' : ''
        badge_match = re.search(
            r"(?:const|let|var)\s+draftEpicBadgeHtml\s*=\s*(.*?);",
            create_card_body,
            re.DOTALL,
        )
        assert badge_match
        condition = badge_match.group(1)
        # A ternary with empty-string fallback
        assert re.search(r":\s*['\"]['\"]", condition) or re.search(r":\s*``", condition), (
            "draftEpicBadgeHtml ternary must produce empty string ('') when not a draft epic"
        )


# ===========================================================================
# 4. .draft-epic-badge CSS — styling and distinctiveness
# ===========================================================================

class TestDraftEpicBadgeCSS:
    """Verify the .draft-epic-badge CSS class has correct and distinct styling."""

    def test_draft_epic_badge_class_defined_in_stylesheet(self, html):
        """.draft-epic-badge must be defined in the <style> block."""
        style_match = re.search(r"<style>(.*?)</style>", html, re.DOTALL)
        assert style_match, "No <style> block found"
        style = style_match.group(1)
        assert ".draft-epic-badge" in style, (
            ".draft-epic-badge CSS class must be defined in the <style> block"
        )

    def test_draft_epic_badge_uses_accent_color_not_purple(self, html):
        """draft-epic-badge must use --accent (blue), NOT --purple, to differ from merged-badge."""
        badge_match = re.search(
            r"\.draft-epic-badge\s*\{([^}]*)\}",
            html,
            re.DOTALL,
        )
        assert badge_match, "Could not find .draft-epic-badge CSS block"
        css_body = badge_match.group(1)
        assert "--accent" in css_body or "#58a6ff" in css_body, (
            "draft-epic-badge should use --accent (blue) color"
        )
        assert "--purple" not in css_body, (
            "draft-epic-badge should NOT use --purple (to distinguish from merged-badge)"
        )

    def test_draft_epic_badge_has_border_radius(self, html):
        """draft-epic-badge must have border-radius for pill-like appearance."""
        badge_match = re.search(
            r"\.draft-epic-badge\s*\{([^}]*)\}",
            html,
            re.DOTALL,
        )
        assert badge_match
        assert "border-radius" in badge_match.group(1)

    def test_draft_epic_badge_has_font_size(self, html):
        """draft-epic-badge must specify font-size consistent with other badges."""
        badge_match = re.search(
            r"\.draft-epic-badge\s*\{([^}]*)\}",
            html,
            re.DOTALL,
        )
        assert badge_match
        assert "font-size" in badge_match.group(1)

    def test_draft_epic_badge_has_monospace_font_family(self, html):
        """draft-epic-badge must use a monospace font-family consistent with other badges."""
        badge_match = re.search(
            r"\.draft-epic-badge\s*\{([^}]*)\}",
            html,
            re.DOTALL,
        )
        assert badge_match
        assert "font-family" in badge_match.group(1)

    def test_draft_epic_badge_has_padding(self, html):
        """draft-epic-badge must have padding for visual comfort."""
        badge_match = re.search(
            r"\.draft-epic-badge\s*\{([^}]*)\}",
            html,
            re.DOTALL,
        )
        assert badge_match
        assert "padding" in badge_match.group(1)

    def test_draft_epic_badge_visually_distinct_from_merged_badge(self, html):
        """draft-epic-badge and merged-badge must use different color values."""
        merged_match = re.search(
            r"\.merged-badge\s*\{([^}]*)\}",
            html,
            re.DOTALL,
        )
        draft_match = re.search(
            r"\.draft-epic-badge\s*\{([^}]*)\}",
            html,
            re.DOTALL,
        )
        assert merged_match, "merged-badge CSS not found"
        assert draft_match, "draft-epic-badge CSS not found"
        merged_css = merged_match.group(1)
        draft_css = draft_match.group(1)
        # Colors must differ — merged uses purple, draft should use accent/blue
        merged_has_purple = "--purple" in merged_css or "purple" in merged_css.lower()
        draft_has_purple = "--purple" in draft_css or "purple" in draft_css.lower()
        assert merged_has_purple, "merged-badge should reference purple color"
        assert not draft_has_purple, (
            "draft-epic-badge must NOT use purple — it must differ from merged-badge"
        )

    def test_draft_epic_badge_in_style_before_close_style_tag(self, html):
        """draft-epic-badge CSS must appear inside the <style> block."""
        draft_pos = html.find(".draft-epic-badge")
        style_end = html.find("</style>")
        assert draft_pos != -1, ".draft-epic-badge not found"
        assert style_end != -1, "</style> tag not found"
        assert draft_pos < style_end, (
            ".draft-epic-badge CSS rule must appear before </style>"
        )


# ===========================================================================
# 5. Server-side API data shape — labels and issue_type are serialized
# ===========================================================================

class TestApiIssuesDataShape:
    """Verify /api/v1/issues returns the fields the frontend filter needs."""

    def test_api_issues_includes_labels_field(self, api_client):
        """Each issue in the API response must include a 'labels' list."""
        issues = [
            _make_issue(id="e1", identifier="E-1", issue_type="epic", labels=["draft"]),
            _make_issue(id="t1", identifier="T-1", issue_type="task", labels=[]),
        ]
        mock_orch = _make_orch_with_issues(issues)

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = api_client.get("/api/v1/issues")

        assert resp.status_code == 200
        data = resp.json()
        all_entries = [entry for col in data.values() for entry in col]
        for entry in all_entries:
            assert "labels" in entry, f"Issue {entry.get('id')} is missing 'labels' field"

    def test_api_issues_includes_issue_type_field(self, api_client):
        """Each issue in the API response must include 'issue_type'."""
        issues = [
            _make_issue(id="e1", identifier="E-1", issue_type="epic", labels=["draft"]),
            _make_issue(id="t1", identifier="T-1", issue_type="task"),
        ]
        mock_orch = _make_orch_with_issues(issues)

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = api_client.get("/api/v1/issues")

        assert resp.status_code == 200
        data = resp.json()
        all_entries = [entry for col in data.values() for entry in col]
        for entry in all_entries:
            assert "issue_type" in entry, f"Issue {entry.get('id')} is missing 'issue_type'"

    def test_api_issues_draft_epic_labels_preserved(self, api_client):
        """A draft epic's labels list must include 'draft' in the API response."""
        draft_epic = _make_issue(
            id="e1", identifier="EPIC-1", issue_type="epic", labels=["draft"]
        )
        mock_orch = _make_orch_with_issues([draft_epic])

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = api_client.get("/api/v1/issues")

        assert resp.status_code == 200
        data = resp.json()
        all_entries = [entry for col in data.values() for entry in col]
        epic_entries = [e for e in all_entries if e.get("issue_type") == "epic"]
        assert epic_entries, "No epic entries found in response"
        draft_epic_entries = [e for e in epic_entries if "draft" in e.get("labels", [])]
        assert draft_epic_entries, (
            "Draft epic must have 'draft' in labels in the API response"
        )

    def test_api_issues_non_draft_epic_not_labeled_draft(self, api_client):
        """A non-draft epic must NOT have 'draft' in its labels."""
        plain_epic = _make_issue(
            id="e2", identifier="EPIC-2", issue_type="epic", labels=[]
        )
        mock_orch = _make_orch_with_issues([plain_epic])

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = api_client.get("/api/v1/issues")

        assert resp.status_code == 200
        data = resp.json()
        all_entries = [entry for col in data.values() for entry in col]
        epic_entries = [e for e in all_entries if e.get("issue_type") == "epic"]
        for entry in epic_entries:
            assert "draft" not in entry.get("labels", []), (
                f"Non-draft epic {entry.get('identifier')} must NOT have 'draft' in labels"
            )

    def test_api_issues_includes_all_required_fields(self, api_client):
        """Each issue entry must include id, identifier, title, state, labels, issue_type."""
        issues = [
            _make_issue(id="t1", identifier="T-1", title="A task", issue_type="task"),
        ]
        mock_orch = _make_orch_with_issues(issues)

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = api_client.get("/api/v1/issues")

        assert resp.status_code == 200
        data = resp.json()
        all_entries = [entry for col in data.values() for entry in col]
        assert all_entries, "No issues returned"
        required_fields = {"id", "identifier", "title", "state", "labels", "issue_type"}
        for entry in all_entries:
            missing = required_fields - set(entry.keys())
            assert not missing, f"Issue {entry.get('identifier')} missing fields: {missing}"

    def test_api_issues_grouped_by_state(self, api_client):
        """API response must group issues by state (open, in_progress, etc.)."""
        issues = [
            _make_issue(id="t1", identifier="T-1", state="open"),
            _make_issue(id="t2", identifier="T-2", state="in_progress"),
        ]
        mock_orch = _make_orch_with_issues(issues)

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = api_client.get("/api/v1/issues")

        assert resp.status_code == 200
        data = resp.json()
        assert "open" in data, "Response must have 'open' key"
        assert "in_progress" in data, "Response must have 'in_progress' key"

    def test_api_issues_labels_is_list_not_null(self, api_client):
        """Labels field must be a list even when the issue has no labels."""
        issues = [
            _make_issue(id="t1", identifier="T-1", labels=[]),
        ]
        mock_orch = _make_orch_with_issues(issues)

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = api_client.get("/api/v1/issues")

        assert resp.status_code == 200
        data = resp.json()
        all_entries = [entry for col in data.values() for entry in col]
        for entry in all_entries:
            assert isinstance(entry["labels"], list), (
                f"labels must be a list, got {type(entry['labels'])}"
            )


# ===========================================================================
# 6. Edge cases — server-side filtering and serialization correctness
# ===========================================================================

class TestApiIssuesEdgeCases:
    """Edge cases for the server-side API endpoint."""

    def test_archived_issues_excluded_from_response(self, api_client):
        """Issues with 'archive:yes' label must be excluded from the response."""
        issues = [
            _make_issue(id="t1", identifier="T-ARCHIVED", labels=["archive:yes"]),
            _make_issue(id="t2", identifier="T-VISIBLE", labels=[]),
        ]
        mock_orch = _make_orch_with_issues(issues)

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = api_client.get("/api/v1/issues")

        assert resp.status_code == 200
        data = resp.json()
        all_entries = [entry for col in data.values() for entry in col]
        identifiers = [e["identifier"] for e in all_entries]
        assert "T-ARCHIVED" not in identifiers, "Archived issues must be excluded"
        assert "T-VISIBLE" in identifiers, "Non-archived issues must be included"

    def test_draft_epic_appears_in_api_response(self, api_client):
        """A draft epic must appear in the API response (not filtered out server-side)."""
        issues = [
            _make_issue(
                id="e1", identifier="EPIC-DRAFT", issue_type="epic", labels=["draft"]
            ),
        ]
        mock_orch = _make_orch_with_issues(issues)

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = api_client.get("/api/v1/issues")

        assert resp.status_code == 200
        data = resp.json()
        all_entries = [entry for col in data.values() for entry in col]
        identifiers = [e["identifier"] for e in all_entries]
        assert "EPIC-DRAFT" in identifiers, (
            "Draft epic must appear in API response — server-side should NOT filter it out"
        )

    def test_non_draft_epic_appears_in_api_response(self, api_client):
        """A non-draft epic must also appear in the API response (server-side includes all epics)."""
        issues = [
            _make_issue(id="e2", identifier="EPIC-PLAIN", issue_type="epic", labels=[]),
        ]
        mock_orch = _make_orch_with_issues(issues)

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = api_client.get("/api/v1/issues")

        assert resp.status_code == 200
        data = resp.json()
        all_entries = [entry for col in data.values() for entry in col]
        identifiers = [e["identifier"] for e in all_entries]
        assert "EPIC-PLAIN" in identifiers, (
            "Non-draft epic must appear in API response — filtering is done client-side in flat view"
        )

    def test_task_with_draft_label_not_confused_with_draft_epic(self, api_client):
        """A task with 'draft' label is NOT a draft epic and must pass through normally."""
        issues = [
            _make_issue(id="t1", identifier="TASK-DRAFT", issue_type="task", labels=["draft"]),
        ]
        mock_orch = _make_orch_with_issues(issues)

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = api_client.get("/api/v1/issues")

        assert resp.status_code == 200
        data = resp.json()
        all_entries = [entry for col in data.values() for entry in col]
        task_entries = [e for e in all_entries if e.get("identifier") == "TASK-DRAFT"]
        assert task_entries, "Task with 'draft' label must appear in API response"
        assert task_entries[0]["issue_type"] == "task", "issue_type must remain 'task'"
        assert "draft" in task_entries[0]["labels"], "labels must include 'draft'"

    def test_multiple_labels_including_draft_on_epic(self, api_client):
        """An epic with multiple labels including 'draft' must be recognized as a draft epic."""
        issues = [
            _make_issue(
                id="e1",
                identifier="EPIC-MULTI",
                issue_type="epic",
                labels=["planning", "draft", "team:alpha"],
            ),
        ]
        mock_orch = _make_orch_with_issues(issues)

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = api_client.get("/api/v1/issues")

        assert resp.status_code == 200
        data = resp.json()
        all_entries = [entry for col in data.values() for entry in col]
        epic_entries = [e for e in all_entries if e.get("identifier") == "EPIC-MULTI"]
        assert epic_entries
        assert "draft" in epic_entries[0]["labels"]
        assert "planning" in epic_entries[0]["labels"]
        assert "team:alpha" in epic_entries[0]["labels"]

    def test_empty_issues_returns_empty_dict(self, api_client):
        """When there are no issues, the API returns an empty dict."""
        mock_orch = _make_orch_with_issues([])

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = api_client.get("/api/v1/issues")

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict), "Response must be a dict"
        all_entries = [entry for col in data.values() for entry in col]
        assert all_entries == [], "No issues should be returned"


# ===========================================================================
# 7. Regression — filter expression is correct (not the old broken version)
# ===========================================================================

class TestRegressionFilterExpression:
    """Regression tests to prevent reverting to the old broken filter."""

    def test_old_broken_filter_not_present(self, render_flat_body):
        """The old broken filter 'i.issue_type !== epic' alone must NOT be the only filter.

        The old code was: filter(i => i.issue_type !== 'epic')
        This excluded ALL epics including draft ones.
        The new code must include the || (labels || []).includes('draft') exception.
        """
        # If the filter is only "i.issue_type !== 'epic'" with NO draft exception
        old_filter_pattern = re.search(
            r"filter\(\s*i\s*=>\s*i\.issue_type\s*!==\s*['\"]epic['\"]\s*\)",
            render_flat_body,
        )
        # The old filter (without any 'draft' OR clause) must NOT exist alone
        # Either no match (good — new filter), or there's also a draft clause
        if old_filter_pattern:
            # If old filter exists, it must be accompanied by draft handling elsewhere
            # This would be a bug regression
            pytest.fail(
                "Old broken filter found: filter(i => i.issue_type !== 'epic') "
                "— this excludes ALL epics including draft ones. "
                "The filter must include the || (i.labels || []).includes('draft') exception."
            )

    def test_filter_allows_non_epic_issues_through(self, render_flat_body):
        """The filter must still allow all non-epic issue types (task, bug, feature) through."""
        # The filter condition is: i.issue_type !== 'epic' || ...
        # For non-epics, the first clause (true) short-circuits → included ✓
        assert re.search(
            r"i\.issue_type\s*!==\s*['\"]epic['\"]",
            render_flat_body,
        ), "Filter must use issue_type !== 'epic' as the base condition for non-epics"

    def test_filter_or_clause_provides_draft_exception(self, render_flat_body):
        """The filter must have an OR clause to include draft epics."""
        assert re.search(
            r"issue_type.*!==.*epic.*\|\|.*draft",
            render_flat_body,
            re.DOTALL,
        ), (
            "Filter must include || clause for draft epics. "
            "Expected: i.issue_type !== 'epic' || (i.labels || []).includes('draft')"
        )


# ===========================================================================
# 8. Integration — API response shape supports frontend draft epic detection
# ===========================================================================

class TestApiResponseSupportsFrontendFilter:
    """Verify that the API response provides everything the frontend filter needs."""

    def test_draft_epic_in_api_has_both_issue_type_and_labels(self, api_client):
        """A draft epic response entry must have issue_type='epic' AND labels=['draft'].

        Both fields are required for the frontend filter:
        i.issue_type !== 'epic' || (i.labels || []).includes('draft')
        """
        issues = [
            _make_issue(
                id="e1", identifier="EPIC-D1", issue_type="epic", labels=["draft"]
            ),
        ]
        mock_orch = _make_orch_with_issues(issues)

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = api_client.get("/api/v1/issues")

        assert resp.status_code == 200
        data = resp.json()
        all_entries = [entry for col in data.values() for entry in col]
        epic = next((e for e in all_entries if e.get("identifier") == "EPIC-D1"), None)
        assert epic is not None, "Draft epic must appear in API response"
        assert epic["issue_type"] == "epic", "Draft epic must have issue_type='epic'"
        assert "draft" in epic["labels"], "Draft epic must have 'draft' in labels"

    def test_plain_epic_in_api_has_issue_type_epic_no_draft_label(self, api_client):
        """A plain epic must have issue_type='epic' but NOT 'draft' in labels.

        Frontend filter:  i.issue_type !== 'epic' || includes('draft')
        For plain epic:   false || false → excluded from flat view ✓
        """
        issues = [
            _make_issue(id="e2", identifier="EPIC-P1", issue_type="epic", labels=[]),
        ]
        mock_orch = _make_orch_with_issues(issues)

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = api_client.get("/api/v1/issues")

        assert resp.status_code == 200
        data = resp.json()
        all_entries = [entry for col in data.values() for entry in col]
        epic = next((e for e in all_entries if e.get("identifier") == "EPIC-P1"), None)
        assert epic is not None
        assert epic["issue_type"] == "epic"
        assert "draft" not in epic["labels"]

    def test_task_in_api_has_non_epic_issue_type(self, api_client):
        """A task must have issue_type='task' so frontend filter passes it through.

        Frontend filter:  i.issue_type !== 'epic' || includes('draft')
        For task:         true || <anything> → included ✓
        """
        issues = [
            _make_issue(id="t1", identifier="TASK-1", issue_type="task", labels=[]),
        ]
        mock_orch = _make_orch_with_issues(issues)

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = api_client.get("/api/v1/issues")

        assert resp.status_code == 200
        data = resp.json()
        all_entries = [entry for col in data.values() for entry in col]
        task = next((e for e in all_entries if e.get("identifier") == "TASK-1"), None)
        assert task is not None
        assert task["issue_type"] == "task"
        # With issue_type='task', the filter's first clause is true → task always shown

    def test_mixed_issues_all_have_required_fields(self, api_client):
        """Mix of epics, tasks, bugs, draft epics — all must have labels and issue_type."""
        issues = [
            _make_issue(id="e1", identifier="E-1", issue_type="epic", labels=["draft"]),
            _make_issue(id="e2", identifier="E-2", issue_type="epic", labels=[]),
            _make_issue(id="t1", identifier="T-1", issue_type="task", labels=[]),
            _make_issue(id="b1", identifier="B-1", issue_type="bug", labels=["urgent"]),
            _make_issue(id="f1", identifier="F-1", issue_type="feature", labels=[]),
        ]
        mock_orch = _make_orch_with_issues(issues)

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = api_client.get("/api/v1/issues")

        assert resp.status_code == 200
        data = resp.json()
        all_entries = [entry for col in data.values() for entry in col]
        assert len(all_entries) == 5, f"Expected 5 issues, got {len(all_entries)}"
        for entry in all_entries:
            assert "issue_type" in entry
            assert "labels" in entry
            assert isinstance(entry["labels"], list)
