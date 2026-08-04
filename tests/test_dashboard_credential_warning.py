"""Credential and auth facts use the unified dashboard alert center."""

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


def _function(html: str, name: str) -> str:
    match = re.search(rf"function\s+{re.escape(name)}\s*\([^)]*\)\s*\{{", html)
    assert match, f"missing function {name}"
    depth = 0
    for index in range(match.start(), len(html)):
        if html[index] == "{":
            depth += 1
        elif html[index] == "}":
            depth -= 1
            if depth == 0:
                return html[match.start() : index + 1]
    raise AssertionError(f"unterminated function {name}")


def test_credential_and_auth_alerts_are_not_routed_to_legacy_banners() -> None:
    html = _dashboard_html()
    state_update = _function(html, "handleStateUpdate")

    assert 'id="cred-error-banner"' not in html
    assert 'id="alerts-banner"' not in html
    assert "cred_error:" not in state_update
    assert "agent-warnings" not in state_update
    assert "renderAlertCenter(actionableAlerts)" in state_update


def test_alert_detail_fields_remain_escaped_in_the_unified_list() -> None:
    render_item = _function(_dashboard_html(), "renderAlertItem")

    assert "alertPrimaryText(alert)" in render_item
    assert "alertDetailText(alert)" in render_item
    assert "alertActionText(alert)" in render_item
    assert "esc(title)" in render_item
    assert "esc(detail)" in render_item
    assert "esc(action)" in render_item
    assert "esc(source)" in render_item


def test_auth_health_is_status_when_healthy_and_not_a_duplicate_when_degraded() -> None:
    html = _dashboard_html()
    state_update = _function(html, "handleStateUpdate")
    auth_renderer = _function(html, "renderAuthHealthBanner")

    assert "const authHealthHasAction" in state_update
    assert "renderAuthHealthBanner(state.auth_health || null, authHealthHasAction)" in state_update
    assert "if (hiddenByAlert || !authHealth)" in auth_renderer
    assert "Operator auth" in auth_renderer
    assert "Worker token" in auth_renderer


def test_policy_denials_remain_available_in_diagnostics() -> None:
    auth_renderer = _function(_dashboard_html(), "renderAuthHealthBanner")

    assert "policy_denial_count" in auth_renderer
    assert "task-policy denial" in auth_renderer
    assert "coordinate peers" in auth_renderer
    assert "coordinate inbox" in auth_renderer
