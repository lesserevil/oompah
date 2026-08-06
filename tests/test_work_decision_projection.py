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
            },
        ]
    ) == []


def test_actionable_alerts_do_not_merge_distinct_source_less_alerts() -> None:
    alerts = [
        {"level": "warning", "action_required": True, "message": "first"},
        {"level": "warning", "action_required": True, "message": "second"},
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
    decision = _decision(action_required=True, level=AlertSeverity.WARNING)
    projection = project_work_decision(decision)
    serialized = str(projection)
    assert "Authorization:" not in serialized
    assert "Bearer " not in serialized
    assert "password" not in serialized.lower()
