"""Production, task-scoped effects for the durable review/CI workflow.

The legacy review loop fetches every review and then mutates every matching
task.  Durable jobs must have a narrower authority boundary: one project, one
task, one immutable review, and one facts generation.  This module supplies
that boundary without consulting ``Orchestrator._reviews_cache`` or invoking
any project sweep.
"""

from __future__ import annotations

import asyncio
import contextlib
import re
import threading
from collections.abc import Mapping
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any

from oompah.integration import (
    ACCEPTED_SUBMISSION_STATES,
    IntegrationRecord,
    REVIEW_GENERATION_REQUEUE_WAIT_REASON,
    assigned_work_branch,
    requeue_standalone_review_generation,
    review_generation_requeue_marker,
)
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
    DONE,
    IN_REVIEW,
    IN_VALIDATION,
    MERGED,
    NEEDS_CI_FIX,
    NEEDS_REBASE,
    OPEN,
    READY_TO_INTEGRATE,
    canonicalize_status,
)
from oompah.terminal_audit import TargetState
from oompah.task_transition_service import (
    TransitionAuthority,
    TransitionIntent,
    issue_authority_version,
    issue_exact_head,
)
from oompah.workflow_fact_model import (
    FactDomain,
    FactState,
    LandingFact,
    LandingState,
)
from oompah.workflow_jobs import WorkflowFailureCategory
from oompah.workflow_worker import (
    EffectResult,
    RevalidationResult,
    VerificationResult,
    WorkflowActionError,
    WorkflowActionSuperseded,
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

    @contextmanager
    def observation_scope(self):
        """Share one successful forge listing across a reconciliation pass.

        The review controller evaluates every In Review task from one tracker
        snapshot. Fetching the same project's complete open-review list once
        per task is both expensive and less coherent than selecting all task
        reviews from one provider observation. The scope is thread-local and
        discarded before the next authoritative pass.
        """

        previous = getattr(self._local, "open_reviews", None)
        self._local.open_reviews = None
        self._local.open_reviews_loaded = False
        try:
            yield
        finally:
            if previous is None:
                for name in ("open_reviews", "open_reviews_loaded"):
                    try:
                        delattr(self._local, name)
                    except AttributeError:
                        pass
            else:
                self._local.open_reviews = previous
                self._local.open_reviews_loaded = True

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
            base_sha=_text(raw.get("base_sha")) or None,
            source_repository=_text(raw.get("source_repository")) or None,
            target_repository=_text(raw.get("target_repository")) or None,
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
        reviews = None
        if getattr(self._local, "open_reviews_loaded", False):
            reviews = getattr(self._local, "open_reviews", None)
        else:
            try:
                reviews = provider.list_open_reviews(repo)
            except Exception as exc:  # noqa: BLE001 - provider evidence boundary
                raise ReviewObservationUnavailable(
                    "review provider unavailable"
                ) from exc
            if (
                reviews is None
                or getattr(provider, "last_open_reviews_fetch_ok", True) is False
            ):
                raise ReviewObservationUnavailable("review provider unavailable")
            reviews = tuple(reviews)
            if hasattr(self._local, "open_reviews_loaded"):
                self._local.open_reviews = reviews
                self._local.open_reviews_loaded = True

        raw = review_fact_source(
            provider,
            repo,
            provider_name=provider_label,
            review_id=_text(issue.review_number) or None,
            source_branch=self._source(issue) or None,
            capacity={"limit": int(getattr(project, "max_in_flight_prs", 1))},
            open_reviews=reviews,
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
        "review_terminal_stage": frozenset({DONE, IN_VALIDATION, MERGED}),
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
        review_head = _text(issue.review_head).lower()
        integration = issue.integration
        integration_head = _text(
            integration.head_sha if isinstance(integration, IntegrationRecord) else None
        ).lower()
        integration_base = _text(
            integration.base_sha if isinstance(integration, IntegrationRecord) else None
        ).lower()
        if (
            observation is None
            or snapshot.provider_context is None
            or not isinstance(integration, IntegrationRecord)
            or integration.state not in ACCEPTED_SUBMISSION_STATES
        ):
            raise WorkflowActionError(
                "review merge lacks accepted integration identity",
                category=WorkflowFailureCategory.STALE_EVIDENCE,
                retryable=False,
            )
        observed_review = _text(observation.review_id)
        observed_head = _text(observation.head_sha).lower()
        expected_source = _text(
            assigned_work_branch(issue)
            or issue.work_branch
            or issue.branch_name
            or issue.identifier
        )
        expected_target = _text(issue.target_branch)
        expected_repo = _text(snapshot.provider_context.repo).casefold()
        identities_match = bool(
            review_id
            and review_id == observed_review
            and expected_source
            and expected_source == observation.source_branch
            and expected_source == _text(integration.task_branch)
            and expected_target
            and expected_target == observation.target_branch
            and expected_target == _text(integration.base_branch)
            and expected_repo
            and expected_repo == _text(observation.target_repository).casefold()
            and expected_repo == _text(observation.source_repository).casefold()
            and _HEAD_RE.fullmatch(review_head)
            and review_head == integration_head
            and review_head == observed_head
            and _HEAD_RE.fullmatch(integration_base)
            and integration_base == _text(observation.base_sha).lower()
        )
        if not identities_match:
            raise WorkflowActionError(
                "review, repository, branch, or exact head identity changed",
                category=WorkflowFailureCategory.STALE_EVIDENCE,
                retryable=False,
            )
        head = review_head
        return review_id, head

    @staticmethod
    def _head_reconciliation_identity(
        snapshot: ReviewActionSnapshot,
    ) -> tuple[IntegrationRecord, str, str, str]:
        """Bind a forge head replacement to one accepted standalone review."""

        issue = snapshot.issue
        observation = snapshot.observation
        provider_context = snapshot.provider_context
        integration = issue.integration
        old_head = _text(issue.review_head).lower()
        new_head = _text(observation.head_sha if observation is not None else None).lower()
        old_base = _text(
            integration.base_sha if isinstance(integration, IntegrationRecord) else None
        ).lower()
        new_base = _text(
            observation.base_sha if observation is not None else None
        ).lower()
        checkpoint = review_generation_requeue_marker(
            observation.review_id if observation is not None else None,
            new_head,
            new_base,
        )
        accepted_checkpoint = review_generation_requeue_marker(
            observation.review_id if observation is not None else None,
            integration.head_sha
            if isinstance(integration, IntegrationRecord)
            else None,
            old_base,
        )
        expected_repo = _text(
            provider_context.repo if provider_context is not None else None
        ).casefold()
        expected_source = _text(
            assigned_work_branch(issue)
            or issue.work_branch
            or issue.branch_name
            or issue.identifier
        )
        expected_target = _text(issue.target_branch)
        integration_base_branch = _text(
            integration.base_branch
            if isinstance(integration, IntegrationRecord)
            else None
        )
        old_base_is_enrichable = bool(
            isinstance(integration, IntegrationRecord)
            and not old_base
            and integration_base_branch in {"", expected_target}
        )
        valid = bool(
            observation is not None
            and provider_context is not None
            and isinstance(integration, IntegrationRecord)
            and integration.state in ACCEPTED_SUBMISSION_STATES
            and _text(integration.mode).lower() in {"", "standalone"}
            and _text(issue.review_number)
            and _text(issue.review_number) == _text(observation.review_id)
            and expected_source
            and expected_source == observation.source_branch
            and expected_source == _text(integration.task_branch)
            and expected_target
            and expected_target == observation.target_branch
            and integration_base_branch in {"", expected_target}
            and expected_repo
            and expected_repo == _text(observation.target_repository).casefold()
            and expected_repo == _text(observation.source_repository).casefold()
            and _HEAD_RE.fullmatch(old_head)
            and _HEAD_RE.fullmatch(new_head)
            and (_HEAD_RE.fullmatch(old_base) or old_base_is_enrichable)
            and _HEAD_RE.fullmatch(new_base)
            and (
                new_head != old_head
                or new_base != old_base
                or not integration_base_branch
                or (
                    integration.wait_reason
                    == REVIEW_GENERATION_REQUEUE_WAIT_REASON
                    and checkpoint is not None
                    and integration.wait_generation == checkpoint
                )
            )
            and (
                _text(integration.head_sha).lower() == old_head
                or (
                    integration.state == "ready"
                    and integration.wait_reason
                    == REVIEW_GENERATION_REQUEUE_WAIT_REASON
                    and accepted_checkpoint is not None
                    and integration.wait_generation == accepted_checkpoint
                )
            )
        )
        if not valid:
            raise WorkflowActionError(
                "review head replacement lacks exact task, review, branch, or repository identity",
                category=WorkflowFailureCategory.STALE_EVIDENCE,
                retryable=False,
            )
        return integration, old_head, new_head, new_base

    def _successor_generation(
        self,
        context: WorkflowJobContext,
        snapshot: ReviewActionSnapshot,
    ) -> str | None:
        """Return fresh valid review authority that supersedes this effect.

        Review actions observe twice around the external-effect boundary.  A
        synchronize, target-base advance, or post-deployment identity
        enrichment between those reads is a new optimistic-concurrency
        generation, not a failure of the old generation.  Only a complete,
        same-repository review identity may rearm authority here; malformed,
        forked, conflicting, or policy-invalid observations stay on the
        bounded failure path.
        """

        issue = snapshot.issue
        observation = snapshot.observation
        provider_context = snapshot.provider_context
        integration = issue.integration
        decision = snapshot.decision
        if (
            canonicalize_status(issue.state) != IN_REVIEW
            or observation is None
            or provider_context is None
            or not isinstance(integration, IntegrationRecord)
            or integration.state not in ACCEPTED_SUBMISSION_STATES
            or _text(integration.mode).lower() not in {"", "standalone"}
            or decision is None
            or len(decision.durable_jobs) != 1
            or decision.durable_jobs[0] not in REVIEW_ACTION_JOBS
            or observation.state != "open"
            or observation.source_deleted
            or observation.conflict
            or observation.needs_rebase
            or observation.mergeable is False
            or observation.mergeable_state in {"dirty", "behind"}
        ):
            return None
        expected_review = _text(issue.review_number)
        expected_head = _text(issue.review_head).lower()
        expected_source = _text(
            assigned_work_branch(issue)
            or issue.work_branch
            or issue.branch_name
            or issue.identifier
        )
        expected_target = _text(issue.target_branch)
        expected_repo = _text(provider_context.repo).casefold()
        observed_head = _text(observation.head_sha).lower()
        observed_base = _text(observation.base_sha).lower()
        integration_head = _text(integration.head_sha).lower()
        integration_base = _text(integration.base_sha).lower()
        integration_target = _text(integration.base_branch)
        exact_identity = bool(
            expected_review
            and expected_review == _text(observation.review_id)
            and expected_source
            and expected_source == _text(observation.source_branch)
            and expected_source == _text(integration.task_branch)
            and expected_target
            and expected_target == _text(observation.target_branch)
            and integration_target in {"", expected_target}
            and expected_repo
            and expected_repo
            == _text(observation.target_repository).casefold()
            and expected_repo
            == _text(observation.source_repository).casefold()
            and _HEAD_RE.fullmatch(expected_head)
            and _HEAD_RE.fullmatch(integration_head)
            and expected_head == integration_head
            and _HEAD_RE.fullmatch(observed_head)
            and _HEAD_RE.fullmatch(observed_base)
            and (not integration_base or _HEAD_RE.fullmatch(integration_base))
        )
        if not exact_identity:
            return None
        current_action = decision.durable_jobs[0]
        evidence_changed = bool(
            current_action != context.job.action
            or decision.evidence_revision
            != context.job.expected_evidence_revision
        )
        if not evidence_changed:
            return None
        return self.controller.scheduler.decision_revision(decision)

    def _raise_for_successor(
        self,
        context: WorkflowJobContext,
        snapshot: ReviewActionSnapshot,
    ) -> None:
        replacement = self._successor_generation(context, snapshot)
        if replacement is not None:
            raise WorkflowActionSuperseded(
                "review effect authority was superseded by a fresh exact generation",
                replacement_generation=replacement,
            )

    def _persist_reconciled_head(
        self,
        context: WorkflowJobContext,
        snapshot: ReviewActionSnapshot,
    ) -> IntegrationRecord:
        """Atomically replace accepted authority before the RTI transition."""

        integration, _old_head, new_head, new_base = self._head_reconciliation_identity(
            snapshot
        )
        issue_id = _text(snapshot.issue.id or snapshot.issue.identifier)
        lock_factory = getattr(self.orchestrator, "issue_transition_lock", None)
        lock = lock_factory(issue_id) if callable(lock_factory) else None
        sync = getattr(lock, "sync", None)
        lock_context = sync() if callable(sync) else contextlib.nullcontext()
        with lock_context:
            context.check_interrupted()
            current = self._issue(context.job.task_id)
            current_integration = current.integration
            if (
                isinstance(current_integration, IntegrationRecord)
                and current_integration.state == "ready"
                and _text(current_integration.head_sha).lower() == new_head
                and _text(current_integration.base_sha).lower() == new_base
                and _text(current_integration.base_branch)
                == _text(snapshot.issue.target_branch)
                and current_integration.wait_reason
                == REVIEW_GENERATION_REQUEUE_WAIT_REASON
                and current_integration.wait_generation
                == review_generation_requeue_marker(
                    snapshot.observation.review_id,
                    new_head,
                    new_base,
                )
            ):
                return current_integration
            if issue_authority_version(current) != issue_authority_version(
                snapshot.issue
            ):
                raise WorkflowActionError(
                    "review task authority changed before head replacement",
                    category=WorkflowFailureCategory.STALE_EVIDENCE,
                    retryable=False,
                )
            replacement = requeue_standalone_review_generation(
                replace(
                    integration,
                    base_branch=(
                        integration.base_branch
                        or _text(snapshot.issue.target_branch)
                    ),
                ),
                review_id=snapshot.observation.review_id,
                head_sha=new_head,
                base_sha=new_base,
                updated_at=datetime.now(timezone.utc).isoformat(),
            )
            self.binding.tracker.set_metadata_field(
                context.job.task_id,
                "oompah.integration",
                replacement.to_dict(),
            )
            context.check_interrupted()
            persisted = self._issue(context.job.task_id).integration
            if (
                not isinstance(persisted, IntegrationRecord)
                or persisted.state != "ready"
                or _text(persisted.head_sha).lower() != new_head
                or _text(persisted.base_sha).lower() != new_base
                or _text(persisted.base_branch)
                != _text(snapshot.issue.target_branch)
                or persisted.wait_reason != REVIEW_GENERATION_REQUEUE_WAIT_REASON
                or persisted.wait_generation != replacement.wait_generation
            ):
                raise WorkflowActionError(
                    "review head replacement did not persist",
                    category=WorkflowFailureCategory.TRANSIENT,
                    retryable=True,
                )
            return persisted

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
        expected_repo = _text(
            snapshot.provider_context.repo
            if snapshot.provider_context is not None
            else None
        ).casefold()
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
            and (
                not expected_repo
                or not observation.target_repository
                or expected_repo == observation.target_repository.casefold()
            )
            and (
                not expected_repo
                or not observation.source_repository
                or expected_repo == observation.source_repository.casefold()
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
            integration = snapshot.issue.integration
            integration_base = _text(
                integration.base_sha
                if isinstance(integration, IntegrationRecord)
                else None
            ).lower()
            observed_base = _text(observation.base_sha).lower()
            checkpoint = review_generation_requeue_marker(
                observation.review_id,
                observed_head,
                observed_base,
            )
            pending = bool(
                isinstance(integration, IntegrationRecord)
                and integration.wait_reason
                == REVIEW_GENERATION_REQUEUE_WAIT_REASON
                and checkpoint is not None
                and integration.wait_generation == checkpoint
            )
            decision_requires_reconciliation = bool(
                snapshot.decision is not None
                and action in snapshot.decision.durable_jobs
            )
            return (
                "head_changed"
                if decision_requires_reconciliation
                or pending
                or (issue_head and observed_head != issue_head)
                or (
                    integration_base
                    and observed_base
                    and integration_base != observed_base
                )
                else "observed"
            )
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
        action = context.job.action
        # Effects must observe again after revalidation.  A synchronize,
        # undraft, or check delivery can otherwise change the review between
        # the decision read and a merge/requeue write.
        snapshot = (
            await self._snapshot(context)
            if action in {"review_merge", "review_head_reconciliation"}
            else await self._current_snapshot(context)
        )
        if action == "review_head_reconciliation":
            decision = snapshot.decision
            if (
                decision is None
                or action not in decision.durable_jobs
                or self._condition(action, snapshot) != "head_changed"
            ):
                raise WorkflowActionError(
                    "review head replacement is no longer current",
                    category=WorkflowFailureCategory.STALE_EVIDENCE,
                    retryable=False,
                )
            replacement = await asyncio.to_thread(
                self._persist_reconciled_head,
                context,
                snapshot,
            )
            return ReviewExecutionResult(
                "head_changed",
                f"accepted standalone head replaced with {replacement.head_sha}",
                snapshot.observation,
            )
        if action == "review_merge":
            provider_context = snapshot.provider_context
            if provider_context is None:
                return ReviewExecutionResult("provider_unavailable")
            decision = snapshot.decision
            if (
                decision is None
                or action not in decision.durable_jobs
                or self._condition(action, snapshot) != "ready_to_merge"
            ):
                self._raise_for_successor(context, snapshot)
                raise WorkflowActionError(
                    "review is no longer authorized for merge",
                    category=WorkflowFailureCategory.STALE_EVIDENCE,
                    retryable=False,
                )
            try:
                review_id, head = self._exact_identity(snapshot)
            except WorkflowActionError:
                self._raise_for_successor(context, snapshot)
                raise
            if not review_id or not _HEAD_RE.fullmatch(head):
                raise WorkflowActionError(
                    "review merge requires an immutable review and exact head",
                    category=WorkflowFailureCategory.STALE_EVIDENCE,
                    retryable=False,
                )
            queue_enabled = bool(
                getattr(provider_context.project, "merge_queue_enabled", False)
            )
            provider_name = _text(
                getattr(snapshot.observation, "provider", None)
            ).casefold()
            if provider_name == "gitlab" and not queue_enabled:
                return ReviewExecutionResult(
                    "policy_error",
                    "GitLab review merge requires merge_queue_enabled so the "
                    "exact head is validated through a merge train",
                    snapshot.observation,
                )
            operation = (
                provider_context.provider.enable_auto_merge_exact
                if queue_enabled
                else provider_context.provider.merge_review_exact
            )
            ok, message = await asyncio.to_thread(
                operation, provider_context.repo, review_id, head
            )
            context.check_interrupted()
            if not ok:
                current = await self._snapshot(context)
                self._raise_for_successor(context, current)
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
            receipt = dict(effect.receipt)
            if action == "review_head_reconciliation" and current == expected:
                try:
                    _integration, _old_head, new_head, new_base = (
                        self._head_reconciliation_identity(snapshot)
                    )
                except WorkflowActionError:
                    return VerificationResult(
                        False,
                        receipt,
                        "review advanced again before replacement transition",
                    )
                current_integration = snapshot.issue.integration
                if (
                    not isinstance(current_integration, IntegrationRecord)
                    or current_integration.state != "ready"
                    or _text(current_integration.head_sha).lower() != new_head
                    or _text(current_integration.base_sha).lower() != new_base
                    or _text(current_integration.base_branch)
                    != _text(snapshot.issue.target_branch)
                ):
                    return VerificationResult(
                        False,
                        receipt,
                        "replacement integration generation is not durable",
                    )
                receipt["head_sha"] = new_head
            if action == "review_terminal_stage" and current == expected:
                decision = snapshot.decision
                evidence_revision = _text(
                    decision.evidence_revision if decision is not None else None
                )
                if (
                    not evidence_revision
                    or decision is None
                    or action not in decision.durable_jobs
                ):
                    return VerificationResult(
                        False,
                        receipt,
                        "fresh review landing evidence revision is unavailable",
                    )
                expected_revision = _text(
                    context.job.expected_evidence_revision
                )
                if expected_revision and evidence_revision != expected_revision:
                    raise WorkflowActionError(
                        "review landing evidence changed before terminal transition",
                        category=WorkflowFailureCategory.STALE_EVIDENCE,
                        retryable=False,
                    )
                receipt["evidence_revision"] = evidence_revision
            return VerificationResult(
                current == expected,
                receipt,
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

    def _landed_review_terminal_status(self, issue: Issue) -> str:
        """Resolve the immediate landed-review target without mock leakage."""

        resolver = None
        try:
            resolver = vars(self.orchestrator).get(
                "resolve_landed_review_terminal_target"
            )
        except TypeError:
            pass
        if not callable(resolver):
            implemented = getattr(
                type(self.orchestrator),
                "resolve_landed_review_terminal_target",
                None,
            )
            if callable(implemented):
                resolver = implemented.__get__(
                    self.orchestrator,
                    type(self.orchestrator),
                )
        if resolver is None:
            # Tracker-neutral embedders do not have hierarchy I/O. Preserve
            # deterministic task-shape behavior while production uses the
            # fail-closed Orchestrator resolver above.
            return (
                DONE
                if _text(issue.parent_id)
                and _text(issue.issue_type).lower() != "epic"
                else MERGED
            )
        try:
            target = TargetState.from_raw(resolver(issue, self.project_id))
        except Exception as exc:
            retryable = bool(getattr(exc, "retryable", False))
            raise WorkflowActionError(
                "review terminal target topology is unavailable",
                category=(
                    WorkflowFailureCategory.TRANSIENT
                    if retryable
                    else WorkflowFailureCategory.PERMANENT
                ),
                retryable=retryable,
            ) from exc
        if target not in {TargetState.DONE, TargetState.MERGED}:
            raise WorkflowActionError(
                "review terminal target topology returned an unsupported state",
                category=WorkflowFailureCategory.POLICY,
                retryable=False,
            )
        return target.value

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
        precondition_revision = None
        if context.job.action == "review_terminal_stage":
            requested = self._landed_review_terminal_status(issue)
            precondition_revision = _text(
                verification.receipt.get("evidence_revision")
            ) or None
            if precondition_revision is None:
                raise WorkflowActionError(
                    "review terminal transition lacks a freshly verified evidence revision",
                    category=WorkflowFailureCategory.PERMANENT,
                    retryable=False,
                )
        elif context.job.action == "review_head_reconciliation":
            integration = issue.integration
            exact_head = _text(
                integration.head_sha
                if isinstance(integration, IntegrationRecord)
                else None
            ).lower()
            if not _HEAD_RE.fullmatch(exact_head):
                raise WorkflowActionError(
                    "review head transition lacks replacement integration authority",
                    category=WorkflowFailureCategory.PERMANENT,
                    retryable=False,
                )
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
            precondition_revision=precondition_revision,
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
