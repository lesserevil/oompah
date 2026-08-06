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
    AuditAttempt,
    ContributorIdentity,
    EvidenceFingerprint,
    FailureClassification,
    OverrideRecord,
    RequestState,
    TargetState,
    TerminalAuditRecord,
    Verdict,
)
from oompah.terminal_audit_metadata import (
    METADATA_KEY,
    MetadataQuarantine,
    TerminalAuditMetadata,
)
from oompah.config import ServiceConfig
from oompah.models import Issue, RunningEntry
from oompah.orchestrator import Orchestrator


class _Clock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value


class _MetadataTracker:
    def __init__(self) -> None:
        self.metadata: dict[str, dict] = {}
        self.issues: dict[str, Issue] = {}

    def get_metadata(self, identifier: str) -> dict:
        return self.metadata.get(identifier, {})

    def set_metadata_field(self, identifier: str, field: str, value) -> None:
        self.metadata.setdefault(identifier, {})[field] = value

    def fetch_issue_detail(self, identifier: str) -> Issue | None:
        return self.issues.get(identifier)


def _no_auditor_record(
    audit_id: str,
    fingerprint: EvidenceFingerprint,
    *,
    target: TargetState = TargetState.MERGED,
    completed_at: str = "2026-07-31T10:00:00+00:00",
) -> TerminalAuditRecord:
    attempt = AuditAttempt(
        attempt_id=f"attempt-{audit_id}",
        target_state=target,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.COMPLETED,
        verdict=Verdict.FAIL,
        failure_classification=FailureClassification.NO_AUDITOR,
        created_at=completed_at,
        completed_at=completed_at,
    )
    return TerminalAuditRecord(
        audit_id=audit_id,
        project_id="project-a",
        task_id="TASK-1",
        target_state=target,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.COMPLETED,
        attempts=[attempt],
        created_at=completed_at,
        updated_at=completed_at,
    )


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


def test_quality_gate_decision_and_validation_lane_telemetry_survive_restart() -> None:
    persisted: dict = {}
    first = TerminalAuditMetrics(
        load_state=lambda: persisted,
        save_state=lambda update: persisted.update(update),
    )
    first.record_quality_gate_decision(
        "project-a",
        "TASK-1",
        "audit-1",
        decision="reuse_authoritative_gate",
        result="passed",
        head_sha="a" * 40,
        command="make test",
        duration_seconds=42.0,
    )
    first.record_auditor_validation_command(
        "project-a",
        "TASK-1",
        "audit-1",
        command="pytest tests/test_warning.py -q",
        configured_command="make test",
        duration_seconds=1.5,
    )

    restarted = TerminalAuditMetrics(
        load_state=lambda: persisted,
        save_state=lambda update: persisted.update(update),
    )
    snapshot = restarted.snapshot()

    assert snapshot["authoritative_gate_reused"] == 1
    assert snapshot["focused_supplemental_commands"] == 1
    assert snapshot["validation"]["last_decision"]["decision"] == (
        "reuse_authoritative_gate"
    )
    assert snapshot["validation"]["last_command"]["category"] == (
        "focused_supplemental_commands"
    )


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


def test_snapshot_discards_running_gauge_after_last_auditor_exits(
    tmp_path: Path,
) -> None:
    """An empty agent map cannot retain a persisted running audit gauge."""
    orchestrator = Orchestrator(
        ServiceConfig(workspace_root=str(tmp_path / "workspace")),
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(tmp_path / "service_state.json"),
    )
    try:
        orchestrator._terminal_audit_metrics.record_running(
            "project-a", "TASK-1", "audit-1", attempts=2
        )
        assert orchestrator._terminal_audit_metrics.snapshot()["running"] == 1
        assert orchestrator.state.running == {}

        snapshot = orchestrator.get_snapshot()

        assert snapshot["running"] == []
        assert snapshot["terminal_audit"]["running"] == 0
        assert snapshot["terminal_audit_health"]["in_progress_count"] == 0
    finally:
        orchestrator._tick_pool.shutdown(wait=True, cancel_futures=True)
        orchestrator._refresh_pool.shutdown(wait=True, cancel_futures=True)


def test_snapshot_exposes_finalization_failure_separately(tmp_path: Path) -> None:
    orchestrator = Orchestrator(
        ServiceConfig(workspace_root=str(tmp_path / "workspace")),
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(tmp_path / "service_state.json"),
    )
    try:
        orchestrator._refresh_terminal_audit_health(
            [],
            scan_complete=True,
            scan_error_count=0,
            finalization_failure_count=1,
        )

        snapshot = orchestrator.get_snapshot()
        health = snapshot["terminal_audit_health"]
        assert health["finalization_failure_count"] == 1
        assert health["transport_failure_count"] == 0
        assert health["policy_incompatibility_count"] == 0
        assert any(
            str(alert["source"]).endswith("finalization_failures")
            for alert in snapshot["alerts"]
        )
    finally:
        orchestrator._tick_pool.shutdown(wait=True, cancel_futures=True)
        orchestrator._refresh_pool.shutdown(wait=True, cancel_futures=True)


def test_restart_reconciles_stale_no_candidate_alert_from_cancelled_metadata(
    tmp_path: Path,
) -> None:
    """Durable cancellation wins over a stale metrics cache after restart."""
    state_path = tmp_path / "service_state.json"
    tracker = _MetadataTracker()
    fingerprint = EvidenceFingerprint("a" * 64)
    cancelled = TerminalAuditRecord(
        audit_id="audit-cancelled",
        project_id="project-a",
        task_id="TASK-1",
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.CANCELLED,
    )
    tracker.metadata["TASK-1"] = {
        METADATA_KEY: TerminalAuditMetadata(pending_chain=[cancelled]).to_dict()
    }

    first = Orchestrator(
        ServiceConfig(workspace_root=str(tmp_path / "workspace")),
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(state_path),
    )
    try:
        # Simulate a crash window: the service-state metrics write landed, but
        # the alert registry had not yet been reconciled with tracker metadata.
        first.record_terminal_audit_no_candidate(
            "project-a", "TASK-1", "audit-cancelled", reason="stale callback"
        )
    finally:
        first._tick_pool.shutdown(wait=True, cancel_futures=True)
        first._refresh_pool.shutdown(wait=True, cancel_futures=True)

    restarted = Orchestrator(
        ServiceConfig(workspace_root=str(tmp_path / "workspace-2")),
        str(tmp_path / "WORKFLOW-2.md"),
        state_path=str(state_path),
    )
    try:
        restarted._tracker_for_project = lambda _project_id: tracker
        restarted._sync_terminal_audit_observability_alerts()
        assert not [
            alert
            for alert in restarted.get_snapshot()["alerts"]
            if "audit-cancelled" in str(alert.get("source", ""))
        ]
        assert restarted._terminal_audit_metrics.snapshot()["no_independent_candidate"] == 1
    finally:
        restarted._tick_pool.shutdown(wait=True, cancel_futures=True)
        restarted._refresh_pool.shutdown(wait=True, cancel_futures=True)


def test_terminal_state_retires_legacy_alert_after_fingerprint_changes_and_restart(
    tmp_path: Path,
) -> None:
    """A canonical terminal state retires an old alert without restaging."""
    state_path = tmp_path / "service_state.json"
    tracker = _MetadataTracker()
    fingerprint = EvidenceFingerprint("a" * 64)
    record = _no_auditor_record("audit-legacy", fingerprint)
    tracker.metadata["TASK-1"] = {
        METADATA_KEY: TerminalAuditMetadata(pending_chain=[record]).to_dict()
    }
    issue = Issue(
        id="TASK-1",
        identifier="TASK-1",
        title="Merged task",
        description="old evidence",
        state="Needs Human",
        project_id="project-a",
    )
    tracker.issues["TASK-1"] = issue

    first = Orchestrator(
        ServiceConfig(workspace_root=str(tmp_path / "workspace")),
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(state_path),
    )
    try:
        first._tracker_for_project = lambda _project_id: tracker
        first.record_terminal_audit_no_candidate(
            "project-a", "TASK-1", "audit-legacy", reason="legacy callback"
        )
        assert any(
            "audit-legacy" in str(alert.get("source", ""))
            for alert in first.get_snapshot()["alerts"]
        )

        # Merge changed the live evidence, so replaying the historical
        # override is not supported. The canonical tracker state is still
        # authoritative for retiring the old observability identity.
        issue.description = "new evidence after merge"
        issue.state = "Merged"
        recovered = first.get_snapshot()
        assert not [
            alert
            for alert in recovered["alerts"]
            if "audit-legacy" in str(alert.get("source", ""))
        ]
        assert first._terminal_audit_metrics.snapshot()["no_independent_candidate"] == 1
    finally:
        first._tick_pool.shutdown(wait=True, cancel_futures=True)
        first._refresh_pool.shutdown(wait=True, cancel_futures=True)

    restarted = Orchestrator(
        ServiceConfig(workspace_root=str(tmp_path / "workspace-2")),
        str(tmp_path / "WORKFLOW-2.md"),
        state_path=str(state_path),
    )
    try:
        restarted._tracker_for_project = lambda _project_id: tracker
        assert not [
            alert
            for alert in restarted.get_snapshot()["alerts"]
            if "audit-legacy" in str(alert.get("source", ""))
        ]
        assert restarted._terminal_audit_metrics.snapshot()["no_independent_candidate"] == 1
    finally:
        restarted._tick_pool.shutdown(wait=True, cancel_futures=True)
        restarted._refresh_pool.shutdown(wait=True, cancel_futures=True)


def test_retirement_rows_clear_only_old_id_when_task_reopened(
    tmp_path: Path,
) -> None:
    """A migrated retirement ledger must not hide a new Needs Human audit."""
    tracker = _MetadataTracker()
    fingerprint = EvidenceFingerprint("b" * 64)
    old_override = _no_auditor_record("audit-override", fingerprint)
    old_pass = _no_auditor_record("audit-pass", fingerprint)
    current = _no_auditor_record(
        "audit-current", fingerprint, completed_at="2026-07-31T12:00:00+00:00"
    )
    tracker.metadata["TASK-1"] = {
        METADATA_KEY: TerminalAuditMetadata(
            pending_chain=[old_override, old_pass, current],
            unknown_fields={
                "oompah.terminal_audit_retirements": [
                    {
                        "project_id": "project-a",
                        "task_id": "TASK-1",
                        "target_state": "Merged",
                        "evidence_fingerprint": fingerprint.digest,
                        "audit_ids": ["audit-override"],
                        "kind": "override",
                        "applied": True,
                    },
                    {
                        "project_id": "project-a",
                        "task_id": "TASK-1",
                        "target_state": "Merged",
                        "evidence_fingerprint": fingerprint.digest,
                        "audit_ids": ["audit-pass"],
                        "kind": "result",
                        "applied": True,
                    },
                ]
            },
        ).to_dict()
    }
    tracker.issues["TASK-1"] = Issue(
        id="TASK-1",
        identifier="TASK-1",
        title="Reopened task",
        description="needs another human decision",
        state="Needs Human",
        project_id="project-a",
    )
    orchestrator = Orchestrator(
        ServiceConfig(workspace_root=str(tmp_path / "workspace")),
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(tmp_path / "service_state.json"),
    )
    try:
        orchestrator._tracker_for_project = lambda _project_id: tracker
        for audit_id in ("audit-override", "audit-pass", "audit-current"):
            orchestrator.record_terminal_audit_no_candidate(
                "project-a", "TASK-1", audit_id, reason="migrated callback"
            )
        sources = [str(alert.get("source", "")) for alert in orchestrator.get_snapshot()["alerts"]]
        assert not any("audit-override" in source for source in sources)
        assert not any("audit-pass" in source for source in sources)
        assert any("audit-current" in source for source in sources)
        assert orchestrator._terminal_audit_metrics.snapshot()["no_independent_candidate"] == 3
    finally:
        orchestrator._tick_pool.shutdown(wait=True, cancel_futures=True)
        orchestrator._refresh_pool.shutdown(wait=True, cancel_futures=True)


def test_mismatched_retirement_identity_keeps_no_candidate_alert(
    tmp_path: Path,
) -> None:
    """An audit ID match without target/fingerprint proof must fail closed."""
    tracker = _MetadataTracker()
    fingerprint = EvidenceFingerprint("b" * 64)
    record = _no_auditor_record("audit-current", fingerprint)
    tracker.metadata["TASK-1"] = {
        METADATA_KEY: TerminalAuditMetadata(
            pending_chain=[record],
            unknown_fields={
                "oompah.terminal_audit_retirements": [
                    {
                        "project_id": "project-a",
                        "task_id": "TASK-1",
                        "target_state": "Done",
                        "evidence_fingerprint": EvidenceFingerprint("c" * 64).digest,
                        "audit_ids": ["audit-current"],
                        "kind": "result",
                        "applied": True,
                    }
                ]
            },
        ).to_dict()
    }
    tracker.issues["TASK-1"] = Issue(
        id="TASK-1",
        identifier="TASK-1",
        title="Needs human review",
        description="current audit must stay visible",
        state="Needs Human",
        project_id="project-a",
    )
    orchestrator = Orchestrator(
        ServiceConfig(workspace_root=str(tmp_path / "workspace")),
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(tmp_path / "service_state.json"),
    )
    try:
        orchestrator._tracker_for_project = lambda _project_id: tracker
        orchestrator.record_terminal_audit_no_candidate(
            "project-a", "TASK-1", "audit-current", reason="current callback"
        )
        assert any(
            "audit-current" in str(alert.get("source", ""))
            for alert in orchestrator.get_snapshot()["alerts"]
        )
    finally:
        orchestrator._tick_pool.shutdown(wait=True, cancel_futures=True)
        orchestrator._refresh_pool.shutdown(wait=True, cancel_futures=True)


def test_migrated_override_and_pass_metadata_retire_older_identities(
    tmp_path: Path,
) -> None:
    """Legacy applied decisions clear old alerts without hiding a reopen."""
    tracker = _MetadataTracker()
    override_fingerprint = EvidenceFingerprint("e" * 64)
    pass_fingerprint = EvidenceFingerprint("f" * 64)
    old_override = _no_auditor_record(
        "audit-old-override",
        override_fingerprint,
        target=TargetState.DONE,
        completed_at="2026-07-31T10:00:00+00:00",
    )
    old_pass = _no_auditor_record(
        "audit-old-pass",
        pass_fingerprint,
        target=TargetState.MERGED,
        completed_at="2026-07-31T10:00:00+00:00",
    )
    pass_attempt = AuditAttempt(
        attempt_id="attempt-pass",
        target_state=TargetState.MERGED,
        evidence_fingerprint=pass_fingerprint,
        request_state=RequestState.COMPLETED,
        verdict=Verdict.PASS,
        created_at="2026-07-31T11:00:00+00:00",
        completed_at="2026-07-31T11:00:00+00:00",
    )
    later_pass = TerminalAuditRecord(
        audit_id="audit-later-pass",
        project_id="project-a",
        task_id="TASK-1",
        target_state=TargetState.MERGED,
        evidence_fingerprint=pass_fingerprint,
        request_state=RequestState.COMPLETED,
        attempts=[pass_attempt],
        created_at="2026-07-31T11:00:00+00:00",
        updated_at="2026-07-31T11:00:00+00:00",
    )
    current = _no_auditor_record(
        "audit-reopened",
        pass_fingerprint,
        target=TargetState.MERGED,
        completed_at="2026-07-31T12:00:00+00:00",
    )
    override = OverrideRecord(
        override_id="override-legacy",
        project_id="project-a",
        task_id="TASK-1",
        target_state=TargetState.DONE,
        evidence_fingerprint=override_fingerprint,
        authorized_by=ContributorIdentity("owner", "github"),
        reason="Owner approved terminal completion.",
        created_at="2026-07-31T10:30:00+00:00",
    ).to_dict()
    override["applied"] = True
    tracker.metadata["TASK-1"] = {
        METADATA_KEY: TerminalAuditMetadata(
            pending_chain=[old_override, old_pass, later_pass, current],
            unknown_fields={"oompah.terminal_override_records": [override]},
        ).to_dict()
    }
    tracker.issues["TASK-1"] = Issue(
        id="TASK-1",
        identifier="TASK-1",
        title="Reopened task",
        description="still in validation",
        state="In Validation",
        project_id="project-a",
    )
    orchestrator = Orchestrator(
        ServiceConfig(workspace_root=str(tmp_path / "workspace")),
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(tmp_path / "service_state.json"),
    )
    try:
        orchestrator._tracker_for_project = lambda _project_id: tracker
        for audit_id in ("audit-old-override", "audit-old-pass", "audit-reopened"):
            orchestrator.record_terminal_audit_no_candidate(
                "project-a", "TASK-1", audit_id, reason="legacy callback"
            )
        sources = [str(alert.get("source", "")) for alert in orchestrator.get_snapshot()["alerts"]]
        assert not any("audit-old-override" in source for source in sources)
        assert not any("audit-old-pass" in source for source in sources)
        assert any("audit-reopened" in source for source in sources)
    finally:
        orchestrator._tick_pool.shutdown(wait=True, cancel_futures=True)
        orchestrator._refresh_pool.shutdown(wait=True, cancel_futures=True)


def test_no_candidate_reconciliation_fails_closed_on_read_failure_or_quarantine(
    tmp_path: Path,
) -> None:
    """Unknown tracker/metadata state must never clear an actionable alert."""

    class _ReadFailureTracker(_MetadataTracker):
        def fetch_issue_detail(self, identifier: str) -> Issue | None:
            raise RuntimeError(f"read failed for {identifier}")

    fingerprint = EvidenceFingerprint("c" * 64)
    failing_tracker = _ReadFailureTracker()
    record = _no_auditor_record("audit-read-failure", fingerprint)
    failing_tracker.metadata["TASK-1"] = {
        METADATA_KEY: TerminalAuditMetadata(pending_chain=[record]).to_dict()
    }
    failing_orchestrator = Orchestrator(
        ServiceConfig(workspace_root=str(tmp_path / "workspace-read")),
        str(tmp_path / "WORKFLOW-read.md"),
        state_path=str(tmp_path / "state-read.json"),
    )
    try:
        failing_orchestrator._tracker_for_project = lambda _project_id: failing_tracker
        failing_orchestrator.record_terminal_audit_no_candidate(
            "project-a", "TASK-1", "audit-read-failure", reason="read failure"
        )
        assert any(
            "audit-read-failure" in str(alert.get("source", ""))
            for alert in failing_orchestrator.get_snapshot()["alerts"]
        )
    finally:
        failing_orchestrator._tick_pool.shutdown(wait=True, cancel_futures=True)
        failing_orchestrator._refresh_pool.shutdown(wait=True, cancel_futures=True)

    quarantined_tracker = _MetadataTracker()
    quarantined_tracker.metadata["TASK-1"] = {
        METADATA_KEY: TerminalAuditMetadata(
            quarantine=MetadataQuarantine("d" * 64)
        ).to_dict()
    }
    quarantined_orchestrator = Orchestrator(
        ServiceConfig(workspace_root=str(tmp_path / "workspace-quarantine")),
        str(tmp_path / "WORKFLOW-quarantine.md"),
        state_path=str(tmp_path / "state-quarantine.json"),
    )
    try:
        quarantined_orchestrator._tracker_for_project = lambda _project_id: quarantined_tracker
        quarantined_orchestrator.record_terminal_audit_no_candidate(
            "project-a", "TASK-1", "audit-quarantine", reason="quarantine"
        )
        assert any(
            "audit-quarantine" in str(alert.get("source", ""))
            for alert in quarantined_orchestrator.get_snapshot()["alerts"]
        )
    finally:
        quarantined_orchestrator._tick_pool.shutdown(wait=True, cancel_futures=True)
        quarantined_orchestrator._refresh_pool.shutdown(wait=True, cancel_futures=True)


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


def test_pass_clears_sibling_alert_in_production_registry_across_restart(
    tmp_path: Path,
) -> None:
    """OOMPAH-644 barrier: a cancelled sibling's actionable alert must clear
    against the production alert registry and stay clear across restart.

    Two audits with the same target/fingerprint are registered; one is
    cancelled and gets a live no_independent_candidate alert. After clear,
    the alert must be gone.  After a restart with the CANCELLED metadata
    seeded, the reconciliation path must not re-emit the alert.
    """
    state_path = tmp_path / "service_state.json"
    tracker = _MetadataTracker()
    fingerprint = EvidenceFingerprint("a" * 64)
    passed = TerminalAuditRecord(
        audit_id="audit-passed",
        project_id="project-a",
        task_id="TASK-1",
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.COMPLETED,
    )
    cancelled_sibling = TerminalAuditRecord(
        audit_id="audit-sibling",
        project_id="project-a",
        task_id="TASK-1",
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.SUPERSEDED,
    )
    tracker.metadata["TASK-1"] = {
        METADATA_KEY: TerminalAuditMetadata(
            pending_chain=[passed, cancelled_sibling]
        ).to_dict()
    }

    first = Orchestrator(
        ServiceConfig(workspace_root=str(tmp_path / "workspace")),
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(state_path),
    )
    try:
        # Simulate an actionable alert that was registered before PASS won.
        first.record_terminal_audit_no_candidate(
            "project-a", "TASK-1", "audit-sibling", reason="race window"
        )
        before = first.get_snapshot()["alerts"]
        assert any("audit-sibling" in str(a.get("source", "")) for a in before)

        # The coordinator's post-PASS cleanup calls this method for every
        # cancelled sibling.  It must retire the alert against the live
        # production registry, not only the metrics counter.
        first.clear_terminal_audit_alert("project-a", "TASK-1", "audit-sibling")
        after = first.get_snapshot()["alerts"]
        assert not [
            a for a in after if "audit-sibling" in str(a.get("source", ""))
        ]
    finally:
        first._tick_pool.shutdown(wait=True, cancel_futures=True)
        first._refresh_pool.shutdown(wait=True, cancel_futures=True)

    # Restart with the same state file; the durable metadata still shows the
    # sibling as SUPERSEDED, and reconciliation must not re-emit the alert.
    restarted = Orchestrator(
        ServiceConfig(workspace_root=str(tmp_path / "workspace-2")),
        str(tmp_path / "WORKFLOW-2.md"),
        state_path=str(state_path),
    )
    try:
        restarted._tracker_for_project = lambda _project_id: tracker
        restarted._sync_terminal_audit_observability_alerts()
        recovered = restarted.get_snapshot()["alerts"]
        assert not [
            a for a in recovered
            if "audit-sibling" in str(a.get("source", ""))
        ]
    finally:
        restarted._tick_pool.shutdown(wait=True, cancel_futures=True)
        restarted._refresh_pool.shutdown(wait=True, cancel_futures=True)


def test_project_isolation_pass_alert_cleanup_does_not_cross_projects(
    tmp_path: Path,
) -> None:
    """Alert cleanup must be scoped by project id.

    Two projects host a task with identical identifier and audit id (a real
    possibility across managed projects).  Clearing one must not touch the
    other's actionable alerts or metrics counters.
    """
    orchestrator = Orchestrator(
        ServiceConfig(workspace_root=str(tmp_path / "workspace")),
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(tmp_path / "service_state.json"),
    )
    try:
        orchestrator.record_terminal_audit_no_candidate(
            "project-a", "TASK-1", "audit-1", reason="race window a"
        )
        orchestrator.record_terminal_audit_no_candidate(
            "project-b", "TASK-1", "audit-1", reason="race window b"
        )
        before = orchestrator.get_snapshot()["alerts"]
        source_strings_before = [str(a.get("source", "")) for a in before]
        assert any(
            "project-a:TASK-1:audit-1" in src for src in source_strings_before
        )
        assert any(
            "project-b:TASK-1:audit-1" in src for src in source_strings_before
        )

        # Retire only project-a's audit; project-b's alert must remain.
        orchestrator.clear_terminal_audit_alert("project-a", "TASK-1", "audit-1")
        after = orchestrator.get_snapshot()["alerts"]
        source_strings_after = [str(a.get("source", "")) for a in after]
        assert not any(
            "project-a:TASK-1:audit-1" in src for src in source_strings_after
        )
        assert any(
            "project-b:TASK-1:audit-1" in src for src in source_strings_after
        )

        # Historical counters are retained regardless of alert clearing:
        # both projects contributed one no_independent_candidate observation.
        metrics_snapshot = orchestrator._terminal_audit_metrics.snapshot()
        assert metrics_snapshot["no_independent_candidate"] == 2
    finally:
        orchestrator._tick_pool.shutdown(wait=True, cancel_futures=True)
        orchestrator._refresh_pool.shutdown(wait=True, cancel_futures=True)
