"""Static dashboard contracts for the canonical WorkDecision projection."""

from __future__ import annotations

from pathlib import Path


def _dashboard() -> str:
    return (
        Path(__file__).resolve().parents[1] / "oompah" / "templates" / "dashboard.html"
    ).read_text(encoding="utf-8")


def test_board_detail_and_agent_panels_share_decision_renderer() -> None:
    html = _dashboard()
    assert "function renderWorkDecisionSummary(decision, compact)" in html
    assert "renderWorkDecisionSummary(issue.work_decision, false)" in html
    assert "renderWorkDecisionSummary(detail.work_decision, false)" in html
    assert "r.work_decision || null" in html
    assert "decision.reason_text || decision.reason_code" in html


def test_global_warning_banner_uses_explicit_global_alert_projection() -> None:
    html = _dashboard()
    assert "const alerts = state.alerts || [];" in html
    assert "const globalAlerts = Array.isArray(state.global_alerts)" in html
    assert "globalAlerts.filter(function(a)" in html
    assert "role=\"status\"" in html
    assert "aria-label=\"" in html


def test_decision_rendering_escapes_operator_values() -> None:
    html = _dashboard()
    start = html.index("function renderWorkDecisionSummary")
    end = html.index("function renderTerminalAuditHealth", start)
    body = html[start:end]
    assert "esc(reason)" in body
    assert "esc(owner)" in body
    assert "esc(action)" in body
    assert "Prerequisites" in body
