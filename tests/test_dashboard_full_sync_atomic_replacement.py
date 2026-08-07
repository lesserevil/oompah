"""OOMPAH-744: Atomic replacement contracts for authoritative full_sync snapshots.

Every ``full_sync`` payload replaces the dashboard's alert, terminal-audit,
quality-gate, authentication, and repository-health presentation state. These
contracts pin the DOM lifecycle so a browser reconciled after a detected
WebSocket sequence gap cannot show a stale banner alongside a recovered live
counter.

The tests are source-contract style (mirroring
``tests/test_dashboard_alert_center.py``): they exercise the real dashboard
JavaScript with a minimal DOM stub under ``node``. That keeps them fast, free
of a browser dependency, and directly wired to the checked-in template.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest


DASHBOARD_PATH = (
    Path(__file__).resolve().parents[1] / "oompah" / "templates" / "dashboard.html"
)


def _dashboard_html() -> str:
    return DASHBOARD_PATH.read_text(encoding="utf-8")


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


def _var_decl(html: str, name: str) -> str:
    """Extract a top-level ``var <name> = ...;`` (used for module state)."""
    match = re.search(rf"\bvar\s+{re.escape(name)}\s*=[^;]*;", html)
    assert match, f"missing var {name}"
    return match.group(0)


# ---------------------------------------------------------------------------
# Structural contracts — target the current template
# ---------------------------------------------------------------------------


def test_full_sync_calls_atomic_clear_before_state_render() -> None:
    """``_applyFullSyncMessage`` clears every presentation panel before rendering.

    Ordering matters: if ``handleStateUpdate`` ran first and then the clear
    swept the DOM, the authoritative snapshot would be erased. The clear must
    come first, in the same synchronous frame as the render.
    """
    apply = _function(_dashboard_html(), "_applyFullSyncMessage")

    clear_index = apply.index("_clearAllAlertAndHealthUI()")
    state_index = apply.index("handleStateUpdate(msg.state)")
    board_index = apply.index("renderBoard(")

    assert clear_index < state_index < board_index, (
        "full_sync must clear presentation state before applying the "
        "authoritative snapshot"
    )
    assert "wsApplyingFullSync = true" in apply
    assert "wsApplyingFullSync = wasApplying" in apply


def test_atomic_clear_targets_current_template_ids() -> None:
    """The clear addresses every current alert/health DOM anchor."""
    html = _dashboard_html()
    clear = _function(html, "_clearAllAlertAndHealthUI")

    # Alert center (post OOMPAH-742 compact center) — reset counters, drop
    # the announcement signature so the next render's diff is a real diff.
    for token in (
        "getElementById('alert-center')",
        "getElementById('alert-center-list')",
        "getElementById('alert-center-count')",
        "getElementById('alert-center-severity-label')",
        "getElementById('alert-center-live')",
        "removeAttribute('data-alert-signature')",
        "setAttribute('data-alert-count', '0')",
        "setAttribute('data-highest-severity', 'none')",
        "setAttribute('aria-expanded', 'false')",
    ):
        assert token in clear, f"clear missing token {token}"

    # Diagnostic-facts overlay (non-actionable facts).
    assert "getElementById('diagnostic-facts')" in clear
    assert "getElementById('diagnostic-facts-list')" in clear

    # Dedicated health panels.
    for token in (
        "getElementById('terminal-audit-health')",
        "getElementById('terminal-audit-health-detail')",
        "getElementById('quality-gate-health')",
        "getElementById('quality-gate-health-detail')",
        "getElementById('repo-hygiene-health')",
        "getElementById('repo-hygiene-inventory')",
        "getElementById('repo-hygiene-overdue-list')",
        "getElementById('repo-hygiene-error-list')",
        "getElementById('auth-health-banner')",
        "getElementById('auth-health-planes')",
        "getElementById('auth-health-details')",
        "getElementById('running-agents')",
    ):
        assert token in clear, f"clear missing token {token}"

    # Every id it addresses must exist in the template.
    for element_id in (
        "alert-center",
        "alert-center-list",
        "alert-center-count",
        "alert-center-severity-label",
        "alert-center-live",
        "diagnostic-facts",
        "diagnostic-facts-list",
        "terminal-audit-health",
        "terminal-audit-health-detail",
        "quality-gate-health",
        "quality-gate-health-detail",
        "repo-hygiene-health",
        "repo-hygiene-inventory",
        "repo-hygiene-overdue-list",
        "repo-hygiene-error-list",
        "auth-health-banner",
        "auth-health-planes",
        "auth-health-details",
        "running-agents",
    ):
        assert f'id="{element_id}"' in html, (
            f"template must expose #{element_id} for the atomic clear to reach it"
        )


def test_full_sync_records_bounded_replacement_failure_diagnostics() -> None:
    """A presentation replacement failure is captured without a warning loop."""
    html = _dashboard_html()
    apply = _function(html, "_applyFullSyncMessage")
    record = _function(html, "_recordPresentationReplacementFailure")

    # The apply path guards each phase (clear, state, board) with its own
    # try/catch so a failure in one phase does not leave the operator with a
    # blank board or block the recovery watermark.
    assert apply.count("try {") >= 4  # outer + clear + state + board
    for phase in ("'clear'", "'state'", "'board'"):
        assert f"_recordPresentationReplacementFailure({phase}," in apply

    # The record helper is bounded so a repeatedly-failing snapshot cannot
    # grow the diagnostics ring buffer without limit.
    assert "_PRESENTATION_REPLACEMENT_DIAGNOSTIC_MAX" in html
    assert "_presentationReplacementDiagnostics" in record
    assert ".push(" in record
    assert ".shift()" in record
    # Guard against the diagnostics path itself throwing (a "warning loop"
    # would arise if a failure in the console path re-entered this helper).
    assert "catch (loopGuard)" in record


def test_dashboard_uses_shared_stable_identity_for_partial_and_full_updates() -> None:
    """Incremental updates and full replacements share dedupe/identity rules.

    Both paths flow through ``handleStateUpdate → renderAlertCenter →
    dedupeAlertFacts → alertStableIdentity``. Pinning the shared entry point
    stops a future refactor from splitting the ordering/identity rules.
    """
    html = _dashboard_html()

    apply = _function(html, "_applyFullSyncMessage")
    state = _function(html, "handleStateUpdate")

    assert "handleStateUpdate(msg.state)" in apply
    assert "renderAlertCenter(actionableAlerts)" in state
    assert "dedupeAlertFacts(alerts)" in state
    assert "alertStableIdentity" in html
    # The alert-center render already keys announcements on the stable
    # signature so repeated identical snapshots do not re-announce.
    render_center = _function(html, "renderAlertCenter")
    assert "data-alert-signature" in render_center
    assert "previousSignature !== signature" in render_center


# ---------------------------------------------------------------------------
# Runtime contracts — exercise the JavaScript with a DOM stub
# ---------------------------------------------------------------------------


def _node_available() -> bool:
    return shutil.which("node") is not None


@pytest.mark.skipif(not _node_available(), reason="node is required for runtime contracts")
def test_atomic_clear_removes_every_stale_alert_and_health_dom_element() -> None:
    """A stale board recovers with zero residual alert/health DOM.

    Simulates a browser that has already rendered a transport-failure alert,
    a failed quality-gate panel, a degraded auth banner, and running chips.
    After the atomic clear, none of that DOM survives — every panel is empty
    and hidden, matching the shape of an authoritative "healthy" snapshot.
    """
    html = _dashboard_html()

    clear_fn = _function(html, "_clearAllAlertAndHealthUI")
    record_fn = _function(html, "_recordPresentationReplacementFailure")
    diag_var = _var_decl(html, "_presentationReplacementDiagnostics")
    diag_cap_var = _var_decl(html, "_PRESENTATION_REPLACEMENT_DIAGNOSTIC_MAX")

    script = f"""
const assert = require('node:assert/strict');

function element(id) {{
  const attrs = new Map();
  return {{
    id, hidden: false, textContent: 'stale', innerHTML: '<span>stale</span>',
    classList: (function() {{
      const set = new Set(['degraded']);
      return {{
        add(name) {{ set.add(name); }},
        remove(name) {{ set.delete(name); }},
        toggle(name, on) {{ on ? set.add(name) : set.delete(name); }},
        contains(name) {{ return set.has(name); }},
        _dump() {{ return Array.from(set); }},
      }};
    }})(),
    setAttribute(name, value) {{ attrs.set(name, String(value)); }},
    getAttribute(name) {{ return attrs.has(name) ? attrs.get(name) : null; }},
    removeAttribute(name) {{ attrs.delete(name); }},
    hasAttribute(name) {{ return attrs.has(name); }},
    querySelector() {{ return null; }},
  }};
}}

const registry = {{}};
[
  'alert-center', 'alert-center-list', 'alert-center-count',
  'alert-center-severity-label', 'alert-center-live',
  'diagnostic-facts', 'diagnostic-facts-list',
  'terminal-audit-health', 'terminal-audit-health-detail',
  'quality-gate-health', 'quality-gate-health-detail',
  'repo-hygiene-health', 'repo-hygiene-health-icon',
  'repo-hygiene-health-title', 'repo-hygiene-health-summary',
  'repo-hygiene-inventory', 'repo-hygiene-overdue',
  'repo-hygiene-overdue-list', 'repo-hygiene-errors',
  'repo-hygiene-error-list',
  'auth-health-banner', 'auth-health-planes', 'auth-health-details',
  'running-agents',
].forEach((id) => {{ registry[id] = element(id); }});

// Stale attribute state on the alert center — the observation is that
// data-alert-signature must be dropped so the next authoritative render is
// diffed against a clean slate rather than an equal previous signature.
registry['alert-center'].setAttribute('data-alert-count', '3');
registry['alert-center'].setAttribute('aria-expanded', 'true');
registry['alert-center'].setAttribute('data-highest-severity', 'critical');
registry['alert-center'].setAttribute('data-alert-signature', 'stale-signature');

const document = {{
  getElementById(id) {{ return registry[id] || null; }},
}};

{diag_var}
{diag_cap_var}
{record_fn}
{clear_fn}

_clearAllAlertAndHealthUI();

// Every list container is emptied — no stale item survives.
for (const id of [
  'alert-center-list',
  'diagnostic-facts-list',
  'repo-hygiene-inventory',
  'repo-hygiene-overdue-list',
  'repo-hygiene-error-list',
  'auth-health-planes',
  'auth-health-details',
  'running-agents',
]) {{
  assert.equal(registry[id].innerHTML, '',
    'innerHTML for ' + id + ' should be empty after atomic clear');
}}

// Every leaf text element is empty (or reset to a healthy default) — the
// alert-center count is reset to '0' as its healthy sentinel value.
assert.equal(registry['alert-center-count'].textContent, '0');
for (const id of [
  'alert-center-severity-label',
  'alert-center-live',
  'terminal-audit-health-detail',
  'quality-gate-health-detail',
  'repo-hygiene-health-icon',
  'repo-hygiene-health-title',
  'repo-hygiene-health-summary',
]) {{
  assert.equal(registry[id].textContent, '',
    'textContent for ' + id + ' should be empty after atomic clear');
}}

// Panels that carry role="status" for degraded facts are hidden by default.
for (const id of ['alert-center-list', 'diagnostic-facts',
                  'terminal-audit-health', 'quality-gate-health',
                  'repo-hygiene-health', 'repo-hygiene-overdue',
                  'repo-hygiene-errors', 'auth-health-banner']) {{
  assert.equal(registry[id].hidden, true, id + ' should be hidden');
}}

// The alert center's stale attributes are reset atomically so the next
// authoritative render cannot observe a mixed-generation summary.
const center = registry['alert-center'];
assert.equal(center.getAttribute('data-alert-count'), '0');
assert.equal(center.getAttribute('data-highest-severity'), 'none');
assert.equal(center.getAttribute('aria-expanded'), 'false');
assert.equal(center.hasAttribute('data-alert-signature'), false,
  'the announcement signature must be dropped so a repeated snapshot ' +
  'does not silently reuse the stale summary');
assert.equal(registry['repo-hygiene-health'].classList.contains('degraded'), false,
  'the repo-hygiene panel must lose its degraded class after replacement');
"""

    result = subprocess.run(
        ["node", "-e", script], check=False, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(not _node_available(), reason="node is required for runtime contracts")
def test_replacement_failure_is_bounded_and_never_loops() -> None:
    """Repeated presentation faults do not grow diagnostics unboundedly.

    A snapshot that repeatedly fails to apply — for example, because a
    schema-invalid alert forces a render exception every time — must not
    grow the in-memory ring buffer without limit, and must not re-emit into
    the alert stream (which would create a warning loop when the alert
    source is itself the failing producer).
    """
    html = _dashboard_html()

    record_fn = _function(html, "_recordPresentationReplacementFailure")
    diag_var = _var_decl(html, "_presentationReplacementDiagnostics")
    diag_cap_var = _var_decl(html, "_PRESENTATION_REPLACEMENT_DIAGNOSTIC_MAX")

    script = f"""
const assert = require('node:assert/strict');

// The bounded record path is expected to log to console.warn (once per
// failure) rather than push back into the alert stream. Count the calls
// so we can assert the bound.
let warnCount = 0;
const console = {{ warn: () => {{ warnCount += 1; }} }};

{diag_var}
{diag_cap_var}
{record_fn}

// Simulate ten replacement failures.
for (let i = 0; i < 10; i += 1) {{
  _recordPresentationReplacementFailure('state', new Error('boom ' + i));
}}

// Ring buffer stays bounded — the older entries have been shifted out.
assert.equal(
  _presentationReplacementDiagnostics.length,
  _PRESENTATION_REPLACEMENT_DIAGNOSTIC_MAX,
  'diagnostics ring buffer must clamp to its configured maximum'
);
// The retained entries are the most recent ones.
assert.equal(
  _presentationReplacementDiagnostics[
    _presentationReplacementDiagnostics.length - 1
  ].message,
  'boom 9'
);
// Each failure logged exactly once — no re-emission cascade.
assert.equal(warnCount, 10);

// Even if the record helper is called with a producer that throws when
// stringified, it swallows the loop-guard and does not throw.
_recordPresentationReplacementFailure('state', {{
  get message() {{ throw new Error('cannot stringify'); }},
}});
"""

    result = subprocess.run(
        ["node", "-e", script], check=False, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(not _node_available(), reason="node is required for runtime contracts")
def test_apply_full_sync_recovers_when_state_render_throws() -> None:
    """A ``handleStateUpdate`` fault must not leak the pre-apply DOM state.

    The clear runs before the render, so if the render throws, the operator
    sees an empty board rather than the stale rendering they had before the
    resync began. Recovery of the full DOM happens on the next successful
    full_sync — meanwhile, the diagnostics ring records the fault.
    """
    html = _dashboard_html()

    apply_fn = _function(html, "_applyFullSyncMessage")
    clear_fn = _function(html, "_clearAllAlertAndHealthUI")
    record_fn = _function(html, "_recordPresentationReplacementFailure")
    diag_var = _var_decl(html, "_presentationReplacementDiagnostics")
    diag_cap_var = _var_decl(html, "_PRESENTATION_REPLACEMENT_DIAGNOSTIC_MAX")

    # We only need a tiny fake for _numericRevision, refresh, and staleness.
    script = f"""
const assert = require('node:assert/strict');

const registry = {{}};
function element(id) {{
  const attrs = new Map();
  return {{
    id, hidden: false, textContent: 'stale', innerHTML: '<span>stale</span>',
    classList: {{
      add() {{}}, remove() {{}}, toggle() {{}}, contains() {{ return false; }},
    }},
    setAttribute(name, value) {{ attrs.set(name, String(value)); }},
    getAttribute(name) {{ return attrs.has(name) ? attrs.get(name) : null; }},
    removeAttribute(name) {{ attrs.delete(name); }},
    hasAttribute(name) {{ return attrs.has(name); }},
    querySelector() {{ return null; }},
  }};
}}
[
  'alert-center', 'alert-center-list', 'alert-center-count',
  'alert-center-severity-label', 'alert-center-live',
  'diagnostic-facts', 'diagnostic-facts-list',
  'terminal-audit-health', 'terminal-audit-health-detail',
  'quality-gate-health', 'quality-gate-health-detail',
  'repo-hygiene-health', 'repo-hygiene-health-icon',
  'repo-hygiene-health-title', 'repo-hygiene-health-summary',
  'repo-hygiene-inventory', 'repo-hygiene-overdue',
  'repo-hygiene-overdue-list', 'repo-hygiene-errors',
  'repo-hygiene-error-list',
  'auth-health-banner', 'auth-health-planes', 'auth-health-details',
  'running-agents',
].forEach((id) => {{ registry[id] = element(id); }});
const document = {{ getElementById(id) {{ return registry[id] || null; }} }};

// Minimum module state the apply path expects — assign before the source
// blocks below so the try/catch phases can see them.
let wsFullSyncPending = true;
let wsApplyingFullSync = false;
let wsLastAppliedStateRevision = null;
let wsLastAppliedIssueRevision = null;
let wsLastFullSyncDeliverySeq = 0;
let wsHighestObservedDeliverySeq = 0;
let wsDeliverySeq = 0;
let wsEpoch = null;
let wsReconciling = true;
let wsFullSyncRetryAttempt = 0;
let wsBufferedMessages = [];
let currentProjects = [];
function _numericRevision(value) {{
  return typeof value === 'number' ? value : null;
}}
function _scheduleFullSyncRetry() {{}}
function clearFullSyncRetryTimer() {{}}
function setWebSocketStatus() {{}}
function refreshOpenDetailPanel() {{}}
function _setTrackerStaleBanner() {{}}
function _updateTaskStateStaleBanner() {{}}
function filterByProject(x) {{ return x; }}
function renderBoard() {{}}
function _observeWebSocketEnvelope() {{ return true; }}
function _heartbeatNeedsFullSync() {{ return false; }}
function _markWebSocketStale() {{}}
function _bufferWebSocketMessage() {{}}
function _routeWebSocketMessage() {{}}
function _backfillConsoleTranscript() {{}}
let _activeConsoleProject = null;

let stateRenderInvocations = 0;
function handleStateUpdate(state) {{
  stateRenderInvocations += 1;
  throw new Error('deliberate state render fault');
}}

let warnCount = 0;
const console = {{ warn: () => {{ warnCount += 1; }} }};

{diag_var}
{diag_cap_var}
{record_fn}
{clear_fn}
{apply_fn}

// Message shape mirrors the real full_sync envelope.
_applyFullSyncMessage({{
  state: {{ paused: false }},
  issues: {{}},
  state_revision: 4,
  issue_revision: 7,
  epoch: 'test-epoch',
  delivery_seq: 42,
}});

// The clear ran successfully — the list containers are emptied even though
// the render throw prevented handleStateUpdate from repopulating them.
// This is the operator-visible property that guards against
// mixed-generation output: no stale alert survives beside a blank board.
for (const id of [
  'alert-center-list',
  'diagnostic-facts-list',
  'repo-hygiene-inventory',
  'repo-hygiene-overdue-list',
  'repo-hygiene-error-list',
  'auth-health-planes',
  'auth-health-details',
  'running-agents',
]) {{
  assert.equal(registry[id].innerHTML, '',
    'innerHTML for ' + id + ' should be empty after atomic clear');
}}

// The failing state render was captured exactly once as a bounded
// diagnostic — no re-emission into the alert stream.
assert.equal(stateRenderInvocations, 1);
assert.equal(_presentationReplacementDiagnostics.length, 1);
assert.equal(_presentationReplacementDiagnostics[0].phase, 'state');
assert.equal(warnCount, 1);

// The full_sync path still committed the delivery watermark so a future
// snapshot can proceed. The state revision is committed even when the
// render throws, because the raw fact — the snapshot arrived — is not
// disputed by a downstream rendering fault.
assert.equal(wsLastAppliedStateRevision, 4);
assert.equal(wsLastAppliedIssueRevision, 7);
assert.equal(wsLastFullSyncDeliverySeq, 42);
assert.equal(wsFullSyncPending, false);
assert.equal(wsReconciling, false);
"""

    result = subprocess.run(
        ["node", "-e", script], check=False, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(not _node_available(), reason="node is required for runtime contracts")
def test_repeated_identical_snapshots_do_not_duplicate_announcements() -> None:
    """Two identical authoritative snapshots collapse to one announcement.

    Combines the atomic clear with ``renderAlertCenter`` to model the browser
    receiving the same snapshot twice (e.g., a full_sync followed by an
    identical incremental state message). The dedicated live region must not
    re-announce, and the alert list must not double up.
    """
    html = _dashboard_html()

    helpers = "\n".join(
        [
            *(
                re.search(rf"const {name} = [^;]+;", html).group(0)
                for name in (
                    "ALERT_RENDER_TITLE_MAX",
                    "ALERT_RENDER_SUMMARY_MAX",
                    "ALERT_RENDER_EXPLANATION_MAX",
                    "ALERT_RENDER_ACTION_MAX",
                    "ALERT_RENDER_SOURCE_MAX",
                    "ALERT_RENDER_DIAGNOSTIC_MAX",
                    "ALERT_RENDER_TRUNCATION_MARKER",
                    "ALERT_SEVERITY_RANK",
                )
            ),
            *(
                _function(html, name)
                for name in (
                    "alertSafeText",
                    "alertBoundedText",
                    "alertPrimaryText",
                    "alertDetailText",
                    "alertActionText",
                    "alertDiagnosticText",
                    "renderAlertItem",
                    "getAlertSeverity",
                    "getHighestAlertSeverity",
                    "getSeverityLabel",
                    "alertStableIdentity",
                    "dedupeAlertFacts",
                    "setAlertCenterExpanded",
                    "focusBoardAfterAlertCenter",
                    "renderAlertCenter",
                )
            ),
        ]
    )

    script = f"""
const assert = require('node:assert/strict');

function element() {{
  const attrs = new Map();
  return {{
    hidden: false, textContent: '', innerHTML: '', focused: false,
    setAttribute(name, value) {{ attrs.set(name, String(value)); }},
    getAttribute(name) {{ return attrs.has(name) ? attrs.get(name) : null; }},
    removeAttribute(name) {{ attrs.delete(name); }},
    hasAttribute(name) {{ return attrs.has(name); }},
    focus() {{ this.focused = true; }},
    querySelector() {{ return null; }},
    contains() {{ return false; }},
  }};
}}
const center = element();
const list = element();
const count = element();
const severity = element();
const live = element();
const board = element();
center.setAttribute('data-alert-count', '0');
center.setAttribute('aria-expanded', 'false');
const document = {{
  activeElement: null,
  getElementById(id) {{
    return {{
      'alert-center': center, 'alert-center-list': list,
      'alert-center-count': count, 'alert-center-severity-label': severity,
      'alert-center-live': live, board,
    }}[id] || null;
  }},
}};
function esc(value) {{ return String(value || ''); }}

{helpers}

const snapshot = [
  {{stable_id: 'quality_gate:proj:task', severity: 'error', summary: 'Gate failed'}},
  {{stable_id: 'auth_health:worker', severity: 'warning', summary: 'Token stale'}},
];

renderAlertCenter(snapshot);
const firstItems = (list.innerHTML.match(/class=\"alert-item\"/g) || []).length;
const firstLive = live.textContent;
const firstSignature = center.getAttribute('data-alert-signature');

// Identical replay — no additional items, and the sr-only live region
// stays with its previous announcement (no re-announcement flicker).
renderAlertCenter(snapshot);
const secondItems = (list.innerHTML.match(/class=\"alert-item\"/g) || []).length;
const secondLive = live.textContent;
const secondSignature = center.getAttribute('data-alert-signature');

assert.equal(secondItems, firstItems,
  'identical snapshots must not duplicate alert-item DOM nodes');
assert.equal(secondSignature, firstSignature,
  'the stable announcement signature must be identical for identical snapshots');
assert.equal(secondLive, firstLive,
  'the sr-only live region must not re-announce on an identical snapshot');
"""

    result = subprocess.run(
        ["node", "-e", script], check=False, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
