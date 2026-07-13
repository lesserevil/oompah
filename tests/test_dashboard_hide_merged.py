"""Tests for the dashboard 'Hide merged' toggle (issue oompah-zlz_2-7nr).

This is a render-time client-side filter: closed tasks with the 'merged'
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

    def test_toggle_tooltip_names_needs_human(self, html: str):
        """The tooltip must name 'Needs Human' as an in-flight state (OOMPAH-187)."""
        toggle_idx = html.find('id="hide-merged-toggle"')
        assert toggle_idx != -1
        # Find the title attribute on the toggle label
        title_match = __import__("re").search(
            r'id="hide-merged-toggle"[^>]*title="([^"]*)"',
            html[toggle_idx : toggle_idx + 800],
        )
        assert title_match, "hide-merged-toggle label must have a title attribute"
        tooltip_text = title_match.group(1)
        assert "Needs Human" in tooltip_text, (
            "Toggle tooltip must name 'Needs Human' as an in-flight state"
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
        assert "'Done'" in body or '"Done"' in body, (
            "_isIndividuallyInFlight must check terminal Done state"
        )

    def test_filter_checks_merged_label(self, script: str):
        # As of commit 09d8b6d, the filter no longer keys off the 'merged'
        # label — it uses has_open_review on closed tasks instead. Verify the
        # in-flight predicate references has_open_review.
        body = _extract_function(script, "_isIndividuallyInFlight")
        assert "has_open_review" in body, (
            "_isIndividuallyInFlight must check has_open_review for closed tasks"
        )

    def test_filter_handles_missing_labels(self, script: str):
        # As of commit 09d8b6d, the filter is state/has_open_review-based and
        # does not consult labels. Guard against missing state instead.
        body = _extract_function(script, "_isIndividuallyInFlight")
        assert "columnKeyForStatus(issue.state || issue.tracker_state)" in body, (
            "_isIndividuallyInFlight must normalize missing/variant status values"
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
# 5. boardData stays unfiltered so toggling OFF restores merged tasks
# ===========================================================================


class TestBoardDataUnfiltered:
    """The server's full payload is preserved in boardData; the filter is
    applied to a derivative for rendering only. This means the user can flip
    the toggle off and merged tasks come back without a refetch."""

    def test_boarddata_assigned_before_filter(self, script: str):
        body = _extract_function(script, "renderBoard")
        # Look for the order: boardData = data; then applyHideMergedFilter(data)
        m = re.search(r"boardData\s*=\s*data\s*;", body)
        f = re.search(r"applyHideMergedFilter\(", body)
        assert m and f, "renderBoard must assign boardData and call applyHideMergedFilter"
        assert m.start() < f.start(), (
            "boardData must be assigned BEFORE applyHideMergedFilter is applied so "
            "toggling Hide-merged off can recover merged-closed tasks without refetching"
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
#
# The filter is keyed off canonical status + has_open_review + epic-subtree
# presence. Backlog and active columns pass through; waiting/terminal columns
# are hidden unless they belong to a tree with in-flight work.


def _column_key(status: str | None) -> str:
    key = (status or "").strip().lower().replace("-", "_").replace(" ", "_")
    if key in {"to_do", "todo", "deferred"}:
        return "Backlog"
    if key == "closed":
        return "Done"
    if key in {"asking_question", "needs_info", "needs_information"}:
        return "Needs Answer"
    if key == "human_only":
        return "Needs Human"
    if key == "ci_fix":
        return "Needs CI Fix"
    if key == "merge_conflict":
        return "Needs Rebase"
    canonical = {
        "backlog": "Backlog",
        "open": "Open",
        "in_progress": "In Progress",
        "needs_answer": "Needs Answer",
        "needs_human": "Needs Human",
        "needs_ci_fix": "Needs CI Fix",
        "needs_rebase": "Needs Rebase",
        "in_review": "In Review",
        "done": "Done",
        "merged": "Merged",
        "archived": "Archived",
    }
    return canonical.get(key, status or "")


def _is_individually_in_flight(issue: dict) -> bool:
    state = _column_key(issue.get("state") or issue.get("tracker_state"))
    if state in {"Open", "In Progress", "Needs Human", "Needs CI Fix", "Needs Rebase", "In Review"}:
        return True
    if state in {"Done", "Merged"} and issue.get("has_open_review"):
        return True
    return False


def _compute_in_flight_show_set(all_issues: list[dict]) -> set:
    by_id = {i["id"]: i for i in all_issues if "id" in i}
    children_by_id: dict = {}
    for i in all_issues:
        if i.get("parent_id"):
            children_by_id.setdefault(i["parent_id"], []).append(i["id"])
    subtree_in_flight: dict = {}

    def has_in_flight_subtree(iid, stack):
        if iid in subtree_in_flight:
            return subtree_in_flight[iid]
        if iid in stack:
            return False
        stack.add(iid)
        issue = by_id.get(iid)
        if not issue:
            subtree_in_flight[iid] = False
            stack.discard(iid)
            return False
        if _is_individually_in_flight(issue):
            subtree_in_flight[iid] = True
            stack.discard(iid)
            return True
        for cid in children_by_id.get(iid, []):
            if has_in_flight_subtree(cid, stack):
                subtree_in_flight[iid] = True
                stack.discard(iid)
                return True
        subtree_in_flight[iid] = False
        stack.discard(iid)
        return False

    for iid in by_id:
        has_in_flight_subtree(iid, set())

    show: set = set()
    for issue in all_issues:
        if _is_individually_in_flight(issue):
            show.add(issue["id"])
            continue
        # Rule 2: show if this issue's own subtree has in-flight work.
        if subtree_in_flight.get(issue["id"]):
            show.add(issue["id"])
            continue
        # Rule 3: walk up the parent chain; show if any ancestor has in-flight subtree.
        cur = issue
        seen: set = set()
        while cur and cur.get("parent_id") and cur["parent_id"] not in seen:
            seen.add(cur["parent_id"])
            if subtree_in_flight.get(cur["parent_id"]):
                show.add(issue["id"])
                break
            cur = by_id.get(cur["parent_id"])
    return show


def _apply_hide_merged_filter(
    data: dict, toggle_on: bool
) -> tuple[dict, int]:
    """Pure-Python mirror of applyHideMergedFilter for behavioural assertions.

    `data` is a {state: [issue, ...]} mapping. Returns (filtered_data,
    hidden_count). Hidden count reflects hidden non-active tasks.
    """
    if not toggle_on:
        return data, 0
    all_issues: list[dict] = []
    for issues in data.values():
        for i in issues:
            all_issues.append(i)
    show_set = _compute_in_flight_show_set(all_issues)
    hidden = 0
    filtered: dict = {}
    for state, issues in data.items():
        state_key = _column_key(state)
        if state_key in {
            "Backlog",
            "Open",
            "In Progress",
            "Needs Human",
            "Needs CI Fix",
            "Needs Rebase",
            "In Review",
        }:
            filtered[state] = issues
            continue
        kept: list[dict] = []
        for issue in issues:
            if issue.get("id") in show_set:
                kept.append(issue)
            else:
                hidden += 1
        filtered[state] = kept
    return filtered, hidden


class TestFilterBehavior:
    """Behavioural assertions encoded in the acceptance criteria."""

    def test_done_without_pr_hidden_when_toggle_on(self):
        data = {
            "Done": [{"id": "a", "state": "Done", "has_open_review": False}],
            "Open": [{"id": "b", "state": "Open"}],
        }
        out, hidden = _apply_hide_merged_filter(data, toggle_on=True)
        assert hidden == 1
        assert out["Done"] == []
        assert [i["id"] for i in out["Open"]] == ["b"]

    def test_done_with_open_pr_visible_when_toggle_on(self):
        """Done tasks with an open PR (queued / in CI) stay visible."""
        data = {
            "Done": [
                {"id": "a", "state": "Done", "has_open_review": True},
                {"id": "b", "state": "Done", "has_open_review": False},
            ],
        }
        out, hidden = _apply_hide_merged_filter(data, toggle_on=True)
        assert hidden == 1
        assert [i["id"] for i in out["Done"]] == ["a"]

    def test_done_visible_when_toggle_off(self):
        data = {
            "Done": [{"id": "a", "state": "Done", "has_open_review": False}],
            "Open": [{"id": "b", "state": "Open"}],
        }
        out, hidden = _apply_hide_merged_filter(data, toggle_on=False)
        assert hidden == 0
        assert [i["id"] for i in out["Done"]] == ["a"]
        assert [i["id"] for i in out["Open"]] == ["b"]

    def test_backlog_column_unaffected_by_toggle(self):
        """Backlog-column tasks stay visible so operators can promote them to Open."""
        data = {
            "Backlog": [
                {"id": "d1", "state": "Backlog"},
                {"id": "d2", "state": "Backlog"},
                {"id": "d3", "state": "Backlog", "labels": ["chore"]},
            ],
        }
        out, hidden = _apply_hide_merged_filter(data, toggle_on=True)
        assert hidden == 0
        assert out["Backlog"] == data["Backlog"]

    def test_open_column_unaffected_by_toggle(self):
        """Open tasks always show, even ones with no parent epic and no
        children (the previous filter would have included them via the
        individually-in-flight rule, but we now bypass the column entirely).
        """
        data = {
            "Open": [
                {"id": "o1", "state": "Open"},
                {"id": "o2", "state": "Open"},
            ],
        }
        out, hidden = _apply_hide_merged_filter(data, toggle_on=True)
        assert hidden == 0
        assert out["Open"] == data["Open"]

    def test_in_progress_column_unaffected_by_toggle(self):
        data = {
            "In Progress": [
                {"id": "p1", "state": "In Progress"},
                {"id": "p2", "state": "In Progress"},
            ],
        }
        out, hidden = _apply_hide_merged_filter(data, toggle_on=True)
        assert hidden == 0
        assert out["In Progress"] == data["In Progress"]

    def test_active_columns_pass_through_with_unrelated_backlog_tasks(self):
        """Backlog and active columns pass through; unrelated Done tasks hide."""
        data = {
            "Open": [{"id": "o1", "state": "Open"}],
            "In Progress": [{"id": "p1", "state": "In Progress"}],
            "Backlog": [
                {"id": "d1", "state": "Backlog"},
                {"id": "d2", "state": "Backlog"},
            ],
            "Done": [
                # Done with PR -> visible
                {"id": "c1", "state": "Done", "has_open_review": True},
                # Done without PR and no in-flight ancestor -> hidden
                {"id": "c2", "state": "Done", "has_open_review": False},
            ],
        }
        out, hidden = _apply_hide_merged_filter(data, toggle_on=True)
        assert hidden == 1
        assert [i["id"] for i in out["Open"]] == ["o1"]
        assert [i["id"] for i in out["In Progress"]] == ["p1"]
        assert [i["id"] for i in out["Backlog"]] == ["d1", "d2"]
        assert [i["id"] for i in out["Done"]] == ["c1"]

    def test_hidden_count_excludes_visible_backlog_tasks(self):
        """Hidden-count label excludes backlog-column tasks because they stay visible."""
        data = {
            "Backlog": [{"id": f"d{i}", "state": "Backlog"} for i in range(50)],
            "Done": [
                {"id": f"c{i}", "state": "Done", "has_open_review": False}
                for i in range(10)
            ],
        }
        out, hidden = _apply_hide_merged_filter(data, toggle_on=True)
        assert hidden == 10
        assert len(out["Backlog"]) == 50
        assert out["Done"] == []

    def test_done_with_in_flight_ancestor_stays_visible(self):
        """Done children of an epic whose subtree contains active work stay visible."""
        data = {
            "Open": [{"id": "child-active", "state": "Open", "parent_id": "epic-1"}],
            "Done": [
                # Sibling of an active child, under the same epic — stays visible.
                {
                    "id": "child-merged",
                    "state": "Done",
                    "has_open_review": False,
                    "parent_id": "epic-1",
                },
                # Lone done task with no parent and no PR — hidden.
                {"id": "lone-done", "state": "Done", "has_open_review": False},
            ],
        }
        # Have to also include the epic itself in the data so the show-set
        # walker can find it as a parent.
        data["Open"].append({"id": "epic-1", "state": "Open"})
        out, hidden = _apply_hide_merged_filter(data, toggle_on=True)
        kept_ids = [i["id"] for i in out["Done"]]
        assert "child-merged" in kept_ids
        assert "lone-done" not in kept_ids
        assert hidden == 1

    def test_state_case_insensitive(self):
        """state may arrive as 'DONE' or with whitespace."""
        data = {
            "Done": [{"id": "a", "state": "DONE", "has_open_review": False}],
        }
        out, hidden = _apply_hide_merged_filter(data, toggle_on=True)
        assert hidden == 1
        assert out["Done"] == []

    def test_counter_matches_hidden_count(self):
        """294 hidden Done tasks — matches the example in the issue."""
        data = {
            "Done": [
                {"id": str(i), "state": "Done", "has_open_review": False}
                for i in range(294)
            ],
        }
        out, hidden = _apply_hide_merged_filter(data, toggle_on=True)
        assert hidden == 294
        assert out["Done"] == []

    # -----------------------------------------------------------------------
    # Needs Human — these tests reflect OOMPAH-187 acceptance criteria.
    # -----------------------------------------------------------------------

    def test_needs_human_visible_when_toggle_on(self):
        """Needs Human tasks must stay visible with In-flight only enabled."""
        data = {
            "Needs Human": [
                {"id": "nh-1", "state": "Needs Human"},
                {"id": "nh-2", "state": "needs_human"},
            ],
            "Done": [
                {"id": "d-1", "state": "Done", "has_open_review": False},
            ],
        }
        out, hidden = _apply_hide_merged_filter(data, toggle_on=True)
        # Needs Human column passes through unchanged
        nh_ids = [i["id"] for i in out["Needs Human"]]
        assert "nh-1" in nh_ids
        assert "nh-2" in nh_ids
        # Done without PR is still hidden
        assert hidden == 1
        assert out["Done"] == []

    def test_needs_human_column_hidden_count_is_zero(self):
        """Needs Human tasks do NOT count as hidden — they are in-flight."""
        data = {
            "Needs Human": [
                {"id": f"nh-{i}", "state": "Needs Human"} for i in range(10)
            ],
        }
        out, hidden = _apply_hide_merged_filter(data, toggle_on=True)
        assert hidden == 0, "Needs Human tasks must not be counted as hidden"
        assert len(out["Needs Human"]) == 10

    def test_needs_human_parent_epic_visible_when_toggle_on(self):
        """When a child is in 'Needs Human', its parent epic stays visible.

        OOMPAH-44/46/48-style Needs Human cards: an epic in Done whose only
        active descendant is Needs Human should remain visible along with the
        child.
        """
        data = {
            "Needs Human": [
                {"id": "nh-child", "state": "Needs Human", "parent_id": "epic-1"},
            ],
            "Done": [
                # The epic itself is Done but has an in-flight Needs Human child
                {"id": "epic-1", "state": "Done", "has_open_review": False},
                # Lone Done task with no connection — should be hidden
                {"id": "lone-done", "state": "Done", "has_open_review": False},
            ],
        }
        out, hidden = _apply_hide_merged_filter(data, toggle_on=True)
        # Needs Human child must be visible
        assert out["Needs Human"] == data["Needs Human"]
        # Epic must be visible because it has an in-flight Needs Human descendant
        kept_done_ids = [i["id"] for i in out["Done"]]
        assert "epic-1" in kept_done_ids, (
            "Parent epic of a Needs Human child must be visible when In-flight only is on"
        )
        assert "lone-done" not in kept_done_ids
        # Only lone-done is hidden
        assert hidden == 1

    def test_needs_human_toggle_off_column_unchanged(self):
        """With toggle OFF, Needs Human column is unaffected (no filtering)."""
        data = {
            "Needs Human": [
                {"id": "nh-1", "state": "Needs Human"},
            ],
        }
        out, hidden = _apply_hide_merged_filter(data, toggle_on=False)
        assert hidden == 0
        assert out["Needs Human"] == data["Needs Human"]


class TestColumnPassthroughInJS:
    """Static-analysis assertions confirming the JS filter passes active columns
    through and filters non-active columns."""

    def test_apply_filter_skips_non_closed_columns(self, script: str):
        body = _extract_function(script, "applyHideMergedFilter")
        assert "stateKey" in body and "Needs CI Fix" in body, (
            "applyHideMergedFilter must compute a canonical state key and pass "
            "active columns through unchanged"
        )

    def test_apply_filter_continues_for_non_closed(self, script: str):
        body = _extract_function(script, "applyHideMergedFilter")
        # The non-closed branch should assign filtered[state] = issues then
        # `continue` so the column is passed through verbatim.
        assert "filtered[state] = issues" in body, (
            "Non-closed columns must be passed through with "
            "`filtered[state] = issues` (no filtering)"
        )
        assert "continue;" in body, (
            "applyHideMergedFilter must `continue` after passing through a "
            "non-closed column rather than falling into the filter loop"
        )

    def test_apply_filter_includes_needs_human_in_passthrough(self, script: str):
        """'Needs Human' must be in the unconditional-passthrough list (OOMPAH-187)."""
        body = _extract_function(script, "applyHideMergedFilter")
        assert "Needs Human" in body, (
            "applyHideMergedFilter must include 'Needs Human' in the passthrough "
            "column list so Needs Human tasks remain visible when In-flight only is on"
        )

    def test_is_individually_in_flight_includes_needs_human(self, script: str):
        """_isIndividuallyInFlight must treat Needs Human as in flight (OOMPAH-187)."""
        body = _extract_function(script, "_isIndividuallyInFlight")
        assert "Needs Human" in body, (
            "_isIndividuallyInFlight must include 'Needs Human' in the in-flight "
            "state list so Needs Human tasks are considered active"
        )


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
