"""Headless-browser regression coverage for the dashboard alert experience.

The dashboard is deliberately a single HTML/JavaScript page.  These tests run
that exact template in headless Chrome with an in-page WebSocket double, which
lets us exercise alert rendering, disclosure behaviour, responsive layout, and
full-sync recovery without a server, network, or pixel snapshot.
"""

from __future__ import annotations

import base64
import html as html_lib
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest


_CHROME = shutil.which("google-chrome") or shutil.which("chromium")
_ROOT = Path(__file__).resolve().parents[1]
_TEMPLATE = _ROOT / "oompah" / "templates" / "dashboard.html"
_RESULT_ATTRIBUTE = "data-dashboard-alert-test-result"
_RAW_TRANSCRIPT_MARKER = "RAW-TRANSCRIPT-MUST-REMAIN-DISCLOSED"


pytestmark = pytest.mark.skipif(
    _CHROME is None,
    reason="headless Chrome is required for dashboard browser regression coverage",
)


def _issue(identifier: str = "OOMPAH-100") -> dict[str, object]:
    return {
        "identifier": identifier,
        "title": "Task remains reachable beneath alerts",
        "description": "A board card used to prove task navigation remains available.",
        "state": "Open",
        "priority": 1,
        "project_id": "proj-dashboard",
    }


def _healthy_repo_hygiene() -> dict[str, object]:
    counts = {
        "active": 1,
        "dirty": 0,
        "unmerged": 0,
        "terminal_protected": 0,
        "shared_owner": 0,
        "safely_prunable": 0,
    }
    return {
        "is_healthy": True,
        "summary": "Repository hygiene healthy",
        "worktrees": counts,
        "branches_local": counts,
        "branches_remote": counts,
        "overdue_artifacts": [],
        "cleanup_errors": [],
    }


def _state(
    alerts: list[dict[str, object]],
    *,
    audit_age: int = 0,
    quality_status: str = "idle",
    policy_denials: int = 0,
) -> dict[str, object]:
    """Return a complete, production-shaped state payload for the dashboard."""
    return {
        "paused": False,
        "http_auth": {"enabled": False},
        "alerts": alerts,
        "terminal_audit_health": {
            "policy_incompatibility_count": 0,
            "launch_failure_count": 0,
            "transport_failure_count": 0,
            "retry_exhausted_count": 0,
            "oldest_pending_age_seconds": audit_age,
            "scan_complete": True,
        },
        "quality_gates": {
            "status": quality_status,
            "active": [
                {
                    "task_id": "OOMPAH-100",
                    "project_id": "proj-dashboard",
                    "head_sha": "0123456789abcdef",
                    "authority_generation": "generation-1",
                }
            ]
            if quality_status != "idle"
            else [],
        },
        "orchestrator_metrics": {
            "maintenance": {"repo_hygiene_health": _healthy_repo_hygiene()}
        },
        "auth_health": {
            "operator": {"status": "ok"},
            "worker": {"status": "ok", "policy_denial_count": policy_denials},
        },
        "agent_totals": {"total_tokens": 0, "estimated_cost": 0},
        "budget": {},
        "projects": [],
        "running": [],
        "owner_claims": [],
    }


def _browser_bootstrap() -> str:
    """Install an in-page WebSocket double before the production script runs."""
    return """
<script>
window.__dashboardTestSockets = [];
window.__dashboardTestFetches = [];
window.fetch = async function() {
  window.__dashboardTestFetches.push(Array.from(arguments));
  return {ok: false, status: 503, json: async function() { return {}; }};
};
window.WebSocket = class DashboardTestSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;
  constructor(url) {
    this.url = url;
    this.readyState = DashboardTestSocket.OPEN;
    this.sent = [];
    window.__dashboardTestSockets.push(this);
  }
  send(payload) { this.sent.push(payload); }
  close() {
    this.readyState = DashboardTestSocket.CLOSED;
    if (this.onclose) this.onclose();
  }
  open() { if (this.onopen) this.onopen(); }
  deliver(message) {
    if (this.onmessage) this.onmessage({data: JSON.stringify(message)});
  }
};
</script>
"""


def _run_dashboard(
    tmp_path: Path,
    *,
    script: str,
    viewport: tuple[int, int] = (1440, 900),
) -> dict[str, object]:
    """Run a scenario after the real dashboard script and return its JSON result."""
    html = _TEMPLATE.read_text(encoding="utf-8")
    html = html.replace("</head>", _browser_bootstrap() + "</head>", 1)
    result_script = f"""
<script>
(function() {{
  function finish(value) {{
    document.documentElement.setAttribute(
      "{_RESULT_ATTRIBUTE}",
      btoa(unescape(encodeURIComponent(JSON.stringify(value))))
    );
  }}
  try {{
    {script}
  }} catch (error) {{
    finish({{error: String(error && error.stack || error)}});
  }}
}})();
</script>
"""
    html = html.replace("</body>", result_script + "</body>", 1)
    scenario_path = tmp_path / "dashboard-alert-scenario.html"
    scenario_path.write_text(html, encoding="utf-8")

    profile_dir = tmp_path / "chrome-profile"
    proc = subprocess.run(
        [
            _CHROME,
            "--headless=new",
            "--no-sandbox",
            "--disable-gpu",
            "--disable-dev-shm-usage",
            f"--user-data-dir={profile_dir}",
            f"--window-size={viewport[0]},{viewport[1]}",
            "--dump-dom",
            scenario_path.as_uri(),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    match = re.search(rf'{_RESULT_ATTRIBUTE}="([^"]+)"', proc.stdout)
    assert match, f"dashboard scenario did not publish a result: {proc.stderr}"
    encoded = html_lib.unescape(match.group(1))
    result = json.loads(base64.b64decode(encoded).decode("utf-8"))
    assert "error" not in result, result["error"]
    return result


def _js(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def _mixed_alerts() -> list[dict[str, object]]:
    return [
        {
            "source": "integration:rebase_conflict:OOMPAH-100",
            "title": "Integration rebase conflict",
            "detail": "The candidate must be rebased before it can merge.",
            "action": "Resolve the conflict and submit the rebased head.",
        },
        {
            "source": "terminal_audit:stale_backlog:OOMPAH-101",
            "title": "Terminal audit backlog is stale",
            "detail": "The oldest terminal audit has waited longer than the policy window.",
            "action": "Investigate the audit queue before dispatching more work.",
        },
        {
            "source": "operator:action_required:OOMPAH-102",
            "title": "Operator action is required",
            "detail": "A real external prerequisite needs an operator decision.",
            "action": "Complete the prerequisite, then retry the task.",
            "diagnostic": _RAW_TRANSCRIPT_MARKER + "\n" + ("line from transcript\n" * 300),
        },
    ]


class TestDashboardAlertExperience:
    """Production-shaped alert flows through the browser's real DOM and CSS."""

    def test_mixed_payload_is_compact_truthful_and_keeps_a_task_reachable(
        self, tmp_path: Path
    ) -> None:
        state = _state(
            _mixed_alerts(), audit_age=7200, quality_status="failed", policy_denials=2
        )
        issues = {"Open": [_issue()]}
        result = _run_dashboard(
            tmp_path,
            script=f"""
const state = {_js(state)};
const issues = {_js(issues)};
handleStateUpdate(state);
renderBoard(issues);
const center = document.getElementById('alert-center');
const toggle = center.querySelector('.alert-center-toggle');
const list = document.getElementById('alert-center-list');
const board = document.getElementById('board');
const collapsed = {{
  expanded: center.getAttribute('aria-expanded'),
  toggleExpanded: toggle.getAttribute('aria-expanded'),
  listDisplay: getComputedStyle(list).display,
  centerHeight: Math.ceil(center.getBoundingClientRect().height),
  boardTop: Math.floor(board.getBoundingClientRect().top),
  boardHeight: Math.floor(board.getBoundingClientRect().height),
  viewportHeight: window.innerHeight,
}};
toggle.click();
const visibleText = document.body.innerText;
const titles = {_js([alert['title'] for alert in _mixed_alerts()])};
const titleCounts = Object.fromEntries(titles.map(function(title) {{
  return [title, visibleText.split(title).length - 1];
}}));
const focusables = Array.from(document.querySelectorAll(
  'button, [href], input, select, textarea, summary, [tabindex]:not([tabindex="-1"])'
));
toggle.focus();
finish({{
  collapsed: collapsed,
  expanded: center.getAttribute('aria-expanded'),
  toggleExpanded: toggle.getAttribute('aria-expanded'),
  alertCount: Number(center.getAttribute('data-alert-count')),
  detailsText: list.innerText,
  titleCounts: titleCounts,
  rawTranscriptVisible: visibleText.includes({_js(_RAW_TRANSCRIPT_MARKER)}),
  diagnostics: list.querySelectorAll('details.alert-diagnostics').length,
  diagnosticOpen: list.querySelector('details.alert-diagnostics').open,
  diagnosticFocusableAfterToggle:
    focusables.indexOf(list.querySelector('summary')) > focusables.indexOf(toggle),
  focusedElement: document.activeElement.className,
  ariaLive: document.getElementById('alert-center-live') ? document.getElementById('alert-center-live').getAttribute('aria-live') : null,
  ariaLabel: list.getAttribute('aria-label'),
  taskCardVisible: !!document.querySelector('#board .card'),
  terminalAuditVisible: !document.getElementById('terminal-audit-health').hidden,
  qualityGateVisible: !document.getElementById('quality-gate-health').hidden,
  repoHygieneVisible: !document.getElementById('repo-hygiene-health').hidden,
  authPolicyVisible: !document.getElementById('auth-health-banner').hidden,
}});
""",
        )

        assert result["collapsed"]["expanded"] == "false"
        assert result["collapsed"]["toggleExpanded"] == "false"
        assert result["collapsed"]["listDisplay"] == "none"
        assert result["collapsed"]["centerHeight"] <= 80
        assert result["collapsed"]["boardTop"] < result["collapsed"]["viewportHeight"]
        assert result["collapsed"]["boardHeight"] > 0

        assert result["expanded"] == "true"
        assert result["toggleExpanded"] == "true"
        assert result["alertCount"] == 3
        assert result["titleCounts"] == {
            "Integration rebase conflict": 1,
            "Terminal audit backlog is stale": 1,
            "Operator action is required": 1,
        }
        assert result["rawTranscriptVisible"] is False
        assert "Branch quality gate health" not in result["detailsText"]
        assert "Repository hygiene healthy" not in result["detailsText"]
        assert "intentional task-policy denial" not in result["detailsText"]
        assert result["diagnostics"] == 1
        assert result["diagnosticOpen"] is False
        assert result["diagnosticFocusableAfterToggle"] is True
        assert result["focusedElement"] == "alert-center-toggle"
        assert result["ariaLive"] == "polite"
        assert result["ariaLabel"] == "Active alert details"
        assert result["taskCardVisible"] is True

        # Status panels retain their distinct, non-duplicated semantics while
        # only actionable alert records appear in the expandable center.
        # The terminal-audit panel is hidden when an actionable terminal_audit: alert
        # is already shown once in the alert center, avoiding duplication.
        assert result["terminalAuditVisible"] is False
        assert result["qualityGateVisible"] is True
        assert result["repoHygieneVisible"] is True
        assert result["authPolicyVisible"] is True

    def test_many_alerts_scroll_inside_the_center_at_a_phone_viewport(
        self, tmp_path: Path
    ) -> None:
        alerts = [
            {
                "source": f"operator:action_required:{index}",
                "title": f"Actionable alert {index}",
                "detail": "An operator must make a concrete decision.",
                "action": "Inspect the linked task and take the stated action.",
                "diagnostic": (
                    _RAW_TRANSCRIPT_MARKER if index == 0 else "diagnostic"
                )
                + "\n"
                + ("x" * 5000),
            }
            for index in range(32)
        ]
        result = _run_dashboard(
            tmp_path,
            viewport=(390, 844),
            script=f"""
handleStateUpdate({_js(_state(alerts))});
renderBoard({_js({'Open': [_issue()]})});
const center = document.getElementById('alert-center');
const toggle = center.querySelector('.alert-center-toggle');
const list = document.getElementById('alert-center-list');
const board = document.getElementById('board');
const collapsedBoard = board.getBoundingClientRect();
toggle.click();
const details = list.querySelector('details.alert-diagnostics');
const summary = details.querySelector('summary');
const rawVisibleWhileClosed = document.body.innerText.includes({_js(_RAW_TRANSCRIPT_MARKER)});
summary.click();
finish({{
  count: Number(center.getAttribute('data-alert-count')),
  expanded: center.getAttribute('aria-expanded'),
  listClientHeight: list.clientHeight,
  listScrollHeight: list.scrollHeight,
  overflowY: getComputedStyle(list).overflowY,
  boardTop: Math.floor(collapsedBoard.top),
  boardHeight: Math.floor(collapsedBoard.height),
  viewportHeight: window.innerHeight,
  rawVisibleWhileClosed: rawVisibleWhileClosed,
  diagnosticExpanded: details.open,
  diagnosticTextLength: details.querySelector('pre').textContent.length,
  scriptsInDiagnostic: details.querySelectorAll('script').length,
}});
""",
        )

        assert result["count"] == 32
        assert result["expanded"] == "true"
        assert 0 < result["listClientHeight"] <= 300
        assert result["listScrollHeight"] > result["listClientHeight"]
        assert result["overflowY"] == "auto"
        assert result["boardTop"] < result["viewportHeight"]
        assert result["boardHeight"] > 0
        assert result["rawVisibleWhileClosed"] is False
        assert result["diagnosticExpanded"] is True
        assert result["diagnosticTextLength"] <= 4000
        assert result["scriptsInDiagnostic"] == 0

    def test_sequence_gap_full_sync_replaces_stale_alerts_without_reloading(
        self, tmp_path: Path
    ) -> None:
        running_state = _state(
            _mixed_alerts(), audit_age=7200, quality_status="running", policy_denials=1
        )
        running_state["terminal_audit_health"]["transport_failure_count"] = 1
        failed_state = _state(
            _mixed_alerts(), audit_age=7200, quality_status="failed", policy_denials=1
        )
        recovered_state = _state([], audit_age=0, quality_status="idle", policy_denials=0)
        issues = {"Open": [_issue("OOMPAH-103")]}
        result = _run_dashboard(
            tmp_path,
            script=f"""
const runningState = {_js(running_state)};
const failedState = {_js(failed_state)};
const recoveredState = {_js(recovered_state)};
const recoveredIssues = {_js(issues)};
const socket = window.__dashboardTestSockets[0];
socket.open();
socket.deliver({{
  type: 'state', epoch: 'browser-test', delivery_seq: 1, state_revision: 1,
  data: runningState,
}});
const runningQualityText = document.getElementById('quality-gate-health-detail').textContent;
socket.deliver({{
  type: 'state', epoch: 'browser-test', delivery_seq: 2, state_revision: 2,
  data: failedState,
}});
const failedQualityText = document.getElementById('quality-gate-health-detail').textContent;
socket.deliver({{
  type: 'state', epoch: 'browser-test', delivery_seq: 4, state_revision: 4,
  data: failedState,
}});
const fullSyncRequested = socket.sent.some(function(raw) {{
  return JSON.parse(raw).action === 'full_sync';
}});
socket.deliver({{
  type: 'full_sync', epoch: 'browser-test', delivery_seq: 5,
  state_revision: 5, issue_revision: 5,
  state: recoveredState, issues: recoveredIssues,
}});
const center = document.getElementById('alert-center');
const list = document.getElementById('alert-center-list');
finish({{
  fullSyncRequested: fullSyncRequested,
  runningQualityText: runningQualityText,
  failedQualityText: failedQualityText,
  alertCount: Number(center.getAttribute('data-alert-count')),
  expanded: center.getAttribute('aria-expanded'),
  alertItems: list.querySelectorAll('.alert-item').length,
  terminalAuditHidden: document.getElementById('terminal-audit-health').hidden,
  qualityGateHidden: document.getElementById('quality-gate-health').hidden,
  authHealthHidden: document.getElementById('auth-health-banner').hidden,
  staleTitleVisible: document.body.innerText.includes('Terminal audit backlog is stale'),
  recoveredTaskVisible: !!document.querySelector('#board .card[data-id="OOMPAH-103"]'),
  status: document.getElementById('status-text').textContent,
}});
""",
        )

        assert result["fullSyncRequested"] is True
        assert result["runningQualityText"].startswith("running")
        assert result["failedQualityText"].startswith("failed")
        assert result["alertCount"] == 0
        assert result["expanded"] == "false"
        assert result["alertItems"] == 0
        assert result["terminalAuditHidden"] is True
        assert result["qualityGateHidden"] is True
        # Auth health banner remains visible as status information even when
        # all planes are healthy; it is only hidden when hiddenByAlert is true.
        assert result["authHealthHidden"] is False
        assert result["staleTitleVisible"] is False
        assert result["recoveredTaskVisible"] is True
        assert result["status"] == "Connected"
