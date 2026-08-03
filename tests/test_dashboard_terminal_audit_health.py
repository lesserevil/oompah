"""Contract tests for the dashboard terminal-audit health surface."""

from __future__ import annotations

import os
import re


def _load_dashboard() -> str:
    template_dir = os.path.join(os.path.dirname(__file__), "..", "oompah", "templates")
    path = os.path.join(template_dir, "dashboard.html")
    with open(path, encoding="utf-8") as f:
        return f.read()


def _extract_function(name: str, html: str) -> str:
    """Extract a named JS function body (naive but sufficient for these tests)."""
    pattern = re.compile(
        r"function\s+" + re.escape(name) + r"\s*\([^)]*\)\s*\{",
    )
    match = pattern.search(html)
    if not match:
        return ""
    start = match.start()
    depth = 0
    for i in range(match.start(), len(html)):
        if html[i] == "{":
            depth += 1
        elif html[i] == "}":
            depth -= 1
            if depth == 0:
                return html[start : i + 1]
    return html[start:]


class TestTerminalAuditHealthBannerIsAccessibleAndHiddenByDefault:
    """The terminal-audit-health banner must meet accessibility requirements."""

    def test_banner_exists_and_is_hidden_by_default(self):
        html = _load_dashboard()
        # There must be a terminal-audit-health element
        match = re.search(r'<[^>]+id="terminal-audit-health"[^>]*>', html)
        assert match is not None, "No element with id='terminal-audit-health' found"
        tag = match.group(0)
        # Must start hidden
        assert "hidden" in tag, f"terminal-audit-health element is not hidden: {tag}"

    def test_banner_has_required_aria_attributes(self):
        html = _load_dashboard()
        match = re.search(r'<[^>]+id="terminal-audit-health"[^>]*>', html)
        assert match is not None
        tag = match.group(0)
        assert 'role="status"' in tag, f"Missing role=status: {tag}"
        assert 'aria-live="polite"' in tag, f"Missing aria-live=polite: {tag}"
        assert 'aria-label="Terminal-audit health"' in tag, (
            f"Missing aria-label: {tag}"
        )

    def test_detail_element_exists(self):
        html = _load_dashboard()
        assert 'id="terminal-audit-health-detail"' in html, (
            "Missing terminal-audit-health-detail element"
        )


class TestTerminalAuditHealthRendererUsesSafeNumericFacts:
    """The renderTerminalAuditHealth function must use only numeric health facts."""

    def test_function_exists(self):
        html = _load_dashboard()
        fn = _extract_function("renderTerminalAuditHealth", html)
        assert fn, "renderTerminalAuditHealth function not found in dashboard"

    def test_function_uses_launch_failure_count(self):
        html = _load_dashboard()
        fn = _extract_function("renderTerminalAuditHealth", html)
        assert "health.launch_failure_count" in fn, (
            "renderTerminalAuditHealth must reference health.launch_failure_count"
        )

    def test_function_uses_transport_failure_count(self):
        html = _load_dashboard()
        fn = _extract_function("renderTerminalAuditHealth", html)
        assert "health.transport_failure_count" in fn, (
            "renderTerminalAuditHealth must reference health.transport_failure_count"
        )

    def test_function_distinguishes_uncommitted_finalization_failures(self):
        html = _load_dashboard()
        fn = _extract_function("renderTerminalAuditHealth", html)
        assert "health.finalization_failure_count" in fn, (
            "renderTerminalAuditHealth must reference "
            "health.finalization_failure_count"
        )
        assert "uncommitted audit finalization failure(s)" in fn, (
            "finalization failures must not be presented as transport or "
            "command-policy failures"
        )

    def test_function_uses_oldest_pending_age(self):
        html = _load_dashboard()
        fn = _extract_function("renderTerminalAuditHealth", html)
        assert "health.oldest_pending_age_seconds" in fn, (
            "renderTerminalAuditHealth must reference health.oldest_pending_age_seconds"
        )

    def test_function_uses_retry_exhausted_count(self):
        html = _load_dashboard()
        fn = _extract_function("renderTerminalAuditHealth", html)
        assert "health.retry_exhausted_count" in fn, (
            "renderTerminalAuditHealth must reference health.retry_exhausted_count"
        )

    def test_function_uses_stale_in_validation_count(self):
        html = _load_dashboard()
        fn = _extract_function("renderTerminalAuditHealth", html)
        assert "health.stale_in_validation_count" in fn, (
            "renderTerminalAuditHealth must reference health.stale_in_validation_count"
        )

    def test_function_uses_scan_complete(self):
        html = _load_dashboard()
        fn = _extract_function("renderTerminalAuditHealth", html)
        assert "health.scan_complete" in fn, (
            "renderTerminalAuditHealth must reference health.scan_complete"
        )

    def test_function_shows_banner_on_degraded(self):
        html = _load_dashboard()
        fn = _extract_function("renderTerminalAuditHealth", html)
        # Function must show the banner when there are issues
        assert "banner.hidden = false" in fn, (
            "renderTerminalAuditHealth must set banner.hidden=false on degraded"
        )

    def test_function_hides_banner_when_healthy(self):
        html = _load_dashboard()
        fn = _extract_function("renderTerminalAuditHealth", html)
        assert "banner.hidden = true" in fn, (
            "renderTerminalAuditHealth must set banner.hidden=true on healthy"
        )

    def test_function_sets_detail_text_content(self):
        html = _load_dashboard()
        fn = _extract_function("renderTerminalAuditHealth", html)
        assert "detail.textContent" in fn, (
            "renderTerminalAuditHealth must set detail.textContent"
        )


class TestStateUpdateAcceptsTerminalAuditHealthAndClearsBannerRecovered:
    """handleStateUpdate must read terminal_audit_health and call renderTerminalAuditHealth."""

    def test_handle_state_update_reads_terminal_audit_health(self):
        html = _load_dashboard()
        fn = _extract_function("handleStateUpdate", html)
        assert "state.terminal_audit_health" in fn, (
            "handleStateUpdate must read state.terminal_audit_health"
        )

    def test_handle_state_update_calls_render_function(self):
        html = _load_dashboard()
        fn = _extract_function("handleStateUpdate", html)
        assert "renderTerminalAuditHealth" in fn, (
            "handleStateUpdate must call renderTerminalAuditHealth"
        )

    def test_handles_missing_health_gracefully(self):
        """renderTerminalAuditHealth must handle null/undefined gracefully."""
        html = _load_dashboard()
        fn = _extract_function("renderTerminalAuditHealth", html)
        # Must check for null/undefined/non-object health
        assert "!health" in fn or "typeof health" in fn, (
            "renderTerminalAuditHealth must guard against null health"
        )


class TestQualityGateHealthSurface:
    """The dashboard exposes the active gate owner and clears at idle."""

    def test_accessible_quality_gate_health_banner_exists(self):
        html = _load_dashboard()
        match = re.search(r'<[^>]+id="quality-gate-health"[^>]*>', html)
        assert match is not None
        tag = match.group(0)
        assert "hidden" in tag
        assert 'role="status"' in tag
        assert 'aria-live="polite"' in tag
        assert 'aria-label="Branch quality gate health"' in tag
        assert 'id="quality-gate-health-detail"' in html

    def test_renderer_uses_owner_and_clears_idle_state(self):
        html = _load_dashboard()
        fn = _extract_function("renderQualityGateHealth", html)
        assert fn
        assert "health.active" in fn
        assert "owner.task_id" in fn
        assert "owner.project_id" in fn
        assert "owner.head_sha" in fn
        assert "owner.authority_generation" in fn
        assert "status === 'idle'" in fn
        assert "banner.hidden = true" in fn

    def test_state_update_reads_quality_gate_health(self):
        html = _load_dashboard()
        fn = _extract_function("handleStateUpdate", html)
        assert "state.quality_gates" in fn
        assert "renderQualityGateHealth" in fn
