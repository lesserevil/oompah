"""Regression coverage for dashboard scrolling with dynamic alert panels.

The dashboard is an app-style flex layout rather than a document-scrolling
page: flat-view ``.column-body`` elements own vertical scrolling, while the
board owns horizontal scrolling (and vertical scrolling in swimlane view).
These static contracts cover the layout without requiring a browser runtime.
"""

from __future__ import annotations

import re
from pathlib import Path


def _dashboard_html() -> str:
    return (
        Path(__file__).resolve().parents[1]
        / "oompah"
        / "templates"
        / "dashboard.html"
    ).read_text(encoding="utf-8")


def _styles(html: str) -> str:
    match = re.search(r"<style>(?P<style>.*?)</style>", html, re.DOTALL)
    assert match, "dashboard.html must contain an inline stylesheet"
    return match.group("style")


def _rule(styles: str, selector: str) -> str:
    match = re.search(
        rf"(?m)^\s*{re.escape(selector)}\s*\{{(?P<body>.*?)\n\s*\}}",
        styles,
        re.DOTALL,
    )
    assert match, f"missing CSS rule for {selector}"
    return match.group("body")


def _state_update_body(html: str) -> str:
    scripts = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    assert scripts, "dashboard.html must contain a script block"
    script = max(scripts, key=len)
    match = re.search(
        r"function handleStateUpdate\(state\) \{(?P<body>.*?)\n\}",
        script,
        re.DOTALL,
    )
    assert match, "handleStateUpdate() must remain present"
    return match.group("body")


def test_no_alert_layout_keeps_the_compact_center_before_the_board() -> None:
    """No alerts leaves only the hidden center between the agent bar and board."""
    html = _dashboard_html()
    main_area = html.index('<div class="main-area">')
    preboard_panel_ids = (
        "alert-center",
        "task-state-stale-banner",
        "board-error",
        "board-notice",
    )

    previous = html.index('<div class="agent-bar"')
    for panel_id in preboard_panel_ids:
        match = re.search(rf'<[^>]+id="{re.escape(panel_id)}"[^>]*>', html)
        assert match, f"missing pre-board panel {panel_id}"
        if panel_id == "alert-center":
            assert 'data-alert-count="0"' in match.group(0)
        else:
            assert "hidden" in match.group(0), f"{panel_id} must be hidden with no alert"
        assert previous < match.start() < main_area
        previous = match.start()


def test_alert_transitions_reflow_the_same_board_container() -> None:
    """One or many alerts update the center instead of replacing the board."""
    html = _dashboard_html()
    body = _state_update_body(html)

    assert "const alerts = Array.isArray(state.alerts) ? state.alerts : [];" in body
    assert "const actionableAlerts" in body
    assert "renderAlertCenter(actionableAlerts);" in body
    assert "renderDiagnosticFacts(diagnosticAlerts);" in body
    assert 'id="board"' in html


def test_flat_view_scroll_owner_fits_after_any_visible_alert_stack() -> None:
    """Tall flat columns can scroll to their bottom in the available viewport."""
    styles = _styles(_dashboard_html())
    body = _rule(styles, "body")
    main_area = _rule(styles, ".main-area")
    board = _rule(styles, ".board")
    column = _rule(styles, ".column")
    column_body = _rule(styles, ".column-body")

    # The app viewport remains the document boundary; the flex chain must be
    # allowed to shrink when banners become visible above .main-area.
    assert "height: 100vh" in body
    assert "overflow: hidden" in body
    assert "overflow: hidden" in main_area
    assert "min-height: 0" in main_area
    assert "min-height: 0" in board

    # A viewport-relative max-height would ignore the alert stack.  The
    # percentage is resolved against the resized board, so .column-body can
    # reach its scrollHeight all the way to the final card.
    assert "max-height: 100%" in column
    assert "calc(100vh" not in column
    assert "min-height: 0" in column
    assert "overflow-y: auto" in column_body
    assert "min-height: 0" in column_body


def test_board_horizontal_and_swimlane_vertical_scrolling_are_preserved() -> None:
    styles = _styles(_dashboard_html())
    board = _rule(styles, ".board")
    swimlane_board = _rule(styles, ".board.swimlane-view")

    assert "overflow-x: auto" in board
    assert "overflow-y: hidden" in board
    assert "overflow-y: auto" in swimlane_board
    assert "overflow-x: hidden" in swimlane_board
    assert "overflow-x: auto" in _rule(styles, ".swimlane-columns")
