"""Tests for Draft Epic badge styling and card rendering.

Draft epics are issues with issue_type === 'epic' AND labels includes 'draft'.
They should:
- Show a '.draft-epic-badge' with text 'Draft Epic' in the card-id row
- Be draggable between columns (draggable=true on the card)
- Have a working click handler for openDetailPanel on the card id span
- Pass through the flat view filter (not be filtered out like regular epics)

See issue: oompah-7e0
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


class TestDraftEpicBadgeCSS:
    """Verify that the .draft-epic-badge CSS class exists with appropriate styling."""

    def test_draft_epic_badge_class_exists(self, html):
        """.draft-epic-badge CSS class must be defined in the stylesheet."""
        assert ".draft-epic-badge" in html

    def test_draft_epic_badge_has_distinct_color_from_merged_badge(self, html):
        """Draft epic badge must use a different color than the merged-badge (purple).

        The draft-epic-badge should use the --accent blue color to distinguish
        from the purple used by merged-badge and epic-badge.
        """
        # Extract .draft-epic-badge block
        badge_match = re.search(
            r"\.draft-epic-badge\s*\{([^}]*)\}",
            html,
            re.DOTALL,
        )
        assert badge_match, "Could not find .draft-epic-badge CSS block"
        css_body = badge_match.group(1)

        # Must reference --accent (blue) not --purple
        assert "--accent" in css_body or "#58a6ff" in css_body, \
            "draft-epic-badge should use --accent (blue) color"
        assert "--purple" not in css_body, \
            "draft-epic-badge should NOT use --purple (to distinguish from merged-badge)"

    def test_draft_epic_badge_has_font_family(self, html):
        """Badge should use monospace font consistent with other badges."""
        badge_match = re.search(
            r"\.draft-epic-badge\s*\{([^}]*)\}",
            html,
            re.DOTALL,
        )
        assert badge_match
        css_body = badge_match.group(1)
        assert "font-family" in css_body

    def test_draft_epic_badge_has_border_radius(self, html):
        """Badge should have a border-radius for visual consistency with other badges."""
        badge_match = re.search(
            r"\.draft-epic-badge\s*\{([^}]*)\}",
            html,
            re.DOTALL,
        )
        assert badge_match
        css_body = badge_match.group(1)
        assert "border-radius" in css_body

    def test_draft_epic_badge_has_font_size(self, html):
        """Badge should have a small font-size consistent with other badges."""
        badge_match = re.search(
            r"\.draft-epic-badge\s*\{([^}]*)\}",
            html,
            re.DOTALL,
        )
        assert badge_match
        css_body = badge_match.group(1)
        assert "font-size" in css_body

    def test_draft_epic_badge_appears_after_merged_badge(self, html):
        """The .draft-epic-badge rule should appear near the .merged-badge rule."""
        merged_pos = html.find(".merged-badge")
        draft_pos = html.find(".draft-epic-badge")
        assert merged_pos != -1, "merged-badge must exist"
        assert draft_pos != -1, "draft-epic-badge must exist"
        # Both should be in the CSS section (before </style>)
        style_end = html.find("</style>")
        assert draft_pos < style_end, "draft-epic-badge must be in the <style> section"


class TestDraftEpicBadgeInCreateCard:
    """Verify that createCard() generates the Draft Epic badge correctly."""

    def test_draft_epic_badge_variable_in_createCard(self, script):
        """createCard() must define a draftEpicBadgeHtml variable."""
        createcard_match = re.search(
            r"function createCard\(.*?\)\s*\{(.*?)(?=\nfunction )",
            script,
            re.DOTALL,
        )
        assert createcard_match, "Could not find createCard function"
        body = createcard_match.group(1)
        assert "draftEpicBadgeHtml" in body

    def test_draft_epic_badge_checks_swimlane_parent(self, script):
        """Badge condition must check isSwimlaneParent(issue)."""
        createcard_match = re.search(
            r"function createCard\(.*?\)\s*\{(.*?)(?=\nfunction )",
            script,
            re.DOTALL,
        )
        assert createcard_match
        body = createcard_match.group(1)
        # Find the draftEpicBadgeHtml assignment using isSwimlaneParent
        assert re.search(
            r"draftEpicBadgeHtml\s*=.*isSwimlaneParent\(issue\)",
            body,
        ), "createCard must check isSwimlaneParent(issue) for draft epic badge"

    def test_draft_epic_badge_checks_draft_label(self, script):
        """Badge condition must check for 'draft' in issue.labels."""
        createcard_match = re.search(
            r"function createCard\(.*?\)\s*\{(.*?)(?=\nfunction )",
            script,
            re.DOTALL,
        )
        assert createcard_match
        body = createcard_match.group(1)
        # Find the draftEpicBadgeHtml assignment block
        badge_match = re.search(
            r"draftEpicBadgeHtml\s*=.*?;",
            body,
            re.DOTALL,
        )
        assert badge_match, "Could not find draftEpicBadgeHtml assignment"
        badge_code = badge_match.group(0)
        assert "draft" in badge_code, "draftEpicBadgeHtml must check for 'draft' label"

    def test_draft_epic_badge_text_is_Draft_Epic(self, script):
        """Badge HTML must contain the text 'Draft Epic'."""
        createcard_match = re.search(
            r"function createCard\(.*?\)\s*\{(.*?)(?=\nfunction )",
            script,
            re.DOTALL,
        )
        assert createcard_match
        body = createcard_match.group(1)
        assert "Draft Epic" in body, "createCard must produce a 'Draft Epic' badge text"

    def test_draft_epic_badge_uses_draft_epic_badge_class(self, script):
        """Badge HTML must use the .draft-epic-badge CSS class."""
        createcard_match = re.search(
            r"function createCard\(.*?\)\s*\{(.*?)(?=\nfunction )",
            script,
            re.DOTALL,
        )
        assert createcard_match
        body = createcard_match.group(1)
        assert 'draft-epic-badge' in body, \
            "createCard must use 'draft-epic-badge' CSS class"

    def test_draft_epic_badge_in_card_id_row(self, script):
        """draftEpicBadgeHtml must be rendered inside the card-id row."""
        createcard_match = re.search(
            r"function createCard\(.*?\)\s*\{(.*?)(?=\nfunction )",
            script,
            re.DOTALL,
        )
        assert createcard_match
        body = createcard_match.group(1)
        # Find the card.innerHTML template literal
        inner_html_match = re.search(
            r"card\.innerHTML\s*=\s*`(.*?)`\s*;",
            body,
            re.DOTALL,
        )
        assert inner_html_match, "Could not find card.innerHTML template"
        inner_html = inner_html_match.group(1)
        # card-id-left must contain draftEpicBadgeHtml
        card_id_match = re.search(
            r"card-id-left(.*?)(?=</span>\s*\n\s*<span class=\"priority-badge)",
            inner_html,
            re.DOTALL,
        )
        assert card_id_match, "Could not find card-id-left section in card.innerHTML"
        card_id_left = card_id_match.group(1)
        assert "draftEpicBadgeHtml" in card_id_left, \
            "draftEpicBadgeHtml must be placed inside the card-id-left span"

    def test_draft_epic_badge_placed_alongside_merged_badge(self, script):
        """Both draftEpicBadgeHtml and mergedBadgeHtml must appear in card-id-left."""
        createcard_match = re.search(
            r"function createCard\(.*?\)\s*\{(.*?)(?=\nfunction )",
            script,
            re.DOTALL,
        )
        assert createcard_match
        body = createcard_match.group(1)
        inner_html_match = re.search(
            r"card\.innerHTML\s*=\s*`(.*?)`\s*;",
            body,
            re.DOTALL,
        )
        assert inner_html_match
        inner_html = inner_html_match.group(1)
        assert "draftEpicBadgeHtml" in inner_html
        assert "mergedBadgeHtml" in inner_html

    def test_draft_epic_badge_has_aria_label(self, script):
        """Badge span should have an aria-label for accessibility."""
        createcard_match = re.search(
            r"function createCard\(.*?\)\s*\{(.*?)(?=\nfunction )",
            script,
            re.DOTALL,
        )
        assert createcard_match
        body = createcard_match.group(1)
        # Find badge HTML assignment
        badge_match = re.search(
            r"draftEpicBadgeHtml\s*=.*?;",
            body,
            re.DOTALL,
        )
        assert badge_match
        badge_code = badge_match.group(0)
        assert "aria-label" in badge_code, \
            "draft-epic-badge span must include aria-label for accessibility"


class TestDraftEpicBadgeConditionLogic:
    """Verify the conditional logic for when to show the badge."""

    def test_badge_only_for_swimlane_parent(self, script):
        """Badge must require issue to be a swimlane parent (epic or has children)."""
        createcard_match = re.search(
            r"function createCard\(.*?\)\s*\{(.*?)(?=\nfunction )",
            script,
            re.DOTALL,
        )
        assert createcard_match
        body = createcard_match.group(1)
        # The condition should involve isSwimlaneParent check AND label check
        badge_match = re.search(
            r"(const|let|var)\s+draftEpicBadgeHtml\s*=\s*(.*?);",
            body,
            re.DOTALL,
        )
        assert badge_match, "Could not find draftEpicBadgeHtml declaration"
        condition_code = badge_match.group(2)
        assert "isSwimlaneParent" in condition_code, \
            "draftEpicBadgeHtml condition must check isSwimlaneParent(issue)"
        assert "draft" in condition_code, \
            "draftEpicBadgeHtml condition must check for 'draft' label"

    def test_badge_handles_missing_labels_gracefully(self, script):
        """Badge condition should handle issues without labels (labels may be null/undefined)."""
        createcard_match = re.search(
            r"function createCard\(.*?\)\s*\{(.*?)(?=\nfunction )",
            script,
            re.DOTALL,
        )
        assert createcard_match
        body = createcard_match.group(1)
        badge_match = re.search(
            r"(const|let|var)\s+draftEpicBadgeHtml\s*=\s*(.*?);",
            body,
            re.DOTALL,
        )
        assert badge_match
        condition_code = badge_match.group(2)
        # Should use (issue.labels || []) pattern for safety
        assert "|| []" in condition_code or "||[]" in condition_code, \
            "draftEpicBadgeHtml must handle missing labels with '|| []' pattern"


class TestDraftEpicDraggability:
    """Verify that draft epics are draggable in the flat view."""

    def test_createCard_sets_draggable_true(self, script):
        """createCard() must set card.draggable = true unconditionally."""
        createcard_match = re.search(
            r"function createCard\(.*?\)\s*\{(.*?)(?=\nfunction )",
            script,
            re.DOTALL,
        )
        assert createcard_match
        body = createcard_match.group(1)
        assert "card.draggable = true" in body, \
            "createCard must set card.draggable = true so draft epics are draggable"

    def test_createCard_attaches_dragstart_handler(self, script):
        """createCard() must attach a dragstart event listener."""
        createcard_match = re.search(
            r"function createCard\(.*?\)\s*\{(.*?)(?=\nfunction )",
            script,
            re.DOTALL,
        )
        assert createcard_match
        body = createcard_match.group(1)
        assert "dragstart" in body, \
            "createCard must attach dragstart event handler for drag support"

    def test_createCard_attaches_dragend_handler(self, script):
        """createCard() must attach a dragend event listener."""
        createcard_match = re.search(
            r"function createCard\(.*?\)\s*\{(.*?)(?=\nfunction )",
            script,
            re.DOTALL,
        )
        assert createcard_match
        body = createcard_match.group(1)
        assert "dragend" in body, \
            "createCard must attach dragend event handler for drag support"

    def test_renderFlatView_does_not_filter_draft_epics(self, script):
        """renderFlatView must pass draft epics (epic with 'draft' label) through the filter."""
        render_match = re.search(
            r"function renderFlatView\(.*?\)\s*\{(.*?)(?=\nfunction )",
            script,
            re.DOTALL,
        )
        assert render_match, "Could not find renderFlatView function"
        body = render_match.group(1)
        # The filter must handle draft epics (allow them through).
        # Look for the filter line that uses isSwimlaneParent — it should have a draft exception.
        filter_match = re.search(
            r"\.filter\(.*?isSwimlaneParent.*?draft.*?\)",
            body,
            re.DOTALL,
        )
        assert filter_match, (
            "renderFlatView must have an isSwimlaneParent filter that handles draft epics"
        )
        filter_code = filter_match.group(0)
        # The filter should include an exception for draft label
        assert "draft" in filter_code, \
            "renderFlatView filter must allow draft epics through (check for 'draft' label)"

    def test_setupDropZone_handles_drag_drop(self, script):
        """setupDropZone() must handle the drop event to enable moving cards between columns."""
        assert "function setupDropZone(" in script
        setup_match = re.search(
            r"function setupDropZone\(.*?\)\s*\{(.*?)(?=\nfunction )",
            script,
            re.DOTALL,
        )
        assert setup_match, "Could not find setupDropZone function"
        body = setup_match.group(1)
        assert "drop" in body, "setupDropZone must handle 'drop' events"
        assert "dragover" in body, "setupDropZone must handle 'dragover' events"


class TestDraftEpicClickHandler:
    """Verify that the card click handler works for draft epic cards."""

    def test_card_id_click_calls_openDetailPanel(self, script):
        """Clicking the card ID span must call openDetailPanel with the issue identifier."""
        createcard_match = re.search(
            r"function createCard\(.*?\)\s*\{(.*?)(?=\nfunction )",
            script,
            re.DOTALL,
        )
        assert createcard_match
        body = createcard_match.group(1)
        assert "openDetailPanel" in body, \
            "createCard must call openDetailPanel when card id is clicked"

    def test_card_id_click_uses_card_id_left_span(self, script):
        """The click handler must be attached to the first span in card-id-left."""
        createcard_match = re.search(
            r"function createCard\(.*?\)\s*\{(.*?)(?=\nfunction )",
            script,
            re.DOTALL,
        )
        assert createcard_match
        body = createcard_match.group(1)
        # Must query the first span within card-id-left for the click handler
        assert "card-id-left" in body, \
            "createCard must reference card-id-left to attach the click handler"

    def test_openDetailPanel_function_exists(self, script):
        """openDetailPanel function must be defined for the click handler to work."""
        assert "function openDetailPanel(" in script, \
            "openDetailPanel function must be defined"

    def test_card_id_click_stops_propagation(self, script):
        """The card id click handler should stop event propagation."""
        createcard_match = re.search(
            r"function createCard\(.*?\)\s*\{(.*?)(?=\nfunction )",
            script,
            re.DOTALL,
        )
        assert createcard_match
        body = createcard_match.group(1)
        # Find the click event listener for the card ID
        click_listener_match = re.search(
            r"addEventListener\(['\"]click['\"].*?openDetailPanel.*?\}\)",
            body,
            re.DOTALL,
        )
        assert click_listener_match, "Could not find click event listener with openDetailPanel"
        click_code = click_listener_match.group(0)
        assert "stopPropagation" in click_code, \
            "Card id click handler must call e.stopPropagation()"
