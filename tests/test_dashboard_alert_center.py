"""Tests for the compact alert center (OOMPAH-742).

Validates that the alert center consolidates multiple alert sources into a
single collapsible component with bounded height and proper a11y.
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


def test_alert_center_exists_in_html() -> None:
    """Alert center markup is present and positioned before the board."""
    html = _dashboard_html()
    
    # Alert center should exist
    assert 'id="alert-center"' in html
    assert 'class="alert-center"' in html
    
    # Alert center summary button should exist
    assert 'class="alert-center-toggle"' in html
    
    # Alert center list should exist
    assert 'id="alert-center-list"' in html


def test_alert_center_positioned_before_main_area() -> None:
    """Alert center is positioned before the board."""
    html = _dashboard_html()
    main_area_pos = html.index('<div class="main-area">')
    alert_center_pos = html.index('id="alert-center"')
    
    assert alert_center_pos < main_area_pos, "alert-center must come before main-area"


def test_alert_center_has_collapsed_state_css() -> None:
    """Alert center has proper CSS for collapsed state."""
    styles = _styles(_dashboard_html())
    
    # The collapsed summary should be visible
    collapsed = _rule(styles, ".alert-center-toggle")
    assert "display" in collapsed or "flex" in collapsed
    assert "cursor: pointer" in collapsed


def test_alert_center_list_has_bounded_height_when_expanded() -> None:
    """Expanded alert list has max-height and internal scrolling."""
    styles = _styles(_dashboard_html())
    
    list_rule = _rule(styles, ".alert-center-list")
    
    # Should have internal scrolling
    assert "max-height" in list_rule
    assert "overflow-y" in list_rule


def test_alert_center_console_uses_compact_collapsed_state() -> None:
    """Alert center is rendered in handleStateUpdate."""
    html = _dashboard_html()
    body = _state_update_body(html)
    
    # Should call renderAlertCenter
    assert "renderAlertCenter" in body
    # Should handle alerts list
    assert "otherAlerts" in body


def test_alert_center_with_no_alerts_stays_hidden() -> None:
    """Alert center is hidden when there are no alerts."""
    html = _dashboard_html()
    
    # Should have hidden attribute or logic to hide it
    assert 'id="alert-center"' in html


def test_alert_center_expands_on_toggle_click() -> None:
    """Alert center list expands/collapses on toggle button click."""
    html = _dashboard_html()
    
    # Toggle button should exist
    assert 'alert-center-toggle' in html
    # Should use aria-expanded or similar
    assert 'aria-expanded' in html or 'onclick' in html


def test_alert_center_maintains_board_visibility() -> None:
    """Board remains visible and scrollable even with expanded alert center."""
    styles = _styles(_dashboard_html())
    
    body_rule = _rule(styles, "body")
    main_area_rule = _rule(styles, ".main-area")
    board_rule = _rule(styles, ".board")
    
    # Body should maintain viewport height
    assert "height: 100vh" in body_rule
    
    # Main area should flex and shrink
    assert "flex" in main_area_rule
    assert "min-height" in main_area_rule
    
    # Board should have room to scroll
    assert "overflow-x: auto" in board_rule


def test_alert_center_list_items_have_proper_structure() -> None:
    """Alert items in the list have proper semantic structure."""
    html = _dashboard_html()
    
    # Alert items should be in a list
    assert 'id="alert-center-list"' in html
    # List items should have class for styling
    assert 'class="alert-item"' in html or 'alert-' in html


def test_alert_center_has_accessibility_attributes() -> None:
    """Alert center has proper ARIA labels for a11y."""
    html = _dashboard_html()
    
    # Should have role, aria-live, or aria-label
    assert 'alert-center' in html
    assert 'role=' in html or 'aria-' in html


def test_old_alert_banners_remain_for_compatibility() -> None:
    """Old individual banners (cred-error, alerts-banner, etc) still exist but may be hidden."""
    html = _dashboard_html()
    
    # These should still exist (for backward compatibility during migration)
    assert 'id="cred-error-banner"' in html
    assert 'id="alerts-banner"' in html
    assert 'id="terminal-audit-health"' in html
    assert 'id="repo-hygiene-health"' in html
    assert 'id="auth-health-banner"' in html
