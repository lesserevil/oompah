"""Health and alert lifecycle tests for the independent terminal auditor."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import pytest

from oompah.terminal_audit import (
    AuditAttempt,
    EvidenceFingerprint,
    FailureClassification,
    RequestState,
    TargetState,
    TerminalAuditRecord,
)
from oompah.terminal_audit_health import (
    AuditHealthObservation,
    DEFAULT_STALE_AFTER_SECONDS,
    HEALTH_ALERT_PREFIX,
    TerminalAuditHealth,
    build_terminal_audit_health,
    terminal_audit_health_alerts,
)

NOW = datetime(2026, 7, 30, 12, 0, 0, tzinfo=timezone.utc)


def _fp() -> EvidenceFingerprint:
    digest = hashlib.sha256(b"test").hexdigest()
    return EvidenceFingerprint(digest)


def _record(
    *,
    audit_id: str = "audit-1",
    project_id: str = "project-1",
    task_id: str = "TASK-1",
    request_state: RequestState = RequestState.PENDING,
    attempts: list | None = None,
) -> TerminalAuditRecord:
    return TerminalAuditRecord(
        audit_id=audit_id,
        project_id=project_id,
        task_id=task_id,
        target_state=TargetState.DONE,
        evidence_fingerprint=_fp(),
        request_state=request_state,
        attempts=attempts or [],
        created_at=NOW.isoformat(),
    )


def _attempt(
    attempt_id: str = "attempt-1",
    *,
    failure_reason: str | None = None,
    ended_at: str | None = None,
    request_state: RequestState = RequestState.PENDING,
) -> AuditAttempt:
    return AuditAttempt(
        attempt_id=attempt_id,
        target_state=TargetState.DONE,
        evidence_fingerprint=_fp(),
        request_state=request_state,
        failure_reason=failure_reason,
        ended_at=ended_at,
        created_at=NOW.isoformat(),
    )


def _obs(
    record: TerminalAuditRecord | None = None,
    *,
    project_id: str = "project-1",
    issue_identifier: str = "TASK-1",
    issue_created_at: datetime | None = None,
    quarantined: bool = False,
    finalization_failure_count: int = 0,
) -> AuditHealthObservation:
    return AuditHealthObservation(
        project_id=project_id,
        issue_identifier=issue_identifier,
        issue_created_at=issue_created_at or NOW,
        record=record,
        quarantined=quarantined,
        finalization_failure_count=finalization_failure_count,
    )


# ---------------------------------------------------------------------------
# Empty backlog
# ---------------------------------------------------------------------------


class TestEmptyBacklog:
    def test_empty_backlog_is_healthy_and_quiet(self):
        """An empty observation list must not surface any alerts."""
        health = build_terminal_audit_health([], now=NOW)
        assert not health.degraded
        assert health.pending_count == 0
        assert health.in_progress_count == 0
        alerts = terminal_audit_health_alerts(health)
        assert alerts == [], f"Expected no alerts, got: {alerts}"

    def test_uncommitted_finalization_is_distinct_and_actionable(self):
        health = build_terminal_audit_health(
            [_obs(record=None, finalization_failure_count=1)],
            now=NOW,
        )

        assert health.finalization_failure_count == 1
        assert health.transport_failure_count == 0
        assert health.policy_incompatibility_count == 0
        assert health.stale_in_validation_count == 0
        alerts = terminal_audit_health_alerts(health)
        finalization = next(
            alert for alert in alerts if alert["source"].endswith("finalization_failures")
        )
        assert "durable status" in finalization["detail"]
        assert "comment" in finalization["action"]

    def test_empty_health_to_dict_has_expected_keys(self):
        health = TerminalAuditHealth()
        d = health.to_dict()
        for key in (
            "pending_count",
            "in_progress_count",
            "oldest_pending_at",
            "oldest_pending_age_seconds",
            "stale_pending_count",
            "stale_in_validation_count",
            "launch_failure_count",
            "transport_failure_count",
            "policy_incompatibility_count",
            "failure_count",
            "retry_exhausted_count",
            "quarantined_count",
            "stale_after_seconds",
            "scan_complete",
            "scan_error_count",
            "degraded",
            "projects",
        ):
            assert key in d, f"Missing key: {key}"

    def test_healthy_empty_state_degrades_only_on_incomplete_scan(self):
        """An incomplete scan of an empty queue is still degraded."""
        health = build_terminal_audit_health(
            [], now=NOW, scan_complete=False, scan_error_count=1
        )
        assert health.degraded
        alerts = terminal_audit_health_alerts(health)
        sources = [a["source"] for a in alerts]
        assert HEALTH_ALERT_PREFIX + "scan" in sources


# ---------------------------------------------------------------------------
# Fresh normal queue
# ---------------------------------------------------------------------------


class TestFreshNormalQueue:
    def test_fresh_normal_queue_has_age_metrics_without_alerts(self):
        """A single fresh pending record must not trigger any alerts."""
        rec = _record()  # created_at=NOW
        health = build_terminal_audit_health(
            [_obs(rec)],
            now=NOW + timedelta(seconds=30),
            stale_after_seconds=3600,
        )
        assert health.pending_count == 1
        assert health.oldest_pending_age_seconds is not None
        assert health.oldest_pending_age_seconds < 3600
        assert not health.degraded
        alerts = terminal_audit_health_alerts(health)
        assert alerts == [], f"Expected no alerts for fresh queue, got: {alerts}"

    def test_fresh_in_progress_counts_correctly(self):
        """An in-progress record increments in_progress_count, not pending_count."""
        rec = _record(request_state=RequestState.IN_PROGRESS)
        health = build_terminal_audit_health([_obs(rec)], now=NOW)
        assert health.in_progress_count == 1
        assert health.pending_count == 0

    def test_stale_threshold_not_reached_is_healthy(self):
        """A record at exactly stale_after_seconds - 1 must not be stale."""
        rec = _record()
        age = DEFAULT_STALE_AFTER_SECONDS - 1
        health = build_terminal_audit_health(
            [_obs(rec)],
            now=NOW + timedelta(seconds=age),
            stale_after_seconds=DEFAULT_STALE_AFTER_SECONDS,
        )
        assert health.stale_pending_count == 0
        alerts = terminal_audit_health_alerts(health)
        backlog_alerts = [a for a in alerts if "backlog_age" in a["source"]]
        assert not backlog_alerts, f"Unexpected backlog alert: {backlog_alerts}"


# ---------------------------------------------------------------------------
# Aged backlog and stale validation
# ---------------------------------------------------------------------------


class TestAgedBacklogAndStaleValidation:
    def test_aged_backlog_surfaces_warning_alert(self):
        """A record older than stale_after_seconds must surface a backlog_age alert."""
        rec = _record()
        health = build_terminal_audit_health(
            [_obs(rec)],
            now=NOW + timedelta(seconds=DEFAULT_STALE_AFTER_SECONDS + 1),
        )
        assert health.stale_pending_count == 1
        alerts = terminal_audit_health_alerts(health)
        sources = [a["source"] for a in alerts]
        assert HEALTH_ALERT_PREFIX + "backlog_age" in sources, (
            f"Expected backlog_age alert, got: {sources}"
        )
        backlog_alert = next(a for a in alerts if "backlog_age" in a["source"])
        assert backlog_alert["level"] == "warning"

    def test_stale_in_validation_no_record_surfaces_validation_alert(self):
        """An In Validation task with no audit record beyond threshold is stale."""
        obs = _obs(record=None, issue_created_at=NOW - timedelta(seconds=7200))
        health = build_terminal_audit_health([obs], now=NOW, stale_after_seconds=3600)
        assert health.stale_in_validation_count == 1
        alerts = terminal_audit_health_alerts(health)
        sources = [a["source"] for a in alerts]
        assert HEALTH_ALERT_PREFIX + "stale_validation" in sources, (
            f"Expected stale_validation alert, got: {sources}"
        )

    def test_aged_backlog_and_stale_validation_are_distinct_alerts(self):
        """Aged pending record and stale no-metadata record produce two distinct alerts."""
        aged_rec = _record()
        aged_obs = _obs(aged_rec)
        stale_obs = _obs(record=None, issue_created_at=NOW - timedelta(seconds=7200))
        health = build_terminal_audit_health(
            [aged_obs, stale_obs],
            now=NOW + timedelta(seconds=DEFAULT_STALE_AFTER_SECONDS + 1),
        )
        alerts = terminal_audit_health_alerts(health)
        sources = [a["source"] for a in alerts]
        assert HEALTH_ALERT_PREFIX + "backlog_age" in sources
        assert HEALTH_ALERT_PREFIX + "stale_validation" in sources

    def test_stale_in_validation_fresh_record_is_not_stale(self):
        """An In Validation task with fresh metadata (record) is not stale."""
        # The record's own created_at is used; issue_created_at is secondary.
        rec = _record()  # created_at=NOW
        obs = _obs(rec, issue_created_at=NOW - timedelta(seconds=99999))
        health = build_terminal_audit_health([obs], now=NOW + timedelta(seconds=60))
        assert health.stale_pending_count == 0


# ---------------------------------------------------------------------------
# Launch/transport failures
# ---------------------------------------------------------------------------


class TestLaunchAndTransportFailures:
    def test_repeated_launch_and_transport_failures_are_counted_without_details(self):
        """Launch and transport failures increment counters without leaking failure text."""
        launch_attempt = _attempt(
            "attempt-launch",
            failure_reason="auditor launch failed: api_key=super-secret",
            ended_at=NOW.isoformat(),
        )
        transport_attempt = _attempt(
            "attempt-transport",
            failure_reason="provider transport timeout: assistant response leaked",
            ended_at=NOW.isoformat(),
        )
        rec = _record(attempts=[launch_attempt, transport_attempt])
        health = build_terminal_audit_health([_obs(rec)], now=NOW)
        assert health.launch_failure_count == 1
        assert health.transport_failure_count == 1
        alerts = terminal_audit_health_alerts(health)
        sources = [a["source"] for a in alerts]
        assert HEALTH_ALERT_PREFIX + "launch_failures" in sources

        # The alert must NOT expose the failure reason text
        for alert in alerts:
            for field in ("title", "detail", "action"):
                text = alert.get(field, "")
                assert "super-secret" not in text, f"Credential in {field}: {text}"
                assert "assistant response leaked" not in text, (
                    f"Model output in {field}: {text}"
                )

    def test_failure_alert_is_error_level(self):
        """Launch failure alerts must be error-level, not warning."""
        launch_attempt = _attempt(
            "attempt-launch",
            failure_reason="auditor launch failed",
            ended_at=NOW.isoformat(),
        )
        rec = _record(attempts=[launch_attempt])
        health = build_terminal_audit_health([_obs(rec)], now=NOW)
        alerts = terminal_audit_health_alerts(health)
        launch_alert = next(
            (a for a in alerts if "launch_failures" in a["source"]), None
        )
        assert launch_alert is not None, "Expected launch_failures alert"
        assert launch_alert["level"] == "error"

    def test_connection_timeout_is_transport_failure(self):
        """An attempt with 'connection timeout' in the reason is a transport failure."""
        attempt = _attempt(
            "attempt-t",
            failure_reason="connection timeout",
            ended_at=NOW.isoformat(),
        )
        rec = _record(attempts=[attempt])
        health = build_terminal_audit_health([_obs(rec)], now=NOW)
        assert health.transport_failure_count == 1
        assert health.launch_failure_count == 0

    def test_policy_incompatibility_is_not_transport_failure(self):
        """Local auditor policy failures must not raise a provider outage alert."""
        from dataclasses import replace

        attempt = replace(
            _attempt(
                "attempt-policy",
                failure_reason="auditor policy denial limit reached",
                ended_at=NOW.isoformat(),
            ),
            failure_classification=FailureClassification.POLICY_INCOMPATIBILITY,
        )
        health = build_terminal_audit_health([_obs(_record(attempts=[attempt]))], now=NOW)
        assert health.policy_incompatibility_count == 1
        assert health.transport_failure_count == 0
        sources = [alert["source"] for alert in terminal_audit_health_alerts(health)]
        assert HEALTH_ALERT_PREFIX + "policy_incompatibility" in sources
        assert HEALTH_ALERT_PREFIX + "launch_failures" not in sources

    def test_no_auditor_classification_is_not_a_failure(self):
        """NO_AUDITOR classification is exhaustion, not launch/transport failure."""
        from oompah.terminal_audit import FailureClassification

        attempt = _attempt(
            "attempt-no-auditor",
            failure_reason="no candidates available",
            ended_at=NOW.isoformat(),
        )
        # Manually set the failure_classification
        from dataclasses import replace

        attempt = replace(
            attempt,
            failure_classification=FailureClassification.NO_AUDITOR,
        )
        rec = _record(attempts=[attempt])
        health = build_terminal_audit_health([_obs(rec)], now=NOW)
        assert health.launch_failure_count == 0
        assert health.transport_failure_count == 0


# ---------------------------------------------------------------------------
# Retry exhaustion
# ---------------------------------------------------------------------------


class TestRetryExhaustion:
    def test_retry_exhaustion_is_active_until_the_record_recovers(self):
        """An audit that used max_attempts increments retry_exhausted_count."""
        attempts = [
            _attempt(f"attempt-{i}", failure_reason="failed", ended_at=NOW.isoformat())
            for i in range(3)
        ]
        rec = _record(attempts=attempts)
        health = build_terminal_audit_health([_obs(rec)], now=NOW, max_attempts=3)
        assert health.retry_exhausted_count == 1
        alerts = terminal_audit_health_alerts(health)
        sources = [a["source"] for a in alerts]
        assert HEALTH_ALERT_PREFIX + "retry_exhausted" in sources

    def test_retry_exhaustion_alert_is_error_level(self):
        """Retry exhaustion alert must be error-level."""
        attempts = [
            _attempt(f"attempt-{i}", failure_reason="failed", ended_at=NOW.isoformat())
            for i in range(3)
        ]
        rec = _record(attempts=attempts)
        health = build_terminal_audit_health([_obs(rec)], now=NOW, max_attempts=3)
        alerts = terminal_audit_health_alerts(health)
        exhausted_alert = next(
            (a for a in alerts if "retry_exhausted" in a["source"]), None
        )
        assert exhausted_alert is not None
        assert exhausted_alert["level"] == "error"

    def test_fewer_than_max_attempts_is_not_exhausted(self):
        """An audit with fewer attempts than max is not exhausted."""
        attempts = [
            _attempt(f"attempt-{i}", failure_reason="failed", ended_at=NOW.isoformat())
            for i in range(2)
        ]
        rec = _record(attempts=attempts)
        health = build_terminal_audit_health([_obs(rec)], now=NOW, max_attempts=3)
        assert health.retry_exhausted_count == 0


# ---------------------------------------------------------------------------
# Recovery and alert clearing
# ---------------------------------------------------------------------------


class TestRecoveryAndAlertClearing:
    def test_successful_recovery_produces_no_alerts(self):
        """After all pending issues clear, no alerts should remain."""
        # Start with a degraded state
        launch_attempt = _attempt(
            "attempt-launch",
            failure_reason="auditor launch failed",
            ended_at=NOW.isoformat(),
        )
        rec = _record(attempts=[launch_attempt])
        health1 = build_terminal_audit_health([_obs(rec)], now=NOW)
        assert health1.degraded

        # Now simulate recovery: empty queue
        health2 = build_terminal_audit_health([], now=NOW + timedelta(seconds=1))
        assert not health2.degraded
        alerts = terminal_audit_health_alerts(health2)
        assert alerts == [], f"Expected no alerts after recovery: {alerts}"

    def test_scan_incomplete_preserves_degraded_on_empty_observations(self):
        """An incomplete scan must not claim a healthy empty state."""
        health = build_terminal_audit_health(
            [], now=NOW, scan_complete=False, scan_error_count=1
        )
        assert health.degraded
        assert not health.scan_complete

    def test_fresh_healthy_record_clears_all_failure_counters(self):
        """A queue with only healthy in-progress records has zero failure counts."""
        rec = _record(request_state=RequestState.IN_PROGRESS)
        health = build_terminal_audit_health([_obs(rec)], now=NOW)
        assert health.launch_failure_count == 0
        assert health.transport_failure_count == 0
        assert health.retry_exhausted_count == 0
        assert not health.degraded


# ---------------------------------------------------------------------------
# Restart persistence (from_dict round-trip)
# ---------------------------------------------------------------------------


class TestRestartPersistence:
    def test_health_snapshot_round_trips_for_restart_persistence(self):
        """TerminalAuditHealth.to_dict / from_dict must preserve numeric fields."""
        launch_attempt = _attempt(
            "attempt-launch",
            failure_reason="auditor launch failed",
            ended_at=NOW.isoformat(),
        )
        rec = _record(attempts=[launch_attempt])
        health = build_terminal_audit_health(
            [_obs(rec)],
            now=NOW + timedelta(seconds=DEFAULT_STALE_AFTER_SECONDS + 1),
        )
        raw = health.to_dict()
        restored = TerminalAuditHealth.from_dict(raw)
        assert restored.launch_failure_count == health.launch_failure_count
        assert restored.stale_pending_count == health.stale_pending_count
        assert restored.scan_complete == health.scan_complete
        assert restored.oldest_pending_age_seconds == health.oldest_pending_age_seconds

    def test_from_dict_tolerates_empty(self):
        """from_dict with an empty dict returns default TerminalAuditHealth."""
        restored = TerminalAuditHealth.from_dict({})
        assert restored.pending_count == 0
        assert restored.scan_complete is True

    def test_from_dict_tolerates_non_dict(self):
        """from_dict with a non-dict returns default TerminalAuditHealth."""
        restored = TerminalAuditHealth.from_dict(None)
        assert restored.pending_count == 0

    def test_from_dict_ignores_unknown_keys(self):
        """from_dict with extra keys must not raise."""
        raw = {"pending_count": 5, "unknown_key": "ignored"}
        restored = TerminalAuditHealth.from_dict(raw)
        assert restored.pending_count == 5


# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------


class TestRedaction:
    def test_alert_titles_do_not_contain_failure_reasons(self):
        """Alert text must be generic and must not contain failure_reason strings."""
        sensitive_reason = "launch failed: api_key=super-secret extra_data"
        launch_attempt = _attempt(
            "attempt-sensitive",
            failure_reason=sensitive_reason,
            ended_at=NOW.isoformat(),
        )
        rec = _record(attempts=[launch_attempt])
        health = build_terminal_audit_health([_obs(rec)], now=NOW)
        alerts = terminal_audit_health_alerts(health)
        for alert in alerts:
            for field in ("title", "detail", "action"):
                text = alert.get(field, "")
                assert sensitive_reason not in text, (
                    f"Sensitive data found in alert.{field}: {text!r}"
                )
                assert "api_key" not in text.lower(), (
                    f"api_key found in alert.{field}: {text!r}"
                )

    def test_alert_sources_use_safe_prefix(self):
        """All alert sources must start with the HEALTH_ALERT_PREFIX."""
        launch_attempt = _attempt(
            "attempt-l",
            failure_reason="auditor launch failed",
            ended_at=NOW.isoformat(),
        )
        rec = _record(attempts=[launch_attempt])
        health = build_terminal_audit_health([_obs(rec)], now=NOW)
        alerts = terminal_audit_health_alerts(health)
        for alert in alerts:
            assert alert["source"].startswith(HEALTH_ALERT_PREFIX), (
                f"Alert source {alert['source']!r} does not start with prefix"
            )

    def test_scan_incomplete_alert_does_not_expose_error(self):
        """scan_incomplete alert must not include internal error text."""
        health = build_terminal_audit_health(
            [], now=NOW, scan_complete=False, scan_error_count=1
        )
        alerts = terminal_audit_health_alerts(health)
        for alert in alerts:
            for field in ("title", "detail", "action"):
                text = alert.get(field, "")
                assert "Exception" not in text, (
                    f"Exception class in alert.{field}: {text!r}"
                )


# ---------------------------------------------------------------------------
# Quarantine
# ---------------------------------------------------------------------------


class TestQuarantine:
    def test_quarantined_observation_increments_count(self):
        """A quarantined observation must not add to pending_count."""
        obs = _obs(record=_record(), quarantined=True)
        health = build_terminal_audit_health([obs], now=NOW)
        assert health.quarantined_count == 1
        assert health.pending_count == 0  # quarantined, not pending
        assert health.degraded

    def test_quarantined_alert_is_error_level(self):
        """metadata_quarantine alert must be error-level."""
        obs = _obs(record=_record(), quarantined=True)
        health = build_terminal_audit_health([obs], now=NOW)
        alerts = terminal_audit_health_alerts(health)
        q_alert = next(
            (a for a in alerts if "metadata_quarantine" in a["source"]), None
        )
        assert q_alert is not None, "Expected metadata_quarantine alert"
        assert q_alert["level"] == "error"

    def test_incomplete_scan_is_not_a_healthy_empty_backlog(self):
        """An incomplete scan of an otherwise empty queue is degraded, not healthy."""
        health = build_terminal_audit_health(
            [], now=NOW, scan_complete=False
        )
        assert not health.scan_complete
        assert health.degraded
        alerts = terminal_audit_health_alerts(health)
        assert len(alerts) > 0, "Expected at least one alert for incomplete scan"


# ---------------------------------------------------------------------------
# Per-audit-attempt recovery: cleared failures must not contaminate later audits
# ---------------------------------------------------------------------------


class TestTransportFailureRecovery:
    """Transport/launch failures must clear when an active replacement is running.

    These tests reproduce the OOMPAH-607/641 contamination scenario:
    - OOMPAH-607 attempt 1 fails (transport)
    - OOMPAH-607 attempt 2 is launched → record goes to IN_PROGRESS
    - The failure alert must clear (active recovery, no operator action needed)
    - After attempt 2 succeeds, OOMPAH-607 leaves In Validation (not in observations)
    - A later OOMPAH-641 in validation must see a clean health state
    """

    def test_pending_record_with_transport_failure_fires_alert(self):
        """A PENDING record with a transport failure must surface the alert."""
        transport_attempt = _attempt(
            "attempt-1",
            failure_reason="provider transport timeout",
            ended_at=NOW.isoformat(),
        )
        rec = _record(request_state=RequestState.PENDING, attempts=[transport_attempt])
        health = build_terminal_audit_health([_obs(rec)], now=NOW)
        assert health.transport_failure_count == 1
        assert health.degraded
        alerts = terminal_audit_health_alerts(health)
        assert any("launch_failures" in a["source"] for a in alerts), (
            "Expected launch_failures alert for PENDING record with transport failure"
        )

    def test_in_progress_record_with_past_transport_failure_does_not_fire_alert(self):
        """An IN_PROGRESS record with a past transport failure must NOT fire an alert.

        An active replacement is running; the prior failure is being recovered
        automatically. Operator intervention (transport restoration) is not needed.
        This is the core OOMPAH-645 fix.
        """
        failed_attempt = _attempt(
            "attempt-1",
            failure_reason="provider transport timeout",
            ended_at=NOW.isoformat(),
            request_state=RequestState.PENDING,
        )
        active_attempt = _attempt(
            "attempt-2",
            request_state=RequestState.IN_PROGRESS,
            # No ended_at: the replacement is currently running
        )
        # Record is IN_PROGRESS because attempt-2 is active
        rec = _record(
            request_state=RequestState.IN_PROGRESS,
            attempts=[failed_attempt, active_attempt],
        )
        health = build_terminal_audit_health([_obs(rec)], now=NOW)
        assert health.transport_failure_count == 0, (
            "Active replacement must suppress stale transport failure count"
        )
        assert health.launch_failure_count == 0
        assert not health.degraded, (
            "IN_PROGRESS record with prior failure must not degrade health"
        )
        alerts = terminal_audit_health_alerts(health)
        failure_alerts = [a for a in alerts if "launch_failures" in a["source"]]
        assert not failure_alerts, (
            f"Must not fire failure alert when replacement is active: {failure_alerts}"
        )

    def test_transition_from_pending_to_in_progress_clears_failure_alert(self):
        """Going from PENDING (failed) to IN_PROGRESS (retry running) clears the alert."""
        failed_attempt = _attempt(
            "attempt-1",
            failure_reason="provider transport timeout",
            ended_at=NOW.isoformat(),
            request_state=RequestState.PENDING,
        )
        # Phase 1: attempt 1 failed, no replacement yet — PENDING
        pending_rec = _record(
            request_state=RequestState.PENDING,
            attempts=[failed_attempt],
        )
        health_pending = build_terminal_audit_health([_obs(pending_rec)], now=NOW)
        assert health_pending.transport_failure_count == 1
        assert health_pending.degraded

        # Phase 2: attempt 2 is launched — IN_PROGRESS
        active_attempt = _attempt("attempt-2", request_state=RequestState.IN_PROGRESS)
        in_progress_rec = _record(
            request_state=RequestState.IN_PROGRESS,
            attempts=[failed_attempt, active_attempt],
        )
        health_recovering = build_terminal_audit_health(
            [_obs(in_progress_rec)], now=NOW
        )
        assert health_recovering.transport_failure_count == 0, (
            "Launching a replacement must clear the transport failure count"
        )
        assert not health_recovering.degraded, (
            "Launching a replacement must resolve the degraded state"
        )

    def test_retry_failed_again_re_fires_alert(self):
        """When attempt 2 also fails, the alert re-fires on the next scan."""
        failed_1 = _attempt(
            "attempt-1",
            failure_reason="provider transport timeout",
            ended_at=NOW.isoformat(),
            request_state=RequestState.PENDING,
        )
        failed_2 = _attempt(
            "attempt-2",
            failure_reason="network connection refused",
            ended_at=(NOW + timedelta(seconds=60)).isoformat(),
            request_state=RequestState.PENDING,
        )
        # Both attempts failed; record is back to PENDING
        rec = _record(
            request_state=RequestState.PENDING,
            attempts=[failed_1, failed_2],
        )
        health = build_terminal_audit_health([_obs(rec)], now=NOW)
        assert health.transport_failure_count == 2, (
            "Both failed attempts must be counted after all retries fail"
        )
        assert health.degraded
        alerts = terminal_audit_health_alerts(health)
        assert any("launch_failures" in a["source"] for a in alerts)

    def test_recovered_audit_plus_unrelated_pending_audit_stays_clean(self):
        """A task whose audit recovered (gone from In Validation) must not contaminate
        a later unrelated task in validation.

        Scenario: OOMPAH-607 completed (out of observations) and OOMPAH-641 is
        freshly pending. The health for OOMPAH-641's scan must be clean.
        """
        # OOMPAH-607 is gone from In Validation (not in observations)
        # OOMPAH-641 is fresh with no failed attempts
        fresh_rec = _record(
            audit_id="audit-641",
            task_id="OOMPAH-641",
            request_state=RequestState.PENDING,
            attempts=[],  # No attempts yet, just queued
        )
        health = build_terminal_audit_health(
            [_obs(fresh_rec, issue_identifier="OOMPAH-641")],
            now=NOW,
        )
        assert health.transport_failure_count == 0, (
            "Recovered earlier audit must not contaminate unrelated later audit"
        )
        assert health.launch_failure_count == 0
        assert not health.degraded, (
            "Later unrelated pending audit must start with clean health state"
        )
        alerts = terminal_audit_health_alerts(health)
        assert not any("launch_failures" in a["source"] for a in alerts), (
            "No failure alert must appear for a clean later audit"
        )

    def test_retry_exhaustion_not_fired_when_last_attempt_is_still_in_progress(self):
        """If the last attempt is IN_PROGRESS, retry budget is not yet consumed."""
        failed_1 = _attempt(
            "attempt-1",
            failure_reason="transport failure",
            ended_at=NOW.isoformat(),
            request_state=RequestState.PENDING,
        )
        failed_2 = _attempt(
            "attempt-2",
            failure_reason="transport failure",
            ended_at=NOW.isoformat(),
            request_state=RequestState.PENDING,
        )
        # Third attempt is IN_PROGRESS (still running)
        active_3 = _attempt("attempt-3", request_state=RequestState.IN_PROGRESS)
        rec = _record(
            request_state=RequestState.IN_PROGRESS,
            attempts=[failed_1, failed_2, active_3],
        )
        health = build_terminal_audit_health([_obs(rec)], now=NOW, max_attempts=3)
        assert health.retry_exhausted_count == 0, (
            "Retry budget is not exhausted while the last attempt is still running"
        )
        assert health.transport_failure_count == 0, (
            "Transport failures must not be counted while IN_PROGRESS"
        )

    def test_retry_exhaustion_fires_after_all_attempts_fail(self):
        """After all attempts fail, exhaustion AND transport failures are both actionable."""
        attempts = [
            _attempt(
                f"attempt-{i}",
                failure_reason="provider transport timeout",
                ended_at=NOW.isoformat(),
                request_state=RequestState.PENDING,
            )
            for i in range(3)
        ]
        rec = _record(request_state=RequestState.PENDING, attempts=attempts)
        health = build_terminal_audit_health([_obs(rec)], now=NOW, max_attempts=3)
        assert health.retry_exhausted_count == 1
        assert health.transport_failure_count == 3
        assert health.degraded


class TestMultiProjectIsolation:
    """Health failures from one project must not bleed into another project's data."""

    def test_transport_failure_in_project_a_does_not_appear_in_project_b_counts(self):
        """Per-project counters must be isolated."""
        # Project A: PENDING with transport failure
        failed_a = _attempt(
            "attempt-a",
            failure_reason="provider transport timeout",
            ended_at=NOW.isoformat(),
        )
        rec_a = _record(
            audit_id="audit-a",
            project_id="project-a",
            task_id="TASK-A",
            request_state=RequestState.PENDING,
            attempts=[failed_a],
        )
        obs_a = _obs(rec_a, project_id="project-a", issue_identifier="TASK-A")

        # Project B: IN_PROGRESS (recovering, no alert)
        failed_b1 = _attempt(
            "attempt-b1",
            failure_reason="network connection refused",
            ended_at=NOW.isoformat(),
            request_state=RequestState.PENDING,
        )
        active_b2 = _attempt("attempt-b2", request_state=RequestState.IN_PROGRESS)
        rec_b = _record(
            audit_id="audit-b",
            project_id="project-b",
            task_id="TASK-B",
            request_state=RequestState.IN_PROGRESS,
            attempts=[failed_b1, active_b2],
        )
        obs_b = _obs(rec_b, project_id="project-b", issue_identifier="TASK-B")

        health = build_terminal_audit_health([obs_a, obs_b], now=NOW)

        # Overall: 1 transport failure from project A only
        assert health.transport_failure_count == 1, (
            "Only PENDING record's transport failure should count"
        )
        # Project-level: project-a has the failure, project-b does not
        project_a_counts = health.projects.get("project-a", {})
        project_b_counts = health.projects.get("project-b", {})
        assert project_a_counts.get("transport_failure_count", 0) == 1, (
            "project-a must have transport_failure_count=1"
        )
        assert project_b_counts.get("transport_failure_count", 0) == 0, (
            "project-b must have transport_failure_count=0 (IN_PROGRESS = recovering)"
        )

    def test_failure_in_recovering_project_does_not_trigger_alert(self):
        """A project with a recovered IN_PROGRESS audit must not see failure alerts."""
        failed = _attempt(
            "attempt-1",
            failure_reason="provider transport timeout",
            ended_at=NOW.isoformat(),
            request_state=RequestState.PENDING,
        )
        active = _attempt("attempt-2", request_state=RequestState.IN_PROGRESS)
        rec = _record(
            project_id="project-recovering",
            request_state=RequestState.IN_PROGRESS,
            attempts=[failed, active],
        )
        obs = _obs(rec, project_id="project-recovering")
        health = build_terminal_audit_health([obs], now=NOW)
        assert not health.degraded
        alerts = terminal_audit_health_alerts(health)
        assert not alerts, (
            f"No alerts for a project with IN_PROGRESS recovery: {alerts}"
        )


class TestAlertTextRefersOnlyToUnresolvedAudits:
    """Alert detail text must only reference counts from unresolved (PENDING) audits."""

    def test_alert_count_matches_only_unresolved_failures(self):
        """The transport failure count in alert text reflects only PENDING records."""
        # One PENDING record (unresolved transport failure)
        failed = _attempt(
            "attempt-pending",
            failure_reason="provider transport timeout",
            ended_at=NOW.isoformat(),
        )
        pending_rec = _record(
            audit_id="audit-pending",
            project_id="project-1",
            task_id="TASK-PENDING",
            request_state=RequestState.PENDING,
            attempts=[failed],
        )
        # One IN_PROGRESS record (recovering, should NOT count)
        failed_hist = _attempt(
            "attempt-hist",
            failure_reason="network connection refused",
            ended_at=NOW.isoformat(),
            request_state=RequestState.PENDING,
        )
        active = _attempt(
            "attempt-active",
            request_state=RequestState.IN_PROGRESS,
        )
        recovering_rec = _record(
            audit_id="audit-recovering",
            project_id="project-1",
            task_id="TASK-RECOVERING",
            request_state=RequestState.IN_PROGRESS,
            attempts=[failed_hist, active],
        )
        obs_pending = _obs(pending_rec, issue_identifier="TASK-PENDING")
        obs_recovering = _obs(recovering_rec, issue_identifier="TASK-RECOVERING")

        health = build_terminal_audit_health([obs_pending, obs_recovering], now=NOW)

        # Only the PENDING record's failure is counted
        assert health.transport_failure_count == 1, (
            f"Expected 1 (only PENDING record), got {health.transport_failure_count}"
        )
        alerts = terminal_audit_health_alerts(health)
        failure_alerts = [a for a in alerts if "launch_failures" in a["source"]]
        assert len(failure_alerts) == 1

        # The detail text must say "1" (only the unresolved failure)
        detail = failure_alerts[0].get("detail", "")
        assert "1 transport failure" in detail or "1 launch" in detail, (
            f"Alert detail must mention count 1 for the single unresolved audit: {detail!r}"
        )

    def test_alert_action_recommends_operator_restore_only_when_truly_unresolved(self):
        """The recovery action should recommend transport restoration only when
        no active replacement is already running."""
        # Record is PENDING with transport failure: operator must act
        failed = _attempt(
            "attempt-1",
            failure_reason="provider transport timeout",
            ended_at=NOW.isoformat(),
        )
        rec = _record(request_state=RequestState.PENDING, attempts=[failed])
        health = build_terminal_audit_health([_obs(rec)], now=NOW)
        alerts = terminal_audit_health_alerts(health)
        failure_alert = next(
            (a for a in alerts if "launch_failures" in a["source"]), None
        )
        assert failure_alert is not None
        action = failure_alert.get("action", "")
        # The action must mention transport restoration (operator needs to act)
        assert "transport" in action.lower() or "auditor" in action.lower(), (
            f"Action must reference transport/auditor: {action!r}"
        )


# ---------------------------------------------------------------------------
# HEALTH_ALERT_PREFIX constant
# ---------------------------------------------------------------------------


class TestAlertPrefix:
    def test_prefix_constant_is_as_expected(self):
        assert HEALTH_ALERT_PREFIX == "terminal_audit_health:"

    def test_all_alerts_use_prefix(self):
        """Every alert source must begin with HEALTH_ALERT_PREFIX."""
        # Force all alert branches to fire
        exhausted_attempts = [
            _attempt(f"a{i}", failure_reason="launch failed", ended_at=NOW.isoformat())
            for i in range(3)
        ]
        rec = _record(attempts=exhausted_attempts)
        stale_obs = _obs(record=None, issue_created_at=NOW - timedelta(seconds=99999))
        aged_obs = _obs(rec)
        quaran_obs = _obs(record=_record(audit_id="audit-q"), quarantined=True)
        health = build_terminal_audit_health(
            [aged_obs, stale_obs, quaran_obs],
            now=NOW + timedelta(seconds=DEFAULT_STALE_AFTER_SECONDS + 1),
            scan_complete=False,
            scan_error_count=1,
            max_attempts=3,
        )
        alerts = terminal_audit_health_alerts(health)
        assert len(alerts) > 0, "Expected at least one alert"
        for alert in alerts:
            assert alert["source"].startswith(HEALTH_ALERT_PREFIX), (
                f"Bad source: {alert['source']!r}"
            )
