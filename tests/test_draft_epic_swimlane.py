"""Regression tests: draft-specific swimlane controls removed (OOMPAH-171).

After OOMPAH-171, the swimlane view must NOT contain:
- .swimlane-draft-badge CSS or HTML spans
- Mark as Draft / Finalize buttons
- toggleEpicDraft() function calls
- hasDraftLabel() calls in shouldShowIssueAsWorkCard

Core swimlane controls (collapsing, header rendering) must still be present.

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


class TestSwimlaneCSS:
    """Draft CSS classes must be absent; core swimlane CSS must remain."""

    def test_swimlane_draft_badge_css_absent(self):
        html = _load_dashboard_html()
        assert ".swimlane-draft-badge" not in html, (
            ".swimlane-draft-badge CSS must be removed (OOMPAH-171)"
        )

    def test_draft_epic_badge_css_absent(self):
        html = _load_dashboard_html()
        assert ".draft-epic-badge" not in html, (
            ".draft-epic-badge CSS must be removed (OOMPAH-171)"
        )

    def test_swimlane_css_still_present(self):
        html = _load_dashboard_html()
        assert "swimlane" in html.lower(), "Core swimlane CSS must still be present"


class TestSwimlaneHTMLControls:
    """Draft controls must be removed from swimlane header template."""

    def test_swimlane_draft_badge_span_absent(self):
        html = _load_dashboard_html()
        assert "swimlane-draft-badge" not in html, (
            "swimlane-draft-badge span must be removed (OOMPAH-171)"
        )

    def test_mark_as_draft_button_absent(self):
        html = _load_dashboard_html()
        assert "Mark as Draft" not in html, (
            "'Mark as Draft' button must be removed (OOMPAH-171)"
        )

    def test_finalize_button_absent(self):
        html = _load_dashboard_html()
        assert "Finalize" not in html, (
            "'Finalize' draft button must be removed (OOMPAH-171)"
        )


class TestSwimlaneJS:
    """Draft JS functions must be absent; core swimlane JS must remain."""

    def test_toggle_epic_draft_absent(self):
        html = _load_dashboard_html()
        script = _extract_script(html)
        assert "toggleEpicDraft" not in script, (
            "toggleEpicDraft() must be removed (OOMPAH-171)"
        )

    def test_has_draft_label_absent(self):
        html = _load_dashboard_html()
        script = _extract_script(html)
        assert "hasDraftLabel" not in script, (
            "hasDraftLabel() must be removed (OOMPAH-171)"
        )

    def test_should_show_issue_no_draft_branch(self):
        html = _load_dashboard_html()
        script = _extract_script(html)
        # shouldShowIssueAsWorkCard must not have a hasDraftLabel branch
        assert "hasDraftLabel" not in script, (
            "shouldShowIssueAsWorkCard must not call hasDraftLabel (OOMPAH-171)"
        )

    def test_render_swimlane_view_still_present(self):
        html = _load_dashboard_html()
        script = _extract_script(html)
        assert "renderSwimlaneView" in script, (
            "renderSwimlaneView() must still be present"
        )

    def test_swimlane_header_rendering_still_present(self):
        html = _load_dashboard_html()
        script = _extract_script(html)
        # swimlane-header class or similar should still appear in JS template
        assert "swimlane" in script.lower(), (
            "Swimlane header rendering must still be present"
        )
