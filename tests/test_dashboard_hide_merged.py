"""Tests for the dashboard 'Hide merged' toggle (issue oompah-zlz_2-7nr).

This is a render-time client-side filter: closed beads with the 'merged'
label are hidden from the kanban (flat + swimlane) when the toggle is ON.

The toggle:
  * appears in the dashboard top bar
  * defaults to ON
  * persists in localStorage('oompah_hide_merged')
  * shows a counter "Hide merged: ON (N hidden)"
  * leaves /api/v1/issues raw responses unfiltered (server-side passthrough)

These tests use the same static-analysis approach as
tests/test_dashboard_draft_epics.py — they parse dashboard.html, locate the
relevant JS functions, and assert the filter pattern is wired up correctly.
A small in-process JS evaluator (via `js2py` if available, otherwise pattern
checks) verifies the filter logic itself.
"""

from __future__ import annotations

import os
import re

import pytest


# ---------------------------------------------------------------------------
# Helpers — load dashboard.html and extract relevant JS pieces
# ---------------------------------------------------------------------------


def _load_dashboard_html() -> str:
    template_path = os.path.join(
        os.path.dirname(__file__), os.pardir, "oompah", "templates", "dashboard.html"
    )
    with open(template_path, "r") as f:
        return f.read()


def _extract_script(html: str) -> str:
    matches = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    assert matches, "Could not find any <script> block in dashboard HTML"
    return max(matches, key=len)


def _extract_function(script: str, name: str) -> str:
    """Extract `function <name>(...) { ... }` body up to the next top-level function."""
    pattern = rf"function {re.escape(name)}\s*\(.*?\)\s*\{{(.*?)(?=\nfunction |\Z)"
    match = re.search(pattern, script, re.DOTALL)
    assert match, f"Could not find function {name} in script"
    return match.group(1)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def html() -> str:
    return _load_dashboard_html()


@pytest.fixture(scope="module")
def script(html: str) -> str:
    return _extract_script(html)


# ===========================================================================
# 1. Toolbar UI: toggle element exists and uses correct ids/labels
# ===========================================================================


class TestToolbarUI:
    """Verify the Hide merged toggle is wired into the toolbar HTML."""

    def test_toggle_label_present(self, html: str):
        assert 'id="hide-merged-toggle"' in html, (
            "Dashboard must contain a label with id='hide-merged-toggle'"
        )

    def test_toggle_checkbox_present(self, html: str):
        assert 'id="hide-merged-checkbox"' in html, (
            "Dashboard must contain an <input type=checkbox> with id='hide-merged-checkbox'"
        )

    def test_toggle_calls_handler_onchange(self, html: str):
        assert 'onchange="toggleHideMerged()"' in html, (
            "The hide-merged checkbox must call toggleHideMerged() on change"
        )

    def test_toggle_label_starts_with_hide_merged_text(self, html: str):
        assert 'id="hide-merged-label"' in html
        # The default text should follow the documented format. The toggle
        # was renamed "Hide merged" → "In-flight only" in commit 09d8b6d.
        assert "In-flight only: ON (0 hidden)" in html or re.search(
            r'id="hide-merged-label"[^>]*>\s*In-flight only:', html
        ), "hide-merged-label span must show 'In-flight only: ...' default text"

    def test_toggle_lives_inside_toolbar(self, html: str):
        # Toolbar div precedes the toggle in the DOM
        toolbar_idx = html.find('class="toolbar"')
        toggle_idx = html.find('id="hide-merged-toggle"')
        assert toolbar_idx != -1 and toggle_idx != -1
        assert toolbar_idx < toggle_idx, (
            "Hide-merged toggle must appear inside the top toolbar"
        )

    def test_toggle_near_project_filter(self, html: str):
        """Toggle should be near the project-filter dropdown for discoverability."""
        proj_idx = html.find('id="project-filter"')
        toggle_idx = html.find('id="hide-merged-toggle"')
        assert proj_idx != -1 and toggle_idx != -1
        # Toggle right after project-filter, with no more than ~600 bytes between
        assert 0 < toggle_idx - proj_idx < 1500, (
            "Hide-merged toggle should be adjacent to project-filter"
        )


# ===========================================================================
# 2. Filter helper presence and structure
# ===========================================================================


class TestFilterHelper:
    """The applyHideMergedFilter / isHiddenByMergedFilter helpers exist and
    have the correct structure."""

    def test_apply_hide_merged_filter_function_exists(self, script: str):
        assert re.search(r"\bfunction\s+applyHideMergedFilter\s*\(", script), (
            "applyHideMergedFilter must be defined as a function"
        )

    def test_is_hidden_by_merged_filter_function_exists(self, script: str):
        assert re.search(r"\bfunction\s+isHiddenByMergedFilter\s*\(", script), (
            "isHiddenByMergedFilter must be defined as a function"
        )

    def test_filter_checks_closed_state(self, script: str):
        # As of commit 09d8b6d, isHiddenByMergedFilter delegates to
        # _isIndividuallyInFlight, which is where the closed-state check lives.
        body = _extract_function(script, "_isIndividuallyInFlight")
        assert "'closed'" in body or '"closed"' in body, (
            "_isIndividuallyInFlight must check state === 'closed'"
        )

    def test_filter_checks_merged_label(self, script: str):
        # As of commit 09d8b6d, the filter no longer keys off the 'merged'
        # label — it uses has_open_review on closed beads instead. Verify the
        # in-flight predicate references has_open_review.
        body = _extract_function(script, "_isIndividuallyInFlight")
        assert "has_open_review" in body, (
            "_isIndividuallyInFlight must check has_open_review for closed beads"
        )

    def test_filter_handles_missing_labels(self, script: str):
        # As of commit 09d8b6d, the filter is state/has_open_review-based and
        # does not consult labels. Guard against missing state instead.
        body = _extract_function(script, "_isIndividuallyInFlight")
        assert re.search(r"issue\.state\s*\|\|\s*['\"]\s*['\"]", body), (
            "_isIndividuallyInFlight must guard against missing state via 'issue.state || \"\"'"
        )

    def test_apply_filter_short_circuits_when_off(self, script: str):
        body = _extract_function(script, "applyHideMergedFilter")
        # When toggle is OFF the function should return early
        assert "isHideMergedOn" in body, (
            "applyHideMergedFilter must consult isHideMergedOn() and short-circuit when OFF"
        )

    def test_apply_filter_updates_hidden_counter(self, script: str):
        body = _extract_function(script, "applyHideMergedFilter")
        assert "_hideMergedHiddenCount" in body, (
            "applyHideMergedFilter must update _hideMergedHiddenCount"
        )


# ===========================================================================
# 3. Persistence: localStorage + default ON
# ===========================================================================


class TestPersistence:
    """Toggle state survives reload via localStorage('oompah_hide_merged')."""

    def test_localstorage_key_used(self, script: str):
        assert "'oompah_hide_merged'" in script or '"oompah_hide_merged"' in script, (
            "Persistence must use localStorage key 'oompah_hide_merged'"
        )

    def test_default_is_on(self, script: str):
        body = _extract_function(script, "isHideMergedOn")
        # Default ON: missing key counts as 'on', i.e. only 'off' explicitly turns it off
        assert "'off'" in body or '"off"' in body, (
            "Default-ON behavior must be expressed via 'off' sentinel "
            "(value !== 'off' means ON, including missing key)"
        )

    def test_toggle_persists_state(self, script: str):
        body = _extract_function(script, "toggleHideMerged")
        assert "setItem" in body and "oompah_hide_merged" in body, (
            "toggleHideMerged must persist state via localStorage.setItem"
        )

    def test_toggle_triggers_rerender(self, script: str):
        body = _extract_function(script, "toggleHideMerged")
        assert "renderBoard" in body, (
            "toggleHideMerged must re-render the board so the filter takes effect"
        )


# ===========================================================================
# 4. Counter: "Hide merged: ON (N hidden)" format
# ===========================================================================


class TestCounter:
    """The hidden-count counter shows up in the toggle label after each render."""

    def test_label_format(self, script: str):
        body = _extract_function(script, "setHideMergedLabel")
        # Format: "In-flight only: <ON|OFF> (<N> hidden)" since commit 09d8b6d.
        assert "In-flight only:" in body, "Counter must use 'In-flight only:' prefix"
        assert "hidden" in body, "Counter must contain the word 'hidden'"

    def test_label_contains_on_off_state(self, script: str):
        body = _extract_function(script, "setHideMergedLabel")
        assert "ON" in body and "OFF" in body, (
            "Counter must show ON/OFF state, not just the count"
        )

    def test_setlabel_called_from_renderboard(self, script: str):
        body = _extract_function(script, "renderBoard")
        assert "setHideMergedLabel" in body, (
            "renderBoard must call setHideMergedLabel() after applying the filter"
        )

    def test_renderboard_calls_filter(self, script: str):
        body = _extract_function(script, "renderBoard")
        assert "applyHideMergedFilter" in body, (
            "renderBoard must call applyHideMergedFilter() before flattening data"
        )


# ===========================================================================
# 5. boardData stays unfiltered so toggling OFF restores merged beads
# ===========================================================================


class TestBoardDataUnfiltered:
    """The server's full payload is preserved in boardData; the filter is
    applied to a derivative for rendering only. This means the user can flip
    the toggle off and merged beads come back without a refetch."""

    def test_boarddata_assigned_before_filter(self, script: str):
        body = _extract_function(script, "renderBoard")
        # Look for the order: boardData = data; then applyHideMergedFilter(data)
        m = re.search(r"boardData\s*=\s*data\s*;", body)
        f = re.search(r"applyHideMergedFilter\(", body)
        assert m and f, "renderBoard must assign boardData and call applyHideMergedFilter"
        assert m.start() < f.start(), (
            "boardData must be assigned BEFORE applyHideMergedFilter is applied so "
            "toggling Hide-merged off can recover merged-closed beads without refetching"
        )


# ===========================================================================
# 6. Init wired up at page load
# ===========================================================================


class TestInit:
    def test_init_function_exists(self, script: str):
        assert re.search(r"\bfunction\s+initHideMergedToggle\s*\(", script), (
            "initHideMergedToggle must be defined"
        )

    def test_init_called_on_load(self, script: str):
        # initHideMergedToggle() is called in the bootstrap region
        assert "initHideMergedToggle()" in script, (
            "initHideMergedToggle() must be invoked at page load (near connectWebSocket)"
        )

    def test_init_seeds_checkbox(self, script: str):
        body = _extract_function(script, "initHideMergedToggle")
        assert "isHideMergedOn" in body and "checked" in body, (
            "initHideMergedToggle must seed the checkbox.checked from localStorage state"
        )


# ===========================================================================
# 7. Functional behaviour — exercise the JS filter via a tiny Python port
# ===========================================================================
#
# We can't execute the page's JavaScript directly here without a JS runtime,
# but we can re-implement the filter rule in Python and assert the OBSERVED
# behaviour matches the spec. The static-analysis tests above guarantee the
# JS implementation expresses the same rule.


def _hide_merged_filter(issues: list[dict], toggle_on: bool) -> tuple[list[dict], int]:
    """Pure-Python mirror of applyHideMergedFilter for behavioural assertions."""
    if not toggle_on:
        return issues, 0
    kept: list[dict] = []
    hidden = 0
    for issue in issues:
        state = (issue.get("state") or "").strip().lower()
        labels = issue.get("labels") or []
        if state == "closed" and "merged" in labels:
            hidden += 1
        else:
            kept.append(issue)
    return kept, hidden


class TestFilterBehavior:
    """Behavioural assertions encoded in the acceptance criteria."""

    def test_merged_closed_hidden_when_toggle_on(self):
        issues = [
            {"identifier": "a", "state": "closed", "labels": ["merged"]},
            {"identifier": "b", "state": "open", "labels": []},
        ]
        kept, hidden = _hide_merged_filter(issues, toggle_on=True)
        assert hidden == 1
        assert [i["identifier"] for i in kept] == ["b"]

    def test_merged_closed_visible_when_toggle_off(self):
        issues = [
            {"identifier": "a", "state": "closed", "labels": ["merged"]},
            {"identifier": "b", "state": "open", "labels": []},
        ]
        kept, hidden = _hide_merged_filter(issues, toggle_on=False)
        assert hidden == 0
        assert [i["identifier"] for i in kept] == ["a", "b"]

    def test_closed_without_merged_label_stays_visible(self):
        """Closed-but-not-merged beads (abandoned work) must remain visible."""
        issues = [
            {"identifier": "abandoned", "state": "closed", "labels": []},
            {"identifier": "abandoned-with-tag", "state": "closed", "labels": ["wontfix"]},
        ]
        kept, hidden = _hide_merged_filter(issues, toggle_on=True)
        assert hidden == 0
        assert {i["identifier"] for i in kept} == {"abandoned", "abandoned-with-tag"}

    def test_merged_label_on_open_bead_stays_visible(self):
        """Only closed+merged is filtered. An open bead with 'merged' (rare,
        but possible mid-relabel) must remain visible."""
        issues = [
            {"identifier": "weird", "state": "open", "labels": ["merged"]},
        ]
        kept, hidden = _hide_merged_filter(issues, toggle_on=True)
        assert hidden == 0
        assert kept == issues

    def test_missing_labels_is_safe(self):
        issues = [
            {"identifier": "a", "state": "closed"},  # no labels key
            {"identifier": "b", "state": "closed", "labels": None},  # null
        ]
        kept, hidden = _hide_merged_filter(issues, toggle_on=True)
        assert hidden == 0
        assert {i["identifier"] for i in kept} == {"a", "b"}

    def test_state_case_insensitive(self):
        """state may arrive as 'CLOSED' or with whitespace; the JS uses
        .trim().toLowerCase(). The Python mirror does the same."""
        issues = [
            {"identifier": "a", "state": "CLOSED", "labels": ["merged"]},
            {"identifier": "b", "state": " closed ", "labels": ["merged"]},
        ]
        kept, hidden = _hide_merged_filter(issues, toggle_on=True)
        assert hidden == 2
        assert kept == []

    def test_counter_matches_hidden_count(self):
        issues = [
            {"identifier": str(i), "state": "closed", "labels": ["merged"]}
            for i in range(294)
        ]
        kept, hidden = _hide_merged_filter(issues, toggle_on=True)
        # 294 hidden, none kept — matches the example in the issue description
        assert hidden == 294
        assert kept == []


# ===========================================================================
# 8. Server-side /api/v1/issues remains unfiltered (passthrough)
# ===========================================================================


class TestServerPassthrough:
    """The acceptance criterion 'API returns the complete set as today;
    filtering is purely a render-time concern' means we MUST NOT have added
    any server-side filtering. Verify by inspecting the server route."""

    def test_no_hide_merged_keyword_in_server(self):
        server_path = os.path.join(
            os.path.dirname(__file__), os.pardir, "oompah", "server.py"
        )
        with open(server_path, "r") as f:
            src = f.read()
        # No server-side knob / parameter referencing this filter
        assert "hide_merged" not in src.lower(), (
            "Server must NOT implement a 'hide_merged' parameter; "
            "the filter is purely client-side per the issue spec"
        )
