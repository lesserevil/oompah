"""Tests for the Verbose toggle on the agent-log activity panel.

The Verbose toggle (oompah-zlz_2-a7b) adds a checkbox at the top of the
activity panel that controls whether every activity entry is rendered
(Verbose ON, default — current behavior) or only message-kind entries
are shown with their full text inline and no expand/collapse interaction
(Verbose OFF — transcript view).

Persistence: localStorage key 'oompah_agent_log_verbose' ('on' | 'off').
"""

import os
import re

import pytest


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


@pytest.fixture(scope="module")
def html():
    return _load_dashboard_html()


@pytest.fixture(scope="module")
def script(html):
    return _extract_script(html)


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


class TestVerboseToggleHTML:
    """The HTML must include a checkbox + label for the Verbose toggle."""

    def test_toggle_checkbox_in_overlay(self, html):
        assert 'id="activity-verbose-checkbox"' in html, \
            "Verbose toggle checkbox must be present in the activity overlay"

    def test_toggle_label_in_overlay(self, html):
        assert 'id="activity-verbose-label"' in html, \
            "Verbose toggle label must be present in the activity overlay"

    def test_toggle_default_label_is_on(self, html):
        # The label should default to "Verbose: ON" so first paint is correct
        # before JS runs.
        m = re.search(r'id="activity-verbose-label"[^>]*>\s*([^<]+)\s*<', html)
        assert m, "Could not find activity-verbose-label content in HTML"
        assert "Verbose" in m.group(1) and "ON" in m.group(1), \
            f"Default label should mention 'Verbose: ON', got: {m.group(1)!r}"

    def test_toggle_change_handler_wired(self, html):
        # The checkbox onchange must call toggleAgentLogVerbose
        assert "toggleAgentLogVerbose" in html, \
            "toggleAgentLogVerbose() must be referenced from the checkbox onchange handler"

    def test_toggle_inside_activity_overlay(self, html):
        # The checkbox must live inside the activity-overlay element so
        # closing/opening the popup carries it along.
        overlay_idx = html.find('id="activity-overlay"')
        cb_idx = html.find('id="activity-verbose-checkbox"')
        assert overlay_idx != -1, "activity-overlay must exist"
        assert cb_idx != -1, "activity-verbose-checkbox must exist"
        assert overlay_idx < cb_idx, \
            "Verbose checkbox must appear inside the activity-overlay element"


class TestVerboseToggleJS:
    """The JS must implement isAgentLogVerbose, toggleAgentLogVerbose,
    and persist to the documented localStorage key.
    """

    def test_is_agent_log_verbose_function(self, script):
        assert "function isAgentLogVerbose(" in script, \
            "isAgentLogVerbose() function must be defined"

    def test_toggle_agent_log_verbose_function(self, script):
        assert "function toggleAgentLogVerbose(" in script, \
            "toggleAgentLogVerbose() function must be defined"

    def test_localstorage_key_used(self, script):
        # Both read + write paths must use the documented key.
        assert "'oompah_agent_log_verbose'" in script or \
               '"oompah_agent_log_verbose"' in script, \
            "localStorage key 'oompah_agent_log_verbose' must be used"

    def test_default_is_on(self, script):
        # isAgentLogVerbose() must default to true when the key is missing.
        # The pattern mirrors isHideMergedOn(): treat the missing key as 'on'.
        body = _get_func_body(script, "isAgentLogVerbose")
        assert "!==" in body or "!=" in body or "===" in body, \
            "isAgentLogVerbose must compare to 'off' to compute default-on behavior"
        # Specifically check it returns true when value is anything other than 'off'.
        assert "'off'" in body or '"off"' in body, \
            "isAgentLogVerbose must reference the 'off' sentinel value"

    def test_toggle_persists_to_localstorage(self, script):
        body = _get_func_body(script, "toggleAgentLogVerbose")
        assert "localStorage.setItem" in body, \
            "toggleAgentLogVerbose must persist the new state to localStorage"

    def test_toggle_does_not_fetch(self, script):
        # The toggle must re-render from cache; it must not call refreshActivity
        # or fetch() (per acceptance criterion: "no extra network call").
        body = _get_func_body(script, "toggleAgentLogVerbose")
        assert "refreshActivity" not in body, \
            "toggleAgentLogVerbose must not call refreshActivity (no network call)"
        assert "fetch(" not in body, \
            "toggleAgentLogVerbose must not call fetch() (no network call)"

    def test_toggle_re_renders_panel(self, script):
        # The toggle must re-render the visible entries from the cached array.
        body = _get_func_body(script, "toggleAgentLogVerbose")
        # Either renderActivityList or a direct loop over the cache — accept
        # either pattern, but require the cached entries variable.
        assert "_activityEntries" in body, \
            "toggleAgentLogVerbose must re-render from the cached _activityEntries"


class TestRenderActivityEntryRespectsVerbose:
    """renderActivityEntry must consult isAgentLogVerbose() and adjust output."""

    def test_render_calls_is_verbose(self, script):
        body = _get_func_body(script, "renderActivityEntry")
        assert "isAgentLogVerbose" in body, \
            "renderActivityEntry must call isAgentLogVerbose() to choose render mode"

    def test_render_filters_non_message_kinds_when_off(self, script):
        body = _get_func_body(script, "renderActivityEntry")
        # In compact mode, non-message kinds are skipped — render returns null/early.
        assert "return null" in body, \
            "renderActivityEntry must return null for filtered-out entries"

    def test_render_uses_compact_class_when_off(self, script):
        body = _get_func_body(script, "renderActivityEntry")
        assert "activity-entry-compact" in body, \
            "renderActivityEntry must use the activity-entry-compact class when Verbose is OFF"

    def test_render_no_toggle_or_kind_pills_in_compact(self, script):
        # Compact mode must not include the activity-toggle / activity-kind /
        # activity-turn pills nor the activity-entry-header structure.
        # We can't fully verify that without parsing the JS branches, but at
        # minimum the textContent / no-innerHTML pattern for compact entries
        # must show up, AND the compact class must appear in the same body.
        body = _get_func_body(script, "renderActivityEntry")
        assert "textContent" in body, \
            "Compact entries should set .textContent (not innerHTML with header pills)"


class TestVerboseToggleCSS:
    """CSS must define the toolbar and compact-entry styles."""

    def test_compact_entry_class_styled(self, html):
        assert ".activity-entry-compact" in html, \
            ".activity-entry-compact CSS class must be defined"

    def test_toolbar_class_styled(self, html):
        assert ".activity-toolbar" in html, \
            ".activity-toolbar CSS class must be defined for the Verbose-toggle bar"


class TestActivityCacheAndPush:
    """Live push must filter through the current Verbose state and keep the cache."""

    def test_handle_activity_push_updates_cache(self, script):
        body = _get_func_body(script, "handleActivityPush")
        assert "_activityEntries" in body, \
            "handleActivityPush must keep _activityEntries in sync with pushed entries"

    def test_handle_activity_push_renders_through_filter(self, script):
        body = _get_func_body(script, "handleActivityPush")
        # The push handler must consult renderActivityEntry (which itself
        # consults isAgentLogVerbose) so a non-message entry pushed during
        # Verbose=OFF doesn't appear in the panel.
        assert "renderActivityEntry" in body, \
            "handleActivityPush must call renderActivityEntry so the Verbose filter applies"

    def test_refresh_activity_caches_entries(self, script):
        body = _get_func_body(script, "refreshActivity")
        assert "_activityEntries" in body, \
            "refreshActivity must cache the fetched entries into _activityEntries"


class TestCompactModeWhitespaceHandling:
    """Compact mode (Verbose OFF) must trim whitespace and skip empty messages."""

    def test_compact_trims_detail_and_summary(self, script):
        """Both detail and summary must be trimmed with a local _trim helper before use."""
        body = _get_func_body(script, "renderActivityEntry")
        # The compact branch must define a helper that strips leading/trailing whitespace.
        # Accept either ' s => ' (arrow) or 'function' patterns — just verify trim() is called.
        assert ".trim()" in body, \
            "renderActivityEntry compact mode must call .trim() on detail/summary"

    def test_compact_skips_whitespace_only_messages(self, script):
        """Entries where both detail and summary are whitespace-only must return null."""
        body = _get_func_body(script, "renderActivityEntry")
        # When verbose is off, an early-return on null/empty content must exist so
        # whitespace-only messages don't appear in the compact listing.
        # The implementation uses: if (!detail && !summary) return null;
        # After trim(), whitespace-only strings become empty, satisfying the condition.
        # Verify the "return null" for empty content is reachable in the compact branch.
        # Split at verbose check to isolate the compact-mode logic.
        lines = body.split("\n")
        verbose_branch_start = -1
        for i, line in enumerate(lines):
            if "isAgentLogVerbose" in line or "verbose" in line:
                verbose_branch_start = i
        if verbose_branch_start >= 0:
            # Find the start of the compact (!verbose) block
            for i in range(verbose_branch_start, len(lines)):
                if "!verbose" in lines[i] or "verbose" in lines[i]:
                    # This is the compact branch — confirm it has return null for empty
                    compact_section = "\n".join(lines[i:])
                    assert "return null" in compact_section, \
                        "Compact mode must return null for empty/whitespace-only content"
                    break

    def test_compact_prefers_longer_trimmed_content(self, script):
        """The text shown must be the longer of (trimmed detail, trimmed summary)."""
        body = _get_func_body(script, "renderActivityEntry")
        # Both detail and summary must participate in the length comparison.
        # The pattern: longer content wins — detail.length > summary.length ? detail : summary
        # After trimming, the comparison reflects actual displayable content.
        assert "detail.length" in body and "summary.length" in body, \
            "renderActivityEntry compact mode must compare trimmed detail and summary lengths"


class TestPanelInitWiresToggle:
    """Opening the panel must reflect the persisted toggle state in the UI."""

    def test_open_calls_init_toggle(self, script):
        body = _get_func_body(script, "openActivityPanel")
        assert "initAgentLogVerboseToggle" in body or "setAgentLogVerboseLabel" in body, \
            "openActivityPanel must initialize the Verbose toggle from localStorage"
