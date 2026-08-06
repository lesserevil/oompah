"""Public, redacted projection of one :class:`WorkDecision`.

The evaluator is intentionally an internal policy value.  This module is the
single presentation boundary used by REST, WebSocket state, and the dashboard
so consumers do not each invent their own owner/reason/alert heuristics.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from oompah.secrets import redact_sensitive_data
from oompah.work_decision import WorkDecision
from oompah.workflow_reasons import AlertSeverity, REASON_DEFINITIONS


PROJECTION_SCHEMA_VERSION = 1
_GLOBAL_ALERT_LEVELS = frozenset({"warning", "critical", "error"})


def _humanize(value: object) -> str:
    text = str(value or "").strip().replace("_", " ")
    return text[:1].upper() + text[1:]


def reason_text(reason_code: str) -> str:
    """Return stable operator prose without parsing logs or task text."""

    definition = REASON_DEFINITIONS.get(str(reason_code or "").strip())
    if definition is not None:
        return definition.summary
    return _humanize(str(reason_code).replace(".", ": ")) or "Workflow evidence is being evaluated."


def recovery_action(decision: WorkDecision) -> str | None:
    """Return the one action the owning subsystem should take next."""

    definition = REASON_DEFINITIONS.get(decision.reason_code)
    if decision.action_required and definition is not None and definition.operator_remedy:
        return definition.operator_remedy
    if not decision.permitted_actions:
        return None
    return _humanize(decision.permitted_actions[0].value)


def project_work_decision(decision: WorkDecision) -> dict[str, Any]:
    """Serialize a decision for every read consumer.

    Compatibility names are deliberately aliases, not separate answers:
    ``owner``/``responsible_owner``, ``prerequisites``/``unmet_prerequisites``,
    and ``next_reassessment``/``next_reassessment_at`` all carry the exact
    values from the evaluator.
    """

    raw = decision.to_dict()
    owner = raw["responsible_owner"]
    prerequisites = list(raw["unmet_prerequisites"])
    next_at = raw["next_reassessment_at"]
    text = reason_text(raw["reason_code"])
    action = recovery_action(decision)
    projection = {
        "projection_schema_version": PROJECTION_SCHEMA_VERSION,
        **raw,
        "owner": owner,
        "reason_text": text,
        "reason": {"code": raw["reason_code"], "text": text},
        "prerequisites": prerequisites,
        "next_reassessment": next_at,
        "recovery_action": action,
        "global_alert": bool(
            raw["action_required"]
            and raw["alert_level"] in {AlertSeverity.WARNING.value, AlertSeverity.CRITICAL.value}
        ),
    }
    redacted = redact_sensitive_data(projection)
    return redacted if isinstance(redacted, dict) else {
        "projection_schema_version": PROJECTION_SCHEMA_VERSION,
        "project_id": decision.project_id,
        "task_id": decision.task_id,
        "action_required": True,
        "reason_code": "controller.evaluation_failed",
        "reason_text": "The workflow decision could not be safely rendered.",
        "recovery_action": "Inspect the task through an authenticated operator session.",
        "global_alert": True,
    }


def project_work_decision_payload(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Project a serialized decision received from a diagnostic/cache row."""

    # A cache may already contain the public projection, which has aliases and
    # schema metadata in addition to the evaluator's constructor fields.
    # Decode only the versioned WorkDecision payload so a presentation object
    # can safely be fed back through this boundary.
    fields = {
        "schema_version",
        "project_id",
        "task_id",
        "status",
        "disposition",
        "reason_code",
        "responsible_owner",
        "unmet_prerequisites",
        "evidence_revision",
        "next_reassessment_at",
        "permitted_actions",
        "action_required",
        "alert_level",
        "durable_jobs",
        "recommended_status",
        "decision_revision",
    }
    values = {key: value for key, value in raw.items() if key in fields}
    return project_work_decision(WorkDecision.from_dict(values))


def work_decision_alert(decision: WorkDecision) -> dict[str, Any] | None:
    """Build a global alert only for a decision requiring operator action."""

    if not decision.action_required:
        return None
    if decision.alert_level not in {AlertSeverity.WARNING, AlertSeverity.CRITICAL}:
        return None
    projection = project_work_decision(decision)
    text = str(projection["reason_text"])
    action = projection.get("recovery_action")
    return {
        "level": decision.alert_level.value,
        "source": f"work_decision:{decision.project_id}:{decision.task_id}",
        "project_id": decision.project_id,
        "task_id": decision.task_id,
        "reason_code": decision.reason_code,
        "message": f"{decision.task_id}: {text}",
        "detail": ", ".join(
            item["subject"]
            for item in projection["prerequisites"]
            if isinstance(item, Mapping) and item.get("subject")
        ) or None,
        "action": action,
        "action_required": True,
        "evidence_revision": decision.evidence_revision,
        "decision_revision": decision.decision_revision,
    }


def operator_actionable_alerts(alerts: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Filter legacy/system alerts to explicit operator actions.

    Missing ``action_required`` is intentionally non-actionable at this
    boundary.  Producers must opt into a global warning explicitly; routine
    queue age, retry, capacity, audit, and authentication observations remain
    available in ``alerts`` but cannot become a warning banner by omission.
    """

    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for alert in alerts:
        if not isinstance(alert, Mapping):
            continue
        level = str(alert.get("level") or "").lower()
        if alert.get("action_required") is not True or level not in _GLOBAL_ALERT_LEVELS:
            continue
        source = str(alert.get("source") or "")
        if source and source in seen:
            continue
        if source:
            seen.add(source)
        result.append(dict(alert))
    return result


__all__ = [
    "PROJECTION_SCHEMA_VERSION",
    "operator_actionable_alerts",
    "project_work_decision",
    "project_work_decision_payload",
    "reason_text",
    "recovery_action",
    "work_decision_alert",
]
