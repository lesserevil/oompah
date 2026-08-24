"""Authoritative workflow liveness projection and alert contracts."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import pytest

from oompah.work_decision import PermittedAction, UnmetPrerequisite, WorkDecision
from oompah.workflow_contract import TaskDisposition, WorkflowOwner
from oompah.workflow_facts import (
    FactDomain,
    FactObservation,
    REQUIRED_FACT_DOMAINS,
    WorkflowFacts,
)
from oompah.workflow_liveness_metrics import (
    LIVENESS_STATE_SCHEMA_VERSION,
    DecisionLivenessFacts,
    WorkflowLivenessTracker,
    workflow_liveness_health_alerts,
)
from oompah.workflow_reasons import AlertSeverity, LIVENESS_SLOS


NOW = datetime(2026, 8, 5, 12, tzinfo=timezone.utc)


def _revision(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _decision(
    task_id: str = "TASK-1",
    *,
    project_id: str = "project-a",
    status: str = "Open",
    disposition: TaskDisposition = TaskDisposition.RUNNABLE,
    reason_code: str = "dispatch.eligible",
    owner: WorkflowOwner = WorkflowOwner.DISPATCHER,
    evidence_revision: str = "evidence-1",
    deadline: datetime | None = None,
    action_required: bool = False,
    alert_level: AlertSeverity = AlertSeverity.NONE,
    durable_jobs: tuple[str, ...] = (),
) -> WorkDecision:
    return WorkDecision(
        project_id=project_id,
        task_id=task_id,
        status=status,
        disposition=disposition,
        reason_code=reason_code,
        responsible_owner=owner,
        unmet_prerequisites=(),
        evidence_revision=_revision(evidence_revision),
        next_reassessment_at=(deadline or (NOW + timedelta(minutes=2))).isoformat(),
        permitted_actions=(PermittedAction.CLAIM_IMPLEMENTATION,),
        action_required=action_required,
        alert_level=alert_level,
        durable_jobs=durable_jobs,
    )


def _action_required(
    task_id: str = "TASK-1",
    *,
    project_id: str = "project-a",
    alert_level: AlertSeverity = AlertSeverity.WARNING,
) -> WorkDecision:
    return WorkDecision(
        project_id=project_id,
        task_id=task_id,
        status="Needs Human",
        disposition=TaskDisposition.ACTION_REQUIRED,
        reason_code="operator.action_required",
        responsible_owner=WorkflowOwner.OPERATOR,
        unmet_prerequisites=(
            UnmetPrerequisite("operator.action", task_id),
        ),
        evidence_revision=_revision("operator-evidence"),
        next_reassessment_at=(NOW + timedelta(minutes=15)).isoformat(),
        permitted_actions=(PermittedAction.RESOLVE_OPERATOR_ACTION,),
        action_required=True,
        alert_level=alert_level,
    )


def _recovery(task_id: str = "TASK-1") -> WorkDecision:
    return WorkDecision(
        project_id="project-a",
        task_id=task_id,
        status="In Validation",
        disposition=TaskDisposition.RETRY_SCHEDULED,
        reason_code="validation.retry_scheduled",
        responsible_owner=WorkflowOwner.AUDITOR,
        unmet_prerequisites=(),
        evidence_revision=_revision("retry-evidence"),
        next_reassessment_at=(NOW + timedelta(minutes=10)).isoformat(),
        permitted_actions=(PermittedAction.RETRY_AUDIT,),
        action_required=False,
        alert_level=AlertSeverity.INFO,
        durable_jobs=("audit_recovery",),
    )


def _observe(
    tracker: WorkflowLivenessTracker,
    decisions: tuple[WorkDecision, ...],
    *,
    expected: tuple[tuple[str, str], ...] | None = None,
    generation: int = 1,
    now: datetime = NOW,
    source_scan_complete: bool = True,
    decision_facts: dict[tuple[str, str], DecisionLivenessFacts] | None = None,
    source_errors: dict[str, str] | None = None,
    excluded_projects: dict[str, str] | None = None,
    reconciliation_complete: bool = True,
    required_recovery_count: int = 0,
    materialized_recovery_count: int = 0,
    source_scan_deferred: bool = False,
):
    identities = expected or tuple(
        (decision.project_id, decision.task_id) for decision in decisions
    )
    return tracker.observe(
        decisions,
        expected_identities=identities,
        snapshot_generation=generation,
        source_scan_complete=source_scan_complete,
        reconciliation_complete=reconciliation_complete,
        required_recovery_count=required_recovery_count,
        materialized_recovery_count=materialized_recovery_count,
        decision_facts=decision_facts,
        source_errors=source_errors,
        excluded_projects=excluded_projects,
        source_scan_deferred=source_scan_deferred,
        now=now,
    )


def test_empty_complete_coverage_is_healthy_and_quiet():
    tracker = WorkflowLivenessTracker(clock=lambda: NOW)

    health = _observe(tracker, ())

    assert health.healthy
    assert health.scan_complete
    assert health.total_nonterminal_count == 0
    assert workflow_liveness_health_alerts(health) == []


def test_publication_deferred_scan_finalizes_when_fully_reconciled():
    # OOMPAH-1331: a scan that is only "incomplete" because publication
    # deferred already-covered tasks (terminal-audit disposition changes)
    # must not leave restart reconstruction pending forever with a phantom
    # unexplained divergence. With no source errors, reconciliation
    # complete, no missing decisions, and full recovery materialization,
    # the tracker must finalize.
    tracker = WorkflowLivenessTracker(clock=lambda: NOW)

    health = _observe(
        tracker,
        (),
        source_scan_complete=False,
        source_scan_deferred=True,
        reconciliation_complete=True,
        required_recovery_count=83,
        materialized_recovery_count=83,
    )

    assert health.scan_complete
    assert health.restart_reconstruction_pending is False
    assert health.current_divergence_count == 0
    assert health.unexplained_count == 0
    assert health.status != "invariant_breach"


def test_non_deferred_incomplete_scan_still_fails_closed():
    # A genuinely incomplete scan (not a publication deferral) must remain
    # fail-closed even when recovery is fully materialized.
    tracker = WorkflowLivenessTracker(clock=lambda: NOW)

    health = _observe(
        tracker,
        (),
        source_scan_complete=False,
        source_scan_deferred=False,
        reconciliation_complete=True,
        required_recovery_count=83,
        materialized_recovery_count=83,
    )

    assert health.scan_complete is False


def test_exact_authoritative_deadline_is_healthy_then_one_second_late_is_not():
    tracker = WorkflowLivenessTracker(clock=lambda: NOW)
    decision = _decision(deadline=NOW)

    boundary = _observe(tracker, (decision,))
    overdue = tracker.snapshot(now=NOW + timedelta(seconds=1))

    assert boundary.healthy
    assert boundary.tasks[0].deadline_seconds_remaining == 0
    assert boundary.tasks[0].reassessment_lateness_seconds == 0
    assert not overdue.healthy
    assert overdue.status == "overdue"
    assert overdue.tasks[0].reassessment_lateness_seconds == 1
    # A timer becoming due is not an operator warning until the controller
    # emits an explicit action-required decision.
    assert workflow_liveness_health_alerts(overdue) == []


def test_successful_unchanged_reassessment_renews_liveness_deadline():
    tracker = WorkflowLivenessTracker(
        snapshot_stale_seconds=10_000,
        clock=lambda: NOW,
    )
    first = _decision(deadline=NOW + timedelta(seconds=120))
    refreshed = _decision(deadline=NOW + timedelta(seconds=180))

    _observe(tracker, (first,))
    second = _observe(
        tracker,
        (refreshed,),
        generation=2,
        now=NOW + timedelta(seconds=60),
    )
    overdue = tracker.snapshot(now=NOW + timedelta(seconds=121))

    assert second.tasks[0].last_progress_at == NOW.isoformat()
    assert second.tasks[0].next_reassessment_at == (
        NOW + timedelta(seconds=180)
    ).isoformat()
    assert overdue.healthy
    assert overdue.tasks[0].deadline_seconds_remaining == 59


def test_owned_without_real_job_or_lease_uses_reassessment_deadline():
    tracker = WorkflowLivenessTracker(
        snapshot_stale_seconds=10_000,
        clock=lambda: NOW,
    )
    owned = _decision(
        status="In Review",
        disposition=TaskDisposition.OWNED,
        reason_code="review.monitoring",
        owner=WorkflowOwner.REVIEW_MONITOR,
        deadline=NOW + timedelta(seconds=10),
    )

    initial = _observe(tracker, (owned,))
    overdue = tracker.snapshot(now=NOW + timedelta(seconds=11))

    assert not initial.tasks[0].active_job
    assert initial.tasks[0].deadline_kind == "reassessment"
    assert overdue.tasks[0].overdue
    assert overdue.status == "overdue"


def test_review_monitor_projects_only_explicit_durable_job_evidence():
    decision = _decision(
        status="In Review",
        disposition=TaskDisposition.OWNED,
        reason_code="review.monitoring",
        owner=WorkflowOwner.REVIEW_MONITOR,
    )
    observations = {
        domain: FactObservation.missing(
            domain,
            observed_at=NOW.isoformat(),
            source="test",
        )
        for domain in REQUIRED_FACT_DOMAINS
    }
    observations[FactDomain.REVIEW_CI] = FactObservation.known(
        FactDomain.REVIEW_CI,
        {
            "review_id": "review-1",
            "job_id": "review-job-1",
            "actively_working": True,
        },
        observed_at=NOW.isoformat(),
        source="workflow_job_store",
    )
    facts = WorkflowFacts(
        "project-a", "TASK-1", NOW.isoformat(), observations
    )

    projected = DecisionLivenessFacts.from_workflow_facts(decision, facts)

    assert projected.active_job
    assert projected.active_job_id == "review-job-1"


def test_reconciliation_truncation_with_unmaterialized_recovery_fails_closed():
    tracker = WorkflowLivenessTracker(clock=lambda: NOW)
    recovery = _recovery()

    health = _observe(
        tracker,
        (recovery,),
        reconciliation_complete=False,
        required_recovery_count=1,
        materialized_recovery_count=0,
    )

    assert not health.scan_complete
    assert health.status == "incomplete"
    assert not health.reconciliation_complete
    assert health.current_divergence_count == 1


def test_projection_uses_contract_slo_and_authoritative_deadline_kind():
    tracker = WorkflowLivenessTracker(clock=lambda: NOW)
    open_health = _observe(tracker, (_decision(),))

    assert open_health.tasks[0].slo_key == "dispatch_latency"
    assert open_health.tasks[0].slo_seconds == LIVENESS_SLOS[
        "dispatch_latency"
    ].max_reassessment_seconds
    assert open_health.tasks[0].deadline_kind == "reassessment"

    recovery_health = _observe(
        tracker,
        (_recovery(),),
        generation=2,
        decision_facts={
            ("project-a", "TASK-1"): DecisionLivenessFacts(
                retry_due_at=(NOW + timedelta(minutes=4)).isoformat(),
                recovery_attempt=2,
            )
        },
    )
    assert recovery_health.tasks[0].deadline_kind == "retry"
    assert recovery_health.tasks[0].retry_due_at == (
        NOW + timedelta(minutes=4)
    ).isoformat()
    assert recovery_health.tasks[0].recovery_attempt == 2


def test_normal_owned_and_recovery_decisions_are_healthy_without_warnings():
    tracker = WorkflowLivenessTracker(clock=lambda: NOW)
    owned = WorkDecision(
        project_id="project-a",
        task_id="TASK-owned",
        status="In Progress",
        disposition=TaskDisposition.OWNED,
        reason_code="implementation.active",
        responsible_owner=WorkflowOwner.IMPLEMENTER,
        unmet_prerequisites=(),
        evidence_revision=_revision("lease-evidence"),
        next_reassessment_at=(NOW + timedelta(minutes=15)).isoformat(),
        permitted_actions=(PermittedAction.CONTINUE_IMPLEMENTATION,),
        action_required=False,
        alert_level=AlertSeverity.NONE,
    )

    health = _observe(
        tracker,
        (owned, _recovery("TASK-retry")),
        decision_facts={
            ("project-a", "TASK-owned"): DecisionLivenessFacts(
                active_job=True, active_job_id="implementation-job"
            ),
            ("project-a", "TASK-retry"): DecisionLivenessFacts(
                retry_due_at=(NOW + timedelta(minutes=10)).isoformat()
            ),
        },
    )

    assert health.healthy
    assert health.owned_count == 1
    assert health.recovery_count == 1
    assert {item.deadline_kind for item in health.tasks} == {"active_job", "retry"}
    assert workflow_liveness_health_alerts(health) == []


def test_active_job_is_not_false_overdue_when_reassessment_timer_passes():
    tracker = WorkflowLivenessTracker(
        snapshot_stale_seconds=10_000,
        clock=lambda: NOW,
    )
    owned = WorkDecision(
        project_id="project-a",
        task_id="TASK-owned",
        status="In Progress",
        disposition=TaskDisposition.OWNED,
        reason_code="implementation.active",
        responsible_owner=WorkflowOwner.IMPLEMENTER,
        unmet_prerequisites=(),
        evidence_revision=_revision("live-process"),
        next_reassessment_at=(NOW + timedelta(seconds=10)).isoformat(),
        permitted_actions=(PermittedAction.CONTINUE_IMPLEMENTATION,),
        action_required=False,
        alert_level=AlertSeverity.NONE,
    )

    _observe(
        tracker,
        (owned,),
        decision_facts={
            ("project-a", "TASK-owned"): DecisionLivenessFacts(
                active_job=True, active_job_id="implementation-job"
            )
        },
    )
    health = tracker.snapshot(now=NOW + timedelta(seconds=11))

    assert health.tasks[0].active_job
    assert health.tasks[0].reassessment_lateness_seconds == 1
    assert health.tasks[0].deadline_kind == "active_job"
    assert not health.tasks[0].overdue
    assert health.healthy


def test_actual_lease_expiry_controls_owned_task_overdue_health():
    tracker = WorkflowLivenessTracker(
        snapshot_stale_seconds=10_000,
        clock=lambda: NOW,
    )
    owned = WorkDecision(
        project_id="project-a",
        task_id="TASK-owned",
        status="In Progress",
        disposition=TaskDisposition.OWNED,
        reason_code="implementation.active",
        responsible_owner=WorkflowOwner.DIRECT_OWNER,
        unmet_prerequisites=(),
        evidence_revision=_revision("claim"),
        next_reassessment_at=(NOW + timedelta(minutes=15)).isoformat(),
        permitted_actions=(PermittedAction.CONTINUE_IMPLEMENTATION,),
        action_required=False,
        alert_level=AlertSeverity.NONE,
    )
    lease_deadline = NOW + timedelta(seconds=20)

    _observe(
        tracker,
        (owned,),
        decision_facts={
            ("project-a", "TASK-owned"): DecisionLivenessFacts(
                lease_expires_at=lease_deadline.isoformat()
            )
        },
    )
    health = tracker.snapshot(now=lease_deadline + timedelta(seconds=1))

    assert health.tasks[0].deadline_kind == "lease"
    assert health.tasks[0].effective_deadline_at == lease_deadline.isoformat()
    assert health.tasks[0].deadline_lateness_seconds == 1
    assert health.status == "overdue"


def test_real_lease_bounds_active_job_when_both_are_present():
    tracker = WorkflowLivenessTracker(
        snapshot_stale_seconds=10_000,
        clock=lambda: NOW,
    )
    owned = _decision(
        status="In Progress",
        disposition=TaskDisposition.OWNED,
        reason_code="implementation.active",
        owner=WorkflowOwner.IMPLEMENTER,
    )
    lease = NOW + timedelta(seconds=10)

    initial = _observe(
        tracker,
        (owned,),
        decision_facts={
            ("project-a", "TASK-1"): DecisionLivenessFacts(
                active_job=True,
                active_job_id="implementation-job",
                lease_expires_at=lease.isoformat(),
            )
        },
    )
    overdue = tracker.snapshot(now=lease + timedelta(seconds=1))

    assert initial.tasks[0].deadline_kind == "lease"
    assert overdue.tasks[0].overdue


def test_only_action_required_decisions_create_dashboard_warning():
    tracker = WorkflowLivenessTracker(clock=lambda: NOW)

    health = _observe(
        tracker,
        (_recovery("TASK-retry"), _action_required("TASK-human")),
    )
    alerts = workflow_liveness_health_alerts(health)

    assert health.status == "action_required"
    assert health.action_required_count == 1
    assert len(alerts) == 1
    assert alerts[0]["source"] == "workflow_liveness:action_required"
    assert alerts[0]["level"] == "warning"
    assert alerts[0]["action_required"] is True
    assert alerts[0]["tasks"] == ["project-a/TASK-human"]


def test_critical_action_required_decision_preserves_controller_severity():
    tracker = WorkflowLivenessTracker(clock=lambda: NOW)

    health = _observe(
        tracker,
        (_action_required(alert_level=AlertSeverity.CRITICAL),),
    )

    assert workflow_liveness_health_alerts(health)[0]["level"] == "critical"


def test_reassessment_recovery_and_escalation_events_survive_refreshes():
    tracker = WorkflowLivenessTracker(clock=lambda: NOW)
    identity = (("project-a", "TASK-1"),)

    first = _observe(tracker, (_recovery(),), expected=identity)
    second = _observe(
        tracker,
        (_recovery(),),
        expected=identity,
        generation=2,
        now=NOW + timedelta(seconds=1),
    )
    escalated = _observe(
        tracker,
        (_action_required(),),
        expected=identity,
        generation=3,
        now=NOW + timedelta(seconds=2),
    )

    assert first.recovery_count == 1
    assert second.recovery_count == 1
    assert second.reassessment_count == 2
    assert escalated.recovery_count == 1
    assert escalated.escalation_count == 1
    assert escalated.tasks[0].reassessment_count == 3


def test_progress_timestamps_track_evidence_and_semantic_changes_correctly():
    tracker = WorkflowLivenessTracker(clock=lambda: NOW)
    identity = (("project-a", "TASK-1"),)
    initial = _observe(tracker, (_decision(),), expected=identity)
    unchanged = _observe(
        tracker,
        (_decision(deadline=NOW + timedelta(minutes=3)),),
        expected=identity,
        generation=2,
        now=NOW + timedelta(seconds=10),
    )
    refreshed = _observe(
        tracker,
        (_decision(evidence_revision="evidence-2"),),
        expected=identity,
        generation=3,
        now=NOW + timedelta(seconds=20),
    )
    changed = _observe(
        tracker,
        (
            _decision(
                status="In Review",
                disposition=TaskDisposition.OWNED,
                reason_code="review.monitoring",
                owner=WorkflowOwner.REVIEW_MONITOR,
                evidence_revision="review-evidence",
            ),
        ),
        expected=identity,
        generation=4,
        now=NOW + timedelta(seconds=30),
    )

    assert unchanged.tasks[0].first_observed_at == initial.tasks[0].first_observed_at
    assert unchanged.tasks[0].last_progress_at == initial.tasks[0].last_progress_at
    assert refreshed.tasks[0].first_observed_at == initial.tasks[0].first_observed_at
    assert refreshed.tasks[0].last_progress_at == (
        NOW + timedelta(seconds=20)
    ).isoformat()
    assert changed.tasks[0].first_observed_at == (
        NOW + timedelta(seconds=30)
    ).isoformat()
    assert changed.tasks[0].decision_age_seconds == 0


def test_cross_generation_partial_windows_never_claim_complete_coverage():
    tracker = WorkflowLivenessTracker(max_task_records=4, clock=lambda: NOW)
    decisions = tuple(_decision(f"TASK-{number}") for number in range(4))
    expected = tuple(
        (decision.project_id, decision.task_id) for decision in decisions
    )

    first = _observe(tracker, decisions[:2], expected=expected)
    second = _observe(
        tracker,
        decisions[2:],
        expected=expected,
        generation=2,
        now=NOW + timedelta(seconds=1),
    )

    assert not first.scan_complete
    assert first.status == "incomplete"
    complete = _observe(
        tracker,
        decisions,
        expected=expected,
        generation=3,
        now=NOW + timedelta(seconds=2),
    )

    assert not second.scan_complete
    assert second.status == "incomplete"
    assert second.missing_decision_count == 2
    assert complete.scan_complete
    assert complete.healthy
    assert complete.tracked_task_count == 4


def test_source_scan_failure_is_fail_closed_and_never_invents_warning():
    tracker = WorkflowLivenessTracker(clock=lambda: NOW)
    healthy = _observe(tracker, (_decision(),))
    incomplete = _observe(
        tracker,
        (_decision(),),
        generation=2,
        source_scan_complete=False,
        source_errors={"project-b": "TimeoutError"},
        now=NOW + timedelta(seconds=1),
    )
    failed = tracker.record_scan_failure(
        "tracker timeout", now=NOW + timedelta(seconds=2)
    )

    assert healthy.healthy
    assert incomplete.status == "incomplete"
    assert not incomplete.scan_complete
    assert incomplete.source_error_count == 1
    assert incomplete.projects["project-b"]["source_error"] == "TimeoutError"
    assert failed.status == "incomplete"
    assert failed.last_error == "tracker timeout"
    assert workflow_liveness_health_alerts(failed) == []


def test_failed_project_keeps_last_known_attribution_until_fresh_scan():
    tracker = WorkflowLivenessTracker(clock=lambda: NOW)
    initial = (
        _decision("TASK-a", project_id="project-a"),
        _decision("TASK-b", project_id="project-b"),
    )
    _observe(tracker, initial)

    partial = _observe(
        tracker,
        (initial[0],),
        generation=2,
        source_scan_complete=False,
        source_errors={"project-b": "TimeoutError"},
        now=NOW + timedelta(seconds=1),
    )
    recovered = _observe(
        tracker,
        (initial[0],),
        generation=3,
        now=NOW + timedelta(seconds=2),
    )

    assert {item.project_id for item in partial.tasks} == {
        "project-a",
        "project-b",
    }
    assert partial.projects["project-b"]["source_error"] == "TimeoutError"
    assert not partial.scan_complete
    assert {item.project_id for item in recovered.tasks} == {"project-a"}
    assert recovered.healthy


def test_schema_v6_exclusion_round_trip_suspends_paused_deadlines_and_resumes():
    tracker = WorkflowLivenessTracker(
        snapshot_stale_seconds=10_000,
        clock=lambda: NOW,
    )
    active = _decision(
        "TASK-active",
        project_id="project-active",
        deadline=NOW + timedelta(seconds=100),
    )
    paused = _decision(
        "TASK-paused",
        project_id="project-paused",
        deadline=NOW + timedelta(seconds=1),
    )
    _observe(tracker, (active, paused))

    excluded = _observe(
        tracker,
        (active,),
        generation=2,
        now=NOW + timedelta(seconds=2),
        excluded_projects={"project-paused": "project_paused"},
    )
    after_deadline = tracker.snapshot(now=NOW + timedelta(seconds=3))
    state = tracker.to_state()

    assert excluded.healthy
    assert excluded.scan_complete
    assert excluded.coverage_scope == "active_projects"
    assert not excluded.global_coverage_complete
    assert excluded.active_project_count == 1
    assert excluded.excluded_projects == {
        "project-paused": "project_paused"
    }
    assert excluded.excluded_project_count == 1
    assert excluded.omitted_excluded_project_count == 0
    assert excluded.excluded_task_count == 1
    assert excluded.total_nonterminal_count == 2
    assert excluded.tracked_task_count == 1
    assert excluded.omitted_task_count == 0
    assert {item.task_id for item in excluded.tasks} == {"TASK-active"}
    paused_summary = excluded.projects["project-paused"]
    assert paused_summary["coverage_state"] == "excluded"
    assert paused_summary["exclusion_reason"] == "project_paused"
    assert paused_summary["last_known_task_count"] == 1
    assert paused_summary["task_count"] == 0
    assert paused_summary["tracked_task_count"] == 0
    assert paused_summary["omitted_task_count"] == 0
    assert paused_summary["action_required_count"] == 0
    assert paused_summary["overdue_count"] == 0
    assert after_deadline.healthy
    assert after_deadline.overdue_count == 0
    assert {item["task_id"] for item in state["records"]} == {
        "TASK-active",
        "TASK-paused",
    }
    assert state["schema_version"] == LIVENESS_STATE_SCHEMA_VERSION == 6
    assert state["coverage_scope"] == "active_projects"
    assert not state["global_coverage_complete"]
    assert state["active_project_count"] == 1
    assert state["excluded_task_count"] == 1
    assert state["excluded_projects"] == {
        "project-paused": "project_paused"
    }

    restarted = WorkflowLivenessTracker(
        snapshot_stale_seconds=10_000,
        clock=lambda: NOW + timedelta(seconds=4),
    )
    restarted.restore(state, now=NOW + timedelta(seconds=4))
    restored = restarted.snapshot(now=NOW + timedelta(seconds=4))

    assert restored.excluded_projects == excluded.excluded_projects
    assert restored.excluded_project_count == 1
    assert restored.excluded_task_count == 1
    assert restored.active_project_count == 1
    assert {item.task_id for item in restored.tasks} == {"TASK-active"}
    assert not restored.scan_complete

    resumed = _observe(
        restarted,
        (
            active,
            _decision(
                "TASK-paused",
                project_id="project-paused",
                evidence_revision="paused-resumed",
                deadline=NOW + timedelta(minutes=10),
            ),
        ),
        generation=3,
        now=NOW + timedelta(seconds=5),
    )

    assert resumed.healthy
    assert resumed.scan_complete
    assert resumed.global_coverage_complete
    assert resumed.active_project_count == 2
    assert resumed.excluded_projects == {}
    assert resumed.excluded_project_count == 0
    assert resumed.excluded_task_count == 0
    assert {item.task_id for item in resumed.tasks} == {
        "TASK-active",
        "TASK-paused",
    }


def test_exclusion_overlap_rejection_never_changes_tracker_state():
    tracker = WorkflowLivenessTracker(clock=lambda: NOW)
    _observe(tracker, (_decision(),))
    before_state = tracker.to_state()
    before_health = tracker.snapshot(now=NOW).to_dict()

    invalid_observations = (
        {
            "decisions": (),
            "expected": (),
            "source_errors": {"project-paused": "TimeoutError"},
        },
        {
            "decisions": (),
            "expected": (("project-paused", "TASK-paused"),),
        },
        {
            "decisions": (
                _decision("TASK-paused", project_id="project-paused"),
            ),
            "expected": (("project-a", "TASK-1"),),
        },
    )
    for invalid in invalid_observations:
        with pytest.raises(ValueError, match="overlap|escaped"):
            _observe(
                tracker,
                invalid["decisions"],
                expected=invalid["expected"],
                generation=2,
                source_scan_complete=not bool(invalid.get("source_errors")),
                source_errors=invalid.get("source_errors"),
                excluded_projects={"project-paused": "project_paused"},
                now=NOW + timedelta(seconds=1),
            )
        assert tracker.to_state() == before_state
        assert tracker.snapshot(now=NOW).to_dict() == before_health


def test_exclusion_caps_preserve_exact_counts_without_active_omissions():
    tracker = WorkflowLivenessTracker(
        max_task_records=10,
        max_project_records=1,
        clock=lambda: NOW,
    )
    decisions = tuple(
        _decision(f"TASK-{name}", project_id=f"project-{name}")
        for name in ("active", "b", "c")
    )
    _observe(tracker, decisions)

    health = _observe(
        tracker,
        (decisions[0],),
        generation=2,
        now=NOW + timedelta(seconds=1),
        excluded_projects={
            "project-b": "project_paused",
            "project-c": "project_paused",
            "project-d": "project_paused",
        },
    )
    state = tracker.to_state()

    assert health.healthy
    assert health.active_project_count == 1
    assert health.excluded_project_count == 3
    assert health.excluded_task_count == 2
    assert len(health.excluded_projects) == 1
    assert health.omitted_excluded_project_count == 2
    assert health.total_nonterminal_count == 3
    assert health.tracked_task_count == 1
    assert health.omitted_task_count == 0
    assert state["excluded_project_count"] == 3
    assert len(state["excluded_projects"]) == 1
    assert state["excluded_task_count"] == 2


def test_exclusion_cap_restart_prioritizes_retained_paused_record_and_exact_count():
    tracker = WorkflowLivenessTracker(
        max_task_records=2,
        max_project_records=1,
        snapshot_stale_seconds=10_000,
        clock=lambda: NOW,
    )
    active = _decision("TASK-active", project_id="project-0-active")
    omitted_a = _decision("TASK-a", project_id="project-a")
    omitted_b = _decision("TASK-b", project_id="project-b")
    retained_late = _action_required("TASK-z", project_id="project-z-paused")
    _observe(tracker, (active, omitted_a, omitted_b, retained_late))
    _observe(
        tracker,
        (active,),
        generation=2,
        now=NOW + timedelta(seconds=1),
        excluded_projects={
            "project-a": "paused",
            "project-b": "paused",
            "project-z-paused": "paused",
        },
    )
    state = tracker.to_state()

    assert state["excluded_project_ids"][0] == "project-z-paused"
    assert state["excluded_task_count"] == 3

    restarted = WorkflowLivenessTracker(
        max_task_records=2,
        max_project_records=1,
        snapshot_stale_seconds=10_000,
        clock=lambda: NOW + timedelta(seconds=2),
    )
    restarted.restore(state, now=NOW + timedelta(seconds=2))
    health = restarted.snapshot(now=NOW + timedelta(seconds=2))

    assert {item.task_id for item in health.tasks} == {"TASK-active"}
    assert health.action_required_count == 0
    assert health.overdue_count == 0
    assert health.excluded_project_count == 3
    assert health.excluded_task_count == 3
    assert health.total_nonterminal_count == 4
    assert health.tracked_task_count == 1
    assert health.omitted_task_count == 0


def test_source_failure_and_paused_exclusion_remain_distinct_and_fail_closed():
    tracker = WorkflowLivenessTracker(clock=lambda: NOW)
    decisions = (
        _decision("TASK-active", project_id="project-active"),
        _decision("TASK-paused", project_id="project-paused"),
        _decision("TASK-failed", project_id="project-failed"),
    )
    _observe(tracker, decisions)

    health = _observe(
        tracker,
        (decisions[0],),
        generation=2,
        now=NOW + timedelta(seconds=1),
        source_scan_complete=False,
        source_errors={"project-failed": "TimeoutError"},
        excluded_projects={"project-paused": "project_paused"},
    )

    assert health.status == "incomplete"
    assert not health.scan_complete
    assert not health.global_coverage_complete
    assert health.source_errors == {"project-failed": "TimeoutError"}
    assert health.source_error_count == 1
    assert health.excluded_projects == {
        "project-paused": "project_paused"
    }
    assert health.excluded_project_count == 1
    assert set(health.source_errors).isdisjoint(health.excluded_projects)
    assert {item.project_id for item in health.tasks} == {
        "project-active",
        "project-failed",
    }
    assert health.projects["project-paused"]["coverage_state"] == "excluded"
    assert health.projects["project-failed"]["source_error"] == "TimeoutError"


def test_task_cardinality_cap_is_enforced_and_action_required_is_retained():
    tracker = WorkflowLivenessTracker(max_task_records=2, clock=lambda: NOW)
    decisions = (
        _decision("TASK-normal-1"),
        _decision("TASK-normal-2"),
        _action_required("TASK-human"),
    )

    health = _observe(tracker, decisions)

    assert health.tracked_task_count == 2
    assert health.omitted_task_count == 1
    assert not health.scan_complete
    assert any(item.task_id == "TASK-human" for item in health.tasks)
    assert health.action_required_count == 1


def test_over_cap_replaces_rows_outside_current_membership():
    tracker = WorkflowLivenessTracker(max_task_records=2, clock=lambda: NOW)
    _observe(
        tracker,
        (_decision("OLD-1"), _decision("OLD-2")),
    )

    current = (
        _decision("NEW-1"),
        _decision("NEW-2"),
        _decision("NEW-3"),
    )
    health = _observe(
        tracker,
        current,
        generation=2,
        now=NOW + timedelta(seconds=1),
    )

    assert {item.task_id for item in health.tasks} <= {
        "NEW-1",
        "NEW-2",
        "NEW-3",
    }
    assert health.tracked_task_count == 2
    assert health.omitted_task_count == 1
    assert not health.scan_complete


def test_live_reconfigure_enforces_smaller_cap_and_new_stale_threshold():
    tracker = WorkflowLivenessTracker(
        max_task_records=3,
        snapshot_stale_seconds=100,
        clock=lambda: NOW,
    )
    _observe(
        tracker,
        tuple(_decision(f"TASK-{number}") for number in range(3)),
    )

    tracker.reconfigure(
        max_task_records=2,
        max_project_records=1,
        snapshot_stale_seconds=5,
    )
    health = tracker.snapshot(now=NOW + timedelta(seconds=6))

    assert health.tracked_task_count == 2
    assert health.omitted_task_count == 1
    assert health.stale
    assert not health.scan_complete
    assert health.to_dict()["limits"] == {
        "max_task_records": 2,
        "max_project_records": 1,
        "snapshot_stale_seconds": 5,
    }


def test_project_cardinality_cap_is_enforced_after_exact_aggregation():
    tracker = WorkflowLivenessTracker(
        max_task_records=10,
        max_project_records=2,
        clock=lambda: NOW,
    )
    decisions = tuple(
        _decision(f"TASK-{number}", project_id=f"project-{number}")
        for number in range(3)
    )

    health = _observe(tracker, decisions)

    assert health.scan_complete
    assert len(health.projects) == 2
    assert health.omitted_project_count == 1


def test_source_error_attribution_is_bounded_without_losing_global_count():
    tracker = WorkflowLivenessTracker(
        max_project_records=2,
        clock=lambda: NOW,
    )

    health = _observe(
        tracker,
        (),
        source_scan_complete=False,
        source_errors={
            "project-a": "TimeoutError",
            "project-b": "TrackerError",
            "project-c": "PermissionError",
        },
    )

    assert health.source_error_count == 3
    assert len(health.source_errors) == 2
    assert health.omitted_source_error_count == 1
    assert health.divergence_count == 3
    assert health.status == "incomplete"


def test_cumulative_events_survive_terminal_removal_cap_eviction_and_restart():
    tracker = WorkflowLivenessTracker(max_task_records=1, clock=lambda: NOW)
    _observe(tracker, (_recovery("TASK-recovery"),))
    _observe(
        tracker,
        (_action_required("TASK-human"), _decision("TASK-normal")),
        generation=2,
        now=NOW + timedelta(seconds=1),
    )
    state = tracker.to_state()
    restored = WorkflowLivenessTracker(
        max_task_records=1,
        clock=lambda: NOW + timedelta(seconds=2),
    )
    restored.restore(state, now=NOW + timedelta(seconds=2))
    health = restored.snapshot(now=NOW + timedelta(seconds=2))

    assert health.recovery_count == 1
    assert health.escalation_count == 1
    assert state["cumulative"]["recovery_count"] == 1
    assert state["cumulative"]["escalation_count"] == 1


def test_failed_source_omission_truth_survives_restart():
    tracker = WorkflowLivenessTracker(
        max_project_records=1,
        clock=lambda: NOW,
    )
    failed = _observe(
        tracker,
        (),
        source_scan_complete=False,
        source_errors={
            "project-a": "TimeoutError",
            "project-b": "PermissionError",
            "project-c": "TrackerError",
        },
    )
    restored = WorkflowLivenessTracker(
        max_project_records=1,
        clock=lambda: NOW + timedelta(seconds=1),
    )
    restored.restore(tracker.to_state(), now=NOW + timedelta(seconds=1))
    after_restart = restored.snapshot(now=NOW + timedelta(seconds=1))

    assert failed.source_error_count == 3
    assert failed.omitted_project_count == 2
    assert after_restart.source_error_count == 3
    assert after_restart.omitted_source_error_count == 2
    assert after_restart.omitted_project_count == 2
    assert after_restart.divergence_count == failed.divergence_count


def test_failed_project_membership_above_task_cap_survives_partial_scan_restart():
    tracker = WorkflowLivenessTracker(
        max_task_records=2,
        clock=lambda: NOW,
    )
    project_tasks = tuple(
        _decision(f"TASK-{number}", project_id="project-large")
        for number in range(5)
    )
    initial = _observe(tracker, project_tasks, generation=1)
    partial = _observe(
        tracker,
        (),
        generation=2,
        source_scan_complete=False,
        source_errors={"project-large": "TimeoutError"},
        now=NOW + timedelta(seconds=1),
    )
    restored = WorkflowLivenessTracker(
        max_task_records=2,
        clock=lambda: NOW + timedelta(seconds=2),
    )
    restored.restore(tracker.to_state(), now=NOW + timedelta(seconds=2))
    after_restart = restored.snapshot(now=NOW + timedelta(seconds=2))

    assert initial.total_nonterminal_count == 5
    assert initial.omitted_task_count == 3
    assert partial.total_nonterminal_count == 5
    assert partial.omitted_task_count == 3
    assert partial.projects["project-large"]["task_count"] == 5
    assert partial.projects["project-large"]["tracked_task_count"] == 2
    assert partial.projects["project-large"]["omitted_task_count"] == 3
    assert after_restart.total_nonterminal_count == 5
    assert after_restart.omitted_task_count == 3
    assert restored.to_state()["project_task_counts"] == {
        "project-large": 5
    }


def test_bounded_event_ledger_prevents_recount_beyond_record_cap_after_restart():
    tracker = WorkflowLivenessTracker(max_task_records=1, clock=lambda: NOW)
    recoveries = tuple(_recovery(f"TASK-recovery-{index}") for index in range(12))
    escalations = tuple(
        _action_required(f"TASK-human-{index}") for index in range(12)
    )
    for generation, decision in enumerate(
        (*recoveries, *escalations), start=1
    ):
        _observe(
            tracker,
            (decision,),
            generation=generation,
            now=NOW + timedelta(seconds=generation),
        )
    restored = WorkflowLivenessTracker(
        max_task_records=1,
        clock=lambda: NOW + timedelta(seconds=25),
    )
    restored.restore(tracker.to_state(), now=NOW + timedelta(seconds=25))
    final = None
    for generation, decision in enumerate(
        (*recoveries, *escalations), start=25
    ):
        final = _observe(
            restored,
            (decision,),
            generation=generation,
            now=NOW + timedelta(seconds=generation),
        )

    assert final is not None
    assert final.recovery_count == 12
    assert final.escalation_count == 12
    ledger = restored.to_state()["event_signature_ledger"]
    assert ledger["bit_count"] == 32_768
    assert len(ledger["bits"]) == 8_192


def test_missing_nested_state_stays_fail_closed_across_restart_without_recount():
    first = WorkflowLivenessTracker(clock=lambda: NOW)
    first.restore(None, now=NOW)
    sentinel = first.to_state()

    assert sentinel["history_corrupt"]
    assert set(sentinel["event_signature_ledger"]["bits"]) == {"f"}
    assert first.snapshot(now=NOW).status == "incomplete"

    restarted = WorkflowLivenessTracker(clock=lambda: NOW)
    restarted.restore(sentinel, now=NOW)
    health = _observe(restarted, (_recovery(),), generation=1, now=NOW)

    assert health.status == "overdue"
    assert not health.healthy
    assert health.recovery_count == 0
    assert health.tasks[0].recovery_count == 0
    assert health.tasks[0].last_progress_at == "1970-01-01T00:00:00+00:00"
    assert not restarted.to_state()["history_corrupt"]
    assert set(restarted.to_state()["event_signature_ledger"]["bits"]) == {"f"}


def test_wrong_schema_and_corrupt_nested_records_use_conservative_progress():
    valid = WorkflowLivenessTracker(clock=lambda: NOW)
    _observe(valid, (_recovery(),))
    corrupt_records = valid.to_state()
    corrupt_records["records"] = [{"task_id": "truncated"}]

    for raw in (
        "not-a-mapping",
        {"schema_version": LIVENESS_STATE_SCHEMA_VERSION - 1},
        corrupt_records,
    ):
        restored = WorkflowLivenessTracker(clock=lambda: NOW)
        restored.restore(raw, now=NOW)
        health = _observe(restored, (_recovery(),), generation=2, now=NOW)

        assert health.status == "overdue"
        assert not health.healthy
        assert health.recovery_count == 0
        assert health.tasks[0].recovery_count == 0
        assert health.tasks[0].last_progress_at == (
            "1970-01-01T00:00:00+00:00"
        )


def test_fail_closed_restore_discards_existing_untrusted_cumulative_history():
    tracker = WorkflowLivenessTracker(clock=lambda: NOW)
    initial = _observe(tracker, (_recovery(),))
    assert initial.recovery_count == 1

    tracker.restore("not-a-mapping", now=NOW)
    health = _observe(tracker, (_recovery(),), generation=2, now=NOW)

    assert health.recovery_count == 0
    assert health.tasks[0].recovery_count == 0
    assert set(tracker.to_state()["event_signature_ledger"]["bits"]) == {"f"}


def test_partial_corrupt_restore_keeps_event_aggregates_consistent():
    original = WorkflowLivenessTracker(clock=lambda: NOW)
    _observe(
        original,
        (
            _recovery("TASK-1"),
            _action_required("TASK-2"),
            _recovery("TASK-3"),
        ),
    )
    state = original.to_state()
    state["records"] = [
        {"task_id": "truncated"} if item["task_id"] == "TASK-3" else item
        for item in state["records"]
    ]

    restored = WorkflowLivenessTracker(clock=lambda: NOW)
    restored.restore(state, now=NOW)
    before = restored.snapshot(now=NOW)
    after = _observe(
        restored,
        (_recovery("TASK-1"), _action_required("TASK-2")),
        generation=2,
        now=NOW,
    )

    assert before.recovery_count == 0
    assert before.escalation_count == 0
    assert before.reassessment_count == 0
    assert all(item.recovery_count == 0 for item in before.tasks)
    assert all(item.escalation_count == 0 for item in before.tasks)
    assert all(item.reassessment_count == 0 for item in before.tasks)
    assert before.projects["project-a"]["recovery_count"] == 0
    assert before.projects["project-a"]["escalation_count"] == 0
    assert before.projects["project-a"]["reassessment_count"] == 0
    assert after.recovery_count == sum(item.recovery_count for item in after.tasks)
    assert after.escalation_count == sum(
        item.escalation_count for item in after.tasks
    )
    assert after.reassessment_count == sum(
        item.reassessment_count for item in after.tasks
    )
    assert after.projects["project-a"]["recovery_count"] == after.recovery_count
    assert (
        after.projects["project-a"]["escalation_count"]
        == after.escalation_count
    )
    assert (
        after.projects["project-a"]["reassessment_count"]
        == after.reassessment_count
    )


def test_corrupt_persisted_authority_revisions_cannot_renew_liveness_slo():
    original = WorkflowLivenessTracker(clock=lambda: NOW)
    decision = _decision()
    _observe(original, (decision,))

    for field, corrupt_value in (
        ("semantic_revision", "0" * 63),
        ("evidence_revision", ["0" * 64]),
    ):
        state = original.to_state()
        state["records"][0][field] = corrupt_value
        restored = WorkflowLivenessTracker(clock=lambda: NOW)

        restored.restore(state, now=NOW)
        before_scan = restored.snapshot(now=NOW)
        before_state = restored.to_state()
        refreshed = _observe(
            restored,
            (decision,),
            generation=2,
            now=NOW + timedelta(days=30),
        )

        assert before_scan.status == "incomplete"
        assert before_scan.tasks == ()
        assert before_state["history_corrupt"]
        assert before_state["history_incomplete"]
        assert restored.to_state()["event_signature_ledger"]["bits"] == "f" * 8192
        assert refreshed.status == "overdue"
        assert refreshed.tasks[0].last_progress_at == (
            "1970-01-01T00:00:00+00:00"
        )


def test_corrupt_incoming_evidence_cannot_renew_liveness_slo():
    tracker = WorkflowLivenessTracker(
        snapshot_stale_seconds=10_000,
        clock=lambda: NOW,
    )
    decision = _decision(deadline=NOW + timedelta(seconds=60))
    _observe(tracker, (decision,))
    corrupt = WorkDecision(
        project_id=decision.project_id,
        task_id=decision.task_id,
        status=decision.status,
        disposition=decision.disposition,
        reason_code=decision.reason_code,
        responsible_owner=decision.responsible_owner,
        unmet_prerequisites=decision.unmet_prerequisites,
        evidence_revision="corrupt-adapter-revision",
        next_reassessment_at=(NOW + timedelta(days=1)).isoformat(),
        permitted_actions=decision.permitted_actions,
        action_required=decision.action_required,
        alert_level=decision.alert_level,
        durable_jobs=decision.durable_jobs,
        recommended_status=decision.recommended_status,
    )

    with pytest.raises(ValueError, match="decision evidence_revision"):
        _observe(
            tracker,
            (corrupt,),
            generation=2,
            now=NOW + timedelta(seconds=30),
        )

    overdue = tracker.snapshot(now=NOW + timedelta(seconds=61))
    assert overdue.status == "overdue"
    assert overdue.tasks[0].last_progress_at == NOW.isoformat()


def test_evicted_history_cannot_renew_unchanged_deadline_after_restart_and_expansion():
    original = WorkflowLivenessTracker(max_task_records=2, clock=lambda: NOW)
    initial = (
        _decision("TASK-a", deadline=NOW + timedelta(minutes=2)),
        _decision("TASK-b", deadline=NOW + timedelta(minutes=2)),
    )
    _observe(original, initial, generation=1, now=NOW)

    reduced = WorkflowLivenessTracker(max_task_records=1, clock=lambda: NOW)
    reduced.restore(original.to_state(), now=NOW)
    reduced_state = reduced.to_state()
    assert reduced_state["history_incomplete"]

    later = NOW + timedelta(days=30)
    expanded = WorkflowLivenessTracker(max_task_records=2, clock=lambda: later)
    expanded.restore(reduced_state, now=later)
    refreshed = (
        _decision("TASK-a", deadline=later + timedelta(minutes=2)),
        _decision("TASK-b", deadline=later + timedelta(minutes=2)),
    )
    health = _observe(expanded, refreshed, generation=2, now=later)

    assert health.status == "overdue"
    by_task = {item.task_id: item for item in health.tasks}
    assert not by_task["TASK-a"].overdue
    assert by_task["TASK-b"].overdue
    assert by_task["TASK-b"].last_progress_at == (
        "1970-01-01T00:00:00+00:00"
    )
    assert not expanded.to_state()["history_incomplete"]


def test_cold_restore_applies_priority_before_smaller_record_cap():
    original = WorkflowLivenessTracker(max_task_records=3, clock=lambda: NOW)
    _observe(
        original,
        (
            _decision("AAA-normal"),
            _decision("BBB-normal"),
            _action_required("ZZZ-action"),
        ),
        generation=1,
    )
    restored = WorkflowLivenessTracker(max_task_records=1, clock=lambda: NOW)

    restored.restore(original.to_state(), now=NOW)
    health = restored.snapshot(now=NOW)

    assert health.tracked_task_count == 1
    assert health.tasks[0].task_id == "ZZZ-action"
    assert health.tasks[0].action_required


def test_stale_snapshot_generation_cannot_replace_newer_liveness_state():
    tracker = WorkflowLivenessTracker(clock=lambda: NOW)
    accepted = _observe(
        tracker,
        (_decision("TASK-current"),),
        generation=2,
    )
    restored = WorkflowLivenessTracker(
        clock=lambda: NOW + timedelta(seconds=1)
    )
    restored.restore(tracker.to_state(), now=NOW + timedelta(seconds=1))
    before_rejected = restored.snapshot(now=NOW + timedelta(seconds=1))
    rejected = _observe(
        restored,
        (_action_required("TASK-stale"),),
        generation=1,
        now=NOW + timedelta(seconds=1),
        source_scan_complete=False,
        source_errors={"project-stale": "TimeoutError"},
        reconciliation_complete=False,
        required_recovery_count=1,
        materialized_recovery_count=0,
    )

    assert rejected.to_dict() == before_rejected.to_dict()
    assert rejected.snapshot_generation == 2
    assert rejected.observed_at == accepted.observed_at
    assert [item.task_id for item in rejected.tasks] == ["TASK-current"]
    assert rejected.escalation_count == 0


def test_restored_ages_are_safe_but_health_requires_fresh_coverage():
    original = WorkflowLivenessTracker(clock=lambda: NOW)
    _observe(original, (_decision(),))
    state = original.to_state()
    restarted_at = NOW + timedelta(seconds=30)
    restored = WorkflowLivenessTracker(clock=lambda: restarted_at)

    restored.restore(state, now=restarted_at)
    before_scan = restored.snapshot(now=restarted_at)
    after_scan = _observe(
        restored,
        (_decision(),),
        generation=2,
        now=restarted_at,
    )

    assert before_scan.restored
    assert not before_scan.scan_complete
    assert before_scan.status == "incomplete"
    assert before_scan.tasks[0].decision_age_seconds == 30
    assert not after_scan.restored
    assert after_scan.scan_complete
    assert after_scan.tasks[0].first_observed_at == NOW.isoformat()


def test_future_persisted_progress_timestamps_are_clamped_on_restart():
    original = WorkflowLivenessTracker(clock=lambda: NOW)
    _observe(original, (_decision(),))
    state = original.to_state()
    future = (NOW + timedelta(hours=1)).isoformat()
    state["records"][0]["first_observed_at"] = future
    state["records"][0]["last_progress_at"] = future
    state["records"][0]["last_observed_at"] = future
    restored = WorkflowLivenessTracker(clock=lambda: NOW)

    restored.restore(state, now=NOW)
    task = restored.snapshot(now=NOW).tasks[0]

    assert task.first_observed_at == NOW.isoformat()
    assert task.last_progress_at == NOW.isoformat()
    assert task.last_observed_at == NOW.isoformat()
    assert task.decision_age_seconds == 0


def test_restart_reconstruction_has_persisted_bounded_deadline():
    original = WorkflowLivenessTracker(clock=lambda: NOW)
    _observe(original, (_decision(),))
    restarted = WorkflowLivenessTracker(clock=lambda: NOW)
    restarted.restore(original.to_state(), now=NOW)
    deadline = NOW + timedelta(
        seconds=LIVENESS_SLOS["restart_convergence"].max_reassessment_seconds
    )

    overdue = restarted.snapshot(now=deadline + timedelta(seconds=1))
    persisted = restarted.to_state()
    restarted_again = WorkflowLivenessTracker(
        clock=lambda: deadline + timedelta(seconds=2)
    )
    restarted_again.restore(
        persisted,
        now=deadline + timedelta(seconds=2),
    )
    repeated = restarted_again.snapshot(now=deadline + timedelta(seconds=2))

    assert overdue.status == "restart_overdue"
    assert overdue.restart_reconstruction_pending
    assert overdue.restart_lateness_seconds == 1
    assert repeated.restart_started_at == NOW.isoformat()
    assert repeated.restart_deadline_at == deadline.isoformat()
    assert repeated.restart_lateness_seconds == 2


def test_malformed_persisted_restart_timestamps_fail_closed_without_exceptions():
    original = WorkflowLivenessTracker(clock=lambda: NOW)
    _observe(original, (_decision(),))
    restarted_at = NOW + timedelta(seconds=1)

    for field in ("restart_started_at", "restart_deadline_at"):
        state = original.to_state()
        state["restart_reconstruction_pending"] = True
        state["restart_started_at"] = NOW.isoformat()
        state["restart_deadline_at"] = (NOW + timedelta(minutes=5)).isoformat()
        state[field] = {"not": "a timestamp"}
        restored = WorkflowLivenessTracker(clock=lambda: restarted_at)

        restored.restore(state, now=restarted_at)
        health = restored.snapshot(now=restarted_at)
        overdue = restored.snapshot(now=restarted_at + timedelta(seconds=1))

        assert health.status == "incomplete"
        assert health.last_error == "workflow liveness restart timestamps are corrupt"
        assert health.restart_started_at == restarted_at.isoformat()
        assert health.restart_deadline_at == restarted_at.isoformat()
        assert overdue.status == "restart_overdue"

    empty_state = original.to_state()
    empty_state["records"] = []
    empty_state["observed_at"] = None
    empty_state["total_nonterminal_count"] = 0
    empty_state["project_task_counts"] = {}
    empty_state["restart_started_at"] = "not-a-timestamp"
    empty = WorkflowLivenessTracker(clock=lambda: restarted_at)

    empty.restore(empty_state, now=restarted_at)
    empty_health = empty.snapshot(now=restarted_at)

    assert empty_health.status == "incomplete"
    assert empty.to_state()["history_corrupt"]
    assert empty_health.restart_deadline_at == restarted_at.isoformat()


def test_snapshot_fails_closed_when_valid_restored_state_is_mutated_corrupt():
    original = WorkflowLivenessTracker(clock=lambda: NOW)
    _observe(original, (_decision(),))
    restarted_at = NOW + timedelta(seconds=1)
    restored = WorkflowLivenessTracker(clock=lambda: restarted_at)
    restored.restore(original.to_state(), now=restarted_at)

    # Simulate a partially failed reload after a valid root restored.  The
    # snapshot/read path, used during startup health publication, must be as
    # defensive as restore itself.
    restored._restart_deadline_at = "not-a-timestamp"  # noqa: SLF001
    health = restored.snapshot(now=restarted_at)

    assert health.status == "incomplete"
    assert health.last_error == "workflow liveness restart timestamps are corrupt"
    assert health.restart_deadline_at == restarted_at.isoformat()


def test_configured_restart_deadline_and_convergence_counter_are_persisted():
    original = WorkflowLivenessTracker(clock=lambda: NOW)
    decision = _decision()
    _observe(original, (decision,))
    restarted = WorkflowLivenessTracker(
        slo_seconds={"restart_convergence": 30},
        clock=lambda: NOW + timedelta(seconds=1),
    )
    restarted.restore(original.to_state(), now=NOW + timedelta(seconds=1))

    assert restarted.snapshot().restart_deadline_at == (
        NOW + timedelta(seconds=31)
    ).isoformat()
    converged = _observe(
        restarted,
        (decision,),
        generation=2,
        now=NOW + timedelta(seconds=2),
    )
    persisted = restarted.to_state()

    assert converged.restart_convergence_count == 1
    assert persisted["cumulative"]["restart_convergence_count"] == 1


def test_live_slo_reload_reanchors_to_progress_not_reload_time():
    tracker = WorkflowLivenessTracker(
        slo_seconds={"dispatch_latency": 120},
        snapshot_stale_seconds=10_000,
        clock=lambda: NOW,
    )
    _observe(tracker, (_decision(deadline=NOW + timedelta(seconds=120)),))
    original_epoch = tracker.snapshot().policy_epoch

    tracker.reconfigure(
        max_task_records=256,
        max_project_records=64,
        snapshot_stale_seconds=10_000,
        slo_seconds={"dispatch_latency": 30},
    )
    health = tracker.snapshot(now=NOW + timedelta(seconds=31))

    assert health.tasks[0].slo_seconds == 30
    assert health.policy_epoch != original_epoch
    assert health.tasks[0].policy_epoch == health.policy_epoch
    assert health.tasks[0].next_reassessment_at == (
        NOW + timedelta(seconds=30)
    ).isoformat()
    assert health.status == "overdue"


def test_snapshot_staleness_fails_health_closed_without_warning():
    tracker = WorkflowLivenessTracker(
        snapshot_stale_seconds=10,
        clock=lambda: NOW,
    )
    _observe(tracker, (_decision(),))

    health = tracker.snapshot(now=NOW + timedelta(seconds=11))

    assert health.stale
    assert not health.scan_complete
    assert health.status == "incomplete"
    assert workflow_liveness_health_alerts(health) == []
