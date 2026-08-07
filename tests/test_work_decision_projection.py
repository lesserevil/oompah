"""Contract tests for the one why-not-progressing read projection."""

from __future__ import annotations

from datetime import datetime, timezone

from oompah.work_decision import PermittedAction, UnmetPrerequisite, WorkDecision
from oompah.work_decision_projection import (
    operator_actionable_alerts,
    project_work_decision,
    project_work_decision_payload,
    work_decision_alert,
)
from oompah.auth_health import OperatorAuthHealth, WorkerAuthHealth
from oompah.terminal_audit_health import (
    TerminalAuditHealth,
    terminal_audit_health_alerts,
)
from oompah.terminal_audit_observability import AuditAlertCondition
from oompah.workflow_contract import TaskDisposition, WorkflowOwner
from oompah.workflow_reasons import AlertSeverity


def _decision(*, action_required: bool, level: AlertSeverity) -> WorkDecision:
    return WorkDecision(
        project_id="project-a",
        task_id="TASK-1",
        status="Needs Human" if action_required else "Open",
        disposition=(
            TaskDisposition.ACTION_REQUIRED
            if action_required
            else TaskDisposition.RETRY_SCHEDULED
        ),
        reason_code=(
            "operator.action_required"
            if action_required
            else "implementation.recovery_scheduled"
        ),
        responsible_owner=(
            WorkflowOwner.OPERATOR
            if action_required
            else WorkflowOwner.DISPATCHER
        ),
        unmet_prerequisites=(
            (UnmetPrerequisite("operator.action_required", "TASK-1"),)
            if action_required
            else ()
        ),
        evidence_revision="evidence-1",
        next_reassessment_at=datetime(
            2026, 8, 6, 5, tzinfo=timezone.utc
        ).isoformat(),
        permitted_actions=(
            (PermittedAction.RESOLVE_OPERATOR_ACTION,)
            if action_required
            else (PermittedAction.RECOVER_IMPLEMENTATION,)
        ),
        action_required=action_required,
        alert_level=level,
        durable_jobs=("implementation_recovery",) if not action_required else (),
    )


def test_projection_contains_one_answer_and_compatibility_aliases() -> None:
    projection = project_work_decision(
        _decision(action_required=True, level=AlertSeverity.WARNING)
    )

    assert projection["owner"] == projection["responsible_owner"] == "operator"
    assert projection["disposition"] == "action_required"
    assert projection["reason"]["code"] == projection["reason_code"]
    assert projection["reason"]["text"] == projection["reason_text"]
    assert projection["prerequisites"] == projection["unmet_prerequisites"]
    assert projection["next_reassessment"] == projection["next_reassessment_at"]
    assert projection["evidence_revision"] == "evidence-1"
    assert projection["action_required"] is True
    assert projection["global_alert"] is True
    assert projection["recovery_action"]


def test_projection_payload_accepts_a_projection_round_trip() -> None:
    decision = _decision(action_required=True, level=AlertSeverity.WARNING)
    projection = project_work_decision(decision)

    assert project_work_decision_payload(projection) == projection


def test_normal_recovery_never_becomes_global_warning() -> None:
    decision = _decision(action_required=False, level=AlertSeverity.INFO)

    assert work_decision_alert(decision) is None
    assert operator_actionable_alerts(
        [
            {
                "level": "warning",
                "source": "retry_backoff:TASK-1",
                "action_required": False,
            },
            {
                "level": "warning",
                "source": "missing-marker",
                "action": "Should not be enough without action_required.",
            },
        ]
    ) == []


def test_actionable_alerts_do_not_merge_distinct_source_less_alerts() -> None:
    alerts = [
        {
            "level": "warning",
            "action_required": True,
            "message": "first",
            "action": "Repair first",
        },
        {
            "level": "warning",
            "action_required": True,
            "message": "second",
            "action": "Repair second",
        },
    ]

    assert operator_actionable_alerts(alerts) == alerts


def test_actionable_alert_severity_transitions_and_clears() -> None:
    blocked = _decision(action_required=True, level=AlertSeverity.WARNING)
    alert = work_decision_alert(blocked)
    assert alert is not None
    assert alert["action_required"] is True
    assert alert["level"] == "warning"
    assert operator_actionable_alerts([alert]) == [alert]

    critical = _decision(action_required=True, level=AlertSeverity.CRITICAL)
    critical_alert = work_decision_alert(critical)
    assert critical_alert is not None
    assert critical_alert["level"] == "critical"

    recovered = _decision(action_required=False, level=AlertSeverity.INFO)
    assert work_decision_alert(recovered) is None
    assert operator_actionable_alerts([critical_alert]) == [critical_alert]
    assert operator_actionable_alerts([]) == []


def test_projection_does_not_include_secrets_from_decision_values() -> None:
    original = _decision(action_required=True, level=AlertSeverity.WARNING)
    decision = WorkDecision(
        **{
            **original.to_dict(),
            "unmet_prerequisites": (
                UnmetPrerequisite(
                    "operator.action_required",
                    "TASK-1",
                    "Authorization: Bearer very-secret-token",
                ),
            ),
            "permitted_actions": original.permitted_actions,
            "durable_jobs": original.durable_jobs,
            "decision_revision": None,
        }
    )
    projection = project_work_decision(decision)
    serialized = str(projection)
    assert "Authorization:" not in serialized
    assert "Bearer " not in serialized
    assert "very-secret-token" not in serialized
    assert "[REDACTED]" in serialized


def test_action_required_without_concrete_instruction_fails_closed() -> None:
    assert operator_actionable_alerts(
        [
            {
                "level": "warning",
                "source": "broken-producer",
                "action_required": True,
                "message": "Something needs attention",
            }
        ]
    ) == []


def test_transient_auth_observations_are_informational_and_self_clear() -> None:
    now = [0.0]
    operator = OperatorAuthHealth(now=lambda: now[0])
    worker = WorkerAuthHealth(now=lambda: now[0])
    operator.record_401()
    worker.record_minted()
    worker.record_401()

    observed = [operator.build_alert(), worker.build_alert()]
    assert all(alert is not None for alert in observed)
    assert all(alert["level"] == "info" for alert in observed if alert)
    assert all(alert["action_required"] is False for alert in observed if alert)
    assert operator_actionable_alerts(alert for alert in observed if alert) == []

    now[0] = 901.0
    assert operator.build_alert(window_seconds=900) is None
    assert worker.build_alert(window_seconds=900) is None


def test_terminal_audit_retry_rotation_is_info_until_recovery_is_exhausted() -> None:
    rotating = terminal_audit_health_alerts(
        TerminalAuditHealth(launch_failure_count=1, transport_failure_count=1)
    )
    assert len(rotating) == 1
    assert rotating[0]["level"] == "info"
    assert rotating[0]["action_required"] is False
    assert operator_actionable_alerts(rotating) == []

    exhausted = terminal_audit_health_alerts(
        TerminalAuditHealth(retry_exhausted_count=1)
    )
    assert exhausted[0]["action_required"] is True
    assert operator_actionable_alerts(exhausted) == exhausted


def test_actionable_terminal_audit_condition_crosses_global_alert_boundary() -> None:
    alert = AuditAlertCondition(
        "no_independent_candidate",
        "project-a",
        "TASK-1",
        "audit-1",
        "No independent auditor is available.",
        "Configure an independent auditor and retry the audit.",
    ).to_alert()

    assert alert["action_required"] is True
    assert operator_actionable_alerts([alert]) == [alert]
