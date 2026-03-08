"""Tests for draft epic kanban visibility in swimlane view.

Draft epics (issue_type === 'epic' with 'draft' in labels) should:
- NOT appear as swimlane headers in renderSwimlaneView()
- Appear as regular cards in the Unassigned/orphans swimlane
- Show the 'Draft Epic' badge via createCard()
- Be included in getCardsInColumn() results (not filtered out)
- Be included in orphan swimlane results in getCardsInColumn()

Regular (non-draft) epics should:
- Still appear as swimlane headers
- Still be excluded from card results

See issue: oompah-7mb
"""

import os
import re

import pytest


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


@pytest.fixture(scope="module")
def html():
    return _load_dashboard_html()


@pytest.fixture(scope="module")
def script(html):
    return _extract_script(html)


# ---------------------------------------------------------------------------
# renderSwimlaneView — epic collection filter
# ---------------------------------------------------------------------------

class TestRenderSwimlaneViewEpicFilter:
    """Verify that renderSwimlaneView() excludes draft epics from swimlane headers."""

    def _get_render_body(self, script: str) -> str:
        match = re.search(
            r"function renderSwimlaneView\(.*?\)\s*\{(.*)",
            script,
            re.DOTALL,
        )
        assert match, "Could not find renderSwimlaneView function"
        return match.group(1)

    def test_epics_filter_excludes_draft_label(self, script):
        """The epics array in renderSwimlaneView must exclude epics with the 'draft' label."""
        body = self._get_render_body(script)
        # Find the line that builds the epics array
        epics_line_match = re.search(
            r"(?:const|let|var)\s+epics\s*=\s*allIssuesFlat\.filter\(.*?\);",
            body,
            re.DOTALL,
        )
        assert epics_line_match, "Could not find 'epics = allIssuesFlat.filter(...)' assignment"
        epics_line = epics_line_match.group(0)
        # Must exclude draft epics
        assert "draft" in epics_line, \
            "epics filter must exclude draft epics (check for 'draft' label)"

    def test_epics_filter_still_requires_epic_type(self, script):
        """The epics array filter must still require issue_type === 'epic'."""
        body = self._get_render_body(script)
        epics_line_match = re.search(
            r"(?:const|let|var)\s+epics\s*=\s*allIssuesFlat\.filter\(.*?\);",
            body,
            re.DOTALL,
        )
        assert epics_line_match, "Could not find 'epics = allIssuesFlat.filter(...)' assignment"
        epics_line = epics_line_match.group(0)
        assert "issue_type" in epics_line, \
            "epics filter must still check issue_type"
        assert "epic" in epics_line, \
            "epics filter must still check for 'epic' type"

    def test_epics_filter_uses_negation_for_draft(self, script):
        """The epics filter must negate the draft condition (exclude items WITH draft label)."""
        body = self._get_render_body(script)
        epics_line_match = re.search(
            r"(?:const|let|var)\s+epics\s*=\s*allIssuesFlat\.filter\(.*?\);",
            body,
            re.DOTALL,
        )
        assert epics_line_match
        epics_line = epics_line_match.group(0)
        # Should use negation (!) to exclude draft epics
        assert "!" in epics_line, \
            "epics filter must use negation (!) to exclude draft epics from headers"

    def test_epics_filter_handles_missing_labels(self, script):
        """The epics filter must safely handle issues with no labels array."""
        body = self._get_render_body(script)
        epics_line_match = re.search(
            r"(?:const|let|var)\s+epics\s*=\s*allIssuesFlat\.filter\(.*?\);",
            body,
            re.DOTALL,
        )
        assert epics_line_match
        epics_line = epics_line_match.group(0)
        assert "|| []" in epics_line or "||[]" in epics_line, \
            "epics filter must use '|| []' to safely handle missing labels"


# ---------------------------------------------------------------------------
# renderSwimlaneView — orphans filter
# ---------------------------------------------------------------------------

class TestRenderSwimlaneViewOrphansFilter:
    """Verify that the orphans filter in renderSwimlaneView() includes draft epics."""

    def _get_render_body(self, script: str) -> str:
        match = re.search(
            r"function renderSwimlaneView\(.*?\)\s*\{(.*)",
            script,
            re.DOTALL,
        )
        assert match, "Could not find renderSwimlaneView function"
        return match.group(1)

    def test_orphans_filter_includes_draft_epics(self, script):
        """Orphans filter must allow draft epics (issue_type === 'epic' with 'draft' label)."""
        body = self._get_render_body(script)
        orphans_line_match = re.search(
            r"(?:const|let|var)\s+orphans\s*=\s*allIssuesFlat\.filter\(.*?\);",
            body,
            re.DOTALL,
        )
        assert orphans_line_match, "Could not find 'orphans = allIssuesFlat.filter(...)' assignment"
        orphans_line = orphans_line_match.group(0)
        assert "draft" in orphans_line, \
            "orphans filter must include draft epics (check for 'draft' label)"

    def test_orphans_filter_not_simple_epic_exclusion(self, script):
        """Orphans filter must NOT be a simple 'issue_type !== epic' — it needs draft exception."""
        body = self._get_render_body(script)
        orphans_line_match = re.search(
            r"(?:const|let|var)\s+orphans\s*=\s*allIssuesFlat\.filter\(.*?\);",
            body,
            re.DOTALL,
        )
        assert orphans_line_match
        orphans_line = orphans_line_match.group(0)
        # Must NOT be the simple pattern that just excludes all epics
        # (i.e. must have more than just !== 'epic' check)
        assert "draft" in orphans_line, \
            "Simple '!== epic' filter would miss draft epics — 'draft' must be mentioned"

    def test_orphans_filter_handles_missing_labels(self, script):
        """Orphans filter must safely handle issues without labels."""
        body = self._get_render_body(script)
        orphans_line_match = re.search(
            r"(?:const|let|var)\s+orphans\s*=\s*allIssuesFlat\.filter\(.*?\);",
            body,
            re.DOTALL,
        )
        assert orphans_line_match
        orphans_line = orphans_line_match.group(0)
        assert "|| []" in orphans_line or "||[]" in orphans_line, \
            "orphans filter must use '|| []' to safely handle missing labels"

    def test_orphans_filter_still_excludes_parent_with_known_epic(self, script):
        """Orphans filter must still exclude issues whose parent is a non-draft epic."""
        body = self._get_render_body(script)
        orphans_line_match = re.search(
            r"(?:const|let|var)\s+orphans\s*=\s*allIssuesFlat\.filter\(.*?\);",
            body,
            re.DOTALL,
        )
        assert orphans_line_match
        orphans_line = orphans_line_match.group(0)
        # Must still check epicIds to filter out children of known epics
        assert "epicIds" in orphans_line, \
            "orphans filter must use epicIds to exclude children of non-draft epics"
        assert "parent_id" in orphans_line, \
            "orphans filter must check parent_id"


# ---------------------------------------------------------------------------
# getCardsInColumn — draft epic inclusion
# ---------------------------------------------------------------------------

class TestGetCardsInColumnDraftEpics:
    """Verify that getCardsInColumn() includes draft epics."""

    def _get_function_body(self, script: str) -> str:
        match = re.search(
            r"function getCardsInColumn\(.*?\)\s*\{(.*?)\n\}",
            script,
            re.DOTALL,
        )
        assert match, "Could not find getCardsInColumn function"
        return match.group(1)

    def test_base_filter_allows_draft_epics(self, script):
        """The base issues filter in getCardsInColumn must allow draft epics through."""
        body = self._get_function_body(script)
        # Find the base filter line
        filter_match = re.search(
            r"(?:const|let|var)\s+issues\s*=.*?\.filter\(.*?\);",
            body,
            re.DOTALL,
        )
        assert filter_match, "Could not find 'issues = ...' filter in getCardsInColumn"
        filter_line = filter_match.group(0)
        assert "draft" in filter_line, \
            "Base issues filter must allow draft epics through"

    def test_base_filter_still_excludes_non_draft_epics(self, script):
        """Base issues filter must exclude regular (non-draft) epics."""
        body = self._get_function_body(script)
        filter_match = re.search(
            r"(?:const|let|var)\s+issues\s*=.*?\.filter\(.*?\);",
            body,
            re.DOTALL,
        )
        assert filter_match
        filter_line = filter_match.group(0)
        # Must have the epic type check
        assert "issue_type" in filter_line, \
            "Base filter must still check issue_type"
        assert "epic" in filter_line, \
            "Base filter must still reference 'epic'"

    def test_base_filter_handles_missing_labels(self, script):
        """Base filter must safely handle missing labels."""
        body = self._get_function_body(script)
        filter_match = re.search(
            r"(?:const|let|var)\s+issues\s*=.*?\.filter\(.*?\);",
            body,
            re.DOTALL,
        )
        assert filter_match
        filter_line = filter_match.group(0)
        assert "|| []" in filter_line or "||[]" in filter_line, \
            "Base filter must handle missing labels with '|| []' pattern"

    def test_orphans_branch_builds_epicIds_from_non_draft_epics(self, script):
        """In the _orphans branch, epicIds must only contain non-draft epic IDs."""
        body = self._get_function_body(script)
        # Find the _orphans branch
        orphans_branch_match = re.search(
            r"_orphans.*?(?=} else|return issues\.filter)",
            body,
            re.DOTALL,
        )
        assert orphans_branch_match, "Could not find _orphans branch in getCardsInColumn"
        orphans_branch = orphans_branch_match.group(0)
        # epicIds should be built from non-draft epics
        assert "draft" in orphans_branch, \
            "_orphans branch epicIds must exclude draft epics"

    def test_orphans_branch_negates_draft_in_epicIds_set(self, script):
        """The epicIds set in _orphans must filter OUT draft epics (negation)."""
        body = self._get_function_body(script)
        orphans_branch_match = re.search(
            r"epicId === '_orphans'.*?(?=} else \{|return issues\.filter)",
            body,
            re.DOTALL,
        )
        assert orphans_branch_match, "Could not find _orphans branch"
        orphans_branch = orphans_branch_match.group(0)
        # Should use negation for draft check
        assert "!" in orphans_branch, \
            "_orphans epicIds must negate draft condition to exclude draft epics from the set"


# ---------------------------------------------------------------------------
# Integration-style checks: filters are consistent
# ---------------------------------------------------------------------------

class TestDraftEpicFilterConsistency:
    """Verify that draft epic handling is consistent across rendering functions."""

    def test_renderSwimlaneView_and_getCardsInColumn_both_use_draft_check(self, script):
        """Both renderSwimlaneView and getCardsInColumn must reference 'draft' label."""
        # renderSwimlaneView epics filter
        render_epics_match = re.search(
            r"function renderSwimlaneView.*?(?:const|let|var)\s+epics\s*=.*?;",
            script,
            re.DOTALL,
        )
        assert render_epics_match
        assert "draft" in render_epics_match.group(0)

        # getCardsInColumn base filter
        get_cards_match = re.search(
            r"function getCardsInColumn.*?(?:const|let|var)\s+issues\s*=.*?;",
            script,
            re.DOTALL,
        )
        assert get_cards_match
        assert "draft" in get_cards_match.group(0)

    def test_both_orphan_filters_handle_draft_epics(self, script):
        """Both the orphans in renderSwimlaneView and _orphans in getCardsInColumn must handle draft."""
        # renderSwimlaneView orphans
        render_match = re.search(
            r"function renderSwimlaneView.*?(?:const|let|var)\s+orphans\s*=.*?;",
            script,
            re.DOTALL,
        )
        assert render_match
        assert "draft" in render_match.group(0)

        # getCardsInColumn _orphans branch
        func_match = re.search(
            r"function getCardsInColumn\(.*?\)\s*\{(.*?)\n\}",
            script,
            re.DOTALL,
        )
        assert func_match
        body = func_match.group(1)
        orphans_branch = re.search(r"_orphans.*?return issues\.filter", body, re.DOTALL)
        assert orphans_branch
        assert "draft" in orphans_branch.group(0)

    def test_draft_epic_badge_shown_in_createCard(self, script):
        """createCard() must have draftEpicBadgeHtml logic (the badge for draft epic cards)."""
        assert "draftEpicBadgeHtml" in script, \
            "createCard must define draftEpicBadgeHtml for draft epic badge display"
        assert "Draft Epic" in script, \
            "createCard must include 'Draft Epic' text in the badge"

    def test_orphans_swimlane_rendered_in_swimlane_view(self, script):
        """renderSwimlaneView must render the Unassigned swimlane for orphans."""
        render_match = re.search(
            r"function renderSwimlaneView\(.*?\)\s*\{(.*)",
            script,
            re.DOTALL,
        )
        assert render_match
        body = render_match.group(1)
        assert "Unassigned" in body, \
            "renderSwimlaneView must render an 'Unassigned' swimlane for orphans/draft epics"
        assert "orphans" in body, \
            "renderSwimlaneView must use the orphans array for the Unassigned swimlane"
