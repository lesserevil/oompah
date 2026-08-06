"""Production, task-scoped effects for the durable review/CI workflow.

The legacy review loop fetches every review and then mutates every matching
task.  Durable jobs must have a narrower authority boundary: one project, one
task, one immutable review, and one facts generation.  This module supplies
that boundary without consulting ``Orchestrator._reviews_cache`` or invoking
any project sweep.
"""

from __future__ import annotations

import asyncio
import re
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from oompah.integration import assigned_work_branch
from oompah.models import Issue
from oompah.review_workflow import (
    ReviewCapacityReconciler,
    ReviewExecutionResult,
    ReviewObservation,
    ReviewObservationUnavailable,
    ReviewWorkflowController,
    ReviewWorkflowHandler,
    review_fact_source,
)
from oompah.scm import detect_provider, extract_repo_slug
from oompah.statuses import (
    IN_REVIEW,
    IN_VALIDATION,
    MERGED,
    NEEDS_CI_FIX,
    NEEDS_REBASE,
    OPEN,
    READY_TO_INTEGRATE,
    canonicalize_status,
)
from oompah.task_transition_service import (
    TransitionAuthority,
    TransitionIntent,
    issue_authority_version,
    issue_exact_head,
)
from oompah.workflow_facts import FactDomain, FactState, LandingFact, LandingState
from oompah.workflow_jobs import WorkflowFailureCategory
from oompah.workflow_worker import (
    EffectResult,
    RevalidationResult,
    VerificationResult,
    WorkflowActionError,
    WorkflowJobContext,
)
from oompah.work_decision import REVIEW_ACTION_JOBS, WorkDecision


_HEAD_RE = re.compile(r"^[0-9a-f]{40,64}$")


def _text(value: object | None) -> str:
    return str(value or "").strip()


@dataclass(frozen=True, slots=True)
class FreshReviewContext:
    """One successful project-scoped provider observation."""

    project_id: str
    task_id: str
    provider: Any
    repo: str
    project: Any
    observation: ReviewObservation


class FreshReviewFactSource:
    """Resolve the project provider for every collection, never a stale cache."""

    def __init__(self, orchestrator: Any, *, project_id: str) -> None:
        self.orchestrator = orchestrator
        self.project_id = _text(project_id)
        if not self.project_id:
            raise ValueError("project_id is required")
        self._local = threading.local()

    def _project(self) -> Any:
        project = self.orchestrator.project_store.get(self.project_id)
        if project is None:
            raise ReviewObservationUnavailable(
                f"review project {self.project_id} is unavailable"
            )
        return project

    @staticmethod
    def _source(issue: Issue) -> str:
        return _text(
            assigned_work_branch(issue)
            or issue.work_branch
            or issue.branch_name
            or issue.identifier
        )

    @staticmethod
    def _observation(raw: Mapping[str, Any]) -> ReviewObservation:
        return ReviewObservation(
            state=_text(raw.get("state")) or "missing",
            review_id=_text(raw.get("review_id")) or None,
            source_branch=_text(raw.get("source_branch")) or None,
            target_branch=_text(raw.get("target_branch")) or None,
            head_sha=_text(raw.get("head_sha")) or None,
            ci=_text(raw.get("ci")) or "unknown",
            mergeable=raw.get("mergeable"),
            mergeable_state=_text(raw.get("mergeable_state")),
            conflict=bool(raw.get("conflict")),
            needs_rebase=bool(raw.get("needs_rebase")),
            draft=bool(raw.get("draft")),
            auto_merge_enabled=bool(raw.get("auto_merge_enabled")),
            provider=_text(raw.get("provider")) or None,
            source_deleted=bool(raw.get("source_deleted")),
            capacity=(
                dict(raw.get("capacity"))
                if isinstance(raw.get("capacity"), Mapping)
                else None
            ),
        )

    def __call__(self, issue: Issue) -> Mapping[str, Any]:
        contexts = getattr(self._local, "contexts", None)
        if contexts is None:
            contexts = {}
            self._local.contexts = contexts
        # A failed collection must not inherit the last successful provider
        # body for the same task on this worker thread.
        contexts.pop(issue.identifier, None)
        issue_project = _text(issue.project_id) or self.project_id
        if issue_project != self.project_id:
            raise ReviewObservationUnavailable(
                "review task crossed its project provider binding"
            )
        project = self._project()
        repo_url = _text(getattr(project, "repo_url", None))
        provider = detect_provider(
            repo_url,
            access_token=getattr(project, "access_token", None),
        )
        if provider is None:
            raise ReviewObservationUnavailable(
                "review project has no supported forge provider"
            )
        repo = extract_repo_slug(repo_url)
        provider_name = getattr(provider, "provider_name", None)
        provider_label = (
            _text(provider_name()) if callable(provider_name) else type(provider).__name__
        )
        raw = review_fact_source(
            provider,
            repo,
            provider_name=provider_label,
            review_id=_text(issue.review_number) or None,
            source_branch=self._source(issue) or None,
            capacity={"limit": int(getattr(project, "max_in_flight_prs", 1))},
        )(issue)
        observation = self._observation(raw)
        contexts[issue.identifier] = FreshReviewContext(
            self.project_id,
            issue.identifier,
            provider,
            repo,
            project,
            observation,
        )
        return raw

    def last_context(self, task_id: str) -> FreshReviewContext | None:
        contexts = getattr(self._local, "contexts", {})
        return contexts.get(_text(task_id))


@dataclass(frozen=True, slots=True)
class ReviewActionSnapshot:
    issue: Issue
    provider_context: FreshReviewContext | None
    decision: WorkDecision | None
    landing: LandingFact | None

    @property
    def observation(self) -> ReviewObservation | None:
        if self.provider_context is None:
            return None
        return self.provider_context.observation


class ProductionReviewWorkflowBackend:
    """Generation-fenced backend shared by all ten review actions."""

    _TRANSITIONS = {
        "review_ci_repair": (NEEDS_CI_FIX, "review.ci_fix_required"),
        "review_conflict_repair": (NEEDS_REBASE, "review.rebase_required"),
        "review_closed_repair": (OPEN, "review.closed_unmerged"),
        "review_head_reconciliation": (
            READY_TO_INTEGRATE,
            "review.head_changed",
        ),
        "review_terminal_stage": (
            MERGED,
            "terminal.immediate_target_landing_proven",
        ),
    }

    _RECOVERY_STATES = {
        "review_ci_repair": frozenset({NEEDS_CI_FIX}),
        "review_conflict_repair": frozenset({NEEDS_REBASE}),
        "review_closed_repair": frozenset({OPEN}),
        "review_head_reconciliation": frozenset({READY_TO_INTEGRATE}),
        "review_terminal_stage": frozenset({IN_VALIDATION, MERGED}),
    }

    def __init__(
        self,
        orchestrator: Any,
        binding: Any,
        source: FreshReviewFactSource,
    ) -> None:
        self.orchestrator = orchestrator
        self.binding = binding
        self.source = source
        self.project_id = _text(binding.project_id)
        self.controller: ReviewWorkflowController = binding.review_controller
        self._snapshots: dict[str, ReviewActionSnapshot] = {}
        self._lock = threading.RLock()

    def _issue(self, task_id: str) -> Issue:
        invalidate = getattr(self.binding.tracker, "invalidate_read_cache", None)
        if callable(invalidate):
            invalidate()
        issue = self.binding.tracker.fetch_issue_detail(task_id)
        if issue is None:
            raise WorkflowActionError(
                f"review task {task_id} is unavailable",
                category=WorkflowFailureCategory.TRANSIENT,
                retryable=True,
            )
        if _text(issue.project_id) not in {"", self.project_id}:
            raise WorkflowActionError(
                "review task crossed its project binding",
                category=WorkflowFailureCategory.POLICY,
                retryable=False,
            )
        issue.project_id = self.project_id
        return issue

    @staticmethod
    def _landing_for(snapshot_item: Any) -> LandingFact | None:
        task = snapshot_item.task
        source = _text(task.work_branch or task.branch_name or task.identifier)
        target = _text(task.target_branch)
        head = _text(task.review_head or task.head_sha).lower()
        return next(
            (
                landing
                for landing in snapshot_item.facts.landings
                if landing.state is LandingState.LANDED
                and landing.durable
                and (not source or landing.source == source)
                and (not target or landing.target == target)
                and (not head or landing.revision == head)
            ),
            None,
        )

    def _snapshot_sync(self, context: WorkflowJobContext) -> ReviewActionSnapshot:
        job = context.job
        if job.project_id != self.project_id:
            raise WorkflowActionError(
                "review job crossed its project binding",
                category=WorkflowFailureCategory.POLICY,
                retryable=False,
            )
        issue = self._issue(job.task_id)
        recovery = canonicalize_status(issue.state) in self._RECOVERY_STATES.get(
            job.action, ()
        )
        if issue.state != IN_REVIEW:
            if not recovery:
                return ReviewActionSnapshot(issue, None, None, None)
            # A transition may have committed immediately before worker
            # checkpointing.  Tracker status plus the transition journal is
            # sufficient recovery evidence; do not require the forge to be up.
            return ReviewActionSnapshot(issue, None, None, None)

        batch = self.controller.evaluate((issue,))
        if not batch.tasks:
            return ReviewActionSnapshot(issue, None, None, None)
        evaluated = batch.tasks[0]
        provider_context = self.source.last_context(job.task_id)
        review_fact = evaluated.facts.fact(FactDomain.REVIEW_CI)
        if review_fact.state is FactState.KNOWN and provider_context is None:
            raise WorkflowActionError(
                "fresh review evidence lost its provider scope",
                category=WorkflowFailureCategory.PERMANENT,
                retryable=False,
            )
        return ReviewActionSnapshot(
            issue,
            provider_context,
            evaluated.decision,
            self._landing_for(evaluated),
        )

    async def _snapshot(self, context: WorkflowJobContext) -> ReviewActionSnapshot:
        snapshot = await asyncio.to_thread(self._snapshot_sync, context)
        with self._lock:
            self._snapshots[context.job.job_id] = snapshot
        return snapshot

    async def _current_snapshot(
        self, context: WorkflowJobContext
    ) -> ReviewActionSnapshot:
        with self._lock:
            snapshot = self._snapshots.get(context.job.job_id)
        return snapshot if snapshot is not None else await self._snapshot(context)

    @staticmethod
    def _exact_identity(snapshot: ReviewActionSnapshot) -> tuple[str, str]:
        issue = snapshot.issue
        observation = snapshot.observation
        review_id = _text(issue.review_number)
        head = _text(issue.review_head or issue.head_sha).lower()
        if observation is not None:
            observed_review = _text(observation.review_id)
            observed_head = _text(observation.head_sha).lower()
            expected_source = _text(
                assigned_work_branch(issue)
                or issue.work_branch
                or issue.branch_name
                or issue.identifier
            )
            expected_target = _text(issue.target_branch)
            if review_id and observed_review and review_id != observed_review:
                raise WorkflowActionError(
                    "review identity changed after scheduling",
                    category=WorkflowFailureCategory.STALE_EVIDENCE,
                    retryable=False,
                )
            if (
                expected_source
                and observation.source_branch
                and expected_source != observation.source_branch
            ):
                raise WorkflowActionError(
                    "review source changed after scheduling",
                    category=WorkflowFailureCategory.STALE_EVIDENCE,
                    retryable=False,
                )
            if (
                expected_target
                and observation.target_branch
                and expected_target != observation.target_branch
            ):
                raise WorkflowActionError(
                    "review target changed after scheduling",
                    category=WorkflowFailureCategory.STALE_EVIDENCE,
                    retryable=False,
                )
            if head and observed_head and head != observed_head:
                raise WorkflowActionError(
                    "review head changed after scheduling",
                    category=WorkflowFailureCategory.STALE_EVIDENCE,
                    retryable=False,
                )
            review_id = review_id or observed_review
            head = head or observed_head
        return review_id, head

    @staticmethod
    def _identity_matches(snapshot: ReviewActionSnapshot) -> bool:
        issue = snapshot.issue
        observation = snapshot.observation
        if observation is None:
            return False
        expected_review = _text(issue.review_number)
        expected_head = _text(issue.review_head or issue.head_sha).lower()
        observed_review = _text(observation.review_id)
        observed_head = _text(observation.head_sha).lower()
        expected_source = _text(
            assigned_work_branch(issue)
            or issue.work_branch
            or issue.branch_name
            or issue.identifier
        )
        expected_target = _text(issue.target_branch)
        return bool(
            (
                not expected_review
                or not observed_review
                or expected_review == observed_review
            )
            and (
                not expected_head
                or not observed_head
                or expected_head == observed_head
            )
            and (
                not expected_source
                or not observation.source_branch
                or expected_source == observation.source_branch
            )
            and (
                not expected_target
                or not observation.target_branch
                or expected_target == observation.target_branch
            )
        )

    async def revalidate(self, context: WorkflowJobContext) -> RevalidationResult:
        snapshot = await self._snapshot(context)
        issue = snapshot.issue
        recovery = canonicalize_status(issue.state) in self._RECOVERY_STATES.get(
            context.job.action, ()
        )
        if recovery:
            return RevalidationResult(
                context.job.generation,
                evidence_revision=context.job.expected_evidence_revision,
                head_sha=context.job.expected_head_sha,
                current=True,
                details={"recovered_status": canonicalize_status(issue.state)},
            )
        decision = snapshot.decision
        merge_recovery = bool(
            context.job.action == "review_merge"
            and snapshot.observation is not None
            and self._identity_matches(snapshot)
            and (
                snapshot.observation.state == "merged"
                or (
                    snapshot.provider_context is not None
                    and bool(
                        getattr(
                            snapshot.provider_context.project,
                            "merge_queue_enabled",
                            False,
                        )
                    )
                    and snapshot.observation.auto_merge_enabled
                )
            )
        )
        capacity_event = bool(
            context.job.action == "review_capacity_recheck"
            and snapshot.observation is not None
        )
        current = bool(
            merge_recovery
            or capacity_event
            or (
                decision is not None
                and context.job.action in decision.durable_jobs
                and (
                    context.job.expected_evidence_revision is None
                    or decision.evidence_revision
                    == context.job.expected_evidence_revision
                )
            )
        )
        return RevalidationResult(
            context.job.generation,
            evidence_revision=(
                context.job.expected_evidence_revision
                if merge_recovery
                else decision.evidence_revision if decision is not None else None
            ),
            head_sha=context.job.expected_head_sha,
            current=current,
            details={
                "review_id": _text(
                    snapshot.observation.review_id
                    if snapshot.observation is not None
                    else issue.review_number
                )
                or None,
                "review_head": _text(
                    snapshot.observation.head_sha
                    if snapshot.observation is not None
                    else issue.review_head
                )
                or None,
            },
        )

    @staticmethod
    def _condition(action: str, snapshot: ReviewActionSnapshot) -> str:
        observation = snapshot.observation
        if observation is None:
            return "provider_unavailable"
        if action in {"review_monitor", "review_refresh"}:
            return "observed"
        if action == "review_ci_repair":
            return "ci_failure" if observation.ci == "failed" else "observed"
        if action == "review_conflict_repair":
            conflict = (
                observation.conflict
                or observation.needs_rebase
                or observation.mergeable is False
                or observation.mergeable_state in {"dirty", "behind"}
            )
            return "conflict" if conflict else "observed"
        if action == "review_closed_repair":
            return "closed_unmerged" if observation.state == "closed_unmerged" else "observed"
        if action == "review_head_reconciliation":
            issue_head = _text(
                snapshot.issue.review_head or snapshot.issue.head_sha
            ).lower()
            observed_head = _text(observation.head_sha).lower()
            return "head_changed" if issue_head and observed_head != issue_head else "observed"
        if action == "review_merge":
            if observation.state == "merged":
                return "observed"
            ready = (
                observation.state == "open"
                and observation.ci in {"passed", "success", "successful"}
                and not observation.conflict
                and not observation.needs_rebase
                and observation.mergeable is not False
            )
            return "ready_to_merge" if ready else "provider_unavailable"
        if action in {"review_landing_refresh", "review_terminal_stage"}:
            return "landed" if snapshot.landing is not None else "landing_unknown"
        if action == "review_capacity_recheck":
            return "capacity_recheck"
        raise WorkflowActionError(
            f"unknown review action {action!r}",
            category=WorkflowFailureCategory.POLICY,
            retryable=False,
        )

    async def observe(self, context: WorkflowJobContext) -> ReviewExecutionResult:
        snapshot = await self._current_snapshot(context)
        if canonicalize_status(snapshot.issue.state) in self._RECOVERY_STATES.get(
            context.job.action, ()
        ):
            return ReviewExecutionResult("observed", "transition already applied")
        status = self._condition(context.job.action, snapshot)
        return ReviewExecutionResult(
            status,
            observation=snapshot.observation,
            landing=snapshot.landing,
        )

    async def repair(self, context: WorkflowJobContext) -> ReviewExecutionResult:
        context.check_interrupted()
        snapshot = await self._current_snapshot(context)
        action = context.job.action
        if action == "review_merge":
            provider_context = snapshot.provider_context
            if provider_context is None:
                return ReviewExecutionResult("provider_unavailable")
            review_id, head = self._exact_identity(snapshot)
            if not review_id or not _HEAD_RE.fullmatch(head):
                raise WorkflowActionError(
                    "review merge requires an immutable review and exact head",
                    category=WorkflowFailureCategory.STALE_EVIDENCE,
                    retryable=False,
                )
            operation = (
                provider_context.provider.enable_auto_merge
                if bool(getattr(provider_context.project, "merge_queue_enabled", False))
                else provider_context.provider.merge_review
            )
            ok, message = await asyncio.to_thread(
                operation, provider_context.repo, review_id
            )
            context.check_interrupted()
            if not ok:
                return ReviewExecutionResult(
                    "transport_error",
                    _text(message) or "review merge was not accepted",
                    snapshot.observation,
                )
            return ReviewExecutionResult(
                "observed",
                _text(message) or "review merge accepted",
                snapshot.observation,
            )
        if action == "review_capacity_recheck":
            provider_context = snapshot.provider_context
            if provider_context is None:
                return ReviewExecutionResult("provider_unavailable")
            result = await asyncio.to_thread(
                ReviewCapacityReconciler(
                    self.orchestrator.review_capacity_store
                ).reconcile,
                provider=provider_context.provider,
                repo=provider_context.repo,
                project_id=self.project_id,
            )
            return ReviewExecutionResult(
                "observed",
                f"review capacity reconciled; released={result.released}",
                snapshot.observation,
            )
        return ReviewExecutionResult(
            self._condition(action, snapshot),
            observation=snapshot.observation,
            landing=snapshot.landing,
        )

    async def verify(
        self,
        context: WorkflowJobContext,
        effect: EffectResult,
    ) -> VerificationResult:
        action = context.job.action
        if action in self._TRANSITIONS:
            snapshot = await self._snapshot(context)
            if canonicalize_status(snapshot.issue.state) in self._RECOVERY_STATES[action]:
                return VerificationResult(True, dict(effect.receipt))
            expected = {
                "review_ci_repair": "ci_failure",
                "review_conflict_repair": "conflict",
                "review_closed_repair": "closed_unmerged",
                "review_head_reconciliation": "head_changed",
                "review_terminal_stage": "landed",
            }[action]
            current = self._condition(action, snapshot)
            return VerificationResult(
                current == expected,
                dict(effect.receipt),
                None if current == expected else "review evidence changed before transition",
            )
        if action == "review_merge":
            snapshot = await self._snapshot(context)
            observation = snapshot.observation
            verified = bool(
                observation is not None
                and (
                    observation.state == "merged"
                    or (
                        bool(
                            getattr(
                                snapshot.provider_context.project,
                                "merge_queue_enabled",
                                False,
                            )
                        )
                        and observation.state == "open"
                        and observation.auto_merge_enabled
                    )
                )
            )
            if verified:
                review_id, _head = self._exact_identity(snapshot)
                await asyncio.to_thread(
                    self.orchestrator.review_capacity_store.release,
                    project_id=self.project_id,
                    review_id=review_id or None,
                    task_id=context.job.task_id,
                )
            return VerificationResult(
                verified,
                dict(effect.receipt),
                None if verified else "review merge is not yet visible",
            )
        if action in {"review_landing_refresh", "review_terminal_stage"}:
            snapshot = await self._snapshot(context)
            return VerificationResult(
                snapshot.landing is not None,
                dict(effect.receipt),
                None if snapshot.landing is not None else "landing is not yet proven",
            )
        return VerificationResult(True, dict(effect.receipt))

    async def build_transition(
        self,
        context: WorkflowJobContext,
        verification: VerificationResult,
    ) -> TransitionIntent | None:
        transition = self._TRANSITIONS.get(context.job.action)
        if transition is None:
            return None
        requested, reason = transition
        issue = await asyncio.to_thread(self._issue, context.job.task_id)
        if canonicalize_status(issue.state) in self._RECOVERY_STATES[context.job.action]:
            return None
        if issue.state != IN_REVIEW:
            raise WorkflowActionError(
                "review task status changed before transition",
                category=WorkflowFailureCategory.STALE_EVIDENCE,
                retryable=False,
            )
        exact_head = _text(issue_exact_head(issue)).lower()
        return TransitionIntent(
            project_id=self.project_id,
            task_id=context.job.task_id,
            expected_status=issue.state,
            expected_version=issue_authority_version(issue),
            requested_status=requested,
            actor="oompah",
            authority=TransitionAuthority.ORCHESTRATOR,
            reason_code=reason,
            idempotency_key=f"{context.job.idempotency_key}:transition",
            originating_job=context.job.job_id,
            evidence_generation=context.job.generation,
            exact_head=exact_head if _HEAD_RE.fullmatch(exact_head) else None,
        )


def build_review_workflow_handlers(
    orchestrator: Any,
    binding: Any,
) -> Mapping[str, ReviewWorkflowHandler]:
    """Return total task-scoped production coverage for the review domain."""

    source = binding.review_controller.collector.sources.get(FactDomain.REVIEW_CI)
    if not isinstance(source, FreshReviewFactSource):
        raise RuntimeError("review controller is not wired to fresh provider facts")
    backend = ProductionReviewWorkflowBackend(orchestrator, binding, source)
    handler = ReviewWorkflowHandler(backend)
    return {action: handler for action in REVIEW_ACTION_JOBS}


__all__ = [
    "FreshReviewContext",
    "FreshReviewFactSource",
    "ProductionReviewWorkflowBackend",
    "ReviewActionSnapshot",
    "build_review_workflow_handlers",
]
