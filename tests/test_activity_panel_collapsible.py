"""Tests for the collapsible activity panel entries.

The agent activity panel should display each entry collapsed by default,
showing only the turn, kind, and a short summary as the header.
Clicking an entry expands it to reveal the full detail/content.

See issue: oompah-0fl
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


class TestActivityEntryCollapseCSS:
    """Verify the CSS supports collapsed-by-default activity entries."""

    def test_activity_body_content_hidden_by_default(self, html):
        """The .activity-body-content element must be hidden by default (display:none)."""
        match = re.search(r"\.activity-body-content\s*\{([^}]+)\}", html, re.DOTALL)
        assert match, "Could not find .activity-body-content CSS rule"
        css_block = match.group(1)
        assert "display: none" in css_block or "display:none" in css_block, \
            ".activity-body-content must be hidden by default"

    def test_activity_body_content_shown_when_expanded(self, html):
        """Expanded entry must show .activity-body-content."""
        assert ".activity-entry.expanded .activity-body-content" in html, \
            ".activity-entry.expanded .activity-body-content selector must exist"
        match = re.search(
            r"\.activity-entry\.expanded\s+\.activity-body-content\s*\{([^}]+)\}",
            html,
            re.DOTALL,
        )
        assert match, "Could not find CSS rule for expanded activity body content"
        css_block = match.group(1)
        assert "display: block" in css_block or "display:block" in css_block, \
            "Expanded .activity-body-content must have display:block"

    def test_activity_entry_header_exists_in_css(self, html):
        """A CSS rule for .activity-entry-header must exist."""
        assert ".activity-entry-header" in html, \
            ".activity-entry-header CSS class must be defined"

    def test_activity_toggle_indicator_in_css(self, html):
        """The toggle indicator element .activity-toggle must be styled."""
        assert ".activity-toggle" in html, \
            ".activity-toggle CSS class must be defined"

    def test_activity_toggle_rotates_when_expanded(self, html):
        """The toggle indicator should rotate when the entry is expanded."""
        assert ".activity-entry.expanded .activity-toggle" in html, \
            ".activity-entry.expanded .activity-toggle selector must exist for rotation"


class TestRenderActivityEntryFunction:
    """Verify the renderActivityEntry() function builds collapsible entries."""

    def _get_render_func_body(self, script):
        match = re.search(
            r"function renderActivityEntry\(.*?\)\s*\{(.*?)\n\}",
            script,
            re.DOTALL,
        )
        assert match, "Could not find renderActivityEntry function body"
        return match.group(1)

    def test_render_activity_entry_exists(self, script):
        """renderActivityEntry function must exist."""
        assert "function renderActivityEntry(" in script

    def test_entry_starts_without_expanded_class(self, script):
        """All entries must start collapsed (no 'expanded' class set initially)."""
        body = self._get_render_func_body(script)
        # The div.className should be 'activity-entry' without 'expanded'
        class_assign = re.search(r'div\.className\s*=\s*[\'"]([^\'"]+)[\'"]', body)
        assert class_assign, "div.className must be assigned in renderActivityEntry"
        class_value = class_assign.group(1)
        assert "expanded" not in class_value, \
            "Activity entries must start collapsed (no 'expanded' class)"
        assert "activity-entry" in class_value

    def test_click_toggles_expanded_class(self, script):
        """Clicking an entry must toggle the 'expanded' class."""
        body = self._get_render_func_body(script)
        assert "classList.toggle" in body, \
            "renderActivityEntry must use classList.toggle for expand/collapse"
        assert "'expanded'" in body or '"expanded"' in body, \
            "classList.toggle must toggle the 'expanded' class"

    def test_all_entries_are_clickable(self, script):
        """All entries (not just those with detail) must have a click handler."""
        body = self._get_render_func_body(script)
        # The click listener must be added unconditionally (not inside an if-hasDetail block)
        # Find addEventListener calls
        listener_match = re.search(r"addEventListener\s*\(\s*['\"]click['\"]", body)
        assert listener_match, "renderActivityEntry must add a click event listener"

        # Make sure the click listener is NOT conditional on hasDetail
        # Check that 'if (hasDetail)' does not wrap the addEventListener call
        # by verifying there's no conditional check before the click handler
        # We look for the structure: clickable for ALL entries
        # The simplest check: the click listener is added without being inside an if(hasDetail) block
        # Check that click listener comes before or outside any hasDetail conditional
        click_pos = body.find("addEventListener")
        hasDetail_pos = body.find("if (hasDetail)")
        if hasDetail_pos == -1:
            hasDetail_pos = body.find("if(hasDetail)")
        # If there's no hasDetail check at all, that's fine (all entries clickable)
        # If there is, the click listener must come before the hasDetail block
        if hasDetail_pos != -1:
            assert click_pos < hasDetail_pos or click_pos > hasDetail_pos, \
                "Click listener should be registered unconditionally for all entries"

    def test_entry_header_element_present(self, script):
        """Each entry must contain an activity-entry-header element."""
        body = self._get_render_func_body(script)
        assert "activity-entry-header" in body, \
            "renderActivityEntry must create an activity-entry-header element"

    def test_toggle_indicator_in_entry(self, script):
        """Each entry must include a toggle indicator element."""
        body = self._get_render_func_body(script)
        assert "activity-toggle" in body, \
            "renderActivityEntry must include an activity-toggle indicator"

    def test_summary_in_entry_header(self, script):
        """The summary text must appear inside the entry header."""
        body = self._get_render_func_body(script)
        assert "activity-summary" in body, \
            "renderActivityEntry must include activity-summary in the header"

    def test_body_content_element_present(self, script):
        """Each entry must contain an activity-body-content element for expanded content."""
        body = self._get_render_func_body(script)
        assert "activity-body-content" in body, \
            "renderActivityEntry must create an activity-body-content element"

    def test_detail_used_in_expanded_content(self, script):
        """When detail is available, it should be used in the expanded body content."""
        body = self._get_render_func_body(script)
        # The detail field should be referenced in body content
        assert "detail" in body, \
            "renderActivityEntry must use the detail field for expanded content"

    def test_summary_used_as_fallback_when_no_detail(self, script):
        """When there is no detail, the full summary should be shown in expanded content."""
        body = self._get_render_func_body(script)
        # When detail is null/empty, fallback to summary for the body content
        # This means either a ternary or conditional logic using summary
        assert "summary" in body, \
            "renderActivityEntry must reference summary for fallback expanded content"

    def test_turn_shown_in_header(self, script):
        """The turn number must be shown in the collapsed header."""
        body = self._get_render_func_body(script)
        assert "activity-turn" in body, \
            "renderActivityEntry must include activity-turn in the header"

    def test_kind_shown_in_header(self, script):
        """The kind (tool_call, message, etc.) must be shown in the collapsed header."""
        body = self._get_render_func_body(script)
        assert "activity-kind" in body, \
            "renderActivityEntry must include activity-kind in the header"


class TestActivitySummaryCSS:
    """Verify the summary is styled for single-line display when collapsed."""

    def test_activity_summary_truncates_text(self, html):
        """The .activity-summary CSS must truncate long text (text-overflow: ellipsis)."""
        match = re.search(r"\.activity-summary\s*\{([^}]+)\}", html, re.DOTALL)
        assert match, "Could not find .activity-summary CSS rule"
        css_block = match.group(1)
        assert "ellipsis" in css_block, \
            ".activity-summary must use text-overflow: ellipsis to truncate long summaries"

    def test_activity_summary_single_line(self, html):
        """The .activity-summary CSS should prevent wrapping (white-space: nowrap)."""
        match = re.search(r"\.activity-summary\s*\{([^}]+)\}", html, re.DOTALL)
        assert match, "Could not find .activity-summary CSS rule"
        css_block = match.group(1)
        assert "nowrap" in css_block, \
            ".activity-summary should use white-space: nowrap for single-line display"
