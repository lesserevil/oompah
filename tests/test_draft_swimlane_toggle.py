"""Tests for Draft badge in swimlane header for draft epics.

When an epic has the 'draft' label, the swimlane header should display a
'.swimlane-draft-badge' badge with the text 'Draft'.

See issue: oompah-eqj
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


class TestSwimlaneDraftBadge:
    """Verify the Draft badge in swimlane headers for draft epics."""

    def test_swimlane_draft_badge_css_class_exists(self, html):
        """.swimlane-draft-badge CSS class must be defined in the stylesheet."""
        assert ".swimlane-draft-badge" in html, (
            ".swimlane-draft-badge CSS class must be present in dashboard.html"
        )

    def test_swimlane_draft_badge_css_in_style_section(self, html):
        """.swimlane-draft-badge must appear in the <style> section."""
        style_end = html.find("</style>")
        badge_pos = html.find(".swimlane-draft-badge")
        assert badge_pos != -1, ".swimlane-draft-badge must exist in the HTML"
        assert badge_pos < style_end, (
            ".swimlane-draft-badge must be defined inside the <style> block"
        )

    def test_swimlane_draft_badge_uses_accent_color(self, html):
        """.swimlane-draft-badge must use the --accent blue color."""
        badge_match = re.search(
            r"\.swimlane-draft-badge\s*\{([^}]*)\}",
            html,
            re.DOTALL,
        )
        assert badge_match, "Could not find .swimlane-draft-badge CSS block"
        css_body = badge_match.group(1)
        assert "--accent" in css_body or "#58a6ff" in css_body, (
            ".swimlane-draft-badge should use --accent (blue) color"
        )

    def test_swimlane_draft_badge_html_in_render_swimlane_view_when_draft(self, script):
        """renderSwimlaneView must generate the .swimlane-draft-badge when epic has 'draft' label."""
        render_match = re.search(
            r"function renderSwimlaneView\(.*?\)\s*\{(.*?)(?=\nfunction )",
            script,
            re.DOTALL,
        )
        assert render_match, "Could not find renderSwimlaneView function"
        body = render_match.group(1)
        assert "swimlane-draft-badge" in body, (
            "renderSwimlaneView must reference 'swimlane-draft-badge' class for the badge"
        )

    def test_swimlane_draft_badge_html_not_generated_without_draft_label(self, script):
        """renderSwimlaneView must only show badge when epic has 'draft' label (conditional)."""
        render_match = re.search(
            r"function renderSwimlaneView\(.*?\)\s*\{(.*?)(?=\nfunction )",
            script,
            re.DOTALL,
        )
        assert render_match, "Could not find renderSwimlaneView function"
        body = render_match.group(1)
        # The badge must be conditional on labels containing 'draft'
        # Look for a ternary/conditional pattern referencing draft
        assert re.search(
            r"labels.*includes.*['\"]draft['\"]|['\"]draft['\"].*includes",
            body,
        ), (
            "renderSwimlaneView must conditionally show badge based on 'draft' label"
        )

    def test_swimlane_draft_badge_uses_swimlane_draft_badge_class(self, script):
        """Badge HTML in renderSwimlaneView must use .swimlane-draft-badge CSS class."""
        render_match = re.search(
            r"function renderSwimlaneView\(.*?\)\s*\{(.*?)(?=\nfunction )",
            script,
            re.DOTALL,
        )
        assert render_match, "Could not find renderSwimlaneView function"
        body = render_match.group(1)
        assert "swimlane-draft-badge" in body, (
            "Badge in renderSwimlaneView must use class 'swimlane-draft-badge'"
        )

    def test_swimlane_draft_badge_text_is_Draft(self, script):
        """Badge HTML in renderSwimlaneView must display the text 'Draft'."""
        render_match = re.search(
            r"function renderSwimlaneView\(.*?\)\s*\{(.*?)(?=\nfunction )",
            script,
            re.DOTALL,
        )
        assert render_match, "Could not find renderSwimlaneView function"
        body = render_match.group(1)
        # Find the swimlane-draft-badge span and verify it contains 'Draft'
        badge_match = re.search(
            r"swimlane-draft-badge[^>]*>([^<]*)<",
            body,
        )
        assert badge_match, "Could not find swimlane-draft-badge span content"
        badge_text = badge_match.group(1).strip()
        assert badge_text == "Draft", (
            f"Badge text must be 'Draft', got '{badge_text}'"
        )

    def test_swimlane_draft_badge_has_aria_label(self, script):
        """Badge span must have an aria-label for accessibility."""
        render_match = re.search(
            r"function renderSwimlaneView\(.*?\)\s*\{(.*?)(?=\nfunction )",
            script,
            re.DOTALL,
        )
        assert render_match, "Could not find renderSwimlaneView function"
        body = render_match.group(1)
        # Find the badge HTML and check for aria-label
        badge_match = re.search(
            r"swimlane-draft-badge.*?aria-label",
            body,
            re.DOTALL,
        )
        assert badge_match, (
            "swimlane-draft-badge must include an aria-label attribute for accessibility"
        )

    def test_swimlane_draft_badge_handles_missing_labels_gracefully(self, script):
        """Badge condition must handle epics without labels (labels may be null/undefined)."""
        render_match = re.search(
            r"function renderSwimlaneView\(.*?\)\s*\{(.*?)(?=\nfunction )",
            script,
            re.DOTALL,
        )
        assert render_match, "Could not find renderSwimlaneView function"
        body = render_match.group(1)
        # Should use (epic.labels || []) pattern for safety
        assert "|| []" in body or "||[]" in body, (
            "renderSwimlaneView badge condition must handle missing labels with '|| []' pattern"
        )

    def test_swimlane_draft_badge_placed_between_title_and_counts(self, script):
        """Badge must appear between swimlane-title and swimlane-counts spans."""
        render_match = re.search(
            r"function renderSwimlaneView\(.*?\)\s*\{(.*?)(?=\nfunction )",
            script,
            re.DOTALL,
        )
        assert render_match, "Could not find renderSwimlaneView function"
        body = render_match.group(1)
        # Check ordering: swimlane-title comes before badge, badge before swimlane-counts
        title_pos = body.find("swimlane-title")
        badge_pos = body.find("swimlane-draft-badge")
        counts_pos = body.find("swimlane-counts")
        assert title_pos != -1, "swimlane-title must be present"
        assert badge_pos != -1, "swimlane-draft-badge must be present"
        assert counts_pos != -1, "swimlane-counts must be present"
        assert title_pos < badge_pos < counts_pos, (
            "swimlane-draft-badge must appear between swimlane-title and swimlane-counts"
        )
