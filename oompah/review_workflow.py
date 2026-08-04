"""Durable review/CI observation and repair workflow.

Review reconciliation used to be a collection of maintenance sweeps over an
in-memory provider cache.  This adapter gives that lane the same boundary as
integration: immutable facts are evaluated once, one current action is
materialized in the durable job ledger, and any status change is returned as
a :class:`~oompah.task_transition_service.TransitionIntent` for the worker's
transition service.

The module deliberately knows nothing about GitHub or GitLab API response
shapes.  Providers normalize into :class:`ReviewObservation`; both forges can
therefore exercise the same decisions and UI projection.
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol

from oompah.models import Issue
from oompah.statuses import IN_REVIEW
from oompah.task_transition_service import TransitionIntent
from oompah.work_decision import REVIEW_ACTION_JOBS, WorkDecision, evaluate_task
from oompah.workflow_facts import (
    LandingFact,
    LandingRequest,
    LandingState,
    WorkflowFactCollector,
    WorkflowFacts,
)
from oompah.workflow_jobs import (
    WorkflowFailureCategory,
    WorkflowJob,
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
    WorkflowJobContext,
)


DEFAULT_REVIEW_DECISION_LIMIT = 1000


def _text(value: object | None) -> str:
    return str(value or "").strip()


class ReviewObservationUnavailable(RuntimeError):
    """Provider could not answer; this is not an empty review result."""


@dataclass(frozen=True, slots=True)
class ReviewObservation:
    """Forge-neutral review state captured at one provider observation."""

    state: str = "missing"
    review_id: str | None = None
    source_branch: str | None = None
    target_branch: str | None = None
    head_sha: str | None = None
    ci: str = "unknown"
    mergeable: bool | None = None
    mergeable_state: str = ""
    conflict: bool = False
    draft: bool = False
    provider: str | None = None
    source_deleted: bool = False
    capacity: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        state = _text(self.state).lower() or "missing"
        if state == "closed":
            state = "closed_unmerged"
        if state not in {
            "open",
            "closed",
            "closed_unmerged",
            "merged",
            "missing",
        }:
            raise ValueError(f"unknown review state: {state!r}")
        object.__setattr__(self, "state", state)
        for name in (
            "review_id",
            "source_branch",
            "target_branch",
            "head_sha",
            "provider",
        ):
            value = _text(getattr(self, name)) or None
            object.__setattr__(self, name, value)
        ci = _text(self.ci).lower() or "unknown"
        if ci == "failure":
            ci = "failed"
        object.__setattr__(self, "ci", ci)
        object.__setattr__(self, "mergeable_state", _text(self.mergeable_state).lower())
        if self.capacity is not None and not isinstance(self.capacity, Mapping):
            raise TypeError("review capacity must be a mapping")

    @classmethod
    def from_review(
        cls,
        review: Any,
        *,
        provider: str | None = None,
        capacity: Mapping[str, Any] | None = None,
    ) -> "ReviewObservation":
        """Normalize a GitHub/GitLab ``ReviewRequest``-like object."""

        state = _text(getattr(review, "state", "open")).lower() or "open"
        merged = bool(getattr(review, "merged", False))
        if merged:
            state = "merged"
        elif state == "closed":
            state = "closed_unmerged"
        mergeable = getattr(review, "mergeable", None)
        if mergeable is None and hasattr(review, "has_conflicts"):
            mergeable = not bool(getattr(review, "has_conflicts", False))
        ci = getattr(review, "ci_status", "unknown")
        ci = getattr(ci, "value", ci)
        return cls(
            state=state,
            review_id=_text(getattr(review, "id", None)) or None,
            source_branch=_text(getattr(review, "source_branch", None)) or None,
            target_branch=_text(getattr(review, "target_branch", None)) or None,
            head_sha=_text(getattr(review, "head_sha", None)) or None,
            ci=_text(ci) or "unknown",
            mergeable=mergeable,
            mergeable_state=_text(getattr(review, "mergeable_state", None)),
            conflict=bool(getattr(review, "has_conflicts", False)),
            draft=bool(getattr(review, "draft", False)),
            provider=provider,
            capacity=capacity,
        )

    @classmethod
    def missing(
        cls,
        *,
        source_branch: str | None = None,
        source_deleted: bool = False,
        provider: str | None = None,
    ) -> "ReviewObservation":
        return cls(
            state="missing",
            source_branch=source_branch,
            source_deleted=source_deleted,
            provider=provider,
        )

    def to_fact_value(self) -> dict[str, Any]:
        """Return the stable mapping used by ``FactDomain.REVIEW_CI``."""

        return {
            "state": self.state,
            "present": self.state != "missing",
            "review_id": self.review_id,
            "source_branch": self.source_branch,
            "target_branch": self.target_branch,
            "head_sha": self.head_sha,
            "ci": self.ci,
            "mergeable": self.mergeable,
            "mergeable_state": self.mergeable_state,
            "conflict": self.conflict,
            "draft": self.draft,
            "provider": self.provider,
            "source_deleted": self.source_deleted,
            "capacity": dict(self.capacity or {}),
        }


def review_fact_source(
    provider: Any,
    repo: str,
    *,
    provider_name: str | None = None,
    review_id: str | None = None,
    source_branch: str | None = None,
    capacity: Mapping[str, Any] | None = None,
):
    """Build a collector source that preserves timeout vs empty semantics.

    ``SCMProvider.list_open_reviews`` historically returns ``[]`` for an API
    failure.  Its ``last_open_reviews_fetch_ok`` marker is the compatibility
    signal that lets this adapter emit an explicit error instead of treating a
    timeout as proof that a review disappeared.
    """

    def collect(_issue: Issue) -> Mapping[str, Any]:
        try:
            reviews = provider.list_open_reviews(repo)
        except Exception as exc:  # noqa: BLE001 - collector turns this into a fact error
            raise ReviewObservationUnavailable("review provider unavailable") from exc
        if getattr(provider, "last_open_reviews_fetch_ok", True) is False:
            raise ReviewObservationUnavailable("review provider unavailable")
        if reviews is None:
            raise ReviewObservationUnavailable("review provider returned no result")
        selected = None
        for review in reviews:
            if review_id and _text(getattr(review, "id", None)) == _text(review_id):
                selected = review
                break
            if source_branch and _text(getattr(review, "source_branch", None)) == _text(
                source_branch
            ):
                selected = review
                break
        # The open-list endpoint is intentionally the fast path, but a task
        # can remain In Review after its PR/MR closed or merged.  When durable
        # review metadata identifies that artifact, ask the provider for the
        # historical object before classifying the list as an empty result.
        if selected is None and review_id and hasattr(provider, "get_review"):
            try:
                selected = provider.get_review(repo, _text(review_id))
            except Exception as exc:  # noqa: BLE001 - preserve unavailable state
                raise ReviewObservationUnavailable("review provider unavailable") from exc
        if selected is None:
            return ReviewObservation.missing(
                source_branch=source_branch,
                provider=provider_name,
            ).to_fact_value()
        return ReviewObservation.from_review(
            selected,
            provider=provider_name,
            capacity=capacity,
        ).to_fact_value()

    return collect


class ReviewRoute(str, Enum):
    OBSERVED = "observed"
    CI_REPAIR = "ci_repair"
    CONFLICT_REPAIR = "conflict_repair"
    CLOSED_REPAIR = "closed_repair"
    HEAD_REPAIR = "head_repair"
    LANDED = "landed"
    RETRY = "retry"
    ACTION_REQUIRED = "action_required"


@dataclass(frozen=True, slots=True)
class ReviewExecutionResult:
    status: str
    message: str = ""
    observation: ReviewObservation | None = None
    landing: LandingFact | None = None


@dataclass(frozen=True, slots=True)
class ClassifiedReviewResult:
    route: ReviewRoute
    retryable: bool
    category: WorkflowFailureCategory


def classify_review_result(result: ReviewExecutionResult) -> ClassifiedReviewResult:
    """Map provider/action outcomes to one bounded worker route."""

    status = _text(result.status).lower()
    if status in {
        "observed",
        "monitoring",
        "open",
        "pending",
        "passed",
        "repaired",
    }:
        return ClassifiedReviewResult(
            ReviewRoute.OBSERVED, False, WorkflowFailureCategory.UNKNOWN
        )
    if status in {"ci_failure", "failed", "needs_ci_fix"}:
        return ClassifiedReviewResult(
            ReviewRoute.CI_REPAIR, False, WorkflowFailureCategory.PERMANENT
        )
    if status in {"conflict", "needs_rebase", "behind"}:
        return ClassifiedReviewResult(
            ReviewRoute.CONFLICT_REPAIR, False, WorkflowFailureCategory.STALE_EVIDENCE
        )
    if status in {"closed", "closed_unmerged"}:
        return ClassifiedReviewResult(
            ReviewRoute.CLOSED_REPAIR, False, WorkflowFailureCategory.PERMANENT
        )
    if status in {"head_changed", "stale_head"}:
        return ClassifiedReviewResult(
            ReviewRoute.HEAD_REPAIR, False, WorkflowFailureCategory.STALE_EVIDENCE
        )
    if status in {"merged", "landed", "terminal"}:
        if result.landing is not None and result.landing.state is LandingState.LANDED:
            return ClassifiedReviewResult(
                ReviewRoute.LANDED, False, WorkflowFailureCategory.UNKNOWN
            )
        return ClassifiedReviewResult(
            ReviewRoute.RETRY, True, WorkflowFailureCategory.TRANSIENT
        )
    if status in {
        "timeout",
        "provider_unavailable",
        "transport_error",
        "registration_pending",
        "landing_unknown",
    }:
        return ClassifiedReviewResult(
            ReviewRoute.RETRY, True, WorkflowFailureCategory.TRANSIENT
        )
    return ClassifiedReviewResult(
        ReviewRoute.ACTION_REQUIRED, False, WorkflowFailureCategory.POLICY
    )


@dataclass(frozen=True, slots=True)
class ReviewTaskDecision:
    task: Issue
    facts: WorkflowFacts
    decision: WorkDecision


@dataclass(frozen=True, slots=True)
class ReviewDecisionBatch:
    tasks: tuple[ReviewTaskDecision, ...]

    @property
    def decisions(self) -> tuple[WorkDecision, ...]:
        return tuple(item.decision for item in self.tasks)


@dataclass(frozen=True, slots=True)
class ReviewProjection:
    """UI/API projection made from exactly the same decision as scheduling."""

    project_id: str
    task_id: str
    disposition: str
    reason_code: str
    owner: str
    waiting_on: tuple[str, ...]
    evidence_revision: str
    next_reassessment_at: str | None
    action_required: bool
    alert_level: str
    durable_jobs: tuple[str, ...]
    active_job_state: str | None = None

    @classmethod
    def from_decision(
        cls, decision: WorkDecision, job: WorkflowJob | None = None
    ) -> "ReviewProjection":
        return cls(
            project_id=decision.project_id,
            task_id=decision.task_id,
            disposition=decision.disposition.value,
            reason_code=decision.reason_code,
            owner=decision.responsible_owner.value,
            waiting_on=tuple(item.subject for item in decision.unmet_prerequisites),
            evidence_revision=decision.evidence_revision,
            next_reassessment_at=decision.next_reassessment_at,
            action_required=decision.action_required,
            alert_level=decision.alert_level.value,
            durable_jobs=decision.durable_jobs,
            active_job_state=job.state.value if job else None,
        )


class ReviewWorkflowController:
    """Evaluate every In Review task and persist its current action."""

    def __init__(
        self,
        *,
        collector: WorkflowFactCollector,
        store: WorkflowJobStore,
        scheduler: WorkflowJobScheduler | None = None,
        decision_limit: int = DEFAULT_REVIEW_DECISION_LIMIT,
    ) -> None:
        if decision_limit < 1 or decision_limit > DEFAULT_REVIEW_DECISION_LIMIT:
            raise ValueError(
                f"decision_limit must be between 1 and {DEFAULT_REVIEW_DECISION_LIMIT}"
            )
        self.collector = collector
        self.store = store
        self.scheduler = scheduler or WorkflowJobScheduler(
            store=store, decision_limit=decision_limit
        )
        self.decision_limit = decision_limit
        self._latest: dict[str, ReviewTaskDecision] = {}

    @staticmethod
    def _landing_request(task: Issue) -> tuple[LandingRequest, ...]:
        source = _text(task.work_branch or task.branch_name or task.identifier)
        target = _text(task.target_branch)
        revision = _text(task.review_head or task.head_sha)
        if not source or not target:
            return ()
        try:
            return (LandingRequest(source, target, revision or None),)
        except ValueError:
            # A malformed metadata value is evidence for the fact collector,
            # not a reason to crash the complete project reconciliation pass.
            return ()

    def evaluate(self, tasks: Sequence[Issue]) -> ReviewDecisionBatch:
        selected = dict(sorted({task.identifier: task for task in tasks}.items()))
        evaluated: list[ReviewTaskDecision] = []
        for task in tuple(selected.values())[: self.decision_limit]:
            if task.state != IN_REVIEW:
                continue
            facts = self.collector.collect(
                task.identifier,
                landing_requests=self._landing_request(task),
            )
            evaluated.append(ReviewTaskDecision(task, facts, evaluate_task(task, facts)))
        self._latest = {item.task.identifier: item for item in evaluated}
        return ReviewDecisionBatch(tuple(evaluated))

    def reconcile(
        self,
        tasks: Sequence[Issue],
        *,
        snapshot_generation: int | None = None,
    ) -> tuple[ReviewDecisionBatch, WorkflowReconcileResult]:
        batch = self.evaluate(tasks)
        for decision in batch.decisions:
            unknown = set(decision.durable_jobs) - REVIEW_ACTION_JOBS
            if unknown:
                raise ValueError(
                    "review decision produced non-review durable jobs: "
                    + ", ".join(sorted(unknown))
                )
        scheduled = self.scheduler.reconcile(
            batch.decisions,
            snapshot_generation=snapshot_generation,
        )
        return batch, scheduled

    def projections(self) -> tuple[ReviewProjection, ...]:
        jobs = self.store.list_jobs(limit=self.decision_limit)
        active: dict[str, WorkflowJob] = {}
        for job in jobs:
            if job.is_active:
                previous = active.get(job.task_id)
                if previous is None or job.enqueue_sequence > previous.enqueue_sequence:
                    active[job.task_id] = job
        return tuple(
            ReviewProjection.from_decision(item.decision, active.get(task_id))
            for task_id, item in sorted(self._latest.items())
        )


class ReviewWorkflowBackend(Protocol):
    def revalidate(
        self, context: WorkflowJobContext
    ) -> RevalidationResult | Awaitable[RevalidationResult]: ...

    def observe(
        self, context: WorkflowJobContext
    ) -> ReviewExecutionResult | Awaitable[ReviewExecutionResult]: ...

    def repair(
        self, context: WorkflowJobContext
    ) -> ReviewExecutionResult | Awaitable[ReviewExecutionResult]: ...

    def build_transition(
        self,
        context: WorkflowJobContext,
        verification: VerificationResult,
    ) -> TransitionIntent | None | Awaitable[TransitionIntent | None]: ...


async def _resolve(value: Any) -> Any:
    return await value if inspect.isawaitable(value) else value


class ReviewWorkflowHandler:
    """Resumable review observation/repair action handler."""

    domain = WorkflowActionDomain.FORGE

    def __init__(self, backend: ReviewWorkflowBackend) -> None:
        self.backend = backend

    async def revalidate(self, context: WorkflowJobContext) -> RevalidationResult:
        result = await _resolve(self.backend.revalidate(context))
        if not isinstance(result, RevalidationResult):
            raise WorkflowActionError(
                "review backend returned invalid revalidation",
                category=WorkflowFailureCategory.PERMANENT,
                retryable=False,
            )
        return result

    async def inspect(self, context: WorkflowJobContext) -> EffectObservation:
        result = await _resolve(self.backend.observe(context))
        if not isinstance(result, ReviewExecutionResult):
            raise WorkflowActionError(
                "review backend returned invalid observation",
                category=WorkflowFailureCategory.PERMANENT,
                retryable=False,
            )
        classified = classify_review_result(result)
        if classified.route is ReviewRoute.RETRY:
            raise WorkflowActionError(
                result.message or "review observation is temporarily unavailable",
                category=classified.category,
                retryable=True,
            )
        return EffectObservation(
            applied=classified.route in {ReviewRoute.OBSERVED, ReviewRoute.LANDED},
            receipt={
                "status": result.status,
                "message": result.message,
                "route": classified.route.value,
                "landing": result.landing.to_dict() if result.landing else None,
            },
        )

    async def apply(self, context: WorkflowJobContext) -> EffectResult:
        result = await _resolve(self.backend.repair(context))
        if not isinstance(result, ReviewExecutionResult):
            raise WorkflowActionError(
                "review backend returned invalid repair result",
                category=WorkflowFailureCategory.PERMANENT,
                retryable=False,
            )
        classified = classify_review_result(result)
        if classified.route is ReviewRoute.RETRY:
            raise WorkflowActionError(
                result.message or "review action is temporarily unavailable",
                category=classified.category,
                retryable=True,
            )
        if classified.route is ReviewRoute.ACTION_REQUIRED:
            raise WorkflowActionError(
                result.message or "review action requires operator attention",
                category=classified.category,
                retryable=False,
            )
        return EffectResult(
            {
                "status": result.status,
                "message": result.message,
                "route": classified.route.value,
                "landing": result.landing.to_dict() if result.landing else None,
            }
        )

    async def verify(
        self,
        context: WorkflowJobContext,
        effect: EffectResult,
    ) -> VerificationResult:
        route = _text(effect.receipt.get("route"))
        if route == ReviewRoute.LANDED.value:
            raw = effect.receipt.get("landing")
            if not isinstance(raw, Mapping):
                return VerificationResult(False, dict(effect.receipt), "landing proof missing")
            landing = LandingFact.from_dict(raw)
            if landing.state is not LandingState.LANDED:
                return VerificationResult(False, dict(effect.receipt), "landing is not positive")
        return VerificationResult(True, dict(effect.receipt))

    async def build_transition(
        self,
        context: WorkflowJobContext,
        verification: VerificationResult,
    ) -> TransitionIntent | None:
        return await _resolve(self.backend.build_transition(context, verification))


__all__ = [
    "ClassifiedReviewResult",
    "DEFAULT_REVIEW_DECISION_LIMIT",
    "ReviewDecisionBatch",
    "ReviewExecutionResult",
    "ReviewObservation",
    "ReviewObservationUnavailable",
    "ReviewProjection",
    "ReviewRoute",
    "ReviewTaskDecision",
    "ReviewWorkflowBackend",
    "ReviewWorkflowController",
    "ReviewWorkflowHandler",
    "classify_review_result",
    "review_fact_source",
]
