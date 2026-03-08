"""Tests for the 'questions waiting' notification widget on the dashboard.

When issues are tagged with the 'asking_question' label, the dashboard must
display a notification in the agent-bar so end users know they need to respond.

Covers:
  1. HTML structure — questions-stat element exists in agent-bar with correct attributes
  2. CSS — questions-dropdown styles are defined
  3. scanQuestionsFromBoard() JS function — structure and logic
  4. toggleQuestionsDropdown() and closeQuestionsDropdown() — existence
  5. renderBoard() calls scanQuestionsFromBoard()
  6. Dropdown items contain identifier and title, with onclick to open detail panel
  7. Escape key closes the dropdown
  8. Click-outside handler closes the dropdown
  9. Accessibility — aria attributes on the stat element

See issue: oompah-ga1
"""

from __future__ import annotations

import os
import re

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_dashboard_html() -> str:
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


def _extract_function(script: str, func_name: str) -> str:
    """Extract the body of a named JS function from the script."""
    match = re.search(
        rf"function {re.escape(func_name)}\(.*?\)\s*\{{(.*?)(?=\nfunction |\Z)",
        script,
        re.DOTALL,
    )
    assert match, f"Could not find function '{func_name}' in script"
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
def style_block(html):
    match = re.search(r"<style>(.*?)</style>", html, re.DOTALL)
    assert match, "No <style> block found in dashboard HTML"
    return match.group(1)


@pytest.fixture(scope="module")
def scan_questions_body(script):
    return _extract_function(script, "scanQuestionsFromBoard")


@pytest.fixture(scope="module")
def toggle_questions_body(script):
    return _extract_function(script, "toggleQuestionsDropdown")


@pytest.fixture(scope="module")
def close_questions_body(script):
    return _extract_function(script, "closeQuestionsDropdown")


@pytest.fixture(scope="module")
def render_board_body(script):
    return _extract_function(script, "renderBoard")


# ===========================================================================
# 1. HTML structure
# ===========================================================================

class TestQuestionsStatHTML:
    """Verify the questions-stat element is present in the agent-bar HTML."""

    def test_questions_stat_element_exists(self, html):
        """A span with id='questions-stat' must exist in the HTML."""
        assert 'id="questions-stat"' in html, (
            "Dashboard must have an element with id='questions-stat'"
        )

    def test_questions_stat_inside_agent_bar(self, html):
        """questions-stat must appear inside the agent-bar section."""
        agent_bar_start = html.find('id="agent-bar"')
        questions_stat_pos = html.find('id="questions-stat"')
        agent_bar_end = html.find('</div>', agent_bar_start)
        # questions-stat must be between agent-bar opening and its closing div region
        assert agent_bar_start < questions_stat_pos, (
            "questions-stat must come after the agent-bar element"
        )

    def test_questions_count_element_exists(self, html):
        """A strong/element with id='questions-count' must display the count."""
        assert 'id="questions-count"' in html, (
            "Dashboard must have an element with id='questions-count'"
        )

    def test_questions_dropdown_element_exists(self, html):
        """A div with id='questions-dropdown' must exist for the dropdown."""
        assert 'id="questions-dropdown"' in html, (
            "Dashboard must have an element with id='questions-dropdown'"
        )

    def test_questions_dropdown_inside_questions_stat(self, html):
        """The questions-dropdown must be nested inside questions-stat."""
        stat_start = html.find('id="questions-stat"')
        dropdown_pos = html.find('id="questions-dropdown"')
        assert stat_start < dropdown_pos, (
            "questions-dropdown must be inside (after the opening of) questions-stat"
        )
        # Find the closing tag of questions-stat element
        # (rough check: dropdown comes before running-agents)
        running_agents_pos = html.find('id="running-agents"')
        assert dropdown_pos < running_agents_pos, (
            "questions-dropdown must come before running-agents in the DOM"
        )

    def test_questions_stat_hidden_by_default(self, html):
        """questions-stat must be hidden by default (display:none)."""
        # Find the questions-stat opening tag
        stat_start = html.find('id="questions-stat"')
        # Get the full opening tag
        tag_end = html.find('>', stat_start)
        tag = html[stat_start:tag_end]
        assert "display:none" in tag or "display: none" in tag, (
            "questions-stat must be hidden by default (display:none)"
        )

    def test_questions_stat_has_cursor_pointer(self, html):
        """questions-stat must have cursor:pointer for interactivity."""
        stat_start = html.find('id="questions-stat"')
        tag_end = html.find('>', stat_start)
        tag = html[stat_start:tag_end]
        assert "cursor:pointer" in tag or "cursor: pointer" in tag, (
            "questions-stat must have cursor:pointer"
        )

    def test_questions_stat_text_label(self, html):
        """The notification must include human-readable text about 'questions'."""
        stat_start = html.find('id="questions-stat"')
        stat_end = html.find('id="running-agents"')
        stat_html = html[stat_start:stat_end]
        assert "question" in stat_html.lower(), (
            "questions-stat must contain text mentioning 'question(s)'"
        )


# ===========================================================================
# 2. Accessibility attributes
# ===========================================================================

class TestQuestionsStatAccessibility:
    """Verify accessibility attributes on the questions-stat element."""

    def test_questions_stat_has_aria_haspopup(self, html):
        """questions-stat must have aria-haspopup to indicate it controls a popup."""
        stat_start = html.find('id="questions-stat"')
        tag_end = html.find('>', stat_start)
        tag = html[stat_start:tag_end]
        assert "aria-haspopup" in tag, (
            "questions-stat must have aria-haspopup attribute"
        )

    def test_questions_stat_has_aria_expanded(self, html):
        """questions-stat must have aria-expanded to reflect dropdown state."""
        stat_start = html.find('id="questions-stat"')
        tag_end = html.find('>', stat_start)
        tag = html[stat_start:tag_end]
        assert "aria-expanded" in tag, (
            "questions-stat must have aria-expanded attribute"
        )

    def test_questions_stat_has_aria_label(self, html):
        """questions-stat must have an aria-label for screen readers."""
        stat_start = html.find('id="questions-stat"')
        tag_end = html.find('>', stat_start)
        tag = html[stat_start:tag_end]
        assert "aria-label" in tag, (
            "questions-stat must have an aria-label for screen readers"
        )

    def test_questions_dropdown_has_role_menu(self, html):
        """questions-dropdown must have role='menu' for accessibility."""
        dropdown_start = html.find('id="questions-dropdown"')
        tag_end = html.find('>', dropdown_start)
        tag = html[dropdown_start:tag_end]
        assert 'role="menu"' in tag or "role='menu'" in tag, (
            "questions-dropdown must have role='menu'"
        )

    def test_questions_dropdown_has_aria_label(self, html):
        """questions-dropdown must have an aria-label."""
        dropdown_start = html.find('id="questions-dropdown"')
        tag_end = html.find('>', dropdown_start)
        tag = html[dropdown_start:tag_end]
        assert "aria-label" in tag, (
            "questions-dropdown must have an aria-label"
        )


# ===========================================================================
# 3. CSS for questions-dropdown
# ===========================================================================

class TestQuestionsDropdownCSS:
    """Verify CSS classes for the dropdown are defined."""

    def test_questions_dropdown_class_defined(self, style_block):
        """.questions-dropdown CSS class must be defined."""
        assert ".questions-dropdown" in style_block, (
            ".questions-dropdown CSS class must be defined in the <style> block"
        )

    def test_questions_dropdown_open_class_defined(self, style_block):
        """.questions-dropdown.open CSS class must be defined."""
        assert ".questions-dropdown.open" in style_block, (
            ".questions-dropdown.open CSS class must be defined"
        )

    def test_questions_dropdown_hidden_by_default(self, style_block):
        """The .questions-dropdown rule must include display:none to hide it by default."""
        match = re.search(r"\.questions-dropdown\s*\{([^}]*)\}", style_block, re.DOTALL)
        assert match, "Could not find .questions-dropdown CSS block"
        css_body = match.group(1)
        assert "display" in css_body and "none" in css_body, (
            ".questions-dropdown must have display:none by default"
        )

    def test_questions_dropdown_open_shows_block(self, style_block):
        """The .questions-dropdown.open rule must show the dropdown (display:block)."""
        match = re.search(r"\.questions-dropdown\.open\s*\{([^}]*)\}", style_block, re.DOTALL)
        assert match, "Could not find .questions-dropdown.open CSS block"
        css_body = match.group(1)
        assert "display" in css_body and "block" in css_body, (
            ".questions-dropdown.open must have display:block"
        )

    def test_questions_dropdown_has_z_index(self, style_block):
        """The dropdown must have a high z-index to appear above other content."""
        match = re.search(r"\.questions-dropdown\s*\{([^}]*)\}", style_block, re.DOTALL)
        assert match
        css_body = match.group(1)
        assert "z-index" in css_body, (
            ".questions-dropdown must have z-index to appear above other UI elements"
        )

    def test_questions_dropdown_has_position_absolute(self, style_block):
        """The dropdown must be absolutely positioned."""
        match = re.search(r"\.questions-dropdown\s*\{([^}]*)\}", style_block, re.DOTALL)
        assert match
        css_body = match.group(1)
        assert "position" in css_body and "absolute" in css_body, (
            ".questions-dropdown must have position:absolute"
        )

    def test_questions_dropdown_has_background(self, style_block):
        """The dropdown must have a background color."""
        match = re.search(r"\.questions-dropdown\s*\{([^}]*)\}", style_block, re.DOTALL)
        assert match
        css_body = match.group(1)
        assert "background" in css_body, (
            ".questions-dropdown must have a background color"
        )

    def test_questions_dropdown_item_class_defined(self, style_block):
        """.questions-dropdown-item CSS class must be defined."""
        assert ".questions-dropdown-item" in style_block, (
            ".questions-dropdown-item CSS class must be defined"
        )

    def test_questions_stat_position_relative(self, style_block):
        """.questions-stat must have position:relative to anchor the dropdown."""
        match = re.search(r"\.questions-stat\s*\{([^}]*)\}", style_block, re.DOTALL)
        assert match, "Could not find .questions-stat CSS block"
        css_body = match.group(1)
        assert "position" in css_body and "relative" in css_body, (
            ".questions-stat must have position:relative to anchor the dropdown"
        )


# ===========================================================================
# 4. scanQuestionsFromBoard() function
# ===========================================================================

class TestScanQuestionsFromBoard:
    """Verify the scanQuestionsFromBoard() function exists and is correctly structured."""

    def test_function_exists(self, script):
        """scanQuestionsFromBoard function must be defined."""
        assert "function scanQuestionsFromBoard" in script, (
            "scanQuestionsFromBoard function must be defined in the dashboard script"
        )

    def test_filters_by_asking_question_label(self, scan_questions_body):
        """Must filter allIssuesFlat for issues with 'asking_question' label."""
        assert "asking_question" in scan_questions_body, (
            "scanQuestionsFromBoard must filter for 'asking_question' label"
        )

    def test_uses_allIssuesFlat(self, scan_questions_body):
        """Must read from allIssuesFlat."""
        assert "allIssuesFlat" in scan_questions_body, (
            "scanQuestionsFromBoard must use allIssuesFlat to find questions"
        )

    def test_uses_labels_filter(self, scan_questions_body):
        """Must check labels array for the 'asking_question' tag."""
        assert "labels" in scan_questions_body, (
            "scanQuestionsFromBoard must check issue labels"
        )
        assert "includes" in scan_questions_body, (
            "scanQuestionsFromBoard must use .includes() to check for the label"
        )

    def test_handles_missing_labels_safely(self, scan_questions_body):
        """Must use (labels || []) to safely handle issues without labels."""
        assert "|| []" in scan_questions_body or "||[]" in scan_questions_body, (
            "scanQuestionsFromBoard must use (labels || []) to handle missing labels"
        )

    def test_updates_questions_count_element(self, scan_questions_body):
        """Must update the questions-count element text."""
        assert "questions-count" in scan_questions_body, (
            "scanQuestionsFromBoard must update questions-count element"
        )

    def test_shows_stat_when_questions_exist(self, scan_questions_body):
        """Must show the questions-stat element when questions exist."""
        assert "questions-stat" in scan_questions_body, (
            "scanQuestionsFromBoard must reference questions-stat element"
        )
        # When questions exist, display must be set to non-empty
        assert "style.display" in scan_questions_body, (
            "scanQuestionsFromBoard must set style.display to show/hide the stat"
        )

    def test_hides_stat_when_no_questions(self, scan_questions_body):
        """Must hide the questions-stat element when no questions exist."""
        # Must set display to 'none' to hide when empty
        assert "'none'" in scan_questions_body or '"none"' in scan_questions_body, (
            "scanQuestionsFromBoard must set display to 'none' when no questions"
        )

    def test_populates_dropdown_with_issues(self, scan_questions_body):
        """Must populate the dropdown with issue items."""
        assert "questions-dropdown" in scan_questions_body, (
            "scanQuestionsFromBoard must populate the questions-dropdown element"
        )
        assert "innerHTML" in scan_questions_body, (
            "scanQuestionsFromBoard must set innerHTML to build the dropdown items"
        )

    def test_dropdown_items_include_identifier(self, scan_questions_body):
        """Dropdown items must include the issue identifier."""
        assert "identifier" in scan_questions_body, (
            "scanQuestionsFromBoard must include issue identifier in dropdown items"
        )

    def test_dropdown_items_include_title(self, scan_questions_body):
        """Dropdown items must include the issue title."""
        assert "title" in scan_questions_body, (
            "scanQuestionsFromBoard must include issue title in dropdown items"
        )

    def test_dropdown_items_call_openDetailPanel(self, scan_questions_body):
        """Clicking a dropdown item must call openDetailPanel()."""
        assert "openDetailPanel" in scan_questions_body, (
            "scanQuestionsFromBoard must include openDetailPanel() in item click handlers"
        )

    def test_dropdown_items_close_dropdown_on_click(self, scan_questions_body):
        """Clicking a dropdown item must also close the dropdown."""
        assert "closeQuestionsDropdown" in scan_questions_body, (
            "scanQuestionsFromBoard must call closeQuestionsDropdown() when an item is clicked"
        )

    def test_dropdown_items_use_esc_for_safety(self, scan_questions_body):
        """Must use esc() to safely escape issue identifiers/titles in HTML."""
        assert "esc(" in scan_questions_body, (
            "scanQuestionsFromBoard must use esc() to safely escape HTML content"
        )

    def test_dropdown_items_have_role_menuitem(self, scan_questions_body):
        """Dropdown items must have role='menuitem' for accessibility."""
        assert "menuitem" in scan_questions_body, (
            "scanQuestionsFromBoard must add role='menuitem' to dropdown items"
        )

    def test_dropdown_items_have_keyboard_handler(self, scan_questions_body):
        """Dropdown items must support keyboard navigation (Enter/Space)."""
        assert "onkeydown" in scan_questions_body or "keydown" in scan_questions_body, (
            "scanQuestionsFromBoard must add keyboard handlers to dropdown items"
        )

    def test_calls_closeQuestionsDropdown_when_empty(self, scan_questions_body):
        """Must call closeQuestionsDropdown() when there are no questions."""
        assert "closeQuestionsDropdown" in scan_questions_body, (
            "scanQuestionsFromBoard must call closeQuestionsDropdown() when no questions"
        )

    def test_dropdown_has_header_section(self, scan_questions_body):
        """Dropdown must include a header section for context."""
        assert "questions-dropdown-header" in scan_questions_body or \
               "Waiting" in scan_questions_body or \
               "header" in scan_questions_body.lower(), (
            "scanQuestionsFromBoard must include a header in the dropdown"
        )


# ===========================================================================
# 5. toggleQuestionsDropdown() function
# ===========================================================================

class TestToggleQuestionsDropdown:
    """Verify toggleQuestionsDropdown() exists and works correctly."""

    def test_function_exists(self, script):
        """toggleQuestionsDropdown function must be defined."""
        assert "function toggleQuestionsDropdown" in script, (
            "toggleQuestionsDropdown function must be defined"
        )

    def test_toggles_open_class(self, toggle_questions_body):
        """Must toggle the 'open' class on the dropdown."""
        assert "open" in toggle_questions_body, (
            "toggleQuestionsDropdown must toggle the 'open' class"
        )

    def test_calls_closeQuestionsDropdown(self, toggle_questions_body):
        """Must call closeQuestionsDropdown() to close."""
        assert "closeQuestionsDropdown" in toggle_questions_body, (
            "toggleQuestionsDropdown must call closeQuestionsDropdown() to close"
        )

    def test_stops_propagation(self, toggle_questions_body):
        """Must stop event propagation to prevent immediate close from click-outside handler."""
        assert "stopPropagation" in toggle_questions_body, (
            "toggleQuestionsDropdown must call e.stopPropagation() to prevent "
            "immediate closure from click-outside handler"
        )

    def test_updates_aria_expanded(self, toggle_questions_body):
        """Must update aria-expanded on the stat element."""
        assert "aria-expanded" in toggle_questions_body, (
            "toggleQuestionsDropdown must update aria-expanded attribute"
        )


# ===========================================================================
# 6. closeQuestionsDropdown() function
# ===========================================================================

class TestCloseQuestionsDropdown:
    """Verify closeQuestionsDropdown() exists and removes the open class."""

    def test_function_exists(self, script):
        """closeQuestionsDropdown function must be defined."""
        assert "function closeQuestionsDropdown" in script, (
            "closeQuestionsDropdown function must be defined"
        )

    def test_removes_open_class(self, close_questions_body):
        """Must remove the 'open' class from the dropdown."""
        assert "remove" in close_questions_body and "open" in close_questions_body, (
            "closeQuestionsDropdown must call classList.remove('open')"
        )

    def test_updates_aria_expanded_false(self, close_questions_body):
        """Must set aria-expanded to 'false' when closing."""
        assert "aria-expanded" in close_questions_body, (
            "closeQuestionsDropdown must update aria-expanded attribute"
        )
        assert "'false'" in close_questions_body or '"false"' in close_questions_body, (
            "closeQuestionsDropdown must set aria-expanded to 'false'"
        )


# ===========================================================================
# 7. renderBoard() integration
# ===========================================================================

class TestRenderBoardCallsScan:
    """Verify renderBoard() calls scanQuestionsFromBoard() after building the board."""

    def test_renderBoard_calls_scanQuestionsFromBoard(self, render_board_body):
        """renderBoard must call scanQuestionsFromBoard() after rendering."""
        assert "scanQuestionsFromBoard" in render_board_body, (
            "renderBoard() must call scanQuestionsFromBoard() to update the notification widget"
        )

    def test_scan_called_after_board_rendered(self, render_board_body):
        """scanQuestionsFromBoard() call must come after board rendering logic."""
        render_flat_pos = render_board_body.find("renderFlatView")
        render_swimlane_pos = render_board_body.find("renderSwimlaneView")
        scan_pos = render_board_body.find("scanQuestionsFromBoard")

        assert scan_pos != -1, "scanQuestionsFromBoard must be called in renderBoard"
        # The scan call should come after both render functions are defined/called
        min_render_pos = min(p for p in [render_flat_pos, render_swimlane_pos] if p != -1)
        assert scan_pos > min_render_pos, (
            "scanQuestionsFromBoard() must be called after the board rendering logic"
        )


# ===========================================================================
# 8. Escape key and click-outside handling
# ===========================================================================

class TestDropdownDismissal:
    """Verify the dropdown can be closed via Escape key and click-outside."""

    def test_escape_key_handler_calls_closeQuestionsDropdown(self, script):
        """The Escape key handler must close the questions dropdown."""
        # Find the keydown event listener for Escape
        escape_handler_match = re.search(
            r"key\s*===\s*['\"]Escape['\"].*?closeQuestionsDropdown",
            script,
            re.DOTALL,
        )
        assert escape_handler_match, (
            "The Escape keydown handler must call closeQuestionsDropdown()"
        )

    def test_click_outside_handler_exists(self, script):
        """A document click handler must close the dropdown when clicking outside."""
        # Look for document.addEventListener('click', ...) that closes the dropdown
        click_outside_match = re.search(
            r"document\.addEventListener\(['\"]click['\"].*?closeQuestionsDropdown",
            script,
            re.DOTALL,
        )
        assert click_outside_match, (
            "A document click handler must close questions dropdown when clicking outside"
        )

    def test_click_outside_checks_contains(self, script):
        """The click-outside handler must check if the click target is inside questions-stat."""
        # The handler should use .contains() to check if click is inside the widget
        click_outside_region = re.search(
            r"document\.addEventListener\(['\"]click['\"](.*?)(?=\}\);|\Z)",
            script,
            re.DOTALL,
        )
        assert click_outside_region, "Could not find document click handler"
        handler_body = click_outside_region.group(1)
        assert "contains" in handler_body, (
            "Click-outside handler must use .contains() to check if click target is inside "
            "the questions-stat element"
        )
        assert "questions-stat" in handler_body, (
            "Click-outside handler must reference questions-stat element"
        )


# ===========================================================================
# 9. toggleQuestionsDropdown called from HTML element
# ===========================================================================

class TestHTMLWiring:
    """Verify the HTML element is wired to the JS functions."""

    def test_questions_stat_onclick_calls_toggle(self, html):
        """questions-stat must call toggleQuestionsDropdown on click."""
        stat_start = html.find('id="questions-stat"')
        tag_end = html.find('>', stat_start)
        tag = html[stat_start:tag_end]
        assert "toggleQuestionsDropdown" in tag, (
            "questions-stat element must have onclick='toggleQuestionsDropdown(event)'"
        )

    def test_questions_stat_onclick_passes_event(self, html):
        """The onclick must pass event to toggleQuestionsDropdown for stopPropagation."""
        stat_start = html.find('id="questions-stat"')
        tag_end = html.find('>', stat_start)
        tag = html[stat_start:tag_end]
        # Should call toggleQuestionsDropdown(event)
        assert "toggleQuestionsDropdown(event)" in tag, (
            "questions-stat onclick must pass 'event' to toggleQuestionsDropdown"
        )
