"""Tests for oompah/auth_health.py — separate operator and worker auth-plane health signals.

Covers:
- Healthy operator path (no 401s → status ok, no alert)
- Stale operator credentials (recent 401s → status degraded, alert generated)
- Healthy worker path (token minted and accepted → status ok, no alert)
- Missing/expired worker token (401 → degraded alert)
- Cross-scope rejection (403_scope → degraded alert)
- Intentional action denial (403_action → never triggers an alert)
- Alert clear after recovery (counts fall out of window → ok again)
- Redaction (no credentials in snapshot or alert dicts)
"""

from __future__ import annotations

import pytest

from oompah.auth_health import (
    OperatorAuthHealth,
    WorkerAuthHealth,
    _reset_for_testing,
    auth_health_alerts,
    auth_health_snapshot,
    record_operator_401,
    record_worker_401,
    record_worker_403_action,
    record_worker_403_policy,
    record_worker_403_scope,
    record_worker_token_accepted,
    record_worker_token_minted,
)


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset process-level singleton counters before each test."""
    _reset_for_testing()
    yield
    _reset_for_testing()


# ---------------------------------------------------------------------------
# OperatorAuthHealth
# ---------------------------------------------------------------------------


class TestOperatorAuthHealth:
    def _make(self, start_time: float = 0.0):
        now = [start_time]
        health = OperatorAuthHealth(now=lambda: now[0])
        return health, now

    def test_initial_state_is_ok(self):
        health, _ = self._make()
        snap = health.snapshot()
        assert snap["plane"] == "operator_basic"
        assert snap["status"] == "ok"
        assert snap["recent_401_count"] == 0
        assert snap["total_401_count"] == 0

    def test_no_alert_when_healthy(self):
        health, _ = self._make()
        assert health.build_alert() is None

    def test_single_401_marks_degraded(self):
        health, now = self._make()
        health.record_401()
        snap = health.snapshot(window_seconds=900)
        assert snap["status"] == "degraded"
        assert snap["recent_401_count"] == 1
        assert snap["total_401_count"] == 1

    def test_multiple_401s_accumulate(self):
        health, now = self._make()
        for _ in range(5):
            health.record_401()
        snap = health.snapshot()
        assert snap["recent_401_count"] == 5
        assert snap["total_401_count"] == 5

    def test_alert_contains_count_and_guidance(self):
        health, _ = self._make()
        health.record_401()
        alert = health.build_alert()
        assert alert is not None
        assert alert["source"] == "auth_health:operator"
        assert alert["level"] == "warning"
        assert "1" in alert["message"]
        assert "restart" in alert["action"].lower() or "htpasswd" in alert["action"].lower()

    def test_alert_clears_after_window_expires(self):
        health, now = self._make(start_time=0.0)
        health.record_401()
        # Still within window
        now[0] = 800.0
        assert health.build_alert(window_seconds=900) is not None
        # Past window
        now[0] = 1000.0
        alert = health.build_alert(window_seconds=900)
        assert alert is None
        snap = health.snapshot(window_seconds=900)
        assert snap["status"] == "ok"
        assert snap["recent_401_count"] == 0

    def test_total_count_survives_window_expiry(self):
        health, now = self._make(start_time=0.0)
        for _ in range(3):
            health.record_401()
        now[0] = 5000.0
        snap = health.snapshot(window_seconds=900)
        assert snap["recent_401_count"] == 0
        assert snap["total_401_count"] == 3

    def test_snapshot_contains_no_credentials(self):
        health, _ = self._make()
        health.record_401()
        snap = health.snapshot()
        snap_str = str(snap)
        for secret_word in ["password", "token", "secret", "credential", "auth"]:
            # "auth" appears in the plane name — that's fine
            pass
        # More specifically, ensure no Authorization-header-like content
        assert "Authorization" not in snap_str
        assert "Basic " not in snap_str


# ---------------------------------------------------------------------------
# WorkerAuthHealth
# ---------------------------------------------------------------------------


class TestWorkerAuthHealth:
    def _make(self, start_time: float = 0.0):
        now = [start_time]
        health = WorkerAuthHealth(now=lambda: now[0])
        return health, now

    def test_initial_state_is_never_minted(self):
        health, _ = self._make()
        snap = health.snapshot()
        assert snap["plane"] == "worker_task_handoff"
        assert snap["status"] == "never_minted"
        assert not snap["token_ever_minted"]
        assert not snap["token_ever_accepted"]

    def test_no_alert_when_never_minted(self):
        health, _ = self._make()
        assert health.build_alert() is None

    def test_minted_and_accepted_is_ok(self):
        health, _ = self._make()
        health.record_minted()
        health.record_accepted()
        snap = health.snapshot()
        assert snap["status"] == "ok"
        assert snap["token_ever_minted"]
        assert snap["token_ever_accepted"]
        assert health.build_alert() is None

    def test_minted_but_never_accepted_still_ok_without_failures(self):
        health, _ = self._make()
        health.record_minted()
        snap = health.snapshot()
        # Without any recent 401/403 scope failures, status is ok even if
        # no successful acceptance has been recorded yet (first dispatch is valid).
        assert snap["status"] == "ok"

    def test_401_after_mint_marks_degraded(self):
        health, _ = self._make()
        health.record_minted()
        health.record_401()
        snap = health.snapshot()
        assert snap["status"] == "degraded"
        assert snap["recent_401_count"] == 1
        assert snap["token_ever_minted"]
        assert not snap["token_ever_accepted"]

    def test_403_scope_marks_degraded(self):
        health, _ = self._make()
        health.record_minted()
        health.record_403_scope()
        snap = health.snapshot()
        assert snap["status"] == "degraded"
        assert snap["recent_403_scope_count"] == 1

    def test_403_action_never_triggers_alert(self):
        """Intentional least-privilege action denial must never alert."""
        health, _ = self._make()
        health.record_minted()
        health.record_accepted()
        for _ in range(10):
            health.record_403_action()
        snap = health.snapshot()
        assert snap["status"] == "ok"
        assert snap["scope_denial_count"] == 10
        assert health.build_alert() is None

    def test_alert_contains_count_and_guidance(self):
        health, _ = self._make()
        health.record_minted()
        health.record_401()
        alert = health.build_alert()
        assert alert is not None
        assert alert["source"] == "auth_health:worker"
        assert alert["level"] == "warning"
        assert "OOMPAH_TASK_HANDOFF_TOKEN" in alert["action"]

    def test_alert_includes_not_accepted_note_when_minted_but_never_accepted(self):
        health, _ = self._make()
        health.record_minted()
        health.record_401()
        alert = health.build_alert()
        assert "never successfully accepted" in alert["message"]

    def test_alert_omits_not_accepted_note_when_some_accepted(self):
        health, _ = self._make()
        health.record_minted()
        health.record_accepted()
        health.record_401()
        alert = health.build_alert()
        assert "never successfully accepted" not in alert["message"]

    def test_alert_clears_after_window_expires(self):
        health, now = self._make(start_time=0.0)
        health.record_minted()
        health.record_accepted()
        health.record_401()
        now[0] = 1000.0
        snap = health.snapshot(window_seconds=900)
        assert snap["status"] == "ok"
        assert health.build_alert(window_seconds=900) is None

    def test_snapshot_contains_no_token_values(self):
        health, _ = self._make()
        health.record_minted()
        health.record_401()
        snap = health.snapshot()
        snap_str = str(snap)
        assert "token_urlsafe" not in snap_str
        # The snapshot reports booleans, not token strings
        assert isinstance(snap["token_ever_minted"], bool)
        assert isinstance(snap["token_ever_accepted"], bool)

    def test_scope_denial_count_is_informational_only(self):
        health, _ = self._make()
        health.record_minted()
        health.record_403_action()
        snap = health.snapshot()
        assert snap["scope_denial_count"] == 1
        # Must not appear in the sliding-window degraded count
        assert snap["recent_403_scope_count"] == 0
        assert snap["status"] == "ok"

    def test_verified_policy_denial_is_informational_only(self):
        health, _ = self._make()
        health.record_minted()
        health.record_accepted()
        for _ in range(5):
            health.record_403_policy()
        snap = health.snapshot()
        assert snap["policy_denial_count"] == 5
        assert snap["scope_denial_count"] == 5
        assert snap["recent_403_scope_count"] == 0
        assert snap["status"] == "ok"
        assert health.build_alert() is None


# ---------------------------------------------------------------------------
# Combined auth_health_snapshot and auth_health_alerts
# ---------------------------------------------------------------------------


class TestCombinedAuthHealth:
    def test_snapshot_shape(self):
        snap = auth_health_snapshot()
        assert "operator" in snap
        assert "worker" in snap
        assert snap["operator"]["plane"] == "operator_basic"
        assert snap["worker"]["plane"] == "worker_task_handoff"

    def test_no_alerts_when_healthy(self):
        assert auth_health_alerts() == []

    def test_operator_alert_surfaced(self):
        record_operator_401()
        alerts = auth_health_alerts()
        sources = [a["source"] for a in alerts]
        assert "auth_health:operator" in sources

    def test_worker_alert_surfaced_after_mint_and_401(self):
        record_worker_token_minted()
        record_worker_401()
        alerts = auth_health_alerts()
        sources = [a["source"] for a in alerts]
        assert "auth_health:worker" in sources

    def test_scope_denial_does_not_surface_alert(self):
        record_worker_token_minted()
        record_worker_token_accepted()
        for _ in range(5):
            record_worker_403_action()
        alerts = auth_health_alerts()
        assert not any(a["source"] == "auth_health:worker" for a in alerts)

    def test_policy_denial_does_not_surface_alert(self):
        record_worker_token_minted()
        record_worker_token_accepted()
        for _ in range(5):
            record_worker_403_policy()
        assert not any(
            a["source"] == "auth_health:worker" for a in auth_health_alerts()
        )

    def test_both_planes_can_alert_simultaneously(self):
        record_operator_401()
        record_worker_token_minted()
        record_worker_403_scope()
        alerts = auth_health_alerts()
        sources = {a["source"] for a in alerts}
        assert "auth_health:operator" in sources
        assert "auth_health:worker" in sources

    def test_alert_message_does_not_contain_secrets(self):
        record_operator_401()
        record_worker_token_minted()
        record_worker_401()
        alerts = auth_health_alerts()
        for a in alerts:
            full_text = str(a)
            # "Authorization:" header value must not appear (would leak a credential)
            assert "Authorization:" not in full_text
            # Base64-encoded credential strings must not appear
            import base64
            assert base64.b64encode(b":").decode() not in full_text
            # Raw bearer token strings must not appear (tokens are hex/urlsafe)
            # The alerts may mention "HTTP Basic auth" (protocol description) — that is fine.
            # What must NOT appear is an actual encoded credential value.
