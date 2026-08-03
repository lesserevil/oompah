"""Static contracts for bounded, accessible dashboard alert rendering."""

from __future__ import annotations

from pathlib import Path


def _dashboard() -> str:
    return (Path(__file__).parents[1] / "oompah" / "templates" / "dashboard.html").read_text(
        encoding="utf-8"
    )


def test_agent_bar_alerts_are_single_line_and_width_bounded() -> None:
    html = _dashboard()
    css = html.split("</style>", 1)[0]

    assert "white-space: nowrap" in css
    assert "text-overflow: ellipsis" in css
    assert "max-width: min(42vw, 36rem)" in css


def test_alert_renderer_has_defensive_limits_and_escaped_collapsed_diagnostics() -> None:
    html = _dashboard()

    assert "ALERT_RENDER_SUMMARY_MAX = 240" in html
    assert "ALERT_RENDER_DIAGNOSTIC_MAX = 4000" in html
    assert "normalizeAlertForRender" in html
    assert "Array.isArray(alerts) ? alerts : []" in html
    assert "[alert.summary, ALERT_RENDER_SUMMARY_MAX]" in html
    assert "[alert.title, ALERT_RENDER_TITLE_MAX]" in html
    assert '<details class="alert-diagnostics">' in html
    assert "esc(diagnostic)" in html
    assert "Diagnostic details (truncated)" in html


def test_expanded_alert_order_keeps_explanation_and_action_before_transcript() -> None:
    html = _dashboard()
    detail_position = html.index("(detail ? '<div class=\"alert-detail\">")
    action_position = html.index("(action ? '<div class=\"alert-action\">")
    diagnostic_position = html.index("<details class=\"alert-diagnostics\">")

    assert detail_position < action_position < diagnostic_position
