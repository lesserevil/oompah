"""Contract tests: epic-strategy controls removed from projects.html (OOMPAH-169).

After OOMPAH-167 made 'shared' the only supported epic strategy in the backend
and OOMPAH-169 removed the UI controls, the projects management page must NOT:

  - Contain any epic-strategy CSS classes (.epic-strategy-group,
    .epic-strategy-option, .epic-strategy-name, .epic-strategy-desc,
    .epic-strategy-tag, .epic-strategy-label)
  - Render an "Epic Strategy:" display field in project cards
  - Render flat/stacked/shared radio buttons in the edit form
  - Include epic_strategy in the saveProject() PATCH body
  - Read an epic-strategy radio element to construct the request

These tests read the static HTML/JS source the same way
test_projects_whitelist_ui.py does, so they work without a running server.
"""

from __future__ import annotations

import os
import re

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_projects_html() -> str:
    template_path = os.path.join(
        os.path.dirname(__file__),
        os.pardir,
        "oompah",
        "templates",
        "projects.html",
    )
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()


def _extract_main_script(html: str) -> str:
    """Return the largest <script> block — that's the page logic."""
    matches = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    assert matches, "Could not find any <script> block in projects.html"
    return max(matches, key=len)


def _get_func_body(script: str, func_name: str) -> str:
    """Extract the body of a top-level JS function by name."""
    match = re.search(
        r"(?:async\s+)?function\s+" + re.escape(func_name) + r"\s*\([^)]*\)\s*\{",
        script,
    )
    if not match:
        return ""
    start = match.end()
    depth = 1
    i = start
    while i < len(script) and depth > 0:
        ch = script[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        i += 1
    return script[start : i - 1]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def html() -> str:
    return _load_projects_html()


@pytest.fixture(scope="module")
def script(html: str) -> str:
    return _extract_main_script(html)


# ---------------------------------------------------------------------------
# CSS — no epic-strategy classes
# ---------------------------------------------------------------------------


class TestEpicStrategyCssRemoved:
    """No epic-strategy CSS classes survive in projects.html."""

    def test_no_epic_strategy_group_css(self, html: str) -> None:
        assert ".epic-strategy-group" not in html, (
            ".epic-strategy-group CSS class must be removed from projects.html "
            "(epic-strategy selector UI was deleted in OOMPAH-169)."
        )

    def test_no_epic_strategy_option_css(self, html: str) -> None:
        assert ".epic-strategy-option" not in html, (
            ".epic-strategy-option CSS class must be removed from projects.html."
        )

    def test_no_epic_strategy_name_css(self, html: str) -> None:
        assert ".epic-strategy-name" not in html, (
            ".epic-strategy-name CSS class must be removed from projects.html."
        )

    def test_no_epic_strategy_desc_css(self, html: str) -> None:
        assert ".epic-strategy-desc" not in html, (
            ".epic-strategy-desc CSS class must be removed from projects.html."
        )

    def test_no_epic_strategy_tag_css(self, html: str) -> None:
        assert ".epic-strategy-tag" not in html, (
            ".epic-strategy-tag CSS class must be removed from projects.html."
        )

    def test_no_epic_strategy_label_css(self, html: str) -> None:
        assert ".epic-strategy-label" not in html, (
            ".epic-strategy-label CSS class must be removed from projects.html."
        )


# ---------------------------------------------------------------------------
# HTML — no epic-strategy display row or form controls
# ---------------------------------------------------------------------------


class TestEpicStrategyHtmlRemoved:
    """No epic-strategy HTML renders in the project card or edit form."""

    def test_no_epic_strategy_display_row(self, html: str) -> None:
        assert "Epic Strategy" not in html, (
            "The 'Epic Strategy:' display row must be removed from project cards "
            "in projects.html. Shared is the only strategy and needs no display."
        )

    def test_no_flat_radio_button(self, html: str) -> None:
        # Radio with value="flat" must not appear
        assert 'value="flat"' not in html, (
            "The flat radio button must be removed from the epic-strategy form group."
        )

    def test_no_stacked_radio_button(self, html: str) -> None:
        assert 'value="stacked"' not in html, (
            "The stacked radio button must be removed from the epic-strategy form group."
        )

    def test_no_epic_strategy_radio_group(self, html: str) -> None:
        assert "edit-epic-strategy" not in html, (
            "The edit-epic-strategy radio group name must be removed from projects.html."
        )

    def test_no_epic_strategy_group_div(self, html: str) -> None:
        assert "epic-strategy-group" not in html, (
            "The epic-strategy-group div must be removed from the edit form."
        )


# ---------------------------------------------------------------------------
# JS — saveProject() does not read or send epic_strategy
# ---------------------------------------------------------------------------


class TestSaveProjectNoEpicStrategy:
    """saveProject() must not read an epic-strategy radio or send epic_strategy."""

    def test_saveProject_no_epic_strategy_radio_read(self, script: str) -> None:
        body = _get_func_body(script, "saveProject")
        assert body, "saveProject must be defined in projects.html"
        assert "epic-strategy" not in body, (
            "saveProject() must not read from an 'edit-epic-strategy' radio group. "
            "The epic-strategy selector was removed in OOMPAH-169."
        )

    def test_saveProject_no_epic_strategy_field_in_body(self, script: str) -> None:
        body = _get_func_body(script, "saveProject")
        assert "epic_strategy" not in body, (
            "saveProject() must not include epic_strategy in the PATCH body. "
            "The field was removed from the UI in OOMPAH-169; the backend "
            "treats all projects as 'shared' without the client needing to send it."
        )

    def test_saveProject_no_flat_default_fallback(self, script: str) -> None:
        body = _get_func_body(script, "saveProject")
        # The old code fell back to 'flat' when no radio was selected
        assert "'flat'" not in body, (
            "saveProject() must not contain a 'flat' default fallback — "
            "the epic-strategy controls were removed in OOMPAH-169."
        )


# ---------------------------------------------------------------------------
# JS — no helper functions for epic strategy remain
# ---------------------------------------------------------------------------


class TestNoEpicStrategyHelpers:
    """No lingering JS helpers that were exclusive to the epic-strategy UI."""

    def test_no_epic_strategy_variable(self, script: str) -> None:
        assert "epicStrategy" not in script, (
            "The epicStrategy JS variable must not exist in projects.html — "
            "it was only used to hold the radio-group selection."
        )

    def test_no_epicStrategyEl_variable(self, script: str) -> None:
        assert "epicStrategyEl" not in script, (
            "The epicStrategyEl JS variable (used to read the radio group) "
            "must be removed from projects.html."
        )
