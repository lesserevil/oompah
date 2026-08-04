"""Versioned reason-code and liveness-SLO contract for workflow decisions.

Reason codes are durable API data.  Operators and the dashboard must never
infer a task's condition by parsing prose from logs or comments.  This module
defines the stable taxonomy, the responsible subsystem, evidence shape,
bounded reassessment objective, and whether a condition deserves operator
attention.

Unknown future codes are preserved when records are deserialized.  This lets
older clients relay newer server data without silently changing its severity
or dropping evidence.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any

from oompah.workflow_contract import (
    BACKLOG,
    CANONICAL_STATUSES,
    DECOMPOSED,
    DONE,
    DUPLICATE_CANDIDATE,
    IN_PROGRESS,
    IN_REVIEW,
    IN_VALIDATION,
    LIFECYCLE_FINAL_STATUSES,
    NEEDS_ANSWER,
    NEEDS_CI_FIX,
    NEEDS_HUMAN,
    NEEDS_REBASE,
    OPEN,
    PROPOSED,
    READY_TO_INTEGRATE,
    STATUS_CONTRACTS,
    canonicalize_status,
)

REASON_SCHEMA_VERSION = 1
REASON_TAXONOMY_VERSION = "1.0"


class ReasonClass(str, Enum):
    """Operator meaning of a workflow condition."""

    NORMAL = "normal"
    INFORMATIONAL = "informational"
    ACTION_REQUIRED = "action_required"


class AlertSeverity(str, Enum):
    """Presentation severity derived without parsing message text."""

    NONE = "none"
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class ResponsibleSubsystem(str, Enum):
    """Subsystem or role responsible for producing the next decision."""

    INTAKE = "intake"
    PROJECT_OWNER = "project_owner"
    DISPATCHER = "dispatcher"
    IMPLEMENTATION = "implementation"
    REQUESTOR = "requestor"
    OPERATOR = "operator"
    REVIEW_MONITOR = "review_monitor"
    AUDITOR = "auditor"
    INTEGRATOR = "integrator"
    ROLLUP = "rollup"
    DUPLICATE_INVESTIGATOR = "duplicate_investigator"
    RESTART_RECONCILER = "restart_reconciler"
    LIVENESS_CONTROLLER = "liveness_controller"


@dataclass(frozen=True, slots=True)
class LivenessSLO:
    """Maximum interval before a condition receives a fresh decision."""

    key: str
    max_reassessment_seconds: int
    breach_reason_code: str
    description: str


@dataclass(frozen=True, slots=True)
class ReasonDefinition:
    """Stable taxonomy entry for one workflow condition."""

    code: str
    statuses: frozenset[str]
    classification: ReasonClass
    severity: AlertSeverity
    subsystem: ResponsibleSubsystem
    slo_key: str
    evidence_fields: tuple[str, ...]
    summary: str
    operator_remedy: str | None = None


def _parse_time(value: Any, field_name: str) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError(f"{field_name} is required")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field_name} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _render_time(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("workflow reason timestamps must include a timezone")
    return value.astimezone(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class WorkflowReason:
    """Serializable reason instance attached to a workflow decision."""

    code: str
    status: str
    classification: ReasonClass
    severity: AlertSeverity
    subsystem: str
    observed_at: str
    reassess_at: str
    evidence: Mapping[str, Any]
    operator_remedy: str | None = None
    schema_version: int = REASON_SCHEMA_VERSION
    taxonomy_version: str = REASON_TAXONOMY_VERSION
    unknown_code: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return a stable JSON-compatible representation."""

        return {
            "schema_version": self.schema_version,
            "taxonomy_version": self.taxonomy_version,
            "code": self.code,
            "status": self.status,
            "classification": self.classification.value,
            "severity": self.severity.value,
            "subsystem": self.subsystem,
            "observed_at": self.observed_at,
            "reassess_at": self.reassess_at,
            "evidence": {key: self.evidence[key] for key in sorted(self.evidence)},
            "operator_remedy": self.operator_remedy,
            "unknown_code": self.unknown_code,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "WorkflowReason":
        """Parse known or future reason codes without discarding fields."""

        if not isinstance(raw, Mapping):
            raise ValueError("workflow reason must be an object")
        try:
            schema_version = int(raw.get("schema_version", REASON_SCHEMA_VERSION))
        except (TypeError, ValueError) as exc:
            raise ValueError("schema_version must be an integer") from exc
        if schema_version < 1:
            raise ValueError("schema_version must be positive")
        code = str(raw.get("code") or "").strip()
        if not code:
            raise ValueError("code is required")
        status = canonicalize_status(raw.get("status"))
        if status not in CANONICAL_STATUSES:
            raise ValueError(f"unknown canonical status: {status!r}")
        observed = _parse_time(raw.get("observed_at"), "observed_at")
        reassess = _parse_time(raw.get("reassess_at"), "reassess_at")
        if reassess <= observed:
            raise ValueError("reassess_at must be later than observed_at")
        evidence = raw.get("evidence", {})
        if not isinstance(evidence, Mapping):
            raise ValueError("evidence must be an object")
        known = REASON_DEFINITIONS.get(code)
        try:
            classification = ReasonClass(
                raw.get("classification")
                or (
                    known.classification.value
                    if known
                    else ReasonClass.INFORMATIONAL.value
                )
            )
            severity = AlertSeverity(
                raw.get("severity")
                or (known.severity.value if known else AlertSeverity.INFO.value)
            )
        except ValueError as exc:
            raise ValueError(
                "invalid workflow reason classification or severity"
            ) from exc
        subsystem = str(
            raw.get("subsystem")
            or (
                known.subsystem.value
                if known
                else ResponsibleSubsystem.LIVENESS_CONTROLLER.value
            )
        ).strip()
        if not subsystem:
            raise ValueError("subsystem is required")
        remedy_raw = raw.get("operator_remedy")
        remedy = str(remedy_raw).strip() if remedy_raw is not None else None
        return cls(
            code=code,
            status=status,
            classification=classification,
            severity=severity,
            subsystem=subsystem,
            observed_at=_render_time(observed),
            reassess_at=_render_time(reassess),
            evidence=MappingProxyType(dict(evidence)),
            operator_remedy=remedy,
            schema_version=schema_version,
            taxonomy_version=str(
                raw.get("taxonomy_version") or REASON_TAXONOMY_VERSION
            ),
            unknown_code=known is None or bool(raw.get("unknown_code", False)),
        )


def _slo(key: str, seconds: int, description: str) -> LivenessSLO:
    return LivenessSLO(
        key=key,
        max_reassessment_seconds=seconds,
        breach_reason_code="liveness.reassessment_overdue",
        description=description,
    )


# These values are contract ceilings, not polling intervals.  Implementations
# may re-evaluate sooner but cannot claim liveness compliance after the ceiling.
LIVENESS_SLOS: Mapping[str, LivenessSLO] = MappingProxyType(
    {
        item.key: item
        for item in (
            _slo("intake_reassessment", 900, "Refresh pending intake decisions."),
            _slo(
                "prioritization_visibility",
                3600,
                "Refresh owner prioritization visibility.",
            ),
            _slo("dispatch_latency", 120, "Reconsider eligible implementation work."),
            _slo(
                "implementation_lease",
                900,
                "Renew or recover implementation ownership.",
            ),
            _slo("requestor_visibility", 3600, "Refresh requestor-answer visibility."),
            _slo("operator_visibility", 900, "Refresh operator-action visibility."),
            _slo("repair_dispatch_latency", 120, "Reconsider eligible repair work."),
            _slo("review_reassessment", 300, "Refresh review and CI evidence."),
            _slo("audit_lease", 600, "Renew or recover audit ownership."),
            _slo("integration_lease", 600, "Renew or recover integration ownership."),
            _slo("rollup_reassessment", 120, "Recompute child and containment rollup."),
            _slo(
                "duplicate_investigation_lease",
                600,
                "Renew or recover duplicate review.",
            ),
            _slo(
                "landing_reassessment", 300, "Refresh target-branch landing evidence."
            ),
            _slo(
                "restart_convergence",
                120,
                "Reconstruct and reconcile durable work after restart.",
            ),
        )
    }
)


def _reason(
    code: str,
    statuses: set[str],
    classification: ReasonClass,
    subsystem: ResponsibleSubsystem,
    slo_key: str,
    evidence_fields: tuple[str, ...],
    summary: str,
    *,
    remedy: str | None = None,
    severity: AlertSeverity | None = None,
) -> ReasonDefinition:
    if severity is None:
        severity = {
            ReasonClass.NORMAL: AlertSeverity.NONE,
            ReasonClass.INFORMATIONAL: AlertSeverity.INFO,
            ReasonClass.ACTION_REQUIRED: AlertSeverity.WARNING,
        }[classification]
    return ReasonDefinition(
        code,
        frozenset(statuses),
        classification,
        severity,
        subsystem,
        slo_key,
        evidence_fields,
        summary,
        remedy,
    )


_REASONS = (
    _reason(
        "intake.awaiting_decision",
        {PROPOSED},
        ReasonClass.NORMAL,
        ResponsibleSubsystem.INTAKE,
        "intake_reassessment",
        ("intake_state",),
        "Intake is evaluating the request.",
    ),
    _reason(
        "prioritization.awaiting_owner",
        {BACKLOG},
        ReasonClass.NORMAL,
        ResponsibleSubsystem.PROJECT_OWNER,
        "prioritization_visibility",
        ("priority",),
        "Accepted work is waiting for owner prioritization.",
    ),
    _reason(
        "dispatch.eligible",
        {OPEN, NEEDS_CI_FIX, NEEDS_REBASE},
        ReasonClass.NORMAL,
        ResponsibleSubsystem.DISPATCHER,
        "dispatch_latency",
        ("candidate_generation",),
        "Work is eligible for a dispatch decision.",
    ),
    _reason(
        "dispatch.dependencies_blocked",
        {OPEN, NEEDS_CI_FIX, NEEDS_REBASE},
        ReasonClass.INFORMATIONAL,
        ResponsibleSubsystem.DISPATCHER,
        "dispatch_latency",
        ("blocking_task_ids",),
        "A named dependency currently prevents ownership.",
    ),
    _reason(
        "dispatch.capacity_wait",
        {OPEN, NEEDS_CI_FIX, NEEDS_REBASE},
        ReasonClass.NORMAL,
        ResponsibleSubsystem.DISPATCHER,
        "dispatch_latency",
        ("capacity_used", "capacity_limit"),
        "Eligible work is waiting for available capacity.",
    ),
    _reason(
        "implementation.active",
        {IN_PROGRESS},
        ReasonClass.NORMAL,
        ResponsibleSubsystem.IMPLEMENTATION,
        "implementation_lease",
        ("owner_id", "generation", "lease_expires_at"),
        "An implementation owner holds the current generation.",
    ),
    _reason(
        "implementation.recovery_scheduled",
        {IN_PROGRESS, OPEN},
        ReasonClass.INFORMATIONAL,
        ResponsibleSubsystem.IMPLEMENTATION,
        "implementation_lease",
        ("generation", "retry_at"),
        "Normal recovery is scheduled for interrupted implementation work.",
    ),
    _reason(
        "requestor.answer_required",
        {NEEDS_ANSWER},
        ReasonClass.ACTION_REQUIRED,
        ResponsibleSubsystem.REQUESTOR,
        "requestor_visibility",
        ("question_id",),
        "The requestor must answer a specific question.",
        remedy="Answer the recorded question so the task can be reassessed.",
    ),
    _reason(
        "operator.action_required",
        {NEEDS_HUMAN},
        ReasonClass.ACTION_REQUIRED,
        ResponsibleSubsystem.OPERATOR,
        "operator_visibility",
        ("action_code", "action_detail"),
        "A named operator action is required.",
        remedy="Perform the recorded action or provide an explicit disposition.",
    ),
    _reason(
        "review.monitoring",
        {IN_REVIEW},
        ReasonClass.NORMAL,
        ResponsibleSubsystem.REVIEW_MONITOR,
        "review_reassessment",
        ("review_id", "head_sha"),
        "Review, CI, and mergeability are being monitored.",
    ),
    _reason(
        "review.ci_pending",
        {IN_REVIEW},
        ReasonClass.NORMAL,
        ResponsibleSubsystem.REVIEW_MONITOR,
        "review_reassessment",
        ("review_id", "head_sha", "ci"),
        "Review CI is pending or has not registered a verdict yet.",
    ),
    _reason(
        "review.draft_wait",
        {IN_REVIEW},
        ReasonClass.NORMAL,
        ResponsibleSubsystem.REVIEW_MONITOR,
        "review_reassessment",
        ("review_id", "head_sha"),
        "The draft review is being monitored without merge or repair actions.",
    ),
    _reason(
        "review.ready_to_merge",
        {IN_REVIEW},
        ReasonClass.NORMAL,
        ResponsibleSubsystem.REVIEW_MONITOR,
        "review_reassessment",
        ("review_id", "head_sha", "ci"),
        "The exact review head passed CI and a durable merge action is queued.",
    ),
    _reason(
        "review.ci_fix_required",
        {IN_REVIEW},
        ReasonClass.INFORMATIONAL,
        ResponsibleSubsystem.REVIEW_MONITOR,
        "repair_dispatch_latency",
        ("review_id", "head_sha", "ci"),
        "Review CI failed and a durable repair action is queued.",
    ),
    _reason(
        "review.rebase_required",
        {IN_REVIEW},
        ReasonClass.INFORMATIONAL,
        ResponsibleSubsystem.REVIEW_MONITOR,
        "repair_dispatch_latency",
        ("review_id", "head_sha", "mergeable_state"),
        "Review mergeability requires a durable conflict repair action.",
    ),
    _reason(
        "review.capacity_wait",
        {IN_REVIEW},
        ReasonClass.INFORMATIONAL,
        ResponsibleSubsystem.REVIEW_MONITOR,
        "review_reassessment",
        ("capacity_used", "capacity_limit"),
        "Review progression is waiting for capacity to be observed again.",
    ),
    _reason(
        "review.closed_unmerged",
        {IN_REVIEW},
        ReasonClass.INFORMATIONAL,
        ResponsibleSubsystem.REVIEW_MONITOR,
        "repair_dispatch_latency",
        ("review_id", "source_branch", "target_branch"),
        "The review closed without landing and is queued for repair.",
    ),
    _reason(
        "review.missing_artifact",
        {IN_REVIEW},
        ReasonClass.INFORMATIONAL,
        ResponsibleSubsystem.REVIEW_MONITOR,
        "review_reassessment",
        ("source_branch", "target_branch"),
        "The provider returned no review artifact; reassessment remains durable.",
    ),
    _reason(
        "review.landing_refresh",
        {IN_REVIEW},
        ReasonClass.INFORMATIONAL,
        ResponsibleSubsystem.REVIEW_MONITOR,
        "landing_reassessment",
        ("review_id", "head_sha", "target_branch"),
        "The review is merged but target landing proof is still being refreshed.",
    ),
    _reason(
        "review.head_changed",
        {IN_REVIEW},
        ReasonClass.INFORMATIONAL,
        ResponsibleSubsystem.REVIEW_MONITOR,
        "repair_dispatch_latency",
        ("recorded_head", "current_head"),
        "The source head changed after the recorded review and needs a fresh review.",
    ),
    _reason(
        "review.merge_target_mismatch",
        {IN_REVIEW},
        ReasonClass.ACTION_REQUIRED,
        ResponsibleSubsystem.OPERATOR,
        "operator_visibility",
        ("expected_target", "observed_target"),
        "The review targets a different branch than the task configuration.",
        remedy="Correct the review target or update the task's target-branch evidence, then reassess.",
    ),
    _reason(
        "review.source_deleted",
        {IN_REVIEW},
        ReasonClass.ACTION_REQUIRED,
        ResponsibleSubsystem.OPERATOR,
        "operator_visibility",
        ("source_branch", "review_id"),
        "The review source branch disappeared without durable landing proof.",
        remedy="Confirm the merge, restore the source review, or explicitly archive the task.",
    ),
    _reason(
        "review.provider_unavailable",
        {IN_REVIEW},
        ReasonClass.INFORMATIONAL,
        ResponsibleSubsystem.REVIEW_MONITOR,
        "review_reassessment",
        ("provider", "error_code"),
        "The review provider is unavailable; the prior decision remains fenced and will retry.",
    ),
    _reason(
        "validation.queued",
        {IN_VALIDATION},
        ReasonClass.NORMAL,
        ResponsibleSubsystem.AUDITOR,
        "audit_lease",
        ("audit_id", "requested_target"),
        "Validation is queued for an independent auditor.",
    ),
    _reason(
        "validation.active",
        {IN_VALIDATION},
        ReasonClass.NORMAL,
        ResponsibleSubsystem.AUDITOR,
        "audit_lease",
        ("audit_id", "owner_id", "lease_expires_at"),
        "An auditor owns the current validation attempt.",
    ),
    _reason(
        "validation.retry_scheduled",
        {IN_VALIDATION},
        ReasonClass.INFORMATIONAL,
        ResponsibleSubsystem.AUDITOR,
        "audit_lease",
        ("audit_id", "retry_at"),
        "Normal validation recovery is scheduled.",
    ),
    _reason(
        "integration.queued",
        {READY_TO_INTEGRATE},
        ReasonClass.NORMAL,
        ResponsibleSubsystem.INTEGRATOR,
        "integration_lease",
        ("job_id", "head_sha", "target_branch"),
        "Accepted work is queued for integration.",
    ),
    _reason(
        "integration.active",
        {READY_TO_INTEGRATE},
        ReasonClass.NORMAL,
        ResponsibleSubsystem.INTEGRATOR,
        "integration_lease",
        ("job_id", "owner_id", "lease_expires_at"),
        "An integrator owns the current integration attempt.",
    ),
    _reason(
        "integration.retry_scheduled",
        {READY_TO_INTEGRATE},
        ReasonClass.INFORMATIONAL,
        ResponsibleSubsystem.INTEGRATOR,
        "integration_lease",
        ("job_id", "retry_at"),
        "Normal integration recovery is scheduled.",
    ),
    _reason(
        "rollup.waiting_children",
        {DECOMPOSED},
        ReasonClass.NORMAL,
        ResponsibleSubsystem.ROLLUP,
        "rollup_reassessment",
        ("incomplete_child_ids",),
        "The decomposed wrapper is waiting for child completion.",
    ),
    _reason(
        "duplicate.investigating",
        {DUPLICATE_CANDIDATE},
        ReasonClass.NORMAL,
        ResponsibleSubsystem.DUPLICATE_INVESTIGATOR,
        "duplicate_investigation_lease",
        ("investigation_id", "lease_expires_at"),
        "A duplicate investigator is comparing candidate work.",
    ),
    _reason(
        "landing.waiting",
        {DONE},
        ReasonClass.NORMAL,
        ResponsibleSubsystem.ROLLUP,
        "landing_reassessment",
        ("head_sha", "target_branch"),
        "Completed work is waiting for target-branch landing or rollup.",
    ),
    _reason(
        "restart.reconciling",
        set(CANONICAL_STATUSES) - set(LIFECYCLE_FINAL_STATUSES),
        ReasonClass.INFORMATIONAL,
        ResponsibleSubsystem.RESTART_RECONCILER,
        "restart_convergence",
        ("service_instance_id", "facts_version"),
        "Durable work is being reconstructed after restart.",
    ),
    _reason(
        "liveness.reassessment_overdue",
        set(CANONICAL_STATUSES) - set(LIFECYCLE_FINAL_STATUSES),
        ReasonClass.ACTION_REQUIRED,
        ResponsibleSubsystem.LIVENESS_CONTROLLER,
        "operator_visibility",
        ("previous_reason_code", "deadline", "overdue_seconds"),
        "A bounded reassessment deadline was missed.",
        remedy="Inspect the responsible subsystem and rearm or resolve its durable work.",
    ),
)

REASON_DEFINITIONS: Mapping[str, ReasonDefinition] = MappingProxyType(
    {definition.code: definition for definition in _REASONS}
)


def build_workflow_reason(
    code: str,
    status: str,
    *,
    observed_at: datetime,
    evidence: Mapping[str, Any],
    reassessment_seconds: int | None = None,
) -> WorkflowReason:
    """Build and validate a known reason instance."""

    definition = REASON_DEFINITIONS.get(str(code or "").strip())
    if definition is None:
        raise ValueError(f"unknown workflow reason code: {code!r}")
    canonical = canonicalize_status(status)
    if canonical not in definition.statuses:
        raise ValueError(f"reason {code!r} does not apply to status {canonical!r}")
    missing = [field for field in definition.evidence_fields if field not in evidence]
    if missing:
        raise ValueError(f"reason {code!r} is missing evidence fields: {missing!r}")
    slo = LIVENESS_SLOS[definition.slo_key]
    seconds = (
        slo.max_reassessment_seconds
        if reassessment_seconds is None
        else int(reassessment_seconds)
    )
    if seconds <= 0 or seconds > slo.max_reassessment_seconds:
        raise ValueError(
            f"reassessment_seconds must be between 1 and {slo.max_reassessment_seconds}"
        )
    if observed_at.tzinfo is None:
        raise ValueError("observed_at must include a timezone")
    observed = observed_at.astimezone(timezone.utc)
    return WorkflowReason(
        code=definition.code,
        status=canonical,
        classification=definition.classification,
        severity=definition.severity,
        subsystem=definition.subsystem.value,
        observed_at=_render_time(observed),
        reassess_at=_render_time(observed + timedelta(seconds=seconds)),
        evidence=MappingProxyType(dict(evidence)),
        operator_remedy=definition.operator_remedy,
    )


def validate_workflow_reason(reason: WorkflowReason) -> tuple[str, ...]:
    """Return schema/contract violations for a reason instance."""

    errors: list[str] = []
    try:
        observed = _parse_time(reason.observed_at, "observed_at")
        reassess = _parse_time(reason.reassess_at, "reassess_at")
    except ValueError as exc:
        return (str(exc),)
    if reassess <= observed:
        errors.append("reassess_at must be later than observed_at")
    definition = REASON_DEFINITIONS.get(reason.code)
    if definition is None:
        if not reason.unknown_code:
            errors.append("unknown reason code must be marked unknown_code")
        return tuple(errors)
    if reason.unknown_code:
        errors.append("known reason code cannot be marked unknown_code")
    if reason.status not in definition.statuses:
        errors.append(f"reason does not apply to status {reason.status!r}")
    if reason.classification != definition.classification:
        errors.append("classification does not match reason definition")
    if reason.severity != definition.severity:
        errors.append("severity does not match reason definition")
    missing = [
        field for field in definition.evidence_fields if field not in reason.evidence
    ]
    if missing:
        errors.append(f"missing evidence fields: {missing!r}")
    slo = LIVENESS_SLOS[definition.slo_key]
    if (reassess - observed).total_seconds() > slo.max_reassessment_seconds:
        errors.append(f"reassessment exceeds SLO {definition.slo_key!r}")
    return tuple(errors)


_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")


def validate_reason_taxonomy() -> tuple[str, ...]:
    """Return structural violations in the static taxonomy/SLO contract."""

    errors: list[str] = []
    if len(REASON_DEFINITIONS) != len(_REASONS):
        errors.append("reason codes are not unique")
    for key, slo in LIVENESS_SLOS.items():
        if key != slo.key:
            errors.append(f"SLO key mismatch for {key!r}")
        if slo.max_reassessment_seconds <= 0:
            errors.append(f"SLO {key!r} is not bounded")
    for code, definition in REASON_DEFINITIONS.items():
        if code != definition.code or not _CODE_PATTERN.fullmatch(code):
            errors.append(f"invalid stable reason code {code!r}")
        if not definition.statuses:
            errors.append(f"reason {code!r} has no applicable statuses")
        unknown_statuses = set(definition.statuses) - set(CANONICAL_STATUSES)
        if unknown_statuses:
            errors.append(
                f"reason {code!r} references unknown statuses {unknown_statuses!r}"
            )
        if definition.slo_key not in LIVENESS_SLOS:
            errors.append(
                f"reason {code!r} references unknown SLO {definition.slo_key!r}"
            )
        if (
            definition.classification == ReasonClass.NORMAL
            and definition.severity != AlertSeverity.NONE
        ):
            errors.append(f"normal reason {code!r} must not alert")
        if "recovery" in code and definition.severity in {
            AlertSeverity.WARNING,
            AlertSeverity.CRITICAL,
        }:
            errors.append(f"normal recovery reason {code!r} must not warn")
        if (
            definition.classification == ReasonClass.ACTION_REQUIRED
            and not definition.operator_remedy
        ):
            errors.append(f"action-required reason {code!r} has no remedy")
    nonfinal = set(CANONICAL_STATUSES) - set(LIFECYCLE_FINAL_STATUSES)
    covered = {
        status
        for definition in REASON_DEFINITIONS.values()
        if definition.code != "restart.reconciling"
        for status in definition.statuses
    }
    missing = nonfinal - covered
    if missing:
        errors.append(f"non-final statuses lack reason coverage: {sorted(missing)!r}")
    for status in nonfinal:
        slo_key = STATUS_CONTRACTS[status].reassessment.slo_key
        if not slo_key or slo_key not in LIVENESS_SLOS:
            errors.append(f"status {status!r} lacks a defined reassessment SLO")
    return tuple(errors)


_taxonomy_errors = validate_reason_taxonomy()
if _taxonomy_errors:
    raise ValueError("invalid workflow reason taxonomy: " + "; ".join(_taxonomy_errors))


__all__ = [
    "AlertSeverity",
    "LIVENESS_SLOS",
    "LivenessSLO",
    "REASON_DEFINITIONS",
    "REASON_SCHEMA_VERSION",
    "REASON_TAXONOMY_VERSION",
    "ReasonClass",
    "ReasonDefinition",
    "ResponsibleSubsystem",
    "WorkflowReason",
    "build_workflow_reason",
    "validate_reason_taxonomy",
    "validate_workflow_reason",
]
