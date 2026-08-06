"""Durable integration decisions, execution, and UI projection.

This module is the integration-domain adapter for the shared workflow engine.
It collects immutable facts for every Ready task, evaluates each task exactly
once, schedules durable jobs from those decisions, and exposes the same
decision as the queue/UI projection.  The action handler wraps the existing
Git executor behind revalidation, exact-head landing proof, bounded failure
classification, and transition-intent construction.
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol

from oompah.integration_executor import (
    IntegrationExecutionResult,
)
from oompah.models import Issue
from oompah.task_transition_service import TransitionIntent
from oompah.work_decision import WorkDecision, evaluate_task
from oompah.workflow_contract import READY_TO_INTEGRATE
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

DEFAULT_INTEGRATION_DECISION_LIMIT = 1000
INTEGRATION_ACTIONS = frozenset(
    {
        "epic_branch_reconciliation",
        "historical_audit_replay_batch",
        "integration_attempt",
        "integration_landing_refresh",
        "integration_recovery",
        "integration_terminal_stage",
        "standalone_delivery",
    }
)


class IntegrationRoute(str, Enum):
    LANDED = "landed"
    REBASE = "rebase"
    CI_FIX = "ci_fix"
    RETRY = "retry"
    SUPERSEDED = "superseded"
    ACTION_REQUIRED = "action_required"


@dataclass(frozen=True, slots=True)
class ClassifiedIntegrationResult:
    route: IntegrationRoute
    retryable: bool
    category: WorkflowFailureCategory


_REBASE_RESULTS = frozenset({"conflict", "needs_rebase"})
_CI_FIX_RESULTS = frozenset({"ci_failure"})
_SUPERSEDED_RESULTS = frozenset(
    {"stale_head", "epic_head_race", "task_push_race", "cancelled"}
)
_RETRYABLE_RESULTS = frozenset(
    {
        "error",
        "interrupted",
        "authority_unavailable",
        "authentication_failed",
        "credential_missing",
        "missing_head",
        "missing_epic",
        "worktree_recovery",
    }
)
_ACTION_REQUIRED_RESULTS = frozenset(
    {"generated_helper", "wrong_worktree", "dirty_worktree"}
)


def classify_integration_result(
    result: IntegrationExecutionResult,
) -> ClassifiedIntegrationResult:
    """Give every executor outcome one bounded workflow disposition."""

    status = str(result.status or "").strip().lower()
    if status == "integrated":
        return ClassifiedIntegrationResult(
            IntegrationRoute.LANDED, False, WorkflowFailureCategory.UNKNOWN
        )
    if status in _REBASE_RESULTS:
        return ClassifiedIntegrationResult(
            IntegrationRoute.REBASE, False, WorkflowFailureCategory.STALE_EVIDENCE
        )
    if status in _CI_FIX_RESULTS:
        return ClassifiedIntegrationResult(
            IntegrationRoute.CI_FIX, False, WorkflowFailureCategory.PERMANENT
        )
    if status in _SUPERSEDED_RESULTS:
        return ClassifiedIntegrationResult(
            IntegrationRoute.SUPERSEDED,
            False,
            WorkflowFailureCategory.STALE_EVIDENCE,
        )
    if status in _RETRYABLE_RESULTS:
        category = (
            WorkflowFailureCategory.AUTHORIZATION
            if status in {"authentication_failed", "credential_missing"}
            else WorkflowFailureCategory.TRANSIENT
        )
        return ClassifiedIntegrationResult(IntegrationRoute.RETRY, True, category)
    return ClassifiedIntegrationResult(
        IntegrationRoute.ACTION_REQUIRED,
        False,
        WorkflowFailureCategory.POLICY,
    )


@dataclass(frozen=True, slots=True)
class IntegrationTaskDecision:
    task: Issue
    facts: WorkflowFacts
    decision: WorkDecision
    landing_requests: tuple[LandingRequest, ...] = ()


@dataclass(frozen=True, slots=True)
class IntegrationDecisionBatch:
    tasks: tuple[IntegrationTaskDecision, ...]
    topological_batches: tuple[tuple[str, ...], ...]
    cyclic_tasks: tuple[str, ...]

    @property
    def decisions(self) -> tuple[WorkDecision, ...]:
        return tuple(item.decision for item in self.tasks)


@dataclass(frozen=True, slots=True)
class IntegrationProjection:
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
    ) -> IntegrationProjection:
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


class IntegrationWorkflowController:
    """Evaluate and schedule all Ready tasks without first-row shortcuts."""

    def __init__(
        self,
        *,
        collector: WorkflowFactCollector,
        store: WorkflowJobStore,
        scheduler: WorkflowJobScheduler | None = None,
        decision_limit: int = DEFAULT_INTEGRATION_DECISION_LIMIT,
    ) -> None:
        if decision_limit < 1 or decision_limit > DEFAULT_INTEGRATION_DECISION_LIMIT:
            raise ValueError(
                f"decision_limit must be between 1 and {DEFAULT_INTEGRATION_DECISION_LIMIT}"
            )
        self.collector = collector
        self.store = store
        self.scheduler = scheduler or WorkflowJobScheduler(
            store=store, decision_limit=decision_limit
        )
        self.decision_limit = decision_limit
        self._latest: dict[str, IntegrationTaskDecision] = {}

    @staticmethod
    def _default_landing_request(task: Issue) -> tuple[LandingRequest, ...]:
        integration = task.integration
        if integration is None:
            return ()
        value = (
            integration.to_dict()
            if hasattr(integration, "to_dict")
            else dict(integration)
            if isinstance(integration, Mapping)
            else {}
        )
        if str(value.get("state") or "").strip().lower() != "integrated":
            return ()
        source = str(value.get("task_branch") or task.work_branch or "").strip()
        target = str(value.get("base_branch") or task.target_branch or "").strip()
        revision = str(
            value.get("integrated_sha") or value.get("head_sha") or ""
        ).strip()
        if not source or not target:
            return ()
        return (LandingRequest(source, target, revision or None),)

    @staticmethod
    def _topological_batches(
        tasks: Sequence[Issue],
    ) -> tuple[tuple[tuple[str, ...], ...], tuple[str, ...]]:
        identifiers = {task.identifier for task in tasks}
        dependencies = {
            task.identifier: {
                blocker.identifier
                for blocker in (*task.blocked_by, *task.start_blocked_by)
                if blocker.identifier in identifiers
            }
            for task in tasks
        }
        remaining = set(identifiers)
        completed: set[str] = set()
        batches: list[tuple[str, ...]] = []
        while remaining:
            ready = tuple(
                sorted(
                    task_id
                    for task_id in remaining
                    if dependencies[task_id] <= completed
                )
            )
            if not ready:
                break
            batches.append(ready)
            remaining.difference_update(ready)
            completed.update(ready)
        return tuple(batches), tuple(sorted(remaining))

    def evaluate(
        self,
        tasks: Sequence[Issue],
        *,
        landing_requests: Mapping[str, Sequence[LandingRequest]] | None = None,
    ) -> IntegrationDecisionBatch:
        # The window belongs to the Ready lane.  Limiting the complete task
        # corpus first lets stable terminal rows ahead of a Ready identifier
        # hide it from every pass.
        selected = sorted(
            {
                task.identifier: task
                for task in tasks
                if task.state == READY_TO_INTEGRATE
            }.items()
        )
        if len(selected) > self.decision_limit:
            offset = self.store.allocate_decision_window(
                total=len(selected),
                limit=self.decision_limit,
                scope=f"{self.collector.project_id}:integration",
            )
            selected = (selected[offset:] + selected[:offset])[
                : self.decision_limit
            ]
        ready = tuple(task for _, task in selected)
        batches, cycles = self._topological_batches(ready)
        requests = landing_requests or {}
        evaluated: list[IntegrationTaskDecision] = []
        for task in ready:
            task_requests = tuple(
                requests.get(
                    task.identifier,
                    self._default_landing_request(task),
                )
            )
            facts = self.collector.collect(
                task.identifier, landing_requests=task_requests
            )
            evaluated.append(
                IntegrationTaskDecision(
                    task,
                    facts,
                    evaluate_task(task, facts),
                    task_requests,
                )
            )
        self._latest = {item.task.identifier: item for item in evaluated}
        return IntegrationDecisionBatch(tuple(evaluated), batches, cycles)

    def reconcile(
        self,
        tasks: Sequence[Issue],
        *,
        landing_requests: Mapping[str, Sequence[LandingRequest]] | None = None,
        snapshot_generation: int | None = None,
    ) -> tuple[IntegrationDecisionBatch, WorkflowReconcileResult]:
        batch = self.evaluate(tasks, landing_requests=landing_requests)
        for decision in batch.decisions:
            unknown = set(decision.durable_jobs) - INTEGRATION_ACTIONS
            if unknown:
                raise ValueError(
                    "integration decision produced non-integration durable jobs: "
                    + ", ".join(sorted(unknown))
                )
        scheduled = self.scheduler.reconcile(
            batch.decisions, snapshot_generation=snapshot_generation
        )
        return batch, scheduled

    def projections(self) -> tuple[IntegrationProjection, ...]:
        jobs = self.store.list_jobs(limit=self.decision_limit)
        by_task: dict[str, WorkflowJob] = {}
        for job in jobs:
            if job.is_active:
                current = by_task.get(job.task_id)
                if current is None or job.enqueue_sequence > current.enqueue_sequence:
                    by_task[job.task_id] = job
        return tuple(
            IntegrationProjection.from_decision(item.decision, by_task.get(task_id))
            for task_id, item in sorted(self._latest.items())
        )


class IntegrationWorkflowBackend(Protocol):
    def revalidate(
        self, context: WorkflowJobContext
    ) -> RevalidationResult | Awaitable[RevalidationResult]: ...

    def observe_landing(
        self, context: WorkflowJobContext
    ) -> LandingFact | None | Awaitable[LandingFact | None]: ...

    def integrate(
        self, context: WorkflowJobContext
    ) -> IntegrationExecutionResult | Awaitable[IntegrationExecutionResult]: ...

    def build_transition(
        self,
        context: WorkflowJobContext,
        verification: VerificationResult,
    ) -> TransitionIntent | None | Awaitable[TransitionIntent | None]: ...


async def _resolve(value: Any) -> Any:
    return await value if inspect.isawaitable(value) else value


class IntegrationWorkflowHandler:
    """Idempotent Git action handler for ``DurableWorkflowWorker``."""

    domain = WorkflowActionDomain.GIT

    def __init__(self, backend: IntegrationWorkflowBackend) -> None:
        self.backend = backend
        self._results: dict[str, IntegrationExecutionResult] = {}

    async def revalidate(self, context: WorkflowJobContext) -> RevalidationResult:
        result = await _resolve(self.backend.revalidate(context))
        if not isinstance(result, RevalidationResult):
            raise WorkflowActionError(
                "integration backend returned invalid revalidation",
                category=WorkflowFailureCategory.PERMANENT,
                retryable=False,
            )
        return result

    async def inspect(self, context: WorkflowJobContext) -> EffectObservation:
        landing = await _resolve(self.backend.observe_landing(context))
        applied = self._landing_matches(context.job, landing)
        return EffectObservation(
            applied,
            {"landing": landing.to_dict()} if applied and landing else {},
        )

    @staticmethod
    def _landing_matches(job: WorkflowJob, landing: LandingFact | None) -> bool:
        if landing is None or landing.state is not LandingState.LANDED:
            return False
        return not job.expected_head_sha or landing.revision == job.expected_head_sha

    async def apply(self, context: WorkflowJobContext) -> EffectResult:
        result = await _resolve(self.backend.integrate(context))
        if not isinstance(result, IntegrationExecutionResult):
            raise WorkflowActionError(
                "integration backend returned invalid execution result",
                category=WorkflowFailureCategory.PERMANENT,
                retryable=False,
            )
        classified = classify_integration_result(result)
        if classified.route is IntegrationRoute.RETRY:
            raise WorkflowActionError(
                result.message,
                category=classified.category,
                retryable=True,
            )
        if classified.route is IntegrationRoute.ACTION_REQUIRED:
            raise WorkflowActionError(
                result.message,
                category=classified.category,
                retryable=False,
            )
        if classified.route is IntegrationRoute.SUPERSEDED:
            raise WorkflowActionError(
                f"integration evidence superseded: {result.message}",
                category=WorkflowFailureCategory.STALE_EVIDENCE,
                retryable=True,
            )
        self._results[context.job.job_id] = result
        return EffectResult(
            {
                "status": result.status,
                "message": result.message,
                "route": classified.route.value,
                "expected_epic_sha": result.expected_epic_sha,
                "rebased_task_sha": result.rebased_task_sha,
                "integrated_sha": result.integrated_sha,
            }
        )

    async def verify(
        self, context: WorkflowJobContext, effect: EffectResult
    ) -> VerificationResult:
        route = str(effect.receipt.get("route") or "")
        if route in {IntegrationRoute.REBASE.value, IntegrationRoute.CI_FIX.value}:
            return VerificationResult(True, dict(effect.receipt))
        landing = await _resolve(self.backend.observe_landing(context))
        if self._landing_matches(context.job, landing):
            return VerificationResult(
                True,
                {**dict(effect.receipt), "landing": landing.to_dict()},
            )
        return VerificationResult(
            False,
            dict(effect.receipt),
            "exact integration head is not yet proven on the target branch",
        )

    async def build_transition(
        self,
        context: WorkflowJobContext,
        verification: VerificationResult,
    ) -> TransitionIntent | None:
        return await _resolve(self.backend.build_transition(context, verification))
