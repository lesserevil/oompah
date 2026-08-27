"""Pure, total workflow evaluation from one task and versioned facts.

``evaluate_task`` is the shared answer for scheduling, dashboard explanation,
and liveness.  It performs no I/O and never mutates tracker state.  Normal
queues, bounded retries, and recovery are not warnings; only an explicit
requestor/operator action produces an actionable alert.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from oompah.integration import (
    ACCEPTED_SUBMISSION_STATES,
    REVIEW_GENERATION_REQUEUE_WAIT_REASON,
    direct_epic_maintenance_completion_ready,
    direct_epic_maintenance_handoff_ready,
    review_generation_requeue_marker,
)
from oompah.models import Issue
from oompah.statuses import (
    ARCHIVED,
    BACKLOG,
    DECOMPOSED,
    DONE,
    DUPLICATE_CANDIDATE,
    IN_PROGRESS,
    IN_REVIEW,
    IN_VALIDATION,
    MERGED,
    NEEDS_ANSWER,
    NEEDS_CI_FIX,
    NEEDS_HUMAN,
    NEEDS_REBASE,
    OPEN,
    PROPOSED,
    READY_TO_INTEGRATE,
    canonicalize_status,
)
from oompah.workflow_contract import (
    LIFECYCLE_FINAL_STATUSES,
    STATUS_CONTRACTS,
    TaskDisposition,
    WorkflowOwner,
)
from oompah.workflow_fact_model import (
    FactDomain,
    FactState,
    LandingFact,
    LandingState,
    WorkflowFacts,
)
from oompah.workflow_reasons import (
    AlertSeverity,
    build_liveness_slos,
)

WORK_DECISION_SCHEMA_VERSION = 1
SATISFIED_DEPENDENCY_STATUSES = frozenset({DONE, MERGED, ARCHIVED})
IMPLEMENTATION_ACTION_JOBS = frozenset(
    {
        "implementation_start",
        "direct_owner_claim",
        "duplicate_screening",
        "focus_handoff",
        "worker_exit",
        "validation_submission",
        "authority_revocation",
        "implementation_retry",
        "implementation_recovery",
    }
)

# Review actions are deliberately named independently from the legacy
# maintenance methods.  A controller may materialize these names in the
# durable job ledger and a worker can safely replay them after a restart.
REVIEW_ACTION_JOBS = frozenset(
    {
        "review_monitor",
        "review_merge",
        "review_refresh",
        "review_ci_repair",
        "review_conflict_repair",
        "review_closed_repair",
        "review_head_reconciliation",
        "review_landing_refresh",
        "review_terminal_stage",
        "review_capacity_recheck",
    }
)

_FIXED_DECISION_REASON_CODES = frozenset(
    {
        "coordination.policy_denied",
        "controller.evaluation_failed",
        "dispatch.dependencies_blocked",
        "dispatch.eligible",
        "dispatch.hierarchy_wait",
        "duplicate.confirmed",
        "duplicate.investigating",
        "duplicate.recovery_scheduled",
        "duplicate.screening_disabled",
        "evidence.conflicting_task_facts",
        "evidence.containment_malformed",
        "evidence.dependencies_malformed",
        "evidence.project_or_task_mismatch",
        "evidence.task_fact_identity_mismatch",
        "evidence.task_status_mismatch",
        "implementation.active",
        "implementation.action_scheduled",
        "implementation.recovery_scheduled",
        "implementation.submission_recovery_parked",
        "intake.awaiting_decision",
        "integration.active",
        "integration.dependencies_blocked",
        "integration.gate_blocked",
        "integration.live_claim_precedes_history",
        "integration.landing_proven",
        "integration.landing_unproven",
        "integration.owner_retirement_pending",
        "integration.queued",
        "integration.required_base_missing",
        "integration.retry_scheduled",
        "landing.evidence_unknown",
        "landing.target_evidence_missing",
        "landing.waiting",
        "maintenance.publication_completion_pending",
        "maintenance.publication_proven",
        "graph.impossible",
        "liveness.reassessment_overdue",
        "operator.action_required",
        "ownership.conflict",
        "ownership.impossible",
        "prioritization.awaiting_owner",
        "requestor.answer_required",
        "retry.exhausted",
        "automation.unavailable",
        "review.ci_fix_required",
        "review.ci_pending",
        "review.capacity_wait",
        "review.closed_unmerged",
        "review.draft_wait",
        "review.head_changed",
        "review.landing_refresh",
        "review.merge_target_mismatch",
        "review.missing_artifact",
        "review.monitoring",
        "review.provider_unavailable",
        "review.rebase_required",
        "review.ready_to_merge",
        "review.source_deleted",
        "rollup.children_complete",
        "rollup.children_missing",
        "rollup.status_reconciliation",
        "rollup.waiting_parent_landing",
        "rollup.waiting_children",
        "standalone.delivery_eligible",
        "standalone.remote_identity_ambiguous",
        "standalone.remote_identity_unavailable",
        "standalone.resubmission_required",
        "terminal.final",
        "terminal.immediate_target_landing_proven",
        "terminal.preserve_verified_merged",
        "terminal.provenance_invalid",
        "terminal.provenance_retained",
        "ownership.conflict",
        "ownership.impossible",
        "validation.active",
        "validation.queued",
        "validation.retry_scheduled",
        "workflow.unknown_status",
    }
)
KNOWN_DECISION_REASON_CODES = frozenset(
    _FIXED_DECISION_REASON_CODES
    | {
        f"evidence.{domain.value}_{state.value}"
        for domain in FactDomain
        for state in FactState
    }
)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _required_text(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} is required")
    return text


def _optional_text(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_time(value: object, name: str) -> datetime:
    raw = _required_text(value, name)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{name} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _render_time(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("decision timestamps must include a timezone")
    return value.astimezone(timezone.utc).isoformat()


def _mapping(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def epic_immediate_target_landings(facts: WorkflowFacts) -> tuple[LandingFact, ...]:
    """Return only landing facts for an epic's exact containment target.

    Epic fact snapshots contain both direct-child landings and the epic's own
    landing.  Tracker branch fields can be absent on legacy Done epics, so the
    containment fact is the canonical source/target authority.  Keeping this
    selector shared with the mutation guard prevents an unrelated child landing
    from making the public decision more permissive than the commit boundary.
    """

    containment = facts.fact(FactDomain.CONTAINMENT)
    value = (
        _mapping(containment.value)
        if containment.state is FactState.KNOWN
        else None
    )
    source = str((value or {}).get("epic_branch") or "").strip()
    target = str((value or {}).get("target_branch") or "").strip()
    if not source or not target:
        return ()
    return tuple(
        item
        for item in facts.landings
        if item.source == source and item.target == target
    )


class PermittedAction(str, Enum):
    """Stable actions consumers may offer or enqueue for a decision."""

    ACCEPT_INTAKE = "accept_intake"
    PROMOTE_OPEN = "promote_open"
    CLAIM_IMPLEMENTATION = "claim_implementation"
    WAIT_DEPENDENCY = "wait_dependency"
    RECOVER_IMPLEMENTATION = "recover_implementation"
    CONTINUE_IMPLEMENTATION = "continue_implementation"
    RECONCILE_IMPLEMENTATION = "reconcile_implementation"
    ANSWER_REQUEST = "answer_request"
    RESOLVE_OPERATOR_ACTION = "resolve_operator_action"
    CLAIM_REPAIR = "claim_repair"
    REFRESH_REVIEW = "refresh_review"
    MERGE_REVIEW = "merge_review"
    ROUTE_CI_FIX = "route_ci_fix"
    ROUTE_REBASE = "route_rebase"
    CLAIM_AUDIT = "claim_audit"
    RETRY_AUDIT = "retry_audit"
    CLAIM_INTEGRATION = "claim_integration"
    RECONCILE_TARGET = "reconcile_target"
    ROLLUP_CHILDREN = "rollup_children"
    INVESTIGATE_DUPLICATE = "investigate_duplicate"
    REFRESH_LANDING = "refresh_landing"
    REQUEST_DONE = "request_done"
    REQUEST_MERGED = "request_merged"


@dataclass(frozen=True, slots=True)
class UnmetPrerequisite:
    """Machine-readable reason one otherwise valid action cannot run."""

    code: str
    subject: str
    observed: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", _required_text(self.code, "code"))
        object.__setattr__(self, "subject", _required_text(self.subject, "subject"))
        object.__setattr__(self, "observed", _optional_text(self.observed))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "subject": self.subject,
            "observed": self.observed,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "UnmetPrerequisite":
        return cls(**dict(raw))


@dataclass(frozen=True, slots=True)
class WorkDecision:
    """Complete, serializable answer for one exact facts revision."""

    project_id: str
    task_id: str
    status: str
    disposition: TaskDisposition | str
    reason_code: str
    responsible_owner: WorkflowOwner | str
    unmet_prerequisites: tuple[UnmetPrerequisite, ...]
    evidence_revision: str
    next_reassessment_at: str | None
    permitted_actions: tuple[PermittedAction | str, ...]
    action_required: bool
    alert_level: AlertSeverity | str
    durable_jobs: tuple[str, ...] = ()
    recommended_status: str | None = None
    decision_revision: str | None = None
    schema_version: int = WORK_DECISION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "project_id", _required_text(self.project_id, "project_id")
        )
        object.__setattr__(self, "task_id", _required_text(self.task_id, "task_id"))
        object.__setattr__(self, "status", canonicalize_status(self.status))
        object.__setattr__(self, "disposition", TaskDisposition(self.disposition))
        object.__setattr__(
            self, "reason_code", _required_text(self.reason_code, "reason_code")
        )
        if self.reason_code not in KNOWN_DECISION_REASON_CODES:
            raise ValueError(f"unknown work-decision reason_code: {self.reason_code!r}")
        object.__setattr__(
            self, "responsible_owner", WorkflowOwner(self.responsible_owner)
        )
        raw_prerequisites = tuple(self.unmet_prerequisites)
        if any(not isinstance(item, UnmetPrerequisite) for item in raw_prerequisites):
            raise TypeError("unmet_prerequisites must contain UnmetPrerequisite values")
        prerequisites = tuple(
            sorted(
                raw_prerequisites,
                key=lambda item: (item.code, item.subject, item.observed or ""),
            )
        )
        object.__setattr__(self, "unmet_prerequisites", prerequisites)
        object.__setattr__(
            self,
            "evidence_revision",
            _required_text(self.evidence_revision, "evidence_revision"),
        )
        if self.next_reassessment_at is not None:
            object.__setattr__(
                self,
                "next_reassessment_at",
                _render_time(
                    _parse_time(self.next_reassessment_at, "next_reassessment_at")
                ),
            )
        actions = tuple(
            sorted(
                {PermittedAction(item) for item in self.permitted_actions},
                key=lambda item: item.value,
            )
        )
        object.__setattr__(self, "permitted_actions", actions)
        object.__setattr__(self, "alert_level", AlertSeverity(self.alert_level))
        jobs = tuple(
            sorted({_required_text(item, "durable_job") for item in self.durable_jobs})
        )
        object.__setattr__(self, "durable_jobs", jobs)
        recommended = _optional_text(self.recommended_status)
        object.__setattr__(
            self,
            "recommended_status",
            canonicalize_status(recommended) if recommended else None,
        )
        if self.schema_version != WORK_DECISION_SCHEMA_VERSION:
            raise ValueError("unsupported WorkDecision schema_version")
        if self.action_required != (
            self.disposition is TaskDisposition.ACTION_REQUIRED
        ):
            raise ValueError("action_required must match ACTION_REQUIRED disposition")
        if self.action_required and self.alert_level not in {
            AlertSeverity.WARNING,
            AlertSeverity.CRITICAL,
        }:
            raise ValueError("action-required decisions must be visibly alerting")
        if not self.action_required and self.alert_level in {
            AlertSeverity.WARNING,
            AlertSeverity.CRITICAL,
        }:
            raise ValueError("normal/recovery decisions cannot be warnings")
        expected = self.compute_decision_revision()
        if self.decision_revision is not None and self.decision_revision != expected:
            raise ValueError("decision_revision does not match decision content")
        object.__setattr__(self, "decision_revision", expected)

    def compute_decision_revision(self) -> str:
        raw = self.to_dict()
        raw.pop("decision_revision", None)
        return _digest(raw)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "project_id": self.project_id,
            "task_id": self.task_id,
            "status": self.status,
            "disposition": self.disposition.value,
            "reason_code": self.reason_code,
            "responsible_owner": self.responsible_owner.value,
            "unmet_prerequisites": [
                item.to_dict() for item in self.unmet_prerequisites
            ],
            "evidence_revision": self.evidence_revision,
            "next_reassessment_at": self.next_reassessment_at,
            "permitted_actions": [item.value for item in self.permitted_actions],
            "action_required": self.action_required,
            "alert_level": self.alert_level.value,
            "durable_jobs": list(self.durable_jobs),
            "recommended_status": self.recommended_status,
            "decision_revision": self.decision_revision,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "WorkDecision":
        if not isinstance(raw, Mapping):
            raise ValueError("WorkDecision must be an object")
        values = dict(raw)
        values["unmet_prerequisites"] = tuple(
            UnmetPrerequisite.from_dict(item)
            for item in values.get("unmet_prerequisites", ())
        )
        values["permitted_actions"] = tuple(values.get("permitted_actions", ()))
        values["durable_jobs"] = tuple(values.get("durable_jobs", ()))
        return cls(**values)


def decision_scheduling_revision(
    decision: WorkDecision,
    *,
    policy_epoch: str = "standalone-v1",
) -> str:
    """Hash durable scheduling semantics without an observation timestamp.

    Whether a decision recurs is semantic, while its absolute reassessment
    timestamp is not. The liveness-policy epoch fences SLO changes without
    creating wall-clock revision buckets.
    """

    if not isinstance(decision, WorkDecision):
        raise TypeError("decision must be a WorkDecision")
    normalized_epoch = str(policy_epoch or "").strip()
    if not normalized_epoch:
        raise ValueError("policy_epoch is required")
    raw = decision.to_dict()
    raw.pop("decision_revision", None)
    raw.pop("next_reassessment_at", None)
    recurring = decision.next_reassessment_at is not None
    raw["recurrence"] = {
        "enabled": recurring,
        "policy_epoch": normalized_epoch if recurring else None,
    }
    return _digest(raw)


@dataclass(frozen=True, slots=True)
class _TaskView:
    project_id: str
    task_id: str
    status: str
    parent_id: str | None
    issue_type: str
    target_branch: str | None


def _task_view(task: Issue | Mapping[str, Any]) -> _TaskView:
    if isinstance(task, Issue):
        return _TaskView(
            str(task.project_id or ""),
            task.identifier,
            canonicalize_status(task.state),
            _optional_text(task.parent_id),
            str(task.issue_type or "task"),
            _optional_text(task.target_branch),
        )
    if not isinstance(task, Mapping):
        raise TypeError("task must be an Issue or mapping")
    return _TaskView(
        str(task.get("project_id") or ""),
        _required_text(task.get("identifier", task.get("task_id")), "task_id"),
        canonicalize_status(task.get("status", task.get("state"))),
        _optional_text(task.get("parent_id")),
        str(task.get("issue_type") or "task"),
        _optional_text(task.get("target_branch")),
    )


def _terminal_landing_identity(
    task: Issue | Mapping[str, Any],
) -> tuple[str, str, str] | None:
    """Return the exact accepted source/target/revision for terminal proof.

    A positive landing fact is project-scoped, but that alone is not enough
    to explain why *this* task is safely Merged.  Require all three immutable
    integration coordinates so an unrelated durable LANDED observation can
    never upgrade the terminal reason or mask corrupt task evidence.
    """

    if isinstance(task, Issue):
        integration = getattr(task, "integration", None)
        source = str(
            getattr(integration, "task_branch", "")
            or getattr(task, "work_branch", "")
            or ""
        ).strip()
        target = str(
            getattr(integration, "base_branch", "")
            or getattr(task, "target_branch", "")
            or ""
        ).strip()
        revision = str(
            getattr(integration, "integrated_sha", "")
            or getattr(integration, "head_sha", "")
            or getattr(task, "head_sha", "")
            or ""
        ).strip().lower()
    else:
        integration = _mapping(task.get("integration")) or {}
        source = str(
            integration.get("task_branch") or task.get("work_branch") or ""
        ).strip()
        target = str(
            integration.get("base_branch") or task.get("target_branch") or ""
        ).strip()
        revision = str(
            integration.get("integrated_sha")
            or integration.get("head_sha")
            or task.get("head_sha")
            or ""
        ).strip().lower()
    return (source, target, revision) if source and target and revision else None


def _reassessment(status: str, collected_at: str) -> str | None:
    contract = STATUS_CONTRACTS.get(status)
    if contract is None or contract.reassessment.slo_key is None:
        return None
    slo = build_liveness_slos()[contract.reassessment.slo_key]
    return _render_time(
        _parse_time(collected_at, "collected_at")
        + timedelta(seconds=slo.max_reassessment_seconds)
    )


def _prerequisites(
    facts: WorkflowFacts,
) -> tuple[tuple[UnmetPrerequisite, ...], tuple[UnmetPrerequisite, ...]]:
    observation = facts.fact(FactDomain.DEPENDENCIES)
    if observation.state is not FactState.KNOWN:
        unknown = (
            UnmetPrerequisite(
                f"dependencies.{observation.state.value}",
                FactDomain.DEPENDENCIES.value,
                observation.error_code,
            ),
        )
        return unknown, unknown
    value = _mapping(observation.value)
    if value is None:
        malformed = (UnmetPrerequisite("dependencies.malformed", "dependencies"),)
        return malformed, malformed

    def unresolved(kind: str) -> tuple[UnmetPrerequisite, ...]:
        raw_items = value.get(kind, ())
        if not isinstance(raw_items, (tuple, list)):
            return (UnmetPrerequisite("dependencies.malformed", kind),)
        result: list[UnmetPrerequisite] = []
        for item in raw_items:
            entry = _mapping(item)
            if entry is None:
                result.append(UnmetPrerequisite("dependencies.malformed", kind))
                continue
            identifier = str(entry.get("identifier") or entry.get("id") or "unknown")
            status = canonicalize_status(entry.get("status"))
            if status not in SATISFIED_DEPENDENCY_STATUSES:
                result.append(
                    UnmetPrerequisite(
                        f"dependencies.{kind}_incomplete", identifier, status
                    )
                )
        return tuple(result)

    return unresolved("finish"), unresolved("hard_start")


def _valid_lease(value: Mapping[str, Any], now: datetime) -> bool:
    expiry = value.get("lease_expires_at")
    if not expiry:
        return False
    try:
        return _parse_time(expiry, "lease_expires_at") > now
    except ValueError:
        return False


def _valid_active_job(value: Mapping[str, Any]) -> bool:
    """Require an explicit live observation tied to a stable job identity."""

    return bool(
        value.get("actively_working") is True
        and str(
            value.get("active_job_id")
            or value.get("job_id")
            or value.get("audit_id")
            or ""
        ).strip()
    )
def _owner_for_status(status: str) -> WorkflowOwner:
    contract = STATUS_CONTRACTS.get(status)
    if contract is None or not contract.owners:
        return WorkflowOwner.OPERATOR
    preferred = (
        WorkflowOwner.DISPATCHER,
        WorkflowOwner.IMPLEMENTER,
        WorkflowOwner.REPAIR_WORKER,
        WorkflowOwner.REVIEW_MONITOR,
        WorkflowOwner.AUDITOR,
        WorkflowOwner.INTEGRATOR,
        WorkflowOwner.ROLLUP,
        WorkflowOwner.DUPLICATE_INVESTIGATOR,
        WorkflowOwner.PROJECT_OWNER,
        WorkflowOwner.INTAKE,
        WorkflowOwner.REQUESTOR,
        WorkflowOwner.OPERATOR,
        WorkflowOwner.NONE,
    )
    return next(owner for owner in preferred if owner in contract.owners)


def _decision(
    task: _TaskView,
    facts: WorkflowFacts,
    *,
    disposition: TaskDisposition,
    reason_code: str,
    owner: WorkflowOwner | None = None,
    prerequisites: tuple[UnmetPrerequisite, ...] = (),
    actions: tuple[PermittedAction, ...] = (),
    alert: AlertSeverity = AlertSeverity.NONE,
    durable_jobs: tuple[str, ...] = (),
    recommended_status: str | None = None,
    reassess: bool = True,
) -> WorkDecision:
    return WorkDecision(
        project_id=facts.project_id,
        task_id=facts.task_id,
        status=task.status,
        disposition=disposition,
        reason_code=reason_code,
        responsible_owner=owner or _owner_for_status(task.status),
        unmet_prerequisites=prerequisites,
        evidence_revision=facts.facts_version,
        next_reassessment_at=(
            _reassessment(task.status, facts.collected_at) if reassess else None
        ),
        permitted_actions=actions,
        action_required=disposition is TaskDisposition.ACTION_REQUIRED,
        alert_level=alert,
        durable_jobs=durable_jobs,
        recommended_status=recommended_status,
    )


def _fact_wait(
    task: _TaskView,
    facts: WorkflowFacts,
    domain: FactDomain,
    *,
    owner: WorkflowOwner,
    action: PermittedAction,
    job: str,
) -> WorkDecision:
    observation = facts.fact(domain)
    reason_code = (
        "review.provider_unavailable"
        if domain is FactDomain.REVIEW_CI and observation.state is FactState.ERROR
        else f"evidence.{domain.value}_{observation.state.value}"
    )
    return _decision(
        task,
        facts,
        disposition=TaskDisposition.RETRY_SCHEDULED,
        reason_code=reason_code,
        owner=owner,
        prerequisites=(
            UnmetPrerequisite(
                f"evidence.{observation.state.value}",
                domain.value,
                observation.error_code,
            ),
        ),
        actions=(action,),
        alert=AlertSeverity.INFO,
        durable_jobs=(job,),
    )


def _implementation_decision(
    task: _TaskView, facts: WorkflowFacts, now: datetime
) -> WorkDecision:
    config = facts.fact(FactDomain.CONFIG)
    config_value = _mapping(config.value) if config.state is FactState.KNOWN else None
    pending_action = (
        str(config_value.get("implementation_pending_action") or "").strip()
        if config_value
        else ""
    )
    if pending_action not in IMPLEMENTATION_ACTION_JOBS:
        pending_action = ""
    authority = facts.fact(FactDomain.IMPLEMENTATION_AUTHORITY)
    authority_value = (
        _mapping(authority.value) if authority.state is FactState.KNOWN else None
    )
    authority_independent_actions = {
        "direct_owner_claim",
        "duplicate_screening",
        "focus_handoff",
        "implementation_recovery",
        "implementation_start",
        "validation_submission",
    }
    if pending_action and (
        pending_action in authority_independent_actions
        or (authority_value is not None and _valid_lease(authority_value, now))
    ):
        return _decision(
            task,
            facts,
            disposition=TaskDisposition.RETRY_SCHEDULED,
            reason_code="implementation.action_scheduled",
            owner=WorkflowOwner.DISPATCHER,
            actions=(PermittedAction.RECONCILE_IMPLEMENTATION,),
            alert=AlertSeverity.INFO,
            durable_jobs=(pending_action,),
        )
    submission_recovery_state = str(
        (config_value or {}).get("accepted_submission_recovery_state") or ""
    ).strip()
    if submission_recovery_state.startswith("accepted_submission_"):
        # Accepted integration metadata is stronger than an expired or absent
        # implementer lease.  Exact/landed evidence publishes
        # ``validation_submission`` above; every other accepted state is an
        # explicit fail-closed park and must remain jobless.  Scheduling a
        # generic recovery here only creates an immediate supersede loop at
        # the provider boundary.
        return _decision(
            task,
            facts,
            disposition=TaskDisposition.BLOCKED,
            reason_code="implementation.submission_recovery_parked",
            owner=WorkflowOwner.DISPATCHER,
            actions=(PermittedAction.RECONCILE_IMPLEMENTATION,),
            alert=AlertSeverity.INFO,
        )
    if authority.state is not FactState.KNOWN or _mapping(authority.value) is None:
        return _fact_wait(
            task,
            facts,
            FactDomain.IMPLEMENTATION_AUTHORITY,
            owner=WorkflowOwner.DISPATCHER,
            action=PermittedAction.RECOVER_IMPLEMENTATION,
            job="implementation_recovery",
        )
    value = authority_value
    assert value is not None
    if bool(value.get("transition_pending")) and value.get("state") == "retry_wait":
        return _decision(
            task,
            facts,
            disposition=TaskDisposition.RETRY_SCHEDULED,
            reason_code="implementation.action_scheduled",
            owner=WorkflowOwner.DISPATCHER,
            actions=(PermittedAction.RECONCILE_IMPLEMENTATION,),
            alert=AlertSeverity.INFO,
        )
    if bool(value.get("transition_pending")) and value.get("state") in {
        "submitted",
        "revoked",
        "completed",
    }:
        return _decision(
            task,
            facts,
            disposition=TaskDisposition.OWNED,
            reason_code="implementation.active",
            owner=WorkflowOwner.DISPATCHER,
            actions=(PermittedAction.CONTINUE_IMPLEMENTATION,),
        )
    if _valid_active_job(value) or _valid_lease(value, now):
        owner = (
            WorkflowOwner.DIRECT_OWNER
            if value.get("ownership_source") == "direct_owner"
            else WorkflowOwner.IMPLEMENTER
        )
        return _decision(
            task,
            facts,
            disposition=TaskDisposition.OWNED,
            reason_code=(
                "coordination.policy_denied"
                if config_value
                and bool(config_value.get("coordination_policy_denied"))
                else "implementation.active"
            ),
            owner=owner,
            actions=(PermittedAction.CONTINUE_IMPLEMENTATION,),
        )
    return _decision(
        task,
        facts,
        disposition=TaskDisposition.RETRY_SCHEDULED,
        reason_code="implementation.recovery_scheduled",
        owner=WorkflowOwner.DISPATCHER,
        actions=(PermittedAction.RECOVER_IMPLEMENTATION,),
        alert=AlertSeverity.INFO,
        durable_jobs=("implementation_recovery",),
    )


def _review_decision(task: _TaskView, facts: WorkflowFacts) -> WorkDecision:
    review = facts.fact(FactDomain.REVIEW_CI)
    value = _mapping(review.value) if review.state is FactState.KNOWN else None
    if value is None:
        return _fact_wait(
            task,
            facts,
            FactDomain.REVIEW_CI,
            owner=WorkflowOwner.REVIEW_MONITOR,
            action=PermittedAction.REFRESH_REVIEW,
            job="review_refresh",
        )

    # The collector uses ``state=missing`` for a successful empty forge
    # result.  This must remain distinct from FactState.ERROR/STALE above:
    # empty means the provider answered, whereas error means it did not.
    state = str(value.get("state") or "open").strip().lower()
    task_fact = _mapping(facts.fact(FactDomain.TASK).value) or {}
    expected_target = str(
        task.target_branch or task_fact.get("target_branch") or ""
    ).strip()
    expected_source = str(
        task_fact.get("work_branch")
        or task_fact.get("branch_name")
        or task.task_id
    ).strip()
    observed_target = str(value.get("target_branch") or "").strip()
    if observed_target and expected_target and observed_target != expected_target:
        return _decision(
            task,
            facts,
            disposition=TaskDisposition.ACTION_REQUIRED,
            reason_code="review.merge_target_mismatch",
            owner=WorkflowOwner.OPERATOR,
            prerequisites=(
                UnmetPrerequisite(
                    "review.merge_target_mismatch",
                    expected_target,
                    observed_target,
                ),
            ),
            actions=(PermittedAction.RESOLVE_OPERATOR_ACTION,),
            alert=AlertSeverity.WARNING,
            recommended_status=NEEDS_HUMAN,
        )

    recorded_head = str(task_fact.get("review_head") or "").strip().lower()
    current_head = str(task_fact.get("head_sha") or "").strip().lower()
    observed_head = str(value.get("head_sha") or "").strip().lower()
    integration_fact = facts.fact(FactDomain.INTEGRATION)
    integration_value = (
        _mapping(integration_fact.value)
        if integration_fact.state is FactState.KNOWN
        else None
    ) or {}
    recorded_base = str(integration_value.get("base_sha") or "").strip().lower()
    recorded_base_branch = str(
        integration_value.get("base_branch") or ""
    ).strip()
    observed_base = str(value.get("base_sha") or "").strip().lower()
    expected_head = recorded_head or current_head
    changed_head = ""
    if recorded_head and current_head and recorded_head != current_head:
        changed_head = current_head
    if expected_head and observed_head and expected_head != observed_head:
        changed_head = observed_head
    changed_base = bool(
        recorded_base and observed_base and recorded_base != observed_base
    )
    observed_generation_marker = review_generation_requeue_marker(
        value.get("review_id"),
        observed_head,
        observed_base,
    )
    recorded_review = str(task_fact.get("review_number") or "").strip()
    observed_review = str(value.get("review_id") or "").strip()
    integration_head = str(
        integration_value.get("head_sha") or ""
    ).strip().lower()
    integration_source = str(
        integration_value.get("task_branch") or ""
    ).strip()
    source_repository = str(
        value.get("source_repository") or ""
    ).strip().casefold()
    target_repository = str(
        value.get("target_repository") or ""
    ).strip().casefold()
    observed_source = str(value.get("source_branch") or "").strip()
    missing_base_identity = bool(
        str(integration_value.get("state") or "").strip().lower()
        in ACCEPTED_SUBMISSION_STATES
        and str(integration_value.get("mode") or "standalone").strip().lower()
        == "standalone"
        and observed_generation_marker is not None
        and expected_head
        and integration_head == expected_head
        and observed_head == expected_head
        and recorded_review
        and observed_review == recorded_review
        and expected_source
        and observed_source == expected_source
        and integration_source == expected_source
        and expected_target
        and observed_target == expected_target
        and recorded_base_branch in {"", expected_target}
        and source_repository
        and source_repository == target_repository
        and (not recorded_base or not recorded_base_branch)
    )
    pending_generation = bool(
        integration_value.get("wait_reason")
        == REVIEW_GENERATION_REQUEUE_WAIT_REASON
        and observed_generation_marker is not None
        and integration_value.get("wait_generation")
        == observed_generation_marker
    )
    if changed_head or changed_base or missing_base_identity or pending_generation:
        current_generation = changed_head or observed_head or expected_head
        return _decision(
            task,
            facts,
            disposition=TaskDisposition.RETRY_SCHEDULED,
            reason_code="review.head_changed",
            owner=WorkflowOwner.REVIEW_MONITOR,
            prerequisites=(
                UnmetPrerequisite(
                    "review.head_changed",
                    f"{expected_head}@{recorded_base or '<missing-base>'}",
                    f"{current_generation}@{observed_base or '<missing-base>'}",
                ),
            ),
            actions=(PermittedAction.ROUTE_REBASE,),
            alert=AlertSeverity.INFO,
            durable_jobs=("review_head_reconciliation",),
            recommended_status=READY_TO_INTEGRATE,
        )

    def exact_landings() -> tuple[Any, ...]:
        return tuple(
            item
            for item in facts.landings
            if item.state is LandingState.LANDED
            and item.durable
            and (not expected_source or item.source == expected_source)
            and (not expected_target or item.target == expected_target)
            and (not expected_head or item.revision == expected_head)
        )

    landed_review_status = (
        DONE
        if task.parent_id and task.issue_type.strip().lower() != "epic"
        else MERGED
    )
    landed_review_action = (
        PermittedAction.REQUEST_DONE
        if landed_review_status == DONE
        else PermittedAction.REQUEST_MERGED
    )

    if state in {"missing", "not_found", "none"} or value.get("present") is False:
        landed = exact_landings()
        if landed:
            return _decision(
                task,
                facts,
                disposition=TaskDisposition.TERMINAL,
                reason_code="terminal.immediate_target_landing_proven",
                owner=WorkflowOwner.REVIEW_MONITOR,
                actions=(landed_review_action,),
                durable_jobs=("review_terminal_stage",),
                recommended_status=landed_review_status,
            )
        if bool(value.get("source_deleted")):
            return _decision(
                task,
                facts,
                disposition=TaskDisposition.ACTION_REQUIRED,
                reason_code="review.source_deleted",
                owner=WorkflowOwner.OPERATOR,
                prerequisites=(
                    UnmetPrerequisite(
                        "review.source_deleted",
                        str(value.get("source_branch") or "review_source"),
                    ),
                ),
                actions=(PermittedAction.RESOLVE_OPERATOR_ACTION,),
                alert=AlertSeverity.WARNING,
                recommended_status=NEEDS_HUMAN,
            )
        return _decision(
            task,
            facts,
            disposition=TaskDisposition.RETRY_SCHEDULED,
            reason_code="review.missing_artifact",
            owner=WorkflowOwner.REVIEW_MONITOR,
            prerequisites=(
                UnmetPrerequisite(
                    "review.missing_artifact",
                    str(value.get("source_branch") or "review"),
                ),
            ),
            actions=(PermittedAction.REFRESH_REVIEW,),
            alert=AlertSeverity.INFO,
            durable_jobs=("review_refresh",),
        )

    if state in {"merged", "closed_merged"}:
        landed = exact_landings()
        if landed:
            return _decision(
                task,
                facts,
                disposition=TaskDisposition.TERMINAL,
                reason_code="terminal.immediate_target_landing_proven",
                owner=WorkflowOwner.REVIEW_MONITOR,
                actions=(landed_review_action,),
                durable_jobs=("review_terminal_stage",),
                recommended_status=landed_review_status,
            )
        return _decision(
            task,
            facts,
            disposition=TaskDisposition.RETRY_SCHEDULED,
            reason_code="review.landing_refresh",
            owner=WorkflowOwner.REVIEW_MONITOR,
            prerequisites=(
                UnmetPrerequisite(
                    "review.landing_unknown",
                    expected_target or "review_target",
                ),
            ),
            actions=(PermittedAction.REFRESH_LANDING,),
            alert=AlertSeverity.INFO,
            durable_jobs=("review_landing_refresh",),
        )

    if state in {"closed", "closed_unmerged"}:
        return _decision(
            task,
            facts,
            disposition=TaskDisposition.OWNED,
            reason_code="review.closed_unmerged",
            owner=WorkflowOwner.REPAIR_WORKER,
            actions=(PermittedAction.CLAIM_REPAIR,),
            durable_jobs=("review_closed_repair",),
            recommended_status=OPEN,
        )

    if bool(value.get("draft")):
        return _decision(
            task,
            facts,
            disposition=TaskDisposition.OWNED,
            reason_code="review.draft_wait",
            owner=WorkflowOwner.REVIEW_MONITOR,
            actions=(PermittedAction.REFRESH_REVIEW,),
            durable_jobs=("review_monitor",),
        )

    ci = str(value.get("ci") or "unknown").strip().lower()
    if ci in {"failed", "failure"}:
        return _decision(
            task,
            facts,
            disposition=TaskDisposition.OWNED,
            reason_code="review.ci_fix_required",
            owner=WorkflowOwner.REVIEW_MONITOR,
            actions=(PermittedAction.ROUTE_CI_FIX,),
            durable_jobs=("review_ci_repair",),
            recommended_status=NEEDS_CI_FIX,
        )
    if (
        value.get("conflict")
        or value.get("needs_rebase")
        or value.get("mergeable") is False
        or str(value.get("mergeable_state") or "").strip().lower()
        in {"dirty", "behind"}
    ):
        return _decision(
            task,
            facts,
            disposition=TaskDisposition.OWNED,
            reason_code="review.rebase_required",
            owner=WorkflowOwner.REVIEW_MONITOR,
            actions=(PermittedAction.ROUTE_REBASE,),
            durable_jobs=("review_conflict_repair",),
            recommended_status=NEEDS_REBASE,
        )
    if ci in {"pending", "unknown", ""}:
        return _decision(
            task,
            facts,
            disposition=TaskDisposition.OWNED,
            reason_code="review.ci_pending",
            owner=WorkflowOwner.REVIEW_MONITOR,
            actions=(PermittedAction.REFRESH_REVIEW,),
            durable_jobs=("review_monitor",),
        )
    if ci in {"passed", "success", "successful"}:
        if bool(value.get("auto_merge_enabled")):
            return _decision(
                task,
                facts,
                disposition=TaskDisposition.OWNED,
                reason_code="review.monitoring",
                owner=WorkflowOwner.REVIEW_MONITOR,
                actions=(PermittedAction.REFRESH_REVIEW,),
                durable_jobs=("review_monitor",),
            )
        return _decision(
            task,
            facts,
            disposition=TaskDisposition.OWNED,
            reason_code="review.ready_to_merge",
            owner=WorkflowOwner.REVIEW_MONITOR,
            actions=(PermittedAction.MERGE_REVIEW,),
            durable_jobs=("review_merge",),
        )
    return _decision(
        task,
        facts,
        disposition=TaskDisposition.OWNED,
        reason_code="review.monitoring",
        owner=WorkflowOwner.REVIEW_MONITOR,
        actions=(PermittedAction.REFRESH_REVIEW,),
        durable_jobs=("review_monitor",),
    )


def _validation_decision(
    task: _TaskView, facts: WorkflowFacts, now: datetime
) -> WorkDecision:
    audit = facts.fact(FactDomain.TERMINAL_AUDIT)
    value = _mapping(audit.value) if audit.state is FactState.KNOWN else None
    if value is None:
        return _fact_wait(
            task,
            facts,
            FactDomain.TERMINAL_AUDIT,
            owner=WorkflowOwner.AUDITOR,
            action=PermittedAction.RETRY_AUDIT,
            job="terminal_audit_recovery",
        )
    # Quarantined or unsafe evidence cannot be automatically retried: the
    # metadata is corrupt or the audit found an unsafe archive condition.
    if bool(value.get("quarantined")) or bool(value.get("unsafe")):
        return _decision(
            task,
            facts,
            disposition=TaskDisposition.ACTION_REQUIRED,
            reason_code="operator.action_required",
            owner=WorkflowOwner.OPERATOR,
            prerequisites=(
                UnmetPrerequisite(
                    str(value.get("action_code") or "audit.evidence_unsafe"),
                    "terminal_audit",
                ),
            ),
            actions=(PermittedAction.RESOLVE_OPERATOR_ACTION,),
            alert=AlertSeverity.WARNING,
        )
    if bool(value.get("action_required")):
        return _decision(
            task,
            facts,
            disposition=TaskDisposition.ACTION_REQUIRED,
            reason_code="operator.action_required",
            owner=WorkflowOwner.OPERATOR,
            prerequisites=(
                UnmetPrerequisite(
                    str(value.get("action_code") or "audit.action_required"),
                    "terminal_audit",
                ),
            ),
            actions=(PermittedAction.RESOLVE_OPERATOR_ACTION,),
            alert=AlertSeverity.WARNING,
        )
    if value.get("phase") == "active":
        if _valid_active_job(value) or _valid_lease(value, now):
            return _decision(
                task,
                facts,
                disposition=TaskDisposition.OWNED,
                reason_code="validation.active",
                owner=WorkflowOwner.AUDITOR,
                actions=(PermittedAction.RETRY_AUDIT,),
            )
        return _decision(
            task,
            facts,
            disposition=TaskDisposition.RETRY_SCHEDULED,
            reason_code="validation.retry_scheduled",
            owner=WorkflowOwner.AUDITOR,
            actions=(PermittedAction.RETRY_AUDIT,),
            alert=AlertSeverity.INFO,
            durable_jobs=("terminal_audit_recovery",),
        )
    return _decision(
        task,
        facts,
        disposition=TaskDisposition.RETRY_SCHEDULED,
        reason_code=(
            "validation.retry_scheduled"
            if value.get("retry_at")
            else "validation.queued"
        ),
        owner=WorkflowOwner.AUDITOR,
        actions=(PermittedAction.CLAIM_AUDIT,),
        alert=AlertSeverity.INFO if value.get("retry_at") else AlertSeverity.NONE,
        durable_jobs=("terminal_audit",),
    )


def _integration_decision(
    task: _TaskView,
    facts: WorkflowFacts,
    now: datetime,
    finish: tuple[UnmetPrerequisite, ...],
    hard_start: tuple[UnmetPrerequisite, ...],
) -> WorkDecision:
    implementation = facts.fact(FactDomain.IMPLEMENTATION_AUTHORITY)
    implementation_value = (
        _mapping(implementation.value)
        if implementation.state is FactState.KNOWN
        else None
    )
    if implementation.state is FactState.ERROR or (
        implementation.state is FactState.KNOWN
        and implementation_value is None
    ):
        # Once direct-owner retirement participates in the integration handoff,
        # an authority-read failure cannot be interpreted as proof that no claim
        # exists. Keep the integration lane jobless until a clean fact cut.
        return _decision(
            task,
            facts,
            disposition=TaskDisposition.RETRY_SCHEDULED,
            reason_code=(
                f"evidence.{FactDomain.IMPLEMENTATION_AUTHORITY.value}_"
                f"{implementation.state.value}"
            ),
            owner=WorkflowOwner.INTEGRATOR,
            prerequisites=(
                UnmetPrerequisite(
                    f"evidence.{implementation.state.value}",
                    FactDomain.IMPLEMENTATION_AUTHORITY.value,
                    implementation.error_code,
                ),
            ),
            actions=(PermittedAction.CLAIM_INTEGRATION,),
            alert=AlertSeverity.INFO,
        )
    if (
        implementation_value is not None
        and implementation_value.get("ownership_source") == "direct_owner"
        and str(implementation_value.get("generation") or "").strip()
    ):
        # Ready is only an integration handoff after the captured direct-owner
        # generation has disappeared.  A persisted retirement marker is not a
        # release: keeping this decision jobless prevents a standalone/shared
        # gate from materializing while the exact revocation event completes.
        return _decision(
            task,
            facts,
            disposition=TaskDisposition.OWNED,
            reason_code="integration.owner_retirement_pending",
            owner=WorkflowOwner.DIRECT_OWNER,
            prerequisites=(
                UnmetPrerequisite(
                    "integration.owner_retirement_pending",
                    str(implementation_value.get("generation")),
                ),
            ),
            actions=(PermittedAction.CONTINUE_IMPLEMENTATION,),
        )
    integration = facts.fact(FactDomain.INTEGRATION)
    value = (
        _mapping(integration.value) if integration.state is FactState.KNOWN else None
    )
    if value is None:
        return _fact_wait(
            task,
            facts,
            FactDomain.INTEGRATION,
            owner=WorkflowOwner.INTEGRATOR,
            action=PermittedAction.CLAIM_INTEGRATION,
            job="integration_recovery",
        )
    required_base = value.get("required_base_missing")
    if isinstance(required_base, (tuple, list)) and required_base:
        return _decision(
            task,
            facts,
            disposition=TaskDisposition.RETRY_SCHEDULED,
            reason_code="integration.required_base_missing",
            owner=WorkflowOwner.INTEGRATOR,
            prerequisites=tuple(
                UnmetPrerequisite("integration.required_base_missing", str(item))
                for item in required_base
            ),
            actions=(PermittedAction.RECONCILE_TARGET,),
            alert=AlertSeverity.INFO,
            durable_jobs=("epic_branch_reconciliation",),
        )
    if finish or hard_start:
        return _decision(
            task,
            facts,
            disposition=TaskDisposition.BLOCKED,
            reason_code="integration.dependencies_blocked",
            owner=WorkflowOwner.INTEGRATOR,
            prerequisites=finish + hard_start,
            actions=(PermittedAction.WAIT_DEPENDENCY,),
        )
    # A current exact live claim outranks a historical action-required fact.
    if bool(value.get("live_claim_precedes_history")):
        return _decision(
            task,
            facts,
            disposition=TaskDisposition.OWNED,
            reason_code="integration.live_claim_precedes_history",
            owner=WorkflowOwner.INTEGRATOR,
            actions=(PermittedAction.CLAIM_INTEGRATION,),
            # Historical rows are scheduled independently in the bounded,
            # low-priority project-maintenance lane.  Coupling that job to the
            # live task would enqueue it first alphabetically at the same
            # priority and recreate OOMPAH-749 starvation.
            durable_jobs=("integration_attempt",),
        )
    if bool(value.get("action_required")):
        return _decision(
            task,
            facts,
            disposition=TaskDisposition.ACTION_REQUIRED,
            reason_code="operator.action_required",
            owner=WorkflowOwner.OPERATOR,
            prerequisites=(
                UnmetPrerequisite(
                    str(value.get("action_code") or "integration.action_required"),
                    "integration",
                ),
            ),
            actions=(PermittedAction.RESOLVE_OPERATOR_ACTION,),
            alert=AlertSeverity.WARNING,
        )
    if value.get("state") == "integrated":
        expected_revision = str(
            value.get("integrated_sha") or value.get("head_sha") or ""
        ).strip()
        target = str(value.get("base_branch") or task.target_branch or "").strip()
        landing = next(
            (
                item
                for item in facts.landings
                if (not expected_revision or item.revision == expected_revision)
                and (not target or item.target == target)
            ),
            None,
        )
        if landing is not None and landing.state is LandingState.LANDED:
            return _decision(
                task,
                facts,
                disposition=TaskDisposition.RETRY_SCHEDULED,
                reason_code="integration.landing_proven",
                owner=WorkflowOwner.INTEGRATOR,
                actions=(PermittedAction.CLAIM_INTEGRATION,),
                durable_jobs=("integration_terminal_stage",),
                recommended_status=IN_VALIDATION,
            )
        return _decision(
            task,
            facts,
            disposition=TaskDisposition.RETRY_SCHEDULED,
            reason_code="integration.landing_unproven",
            owner=WorkflowOwner.INTEGRATOR,
            prerequisites=(
                UnmetPrerequisite(
                    "integration.landing_unproven",
                    target or "integration_target",
                    landing.state.value if landing is not None else None,
                ),
            ),
            actions=(PermittedAction.RECONCILE_TARGET,),
            alert=AlertSeverity.INFO,
            durable_jobs=("integration_landing_refresh",),
        )
    mode = str(value.get("mode") or "").strip().lower()
    state = str(value.get("state") or "").strip().lower()
    has_parent = bool(str(task.parent_id or "").strip())
    explicit_target = str(task.target_branch or "").strip()
    integration_target = str(value.get("base_branch") or "").strip()
    exact_standalone_route = bool(
        not has_parent
        or (
            explicit_target
            and integration_target
            and explicit_target == integration_target
            and str(value.get("post_landed_parent_id") or "").strip()
            == str(task.parent_id or "").strip()
        )
    )
    if mode == "standalone" and state == "ready" and exact_standalone_route:
        config = facts.fact(FactDomain.CONFIG)
        config_value = (
            _mapping(config.value) if config.state is FactState.KNOWN else None
        )
        recovery_state = str(
            (config_value or {}).get("accepted_submission_recovery_state") or ""
        ).strip()
        accepted_head = str(
            (config_value or {}).get("accepted_submission_head")
            or value.get("head_sha")
            or ""
        ).strip()
        observed_branch_head = str(
            (config_value or {}).get("accepted_submission_branch_head") or ""
        ).strip()
        observed_review_head = str(
            (config_value or {}).get("accepted_submission_review_head") or ""
        ).strip()
        if recovery_state == "accepted_submission_branch_advanced":
            observed = observed_branch_head or observed_review_head
            return _decision(
                task,
                facts,
                disposition=TaskDisposition.ACTION_REQUIRED,
                reason_code="standalone.resubmission_required",
                owner=WorkflowOwner.OPERATOR,
                prerequisites=(
                    UnmetPrerequisite(
                        "standalone.resubmission_required",
                        accepted_head or task.task_id,
                        observed or recovery_state,
                    ),
                ),
                actions=(PermittedAction.RESOLVE_OPERATOR_ACTION,),
                alert=AlertSeverity.WARNING,
            )
        if recovery_state == "accepted_submission_remote_ambiguous":
            return _decision(
                task,
                facts,
                disposition=TaskDisposition.BLOCKED,
                reason_code="standalone.remote_identity_ambiguous",
                owner=WorkflowOwner.INTEGRATOR,
                prerequisites=(
                    UnmetPrerequisite(
                        "standalone.remote_identity_ambiguous",
                        accepted_head or task.task_id,
                        observed_review_head
                        or observed_branch_head
                        or recovery_state,
                    ),
                ),
                actions=(PermittedAction.CLAIM_INTEGRATION,),
                alert=AlertSeverity.INFO,
            )
        if recovery_state in {
            "accepted_submission_branch_unavailable",
            "accepted_submission_claim_changed",
            "accepted_submission_claim_retiring",
        }:
            return _decision(
                task,
                facts,
                disposition=TaskDisposition.BLOCKED,
                reason_code="standalone.remote_identity_unavailable",
                owner=WorkflowOwner.INTEGRATOR,
                prerequisites=(
                    UnmetPrerequisite(
                        "standalone.remote_identity_unavailable",
                        accepted_head or task.task_id,
                        recovery_state,
                    ),
                ),
                actions=(PermittedAction.CLAIM_INTEGRATION,),
                alert=AlertSeverity.INFO,
            )
        return _decision(
            task,
            facts,
            disposition=TaskDisposition.RETRY_SCHEDULED,
            reason_code="standalone.delivery_eligible",
            owner=WorkflowOwner.INTEGRATOR,
            actions=(PermittedAction.CLAIM_INTEGRATION,),
            durable_jobs=("standalone_delivery",),
        )
    if state in {"integrating", "active"}:
        if _valid_lease(value, now):
            return _decision(
                task,
                facts,
                disposition=TaskDisposition.OWNED,
                reason_code="integration.active",
                owner=WorkflowOwner.INTEGRATOR,
                actions=(PermittedAction.CLAIM_INTEGRATION,),
            )
        return _decision(
            task,
            facts,
            disposition=TaskDisposition.RETRY_SCHEDULED,
            reason_code="integration.retry_scheduled",
            owner=WorkflowOwner.INTEGRATOR,
            actions=(PermittedAction.CLAIM_INTEGRATION,),
            alert=AlertSeverity.INFO,
            durable_jobs=("integration_recovery",),
        )
    # A blocked exact-head gate is authoritative unless an explicit
    # same-generation retry has been forced by the repair path.
    if value.get("state") == "blocked" and not bool(value.get("retry_forced")):
        return _decision(
            task,
            facts,
            disposition=TaskDisposition.ACTION_REQUIRED,
            reason_code="integration.gate_blocked",
            owner=WorkflowOwner.OPERATOR,
            prerequisites=(
                UnmetPrerequisite(
                    "integration.gate_blocked",
                    task.task_id,
                    str(value.get("last_error") or "gate_blocked"),
                ),
            ),
            actions=(PermittedAction.RESOLVE_OPERATOR_ACTION,),
            alert=AlertSeverity.WARNING,
        )
    if state == "blocked" and bool(value.get("retry_forced")):
        return _decision(
            task,
            facts,
            disposition=TaskDisposition.RETRY_SCHEDULED,
            reason_code="integration.queued",
            owner=WorkflowOwner.INTEGRATOR,
            actions=(PermittedAction.CLAIM_INTEGRATION,),
            durable_jobs=("integration_attempt",),
        )
    if state in {"ready", "queued"} and (
        mode in {"", "queue"} or has_parent
    ):
        return _decision(
            task,
            facts,
            disposition=TaskDisposition.RETRY_SCHEDULED,
            reason_code=(
                "integration.retry_scheduled"
                if value.get("retry_at")
                else "integration.queued"
            ),
            owner=WorkflowOwner.INTEGRATOR,
            actions=(PermittedAction.CLAIM_INTEGRATION,),
            alert=(
                AlertSeverity.INFO if value.get("retry_at") else AlertSeverity.NONE
            ),
            durable_jobs=("integration_attempt",),
        )
    # A known but unclassified record is not integration-attempt authority.
    # Reconcile its production mode/queue evidence before any Git mutation.
    return _decision(
        task,
        facts,
        disposition=TaskDisposition.RETRY_SCHEDULED,
        reason_code="integration.retry_scheduled",
        owner=WorkflowOwner.INTEGRATOR,
        actions=(PermittedAction.CLAIM_INTEGRATION,),
        alert=AlertSeverity.INFO,
        durable_jobs=("integration_recovery",),
    )


def retained_terminal_child_waiver(
    child: Mapping[str, Any],
    *,
    project_id: str,
    parent_id: str,
) -> Mapping[str, Any] | None:
    """Return one exact owner-retention waiver or fail closed with ``None``."""

    raw = _mapping(child.get("retained_terminal_provenance"))
    if raw is None:
        return None
    generation = raw.get("provenance_authority_generation")
    identifier = str(child.get("identifier") or "").strip()
    source = str(child.get("landing_source") or "").strip()
    target = str(child.get("landing_target") or "").strip()
    child_revision = str(child.get("revision") or "").strip().lower()
    authority_version = str(child.get("authority_version") or "").strip().lower()
    status = canonicalize_status(child.get("status"))
    valid = bool(
        project_id
        and parent_id
        and identifier
        and source
        and target
        and raw.get("schema_version") == 1
        and not isinstance(raw.get("schema_version"), bool)
        and raw.get("kind") == "owner_terminal_provenance"
        and raw.get("project_id") == project_id
        and raw.get("parent_id") == parent_id
        and raw.get("parent_id") == child.get("parent_id")
        and raw.get("task_id") == identifier
        and raw.get("status") == status == DONE
        and raw.get("landing_source") == source
        and raw.get("landing_target") == target
        and isinstance(raw.get("revision"), str)
        and str(raw.get("revision") or "").strip().lower() == child_revision
        and 40 <= len(child_revision) <= 64
        and all(character in "0123456789abcdef" for character in child_revision)
        and isinstance(raw.get("authority_version"), str)
        and raw.get("authority_version") == authority_version
        and len(authority_version) == 64
        and all(character in "0123456789abcdef" for character in authority_version)
        and isinstance(raw.get("marker_version"), int)
        and not isinstance(raw.get("marker_version"), bool)
        and raw.get("marker_version") == 1
        and isinstance(generation, int)
        and not isinstance(generation, bool)
        and generation >= 0
        and isinstance(raw.get("authorized_by"), str)
        and str(raw.get("authorized_by") or "").strip()
        and isinstance(raw.get("actor_source"), str)
        and str(raw.get("actor_source") or "").strip()
    )
    return raw if valid else None


def _rollup_decision(task: _TaskView, facts: WorkflowFacts) -> WorkDecision:
    containment = facts.fact(FactDomain.CONTAINMENT)
    value = (
        _mapping(containment.value) if containment.state is FactState.KNOWN else None
    )
    if value is None:
        return _fact_wait(
            task,
            facts,
            FactDomain.CONTAINMENT,
            owner=WorkflowOwner.ROLLUP,
            action=PermittedAction.ROLLUP_CHILDREN,
            job="rollup_reconciliation",
        )
    raw_children = value.get("children", ())
    if not isinstance(raw_children, (tuple, list)):
        return _fact_wait(
            task,
            facts,
            FactDomain.CONTAINMENT,
            owner=WorkflowOwner.ROLLUP,
            action=PermittedAction.ROLLUP_CHILDREN,
            job="rollup_reconciliation",
        )
    if not raw_children:
        return _decision(
            task,
            facts,
            disposition=TaskDisposition.RETRY_SCHEDULED,
            reason_code="rollup.children_missing",
            owner=WorkflowOwner.ROLLUP,
            prerequisites=(UnmetPrerequisite("rollup.children_missing", task.task_id),),
            actions=(PermittedAction.ROLLUP_CHILDREN,),
            alert=AlertSeverity.INFO,
            durable_jobs=("rollup_reconciliation",),
        )

    if value.get("acyclic") is False:
        return _decision(
            task,
            facts,
            disposition=TaskDisposition.ACTION_REQUIRED,
            reason_code="operator.action_required",
            owner=WorkflowOwner.OPERATOR,
            prerequisites=(
                UnmetPrerequisite(
                    "containment.cycle",
                    str(value.get("cycle") or task.task_id),
                ),
            ),
            actions=(PermittedAction.RESOLVE_OPERATOR_ACTION,),
            alert=AlertSeverity.WARNING,
        )

    # Generic task rollups historically used terminal status as their only
    # proof.  Epic facts opt into the stricter target-relative contract by
    # carrying ``requires_landing`` plus exact source/target identities.  A
    # nested epic is intentionally checked by its landing fact alone: asking
    # for the parent's derived status here would recreate the parent/child
    # proof cycle this evaluator is meant to remove.
    target_relative = any(
        isinstance(_mapping(item), Mapping)
        and (
            "requires_landing" in (_mapping(item) or {})
            or str((_mapping(item) or {}).get("kind") or "")
            in {"nested", "nested_epic", "maintenance"}
        )
        for item in raw_children
    )
    epic_source = str(value.get("epic_branch") or "").strip()
    epic_target = str(value.get("target_branch") or "").strip()
    epic_landing = None
    if target_relative and epic_source and epic_target:
        epic_landing = next(
            (
                item
                for item in facts.landings
                if item.source == epic_source and item.target == epic_target
            ),
            None,
        )
    incomplete: list[UnmetPrerequisite] = []
    landing_unknown: list[UnmetPrerequisite] = []
    landing_observation = facts.fact(FactDomain.LANDING)

    for raw_child in raw_children:
        child = _mapping(raw_child) or {}
        identifier = str(child.get("identifier") or "unknown")
        kind = str(child.get("kind") or "normal")
        status = canonicalize_status(child.get("status"))
        maintenance = bool(child.get("maintenance")) or kind == "maintenance"
        archived = kind == "archived" or status == ARCHIVED
        nested = kind == "nested_epic" or (
            kind == "nested" and str(child.get("issue_type") or "").lower() == "epic"
        )

        if not target_relative:
            if status not in SATISFIED_DEPENDENCY_STATUSES:
                incomplete.append(
                    UnmetPrerequisite("rollup.child_incomplete", identifier, status)
                )
            continue

        if archived:
            # Safely retired children carry no code landing obligation.
            continue
        if nested:
            # Nested epic readiness is target evidence, never the parent's
            # lifecycle status (which may itself be derived from this child).
            requires_landing = True
        else:
            if not maintenance and status != "Done":
                incomplete.append(
                    UnmetPrerequisite("rollup.child_incomplete", identifier, status)
                )
                continue
            if maintenance:
                if status not in SATISFIED_DEPENDENCY_STATUSES:
                    incomplete.append(
                        UnmetPrerequisite("rollup.child_incomplete", identifier, status)
                    )
                continue
            # Old projections without target-relative metadata retain their
            # established terminal-status behavior.
            requires_landing = bool(child.get("requires_landing"))
            if not requires_landing:
                continue

        if not requires_landing:
            continue
        if retained_terminal_child_waiver(
            child,
            project_id=facts.project_id,
            parent_id=facts.task_id,
        ) is not None:
            # Owner retention is an explicit, scoped waiver of this child's
            # delivery obligation.  It never creates or substitutes a Git
            # LandingFact, and any mismatch falls through to normal landing
            # evidence below.
            continue
        source = str(child.get("landing_source") or "").strip()
        target = str(child.get("landing_target") or "").strip()
        matching = tuple(
            item
            for item in facts.landings
            if (not source or item.source == source)
            and (not target or item.target == target)
        )
        if landing_observation.state is not FactState.KNOWN:
            landing_unknown.append(
                UnmetPrerequisite(
                    f"landing.{landing_observation.state.value}",
                    f"{source or identifier}->{target or 'target'}",
                    landing_observation.error_code,
                )
            )
            continue
        landed = any(item.state is LandingState.LANDED for item in matching)
        if landed:
            continue
        if any(item.state is LandingState.UNKNOWN for item in matching) or not matching:
            landing_unknown.append(
                UnmetPrerequisite(
                    "landing.unknown",
                    f"{source or identifier}->{target or 'target'}",
                )
            )
        else:
            incomplete.append(
                UnmetPrerequisite(
                    "landing.not_landed",
                    f"{source or identifier}->{target or 'target'}",
                )
            )

    if landing_unknown:
        return _decision(
            task,
            facts,
            disposition=TaskDisposition.RETRY_SCHEDULED,
            reason_code="landing.evidence_unknown",
            owner=WorkflowOwner.ROLLUP,
            prerequisites=tuple(landing_unknown),
            actions=(PermittedAction.REFRESH_LANDING,),
            alert=AlertSeverity.INFO,
            durable_jobs=(
                "child_landing_verification" if target_relative else "rollup_reconciliation",
            ),
        )
    if incomplete:
        return _decision(
            task,
            facts,
            disposition=TaskDisposition.BLOCKED,
            reason_code="rollup.waiting_children",
            owner=WorkflowOwner.ROLLUP,
            prerequisites=incomplete,
            actions=(
                (
                    PermittedAction.REFRESH_LANDING,
                    PermittedAction.ROLLUP_CHILDREN,
                )
                if target_relative
                else (PermittedAction.ROLLUP_CHILDREN,)
            ),
            durable_jobs=(
                "child_landing_verification" if target_relative else "rollup_reconciliation",
            ),
        )

    if target_relative and epic_source and epic_target:
        # The epic's own landing can authorize terminalization only after the
        # current containment snapshot has passed every child obligation above.
        # A previously landed (or still-base) epic ref must not hide a child
        # added or reopened after that landing.  Persisted per-child landing
        # facts keep already-pruned terminal children from deadlocking here.
        if epic_landing is not None and epic_landing.state is LandingState.LANDED:
            return _decision(
                task,
                facts,
                disposition=TaskDisposition.RUNNABLE,
                reason_code="terminal.immediate_target_landing_proven",
                owner=WorkflowOwner.ROLLUP,
                actions=(PermittedAction.REQUEST_MERGED,),
                durable_jobs=("epic_auto_close",),
            )
        if epic_landing is None or epic_landing.state is LandingState.UNKNOWN:
            return _decision(
                task,
                facts,
                disposition=TaskDisposition.RETRY_SCHEDULED,
                reason_code="landing.evidence_unknown",
                owner=WorkflowOwner.ROLLUP,
                prerequisites=(
                    UnmetPrerequisite(
                        "landing.unknown",
                        f"{epic_source}->{epic_target}",
                        epic_landing.error_code if epic_landing is not None else None,
                    ),
                ),
                actions=(PermittedAction.REFRESH_LANDING,),
                alert=AlertSeverity.INFO,
                durable_jobs=("epic_terminal_validation",),
            )
    return _decision(
        task,
        facts,
        disposition=TaskDisposition.RUNNABLE,
        reason_code="rollup.children_complete",
        owner=WorkflowOwner.ROLLUP,
        actions=(PermittedAction.ROLLUP_CHILDREN,),
        durable_jobs=(
            "rollup_review_creation" if target_relative else "rollup_reconciliation",
        ),
    )


def _landing_decision(task: _TaskView, facts: WorkflowFacts) -> WorkDecision:
    epic = task.issue_type.strip().lower() == "epic"
    refresh_job = (
        "epic_terminal_validation"
        if epic
        else "integration_landing_refresh"
    )
    expected_target = task.target_branch
    if epic:
        containment = facts.fact(FactDomain.CONTAINMENT)
        if containment.state is not FactState.KNOWN:
            return _fact_wait(
                task,
                facts,
                FactDomain.CONTAINMENT,
                owner=WorkflowOwner.ROLLUP,
                action=PermittedAction.REFRESH_LANDING,
                job=refresh_job,
            )
        containment_value = _mapping(containment.value)
        expected_source = str(
            (containment_value or {}).get("epic_branch") or ""
        ).strip()
        expected_target = str(
            (containment_value or {}).get("target_branch") or ""
        ).strip()
        if not expected_source or not expected_target:
            return _decision(
                task,
                facts,
                disposition=TaskDisposition.RETRY_SCHEDULED,
                reason_code="evidence.containment_malformed",
                owner=WorkflowOwner.ROLLUP,
                prerequisites=(
                    UnmetPrerequisite("evidence.malformed", "containment"),
                ),
                actions=(PermittedAction.REFRESH_LANDING,),
                alert=AlertSeverity.INFO,
                durable_jobs=(refresh_job,),
            )
        candidates = epic_immediate_target_landings(facts)
    else:
        candidates = tuple(
            item
            for item in facts.landings
            if task.target_branch is None or item.target == task.target_branch
        )
    if not candidates and facts.landings:
        return _decision(
            task,
            facts,
            disposition=TaskDisposition.RETRY_SCHEDULED,
            reason_code="landing.target_evidence_missing",
            owner=WorkflowOwner.ROLLUP,
            prerequisites=(
                UnmetPrerequisite(
                    "landing.target_evidence_missing",
                    expected_target or "configured_target",
                ),
            ),
            actions=(PermittedAction.REFRESH_LANDING,),
            alert=AlertSeverity.INFO,
            durable_jobs=(refresh_job,),
        )
    if not candidates:
        return _fact_wait(
            task,
            facts,
            FactDomain.LANDING,
            owner=WorkflowOwner.ROLLUP,
            action=PermittedAction.REFRESH_LANDING,
            job=refresh_job,
        )
    landed = tuple(item for item in candidates if item.state is LandingState.LANDED)
    unknown = tuple(item for item in candidates if item.state is LandingState.UNKNOWN)
    if landed:
        if not epic and task.parent_id:
            task_observation = facts.fact(FactDomain.TASK)
            task_value = (
                _mapping(task_observation.value)
                if task_observation.state is FactState.KNOWN
                else None
            )
            parent_identity = str(
                (task_value or {}).get("parent_identifier") or ""
            ).strip()
            parent_status = canonicalize_status(
                (task_value or {}).get("parent_status")
            )
            parent_issue_type = str(
                (task_value or {}).get("parent_issue_type") or ""
            ).strip().lower()
            parent_error = str(
                (task_value or {}).get("parent_error") or ""
            ).strip()
            if (
                parent_identity != task.parent_id
                or parent_issue_type != "epic"
                or parent_status not in {MERGED, ARCHIVED}
            ):
                # A shared child's accepted revision landing on the parent
                # branch proves Done, not Merged.  The parent rollup owns the
                # later target landing.  Publishing a terminal job before the
                # parent is terminal guarantees coordinator rejection and can
                # hold restart reconstruction at N-1 forever.  Keep this
                # normal wait jobless; the canonical project scan observes
                # the exact parent status and reassesses it automatically.
                observed = (
                    parent_error
                    or parent_status
                    or "parent_authority_unavailable"
                )
                return _decision(
                    task,
                    facts,
                    disposition=TaskDisposition.BLOCKED,
                    reason_code="rollup.waiting_parent_landing",
                    owner=WorkflowOwner.ROLLUP,
                    prerequisites=(
                        UnmetPrerequisite(
                            "rollup.parent_not_terminal",
                            task.parent_id,
                            observed,
                        ),
                    ),
                    actions=(PermittedAction.REFRESH_LANDING,),
                )
        action = (
            "epic_auto_close"
            if epic
            else "parent_rollup_review"
        )
        return _decision(
            task,
            facts,
            disposition=TaskDisposition.TERMINAL,
            reason_code="terminal.immediate_target_landing_proven",
            owner=WorkflowOwner.ROLLUP,
            actions=(PermittedAction.REQUEST_MERGED,),
            durable_jobs=(action,),
            recommended_status=MERGED,
        )
    if unknown:
        return _decision(
            task,
            facts,
            disposition=TaskDisposition.RETRY_SCHEDULED,
            reason_code="landing.evidence_unknown",
            owner=WorkflowOwner.ROLLUP,
            prerequisites=tuple(
                UnmetPrerequisite(
                    "landing.unknown", f"{item.source}->{item.target}", item.error_code
                )
                for item in unknown
            ),
            actions=(PermittedAction.REFRESH_LANDING,),
            alert=AlertSeverity.INFO,
            durable_jobs=(refresh_job,),
        )
    return _decision(
        task,
        facts,
        disposition=TaskDisposition.BLOCKED,
        reason_code="landing.waiting",
        owner=WorkflowOwner.ROLLUP,
        prerequisites=tuple(
            UnmetPrerequisite("landing.not_landed", f"{item.source}->{item.target}")
            for item in candidates
        ),
        actions=(PermittedAction.REFRESH_LANDING,),
    )


def _terminal_provenance_decision(
    task: _TaskView,
    facts: WorkflowFacts,
) -> WorkDecision | None:
    """Reduce an authenticated terminal-provenance marker, if present.

    The fact adapter emits this payload only after parsing the durable marker,
    but the decision boundary validates the complete identity again.  This
    keeps a malformed, cross-project, or cross-task fact from becoming a
    delivery bypass if a future adapter regresses.
    """

    def invalid(error_code: str) -> WorkDecision:
        return _decision(
            task,
            facts,
            disposition=TaskDisposition.ACTION_REQUIRED,
            reason_code="terminal.provenance_invalid",
            owner=WorkflowOwner.OPERATOR,
            prerequisites=(
                UnmetPrerequisite(
                    "terminal.provenance_invalid",
                    task.task_id,
                    error_code,
                ),
            ),
            actions=(PermittedAction.RESOLVE_OPERATOR_ACTION,),
            alert=AlertSeverity.WARNING,
            reassess=False,
        )

    observation = facts.fact(FactDomain.TERMINAL_AUDIT)
    if observation.state is not FactState.KNOWN:
        return None
    value = _mapping(observation.value)
    if value is None:
        return invalid("identity_or_authority_mismatch")
    if "terminal_provenance" not in value:
        return None

    raw = _mapping(value["terminal_provenance"])
    if raw is None:
        return invalid("identity_or_authority_mismatch")

    schema_version = raw.get("schema_version")
    marker_present = raw.get("marker_present")
    generation = raw.get("authority_generation")
    raw_malformed = raw.get("malformed")
    raw_retained = raw.get("retained")
    malformed = raw_malformed is True
    common_valid = bool(
        isinstance(marker_present, bool)
        and isinstance(raw_retained, bool)
        and isinstance(raw_malformed, bool)
        and isinstance(schema_version, int)
        and not isinstance(schema_version, bool)
        and schema_version == 1
        and raw.get("project_id") == facts.project_id
        and raw.get("task_id") == facts.task_id
        and isinstance(generation, int)
        and not isinstance(generation, bool)
        and generation >= 0
    )
    if malformed or not common_valid:
        return invalid(
            "malformed" if malformed else "identity_or_authority_mismatch"
        )
    if marker_present is False:
        marker_only_fields = {
            "marker_version",
            "authorized_by",
            "actor_source",
            "marked_at",
            "updated_at",
        }
        valid_absence = bool(
            raw_retained is False
            and generation == 0
            and task.status == DONE
            and not marker_only_fields.intersection(raw)
        )
        return None if valid_absence else invalid("identity_or_authority_mismatch")

    marker_version = raw.get("marker_version")
    marker_valid = bool(
        isinstance(marker_version, int)
        and not isinstance(marker_version, bool)
        and marker_version == 1
        and isinstance(raw.get("authorized_by"), str)
        and str(raw.get("authorized_by") or "").strip()
        and isinstance(raw.get("actor_source"), str)
        and str(raw.get("actor_source") or "").strip()
        and isinstance(raw.get("marked_at"), str)
        and isinstance(raw.get("updated_at"), str)
        and str(raw.get("updated_at") or "").strip()
    )
    if not marker_valid:
        return invalid("identity_or_authority_mismatch")
    if not raw_retained:
        return (
            None
            if generation >= 1
            else invalid("identity_or_authority_mismatch")
        )
    if not str(raw.get("marked_at") or "").strip():
        return invalid("identity_or_authority_mismatch")
    if task.status != DONE:
        return _decision(
            task,
            facts,
            disposition=TaskDisposition.ACTION_REQUIRED,
            reason_code="terminal.provenance_invalid",
            owner=WorkflowOwner.OPERATOR,
            prerequisites=(
                UnmetPrerequisite(
                    "terminal.provenance_invalid",
                    task.task_id,
                    f"retained_marker_with_{task.status}",
                ),
            ),
            actions=(PermittedAction.RESOLVE_OPERATOR_ACTION,),
            alert=AlertSeverity.WARNING,
            reassess=False,
        )
    return _decision(
        task,
        facts,
        disposition=TaskDisposition.TERMINAL,
        reason_code="terminal.provenance_retained",
        owner=WorkflowOwner.NONE,
        reassess=False,
    )


def _evaluate_task_default_policy(
    task: Issue | Mapping[str, Any],
    facts: WorkflowFacts,
    *,
    now: datetime | None = None,
) -> WorkDecision:
    """Return one deterministic decision without I/O or mutation."""

    view = _task_view(task)
    decision_now = now or _parse_time(facts.collected_at, "collected_at")
    if decision_now.tzinfo is None:
        raise ValueError("now must include a timezone")
    decision_now = decision_now.astimezone(timezone.utc)

    if view.task_id != facts.task_id or (
        view.project_id and view.project_id != facts.project_id
    ):
        return _decision(
            view,
            facts,
            disposition=TaskDisposition.ACTION_REQUIRED,
            reason_code="evidence.project_or_task_mismatch",
            owner=WorkflowOwner.OPERATOR,
            prerequisites=(
                UnmetPrerequisite("evidence.identity_mismatch", view.task_id),
            ),
            actions=(PermittedAction.RESOLVE_OPERATOR_ACTION,),
            alert=AlertSeverity.WARNING,
        )
    # A lifecycle-final tracker status is authoritative and must not regress
    # merely because a supporting snapshot is missing, stale, or unavailable.
    if view.status in LIFECYCLE_FINAL_STATUSES:
        identity = _terminal_landing_identity(task)
        exact_landing = bool(
            view.status == MERGED
            and identity is not None
            and any(
                item.state is LandingState.LANDED
                and item.durable
                and (item.source, item.target, item.revision) == identity
                for item in facts.landings
            )
        )
        return _decision(
            view,
            facts,
            disposition=TaskDisposition.TERMINAL,
            reason_code=(
                "terminal.preserve_verified_merged"
                if exact_landing
                else "terminal.final"
            ),
            owner=WorkflowOwner.NONE,
            reassess=False,
        )
    task_fact = facts.fact(FactDomain.TASK)
    task_value = (
        _mapping(task_fact.value) if task_fact.state is FactState.KNOWN else None
    )
    if task_value is None:
        return _fact_wait(
            view,
            facts,
            FactDomain.TASK,
            owner=_owner_for_status(view.status),
            action=PermittedAction.RECOVER_IMPLEMENTATION,
            job="facts_refresh",
        )
    fact_identifier = str(
        task_value.get("identifier") or task_value.get("task_id") or ""
    )
    fact_project = str(task_value.get("project_id") or facts.project_id)
    if fact_identifier != facts.task_id or fact_project != facts.project_id:
        return _decision(
            view,
            facts,
            disposition=TaskDisposition.ACTION_REQUIRED,
            reason_code="evidence.task_fact_identity_mismatch",
            owner=WorkflowOwner.OPERATOR,
            prerequisites=(
                UnmetPrerequisite(
                    "evidence.task_fact_identity_mismatch",
                    fact_identifier or "missing",
                    fact_project,
                ),
            ),
            actions=(PermittedAction.RESOLVE_OPERATOR_ACTION,),
            alert=AlertSeverity.WARNING,
        )
    fact_status = canonicalize_status(task_value.get("status"))
    if fact_status != view.status:
        return _decision(
            view,
            facts,
            disposition=TaskDisposition.RETRY_SCHEDULED,
            reason_code="evidence.task_status_mismatch",
            prerequisites=(
                UnmetPrerequisite("evidence.status_changed", view.task_id, fact_status),
            ),
            actions=(PermittedAction.RECOVER_IMPLEMENTATION,),
            alert=AlertSeverity.INFO,
            durable_jobs=("facts_refresh",),
        )
    if view.status not in STATUS_CONTRACTS:
        return _decision(
            view,
            facts,
            disposition=TaskDisposition.ACTION_REQUIRED,
            reason_code="workflow.unknown_status",
            owner=WorkflowOwner.OPERATOR,
            prerequisites=(UnmetPrerequisite("workflow.unknown_status", view.status),),
            actions=(PermittedAction.RESOLVE_OPERATOR_ACTION,),
            alert=AlertSeverity.WARNING,
        )

    provenance_decision = _terminal_provenance_decision(view, facts)
    if provenance_decision is not None:
        return provenance_decision

    # A direct epic-maintenance helper has already published its accepted
    # revision onto the authoritative parent ref.  Once its independent audit
    # reaches Done there is no ordinary source-to-target landing left to
    # discover; treating it as an ordinary Done child manufactures a missing
    # landing fact and eventually an actionable retry-exhaustion alert.
    integration = facts.fact(FactDomain.INTEGRATION)
    integration_value = (
        _mapping(integration.value)
        if integration.state is FactState.KNOWN
        else None
    )
    config = facts.fact(FactDomain.CONFIG)
    config_value = (
        _mapping(config.value) if config.state is FactState.KNOWN else None
    )
    direct_handoff_ready = bool(
        integration_value
        and direct_epic_maintenance_handoff_ready(task, integration_value)
    )
    # Parent state is part of the completion effect, not optional diagnostics.
    # Missing/stale/error CONFIG authority must therefore fail closed and keep
    # the exact idempotent completion job live until convergence can be proved.
    parent_convergence_unproven = bool(
        direct_handoff_ready
        and (
            (
                config_value is not None
                and config_value.get("direct_epic_maintenance_parent_rebased")
                is False
            )
            # An Open/repair helper still has terminal-audit work to do, so
            # its established audited handoff remains runnable when an older
            # collector lacks this new observation.  Done is the dangerous
            # terminal boundary: never declare it complete without positive
            # parent convergence authority.
            or (
                view.status == DONE
                and (
                    config_value is None
                    or config_value.get(
                        "direct_epic_maintenance_parent_rebased"
                    )
                    is not True
                )
            )
        )
    )
    if (
        view.status
        in {
            OPEN,
            NEEDS_CI_FIX,
            NEEDS_REBASE,
            IN_VALIDATION,
            READY_TO_INTEGRATE,
            DONE,
        }
        and integration_value
        and (
            direct_epic_maintenance_completion_ready(task, integration_value)
            or parent_convergence_unproven
            or (view.status == READY_TO_INTEGRATE and direct_handoff_ready)
        )
    ):
        return _decision(
            view,
            facts,
            disposition=TaskDisposition.RETRY_SCHEDULED,
            reason_code="maintenance.publication_completion_pending",
            owner=WorkflowOwner.INTEGRATOR,
            actions=(PermittedAction.RECONCILE_TARGET,),
            durable_jobs=("direct_epic_maintenance_completion",),
        )
    if (
        view.status == DONE
        and integration_value
        and direct_handoff_ready
    ):
        return _decision(
            view,
            facts,
            disposition=TaskDisposition.TERMINAL,
            reason_code="maintenance.publication_proven",
            owner=WorkflowOwner.NONE,
            reassess=False,
        )

    # A Done nested epic has already completed its own containment rollup.  Its
    # remaining obligation is the exact landing on its immediate target, just
    # like any other Done task.  Sending it back through child rollup can
    # manufacture ``children_missing`` and recreate the OOMPAH-748
    # parent/child terminalization cycle.
    if view.issue_type.lower() == "epic" and view.status != DONE:
        return _rollup_decision(view, facts)

    dependency_sensitive = {
        OPEN,
        NEEDS_CI_FIX,
        NEEDS_REBASE,
        READY_TO_INTEGRATE,
    }
    dependency_fact = facts.fact(FactDomain.DEPENDENCIES)
    if view.status in dependency_sensitive:
        if dependency_fact.state is not FactState.KNOWN:
            return _fact_wait(
                view,
                facts,
                FactDomain.DEPENDENCIES,
                owner=(
                    WorkflowOwner.INTEGRATOR
                    if view.status == READY_TO_INTEGRATE
                    else _owner_for_status(view.status)
                ),
                action=PermittedAction.WAIT_DEPENDENCY,
                job="dependency_refresh",
            )
        dependency_value = _mapping(dependency_fact.value)
        if dependency_value is None or any(
            not isinstance(dependency_value.get(key, ()), (tuple, list))
            for key in ("finish", "hard_start")
        ):
            return _decision(
                view,
                facts,
                disposition=TaskDisposition.RETRY_SCHEDULED,
                reason_code="evidence.dependencies_malformed",
                owner=(
                    WorkflowOwner.INTEGRATOR
                    if view.status == READY_TO_INTEGRATE
                    else _owner_for_status(view.status)
                ),
                prerequisites=(
                    UnmetPrerequisite("evidence.malformed", "dependencies"),
                ),
                actions=(PermittedAction.WAIT_DEPENDENCY,),
                alert=AlertSeverity.INFO,
                durable_jobs=("dependency_refresh",),
            )

    finish, hard_start = _prerequisites(facts)
    if view.status == PROPOSED:
        return _decision(
            view,
            facts,
            disposition=TaskDisposition.BLOCKED,
            reason_code="intake.awaiting_decision",
            owner=WorkflowOwner.INTAKE,
            actions=(PermittedAction.ACCEPT_INTAKE,),
        )
    if view.status == BACKLOG:
        return _decision(
            view,
            facts,
            disposition=TaskDisposition.BLOCKED,
            reason_code="prioritization.awaiting_owner",
            owner=WorkflowOwner.PROJECT_OWNER,
            actions=(PermittedAction.PROMOTE_OPEN,),
        )
    if view.status in {OPEN, NEEDS_CI_FIX, NEEDS_REBASE}:
        integration_value = (
            _mapping(integration.value)
            if integration.state is FactState.KNOWN
            else None
        )
        if integration_value and direct_epic_maintenance_handoff_ready(
            task, integration_value
        ):
            return _decision(
                view,
                facts,
                disposition=TaskDisposition.OWNED,
                reason_code="maintenance.publication_proven",
                owner=WorkflowOwner.AUDITOR,
                actions=(PermittedAction.CLAIM_AUDIT,),
                durable_jobs=("terminal_audit_done",),
                recommended_status=IN_VALIDATION,
            )
        duplicate_state = str(
            (config_value or {}).get("duplicate_screening_state") or ""
        ).strip().lower()
        pending_action = str(
            (config_value or {}).get("implementation_pending_action") or ""
        ).strip()
        submission_recovery_state = str(
            (config_value or {}).get("accepted_submission_recovery_state") or ""
        ).strip()
        if view.status == OPEN and duplicate_state == "running":
            return _decision(
                view,
                facts,
                disposition=TaskDisposition.OWNED,
                reason_code="duplicate.investigating",
                owner=WorkflowOwner.DUPLICATE_INVESTIGATOR,
                actions=(PermittedAction.INVESTIGATE_DUPLICATE,),
            )
        if pending_action == "validation_submission":
            return _decision(
                view,
                facts,
                disposition=TaskDisposition.RETRY_SCHEDULED,
                reason_code="implementation.action_scheduled",
                owner=WorkflowOwner.DISPATCHER,
                actions=(PermittedAction.RECONCILE_IMPLEMENTATION,),
                alert=AlertSeverity.INFO,
                durable_jobs=(pending_action,),
            )
        if submission_recovery_state.startswith("accepted_submission_"):
            return _decision(
                view,
                facts,
                disposition=TaskDisposition.BLOCKED,
                reason_code="implementation.submission_recovery_parked",
                owner=WorkflowOwner.DISPATCHER,
                prerequisites=(
                    UnmetPrerequisite(
                        "implementation.submission_recovery_parked",
                        submission_recovery_state,
                    ),
                ),
                actions=(PermittedAction.RECONCILE_IMPLEMENTATION,),
                alert=AlertSeverity.INFO,
            )
        if hard_start:
            return _decision(
                view,
                facts,
                disposition=TaskDisposition.BLOCKED,
                reason_code="dispatch.dependencies_blocked",
                prerequisites=hard_start,
                actions=(PermittedAction.WAIT_DEPENDENCY,),
            )
        if view.status == OPEN and pending_action in {
            "duplicate_screening",
            "worker_exit",
        }:
            return _decision(
                view,
                facts,
                disposition=TaskDisposition.RETRY_SCHEDULED,
                reason_code=(
                    "duplicate.recovery_scheduled"
                    if pending_action == "duplicate_screening"
                    else "implementation.action_scheduled"
                ),
                owner=(
                    WorkflowOwner.DUPLICATE_INVESTIGATOR
                    if pending_action == "duplicate_screening"
                    else WorkflowOwner.DISPATCHER
                ),
                actions=(
                    (
                        PermittedAction.INVESTIGATE_DUPLICATE
                        if pending_action == "duplicate_screening"
                        else PermittedAction.RECONCILE_IMPLEMENTATION
                    ),
                ),
                alert=AlertSeverity.INFO,
                durable_jobs=(pending_action,),
            )
        return _decision(
            view,
            facts,
            disposition=TaskDisposition.RUNNABLE,
            reason_code="dispatch.eligible",
            owner=(
                WorkflowOwner.REPAIR_WORKER
                if view.status in {NEEDS_CI_FIX, NEEDS_REBASE}
                else WorkflowOwner.DISPATCHER
            ),
            actions=(
                PermittedAction.CLAIM_REPAIR
                if view.status in {NEEDS_CI_FIX, NEEDS_REBASE}
                else PermittedAction.CLAIM_IMPLEMENTATION,
            ),
            durable_jobs=("implementation_start",),
        )
    if view.status == IN_PROGRESS:
        return _implementation_decision(view, facts, decision_now)
    if view.status == NEEDS_ANSWER:
        return _decision(
            view,
            facts,
            disposition=TaskDisposition.ACTION_REQUIRED,
            reason_code="requestor.answer_required",
            owner=WorkflowOwner.REQUESTOR,
            actions=(PermittedAction.ANSWER_REQUEST,),
            alert=AlertSeverity.WARNING,
        )
    if view.status == NEEDS_HUMAN:
        return _decision(
            view,
            facts,
            disposition=TaskDisposition.ACTION_REQUIRED,
            reason_code="operator.action_required",
            owner=WorkflowOwner.OPERATOR,
            actions=(PermittedAction.RESOLVE_OPERATOR_ACTION,),
            alert=AlertSeverity.WARNING,
        )
    if view.status == IN_REVIEW:
        return _review_decision(view, facts)
    if view.status == IN_VALIDATION:
        return _validation_decision(view, facts, decision_now)
    if view.status == READY_TO_INTEGRATE:
        return _integration_decision(view, facts, decision_now, finish, hard_start)
    if view.status == DECOMPOSED:
        return _rollup_decision(view, facts)
    if view.status == DUPLICATE_CANDIDATE:
        config = facts.fact(FactDomain.CONFIG)
        config_value = (
            _mapping(config.value) if config.state is FactState.KNOWN else None
        )
        duplicate_state = str(
            (config_value or {}).get("duplicate_screening_state") or ""
        ).strip().lower()
        duplicate_verdict = str(
            (config_value or {}).get("duplicate_screening_verdict") or ""
        ).strip().lower()
        pending_action = str(
            (config_value or {}).get("implementation_pending_action") or ""
        ).strip()
        if pending_action == "worker_exit":
            return _decision(
                view,
                facts,
                disposition=TaskDisposition.RETRY_SCHEDULED,
                reason_code="implementation.action_scheduled",
                owner=WorkflowOwner.DISPATCHER,
                actions=(PermittedAction.RECONCILE_IMPLEMENTATION,),
                alert=AlertSeverity.INFO,
                durable_jobs=(pending_action,),
            )
        if (
            duplicate_state == "checked"
            and duplicate_verdict == "duplicate_candidate"
        ):
            return _decision(
                view,
                facts,
                disposition=TaskDisposition.ACTION_REQUIRED,
                reason_code="duplicate.confirmed",
                owner=WorkflowOwner.PROJECT_OWNER,
                actions=(PermittedAction.RESOLVE_OPERATOR_ACTION,),
                alert=AlertSeverity.WARNING,
            )
        if (
            config_value is not None
            and config_value.get("duplicate_screening_enabled") is False
        ):
            return _decision(
                view,
                facts,
                disposition=TaskDisposition.ACTION_REQUIRED,
                reason_code="duplicate.screening_disabled",
                owner=WorkflowOwner.OPERATOR,
                actions=(PermittedAction.RESOLVE_OPERATOR_ACTION,),
                alert=AlertSeverity.WARNING,
            )
        authority = facts.fact(FactDomain.DUPLICATE_INVESTIGATION)
        value = (
            _mapping(authority.value) if authority.state is FactState.KNOWN else None
        )
        active_duplicate_job = bool(value and _valid_active_job(value))
        if value and (active_duplicate_job or _valid_lease(value, decision_now)):
            return _decision(
                view,
                facts,
                disposition=TaskDisposition.OWNED,
                reason_code="duplicate.investigating",
                owner=WorkflowOwner.DUPLICATE_INVESTIGATOR,
                actions=(PermittedAction.INVESTIGATE_DUPLICATE,),
            )
        return _decision(
            view,
            facts,
            disposition=TaskDisposition.RETRY_SCHEDULED,
            reason_code="duplicate.recovery_scheduled",
            owner=WorkflowOwner.DUPLICATE_INVESTIGATOR,
            actions=(PermittedAction.INVESTIGATE_DUPLICATE,),
            alert=AlertSeverity.INFO,
            durable_jobs=("duplicate_screening",),
        )
    if view.status == DONE:
        return _landing_decision(view, facts)
    raise AssertionError(f"unhandled canonical workflow status: {view.status}")


def evaluate_task(
    task: Issue | Mapping[str, Any],
    facts: WorkflowFacts,
    *,
    now: datetime | None = None,
    liveness_slo_seconds: Mapping[str, int] | None = None,
) -> WorkDecision:
    """Evaluate with an isolated runtime reassessment policy.

    The taxonomy defaults remain suitable for library callers. The service
    always injects its environment-derived policy, and replacing the absolute
    deadline here ensures controller escalation and health use the same value.
    """

    decision = _evaluate_task_default_policy(task, facts, now=now)
    if decision.next_reassessment_at is None:
        return decision
    contract = STATUS_CONTRACTS.get(decision.status)
    slo_key = contract.reassessment.slo_key if contract is not None else None
    if slo_key is None:
        return decision
    policy = build_liveness_slos(liveness_slo_seconds)
    deadline = _render_time(
        _parse_time(facts.collected_at, "collected_at")
        + timedelta(seconds=policy[slo_key].max_reassessment_seconds)
    )
    if deadline == decision.next_reassessment_at:
        return decision
    return replace(
        decision,
        next_reassessment_at=deadline,
        decision_revision=None,
    )
