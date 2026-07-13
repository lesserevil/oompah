"""Regression tests: Draft Epic badge removed from card rendering (OOMPAH-171).

After OOMPAH-171, the dashboard card rendering must NOT include any draft-epic
badge HTML (draftEpicBadgeHtml variable, .draft-epic-badge CSS, Draft Epic text
from a badge element). Other badges (merged, etc.) must still be present.

See issue: OOMPAH-171
"""

import os
import re

import pytest


def _load_dashboard_html() -> str:
    template_path = os.path.join(
        os.path.dirname(__file__), os.pardir, "oompah", "templates", "dashboard.html"
    )
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()


def _extract_script(html: str) -> str:
    matches = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    return max(matches, key=len) if matches else ""


class TestDraftEpicBadgeCSS:
    """Verify .draft-epic-badge CSS block is absent."""

    def test_draft_epic_badge_css_absent(self):
        html = _load_dashboard_html()
        assert ".draft-epic-badge" not in html, (
            ".draft-epic-badge CSS class must be removed (OOMPAH-171)"
        )

    def test_swimlane_draft_badge_css_absent(self):
        html = _load_dashboard_html()
        assert ".swimlane-draft-badge" not in html, (
            ".swimlane-draft-badge CSS class must be removed (OOMPAH-171)"
        )


class TestDraftEpicBadgeJS:
    """Verify draftEpicBadgeHtml and related JS are absent from createCard()."""

    def test_draft_epic_badge_html_variable_absent(self):
        html = _load_dashboard_html()
        script = _extract_script(html)
        assert "draftEpicBadgeHtml" not in script, (
            "draftEpicBadgeHtml variable must be removed from createCard() (OOMPAH-171)"
        )

    def test_has_draft_label_function_absent(self):
        html = _load_dashboard_html()
        script = _extract_script(html)
        assert "hasDraftLabel" not in script, (
            "hasDraftLabel() must be removed (OOMPAH-171)"
        )

    def test_draft_epic_badge_text_not_in_js_string(self):
        html = _load_dashboard_html()
        script = _extract_script(html)
        # "Draft Epic" as a badge label should not appear in JS
        assert "Draft Epic" not in script, (
            "'Draft Epic' badge text must be removed from JS (OOMPAH-171)"
        )


class TestDraftEpicBadgeHTML:
    """Verify draft-epic-badge elements are not present in any HTML template."""

    def test_draft_epic_badge_span_not_in_html(self):
        html = _load_dashboard_html()
        assert "draft-epic-badge" not in html, (
            "draft-epic-badge span must not appear in HTML (OOMPAH-171)"
        )


class TestOtherBadgesStillPresent:
    """Other card badges must still be rendered (regression guard)."""

    def test_merged_badge_css_still_present(self):
        html = _load_dashboard_html()
        # .merged-badge or similar should still exist
        assert "merged" in html.lower(), (
            "Merged badge CSS/HTML should still be present"
        )

    def test_create_card_function_still_present(self):
        html = _load_dashboard_html()
        script = _extract_script(html)
        assert "createCard" in script, "createCard() function must still be present"

    def test_card_id_row_still_present(self):
        html = _load_dashboard_html()
        script = _extract_script(html)
        assert "card-id" in script, "card-id row must still be rendered in createCard()"
