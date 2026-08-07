"""Behavioural contracts for compact dashboard health surfaces."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest


def _dashboard() -> str:
    return (
        Path(__file__).resolve().parents[1] / "oompah" / "templates" / "dashboard.html"
    ).read_text(encoding="utf-8")


def _extract_function(name: str) -> str:
    source = _dashboard()
    match = re.search(rf"function\s+{re.escape(name)}\s*\([^)]*\)\s*\{{", source)
    assert match, f"dashboard function {name} was not found"
    depth = 0
    for index in range(match.start(), len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[match.start() : index + 1]
    raise AssertionError(f"dashboard function {name} was not terminated")


def _run(functions: tuple[str, ...], body: str) -> object:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for dashboard behaviour tests")
    source = "\n".join(_extract_function(name) for name in functions)
    result = subprocess.run(
        [node, "-e", source + "\n" + body],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_health_banners_are_accessible_and_hidden_by_default() -> None:
    html = _dashboard()
    for element_id, label in (
        ("terminal-audit-health", "Terminal-audit health"),
        ("quality-gate-health", "Branch quality gate health"),
    ):
        match = re.search(rf'<[^>]+id="{element_id}"[^>]*>', html)
        assert match is not None
        tag = match.group(0)
        assert "hidden" in tag
        assert 'role="status"' in tag
        assert 'aria-live="polite"' in tag
        assert f'aria-label="{label}"' in tag


def test_terminal_audit_rotation_and_backlog_stay_hidden_until_action_required() -> None:
    result = _run(
        ("renderTerminalAuditHealth",),
        r"""
const banner = {hidden: false};
const detail = {textContent: 'old'};
const document = {getElementById: id => id === 'terminal-audit-health' ? banner : detail};
const health = {
  launch_failure_count: 2, transport_failure_count: 1,
  stale_pending_count: 4, oldest_pending_age_seconds: 4000,
  retry_exhausted_count: 0, policy_incompatibility_count: 0,
  finalization_failure_count: 0, quarantined_count: 0,
};
renderTerminalAuditHealth(health, []);
const automatic = {hidden: banner.hidden, detail: detail.textContent};
health.retry_exhausted_count = 1;
renderTerminalAuditHealth(health, [{
  source: 'terminal_audit_health:retry_exhausted',
  level: 'error', action_required: true,
}]);
console.log(JSON.stringify({automatic, exhausted: {
  hidden: banner.hidden, detail: detail.textContent,
}}));
""",
    )
    assert result["automatic"] == {"hidden": True, "detail": ""}
    assert result["exhausted"]["hidden"] is False
    assert "exhausted retries" in result["exhausted"]["detail"]


def test_terminal_audit_banner_clears_after_actionable_condition_recovers() -> None:
    result = _run(
        ("renderTerminalAuditHealth",),
        r"""
const banner = {hidden: true};
const detail = {textContent: ''};
const document = {getElementById: id => id === 'terminal-audit-health' ? banner : detail};
const health = {retry_exhausted_count: 1};
renderTerminalAuditHealth(health, [{
  source: 'terminal_audit_health:retry_exhausted', action_required: true,
}]);
const before = {hidden: banner.hidden, detail: detail.textContent};
renderTerminalAuditHealth({retry_exhausted_count: 0}, []);
console.log(JSON.stringify({before, after: {
  hidden: banner.hidden, detail: detail.textContent,
}}));
""",
    )
    assert result["before"]["hidden"] is False
    assert result["after"] == {"hidden": True, "detail": ""}


def test_running_quality_gate_is_task_local_until_operator_action_is_required() -> None:
    result = _run(
        ("renderQualityGateHealth",),
        r"""
const banner = {hidden: false};
const detail = {textContent: 'old'};
const document = {getElementById: id => id === 'quality-gate-health' ? banner : detail};
const running = {status: 'running', action_required: false, active: [{
  task_id: 'TASK-1', project_id: 'project-a', head_sha: 'abcdef1234567890',
  authority_generation: 'gate-1',
}]};
renderQualityGateHealth(running);
const automatic = {hidden: banner.hidden, detail: detail.textContent};
running.action_required = true;
renderQualityGateHealth(running);
console.log(JSON.stringify({automatic, actionable: {
  hidden: banner.hidden, detail: detail.textContent,
}}));
""",
    )
    assert result["automatic"] == {"hidden": True, "detail": ""}
    assert result["actionable"]["hidden"] is False
    assert "project-a/TASK-1" in result["actionable"]["detail"]


def test_healthy_repo_hygiene_does_not_consume_dashboard_space() -> None:
    result = _run(
        ("renderRepoHygieneHealth",),
        r"""
function node() {
  return {hidden: false, innerHTML: 'old', textContent: 'old',
    classList: {toggle: function() {}}};
}
const ids = {};
[
  'repo-hygiene-health', 'repo-hygiene-health-icon',
  'repo-hygiene-health-title', 'repo-hygiene-health-summary',
  'repo-hygiene-inventory', 'repo-hygiene-overdue',
  'repo-hygiene-overdue-list', 'repo-hygiene-errors',
  'repo-hygiene-error-list',
].forEach(id => ids[id] = node());
const document = {getElementById: id => ids[id]};
renderRepoHygieneHealth({is_healthy: true});
console.log(JSON.stringify({
  hidden: ids['repo-hygiene-health'].hidden,
  inventory: ids['repo-hygiene-inventory'].innerHTML,
  overdue: ids['repo-hygiene-overdue-list'].innerHTML,
  errors: ids['repo-hygiene-error-list'].innerHTML,
}));
""",
    )
    assert result == {"hidden": True, "inventory": "", "overdue": "", "errors": ""}


def test_transient_auth_failures_do_not_reserve_global_dashboard_space() -> None:
    result = _run(
        ("esc", "renderAuthHealthBanner"),
        r"""
const banner = {hidden: false};
const planes = {innerHTML: 'old'};
const details = {innerHTML: 'old'};
const document = {
  getElementById: id => id === 'auth-health-banner'
    ? banner : id === 'auth-health-planes' ? planes : details,
  createElement: function() {
    let encoded = '';
    return {
      set textContent(value) {
        encoded = String(value).replace(/&/g, '&amp;').replace(/</g, '&lt;')
          .replace(/>/g, '&gt;').replace(/\"/g, '&quot;');
      },
      get innerHTML() { return encoded; },
    };
  },
};
renderAuthHealthBanner({
  operator: {status: 'ok'},
  worker: {status: 'degraded', recent_401_count: 5,
    token_ever_minted: true, token_ever_accepted: false},
}, []);
console.log(JSON.stringify({
  hidden: banner.hidden, planes: planes.innerHTML, details: details.innerHTML,
}));
""",
    )
    assert result == {"hidden": True, "planes": "", "details": ""}
