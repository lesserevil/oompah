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
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

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
from oompah.workflow_facts import (
    FactDomain,
    FactState,
    LandingState,
    WorkflowFacts,
)
from oompah.workflow_reasons import AlertSeverity, LIVENESS_SLOS

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
        "dispatch.dependencies_blocked",
        "dispatch.eligible",
        "duplicate.investigating",
        "duplicate.recovery_scheduled",
        "evidence.dependencies_malformed",
        "evidence.project_or_task_mismatch",
        "evidence.task_fact_identity_mismatch",
        "evidence.task_status_mismatch",
        "implementation.active",
        "implementation.action_scheduled",
        "implementation.recovery_scheduled",
        "intake.awaiting_decision",
        "integration.active",
        "integration.dependencies_blocked",
        "integration.live_claim_precedes_history",
        "integration.landing_proven",
        "integration.landing_unproven",
        "integration.queued",
        "integration.required_base_missing",
        "integration.retry_scheduled",
        "landing.evidence_unknown",
        "landing.target_evidence_missing",
        "landing.waiting",
        "maintenance.publication_proven",
        "operator.action_required",
        "prioritization.awaiting_owner",
        "requestor.answer_required",
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
        "rollup.waiting_children",
        "standalone.delivery_eligible",
        "terminal.final",
        "terminal.immediate_target_landing_proven",
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


def _reassessment(status: str, collected_at: str) -> str | None:
    contract = STATUS_CONTRACTS.get(status)
    if contract is None or contract.reassessment.slo_key is None:
        return None
    slo = LIVENESS_SLOS[contract.reassessment.slo_key]
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
        "implementation_recovery",
        "implementation_start",
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
    if _valid_lease(value, now):
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
    expected_head = recorded_head or current_head
    changed_head = ""
    if recorded_head and current_head and recorded_head != current_head:
        changed_head = current_head
    if expected_head and observed_head and expected_head != observed_head:
        changed_head = observed_head
    if changed_head:
        return _decision(
            task,
            facts,
            disposition=TaskDisposition.RETRY_SCHEDULED,
            reason_code="review.head_changed",
            owner=WorkflowOwner.REVIEW_MONITOR,
            prerequisites=(
                UnmetPrerequisite(
                    "review.head_changed",
                    expected_head,
                    changed_head,
                ),
            ),
            actions=(PermittedAction.ROUTE_REBASE,),
            alert=AlertSeverity.INFO,
            durable_jobs=("review_head_reconciliation",),
            recommended_status=READY_TO_INTEGRATE,
        )

    expected_source = str(
        task_fact.get("work_branch")
        or task_fact.get("branch_name")
        or task.task_id
    ).strip()

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

    if state in {"missing", "not_found", "none"} or value.get("present") is False:
        landed = exact_landings()
        if landed:
            return _decision(
                task,
                facts,
                disposition=TaskDisposition.TERMINAL,
                reason_code="terminal.immediate_target_landing_proven",
                owner=WorkflowOwner.REVIEW_MONITOR,
                actions=(PermittedAction.REQUEST_MERGED,),
                durable_jobs=("review_terminal_stage",),
                recommended_status=MERGED,
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
                actions=(PermittedAction.REQUEST_MERGED,),
                durable_jobs=("review_terminal_stage",),
                recommended_status=MERGED,
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
        if _valid_lease(value, now):
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
    if bool(value.get("live_claim_precedes_history")):
        return _decision(
            task,
            facts,
            disposition=TaskDisposition.OWNED,
            reason_code="integration.live_claim_precedes_history",
            owner=WorkflowOwner.INTEGRATOR,
            actions=(PermittedAction.CLAIM_INTEGRATION,),
            durable_jobs=("historical_audit_replay_batch", "integration_attempt"),
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
    if value.get("mode") == "standalone" and value.get("state") == "ready":
        return _decision(
            task,
            facts,
            disposition=TaskDisposition.RETRY_SCHEDULED,
            reason_code="standalone.delivery_eligible",
            owner=WorkflowOwner.INTEGRATOR,
            actions=(PermittedAction.CLAIM_INTEGRATION,),
            durable_jobs=("standalone_delivery",),
        )
    if value.get("state") in {"integrating", "active"}:
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
        alert=AlertSeverity.INFO if value.get("retry_at") else AlertSeverity.NONE,
        durable_jobs=("integration_attempt",),
    )


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

    epic_source = str(value.get("epic_branch") or "").strip()
    epic_target = str(value.get("target_branch") or "").strip()
    if target_relative and epic_source and epic_target:
        epic_landing = next(
            (
                item
                for item in facts.landings
                if item.source == epic_source and item.target == epic_target
            ),
            None,
        )
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
                    task.target_branch or "configured_target",
                ),
            ),
            actions=(PermittedAction.REFRESH_LANDING,),
            alert=AlertSeverity.INFO,
            durable_jobs=("landing_reconciliation",),
        )
    if not candidates:
        return _fact_wait(
            task,
            facts,
            FactDomain.LANDING,
            owner=WorkflowOwner.ROLLUP,
            action=PermittedAction.REFRESH_LANDING,
            job="landing_reconciliation",
        )
    landed = tuple(item for item in candidates if item.state is LandingState.LANDED)
    unknown = tuple(item for item in candidates if item.state is LandingState.UNKNOWN)
    if landed:
        return _decision(
            task,
            facts,
            disposition=TaskDisposition.TERMINAL,
            reason_code="terminal.immediate_target_landing_proven",
            owner=WorkflowOwner.ROLLUP,
            actions=(PermittedAction.REQUEST_MERGED,),
            durable_jobs=("parent_rollup_review",),
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
            durable_jobs=("landing_reconciliation",),
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


def evaluate_task(
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
        return _decision(
            view,
            facts,
            disposition=TaskDisposition.TERMINAL,
            reason_code="terminal.final",
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

    if view.issue_type.lower() == "epic":
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
        integration = facts.fact(FactDomain.INTEGRATION)
        integration_value = (
            _mapping(integration.value)
            if integration.state is FactState.KNOWN
            else None
        )
        if integration_value and bool(
            integration_value.get("maintenance_publication_proven")
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
        if hard_start:
            return _decision(
                view,
                facts,
                disposition=TaskDisposition.BLOCKED,
                reason_code="dispatch.dependencies_blocked",
                prerequisites=hard_start,
                actions=(PermittedAction.WAIT_DEPENDENCY,),
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
        authority = facts.fact(FactDomain.IMPLEMENTATION_AUTHORITY)
        value = (
            _mapping(authority.value) if authority.state is FactState.KNOWN else None
        )
        if (
            value
            and value.get("ownership_source") == "duplicate_investigator"
            and _valid_lease(value, decision_now)
        ):
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
