"""Static contract tests for the dashboard terminal-audit experience."""

from __future__ import annotations

import re
from pathlib import Path


def _dashboard() -> str:
    return (
        Path(__file__).resolve().parents[1]
        / "oompah"
        / "templates"
        / "dashboard.html"
    ).read_text(encoding="utf-8")


def _script() -> str:
    html = _dashboard()
    scripts = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    assert scripts
    return max(scripts, key=len)


def _function_body(script: str, name: str) -> str:
    match = re.search(rf"function\s+{re.escape(name)}\s*\([^)]*\)\s*\{{", script)
    assert match, f"missing {name}"
    start = match.end() - 1
    depth = 0
    for index in range(start, len(script)):
        if script[index] == "{":
            depth += 1
        elif script[index] == "}":
            depth -= 1
            if depth == 0:
                return script[start + 1 : index]
    raise AssertionError(f"unterminated {name}")


def _column_config(script: str, key: str) -> str:
    match = re.search(rf"\{{key:\s*'{re.escape(key)}'[^}}]+\}}", script)
    assert match, f"missing column {key}"
    return match.group(0)


def test_in_validation_is_one_core_responsive_board_column() -> None:
    script = _script()
    config = _column_config(script, "In Validation")
    columns = re.findall(r"\{key:\s*'([^']+)'", script)

    assert config.count("key: 'In Validation'") == 1
    assert "label: 'In Validation'" in config
    assert "status: 'In Validation'" in config
    assert "base: true" in config
    assert columns.count("In Validation") == 1
    assert "columnKeyForStatus(issue.state" in script
    assert "data-state=\"${col}\"" in script


def test_validation_participates_in_inflight_filter_and_epic_rollup() -> None:
    script = _script()
    assert "'In Validation'" in _function_body(script, "_isIndividuallyInFlight")
    assert "'In Validation'" in _function_body(script, "applyHideMergedFilter")
    assert "'In Validation'," in _function_body(script, "childCountsAreMergeReady")


def test_audit_detail_renders_requested_phase_attempt_revision_models_and_result() -> None:
    script = _script()
    body = _function_body(script, "renderTerminalAuditSummary")

    for label in (
        "Requested target",
        "Attempt",
        "Evidence revision",
        "Contributor models",
        "Auditor provider/model",
        "Latest result",
    ):
        assert label in body
    assert "terminalAuditPhase(audit, record, attempt)" in body
    assert "terminalAuditInstructions(result, audit)" in body
    assert 'role="status"' in body
    assert 'role="alert"' not in body


def test_audit_fields_escape_unknown_and_long_values() -> None:
    script = _script()

    for name in (
        "terminalAuditText",
        "terminalAuditIdentity",
        "terminalAuditRevision",
        "terminalAuditContributors",
        "terminalAuditAuditor",
    ):
        assert name in script
    body = _function_body(script, "renderTerminalAuditSummary")
    assert "esc(terminalAuditRevision" in body
    assert "esc(terminalAuditContributors" in body
    assert "esc(terminalAuditAuditor" in body
    assert "overflow-wrap: anywhere" in _dashboard()


def test_audit_summary_consumes_safe_api_projection_fields() -> None:
    script = _script()

    attempt = _function_body(script, "terminalAuditLatestAttempt")
    assert "attempt_count" in attempt

    identity = _function_body(script, "terminalAuditIdentity")
    assert "provider_model" in identity
    assert "model_id" in identity

    auditor = _function_body(script, "terminalAuditAuditor")
    assert "auditor_provider_model" in auditor

    result = _function_body(script, "terminalAuditResult")
    assert "latest_classification" in result
    assert "latest_summary" in result

    summary = _function_body(script, "renderTerminalAuditSummary")
    assert "terminalAuditResultSummary(result)" in summary
    assert "terminal-audit-result-summary" in summary


def test_pending_audit_is_status_not_global_alert() -> None:
    script = _script()
    body = _function_body(script, "renderTerminalAuditSummary")

    assert 'role="status" aria-live="polite"' in body
    assert "terminalAuditPhase" in body
    assert "alerts-banner" not in body


def test_override_is_fail_closed_and_visible_only_with_explicit_permission() -> None:
    script = _script()
    gate = _function_body(script, "terminalAuditCanOverride")
    render = _function_body(script, "renderTerminalAuditOverride")

    assert "=== true" in gate
    assert "can_override" in gate
    assert "override_authorized" in gate
    assert "if (!terminalAuditCanOverride(detail, audit)) return ''" in render
    assert "Authorized project owners" in render
    assert "owner_override_allowed" in gate


def test_override_requires_target_confirmation_and_reason() -> None:
    script = _script()
    render = _function_body(script, "renderTerminalAuditOverride")
    submit = _function_body(script, "submitTerminalAuditOverride")

    assert 'select id="terminal-audit-target-' in render
    assert 'type="checkbox" required' in render
    assert 'textarea id="terminal-audit-reason-' in render
    assert "if (!target)" in submit
    assert "if (!confirmEl.checked)" in submit
    assert "if (!reason)" in submit
    assert "window.confirm" in submit


def test_override_request_uses_existing_status_api_and_audit_override_fields() -> None:
    script = _script()
    body = _function_body(script, "submitTerminalAuditOverride")

    assert "issueApiUrl(identifier)" in body
    assert "method: 'PATCH'" in body
    assert "status: target" in body
    assert "audit_override: true" in body
    assert "audit_override_target: target" in body
    assert "audit_override_confirmed: true" in body
    assert "audit_override_reason: reason" in body


def test_override_has_loading_and_error_paths() -> None:
    script = _script()
    body = _function_body(script, "submitTerminalAuditOverride")

    assert "button.disabled = true" in body
    assert "aria-busy" in body
    assert "if (!res.ok)" in body
    assert "setTerminalAuditOverrideError(identifier, message)" in body
    assert "network error" in body
    assert "finally" in body


def test_audit_summary_is_used_by_cards_and_detail_panel() -> None:
    script = _script()
    card = _function_body(script, "createCard")
    detail = _function_body(script, "openDetailPanel")

    assert "renderCardTerminalAuditSummary" in card
    assert "renderTerminalAuditSummary(detail, detail.identifier)" in detail
    assert "terminal_audit" in _function_body(script, "issueFingerprint")


def test_override_and_audit_css_have_small_screen_hooks() -> None:
    html = _dashboard()

    assert ".terminal-audit-grid" in html
    assert ".terminal-audit-override" in html
    assert "@media (max-width: 720px)" in html
    assert ".detail-panel.open { width: min(800px, 92vw); }" in html
