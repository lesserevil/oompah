"""Tests for draft epic kanban visibility in swimlane view.

Draft epics (issue_type === 'epic' with 'draft' in labels) should:
- Appear as swimlane headers in renderSwimlaneView() when they have visible child work
- Keep the Draft badge and Finalize action in the swimlane header
- Appear as regular cards only when they are not rendered as swimlane parents
- Show the 'Draft Epic' badge via createCard()
- Be included in getCardsInColumn() results (not filtered out)
- Be excluded from orphan swimlane results when rendered as swimlane headers

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
    """Verify that renderSwimlaneView() includes draft epics as swimlane headers."""

    def _get_render_body(self, script: str) -> str:
        match = re.search(
            r"function renderSwimlaneView\(.*?\)\s*\{(.*)",
            script,
            re.DOTALL,
        )
        assert match, "Could not find renderSwimlaneView function"
        return match.group(1)

    def test_epics_filter_does_not_exclude_draft_label(self, script):
        """The epics array in renderSwimlaneView must not filter out draft epics."""
        body = self._get_render_body(script)
        epics_line_match = re.search(
            r"(?:const|let|var)\s+allEpics\s*=\s*allIssuesFlat\.filter\(.*?\);",
            body,
            re.DOTALL,
        )
        assert epics_line_match, "Could not find 'epics = allIssuesFlat.filter(...)' assignment"
        epics_line = epics_line_match.group(0)
        assert "draft" not in epics_line, (
            "allEpics must include draft epics so draft status does not break hierarchy"
        )

    def test_epics_filter_uses_swimlane_parent_check(self, script):
        """The epics array filter must use isSwimlaneParent to identify parent issues."""
        body = self._get_render_body(script)
        epics_line_match = re.search(
            r"(?:const|let|var)\s+allEpics\s*=\s*allIssuesFlat\.filter\(.*?\);",
            body,
            re.DOTALL,
        )
        assert epics_line_match, "Could not find 'epics = allIssuesFlat.filter(...)' assignment"
        epics_line = epics_line_match.group(0)
        assert "isSwimlaneParent" in epics_line, \
            "epics filter must use isSwimlaneParent to identify parent issues"

    def test_epics_filter_has_no_draft_negation(self, script):
        """The epics filter must not negate the draft condition."""
        body = self._get_render_body(script)
        epics_line_match = re.search(
            r"(?:const|let|var)\s+allEpics\s*=\s*allIssuesFlat\.filter\(.*?\);",
            body,
            re.DOTALL,
        )
        assert epics_line_match
        epics_line = epics_line_match.group(0)
        assert "!" not in epics_line, (
            "allEpics must not use negation to exclude draft epics from headers"
        )

    def test_rendered_epics_are_filtered_by_visible_counts(self, script):
        """Draft and non-draft epics only render as lanes when they have visible child work."""
        body = self._get_render_body(script)
        assert re.search(
            r"(?:const|let|var)\s+epics\s*=\s*allEpics\.filter\(epicHasVisibleCounts\)",
            body,
        ), "rendered epics must be allEpics filtered by epicHasVisibleCounts"


# ---------------------------------------------------------------------------
# renderSwimlaneView — orphans filter
# ---------------------------------------------------------------------------

class TestRenderSwimlaneViewOrphansFilter:
    """Verify that the orphans filter does not swallow valid draft epic hierarchies."""

    def _get_render_body(self, script: str) -> str:
        match = re.search(
            r"function renderSwimlaneView\(.*?\)\s*\{(.*)",
            script,
            re.DOTALL,
        )
        assert match, "Could not find renderSwimlaneView function"
        return match.group(1)

    def test_isSwimlaneParent_helper_exists(self, script):
        """The isSwimlaneParent helper must exist and check both epic type and children_counts."""
        assert "function isSwimlaneParent" in script, \
            "isSwimlaneParent helper function must be defined"
        func_match = re.search(
            r"function isSwimlaneParent\(.*?\)\s*\{(.*?)\}",
            script,
            re.DOTALL,
        )
        assert func_match, "Could not find isSwimlaneParent function body"
        body = func_match.group(1)
        assert "epic" in body, "isSwimlaneParent must check for 'epic' type"
        assert "children_counts" in body, "isSwimlaneParent must check children_counts"

    def test_orphans_filter_uses_work_card_helper(self, script):
        """Orphans filter must delegate draft-card eligibility to shouldShowIssueAsWorkCard."""
        body = self._get_render_body(script)
        orphans_line_match = re.search(
            r"(?:const|let|var)\s+orphans\s*=\s*allIssuesFlat\.filter\(.*?\);",
            body,
            re.DOTALL,
        )
        assert orphans_line_match, "Could not find 'orphans = allIssuesFlat.filter(...)' assignment"
        orphans_line = orphans_line_match.group(0)
        assert "shouldShowIssueAsWorkCard" in orphans_line, (
            "orphans filter must use the work-card helper for draft-card eligibility"
        )

    def test_orphans_filter_excludes_rendered_swimlane_parents(self, script):
        """Draft epics rendered as swimlane parents must not also appear as Unassigned cards."""
        body = self._get_render_body(script)
        orphans_line_match = re.search(
            r"(?:const|let|var)\s+orphans\s*=\s*allIssuesFlat\.filter\(.*?\);",
            body,
            re.DOTALL,
        )
        assert orphans_line_match
        orphans_line = orphans_line_match.group(0)
        assert "renderedEpicKeys" in orphans_line, (
            "orphans filter must exclude epics that are already rendered as swimlanes"
        )

    def test_orphans_filter_not_simple_epic_exclusion(self, script):
        """Orphans filter must not be a simple issue_type exclusion."""
        body = self._get_render_body(script)
        orphans_line_match = re.search(
            r"(?:const|let|var)\s+orphans\s*=\s*allIssuesFlat\.filter\(.*?\);",
            body,
            re.DOTALL,
        )
        assert orphans_line_match
        orphans_line = orphans_line_match.group(0)
        assert "issue_type !== 'epic'" not in orphans_line, (
            "orphans filter must be based on parent relationships, not epic type"
        )

    def test_orphans_filter_still_excludes_parent_with_known_epic(self, script):
        """Orphans filter must exclude issues whose parent is any known epic."""
        body = self._get_render_body(script)
        orphans_line_match = re.search(
            r"(?:const|let|var)\s+orphans\s*=\s*allIssuesFlat\.filter\(.*?\);",
            body,
            re.DOTALL,
        )
        assert orphans_line_match
        orphans_line = orphans_line_match.group(0)
        # Must still check the known-epic set to filter out children of
        # known epics. Keyed by the composite (project_id, id) key
        # `epicKeys` / `parentKeyOf` — bare ids collide across projects.
        assert "epicKeys" in orphans_line, \
            "orphans filter must use epicKeys to exclude children of known epics"
        assert "parent_id" in orphans_line or "parentKeyOf" in orphans_line, \
            "orphans filter must check the issue's parent"


# ---------------------------------------------------------------------------
# renderSwimlaneView — nested epic children
# ---------------------------------------------------------------------------

class TestRenderSwimlaneViewNestedEpics:
    """Verify nested epic relationships are visible in the by-epic view."""

    def _get_render_body(self, script: str) -> str:
        match = re.search(
            r"function renderSwimlaneView\(.*?\)\s*\{(.*)",
            script,
            re.DOTALL,
        )
        assert match, "Could not find renderSwimlaneView function"
        return match.group(1)

    def test_swimlane_children_do_not_filter_out_epic_children(self, script):
        """Immediate child epics should render as cards in their parent epic lane."""
        body = self._get_render_body(script)
        children_line_match = re.search(
            r"(?:const|let|var)\s+children\s*=\s*allIssuesFlat\.filter\(.*?\);",
            body,
            re.DOTALL,
        )
        assert children_line_match, "Could not find children filter in renderSwimlaneView"
        children_line = children_line_match.group(0)
        assert "parentKeyOf(i) === ek" in children_line
        assert "!isSwimlaneParent" not in children_line, (
            "nested epic children must not be filtered out of their parent lane"
        )

    def test_specific_swimlane_cards_are_scoped_by_parent_only(self, script):
        """Column drag in a swimlane should operate on all visible immediate children."""
        func_match = re.search(
            r"function getCardsInColumn\(.*?\)\s*\{(.*?)\n\}",
            script,
            re.DOTALL,
        )
        assert func_match, "Could not find getCardsInColumn function"
        body = func_match.group(1)
        specific_branch = re.search(
            r"// Specific epic swimlane.*?return issues\.filter\(.*?\);",
            body,
            re.DOTALL,
        )
        assert specific_branch, "Could not find specific swimlane branch"
        branch = specific_branch.group(0)
        assert "parentKeyOf(i) === epicId" in branch
        assert "shouldShowIssueAsWorkCard" not in branch, (
            "specific swimlanes must include immediate epic children, not only flat work cards"
        )


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
        assert "shouldShowIssueAsWorkCard" in filter_line, \
            "Base issues filter must delegate draft and merge-flow epic handling"

    def test_base_filter_uses_work_card_helper(self, script):
        """Base issues filter must use the centralized work-card helper."""
        body = self._get_function_body(script)
        filter_match = re.search(
            r"(?:const|let|var)\s+issues\s*=.*?\.filter\(.*?\);",
            body,
            re.DOTALL,
        )
        assert filter_match
        filter_line = filter_match.group(0)
        assert "shouldShowIssueAsWorkCard" in filter_line, \
            "Base filter must use shouldShowIssueAsWorkCard"

    def test_base_filter_handles_missing_labels(self, script):
        """The delegated draft-label helper must safely handle missing labels."""
        helper_match = re.search(
            r"function hasDraftLabel\(issue\)\s*\{(.*?)\n\}",
            script,
            re.DOTALL,
        )
        assert helper_match, "Could not find hasDraftLabel helper"
        helper_line = helper_match.group(0)
        assert "|| []" in helper_line or "||[]" in helper_line, \
            "Draft-label helper must handle missing labels with '|| []' pattern"

    def test_orphans_branch_builds_epicIds_from_all_epics(self, script):
        """In the _orphans branch, epicKeys must include draft and non-draft epic IDs."""
        body = self._get_function_body(script)
        # Find the _orphans branch
        orphans_branch_match = re.search(
            r"_orphans.*?(?=} else|return issues\.filter)",
            body,
            re.DOTALL,
        )
        assert orphans_branch_match, "Could not find _orphans branch in getCardsInColumn"
        orphans_branch = orphans_branch_match.group(0)
        all_epics_match = re.search(
            r"(?:const|let|var)\s+allEpics\s*=\s*allIssuesFlat\.filter\(.*?\);",
            orphans_branch,
            re.DOTALL,
        )
        assert all_epics_match, "Could not find allEpics assignment in _orphans branch"
        all_epics_line = all_epics_match.group(0)
        assert "isSwimlaneParent" in all_epics_line
        assert "draft" not in all_epics_line, (
            "_orphans epicKeys must not exclude draft epics"
        )

    def test_orphans_branch_excludes_rendered_epics(self, script):
        """The _orphans branch must exclude epics rendered as swimlane headers."""
        body = self._get_function_body(script)
        orphans_branch_match = re.search(
            r"epicId === '_orphans'.*?(?=} else \{|return issues\.filter)",
            body,
            re.DOTALL,
        )
        assert orphans_branch_match, "Could not find _orphans branch"
        orphans_branch = orphans_branch_match.group(0)
        assert "renderedEpicKeys" in orphans_branch, (
            "_orphans must exclude epics already rendered as swimlane headers"
        )


# ---------------------------------------------------------------------------
# Integration-style checks: filters are consistent
# ---------------------------------------------------------------------------

class TestDraftEpicFilterConsistency:
    """Verify that draft epic handling is consistent across rendering functions."""

    def test_renderSwimlaneView_and_getCardsInColumn_include_draft_epic_parents(self, script):
        """Both render paths must build epic keys without filtering out draft epics."""
        # renderSwimlaneView epics filter
        render_epics_match = re.search(
            r"(?:const|let|var)\s+allEpics\s*=\s*allIssuesFlat\.filter\(.*?\);",
            self._render_body(script),
            re.DOTALL,
        )
        assert render_epics_match
        assert "draft" not in render_epics_match.group(0)

        # getCardsInColumn orphan branch
        get_cards_match = re.search(
            r"function getCardsInColumn\(.*?\)\s*\{(.*?)\n\}",
            script,
            re.DOTALL,
        )
        assert get_cards_match
        get_cards_body = get_cards_match.group(1)
        orphans_branch = re.search(
            r"epicId === '_orphans'.*?(?=} else \{|return issues\.filter)",
            get_cards_body,
            re.DOTALL,
        )
        assert orphans_branch
        all_epics_match = re.search(
            r"(?:const|let|var)\s+allEpics\s*=\s*allIssuesFlat\.filter\(.*?\);",
            orphans_branch.group(0),
            re.DOTALL,
        )
        assert all_epics_match
        assert "draft" not in all_epics_match.group(0)

    def _render_body(self, script: str) -> str:
        match = re.search(
            r"function renderSwimlaneView\(.*?\)\s*\{(.*)",
            script,
            re.DOTALL,
        )
        assert match
        return match.group(1)

    def test_both_orphan_filters_exclude_rendered_epics(self, script):
        """Both the orphans in renderSwimlaneView and _orphans in getCardsInColumn must avoid duplicate lane/card rendering."""
        # renderSwimlaneView orphans
        render_match = re.search(
            r"function renderSwimlaneView.*?(?:const|let|var)\s+orphans\s*=.*?;",
            script,
            re.DOTALL,
        )
        assert render_match
        assert "renderedEpicKeys" in render_match.group(0)

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
        assert "renderedEpicKeys" in orphans_branch.group(0)

    def test_draft_epic_badge_shown_in_createCard(self, script):
        """createCard() must have draftEpicBadgeHtml logic (the badge for draft epic cards)."""
        assert "draftEpicBadgeHtml" in script, \
            "createCard must define draftEpicBadgeHtml for draft epic badge display"
        assert "Draft Epic" in script, \
            "createCard must include 'Draft Epic' text in the badge"

    def test_orphans_swimlane_rendered_in_swimlane_view(self, script):
        """renderSwimlaneView must render the Unassigned swimlane for true orphans."""
        render_match = re.search(
            r"function renderSwimlaneView\(.*?\)\s*\{(.*)",
            script,
            re.DOTALL,
        )
        assert render_match
        body = render_match.group(1)
        assert "Unassigned" in body, \
            "renderSwimlaneView must render an 'Unassigned' swimlane for true orphans"
        assert "orphans" in body, \
            "renderSwimlaneView must use the orphans array for the Unassigned swimlane"


# ---------------------------------------------------------------------------
# renderSwimlaneView — hide "0 / 0 / 0 / 0" epics
# ---------------------------------------------------------------------------

class TestRenderSwimlaneViewHidesEmptyEpics:
    """Epics whose header counts are 0/0/0/0 (no Backlog/Open/In Progress/
    Done children) must not render in the by-epic view."""

    def _render_body(self, script: str) -> str:
        match = re.search(r"function renderSwimlaneView\(.*?\)\s*\{(.*)", script, re.DOTALL)
        assert match
        return match.group(1)

    def test_helper_sums_displayed_counts(self, script: str):
        assert "function epicHasVisibleCounts" in script
        m = re.search(r"function epicHasVisibleCounts\(.*?\)\s*\{(.*?)\n\}", script, re.DOTALL)
        assert m, "epicHasVisibleCounts body not found"
        body = m.group(1)
        for key in ("Backlog", "Open", "In Progress", "Done"):
            assert f"'{key}'" in body, f"epicHasVisibleCounts must consider {key}"
        assert "> 0" in body, "must keep epics with a positive count sum"

    def test_rendered_epics_filtered_by_visible_counts(self, script: str):
        body = self._render_body(script)
        m = re.search(r"(?:const|let|var)\s+epics\s*=\s*allEpics\.filter\(([^)]*)\)", body)
        assert m, "rendered epics must be allEpics.filter(epicHasVisibleCounts)"
        assert "epicHasVisibleCounts" in m.group(1)

    def test_epickeys_built_from_all_epics(self, script: str):
        # epicKeys must include ALL epics (not the visible-filtered list) so a
        # hidden epic's children aren't mis-classified as orphans.
        body = self._render_body(script)
        m = re.search(r"(?:const|let|var)\s+epicKeys\s*=\s*new Set\(allEpics\.map", body)
        assert m, "epicKeys must be built from allEpics (all epics), not the filtered list"
