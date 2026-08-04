"""Dashboard alert-center contracts for OOMPAH-742.

The dashboard is deliberately framework-free, so these tests keep its DOM,
CSS, and state-update contracts executable through focused source assertions.
They cover the operator scenarios rather than preserving the retired banner
markup from the transition implementation.
"""

from __future__ import annotations

import re
import subprocess
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


def test_alert_center_is_the_only_actionable_alert_surface() -> None:
    html = _dashboard_html()
    state_update = _function(html, "handleStateUpdate")

    assert 'id="alert-center"' in html
    assert 'id="agent-warnings"' not in html
    assert 'id="alerts-banner"' not in html
    assert 'id="cred-error-banner"' not in html
    assert "renderAlertCenter(actionableAlerts)" in state_update
    assert "renderAlertSummary" not in state_update


def test_actionable_partition_keeps_legacy_alerts_but_moves_status_to_diagnostics() -> None:
    state_update = _function(_dashboard_html(), "handleStateUpdate")

    # Missing action_required retains legacy alert semantics; a producer must
    # explicitly mark a fact false for it to leave the operator alert surface.
    assert "return alert.action_required !== false;" in state_update
    assert "return alert.action_required === false;" in state_update
    assert "renderDiagnosticFacts(diagnosticAlerts)" in state_update
    assert "OOMPAH-735 and OOMPAH-741" in state_update


def test_duplicate_stable_identity_is_selected_once_before_partitioning() -> None:
    html = _dashboard_html()
    dedupe = _function(html, "dedupeAlertFacts")
    identity = _function(html, "alertStableIdentity")
    state_update = _function(html, "handleStateUpdate")

    assert "stable_id" in identity
    assert "stable_identity" in identity
    assert "alert_id" in identity
    assert "selected = new Map" in dedupe
    assert "getAlertSeverity" in dedupe
    assert "dedupeAlertFacts(alerts)" in state_update


def test_no_alert_state_hides_details_and_resets_expanded_state() -> None:
    render = _function(_dashboard_html(), "renderAlertCenter")

    assert "const count = uniqueAlerts.length;" in render
    assert "data-alert-count" in render
    assert "if (count === 0)" in render
    assert "setAlertCenterExpanded(center, list, false)" in render
    assert "No active operator alerts." in render


def test_single_and_many_alerts_use_counted_collapsed_summary() -> None:
    html = _dashboard_html()
    render = _function(html, "renderAlertCenter")

    assert 'id="alert-center-count"' in html
    assert "count === 1 ? 'alert' : 'alerts'" in render
    assert "Highest severity:" in render
    assert "aria-label" in render


def test_mixed_severity_uses_structured_severity_not_source_heuristics() -> None:
    html = _dashboard_html()
    severity = _function(html, "getAlertSeverity")
    highest = _function(html, "getHighestAlertSeverity")

    assert "ALERT_SEVERITY_RANK" in html
    assert "alert.severity || alert.level" in severity
    assert "Math.max" in highest
    assert "cred_error:" not in severity


def test_disclosure_is_keyboard_operable_and_has_a_clear_accessible_name() -> None:
    html = _dashboard_html()
    toggle = _function(html, "toggleAlertCenter")
    set_expanded = _function(html, "setAlertCenterExpanded")

    assert 'type="button"' in html
    assert 'aria-controls="alert-center-list"' in html
    assert 'aria-expanded="false"' in html
    assert 'aria-label="Show active alerts"' in html
    assert "list.hidden = !expanded" in set_expanded
    assert "setAlertCenterExpanded" in toggle
    assert 'tabindex="0"' in re.search(
        r'<ul class="alert-center-list"[^>]+>', html,
    ).group(0)


def test_expanded_alert_list_is_viewport_bounded_and_independently_scrollable() -> None:
    styles = _styles(_dashboard_html())
    list_rule = _rule(styles, ".alert-center-list")

    assert "max-height: 35vh" in list_rule
    assert "overflow-y: auto" in list_rule
    assert "overscroll-behavior: contain" in list_rule


def test_dynamic_addition_and_removal_preserves_operator_focus() -> None:
    html = _dashboard_html()
    render = _function(html, "renderAlertCenter")
    focus = _function(html, "focusBoardAfterAlertCenter")

    assert "const hadCenterFocus = center.contains(document.activeElement);" in render
    assert "else if (center.getAttribute('aria-expanded') === 'true')" in render
    assert "setAlertCenterExpanded(center, list, true)" in render
    assert "if (hadCenterFocus) focusBoardAfterAlertCenter();" in render
    assert "board.focus()" in focus
    assert 'id="board" tabindex="-1"' in html


def test_live_region_announces_summary_changes_not_alert_transcripts() -> None:
    html = _dashboard_html()
    render = _function(html, "renderAlertCenter")

    list_tag = re.search(r'<ul class="alert-center-list"[^>]+>', html)
    assert list_tag
    assert "aria-live" not in list_tag.group(0)
    assert 'id="alert-center-live"' in html
    assert 'aria-live="polite"' in html
    assert "data-alert-signature" in render
    assert "highest severity" in render


def test_diagnostics_are_an_overlay_for_non_actionable_facts() -> None:
    html = _dashboard_html()
    styles = _styles(html)
    panel_rule = _rule(styles, ".dashboard-diagnostics-panel")

    assert 'id="dashboard-diagnostics"' in html
    assert 'id="audit-stat"' in html
    assert 'id="repo-hygiene-health"' in html
    assert 'id="quality-gate-health"' in html
    assert 'id="auth-health-banner"' in html
    assert "position: absolute" in panel_rule
    assert "max-height: min(65vh, 34rem)" in panel_rule
    assert "overflow-y: auto" in panel_rule


def test_alert_center_runtime_handles_empty_mixed_and_dynamic_alert_sets() -> None:
    """Exercise the disclosure state without a browser or a UI framework."""
    html = _dashboard_html()
    helpers = "\n".join(
        [
            re.search(
                r"const ALERT_SEVERITY_RANK = [^;]+;", html
            ).group(0),
            *(
                _function(html, name)
                for name in (
                    "alertPrimaryText",
                    "alertDetailText",
                    "alertActionText",
                    "renderAlertItem",
                    "getAlertSeverity",
                    "getHighestAlertSeverity",
                    "getSeverityLabel",
                    "alertStableIdentity",
                    "dedupeAlertFacts",
                    "setAlertCenterExpanded",
                    "toggleAlertCenter",
                    "focusBoardAfterAlertCenter",
                    "renderAlertCenter",
                )
            ),
        ]
    )
    script = (
        """
const assert = require('node:assert/strict');
function element() {
  const attrs = new Map();
  return {
    hidden: false, textContent: '', innerHTML: '', focused: false,
    setAttribute(name, value) { attrs.set(name, String(value)); },
    getAttribute(name) { return attrs.has(name) ? attrs.get(name) : null; },
    focus() { this.focused = true; },
  };
}
const center = element();
const list = element();
const count = element();
const severity = element();
const live = element();
const button = element();
const board = element();
center.setAttribute('data-alert-count', '0');
center.setAttribute('aria-expanded', 'false');
button.setAttribute('aria-expanded', 'false');
center.querySelector = () => button;
center.contains = (target) => target === center || target === list || target === button;
const document = {
  activeElement: null,
  getElementById(id) {
    return {
      'alert-center': center, 'alert-center-list': list,
      'alert-center-count': count, 'alert-center-severity-label': severity,
      'alert-center-live': live, board,
    }[id] || null;
  },
};
function esc(value) { return String(value || ''); }
"""
        + helpers
        + """
renderAlertCenter([]);
assert.equal(center.getAttribute('data-alert-count'), '0');
assert.equal(list.hidden, true);
assert.equal(live.textContent, '');

renderAlertCenter([{stable_id: 'one', severity: 'warning', summary: 'One'}]);
assert.equal(center.getAttribute('data-alert-count'), '1');
assert.equal(severity.textContent, 'Highest severity: warning');
assert.match(button.getAttribute('aria-label'), /Show 1 active alert/);
toggleAlertCenter();
assert.equal(center.getAttribute('aria-expanded'), 'true');
assert.equal(list.hidden, false);

renderAlertCenter([
  {stable_id: 'one', severity: 'info', action_required: false, summary: 'Older copy'},
  {stable_id: 'one', severity: 'error', action_required: true, summary: 'One'},
  {stable_id: 'two', severity: 'warning', summary: 'Two'},
]);
assert.equal(center.getAttribute('data-alert-count'), '2');
assert.equal(center.getAttribute('data-highest-severity'), 'error');
assert.equal(center.getAttribute('aria-expanded'), 'true');
assert.equal((list.innerHTML.match(/class=\"alert-item\"/g) || []).length, 2);

document.activeElement = list;
renderAlertCenter([{stable_id: 'two', severity: 'warning', summary: 'Two'}]);
assert.equal(center.getAttribute('aria-expanded'), 'true');
assert.equal(list.hidden, false);
renderAlertCenter([]);
assert.equal(list.hidden, true);
assert.equal(board.focused, true);
"""
    )
    result = subprocess.run(
        ["node", "-e", script],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
