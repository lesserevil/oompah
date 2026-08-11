"""Deterministic tests for terminal-audit metrics and actionable health."""

from __future__ import annotations

import asyncio
import threading
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from oompah.auditor_candidate_selector import AuditorCandidateSelector
from oompah.config import ServiceConfig
from oompah.models import Issue, Project, RunningEntry
from oompah.orchestrator import (
    DispatchEvent,
    DispatchEventType,
    Orchestrator,
    _AuditCandidateScan,
)
from oompah.roles import Candidate
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
    compute_issue_evidence_fingerprint,
)
from oompah.terminal_audit_health import (
    HEALTH_ALERT_PREFIX,
    AuditHealthObservation,
    build_terminal_audit_health,
)
from oompah.terminal_audit_metadata import (
    METADATA_KEY,
    MetadataQuarantine,
    TerminalAuditMetadata,
)
from oompah.terminal_audit_observability import (
    AuditAlertCondition,
    METRICS_STATE_KEY,
    TerminalAuditAlertRegistry,
    TerminalAuditMetrics,
    threshold_conditions,
)
from oompah.workflow_contract import TaskDisposition, WorkflowOwner
from oompah.work_decision import PermittedAction, WorkDecision


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


def _aged_pending_observation(
    task_id: str = "TASK-STALE",
    audit_id: str = "audit-stale",
) -> AuditHealthObservation:
    old_timestamp = "2000-01-01T00:00:00+00:00"
    pending = TerminalAuditRecord(
        audit_id=audit_id,
        project_id="project-a",
        task_id=task_id,
        target_state=TargetState.DONE,
        evidence_fingerprint=EvidenceFingerprint("d" * 64),
        request_state=RequestState.PENDING,
        created_at=old_timestamp,
    )
    return AuditHealthObservation(
        project_id="project-a",
        issue_identifier=task_id,
        issue_created_at=old_timestamp,
        record=pending,
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


def test_pending_age_starts_when_chained_stage_becomes_eligible() -> None:
    now = datetime(2026, 8, 11, 12, tzinfo=timezone.utc)
    record = TerminalAuditRecord(
        audit_id="audit-merged",
        project_id="project-a",
        task_id="TASK-CHAIN",
        target_state=TargetState.MERGED,
        evidence_fingerprint=EvidenceFingerprint("e" * 64),
        request_state=RequestState.PENDING,
        created_at=(now - timedelta(hours=3)).isoformat(),
        eligible_at=(now - timedelta(seconds=30)).isoformat(),
        prerequisite_audit_id="audit-done",
    )

    health = build_terminal_audit_health(
        [record], now=now, stale_after_seconds=60
    )

    assert health.pending_count == 1
    assert health.oldest_pending_age_seconds == 30
    assert health.stale_pending_count == 0


def test_blocked_chained_stage_has_no_pending_age() -> None:
    now = datetime(2026, 8, 11, 12, tzinfo=timezone.utc)
    record = TerminalAuditRecord(
        audit_id="audit-merged",
        project_id="project-a",
        task_id="TASK-CHAIN",
        target_state=TargetState.MERGED,
        evidence_fingerprint=EvidenceFingerprint("e" * 64),
        request_state=RequestState.PENDING,
        created_at=(now - timedelta(hours=3)).isoformat(),
        eligible_at=None,
        prerequisite_audit_id="audit-done",
    )

    health = build_terminal_audit_health(
        [record], now=now, stale_after_seconds=60
    )

    assert health.pending_count == 1
    assert health.oldest_pending_age_seconds is None
    assert health.stale_pending_count == 0


def test_control_lock_metrics_persist_restore_and_shape() -> None:
    persisted: dict = {}
    first = TerminalAuditMetrics(
        load_state=lambda: persisted,
        save_state=lambda update: persisted.update(update),
    )
    first.record_control_lock_timing(
        "project-a",
        wait_seconds=0.25,
        hold_seconds=0.5,
        timed_out=False,
    )
    first.record_control_lock_timing(
        "project-b",
        wait_seconds=0.75,
        hold_seconds=0.0,
        timed_out=True,
    )

    expected = {
        "acquisitions": 1,
        "timeouts": 1,
        "wait_seconds_total": 1.0,
        "wait_seconds_max": 0.75,
        "wait_seconds_last": 0.75,
        "hold_seconds_total": 0.5,
        "hold_seconds_max": 0.5,
        "hold_seconds_last": 0.0,
        "last_project_id": "project-b",
    }
    assert first.snapshot()["control_lock"] == expected

    restarted = TerminalAuditMetrics(
        load_state=lambda: persisted,
        save_state=lambda update: persisted.update(update),
    )
    assert restarted.snapshot()["control_lock"] == expected
    assert restarted.persistence_corrupt is False


def test_pre_control_lock_metrics_restore_with_zero_defaults() -> None:
    persisted: dict = {}
    first = TerminalAuditMetrics(
        load_state=lambda: persisted,
        save_state=lambda update: persisted.update(update),
    )
    first.record_queued("project-a", "TASK-1", "audit-1")
    persisted[METRICS_STATE_KEY].pop("control_lock")

    restarted = TerminalAuditMetrics(load_state=lambda: persisted)

    assert restarted.persistence_corrupt is False
    assert restarted.snapshot()["control_lock"] == {
        "acquisitions": 0,
        "timeouts": 0,
        "wait_seconds_total": 0.0,
        "wait_seconds_max": 0.0,
        "wait_seconds_last": 0.0,
        "hold_seconds_total": 0.0,
        "hold_seconds_max": 0.0,
        "hold_seconds_last": 0.0,
        "last_project_id": None,
    }


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


def test_direct_recovery_gate_telemetry_uses_durable_audit_head() -> None:
    """A missing reusable gate must still report the exact staged audit head."""

    head = "a" * 40
    issue = Issue(
        id="TASK-1",
        identifier="TASK-1",
        title="Direct recovery",
        description="",
        state="In Validation",
        project_id="project-a",
    )
    fingerprint = compute_issue_evidence_fingerprint(issue, "project-a")
    attempt = AuditAttempt(
        attempt_id="attempt-1",
        target_state=TargetState.MERGED,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.IN_PROGRESS,
        branch_key="work",
        selected_ref=head,
        selected_sha=head,
    )
    record = TerminalAuditRecord(
        audit_id="audit-1",
        project_id="project-a",
        task_id="TASK-1",
        target_state=TargetState.MERGED,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.IN_PROGRESS,
        attempts=[attempt],
        previous_state="Ready to Integrate",
        selected_ref=head,
        selected_sha=head,
    )
    tracker = _MetadataTracker()
    tracker.issues[issue.identifier] = issue
    tracker.metadata[issue.identifier] = {
        METADATA_KEY: TerminalAuditMetadata(pending_chain=[record]).to_dict()
    }
    project = Project(
        id="project-a",
        name="project-a",
        repo_url="repo",
        repo_path="/managed/repo",
        default_branch="main",
        test_command_full="make test",
    )
    orchestrator = object.__new__(Orchestrator)
    orchestrator.project_store = MagicMock()
    orchestrator.project_store.project_write_lock.return_value = threading.RLock()
    orchestrator._tracker_for_project = MagicMock(return_value=tracker)
    orchestrator._branch_quality_gate = MagicMock()
    orchestrator._branch_quality_gate.lookup.return_value = None
    orchestrator._quality_gate_branch_head = MagicMock()
    orchestrator._terminal_audit_metrics = TerminalAuditMetrics()
    target = SimpleNamespace(
        project_id="project-a",
        task_id="TASK-1",
        audit_id="audit-1",
        attempt_id="attempt-1",
        target_state="Merged",
        previous_state="Ready to Integrate",
        evidence_fingerprint=fingerprint.digest,
        selected_ref=head,
        selected_sha=head,
    )

    bundle = orchestrator._terminal_audit_quality_gate_evidence(
        issue,
        project,
        target,
    )
    snapshot = orchestrator._terminal_audit_metrics.snapshot()

    assert bundle["decision"] == "full_gate_required"
    assert bundle["accepted_head_sha"] == head
    assert snapshot["validation"]["last_decision"]["decision"] == (
        "full_gate_required"
    )
    assert snapshot["validation"]["last_decision"]["head_sha"] == head
    orchestrator._branch_quality_gate.lookup.assert_called_once_with(
        repo_identity="repo",
        target_branch="main",
        work_branch="work",
        head_sha=head,
        command="make test",
    )
    orchestrator._quality_gate_branch_head.assert_not_called()


@pytest.mark.parametrize(
    "command",
    [
        "make test",
        "make test-serial",
        "make test-unit",
        "./ci/test.sh",
        "env CI=1 make test-serial",
        "env -S 'make test'",
        "echo ready && make test",
        "bash -lc 'make test-serial'",
        "timeout 30 make -C . test",
        "pytest",
        "pytest -q",
        "pytest -p no:foo",
        "python -m pytest -n auto",
        "bash -lc 'python -m pytest -q -W error'",
        "pytest tests/",
        "npm test",
        "pnpm run test",
        "yarn test",
        "cargo test",
        "tox",
        "nox -s tests",
        "python -m unittest",
        "python -m unittest discover -s tests",
    ],
)
def test_validation_telemetry_semantically_classifies_full_suite_commands(
    command,
) -> None:
    metrics = TerminalAuditMetrics()

    metrics.record_auditor_validation_command(
        "project-a",
        "TASK-1",
        "audit-1",
        command=command,
        configured_command="make test",
    )

    snapshot = metrics.snapshot()
    assert snapshot["auditor_full_suite_runs"] == 1
    assert snapshot["focused_supplemental_commands"] == 0


def test_validation_telemetry_keeps_targeted_pytest_focused() -> None:
    metrics = TerminalAuditMetrics()

    metrics.record_auditor_validation_command(
        "project-a",
        "TASK-1",
        "audit-1",
        command="python -m pytest tests/test_warning.py -q",
        configured_command="make test",
    )

    snapshot = metrics.snapshot()
    assert snapshot["focused_supplemental_commands"] == 1
    assert snapshot["auditor_full_suite_runs"] == 0


def test_validation_telemetry_never_reclassifies_opaque_pytest_as_focused() -> None:
    metrics = TerminalAuditMetrics()

    metrics.record_auditor_validation_command(
        "project-a",
        "TASK-1",
        "audit-1",
        command="pytest tests/test_warning.py -q",
        configured_command="make test",
        validation_scope="opaque",
    )

    snapshot = metrics.snapshot()
    assert snapshot["focused_supplemental_commands"] == 0
    assert snapshot["auditor_full_suite_runs"] == 1
    assert snapshot["validation"]["last_command"]["category"] == (
        "auditor_full_suite_runs"
    )
    assert snapshot["validation"]["last_command"]["validation_scope"] == "opaque"


def test_orchestrator_forwards_trusted_validation_scope() -> None:
    recorded: dict[str, object] = {}
    orchestrator = object.__new__(Orchestrator)
    orchestrator._terminal_audit_metrics = SimpleNamespace(
        record_auditor_validation_command=lambda *args, **kwargs: recorded.update(
            {"args": args, "kwargs": kwargs}
        )
    )
    orchestrator.project_store = SimpleNamespace(get=lambda _project_id: None)

    orchestrator.record_auditor_validation_command(
        audit_target=SimpleNamespace(
            project_id="project-a",
            task_id="TASK-1",
            audit_id="audit-1",
        ),
        command="pytest tests/test_warning.py -q",
        validation_scope="opaque",
    )

    assert recorded["args"] == ("project-a", "TASK-1", "audit-1")
    assert recorded["kwargs"]["validation_scope"] == "opaque"


def test_validation_command_lifecycle_records_timeout_once_across_restart() -> None:
    persisted: dict = {}
    first = TerminalAuditMetrics(
        load_state=lambda: persisted,
        save_state=lambda update: persisted.update(update),
    )
    first.record_auditor_validation_command(
        "project-a",
        "TASK-1",
        "audit-1",
        command="make test-serial",
        configured_command="make test",
        succeeded=False,
        phase="started",
        outcome="running",
        invocation_id="run-1",
    )

    running = first.snapshot()
    assert running["auditor_full_suite_runs"] == 1
    assert running["validation_commands_started"] == 1
    assert running["validation_commands_completed"] == 0
    assert "run-1" in running["validation"]["in_flight"]

    restarted = TerminalAuditMetrics(
        load_state=lambda: persisted,
        save_state=lambda update: persisted.update(update),
    )
    restarted.record_auditor_validation_command(
        "project-a",
        "TASK-1",
        "audit-1",
        command="make test-serial",
        configured_command="make test",
        duration_seconds=15.0,
        succeeded=False,
        phase="completed",
        outcome="timed_out",
        invocation_id="run-1",
    )
    # A repeated provider callback is idempotent for the same invocation.
    restarted.record_auditor_validation_command(
        "project-a",
        "TASK-1",
        "audit-1",
        command="make test-serial",
        configured_command="make test",
        duration_seconds=15.0,
        succeeded=False,
        phase="completed",
        outcome="timed_out",
        invocation_id="run-1",
    )

    snapshot = restarted.snapshot()
    assert snapshot["auditor_full_suite_runs"] == 1
    assert snapshot["validation_commands_started"] == 1
    assert snapshot["validation_commands_completed"] == 1
    assert snapshot["validation_commands_timed_out"] == 1
    assert snapshot["validation_commands_failed"] == 0
    assert snapshot["validation"]["in_flight"] == {}
    assert snapshot["validation"]["last_command"]["outcome"] == "timed_out"


def test_validation_command_lifecycle_records_failed_focused_completion() -> None:
    metrics = TerminalAuditMetrics()
    for phase, outcome in (("started", "running"), ("completed", "failed")):
        metrics.record_auditor_validation_command(
            "project-a",
            "TASK-1",
            "audit-1",
            command="pytest tests/test_warning.py -q",
            configured_command="make test",
            succeeded=False,
            phase=phase,
            outcome=outcome,
            invocation_id="run-focused",
        )

    snapshot = metrics.snapshot()
    assert snapshot["focused_supplemental_commands"] == 1
    assert snapshot["validation_commands_started"] == 1
    assert snapshot["validation_commands_completed"] == 1
    assert snapshot["validation_commands_failed"] == 1


def test_validation_command_lifecycle_records_passed_full_completion() -> None:
    metrics = TerminalAuditMetrics()
    for phase, outcome, succeeded in (
        ("started", "running", False),
        ("completed", "passed", True),
    ):
        metrics.record_auditor_validation_command(
            "project-a",
            "TASK-1",
            "audit-1",
            command="make test",
            configured_command="make test",
            succeeded=succeeded,
            phase=phase,
            outcome=outcome,
            invocation_id="run-full",
        )

    snapshot = metrics.snapshot()
    assert snapshot["auditor_full_suite_runs"] == 1
    assert snapshot["validation_commands_started"] == 1
    assert snapshot["validation_commands_completed"] == 1
    assert snapshot["validation_commands_failed"] == 0
    assert snapshot["validation_commands_timed_out"] == 0
    assert snapshot["validation"]["last_command"]["outcome"] == "passed"


def test_validation_reuse_policy_is_idempotent_and_survives_restart() -> None:
    persisted: dict = {}
    first = TerminalAuditMetrics(
        load_state=lambda: persisted,
        save_state=lambda update: persisted.update(update),
    )
    kwargs = {
        "attempt_id": "attempt-1",
        "invocation_id": "invocation-1",
        "command": "make test-serial",
        "decision": "allowed_distinct_mode",
        "justification": "required race-only mode",
    }
    first.record_validation_reuse_policy(
        "project-a",
        "TASK-1",
        "audit-1",
        **kwargs,
    )

    restarted = TerminalAuditMetrics(
        load_state=lambda: persisted,
        save_state=lambda update: persisted.update(update),
    )
    restarted.record_validation_reuse_policy(
        "project-a",
        "TASK-1",
        "audit-1",
        **kwargs,
    )

    snapshot = restarted.snapshot()
    assert snapshot["reused_gate_distinct_mode_allowed"] == 1
    assert snapshot["validation"]["last_reuse_policy"] == {
        "project_id": "project-a",
        "task_id": "TASK-1",
        "audit_id": "audit-1",
        **kwargs,
        "recorded_at": snapshot["validation"]["last_reuse_policy"][
            "recorded_at"
        ],
    }
    with pytest.raises(ValueError, match="identity collision"):
        restarted.record_validation_reuse_policy(
            "project-a",
            "TASK-1",
            "audit-1",
            **{**kwargs, "decision": "denied_reused_gate"},
        )


def test_validation_reuse_policy_requires_attempt_identity() -> None:
    metrics = TerminalAuditMetrics()

    with pytest.raises(ValueError, match="attempt_id"):
        metrics.record_validation_reuse_policy(
            "project-a",
            "TASK-1",
            "audit-1",
            attempt_id="",
            invocation_id="invocation-1",
            command="make test",
            decision="denied_reused_gate",
        )


def test_post_gate_inspection_denial_is_recorded() -> None:
    metrics = TerminalAuditMetrics()

    metrics.record_validation_reuse_policy(
        "project-a",
        "TASK-1",
        "audit-1",
        attempt_id="attempt-1",
        invocation_id="invocation-1",
        command="git diff HEAD~1 HEAD tests/test_one.py",
        decision="denied_post_gate_inspection",
    )

    snapshot = metrics.snapshot()
    assert snapshot["reused_gate_validation_denied"] == 1
    assert snapshot["validation"]["last_reuse_policy"]["decision"] == (
        "denied_post_gate_inspection"
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


def test_sync_pending_does_not_resurrect_a_worker_discard_after_restart() -> None:
    """A recovery refresh cannot turn a lost worker into a running gauge."""
    persisted: dict[str, object] = {}
    metrics = TerminalAuditMetrics(
        load_state=lambda: persisted,
        save_state=lambda update: persisted.update(update),
    )
    fingerprint = EvidenceFingerprint("c" * 64)
    stale = TerminalAuditRecord(
        audit_id="audit-worker-lost",
        project_id="project-a",
        task_id="TASK-1",
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.IN_PROGRESS,
    )
    live = TerminalAuditRecord(
        audit_id="audit-live",
        project_id="project-a",
        task_id="TASK-2",
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.PENDING,
    )
    stale_entry = SimpleNamespace(
        project_id=stale.project_id,
        task_id=stale.task_id,
        audit_id=stale.audit_id,
        record=stale,
    )
    live_entry = SimpleNamespace(
        project_id=live.project_id,
        task_id=live.task_id,
        audit_id=live.audit_id,
        record=live,
    )

    metrics.record_running(*("project-a", "TASK-1", "audit-worker-lost"))
    metrics.discard_missing_running([])
    assert metrics.snapshot()["stale_discarded"] == 1

    metrics.sync_pending([stale_entry, live_entry])
    first = metrics.snapshot()
    assert first["queued"] == 1
    assert first["running"] == 0
    assert first["oldest_queue_task_id"] == "TASK-2"
    assert first["stale_discarded"] == 1

    restarted = TerminalAuditMetrics(
        load_state=lambda: persisted,
        save_state=lambda update: persisted.update(update),
    )
    restarted.sync_pending([stale_entry, live_entry])
    second = restarted.snapshot()
    assert second["queued"] == 1
    assert second["running"] == 0
    assert second["stale_discarded"] == 1

    # A coordinator-owned run event is a new proof of liveness and is allowed
    # to re-arm the identity without increasing the lifetime stale counter.
    restarted.record_running("project-a", "TASK-1", "audit-worker-lost")
    assert restarted.snapshot()["running"] == 1
    restarted.sync_pending([stale_entry, live_entry])
    assert restarted.snapshot()["running"] == 1
    assert restarted.snapshot()["stale_discarded"] == 1

    # An owner override can be ahead of its final metadata cleanup during a
    # crash window; that durable authority must also prevent rehydration.
    restarted.record_overridden("project-a", "TASK-1", "audit-worker-lost")
    restarted.sync_pending([stale_entry, live_entry])
    assert restarted.snapshot()["running"] == 0
    assert restarted.snapshot()["queued"] == 1
    assert restarted.snapshot()["overridden"] == 1
    assert restarted.snapshot()["stale_discarded"] == 1


def test_queue_age_threshold_is_informational_not_actionable() -> None:
    now = datetime(2026, 7, 29, 12, tzinfo=timezone.utc)
    clock = _Clock(now)
    metrics = TerminalAuditMetrics(clock=clock)
    metrics.record_queued("project-a", "TASK-1", "audit-1", queued_at=now - timedelta(seconds=61), attempts=1)
    snapshot = metrics.snapshot(now=now)
    assert snapshot["oldest_queue_age_seconds"] == 61
    assert threshold_conditions(metrics, max_attempts=3, max_age_seconds=60) == []


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
    assert alert["action_required"] is True
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


def test_partial_health_scan_keeps_one_generation_of_facts_and_alerts(
    tmp_path: Path,
) -> None:
    """A partial scan cannot pair empty current counts with an older alert."""
    orchestrator = Orchestrator(
        ServiceConfig(workspace_root=str(tmp_path / "workspace")),
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(tmp_path / "service_state.json"),
    )
    observation = _aged_pending_observation()
    try:
        orchestrator._refresh_terminal_audit_health(
            [observation], scan_complete=True, scan_error_count=0
        )
        orchestrator._refresh_terminal_audit_health(
            [], scan_complete=False, scan_error_count=1
        )

        incomplete = orchestrator.get_snapshot()
        health = incomplete["terminal_audit_health"]
        assert health == incomplete["health"]["terminal_audit"]
        assert health["pending_count"] == 1
        assert health["stale_pending_count"] == 1
        assert health["oldest_pending_age_seconds"] is not None
        assert health["scan_complete"] is False
        assert health["scan_error_count"] == 1
        health_alerts = {
            alert["source"]: alert
            for alert in incomplete["alerts"]
            if str(alert.get("source", "")).startswith(HEALTH_ALERT_PREFIX)
        }
        backlog = health_alerts[HEALTH_ALERT_PREFIX + "backlog_age"]
        assert "across 1 pending audit(s)" in backlog["detail"]
        assert HEALTH_ALERT_PREFIX + "scan" in health_alerts

        orchestrator._refresh_terminal_audit_health(
            [], scan_complete=True, scan_error_count=0
        )
        recovered = orchestrator.get_snapshot()
        assert recovered["terminal_audit_health"]["pending_count"] == 0
        assert recovered["terminal_audit_health"]["stale_pending_count"] == 0
        assert recovered["terminal_audit_health"]["oldest_pending_at"] is None
        assert (
            recovered["terminal_audit_health"]["oldest_pending_age_seconds"]
            is None
        )
        assert not [
            alert
            for alert in recovered["alerts"]
            if alert.get("source") == HEALTH_ALERT_PREFIX + "backlog_age"
        ]
    finally:
        orchestrator._tick_pool.shutdown(wait=True, cancel_futures=True)
        orchestrator._refresh_pool.shutdown(wait=True, cancel_futures=True)


@pytest.mark.asyncio
async def test_paused_and_restart_deferred_audit_then_resume_restores_dispatch(
    tmp_path: Path,
) -> None:
    """Periodic health retains paused work and resume admits its launch."""
    project_store = MagicMock()
    project = SimpleNamespace(id="project-a", paused=True)
    project_store.list_all.return_value = [project]
    project_store.get.return_value = project
    orchestrator = Orchestrator(
        ServiceConfig(
            workspace_root=str(tmp_path / "workspace"),
            duplicate_preflight_max_agents=0,
        ),
        str(tmp_path / "WORKFLOW.md"),
        project_store=project_store,
        state_path=str(tmp_path / "service_state.json"),
    )
    created_at = datetime(2000, 1, 1, tzinfo=timezone.utc)
    fingerprint = EvidenceFingerprint("c" * 64)
    issue = Issue(
        id="issue-launch",
        identifier="TASK-LAUNCH",
        title="Launch an independent terminal auditor",
        description="Verify health observes the durable launch fence.",
        state="In Validation",
        project_id="project-a",
        branch_name="task-launch",
        created_at=created_at,
    )
    pending = TerminalAuditRecord(
        audit_id="audit-launch",
        project_id="project-a",
        task_id=issue.identifier,
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.PENDING,
        created_at=created_at.isoformat(),
    )
    store = MagicMock()
    store.read.return_value = SimpleNamespace(
        pending_chain=[pending],
        is_quarantined=False,
        unknown_fields={},
    )
    selector = MagicMock()
    selector.select_candidates.return_value = (
        [Candidate(provider_id="provider-a", model="model-a")],
        None,
    )
    tracker = MagicMock()
    tracker.get_metadata.return_value = {}
    update_record = MagicMock(return_value=True)
    launch_state = {"completed": False}

    async def _mark_launched(*_args, **_kwargs) -> bool:
        launch_state["completed"] = True
        return True

    try:
        with (
            patch.object(
                orchestrator,
                "_available_slots",
                side_effect=lambda: (
                    0 if project.paused or launch_state["completed"] else 1
                ),
            ),
            patch.object(
                orchestrator,
                "_dispatch_is_blocked",
                return_value=False,
            ),
            patch.object(
                orchestrator,
                "_fetch_audit_candidates",
                return_value=_AuditCandidateScan((issue,)),
            ),
            patch.object(orchestrator, "_audit_store", return_value=store),
            patch.object(
                orchestrator,
                "_bind_audit_record_revision",
                return_value=pending,
            ),
            patch.object(
                orchestrator,
                "_prepare_audit_selector",
                new=AsyncMock(return_value=(selector, None)),
            ),
            patch.object(
                orchestrator,
                "_terminal_audit_validation_configuration_error",
                return_value=None,
            ),
            patch.object(orchestrator, "_audit_branch_busy", return_value=False),
            patch.object(orchestrator, "_tracker_for_issue", return_value=tracker),
            patch.object(
                orchestrator, "_audit_update_record", new=update_record
            ),
            patch.object(
                orchestrator,
                "_dispatch",
                new=AsyncMock(side_effect=_mark_launched),
            ),
        ):
            paused_result = await orchestrator._dispatch_audit_lane()

            assert paused_result["audit_dispatch"] >= 0
            assert orchestrator._audit_metrics["last_dispatched_count"] == 0
            assert store.read.call_count == 1
            assert orchestrator._audit_health.suspended_count == 1
            assert orchestrator._audit_health.suspended_project_ids == (
                "project-a",
            )
            assert orchestrator._audit_health.pending_count == 0
            assert orchestrator._audit_health.stale_pending_count == 0
            assert orchestrator._audit_health.degraded is False
            assert not orchestrator._alerts
            assert orchestrator._prepare_audit_selector.await_count == 0
            assert orchestrator._dispatch.await_count == 0

            project.paused = False
            deferred = await orchestrator._dispatch_audit_lane(
                allow_new_launches=False
            )

            assert deferred["audit_dispatch"] >= 0
            assert orchestrator._prepare_audit_selector.await_count == 1
            assert orchestrator._dispatch.await_count == 0
            assert update_record.call_count == 0
            assert orchestrator._audit_health.pending_count == 1
            assert (
                orchestrator._audit_metrics[
                    "restart_publication_deferred_count"
                ]
                == 1
            )

            result = await orchestrator._dispatch_audit_lane()

            assert orchestrator._prepare_audit_selector.await_count == 2
            assert orchestrator._dispatch.await_count == 1

        assert result["audit_dispatch"] >= 0
        assert launch_state["completed"] is True
        assert orchestrator._audit_metrics["last_dispatched_count"] == 1
        assert orchestrator._audit_metrics["restart_publication_deferred_count"] == 0
        assert update_record.call_count == 1
        persisted = update_record.call_args.args[2]
        assert persisted.request_state == RequestState.IN_PROGRESS
        assert orchestrator._audit_health.pending_count == 0
        assert orchestrator._audit_health.in_progress_count == 1
        assert orchestrator._audit_health.oldest_pending_at is None
        assert orchestrator._audit_health.oldest_pending_age_seconds is None
        assert orchestrator._audit_health.stale_pending_count == 0
        assert not [
            alert
            for alert in orchestrator._alerts
            if alert.get("source") == HEALTH_ALERT_PREFIX + "backlog_age"
        ]
    finally:
        orchestrator._tick_pool.shutdown(wait=True, cancel_futures=True)
        orchestrator._refresh_pool.shutdown(wait=True, cancel_futures=True)


@pytest.mark.asyncio
async def test_audit_scan_limit_cannot_publish_complete_partial_facts(
    tmp_path: Path,
) -> None:
    """Candidates beyond the lane limit keep last-complete health authoritative."""
    project_store = MagicMock()
    project_store.list_all.return_value = []
    orchestrator = Orchestrator(
        ServiceConfig(
            workspace_root=str(tmp_path / "workspace"),
            audit_lane_scan_limit=1,
            duplicate_preflight_max_agents=0,
        ),
        str(tmp_path / "WORKFLOW.md"),
        project_store=project_store,
        state_path=str(tmp_path / "service_state.json"),
    )
    candidates = tuple(
        Issue(
            id=f"issue-{index}",
            identifier=f"TASK-{index}",
            title=f"Audit candidate {index}",
            state="In Validation",
            project_id="project-a",
            created_at=datetime.now(timezone.utc),
        )
        for index in range(2)
    )
    store = MagicMock()
    store.read.return_value = SimpleNamespace(
        pending_chain=[],
        is_quarantined=False,
        unknown_fields={},
    )
    try:
        orchestrator._refresh_terminal_audit_health(
            [_aged_pending_observation()],
            scan_complete=True,
            scan_error_count=0,
        )
        with (
            patch.object(orchestrator, "_available_slots", return_value=1),
            patch.object(
                orchestrator,
                "_dispatch_is_blocked",
                return_value=False,
            ),
            patch.object(
                orchestrator,
                "_fetch_audit_candidates",
                return_value=_AuditCandidateScan(candidates),
            ),
            patch.object(orchestrator, "_audit_store", return_value=store),
        ):
            await orchestrator._dispatch_audit_lane()

        health = orchestrator._audit_health
        assert orchestrator._audit_metrics["discovered_candidate_count"] == 2
        assert orchestrator._audit_metrics["scanned_candidate_count"] == 1
        assert orchestrator._audit_metrics["candidate_scan_complete"] is False
        assert orchestrator._audit_metrics["pending_count"] == 1
        assert health.pending_count == 1
        assert health.stale_pending_count == 1
        assert health.oldest_pending_age_seconds is not None
        assert health.scan_complete is False
        assert health.scan_error_count == 0
        sources = {str(alert.get("source", "")) for alert in orchestrator._alerts}
        assert HEALTH_ALERT_PREFIX + "backlog_age" in sources
        assert HEALTH_ALERT_PREFIX + "scan" in sources
    finally:
        orchestrator._tick_pool.shutdown(wait=True, cancel_futures=True)
        orchestrator._refresh_pool.shutdown(wait=True, cancel_futures=True)


def test_audit_scan_cursor_rotates_durably_across_restart(tmp_path: Path) -> None:
    """A bounded audit window cannot pin candidates behind its first page."""

    state_path = tmp_path / "service_state.json"
    project_store = MagicMock()
    project_store.list_all.return_value = []
    config = ServiceConfig(
        workspace_root=str(tmp_path / "workspace"),
        audit_lane_scan_limit=2,
        duplicate_preflight_max_agents=0,
    )
    candidates = tuple(
        Issue(
            id=f"issue-{index}",
            identifier=f"TASK-{index}",
            title=f"Audit candidate {index}",
            state="In Validation",
            project_id="project-a",
            created_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
        )
        for index in range(5)
    )
    first = Orchestrator(
        config,
        str(tmp_path / "WORKFLOW.md"),
        project_store=project_store,
        state_path=str(state_path),
    )
    try:
        first_window, truncated = first._audit_candidate_window(candidates)
        assert truncated
        assert [issue.identifier for issue in first_window] == ["TASK-0", "TASK-1"]
        first._set_maintenance_cursor(
            "audit_lane",
            first._audit_candidate_cursor_key(first_window[-1]),
        )
    finally:
        first._tick_pool.shutdown(wait=True, cancel_futures=True)
        first._refresh_pool.shutdown(wait=True, cancel_futures=True)

    restarted = Orchestrator(
        config,
        str(tmp_path / "WORKFLOW.md"),
        project_store=project_store,
        state_path=str(state_path),
    )
    try:
        second_window, truncated = restarted._audit_candidate_window(candidates)
        assert truncated
        assert [issue.identifier for issue in second_window] == [
            "TASK-2",
            "TASK-3",
        ]
    finally:
        restarted._tick_pool.shutdown(wait=True, cancel_futures=True)
        restarted._refresh_pool.shutdown(wait=True, cancel_futures=True)


def test_mixed_priority_health_cursor_rotates_durably_across_restart(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "service_state.json"
    project_store = MagicMock()
    project_store.list_all.return_value = []
    config = ServiceConfig(
        workspace_root=str(tmp_path / "workspace"),
        audit_lane_scan_limit=8,
        duplicate_preflight_max_agents=0,
    )
    created_at = datetime(2026, 8, 4, tzinfo=timezone.utc)
    high_priority = tuple(
        Issue(
            id=f"high-{index}",
            identifier=f"HIGH-{index}",
            title="High priority",
            state="In Validation",
            project_id="project-a",
            priority=100,
            created_at=created_at + timedelta(seconds=index),
        )
        for index in range(8)
    )
    low_priority = Issue(
        id="low-0",
        identifier="LOW-0",
        title="Low priority",
        state="In Validation",
        project_id="project-a",
        priority=0,
        created_at=created_at + timedelta(seconds=8),
    )
    candidates = high_priority + (low_priority,)
    first = Orchestrator(
        config,
        str(tmp_path / "WORKFLOW.md"),
        project_store=project_store,
        state_path=str(state_path),
    )
    try:
        first_window, truncated = first._audit_health_candidate_window(candidates)
        assert truncated is True
        assert [issue.identifier for issue in first_window] == [
            f"HIGH-{index}" for index in range(8)
        ]
        first._set_maintenance_cursor(
            "audit_lane",
            first._audit_candidate_cursor_key(first_window[-1]),
        )
    finally:
        first._tick_pool.shutdown(wait=True, cancel_futures=True)
        first._refresh_pool.shutdown(wait=True, cancel_futures=True)

    restarted = Orchestrator(
        config,
        str(tmp_path / "WORKFLOW.md"),
        project_store=project_store,
        state_path=str(state_path),
    )
    try:
        second_window, truncated = restarted._audit_health_candidate_window(
            candidates
        )
        assert truncated is True
        assert second_window[0].identifier == "LOW-0"
        assert [issue.identifier for issue in second_window[1:]] == [
            f"HIGH-{index}" for index in range(7)
        ]
    finally:
        restarted._tick_pool.shutdown(wait=True, cancel_futures=True)
        restarted._refresh_pool.shutdown(wait=True, cancel_futures=True)


def test_exact_successor_wake_enters_next_bounded_audit_window(
    tmp_path: Path,
) -> None:
    project_store = MagicMock()
    project_store.list_all.return_value = []
    orchestrator = Orchestrator(
        ServiceConfig(
            workspace_root=str(tmp_path / "workspace"),
            audit_lane_scan_limit=2,
            duplicate_preflight_max_agents=0,
        ),
        str(tmp_path / "WORKFLOW.md"),
        project_store=project_store,
        state_path=str(tmp_path / "service_state.json"),
    )
    candidates = tuple(
        Issue(
            id=f"issue-{index}",
            identifier=f"TASK-{index}",
            title="Pending audit",
            state="In Validation",
            project_id="project-a",
            priority=0,
            created_at=datetime(2026, 8, 11, tzinfo=timezone.utc)
            + timedelta(seconds=index),
        )
        for index in range(4)
    )
    try:
        orchestrator._eligible_audit_stage_wakes[(
            "project-a",
            "TASK-3",
        )] = "audit-merged"

        window, truncated = orchestrator._audit_health_candidate_window(
            candidates
        )

        assert truncated is True
        assert [issue.identifier for issue in window] == ["TASK-3", "TASK-0"]
    finally:
        orchestrator._tick_pool.shutdown(wait=True, cancel_futures=True)
        orchestrator._refresh_pool.shutdown(wait=True, cancel_futures=True)


def test_exact_successor_preserves_active_priority_but_bypasses_suspension(
    tmp_path: Path,
) -> None:
    """Exact hints cannot repeatedly jump ahead of a real active blocker."""

    project_store = MagicMock()
    project_store.list_all.return_value = []
    orchestrator = Orchestrator(
        ServiceConfig(
            workspace_root=str(tmp_path / "workspace"),
            audit_lane_scan_limit=4,
            duplicate_preflight_max_agents=0,
        ),
        str(tmp_path / "WORKFLOW.md"),
        project_store=project_store,
        state_path=str(tmp_path / "service_state.json"),
    )
    created_at = datetime(2026, 8, 11, tzinfo=timezone.utc)
    active_high = Issue(
        id="active-high",
        identifier="ACTIVE-HIGH",
        title="Already-running higher-priority audit",
        state="In Validation",
        project_id="active",
        priority=100,
        created_at=created_at,
    )
    suspended_high = replace(
        active_high,
        id="suspended-high",
        identifier="SUSPENDED-HIGH",
        project_id="paused",
    )
    exact = Issue(
        id="exact-low",
        identifier="EXACT-LOW",
        title="Exact successor",
        state="In Validation",
        project_id="active",
        priority=1,
        created_at=created_at + timedelta(seconds=1),
    )
    lower = replace(
        exact,
        id="ordinary-low",
        identifier="ORDINARY-LOW",
        priority=0,
    )
    candidates = (suspended_high, active_high, exact, lower)
    suspension = {
        orchestrator._audit_candidate_cursor_key(suspended_high): True,
        orchestrator._audit_candidate_cursor_key(active_high): False,
        orchestrator._audit_candidate_cursor_key(exact): False,
        orchestrator._audit_candidate_cursor_key(lower): False,
    }
    try:
        orchestrator._record_terminal_audit_stage_wake(
            project_id="active",
            task_id="EXACT-LOW",
            audit_id="audit-exact",
        )

        window, truncated = orchestrator._audit_health_candidate_window(
            candidates,
            candidate_suspension=suspension,
        )

        assert truncated is False
        assert [issue.identifier for issue in window] == [
            "ACTIVE-HIGH",
            "EXACT-LOW",
            "SUSPENDED-HIGH",
            "ORDINARY-LOW",
        ]
    finally:
        orchestrator._tick_pool.shutdown(wait=True, cancel_futures=True)
        orchestrator._refresh_pool.shutdown(wait=True, cancel_futures=True)


@pytest.mark.asyncio
async def test_dedicated_scan_retires_stale_exact_successor_hint(
    tmp_path: Path,
) -> None:
    project_store = MagicMock()
    project_store.list_all.return_value = []
    orchestrator = Orchestrator(
        ServiceConfig(
            workspace_root=str(tmp_path / "workspace"),
            duplicate_preflight_max_agents=0,
        ),
        str(tmp_path / "WORKFLOW.md"),
        project_store=project_store,
        state_path=str(tmp_path / "service_state.json"),
    )
    issue = Issue(
        id="issue-stale",
        identifier="TASK-STALE",
        title="Retired successor",
        state="In Validation",
        project_id="project-a",
    )
    store = MagicMock()
    store.read.return_value = SimpleNamespace(
        pending_chain=[],
        is_quarantined=False,
        unknown_fields={},
    )
    orchestrator._eligible_audit_stage_wakes[(
        "project-a",
        "TASK-STALE",
    )] = "audit-retired"
    try:
        with (
            patch.object(orchestrator, "_available_slots", return_value=1),
            patch.object(orchestrator, "_dispatch_is_blocked", return_value=False),
            patch.object(orchestrator, "_is_project_paused", return_value=False),
            patch.object(
                orchestrator,
                "_fetch_audit_candidates",
                return_value=_AuditCandidateScan((issue,)),
            ),
            patch.object(orchestrator, "_audit_store", return_value=store),
        ):
            await orchestrator._dispatch_audit_lane()

        assert orchestrator._eligible_audit_stage_wakes == {}
    finally:
        orchestrator._tick_pool.shutdown(wait=True, cancel_futures=True)
        orchestrator._refresh_pool.shutdown(wait=True, cancel_futures=True)


@pytest.mark.asyncio
async def test_complete_empty_scan_retires_authoritatively_absent_exact_wake(
    tmp_path: Path,
) -> None:
    project_store = MagicMock()
    project_store.list_all.return_value = []
    orchestrator = Orchestrator(
        ServiceConfig(
            workspace_root=str(tmp_path / "workspace"),
            duplicate_preflight_max_agents=0,
        ),
        str(tmp_path / "WORKFLOW.md"),
        project_store=project_store,
        state_path=str(tmp_path / "service_state.json"),
    )
    orchestrator._record_terminal_audit_stage_wake(
        project_id="project-a",
        task_id="TASK-ABSENT",
        audit_id="audit-absent",
    )
    authority = MagicMock(
        return_value=(None, TerminalAuditMetadata.empty())
    )
    try:
        with (
            patch.object(orchestrator, "_available_slots", return_value=1),
            patch.object(orchestrator, "_dispatch_is_blocked", return_value=False),
            patch.object(
                orchestrator,
                "_fetch_audit_candidates",
                return_value=_AuditCandidateScan(()),
            ),
            patch.object(
                orchestrator,
                "_read_absent_terminal_audit_wake_authority",
                authority,
            ),
        ):
            await orchestrator._dispatch_audit_lane()

        assert orchestrator._terminal_audit_stage_wakes_snapshot() == {}
        assert orchestrator._audit_metrics["continuation_pending_exact_count"] == 0
        assert orchestrator._audit_metrics[
            "continuation_absent_retirement_count"
        ] == 1
        authority.assert_called_once_with("project-a", "TASK-ABSENT")
    finally:
        orchestrator._tick_pool.shutdown(wait=True, cancel_futures=True)
        orchestrator._refresh_pool.shutdown(wait=True, cancel_futures=True)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "proof_mode",
    ["incomplete", "error", "quarantined", "still_eligible"],
)
async def test_absent_exact_wake_survives_incomplete_or_unusable_proof(
    tmp_path: Path,
    proof_mode: str,
) -> None:
    project_store = MagicMock()
    project_store.list_all.return_value = []
    orchestrator = Orchestrator(
        ServiceConfig(
            workspace_root=str(tmp_path / "workspace"),
            duplicate_preflight_max_agents=0,
        ),
        str(tmp_path / "WORKFLOW.md"),
        project_store=project_store,
        state_path=str(tmp_path / "service_state.json"),
    )
    orchestrator._record_terminal_audit_stage_wake(
        project_id="project-a",
        task_id="TASK-RETAIN",
        audit_id="audit-retain",
    )
    eligible_record = TerminalAuditRecord(
        audit_id="audit-retain",
        project_id="project-a",
        task_id="TASK-RETAIN",
        target_state=TargetState.DONE,
        evidence_fingerprint=EvidenceFingerprint("e" * 64),
        request_state=RequestState.PENDING,
        eligible_at="2026-08-11T13:00:00+00:00",
    )
    proof = {
        "incomplete": (None, TerminalAuditMetadata.empty()),
        "error": (None, TerminalAuditMetadata.empty()),
        "quarantined": (
            None,
            TerminalAuditMetadata(
                quarantine=MetadataQuarantine("f" * 64),
            ),
        ),
        "still_eligible": (
            Issue(
                id="retain",
                identifier="TASK-RETAIN",
                title="Still eligible",
                state="In Validation",
                project_id="project-a",
            ),
            TerminalAuditMetadata(pending_chain=[eligible_record]),
        ),
    }[proof_mode]
    authority = MagicMock(return_value=proof)
    if proof_mode == "error":
        authority.side_effect = RuntimeError("tracker unavailable")
    scan = _AuditCandidateScan(
        (),
        scan_error_count=1 if proof_mode == "incomplete" else 0,
    )
    try:
        with (
            patch.object(orchestrator, "_available_slots", return_value=1),
            patch.object(orchestrator, "_dispatch_is_blocked", return_value=False),
            patch.object(
                orchestrator,
                "_fetch_audit_candidates",
                return_value=scan,
            ),
            patch.object(
                orchestrator,
                "_read_absent_terminal_audit_wake_authority",
                authority,
            ),
        ):
            await orchestrator._dispatch_audit_lane()

        assert orchestrator._terminal_audit_stage_wakes_snapshot() == {
            ("project-a", "TASK-RETAIN"): "audit-retain"
        }
        if proof_mode != "incomplete":
            authority.assert_called_once_with("project-a", "TASK-RETAIN")
        else:
            authority.assert_not_called()
        if proof_mode in {"error", "quarantined"}:
            assert orchestrator._audit_metrics[
                "continuation_absent_recheck_error_count"
            ] == 1
    finally:
        orchestrator._tick_pool.shutdown(wait=True, cancel_futures=True)
        orchestrator._refresh_pool.shutdown(wait=True, cancel_futures=True)


@pytest.mark.asyncio
async def test_absent_scan_value_cas_preserves_newer_exact_wake(
    tmp_path: Path,
) -> None:
    project_store = MagicMock()
    project_store.list_all.return_value = []
    orchestrator = Orchestrator(
        ServiceConfig(
            workspace_root=str(tmp_path / "workspace"),
            duplicate_preflight_max_agents=0,
        ),
        str(tmp_path / "WORKFLOW.md"),
        project_store=project_store,
        state_path=str(tmp_path / "service_state.json"),
    )
    orchestrator._record_terminal_audit_stage_wake(
        project_id="project-a",
        task_id="TASK-RACE",
        audit_id="audit-old",
    )
    proof_started = threading.Event()
    release_proof = threading.Event()

    def _blocked_authority(_project_id: str, _task_id: str):
        proof_started.set()
        assert release_proof.wait(timeout=1)
        return None, TerminalAuditMetadata.empty()

    try:
        with patch.object(
            orchestrator,
            "_read_absent_terminal_audit_wake_authority",
            side_effect=_blocked_authority,
        ):
            reconcile = asyncio.create_task(
                orchestrator._reconcile_absent_terminal_audit_wakes(
                    _AuditCandidateScan(()),
                    deadline=asyncio.get_running_loop().time() + 2,
                )
            )
            assert await asyncio.to_thread(proof_started.wait, 1)
            orchestrator._record_terminal_audit_stage_wake(
                project_id="project-a",
                task_id="TASK-RACE",
                audit_id="audit-new",
            )
            release_proof.set()
            result = await asyncio.wait_for(reconcile, timeout=1)

        assert result["retired"] == 0
        assert orchestrator._terminal_audit_stage_wakes_snapshot() == {
            ("project-a", "TASK-RACE"): "audit-new"
        }
        assert orchestrator._audit_metrics["continuation_pending_exact_count"] == 1
    finally:
        release_proof.set()
        orchestrator._tick_pool.shutdown(wait=True, cancel_futures=True)
        orchestrator._refresh_pool.shutdown(wait=True, cancel_futures=True)


def test_audit_candidate_window_interleaves_projects_within_priority(
    tmp_path: Path,
) -> None:
    project_store = MagicMock()
    project_store.list_all.return_value = []
    orchestrator = Orchestrator(
        ServiceConfig(
            workspace_root=str(tmp_path / "workspace"),
            audit_lane_scan_limit=4,
            duplicate_preflight_max_agents=0,
        ),
        str(tmp_path / "WORKFLOW.md"),
        project_store=project_store,
        state_path=str(tmp_path / "service_state.json"),
    )
    created_at = datetime(2026, 8, 4, tzinfo=timezone.utc)
    candidates = tuple(
        Issue(
            id=f"{project_id}-{index}",
            identifier=f"{project_id.upper()}-{index}",
            title="Audit candidate",
            state="In Validation",
            project_id=project_id,
            priority=100,
            created_at=created_at + timedelta(seconds=index),
        )
        for project_id in ("project-a", "project-b")
        for index in range(3)
    )
    try:
        window, truncated = orchestrator._audit_candidate_window(candidates)
        assert truncated is True
        assert [issue.project_id for issue in window] == [
            "project-a",
            "project-b",
            "project-a",
            "project-b",
        ]
    finally:
        orchestrator._tick_pool.shutdown(wait=True, cancel_futures=True)
        orchestrator._refresh_pool.shutdown(wait=True, cancel_futures=True)


@pytest.mark.asyncio
async def test_dispatch_ineligible_observations_do_not_spend_operation_budget(
    tmp_path: Path,
) -> None:
    project_store = MagicMock()
    project_store.list_all.return_value = []
    orchestrator = Orchestrator(
        ServiceConfig(
            workspace_root=str(tmp_path / "workspace"),
            audit_lane_scan_limit=32,
            audit_lane_operation_limit=2,
            audit_lane_max_runtime_seconds=30,
            duplicate_preflight_max_agents=0,
        ),
        str(tmp_path / "WORKFLOW.md"),
        project_store=project_store,
        state_path=str(tmp_path / "service_state.json"),
    )
    candidates = tuple(
        Issue(
            id=f"issue-{index}",
            identifier=f"TASK-{index}",
            title="Audit candidate",
            state="In Validation",
            project_id="project-a",
            created_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
        )
        for index in range(5)
    )
    reads: list[str] = []
    store = MagicMock()

    def _read(identifier: str):
        reads.append(identifier)
        return SimpleNamespace(
            pending_chain=[],
            is_quarantined=False,
            unknown_fields={},
        )

    store.read.side_effect = _read
    try:
        with (
            patch.object(orchestrator, "_available_slots", return_value=1),
            patch.object(orchestrator, "_dispatch_is_blocked", return_value=False),
            patch.object(orchestrator, "_is_project_paused", return_value=False),
            patch.object(
                orchestrator,
                "_fetch_audit_candidates",
                return_value=_AuditCandidateScan(candidates),
            ),
            patch.object(orchestrator, "_audit_store", return_value=store),
            patch.object(
                orchestrator,
                "_request_audit_lane_continuation",
                return_value=True,
            ) as continuation,
        ):
            await orchestrator._dispatch_audit_lane()

        assert reads == [
            "TASK-0",
            "TASK-1",
            "TASK-2",
            "TASK-3",
            "TASK-4",
        ]
        assert continuation.call_count == 0
        assert orchestrator._audit_metrics["active_operation_count"] == 0
        assert orchestrator._audit_metrics["scanned_candidate_count"] == 5
        assert orchestrator._audit_health.scan_complete is True
        assert orchestrator._audit_metrics["candidate_scan_complete"] is True
        assert orchestrator._audit_metrics["health_cycle_candidate_count"] == 5
    finally:
        orchestrator._tick_pool.shutdown(wait=True, cancel_futures=True)
        orchestrator._refresh_pool.shutdown(wait=True, cancel_futures=True)


@pytest.mark.asyncio
async def test_ineligible_high_priority_observations_do_not_defer_lower_health(
    tmp_path: Path,
) -> None:
    project_store = MagicMock()
    project_store.list_all.return_value = []
    orchestrator = Orchestrator(
        ServiceConfig(
            workspace_root=str(tmp_path / "workspace"),
            audit_lane_scan_limit=32,
            audit_lane_operation_limit=8,
            audit_lane_max_runtime_seconds=30,
            duplicate_preflight_max_agents=0,
        ),
        str(tmp_path / "WORKFLOW.md"),
        project_store=project_store,
        state_path=str(tmp_path / "service_state.json"),
    )
    created_at = datetime(2026, 8, 4, tzinfo=timezone.utc)
    high_priority = tuple(
        Issue(
            id=f"high-{index}",
            identifier=f"HIGH-{index}",
            title="High-priority audit candidate",
            state="In Validation",
            project_id="project-a",
            priority=100,
            created_at=created_at + timedelta(seconds=index),
        )
        for index in range(8)
    )
    low_priority = Issue(
        id="low-0",
        identifier="LOW-0",
        title="Lower-priority audit candidate",
        state="In Validation",
        project_id="project-a",
        priority=0,
        created_at=created_at + timedelta(seconds=8),
    )
    candidates = high_priority + (low_priority,)
    reads: list[str] = []
    store = MagicMock()

    def _read(identifier: str):
        reads.append(identifier)
        return SimpleNamespace(
            pending_chain=[],
            is_quarantined=False,
            unknown_fields={},
        )

    store.read.side_effect = _read
    try:
        with (
            patch.object(orchestrator, "_available_slots", return_value=1),
            patch.object(orchestrator, "_dispatch_is_blocked", return_value=False),
            patch.object(orchestrator, "_is_project_paused", return_value=False),
            patch.object(
                orchestrator,
                "_fetch_audit_candidates",
                return_value=_AuditCandidateScan(candidates),
            ),
            patch.object(orchestrator, "_audit_store", return_value=store),
            patch.object(
                orchestrator,
                "_request_audit_lane_continuation",
                return_value=True,
            ) as continuation,
        ):
            await orchestrator._dispatch_audit_lane()

        assert reads == [f"HIGH-{index}" for index in range(8)] + ["LOW-0"]
        assert orchestrator._audit_health.scan_complete is True
        assert orchestrator._audit_health.scan_error_count == 0
        assert orchestrator._audit_metrics["candidate_scan_complete"] is True
        assert orchestrator._audit_metrics["active_operation_count"] == 0
        assert orchestrator._audit_metrics["priority_revisit"] is False
        continuation.assert_not_called()
        assert not any(
            str(alert.get("source", "")).endswith("action_required")
            for alert in orchestrator._alerts
        )
    finally:
        orchestrator._tick_pool.shutdown(wait=True, cancel_futures=True)
        orchestrator._refresh_pool.shutdown(wait=True, cancel_futures=True)


@pytest.mark.asyncio
async def test_paused_candidates_above_operation_limit_cannot_starve_active_audit(
    tmp_path: Path,
) -> None:
    """The live 9-suspended-plus-1-active shape launches in one lane cut."""

    project_store = MagicMock()
    project_store.list_all.return_value = []
    projects = {
        f"paused-{index}": SimpleNamespace(
            id=f"paused-{index}",
            paused=True,
        )
        for index in range(9)
    }
    projects["active"] = SimpleNamespace(id="active", paused=False)
    project_store.list_all.return_value = list(projects.values())
    project_store.get.side_effect = projects.get
    orchestrator = Orchestrator(
        ServiceConfig(
            workspace_root=str(tmp_path / "workspace"),
            audit_lane_scan_limit=32,
            audit_lane_operation_limit=8,
            audit_lane_dispatch_limit=1,
            audit_lane_max_runtime_seconds=30,
            duplicate_preflight_max_agents=0,
        ),
        str(tmp_path / "WORKFLOW.md"),
        project_store=project_store,
        state_path=str(tmp_path / "service_state.json"),
    )
    created_at = datetime(2026, 8, 11, tzinfo=timezone.utc)
    paused = tuple(
        Issue(
            id=f"paused-{index}",
            identifier=f"PAUSED-{index}",
            title="Suspended terminal audit",
            state="In Validation",
            project_id=f"paused-{index}",
            priority=100,
            branch_name=f"paused-{index}",
            created_at=created_at + timedelta(seconds=index),
        )
        for index in range(9)
    )
    active = Issue(
        id="active",
        identifier="ACTIVE-0",
        title="Active terminal audit",
        state="In Validation",
        project_id="active",
        priority=0,
        branch_name="active-0",
        created_at=created_at + timedelta(seconds=9),
    )
    candidates = paused + (active,)
    records = {
        issue.identifier: TerminalAuditRecord(
            audit_id=f"audit-{issue.identifier.lower()}",
            project_id=str(issue.project_id),
            task_id=issue.identifier,
            target_state=TargetState.DONE,
            evidence_fingerprint=EvidenceFingerprint(
                f"{index + 1:064x}"
            ),
            request_state=RequestState.PENDING,
            created_at=created_at.isoformat(),
        )
        for index, issue in enumerate(candidates)
    }
    store = MagicMock()
    store.read.side_effect = lambda identifier: SimpleNamespace(
        pending_chain=[records[identifier]],
        is_quarantined=False,
        unknown_fields={},
    )
    selector = MagicMock()
    selector.select_candidates.return_value = (
        [Candidate(provider_id="provider-a", model="model-a")],
        None,
    )
    tracker = MagicMock()
    tracker.get_metadata.return_value = {}
    launches: list[str] = []

    async def _dispatch(issue: Issue, **_kwargs) -> bool:
        launches.append(issue.identifier)
        return True

    try:
        with (
            patch.object(
                orchestrator,
                "_available_slots",
                side_effect=lambda: 0 if launches else 1,
            ),
            patch.object(orchestrator, "_dispatch_is_blocked", return_value=False),
            patch.object(
                orchestrator,
                "_fetch_audit_candidates",
                return_value=_AuditCandidateScan(candidates),
            ),
            patch.object(orchestrator, "_audit_store", return_value=store),
            patch.object(
                orchestrator,
                "_bind_audit_record_revision",
                side_effect=lambda _issue, record: record,
            ),
            patch.object(
                orchestrator,
                "_prepare_audit_selector",
                new=AsyncMock(return_value=(selector, None)),
            ),
            patch.object(
                orchestrator,
                "_terminal_audit_validation_configuration_error",
                return_value=None,
            ),
            patch.object(orchestrator, "_audit_branch_busy", return_value=False),
            patch.object(orchestrator, "_tracker_for_issue", return_value=tracker),
            patch.object(orchestrator, "_audit_update_record", return_value=True),
            patch.object(
                orchestrator,
                "_claim_terminal_audit_attempt",
                new=AsyncMock(
                    return_value=SimpleNamespace(
                        job_id=1,
                        lease_token="lease-active",
                    )
                ),
            ),
            patch.object(
                orchestrator,
                "_dispatch",
                new=AsyncMock(side_effect=_dispatch),
            ),
            patch.object(
                orchestrator,
                "_request_audit_lane_continuation",
                return_value=True,
            ) as continuation,
        ):
            await orchestrator._dispatch_audit_lane()
            await orchestrator._dispatch_audit_lane()

        assert launches == ["ACTIVE-0"]
        assert orchestrator._audit_metrics["active_operation_count"] == 1
        assert orchestrator._audit_metrics["active_operation_count"] <= 8
        assert orchestrator._audit_metrics["scanned_candidate_count"] == 10
        assert orchestrator._audit_metrics["candidate_scan_complete"] is True
        assert orchestrator._audit_health.suspended_count == 9
        assert orchestrator._audit_health.suspended_project_ids == tuple(
            f"paused-{index}" for index in range(9)
        )
        assert orchestrator._audit_metrics["runtime_overrun_ms"] == 0
        continuation.assert_not_called()
    finally:
        orchestrator._tick_pool.shutdown(wait=True, cancel_futures=True)
        orchestrator._refresh_pool.shutdown(wait=True, cancel_futures=True)


@pytest.mark.asyncio
async def test_live_exact_successor_dispatches_after_ineligible_priority_observation(
    tmp_path: Path,
) -> None:
    """Reproduce the OOMPAH-1085 continuation eligibility storm shape."""

    project = SimpleNamespace(id="active", paused=False)
    project_store = MagicMock()
    project_store.list_all.return_value = [project]
    project_store.get.return_value = project
    orchestrator = Orchestrator(
        ServiceConfig(
            workspace_root=str(tmp_path / "workspace"),
            audit_lane_scan_limit=32,
            audit_lane_operation_limit=8,
            audit_lane_dispatch_limit=1,
            audit_lane_max_runtime_seconds=30,
            duplicate_preflight_max_agents=0,
        ),
        str(tmp_path / "WORKFLOW.md"),
        project_store=project_store,
        state_path=str(tmp_path / "service_state.json"),
    )
    created_at = datetime(2026, 8, 11, tzinfo=timezone.utc)
    higher_ineligible = Issue(
        id="higher-ineligible",
        identifier="HIGHER-INELIGIBLE",
        title="Higher-priority observation has no launchable audit",
        state="In Validation",
        project_id="active",
        priority=100,
        branch_name="higher-ineligible",
        created_at=created_at,
    )
    exact = Issue(
        id="exact-successor",
        identifier="EXACT-SUCCESSOR",
        title="Lower-priority exact successor",
        state="In Validation",
        project_id="active",
        priority=1,
        branch_name="exact-successor",
        created_at=created_at + timedelta(seconds=1),
    )
    record = TerminalAuditRecord(
        audit_id="audit-exact",
        project_id="active",
        task_id=exact.identifier,
        target_state=TargetState.DONE,
        evidence_fingerprint=EvidenceFingerprint("a" * 64),
        request_state=RequestState.PENDING,
        created_at=created_at.isoformat(),
        eligible_at=created_at.isoformat(),
    )
    store = MagicMock()
    store.read.side_effect = lambda identifier: SimpleNamespace(
        pending_chain=[record] if identifier == exact.identifier else [],
        is_quarantined=False,
        unknown_fields={},
    )
    selector = MagicMock()
    selector.select_candidates.return_value = (
        [Candidate(provider_id="provider-a", model="model-a")],
        None,
    )
    tracker = MagicMock()
    tracker.get_metadata.return_value = {}
    launches: list[str] = []

    async def _dispatch(issue: Issue, **_kwargs) -> bool:
        launches.append(issue.identifier)
        return True

    try:
        orchestrator._record_terminal_audit_stage_wake(
            project_id="active",
            task_id=exact.identifier,
            audit_id=record.audit_id,
        )
        with (
            patch.object(
                orchestrator,
                "_available_slots",
                side_effect=lambda: 0 if launches else 1,
            ),
            patch.object(orchestrator, "_dispatch_is_blocked", return_value=False),
            patch.object(orchestrator, "_is_project_paused", return_value=False),
            patch.object(
                orchestrator,
                "_fetch_audit_candidates",
                return_value=_AuditCandidateScan((exact, higher_ineligible)),
            ),
            patch.object(orchestrator, "_audit_store", return_value=store),
            patch.object(
                orchestrator,
                "_bind_audit_record_revision",
                side_effect=lambda _issue, pending: pending,
            ),
            patch.object(
                orchestrator,
                "_prepare_audit_selector",
                new=AsyncMock(return_value=(selector, None)),
            ),
            patch.object(
                orchestrator,
                "_terminal_audit_validation_configuration_error",
                return_value=None,
            ),
            patch.object(orchestrator, "_audit_branch_busy", return_value=False),
            patch.object(orchestrator, "_tracker_for_issue", return_value=tracker),
            patch.object(orchestrator, "_audit_update_record", return_value=True),
            patch.object(
                orchestrator,
                "_claim_terminal_audit_attempt",
                new=AsyncMock(
                    return_value=SimpleNamespace(
                        job_id=1,
                        lease_token="lease-exact",
                    )
                ),
            ),
            patch.object(
                orchestrator,
                "_dispatch",
                new=AsyncMock(side_effect=_dispatch),
            ),
            patch.object(
                orchestrator,
                "_request_audit_lane_continuation",
                return_value=True,
            ) as continuation,
        ):
            await orchestrator._dispatch_audit_lane()

        assert launches == ["EXACT-SUCCESSOR"]
        assert orchestrator._terminal_audit_stage_wakes_snapshot() == {}
        assert orchestrator._audit_metrics["scanned_candidate_count"] == 2
        assert orchestrator._audit_metrics["priority_revisit"] is False
        continuation.assert_not_called()
    finally:
        orchestrator._tick_pool.shutdown(wait=True, cancel_futures=True)
        orchestrator._refresh_pool.shutdown(wait=True, cancel_futures=True)


@pytest.mark.asyncio
async def test_audit_health_rotation_resets_when_candidate_corpus_changes(
    tmp_path: Path,
) -> None:
    project_store = MagicMock()
    project_store.list_all.return_value = []
    orchestrator = Orchestrator(
        ServiceConfig(
            workspace_root=str(tmp_path / "workspace"),
            audit_lane_scan_limit=32,
            audit_lane_operation_limit=2,
            audit_lane_max_runtime_seconds=30,
            duplicate_preflight_max_agents=0,
        ),
        str(tmp_path / "WORKFLOW.md"),
        project_store=project_store,
        state_path=str(tmp_path / "service_state.json"),
    )
    created_at = datetime(2026, 8, 4, tzinfo=timezone.utc)

    def _issue(identifier: str) -> Issue:
        return Issue(
            id=identifier.lower(),
            identifier=identifier,
            title="Audit candidate",
            state="In Validation",
            project_id="project-a",
            priority=100,
            created_at=created_at,
        )

    first_corpus = tuple(
        _issue(identifier) for identifier in ("TASK-A", "TASK-B", "TASK-C")
    )
    changed_corpus = tuple(
        _issue(identifier) for identifier in ("TASK-B", "TASK-C", "TASK-D")
    )
    current_corpus = {"value": first_corpus}
    reads: list[str] = []
    store = MagicMock()

    def _read(identifier: str):
        reads.append(identifier)
        return SimpleNamespace(
            pending_chain=[],
            is_quarantined=False,
            unknown_fields={},
        )

    store.read.side_effect = _read
    try:
        with (
            patch.object(orchestrator, "_available_slots", return_value=1),
            patch.object(orchestrator, "_dispatch_is_blocked", return_value=False),
            patch.object(orchestrator, "_is_project_paused", return_value=False),
            patch.object(
                orchestrator,
                "_fetch_audit_candidates",
                side_effect=lambda: _AuditCandidateScan(current_corpus["value"]),
            ),
            patch.object(orchestrator, "_audit_store", return_value=store),
            patch.object(
                orchestrator,
                "_request_audit_lane_continuation",
                return_value=True,
            ),
        ):
            await orchestrator._dispatch_audit_lane()
            assert orchestrator._audit_metrics["health_cycle_seen_count"] == 3

            current_corpus["value"] = changed_corpus
            await orchestrator._dispatch_audit_lane()
            assert orchestrator._audit_health.scan_complete is True
            assert orchestrator._audit_metrics["health_cycle_seen_count"] == 3

            await orchestrator._dispatch_audit_lane()

        assert reads == [
            "TASK-A",
            "TASK-B",
            "TASK-C",
            "TASK-D",
            "TASK-B",
            "TASK-C",
            "TASK-D",
            "TASK-B",
            "TASK-C",
        ]
        assert orchestrator._audit_health.scan_complete is True
        assert orchestrator._audit_metrics["health_cycle_candidate_count"] == 3
    finally:
        orchestrator._tick_pool.shutdown(wait=True, cancel_futures=True)
        orchestrator._refresh_pool.shutdown(wait=True, cancel_futures=True)


@pytest.mark.asyncio
async def test_runtime_partial_mixed_priority_health_progress_preserves_dispatch_order(
    tmp_path: Path,
) -> None:
    project_store = MagicMock()
    project_store.list_all.return_value = []
    project_store.get.side_effect = lambda project_id: SimpleNamespace(
        id=project_id,
        paused=False,
    )
    orchestrator = Orchestrator(
        ServiceConfig(
            workspace_root=str(tmp_path / "workspace"),
            audit_lane_scan_limit=2,
            audit_lane_operation_limit=2,
            audit_lane_dispatch_limit=2,
            audit_lane_max_runtime_seconds=1,
            duplicate_preflight_max_agents=0,
        ),
        str(tmp_path / "WORKFLOW.md"),
        project_store=project_store,
        state_path=str(tmp_path / "service_state.json"),
    )
    created_at = datetime(2026, 8, 4, tzinfo=timezone.utc)
    high = Issue(
        id="high",
        identifier="TASK-HIGH",
        title="High-priority audit",
        state="In Validation",
        project_id="project-high",
        priority=100,
        branch_name="task-high",
        created_at=created_at,
    )
    low = Issue(
        id="low",
        identifier="TASK-LOW",
        title="Low-priority audit",
        state="In Validation",
        project_id="project-low",
        priority=0,
        branch_name="task-low",
        created_at=created_at + timedelta(seconds=1),
    )
    records = {
        issue.identifier: TerminalAuditRecord(
            audit_id=f"audit-{issue.id}",
            project_id=str(issue.project_id),
            task_id=issue.identifier,
            target_state=TargetState.DONE,
            evidence_fingerprint=EvidenceFingerprint(
                ("a" if issue is high else "b") * 64
            ),
            request_state=RequestState.PENDING,
            created_at=created_at.isoformat(),
        )
        for issue in (high, low)
    }
    records[high.identifier] = replace(
        records[high.identifier],
        eligible_at=created_at.isoformat(),
    )
    store = MagicMock()
    clock = {"value": 0.0, "expire_on_low": True}

    def _read(identifier: str):
        if identifier == low.identifier and clock["expire_on_low"]:
            clock["value"] += 1.1
            clock["expire_on_low"] = False
        return SimpleNamespace(
            pending_chain=[records[identifier]],
            is_quarantined=False,
            unknown_fields={},
        )

    store.read.side_effect = _read
    selector = MagicMock()
    selector.select_candidates.return_value = (
        [Candidate(provider_id="provider-a", model="model-a")],
        None,
    )
    tracker = MagicMock()
    tracker.get_metadata.return_value = {}
    dispatch_order: list[str] = []

    async def _dispatch(issue: Issue, **_kwargs) -> bool:
        dispatch_order.append(issue.identifier)
        return True

    orchestrator._set_maintenance_cursor(
        "audit_lane",
        orchestrator._audit_candidate_cursor_key(high),
    )
    orchestrator._monotonic_clock = lambda: clock["value"]
    try:
        with (
            patch.object(orchestrator, "_available_slots", return_value=2),
            patch.object(orchestrator, "_dispatch_is_blocked", return_value=False),
            patch.object(orchestrator, "_is_project_paused", return_value=False),
            patch.object(
                orchestrator,
                "_fetch_audit_candidates",
                return_value=_AuditCandidateScan((high, low)),
            ),
            patch.object(orchestrator, "_audit_store", return_value=store),
            patch.object(
                orchestrator,
                "_bind_audit_record_revision",
                side_effect=lambda issue, record: record,
            ),
            patch.object(
                orchestrator,
                "_prepare_audit_selector",
                new=AsyncMock(return_value=(selector, None)),
            ),
            patch.object(
                orchestrator,
                "_terminal_audit_validation_configuration_error",
                return_value=None,
            ),
            patch.object(orchestrator, "_audit_branch_busy", return_value=False),
            patch.object(orchestrator, "_tracker_for_issue", return_value=tracker),
            patch.object(orchestrator, "_audit_update_record", return_value=True),
            patch.object(
                orchestrator,
                "_dispatch",
                new=AsyncMock(side_effect=_dispatch),
            ),
            patch.object(
                orchestrator,
                "_request_audit_lane_continuation",
                return_value=True,
            ) as continuation,
        ):
            await orchestrator._dispatch_audit_lane()
            assert dispatch_order == []
            assert orchestrator._audit_health.scan_complete is False
            assert orchestrator._audit_metrics["health_cycle_seen_count"] == 1
            assert orchestrator._audit_metrics["cursor"].endswith("TASK-LOW")

            orchestrator._eligible_audit_stage_wakes[(
                str(high.project_id),
                high.identifier,
            )] = records[high.identifier].audit_id
            await orchestrator._dispatch_audit_lane()

        assert dispatch_order == ["TASK-HIGH", "TASK-LOW"]
        assert orchestrator._audit_metrics["last_dispatched_count"] == 2
        assert orchestrator._audit_metrics["continuation_last_claim_at"] is not None
        assert orchestrator._audit_metrics["continuation_last_dispatch_at"] is not None
        assert (
            orchestrator._audit_metrics[
                "continuation_last_dispatch_latency_seconds"
            ]
            is not None
        )
        assert orchestrator._audit_health.scan_complete is True
        continuation.assert_called_once_with()
    finally:
        orchestrator._tick_pool.shutdown(wait=True, cancel_futures=True)
        orchestrator._refresh_pool.shutdown(wait=True, cancel_futures=True)


@pytest.mark.asyncio
async def test_completed_health_slice_revisits_deferred_lower_priority_launch(
    tmp_path: Path,
) -> None:
    project_store = MagicMock()
    project_store.list_all.return_value = []
    project_store.get.side_effect = lambda project_id: SimpleNamespace(
        id=project_id,
        paused=False,
    )
    orchestrator = Orchestrator(
        ServiceConfig(
            workspace_root=str(tmp_path / "workspace"),
            audit_lane_scan_limit=2,
            audit_lane_operation_limit=2,
            audit_lane_dispatch_limit=2,
            audit_lane_max_runtime_seconds=30,
            duplicate_preflight_max_agents=0,
        ),
        str(tmp_path / "WORKFLOW.md"),
        project_store=project_store,
        state_path=str(tmp_path / "service_state.json"),
    )
    created_at = datetime(2026, 8, 4, tzinfo=timezone.utc)
    high = Issue(
        id="high-no-record",
        identifier="TASK-HIGH-NO-RECORD",
        title="Higher-priority task without an active audit",
        state="In Validation",
        project_id="project-high",
        priority=100,
        branch_name="task-high-no-record",
        created_at=created_at,
    )
    low = Issue(
        id="low-pending",
        identifier="TASK-LOW-PENDING",
        title="Lower-priority pending audit",
        state="In Validation",
        project_id="project-low",
        priority=0,
        branch_name="task-low-pending",
        created_at=created_at + timedelta(seconds=1),
    )
    low_record = TerminalAuditRecord(
        audit_id="audit-low-pending",
        project_id=str(low.project_id),
        task_id=low.identifier,
        target_state=TargetState.DONE,
        evidence_fingerprint=EvidenceFingerprint("c" * 64),
        request_state=RequestState.PENDING,
        created_at=created_at.isoformat(),
    )
    store = MagicMock()
    store.read.side_effect = lambda identifier: SimpleNamespace(
        pending_chain=[low_record] if identifier == low.identifier else [],
        is_quarantined=False,
        unknown_fields={},
    )
    selector = MagicMock()
    selector.select_candidates.return_value = (
        [Candidate(provider_id="provider-a", model="model-a")],
        None,
    )
    tracker = MagicMock()
    tracker.get_metadata.return_value = {}
    dispatch_order: list[str] = []

    async def _dispatch(issue: Issue, **_kwargs) -> bool:
        dispatch_order.append(issue.identifier)
        return True

    orchestrator._set_maintenance_cursor(
        "audit_lane",
        orchestrator._audit_candidate_cursor_key(high),
    )
    try:
        with (
            patch.object(orchestrator, "_available_slots", return_value=2),
            patch.object(orchestrator, "_dispatch_is_blocked", return_value=False),
            patch.object(orchestrator, "_is_project_paused", return_value=False),
            patch.object(
                orchestrator,
                "_fetch_audit_candidates",
                return_value=_AuditCandidateScan((high, low)),
            ),
            patch.object(orchestrator, "_audit_store", return_value=store),
            patch.object(
                orchestrator,
                "_bind_audit_record_revision",
                return_value=low_record,
            ),
            patch.object(
                orchestrator,
                "_prepare_audit_selector",
                new=AsyncMock(return_value=(selector, None)),
            ),
            patch.object(
                orchestrator,
                "_terminal_audit_validation_configuration_error",
                return_value=None,
            ),
            patch.object(orchestrator, "_audit_branch_busy", return_value=False),
            patch.object(orchestrator, "_tracker_for_issue", return_value=tracker),
            patch.object(orchestrator, "_audit_update_record", return_value=True),
            patch.object(
                orchestrator,
                "_dispatch",
                new=AsyncMock(side_effect=_dispatch),
            ),
            patch.object(
                orchestrator,
                "_request_audit_lane_continuation",
                return_value=True,
            ) as continuation,
        ):
            await orchestrator._dispatch_audit_lane()
            assert dispatch_order == []
            assert orchestrator._audit_health.scan_complete is True
            assert orchestrator._audit_metrics["priority_revisit"] is True
            assert orchestrator._audit_metrics["cursor"].endswith(
                "TASK-LOW-PENDING"
            )

            await orchestrator._dispatch_audit_lane()

        assert dispatch_order == ["TASK-LOW-PENDING"]
        assert orchestrator._audit_metrics["last_dispatched_count"] == 1
        assert orchestrator._audit_metrics["priority_revisit"] is False
        continuation.assert_called_once_with()
    finally:
        orchestrator._tick_pool.shutdown(wait=True, cancel_futures=True)
        orchestrator._refresh_pool.shutdown(wait=True, cancel_futures=True)


@pytest.mark.asyncio
async def test_hundreds_of_slow_candidates_stop_at_operation_budget(
    tmp_path: Path,
) -> None:
    project_store = MagicMock()
    project_store.list_all.return_value = []
    orchestrator = Orchestrator(
        ServiceConfig(
            workspace_root=str(tmp_path / "workspace"),
            audit_lane_scan_limit=0,
            audit_lane_operation_limit=3,
            audit_lane_max_runtime_seconds=30,
            duplicate_preflight_max_agents=0,
        ),
        str(tmp_path / "WORKFLOW.md"),
        project_store=project_store,
        state_path=str(tmp_path / "service_state.json"),
    )
    candidates = tuple(
        Issue(
            id=f"issue-{index}",
            identifier=f"TASK-{index:03d}",
            title="Slow audit candidate",
            state="In Validation",
            project_id=f"project-{index % 5}",
            created_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
        )
        for index in range(250)
    )
    clock = {"value": 0.0}
    reads: list[str] = []
    store = MagicMock()

    def _slow_read(identifier: str):
        reads.append(identifier)
        clock["value"] += 0.25
        return SimpleNamespace(
            pending_chain=[],
            is_quarantined=False,
            unknown_fields={},
        )

    store.read.side_effect = _slow_read
    orchestrator._monotonic_clock = lambda: clock["value"]
    try:
        with (
            patch.object(orchestrator, "_available_slots", return_value=1),
            patch.object(orchestrator, "_dispatch_is_blocked", return_value=False),
            patch.object(orchestrator, "_is_project_paused", return_value=False),
            patch.object(
                orchestrator,
                "_fetch_audit_candidates",
                return_value=_AuditCandidateScan(candidates),
            ),
            patch.object(orchestrator, "_audit_store", return_value=store),
            patch.object(
                orchestrator,
                "_request_audit_lane_continuation",
                return_value=True,
            ) as continuation,
        ):
            await orchestrator._dispatch_audit_lane()

        assert len(reads) == 3
        assert orchestrator._audit_metrics["discovered_candidate_count"] == 250
        assert orchestrator._audit_metrics["scanned_candidate_count"] == 3
        assert orchestrator._audit_metrics["budget_reason"] == "operation_limit"
        assert orchestrator._audit_metrics["candidate_scan_complete"] is False
        continuation.assert_called_once_with()
    finally:
        orchestrator._tick_pool.shutdown(wait=True, cancel_futures=True)
        orchestrator._refresh_pool.shutdown(wait=True, cancel_futures=True)


@pytest.mark.asyncio
async def test_slow_selector_preparation_yields_at_audit_runtime_budget(
    tmp_path: Path,
) -> None:
    project_store = MagicMock()
    project_store.list_all.return_value = []
    orchestrator = Orchestrator(
        ServiceConfig(
            workspace_root=str(tmp_path / "workspace"),
            audit_lane_operation_limit=8,
            audit_lane_max_runtime_seconds=0.1,
            duplicate_preflight_max_agents=0,
        ),
        str(tmp_path / "WORKFLOW.md"),
        project_store=project_store,
        state_path=str(tmp_path / "service_state.json"),
    )
    issue = Issue(
        id="slow-issue",
        identifier="TASK-SLOW",
        title="Slow audit authority",
        state="In Validation",
        project_id="project-a",
        created_at=datetime.now(timezone.utc),
    )
    record = TerminalAuditRecord(
        audit_id="audit-slow",
        project_id="project-a",
        task_id=issue.identifier,
        target_state=TargetState.DONE,
        evidence_fingerprint=EvidenceFingerprint("a" * 64),
        request_state=RequestState.PENDING,
        created_at=issue.created_at.isoformat(),
    )
    store = MagicMock()
    store.read.return_value = SimpleNamespace(
        pending_chain=[record],
        is_quarantined=False,
        unknown_fields={},
    )

    async def _slow_prepare(_issue: Issue):
        await asyncio.sleep(1)
        raise AssertionError("selector preparation should have been cancelled")

    runtime = SimpleNamespace(
        started=True,
        worker=SimpleNamespace(accepting=True),
        reconcile_async=AsyncMock(return_value={"worker": {}}),
    )
    orchestrator.workflow_runtime = runtime
    try:
        with (
            patch.object(orchestrator, "_available_slots", return_value=1),
            patch.object(orchestrator, "_dispatch_is_blocked", return_value=False),
            patch.object(orchestrator, "_is_project_paused", return_value=False),
            patch.object(
                orchestrator,
                "_fetch_audit_candidates",
                return_value=_AuditCandidateScan((issue,)),
            ),
            patch.object(orchestrator, "_audit_store", return_value=store),
            patch.object(
                orchestrator,
                "_terminal_audit_validation_configuration_error",
                return_value=None,
            ),
            patch.object(
                orchestrator,
                "_prepare_audit_selector",
                new=AsyncMock(side_effect=_slow_prepare),
            ),
            patch.object(
                orchestrator,
                "_request_audit_lane_continuation",
                return_value=True,
            ) as continuation,
            patch.object(orchestrator, "_dispatch", new=AsyncMock()) as dispatch,
            patch.object(orchestrator, "_run_non_lifecycle_housekeeping"),
            patch.object(orchestrator, "_notify_observers"),
            patch.object(
                orchestrator,
                "_handle_auto_update",
                new=AsyncMock(),
            ),
        ):
            started = asyncio.get_running_loop().time()
            await orchestrator._run_durable_workflow_tick(started_at=started)
            elapsed = asyncio.get_running_loop().time() - started

        assert elapsed < 0.35
        assert orchestrator._audit_metrics["budget_exhausted"] is True
        assert orchestrator._audit_metrics["budget_reason"] == "selector_timeout"
        assert orchestrator._audit_health.scan_complete is False
        continuation.assert_called_once_with()
        runtime.reconcile_async.assert_awaited_once_with()
        dispatch.assert_not_awaited()
    finally:
        orchestrator._tick_pool.shutdown(wait=True, cancel_futures=True)
        orchestrator._refresh_pool.shutdown(wait=True, cancel_futures=True)


@pytest.mark.asyncio
async def test_audit_selector_authority_is_cached_per_project_lane_cut(
    tmp_path: Path,
) -> None:
    project_store = MagicMock()
    project_store.list_all.return_value = []
    orchestrator = Orchestrator(
        ServiceConfig(
            workspace_root=str(tmp_path / "workspace"),
            duplicate_preflight_max_agents=0,
        ),
        str(tmp_path / "WORKFLOW.md"),
        project_store=project_store,
        state_path=str(tmp_path / "service_state.json"),
    )
    project = SimpleNamespace(id="project-a", provider_whitelist=[])
    prepared = AuditorCandidateSelector(
        orchestrator.role_store,
        orchestrator.provider_store,
        project_config=project,
        health_results={},
        budget_limit=orchestrator.config.budget_limit,
    )
    first = Issue(
        id="issue-first",
        identifier="TASK-FIRST",
        title="First",
        state="In Validation",
        project_id="project-a",
    )
    second = Issue(
        id="issue-second",
        identifier="TASK-SECOND",
        title="Second",
        state="In Validation",
        project_id="project-a",
    )
    cache = {}
    try:
        with patch.object(
            orchestrator,
            "_prepare_audit_selector",
            new=AsyncMock(return_value=(prepared, None)),
        ) as prepare:
            first_selector, first_error = (
                await orchestrator._prepare_cached_audit_selector(first, cache)
            )
            second_selector, second_error = (
                await orchestrator._prepare_cached_audit_selector(second, cache)
            )

        assert first_error is None
        assert second_error is None
        assert first_selector is prepared
        assert second_selector is not prepared
        assert second_selector is not None
        assert second_selector.project_config is project
        assert second_selector.health_results is prepared.health_results
        prepare.assert_awaited_once_with(first)
    finally:
        orchestrator._tick_pool.shutdown(wait=True, cancel_futures=True)
        orchestrator._refresh_pool.shutdown(wait=True, cancel_futures=True)


@pytest.mark.asyncio
async def test_audit_finalization_replays_before_expired_candidate_budget(
    tmp_path: Path,
) -> None:
    project_store = MagicMock()
    project_store.list_all.return_value = []
    orchestrator = Orchestrator(
        ServiceConfig(
            workspace_root=str(tmp_path / "workspace"),
            audit_lane_max_runtime_seconds=0.1,
            duplicate_preflight_max_agents=0,
        ),
        str(tmp_path / "WORKFLOW.md"),
        project_store=project_store,
        state_path=str(tmp_path / "service_state.json"),
    )
    issue = Issue(
        id="deferred-issue",
        identifier="TASK-DEFERRED",
        title="Deferred audit candidate",
        state="In Validation",
        project_id="project-a",
    )
    clock = {"value": 0.0}

    async def _replay() -> int:
        clock["value"] = 1.0
        return 1

    orchestrator._monotonic_clock = lambda: clock["value"]
    try:
        with (
            patch.object(
                orchestrator,
                "_replay_terminal_audit_finalizations",
                new=AsyncMock(side_effect=_replay),
            ) as replay,
            patch.object(orchestrator, "_available_slots", return_value=1),
            patch.object(orchestrator, "_dispatch_is_blocked", return_value=False),
            patch.object(
                orchestrator,
                "_fetch_audit_candidates",
                return_value=_AuditCandidateScan((issue,)),
            ),
            patch.object(orchestrator, "_audit_store") as audit_store,
            patch.object(
                orchestrator,
                "_request_audit_lane_continuation",
                return_value=True,
            ),
        ):
            await orchestrator._dispatch_audit_lane()

        replay.assert_awaited_once_with()
        assert orchestrator._audit_metrics["finalizations_replayed"] == 1
        assert orchestrator._audit_metrics["budget_reason"] == "runtime_limit"
        audit_store.assert_not_called()
    finally:
        orchestrator._tick_pool.shutdown(wait=True, cancel_futures=True)
        orchestrator._refresh_pool.shutdown(wait=True, cancel_futures=True)


def test_audit_budget_continuation_queues_dedicated_lane_before_startup() -> None:
    orchestrator = object.__new__(Orchestrator)
    orchestrator.workflow_runtime = SimpleNamespace(
        worker=SimpleNamespace(accepting=True)
    )
    orchestrator._provider_admission_lock = threading.RLock()
    orchestrator._stopping = False
    orchestrator._quiesced = False
    orchestrator._paused = False
    orchestrator._dispatch_loop = None
    orchestrator._terminal_audit_continuation_wake_pending = False
    orchestrator._set_refresh_requested = Mock()
    orchestrator._post_event = Mock()

    assert orchestrator._request_audit_lane_continuation() is True

    orchestrator._set_refresh_requested.assert_not_called()
    orchestrator._post_event.assert_not_called()
    assert orchestrator._terminal_audit_continuation_wake_pending is True


def test_next_audit_stage_registers_exact_wake_before_requesting_lane() -> None:
    orchestrator = object.__new__(Orchestrator)
    orchestrator._eligible_audit_stage_wakes = {}
    orchestrator._request_audit_lane_continuation = Mock(return_value=True)

    assert orchestrator._request_next_audit_stage(
        project_id="project-a",
        task_id="TASK-1",
        audit_id="audit-merged",
    ) is True

    assert orchestrator._eligible_audit_stage_wakes == {
        ("project-a", "TASK-1"): "audit-merged"
    }
    orchestrator._request_audit_lane_continuation.assert_called_once_with(
        external=True
    )


@pytest.mark.parametrize(
    ("stopping", "quiesced", "paused", "accepting"),
    (
        (True, False, False, True),
        (False, True, False, True),
        (False, False, True, True),
        (False, False, False, False),
    ),
)
def test_audit_budget_continuation_respects_shutdown_fences(
    stopping: bool,
    quiesced: bool,
    paused: bool,
    accepting: bool,
) -> None:
    orchestrator = object.__new__(Orchestrator)
    orchestrator.workflow_runtime = SimpleNamespace(
        worker=SimpleNamespace(accepting=accepting)
    )
    orchestrator._provider_admission_lock = threading.RLock()
    orchestrator._stopping = stopping
    orchestrator._quiesced = quiesced
    orchestrator._paused = paused
    orchestrator._set_refresh_requested = Mock()
    orchestrator._post_event = Mock()

    assert orchestrator._request_audit_lane_continuation() is False
    orchestrator._set_refresh_requested.assert_not_called()
    orchestrator._post_event.assert_not_called()


def _dedicated_audit_lane_host(
    loop: asyncio.AbstractEventLoop,
) -> Orchestrator:
    """Return the smallest production-shaped dedicated-lane host."""

    orchestrator = object.__new__(Orchestrator)
    orchestrator.config = ServiceConfig(workspace_root=".")
    orchestrator.workflow_runtime = SimpleNamespace(
        started=True,
        worker=SimpleNamespace(accepting=True),
    )
    orchestrator._provider_admission_lock = threading.RLock()
    orchestrator._stopping = False
    orchestrator._quiesced = False
    orchestrator._paused = False
    orchestrator._dispatch_loop = loop
    orchestrator._dispatch_queue = asyncio.Queue()
    orchestrator._dispatch_event_lock = threading.Lock()
    orchestrator._dispatch_pending_event_keys = set()
    orchestrator._dispatch_pending_coalesced_counts = {}
    orchestrator._dispatch_events_coalesced = 0
    orchestrator._refresh_requested = asyncio.Event()
    orchestrator._terminal_audit_continuation_future = None
    orchestrator._terminal_audit_continuation_recheck_requested = False
    orchestrator._terminal_audit_continuation_external_recheck_requested = False
    orchestrator._terminal_audit_continuation_wake_pending = False
    orchestrator._terminal_audit_lane_lock = asyncio.Lock()
    orchestrator._eligible_audit_stage_wakes = {}
    orchestrator._audit_metrics = {}
    orchestrator._available_slots = Mock(return_value=1)
    return orchestrator


def _runnable_implementation_decision(task_id: str) -> WorkDecision:
    return WorkDecision(
        project_id="project-a",
        task_id=task_id,
        status="Open",
        disposition=TaskDisposition.RUNNABLE,
        reason_code="dispatch.eligible",
        responsible_owner=WorkflowOwner.DISPATCHER,
        unmet_prerequisites=(),
        evidence_revision=f"evidence-{task_id}",
        next_reassessment_at=None,
        permitted_actions=(PermittedAction.CLAIM_IMPLEMENTATION,),
        action_required=False,
        alert_level="info",
        durable_jobs=("implementation_start",),
    )


@pytest.mark.parametrize(
    "job",
    ("direct_owner_claim", "validation_submission", "implementation_retry"),
)
def test_audit_reservation_ignores_non_provider_implementation_jobs(job: str) -> None:
    decision = replace(
        _runnable_implementation_decision("TASK-CONTROL"),
        disposition=TaskDisposition.RETRY_SCHEDULED,
        durable_jobs=(job,),
        decision_revision=None,
    )

    assert not Orchestrator._decision_has_runnable_implementation_provider(
        decision
    )


@pytest.mark.asyncio
async def test_one_slot_continuation_rechecks_implementation_reservation_after_lock(
) -> None:
    """A late ordinary-selection proof wins the single free slot."""

    loop = asyncio.get_running_loop()
    orchestrator = _dedicated_audit_lane_host(loop)
    orchestrator.state = SimpleNamespace(max_concurrent_agents=1)
    orchestrator._available_slots.return_value = 1
    orchestrator._record_terminal_audit_stage_wake(
        project_id="project-a",
        task_id="TASK-AUDIT",
        audit_id="audit-merged",
    )
    observed_reservations: list[int] = []

    async def _owned_scan(**kwargs) -> dict[str, float]:
        reserved = int(kwargs["reserved_non_audit_slots"])
        observed_reservations.append(reserved)
        if orchestrator._available_slots() - reserved > 0:
            orchestrator._retire_terminal_audit_stage_wake(
                project_id="project-a",
                task_id="TASK-AUDIT",
                expected_audit_id="audit-merged",
                reason="test_dispatch",
            )
        return {}

    orchestrator._dispatch_audit_lane_owned = AsyncMock(side_effect=_owned_scan)
    await orchestrator._terminal_audit_lane_lock.acquire()
    orchestrator._wake_terminal_audit_continuation_lane_on_loop()
    owner = orchestrator._terminal_audit_continuation_future
    assert owner is not None
    await asyncio.sleep(0)

    # The ordinary dispatcher proves implementation work after the dedicated
    # task was scheduled but before it can own the shared audit lane.
    orchestrator._terminal_audit_non_audit_ready_hint = True
    orchestrator._terminal_audit_lane_lock.release()
    await asyncio.wait_for(owner, timeout=1)

    assert observed_reservations == [1]
    assert orchestrator._terminal_audit_stage_wakes_snapshot() == {
        ("project-a", "TASK-AUDIT"): "audit-merged"
    }
    assert orchestrator._audit_metrics[
        "continuation_reserved_non_audit_slots"
    ] == 1


@pytest.mark.asyncio
async def test_multi_slot_continuation_preserves_configured_implementation_reserve(
) -> None:
    """Published runtime work keeps every configured non-audit slot."""

    loop = asyncio.get_running_loop()
    orchestrator = _dedicated_audit_lane_host(loop)
    orchestrator.config.audit_non_audit_reserved_slots = 2
    orchestrator.state = SimpleNamespace(max_concurrent_agents=4)
    orchestrator._available_slots.return_value = 4
    orchestrator._work_decisions_lock = threading.RLock()
    orchestrator._work_decisions = {}
    for index in range(4):
        orchestrator._record_terminal_audit_stage_wake(
            project_id="project-a",
            task_id=f"TASK-AUDIT-{index}",
            audit_id=f"audit-{index}",
        )
    observed_reservations: list[int] = []

    async def _owned_scan(**kwargs) -> dict[str, float]:
        reserved = int(kwargs["reserved_non_audit_slots"])
        observed_reservations.append(reserved)
        launch_budget = orchestrator._available_slots() - reserved
        for (project_id, task_id), audit_id in list(
            orchestrator._terminal_audit_stage_wakes_snapshot().items()
        )[:launch_budget]:
            orchestrator._retire_terminal_audit_stage_wake(
                project_id=project_id,
                task_id=task_id,
                expected_audit_id=audit_id,
                reason="test_dispatch",
            )
        return {}

    orchestrator._dispatch_audit_lane_owned = AsyncMock(side_effect=_owned_scan)
    await orchestrator._terminal_audit_lane_lock.acquire()
    orchestrator._wake_terminal_audit_continuation_lane_on_loop()
    owner = orchestrator._terminal_audit_continuation_future
    assert owner is not None
    await asyncio.sleep(0)

    with orchestrator._work_decisions_lock:
        decision = _runnable_implementation_decision("TASK-WORK")
        orchestrator._work_decisions[(decision.project_id, decision.task_id)] = (
            decision
        )
    orchestrator._terminal_audit_lane_lock.release()
    await asyncio.wait_for(owner, timeout=1)

    assert observed_reservations == [2]
    assert len(orchestrator._terminal_audit_stage_wakes_snapshot()) == 2
    assert orchestrator._audit_metrics[
        "continuation_reserved_non_audit_slots"
    ] == 2


@pytest.mark.asyncio
async def test_exact_capacity_release_rearms_once_after_identity_cas() -> None:
    """Only the exact running-entry removal publishes the capacity edge."""

    loop = asyncio.get_running_loop()
    orchestrator = _dedicated_audit_lane_host(loop)
    entry = object()
    replacement = object()
    orchestrator.state = SimpleNamespace(
        max_concurrent_agents=1,
        running={"worker": entry},
    )
    orchestrator._retry_authority_lock = threading.RLock()
    orchestrator._available_slots.side_effect = lambda: max(
        orchestrator.state.max_concurrent_agents
        - len(orchestrator.state.running),
        0,
    )
    orchestrator._record_terminal_audit_stage_wake(
        project_id="project-a",
        task_id="TASK-AUDIT",
        audit_id="audit-merged",
    )
    dispatched = asyncio.Event()
    scans = 0

    async def _scan(**_kwargs) -> dict[str, float]:
        nonlocal scans
        scans += 1
        if orchestrator._available_slots() > 0:
            orchestrator._retire_terminal_audit_stage_wake(
                project_id="project-a",
                task_id="TASK-AUDIT",
                expected_audit_id="audit-merged",
                reason="test_dispatch",
            )
            dispatched.set()
        return {}

    orchestrator._dispatch_audit_lane = AsyncMock(side_effect=_scan)
    orchestrator._wake_terminal_audit_continuation_lane_on_loop()
    first_owner = orchestrator._terminal_audit_continuation_future
    assert first_owner is not None
    await asyncio.wait_for(first_owner, timeout=1)
    assert scans == 1
    assert not dispatched.is_set()

    assert orchestrator._remove_running_entry("worker", replacement) is False
    await asyncio.sleep(0)
    assert scans == 1

    assert orchestrator._remove_running_entry("worker", entry) is True
    await asyncio.wait_for(dispatched.wait(), timeout=1)
    await asyncio.sleep(0)
    assert scans == 2

    # Duplicate/stale retirements cannot produce follow-up scans, and an
    # already-retired exact wake makes every later capacity release a no-op.
    assert orchestrator._remove_running_entry("worker", entry) is False
    orchestrator.state.running["other"] = object()
    assert orchestrator._remove_running_entry("other") is True
    await asyncio.sleep(0)
    assert scans == 2


@pytest.mark.asyncio
async def test_branch_fence_release_rearms_after_early_slot_wake() -> None:
    """A slot wake that precedes auditor branch release cannot strand work."""

    loop = asyncio.get_running_loop()
    orchestrator = _dedicated_audit_lane_host(loop)
    entry = object()
    orchestrator.state = SimpleNamespace(
        max_concurrent_agents=1,
        running={"done-auditor": entry},
    )
    orchestrator._retry_authority_lock = threading.RLock()
    orchestrator._available_slots.side_effect = lambda: max(
        orchestrator.state.max_concurrent_agents
        - len(orchestrator.state.running),
        0,
    )
    orchestrator._audit_branch_claims = {"shared-branch": "attempt-done"}
    orchestrator._record_terminal_audit_stage_wake(
        project_id="project-a",
        task_id="TASK-AUDIT",
        audit_id="audit-merged",
    )
    dispatched = asyncio.Event()

    async def _scan(**_kwargs) -> dict[str, float]:
        if (
            orchestrator._available_slots() > 0
            and "shared-branch" not in orchestrator._audit_branch_claims
        ):
            orchestrator._retire_terminal_audit_stage_wake(
                project_id="project-a",
                task_id="TASK-AUDIT",
                expected_audit_id="audit-merged",
                reason="test_dispatch",
            )
            dispatched.set()
        return {}

    orchestrator._dispatch_audit_lane = AsyncMock(side_effect=_scan)
    orchestrator._wake_terminal_audit_continuation_lane_on_loop()
    first_owner = orchestrator._terminal_audit_continuation_future
    assert first_owner is not None
    await asyncio.wait_for(first_owner, timeout=1)
    assert orchestrator._dispatch_audit_lane.await_count == 1

    assert orchestrator._remove_running_entry("done-auditor", entry) is True
    slot_owner = orchestrator._terminal_audit_continuation_future
    assert slot_owner is not None
    await asyncio.wait_for(slot_owner, timeout=1)
    assert orchestrator._dispatch_audit_lane.await_count == 2
    assert not dispatched.is_set()

    assert orchestrator._release_audit_branch_claim(
        "shared-branch", "attempt-done"
    ) is True
    await asyncio.wait_for(dispatched.wait(), timeout=1)
    await asyncio.sleep(0)
    assert orchestrator._dispatch_audit_lane.await_count == 3

    assert orchestrator._release_audit_branch_claim(
        "shared-branch", "attempt-done"
    ) is False
    await asyncio.sleep(0)
    assert orchestrator._dispatch_audit_lane.await_count == 3


@pytest.mark.asyncio
async def test_worker_thread_successor_registration_is_owned_by_scheduler_loop() -> None:
    loop = asyncio.get_running_loop()
    orchestrator = _dedicated_audit_lane_host(loop)
    scheduler_thread = threading.get_ident()
    registered = asyncio.Event()
    original_record = orchestrator._record_terminal_audit_stage_wake

    def _record_on_owner(**kwargs) -> bool:
        assert threading.get_ident() == scheduler_thread
        changed = original_record(**kwargs)
        registered.set()
        return changed

    with (
        patch.object(
            orchestrator,
            "_record_terminal_audit_stage_wake",
            side_effect=_record_on_owner,
        ),
        patch.object(
            orchestrator,
            "_request_audit_lane_continuation",
            return_value=False,
        ),
    ):
        queued = await asyncio.to_thread(
            orchestrator._request_next_audit_stage,
            project_id="project-a",
            task_id="TASK-THREAD",
            audit_id="audit-thread",
        )
        assert queued is True
        await asyncio.wait_for(registered.wait(), timeout=1)

    assert orchestrator._terminal_audit_stage_wakes_snapshot() == {
        ("project-a", "TASK-THREAD"): "audit-thread"
    }


def test_closed_scheduler_race_retains_capacity_release_wake() -> None:
    orchestrator = object.__new__(Orchestrator)
    loop = MagicMock()
    loop.is_running.return_value = True
    loop.call_soon_threadsafe.side_effect = RuntimeError("loop closed")
    orchestrator._dispatch_loop = loop
    orchestrator._terminal_audit_continuation_wake_pending = False

    with patch.object(orchestrator, "_running_loop", return_value=None):
        orchestrator._wake_terminal_audit_continuation_lane()

    assert orchestrator._terminal_audit_continuation_wake_pending is True


@pytest.mark.asyncio
async def test_exact_successor_dispatch_bypasses_blocked_durable_reconcile() -> None:
    """Reproduce the live OOMPAH-1082 full-world tick race."""

    loop = asyncio.get_running_loop()
    orchestrator = _dedicated_audit_lane_host(loop)
    reconcile_started = asyncio.Event()
    release_reconcile = asyncio.Event()
    capacity_deferred = asyncio.Event()
    release_deferred_owner = asyncio.Event()
    successor_claimed = asyncio.Event()
    done_auditor = object()
    orchestrator.state = SimpleNamespace(
        max_concurrent_agents=1,
        running={"done-auditor": done_auditor},
    )
    orchestrator._retry_authority_lock = threading.RLock()

    async def _reconcile_async() -> dict:
        reconcile_started.set()
        await release_reconcile.wait()
        return {"worker": {}}

    orchestrator.workflow_runtime.reconcile_async = _reconcile_async
    orchestrator._run_terminal_audit_tick_phase = AsyncMock(return_value={})
    orchestrator._request_runtime_report_continuation = Mock(return_value=False)
    orchestrator._request_workflow_batch_continuation = Mock(return_value=False)
    orchestrator._maintenance_future = loop.create_future()
    orchestrator._monotonic_clock = loop.time
    orchestrator._notify_observers = Mock()
    orchestrator._handle_auto_update = AsyncMock()
    orchestrator._finish_terminal_audit_workflow = Mock(return_value=True)
    orchestrator._record_audit_outcome_ownership = Mock()
    orchestrator._available_slots.side_effect = lambda: max(
        orchestrator.state.max_concurrent_agents
        - len(orchestrator.state.running),
        0,
    )

    async def _audit_scan(**_kwargs) -> dict[str, float]:
        if orchestrator._available_slots() <= 0:
            capacity_deferred.set()
            await release_deferred_owner.wait()
            return {}
        orchestrator._eligible_audit_stage_wakes.pop(
            ("project-a", "TASK-1"), None
        )
        successor_claimed.set()
        return {}

    orchestrator._dispatch_audit_lane = AsyncMock(side_effect=_audit_scan)

    world_tick = asyncio.create_task(
        orchestrator._run_durable_workflow_tick(started_at=loop.time())
    )
    await asyncio.wait_for(reconcile_started.wait(), timeout=1)

    issue = Issue(
        id="TASK-1",
        identifier="TASK-1",
        title="Chained audit",
        state="In Validation",
        project_id="project-a",
    )
    outcome = SimpleNamespace(
        success=True,
        advanced_target=TargetState.MERGED,
        advanced_audit_id="audit-merged",
    )
    assert orchestrator._finish_and_wake_terminal_audit_workflow(
        issue,
        SimpleNamespace(),
        outcome,
        SimpleNamespace(),
    )
    await asyncio.wait_for(capacity_deferred.wait(), timeout=1)
    first_owner = orchestrator._terminal_audit_continuation_future
    assert first_owner is not None
    assert not first_owner.done()
    assert not successor_claimed.is_set()
    assert not release_reconcile.is_set()

    # The Done auditor now retires and releases its only slot. The exact
    # capacity CAS is a direct dedicated-lane edge even though the unrelated
    # world cut remains blocked. Hold the initial owner after its capacity
    # observation so the release must coalesce into that same owner; no
    # generic event or full sync is required.
    assert orchestrator._remove_running_entry(
        "done-auditor", done_auditor
    ) is True
    assert orchestrator._terminal_audit_continuation_future is first_owner
    assert orchestrator._terminal_audit_continuation_recheck_requested is True
    assert orchestrator._audit_metrics["continuation_scheduled_count"] == 1
    release_deferred_owner.set()
    await asyncio.wait_for(successor_claimed.wait(), timeout=1)
    await asyncio.wait_for(first_owner, timeout=1)
    assert not release_reconcile.is_set()

    release_reconcile.set()
    await asyncio.wait_for(world_tick, timeout=1)
    orchestrator._maintenance_future.cancel()
    assert orchestrator._run_terminal_audit_tick_phase.await_count == 1
    assert orchestrator._dispatch_audit_lane.await_count == 2
    assert orchestrator._audit_metrics["continuation_scheduled_count"] == 1
    assert orchestrator._audit_metrics["continuation_recheck_count"] == 1


@pytest.mark.asyncio
async def test_dedicated_audit_lane_coalesces_active_wakes_into_one_recheck() -> None:
    loop = asyncio.get_running_loop()
    orchestrator = _dedicated_audit_lane_host(loop)
    first_started = asyncio.Event()
    release_first = asyncio.Event()
    active = 0
    max_active = 0
    scans = 0

    async def _audit_scan(**_kwargs) -> dict[str, float]:
        nonlocal active, max_active, scans
        scans += 1
        active += 1
        max_active = max(max_active, active)
        try:
            if scans == 1:
                first_started.set()
                await release_first.wait()
            else:
                orchestrator._eligible_audit_stage_wakes.clear()
            return {}
        finally:
            active -= 1

    orchestrator._dispatch_audit_lane = AsyncMock(side_effect=_audit_scan)

    assert orchestrator._request_next_audit_stage(
        project_id="project-a",
        task_id="TASK-1",
        audit_id="audit-1",
    )
    await asyncio.wait_for(first_started.wait(), timeout=1)
    owner = orchestrator._terminal_audit_continuation_future
    assert owner is not None
    for task_id in ("TASK-2", "TASK-3"):
        assert orchestrator._request_next_audit_stage(
            project_id="project-a",
            task_id=task_id,
            audit_id=f"audit-{task_id}",
        )

    release_first.set()
    await asyncio.wait_for(owner, timeout=1)
    await asyncio.sleep(0)

    assert scans == 2
    assert max_active == 1
    assert orchestrator._terminal_audit_continuation_future is None
    assert orchestrator._audit_metrics["continuation_scheduled_count"] == 1
    assert orchestrator._audit_metrics["continuation_recheck_count"] == 2


@pytest.mark.asyncio
async def test_internal_continuation_recheck_is_bounded_and_log_rate_limited(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An unchanged eligibility deferral cannot recreate the live CPU storm."""

    loop = asyncio.get_running_loop()
    orchestrator = _dedicated_audit_lane_host(loop)
    orchestrator._record_terminal_audit_stage_wake(
        project_id="project-a",
        task_id="TASK-BLOCKED",
        audit_id="audit-blocked",
    )

    async def _self_rearming_scan(**_kwargs) -> dict[str, float]:
        assert orchestrator._request_audit_lane_continuation() is True
        return {}

    orchestrator._dispatch_audit_lane = AsyncMock(side_effect=_self_rearming_scan)
    caplog.set_level("INFO", logger="oompah.orchestrator")

    orchestrator._wake_terminal_audit_continuation_lane_on_loop()
    owner = orchestrator._terminal_audit_continuation_future
    assert owner is not None
    await asyncio.wait_for(owner, timeout=1)
    await asyncio.sleep(0)

    starts = [
        record
        for record in caplog.records
        if record.getMessage().startswith(
            "Terminal-audit continuation lane started"
        )
    ]
    deferrals = [
        record
        for record in caplog.records
        if record.getMessage().startswith("Terminal-audit continuation deferred")
    ]
    assert orchestrator._dispatch_audit_lane.await_count == 2
    assert orchestrator._terminal_audit_continuation_future is None
    assert orchestrator._audit_metrics["continuation_started_count"] == 1
    assert orchestrator._audit_metrics["continuation_scan_count"] == 2
    assert orchestrator._audit_metrics["continuation_recheck_count"] == 2
    assert (
        orchestrator._audit_metrics.get("continuation_external_recheck_count", 0)
        == 0
    )
    assert orchestrator._audit_metrics["continuation_suppressed_recheck_count"] == 1
    assert orchestrator._audit_metrics["continuation_last_deferred_reason"] == (
        "eligibility_or_policy"
    )
    assert len(starts) == 1
    assert len(deferrals) == 1


@pytest.mark.asyncio
async def test_reserved_slot_stops_internal_continuation_recheck() -> None:
    """A nominally free slot reserved for implementation is not audit capacity."""

    loop = asyncio.get_running_loop()
    orchestrator = _dedicated_audit_lane_host(loop)
    orchestrator._record_terminal_audit_stage_wake(
        project_id="project-a",
        task_id="TASK-RESERVED",
        audit_id="audit-reserved",
    )

    async def _reservation_blocked_scan(**_kwargs) -> dict[str, float]:
        orchestrator._audit_metrics["reserved_non_audit_slots"] = 1
        assert orchestrator._request_audit_lane_continuation() is True
        return {}

    orchestrator._dispatch_audit_lane = AsyncMock(
        side_effect=_reservation_blocked_scan
    )

    orchestrator._wake_terminal_audit_continuation_lane_on_loop()
    owner = orchestrator._terminal_audit_continuation_future
    assert owner is not None
    await asyncio.wait_for(owner, timeout=1)
    await asyncio.sleep(0)

    assert orchestrator._dispatch_audit_lane.await_count == 1
    assert orchestrator._terminal_audit_continuation_future is None
    assert orchestrator._audit_metrics["continuation_started_count"] == 1
    assert orchestrator._audit_metrics["continuation_scan_count"] == 1
    assert orchestrator._audit_metrics["continuation_recheck_count"] == 1
    assert orchestrator._audit_metrics["continuation_last_deferred_reason"] == (
        "capacity"
    )
    assert orchestrator._terminal_audit_stage_wakes_snapshot() == {
        ("project-a", "TASK-RESERVED"): "audit-reserved"
    }


@pytest.mark.asyncio
async def test_external_wake_after_bounded_recheck_hands_off_once() -> None:
    """A late real edge gets one successor owner after the budget is spent."""

    loop = asyncio.get_running_loop()
    orchestrator = _dedicated_audit_lane_host(loop)
    orchestrator._record_terminal_audit_stage_wake(
        project_id="project-a",
        task_id="TASK-LATE",
        audit_id="audit-late",
    )
    second_scan_started = asyncio.Event()
    release_second_scan = asyncio.Event()
    successor_started = asyncio.Event()
    scans = 0
    active = 0
    max_active = 0

    async def _audit_scan(**_kwargs) -> dict[str, float]:
        nonlocal active, max_active, scans
        scans += 1
        active += 1
        max_active = max(max_active, active)
        try:
            if scans == 1:
                assert orchestrator._request_audit_lane_continuation() is True
            elif scans == 2:
                second_scan_started.set()
                await release_second_scan.wait()
            else:
                orchestrator._eligible_audit_stage_wakes.clear()
                successor_started.set()
            return {}
        finally:
            active -= 1

    orchestrator._dispatch_audit_lane = AsyncMock(side_effect=_audit_scan)

    orchestrator._wake_terminal_audit_continuation_lane_on_loop()
    first_owner = orchestrator._terminal_audit_continuation_future
    assert first_owner is not None
    await asyncio.wait_for(second_scan_started.wait(), timeout=1)

    # A worker-exit/exact-stage edge arrives after the owner has already spent
    # its one internal recheck. It must be transferred, not suppressed.
    orchestrator._wake_terminal_audit_continuation_lane_on_loop()
    release_second_scan.set()
    await asyncio.wait_for(first_owner, timeout=1)
    await asyncio.wait_for(successor_started.wait(), timeout=1)
    successor = orchestrator._terminal_audit_continuation_future
    if successor is not None:
        await asyncio.wait_for(successor, timeout=1)
    await asyncio.sleep(0)

    assert scans == 3
    assert max_active == 1
    assert orchestrator._terminal_audit_continuation_future is None
    assert orchestrator._audit_metrics["continuation_scheduled_count"] == 2
    assert orchestrator._audit_metrics["continuation_started_count"] == 2
    assert orchestrator._audit_metrics["continuation_scan_count"] == 3
    assert orchestrator._audit_metrics["continuation_recheck_count"] == 2
    assert orchestrator._audit_metrics["continuation_external_recheck_count"] == 1
    assert (
        orchestrator._audit_metrics.get("continuation_suppressed_recheck_count", 0)
        == 0
    )


@pytest.mark.asyncio
async def test_paused_exact_wake_runs_when_dedicated_lane_is_resumed() -> None:
    loop = asyncio.get_running_loop()
    orchestrator = _dedicated_audit_lane_host(loop)
    dispatched = asyncio.Event()
    orchestrator._paused = True
    orchestrator._eligible_audit_stage_wakes[(
        "project-a",
        "TASK-1",
    )] = "audit-merged"

    orchestrator._wake_terminal_audit_continuation_lane_on_loop()

    assert orchestrator._terminal_audit_continuation_wake_pending is True
    assert orchestrator._terminal_audit_continuation_future is None
    assert orchestrator._audit_metrics["continuation_last_deferred_reason"] == "paused"

    async def _audit_scan(**_kwargs) -> dict[str, float]:
        orchestrator._eligible_audit_stage_wakes.clear()
        dispatched.set()
        return {}

    orchestrator._dispatch_audit_lane = AsyncMock(side_effect=_audit_scan)
    orchestrator._paused = False
    orchestrator._wake_terminal_audit_continuation_lane_on_loop()
    await asyncio.wait_for(dispatched.wait(), timeout=1)


@pytest.mark.asyncio
async def test_dedicated_audit_lane_failure_is_observable_and_not_spun() -> None:
    loop = asyncio.get_running_loop()
    orchestrator = _dedicated_audit_lane_host(loop)
    orchestrator._eligible_audit_stage_wakes[(
        "project-a",
        "TASK-1",
    )] = "audit-merged"
    orchestrator._dispatch_audit_lane = AsyncMock(
        side_effect=RuntimeError("audit store unavailable")
    )

    orchestrator._wake_terminal_audit_continuation_lane_on_loop()
    owner = orchestrator._terminal_audit_continuation_future
    assert owner is not None
    await asyncio.gather(owner, return_exceptions=True)
    await asyncio.sleep(0)

    assert orchestrator._dispatch_audit_lane.await_count == 1
    assert orchestrator._eligible_audit_stage_wakes
    assert orchestrator._audit_metrics["continuation_last_error"] == (
        "RuntimeError: audit store unavailable"
    )


@pytest.mark.asyncio
async def test_ordinary_and_dedicated_audit_scans_have_one_lane_owner() -> None:
    loop = asyncio.get_running_loop()
    orchestrator = _dedicated_audit_lane_host(loop)
    first_started = asyncio.Event()
    release_first = asyncio.Event()
    active = 0
    max_active = 0
    calls = 0

    async def _owned_scan(**_kwargs) -> dict[str, float]:
        nonlocal active, max_active, calls
        calls += 1
        active += 1
        max_active = max(max_active, active)
        try:
            if calls == 1:
                first_started.set()
                await release_first.wait()
            return {}
        finally:
            active -= 1

    orchestrator._dispatch_audit_lane_owned = AsyncMock(side_effect=_owned_scan)
    ordinary = asyncio.create_task(orchestrator._dispatch_audit_lane())
    await asyncio.wait_for(first_started.wait(), timeout=1)
    dedicated = asyncio.create_task(orchestrator._dispatch_audit_lane())
    await asyncio.sleep(0)
    assert orchestrator._dispatch_audit_lane_owned.await_count == 1

    release_first.set()
    await asyncio.gather(ordinary, dedicated)

    assert orchestrator._dispatch_audit_lane_owned.await_count == 2
    assert max_active == 1


def test_unpause_rearms_retained_exact_successor_wake(tmp_path: Path) -> None:
    project_store = MagicMock()
    project_store.list_all.return_value = []
    orchestrator = Orchestrator(
        ServiceConfig(
            workspace_root=str(tmp_path / "workspace"),
            duplicate_preflight_max_agents=0,
        ),
        str(tmp_path / "WORKFLOW.md"),
        project_store=project_store,
        state_path=str(tmp_path / "service_state.json"),
    )
    orchestrator._paused = True
    orchestrator._eligible_audit_stage_wakes[(
        "project-a",
        "TASK-1",
    )] = "audit-merged"
    try:
        with (
            patch.object(orchestrator, "_save_paused_state_if_generation"),
            patch.object(
                orchestrator,
                "_wake_terminal_audit_continuation_lane",
            ) as wake,
        ):
            assert orchestrator.unpause(notify=False) is True

        wake.assert_called_once_with()
    finally:
        orchestrator._tick_pool.shutdown(wait=True, cancel_futures=True)
        orchestrator._refresh_pool.shutdown(wait=True, cancel_futures=True)


def test_audit_capacity_reserves_repair_slot_and_alternates_at_one(
    tmp_path: Path,
) -> None:
    project_store = MagicMock()
    project_store.list_all.return_value = []
    orchestrator = Orchestrator(
        ServiceConfig(
            workspace_root=str(tmp_path / "workspace"),
            max_concurrent_agents=4,
            audit_non_audit_reserved_slots=1,
            duplicate_preflight_max_agents=0,
        ),
        str(tmp_path / "WORKFLOW.md"),
        project_store=project_store,
        state_path=str(tmp_path / "service_state.json"),
    )
    try:
        orchestrator._available_slots = MagicMock(return_value=4)
        assert orchestrator._audit_lane_reserved_slots(non_audit_ready=True) == 1
        assert orchestrator._audit_lane_reserved_slots(non_audit_ready=False) == 0

        orchestrator.state.max_concurrent_agents = 1
        orchestrator._available_slots.return_value = 1
        orchestrator._maintenance_cursors.pop("single_slot_dispatch_lane", None)
        assert orchestrator._audit_lane_reserved_slots(non_audit_ready=True) == 1
        orchestrator._maintenance_cursors["single_slot_dispatch_lane"] = "audit"
        assert orchestrator._audit_lane_reserved_slots(non_audit_ready=True) == 0
    finally:
        orchestrator._tick_pool.shutdown(wait=True, cancel_futures=True)
        orchestrator._refresh_pool.shutdown(wait=True, cancel_futures=True)


@pytest.mark.asyncio
async def test_project_fetch_failure_cannot_clear_last_complete_audit_health(
    tmp_path: Path,
) -> None:
    """One unreadable project makes the aggregate audit scan incomplete."""
    project_store = MagicMock()
    project_store.list_all.return_value = []
    orchestrator = Orchestrator(
        ServiceConfig(
            workspace_root=str(tmp_path / "workspace"),
            duplicate_preflight_max_agents=0,
        ),
        str(tmp_path / "WORKFLOW.md"),
        project_store=project_store,
        state_path=str(tmp_path / "service_state.json"),
    )
    project_store.list_all.return_value = [
        SimpleNamespace(id="project-a"),
        SimpleNamespace(id="project-b"),
    ]
    visible = Issue(
        id="issue-visible",
        identifier="TASK-VISIBLE",
        title="Visible audit candidate",
        state="In Validation",
        created_at=datetime.now(timezone.utc),
    )
    healthy_tracker = MagicMock()
    healthy_tracker.fetch_issues_by_states.return_value = [visible]
    store = MagicMock()
    store.read.return_value = SimpleNamespace(
        pending_chain=[],
        is_quarantined=False,
        unknown_fields={},
    )

    def _tracker_for_project(project_id: str):
        if project_id == "project-b":
            raise RuntimeError("tracker unavailable")
        return healthy_tracker

    try:
        orchestrator._refresh_terminal_audit_health(
            [_aged_pending_observation()],
            scan_complete=True,
            scan_error_count=0,
        )
        with (
            patch.object(orchestrator, "_available_slots", return_value=1),
            patch.object(
                orchestrator,
                "_dispatch_is_blocked",
                return_value=False,
            ),
            patch.object(
                orchestrator,
                "_tracker_for_project",
                side_effect=_tracker_for_project,
            ),
            patch.object(orchestrator, "_audit_store", return_value=store),
        ):
            await orchestrator._dispatch_audit_lane()

        health = orchestrator._audit_health
        assert visible.project_id == "project-a"
        assert orchestrator._audit_metrics["discovered_candidate_count"] == 1
        assert orchestrator._audit_metrics["scanned_candidate_count"] == 1
        assert orchestrator._audit_metrics["candidate_scan_complete"] is False
        assert orchestrator._audit_metrics["pending_count"] == 1
        assert health.pending_count == 1
        assert health.stale_pending_count == 1
        assert health.oldest_pending_age_seconds is not None
        assert health.scan_complete is False
        assert health.scan_error_count == 1
        sources = {str(alert.get("source", "")) for alert in orchestrator._alerts}
        assert HEALTH_ALERT_PREFIX + "backlog_age" in sources
        assert HEALTH_ALERT_PREFIX + "scan" in sources
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
        orchestrator.config.audit_attempt_ttl = 60
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
