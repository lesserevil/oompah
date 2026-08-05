"""Durable implementation ownership and lifecycle actions.

Implementation sessions are represented by short-lived durable action jobs.
The verified receipt of each job is an immutable ownership disposition; an
agent process or direct owner is only an executor of that disposition, never
the authority for it.  Starting work, handing focus to a peer, recording a
worker exit, submitting validation, revoking authority, and retrying are thus
all restart-safe and generation fenced by :mod:`oompah.workflow_jobs`.
"""

from __future__ import annotations

import hashlib
import inspect
import json
from collections.abc import Awaitable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol

from oompah.models import Issue
from oompah.statuses import (
    DUPLICATE_CANDIDATE,
    IN_PROGRESS,
    NEEDS_CI_FIX,
    NEEDS_REBASE,
    OPEN,
)
from oompah.task_transition_service import TransitionIntent, issue_authority_version
from oompah.work_decision import (
    IMPLEMENTATION_ACTION_JOBS,
    WorkDecision,
    evaluate_task,
)
from oompah.workflow_facts import (
    FactDomain,
    FactState,
    WorkflowFactCollector,
    WorkflowFacts,
)
from oompah.workflow_jobs import (
    ACTIVE_JOB_STATES,
    WorkflowFailureCategory,
    WorkflowJob,
    WorkflowJobSpec,
    WorkflowJobStore,
)
from oompah.workflow_scheduler import WorkflowJobScheduler, WorkflowReconcileResult
from oompah.workflow_worker import (
    EffectObservation,
    EffectResult,
    RevalidationResult,
    VerificationResult,
    WorkflowActionDomain,
    WorkflowActionError,
    WorkflowActionSuperseded,
    WorkflowJobContext,
)

IMPLEMENTATION_DISPOSITION_SCHEMA_VERSION = 1
DEFAULT_IMPLEMENTATION_DECISION_LIMIT = 1000
FACT_IMPLEMENTATION_LANE = "event:implementation:fact"
IMPERATIVE_IMPLEMENTATION_LANE = "event:implementation:imperative"
IMPLEMENTATION_ORDERING_NAMESPACE = "implementation-decision"


class ImplementationAction(str, Enum):
    START = "implementation_start"
    DIRECT_OWNER_CLAIM = "direct_owner_claim"
    DUPLICATE_SCREENING = "duplicate_screening"
    FOCUS_HANDOFF = "focus_handoff"
    WORKER_EXIT = "worker_exit"
    VALIDATION_SUBMISSION = "validation_submission"
    AUTHORITY_REVOCATION = "authority_revocation"
    RETRY = "implementation_retry"
    RECOVERY = "implementation_recovery"


IMPLEMENTATION_ACTIONS = IMPLEMENTATION_ACTION_JOBS
if IMPLEMENTATION_ACTIONS != frozenset(action.value for action in ImplementationAction):
    raise RuntimeError("implementation actions disagree with shared work decisions")


class ImplementationOwnershipSource(str, Enum):
    AGENT = "agent"
    DIRECT_OWNER = "direct_owner"
    DUPLICATE_INVESTIGATOR = "duplicate_investigator"
    RECOVERY = "recovery"


class ImplementationState(str, Enum):
    CLAIMED = "claimed"
    ACTIVE = "active"
    HANDED_OFF = "handed_off"
    INCOMPLETE = "incomplete"
    RETRY_WAIT = "retry_wait"
    SUBMITTED = "submitted"
    REVOKED = "revoked"
    COMPLETED = "completed"


def _required_text(value: object, name: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise ValueError(f"{name} is required")
    return result


def _optional_text(value: object | None) -> str | None:
    if value is None:
        return None
    result = str(value).strip()
    return result or None


def _timestamp_epoch(value: object, name: str) -> float:
    raw = _required_text(value, name)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{name} must include a timezone")
    return parsed.astimezone(timezone.utc).timestamp()


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _canonical_payload(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise TypeError("payload must be a mapping")
    try:
        decoded = json.loads(
            json.dumps(
                dict(value),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            )
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("payload must be JSON serializable") from exc
    if not isinstance(decoded, dict):
        raise TypeError("payload must be a JSON object")
    return decoded


def _event_revision(
    *,
    project_id: str,
    task_id: str,
    action: str,
    payload: Mapping[str, Any],
    expected_evidence_revision: str | None,
    expected_head_sha: str | None,
) -> str:
    semantic = {
        "project_id": project_id,
        "task_id": task_id,
        "action": action,
        "payload": payload,
        "expected_evidence_revision": _optional_text(expected_evidence_revision),
        "expected_head_sha": _optional_text(expected_head_sha),
    }
    return hashlib.sha256(_canonical_json(semantic).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class ImplementationDisposition:
    """Durable proof of the one accepted implementation disposition."""

    project_id: str
    task_id: str
    generation: str
    action: ImplementationAction | str
    state: ImplementationState | str
    ownership_source: ImplementationOwnershipSource | str
    owner_id: str | None = None
    assignment_id: str | None = None
    run_id: str | None = None
    focus: str | None = None
    work_branch: str | None = None
    head_sha: str | None = None
    lease_expires_at: str | None = None
    retry_at: str | None = None
    incomplete_sessions: int = 0
    advisory_denials: int = 0
    authority_revision: str | None = None
    schema_version: int = IMPLEMENTATION_DISPOSITION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in ("project_id", "task_id", "generation"):
            object.__setattr__(self, name, _required_text(getattr(self, name), name))
        object.__setattr__(self, "action", ImplementationAction(self.action))
        object.__setattr__(self, "state", ImplementationState(self.state))
        object.__setattr__(
            self,
            "ownership_source",
            ImplementationOwnershipSource(self.ownership_source),
        )
        for name in (
            "owner_id",
            "assignment_id",
            "run_id",
            "focus",
            "work_branch",
            "head_sha",
            "lease_expires_at",
            "retry_at",
        ):
            object.__setattr__(self, name, _optional_text(getattr(self, name)))
        for name in ("incomplete_sessions", "advisory_denials"):
            value = getattr(self, name)
            if isinstance(value, bool) or int(value) < 0:
                raise ValueError(f"{name} must be a non-negative integer")
            object.__setattr__(self, name, int(value))
        if self.schema_version != IMPLEMENTATION_DISPOSITION_SCHEMA_VERSION:
            raise ValueError("unsupported implementation disposition schema_version")
        revision = self.compute_authority_revision()
        if self.authority_revision is not None and self.authority_revision != revision:
            raise ValueError("authority_revision does not match disposition")
        object.__setattr__(self, "authority_revision", revision)

    def compute_authority_revision(self) -> str:
        """Hash authority semantics, excluding clocks and advisory telemetry."""

        semantic = {
            "schema_version": self.schema_version,
            "project_id": self.project_id,
            "task_id": self.task_id,
            "generation": self.generation,
            "action": self.action.value,
            "state": self.state.value,
            "ownership_source": self.ownership_source.value,
            "owner_id": self.owner_id,
            "assignment_id": self.assignment_id,
            "run_id": self.run_id,
            "focus": self.focus,
            "work_branch": self.work_branch,
            "head_sha": self.head_sha,
            "incomplete_sessions": self.incomplete_sessions,
        }
        return hashlib.sha256(_canonical_json(semantic).encode()).hexdigest()

    def matches(self, job: WorkflowJob, *, allow_incomplete: bool = False) -> bool:
        if not (
            self.project_id == job.project_id
            and self.task_id == job.task_id
            and self.generation == job.generation
            and self.action.value == job.action
            and (not job.expected_head_sha or self.head_sha == job.expected_head_sha)
        ):
            return False
        required_source = {
            ImplementationAction.DIRECT_OWNER_CLAIM: (
                ImplementationOwnershipSource.DIRECT_OWNER
            ),
            ImplementationAction.DUPLICATE_SCREENING: (
                ImplementationOwnershipSource.DUPLICATE_INVESTIGATOR
            ),
            ImplementationAction.RECOVERY: ImplementationOwnershipSource.RECOVERY,
        }.get(self.action)
        if required_source is not None and self.ownership_source is not required_source:
            return False
        required_state = {
            ImplementationAction.START: ImplementationState.ACTIVE,
            ImplementationAction.DIRECT_OWNER_CLAIM: ImplementationState.ACTIVE,
            ImplementationAction.DUPLICATE_SCREENING: ImplementationState.ACTIVE,
            ImplementationAction.FOCUS_HANDOFF: ImplementationState.HANDED_OFF,
            ImplementationAction.WORKER_EXIT: ImplementationState.COMPLETED,
            ImplementationAction.VALIDATION_SUBMISSION: ImplementationState.SUBMITTED,
            ImplementationAction.AUTHORITY_REVOCATION: ImplementationState.REVOKED,
            ImplementationAction.RETRY: ImplementationState.RETRY_WAIT,
            ImplementationAction.RECOVERY: ImplementationState.ACTIVE,
        }[self.action]
        if self.state is not required_state and not (
            allow_incomplete and self.state is ImplementationState.INCOMPLETE
        ):
            return False
        if self.state in {
            ImplementationState.CLAIMED,
            ImplementationState.ACTIVE,
            ImplementationState.HANDED_OFF,
        } and (not self.owner_id or not self.lease_expires_at):
            return False
        if self.state is ImplementationState.HANDED_OFF and not self.focus:
            return False
        if (
            self.action is ImplementationAction.DUPLICATE_SCREENING
            and not self.owner_id
        ):
            return False
        if self.state is ImplementationState.RETRY_WAIT and not self.retry_at:
            return False
        if self.state is ImplementationState.INCOMPLETE and self.incomplete_sessions < 1:
            return False
        payload = job.payload or {}
        semantic_fields = {
            "owner_id": self.owner_id,
            "assignment_id": self.assignment_id,
            "run_id": self.run_id,
            "focus": self.focus,
            "work_branch": self.work_branch,
            "head_sha": self.head_sha,
            "lease_expires_at": self.lease_expires_at,
            "ownership_source": self.ownership_source.value,
            "state": self.state.value,
        }
        return all(
            key not in payload or _optional_text(payload[key]) == observed
            for key, observed in semantic_fields.items()
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "project_id": self.project_id,
            "task_id": self.task_id,
            "generation": self.generation,
            "action": self.action.value,
            "state": self.state.value,
            "ownership_source": self.ownership_source.value,
            "owner_id": self.owner_id,
            "assignment_id": self.assignment_id,
            "run_id": self.run_id,
            "focus": self.focus,
            "work_branch": self.work_branch,
            "head_sha": self.head_sha,
            "lease_expires_at": self.lease_expires_at,
            "retry_at": self.retry_at,
            "incomplete_sessions": self.incomplete_sessions,
            "advisory_denials": self.advisory_denials,
            "authority_revision": self.authority_revision,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "ImplementationDisposition":
        if not isinstance(raw, Mapping):
            raise ValueError("implementation disposition must be an object")
        return cls(**dict(raw))


class ImplementationRoute(str, Enum):
    COMPLETED = "completed"
    ADVISORY = "advisory"
    RETRY = "retry"
    SUPERSEDED = "superseded"
    ACTION_REQUIRED = "action_required"


@dataclass(frozen=True, slots=True)
class ImplementationExecutionResult:
    status: str
    message: str
    disposition: ImplementationDisposition | None = None
    retry_delay_seconds: float = 0


@dataclass(frozen=True, slots=True)
class ClassifiedImplementationResult:
    route: ImplementationRoute
    retryable: bool
    category: WorkflowFailureCategory


_SUCCESS_RESULTS = frozenset(
    {
        "started",
        "owner_claimed",
        "duplicate_screened",
        "handoff_recorded",
        "worker_completed",
        "submitted",
        "revoked",
        "retry_scheduled",
        "recovered",
    }
)
_ADVISORY_RESULTS = frozenset({"advisory_denied", "peer_denied"})
_RETRY_RESULTS = frozenset(
    {
        "incomplete",
        "interrupted",
        "transport_error",
        "provider_unavailable",
        "token_changed",
        "authority_unavailable",
    }
)
_SUPERSEDED_RESULTS = frozenset(
    {"stale_generation", "late_result", "head_changed", "owner_replaced"}
)


def classify_implementation_result(
    result: ImplementationExecutionResult,
) -> ClassifiedImplementationResult:
    status = str(result.status or "").strip().lower()
    if status in _SUCCESS_RESULTS:
        return ClassifiedImplementationResult(
            ImplementationRoute.COMPLETED, False, WorkflowFailureCategory.UNKNOWN
        )
    if status in _ADVISORY_RESULTS:
        return ClassifiedImplementationResult(
            ImplementationRoute.ADVISORY, False, WorkflowFailureCategory.UNKNOWN
        )
    if status in _RETRY_RESULTS:
        category = (
            WorkflowFailureCategory.AUTHORIZATION
            if status == "token_changed"
            else WorkflowFailureCategory.TRANSPORT
            if status == "transport_error"
            else WorkflowFailureCategory.TRANSIENT
        )
        return ClassifiedImplementationResult(ImplementationRoute.RETRY, True, category)
    if status in _SUPERSEDED_RESULTS:
        return ClassifiedImplementationResult(
            ImplementationRoute.SUPERSEDED,
            True,
            WorkflowFailureCategory.STALE_EVIDENCE,
        )
    return ClassifiedImplementationResult(
        ImplementationRoute.ACTION_REQUIRED, False, WorkflowFailureCategory.POLICY
    )


@dataclass(frozen=True, slots=True)
class ImplementationTaskDecision:
    task: Issue
    facts: WorkflowFacts
    decision: WorkDecision


@dataclass(frozen=True, slots=True)
class ImplementationDecisionBatch:
    tasks: tuple[ImplementationTaskDecision, ...]

    @property
    def decisions(self) -> tuple[WorkDecision, ...]:
        return tuple(item.decision for item in self.tasks)


@dataclass(frozen=True, slots=True)
class ImplementationProjection:
    project_id: str
    task_id: str
    disposition: str
    reason_code: str
    owner: str
    evidence_revision: str
    action_required: bool
    alert_level: str
    durable_jobs: tuple[str, ...]
    active_job_state: str | None = None
    ownership: ImplementationDisposition | None = None

    @classmethod
    def from_decision(
        cls,
        decision: WorkDecision,
        job: WorkflowJob | None,
        ownership: ImplementationDisposition | None,
    ) -> "ImplementationProjection":
        return cls(
            decision.project_id,
            decision.task_id,
            decision.disposition.value,
            decision.reason_code,
            decision.responsible_owner.value,
            decision.evidence_revision,
            decision.action_required,
            decision.alert_level.value,
            decision.durable_jobs,
            job.state.value if job else None,
            ownership,
        )


class ImplementationWorkflowController:
    """Evaluate implementation work and materialize every durable action."""

    _STATUSES = frozenset(
        {OPEN, IN_PROGRESS, NEEDS_CI_FIX, NEEDS_REBASE, DUPLICATE_CANDIDATE}
    )

    def __init__(
        self,
        *,
        collector: WorkflowFactCollector,
        store: WorkflowJobStore,
        scheduler: WorkflowJobScheduler | None = None,
        decision_limit: int = DEFAULT_IMPLEMENTATION_DECISION_LIMIT,
    ) -> None:
        if decision_limit < 1 or decision_limit > DEFAULT_IMPLEMENTATION_DECISION_LIMIT:
            raise ValueError(
                "decision_limit must be between 1 and "
                f"{DEFAULT_IMPLEMENTATION_DECISION_LIMIT}"
            )
        self.collector = collector
        self.store = store
        self.scheduler = scheduler or WorkflowJobScheduler(
            store=store, decision_limit=decision_limit
        )
        self.decision_limit = decision_limit
        self._latest: dict[str, ImplementationTaskDecision] = {}

    def evaluate(self, tasks: Sequence[Issue]) -> ImplementationDecisionBatch:
        # Apply the bounded window to this domain's eligible population, not
        # to the complete project corpus.  Otherwise enough alphabetically
        # earlier terminal/review tasks can permanently hide an Open task from
        # every reconciliation pass.
        selected = list(
            sorted(
                {
                    task.identifier: task
                    for task in tasks
                    if task.state in self._STATUSES
                }.items()
            )
        )
        if len(selected) > self.decision_limit:
            offset = self.store.allocate_decision_window(
                total=len(selected),
                limit=self.decision_limit,
                scope=f"{self.collector.project_id}:implementation",
            )
            selected = (selected[offset:] + selected[:offset])[
                : self.decision_limit
            ]
        evaluated: list[ImplementationTaskDecision] = []
        for _, task in selected:
            facts = self.collector.collect(task.identifier)
            evaluated.append(
                ImplementationTaskDecision(task, facts, evaluate_task(task, facts))
            )
        self._latest = {item.task.identifier: item for item in evaluated}
        return ImplementationDecisionBatch(tuple(evaluated))

    def reconcile(
        self,
        tasks: Sequence[Issue],
        *,
        snapshot_generation: int | None = None,
    ) -> tuple[ImplementationDecisionBatch, WorkflowReconcileResult]:
        generation = (
            self.store.allocate_snapshot_generation()
            if snapshot_generation is None
            else int(snapshot_generation)
        )
        if generation < 1:
            raise ValueError("snapshot_generation must be a positive integer")
        batch = self.evaluate(tasks)
        applied = stale = created = replayed = superseded = 0
        for item in batch.tasks:
            config = item.facts.fact(FactDomain.CONFIG)
            config_value = (
                config.value
                if config.state is FactState.KNOWN
                and isinstance(config.value, Mapping)
                else {}
            )
            configured_payload = config_value.get("implementation_pending_payload")
            payload = (
                _canonical_payload(configured_payload)
                if isinstance(configured_payload, Mapping)
                else {}
            )
            payload.setdefault("expected_status", item.task.state)
            if item.task.work_branch and "work_branch" not in payload:
                payload["work_branch"] = item.task.work_branch
            if item.task.head_sha and "head_sha" not in payload:
                payload["head_sha"] = item.task.head_sha
            actions = tuple(
                action
                for action in item.decision.durable_jobs
                if action in IMPLEMENTATION_ACTIONS
            )
            if len(actions) > 1:
                raise RuntimeError(
                    "an implementation decision produced multiple dispositions"
                )
            if not actions:
                write = self.store.retire_event_lane(
                    project_id=item.decision.project_id,
                    task_id=item.decision.task_id,
                    scheduling_lane=FACT_IMPLEMENTATION_LANE,
                    ordering_namespace=IMPLEMENTATION_ORDERING_NAMESPACE,
                    source_generation=generation,
                    decision_revision=item.decision.decision_revision,
                    reason="retired by a newer implementation decision",
                )
            else:
                action = actions[0]
                if action == ImplementationAction.RECOVERY.value:
                    retry_payload = self._latest_retry_payload(
                        project_id=item.decision.project_id,
                        task_id=item.decision.task_id,
                    )
                    for key in (
                        "attempt",
                        "profile",
                        "workspace_path",
                        "incomplete_sessions",
                        "focus",
                    ):
                        if key in retry_payload:
                            payload.setdefault(key, retry_payload[key])
                expected_head = _optional_text(
                    payload.get("head_sha") or item.task.head_sha
                )
                event_revision = _event_revision(
                    project_id=item.decision.project_id,
                    task_id=item.decision.task_id,
                    action=action,
                    payload=payload,
                    expected_evidence_revision=issue_authority_version(item.task),
                    expected_head_sha=expected_head,
                )
                write = self.store.materialize_event(
                    project_id=item.decision.project_id,
                    task_id=item.decision.task_id,
                    decision_revision=event_revision,
                    action=action,
                    idempotency_namespace="implementation",
                    scheduling_lane=FACT_IMPLEMENTATION_LANE,
                    ordering_namespace=IMPLEMENTATION_ORDERING_NAMESPACE,
                    source_generation=generation,
                    source_revision=item.decision.decision_revision,
                    protected_scheduling_lanes=(IMPERATIVE_IMPLEMENTATION_LANE,),
                    payload=payload,
                    expected_evidence_revision=issue_authority_version(item.task),
                    expected_head_sha=expected_head,
                    reason="superseded by a newer implementation decision",
                )
            if not write.accepted:
                stale += 1
                continue
            applied += 1
            if write.job is not None:
                created += int(write.created)
                replayed += int(not write.created)
            superseded += write.superseded
        scheduled = WorkflowReconcileResult(
            snapshot_generation=generation,
            decisions_seen=len(batch.tasks),
            decisions_applied=applied,
            stale_rejected=stale,
            jobs_created=created,
            jobs_replayed=replayed,
            jobs_superseded=superseded,
            truncated=False,
        )
        return batch, scheduled

    def _latest_retry_payload(
        self,
        *,
        project_id: str,
        task_id: str,
    ) -> dict[str, Any]:
        """Carry one verified retry's exact launch context into recovery."""

        for job in self.store.list_jobs(
            project_id=project_id,
            task_id=task_id,
            states=("completed", "running", "retry_wait", "exhausted"),
            limit=self.decision_limit,
            newest_first=True,
        ):
            checkpoint = job.checkpoint or {}
            verification = checkpoint.get("verification")
            raw_disposition = (
                verification.get("disposition")
                if isinstance(verification, Mapping)
                else None
            )
            if not isinstance(raw_disposition, Mapping):
                continue
            try:
                disposition = ImplementationDisposition.from_dict(raw_disposition)
            except (TypeError, ValueError):
                continue
            if disposition.matches(job, allow_incomplete=True):
                return (
                    _canonical_payload(job.payload)
                    if job.action == ImplementationAction.RETRY.value
                    else {}
                )
        return {}

    def schedule_event(
        self,
        *,
        project_id: str,
        task_id: str,
        action: ImplementationAction | str,
        payload: Mapping[str, Any] | None = None,
        expected_evidence_revision: str | None = None,
        expected_head_sha: str | None = None,
        priority: int = 100,
        max_attempts: int = 5,
    ) -> WorkflowJob:
        """Atomically replace a task's pending action with one semantic event."""

        normalized_action = ImplementationAction(action)
        normalized_payload = _canonical_payload(payload)
        project = _required_text(project_id, "project_id")
        task = _required_text(task_id, "task_id")
        head = _optional_text(expected_head_sha or normalized_payload.get("head_sha"))
        revision = _event_revision(
            project_id=project,
            task_id=task,
            action=normalized_action.value,
            payload=normalized_payload,
            expected_evidence_revision=expected_evidence_revision,
            expected_head_sha=head,
        )
        source_generation = self.store.allocate_snapshot_generation()
        write = self.store.materialize_event(
            project_id=project,
            task_id=task,
            decision_revision=revision,
            action=normalized_action.value,
            idempotency_namespace="implementation",
            scheduling_lane=IMPERATIVE_IMPLEMENTATION_LANE,
            ordering_namespace=IMPLEMENTATION_ORDERING_NAMESPACE,
            source_generation=source_generation,
            source_revision=revision,
            supersede_scheduling_lanes=(FACT_IMPLEMENTATION_LANE,),
            payload=normalized_payload,
            expected_evidence_revision=_optional_text(expected_evidence_revision),
            expected_head_sha=head,
            priority=priority,
            max_attempts=max_attempts,
            reason="superseded by a newer implementation event",
        )
        if write.job is None:
            raise RuntimeError("imperative implementation event was not accepted")
        return write.job

    def latest_disposition(
        self, task_id: str, *, project_id: str | None = None
    ) -> ImplementationDisposition | None:
        jobs = self.store.list_jobs(
            project_id=project_id,
            task_id=task_id,
            states=("completed", "running", "retry_wait", "exhausted"),
            limit=self.decision_limit,
            newest_first=True,
        )
        for job in jobs:
            checkpoint = job.checkpoint or {}
            verification = checkpoint.get("verification")
            if not isinstance(verification, Mapping):
                continue
            raw = verification.get("disposition")
            if not isinstance(raw, Mapping):
                continue
            try:
                disposition = ImplementationDisposition.from_dict(raw)
            except (TypeError, ValueError):
                continue
            if disposition.matches(job, allow_incomplete=True):
                return disposition
        return None

    def implementation_authority(self, task: Issue) -> dict[str, Any]:
        """Expose accepted jobs as the shared agent/direct-owner fact source."""

        project_id = str(task.project_id or "")
        disposition = self.latest_disposition(
            task.identifier, project_id=project_id or None
        )
        if disposition is None:
            return {"lease_expires_at": None}
        job_state = next(
            (
                job.state.value
                for job in self.store.list_jobs(
                    project_id=project_id or None,
                    task_id=task.identifier,
                    states=("completed", "running", "retry_wait", "exhausted"),
                    limit=self.decision_limit,
                    newest_first=True,
                )
                if job.generation == disposition.generation
                and job.action == disposition.action.value
            ),
            None,
        )
        active_state = disposition.state in {
            ImplementationState.CLAIMED,
            ImplementationState.ACTIVE,
            ImplementationState.HANDED_OFF,
        }
        return {
            "owner_id": disposition.owner_id,
            "generation": disposition.generation,
            "ownership_source": disposition.ownership_source.value,
            "lease_expires_at": (
                disposition.lease_expires_at if active_state else None
            ),
            "assignment_id": disposition.assignment_id,
            "run_id": disposition.run_id,
            "focus": disposition.focus,
            "work_branch": disposition.work_branch,
            "head_sha": disposition.head_sha,
            "state": disposition.state.value,
            "transition_pending": job_state in {
                "running",
                "retry_wait",
                "exhausted",
            },
            "authority_revision": disposition.authority_revision,
        }

    def projections(self) -> tuple[ImplementationProjection, ...]:
        jobs = self.store.list_jobs(
            states=tuple(ACTIVE_JOB_STATES), limit=self.decision_limit
        )
        active: dict[str, WorkflowJob] = {}
        for job in jobs:
            if job.is_active:
                active[job.task_id] = job
        return tuple(
            ImplementationProjection.from_decision(
                item.decision,
                active.get(task_id),
                self.latest_disposition(
                    task_id, project_id=item.decision.project_id
                ),
            )
            for task_id, item in sorted(self._latest.items())
        )


class ImplementationWorkflowBackend(Protocol):
    def revalidate(
        self, context: WorkflowJobContext
    ) -> RevalidationResult | Awaitable[RevalidationResult]: ...

    def observe_disposition(
        self, context: WorkflowJobContext
    ) -> ImplementationDisposition | None | Awaitable[ImplementationDisposition | None]: ...

    def execute(
        self, context: WorkflowJobContext
    ) -> ImplementationExecutionResult | Awaitable[ImplementationExecutionResult]: ...

    def build_transition(
        self,
        context: WorkflowJobContext,
        verification: VerificationResult,
    ) -> TransitionIntent | None | Awaitable[TransitionIntent | None]: ...


async def _resolve(value: Any) -> Any:
    return await value if inspect.isawaitable(value) else value


class ImplementationWorkflowHandler:
    """Idempotent implementation action handler with no process-local authority."""

    domain = WorkflowActionDomain.TRACKER

    def __init__(self, backend: ImplementationWorkflowBackend) -> None:
        self.backend = backend

    async def revalidate(self, context: WorkflowJobContext) -> RevalidationResult:
        result = await _resolve(self.backend.revalidate(context))
        if not isinstance(result, RevalidationResult):
            raise WorkflowActionError(
                "implementation backend returned invalid revalidation",
                category=WorkflowFailureCategory.PERMANENT,
                retryable=False,
            )
        return result

    async def inspect(self, context: WorkflowJobContext) -> EffectObservation:
        disposition = await _resolve(self.backend.observe_disposition(context))
        applied = (
            isinstance(disposition, ImplementationDisposition)
            and disposition.matches(context.job, allow_incomplete=True)
        )
        return EffectObservation(
            applied,
            {
                "status": (
                    "incomplete"
                    if disposition
                    and disposition.state is ImplementationState.INCOMPLETE
                    else "observed"
                ),
                "disposition": disposition.to_dict(),
            }
            if applied and disposition
            else {},
        )

    async def apply(self, context: WorkflowJobContext) -> EffectResult:
        result = await _resolve(self.backend.execute(context))
        if not isinstance(result, ImplementationExecutionResult):
            raise WorkflowActionError(
                "implementation backend returned invalid execution result",
                category=WorkflowFailureCategory.PERMANENT,
                retryable=False,
            )
        classified = classify_implementation_result(result)
        if (
            str(result.status or "").strip().lower() == "incomplete"
            and result.disposition is not None
            and result.disposition.incomplete_sessions > 0
            and result.disposition.matches(context.job, allow_incomplete=True)
        ):
            return EffectResult(
                {
                    "status": "incomplete",
                    "message": result.message,
                    "disposition": result.disposition.to_dict(),
                }
            )
        if classified.route is ImplementationRoute.SUPERSEDED:
            raise WorkflowActionSuperseded(
                result.message,
                replacement_generation=f"reassess:{context.job.generation}",
            )
        if classified.route is ImplementationRoute.RETRY:
            raise WorkflowActionError(
                result.message,
                category=classified.category,
                retryable=True,
                retry_delay_seconds=result.retry_delay_seconds,
            )
        if classified.route is ImplementationRoute.ACTION_REQUIRED:
            raise WorkflowActionError(
                result.message,
                category=classified.category,
                retryable=False,
            )
        if classified.route is ImplementationRoute.ADVISORY:
            return EffectResult(
                {
                    "status": str(result.status),
                    "message": result.message,
                    "advisory_denied": True,
                }
            )
        disposition = result.disposition
        if disposition is None or not disposition.matches(context.job):
            raise WorkflowActionError(
                "implementation result did not prove the exact job disposition",
                category=WorkflowFailureCategory.STALE_EVIDENCE,
                retryable=True,
            )
        return EffectResult(
            {
                "status": str(result.status),
                "message": result.message,
                "disposition": disposition.to_dict(),
            }
        )

    async def verify(
        self, context: WorkflowJobContext, effect: EffectResult
    ) -> VerificationResult:
        if bool(effect.receipt.get("advisory_denied")):
            return VerificationResult(True, dict(effect.receipt))
        disposition = await _resolve(self.backend.observe_disposition(context))
        allow_incomplete = str(effect.receipt.get("status") or "") == "incomplete"
        if isinstance(disposition, ImplementationDisposition) and disposition.matches(
            context.job, allow_incomplete=allow_incomplete
        ):
            return VerificationResult(
                True,
                {**dict(effect.receipt), "disposition": disposition.to_dict()},
            )
        return VerificationResult(
            False,
            dict(effect.receipt),
            "exact implementation disposition is not durably observable",
        )

    async def build_transition(
        self,
        context: WorkflowJobContext,
        verification: VerificationResult,
    ) -> TransitionIntent | None:
        if bool(verification.receipt.get("advisory_denied")):
            return None
        raw = verification.receipt.get("disposition")
        if isinstance(raw, Mapping):
            disposition = ImplementationDisposition.from_dict(raw)
            if disposition.state is ImplementationState.INCOMPLETE:
                return None
            if disposition.state is ImplementationState.RETRY_WAIT:
                retry_epoch = _timestamp_epoch(disposition.retry_at, "retry_at")
                delay = max(0.0, retry_epoch - context.job.updated_at)
                if delay > 0:
                    raise WorkflowActionError(
                        "implementation retry timer armed",
                        category=WorkflowFailureCategory.TRANSIENT,
                        retryable=True,
                        retry_delay_seconds=delay,
                    )
        return await _resolve(self.backend.build_transition(context, verification))
