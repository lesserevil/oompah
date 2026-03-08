"""Tests for visual type indicators on kanban cards.

Each card must display an icon/emoji that indicates its issue type
(feature, epic, task, bug, chore).  This makes it visually distinct
at a glance without opening the detail panel.

See issue: oompah-fpm
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


class TestTypeIconMapping:
    """Verify TYPE_ICONS constant and getTypeIcon() function are present and correct."""

    def test_type_icons_constant_exists(self, script):
        """TYPE_ICONS constant must be declared mapping type strings to icons."""
        assert "const TYPE_ICONS" in script or "var TYPE_ICONS" in script

    def test_type_icons_has_feature(self, script):
        """TYPE_ICONS must include an entry for 'feature'."""
        assert "feature" in script
        # Check that feature maps to an icon (not empty)
        match = re.search(r"feature\s*:\s*['\"](.+?)['\"]", script)
        assert match, "feature key in TYPE_ICONS must map to a non-empty icon string"
        assert match.group(1).strip() != ""

    def test_type_icons_has_bug(self, script):
        """TYPE_ICONS must include an entry for 'bug'."""
        match = re.search(r"bug\s*:\s*['\"](.+?)['\"]", script)
        assert match, "bug key in TYPE_ICONS must map to a non-empty icon string"
        assert match.group(1).strip() != ""

    def test_type_icons_has_task(self, script):
        """TYPE_ICONS must include an entry for 'task'."""
        match = re.search(r"task\s*:\s*['\"](.+?)['\"]", script)
        assert match, "task key in TYPE_ICONS must map to a non-empty icon string"
        assert match.group(1).strip() != ""

    def test_type_icons_has_epic(self, script):
        """TYPE_ICONS must include an entry for 'epic'."""
        match = re.search(r"epic\s*:\s*['\"](.+?)['\"]", script)
        assert match, "epic key in TYPE_ICONS must map to a non-empty icon string"
        assert match.group(1).strip() != ""

    def test_type_icons_has_chore(self, script):
        """TYPE_ICONS must include an entry for 'chore'."""
        match = re.search(r"chore\s*:\s*['\"](.+?)['\"]", script)
        assert match, "chore key in TYPE_ICONS must map to a non-empty icon string"
        assert match.group(1).strip() != ""

    def test_get_type_icon_function_exists(self, script):
        """getTypeIcon() function must be declared."""
        assert "function getTypeIcon" in script

    def test_get_type_icon_uses_type_icons_map(self, script):
        """getTypeIcon() must look up the TYPE_ICONS map."""
        # Find the function body
        match = re.search(r"function getTypeIcon\(.*?\)\s*\{(.*?)\}", script, re.DOTALL)
        assert match, "Could not find getTypeIcon function body"
        body = match.group(1)
        assert "TYPE_ICONS" in body

    def test_get_type_icon_has_fallback(self, script):
        """getTypeIcon() must return a fallback icon for unknown types."""
        match = re.search(r"function getTypeIcon\(.*?\)\s*\{(.*?)\}", script, re.DOTALL)
        assert match, "Could not find getTypeIcon function body"
        body = match.group(1)
        # Must have a fallback (|| operator or default branch)
        assert "||" in body or "default" in body, \
            "getTypeIcon must provide a fallback for unknown issue types"


class TestTypeIconInCardHTML:
    """Verify the type icon is rendered inside createCard()."""

    def test_create_card_calls_get_type_icon(self, script):
        """createCard() must call getTypeIcon to get the icon for each issue."""
        assert "getTypeIcon" in script
        # Confirm it's called within a context that creates cards
        assert "getTypeIcon(issue.issue_type)" in script

    def test_type_icon_element_in_card_template(self, script):
        """The card HTML template must include a type-icon element."""
        assert 'class="type-icon"' in script

    def test_type_icon_has_title_attribute(self, script):
        """The type-icon element must have a title attribute for accessibility."""
        # The title provides a tooltip with the type name
        match = re.search(r'class="type-icon".*?title=', script, re.DOTALL)
        assert match, "type-icon element must have a title attribute"

    def test_type_icon_appears_in_card_id_section(self, script):
        """The type icon must appear inside the card-id section (near the identifier)."""
        # Find the card.innerHTML template and check type-icon is inside card-id
        match = re.search(
            r'card\.innerHTML\s*=\s*`(.*?)`\s*;',
            script,
            re.DOTALL,
        )
        assert match, "Could not find card.innerHTML template"
        card_template = match.group(1)
        assert 'class="card-id"' in card_template
        assert 'type-icon' in card_template
        # type-icon should appear before the priority badge
        type_icon_pos = card_template.find('type-icon')
        priority_badge_pos = card_template.find('priority-badge')
        assert type_icon_pos < priority_badge_pos, \
            "type-icon should appear before the priority badge in the card template"

    def test_type_icon_template_uses_typeIcon_variable(self, script):
        """The card template must interpolate the typeIcon variable."""
        assert "${typeIcon}" in script

    def test_type_label_variable_declared(self, script):
        """typeLabel variable must be declared in createCard for use in title attr."""
        assert "const typeLabel" in script or "let typeLabel" in script or "var typeLabel" in script


class TestTypeIconCSS:
    """Verify CSS for the type-icon element is present."""

    def test_type_icon_css_class_exists(self, html):
        """A .type-icon CSS rule must exist in the dashboard stylesheet."""
        assert ".type-icon" in html

    def test_type_icon_css_has_font_size(self, html):
        """The .type-icon CSS rule should set a font-size for consistent sizing."""
        # Find the .type-icon CSS block
        match = re.search(r"\.type-icon\s*\{([^}]+)\}", html, re.DOTALL)
        assert match, "Could not find .type-icon CSS rule"
        css_block = match.group(1)
        assert "font-size" in css_block


class TestCardIdentifierSelector:
    """Verify the card click handler uses the correct selector after the refactor."""

    def test_card_identifier_class_used_in_click_handler(self, script):
        """The click handler for opening detail panel must use .card-identifier selector."""
        assert ".card-identifier" in script

    def test_card_identifier_in_card_template(self, script):
        """The card template must include a span with class card-identifier."""
        assert 'class="card-identifier"' in script
