"""Bounded health projections for authoritative workflow decisions.

The universal workflow controller is the source of truth for liveness.  This
module does not infer ownership from tracker ages or maintain a second set of
status SLOs.  It projects :class:`~oompah.work_decision.WorkDecision` values
into restart-safe, bounded metrics and preserves the controller's distinction
between normal recovery and work which explicitly requires human action.
"""

from __future__ import annotations

import copy
import hashlib
import json
import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from oompah.work_decision import WorkDecision
from oompah.workflow_contract import (
    STATUS_CONTRACTS,
    TaskDisposition,
    WorkflowOwner,
)
from oompah.workflow_fact_model import FactDomain, FactState, WorkflowFacts
from oompah.workflow_reasons import (
    AlertSeverity,
    LivenessPolicy,
    build_liveness_policy,
)


LIVENESS_STATE_SCHEMA_VERSION = 6
DEFAULT_MAX_TASK_RECORDS = 256
DEFAULT_MAX_PROJECT_RECORDS = 64
DEFAULT_SNAPSHOT_STALE_SECONDS = 900
EVENT_LEDGER_BIT_COUNT = 32_768
EVENT_LEDGER_HASH_COUNT = 4
CONSERVATIVE_PROGRESS_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _optional_time(value: object) -> str | None:
    """Normalize an optional authoritative timestamp without inventing one."""

    if value is None or not str(value).strip():
        return None
    try:
        return _render_time(_parse_time(value, "deadline"))
    except (TypeError, ValueError, OverflowError):
        return None


def _required_digest_revision(value: object, name: str) -> str:
    """Validate a persisted authority revision emitted by workflow hashing."""

    if not isinstance(value, str):
        raise ValueError(f"liveness record {name} must be a string digest")
    revision = value.strip()
    if len(revision) != 64 or any(
        character not in "0123456789abcdef" for character in revision
    ):
        raise ValueError(
            f"liveness record {name} must be a lowercase SHA-256 digest"
        )
    return revision


def _known_fact_mapping(
    facts: WorkflowFacts,
    domain: FactDomain,
) -> Mapping[str, Any] | None:
    observation = facts.fact(domain)
    if observation.state is not FactState.KNOWN:
        return None
    return observation.value if isinstance(observation.value, Mapping) else None


def _utc(value: datetime, name: str = "timestamp") -> datetime:
    if value.tzinfo is None:
        raise ValueError(f"{name} must include a timezone")
    return value.astimezone(timezone.utc)


def _parse_time(value: object, name: str) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError(f"{name} is required")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name} must be an ISO-8601 timestamp") from exc
    return _utc(parsed, name)


def _render_time(value: datetime) -> str:
    return _utc(value).isoformat()


def _seconds(value: float) -> int:
    return max(0, int(value))


def _semantic_revision(decision: WorkDecision) -> str:
    """Return the stable meaning of a decision, excluding refresh metadata."""

    raw = {
        "status": decision.status,
        "disposition": decision.disposition.value,
        "reason_code": decision.reason_code,
        "responsible_owner": decision.responsible_owner.value,
        "unmet_prerequisites": [
            {"code": item.code, "subject": item.subject}
            for item in decision.unmet_prerequisites
        ],
        "permitted_actions": [item.value for item in decision.permitted_actions],
        "action_required": decision.action_required,
        "alert_level": decision.alert_level.value,
        "durable_jobs": list(decision.durable_jobs),
        "recommended_status": decision.recommended_status,
    }
    encoded = json.dumps(raw, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _slo_key(status: str) -> str | None:
    contract = STATUS_CONTRACTS.get(status)
    return contract.reassessment.slo_key if contract is not None else None


@dataclass(frozen=True, slots=True)
class DecisionLivenessFacts:
    """Deadline and recovery evidence read from the decision's exact facts."""

    lease_expires_at: str | None = None
    retry_due_at: str | None = None
    recovery_attempt: int = 0
    active_job: bool = False
    active_job_id: str | None = None

    @classmethod
    def from_workflow_facts(
        cls,
        decision: WorkDecision,
        facts: WorkflowFacts,
    ) -> DecisionLivenessFacts:
        """Project owner-specific lease/retry facts without status-age guesses."""

        owner_domain = {
            WorkflowOwner.IMPLEMENTER: FactDomain.IMPLEMENTATION_AUTHORITY,
            WorkflowOwner.DIRECT_OWNER: FactDomain.IMPLEMENTATION_AUTHORITY,
            WorkflowOwner.DUPLICATE_INVESTIGATOR: (
                FactDomain.DUPLICATE_INVESTIGATION
            ),
            WorkflowOwner.REVIEW_MONITOR: FactDomain.REVIEW_CI,
            WorkflowOwner.AUDITOR: FactDomain.TERMINAL_AUDIT,
            WorkflowOwner.INTEGRATOR: FactDomain.INTEGRATION,
        }.get(decision.responsible_owner)
        owner_value = (
            _known_fact_mapping(facts, owner_domain)
            if owner_domain is not None
            else None
        )
        retry_budget = _known_fact_mapping(facts, FactDomain.RETRY_BUDGET)
        active_job_id = str(
            (
                owner_value.get("active_job_id")
                or owner_value.get("job_id")
                or owner_value.get("audit_id")
                or owner_value.get("owner_id")
            )
            if owner_value
            else ""
        ).strip() or None
        active_job = bool(
            owner_value
            and owner_value.get("actively_working") is True
            and active_job_id
        )
        lease = _optional_time(
            owner_value.get("lease_expires_at") if owner_value else None
        )
        retry = _optional_time(
            owner_value.get("retry_at") if owner_value else None
        ) or _optional_time(
            retry_budget.get("retry_at") if retry_budget else None
        )
        raw_attempt = retry_budget.get("attempts", 0) if retry_budget else 0
        try:
            attempt = max(0, int(raw_attempt or 0))
        except (TypeError, ValueError):
            attempt = 0
        return cls(
            lease_expires_at=lease,
            retry_due_at=retry,
            recovery_attempt=attempt,
            active_job=active_job,
            active_job_id=active_job_id,
        )


def _deadline(
    decision: WorkDecision,
    liveness_facts: DecisionLivenessFacts,
) -> tuple[str | None, str]:
    """Choose the deadline that actually controls the current disposition."""

    if (
        decision.disposition is TaskDisposition.OWNED
        and liveness_facts.lease_expires_at is not None
    ):
        return liveness_facts.lease_expires_at, "lease"
    if (
        decision.disposition is TaskDisposition.OWNED
        and liveness_facts.active_job
        and liveness_facts.active_job_id is not None
    ):
        return None, "active_job"
    if decision.disposition is TaskDisposition.OWNED:
        # OWNED is a conclusion, not evidence of a live worker. If no durable
        # job or lease was observed, the unchanged-evidence reassessment
        # deadline remains authoritative and can become overdue.
        return decision.next_reassessment_at, "reassessment"
    if (
        decision.disposition is TaskDisposition.RETRY_SCHEDULED
        and liveness_facts.retry_due_at is not None
    ):
        return liveness_facts.retry_due_at, "retry"
    return decision.next_reassessment_at, "reassessment"


@dataclass(frozen=True, slots=True)
class LivenessTaskProjection:
    """A redacted, attributable view of one authoritative decision."""

    project_id: str
    task_id: str
    status: str
    disposition: str
    reason_code: str
    responsible_owner: str
    action_required: bool
    alert_level: str
    decision_revision: str
    evidence_revision: str
    first_observed_at: str
    last_progress_at: str
    last_observed_at: str
    next_reassessment_at: str | None
    lease_expires_at: str | None
    retry_due_at: str | None
    effective_deadline_at: str | None
    deadline_kind: str
    slo_key: str | None
    slo_seconds: int | None
    policy_epoch: str
    active_job: bool
    active_job_id: str | None
    recovery_attempt: int
    reassessment_count: int
    recovery_count: int
    escalation_count: int
    decision_age_seconds: int
    seconds_since_progress: int
    deadline_seconds_remaining: int | None
    deadline_lateness_seconds: int
    reassessment_lateness_seconds: int

    @property
    def overdue(self) -> bool:
        return self.deadline_lateness_seconds > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "task_id": self.task_id,
            "status": self.status,
            "disposition": self.disposition,
            "reason_code": self.reason_code,
            "responsible_owner": self.responsible_owner,
            "action_required": self.action_required,
            "alert_level": self.alert_level,
            "decision_revision": self.decision_revision,
            "evidence_revision": self.evidence_revision,
            "first_observed_at": self.first_observed_at,
            "last_progress_at": self.last_progress_at,
            "last_observed_at": self.last_observed_at,
            "next_reassessment_at": self.next_reassessment_at,
            "lease_expires_at": self.lease_expires_at,
            "retry_due_at": self.retry_due_at,
            "effective_deadline_at": self.effective_deadline_at,
            "deadline_kind": self.deadline_kind,
            "slo_key": self.slo_key,
            "slo_seconds": self.slo_seconds,
            "policy_epoch": self.policy_epoch,
            "active_job": self.active_job,
            "active_job_id": self.active_job_id,
            "recovery_attempt": self.recovery_attempt,
            "reassessment_count": self.reassessment_count,
            "recovery_count": self.recovery_count,
            "escalation_count": self.escalation_count,
            "decision_age_seconds": self.decision_age_seconds,
            "seconds_since_progress": self.seconds_since_progress,
            "deadline_seconds_remaining": self.deadline_seconds_remaining,
            "deadline_lateness_seconds": self.deadline_lateness_seconds,
            "reassessment_lateness_seconds": self.reassessment_lateness_seconds,
            "overdue": self.overdue,
        }


@dataclass(frozen=True, slots=True)
class WorkflowLivenessHealth:
    """Global and per-project liveness health from a bounded coverage cycle."""

    status: str
    observed_at: str | None
    snapshot_generation: int | None
    scan_complete: bool
    restored: bool
    stale: bool
    last_error: str | None
    source_errors: Mapping[str, str]
    source_error_count: int
    omitted_source_error_count: int
    total_nonterminal_count: int
    evaluated_count: int
    tracked_task_count: int
    omitted_task_count: int
    missing_decision_count: int
    divergence_count: int
    current_divergence_count: int
    action_required_count: int
    overdue_count: int
    unexplained_count: int
    recovery_count: int
    active_recovery_count: int
    escalation_count: int
    reassessment_count: int
    owned_count: int
    task_count_by_status: Mapping[str, int]
    projects: Mapping[str, Mapping[str, Any]]
    omitted_project_count: int
    coverage_scope: str
    global_coverage_complete: bool
    active_project_count: int
    excluded_projects: Mapping[str, str]
    excluded_project_count: int
    omitted_excluded_project_count: int
    excluded_task_count: int
    oldest_decision_age_seconds: int | None
    oldest_reassessment_lateness_seconds: int | None
    max_task_records: int
    max_project_records: int
    snapshot_stale_seconds: int
    policy_epoch: str
    restart_reconstruction_pending: bool
    restart_started_at: str | None
    restart_deadline_at: str | None
    restart_lateness_seconds: int
    restart_convergence_count: int
    reconciliation_complete: bool
    required_recovery_count: int
    materialized_recovery_count: int
    tasks: tuple[LivenessTaskProjection, ...]

    @property
    def healthy(self) -> bool:
        return self.status == "healthy"

    @property
    def degraded(self) -> bool:
        return not self.healthy

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "healthy": self.healthy,
            "degraded": self.degraded,
            "observed_at": self.observed_at,
            "snapshot_generation": self.snapshot_generation,
            "scan_complete": self.scan_complete,
            "restored": self.restored,
            "stale": self.stale,
            "policy_epoch": self.policy_epoch,
            "last_error": self.last_error,
            "source_errors": dict(self.source_errors),
            "source_error_count": self.source_error_count,
            "omitted_source_error_count": self.omitted_source_error_count,
            "total_nonterminal_count": self.total_nonterminal_count,
            "evaluated_count": self.evaluated_count,
            "tracked_task_count": self.tracked_task_count,
            "omitted_task_count": self.omitted_task_count,
            "missing_decision_count": self.missing_decision_count,
            "divergence_count": self.divergence_count,
            "current_divergence_count": self.current_divergence_count,
            "action_required_count": self.action_required_count,
            "escalation_count": self.escalation_count,
            "overdue_count": self.overdue_count,
            "unexplained_count": self.unexplained_count,
            "unexplained_divergence_count": self.unexplained_count,
            "recovery_count": self.recovery_count,
            "active_recovery_count": self.active_recovery_count,
            "reassessment_count": self.reassessment_count,
            "owned_count": self.owned_count,
            "task_count_by_status": dict(self.task_count_by_status),
            "projects": {
                project_id: dict(summary)
                for project_id, summary in self.projects.items()
            },
            "omitted_project_count": self.omitted_project_count,
            "coverage_scope": self.coverage_scope,
            "global_coverage_complete": self.global_coverage_complete,
            "active_project_count": self.active_project_count,
            "excluded_projects": dict(self.excluded_projects),
            "excluded_project_count": self.excluded_project_count,
            "omitted_excluded_project_count": (
                self.omitted_excluded_project_count
            ),
            "excluded_task_count": self.excluded_task_count,
            "oldest_decision_age_seconds": self.oldest_decision_age_seconds,
            "oldest_reassessment_lateness_seconds": (
                self.oldest_reassessment_lateness_seconds
            ),
            "limits": {
                "max_task_records": self.max_task_records,
                "max_project_records": self.max_project_records,
                "snapshot_stale_seconds": self.snapshot_stale_seconds,
            },
            "restart": {
                "reconstruction_pending": self.restart_reconstruction_pending,
                "started_at": self.restart_started_at,
                "deadline_at": self.restart_deadline_at,
                "lateness_seconds": self.restart_lateness_seconds,
                "convergence_count": self.restart_convergence_count,
            },
            "reconciliation": {
                "complete": self.reconciliation_complete,
                "required_recovery_count": self.required_recovery_count,
                "materialized_recovery_count": self.materialized_recovery_count,
            },
            "tasks": [item.to_dict() for item in self.tasks],
        }


@dataclass(slots=True)
class _DecisionRecord:
    project_id: str
    task_id: str
    status: str
    disposition: str
    reason_code: str
    responsible_owner: str
    action_required: bool
    alert_level: str
    decision_revision: str
    evidence_revision: str
    semantic_revision: str
    first_observed_at: str
    last_progress_at: str
    last_observed_at: str
    next_reassessment_at: str | None
    lease_expires_at: str | None
    retry_due_at: str | None
    effective_deadline_at: str | None
    deadline_kind: str
    slo_seconds: int | None
    policy_epoch: str
    recovery_attempt: int
    active_job: bool
    active_job_id: str | None
    reassessment_count: int
    recovery_count: int
    escalation_count: int

    @property
    def identity(self) -> tuple[str, str]:
        return self.project_id, self.task_id

    @classmethod
    def from_decision(
        cls,
        decision: WorkDecision,
        *,
        now: datetime,
        previous: _DecisionRecord | None,
        liveness_facts: DecisionLivenessFacts,
        slo_seconds: int | None,
        policy_epoch: str,
        conservative_progress: bool = False,
    ) -> _DecisionRecord:
        # ``WorkDecision`` validates that evidence is non-empty, but only
        # workflow facts may mint the revision that is allowed to renew an
        # SLO.  Treating an arbitrary string as new evidence would let a bad
        # adapter keep an otherwise stalled task green forever.
        evidence_revision = _required_digest_revision(
            decision.evidence_revision, "decision evidence_revision"
        )
        observed = _render_time(now)
        initial_progress = (
            _render_time(CONSERVATIVE_PROGRESS_EPOCH)
            if conservative_progress and previous is None
            else observed
        )
        semantic = _semantic_revision(decision)
        same_semantics = previous is not None and previous.semantic_revision == semantic
        same_evidence = (
            previous is not None
            and previous.evidence_revision == evidence_revision
        )
        new_evidence = not same_semantics or not same_evidence
        recovery_event = (
            decision.disposition is TaskDisposition.RETRY_SCHEDULED
            and (
                previous is None
                or previous.disposition != TaskDisposition.RETRY_SCHEDULED.value
                or new_evidence
            )
        )
        escalation_event = decision.action_required and (
            previous is None or not previous.action_required or new_evidence
        )
        anchored_reassessment = decision.next_reassessment_at
        if conservative_progress and previous is None and slo_seconds is not None:
            anchored_reassessment = _render_time(
                CONSERVATIVE_PROGRESS_EPOCH + timedelta(seconds=slo_seconds)
            )
        anchored_decision = (
            decision
            if anchored_reassessment == decision.next_reassessment_at
            else WorkDecision(
                project_id=decision.project_id,
                task_id=decision.task_id,
                status=decision.status,
                disposition=decision.disposition,
                reason_code=decision.reason_code,
                responsible_owner=decision.responsible_owner,
                unmet_prerequisites=decision.unmet_prerequisites,
                evidence_revision=evidence_revision,
                next_reassessment_at=anchored_reassessment,
                permitted_actions=decision.permitted_actions,
                action_required=decision.action_required,
                alert_level=decision.alert_level,
                durable_jobs=decision.durable_jobs,
                recommended_status=decision.recommended_status,
            )
        )
        effective_deadline, deadline_kind = _deadline(
            anchored_decision, liveness_facts
        )
        return cls(
            project_id=decision.project_id,
            task_id=decision.task_id,
            status=decision.status,
            disposition=decision.disposition.value,
            reason_code=decision.reason_code,
            responsible_owner=decision.responsible_owner.value,
            action_required=decision.action_required,
            alert_level=decision.alert_level.value,
            decision_revision=str(decision.decision_revision),
            evidence_revision=evidence_revision,
            semantic_revision=semantic,
            first_observed_at=(
                previous.first_observed_at if same_semantics else initial_progress
            ),
            last_progress_at=(
                previous.last_progress_at
                if same_semantics and same_evidence
                else initial_progress
            ),
            last_observed_at=observed,
            next_reassessment_at=anchored_reassessment,
            lease_expires_at=liveness_facts.lease_expires_at,
            retry_due_at=liveness_facts.retry_due_at,
            effective_deadline_at=effective_deadline,
            deadline_kind=deadline_kind,
            slo_seconds=slo_seconds,
            policy_epoch=policy_epoch,
            recovery_attempt=liveness_facts.recovery_attempt,
            active_job=bool(
                liveness_facts.active_job
                and liveness_facts.active_job_id is not None
            ),
            active_job_id=liveness_facts.active_job_id,
            reassessment_count=(previous.reassessment_count if previous else 0) + 1,
            recovery_count=(previous.recovery_count if previous else 0)
            + int(recovery_event),
            escalation_count=(previous.escalation_count if previous else 0)
            + int(escalation_event),
        )

    @classmethod
    def from_state(cls, raw: Mapping[str, Any], *, now: datetime) -> _DecisionRecord:
        values = {
            field: raw.get(field)
            for field in cls.__dataclass_fields__
        }
        for field in (
            "project_id",
            "task_id",
            "status",
            "disposition",
            "reason_code",
            "responsible_owner",
            "alert_level",
            "decision_revision",
            "evidence_revision",
            "semantic_revision",
            "deadline_kind",
            "policy_epoch",
        ):
            values[field] = str(values[field] or "").strip()
            if not values[field]:
                raise ValueError(f"liveness record {field} is required")
        values["evidence_revision"] = _required_digest_revision(
            raw.get("evidence_revision"), "evidence_revision"
        )
        values["semantic_revision"] = _required_digest_revision(
            raw.get("semantic_revision"), "semantic_revision"
        )
        if not isinstance(values["action_required"], bool):
            raise ValueError("liveness record action_required must be boolean")
        if not isinstance(values["active_job"], bool):
            raise ValueError("liveness record active_job must be boolean")
        values["active_job_id"] = (
            str(values.get("active_job_id") or "").strip() or None
        )
        disposition = TaskDisposition(values["disposition"])
        alert_level = AlertSeverity(values["alert_level"])
        if values["action_required"] != (
            disposition is TaskDisposition.ACTION_REQUIRED
        ):
            raise ValueError("liveness record action_required is inconsistent")
        if values["active_job"] and disposition is not TaskDisposition.OWNED:
            raise ValueError("liveness record active_job is inconsistent")
        if values["active_job"] and values["active_job_id"] is None:
            raise ValueError("active liveness record requires active_job_id")
        if values["action_required"] and alert_level not in {
            AlertSeverity.WARNING,
            AlertSeverity.CRITICAL,
        }:
            raise ValueError("action-required liveness record must be alerting")
        if not values["action_required"] and alert_level in {
            AlertSeverity.WARNING,
            AlertSeverity.CRITICAL,
        }:
            raise ValueError("normal liveness record cannot be alerting")
        first = min(_parse_time(values["first_observed_at"], "first_observed_at"), now)
        progress = min(_parse_time(values["last_progress_at"], "last_progress_at"), now)
        observed = min(_parse_time(values["last_observed_at"], "last_observed_at"), now)
        if progress < first:
            progress = first
        if observed < progress:
            observed = progress
        values["first_observed_at"] = _render_time(first)
        values["last_progress_at"] = _render_time(progress)
        values["last_observed_at"] = _render_time(observed)
        deadline = values.get("next_reassessment_at")
        values["next_reassessment_at"] = (
            _render_time(_parse_time(deadline, "next_reassessment_at"))
            if deadline
            else None
        )
        for field in (
            "lease_expires_at",
            "retry_due_at",
            "effective_deadline_at",
        ):
            values[field] = _optional_time(values.get(field))
        if values["deadline_kind"] not in {
            "active_job",
            "lease",
            "reassessment",
            "retry",
        }:
            raise ValueError("liveness record deadline_kind is invalid")
        raw_slo_seconds = values.get("slo_seconds")
        if raw_slo_seconds is None:
            values["slo_seconds"] = None
        else:
            try:
                values["slo_seconds"] = max(1, int(raw_slo_seconds))
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "liveness record slo_seconds must be an integer"
                ) from exc
        if (
            values["deadline_kind"] == "lease"
            and values["effective_deadline_at"] != values["lease_expires_at"]
        ):
            raise ValueError("lease deadline evidence is inconsistent")
        if (
            values["deadline_kind"] == "retry"
            and values["effective_deadline_at"] != values["retry_due_at"]
        ):
            raise ValueError("retry deadline evidence is inconsistent")
        if (
            values["deadline_kind"] == "active_job"
            and (
                disposition is not TaskDisposition.OWNED
                or not values["active_job"]
                or values["effective_deadline_at"] is not None
            )
        ):
            raise ValueError("active-job deadline evidence is inconsistent")
        for field in (
            "recovery_attempt",
            "reassessment_count",
            "recovery_count",
            "escalation_count",
        ):
            try:
                values[field] = max(0, int(values.get(field) or 0))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"liveness record {field} must be an integer") from exc
        return cls(**values)

    def to_state(self) -> dict[str, Any]:
        return {
            field: getattr(self, field)
            for field in self.__dataclass_fields__
        }

    def project(self, *, now: datetime) -> LivenessTaskProjection:
        first = _parse_time(self.first_observed_at, "first_observed_at")
        progress = _parse_time(self.last_progress_at, "last_progress_at")
        effective_deadline = (
            _parse_time(self.effective_deadline_at, "effective_deadline_at")
            if self.effective_deadline_at
            else None
        )
        reassessment_deadline = (
            _parse_time(self.next_reassessment_at, "next_reassessment_at")
            if self.next_reassessment_at
            else None
        )
        remaining = None
        deadline_lateness = 0
        if effective_deadline is not None:
            delta = (effective_deadline - now).total_seconds()
            remaining = _seconds(delta) if delta >= 0 else 0
            deadline_lateness = _seconds(-delta) if delta < 0 else 0
        reassessment_lateness = 0
        if reassessment_deadline is not None:
            reassessment_delta = (reassessment_deadline - now).total_seconds()
            reassessment_lateness = (
                _seconds(-reassessment_delta) if reassessment_delta < 0 else 0
            )
        slo_key = _slo_key(self.status)
        return LivenessTaskProjection(
            project_id=self.project_id,
            task_id=self.task_id,
            status=self.status,
            disposition=self.disposition,
            reason_code=self.reason_code,
            responsible_owner=self.responsible_owner,
            action_required=self.action_required,
            alert_level=self.alert_level,
            decision_revision=self.decision_revision,
            evidence_revision=self.evidence_revision,
            first_observed_at=self.first_observed_at,
            last_progress_at=self.last_progress_at,
            last_observed_at=self.last_observed_at,
            next_reassessment_at=self.next_reassessment_at,
            lease_expires_at=self.lease_expires_at,
            retry_due_at=self.retry_due_at,
            effective_deadline_at=self.effective_deadline_at,
            deadline_kind=self.deadline_kind,
            slo_key=slo_key,
            slo_seconds=self.slo_seconds,
            policy_epoch=self.policy_epoch,
            active_job=self.active_job,
            active_job_id=self.active_job_id,
            recovery_attempt=self.recovery_attempt,
            reassessment_count=self.reassessment_count,
            recovery_count=self.recovery_count,
            escalation_count=self.escalation_count,
            decision_age_seconds=_seconds((now - first).total_seconds()),
            seconds_since_progress=_seconds((now - progress).total_seconds()),
            deadline_seconds_remaining=remaining,
            deadline_lateness_seconds=deadline_lateness,
            reassessment_lateness_seconds=reassessment_lateness,
        )


def _event_signature(decision: WorkDecision, event: str) -> str:
    payload = {
        "event": event,
        "project_id": decision.project_id,
        "task_id": decision.task_id,
        "semantic_revision": _semantic_revision(decision),
        "evidence_revision": decision.evidence_revision,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


@dataclass(slots=True)
class _BoundedEventLedger:
    """Fixed-size durable membership ledger with no false negatives.

    Hash collisions can conservatively under-count a new event, but a
    signature once observed can never become unseen through record eviction.
    That bounded tradeoff prevents unchanged recovery/escalation rows from
    inflating cumulative totals forever.
    """

    bits: bytearray

    @classmethod
    def empty(cls) -> _BoundedEventLedger:
        return cls(bytearray(EVENT_LEDGER_BIT_COUNT // 8))

    @classmethod
    def saturated(cls) -> _BoundedEventLedger:
        """Fail closed against recount when persisted membership is corrupt."""

        return cls(bytearray([0xFF]) * (EVENT_LEDGER_BIT_COUNT // 8))

    @classmethod
    def from_state(cls, raw: object) -> _BoundedEventLedger:
        if not cls.state_is_valid(raw):
            return cls.saturated()
        assert isinstance(raw, Mapping)
        encoded = str(raw.get("bits") or "")
        return cls(bytearray.fromhex(encoded))

    @classmethod
    def state_is_valid(cls, raw: object) -> bool:
        """Return whether persisted membership can be trusted exactly."""

        if not isinstance(raw, Mapping):
            return False
        try:
            bit_count = int(raw.get("bit_count", 0) or 0)
            hash_count = int(raw.get("hash_count", 0) or 0)
        except (TypeError, ValueError):
            return False
        if (
            raw.get("algorithm") != "sha256-bloom-v1"
            or bit_count != EVENT_LEDGER_BIT_COUNT
            or hash_count != EVENT_LEDGER_HASH_COUNT
        ):
            return False
        encoded = str(raw.get("bits") or "")
        if len(encoded) != EVENT_LEDGER_BIT_COUNT // 4:
            return False
        try:
            bits = bytearray.fromhex(encoded)
        except ValueError:
            return False
        if len(bits) != EVENT_LEDGER_BIT_COUNT // 8:
            return False
        return True

    @staticmethod
    def _positions(signature: str) -> tuple[int, ...]:
        digest = hashlib.sha256(signature.encode("utf-8")).digest()
        return tuple(
            int.from_bytes(digest[index * 8 : (index + 1) * 8], "big")
            % EVENT_LEDGER_BIT_COUNT
            for index in range(EVENT_LEDGER_HASH_COUNT)
        )

    def observe(self, signature: str) -> bool:
        positions = self._positions(signature)
        known = all(
            self.bits[position // 8] & (1 << (position % 8))
            for position in positions
        )
        for position in positions:
            self.bits[position // 8] |= 1 << (position % 8)
        return not known

    def to_state(self) -> dict[str, Any]:
        return {
            "algorithm": "sha256-bloom-v1",
            "bit_count": EVENT_LEDGER_BIT_COUNT,
            "hash_count": EVENT_LEDGER_HASH_COUNT,
            "bits": self.bits.hex(),
        }


class WorkflowLivenessTracker:
    """Thread-safe bounded projection updated by controller coverage passes."""

    def __init__(
        self,
        *,
        max_task_records: int = DEFAULT_MAX_TASK_RECORDS,
        max_project_records: int = DEFAULT_MAX_PROJECT_RECORDS,
        snapshot_stale_seconds: int = DEFAULT_SNAPSHOT_STALE_SECONDS,
        slo_seconds: Mapping[str, int] | None = None,
        policy: LivenessPolicy | None = None,
        shared_lock: threading.RLock | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if isinstance(max_task_records, bool) or int(max_task_records) < 1:
            raise ValueError("max_task_records must be positive")
        if isinstance(max_project_records, bool) or int(max_project_records) < 1:
            raise ValueError("max_project_records must be positive")
        if isinstance(snapshot_stale_seconds, bool) or int(snapshot_stale_seconds) < 1:
            raise ValueError("snapshot_stale_seconds must be positive")
        self.max_task_records = int(max_task_records)
        self.max_project_records = int(max_project_records)
        self.snapshot_stale_seconds = int(snapshot_stale_seconds)
        if policy is not None and slo_seconds is not None:
            raise ValueError("provide policy or slo_seconds, not both")
        self._policy = policy or build_liveness_policy(slo_seconds)
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = shared_lock or threading.RLock()
        self._records: dict[tuple[str, str], _DecisionRecord] = {}
        self._expected: set[tuple[str, str]] = set()
        self._coverage: set[tuple[str, str]] = set()
        self._coverage_complete = False
        self._source_scan_complete = False
        self._restored = False
        self._last_observed_at: str | None = None
        self._snapshot_generation: int | None = None
        self._last_error: str | None = None
        self._source_errors: dict[str, str] = {}
        self._source_error_count = 0
        self._source_error_project_ids: set[str] = set()
        self._source_error_project_count = 0
        self._excluded_projects: dict[str, str] = {}
        self._excluded_project_ids: set[str] = set()
        self._excluded_project_count = 0
        self._excluded_task_count = 0
        self._project_task_counts: dict[str, int] = {}
        self._total_nonterminal_count = 0
        self._total_project_count = 0
        self._evaluated_count = 0
        self._missing_decision_count = 0
        self._restart_started_at: str | None = None
        self._restart_deadline_at: str | None = None
        self._reconciliation_complete = False
        self._required_recovery_count = 0
        self._materialized_recovery_count = 0
        self._cumulative_recovery_count = 0
        self._cumulative_escalation_count = 0
        self._cumulative_divergence_count = 0
        self._cumulative_restart_convergence_count = 0
        self._cumulative_reassessment_count = 0
        self._last_divergence_revision: str | None = None
        self._event_ledger = _BoundedEventLedger.empty()
        self._state_corrupt = False
        self._history_incomplete = False
        self._accepted_snapshot_generation = 0

    def reconfigure(
        self,
        *,
        max_task_records: int,
        max_project_records: int,
        snapshot_stale_seconds: int,
        slo_seconds: Mapping[str, int] | None = None,
        policy: LivenessPolicy | None = None,
    ) -> None:
        """Apply live limits atomically and immediately enforce a smaller cap."""

        if isinstance(max_task_records, bool) or int(max_task_records) < 1:
            raise ValueError("max_task_records must be positive")
        if isinstance(max_project_records, bool) or int(max_project_records) < 1:
            raise ValueError("max_project_records must be positive")
        if isinstance(snapshot_stale_seconds, bool) or int(snapshot_stale_seconds) < 1:
            raise ValueError("snapshot_stale_seconds must be positive")
        if policy is not None and slo_seconds is not None:
            raise ValueError("provide policy or slo_seconds, not both")
        replacement_policy = (
            policy
            if policy is not None
            else build_liveness_policy(slo_seconds)
            if slo_seconds is not None
            else None
        )
        with self._lock:
            self.max_task_records = int(max_task_records)
            self.max_project_records = int(max_project_records)
            self.snapshot_stale_seconds = int(snapshot_stale_seconds)
            if replacement_policy is not None:
                self._policy = replacement_policy
                for record in self._records.values():
                    key = _slo_key(record.status)
                    record.slo_seconds = (
                        self._policy.slos[key].max_reassessment_seconds
                        if key is not None
                        else None
                    )
                    record.policy_epoch = self._policy.epoch
                    if record.slo_seconds is not None:
                        record.next_reassessment_at = _render_time(
                            _parse_time(
                                record.last_progress_at, "last_progress_at"
                            )
                            + timedelta(seconds=record.slo_seconds)
                        )
                        if record.deadline_kind == "reassessment":
                            record.effective_deadline_at = (
                                record.next_reassessment_at
                            )
                if self._restart_started_at:
                    self._restart_deadline_at = _render_time(
                        _parse_time(
                            self._restart_started_at, "restart_started_at"
                        )
                        + timedelta(
                            seconds=self._policy.slos[
                                "restart_convergence"
                            ].max_reassessment_seconds
                        )
                    )
            if len(self._expected) > self.max_task_records:
                self._coverage_complete = False
                self._coverage.clear()
            self._source_errors = dict(
                sorted(self._source_errors.items())[: self.max_project_records]
            )
            self._source_error_project_ids = set(
                sorted(self._source_error_project_ids)[
                    : self.max_project_records
                ]
            )
            self._excluded_projects = dict(
                sorted(self._excluded_projects.items())[
                    : self.max_project_records
                ]
            )
            recorded_projects = {
                record.project_id for record in self._records.values()
            }
            self._excluded_project_ids = set(
                sorted(
                    self._excluded_project_ids,
                    key=lambda project_id: (
                        project_id not in recorded_projects,
                        project_id,
                    ),
                )[: self.max_task_records]
            )
            self._enforce_record_cap()

    def _restore_fail_closed(self, *, now: datetime, reason: str) -> None:
        """Install a conservative restart sentinel for unavailable history."""

        rendered = _render_time(now)
        with self._lock:
            self._records = {}
            self._expected = set()
            self._coverage = set()
            self._coverage_complete = False
            self._source_scan_complete = False
            self._restored = True
            self._state_corrupt = True
            self._history_incomplete = True
            self._last_observed_at = rendered
            self._snapshot_generation = None
            self._accepted_snapshot_generation = 0
            self._last_error = reason
            self._source_errors = {}
            self._source_error_count = 0
            self._source_error_project_ids = set()
            self._source_error_project_count = 0
            self._excluded_projects = {}
            self._excluded_project_ids = set()
            self._excluded_project_count = 0
            self._excluded_task_count = 0
            self._project_task_counts = {}
            self._total_nonterminal_count = 0
            self._total_project_count = 0
            self._evaluated_count = 0
            self._missing_decision_count = 0
            self._reconciliation_complete = False
            self._required_recovery_count = 0
            self._materialized_recovery_count = 0
            self._cumulative_recovery_count = 0
            self._cumulative_escalation_count = 0
            self._cumulative_divergence_count = 0
            self._cumulative_restart_convergence_count = 0
            self._cumulative_reassessment_count = 0
            self._last_divergence_revision = None
            self._event_ledger = _BoundedEventLedger.saturated()
            self._restart_started_at = rendered
            self._restart_deadline_at = rendered

    def restore(self, raw: object, *, now: datetime | None = None) -> None:
        """Restore bounded ages, but require fresh controller coverage to be healthy."""

        current = _utc(now or self._clock(), "now")
        if not isinstance(raw, Mapping):
            self._restore_fail_closed(
                now=current,
                reason="workflow liveness state is missing or not a mapping",
            )
            return
        try:
            schema_version = int(raw.get("schema_version", 0) or 0)
        except (TypeError, ValueError):
            self._restore_fail_closed(
                now=current,
                reason="workflow liveness state schema is corrupt",
            )
            return
        if schema_version != LIVENESS_STATE_SCHEMA_VERSION:
            self._restore_fail_closed(
                now=current,
                reason="workflow liveness state schema is unsupported",
            )
            return
        records: dict[tuple[str, str], _DecisionRecord] = {}
        raw_records = raw.get("records", ())
        state_corrupt = (
            bool(raw.get("history_corrupt"))
            or "records" not in raw
            or not (
                isinstance(raw_records, Sequence)
                and not isinstance(raw_records, (str, bytes))
            )
        )
        if isinstance(raw_records, Sequence) and not isinstance(
            raw_records, (str, bytes)
        ):
            # Persisted state was already bounded by the writer. Parse every
            # candidate before applying this process's possibly smaller cap so
            # actionable/critical priority, not alphabetical order, wins.
            for item in raw_records:
                if not isinstance(item, Mapping):
                    state_corrupt = True
                    continue
                try:
                    record = _DecisionRecord.from_state(item, now=current)
                except (TypeError, ValueError, OverflowError):
                    state_corrupt = True
                    continue
                if record.identity in records:
                    state_corrupt = True
                records[record.identity] = record
        raw_event_ledger = raw.get("event_signature_ledger")
        ledger_valid = _BoundedEventLedger.state_is_valid(raw_event_ledger)
        state_corrupt = state_corrupt or not ledger_valid
        event_ledger = (
            _BoundedEventLedger.from_state(raw_event_ledger)
            if ledger_valid and not state_corrupt
            else _BoundedEventLedger.saturated()
        )
        if state_corrupt:
            # Structurally valid records may still preserve useful timing and
            # evidence, but their event totals cannot remain nonzero after the
            # containing aggregate history has been discarded.  Keeping them
            # would make task/project totals exceed the reset global counters
            # permanently because the saturated ledger correctly forbids a
            # later recount.
            for record in records.values():
                record.recovery_count = 0
                record.escalation_count = 0
                record.reassessment_count = 0
        with self._lock:
            self._records = records
            for record in self._records.values():
                key = _slo_key(record.status)
                record.slo_seconds = (
                    self._policy.slos[key].max_reassessment_seconds
                    if key is not None
                    else None
                )
                record.policy_epoch = self._policy.epoch
                if record.slo_seconds is not None:
                    record.next_reassessment_at = _render_time(
                        _parse_time(record.last_progress_at, "last_progress_at")
                        + timedelta(seconds=record.slo_seconds)
                    )
                    if record.deadline_kind == "reassessment":
                        record.effective_deadline_at = (
                            record.next_reassessment_at
                        )
            self._enforce_record_cap()
            self._event_ledger = event_ledger
            self._state_corrupt = state_corrupt
            self._history_incomplete = bool(
                raw.get("history_incomplete")
                or state_corrupt
                or len(records) > self.max_task_records
            )
            self._expected = set()
            self._coverage = set()
            self._coverage_complete = False
            self._source_scan_complete = False
            raw_observed_at = str(raw.get("observed_at") or "").strip()
            try:
                restored_observed_at = (
                    _render_time(
                        min(_parse_time(raw_observed_at, "observed_at"), current)
                    )
                    if raw_observed_at
                    else None
                )
            except ValueError:
                restored_observed_at = None
            self._restored = bool(records or raw_observed_at or state_corrupt)
            self._last_observed_at = restored_observed_at
            try:
                self._accepted_snapshot_generation = max(
                    0,
                    int(raw.get("accepted_snapshot_generation", 0) or 0),
                )
            except (TypeError, ValueError):
                self._accepted_snapshot_generation = 0
            self._snapshot_generation = (
                self._accepted_snapshot_generation or None
            )
            raw_source_errors = raw.get("source_errors", {})
            self._source_errors = (
                {
                    str(key): str(value)
                    for key, value in sorted(raw_source_errors.items())[
                        : self.max_project_records
                    ]
                }
                if isinstance(raw_source_errors, Mapping)
                else {}
            )
            self._last_error = (
                "; ".join(
                    f"{key}:{value}"
                    for key, value in self._source_errors.items()
                )
                or (
                    "workflow liveness history is corrupt"
                    if state_corrupt
                    else None
                )
            )
            try:
                self._source_error_count = max(
                    len(self._source_errors),
                    int(raw.get("source_error_count", 0) or 0),
                )
            except (TypeError, ValueError):
                self._source_error_count = len(self._source_errors)
            raw_failed_projects = raw.get("source_error_project_ids", ())
            self._source_error_project_ids = (
                {
                    str(item)
                    for item in raw_failed_projects[: self.max_project_records]
                }
                if isinstance(raw_failed_projects, Sequence)
                and not isinstance(raw_failed_projects, (str, bytes))
                else set(self._source_errors)
            )
            try:
                self._source_error_project_count = max(
                    len(self._source_error_project_ids),
                    int(
                        raw.get(
                            "source_error_project_count",
                            self._source_error_count,
                        )
                        or 0
                    ),
                )
            except (TypeError, ValueError):
                self._source_error_project_count = max(
                    len(self._source_error_project_ids),
                    self._source_error_count,
                )
            raw_excluded = raw.get("excluded_projects", {})
            self._excluded_projects = (
                {
                    str(key): str(value)
                    for key, value in sorted(raw_excluded.items())[
                        : self.max_project_records
                    ]
                }
                if isinstance(raw_excluded, Mapping)
                else {}
            )
            raw_excluded_ids = raw.get("excluded_project_ids", ())
            self._excluded_project_ids = (
                {
                    str(item)
                    for item in raw_excluded_ids[: self.max_task_records]
                    if str(item).strip()
                }
                if isinstance(raw_excluded_ids, Sequence)
                and not isinstance(raw_excluded_ids, (str, bytes))
                else set(self._excluded_projects)
            )
            self._excluded_project_ids.update(self._excluded_projects)
            recorded_projects = {record.project_id for record in records.values()}
            self._excluded_project_ids = set(
                sorted(
                    self._excluded_project_ids,
                    key=lambda project_id: (
                        project_id not in recorded_projects,
                        project_id,
                    ),
                )[: self.max_task_records]
            )
            try:
                self._excluded_project_count = max(
                    len(self._excluded_projects),
                    len(self._excluded_project_ids),
                    int(raw.get("excluded_project_count", 0) or 0),
                )
            except (TypeError, ValueError):
                self._excluded_project_count = max(
                    len(self._excluded_projects),
                    len(self._excluded_project_ids),
                )
            try:
                self._excluded_task_count = max(
                    0, int(raw.get("excluded_task_count", 0) or 0)
                )
            except (TypeError, ValueError):
                self._excluded_task_count = 0
            try:
                restored_total = int(
                    raw.get("total_nonterminal_count", len(records)) or 0
                )
            except (TypeError, ValueError):
                restored_total = len(records)
            self._total_nonterminal_count = max(0, restored_total)
            raw_project_counts = raw.get("project_task_counts", {})
            self._project_task_counts = {}
            if isinstance(raw_project_counts, Mapping):
                for project_id, count in raw_project_counts.items():
                    normalized_project_id = str(project_id).strip()
                    if not normalized_project_id:
                        continue
                    try:
                        normalized_count = max(0, int(count))
                    except (TypeError, ValueError):
                        continue
                    self._project_task_counts[normalized_project_id] = (
                        normalized_count
                    )
            self._total_nonterminal_count = max(
                self._total_nonterminal_count,
                len(records),
                sum(self._project_task_counts.values()),
            )
            self._excluded_task_count = max(
                self._excluded_task_count,
                sum(
                    count
                    for project_id, count in self._project_task_counts.items()
                    if project_id in self._excluded_project_ids
                ),
            )
            self._history_incomplete = bool(
                self._history_incomplete
                or self._total_nonterminal_count > len(self._records)
            )
            try:
                self._total_project_count = max(
                    len({record.project_id for record in records.values()}),
                    len(self._project_task_counts),
                    self._source_error_project_count,
                    self._excluded_project_count,
                    int(raw.get("total_project_count", 0) or 0),
                )
            except (TypeError, ValueError):
                self._total_project_count = max(
                    len({record.project_id for record in records.values()}),
                    len(self._project_task_counts),
                    self._source_error_project_count,
                    self._excluded_project_count,
                )
            self._evaluated_count = 0
            self._missing_decision_count = 0
            self._reconciliation_complete = False
            try:
                self._required_recovery_count = max(
                    0, int(raw.get("required_recovery_count", 0) or 0)
                )
                self._materialized_recovery_count = max(
                    0, int(raw.get("materialized_recovery_count", 0) or 0)
                )
            except (TypeError, ValueError):
                self._required_recovery_count = 0
                self._materialized_recovery_count = 0
            # A corrupt nested record makes the aggregate history untrustworthy
            # too.  Keep the event ledger saturated so a later fresh scan cannot
            # recount unknown history, but do not publish persisted counters that
            # can no longer be tied to valid bounded records.
            cumulative = raw.get("cumulative", {}) if not state_corrupt else {}
            cumulative = cumulative if isinstance(cumulative, Mapping) else {}
            for attribute, key in (
                ("_cumulative_recovery_count", "recovery_count"),
                ("_cumulative_escalation_count", "escalation_count"),
                ("_cumulative_divergence_count", "divergence_count"),
                (
                    "_cumulative_restart_convergence_count",
                    "restart_convergence_count",
                ),
                ("_cumulative_reassessment_count", "reassessment_count"),
            ):
                try:
                    value = max(0, int(cumulative.get(key, 0) or 0))
                except (TypeError, ValueError):
                    value = 0
                setattr(self, attribute, value)
            raw_divergence = str(
                raw.get("last_divergence_revision") or ""
            ).strip()
            self._last_divergence_revision = raw_divergence or None
            persisted_pending = bool(raw.get("restart_reconstruction_pending"))
            try:
                raw_started = raw.get("restart_started_at")
                raw_deadline = raw.get("restart_deadline_at")
                persisted_started = (
                    _render_time(_parse_time(raw_started, "restart_started_at"))
                    if raw_started is not None and str(raw_started).strip()
                    else None
                )
                persisted_deadline = (
                    _render_time(_parse_time(raw_deadline, "restart_deadline_at"))
                    if raw_deadline is not None and str(raw_deadline).strip()
                    else None
                )
                if persisted_pending and (
                    not self._restored
                    or persisted_started is None
                    or persisted_deadline is None
                ):
                    raise ValueError(
                        "pending restart reconstruction requires timestamps"
                    )
                if (
                    persisted_started is not None
                    and persisted_deadline is not None
                    and _parse_time(persisted_deadline, "restart_deadline_at")
                    < _parse_time(persisted_started, "restart_started_at")
                ):
                    raise ValueError("restart deadline precedes restart start")
            except (TypeError, ValueError, OverflowError):
                rendered = _render_time(current)
                self._restored = True
                self._state_corrupt = True
                self._history_incomplete = True
                self._event_ledger = _BoundedEventLedger.saturated()
                self._source_scan_complete = False
                self._last_error = (
                    "workflow liveness restart timestamps are corrupt"
                )
                self._restart_started_at = rendered
                self._restart_deadline_at = rendered
            else:
                if self._restored:
                    started = (
                        min(
                            _parse_time(persisted_started, "restart_started_at"),
                            current,
                        )
                        if persisted_pending and persisted_started
                        else current
                    )
                    self._restart_started_at = _render_time(started)
                    same_policy_epoch = (
                        str(raw.get("policy_epoch") or "").strip()
                        == self._policy.epoch
                    )
                    self._restart_deadline_at = (
                        persisted_deadline
                        if persisted_pending
                        and persisted_deadline
                        and same_policy_epoch
                        else _render_time(
                            started
                            + timedelta(
                                seconds=self._policy.slos[
                                    "restart_convergence"
                                ].max_reassessment_seconds
                            )
                        )
                    )

    def observe(
        self,
        decisions: Sequence[WorkDecision],
        *,
        expected_identities: Sequence[tuple[str, str]],
        snapshot_generation: int,
        source_scan_complete: bool,
        reconciliation_complete: bool = True,
        required_recovery_count: int = 0,
        materialized_recovery_count: int = 0,
        decision_facts: Mapping[
            tuple[str, str], DecisionLivenessFacts
        ] | None = None,
        source_errors: Mapping[str, str] | None = None,
        excluded_projects: Mapping[str, str] | None = None,
        source_scan_deferred: bool = False,
        now: datetime | None = None,
    ) -> WorkflowLivenessHealth:
        """Replace the projection from one generation-consistent full scan.

        ``source_scan_deferred`` marks a scan that is only ``incomplete``
        because publication intentionally excluded already-covered tasks
        (e.g. terminal-audit disposition changes fenced at publish time),
        not because a source failed to scan.  When the deferred set is the
        sole reason the scan is not complete and every retained task is
        fully reconciled, restart reconstruction is allowed to finalize
        instead of remaining pending forever on a phantom divergence.
        """

        # Validate the complete authority set before changing any counters or
        # generation fields.  A malformed incoming revision must fail closed,
        # not partially publish a fresh observation timestamp.
        for decision in decisions:
            _required_digest_revision(
                decision.evidence_revision, "decision evidence_revision"
            )
        current = _utc(now or self._clock(), "now")
        if isinstance(snapshot_generation, bool) or int(snapshot_generation) < 1:
            raise ValueError("snapshot_generation must be positive")
        generation = int(snapshot_generation)
        expected = {
            (str(project_id), str(task_id))
            for project_id, task_id in expected_identities
        }
        all_errors = sorted(
            (str(project_id), str(error))
            for project_id, error in (source_errors or {}).items()
        )
        failed_project_ids = {project_id for project_id, _ in all_errors}
        all_excluded = sorted(
            (str(project_id), str(reason or "excluded"))
            for project_id, reason in (excluded_projects or {}).items()
        )
        excluded_project_ids = {
            project_id for project_id, _reason in all_excluded
        }
        overlapping_projects = failed_project_ids & excluded_project_ids
        if overlapping_projects:
            raise ValueError(
                "source errors and explicit exclusions overlap: "
                + ", ".join(sorted(overlapping_projects))
            )
        active_exclusion_overlap = {
            project_id
            for project_id, _task_id in expected
            if project_id in excluded_project_ids
        }
        active_exclusion_overlap.update(
            decision.project_id
            for decision in decisions
            if decision.project_id in excluded_project_ids
        )
        if active_exclusion_overlap:
            raise ValueError(
                "excluded projects escaped into the active topology: "
                + ", ".join(sorted(active_exclusion_overlap))
            )
        normalized_errors = dict(all_errors[: self.max_project_records])
        required_recovery_count = max(0, int(required_recovery_count))
        materialized_recovery_count = max(0, int(materialized_recovery_count))
        effective_reconciliation_complete = bool(
            reconciliation_complete
            and materialized_recovery_count >= required_recovery_count
        )
        # A publication-deferred scan (terminal-audit exclusions of tasks
        # that are already covered) is not a source failure.  When the
        # deferral is the only reason the scan is not complete and every
        # retained task is fully reconciled, treat the scan as effectively
        # complete so restart reconstruction can finalize.
        source_scan_effectively_complete = bool(
            source_scan_complete
            or (
                source_scan_deferred
                and not all_errors
                and effective_reconciliation_complete
            )
        )
        effective_source_complete = bool(
            source_scan_effectively_complete
            and not all_errors
            and effective_reconciliation_complete
        )
        metadata = decision_facts or {}
        with self._lock:
            if generation <= self._accepted_snapshot_generation:
                return self._snapshot_locked(current)
            self._accepted_snapshot_generation = generation
            self._last_observed_at = _render_time(current)
            self._snapshot_generation = generation
            self._last_error = (
                "; ".join(
                    f"{project_id}:{error}"
                    for project_id, error in sorted(normalized_errors.items())
                )
                or None
            )
            self._source_errors = normalized_errors
            self._source_error_count = len(all_errors)
            self._source_error_project_ids = set(failed_project_ids)
            self._source_error_project_count = len(failed_project_ids)
            self._excluded_projects = dict(
                all_excluded[: self.max_project_records]
            )
            self._excluded_project_ids = set(excluded_project_ids)
            self._excluded_project_count = len(all_excluded)
            self._source_scan_complete = effective_source_complete
            self._reconciliation_complete = effective_reconciliation_complete
            self._required_recovery_count = required_recovery_count
            self._materialized_recovery_count = materialized_recovery_count

            # A failed project source is absent from ``expected``. Preserve
            # its last-known membership and attribution until a successful
            # source scan proves those tasks changed or became terminal.
            retained_failed = {
                identity
                for identity in self._records
                if identity[0] in failed_project_ids
            }
            retained_excluded = {
                identity
                for identity in self._records
                if identity[0] in excluded_project_ids
            }
            current_membership = expected | retained_failed | retained_excluded
            successful_counts: dict[str, int] = {}
            for project_id, _task_id in expected:
                successful_counts[project_id] = (
                    successful_counts.get(project_id, 0) + 1
                )
            prior_project_counts = self._project_task_counts
            self._project_task_counts = dict(successful_counts)
            for project_id in failed_project_ids:
                self._project_task_counts[project_id] = max(
                    successful_counts.get(project_id, 0),
                    prior_project_counts.get(project_id, 0),
                )
            for project_id in excluded_project_ids:
                self._project_task_counts[project_id] = max(
                    successful_counts.get(project_id, 0),
                    prior_project_counts.get(project_id, 0),
                )
            self._total_nonterminal_count = sum(
                self._project_task_counts.values()
            )
            self._excluded_task_count = sum(
                count
                for project_id, count in self._project_task_counts.items()
                if project_id in excluded_project_ids
            )
            self._total_project_count = len(
                set(self._project_task_counts)
                | failed_project_ids
                | excluded_project_ids
            )
            self._evaluated_count = len(decisions)

            decision_identities = {
                (decision.project_id, decision.task_id) for decision in decisions
            }
            self._coverage = decision_identities & expected
            self._missing_decision_count = (
                len(expected - decision_identities)
                if len(current_membership) <= self.max_task_records
                else 0
            )
            self._coverage_complete = (
                effective_source_complete
                and len(current_membership) <= self.max_task_records
                and self._coverage == expected
                and not retained_failed
            )
            self._expected = (
                current_membership
                if len(current_membership) <= self.max_task_records
                else set()
            )

            for identity in tuple(self._records):
                if identity not in current_membership:
                    self._records.pop(identity, None)

            for decision in decisions:
                identity = (decision.project_id, decision.task_id)
                previous = self._records.get(identity)
                slo_key = _slo_key(decision.status)
                record = _DecisionRecord.from_decision(
                    decision,
                    now=current,
                    previous=previous,
                    liveness_facts=metadata.get(
                        identity, DecisionLivenessFacts()
                    ),
                    slo_seconds=(
                        self._policy.slos[
                            slo_key
                        ].max_reassessment_seconds
                        if slo_key is not None
                        else None
                    ),
                    policy_epoch=self._policy.epoch,
                    conservative_progress=(
                        (self._state_corrupt or self._history_incomplete)
                        and previous is None
                    ),
                )
                if (
                    self._state_corrupt or self._history_incomplete
                ) and previous is None:
                    # The current signature may be unchanged historical work.
                    # Saturation protects global identity; keep the bounded
                    # per-task projection equally conservative.
                    record.recovery_count = 0
                    record.escalation_count = 0
                    record.reassessment_count = 0
                recovery_event = (
                    decision.disposition is TaskDisposition.RETRY_SCHEDULED
                )
                escalation_event = decision.action_required
                if recovery_event:
                    if self._event_ledger.observe(
                        _event_signature(decision, "recovery")
                    ):
                        self._cumulative_recovery_count += 1
                if escalation_event:
                    if self._event_ledger.observe(
                        _event_signature(decision, "escalation")
                    ):
                        self._cumulative_escalation_count += 1
                self._cumulative_reassessment_count += max(
                    0,
                    record.reassessment_count
                    - (previous.reassessment_count if previous else 0),
                )
                self._records[identity] = record
            self._enforce_record_cap()
            current_divergence = self._missing_decision_count + len(all_errors)
            if not effective_reconciliation_complete:
                current_divergence += max(
                    1,
                    required_recovery_count - materialized_recovery_count,
                )
            if not source_scan_complete and not all_errors:
                current_divergence += 1
            divergence_revision = None
            if current_divergence:
                divergence_revision = hashlib.sha256(
                    json.dumps(
                        {
                            "errors": all_errors,
                            "missing": sorted(expected - decision_identities),
                            "reconciliation_complete": (
                                effective_reconciliation_complete
                            ),
                            "required": required_recovery_count,
                            "materialized": materialized_recovery_count,
                            "source_scan_complete": bool(source_scan_complete),
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                ).hexdigest()
                if divergence_revision != self._last_divergence_revision:
                    self._cumulative_divergence_count += current_divergence
            self._last_divergence_revision = divergence_revision
            if self._coverage_complete:
                if self._restored and not self._state_corrupt:
                    self._cumulative_restart_convergence_count += 1
                self._restored = False
                self._state_corrupt = False
                self._history_incomplete = False
                self._restart_started_at = None
                self._restart_deadline_at = None
            return self._snapshot_locked(current)

    def record_scan_failure(
        self,
        error: str,
        *,
        snapshot_generation: int | None = None,
        now: datetime | None = None,
    ) -> WorkflowLivenessHealth:
        current = _utc(now or self._clock(), "now")
        if snapshot_generation is not None and (
            isinstance(snapshot_generation, bool)
            or int(snapshot_generation) < 1
        ):
            raise ValueError("snapshot_generation must be positive")
        with self._lock:
            generation = (
                self._accepted_snapshot_generation + 1
                if snapshot_generation is None
                else int(snapshot_generation)
            )
            if generation <= self._accepted_snapshot_generation:
                return self._snapshot_locked(current)
            self._accepted_snapshot_generation = generation
            self._snapshot_generation = generation
            self._last_observed_at = _render_time(current)
            self._last_error = str(error or "workflow liveness scan failed")
            self._source_errors = {"controller": self._last_error}
            self._source_error_count = 1
            self._source_error_project_ids = {"controller"}
            self._source_error_project_count = 1
            self._excluded_projects = {}
            self._excluded_project_ids = set()
            self._excluded_project_count = 0
            self._excluded_task_count = 0
            self._total_project_count = max(
                self._total_project_count,
                len(set(self._project_task_counts) | {"controller"}),
            )
            self._coverage.clear()
            self._coverage_complete = False
            self._source_scan_complete = False
            self._reconciliation_complete = False
            self._required_recovery_count = 0
            self._materialized_recovery_count = 0
            self._evaluated_count = 0
            self._missing_decision_count = 0
            revision = hashlib.sha256(
                f"controller:{self._last_error}".encode("utf-8")
            ).hexdigest()
            if revision != self._last_divergence_revision:
                self._cumulative_divergence_count += 1
            self._last_divergence_revision = revision
            return self._snapshot_locked(current)

    def _enforce_record_cap(self) -> None:
        if len(self._records) <= self.max_task_records:
            return
        self._history_incomplete = True
        ordered = sorted(
            self._records.values(),
            key=lambda item: (
                not item.action_required,
                item.alert_level != AlertSeverity.CRITICAL.value,
                item.last_observed_at,
                item.project_id,
                item.task_id,
            ),
        )
        self._records = {
            item.identity: item for item in ordered[: self.max_task_records]
        }

    def snapshot(self, *, now: datetime | None = None) -> WorkflowLivenessHealth:
        current = _utc(now or self._clock(), "now")
        with self._lock:
            return self._snapshot_locked(current)

    def transaction_checkpoint(self) -> dict[str, Any]:
        """Capture bounded mutable state for persistence rollback."""

        with self._lock:
            return {
                key: copy.deepcopy(value)
                for key, value in self.__dict__.items()
                if key not in {"_lock", "_clock", "_policy"}
            }

    def restore_transaction_checkpoint(
        self, checkpoint: Mapping[str, Any]
    ) -> None:
        """Restore an unpublished observe/failure when durable save fails."""

        with self._lock:
            for key, value in checkpoint.items():
                if key not in {"_lock", "_clock", "_policy"}:
                    setattr(self, key, copy.deepcopy(value))

    def _snapshot_locked(self, now: datetime) -> WorkflowLivenessHealth:
        projections = tuple(
            record.project(now=now)
            for record in sorted(
                (
                    record
                    for record in self._records.values()
                    if record.project_id not in self._excluded_project_ids
                ),
                key=lambda item: item.identity,
            )
        )
        stale = True
        if self._last_observed_at:
            try:
                observed_at = _parse_time(self._last_observed_at, "observed_at")
                age = (now - observed_at).total_seconds()
                stale = age > self.snapshot_stale_seconds
            except ValueError:
                stale = True
        scan_complete = self._coverage_complete and not stale and not self._restored
        action_required = sum(item.action_required for item in projections)
        overdue = sum(item.overdue for item in projections)
        unmaterialized_recovery = max(
            0,
            self._required_recovery_count
            - self._materialized_recovery_count,
        )
        unexplained = self._missing_decision_count + int(
            self._last_observed_at is not None
            and not self._restored
            and not self._source_scan_complete
            and self._source_error_count == 0
            and self._reconciliation_complete
        ) + (
            max(1, unmaterialized_recovery)
            if not self._reconciliation_complete
            else 0
        )
        current_divergence = unexplained + self._source_error_count
        active_recovery = sum(
            item.disposition == TaskDisposition.RETRY_SCHEDULED.value
            for item in projections
        )
        recovery = self._cumulative_recovery_count
        escalation = self._cumulative_escalation_count
        reassessments = self._cumulative_reassessment_count
        owned = sum(
            item.disposition == TaskDisposition.OWNED.value for item in projections
        )
        by_status: dict[str, int] = {}
        by_project: dict[str, dict[str, Any]] = {}
        for item in projections:
            by_status[item.status] = by_status.get(item.status, 0) + 1
            summary = by_project.setdefault(
                item.project_id,
                {
                    "task_count": 0,
                    "action_required_count": 0,
                    "escalation_count": 0,
                    "overdue_count": 0,
                    "recovery_count": 0,
                    "active_recovery_count": 0,
                    "reassessment_count": 0,
                    "owned_count": 0,
                    "source_error": None,
                },
            )
            summary["task_count"] += 1
            summary["action_required_count"] += int(item.action_required)
            summary["escalation_count"] += item.escalation_count
            summary["overdue_count"] += int(item.overdue)
            summary["recovery_count"] += item.recovery_count
            summary["active_recovery_count"] += int(
                item.disposition == TaskDisposition.RETRY_SCHEDULED.value
            )
            summary["reassessment_count"] += item.reassessment_count
            summary["owned_count"] += int(
                item.disposition == TaskDisposition.OWNED.value
            )
        for project_id, exact_count in self._project_task_counts.items():
            summary = by_project.setdefault(
                project_id,
                {
                    "task_count": 0,
                    "action_required_count": 0,
                    "escalation_count": 0,
                    "overdue_count": 0,
                    "recovery_count": 0,
                    "active_recovery_count": 0,
                    "reassessment_count": 0,
                    "owned_count": 0,
                    "source_error": None,
                },
            )
            tracked_count = int(summary["task_count"])
            summary["tracked_task_count"] = tracked_count
            summary["task_count"] = exact_count
            summary["omitted_task_count"] = max(
                0, exact_count - tracked_count
            )
            if project_id in self._excluded_project_ids:
                summary["excluded"] = True
                summary["coverage_state"] = "excluded"
                summary["exclusion_reason"] = self._excluded_projects.get(
                    project_id, "explicitly excluded"
                )
                summary["last_known_task_count"] = exact_count
                summary["task_count"] = 0
                summary["tracked_task_count"] = 0
                summary["omitted_task_count"] = 0
        for project_id, error in self._source_errors.items():
            summary = by_project.setdefault(
                project_id,
                {
                    "task_count": 0,
                    "action_required_count": 0,
                    "escalation_count": 0,
                    "overdue_count": 0,
                    "recovery_count": 0,
                    "active_recovery_count": 0,
                    "reassessment_count": 0,
                    "owned_count": 0,
                    "source_error": None,
                },
            )
            summary.setdefault("tracked_task_count", summary["task_count"])
            summary.setdefault("omitted_task_count", 0)
            summary["source_error"] = error
        for project_id in self._source_error_project_ids:
            summary = by_project.setdefault(
                project_id,
                {
                    "task_count": 0,
                    "action_required_count": 0,
                    "escalation_count": 0,
                    "overdue_count": 0,
                    "recovery_count": 0,
                    "active_recovery_count": 0,
                    "reassessment_count": 0,
                    "owned_count": 0,
                    "source_error": None,
                },
            )
            if summary["source_error"] is None:
                summary["source_error"] = "source scan failed"
            summary.setdefault("tracked_task_count", summary["task_count"])
            summary.setdefault("omitted_task_count", 0)
        ordered_projects = sorted(
            by_project.items(),
            key=lambda item: (
                item[1]["source_error"] is None,
                -int(item[1]["action_required_count"]),
                -int(item[1]["overdue_count"]),
                -int(item[1]["task_count"]),
                item[0],
            ),
        )
        projects = dict(ordered_projects[: self.max_project_records])
        omitted_projects = max(
            0,
            self._total_project_count - len(projects),
        )
        excluded_task_count = self._excluded_task_count
        active_nonterminal_count = max(
            0,
            self._total_nonterminal_count - excluded_task_count,
        )

        restart_lateness = 0
        if self._restart_deadline_at:
            try:
                restart_deadline = _parse_time(
                    self._restart_deadline_at, "restart_deadline_at"
                )
            except (TypeError, ValueError, OverflowError):
                # State can be changed by a failed persistence/reload path
                # between restore and this read.  A health endpoint must
                # never turn that corruption into a startup crash.
                rendered = _render_time(now)
                self._restored = True
                self._state_corrupt = True
                self._history_incomplete = True
                self._source_scan_complete = False
                self._coverage_complete = False
                self._event_ledger = _BoundedEventLedger.saturated()
                self._last_error = "workflow liveness restart timestamps are corrupt"
                self._restart_started_at = rendered
                self._restart_deadline_at = rendered
            else:
                restart_lateness = _seconds(
                    max(0.0, (now - restart_deadline).total_seconds())
                )

        if action_required:
            status = "action_required"
        elif self._restored and restart_lateness:
            status = "restart_overdue"
        elif not scan_complete:
            status = "incomplete"
        elif overdue:
            status = "overdue"
        elif unexplained:
            status = "invariant_breach"
        else:
            status = "healthy"
        return WorkflowLivenessHealth(
            status=status,
            observed_at=self._last_observed_at,
            snapshot_generation=self._snapshot_generation,
            scan_complete=scan_complete,
            restored=self._restored,
            stale=stale,
            last_error=self._last_error,
            source_errors=dict(sorted(self._source_errors.items())),
            source_error_count=self._source_error_count,
            omitted_source_error_count=max(
                0, self._source_error_count - len(self._source_errors)
            ),
            total_nonterminal_count=self._total_nonterminal_count,
            evaluated_count=self._evaluated_count,
            tracked_task_count=len(projections),
            omitted_task_count=max(
                0, active_nonterminal_count - len(projections)
            ),
            missing_decision_count=self._missing_decision_count,
            divergence_count=self._cumulative_divergence_count,
            current_divergence_count=current_divergence,
            action_required_count=action_required,
            overdue_count=overdue,
            unexplained_count=unexplained,
            recovery_count=recovery,
            active_recovery_count=active_recovery,
            escalation_count=escalation,
            reassessment_count=reassessments,
            owned_count=owned,
            task_count_by_status=by_status,
            projects=projects,
            omitted_project_count=omitted_projects,
            coverage_scope="active_projects",
            global_coverage_complete=bool(
                scan_complete and self._excluded_project_count == 0
            ),
            active_project_count=max(
                0,
                self._total_project_count - self._excluded_project_count,
            ),
            excluded_projects=dict(sorted(self._excluded_projects.items())),
            excluded_project_count=self._excluded_project_count,
            omitted_excluded_project_count=max(
                0,
                self._excluded_project_count - len(self._excluded_projects),
            ),
            excluded_task_count=excluded_task_count,
            oldest_decision_age_seconds=max(
                (item.decision_age_seconds for item in projections), default=None
            ),
            oldest_reassessment_lateness_seconds=max(
                (item.reassessment_lateness_seconds for item in projections),
                default=None,
            ),
            max_task_records=self.max_task_records,
            max_project_records=self.max_project_records,
            snapshot_stale_seconds=self.snapshot_stale_seconds,
            policy_epoch=self._policy.epoch,
            restart_reconstruction_pending=self._restored,
            restart_started_at=self._restart_started_at,
            restart_deadline_at=self._restart_deadline_at,
            restart_lateness_seconds=restart_lateness,
            restart_convergence_count=(
                self._cumulative_restart_convergence_count
            ),
            reconciliation_complete=self._reconciliation_complete,
            required_recovery_count=self._required_recovery_count,
            materialized_recovery_count=self._materialized_recovery_count,
            tasks=projections,
        )

    def to_state(self) -> dict[str, Any]:
        with self._lock:
            return {
                "schema_version": LIVENESS_STATE_SCHEMA_VERSION,
                "observed_at": self._last_observed_at,
                "policy_epoch": self._policy.epoch,
                "accepted_snapshot_generation": (
                    self._accepted_snapshot_generation
                ),
                "total_nonterminal_count": self._total_nonterminal_count,
                "total_project_count": self._total_project_count,
                "coverage_scope": "active_projects",
                "global_coverage_complete": bool(
                    self._coverage_complete
                    and self._excluded_project_count == 0
                ),
                "active_project_count": max(
                    0,
                    self._total_project_count - self._excluded_project_count,
                ),
                "excluded_task_count": self._excluded_task_count,
                "project_task_counts": dict(
                    sorted(self._project_task_counts.items())
                ),
                "restart_reconstruction_pending": self._restored,
                "history_corrupt": self._state_corrupt,
                "history_incomplete": self._history_incomplete,
                "restart_started_at": self._restart_started_at,
                "restart_deadline_at": self._restart_deadline_at,
                "source_errors": dict(self._source_errors),
                "source_error_count": self._source_error_count,
                "source_error_project_ids": sorted(
                    self._source_error_project_ids
                )[: self.max_project_records],
                "source_error_project_count": (
                    self._source_error_project_count
                ),
                "excluded_projects": dict(
                    sorted(self._excluded_projects.items())
                ),
                "excluded_project_ids": sorted(
                    self._excluded_project_ids,
                    key=lambda project_id: (
                        project_id
                        not in {
                            record.project_id
                            for record in self._records.values()
                        },
                        project_id,
                    ),
                )[: self.max_task_records],
                "excluded_project_count": self._excluded_project_count,
                "required_recovery_count": self._required_recovery_count,
                "materialized_recovery_count": (
                    self._materialized_recovery_count
                ),
                "last_divergence_revision": self._last_divergence_revision,
                "cumulative": {
                    "recovery_count": self._cumulative_recovery_count,
                    "escalation_count": self._cumulative_escalation_count,
                    "divergence_count": self._cumulative_divergence_count,
                    "restart_convergence_count": (
                        self._cumulative_restart_convergence_count
                    ),
                    "reassessment_count": self._cumulative_reassessment_count,
                },
                "event_signature_ledger": self._event_ledger.to_state(),
                "records": [
                    item.to_state()
                    for item in sorted(
                        self._records.values(), key=lambda record: record.identity
                    )
                ],
            }


def workflow_liveness_health_alerts(
    health: WorkflowLivenessHealth,
) -> list[dict[str, Any]]:
    """Return a warning only for authoritative ``action_required`` decisions."""

    if health.action_required_count == 0:
        return []
    attributable = tuple(item for item in health.tasks if item.action_required)
    level = (
        AlertSeverity.CRITICAL.value
        if any(item.alert_level == AlertSeverity.CRITICAL.value for item in attributable)
        else AlertSeverity.WARNING.value
    )
    task_ids = [f"{item.project_id}/{item.task_id}" for item in attributable]
    return [
        {
            "source": "workflow_liveness:action_required",
            "level": level,
            "severity": level,
            "action_required": True,
            "count": health.action_required_count,
            "tasks": task_ids,
            "message": (
                f"{health.action_required_count} workflow task(s) require "
                "a named human action."
            ),
        }
    ]


__all__ = [
    "DEFAULT_MAX_PROJECT_RECORDS",
    "DEFAULT_MAX_TASK_RECORDS",
    "DEFAULT_SNAPSHOT_STALE_SECONDS",
    "DecisionLivenessFacts",
    "LivenessTaskProjection",
    "WorkflowLivenessHealth",
    "WorkflowLivenessTracker",
    "workflow_liveness_health_alerts",
]
