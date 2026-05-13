"""Static-template smoke tests for the console dashboard UI panel
(oompah-zlz_2-577a).

These tests parse oompah/templates/dashboard.html and assert that:

* The DOM nodes the console panel relies on exist.
* The JS render helpers for the 8 normalized event kinds are defined.
* The CSS classes for per-kind styling are present.
* The header has a backend dropdown, token meter, Clear button and
  WS-reconnect/backfill plumbing is wired up.

We follow the same pattern as tests/test_dashboard_activity_summary.py
— pure HTML + JS source inspection, no browser, no orchestrator.

Behavior-level tests (transcript round-trip, backend switch 409, WS
push) live alongside the bead-detail tests under
``tests/test_console_session.py`` and ``tests/test_console_endpoints.py``
— this file is intentionally limited to template-shape assertions.
"""

from __future__ import annotations

import os
import re

import pytest


# ---------------------------------------------------------------------------
# Helpers
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
    """Extract the body of a top-level function by balanced-brace scan."""
    pattern = re.compile(rf"function\s+{re.escape(fn_name)}\s*\(([^)]*)\)\s*\{{")
    m = pattern.search(script)
    assert m, f"Could not find function {fn_name} in script"
    start = m.end() - 1
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
# 1. HTML: console overlay + header controls + body + input row
# ===========================================================================


class TestConsoleHTMLStructure:
    def test_console_overlay_exists(self, html):
        assert 'id="console-overlay"' in html

    def test_console_panel_exists(self, html):
        assert 'class="console-panel"' in html

    def test_console_header_h3(self, html):
        assert 'id="console-title"' in html

    def test_project_select_exists(self, html):
        assert 'id="console-project-select"' in html

    def test_backend_select_exists(self, html):
        assert 'id="console-backend-select"' in html
        # Must be wired to onConsoleBackendChange (the POST handler).
        assert 'onConsoleBackendChange()' in html

    def test_token_meter_exists(self, html):
        assert 'id="console-tokens"' in html
        # The header label uses "tokens:" and the meter is hidden by default.
        assert "console-tokens" in html

    def test_token_meter_hidden_by_default(self, html):
        # The element is rendered with the `hidden` attribute so no
        # token strip flashes before the first usage.
        assert re.search(
            r'id="console-tokens"[^>]*\bhidden\b',
            html,
        ), "console-tokens must default to hidden until usage is observed"

    def test_clear_button_exists(self, html):
        assert 'id="console-clear-btn"' in html
        assert 'onclick="clearConsole()"' in html

    def test_close_button_exists(self, html):
        assert 'aria-label="Close console"' in html

    def test_notice_strip_exists(self, html):
        assert 'id="console-notice"' in html
        # Should be aria-live so backend-409 notices are announced.
        assert re.search(
            r'id="console-notice"[^>]*aria-live=',
            html,
        ), "console-notice must have aria-live for screen readers"

    def test_console_body_exists(self, html):
        assert 'id="console-body"' in html

    def test_console_drop_exists(self, html):
        # Drop zone reuses the attachment-dropzone CSS pattern from the
        # bead-detail panel.
        assert 'id="console-drop"' in html
        assert "attachment-dropzone" in html

    def test_console_input_exists(self, html):
        assert 'id="console-input"' in html
        assert 'aria-label="Console message input"' in html

    def test_send_button_exists(self, html):
        assert 'id="console-send"' in html

    def test_stop_button_exists(self, html):
        # Stop button shows while a turn is in flight (oompah-zlz_2-577a).
        assert 'id="console-stop"' in html
        assert 'onclick="stopConsoleTurn()"' in html
        # Hidden by default — only shown while inflight.
        assert re.search(
            r'id="console-stop"[^>]*\bhidden\b',
            html,
        ), "console-stop must default to hidden until a turn is in flight"

    def test_console_modal_is_aria_dialog(self, html):
        # Console panel must be an a11y dialog so keyboard nav works.
        assert 'role="dialog"' in html
        assert 'aria-modal="true"' in html


# ===========================================================================
# 2. CSS: per-kind message classes are styled (the 8 normalized kinds)
# ===========================================================================


NORMALIZED_KINDS = (
    "operator_input",
    "agent_text",
    "agent_thinking",
    "tool_call",
    "tool_result",
    "permission",
    "session_meta",
    "error",
)


class TestConsoleKindCSS:
    """Each normalized event kind must have a .console-msg-<kind> CSS rule."""

    @pytest.mark.parametrize("kind", NORMALIZED_KINDS)
    def test_kind_css_class_defined(self, html, kind):
        # We accept either ".console-msg-<kind>" or "console-msg-<kind>"
        # in a selector list; some kinds appear in compound selectors.
        assert (
            f".console-msg-{kind}" in html
            or f"console-msg-{kind} " in html
        ), f"CSS rule for .console-msg-{kind} must be defined"

    def test_operator_input_right_aligned(self, html):
        m = re.search(
            r"\.console-msg-operator_input\s*\{([^}]+)\}", html, re.DOTALL
        )
        assert m, "operator_input rule must exist"
        # Right-aligned bubble: align-self: flex-end or margin-left: auto.
        css = m.group(1)
        assert "flex-end" in css or "margin-left" in css, \
            "operator_input must be right-aligned (flex-end or margin-left:auto)"

    def test_agent_text_left_aligned(self, html):
        m = re.search(
            r"\.console-msg-agent_text\s*\{([^}]+)\}", html, re.DOTALL
        )
        assert m, "agent_text rule must exist"
        assert "flex-start" in m.group(1), \
            "agent_text must be left-aligned (flex-start)"

    def test_agent_thinking_italic(self, html):
        m = re.search(
            r"\.console-msg-agent_thinking\s*\{([^}]+)\}", html, re.DOTALL
        )
        assert m, "agent_thinking rule must exist"
        assert "italic" in m.group(1), \
            "agent_thinking must be italic per spec"

    def test_agent_thinking_collapsible(self, html):
        # The collapsed body uses .console-thinking-body which only
        # shows when the parent has .expanded.
        assert "console-thinking-body" in html
        assert ".console-msg-agent_thinking.expanded" in html

    def test_tool_call_collapsed_default(self, html):
        # tool_call args panel is display:none unless .expanded.
        m = re.search(
            r"\.console-msg-tool_call\s+\.console-tool-args\s*\{([^}]+)\}",
            html, re.DOTALL,
        )
        assert m, "tool_call .console-tool-args rule must exist"
        assert "display: none" in m.group(1) or "display:none" in m.group(1), \
            "tool_call args must be display:none by default (collapsed)"

    def test_tool_result_success_error_coloring(self, html):
        # tool_result default is success-colored; .error overrides to red.
        assert ".console-msg-tool_result.error" in html

    def test_session_meta_italic_centered(self, html):
        m = re.search(
            r"\.console-msg-session_meta\s*\{([^}]+)\}", html, re.DOTALL
        )
        assert m, "session_meta rule must exist"
        css = m.group(1)
        assert "italic" in css, "session_meta must be italic"
        assert "center" in css, "session_meta must be centered"

    def test_error_red_card(self, html):
        m = re.search(
            r"\.console-msg-error\s*\{([^}]+)\}", html, re.DOTALL
        )
        assert m, "error rule must exist"
        # Red comes from the --red variable.
        assert "--red" in m.group(1) or "#f85149" in m.group(1), \
            "error card must use the red variable"


# ===========================================================================
# 3. JS: renderConsoleEvent + per-kind branches
# ===========================================================================


class TestRenderConsoleEvent:
    def test_function_exists(self, script):
        assert "function renderConsoleEvent(" in script

    @pytest.mark.parametrize("kind", NORMALIZED_KINDS)
    def test_handles_each_kind(self, script, kind):
        body = _get_func_body(script, "renderConsoleEvent")
        assert f"'{kind}'" in body or f'"{kind}"' in body, \
            f"renderConsoleEvent must explicitly branch on kind={kind!r}"

    def test_operator_input_shows_attachments(self, script):
        body = _get_func_body(script, "renderConsoleEvent")
        # When attachments are present they render as chips.
        assert "console-attach-chip" in body

    def test_agent_text_uses_markdown_renderer(self, script):
        body = _get_func_body(script, "renderConsoleEvent")
        # The renderer delegates to renderConsoleMarkdown for the
        # agent_text body so basic md (code, bold, links) work.
        assert "renderConsoleMarkdown" in body

    def test_tool_result_tracks_tool_use_id(self, script):
        body = _get_func_body(script, "renderConsoleEvent")
        # Paired tool_call → tool_result error propagation uses
        # tool_use_id as the link key.
        assert "tool_use_id" in body


class TestRenderConsoleMarkdown:
    def test_function_exists(self, script):
        assert "function renderConsoleMarkdown(" in script

    def test_handles_code_fences(self, script):
        body = _get_func_body(script, "renderConsoleMarkdown")
        # Code fences ```lang ... ``` must be recognized.
        assert "```" in body

    def test_handles_inline_code(self, script):
        body = _get_func_body(script, "renderConsoleMarkdown")
        # Inline code via backticks.
        assert "<code>" in body

    def test_escapes_input(self, script):
        body = _get_func_body(script, "renderConsoleMarkdown")
        # Must escape user-controlled text before transformations.
        assert "esc(" in body, "Markdown renderer must escape before transforming"


# ===========================================================================
# 4. JS: token meter computation
# ===========================================================================


class TestTokenMeter:
    def test_format_helper_exists(self, script):
        assert "function _formatTokens(" in script

    def test_format_handles_thousands(self, script):
        body = _get_func_body(script, "_formatTokens")
        # Format spec: "14.2K" — division by 1000 and a 'K' suffix.
        assert "1000" in body
        assert "'K'" in body or '"K"' in body

    def test_update_function_exists(self, script):
        assert "function _updateTokenMeter(" in script

    def test_update_uses_latest_usage(self, script):
        body = _get_func_body(script, "_updateTokenMeter")
        assert "_latestUsage(" in body

    def test_update_formats_in_and_out(self, script):
        body = _get_func_body(script, "_updateTokenMeter")
        # "14.2K in / 3.1K out"
        assert "in" in body and "out" in body

    def test_update_hides_when_no_usage(self, script):
        body = _get_func_body(script, "_updateTokenMeter")
        assert "hidden" in body

    def test_latest_usage_helper_exists(self, script):
        assert "function _latestUsage(" in script


# ===========================================================================
# 5. JS: backend switch (POST /api/v1/console/<pid>/backend)
# ===========================================================================


class TestBackendSwitch:
    def test_change_handler_exists(self, script):
        assert "function onConsoleBackendChange(" in script

    def test_change_handler_posts_to_endpoint(self, script):
        body = _get_func_body(script, "onConsoleBackendChange")
        assert "/api/v1/console/" in body
        assert "/backend" in body
        assert "POST" in body or "'POST'" in body or '"POST"' in body

    def test_handles_409_in_flight(self, script):
        body = _get_func_body(script, "onConsoleBackendChange")
        assert "409" in body, "Must handle the 409 turn-in-flight response per spec"

    def test_409_shows_inline_notice(self, script):
        body = _get_func_body(script, "onConsoleBackendChange")
        assert "_showConsoleNotice" in body

    def test_populate_backend_select_exists(self, script):
        assert "_populateConsoleBackendSelect" in script

    def test_loads_backend_list_from_api(self, script):
        assert "/api/v1/acp-backends" in script


# ===========================================================================
# 6. JS: WS reconnect backfill via ?since
# ===========================================================================


class TestWSReconnectBackfill:
    def test_backfill_helper_exists(self, script):
        assert "function _backfillConsoleTranscript(" in script

    def test_backfill_uses_since_param(self, script):
        body = _get_func_body(script, "_backfillConsoleTranscript")
        assert "since=" in body, \
            "WS reconnect backfill must use ?since=<last_ts> per spec"

    def test_ws_onopen_triggers_backfill(self, script):
        # The ws.onopen handler must call _backfillConsoleTranscript for
        # the active project so we don't miss events that landed during
        # the disconnect window.
        # Find the connectWebSocket function and inspect its body.
        body = _get_func_body(script, "connectWebSocket")
        assert "_backfillConsoleTranscript" in body

    def test_last_ts_tracked_on_events(self, script):
        # Each console_event push updates _consoleLastTs[project_id]
        # so the next backfill knows where to resume.
        body = _get_func_body(script, "handleConsoleEvent")
        assert "_consoleLastTs" in body


# ===========================================================================
# 7. JS: Stop button + inflight timeout
# ===========================================================================


class TestStopAndInflight:
    def test_stop_handler_exists(self, script):
        assert "function stopConsoleTurn(" in script

    def test_stop_clears_inflight(self, script):
        body = _get_func_body(script, "stopConsoleTurn")
        # The v1 stop just unblocks the UI (server-side cancel is a
        # follow-up bead) — see issue out-of-scope note.
        assert "_setConsoleInflight" in body or "_consoleInflight" in body

    def test_set_inflight_helper_exists(self, script):
        assert "function _setConsoleInflight(" in script

    def test_inflight_has_long_timeout(self, script):
        body = _get_func_body(script, "_setConsoleInflight")
        # Long timeout safety net so a stuck server-side turn doesn't
        # permanently lock the input.
        assert "setTimeout" in body
        assert "CONSOLE_INFLIGHT_TIMEOUT_MS" in body

    def test_update_send_button_swaps_send_stop(self, script):
        body = _get_func_body(script, "_updateConsoleSendButton")
        # The button-swap logic toggles `hidden` on the Send and Stop
        # buttons so only one is visible at a time.
        assert "hidden" in body
        # Input is disabled while in flight.
        assert "disabled" in body


# ===========================================================================
# 8. JS: clear (DELETE /api/v1/console/<pid>)
# ===========================================================================


class TestClearConsole:
    def test_clear_function_exists(self, script):
        assert "function clearConsole(" in script

    def test_clear_calls_delete_endpoint(self, script):
        body = _get_func_body(script, "clearConsole")
        assert "/api/v1/console/" in body
        assert "DELETE" in body or "'DELETE'" in body or '"DELETE"' in body

    def test_clear_confirms_with_operator(self, script):
        body = _get_func_body(script, "clearConsole")
        # Destructive action — must confirm.
        assert "confirm(" in body

    def test_clear_resets_local_state(self, script):
        body = _get_func_body(script, "clearConsole")
        assert "_consoleTranscripts" in body


# ===========================================================================
# 9. JS: project filter sync
# ===========================================================================


class TestProjectFilterSync:
    def test_sync_helper_exists(self, script):
        assert "function _syncConsoleToProjectFilter(" in script

    def test_top_level_filter_wired_to_sync(self, html):
        # The top-level project-filter onchange must invoke the sync
        # helper so switching projects on the board also flips the
        # console.
        assert "_syncConsoleToProjectFilter()" in html

    def test_sync_swaps_active_project(self, script):
        body = _get_func_body(script, "_syncConsoleToProjectFilter")
        assert "setConsoleProject" in body


# ===========================================================================
# 10. JS: WS message router branch for console_event
# ===========================================================================


class TestWebSocketRouter:
    def test_router_handles_console_event(self, script):
        # The dispatcher in connectWebSocket() routes console_event
        # messages to handleConsoleEvent.
        assert "handleConsoleEvent" in script
        assert "'console_event'" in script or '"console_event"' in script

    def test_send_uses_console_input_type(self, script):
        body = _get_func_body(script, "sendConsoleMessage")
        # Outgoing message type per the server endpoint contract.
        assert "'console_input'" in body or '"console_input"' in body
