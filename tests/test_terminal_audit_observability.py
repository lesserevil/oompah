"""Deterministic tests for terminal-audit metrics and actionable health."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from oompah.terminal_audit_observability import (
    AuditAlertCondition,
    TerminalAuditAlertRegistry,
    TerminalAuditMetrics,
    threshold_conditions,
)
from oompah.terminal_audit import (
    EvidenceFingerprint,
    RequestState,
    TargetState,
    TerminalAuditRecord,
)
from oompah.config import ServiceConfig
from oompah.models import Issue, RunningEntry
from oompah.orchestrator import Orchestrator


class _Clock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value


def test_lifecycle_metrics_and_oldest_age_are_deterministic() -> None:
    now = datetime(2026, 7, 29, 12, tzinfo=timezone.utc)
    clock = _Clock(now)
    metrics = TerminalAuditMetrics(clock=clock)

    metrics.record_queued("project-a", "TASK-1", "audit-1", queued_at=now - timedelta(seconds=90))
    metrics.record_queued("project-b", "TASK-2", "audit-2", queued_at=now - timedelta(seconds=30))
    metrics.record_running("project-a", "TASK-1", "audit-1", attempts=1)
    metrics.record_retried("project-a", "TASK-1", "audit-1", attempts=2)
    metrics.record_passed("project-a", "TASK-1", "audit-1", completed_at=now)
    metrics.record_failed("project-b", "TASK-2", "audit-2")
    metrics.record_stale_discarded("project-a", "TASK-3", "audit-3")
    metrics.record_overridden("project-a", "TASK-4", "audit-4")
    metrics.record_grandfathered("project-a", "TASK-5", "audit-5")
    metrics.record_grandfathered("project-a", "TASK-5", "audit-5")
    metrics.record_no_independent_candidate("project-a", "TASK-6", "audit-6")
    metrics.record_no_independent_candidate("project-a", "TASK-6", "audit-6")

    snapshot = metrics.snapshot()
    assert snapshot["queued"] == 0
    assert snapshot["running"] == 0
    assert snapshot["queued_total"] == 2
    assert snapshot["passed"] == 1
    assert snapshot["failed"] == 1
    assert snapshot["retried"] == 1
    assert snapshot["stale_discarded"] == 1
    assert snapshot["overridden"] == 1
    assert snapshot["grandfathered"] == 1
    assert snapshot["no_independent_candidate"] == 1
    assert snapshot["last_successful_audit_at"] == now.isoformat()


def test_queue_age_and_project_isolation_survive_restart() -> None:
    now = datetime(2026, 7, 29, 12, tzinfo=timezone.utc)
    clock = _Clock(now)
    persisted: dict = {}

    first = TerminalAuditMetrics(
        clock=clock,
        load_state=lambda: persisted,
        save_state=lambda update: persisted.update(update),
    )
    first.record_queued("project-a", "TASK-1", "audit-1", queued_at=now - timedelta(seconds=120))
    first.record_queued("project-b", "TASK-1", "audit-2", queued_at=now - timedelta(seconds=20))
    first.record_retried("project-a", "TASK-1", "audit-1", attempts=3)

    restarted = TerminalAuditMetrics(
        clock=clock,
        load_state=lambda: persisted,
        save_state=lambda update: persisted.update(update),
    )
    snapshot = restarted.snapshot()
    assert snapshot["queued"] == 2
    assert snapshot["oldest_queue_age_seconds"] == 120
    assert snapshot["oldest_queue_project_id"] == "project-a"
    assert snapshot["projects"]["project-a"]["queued"] == 1
    assert snapshot["projects"]["project-a"]["running"] == 0
    assert snapshot["projects"]["project-a"]["retried"] == 1
    assert snapshot["projects"]["project-b"]["queued"] == 1
    assert snapshot["projects"]["project-b"]["retried"] == 0
    assert snapshot["retried"] == 1


def test_sync_pending_uses_only_live_records_and_counts_a_stale_identity_once() -> None:
    now = datetime(2026, 7, 29, 12, tzinfo=timezone.utc)
    metrics = TerminalAuditMetrics(clock=_Clock(now))
    fingerprint = EvidenceFingerprint("a" * 64)
    live = TerminalAuditRecord(
        audit_id="audit-live",
        project_id="project-a",
        task_id="TASK-1",
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.PENDING,
    )
    superseded = TerminalAuditRecord(
        audit_id="audit-stale",
        project_id="project-a",
        task_id="TASK-2",
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.SUPERSEDED,
    )
    metrics.record_running("project-a", "TASK-2", "audit-stale")

    entries = [
        SimpleNamespace(
            project_id=live.project_id,
            task_id=live.task_id,
            audit_id=live.audit_id,
            record=live,
        ),
        SimpleNamespace(
            project_id=superseded.project_id,
            task_id=superseded.task_id,
            audit_id=superseded.audit_id,
            record=superseded,
        ),
    ]
    metrics.sync_pending(entries)
    metrics.sync_pending(entries)

    snapshot = metrics.snapshot(now=now)
    assert snapshot["queued"] == 1
    assert snapshot["running"] == 0
    assert snapshot["queued_total"] == 1
    assert snapshot["oldest_queue_task_id"] == "TASK-1"

    metrics.record_stale_discarded("project-a", "TASK-2", "audit-stale")
    metrics.record_stale_discarded("project-a", "TASK-2", "audit-stale")
    assert metrics.snapshot()["stale_discarded"] == 1


def test_threshold_alerts_deduplicate_and_clear_on_recovery() -> None:
    now = datetime(2026, 7, 29, 12, tzinfo=timezone.utc)
    clock = _Clock(now)
    metrics = TerminalAuditMetrics(clock=clock)
    metrics.record_queued("project-a", "TASK-1", "audit-1", queued_at=now - timedelta(seconds=61), attempts=1)
    registry = TerminalAuditAlertRegistry()

    conditions = threshold_conditions(metrics, max_attempts=3, max_age_seconds=60)
    assert [condition.key for condition in conditions] == [
        ("age_threshold", "project-a", "TASK-1", "audit-1")
    ]
    assert len(registry.sync(conditions)) == 1
    assert len(registry.sync(conditions)) == 1
    assert len(registry.conditions) == 1

    metrics.record_passed("project-a", "TASK-1", "audit-1", completed_at=now)
    assert registry.sync(threshold_conditions(metrics, max_attempts=3, max_age_seconds=60)) == []
    assert registry.conditions == ()


def test_normal_queue_running_and_passed_states_have_no_alerts() -> None:
    now = datetime(2026, 7, 29, 12, tzinfo=timezone.utc)
    metrics = TerminalAuditMetrics(clock=_Clock(now))
    metrics.record_queued("project-a", "TASK-1", "audit-1", queued_at=now)
    assert threshold_conditions(metrics, max_attempts=3, max_age_seconds=60) == []
    metrics.record_running("project-a", "TASK-1", "audit-1")
    assert threshold_conditions(metrics, max_attempts=3, max_age_seconds=60) == []
    metrics.record_passed("project-a", "TASK-1", "audit-1")
    assert threshold_conditions(metrics, max_attempts=3, max_age_seconds=60) == []


def test_no_candidate_alert_has_actionable_instructions_and_is_deduplicated() -> None:
    condition = AuditAlertCondition(
        "no_independent_candidate",
        "project-a",
        "TASK-1",
        "audit-1",
        "No independent auditor candidate is available.",
        "Configure a healthy independent auditor, then retry the audit.",
    )
    registry = TerminalAuditAlertRegistry()
    alert = registry.add(condition)
    registry.add(condition)
    assert len(registry.conditions) == 1
    assert "Configure" in alert["action"]
    assert "project-a:TASK-1:audit-1" in alert["source"]

    registry.clear("project-a", "TASK-1", "audit-1")
    assert registry.conditions == ()


def test_corrupt_persistence_is_visible_and_not_overwritten() -> None:
    persisted = {"terminal_audit_metrics": {"version": 999, "counters": {}}}
    metrics = TerminalAuditMetrics(load_state=lambda: persisted, save_state=lambda _: persisted.update(_))

    assert metrics.persistence_corrupt is True
    snapshot = metrics.snapshot()
    assert snapshot["persistence_corrupt"] is True
    conditions = threshold_conditions(metrics, max_attempts=3, max_age_seconds=60)
    assert any(condition.kind == "persistence_corrupt" for condition in conditions)
    original = dict(persisted["terminal_audit_metrics"])
    metrics.record_queued("project-a", "TASK-1", "audit-1")
    assert persisted["terminal_audit_metrics"] == original


def test_orchestrator_snapshot_and_alert_recovery_shapes(tmp_path: Path) -> None:
    orchestrator = Orchestrator(
        ServiceConfig(workspace_root=str(tmp_path / "workspace")),
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(tmp_path / "service_state.json"),
    )
    try:
        orchestrator.record_terminal_audit_no_candidate(
            "project-a", "TASK-1", "audit-1", reason="all configured candidates are contributors"
        )
        first = orchestrator.get_snapshot()
        assert first["terminal_audit"]["no_independent_candidate"] == 1
        assert first["orchestrator_metrics"]["terminal_audit"]["queued"] == 0
        assert first["maintenance"]["terminal_audit"]["running"] == 0
        alerts = [alert for alert in first["alerts"] if alert["source"].startswith("terminal_audit:")]
        assert len(alerts) == 1
        assert "Configure" in alerts[0]["action"]

        second = orchestrator.get_snapshot()
        assert len([alert for alert in second["alerts"] if alert["source"].startswith("terminal_audit:")]) == 1
        orchestrator.clear_terminal_audit_alert("project-a", "TASK-1", "audit-1")
        recovered = orchestrator.get_snapshot()
        assert not [alert for alert in recovered["alerts"] if alert["source"].startswith("terminal_audit:")]
    finally:
        orchestrator._tick_pool.shutdown(wait=True, cancel_futures=True)
        orchestrator._refresh_pool.shutdown(wait=True, cancel_futures=True)


def test_queue_recovery_alert_survives_snapshots_until_recovery(tmp_path: Path) -> None:
    orchestrator = Orchestrator(
        ServiceConfig(workspace_root=str(tmp_path / "workspace")),
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(tmp_path / "service_state.json"),
    )
    try:
        orchestrator._sync_terminal_audit_observability_alerts(
            ["queue_recovery_failed"]
        )

        first = orchestrator.get_snapshot()
        second = orchestrator.get_snapshot()
        for snapshot in (first, second):
            alerts = [
                alert
                for alert in snapshot["alerts"]
                if str(alert.get("source", "")).startswith("terminal_audit:")
            ]
            assert len(alerts) == 1
            assert alerts[0]["source"].startswith("terminal_audit:queue_recovery:")

        orchestrator._sync_terminal_audit_observability_alerts(
            recovery_complete=True
        )
        recovered = orchestrator.get_snapshot()
        assert not [
            alert
            for alert in recovered["alerts"]
            if str(alert.get("source", "")).startswith("terminal_audit:")
        ]
    finally:
        orchestrator._tick_pool.shutdown(wait=True, cancel_futures=True)
        orchestrator._refresh_pool.shutdown(wait=True, cancel_futures=True)


def test_running_audits_do_not_emit_queue_age_alerts(tmp_path: Path) -> None:
    orchestrator = Orchestrator(
        ServiceConfig(workspace_root=str(tmp_path / "workspace")),
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(tmp_path / "service_state.json"),
    )
    try:
        now = datetime.now(timezone.utc)
        orchestrator.config.audit_attempt_ttl_seconds = 60
        issue = Issue(
            id="TASK-1",
            identifier="TASK-1",
            title="Audit me",
            description="",
            state="In Validation",
            project_id="project-a",
        )
        entry = RunningEntry(
            worker_task=None,
            identifier=issue.identifier,
            issue=issue,
            session=None,
            retry_attempt=0,
            started_at=now,
        )
        # OOMPAH-475 adds these fields to RunningEntry; setattr keeps this
        # regression test compatible with the pre-dispatch base branch.
        entry.is_auditor = True
        entry.audit_id = "audit-1"
        orchestrator.state.running[issue.id] = entry
        orchestrator._terminal_audit_metrics.record_queued(
            "project-a",
            issue.identifier,
            "audit-1",
            queued_at=now - timedelta(seconds=120),
            attempts=1,
        )

        snapshot = orchestrator.get_snapshot()

        assert snapshot["terminal_audit"]["queued"] == 0
        assert snapshot["terminal_audit"]["running"] == 1
        assert not [
            alert
            for alert in snapshot["alerts"]
            if str(alert.get("source", "")).startswith("terminal_audit:")
        ]
    finally:
        orchestrator._tick_pool.shutdown(wait=True, cancel_futures=True)
        orchestrator._refresh_pool.shutdown(wait=True, cancel_futures=True)
