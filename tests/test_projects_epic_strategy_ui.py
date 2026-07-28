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


# Keep all page-level remnants of the retired selector in one contract.  The
# saveProject() body has a separate contract below because unrelated page code
# may legitimately contain strategy-shaped data in the future.
EPIC_STRATEGY_FORBIDDEN_MARKERS = {
    "epic-strategy group CSS class": ".epic-strategy-group",
    "epic-strategy option CSS class": ".epic-strategy-option",
    "epic-strategy name CSS class": ".epic-strategy-name",
    "epic-strategy description CSS class": ".epic-strategy-desc",
    "epic-strategy tag CSS class": ".epic-strategy-tag",
    "epic-strategy label CSS class": ".epic-strategy-label",
    "epic-strategy group HTML class": "epic-strategy-group",
    "Epic Strategy display label": "Epic Strategy",
    "flat strategy radio value": 'value="flat"',
    "stacked strategy radio value": 'value="stacked"',
    "epic-strategy radio group": "edit-epic-strategy",
    "epicStrategyEl helper variable": "epicStrategyEl",
    "epicStrategy helper variable": "epicStrategy",
}

SAVE_PROJECT_EPIC_STRATEGY_FORBIDDEN_MARKERS = {
    "epic-strategy radio selector": "epic-strategy",
    "epic_strategy PATCH field": "epic_strategy",
    "flat strategy fallback": "'flat'",
    "stacked strategy fallback": "'stacked'",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def html() -> str:
    return _load_projects_html()


@pytest.fixture(scope="module")
def script(html: str) -> str:
    return _extract_main_script(html)


def test_projects_page_epic_strategy_markers_absent(html: str) -> None:
    """The projects page contains none of the retired selector controls."""
    for marker_name, marker in EPIC_STRATEGY_FORBIDDEN_MARKERS.items():
        assert marker not in html, (
            f"Retired epic-strategy marker {marker_name} ({marker!r}) "
            "must remain absent from projects.html (OOMPAH-169)"
        )


def test_save_project_does_not_submit_epic_strategy(script: str) -> None:
    """saveProject() cannot read or submit the retired epic-strategy field."""
    body = _get_func_body(script, "saveProject")
    assert body, "saveProject must be defined in projects.html"
    for marker_name, marker in SAVE_PROJECT_EPIC_STRATEGY_FORBIDDEN_MARKERS.items():
        assert marker not in body, (
            f"saveProject() contains retired epic-strategy marker "
            f"{marker_name} ({marker!r}); the projects page must not submit it"
        )
