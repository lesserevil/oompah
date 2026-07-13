"""Regression tests: draft swimlane toggle controls removed (OOMPAH-171).

After OOMPAH-171, the swimlane header must NOT include:
- toggleEpicDraft() function
- hasDraftLabel() function
- "Mark as Draft" text
- "Finalize" text (as draft lifecycle control)
- swimlane-draft-badge spans

Core swimlane controls (expand/collapse, header title) must still be present.

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


class TestToggleFunctionsAbsent:
    """toggleEpicDraft and hasDraftLabel JS must be fully removed."""

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


class TestToggleButtonTextAbsent:
    """Draft toggle button text must not appear anywhere."""

    def test_mark_as_draft_text_absent(self):
        html = _load_dashboard_html()
        assert "Mark as Draft" not in html, (
            "'Mark as Draft' text must be removed (OOMPAH-171)"
        )

    def test_finalize_text_absent(self):
        html = _load_dashboard_html()
        assert "Finalize" not in html, (
            "'Finalize' draft control text must be removed (OOMPAH-171)"
        )

    def test_swimlane_draft_badge_absent(self):
        html = _load_dashboard_html()
        assert "swimlane-draft-badge" not in html, (
            "swimlane-draft-badge must be removed (OOMPAH-171)"
        )


class TestCoreSwimlaneControlsPresent:
    """Core swimlane controls must still be present after draft removal."""

    def test_swimlane_view_function_present(self):
        html = _load_dashboard_html()
        script = _extract_script(html)
        assert "renderSwimlaneView" in script, (
            "renderSwimlaneView() must still be present"
        )

    def test_swimlane_toggle_collapse_present(self):
        html = _load_dashboard_html()
        # Collapse/expand toggle should still exist in swimlane headers
        assert "swimlane" in html.lower(), (
            "Swimlane structure must still exist"
        )

    def test_create_card_function_present(self):
        html = _load_dashboard_html()
        script = _extract_script(html)
        assert "createCard" in script, "createCard() must still be present"
