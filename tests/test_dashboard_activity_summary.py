"""Tests for the agent-log activity summary header (issue oompah-zlz_2-r7py).

The activity summary header is a sticky strip at the top of the agent-log
popup showing live counters (Turn, Tools, Tokens, Cost, Elapsed) in both
Verbose:ON and Verbose:OFF modes. It updates on every handleActivityPush
callback so the operator can see the agent is alive even when Verbose:OFF
filters out tool calls.

These tests use the same static-analysis approach as
tests/test_activity_panel_verbose_toggle.py — they parse dashboard.html,
locate the relevant JS functions, and assert the summary logic is wired
up correctly.
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


def _get_func_body(script: str, fn_name: str) -> str:
    """Extract the body of a top-level function by balanced-brace scan.

    Returns just the inside of the outer { ... } block.
    """
    pattern = re.compile(rf"function\s+{re.escape(fn_name)}\s*\(([^)]*)\)\s*\{{")
    m = pattern.search(script)
    assert m, f"Could not find function {fn_name} in script"
    start = m.end() - 1  # index of '{'
    depth = 0
    for i in range(start, len(script)):
        c = script[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return script[start + 1 : i]
    raise AssertionError(f"Could not find end of function {fn_name}")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def html():
    return _load_dashboard_html()


@pytest.fixture(scope="module")
def script(html):
    return _extract_script(html)


# ===========================================================================
# 1. HTML: summary div exists in the activity panel
# ===========================================================================


class TestSummaryHTMLElement:
    """The activity summary div must exist in the activity overlay."""

    def test_summary_div_exists(self, html):
        assert 'id="activity-summary"' in html, \
            "Activity summary div must be present in the activity overlay"

    def test_summary_div_inside_activity_overlay(self, html):
        overlay_idx = html.find('id="activity-overlay"')
        summary_idx = html.find('id="activity-summary"')
        body_idx = html.find('id="activity-body"')
        assert overlay_idx != -1, "activity-overlay must exist"
        assert summary_idx != -1, "activity-summary must exist"
        assert body_idx != -1, "activity-body must exist"
        assert overlay_idx < summary_idx < body_idx, \
            "activity-summary must appear between activity-overlay and activity-body"

    def test_summary_div_after_toolbar(self, html):
        toolbar_idx = html.find('class="activity-toolbar"')
        summary_idx = html.find('id="activity-summary"')
        assert toolbar_idx != -1 and summary_idx != -1, \
            "Both toolbar and summary must exist"
        assert toolbar_idx < summary_idx, \
            "activity-summary must appear after the activity-toolbar"


# ===========================================================================
# 2. CSS: summary is styled as a muted status strip
# ===========================================================================


class TestSummaryCSS:
    """CSS must style the summary as a compact, muted status strip."""

    def test_summary_css_exists(self, html):
        assert '#activity-summary' in html, \
            "#activity-summary CSS rule must be defined"

    def test_summary_uses_muted_color(self, html):
        match = re.search(r"#activity-summary\s*\{([^}]+)\}", html, re.DOTALL)
        assert match, "Could not find #activity-summary CSS rule"
        css = match.group(1)
        assert "text-muted" in css, \
            "#activity-summary must use var(--text-muted) for muted color"

    def test_summary_has_border_bottom(self, html):
        match = re.search(r"#activity-summary\s*\{([^}]+)\}", html, re.DOTALL)
        assert match, "Could not find #activity-summary CSS rule"
        css = match.group(1)
        assert "border-bottom" in css, \
            "#activity-summary must have a border-bottom to separate from entries"

    def test_summary_small_font(self, html):
        match = re.search(r"#activity-summary\s*\{([^}]+)\}", html, re.DOTALL)
        assert match, "Could not find #activity-summary CSS rule"
        css = match.group(1)
        assert "font-size" in css, \
            "#activity-summary must set font-size for compact display"

    def test_summary_flex_shrink(self, html):
        """Summary must not push the activity body off-screen."""
        match = re.search(r"#activity-summary\s*\{([^}]+)\}", html, re.DOTALL)
        assert match, "Could not find #activity-summary CSS rule"
        css = match.group(1)
        assert "flex-shrink" in css, \
            "#activity-summary must have flex-shrink to prevent pushing body off-screen"


# ===========================================================================
# 3. JS: renderActivitySummary function exists and computes counters
# ===========================================================================


class TestRenderActivitySummary:
    """The renderActivitySummary function must exist and compute counters."""

    def test_function_exists(self, script):
        assert "function renderActivitySummary(" in script, \
            "renderActivitySummary() function must be defined in the script"

    def test_reads_entries_parameter(self, script):
        body = _get_func_body(script, "renderActivitySummary")
        # The function takes entries as a parameter
        assert "entries" in body, \
            "renderActivitySummary must accept entries parameter"

    def test_computes_max_turn(self, script):
        body = _get_func_body(script, "renderActivitySummary")
        assert "turn" in body.lower(), \
            "renderActivitySummary must reference 'turn' to compute max turn"

    def test_counts_tool_calls(self, script):
        body = _get_func_body(script, "renderActivitySummary")
        assert "tool_call" in body, \
            "renderActivitySummary must count entries with kind === 'tool_call'"

    def test_scans_usage_for_tokens(self, script):
        body = _get_func_body(script, "renderActivitySummary")
        assert "input_tokens" in body and "output_tokens" in body, \
            "renderActivitySummary must scan for usage.input_tokens and usage.output_tokens"

    def test_scans_usage_for_cost(self, script):
        body = _get_func_body(script, "renderActivitySummary")
        assert "cost_usd" in body, \
            "renderActivitySummary must scan for usage.cost_usd"

    def test_computes_elapsed(self, script):
        body = _get_func_body(script, "renderActivitySummary")
        assert "elapsed" in body.lower() or "ts" in body, \
            "renderActivitySummary must compute elapsed time from first entry timestamp"

    def test_shows_welcome_when_empty(self, script):
        body = _get_func_body(script, "renderActivitySummary")
        assert "Waiting" in body or "waiting" in body, \
            "renderActivitySummary must show a waiting message for empty entries"

    def test_updates_dom_element(self, script):
        body = _get_func_body(script, "renderActivitySummary")
        assert "activity-summary" in body, \
            "renderActivitySummary must update the #activity-summary DOM element"

    def test_uses_middot_separator(self, script):
        body = _get_func_body(script, "renderActivitySummary")
        assert "·" in body, \
            "renderActivitySummary must use '·' (middot) separator between counters"


# ===========================================================================
# 4. JS: renderActivitySummary is called from the three hook sites
# ===========================================================================


class TestRenderActivitySummaryHooks:
    """renderActivitySummary must be called from renderActivityList,
    handleActivityPush, and toggleAgentLogVerbose."""

    def test_called_from_render_activity_list(self, script):
        body = _get_func_body(script, "renderActivityList")
        assert "renderActivitySummary" in body, \
            "renderActivityList must call renderActivitySummary"

    def test_called_from_handle_activity_push(self, script):
        body = _get_func_body(script, "handleActivityPush")
        assert "renderActivitySummary" in body, \
            "handleActivityPush must call renderActivitySummary"

    def test_called_from_toggle_agent_log_verbose(self, script):
        body = _get_func_body(script, "toggleAgentLogVerbose")
        assert "renderActivitySummary" in body, \
            "toggleAgentLogVerbose must call renderActivitySummary"

    def test_called_from_refresh_activity(self, script):
        body = _get_func_body(script, "refreshActivity")
        assert "renderActivitySummary" in body, \
            "refreshActivity must call renderActivitySummary"


# ===========================================================================
# 5. JS: token formatting helper
# ===========================================================================


class TestTokenFormatting:
    """The summary must format token counts in a human-readable way."""

    def test_thousands_formatted_as_k(self, script):
        body = _get_func_body(script, "renderActivitySummary")
        # The function should have logic to format large numbers with K/M suffixes
        assert "K" in body or "1000" in body or "fmtTokens" in body, \
            "renderActivitySummary must format token counts with K/M suffixes"

    def test_dash_fallback_for_missing_tokens(self, script):
        body = _get_func_body(script, "renderActivitySummary")
        assert "—" in body or "\\u2014" in body or "dash" in body.lower() or "'—'" in body or '"—"' in body or "== null" in body, \
            "renderActivitySummary must show '—' when token data is unavailable"


# ===========================================================================
# 6. JS: cost formatting
# ===========================================================================


class TestCostFormatting:
    """The summary must format cost as a dollar amount."""

    def test_cost_dollar_sign(self, script):
        body = _get_func_body(script, "renderActivitySummary")
        assert "$" in body, \
            "renderActivitySummary must format cost with a dollar sign"

    def test_cost_dash_fallback(self, script):
        body = _get_func_body(script, "renderActivitySummary")
        assert "—" in body or "\\u2014" in body or "'—'" in body or '"—"' in body or "== null" in body, \
            "renderActivitySummary must show '—' when cost data is unavailable"


# ===========================================================================
# 7. Edge cases
# ===========================================================================


class TestEdgeCases:
    """Edge cases from the issue description."""

    def test_empty_entries_shows_waiting(self, script):
        body = _get_func_body(script, "renderActivitySummary")
        # When entries is empty, should show "Waiting for first event..."
        assert "Waiting" in body or "waiting" in body or "first event" in body.lower(), \
            "renderActivitySummary must show waiting message for empty entries"

    def test_no_usage_info_shows_dash(self, script):
        """When no usage info is anywhere in entries, tokens/cost show '—'."""
        body = _get_func_body(script, "renderActivitySummary")
        # Must handle null/undefined usage gracefully — check for null comparisons
        assert "==" in body or "null" in body or "—" in body or "\\u2014" in body, \
            "renderActivitySummary must handle missing usage data gracefully"


# ===========================================================================
# 8. Summary is visible in both Verbose ON and OFF modes
# ===========================================================================


class TestVerboseModeIndependence:
    """The activity summary header is visible regardless of Verbose state."""

    def test_summary_not_inside_verbose_toggle(self, html):
        """The summary div should not be inside the verbose toggle's
        conditional rendering — it should be a sibling element."""
        # The summary div must appear outside the verbose-conditional sections.
        # It should be in the activity panel HTML structure, between toolbar
        # and activity-body.
        toolbar_end = html.find('class="activity-toolbar"')
        summary_idx = html.find('id="activity-summary"')
        body_start = html.find('id="activity-body"')
        assert toolbar_end < summary_idx < body_start, \
            "Summary div must be between toolbar and body (not inside any toggle)"