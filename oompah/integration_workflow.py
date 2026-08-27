"""Durable integration decisions, execution, and UI projection.

This module is the integration-domain adapter for the shared workflow engine.
It collects immutable facts for every Ready task, evaluates each task exactly
once, schedules durable jobs from those decisions, and exposes the same
decision as the queue/UI projection.  The action handler wraps the existing
Git executor behind revalidation, exact-head landing proof, bounded failure
classification, and transition-intent construction.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import inspect
import re
import threading
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol

from oompah.integration_executor import (
    IntegrationExecutionResult,
)
from oompah.integration import (
    ACCEPTED_SUBMISSION_STATES,
    IntegrationRecord,
    direct_epic_maintenance_completion_ready,
    direct_epic_maintenance_handoff_ready,
    is_direct_epic_maintenance_issue,
)
from oompah.integration_queue import STANDALONE_RECLASSIFICATION_REASON
from oompah.models import EpicRebaseState, Issue
from oompah.statuses import (
    ARCHIVED,
    DONE,
    IN_REVIEW,
    IN_VALIDATION,
    MERGED,
    NEEDS_CI_FIX,
    NEEDS_REBASE,
    canonicalize_status,
)
from oompah.task_transition_service import (
    TransitionAuthority,
    TransitionIntent,
    issue_authority_version,
    issue_exact_head,
)
from oompah.terminal_audit import (
    RequestState,
    TargetState,
    Verdict,
    compute_issue_evidence_fingerprint,
)
from oompah.terminal_audit_metadata import METADATA_KEY, TerminalAuditMetadata
from oompah.work_decision import WorkDecision, evaluate_task
from oompah.workflow_contract import READY_TO_INTEGRATE
from oompah.workflow_fact_model import (
    FactDomain,
    LandingFact,
    LandingRequest,
    LandingState,
    WorkflowFacts,
)
from oompah.workflow_facts import WorkflowFactCollector
from oompah.workflow_jobs import (
    WorkflowFailureCategory,
    WorkflowJob,
    WorkflowJobSpec,
    WorkflowJobState,
    WorkflowJobStore,
)
from oompah.workflow_scheduler import WorkflowJobScheduler, WorkflowReconcileResult
from oompah.workflow_worker import (
    EffectObservation,
    EffectResult,
    RevalidationResult,
    VerificationResult,
    WorkflowAdministrativeDeferral,
    WorkflowActionDomain,
    WorkflowActionError,
    WorkflowActionSuperseded,
    WorkflowJobContext,
)

DEFAULT_INTEGRATION_DECISION_LIMIT = 1000
HISTORICAL_REPLAY_TASK_ID = "__oompah_integration_history__"
HISTORICAL_REPLAY_PRIORITY = 10_000
INTEGRATION_ACTIONS = frozenset(
    {
        "epic_branch_reconciliation",
        "direct_epic_maintenance_completion",
        "historical_audit_replay_batch",
        "integration_attempt",
        "integration_landing_refresh",
        "integration_recovery",
        "integration_terminal_stage",
        "parent_rollup_review",
        "standalone_delivery",
        "terminal_audit_done",
    }
)


@dataclass(frozen=True, slots=True)
class StandaloneDeliveryOutcome:
    """Typed non-success result from one scoped standalone delivery attempt.

    The accepted submission remains immutable when its mutable remote branch
    advances.  Returning this evidence to the durable workflow adapter lets it
    retire the stale job without treating a known authority change as a
    transient forge failure or adopting the unsubmitted remote head.
    """

    accepted_head: str
    observed_branch_head: str
    reason: str
    observed_review_head: str | None = None
    review_id: str | None = None
    disposition: str = field(default="resubmission_required", init=False)

    def __post_init__(self) -> None:
        accepted = str(self.accepted_head or "").strip().lower()
        observed = str(self.observed_branch_head or "").strip().lower()
        reason = str(self.reason or "").strip()
        if not accepted or not observed or not reason:
            raise ValueError(
                "standalone delivery drift requires accepted head, "
                "observed branch head, and reason"
            )
        object.__setattr__(self, "accepted_head", accepted)
        object.__setattr__(self, "observed_branch_head", observed)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(
            self,
            "observed_review_head",
            str(self.observed_review_head or "").strip().lower() or None,
        )
        object.__setattr__(
            self,
            "review_id",
            str(self.review_id or "").strip() or None,
        )


def _historical_replay_identity(
    project_id: str,
    cursor: str | None,
    first_sequence: int,
) -> tuple[str, str]:
    evidence = hashlib.sha256(
        f"{project_id}\0{cursor or ''}\0{int(first_sequence)}".encode("utf-8")
    ).hexdigest()
    return f"integration-history:{evidence}", evidence


def schedule_project_historical_replay(
    orchestrator: Any,
    store: WorkflowJobStore,
    project_id: str,
) -> WorkflowJob | None:
    """Materialize the next low-priority project history generation."""

    project = str(project_id or "").strip()
    if not project:
        return None
    cursor_name = f"integration_audit:{project}"
    cursor = getattr(orchestrator, "_maintenance_cursors", {}).get(cursor_name)
    rows = orchestrator.integration_queue.items(
        project_id=project,
        states=("integrated",),
        limit=1,
        after=cursor,
    )
    if not rows:
        return None
    generation, evidence = _historical_replay_identity(
        project, cursor, rows[0].history_sequence
    )
    return store.enqueue(
        WorkflowJobSpec(
            project_id=project,
            task_id=HISTORICAL_REPLAY_TASK_ID,
            generation=generation,
            action="historical_audit_replay_batch",
            idempotency_key=generation,
            expected_evidence_revision=evidence,
            priority=HISTORICAL_REPLAY_PRIORITY,
            max_attempts=5,
            payload={
                "cursor": cursor,
                "first_history_sequence": rows[0].history_sequence,
            },
            scheduling_lane="maintenance",
        )
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


@dataclass(frozen=True, slots=True)
class _RollupHeadAuthority:
    """Exact revision authority retained across one rollup job execution."""

    exact_head: str
    kind: str
    landing_source: str | None = None
    landing_target: str | None = None

    def receipt(self) -> dict[str, str | None]:
        return {
            "rollup_exact_head": self.exact_head,
            "rollup_head_authority": self.kind,
            "rollup_landing_source": self.landing_source,
            "rollup_landing_target": self.landing_target,
        }


class IntegrationLandingRequestResolver:
    """Resolve exact landing evidence across current and legacy authority.

    Older integrated children can predate the tracker fields that name their
    immediate epic target.  Their durable integration-queue row still owns
    the accepted source revision, while the current parent owns the target.
    Keeping that compatibility policy in one resolver prevents controller
    evaluation and action revalidation from proving different branch pairs.
    """

    def __init__(
        self,
        *,
        project_id: str | None = None,
        tracker: Any | None = None,
        integration_queue: Any | None = None,
        project_store: Any | None = None,
        project_default_branch: str | None = None,
        workflow_store: WorkflowJobStore | None = None,
        forge_review_resolver: Callable[[str], Any | None] | None = None,
        landing_collector: Any | None = None,
        parent_source_head_resolver: Callable[[str], str | None] | None = None,
    ) -> None:
        self.project_id = str(project_id or "").strip()
        self.tracker = tracker
        self.integration_queue = integration_queue
        self.project_store = project_store
        self.project_default_branch = str(project_default_branch or "").strip()
        self.workflow_store = workflow_store
        self.forge_review_resolver = forge_review_resolver
        self.landing_collector = landing_collector
        self.parent_source_head_resolver = parent_source_head_resolver
        self._observation_state = threading.local()

    @contextlib.contextmanager
    def observation_scope(self):
        """Memoize request resolution for one authoritative world scan.

        Resolving a Done child can consult its parent, children, queue row,
        persisted landing evidence, forge review, and remote branch head.  A
        large rollup otherwise repeats those external observations once per
        child even though all children are evaluated from the same immutable
        tracker cut.  The cache is thread-local and deliberately discarded at
        the publication boundary so later generations always observe fresh
        authority.
        """

        previous_requests = getattr(self._observation_state, "requests", None)
        previous_parent_heads = getattr(
            self._observation_state, "parent_heads", None
        )
        previous_forge_reviews = getattr(
            self._observation_state, "forge_reviews", None
        )
        self._observation_state.requests = {}
        self._observation_state.parent_heads = {}
        self._observation_state.forge_reviews = {}
        try:
            yield
        finally:
            if previous_requests is None:
                try:
                    del self._observation_state.requests
                except AttributeError:
                    pass
            else:
                self._observation_state.requests = previous_requests
            if previous_parent_heads is None:
                try:
                    del self._observation_state.parent_heads
                except AttributeError:
                    pass
            else:
                self._observation_state.parent_heads = previous_parent_heads
            if previous_forge_reviews is None:
                try:
                    del self._observation_state.forge_reviews
                except AttributeError:
                    pass
            else:
                self._observation_state.forge_reviews = previous_forge_reviews

    @staticmethod
    def _git_revision(value: object) -> str | None:
        revision = str(value or "").strip().lower()
        if re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", revision):
            return revision
        return None

    def _parent_source_branch(self, parent: Issue) -> str:
        branch = str(getattr(parent, "work_branch", "") or "").strip()
        if branch:
            return branch
        branch_name = getattr(self.project_store, "epic_branch_name", None)
        if callable(branch_name):
            try:
                return str(branch_name(parent.identifier) or "").strip()
            except Exception:  # noqa: BLE001 - optional authority source
                return ""
        return ""

    def _parent_landing_target(self, parent: Issue) -> str:
        target = str(getattr(parent, "target_branch", "") or "").strip()
        if target:
            return target
        integration = getattr(parent, "integration", None)
        base_branch = str(
            integration.get("base_branch", "")
            if isinstance(integration, Mapping)
            else getattr(integration, "base_branch", "")
        ).strip()
        source = self._parent_source_branch(parent)
        if base_branch and base_branch != source:
            return base_branch
        parent_id = str(getattr(parent, "parent_id", "") or "").strip()
        branch_name = getattr(self.project_store, "epic_branch_name", None)
        if parent_id and callable(branch_name):
            try:
                return str(branch_name(parent_id) or "").strip()
            except Exception:  # noqa: BLE001 - optional authority source
                return ""
        return self.project_default_branch

    def post_landed_parent_target(self, task: Issue) -> str | None:
        """Return a parent's exact already-landed immediate target, or fail closed."""

        lock_factory = getattr(self.project_store, "project_write_lock", None)
        lock = (
            lock_factory(self.project_id)
            if callable(lock_factory)
            else contextlib.nullcontext()
        )
        try:
            with lock:
                return self._post_landed_parent_target_locked(task)
        except Exception:  # noqa: BLE001 - complete authority cut fails closed
            return None

    def current_parent_queue_target(self, task: Issue) -> str | None:
        """Return the exact current parent branch for queue compensation.

        This deliberately does not require the parent's former landing proof.
        It is the recovery route used when that proof changes after a child was
        classified for standalone delivery.  Direct containment and the
        child's complete tracker authority are still checked under the project
        write lock, so a concurrent reparent cannot redirect the submission.
        """

        lock_factory = getattr(self.project_store, "project_write_lock", None)
        lock = (
            lock_factory(self.project_id)
            if callable(lock_factory)
            else contextlib.nullcontext()
        )
        try:
            with lock:
                parent_id = str(getattr(task, "parent_id", "") or "").strip()
                fetch = getattr(self.tracker, "fetch_issue_detail", None)
                fetch_children = getattr(self.tracker, "fetch_children", None)
                if (
                    not parent_id
                    or not callable(fetch)
                    or not callable(fetch_children)
                ):
                    return None
                parent = fetch(parent_id)
                parent_identity = str(
                    getattr(parent, "identifier", "")
                    or getattr(parent, "id", "")
                    or ""
                ).strip()
                parent_project = str(
                    getattr(parent, "project_id", "") or ""
                ).strip()
                if (
                    parent is None
                    or parent_identity != parent_id
                    or str(
                        getattr(parent, "issue_type", "") or ""
                    ).strip().lower()
                    != "epic"
                    or (
                        parent_project
                        and self.project_id
                        and parent_project != self.project_id
                    )
                ):
                    return None
                matching = tuple(
                    child
                    for child in fetch_children(parent_id)
                    if str(
                        getattr(child, "identifier", "")
                        or getattr(child, "id", "")
                        or ""
                    ).strip()
                    == task.identifier
                    and str(getattr(child, "parent_id", "") or "").strip()
                    == parent_id
                )
                if len(matching) != 1:
                    return None
                current_child = matching[0]
                authority_child = (
                    current_child
                    if current_child.project_id
                    else replace(current_child, project_id=self.project_id)
                )
                authority_task = (
                    task
                    if task.project_id
                    else replace(task, project_id=self.project_id)
                )
                if issue_authority_version(
                    authority_child
                ) != issue_authority_version(authority_task):
                    return None
                return self._parent_source_branch(parent) or None
        except Exception:  # noqa: BLE001 - complete authority cut fails closed
            return None

    def _post_landed_parent_target_locked(self, task: Issue) -> str | None:
        parent_id = str(getattr(task, "parent_id", "") or "").strip()
        fetch = getattr(self.tracker, "fetch_issue_detail", None)
        fetch_children = getattr(self.tracker, "fetch_children", None)
        if (
            not parent_id
            or self.workflow_store is None
            or not callable(fetch)
            or not callable(fetch_children)
        ):
            return None
        parent = fetch(parent_id)
        children = tuple(fetch_children(parent_id))
        parent_identity = str(
            getattr(parent, "identifier", "") or getattr(parent, "id", "") or ""
        ).strip()
        parent_project = str(getattr(parent, "project_id", "") or "").strip()
        if (
            parent is None
            or parent_identity != parent_id
            or str(getattr(parent, "issue_type", "") or "").strip().lower()
            != "epic"
            or (parent_project and self.project_id and parent_project != self.project_id)
        ):
            return None
        matching = tuple(
            child
            for child in children
            if str(
                getattr(child, "identifier", "")
                or getattr(child, "id", "")
                or ""
            ).strip()
            == task.identifier
            and str(getattr(child, "parent_id", "") or "").strip() == parent_id
        )
        if len(matching) != 1:
            return None
        current_child = matching[0]
        authority_child = (
            current_child
            if current_child.project_id
            else replace(current_child, project_id=self.project_id)
        )
        authority_task = (
            task if task.project_id else replace(task, project_id=self.project_id)
        )
        if issue_authority_version(authority_child) != issue_authority_version(
            authority_task
        ):
            return None
        source = self._parent_source_branch(parent)
        target = self._parent_landing_target(parent)
        if not source or not target or source == target:
            return None
        rows = self.workflow_store.latest_landing_facts_for_pair(
            project_id=self.project_id,
            task_id=parent_id,
            source=source,
            target=target,
        )
        if len(rows) != 1:
            return None
        try:
            fact = LandingFact.from_dict(rows[0])
        except (TypeError, ValueError):
            return None
        revision = self._git_revision(fact.revision)
        proof_revision = fact.proof.get("source_sha")
        if (
            fact.project_id != self.project_id
            or fact.source != source
            or fact.target != target
            or fact.state is not LandingState.LANDED
            or not fact.durable
            or revision is None
            or (
                proof_revision is not None
                and self._git_revision(proof_revision) != revision
            )
        ):
            return None
        current_parent_head = self._git_revision(issue_exact_head(parent))
        if current_parent_head is not None and current_parent_head != revision:
            return None
        if (
            not callable(self.parent_source_head_resolver)
            or self.landing_collector is None
        ):
            return None
        live_source_head = self.parent_source_head_resolver(source)
        if live_source_head is not None:
            live_source_head = self._git_revision(live_source_head)
            if live_source_head != revision:
                return None
        observed = self.landing_collector.collect(
            LandingRequest(
                source,
                target,
                revision,
                prior=fact,
                prefer_live_source=live_source_head is not None,
                authoritative_target=True,
            )
        )
        if (
            observed.project_id != self.project_id
            or observed.source != source
            or observed.target != target
            or observed.revision != revision
            or observed.state is not LandingState.LANDED
            or not observed.durable
        ):
            return None
        return target

    @staticmethod
    def _one_exact_head(values: Sequence[object]) -> tuple[str | None, bool]:
        """Return one exact revision and whether this authority class existed."""

        observed = [str(value or "").strip().lower() for value in values]
        if not observed:
            return None, False
        valid = {
            value
            for value in observed
            if re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", value)
        }
        if len(valid) != 1 or len(valid) != len(set(observed)):
            return None, True
        return next(iter(valid)), True

    def _stored_parent_head(
        self,
        parent: Issue,
        source_branch: str,
    ) -> tuple[str | None, bool]:
        if self.workflow_store is None:
            return None, False
        try:
            raw_facts = self.workflow_store.latest_landing_facts(
                project_id=self.project_id,
                task_id=parent.identifier,
                limit=100,
            )
        except Exception:  # noqa: BLE001 - durable evidence boundary
            return None, True
        revisions = []
        expected_target = self._parent_landing_target(parent)
        for raw in raw_facts:
            try:
                fact = LandingFact.from_dict(raw)
            except (TypeError, ValueError):
                return None, True
            if (
                fact.source == source_branch
                and (not expected_target or fact.target == expected_target)
                and fact.state is LandingState.LANDED
                and fact.durable
            ):
                revisions.append(fact.revision)
        return self._one_exact_head(revisions)

    def _queue_parent_head(
        self,
        parent: Issue,
        source_branch: str,
    ) -> tuple[str | None, bool]:
        get_row = getattr(self.integration_queue, "get", None)
        if not callable(get_row):
            return None, False
        try:
            row = get_row(self.project_id, parent.identifier)
        except Exception:  # noqa: BLE001 - durable evidence boundary
            return None, True
        if row is None:
            return None, False
        if str(getattr(row, "state", "") or "").strip().lower() != "integrated":
            return None, False
        if (
            str(getattr(row, "project_id", "") or "").strip() != self.project_id
            or str(getattr(row, "task_id", "") or "").strip()
            != parent.identifier
            or str(getattr(row, "task_branch", "") or "").strip()
            != source_branch
        ):
            return None, True
        expected_target = self._parent_landing_target(parent)
        row_target = str(getattr(row, "base_branch", "") or "").strip()
        if expected_target and row_target and row_target != expected_target:
            return None, True
        return self._one_exact_head(
            (
                getattr(row, "integrated_sha", None)
                or getattr(row, "head_sha", None),
            )
        )

    def _terminal_audit_parent_head(
        self,
        parent: Issue,
        source_branch: str,
    ) -> tuple[str | None, bool, str | None]:
        get_metadata = getattr(self.tracker, "get_metadata", None)
        if not callable(get_metadata):
            return None, False, None
        try:
            metadata = get_metadata(parent.identifier) or {}
            raw = metadata.get(METADATA_KEY) if isinstance(metadata, Mapping) else None
            if raw is None:
                return None, False, None
            document = TerminalAuditMetadata.from_dict(raw)
        except Exception:  # noqa: BLE001 - malformed authority fails closed
            return None, True, None
        if document.is_quarantined:
            return None, True, None
        current = canonicalize_status(parent.state)
        expected_target = (
            TargetState.ARCHIVED if current == ARCHIVED else TargetState.MERGED
        )
        current_fingerprint = compute_issue_evidence_fingerprint(
            parent, self.project_id
        )
        candidates: list[str] = []
        audit_ids: list[str] = []
        for record in document.pending_chain:
            if (
                record.project_id != self.project_id
                or record.task_id != parent.identifier
                or record.target_state is not expected_target
                or record.request_state is not RequestState.COMPLETED
                or record.evidence_fingerprint != current_fingerprint
            ):
                continue
            if record.selected_sha is None:
                # Older audit records predate exact revision binding. They are
                # not contradictory; a lower-priority exact forge receipt may
                # still provide the one-time backfill.
                continue
            selected_ref = str(record.selected_ref or "").strip()
            immutable_ref = self._git_revision(selected_ref)
            accepted_refs = {
                source_branch,
                f"origin/{source_branch}",
                f"refs/heads/{source_branch}",
                f"refs/remotes/origin/{source_branch}",
            }
            if not (
                selected_ref in accepted_refs
                or (
                    immutable_ref is not None
                    and immutable_ref == str(record.selected_sha).strip().lower()
                )
            ):
                return None, True, None
            if not any(
                attempt.verdict is Verdict.PASS
                and attempt.request_state is RequestState.COMPLETED
                and attempt.selected_ref == record.selected_ref
                and attempt.selected_sha == record.selected_sha
                for attempt in record.attempts
            ):
                return None, True, None
            candidates.append(record.selected_sha)
            audit_ids.append(record.audit_id)
        revision, present = self._one_exact_head(candidates)
        return revision, present, audit_ids[-1] if revision and audit_ids else None

    def _forge_parent_head(
        self,
        parent: Issue,
        source_branch: str,
    ) -> tuple[str | None, bool, str | None]:
        if not callable(self.forge_review_resolver):
            return None, False, None
        cache = getattr(self._observation_state, "forge_reviews", None)
        if cache is not None and source_branch in cache:
            review = cache[source_branch]
        else:
            try:
                review = self.forge_review_resolver(source_branch)
            except Exception:  # noqa: BLE001 - forge evidence boundary
                return None, True, None
            if cache is not None:
                cache[source_branch] = review
        if review is None:
            return None, False, None
        expected_target = self._parent_landing_target(parent)
        if (
            str(getattr(review, "state", "") or "").strip().lower() != "merged"
            or str(getattr(review, "source_branch", "") or "").strip()
            != source_branch
            or (
                expected_target
                and str(getattr(review, "target_branch", "") or "").strip()
                != expected_target
            )
        ):
            return None, True, None
        revision, present = self._one_exact_head((getattr(review, "head_sha", None),))
        return revision, present, str(getattr(review, "id", "") or "").strip() or None

    def _persist_parent_head(
        self,
        parent: Issue,
        *,
        source_branch: str,
        revision: str,
        kind: str,
        authority_id: str | None,
    ) -> bool:
        if self.workflow_store is None:
            return True
        target = self._parent_landing_target(parent)
        if not target:
            return False
        proof: dict[str, Any] = {
            "kind": kind,
            "source_sha": revision,
            "authority": "terminal_parent_head_backfill",
        }
        if authority_id:
            proof["authority_id"] = authority_id
        fact = LandingFact(
            source_branch,
            target,
            revision,
            proof,
            datetime.now(timezone.utc).isoformat(),
            self.project_id,
            state=LandingState.LANDED,
            durable=True,
        )
        try:
            self.workflow_store.record_landing_facts(
                project_id=self.project_id,
                task_id=parent.identifier,
                facts=(fact.to_dict(),),
            )
        except Exception:  # noqa: BLE001 - persistence is required authority
            return False
        return True

    def _trusted_terminal_parent_head(
        self,
        parent: Issue,
        source_branch: str,
    ) -> str | None:
        cache = getattr(self._observation_state, "parent_heads", None)
        cache_key = (
            parent.identifier,
            issue_authority_version(parent),
            source_branch,
        )
        if cache is not None and cache_key in cache:
            return cache[cache_key]
        result = self._trusted_terminal_parent_head_uncached(parent, source_branch)
        if cache is not None:
            cache[cache_key] = result
        return result

    def _trusted_terminal_parent_head_uncached(
        self,
        parent: Issue,
        source_branch: str,
    ) -> str | None:
        if canonicalize_status(parent.state) not in {MERGED, ARCHIVED}:
            return None
        integration = getattr(parent, "integration", None)
        integration_state = str(
            integration.get("state", "")
            if isinstance(integration, Mapping)
            else getattr(integration, "state", "")
        ).strip().lower()
        if integration_state in ACCEPTED_SUBMISSION_STATES:
            revision, _present = self._one_exact_head((issue_exact_head(parent),))
            return revision

        revision, present = self._stored_parent_head(parent, source_branch)
        if present:
            return revision

        queue_revision, queue_present = self._queue_parent_head(
            parent, source_branch
        )
        if queue_present and queue_revision is None:
            return None
        audit_revision, audit_present, audit_id = self._terminal_audit_parent_head(
            parent, source_branch
        )
        if audit_present and audit_revision is None:
            return None
        forge_revision, forge_present, review_id = self._forge_parent_head(
            parent, source_branch
        )
        authorities = (
            ("merge_commit", "integration_queue", queue_revision, queue_present),
            ("terminal_audit", audit_id, audit_revision, audit_present),
            ("forge_merge", review_id, forge_revision, forge_present),
        )
        if forge_present and forge_revision is None:
            return None
        exact = {
            revision
            for _, _, revision, present in authorities
            if present and revision is not None
        }
        if len(exact) != 1:
            return None
        revision = next(iter(exact))
        kind, authority_id, _, _ = next(
            authority
            for authority in authorities
            if authority[3] and authority[2] == revision
        )
        if self._persist_parent_head(
            parent,
            source_branch=source_branch,
            revision=revision,
            kind=kind,
            authority_id=authority_id,
        ):
            return revision
        return None

    @staticmethod
    def _record_value(task: Issue) -> dict[str, Any]:
        integration = task.integration
        if integration is None:
            return {}
        if hasattr(integration, "to_dict"):
            value = integration.to_dict()
            return dict(value) if isinstance(value, Mapping) else {}
        return dict(integration) if isinstance(integration, Mapping) else {}

    def _queue_row(self, task: Issue) -> Any | None:
        get_row = getattr(self.integration_queue, "get", None)
        if not callable(get_row):
            return None
        project_id = str(task.project_id or self.project_id or "").strip()
        if not project_id:
            return None
        try:
            row = get_row(project_id, task.identifier)
        except Exception:  # noqa: BLE001 - durable evidence boundary
            return None
        if row is None:
            return None
        row_project = str(getattr(row, "project_id", "") or "").strip()
        row_task = str(getattr(row, "task_id", "") or "").strip()
        if row_project != project_id or row_task != task.identifier:
            return None
        parent_id = str(task.parent_id or "").strip()
        row_parent = str(getattr(row, "epic_id", "") or "").strip()
        if parent_id and row_parent != parent_id:
            # A row from an earlier parent generation cannot supply source or
            # target authority for the task's current containment snapshot.
            return None
        return row

    def _parent_scoped_child_landing(
        self,
        task: Issue,
        *,
        source_candidates: Sequence[object],
        target: str,
        revision_candidates: Sequence[object],
        authoritative_issues: Mapping[str, Issue] | None = None,
        authoritative_children: Mapping[str, Sequence[Issue]] | None = None,
    ) -> LandingFact | None:
        """Return one current parent-owned landing proof for ``task``.

        Epic evaluation persists child landing facts under the epic identity,
        because one graph snapshot owns all of its direct-child obligations.
        A later Done-child integration pass must be able to consume that same
        proof after the child's mutable branch and legacy integration row have
        been pruned.  The parent store key is not authority on its own: bind
        the import to the current direct-containment snapshot, exact route,
        source, and every revision still named by current task state.
        """

        parent_id = str(task.parent_id or "").strip()
        if (
            canonicalize_status(task.state) != DONE
            or not parent_id
            or self.workflow_store is None
        ):
            return None
        try:
            if authoritative_issues is not None:
                parent = authoritative_issues.get(
                    parent_id
                ) or authoritative_issues.get(parent_id.casefold())
                children = tuple(
                    (authoritative_children or {}).get(
                        parent_id.casefold(), ()
                    )
                )
            else:
                fetch = getattr(self.tracker, "fetch_issue_detail", None)
                fetch_children = getattr(self.tracker, "fetch_children", None)
                if not callable(fetch) or not callable(fetch_children):
                    return None
                parent = fetch(parent_id)
                children = tuple(fetch_children(parent_id))
        except Exception:  # noqa: BLE001 - tracker evidence boundary
            return None
        parent_identity = str(
            getattr(parent, "identifier", "") or getattr(parent, "id", "") or ""
        ).strip()
        parent_project = str(getattr(parent, "project_id", "") or "").strip()
        if (
            parent is None
            or parent_identity != parent_id
            or str(getattr(parent, "issue_type", "") or "").strip().lower()
            != "epic"
            or (
                parent_project
                and self.project_id
                and parent_project != self.project_id
            )
        ):
            return None

        matching_children = tuple(
            child
            for child in children
            if str(
                getattr(child, "identifier", "")
                or getattr(child, "id", "")
                or ""
            ).strip()
            == task.identifier
            and str(getattr(child, "parent_id", "") or "").strip() == parent_id
            and (
                not str(getattr(child, "project_id", "") or "").strip()
                or not self.project_id
                or str(getattr(child, "project_id", "") or "").strip()
                == self.project_id
            )
        )
        if len(matching_children) != 1:
            return None
        current_child = matching_children[0]
        authority_child = (
            current_child
            if current_child.project_id
            else replace(current_child, project_id=self.project_id)
        )
        authority_task = (
            task if task.project_id else replace(task, project_id=self.project_id)
        )
        if issue_authority_version(authority_child) != issue_authority_version(
            authority_task
        ):
            # A cached task paired with a newer containment scan is not one
            # atomic authority cut.  The next complete workflow scan retries.
            return None

        expected_target = self._parent_source_branch(parent)
        if not expected_target or (target and target != expected_target):
            return None
        explicit_sources = {
            str(value or "").strip()
            for value in source_candidates
            if str(value or "").strip()
        }
        if len(explicit_sources) > 1:
            return None
        expected_source = next(iter(explicit_sources), "") or str(
            task.work_branch or task.branch_name or task.identifier
        ).strip()
        if not expected_source:
            return None

        current_revisions = {
            revision
            for value in (*revision_candidates, issue_exact_head(current_child))
            if (revision := self._git_revision(value)) is not None
        }
        if len(current_revisions) > 1:
            return None
        expected_revision = next(iter(current_revisions), None)
        try:
            raw_facts = self.workflow_store.latest_landing_facts_for_pair(
                project_id=self.project_id,
                task_id=parent_id,
                source=expected_source,
                target=expected_target,
            )
        except Exception:  # noqa: BLE001 - durable evidence boundary
            return None
        candidates: list[LandingFact] = []
        for raw in raw_facts:
            try:
                fact = LandingFact.from_dict(raw)
            except (TypeError, ValueError):
                # One corrupt parent evidence row makes this authority source
                # incomplete; do not select a convenient sibling row.
                return None
            if (
                fact.project_id == self.project_id
                and fact.source == expected_source
                and fact.target == expected_target
                and fact.state is LandingState.LANDED
                and fact.durable
            ):
                candidates.append(fact)
        if len(candidates) != 1:
            return None
        fact = candidates[0]
        revision = self._git_revision(fact.revision)
        if revision is None or (
            expected_revision is not None and revision != expected_revision
        ):
            return None
        proof_revision_value = fact.proof.get("source_sha")
        if proof_revision_value is not None and (
            self._git_revision(proof_revision_value) != revision
        ):
            return None
        return fact

    def _parent_target(
        self,
        task: Issue,
        *,
        authoritative_issues: Mapping[str, Issue] | None = None,
    ) -> tuple[str, str | None]:
        parent_id = str(task.parent_id or "").strip()
        if not parent_id:
            return "", None
        trusted_revision = None
        fetch = getattr(self.tracker, "fetch_issue_detail", None)
        if authoritative_issues is not None or callable(fetch):
            try:
                if authoritative_issues is not None:
                    parent = authoritative_issues.get(
                        parent_id
                    ) or authoritative_issues.get(parent_id.casefold())
                else:
                    parent = fetch(parent_id)
            except Exception:  # noqa: BLE001 - tracker evidence boundary
                parent = None
            parent_identity = str(
                getattr(parent, "identifier", "") or getattr(parent, "id", "") or ""
            ).strip()
            parent_project = str(getattr(parent, "project_id", "") or "").strip()
            if (
                parent is not None
                and parent_identity == parent_id
                and (
                    not parent_project
                    or not self.project_id
                    or parent_project == self.project_id
                )
            ):
                target = self._parent_source_branch(parent)
                if target:
                    trusted_revision = self._trusted_terminal_parent_head(
                        parent, target
                    )
                    return target, trusted_revision
        branch_name = getattr(self.project_store, "epic_branch_name", None)
        if callable(branch_name):
            try:
                return str(branch_name(parent_id) or "").strip(), trusted_revision
            except Exception:  # noqa: BLE001 - project configuration boundary
                return "", None
        return "", None

    def _default_target(self, task: Issue) -> str:
        explicit = str(task.target_branch or "").strip()
        if explicit:
            return explicit
        if self.project_default_branch:
            return self.project_default_branch
        get_project = getattr(self.project_store, "get", None)
        if not callable(get_project):
            return ""
        project_id = str(task.project_id or self.project_id or "").strip()
        try:
            project = get_project(project_id) if project_id else None
        except Exception:  # noqa: BLE001 - project configuration boundary
            return ""
        return str(getattr(project, "default_branch", "") or "").strip()

    def __call__(
        self,
        task: Issue,
        *,
        include_ready: bool = False,
        authoritative_issues: Mapping[str, Issue] | None = None,
        authoritative_children: Mapping[str, Sequence[Issue]] | None = None,
    ) -> tuple[LandingRequest, ...]:
        scoped_requests = getattr(self._observation_state, "requests", None)
        cache_key = (task.identifier, issue_authority_version(task), include_ready)
        if scoped_requests is not None and cache_key in scoped_requests:
            return scoped_requests[cache_key]

        value = self._record_value(task)
        row = self._queue_row(task)
        record_state = str(value.get("state") or "").strip().lower()
        row_state = str(getattr(row, "state", "") or "").strip().lower()
        integrated = record_state == "integrated" or row_state == "integrated"
        record_authoritative = include_ready or record_state == "integrated"
        queue_authoritative = include_ready or row_state == "integrated"
        record_source = (
            str(value.get("task_branch") or "").strip() if record_authoritative else ""
        )
        record_revision = (
            str(value.get("integrated_sha") or value.get("head_sha") or "").strip()
            if record_authoritative
            else ""
        )
        queue_source = (
            str(getattr(row, "task_branch", "") or "").strip()
            if queue_authoritative
            else ""
        )
        queue_revision = (
            str(
                getattr(row, "integrated_sha", "") or getattr(row, "head_sha", "") or ""
            ).strip()
            if queue_authoritative
            else ""
        )
        if record_source and record_revision:
            source, revision = record_source, record_revision
        elif queue_source and queue_revision:
            source, revision = queue_source, queue_revision
        else:
            # Preserve the existing Ready-path fallback without treating a
            # partial tracker record as exact completed-generation evidence.
            source = record_source or queue_source or str(task.work_branch or "").strip()
            revision = record_revision or queue_revision

        target = (
            str(value.get("base_branch") or "").strip() if record_authoritative else ""
        )
        if not target:
            target = (
                str(getattr(row, "base_branch", "") or "").strip()
                if queue_authoritative
                else ""
            )
        trusted_target_revision = None
        if not target:
            if str(task.parent_id or "").strip():
                target, trusted_target_revision = self._parent_target(
                    task,
                    authoritative_issues=authoritative_issues,
                )
            else:
                target = self._default_target(task)
        elif str(task.parent_id or "").strip():
            # The recorded branch remains the target authority, but a final
            # parent's exact accepted head can preserve that target generation
            # after the mutable container ref has been pruned.
            _parent_branch, trusted_target_revision = self._parent_target(
                task,
                authoritative_issues=authoritative_issues,
            )
        parent_landing = self._parent_scoped_child_landing(
            task,
            source_candidates=(
                record_source,
                queue_source,
                str(task.work_branch or "").strip(),
            ),
            target=target,
            revision_candidates=(record_revision, queue_revision),
            authoritative_issues=authoritative_issues,
            authoritative_children=authoritative_children,
        )
        if parent_landing is not None:
            source = parent_landing.source
            target = parent_landing.target
            revision = parent_landing.revision or ""
            integrated = True
        if not integrated and not include_ready:
            return ()
        if not source or not target:
            return ()
        try:
            result = (
                LandingRequest(
                    source,
                    target,
                    revision or None,
                    prior=parent_landing,
                    authoritative_target=integrated,
                    trusted_target_revision=trusted_target_revision,
                ),
            )
        except ValueError:
            result = ()
        if scoped_requests is not None:
            scoped_requests[cache_key] = result
        return result


class IntegrationWorkflowController:
    """Evaluate and schedule all Ready tasks without first-row shortcuts."""

    def __init__(
        self,
        *,
        collector: WorkflowFactCollector,
        store: WorkflowJobStore,
        scheduler: WorkflowJobScheduler | None = None,
        landing_request_resolver: Callable[..., tuple[LandingRequest, ...]]
        | None = None,
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
        self.landing_request_resolver = (
            landing_request_resolver or IntegrationLandingRequestResolver()
        )
        self.decision_limit = decision_limit
        self._latest: dict[str, IntegrationTaskDecision] = {}

    @staticmethod
    def _default_landing_request(task: Issue) -> tuple[LandingRequest, ...]:
        """Compatibility wrapper for callers without production dependencies."""

        return IntegrationLandingRequestResolver()(task)

    def landing_requests_for(
        self,
        task: Issue,
        *,
        include_ready: bool = False,
        authoritative_issues: Mapping[str, Issue] | None = None,
        authoritative_children: Mapping[str, Sequence[Issue]] | None = None,
    ) -> tuple[LandingRequest, ...]:
        resolver = self.landing_request_resolver
        requests = tuple(
            resolver(
                task,
                include_ready=include_ready,
                authoritative_issues=authoritative_issues,
                authoritative_children=authoritative_children,
            )
            if isinstance(resolver, IntegrationLandingRequestResolver)
            else resolver(task, include_ready=include_ready)
        )
        if not requests:
            return ()
        prior_by_pair: dict[tuple[str, str], LandingFact] = {}
        for raw in self.store.latest_landing_facts(
            project_id=str(task.project_id or self.collector.project_id),
            task_id=task.identifier,
            limit=self.decision_limit,
        ):
            try:
                prior = LandingFact.from_dict(raw)
            except (TypeError, ValueError):
                continue
            if prior.durable:
                prior_by_pair[(prior.source, prior.target)] = prior
        return tuple(
            replace(
                request,
                prior=(
                    request.prior
                    or prior_by_pair.get((request.source, request.target))
                ),
            )
            for request in requests
        )

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
        liveness_slo_seconds: Mapping[str, int] | None = None,
        authoritative_issues: Mapping[str, Issue] | None = None,
        authoritative_children: Mapping[str, Sequence[Issue]] | None = None,
    ) -> IntegrationDecisionBatch:
        # The window belongs to integration-owned work.  In addition to live
        # Ready submissions, the durable lane owns exact Done landing
        # terminalization and the narrowly classified direct-maintenance audit
        # handoff.  Selecting the complete task corpus first would let stable
        # unrelated rows hide these recovery obligations forever.
        normalized_tasks = (
            task
            if task.project_id
            else replace(task, project_id=self.collector.project_id)
            for task in tasks
        )
        selected = sorted(
            {
                task.identifier: task
                for task in normalized_tasks
                if canonicalize_status(task.state) in {READY_TO_INTEGRATE, DONE}
                or direct_epic_maintenance_completion_ready(task)
                or direct_epic_maintenance_handoff_ready(task)
                or is_direct_epic_maintenance_issue(task)
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
            default_requests = (
                ()
                if direct_epic_maintenance_completion_ready(task)
                or direct_epic_maintenance_handoff_ready(task)
                else self.landing_requests_for(
                    task,
                    authoritative_issues=authoritative_issues,
                    authoritative_children=authoritative_children,
                )
            )
            task_requests = tuple(
                requests.get(
                    task.identifier,
                    default_requests,
                )
            )
            facts = self.collector.collect(
                task.identifier,
                landing_requests=task_requests,
                authoritative_issues=authoritative_issues,
                authoritative_children=authoritative_children,
            )
            terminal_value = facts.fact(FactDomain.TERMINAL_AUDIT).value
            owner_delivery = (
                terminal_value.get("owner_delivery")
                if isinstance(terminal_value, Mapping)
                else None
            )
            if (
                not task_requests
                and canonicalize_status(task.state) == DONE
                and isinstance(owner_delivery, Mapping)
            ):
                # A direct owner can terminalize an exact accepted generation
                # before the ordinary integration row reaches ``integrated``.
                # Resolve that generation through the same include-ready
                # source/target policy, then recollect: the fact collector
                # still requires an exact provenance/request tuple match.
                owner_requests = self.landing_requests_for(
                    task,
                    include_ready=True,
                    authoritative_issues=authoritative_issues,
                    authoritative_children=authoritative_children,
                )
                if owner_requests:
                    task_requests = owner_requests
                    facts = self.collector.collect(
                        task.identifier,
                        landing_requests=task_requests,
                        authoritative_issues=authoritative_issues,
                        authoritative_children=authoritative_children,
                    )
            evaluated.append(
                IntegrationTaskDecision(
                    task,
                    facts,
                    evaluate_task(
                        task,
                        facts,
                        liveness_slo_seconds=liveness_slo_seconds,
                    ),
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


class IntegrationActionBackend(Protocol):
    """Task-scoped backend for the seven production integration actions.

    Unlike :class:`IntegrationWorkflowBackend`, this contract never assumes
    that every integration job means "run Git integration".  Maintenance,
    terminal staging, forge delivery, and recovery each receive their exact
    action identity and must return an independently verifiable receipt.
    """

    def revalidate_action(
        self, action: str, context: WorkflowJobContext
    ) -> RevalidationResult | Awaitable[RevalidationResult]: ...

    def observe_action(
        self, action: str, context: WorkflowJobContext
    ) -> EffectObservation | Awaitable[EffectObservation]: ...

    def apply_action(
        self, action: str, context: WorkflowJobContext
    ) -> EffectResult | Awaitable[EffectResult]: ...

    def verify_action(
        self,
        action: str,
        context: WorkflowJobContext,
        effect: EffectResult,
    ) -> VerificationResult | Awaitable[VerificationResult]: ...

    def build_action_transition(
        self,
        action: str,
        context: WorkflowJobContext,
        verification: VerificationResult,
    ) -> TransitionIntent | None | Awaitable[TransitionIntent | None]: ...


async def _resolve(value: Any) -> Any:
    return await value if inspect.isawaitable(value) else value


async def _invoke_backend(method: Any, *args: Any) -> Any:
    """Invoke synchronous adapters off the event loop, then await if needed."""

    if inspect.iscoroutinefunction(method):
        return await method(*args)
    value = await asyncio.to_thread(method, *args)
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


class IntegrationActionHandler:
    """Action-specific production handler with no implicit Git side effect."""

    def __init__(
        self,
        action: str,
        backend: IntegrationActionBackend,
        *,
        domain: WorkflowActionDomain,
        operation_timeout_seconds: float | None = None,
    ) -> None:
        normalized = str(action or "").strip()
        if normalized not in INTEGRATION_ACTIONS:
            raise ValueError(f"unknown integration workflow action: {normalized!r}")
        self.action = normalized
        self.backend = backend
        self.domain = WorkflowActionDomain(domain)
        if operation_timeout_seconds is not None:
            timeout = float(operation_timeout_seconds)
            if timeout <= 0:
                raise ValueError("operation_timeout_seconds must be positive")
            self.operation_timeout_seconds = timeout

    async def revalidate(self, context: WorkflowJobContext) -> RevalidationResult:
        result = await _invoke_backend(
            self.backend.revalidate_action,
            self.action,
            context,
        )
        if not isinstance(result, RevalidationResult):
            raise WorkflowActionError(
                f"{self.action} returned invalid revalidation",
                category=WorkflowFailureCategory.PERMANENT,
                retryable=False,
            )
        return result

    async def inspect(self, context: WorkflowJobContext) -> EffectObservation:
        result = await _invoke_backend(
            self.backend.observe_action,
            self.action,
            context,
        )
        if not isinstance(result, EffectObservation):
            raise WorkflowActionError(
                f"{self.action} returned invalid effect observation",
                category=WorkflowFailureCategory.PERMANENT,
                retryable=False,
            )
        return result

    async def apply(self, context: WorkflowJobContext) -> EffectResult:
        result = await _invoke_backend(
            self.backend.apply_action,
            self.action,
            context,
        )
        if not isinstance(result, EffectResult):
            raise WorkflowActionError(
                f"{self.action} returned invalid effect receipt",
                category=WorkflowFailureCategory.PERMANENT,
                retryable=False,
            )
        return result

    async def verify(
        self, context: WorkflowJobContext, effect: EffectResult
    ) -> VerificationResult:
        result = await _invoke_backend(
            self.backend.verify_action,
            self.action,
            context,
            effect,
        )
        if not isinstance(result, VerificationResult):
            raise WorkflowActionError(
                f"{self.action} returned invalid verification",
                category=WorkflowFailureCategory.PERMANENT,
                retryable=False,
            )
        return result

    async def build_transition(
        self,
        context: WorkflowJobContext,
        verification: VerificationResult,
    ) -> TransitionIntent | None:
        return await _invoke_backend(
            self.backend.build_action_transition,
            self.action,
            context,
            verification,
        )

    async def completion_landing_facts(
        self,
        context: WorkflowJobContext,
        verification: VerificationResult,
    ) -> tuple[dict[str, Any], ...]:
        """Return exact immutable evidence for the worker's success commit."""

        if self.action != "integration_landing_refresh":
            return ()
        receipt = verification.receipt
        expected_receipt = {
            "action": self.action,
            "project_id": context.job.project_id,
            "task_id": context.job.task_id,
            "job_generation": context.job.generation,
        }
        if any(receipt.get(key) != value for key, value in expected_receipt.items()):
            raise WorkflowActionError(
                "landing completion receipt no longer matches job authority",
                category=WorkflowFailureCategory.STALE_EVIDENCE,
                retryable=True,
            )
        raw_landing = receipt.get("landing")
        if not isinstance(raw_landing, Mapping):
            raise WorkflowActionError(
                "landing completion receipt lacks exact proof",
                category=WorkflowFailureCategory.STALE_EVIDENCE,
                retryable=True,
            )
        try:
            landing = LandingFact.from_dict(raw_landing)
        except (TypeError, ValueError) as exc:
            raise WorkflowActionError(
                "landing completion proof revision is invalid",
                category=WorkflowFailureCategory.STALE_EVIDENCE,
                retryable=True,
            ) from exc
        details = OrchestratorIntegrationActionBackend._revalidation_details(context)
        revalidated_evidence = (
            OrchestratorIntegrationActionBackend._revalidated_evidence_revision(
                context
            )
        )
        expected_revision = str(
            details.get("landing_revision")
            or details.get("task_head")
            or context.job.expected_head_sha
            or ""
        ).strip()
        expected_source = str(details.get("landing_source") or "").strip()
        expected_target = str(details.get("landing_target") or "").strip()
        expected_evidence = str(
            context.job.expected_evidence_revision or ""
        ).strip()
        if (
            landing.project_id != context.job.project_id
            or landing.state is not LandingState.LANDED
            or not landing.durable
            or (expected_source and landing.source != expected_source)
            or (expected_target and landing.target != expected_target)
            or (expected_revision and landing.revision != expected_revision)
            or (expected_evidence and revalidated_evidence != expected_evidence)
        ):
            raise WorkflowActionError(
                "landing completion proof is stale or outside job scope",
                category=WorkflowFailureCategory.STALE_EVIDENCE,
                retryable=True,
            )
        return (landing.to_dict(),)


_INTEGRATION_ACTION_DOMAINS = {
    "direct_epic_maintenance_completion": WorkflowActionDomain.GIT,
    "epic_branch_reconciliation": WorkflowActionDomain.GIT,
    "historical_audit_replay_batch": WorkflowActionDomain.AUDIT,
    "integration_attempt": WorkflowActionDomain.GIT,
    "integration_landing_refresh": WorkflowActionDomain.GIT,
    "integration_recovery": WorkflowActionDomain.TRACKER,
    "integration_terminal_stage": WorkflowActionDomain.AUDIT,
    "parent_rollup_review": WorkflowActionDomain.TRACKER,
    "standalone_delivery": WorkflowActionDomain.FORGE,
    "terminal_audit_done": WorkflowActionDomain.TRACKER,
}
_POST_INTEGRATION_STATES = frozenset(
    {IN_REVIEW, IN_VALIDATION, DONE, MERGED, ARCHIVED}
)


class OrchestratorIntegrationActionBackend:
    """Production adapter for exact, durable integration jobs.

    The adapter intentionally uses only task-addressable operations.  It may
    read a complete dependency graph, but it never invokes the legacy queue,
    standalone, or maintenance sweeps for a single workflow job.
    """

    def __init__(self, orchestrator: Any, binding: Any) -> None:
        self.orchestrator = orchestrator
        self.binding = binding
        self.project_id = str(binding.project_id)
        self.tracker = binding.tracker
        controller = getattr(binding, "integration_controller", None)
        self.integration_controller = controller
        resolver = getattr(controller, "landing_request_resolver", None)
        self.landing_request_resolver = (
            resolver
            if callable(resolver)
            else IntegrationLandingRequestResolver(
                project_id=self.project_id,
                tracker=self.tracker,
                integration_queue=getattr(orchestrator, "integration_queue", None),
                project_store=getattr(orchestrator, "project_store", None),
                project_default_branch=self._project_default_branch(),
            )
        )

    def _project_default_branch(self) -> str:
        store = getattr(self.orchestrator, "project_store", None)
        get_project = getattr(store, "get", None)
        project = get_project(self.project_id) if callable(get_project) else None
        return str(getattr(project, "default_branch", "") or "").strip()

    def _issue(self, context: WorkflowJobContext) -> Issue | None:
        if context.job.project_id != self.project_id:
            return None
        issue = self.tracker.fetch_issue_detail(context.job.task_id)
        # Native Markdown tasks omit their project id because the tracker is
        # already project-scoped.  Normalize that representation before
        # computing the transition CAS token so it agrees with
        # TaskTransitionService._fetch().
        if issue is not None and not issue.project_id:
            issue.project_id = self.project_id
        return issue

    def _fresh_issue(self, context: WorkflowJobContext) -> Issue | None:
        invalidate = getattr(self.tracker, "invalidate_read_cache", None)
        if callable(invalidate):
            invalidate()
        return self._issue(context)

    @staticmethod
    def _record(issue: Issue | None) -> Any:
        return getattr(issue, "integration", None) if issue is not None else None

    def _landing_request(
        self, issue: Issue, *, include_ready: bool = False
    ) -> tuple[LandingRequest, ...]:
        resolve = getattr(self.integration_controller, "landing_requests_for", None)
        if callable(resolve):
            return tuple(resolve(issue, include_ready=include_ready))
        return tuple(self.landing_request_resolver(issue, include_ready=include_ready))

    def _post_landed_parent_target(self, issue: Issue | None) -> str | None:
        resolve = getattr(
            self.landing_request_resolver,
            "post_landed_parent_target",
            None,
        )
        if issue is None or not callable(resolve):
            return None
        try:
            return str(resolve(issue) or "").strip() or None
        except Exception:  # noqa: BLE001 - routing evidence fails closed
            return None

    def _standalone_route_is_current(self, issue: Issue | None, record: Any) -> bool:
        if issue is None or record is None:
            return False
        if not str(getattr(issue, "parent_id", "") or "").strip():
            return True
        target = self._post_landed_parent_target(issue)
        return bool(
            target
            and str(getattr(record, "post_landed_parent_id", "") or "").strip()
            == str(getattr(issue, "parent_id", "") or "").strip()
            and str(getattr(issue, "target_branch", "") or "").strip() == target
            and str(getattr(record, "base_branch", "") or "").strip() == target
        )

    def _current_parent_queue_target(self, issue: Issue | None) -> str | None:
        resolve = getattr(
            self.landing_request_resolver,
            "current_parent_queue_target",
            None,
        )
        if issue is None or not callable(resolve):
            return None
        try:
            return str(resolve(issue) or "").strip() or None
        except Exception:  # noqa: BLE001 - recovery authority fails closed
            return None

    def _project_route_authority_lock(self):
        store = getattr(self.landing_request_resolver, "project_store", None)
        if store is None:
            store = getattr(self.orchestrator, "project_store", None)
        lock_factory = getattr(store, "project_write_lock", None)
        return (
            lock_factory(self.project_id)
            if callable(lock_factory)
            else contextlib.nullcontext()
        )

    def _reclassify_invalid_parented_standalone(
        self,
        context: WorkflowJobContext,
        issue: Issue,
        record: IntegrationRecord,
        *,
        expected_branch: str,
        expected_head: str,
    ) -> None:
        """Return stale post-parent standalone authority to natural routing.

        The tracker is the accepted-submission authority and is intentionally
        written before the SQLite queue. The replacement integration-attempt
        generation owns exact absent/cancelled queue repair, avoiding a
        cross-store transaction or a queue-to-project lock inversion.
        """

        parent_id = str(getattr(issue, "parent_id", "") or "").strip()
        if (
            not parent_id
            or record.mode != "standalone"
            or str(record.post_landed_parent_id or "").strip() != parent_id
            or record.task_branch != expected_branch
            or record.head_sha != expected_head
        ):
            raise WorkflowActionError(
                "standalone route changed outside compensable parent authority",
                category=WorkflowFailureCategory.STALE_EVIDENCE,
                retryable=True,
            )

        # _exact_standalone_submission already holds the issue-transition lock.
        # Take the project lock next and retain it through the final route check
        # and tracker writes. Parent Git authority cannot cross this cut.
        with self._project_route_authority_lock():
            context.check_interrupted()
            current_issue = self._fresh_issue(context)
            current_record = self._record(current_issue)
            if (
                current_issue is None
                or not isinstance(current_record, IntegrationRecord)
                or canonicalize_status(current_issue.state)
                != READY_TO_INTEGRATE
                or str(getattr(current_issue, "parent_id", "") or "").strip()
                != parent_id
                or current_record.mode != "standalone"
                or str(current_record.post_landed_parent_id or "").strip()
                != parent_id
                or current_record.task_branch != expected_branch
                or current_record.head_sha != expected_head
            ):
                raise WorkflowActionError(
                    "standalone route changed before parent authority fencing",
                    category=WorkflowFailureCategory.STALE_EVIDENCE,
                    retryable=True,
                )

            landed_target = self._post_landed_parent_target(current_issue)
            if landed_target:
                # The inverse race won before the compensation cut. Preserve
                # standalone authority, retargeting only if the parent's actual
                # immediate destination changed.
                if (
                    str(getattr(current_issue, "target_branch", "") or "").strip()
                    != landed_target
                    or current_record.base_branch != landed_target
                ):
                    self.tracker.set_metadata_field(
                        context.job.task_id,
                        "oompah.target_branch",
                        landed_target,
                    )
                    current_issue = self._fresh_issue(context)
                    current_record = self._record(current_issue)
                    if (
                        current_issue is None
                        or not isinstance(current_record, IntegrationRecord)
                        or self._post_landed_parent_target(current_issue)
                        != landed_target
                        or current_record.mode != "standalone"
                        or str(
                            current_record.post_landed_parent_id or ""
                        ).strip()
                        != parent_id
                        or current_record.task_branch != expected_branch
                        or current_record.head_sha != expected_head
                    ):
                        raise WorkflowActionError(
                            "parent re-landing changed during standalone retargeting",
                            category=WorkflowFailureCategory.STALE_EVIDENCE,
                            retryable=True,
                        )
                    self.tracker.set_metadata_field(
                        context.job.task_id,
                        "oompah.integration",
                        replace(
                            current_record,
                            base_branch=landed_target,
                            base_sha=None,
                        ).to_dict(),
                    )
                current_issue = self._fresh_issue(context)
                current_record = self._record(current_issue)
                facts = self.binding.collector.collect(
                    context.job.task_id,
                    landing_requests=(
                        self._landing_request(current_issue)
                        if current_issue is not None
                        else ()
                    ),
                )
                decision = (
                    evaluate_task(current_issue, facts)
                    if current_issue is not None
                    else None
                )
                if (
                    current_issue is None
                    or current_record is None
                    or not self._standalone_route_is_current(
                        current_issue,
                        current_record,
                    )
                    or decision is None
                    or "standalone_delivery" not in decision.durable_jobs
                ):
                    raise WorkflowActionError(
                        "re-landed parent standalone route is not observable",
                        category=WorkflowFailureCategory.TRANSIENT,
                        retryable=True,
                    )
                self._request_refresh()
                raise WorkflowActionSuperseded(
                    "parent landing became current before queue compensation",
                    replacement_generation=(
                        f"standalone:{decision.decision_revision}"
                    ),
                )

            queue_target = self._current_parent_queue_target(current_issue)
            if (
                not queue_target
                or self._post_landed_parent_target(current_issue) is not None
            ):
                raise WorkflowActionError(
                    "stale standalone parent route could not be fenced",
                    category=WorkflowFailureCategory.TRANSIENT,
                    retryable=True,
                )
            self.tracker.set_metadata_field(
                context.job.task_id,
                "oompah.target_branch",
                queue_target,
            )
            targeted = self._fresh_issue(context)
            targeted_record = self._record(targeted)
            if (
                targeted is None
                or not isinstance(targeted_record, IntegrationRecord)
                or str(getattr(targeted, "parent_id", "") or "").strip()
                != parent_id
                or str(getattr(targeted, "target_branch", "") or "").strip()
                != queue_target
                or self._current_parent_queue_target(targeted) != queue_target
                or self._post_landed_parent_target(targeted) is not None
                or targeted_record.mode != "standalone"
                or str(targeted_record.post_landed_parent_id or "").strip()
                != parent_id
                or targeted_record.task_branch != expected_branch
                or targeted_record.head_sha != expected_head
            ):
                raise WorkflowActionError(
                    "stale standalone target changed during queue compensation",
                    category=WorkflowFailureCategory.STALE_EVIDENCE,
                    retryable=True,
                )
            self.tracker.set_metadata_field(
                context.job.task_id,
                "oompah.integration",
                replace(
                    targeted_record,
                    mode="queue",
                    post_landed_parent_id=None,
                    base_branch=queue_target,
                    base_sha=None,
                ).to_dict(),
            )
            current_issue = self._fresh_issue(context)
            current_record = self._record(current_issue)
            facts = self.binding.collector.collect(
                context.job.task_id,
                landing_requests=(
                    self._landing_request(current_issue)
                    if current_issue is not None
                    else ()
                ),
            )
            decision = (
                evaluate_task(current_issue, facts)
                if current_issue is not None
                else None
            )
            if (
                current_issue is None
                or not isinstance(current_record, IntegrationRecord)
                or current_record.mode != "queue"
                or current_record.post_landed_parent_id is not None
                or current_record.base_branch != queue_target
                or current_record.base_sha is not None
                or self._post_landed_parent_target(current_issue) is not None
                or decision is None
                or "integration_attempt" not in decision.durable_jobs
            ):
                raise WorkflowActionError(
                    "parent queue compensation is not observable",
                    category=WorkflowFailureCategory.TRANSIENT,
                    retryable=True,
                )
            self._request_refresh()
            raise WorkflowActionSuperseded(
                "stale standalone delivery returned to its current parent queue",
                replacement_generation=f"queue-parent:{decision.decision_revision}",
            )

    def _reclassify_queue_submission_if_needed(
        self,
        context: WorkflowJobContext,
        *,
        observed_present: bool,
        observed_generation: str,
        observed_parent: str,
        expected_branch: str,
        expected_head: str,
        expected_evidence: str,
    ) -> None:
        """Move an exact queue record to standalone without lock inversion."""

        with self._project_route_authority_lock():
            context.check_interrupted()
            issue = self._fresh_issue(context)
            record = self._record(issue)
            if (
                issue is None
                or not isinstance(record, IntegrationRecord)
                or canonicalize_status(issue.state) != READY_TO_INTEGRATE
                or is_direct_epic_maintenance_issue(issue)
                or record.mode != "queue"
                or str(record.state or "").strip().lower() != "ready"
                or record.task_branch != expected_branch
                or record.head_sha != expected_head
            ):
                return
            parent_id = str(getattr(issue, "parent_id", "") or "").strip()
            if parent_id != observed_parent:
                return
            post_landed_target = (
                self._post_landed_parent_target(issue) if parent_id else None
            )
            if parent_id and not post_landed_target:
                return
            project_store = getattr(self.orchestrator, "project_store", None)
            get_project = getattr(project_store, "get", None)
            try:
                project = (
                    get_project(self.project_id) if callable(get_project) else None
                )
            except Exception as exc:  # noqa: BLE001 - project lookup boundary
                raise WorkflowActionError(
                    f"standalone target project is unavailable: {exc}",
                    category=WorkflowFailureCategory.TRANSIENT,
                    retryable=True,
                ) from exc
            standalone_base = str(
                post_landed_target
                or getattr(issue, "target_branch", "")
                or getattr(project, "default_branch", "")
                or ""
            ).strip()
            original_target = str(
                getattr(issue, "target_branch", "") or ""
            ).strip()
            if not standalone_base:
                raise WorkflowActionError(
                    "queue delivery has no standalone target branch",
                    category=WorkflowFailureCategory.PERMANENT,
                    retryable=False,
                )
            facts = self.binding.collector.collect(
                issue.identifier,
                landing_requests=self._landing_request(issue),
            )
            decision = evaluate_task(issue, facts)
            if (
                decision.evidence_revision != expected_evidence
                or "integration_attempt" not in decision.durable_jobs
            ):
                raise WorkflowActionError(
                    "integration attempt evidence changed before reclassification",
                    category=WorkflowFailureCategory.STALE_EVIDENCE,
                    retryable=True,
                )
            queue = self.orchestrator.integration_queue
            row = queue.get(self.project_id, context.job.task_id)
            if row is None:
                if observed_present or observed_generation:
                    raise WorkflowActionError(
                        "queue generation disappeared before reclassification",
                        category=WorkflowFailureCategory.STALE_EVIDENCE,
                        retryable=True,
                    )
            elif (
                not observed_generation
                or row.authority_generation() != observed_generation
                or row.state != "ready"
                or row.lease_owner is not None
                or row.rebase_intent_pending
                or row.rebased_publication_pending
                or row.task_branch != expected_branch
                or row.head_sha != expected_head
                or (parent_id and row.epic_id != parent_id)
            ):
                raise WorkflowActionError(
                    "queue generation changed before reclassification",
                    category=WorkflowFailureCategory.STALE_EVIDENCE,
                    retryable=True,
                )

            if post_landed_target:
                self.tracker.set_metadata_field(
                    context.job.task_id,
                    "oompah.target_branch",
                    standalone_base,
                )
                issue = self._fresh_issue(context)
                record = self._record(issue)
                if (
                    issue is None
                    or not isinstance(record, IntegrationRecord)
                    or str(getattr(issue, "parent_id", "") or "").strip()
                    != parent_id
                    or str(getattr(issue, "target_branch", "") or "").strip()
                    != standalone_base
                    or self._post_landed_parent_target(issue) != standalone_base
                    or record.mode != "queue"
                    or record.task_branch != expected_branch
                    or record.head_sha != expected_head
                ):
                    raise WorkflowActionError(
                        "parent landing changed during tracker-first reclassification",
                        category=WorkflowFailureCategory.STALE_EVIDENCE,
                        retryable=True,
                    )
            self.tracker.set_metadata_field(
                context.job.task_id,
                "oompah.integration",
                replace(
                    record,
                    mode="standalone",
                    post_landed_parent_id=(parent_id or None),
                    base_branch=standalone_base,
                    base_sha=None,
                ).to_dict(),
            )
            if row is None:
                retired = queue.run_if_absent(
                    self.project_id,
                    context.job.task_id,
                    action=lambda: True,
                )
            else:
                retired = (
                    queue.retire_task_generation(
                        self.project_id,
                        context.job.task_id,
                        expected_generation=observed_generation,
                        reason=STANDALONE_RECLASSIFICATION_REASON,
                    )
                    is not None
                )
            if not retired:
                # The tracker-first write is safe while the row remains
                # unclaimable by current metadata, but an exact queue CAS can
                # still lose to a concurrent generation. Restore the accepted
                # queue record before yielding; a process exit during this
                # rollback is handled by the same partial-write repair path.
                if post_landed_target:
                    self.tracker.set_metadata_field(
                        context.job.task_id,
                        "oompah.target_branch",
                        original_target,
                    )
                self.tracker.set_metadata_field(
                    context.job.task_id,
                    "oompah.integration",
                    record.to_dict(),
                )
                raise WorkflowActionError(
                    "queue authority changed after tracker-first reclassification",
                    category=WorkflowFailureCategory.STALE_EVIDENCE,
                    retryable=True,
                )
            current_issue = self._fresh_issue(context)
            current_record = self._record(current_issue)
            current_facts = self.binding.collector.collect(
                context.job.task_id,
                landing_requests=(
                    self._landing_request(current_issue)
                    if current_issue is not None
                    else ()
                ),
            )
            replacement = (
                evaluate_task(current_issue, current_facts)
                if current_issue is not None
                else None
            )
            if (
                current_issue is None
                or not isinstance(current_record, IntegrationRecord)
                or not self._standalone_route_is_current(
                    current_issue,
                    current_record,
                )
                or replacement is None
                or "standalone_delivery" not in replacement.durable_jobs
            ):
                raise WorkflowActionError(
                    "standalone delivery reclassification is not observable",
                    category=WorkflowFailureCategory.TRANSIENT,
                    retryable=True,
                )
            self._request_refresh()
            raise WorkflowActionSuperseded(
                (
                    "queued delivery was reclassified because its parent landed"
                    if post_landed_target
                    else "queued delivery was reclassified after parent removal"
                ),
                replacement_generation=(
                    f"standalone:{replacement.decision_revision}"
                ),
            )

    def _landing(self, issue: Issue) -> LandingFact | None:
        requests = self._landing_request(issue, include_ready=True)
        if not requests:
            return None
        # Keep recovery bound to the immutable accepted revision.  The Git
        # collector proves rebases through complete patch-id equivalence, so
        # resolving the live source ref here would only risk adopting an
        # unrelated branch advance after an executor crash.
        return self.binding.collector.collect(
            issue.identifier,
            landing_requests=requests,
        ).landings[0]

    def _rollup_head_authority(
        self,
        issue: Issue,
        *,
        requests: Sequence[LandingRequest],
        facts: WorkflowFacts,
        decision: WorkDecision,
    ) -> _RollupHeadAuthority | None:
        """Resolve the exact head a parent-rollup transition may consume.

        Ordinary submissions remain fenced by their tracker-owned accepted
        head.  A composed Done child can lack that mutable submission record
        after its commit is absorbed into the epic branch.  In that one case,
        accept only the canonical parent-scoped durable landing fact already
        revalidated by ``IntegrationLandingRequestResolver``.
        """

        tracker_head = str(issue_exact_head(issue) or "").strip().lower()
        if tracker_head:
            return _RollupHeadAuthority(tracker_head, "accepted_submission")
        if (
            canonicalize_status(issue.state) != DONE
            or not str(issue.parent_id or "").strip()
            or decision.reason_code
            != "terminal.immediate_target_landing_proven"
            or "parent_rollup_review" not in decision.durable_jobs
            or len(requests) != 1
        ):
            return None
        request = requests[0]
        revision = IntegrationLandingRequestResolver._git_revision(
            request.revision
        )
        prior = request.prior
        if (
            revision is None
            or not request.authoritative_target
            or prior is None
            or prior.project_id != self.project_id
            or prior.state is not LandingState.LANDED
            or not prior.durable
            or prior.source != request.source
            or prior.target != request.target
            or IntegrationLandingRequestResolver._git_revision(prior.revision)
            != revision
        ):
            return None
        proof_revision = prior.proof.get("source_sha")
        if proof_revision is not None and (
            IntegrationLandingRequestResolver._git_revision(proof_revision)
            != revision
        ):
            return None
        matching = tuple(
            landing
            for landing in facts.landings
            if landing.project_id == self.project_id
            and landing.state is LandingState.LANDED
            and landing.durable
            and landing.source == request.source
            and landing.target == request.target
            and IntegrationLandingRequestResolver._git_revision(
                landing.revision
            )
            == revision
        )
        if len(matching) != 1:
            return None
        return _RollupHeadAuthority(
            revision,
            "composed_landing",
            request.source,
            request.target,
        )

    @staticmethod
    def _checkpoint_rollup_authority(
        context: WorkflowJobContext,
    ) -> _RollupHeadAuthority | None:
        details = OrchestratorIntegrationActionBackend._revalidation_details(
            context
        )
        head = IntegrationLandingRequestResolver._git_revision(
            details.get("rollup_exact_head")
        )
        kind = str(details.get("rollup_head_authority") or "").strip()
        if head is None or kind not in {
            "accepted_submission",
            "composed_landing",
        }:
            return None
        source = str(details.get("rollup_landing_source") or "").strip() or None
        target = str(details.get("rollup_landing_target") or "").strip() or None
        if kind == "composed_landing" and not all((source, target)):
            return None
        if kind == "accepted_submission" and (source or target):
            return None
        return _RollupHeadAuthority(head, kind, source, target)

    @staticmethod
    def _receipt_rollup_authority(
        receipt: Mapping[str, Any],
    ) -> _RollupHeadAuthority | None:
        head = IntegrationLandingRequestResolver._git_revision(
            receipt.get("rollup_exact_head")
        )
        kind = str(receipt.get("rollup_head_authority") or "").strip()
        if head is None or kind not in {
            "accepted_submission",
            "composed_landing",
        }:
            return None
        source = str(receipt.get("rollup_landing_source") or "").strip() or None
        target = str(receipt.get("rollup_landing_target") or "").strip() or None
        if kind == "composed_landing" and not all((source, target)):
            return None
        if kind == "accepted_submission" and (source or target):
            return None
        return _RollupHeadAuthority(head, kind, source, target)

    @staticmethod
    def _landing_target_sha(landing: LandingFact | Any | None) -> str | None:
        if landing is None:
            return None
        proof = getattr(landing, "proof", None)
        if not isinstance(proof, Mapping):
            rendered = landing.to_dict() if hasattr(landing, "to_dict") else {}
            proof = (
                rendered.get("proof", {})
                if isinstance(rendered, Mapping)
                else {}
            )
        value = str(proof.get("target_sha", "") or "").strip().lower()
        return value or None

    def _queue_row(self, context: WorkflowJobContext) -> Any | None:
        return self.orchestrator.integration_queue.get(
            self.project_id, context.job.task_id
        )

    @staticmethod
    def _queue_row_matches_issue(issue: Issue | None, row: Any | None) -> bool:
        """Join a queue row to the task's exact current parent container."""

        return bool(
            issue is not None
            and row is not None
            and str(getattr(issue, "parent_id", "") or "").strip()
            == str(getattr(row, "epic_id", "") or "").strip()
        )

    def _write_ready_record(self, issue: Issue, row: Any) -> None:
        existing = self._record(issue)
        self.tracker.set_metadata_field(
            issue.identifier,
            "oompah.integration",
            IntegrationRecord(
                state="ready",
                mode="queue",
                task_branch=row.task_branch,
                base_branch=(
                    row.base_branch
                    or self.orchestrator.project_store.epic_branch_name(row.epic_id)
                ),
                base_sha=row.base_sha,
                head_sha=row.head_sha,
                attempts=row.attempts,
                submitted_at=getattr(existing, "submitted_at", None)
                or row.submitted_at,
            ).to_dict(),
        )

    def _issue_authority_lock(
        self,
        context: WorkflowJobContext,
        *,
        blocking: bool = True,
    ):
        """Return the submission/terminal mutex for this exact tracker task."""

        issue = self._fresh_issue(context)
        issue_id = str(
            getattr(issue, "id", "")
            or getattr(issue, "identifier", "")
            or context.job.task_id
        )
        factory = getattr(self.orchestrator, "issue_transition_lock", None)
        if not callable(factory):
            return contextlib.nullcontext(True)
        lock = factory(issue_id)
        sync = getattr(lock, "sync", None)
        return (
            sync(blocking=blocking)
            if callable(sync)
            else contextlib.nullcontext(True)
        )

    @contextlib.asynccontextmanager
    async def _async_issue_authority_lock(self, context: WorkflowJobContext):
        """Hold the submission/terminal mutex across an awaited mutation."""

        issue = await asyncio.to_thread(self._fresh_issue, context)
        issue_id = str(
            getattr(issue, "id", "")
            or getattr(issue, "identifier", "")
            or context.job.task_id
        )
        factory = getattr(self.orchestrator, "issue_transition_lock", None)
        lock = factory(issue_id) if callable(factory) else None
        acquire = getattr(lock, "acquire", None)
        release = getattr(lock, "release", None)
        if not callable(acquire) or not callable(release):
            yield
            return
        acquired = await _resolve(acquire())
        if acquired is False:
            raise WorkflowActionError(
                "task authority is temporarily unavailable",
                category=WorkflowFailureCategory.TRANSIENT,
                retryable=True,
            )
        try:
            yield
        finally:
            release()

    def _repair_rebased_tracker_checkpoint(
        self,
        context: WorkflowJobContext,
    ) -> tuple[Issue, Any]:
        """Finish one prepared rebase checkpoint after job-current proof.

        Revalidation is deliberately observation-only.  The tracker write is
        therefore performed from ``apply`` while an exact queue transaction
        fences the generation observed by revalidation.
        """

        expected = self._queue_generation_from_checkpoint(context)
        details = self._revalidation_details(context)
        expected_branch = str(
            details.get("integration_queue_branch") or ""
        ).strip()
        expected_head = str(details.get("integration_queue_head") or "").strip()
        if not all((expected, expected_branch, expected_head)):
            raise WorkflowActionError(
                "prepared integration authority is missing from revalidation",
                category=WorkflowFailureCategory.STALE_EVIDENCE,
                retryable=True,
            )

        with self._issue_authority_lock(context):
            context.check_interrupted()
            row = self._queue_row(context)
            issue = self._fresh_issue(context)
            record = self._record(issue)
            containment_current = self._queue_row_matches_issue(issue, row)
            finishing_private_publication = bool(
                row is not None
                and (row.rebase_intent_pending or row.rebased_publication_pending)
            )
            if (
                row is None
                or issue is None
                or record is None
                or row.authority_generation() != expected
                or row.task_branch != expected_branch
                or row.head_sha != expected_head
                or row.state != "ready"
                or row.lease_owner is not None
                or not (containment_current or finishing_private_publication)
            ):
                raise WorkflowActionError(
                    "prepared integration generation changed before tracker repair",
                    category=WorkflowFailureCategory.STALE_EVIDENCE,
                    retryable=True,
                )
            record_branch = str(
                getattr(record, "task_branch", "") or ""
            ).strip()
            record_head = str(getattr(record, "head_sha", "") or "").strip()
            if (
                record_branch != row.task_branch
                or str(getattr(record, "state", "") or "").strip().lower()
                != "ready"
                or str(getattr(record, "mode", "") or "").strip().lower()
                != "queue"
            ):
                raise WorkflowActionError(
                    "prepared integration record changed before tracker repair",
                    category=WorkflowFailureCategory.STALE_EVIDENCE,
                    retryable=True,
                )
            if record_head == row.head_sha:
                return issue, row
            predecessor = str(
                getattr(row, "rebased_from_head_sha", "") or ""
            ).strip()
            if (
                not predecessor
                or record_head != predecessor
                or str(getattr(record, "state", "") or "").strip().lower()
                != "ready"
            ):
                raise WorkflowActionError(
                    "prepared integration tracker evidence is not repairable",
                    category=WorkflowFailureCategory.STALE_EVIDENCE,
                    retryable=True,
                )

            def _repair(current: Any) -> bool:
                context.check_interrupted()
                current_issue = self._fresh_issue(context)
                current_record = self._record(current_issue)
                if (
                    current_issue is None
                    or current_record is None
                    or current.task_branch != expected_branch
                    or current.head_sha != expected_head
                    or str(
                        getattr(current_record, "state", "") or ""
                    ).strip().lower()
                    != "ready"
                    or str(
                        getattr(current_record, "mode", "") or ""
                    ).strip().lower()
                    != "queue"
                    or str(
                        getattr(current_record, "task_branch", "") or ""
                    ).strip()
                    != current.task_branch
                    or str(
                        getattr(current_record, "head_sha", "") or ""
                    ).strip()
                    != predecessor
                ):
                    return False
                self._write_ready_record(current_issue, current)
                return True

            repaired = self.orchestrator.integration_queue.run_if_generation(
                self.project_id,
                context.job.task_id,
                expected_generation=expected,
                action=_repair,
            )
            current = self._queue_row(context)
            current_issue = self._fresh_issue(context)
            if (
                not repaired
                or current is None
                or current.authority_generation() != expected
                or (
                    not self._record_authorizes_queue_row(current_issue, current)
                    and not (
                        current.state == "ready"
                        and current.lease_owner is None
                        and (
                            current.rebase_intent_pending
                            or current.rebased_publication_pending
                        )
                        and current_issue is not None
                        and canonicalize_status(current_issue.state)
                        == READY_TO_INTEGRATE
                        and str(
                            getattr(self._record(current_issue), "state", "") or ""
                        ).strip().lower()
                        == "ready"
                        and str(
                            getattr(self._record(current_issue), "mode", "") or ""
                        ).strip().lower()
                        == "queue"
                        and str(
                            getattr(
                                self._record(current_issue),
                                "task_branch",
                                "",
                            )
                            or ""
                        ).strip()
                        == current.task_branch
                        and str(
                            getattr(self._record(current_issue), "head_sha", "")
                            or ""
                        ).strip()
                        == current.head_sha
                    )
                )
            ):
                raise WorkflowActionError(
                    "prepared integration generation changed during tracker repair",
                    category=WorkflowFailureCategory.STALE_EVIDENCE,
                    retryable=True,
                )
            return current_issue, current

    def _reconcile_attempt_queue_authority(
        self,
        context: WorkflowJobContext,
    ) -> Any:
        """Recover or rehome the exact queue row selected by revalidation.

        Accepted submissions are tracker-first, so a process may exit after
        recording ``ready`` but before inserting the SQLite row.  Parent
        reassignment can likewise leave an otherwise identical row attached to
        the old epic.  Both repairs happen in apply, never revalidation, under
        the task transition mutex and an exact queue CAS.
        """

        details = self._revalidation_details(context)
        observed_present = bool(details.get("integration_queue_present", False))
        observed_generation = self._queue_generation_from_checkpoint(context)
        observed_parent = str(details.get("task_parent") or "").strip()
        observed_branch = str(details.get("task_branch") or "").strip()
        observed_head = str(details.get("task_head") or "").strip()
        expected_evidence = self._revalidated_evidence_revision(context)
        with self._issue_authority_lock(context):
            context.check_interrupted()
            issue = self._fresh_issue(context)
            record = self._record(issue)
            if (
                issue is None
                or canonicalize_status(issue.state) != READY_TO_INTEGRATE
                or record is None
                or is_direct_epic_maintenance_issue(issue)
            ):
                raise WorkflowActionError(
                    "integration attempt lost queue-mode task authority",
                    category=WorkflowFailureCategory.STALE_EVIDENCE,
                    retryable=True,
                )
            parent_id = str(getattr(issue, "parent_id", "") or "").strip()
            branch = str(getattr(record, "task_branch", "") or "").strip()
            head = str(getattr(record, "head_sha", "") or "").strip()
            if (
                not all((branch, head, expected_evidence))
                or (
                    "task_parent" in details
                    and parent_id != observed_parent
                )
                or branch != observed_branch
                or head != observed_head
            ):
                raise WorkflowActionError(
                    "integration attempt task generation changed before queue repair",
                    category=WorkflowFailureCategory.STALE_EVIDENCE,
                    retryable=True,
                )
            row = self._queue_row(context)

            def _require_current_attempt_evidence() -> None:
                facts = self.binding.collector.collect(
                    issue.identifier,
                    landing_requests=self._landing_request(issue),
                )
                decision = evaluate_task(issue, facts)
                if (
                    decision.evidence_revision != expected_evidence
                    or "integration_attempt" not in decision.durable_jobs
                ):
                    raise WorkflowActionError(
                        "integration attempt evidence changed before queue repair",
                        category=WorkflowFailureCategory.STALE_EVIDENCE,
                        retryable=True,
                    )

            def _require_coherent_parent_record(current_row: Any) -> None:
                """Normalize tracker target evidence before any landing lookup.

                Parent reassignment can make a queue row authoritative for the
                new epic while the accepted tracker record still names the old
                base branch.  Acting from that mixed snapshot is unsafe: the
                landing shortcut could prove the head on the old epic and then
                checkpoint it as integrated in the new queue container.  Repair
                the exact ready row under its generation CAS and supersede this
                job so the replacement generation revalidates the normalized
                evidence before it performs Git work.
                """

                try:
                    expected_base = str(
                        current_row.base_branch
                        or self.orchestrator.project_store.epic_branch_name(parent_id)
                        or ""
                    ).strip()
                except Exception as exc:  # noqa: BLE001 - target lookup boundary
                    raise WorkflowActionError(
                        f"integration parent target is unavailable: {exc}",
                        category=WorkflowFailureCategory.TRANSIENT,
                        retryable=True,
                    ) from exc
                current_issue = self._fresh_issue(context)
                current_record = self._record(current_issue)
                if (
                    current_issue is not None
                    and current_record is not None
                    and str(getattr(current_record, "mode", "") or "")
                    .strip()
                    .lower()
                    == "queue"
                    and str(getattr(current_record, "base_branch", "") or "").strip()
                    == expected_base
                ):
                    return

                generation = current_row.authority_generation()

                def _repair(exact_row: Any) -> bool:
                    context.check_interrupted()
                    fresh_issue = self._fresh_issue(context)
                    fresh_record = self._record(fresh_issue)
                    if (
                        fresh_issue is None
                        or fresh_record is None
                        or canonicalize_status(fresh_issue.state)
                        != READY_TO_INTEGRATE
                        or str(getattr(fresh_issue, "parent_id", "") or "").strip()
                        != parent_id
                        or exact_row.state != "ready"
                        or exact_row.lease_owner is not None
                        or exact_row.epic_id != parent_id
                        or exact_row.task_branch != branch
                        or exact_row.head_sha != head
                        or str(getattr(fresh_record, "state", "") or "")
                        .strip()
                        .lower()
                        not in {"ready", "queued"}
                        or str(getattr(fresh_record, "task_branch", "") or "").strip()
                        != branch
                        or str(getattr(fresh_record, "head_sha", "") or "").strip()
                        != head
                    ):
                        return False
                    self._write_ready_record(fresh_issue, exact_row)
                    return True

                repaired = self.orchestrator.integration_queue.run_if_generation(
                    self.project_id,
                    context.job.task_id,
                    expected_generation=generation,
                    action=_repair,
                )
                if not repaired:
                    raise WorkflowActionError(
                        "integration parent evidence changed during metadata repair",
                        category=WorkflowFailureCategory.STALE_EVIDENCE,
                        retryable=True,
                    )
                self._request_refresh()
                raise WorkflowActionSuperseded(
                    "queue delivery metadata was normalized for the current parent",
                    replacement_generation=(
                        f"queue-parent:{parent_id}:"
                        f"{current_row.authority_generation()}"
                    ),
                )

            if (
                row is not None
                and (row.rebase_intent_pending or row.rebased_publication_pending)
                and observed_generation
                and row.authority_generation() == observed_generation
                and row.state == "ready"
                and row.lease_owner is None
                and row.task_branch == branch
                and str(getattr(record, "mode", "") or "").strip().lower()
                == "queue"
                and str(getattr(record, "state", "") or "").strip().lower()
                == "ready"
                and head
                in {
                    row.head_sha,
                    str(getattr(row, "rebased_from_head_sha", "") or "").strip(),
                }
            ):
                # A prepared private-ref rewrite remains authoritative even if
                # the task was concurrently reparented or unparented.  Finish
                # only that exact durable publication first; once its pending
                # bit clears, the ordinary authority check fences quality and
                # epic mutation and the replacement generation can rehome or
                # reclassify the now-stable private head.
                _require_current_attempt_evidence()
                return row

            if (
                parent_id
                and isinstance(record, IntegrationRecord)
                and record.mode == "standalone"
                and str(record.post_landed_parent_id or "").strip()
                == parent_id
                and record.task_branch == branch
                and record.head_sha == head
                and not self._standalone_route_is_current(issue, record)
            ):
                # Restart repair for a process that wrote the parent queue
                # target but exited before changing the integration record.
                # Finish the tracker-first compensation; its replacement
                # integration attempt will own cancelled-row revival.
                self._reclassify_invalid_parented_standalone(
                    context,
                    issue,
                    record,
                    expected_branch=branch,
                    expected_head=head,
                )

            self._reclassify_queue_submission_if_needed(
                context,
                observed_present=observed_present,
                observed_generation=observed_generation,
                observed_parent=observed_parent,
                expected_branch=branch,
                expected_head=head,
                expected_evidence=expected_evidence,
            )

            if (
                row is not None
                and observed_generation
                and row.authority_generation() == observed_generation
                and row.state == "cancelled"
                and row.last_error == STANDALONE_RECLASSIFICATION_REASON
                and row.lease_owner is None
                and not row.rebase_intent_pending
                and not row.rebased_publication_pending
                and row.epic_id == parent_id
                and row.task_branch == branch
                and row.head_sha == head
                and str(getattr(record, "mode", "") or "").strip().lower()
                == "queue"
                and str(getattr(record, "state", "") or "").strip().lower()
                == "ready"
            ):
                # Tracker-first standalone compensation deliberately leaves
                # the retired row untouched.  The replacement queue decision
                # revives only that exact cancelled generation under the
                # issue -> project -> queue lock order.
                with self._project_route_authority_lock():
                    context.check_interrupted()
                    current_issue = self._fresh_issue(context)
                    current_record = self._record(current_issue)
                    queue_target = self._current_parent_queue_target(current_issue)
                    if (
                        current_issue is None
                        or current_record is None
                        or canonicalize_status(current_issue.state)
                        != READY_TO_INTEGRATE
                        or str(
                            getattr(current_issue, "parent_id", "") or ""
                        ).strip()
                        != parent_id
                        or self._post_landed_parent_target(current_issue) is not None
                        or not queue_target
                        or str(
                            getattr(current_issue, "target_branch", "") or ""
                        ).strip()
                        != queue_target
                        or str(
                            getattr(current_record, "base_branch", "") or ""
                        ).strip()
                        != queue_target
                        or str(
                            getattr(current_record, "mode", "") or ""
                        ).strip().lower()
                        != "queue"
                        or str(
                            getattr(current_record, "task_branch", "") or ""
                        ).strip()
                        != branch
                        or str(
                            getattr(current_record, "head_sha", "") or ""
                        ).strip()
                        != head
                    ):
                        raise WorkflowActionError(
                            "cancelled parent queue route changed before repair",
                            category=WorkflowFailureCategory.STALE_EVIDENCE,
                            retryable=True,
                        )
                    _require_current_attempt_evidence()
                    recovered = (
                        self.orchestrator.integration_queue.replace_task_identity(
                            self.project_id,
                            context.job.task_id,
                            expected_generation=observed_generation,
                            epic_id=parent_id,
                            task_branch=branch,
                            head_sha=head,
                            base_branch=queue_target,
                            base_sha=None,
                            priority=getattr(issue, "priority", None),
                            submitted_at=getattr(record, "submitted_at", None),
                        )
                    )
                    if (
                        recovered is None
                        or recovered.state != "ready"
                        or recovered.epic_id != parent_id
                        or recovered.task_branch != branch
                        or recovered.head_sha != head
                        or str(recovered.base_branch or "").strip()
                        != queue_target
                        or self._post_landed_parent_target(current_issue) is not None
                    ):
                        raise WorkflowActionError(
                            "cancelled parent queue generation changed during repair",
                            category=WorkflowFailureCategory.STALE_EVIDENCE,
                            retryable=True,
                        )
                self._request_refresh()
                raise WorkflowActionSuperseded(
                    "cancelled standalone generation was restored to the parent queue",
                    replacement_generation=(
                        f"queue-parent:{parent_id}:"
                        f"{recovered.authority_generation()}"
                    ),
                )

            if (
                row is not None
                and observed_generation
                and row.authority_generation() == observed_generation
                and self._queue_row_matches_issue(issue, row)
            ):
                # Durable effects may legitimately have advanced their
                # tracker facts before a restarted worker finishes repair.
                # A runnable generation gets no such exception.
                if row.state not in {"integrated", "blocked"}:
                    _require_current_attempt_evidence()
                    _require_coherent_parent_record(row)
                return row

            if row is None:
                _require_current_attempt_evidence()
                if observed_present or observed_generation:
                    raise WorkflowActionError(
                        "integration queue row disappeared after revalidation",
                        category=WorkflowFailureCategory.STALE_EVIDENCE,
                        retryable=True,
                    )
                row = self.orchestrator.integration_queue.enqueue_if_absent(
                    project_id=self.project_id,
                    epic_id=parent_id,
                    task_id=context.job.task_id,
                    task_branch=branch,
                    head_sha=head,
                    base_branch=getattr(record, "base_branch", None),
                    base_sha=getattr(record, "base_sha", None),
                    priority=getattr(issue, "priority", None),
                    submitted_at=getattr(record, "submitted_at", None),
                )
                if row is None:
                    raise WorkflowActionError(
                        "integration queue absence changed before recovery",
                        category=WorkflowFailureCategory.STALE_EVIDENCE,
                        retryable=True,
                    )
                _require_coherent_parent_record(row)
                return row

            if (
                not observed_generation
                or row.authority_generation() != observed_generation
            ):
                raise WorkflowActionError(
                    "integration queue generation changed before containment repair",
                    category=WorkflowFailureCategory.STALE_EVIDENCE,
                    retryable=True,
                )
            if row.lease_owner is not None:
                raise WorkflowActionError(
                    "stale-parent integration row still has a live legacy owner",
                    category=WorkflowFailureCategory.TRANSIENT,
                    retryable=True,
                )
            _require_current_attempt_evidence()
            try:
                current_parent = self.tracker.fetch_issue_detail(parent_id)
            except Exception as exc:  # noqa: BLE001 - hierarchy lookup boundary
                raise WorkflowActionError(
                    f"integration parent target is unavailable: {exc}",
                    category=WorkflowFailureCategory.TRANSIENT,
                    retryable=True,
                ) from exc
            if (
                current_parent is None
                or str(
                    getattr(current_parent, "identifier", "")
                    or getattr(current_parent, "id", "")
                    or ""
                ).strip()
                != parent_id
                or (
                    getattr(current_parent, "project_id", None)
                    and str(current_parent.project_id) != self.project_id
                )
            ):
                raise WorkflowActionError(
                    "integration parent target could not be resolved exactly",
                    category=WorkflowFailureCategory.TRANSIENT,
                    retryable=True,
                )
            replacement_base_branch = str(
                getattr(current_parent, "work_branch", "")
                or self.orchestrator.project_store.epic_branch_name(parent_id)
                or ""
            ).strip()
            if not replacement_base_branch:
                raise WorkflowActionError(
                    "integration parent has no hierarchy target branch",
                    category=WorkflowFailureCategory.TRANSIENT,
                    retryable=True,
                )
            recorded_base_branch = str(
                getattr(record, "base_branch", "") or ""
            ).strip()
            replacement_base_sha = (
                getattr(record, "base_sha", None)
                if recorded_base_branch == replacement_base_branch
                else None
            )
            replaced = self.orchestrator.integration_queue.replace_task_identity(
                self.project_id,
                context.job.task_id,
                expected_generation=observed_generation,
                epic_id=parent_id,
                task_branch=branch,
                head_sha=head,
                base_branch=replacement_base_branch,
                base_sha=replacement_base_sha,
                priority=getattr(issue, "priority", None),
                submitted_at=getattr(record, "submitted_at", None),
            )
            if replaced is None:
                raise WorkflowActionError(
                    "integration containment changed during queue repair",
                    category=WorkflowFailureCategory.STALE_EVIDENCE,
                    retryable=True,
                )
            _require_coherent_parent_record(replaced)
            return replaced

    def _prepare_terminal_checkpoint(
        self,
        context: WorkflowJobContext,
    ) -> tuple[Any, str]:
        """Normalize and coordinate one exact integrated generation.

        A legacy tracker-first landing is queue-CASed before its idempotent
        peer notice.  Both the CAS and the notice are fenced by the exact queue
        generation captured during revalidation, so a stale job is read-only.
        """

        expected = self._queue_generation_from_checkpoint(context)
        details = self._revalidation_details(context)
        expected_branch = str(
            details.get("integration_queue_branch") or ""
        ).strip()
        expected_head = str(details.get("integration_queue_head") or "").strip()
        if not all((expected, expected_branch, expected_head)):
            raise WorkflowActionError(
                "terminal queue authority is missing from revalidation",
                category=WorkflowFailureCategory.STALE_EVIDENCE,
                retryable=True,
            )

        with self._issue_authority_lock(context):
            context.check_interrupted()
            row = self._queue_row(context)
            issue = self._fresh_issue(context)
            record = self._record(issue)
            if (
                row is None
                or issue is None
                or record is None
                or row.authority_generation() != expected
                or row.task_branch != expected_branch
                or row.head_sha != expected_head
                or row.state not in {"ready", "integrated"}
                or row.lease_owner is not None
                or not self._queue_row_matches_issue(issue, row)
            ):
                raise WorkflowActionError(
                    "terminal queue generation changed after revalidation",
                    category=WorkflowFailureCategory.STALE_EVIDENCE,
                    retryable=True,
                )
            branch = str(getattr(record, "task_branch", "") or "").strip()
            head = str(getattr(record, "head_sha", "") or "").strip()
            integrated = str(
                getattr(record, "integrated_sha", "") or ""
            ).strip()
            if (
                str(getattr(record, "state", "") or "").strip().lower()
                != "integrated"
                or not all((branch, head, integrated))
                or branch != row.task_branch
            ):
                raise WorkflowActionError(
                    "terminal tracker landing is incomplete",
                    category=WorkflowFailureCategory.STALE_EVIDENCE,
                    retryable=True,
                )
            if (
                row.state == "integrated"
                and row.head_sha == head
                and str(getattr(row, "integrated_sha", "") or "").strip()
                == integrated
            ):
                normalized = row
            else:
                landing = self._landing(issue)
                if (
                    landing is None
                    or landing.state is not LandingState.LANDED
                    or str(getattr(landing, "revision", "") or "").strip()
                    != integrated
                ):
                    raise WorkflowActionError(
                        "legacy tracker landing is not exactly proven",
                        category=WorkflowFailureCategory.STALE_EVIDENCE,
                        retryable=True,
                    )
                normalized = (
                    self.orchestrator.integration_queue.normalize_legacy_tracker_checkpoint(
                        self.project_id,
                        context.job.task_id,
                        expected_generation=expected,
                        task_branch=branch,
                        head_sha=head,
                        integrated_sha=integrated,
                        base_sha=getattr(record, "base_sha", None),
                    )
                )
                if normalized is None:
                    raise WorkflowActionError(
                        "legacy landing queue generation changed before normalization",
                        category=WorkflowFailureCategory.STALE_EVIDENCE,
                        retryable=True,
                    )

            normalized_generation = normalized.authority_generation()

            def _notify(current: Any) -> bool:
                context.check_interrupted()
                notify = getattr(
                    self.orchestrator, "_notify_integrated_task_peers", None
                )
                if not callable(notify):
                    return True
                try:
                    notify(
                        project_id=self.project_id,
                        task_id=context.job.task_id,
                        epic_id=current.epic_id,
                        integrated_sha=integrated,
                    )
                except Exception as exc:
                    raise WorkflowActionError(
                        f"legacy integration peer coordination is not durable: {exc}",
                        category=WorkflowFailureCategory.TRANSIENT,
                        retryable=True,
                    ) from exc
                return True

            coordinated = self.orchestrator.integration_queue.run_if_generation(
                self.project_id,
                context.job.task_id,
                expected_generation=normalized_generation,
                action=_notify,
            )
            current = self._queue_row(context)
            if (
                not coordinated
                or current is None
                or current.authority_generation() != normalized_generation
                or not self._queue_row_matches_issue(
                    self._fresh_issue(context), current
                )
            ):
                raise WorkflowActionError(
                    "terminal queue generation changed before peer coordination",
                    category=WorkflowFailureCategory.STALE_EVIDENCE,
                    retryable=True,
                )
            return current, integrated

    @staticmethod
    def _queue_generation_from_checkpoint(context: WorkflowJobContext) -> str:
        checkpoint = context.job.checkpoint or {}
        revalidation = checkpoint.get("revalidation", {})
        details = (
            revalidation.get("details", {})
            if isinstance(revalidation, Mapping)
            else {}
        )
        return str(
            details.get("integration_queue_generation", "")
            if isinstance(details, Mapping)
            else ""
        ).strip()

    @staticmethod
    def _revalidation_details(context: WorkflowJobContext) -> Mapping[str, Any]:
        checkpoint = context.job.checkpoint or {}
        revalidation = checkpoint.get("revalidation", {})
        if not isinstance(revalidation, Mapping):
            return {}
        details = revalidation.get("details", {})
        return details if isinstance(details, Mapping) else {}

    @staticmethod
    def _revalidated_evidence_revision(context: WorkflowJobContext) -> str:
        checkpoint = context.job.checkpoint or {}
        revalidation = checkpoint.get("revalidation", {})
        if not isinstance(revalidation, Mapping):
            return ""
        return str(revalidation.get("evidence_revision", "") or "").strip()

    @staticmethod
    def _head_from_checkpoint(context: WorkflowJobContext) -> str | None:
        explicit = str(getattr(context.job, "expected_head_sha", "") or "").strip()
        if explicit:
            return explicit
        checkpoint = context.job.checkpoint or {}
        revalidation = checkpoint.get("revalidation", {})
        if not isinstance(revalidation, Mapping):
            return None
        return str(revalidation.get("head_sha", "") or "").strip() or None

    @staticmethod
    def _standalone_resubmission_supersession(
        outcome: Any,
        *,
        expected_head: str,
    ) -> tuple[str, str, str | None, str | None] | None:
        """Validate one typed accepted-vs-remote drift observation.

        The scoped orchestrator call is allowed to report that the mutable
        task branch has advanced beyond the immutable accepted submission.
        Treat that as superseding evidence only when the typed result remains
        bound to this job's exact accepted head and both heads are complete Git
        identities.  Partial/provider-ambiguous observations intentionally
        retain the ordinary bounded retry path; they cannot retire exact
        submission authority or authorize the newer code.
        """

        if not isinstance(outcome, StandaloneDeliveryOutcome):
            return None
        disposition = getattr(outcome.disposition, "value", outcome.disposition)
        if str(disposition or "").strip() != "resubmission_required":
            return None
        accepted_head = str(outcome.accepted_head or "").strip().lower()
        observed_head = str(outcome.observed_branch_head or "").strip().lower()
        required_head = str(expected_head or "").strip().lower()
        exact_sha = r"[0-9a-f]{40}|[0-9a-f]{64}"
        if (
            not re.fullmatch(exact_sha, required_head)
            or accepted_head != required_head
            or not re.fullmatch(exact_sha, observed_head)
            or observed_head == accepted_head
        ):
            return None
        review_head = str(outcome.observed_review_head or "").strip().lower() or None
        if review_head is not None and not re.fullmatch(exact_sha, review_head):
            return None
        reason = str(outcome.reason or "").strip()
        if not reason:
            return None
        review_id = str(outcome.review_id or "").strip() or None
        return observed_head, reason, review_head, review_id

    @classmethod
    def _queue_generation_is_current(
        cls, context: WorkflowJobContext, row: Any | None
    ) -> bool:
        expected = cls._queue_generation_from_checkpoint(context)
        return bool(
            row is not None
            and expected
            and row.authority_generation() == expected
        )

    def _exact_authority(
        self,
        context: WorkflowJobContext,
        *,
        queue_generation: str,
        task_branch: str,
        head_sha: str,
    ) -> bool:
        try:
            context.check_interrupted()
        except Exception:
            return False
        row = self._queue_row(context)
        issue = self._fresh_issue(context)
        record = self._record(issue)
        effective_mode = (
            "queue"
            if str(getattr(issue, "parent_id", "") or "").strip()
            else str(getattr(record, "mode", "") or "").strip().lower()
        )
        finishing_private_publication = bool(
            row is not None
            and (row.rebase_intent_pending or row.rebased_publication_pending)
            and record is not None
            and str(getattr(record, "mode", "") or "").strip().lower()
            == "queue"
        )
        return bool(
            row is not None
            and row.state == "ready"
            and row.lease_owner is None
            and row.authority_generation() == queue_generation
            and row.task_branch == task_branch
            and row.head_sha == head_sha
            and issue is not None
            and (
                self._queue_row_matches_issue(issue, row)
                or finishing_private_publication
            )
            and canonicalize_status(issue.state) == READY_TO_INTEGRATE
            and record is not None
            and effective_mode == "queue"
            and str(getattr(record, "state", "") or "").strip().lower()
            == "ready"
            and str(getattr(record, "task_branch", "") or "").strip()
            == task_branch
            and str(getattr(record, "head_sha", "") or "").strip() == head_sha
        )

    @staticmethod
    def _record_authorizes_queue_row(issue: Issue | None, row: Any) -> bool:
        record = OrchestratorIntegrationActionBackend._record(issue)
        if (
            issue is None
            or record is None
            or canonicalize_status(issue.state) != READY_TO_INTEGRATE
            or not OrchestratorIntegrationActionBackend._queue_row_matches_issue(
                issue, row
            )
        ):
            return False
        branch = str(getattr(record, "task_branch", "") or "").strip()
        head = str(getattr(record, "head_sha", "") or "").strip()
        state = str(getattr(record, "state", "") or "").strip().lower()
        effective_mode = (
            "queue"
            if str(getattr(issue, "parent_id", "") or "").strip()
            else str(getattr(record, "mode", "") or "").strip().lower()
        )
        if effective_mode != "queue":
            return False
        if branch != row.task_branch:
            return False
        if state == "ready":
            return head == row.head_sha
        if state == "integrated":
            return bool(
                head == row.head_sha
                and str(getattr(record, "integrated_sha", "") or "").strip()
                and (
                    not str(getattr(row, "integrated_sha", "") or "").strip()
                    or str(getattr(record, "integrated_sha", "") or "").strip()
                    == str(getattr(row, "integrated_sha", "") or "").strip()
                )
            )
        if state == "blocked":
            return bool(
                head == row.head_sha
                and str(getattr(record, "last_error", "") or "").strip()
            )
        return False

    @staticmethod
    def _blocked_route(row: Any) -> tuple[IntegrationRoute, str, str] | None:
        error = str(getattr(row, "last_error", "") or "")
        status, separator, message = error.partition(":")
        if not separator:
            return None
        if status == "ci_failure":
            return IntegrationRoute.CI_FIX, status, message
        if status in {"conflict", "needs_rebase"}:
            return IntegrationRoute.REBASE, status, message
        return None

    def revalidate_action(
        self, action: str, context: WorkflowJobContext
    ) -> RevalidationResult:
        if action == "historical_audit_replay_batch":
            return self._revalidate_historical_replay(context)
        issue = self._issue(context)
        if issue is None:
            return RevalidationResult(
                f"missing:{context.job.task_id}", current=False
            )
        with self._issue_authority_lock(context):
            issue = self._fresh_issue(context)
            row = self._queue_row(context)
        if issue is None:
            return RevalidationResult(
                f"missing:{context.job.task_id}", current=False
            )
        requests = (
            ()
            if action
            in {"direct_epic_maintenance_completion", "terminal_audit_done"}
            else self._landing_request(issue)
        )
        facts = self.binding.collector.collect(
            issue.identifier, landing_requests=requests
        )
        decision = evaluate_task(issue, facts)
        rollup_authority = (
            self._rollup_head_authority(
                issue,
                requests=requests,
                facts=facts,
                decision=decision,
            )
            if action == "parent_rollup_review"
            else None
        )
        row = self._queue_row(context)
        details: dict[str, Any] = {
            "decision_revision": decision.decision_revision,
            "durable_jobs": list(decision.durable_jobs),
            "integration_queue_present": row is not None,
        }
        if requests:
            request = requests[0]
            details.update(
                {
                    "landing_source": request.source,
                    "landing_target": request.target,
                    "landing_revision": request.revision,
                }
            )
        if row is not None:
            details.update(
                {
                    "integration_queue_generation": row.authority_generation(),
                    "integration_queue_state": row.state,
                    "integration_queue_epic": row.epic_id,
                    "integration_queue_head": row.head_sha,
                    "integration_queue_branch": row.task_branch,
                }
            )
        record = self._record(issue)
        head_sha = str(getattr(record, "head_sha", "") or "").strip() or None
        details.update(
            {
                "task_evidence_revision": decision.evidence_revision,
                "task_parent": str(getattr(issue, "parent_id", "") or "").strip(),
                "task_target": str(
                    getattr(issue, "target_branch", "")
                    or self._project_default_branch()
                    or ""
                ).strip(),
                "task_branch": str(
                    getattr(record, "task_branch", "")
                    or getattr(issue, "work_branch", "")
                    or ""
                ).strip(),
                "task_head": str(
                    getattr(record, "head_sha", "")
                    or getattr(issue, "head_sha", "")
                    or ""
                ).strip(),
                "task_status": canonicalize_status(issue.state),
            }
        )
        if rollup_authority is not None:
            details.update(rollup_authority.receipt())
        current = (
            action in decision.durable_jobs
            and decision.evidence_revision == context.job.expected_evidence_revision
            and (
                action != "parent_rollup_review"
                or rollup_authority is not None
            )
        )
        return RevalidationResult(
            context.job.generation if current else str(decision.decision_revision),
            evidence_revision=decision.evidence_revision,
            head_sha=head_sha,
            current=current,
            details=details,
        )

    def legacy_exhaustion_is_capacity_wait(self, job: WorkflowJob) -> bool:
        """Prove an old standalone exhaustion is only a live capacity wait."""

        if (
            job.action != "standalone_delivery"
            or job.state is not WorkflowJobState.EXHAUSTED
            or "waiting for an exact forge effect"
            not in str(job.last_error or "")
        ):
            return False
        issue = self.tracker.fetch_issue_detail(job.task_id)
        record = self._record(issue)
        checkpoint = job.checkpoint or {}
        revalidation = checkpoint.get("revalidation", {})
        details = (
            revalidation.get("details", {})
            if isinstance(revalidation, Mapping)
            else {}
        )
        checkpoint_head = str(
            (
                revalidation.get("head_sha")
                if isinstance(revalidation, Mapping)
                else None
            )
            or (
                details.get("task_head")
                if isinstance(details, Mapping)
                else None
            )
            or job.expected_head_sha
            or ""
        ).strip()
        checkpoint_branch = str(
            details.get("task_branch", "")
            if isinstance(details, Mapping)
            else ""
        ).strip()
        if (
            issue is None
            or canonicalize_status(issue.state) != READY_TO_INTEGRATE
            or not isinstance(record, IntegrationRecord)
            or str(record.mode or "").strip().lower() != "standalone"
            or not self._standalone_route_is_current(issue, record)
            or not checkpoint_head
            or checkpoint_head != str(record.head_sha or "").strip()
            or not checkpoint_branch
            or checkpoint_branch != str(record.task_branch or "").strip()
        ):
            return False
        capacity = getattr(self.orchestrator, "_project_review_capacity", None)
        if not callable(capacity):
            return False
        _open_reviews, _limit, at_capacity = capacity(self.project_id)
        return bool(at_capacity)

    def _revalidate_historical_replay(
        self, context: WorkflowJobContext
    ) -> RevalidationResult:
        payload = context.job.payload or {}
        expected_cursor = payload.get("cursor")
        if expected_cursor is not None:
            expected_cursor = str(expected_cursor)
        cursor_name = f"integration_audit:{self.project_id}"
        current_cursor = getattr(
            self.orchestrator, "_maintenance_cursors", {}
        ).get(cursor_name)
        rows = self.orchestrator.integration_queue.items(
            project_id=self.project_id,
            states=("integrated",),
            limit=1,
            after=current_cursor,
        )
        first_sequence = rows[0].history_sequence if rows else 0
        generation, evidence = _historical_replay_identity(
            self.project_id, current_cursor, first_sequence
        )
        expected_first = int(payload.get("first_history_sequence") or 0)
        current = bool(
            rows
            and current_cursor == expected_cursor
            and expected_first == first_sequence
            and context.job.generation == generation
            and context.job.expected_evidence_revision == evidence
        )
        return RevalidationResult(
            generation,
            evidence_revision=evidence,
            current=current,
            details={
                "history_cursor": current_cursor,
                "first_history_sequence": first_sequence,
                "project_id": self.project_id,
            },
        )

    def _base_receipt(
        self, action: str, context: WorkflowJobContext
    ) -> dict[str, Any]:
        return {
            "action": action,
            "project_id": self.project_id,
            "task_id": context.job.task_id,
            "job_generation": context.job.generation,
        }

    def _request_refresh(self) -> None:
        refresh = getattr(self.orchestrator, "request_refresh", None)
        if callable(refresh):
            refresh()

    def _terminal_observation(
        self,
        action: str,
        context: WorkflowJobContext,
        *,
        expected_generation: str | None = None,
        expected_head: str | None = None,
    ) -> EffectObservation:
        issue = self._fresh_issue(context)
        row = self._queue_row(context)
        record = self._record(issue)
        status = canonicalize_status(getattr(issue, "state", ""))
        required_generation = str(expected_generation or "").strip() or (
            self._queue_generation_from_checkpoint(context)
        )
        required_head = str(expected_head or "").strip() or (
            self._head_from_checkpoint(context)
        )
        applied = bool(
            status in {IN_VALIDATION, DONE, MERGED, ARCHIVED}
            and row is not None
            and required_generation
            and row.authority_generation() == required_generation
            and row.state == "integrated"
            and self._queue_row_matches_issue(issue, row)
            and record is not None
            and str(getattr(record, "state", "") or "").strip().lower()
            == "integrated"
            and str(getattr(record, "task_branch", "") or "").strip()
            == row.task_branch
            and str(getattr(record, "head_sha", "") or "").strip()
            == row.head_sha
            and (
                not str(getattr(row, "integrated_sha", "") or "").strip()
                or str(getattr(record, "integrated_sha", "") or "").strip()
                == str(getattr(row, "integrated_sha", "") or "").strip()
            )
            and (
                required_head is None
                or str(getattr(record, "head_sha", "") or "").strip()
                == required_head
            )
        )
        return EffectObservation(
            applied,
            {
                **self._base_receipt(action, context),
                "status": status,
                "queue_generation": (
                    row.authority_generation() if row is not None else None
                ),
                "queue_branch": getattr(row, "task_branch", None),
                "queue_head": getattr(row, "head_sha", None),
            },
        )

    def _direct_maintenance_observation(
        self,
        action: str,
        context: WorkflowJobContext,
        *,
        expected_head: str | None = None,
    ) -> EffectObservation:
        """Observe the exact durable result of direct publication completion."""

        issue = self._fresh_issue(context)
        record = self._record(issue)
        head = str(expected_head or self._head_from_checkpoint(context) or "").strip()
        current_head = str(
            getattr(record, "integrated_sha", None)
            or getattr(record, "head_sha", None)
            or ""
        ).strip()
        parent_id = str(getattr(issue, "parent_id", "") or "").strip()
        rebase_state_reader = getattr(
            self.orchestrator, "_get_epic_rebase_state", None
        )
        try:
            parent = (
                self.tracker.fetch_issue_detail(parent_id) if parent_id else None
            )
            parent_rebased = bool(
                callable(rebase_state_reader)
                and rebase_state_reader(parent_id, project_id=self.project_id)
                is EpicRebaseState.REBASED
                and parent is not None
                and EpicRebaseState.REBASED.label in (parent.labels or [])
            )
        except Exception:  # noqa: BLE001 - incomplete observation retries apply
            parent_rebased = False
        applied = bool(
            issue is not None
            and direct_epic_maintenance_handoff_ready(issue, record)
            and head
            and current_head == head
            and parent_rebased
        )
        return EffectObservation(
            applied,
            {
                **self._base_receipt(action, context),
                "task_status": (
                    canonicalize_status(issue.state) if issue is not None else None
                ),
                "task_branch": str(
                    getattr(record, "task_branch", None) or ""
                ).strip()
                or None,
                "task_head": current_head or None,
                "maintenance_publication_proven": bool(
                    getattr(record, "maintenance_publication_proven", False)
                ),
                "parent_id": parent_id or None,
                "parent_rebased": parent_rebased,
            },
        )

    def _terminal_candidate(
        self,
        context: WorkflowJobContext,
        *,
        expected_generation: str | None = None,
        expected_head: str | None = None,
    ) -> tuple[Any, str]:
        """Return the exact landed queue row authorized for terminal staging."""

        row = self._queue_row(context)
        if row is None or row.state != "integrated":
            raise WorkflowActionError(
                "exact integrated queue row is unavailable for terminal staging",
                category=WorkflowFailureCategory.STALE_EVIDENCE,
                retryable=True,
            )
        required_generation = str(expected_generation or "").strip() or (
            self._queue_generation_from_checkpoint(context)
        )
        if not required_generation or row.authority_generation() != required_generation:
            raise WorkflowActionError(
                "integrated audit row changed after job revalidation",
                category=WorkflowFailureCategory.STALE_EVIDENCE,
                retryable=True,
            )
        issue = self._fresh_issue(context)
        record = self._record(issue)
        landing = self._landing(issue) if issue is not None else None
        required_head = str(expected_head or "").strip() or (
            self._head_from_checkpoint(context)
        )
        integrated_sha = str(
            getattr(row, "integrated_sha", "")
            or getattr(record, "integrated_sha", "")
            or ""
        ).strip()
        if (
            issue is None
            or record is None
            or not self._queue_row_matches_issue(issue, row)
            or str(getattr(record, "state", "") or "").strip().lower()
            != "integrated"
            or str(getattr(record, "task_branch", "") or "").strip()
            != row.task_branch
            or str(getattr(record, "head_sha", "") or "").strip()
            != row.head_sha
            or not integrated_sha
            or (
                str(getattr(row, "integrated_sha", "") or "").strip()
                and str(getattr(record, "integrated_sha", "") or "").strip()
                != str(getattr(row, "integrated_sha", "") or "").strip()
            )
            or (
                required_head is not None
                and str(getattr(record, "head_sha", "") or "").strip()
                != required_head
            )
            or landing is None
            or landing.state is not LandingState.LANDED
            or str(getattr(landing, "revision", "") or "").strip()
            != integrated_sha
        ):
            raise WorkflowActionError(
                "terminal staging lost exact integrated landing authority",
                category=WorkflowFailureCategory.STALE_EVIDENCE,
                retryable=True,
            )
        return row, integrated_sha

    def _attempt_observation(
        self,
        action: str,
        context: WorkflowJobContext,
        *,
        expected_generation: str | None = None,
        expected_branch: str | None = None,
        expected_head: str | None = None,
    ) -> EffectObservation:
        details = self._revalidation_details(context)
        generation = str(expected_generation or "").strip() or (
            self._queue_generation_from_checkpoint(context)
        )
        branch = str(expected_branch or "").strip() or str(
            details.get("integration_queue_branch") or ""
        ).strip()
        head = str(expected_head or "").strip() or str(
            details.get("integration_queue_head") or ""
        ).strip()
        fallback = {
            **self._base_receipt(action, context),
            "queue_generation": generation or None,
            "queue_branch": branch or None,
            "queue_head": head or None,
        }
        if not all((generation, branch, head)):
            return EffectObservation(False, fallback)

        captured: list[EffectObservation] = []

        def _observe(row: Any) -> bool:
            receipt = {
                **fallback,
                "queue_state": row.state,
                "queue_generation": row.authority_generation(),
                "queue_branch": row.task_branch,
                "queue_head": row.head_sha,
            }
            if row.task_branch != branch or row.head_sha != head:
                captured.append(EffectObservation(False, receipt))
                return True
            issue = self._fresh_issue(context)
            record = self._record(issue)
            if (
                issue is None
                or record is None
                or not self._queue_row_matches_issue(issue, row)
                or str(getattr(record, "task_branch", "") or "").strip()
                != branch
                or str(getattr(record, "head_sha", "") or "").strip() != head
            ):
                captured.append(EffectObservation(False, receipt))
                return True
            record_state = str(
                getattr(record, "state", "") or ""
            ).strip().lower()
            if row.state == "integrated" and record_state == "integrated":
                landing = self._landing(issue)
                applied = bool(
                    landing is not None
                    and landing.state is LandingState.LANDED
                    and landing.revision
                    in {
                        row.head_sha,
                        str(getattr(record, "integrated_sha", "") or ""),
                    }
                )
                if landing is not None:
                    receipt["landing"] = landing.to_dict()
                captured.append(EffectObservation(applied, receipt))
                return True
            if (
                row.state == "blocked"
                and record_state == "blocked"
                and self._record_authorizes_queue_row(issue, row)
            ):
                blocked = self._blocked_route(row)
                if blocked is not None:
                    route, _status, message = blocked
                    receipt.update({"route": route.value, "message": message})
                    captured.append(EffectObservation(True, receipt))
                    return True
            captured.append(EffectObservation(False, receipt))
            return True

        current = self.orchestrator.integration_queue.run_if_generation(
            self.project_id,
            context.job.task_id,
            expected_generation=generation,
            action=_observe,
        )
        if not current or not captured:
            return EffectObservation(False, fallback)
        return captured[0]

    def _exact_standalone_submission(
        self,
        context: WorkflowJobContext,
    ) -> tuple[str, str]:
        """Return the exact standalone branch/head proven by revalidation."""

        details = self._revalidation_details(context)
        expected_branch = str(details.get("task_branch") or "").strip()
        expected_head = str(details.get("task_head") or "").strip()
        expected_evidence = self._revalidated_evidence_revision(context)
        if not all((expected_branch, expected_head, expected_evidence)):
            raise WorkflowActionError(
                "standalone submission authority is missing from revalidation",
                category=WorkflowFailureCategory.STALE_EVIDENCE,
                retryable=True,
            )
        with self._issue_authority_lock(context):
            context.check_interrupted()
            issue = self._fresh_issue(context)
            record = self._record(issue)
            record_mode = str(
                getattr(record, "mode", "") or ""
            ).strip().lower()
            route_current = self._standalone_route_is_current(issue, record)
            parent_id = str(getattr(issue, "parent_id", "") or "").strip()
            if (
                issue is not None
                and isinstance(record, IntegrationRecord)
                and parent_id
                and canonicalize_status(issue.state) == READY_TO_INTEGRATE
                and record_mode == "standalone"
                and str(record.post_landed_parent_id or "").strip() == parent_id
                and record.task_branch == expected_branch
                and record.head_sha == expected_head
                and not route_current
            ):
                self._reclassify_invalid_parented_standalone(
                    context,
                    issue,
                    record,
                    expected_branch=expected_branch,
                    expected_head=expected_head,
                )
            if (
                issue is None
                or canonicalize_status(issue.state) != READY_TO_INTEGRATE
                or record is None
                or not route_current
                or record_mode not in {"", "standalone"}
                or str(getattr(record, "task_branch", "") or "").strip()
                != expected_branch
                or str(getattr(record, "head_sha", "") or "").strip()
                != expected_head
            ):
                raise WorkflowActionError(
                    "standalone submission changed after revalidation",
                    category=WorkflowFailureCategory.STALE_EVIDENCE,
                    retryable=True,
                )
            if not record_mode:
                # Legacy top-level records predate the durable delivery-mode
                # field.  Canonicalize that service-owned authority before
                # touching a queue row or forge.  Supersede this job because
                # the metadata write changes the evidence revision that the
                # replacement standalone generation must revalidate.
                self.tracker.set_metadata_field(
                    context.job.task_id,
                    "oompah.integration",
                    replace(record, mode="standalone").to_dict(),
                )
                self._request_refresh()
                raise WorkflowActionSuperseded(
                    "legacy standalone delivery mode was canonicalized",
                    replacement_generation=f"standalone-mode:{expected_head}",
                )
            facts = self.binding.collector.collect(
                issue.identifier,
                landing_requests=self._landing_request(issue),
            )
            decision = evaluate_task(issue, facts)
            if (
                decision.evidence_revision != expected_evidence
                or "standalone_delivery" not in decision.durable_jobs
            ):
                raise WorkflowActionError(
                    "standalone task evidence changed after revalidation",
                    category=WorkflowFailureCategory.STALE_EVIDENCE,
                    retryable=True,
                )
            queue = getattr(self.orchestrator, "integration_queue", None)
            row = (
                queue.get(self.project_id, context.job.task_id)
                if queue is not None
                else None
            )
            if row is not None:
                if (
                    row.task_branch != expected_branch
                    or row.head_sha != expected_head
                    or row.lease_owner is not None
                    or row.rebase_intent_pending
                    or row.rebased_publication_pending
                    or row.state not in {"ready", "cancelled"}
                    or (
                        row.state == "cancelled"
                        and row.last_error
                        != STANDALONE_RECLASSIFICATION_REASON
                    )
                ):
                    raise WorkflowActionError(
                        "standalone submission still has incompatible queue authority",
                        category=WorkflowFailureCategory.STALE_EVIDENCE,
                        retryable=True,
                    )
                retired = queue.retire_task_generation(
                    self.project_id,
                    context.job.task_id,
                    expected_generation=row.authority_generation(),
                    reason=STANDALONE_RECLASSIFICATION_REASON,
                )
                if retired is None:
                    raise WorkflowActionError(
                        "standalone queue retirement lost its exact generation",
                        category=WorkflowFailureCategory.STALE_EVIDENCE,
                        retryable=True,
                    )
        return expected_branch, expected_head

    def _standalone_observation(
        self,
        action: str,
        context: WorkflowJobContext,
        *,
        expected_review_number: str | None = None,
        expected_review_head: str | None = None,
        expected_target: str | None = None,
        expected_branch: str | None = None,
    ) -> EffectObservation:
        details = self._revalidation_details(context)
        required_branch = str(expected_branch or "").strip() or str(
            details.get("task_branch") or ""
        ).strip()
        expected_head = str(details.get("task_head") or "").strip()
        required_target = str(expected_target or "").strip() or str(
            details.get("task_target") or ""
        ).strip()
        required_review_number = str(expected_review_number or "").strip()
        required_review_head = str(expected_review_head or "").strip()
        issue = self._fresh_issue(context)
        status = canonicalize_status(getattr(issue, "state", ""))
        review_number = str(getattr(issue, "review_number", "") or "").strip()
        review_head = str(getattr(issue, "review_head", "") or "").strip()
        current_target = str(
            getattr(issue, "target_branch", "")
            or self._project_default_branch()
            or ""
        ).strip()
        record = self._record(issue)
        record_branch = str(getattr(record, "task_branch", "") or "").strip()
        record_head = str(getattr(record, "head_sha", "") or "").strip()
        record_mode = str(getattr(record, "mode", "") or "").strip().lower()
        current_branch = str(
            getattr(issue, "work_branch", "")
            or getattr(issue, "branch_name", "")
            or record_branch
            or ""
        ).strip()
        route_current = self._standalone_route_is_current(issue, record)
        exact_submission = bool(
            issue is not None
            and route_current
            and record_mode == "standalone"
            and required_branch
            and expected_head
            and current_branch == required_branch
            and record_branch == required_branch
            and record_head == expected_head
        )
        applied = bool(
            exact_submission
            and required_target
            and current_target == required_target
            and status in _POST_INTEGRATION_STATES
            and review_number
            and review_head
            and review_head == expected_head
            and (
                not required_review_number
                or review_number == required_review_number
            )
            and (
                not required_review_head
                or review_head == required_review_head
            )
        )
        return EffectObservation(
            applied,
            {
                **self._base_receipt(action, context),
                "status": status,
                "review_number": review_number or None,
                "review_head": review_head or None,
                "target_branch": current_target or None,
                "record_mode": record_mode or None,
                "submission_branch": record_branch or None,
                "submission_head": record_head or None,
            },
        )

    def observe_action(
        self, action: str, context: WorkflowJobContext
    ) -> EffectObservation:
        if action == "direct_epic_maintenance_completion":
            return self._direct_maintenance_observation(action, context)
        if action == "integration_landing_refresh":
            issue = self._fresh_issue(context)
            landing = self._landing(issue) if issue is not None else None
            return EffectObservation(
                False,
                {
                    **self._base_receipt(action, context),
                    "landing": landing.to_dict() if landing is not None else None,
                },
            )
        if action == "integration_terminal_stage":
            return self._terminal_observation(action, context)
        if action in {"parent_rollup_review", "terminal_audit_done"}:
            # These actions intentionally perform their lifecycle mutation via
            # TaskTransitionService after verification.  Revalidation fences
            # the no-op preparation receipt; no tracker mutation is hidden in
            # inspect/apply.
            return EffectObservation(False, self._base_receipt(action, context))
        if action == "historical_audit_replay_batch":
            # A live Ready task merely carries this project-maintenance job; it
            # is deliberately not the historical row being replayed.
            return EffectObservation(False, self._base_receipt(action, context))
        if action == "integration_attempt":
            return self._attempt_observation(action, context)
        if action == "integration_recovery":
            row = self._queue_row(context)
            issue = self._fresh_issue(context)
            applied = bool(
                row is not None
                and self._queue_generation_is_current(context, row)
                and row.state != "integrating"
                and self._record_authorizes_queue_row(issue, row)
            )
            return EffectObservation(
                applied,
                {
                    **self._base_receipt(action, context),
                    "queue_state": getattr(row, "state", None),
                    "queue_generation": (
                        row.authority_generation() if row is not None else None
                    ),
                },
            )
        if action == "standalone_delivery":
            return self._standalone_observation(action, context)
        if action == "epic_branch_reconciliation":
            return EffectObservation(False, self._base_receipt(action, context))
        raise AssertionError(action)

    async def _apply_terminal(
        self, action: str, context: WorkflowJobContext
    ) -> EffectResult:
        prepared_row, prepared_integrated_sha = await asyncio.to_thread(
            self._prepare_terminal_checkpoint, context
        )
        prepared_generation = prepared_row.authority_generation()
        row, integrated_sha = await asyncio.to_thread(
            lambda: self._terminal_candidate(
                context,
                expected_generation=prepared_generation,
                expected_head=prepared_row.head_sha,
            )
        )
        if integrated_sha != prepared_integrated_sha:
            raise WorkflowActionError(
                "terminal landing changed after checkpoint preparation",
                category=WorkflowFailureCategory.STALE_EVIDENCE,
                retryable=True,
            )
        await self.orchestrator._stage_integrated_task_audit(
            row,
            expected_generation=row.authority_generation(),
            expected_task_branch=row.task_branch,
            expected_head_sha=row.head_sha,
            expected_integrated_sha=integrated_sha,
        )
        observed = await asyncio.to_thread(
            lambda: self._terminal_observation(
                action,
                context,
                expected_generation=prepared_generation,
                expected_head=row.head_sha,
            )
        )
        if not observed.applied:
            raise WorkflowActionError(
                "terminal audit staging is not yet observable",
                category=WorkflowFailureCategory.TRANSIENT,
                retryable=True,
            )
        self._request_refresh()
        return EffectResult(dict(observed.receipt))

    def _prepare_rebased_authority(
        self,
        context: WorkflowJobContext,
        authority: dict[str, Any],
        rebased_head_sha: str,
        base_sha: str | None,
    ) -> bool:
        """Durably prepare one exact old-head -> rebased-head publication."""

        with self._issue_authority_lock(context, blocking=False) as owned:
            if owned is None:
                return False
            context.check_interrupted()
            replacement = str(rebased_head_sha or "").strip().lower()
            row = authority["row"]
            generation = str(authority["generation"])
            issue = self._fresh_issue(context)
            record = self._record(issue)
            current = self._queue_row(context)
            if issue is None or record is None or current is None:
                return False
            record_state = str(getattr(record, "state", "") or "").strip().lower()
            record_branch = str(
                getattr(record, "task_branch", "") or ""
            ).strip()
            record_head = str(getattr(record, "head_sha", "") or "").strip()
            if record_state != "ready" or record_branch != row.task_branch:
                return False
            if (
                current.state == "ready"
                and current.lease_owner is None
                and current.head_sha == replacement
                and current.rebased_publication_pending
                and str(getattr(current, "rebased_from_head_sha", "") or "")
                == row.head_sha
                and record_head in {row.head_sha, current.head_sha}
            ):
                advanced = current
            else:
                # Check both durable stores before the first write.  The shared
                # issue mutex prevents submission/terminal authority from
                # changing between this exact observation and the queue CAS.
                if (
                    current.authority_generation() != generation
                    or current.task_branch != row.task_branch
                    or current.head_sha != row.head_sha
                    or record_head != row.head_sha
                ):
                    return False
                advanced = self.orchestrator.integration_queue.prepare_task_publication(
                    self.project_id,
                    context.job.task_id,
                    expected_generation=generation,
                    head_sha=replacement,
                    base_sha=base_sha,
                )
            if advanced is None:
                return False
            if record_head != advanced.head_sha:
                self._write_ready_record(issue, advanced)
            authority["row"] = advanced
            authority["generation"] = advanced.authority_generation()
            context.check_interrupted()
            if not self._exact_authority(
                context,
                queue_generation=authority["generation"],
                task_branch=advanced.task_branch,
                head_sha=advanced.head_sha,
            ):
                raise RuntimeError(
                    "prepared rebased publication is not exactly observable"
                )
            return True

    def _prepare_rebase_intent(
        self,
        context: WorkflowJobContext,
        authority: dict[str, Any],
        base_sha: str,
    ) -> bool:
        """Persist executor ownership before the private Git rebase starts."""

        with self._issue_authority_lock(context, blocking=False) as owned:
            if owned is None:
                return False
            context.check_interrupted()
            row = authority["row"]
            generation = str(authority["generation"])
            if not self._exact_authority(
                context,
                queue_generation=generation,
                task_branch=row.task_branch,
                head_sha=row.head_sha,
            ):
                return False
            prepared = self.orchestrator.integration_queue.prepare_task_rebase(
                self.project_id,
                context.job.task_id,
                expected_generation=generation,
                base_sha=base_sha,
            )
            if prepared is None:
                return False
            authority["row"] = prepared
            authority["generation"] = prepared.authority_generation()
            return self._exact_authority(
                context,
                queue_generation=str(authority["generation"]),
                task_branch=prepared.task_branch,
                head_sha=prepared.head_sha,
            )

    def _abort_rebase_intent(
        self,
        context: WorkflowJobContext,
        authority: dict[str, Any],
    ) -> bool:
        """Clear the exact durable intent only after Git has been rolled back."""

        with self._issue_authority_lock(context, blocking=False) as owned:
            if owned is None:
                return False
            context.check_interrupted()
            row = authority["row"]
            current = self.orchestrator.integration_queue.abort_task_rebase(
                self.project_id,
                context.job.task_id,
                expected_generation=str(authority["generation"]),
            )
            if current is None:
                return False
            authority["row"] = current
            authority["generation"] = current.authority_generation()
            return self._exact_authority(
                context,
                queue_generation=str(authority["generation"]),
                task_branch=row.task_branch,
                head_sha=row.head_sha,
            )

    def _complete_rebased_publication(
        self,
        context: WorkflowJobContext,
        authority: dict[str, Any],
        rebased_head_sha: str,
        _base_sha: str | None,
    ) -> bool:
        """Checkpoint that the exact prepared private ref is now published."""

        with self._issue_authority_lock(context, blocking=False) as owned:
            if owned is None:
                return False
            context.check_interrupted()
            issue = self._fresh_issue(context)
            record = self._record(issue)
            prepared = authority["row"]
            if (
                issue is None
                or record is None
                or str(getattr(record, "state", "") or "").strip().lower()
                != "ready"
                or str(getattr(record, "task_branch", "") or "").strip()
                != prepared.task_branch
                or str(getattr(record, "head_sha", "") or "").strip()
                != prepared.head_sha
            ):
                return False
            completed = self.orchestrator.integration_queue.complete_task_publication(
                self.project_id,
                context.job.task_id,
                expected_generation=str(authority["generation"]),
                head_sha=rebased_head_sha,
            )
            if completed is None:
                return False
            authority["row"] = completed
            authority["generation"] = completed.authority_generation()
            return self._exact_authority(
                context,
                queue_generation=authority["generation"],
                task_branch=completed.task_branch,
                head_sha=completed.head_sha,
            )

    def _notify_integrated_peers(
        self,
        context: WorkflowJobContext,
        row: Any,
        integrated_sha: str,
    ) -> int:
        context.check_interrupted()
        issue = self._fresh_issue(context)
        record = self._record(issue)
        if (
            issue is None
            or canonicalize_status(issue.state) != READY_TO_INTEGRATE
            or record is None
            or str(getattr(record, "state", "") or "").strip().lower()
            != "ready"
            or str(getattr(record, "task_branch", "") or "").strip()
            != row.task_branch
            or str(getattr(record, "head_sha", "") or "").strip()
            != row.head_sha
        ):
            raise WorkflowActionError(
                "tracker submission changed before peer coordination checkpoint",
                category=WorkflowFailureCategory.STALE_EVIDENCE,
                retryable=True,
            )
        notify = getattr(
            self.orchestrator, "_notify_integrated_task_peers", None
        )
        if not callable(notify):
            return 0
        try:
            return int(
                notify(
                    project_id=self.project_id,
                    task_id=context.job.task_id,
                    epic_id=row.epic_id,
                    integrated_sha=integrated_sha,
                )
            )
        except Exception as exc:
            # Keep the tracker in Ready until every idempotent peer receipt is
            # durable.  A restart then re-enters this exact integration action
            # and safely retries both already-sent and unsent peers.
            raise WorkflowActionError(
                f"integration peer coordination is not durable: {exc}",
                category=WorkflowFailureCategory.TRANSIENT,
                retryable=True,
            ) from exc

    def _write_integrated_record(
        self,
        context: WorkflowJobContext,
        row: Any,
        result: IntegrationExecutionResult,
    ) -> None:
        context.check_interrupted()
        current = self._queue_row(context)
        if (
            current is None
            or current.state != "integrated"
            or current.task_branch != row.task_branch
            or current.head_sha != row.head_sha
            or (
                str(getattr(current, "integrated_sha", "") or "").strip()
                and str(getattr(current, "integrated_sha", "") or "").strip()
                != str(result.integrated_sha or row.head_sha).strip()
            )
        ):
            raise WorkflowActionError(
                "integration queue generation changed before metadata checkpoint",
                category=WorkflowFailureCategory.STALE_EVIDENCE,
                retryable=True,
            )
        issue = self._fresh_issue(context)
        existing = self._record(issue)
        if (
            issue is None
            or canonicalize_status(issue.state) != READY_TO_INTEGRATE
            or existing is None
            or str(getattr(existing, "state", "") or "").strip().lower()
            != "ready"
            or str(getattr(existing, "task_branch", "") or "").strip()
            != row.task_branch
            or str(getattr(existing, "head_sha", "") or "").strip()
            != row.head_sha
        ):
            raise WorkflowActionError(
                "tracker submission changed before integrated metadata checkpoint",
                category=WorkflowFailureCategory.STALE_EVIDENCE,
                retryable=True,
            )
        dependency_heads: dict[str, str] = {}
        try:
            issues = self.tracker.fetch_all_issues()
            dependencies = self.orchestrator._integration_dependency_map(
                issues, [row]
            ).get(row.task_id, ())
            aliases: dict[str, Issue] = {}
            for candidate in issues:
                for alias in (candidate.id, candidate.identifier):
                    if str(alias or "").strip():
                        aliases[str(alias).strip()] = candidate
            dependency_ids = set(str(value) for value in dependencies)
            for dependency_id in tuple(dependency_ids):
                candidate = aliases.get(dependency_id)
                if candidate is not None:
                    dependency_ids.update(
                        str(value).strip()
                        for value in (candidate.id, candidate.identifier)
                        if str(value or "").strip()
                    )
            for dependency_id in dependency_ids:
                dependency = self.orchestrator.integration_queue.get(
                    self.project_id, dependency_id
                )
                if dependency is not None and dependency.state == "integrated":
                    dependency_heads[dependency.task_id] = dependency.head_sha
        except Exception:  # noqa: BLE001 - optional coordination enrichment
            # Some standalone tracker adapters expose no whole-graph read.
            # The exact integration receipt remains valid without optional
            # coordination metadata; a full reconcile can enrich it later.
            dependency_heads = {}
        # Optional graph enrichment and peer notification may block in
        # adapters. Re-prove the exact workflow lease immediately before the
        # tracker commit so a timed-out quarantined invocation cannot write
        # after its authority was fenced.
        context.check_interrupted()
        self.tracker.set_metadata_field(
            context.job.task_id,
            "oompah.integration",
            IntegrationRecord(
                state="integrated",
                mode="queue",
                task_branch=row.task_branch,
                base_branch=(
                    row.base_branch
                    or self.orchestrator.project_store.epic_branch_name(row.epic_id)
                ),
                base_sha=result.expected_epic_sha or row.base_sha,
                head_sha=result.rebased_task_sha or row.head_sha,
                integrated_sha=result.integrated_sha or row.head_sha,
                attempts=current.attempts,
                submitted_at=getattr(existing, "submitted_at", None)
                or row.submitted_at,
                dependency_heads=dependency_heads,
            ).to_dict(),
        )

    async def _apply_integration_attempt(
        self, action: str, context: WorkflowJobContext
    ) -> EffectResult:
        checkpoint_generation = self._queue_generation_from_checkpoint(context)
        row = await asyncio.to_thread(
            self._reconcile_attempt_queue_authority, context
        )
        generation = row.authority_generation()
        if row.state == "integrated":
            def _recover_integrated() -> EffectResult:
                issue = self._issue(context)
                if not self._record_authorizes_queue_row(issue, row):
                    raise WorkflowActionError(
                        "integrated queue row no longer matches tracker head authority",
                        category=WorkflowFailureCategory.STALE_EVIDENCE,
                        retryable=True,
                    )
                record = self._record(issue)
                landing = self._landing(issue) if issue is not None else None
                target_sha = (
                    self._landing_target_sha(landing)
                    if landing is not None and landing.state is LandingState.LANDED
                    else None
                )
                result = IntegrationExecutionResult(
                    "integrated",
                    "recovered integrated queue checkpoint",
                    expected_epic_sha=row.base_sha,
                    rebased_task_sha=row.head_sha,
                    integrated_sha=str(
                        getattr(row, "integrated_sha", "")
                        or target_sha
                        or getattr(record, "integrated_sha", "")
                        or row.head_sha
                    ),
                )
                with self._issue_authority_lock(context):
                    context.check_interrupted()
                    record_state = str(
                        getattr(record, "state", "") or ""
                    ).strip().lower()
                    if record_state == "ready":
                        notified = self._notify_integrated_peers(
                            context,
                            row,
                            result.integrated_sha or row.head_sha,
                        )
                        self._write_integrated_record(context, row, result)
                    else:
                        # The only normal writer order is queue -> peers ->
                        # integrated tracker metadata.  An already-integrated
                        # record therefore proves the idempotent peer checkpoint
                        # completed before the prior worker exited.
                        notified = 0
                return EffectResult(
                    {
                        **dict(self._attempt_observation(action, context).receipt),
                        "coordination_notified": notified,
                    }
                )

            return await asyncio.to_thread(_recover_integrated)
        if row.state == "blocked":
            def _recover_blocked() -> EffectResult:
                issue = self._issue(context)
                record = self._record(issue)
                blocked = self._blocked_route(row)
                if blocked is None or not self._record_authorizes_queue_row(issue, row):
                    raise WorkflowActionError(
                        "blocked queue row no longer matches tracker head authority",
                        category=WorkflowFailureCategory.STALE_EVIDENCE,
                        retryable=True,
                    )
                route, status, message = blocked
                if (
                    str(getattr(record, "state", "") or "").strip().lower()
                    == "ready"
                ):
                    with self._issue_authority_lock(context):
                        context.check_interrupted()
                        fresh = self._fresh_issue(context)
                        fresh_record = self._record(fresh)
                        current_row = self._queue_row(context)
                        if (
                            fresh is None
                            or fresh_record is None
                            or canonicalize_status(fresh.state)
                            != READY_TO_INTEGRATE
                            or str(
                                getattr(fresh_record, "state", "") or ""
                            ).strip().lower()
                            != "ready"
                            or str(
                                getattr(fresh_record, "task_branch", "") or ""
                            ).strip()
                            != row.task_branch
                            or str(
                                getattr(fresh_record, "head_sha", "") or ""
                            ).strip()
                            != row.head_sha
                            or current_row is None
                            or current_row.authority_generation()
                            != row.authority_generation()
                        ):
                            raise WorkflowActionError(
                                "blocked recovery authority changed before metadata checkpoint",
                                category=WorkflowFailureCategory.STALE_EVIDENCE,
                                retryable=True,
                            )
                        self.tracker.set_metadata_field(
                            context.job.task_id,
                            "oompah.integration",
                            IntegrationRecord(
                                state="blocked",
                                mode="queue",
                                task_branch=row.task_branch,
                                base_branch=(
                                    row.base_branch
                                    or self.orchestrator.project_store.epic_branch_name(
                                        row.epic_id
                                    )
                                ),
                                base_sha=row.base_sha,
                                head_sha=row.head_sha,
                                attempts=row.attempts,
                                submitted_at=(
                                    getattr(fresh_record, "submitted_at", None)
                                    or row.submitted_at
                                ),
                                last_error=message,
                            ).to_dict(),
                        )
                return EffectResult(
                    {
                        **self._base_receipt(action, context),
                        "route": route.value,
                        "status": status,
                        "message": message,
                        "queue_state": "blocked",
                        "recovered_after_queue_checkpoint": True,
                    }
                )

            effect = await asyncio.to_thread(_recover_blocked)
            self._request_refresh()
            return effect
        if row.state != "ready" or row.lease_owner is not None:
            raise WorkflowActionError(
                "integration row is owned by another execution generation",
                category=WorkflowFailureCategory.TRANSIENT,
                retryable=True,
            )
        if generation == checkpoint_generation:
            _issue, row = await asyncio.to_thread(
                self._repair_rebased_tracker_checkpoint, context
            )
        generation = row.authority_generation()
        authority: dict[str, Any] = {
            "row": row,
            "generation": generation,
        }

        def _consume_retry() -> tuple[Any | None, bool]:
            with self._issue_authority_lock(context):
                context.check_interrupted()
                if row.rebased_publication_pending or row.rebase_intent_pending:
                    return row, False
                return self.orchestrator.integration_queue.consume_retry_generation(
                    self.project_id,
                    context.job.task_id,
                    expected_generation=generation,
                )

        consumed_row, retry_forced = await asyncio.to_thread(_consume_retry)
        if consumed_row is None:
            raise WorkflowActionError(
                "integration retry authority changed before execution",
                category=WorkflowFailureCategory.STALE_EVIDENCE,
                retryable=True,
            )
        authority["row"] = consumed_row
        authority["generation"] = consumed_row.authority_generation()
        row = consumed_row
        landing = await asyncio.to_thread(
            lambda: self._landing(self._issue(context))
        )
        if (
            landing is not None
            and landing.state is LandingState.LANDED
            and not (row.rebase_intent_pending or row.rebased_publication_pending)
        ):
            target_sha = self._landing_target_sha(landing)
            result = IntegrationExecutionResult(
                "integrated",
                "recovered exact landing after executor restart",
                expected_epic_sha=row.base_sha,
                rebased_task_sha=row.head_sha,
                integrated_sha=target_sha or row.head_sha,
            )
        else:
            result = await asyncio.to_thread(
                self.orchestrator._execute_integration_item,
                row,
                workflow_authority=lambda: self._exact_authority(
                    context,
                    queue_generation=str(authority["generation"]),
                    task_branch=authority["row"].task_branch,
                    head_sha=authority["row"].head_sha,
                ),
                rebase_intent_prepare=lambda base: self._prepare_rebase_intent(
                    context,
                    authority,
                    base,
                ),
                rebase_intent_abort=lambda: self._abort_rebase_intent(
                    context,
                    authority,
                ),
                rebased_head_prepare=lambda head, base: (
                    self._prepare_rebased_authority(
                        context,
                        authority,
                        head,
                        base,
                    )
                ),
                rebased_head_checkpoint=lambda head, base: (
                    self._complete_rebased_publication(
                        context,
                        authority,
                        head,
                        base,
                    )
                ),
                gate_generation=f"workflow:{context.job.job_id}:{context.job.generation}",
                retry_forced=retry_forced,
            )
            row = authority["row"]
            generation = str(authority["generation"])
        classified = classify_integration_result(result)
        if classified.route is IntegrationRoute.RETRY:
            raise WorkflowActionError(
                result.message,
                category=classified.category,
                retryable=True,
            )
        if classified.route is IntegrationRoute.SUPERSEDED:
            raise WorkflowActionError(
                result.message,
                category=WorkflowFailureCategory.STALE_EVIDENCE,
                retryable=True,
            )
        if classified.route is IntegrationRoute.ACTION_REQUIRED:
            raise WorkflowActionError(
                result.message,
                category=classified.category,
                retryable=False,
            )
        target_state = (
            "integrated"
            if classified.route is IntegrationRoute.LANDED
            else "blocked"
        )

        def _checkpoint_effect() -> tuple[Any, int]:
            with self._issue_authority_lock(context):
                if not self._exact_authority(
                    context,
                    queue_generation=generation,
                    task_branch=row.task_branch,
                    head_sha=row.head_sha,
                ):
                    raise WorkflowActionError(
                        "integration authority changed before effect checkpoint",
                        category=WorkflowFailureCategory.STALE_EVIDENCE,
                        retryable=True,
                    )
                finished = self.orchestrator.integration_queue.finish_task_generation(
                    self.project_id,
                    context.job.task_id,
                    expected_generation=generation,
                    state=target_state,
                    error=(
                        None
                        if target_state == "integrated"
                        else f"{result.status}:{result.message}"
                    ),
                    integrated_sha=(
                        result.integrated_sha or row.head_sha
                        if target_state == "integrated"
                        else None
                    ),
                )
                if finished is None:
                    raise WorkflowActionError(
                        "integration queue generation changed before effect checkpoint",
                        category=WorkflowFailureCategory.STALE_EVIDENCE,
                        retryable=True,
                    )
                if target_state == "integrated":
                    notified = self._notify_integrated_peers(
                        context,
                        row,
                        result.integrated_sha or row.head_sha,
                    )
                    self._write_integrated_record(context, row, result)
                else:
                    notified = 0
                    existing = self._record(self._issue(context))
                    self.tracker.set_metadata_field(
                        context.job.task_id,
                        "oompah.integration",
                        IntegrationRecord(
                            state="blocked",
                            mode="queue",
                            task_branch=row.task_branch,
                            base_branch=(
                                row.base_branch
                                or self.orchestrator.project_store.epic_branch_name(
                                    row.epic_id
                                )
                            ),
                            base_sha=result.expected_epic_sha or row.base_sha,
                            head_sha=row.head_sha,
                            attempts=finished.attempts,
                            submitted_at=getattr(existing, "submitted_at", None)
                            or row.submitted_at,
                            last_error=result.message,
                        ).to_dict(),
                    )
                return finished, notified

        _finished, notified = await asyncio.to_thread(_checkpoint_effect)
        self._request_refresh()
        return EffectResult(
            {
                **self._base_receipt(action, context),
                "route": classified.route.value,
                "status": result.status,
                "message": result.message,
                "expected_epic_sha": result.expected_epic_sha,
                "rebased_task_sha": result.rebased_task_sha,
                "integrated_sha": result.integrated_sha,
                "queue_state": target_state,
                "queue_generation": _finished.authority_generation(),
                "queue_branch": _finished.task_branch,
                "queue_head": _finished.head_sha,
                "coordination_notified": notified,
            }
        )

    def _apply_recovery(
        self, action: str, context: WorkflowJobContext
    ) -> EffectResult:
        generation = self._queue_generation_from_checkpoint(context)
        checkpoint_details = self._revalidation_details(context)
        queue_was_present = bool(
            checkpoint_details.get("integration_queue_present", False)
        )
        original_branch = str(
            checkpoint_details.get("integration_queue_branch")
            or checkpoint_details.get("task_branch")
            or ""
        ).strip()
        original_head = str(
            checkpoint_details.get("integration_queue_head")
            or checkpoint_details.get("task_head")
            or ""
        ).strip()
        original_evidence = self._revalidated_evidence_revision(context)
        with self._issue_authority_lock(context):
            context.check_interrupted()
            issue = self._fresh_issue(context)
            if issue is None:
                raise WorkflowActionError(
                    "integration recovery task disappeared",
                    category=WorkflowFailureCategory.STALE_EVIDENCE,
                    retryable=True,
                )
            if canonicalize_status(issue.state) != READY_TO_INTEGRATE:
                raise WorkflowActionError(
                    "integration recovery task is no longer Ready to Integrate",
                    category=WorkflowFailureCategory.STALE_EVIDENCE,
                    retryable=True,
                )
            record = self._record(issue)
            requests = self._landing_request(issue)
            current_facts = self.binding.collector.collect(
                issue.identifier, landing_requests=requests
            )
            current_decision = evaluate_task(issue, current_facts)
            if (
                not original_evidence
                or current_decision.evidence_revision != original_evidence
            ):
                raise WorkflowActionError(
                    "integration recovery task evidence changed after revalidation",
                    category=WorkflowFailureCategory.STALE_EVIDENCE,
                    retryable=True,
                )
            row = self._queue_row(context)
            if queue_was_present:
                if (
                    row is None
                    or not generation
                    or row.authority_generation() != generation
                    or row.task_branch != original_branch
                    or row.head_sha != original_head
                ):
                    raise WorkflowActionError(
                        "integration recovery generation changed after revalidation",
                        category=WorkflowFailureCategory.STALE_EVIDENCE,
                        retryable=True,
                    )
            elif row is not None:
                raise WorkflowActionError(
                    "integration recovery cannot adopt a row created after revalidation",
                    category=WorkflowFailureCategory.STALE_EVIDENCE,
                    retryable=True,
                )

            if row is None:
                parent_id = str(getattr(issue, "parent_id", "") or "").strip()
                branch = str(
                    getattr(record, "task_branch", "")
                    or getattr(issue, "work_branch", "")
                    or ""
                ).strip()
                head = str(
                    getattr(record, "head_sha", "")
                    or getattr(issue, "head_sha", "")
                    or ""
                ).strip()
                base_branch = str(
                    getattr(record, "base_branch", "")
                    or getattr(issue, "target_branch", "")
                    or ""
                ).strip()
                if branch != original_branch or head != original_head:
                    raise WorkflowActionError(
                        "integration recovery source changed after revalidation",
                        category=WorkflowFailureCategory.STALE_EVIDENCE,
                        retryable=True,
                    )
                if not parent_id or not branch or not head or not base_branch:
                    raise WorkflowActionError(
                        "integration recovery lacks an exact parent, branch, head, "
                        "or hierarchy target",
                        category=WorkflowFailureCategory.STALE_EVIDENCE,
                        retryable=False,
                    )
                row = self.orchestrator.integration_queue.enqueue_if_absent(
                    project_id=self.project_id,
                    epic_id=parent_id,
                    task_id=context.job.task_id,
                    task_branch=branch,
                    head_sha=head,
                    base_branch=base_branch,
                    base_sha=getattr(record, "base_sha", None),
                    priority=getattr(issue, "priority", None),
                    submitted_at=getattr(record, "submitted_at", None),
                )
                if row is None:
                    raise WorkflowActionError(
                        "integration recovery lost the exact absent-row fence",
                        category=WorkflowFailureCategory.STALE_EVIDENCE,
                        retryable=True,
                    )
            elif row.state == "integrating":
                recovered = (
                    self.orchestrator.integration_queue.recover_task_generation(
                        self.project_id,
                        context.job.task_id,
                        expected_generation=generation,
                    )
                )
                if recovered is None:
                    raise WorkflowActionError(
                        "integration lease is still live or its generation changed",
                        category=WorkflowFailureCategory.TRANSIENT,
                        retryable=True,
                    )
                row = recovered
            elif row.state == "cancelled":
                issue_branch = str(getattr(issue, "work_branch", "") or "").strip()
                issue_head = str(getattr(issue, "head_sha", "") or "").strip()
                if issue_branch != row.task_branch or issue_head != row.head_sha:
                    raise WorkflowActionError(
                        "cancelled integration row no longer matches task authority",
                        category=WorkflowFailureCategory.STALE_EVIDENCE,
                        retryable=True,
                    )
                restored = self.orchestrator.integration_queue.restore_cancelled(
                    self.project_id,
                    row.task_id,
                    expected_head_sha=row.head_sha,
                    expected_task_branch=row.task_branch,
                    expected_epic_id=row.epic_id,
                    expected_generation=generation,
                )
                row = self._queue_row(context)
                if not restored or row is None or row.state != "ready":
                    raise WorkflowActionError(
                        "cancelled integration generation changed before restore",
                        category=WorkflowFailureCategory.STALE_EVIDENCE,
                        retryable=True,
                    )

            def _repair_tracker_checkpoint(current_row: Any) -> bool:
                context.check_interrupted()
                current_issue = self._fresh_issue(context)
                current_record = self._record(current_issue)
                record_state = str(
                    getattr(current_record, "state", "") or ""
                ).strip().lower()
                record_branch = str(
                    getattr(current_record, "task_branch", "") or ""
                ).strip()
                record_head = str(
                    getattr(current_record, "head_sha", "") or ""
                ).strip()
                issue_branch = str(
                    getattr(current_issue, "work_branch", "")
                    or getattr(current_issue, "branch_name", "")
                    or ""
                ).strip()
                issue_head = str(
                    getattr(current_issue, "head_sha", "") or ""
                ).strip()
                exact_source = (
                    issue_branch == current_row.task_branch
                    and issue_head == current_row.head_sha
                    if current_record is None
                    else record_branch == current_row.task_branch
                    and record_head == current_row.head_sha
                )
                compatible_states = {
                    "ready": {"", "ready"},
                    "blocked": {"", "ready", "blocked"},
                    "integrated": {"", "ready", "integrated"},
                }.get(current_row.state, set())
                if not exact_source or record_state not in compatible_states:
                    return False
                context.check_interrupted()

                # Reconstruct the missing/incomplete tracker fact while the
                # exact queue generation is locked against replacement.
                if current_row.state == "ready":
                    if not self._record_authorizes_queue_row(
                        current_issue, current_row
                    ):
                        self._write_ready_record(current_issue, current_row)
                elif current_row.state == "blocked":
                    if record_state != "blocked":
                        self.tracker.set_metadata_field(
                            context.job.task_id,
                            "oompah.integration",
                            IntegrationRecord(
                                state="blocked",
                                mode="queue",
                                task_branch=current_row.task_branch,
                                base_branch=(
                                    current_row.base_branch
                                    or self.orchestrator.project_store.epic_branch_name(
                                        current_row.epic_id
                                    )
                                ),
                                base_sha=current_row.base_sha,
                                head_sha=current_row.head_sha,
                                attempts=current_row.attempts,
                                submitted_at=(
                                    getattr(current_record, "submitted_at", None)
                                    or current_row.submitted_at
                                ),
                                last_error=(
                                    current_row.last_error
                                    or "integration recovery required"
                                ),
                            ).to_dict(),
                        )
                elif current_row.state == "integrated":
                    if record_state != "integrated":
                        if current_record is None:
                            self._write_ready_record(current_issue, current_row)
                        self._notify_integrated_peers(
                            context,
                            current_row,
                            current_row.integrated_sha or current_row.head_sha,
                        )
                        self._write_integrated_record(
                            context,
                            current_row,
                            IntegrationExecutionResult(
                                "integrated",
                                "recovered exact integrated queue checkpoint",
                                expected_epic_sha=current_row.base_sha,
                                rebased_task_sha=current_row.head_sha,
                                integrated_sha=(
                                    current_row.integrated_sha
                                    or current_row.head_sha
                                ),
                            ),
                        )
                else:
                    return False
                return self._record_authorizes_queue_row(
                    self._fresh_issue(context), current_row
                )

            row_generation = row.authority_generation()
            repaired = self.orchestrator.integration_queue.run_if_generation(
                self.project_id,
                context.job.task_id,
                expected_generation=row_generation,
                action=_repair_tracker_checkpoint,
            )
            if not repaired:
                raise WorkflowActionError(
                    "integration recovery queue row no longer matches task authority",
                    category=WorkflowFailureCategory.STALE_EVIDENCE,
                    retryable=True,
                )
            row = self._queue_row(context)
            if row is None or row.authority_generation() != row_generation:
                raise WorkflowActionError(
                    "integration recovery tracker checkpoint is not durable",
                    category=WorkflowFailureCategory.TRANSIENT,
                    retryable=True,
                )
        self._request_refresh()
        return EffectResult(
            {
                **self._base_receipt(action, context),
                "source_queue_present": queue_was_present,
                "source_queue_generation": generation or None,
                "source_evidence_revision": original_evidence,
                "source_task_branch": original_branch,
                "source_task_head": original_head,
                "queue_state": row.state,
                "queue_generation": row.authority_generation(),
                "queue_head": row.head_sha,
            }
        )

    async def apply_action(
        self, action: str, context: WorkflowJobContext
    ) -> EffectResult:
        if action == "direct_epic_maintenance_completion":
            context.check_interrupted()
            details = self._revalidation_details(context)
            expected_evidence = self._revalidated_evidence_revision(context)
            expected_branch = str(details.get("task_branch") or "").strip()
            expected_head = str(details.get("task_head") or "").strip()
            expected_status = canonicalize_status(details.get("task_status"))
            async with self._async_issue_authority_lock(context):
                context.check_interrupted()
                issue = await asyncio.to_thread(self._fresh_issue, context)
                record = self._record(issue)
                if (
                    issue is None
                    or not isinstance(record, IntegrationRecord)
                    or canonicalize_status(issue.state) != expected_status
                    or not (
                        direct_epic_maintenance_completion_ready(issue, record)
                        or direct_epic_maintenance_handoff_ready(issue, record)
                    )
                    or record.task_branch != expected_branch
                    or record.head_sha != expected_head
                ):
                    raise WorkflowActionError(
                        "direct epic maintenance authority changed after revalidation",
                        category=WorkflowFailureCategory.STALE_EVIDENCE,
                        retryable=True,
                    )
                facts = await asyncio.to_thread(
                    self.binding.collector.collect,
                    issue.identifier,
                    landing_requests=(),
                )
                decision = evaluate_task(issue, facts)
                if (
                    action not in decision.durable_jobs
                    or decision.evidence_revision != expected_evidence
                ):
                    raise WorkflowActionError(
                        "direct epic maintenance evidence changed after revalidation",
                        category=WorkflowFailureCategory.STALE_EVIDENCE,
                        retryable=True,
                    )
                completion = (
                    await self.orchestrator.complete_direct_epic_maintenance_submission(
                        issue,
                        record,
                        self.project_id,
                        _authority_owned=True,
                    )
                )
            if completion is None:
                raise WorkflowActionError(
                    "direct epic maintenance classification changed during completion",
                    category=WorkflowFailureCategory.STALE_EVIDENCE,
                    retryable=True,
                )
            completed, message, completed_record = completion
            if not completed:
                raise WorkflowActionError(
                    message,
                    category=WorkflowFailureCategory.TRANSIENT,
                    retryable=True,
                )
            completed_head = str(
                getattr(completed_record, "integrated_sha", None)
                or getattr(completed_record, "head_sha", None)
                or ""
            ).strip()
            context.check_interrupted()
            self._request_refresh()
            return EffectResult(
                {
                    **self._base_receipt(action, context),
                    "source_evidence_revision": expected_evidence,
                    "task_status": expected_status,
                    "task_branch": expected_branch,
                    "task_head": completed_head or expected_head,
                    "message": message,
                }
            )
        if action == "integration_landing_refresh":
            def _refresh_landing() -> LandingFact:
                issue = self._issue(context)
                row = self._queue_row(context)
                expected_queue = self._queue_generation_from_checkpoint(context)
                if expected_queue and not self._queue_generation_is_current(
                    context, row
                ):
                    raise WorkflowActionError(
                        "landing queue generation changed after revalidation",
                        category=WorkflowFailureCategory.STALE_EVIDENCE,
                        retryable=True,
                    )
                landing = self._landing(issue) if issue is not None else None
                if landing is None or landing.state is not LandingState.LANDED:
                    raise WorkflowActionError(
                        "exact landing evidence is temporarily unavailable",
                        category=WorkflowFailureCategory.TRANSIENT,
                        retryable=True,
                    )
                return landing

            landing = await asyncio.to_thread(_refresh_landing)
            self._request_refresh()
            return EffectResult(
                {
                    **self._base_receipt(action, context),
                    "landing": landing.to_dict(),
                }
            )
        if action == "integration_terminal_stage":
            return await self._apply_terminal(action, context)
        if action in {"parent_rollup_review", "terminal_audit_done"}:
            issue = await asyncio.to_thread(self._fresh_issue, context)
            if issue is None:
                raise WorkflowActionError(
                    "transition preparation lost task authority",
                    category=WorkflowFailureCategory.STALE_EVIDENCE,
                    retryable=True,
                )
            requests = (
                ()
                if action == "terminal_audit_done"
                else self._landing_request(issue, include_ready=True)
            )
            facts = await asyncio.to_thread(
                self.binding.collector.collect,
                issue.identifier,
                landing_requests=requests,
            )
            decision = evaluate_task(issue, facts)
            expected_evidence = self._revalidated_evidence_revision(context)
            rollup_authority = (
                self._rollup_head_authority(
                    issue,
                    requests=requests,
                    facts=facts,
                    decision=decision,
                )
                if action == "parent_rollup_review"
                else None
            )
            expected_rollup_authority = (
                self._checkpoint_rollup_authority(context)
                if action == "parent_rollup_review"
                else None
            )
            if (
                action not in decision.durable_jobs
                or decision.evidence_revision != expected_evidence
                or (
                    action == "parent_rollup_review"
                    and (
                        rollup_authority is None
                        or rollup_authority != expected_rollup_authority
                    )
                )
            ):
                raise WorkflowActionError(
                    f"{action} evidence changed after revalidation",
                    category=WorkflowFailureCategory.STALE_EVIDENCE,
                    retryable=True,
                )
            receipt = {
                **self._base_receipt(action, context),
                "decision_reason": decision.reason_code,
                "evidence_revision": decision.evidence_revision,
                "requested_status": (
                    MERGED if action == "parent_rollup_review" else DONE
                ),
            }
            if rollup_authority is not None:
                receipt.update(rollup_authority.receipt())
            return EffectResult(receipt)
        if action == "historical_audit_replay_batch":
            replay = getattr(
                self.orchestrator,
                "_replay_project_integrated_audit_batch",
                None,
            )
            if not callable(replay):
                raise WorkflowActionError(
                    "project-scoped historical audit replay is unavailable",
                    category=WorkflowFailureCategory.PERMANENT,
                    retryable=False,
                )
            payload = context.job.payload or {}
            receipt = await replay(
                project_id=self.project_id,
                expected_cursor=payload.get("cursor"),
            )
            if receipt.get("error"):
                raise WorkflowActionError(
                    str(receipt["error"]),
                    category=WorkflowFailureCategory.TRANSIENT,
                    retryable=True,
                )
            rendered = {**self._base_receipt(action, context), **dict(receipt)}
            if bool(receipt.get("deferred")):
                successor = schedule_project_historical_replay(
                    self.orchestrator,
                    self.orchestrator.workflow_job_store,
                    self.project_id,
                )
                rendered["successor_job_id"] = successor.job_id if successor else None
                rendered["successor_generation"] = (
                    successor.generation if successor else None
                )
            return EffectResult(rendered)
        if action == "integration_attempt":
            return await self._apply_integration_attempt(action, context)
        if action == "integration_recovery":
            return await asyncio.to_thread(self._apply_recovery, action, context)
        if action == "standalone_delivery":
            expected_branch, expected_head = await asyncio.to_thread(
                self._exact_standalone_submission, context
            )

            def _workflow_authority_locally_current() -> bool:
                try:
                    context.check_interrupted()
                except Exception:
                    return False
                return True

            def _workflow_authority_current() -> bool:
                if not _workflow_authority_locally_current():
                    return False
                store = getattr(
                    self.landing_request_resolver,
                    "project_store",
                    None,
                ) or getattr(self.orchestrator, "project_store", None)
                lock_factory = getattr(store, "project_write_lock", None)
                project_lock = (
                    lock_factory(self.project_id)
                    if callable(lock_factory)
                    else None
                )
                lock_context = project_lock or contextlib.nullcontext()
                with lock_context:
                    # The lease can be revoked while this exact barrier waits
                    # for an unrelated project mutation.  Recheck after lock
                    # acquisition and again after the route read so contention
                    # cannot hide a concurrent durable-workflow cancellation.
                    if not _workflow_authority_locally_current():
                        return False
                    issue = self._fresh_issue(context)
                    record = self._record(issue)
                    current = bool(
                        issue is not None
                        and isinstance(record, IntegrationRecord)
                        and canonicalize_status(issue.state)
                        == READY_TO_INTEGRATE
                        and record.mode == "standalone"
                        and record.task_branch == expected_branch
                        and record.head_sha == expected_head
                        and self._standalone_route_is_current(issue, record)
                    )
                    return bool(
                        current and _workflow_authority_locally_current()
                    )

            delivery_outcome = await asyncio.to_thread(
                self.orchestrator._reconcile_one_standalone_ready_to_integrate_task,
                self.project_id,
                context.job.task_id,
                expected_task_branch=expected_branch,
                expected_head_sha=expected_head,
                workflow_generation=(
                    f"{context.job.job_id}:{context.job.generation}:"
                    f"{str(getattr(context.job, 'lease_token', '') or '')}"
                ),
                workflow_authority_check=_workflow_authority_current,
                workflow_local_authority_check=(
                    _workflow_authority_locally_current
                ),
            )
            supersession = self._standalone_resubmission_supersession(
                delivery_outcome,
                expected_head=expected_head,
            )
            if supersession is not None:
                observed_head, reason, review_head, review_id = supersession
                review_evidence = ""
                if review_head is not None:
                    review_label = f" #{review_id}" if review_id else ""
                    review_evidence = (
                        f"; review{review_label} "
                        f"observed head {review_head}"
                    )
                raise WorkflowActionSuperseded(
                    "standalone delivery accepted head "
                    f"{expected_head} was superseded by remote branch head "
                    f"{observed_head}{review_evidence}; explicit exact-head "
                    f"resubmission is required ({reason})",
                    replacement_generation=(
                        f"standalone-resubmission-required:{observed_head}"
                    ),
                )
            observation = await asyncio.to_thread(
                self._standalone_observation,
                action,
                context,
            )
            if not observation.applied:
                if delivery_outcome == "capacity_wait":
                    raise WorkflowAdministrativeDeferral(
                        "standalone delivery is waiting for review capacity",
                        effect_not_started=True,
                    )
                raise WorkflowActionError(
                    "standalone delivery is waiting for an exact forge effect",
                    category=WorkflowFailureCategory.TRANSIENT,
                    retryable=True,
                )
            self._request_refresh()
            return EffectResult(dict(observation.receipt))
        if action == "epic_branch_reconciliation":
            issue, row = await asyncio.to_thread(
                lambda: (self._issue(context), self._queue_row(context))
            )
            if issue is None or row is None:
                raise WorkflowActionError(
                    "exact integration row is unavailable for branch repair",
                    category=WorkflowFailureCategory.STALE_EVIDENCE,
                    retryable=True,
                )
            if not self._queue_generation_is_current(context, row):
                raise WorkflowActionError(
                    "epic repair queue generation changed after revalidation",
                    category=WorkflowFailureCategory.STALE_EVIDENCE,
                    retryable=True,
                )
            issues = await asyncio.to_thread(self.tracker.fetch_all_issues)
            dependency_map, satisfied = await asyncio.to_thread(
                lambda: (
                    self.orchestrator._integration_dependency_map(issues, [row]),
                    self.orchestrator._integration_satisfied_dependencies(
                        issues,
                        [row],
                        project_id=self.project_id,
                        epic_id=row.epic_id,
                    ),
                )
            )
            expected_generation = self._queue_generation_from_checkpoint(context)

            def _repair_exact_generation() -> bool:
                def _repair(current: Any) -> bool:
                    context.check_interrupted()
                    return bool(
                        self.orchestrator._detect_and_repair_integration_queue_staleness_block(
                            project_id=self.project_id,
                            epic_id=current.epic_id,
                            issues=issues,
                            queue_items=[current],
                            dependency_map=dependency_map,
                            satisfied=satisfied,
                            expected_generation=current.authority_generation(),
                            authority_check=lambda: (
                                context.check_interrupted() is None
                            ),
                        )
                    )

                return self.orchestrator.integration_queue.run_if_generation(
                    self.project_id,
                    context.job.task_id,
                    expected_generation=expected_generation,
                    action=_repair,
                )

            scheduled = await asyncio.to_thread(_repair_exact_generation)
            if not scheduled:
                raise WorkflowActionError(
                    "exact epic branch repair is not yet observable",
                    category=WorkflowFailureCategory.TRANSIENT,
                    retryable=True,
                )
            self._request_refresh()
            return EffectResult(
                {
                    **self._base_receipt(action, context),
                    "repair_scheduled": True,
                    "epic_id": row.epic_id,
                    "queue_generation": row.authority_generation(),
                }
            )
        raise AssertionError(action)

    def verify_action(
        self,
        action: str,
        context: WorkflowJobContext,
        effect: EffectResult,
    ) -> VerificationResult:
        if action == "direct_epic_maintenance_completion":
            expected_head = str(effect.receipt.get("task_head") or "").strip()
            observation = self._direct_maintenance_observation(
                action,
                context,
                expected_head=expected_head,
            )
            exact_receipt = bool(
                effect.receipt.get("source_evidence_revision")
                == self._revalidated_evidence_revision(context)
                and effect.receipt.get("task_branch")
                == str(
                    self._revalidation_details(context).get("task_branch") or ""
                ).strip()
                and expected_head
            )
            return VerificationResult(
                bool(exact_receipt and observation.applied),
                {**dict(effect.receipt), **dict(observation.receipt)},
                (
                    None
                    if exact_receipt and observation.applied
                    else "exact direct maintenance completion is not durable"
                ),
            )
        if action == "integration_attempt":
            route = str(effect.receipt.get("route") or "")
            observation = self._attempt_observation(
                action,
                context,
                expected_generation=str(
                    effect.receipt.get("queue_generation") or ""
                ).strip()
                or None,
                expected_branch=str(
                    effect.receipt.get("queue_branch") or ""
                ).strip()
                or None,
                expected_head=str(effect.receipt.get("queue_head") or "").strip()
                or None,
            )
            if route in {IntegrationRoute.REBASE.value, IntegrationRoute.CI_FIX.value}:
                verified = observation.applied and str(
                    observation.receipt.get("route") or ""
                ) == route
            else:
                verified = observation.applied
            return VerificationResult(
                verified,
                {**dict(effect.receipt), **dict(observation.receipt)},
                None if verified else "exact queue and landing receipt are not durable",
            )
        if action == "integration_terminal_stage":
            observation = self._terminal_observation(
                action,
                context,
                expected_generation=str(
                    effect.receipt.get("queue_generation") or ""
                ).strip()
                or None,
                expected_head=str(effect.receipt.get("queue_head") or "").strip()
                or None,
            )
            return VerificationResult(
                observation.applied,
                {**dict(effect.receipt), **dict(observation.receipt)},
                (
                    None
                    if observation.applied
                    else "exact terminal audit receipt is not durable"
                ),
            )
        if action in {"parent_rollup_review", "terminal_audit_done"}:
            issue = self._fresh_issue(context)
            if issue is None:
                return VerificationResult(
                    False,
                    dict(effect.receipt),
                    "transition preparation lost task authority",
                )
            requests = (
                ()
                if action == "terminal_audit_done"
                else self._landing_request(issue, include_ready=True)
            )
            facts = self.binding.collector.collect(
                issue.identifier,
                landing_requests=requests,
            )
            decision = evaluate_task(issue, facts)
            expected_evidence = str(
                effect.receipt.get("evidence_revision") or ""
            ).strip()
            rollup_authority = (
                self._rollup_head_authority(
                    issue,
                    requests=requests,
                    facts=facts,
                    decision=decision,
                )
                if action == "parent_rollup_review"
                else None
            )
            receipt_rollup_authority = (
                self._receipt_rollup_authority(effect.receipt)
                if action == "parent_rollup_review"
                else None
            )
            verified = bool(
                action in decision.durable_jobs
                and decision.evidence_revision == expected_evidence
                and decision.reason_code
                == str(effect.receipt.get("decision_reason") or "")
                and (
                    action != "parent_rollup_review"
                    or (
                        rollup_authority is not None
                        and rollup_authority == receipt_rollup_authority
                    )
                )
            )
            return VerificationResult(
                verified,
                dict(effect.receipt),
                None if verified else f"{action} exact evidence is no longer current",
            )
        if action == "integration_recovery":
            row = self._queue_row(context)
            issue = self._issue(context)
            details = self._revalidation_details(context)
            original_evidence = self._revalidated_evidence_revision(context)
            verified = bool(
                row is not None
                and row.state != "integrating"
                and self._record_authorizes_queue_row(issue, row)
                and bool(effect.receipt.get("source_queue_present"))
                == bool(details.get("integration_queue_present", False))
                and str(effect.receipt.get("source_queue_generation") or "")
                == self._queue_generation_from_checkpoint(context)
                and str(effect.receipt.get("source_evidence_revision") or "")
                == original_evidence
                and str(effect.receipt.get("source_task_branch") or "")
                == str(
                    details.get("integration_queue_branch")
                    or details.get("task_branch")
                    or ""
                ).strip()
                and str(effect.receipt.get("source_task_head") or "")
                == str(
                    details.get("integration_queue_head")
                    or details.get("task_head")
                    or ""
                ).strip()
                and str(effect.receipt.get("queue_generation") or "")
                == row.authority_generation()
            )
            return VerificationResult(
                verified,
                {**dict(effect.receipt), "queue_state": getattr(row, "state", None)},
                None if verified else "exact queue recovery is not durable",
            )
        if action == "integration_landing_refresh":
            issue = self._issue(context)
            row = self._queue_row(context)
            expected_queue = self._queue_generation_from_checkpoint(context)
            if expected_queue and not self._queue_generation_is_current(context, row):
                return VerificationResult(
                    False,
                    dict(effect.receipt),
                    "landing queue generation changed before verification",
                )
            landing = self._landing(issue) if issue is not None else None
            verified = bool(
                landing is not None and landing.state is LandingState.LANDED
            )
            return VerificationResult(
                verified,
                {
                    **dict(effect.receipt),
                    "landing": landing.to_dict() if landing is not None else None,
                },
                None if verified else "exact target landing is not yet proven",
            )
        if action == "epic_branch_reconciliation":
            verified = bool(effect.receipt.get("repair_scheduled"))
            return VerificationResult(
                verified,
                dict(effect.receipt),
                None if verified else "epic repair receipt is missing",
            )
        if action == "historical_audit_replay_batch":
            verified = bool(
                effect.receipt.get("batch_completed")
                and (
                    not effect.receipt.get("deferred")
                    or effect.receipt.get("successor_job_id")
                )
            )
            return VerificationResult(
                verified,
                dict(effect.receipt),
                None if verified else "historical audit batch receipt is incomplete",
            )
        if action == "standalone_delivery":
            observation = self._standalone_observation(
                action,
                context,
                expected_review_number=str(
                    effect.receipt.get("review_number") or ""
                ).strip()
                or None,
                expected_review_head=str(
                    effect.receipt.get("review_head") or ""
                ).strip()
                or None,
                expected_target=str(
                    effect.receipt.get("target_branch") or ""
                ).strip()
                or None,
                expected_branch=str(
                    effect.receipt.get("submission_branch") or ""
                ).strip()
                or None,
            )
            exact_receipt = all(
                str(effect.receipt.get(key) or "").strip()
                for key in (
                    "review_number",
                    "review_head",
                    "target_branch",
                    "submission_branch",
                    "submission_head",
                )
            )
            return VerificationResult(
                bool(exact_receipt and observation.applied),
                {**dict(effect.receipt), **dict(observation.receipt)},
                (
                    None
                    if exact_receipt and observation.applied
                    else "exact standalone review receipt is not durable"
                ),
            )
        observation = self.observe_action(action, context)
        return VerificationResult(
            observation.applied,
            {**dict(effect.receipt), **dict(observation.receipt)},
            None if observation.applied else f"{action} effect is not observable",
        )

    def build_action_transition(
        self,
        action: str,
        context: WorkflowJobContext,
        verification: VerificationResult,
    ) -> TransitionIntent | None:
        if action in {"parent_rollup_review", "terminal_audit_done"}:
            requested = (
                MERGED if action == "parent_rollup_review" else DONE
            )
            with self._issue_authority_lock(context):
                issue = self._fresh_issue(context)
                if issue is None:
                    decision = None
                else:
                    requests = (
                        ()
                        if action == "terminal_audit_done"
                        else self._landing_request(issue, include_ready=True)
                    )
                    facts = self.binding.collector.collect(
                        issue.identifier,
                        landing_requests=requests,
                    )
                    decision = evaluate_task(issue, facts)
                receipt_evidence = str(
                    verification.receipt.get("evidence_revision") or ""
                ).strip()
                receipt_reason = str(
                    verification.receipt.get("decision_reason") or ""
                ).strip()
                if (
                    issue is None
                    or decision is None
                    or action not in decision.durable_jobs
                    or decision.evidence_revision != receipt_evidence
                    or decision.reason_code != receipt_reason
                    or str(verification.receipt.get("requested_status") or "")
                    != requested
                ):
                    raise WorkflowActionError(
                        f"{action} transition evidence changed before commit",
                        category=WorkflowFailureCategory.STALE_EVIDENCE,
                        retryable=True,
                    )
                rollup_authority = (
                    self._rollup_head_authority(
                        issue,
                        requests=requests,
                        facts=facts,
                        decision=decision,
                    )
                    if action == "parent_rollup_review"
                    else None
                )
                receipt_rollup_authority = (
                    self._receipt_rollup_authority(verification.receipt)
                    if action == "parent_rollup_review"
                    else None
                )
                if action == "parent_rollup_review" and (
                    rollup_authority is None
                    or rollup_authority != receipt_rollup_authority
                ):
                    raise WorkflowActionError(
                        "parent_rollup_review exact landing head changed before commit",
                        category=WorkflowFailureCategory.STALE_EVIDENCE,
                        retryable=True,
                    )
                expected_status = issue.state
                expected_version = issue_authority_version(issue)
                exact_head = (
                    rollup_authority.exact_head
                    if rollup_authority is not None
                    else issue_exact_head(issue)
                )
            return TransitionIntent(
                project_id=self.project_id,
                task_id=issue.identifier,
                expected_status=expected_status,
                expected_version=expected_version,
                requested_status=requested,
                actor=(
                    "oompah-workflow-rollup"
                    if action == "parent_rollup_review"
                    else "oompah-workflow-auditor"
                ),
                authority=(
                    TransitionAuthority.INTEGRATOR
                    if action == "parent_rollup_review"
                    else TransitionAuthority.AUDITOR
                ),
                reason_code=str(
                    verification.receipt.get("decision_reason") or action
                ),
                idempotency_key=f"{context.job.idempotency_key}:transition",
                originating_job=context.job.job_id,
                evidence_generation=context.job.generation,
                exact_head=exact_head,
                precondition_revision=(
                    str(verification.receipt.get("evidence_revision") or "")
                    if action == "parent_rollup_review"
                    else None
                ),
            )
        if action != "integration_attempt":
            return None
        route = str(verification.receipt.get("route") or "")
        requested = {
            IntegrationRoute.REBASE.value: NEEDS_REBASE,
            IntegrationRoute.CI_FIX.value: NEEDS_CI_FIX,
        }.get(route)
        if requested is None:
            return None
        expected_generation = str(
            verification.receipt.get("queue_generation") or ""
        ).strip()
        expected_branch = str(
            verification.receipt.get("queue_branch") or ""
        ).strip()
        expected_head = str(
            verification.receipt.get("queue_head") or ""
        ).strip()
        row = self._queue_row(context)
        issue = self._issue(context)
        record = self._record(issue)
        if (
            issue is None
            or record is None
            or row is None
            or not all((expected_generation, expected_branch, expected_head))
            or row.authority_generation() != expected_generation
            or row.task_branch != expected_branch
            or row.head_sha != expected_head
            or str(getattr(record, "task_branch", "") or "").strip()
            != expected_branch
            or str(getattr(record, "head_sha", "") or "").strip()
            != expected_head
        ):
            raise WorkflowActionError(
                "integration generation changed before failure transition",
                category=WorkflowFailureCategory.STALE_EVIDENCE,
                retryable=True,
            )
        return TransitionIntent(
            project_id=self.project_id,
            task_id=issue.identifier,
            expected_status=issue.state,
            expected_version=issue_authority_version(issue),
            requested_status=requested,
            actor="oompah-workflow-integrator",
            authority=TransitionAuthority.INTEGRATOR,
            reason_code="integration.gate_failure",
            idempotency_key=f"{context.job.idempotency_key}:{route}",
            originating_job=context.job.job_id,
            evidence_generation=str(getattr(issue, "assignment_id", "") or "") or None,
            exact_head=issue_exact_head(issue),
        )


def build_integration_action_handlers(
    orchestrator: Any,
    binding: Any,
) -> dict[str, IntegrationActionHandler]:
    """Build total project-routed production coverage for integration."""

    backend = OrchestratorIntegrationActionBackend(orchestrator, binding)
    # Integration and standalone delivery both run the configured branch gate.
    # Keep their durable lease alive through that command, with a small margin
    # for the surrounding fetch/rebase/forge checkpoints.  The worker still
    # fences the commit callback if this outer bound is ever exceeded.
    gate_timeout = max(
        float(
            getattr(
                getattr(orchestrator, "config", None),
                "quality_gate_timeout_seconds",
                3600,
            )
        )
        + 120.0,
        180.0,
    )
    return {
        action: IntegrationActionHandler(
            action,
            backend,
            domain=_INTEGRATION_ACTION_DOMAINS[action],
            operation_timeout_seconds=gate_timeout,
        )
        for action in sorted(INTEGRATION_ACTIONS)
    }
