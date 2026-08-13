"""Production orchestrator effects for the durable epic workflow.

The adapter deliberately exposes only one-epic operations.  Periodic legacy
helpers may accept lists for compatibility, but this module never passes more
than the exact epic leased by the workflow worker and never invokes a
whole-project reconciliation sweep.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import threading
from collections.abc import Mapping
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

from oompah.epic_workflow import (
    EPIC_ACTIONS,
    EpicAction,
    EpicProjectScopeError,
    EpicWorkflowController,
    EpicWorkflowHandler,
    ProductionEpicWorkflowBackend,
    is_epic_rollup_issue,
    normalize_issue_project_scope,
)
from oompah.events import EventType
from oompah.models import EpicRebaseState, Issue
from oompah.scm import detect_provider, extract_repo_slug
from oompah.statuses import (
    ARCHIVED,
    DONE,
    IN_PROGRESS,
    MERGED,
    NEEDS_REBASE,
    OPEN,
    canonicalize_status,
)
from oompah.task_transition_service import (
    TransitionAuthority,
    TransitionDisposition,
    TransitionIntent,
    issue_authority_version,
    issue_exact_head,
)
from oompah.workflow_fact_model import (
    FactDomain,
    FactState,
    LandingState,
    WorkflowFacts,
)
from oompah.workflow_jobs import (
    ACTIVE_JOB_STATES,
    WorkflowFailureCategory,
    WorkflowJobState,
)
from oompah.work_decision import retained_terminal_child_waiver
from oompah.workflow_worker import WorkflowActionError, WorkflowActionSuperseded


def _text(value: object) -> str:
    return str(value or "").strip()


_EXACT_HEAD_RE = re.compile(r"^[0-9a-f]{40,64}$")
_RESTART_CLEANUP_LOG_SAMPLE = 10
logger = logging.getLogger(__name__)


class OrchestratorEpicWorkflowEffects:
    """Real forge, tracker-helper, and Git cleanup effects for one project."""

    def __init__(
        self,
        orchestrator: Any,
        *,
        project_id: str,
        transition_service: Any | None = None,
    ) -> None:
        self.orchestrator = orchestrator
        self.project_id = _text(project_id)
        self.transition_service = transition_service
        if not self.project_id:
            raise ValueError("project_id is required")
        self._mutation_tasks: dict[
            tuple[str, str], asyncio.Task[Mapping[str, Any]]
        ] = {}

    def _mutation_finished(
        self,
        key: tuple[str, str],
        mutation: asyncio.Task[Mapping[str, Any]],
    ) -> None:
        """Retire a shared mutation without leaking a background exception."""

        if self._mutation_tasks.get(key) is mutation:
            self._mutation_tasks.pop(key, None)
        if not mutation.cancelled():
            # Retrieving the result marks an exception as observed; awaiting
            # the same completed task still receives the identical outcome.
            mutation.exception()

    @property
    def pending_mutation_count(self) -> int:
        """Return side effects which must finish before lifecycle stores close."""

        return sum(not mutation.done() for mutation in self._mutation_tasks.values())

    async def drain_mutations(self, *, timeout_seconds: float | None = None) -> bool:
        """Wait for already-started shielded mutations without cancelling them."""

        if timeout_seconds is not None and timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        pending = tuple(
            mutation
            for mutation in self._mutation_tasks.values()
            if not mutation.done()
        )
        if not pending:
            return True
        waiter = asyncio.gather(*pending, return_exceptions=True)
        try:
            if timeout_seconds is None:
                await waiter
            else:
                await asyncio.wait_for(asyncio.shield(waiter), timeout_seconds)
        except TimeoutError:
            return False
        return True

    @staticmethod
    async def _blocking(operation: Any, /, *args: Any, **kwargs: Any) -> Any:
        """Run production tracker, forge, and Git calls off the event loop."""

        return await asyncio.to_thread(operation, *args, **kwargs)

    def _project(self, epic: Issue) -> Any:
        if _text(epic.project_id) != self.project_id:
            raise WorkflowActionError(
                "epic effect crossed its project binding",
                category=WorkflowFailureCategory.POLICY,
                retryable=False,
            )
        project = self.orchestrator.project_store.get(self.project_id)
        if project is None:
            raise WorkflowActionError(
                f"project {self.project_id} is unavailable",
                category=WorkflowFailureCategory.TRANSIENT,
                retryable=True,
            )
        return project

    @staticmethod
    def _containment(facts: WorkflowFacts) -> Mapping[str, Any]:
        fact = facts.fact(FactDomain.CONTAINMENT)
        if fact.state is not FactState.KNOWN or not isinstance(fact.value, Mapping):
            raise WorkflowActionError(
                "epic containment evidence is unavailable",
                category=WorkflowFailureCategory.TRANSIENT,
                retryable=True,
            )
        return fact.value

    def _branches(self, epic: Issue, facts: WorkflowFacts) -> tuple[str, str]:
        containment = self._containment(facts)
        source = _text(containment.get("epic_branch"))
        target = _text(containment.get("target_branch"))
        if not source or not target:
            raise WorkflowActionError(
                "epic source or immediate target is unresolved",
                category=WorkflowFailureCategory.TRANSIENT,
                retryable=True,
            )
        expected = self.orchestrator._epic_branch_for_issue(epic)
        if source != expected:
            raise WorkflowActionError(
                f"epic source changed from {source} to {expected}",
                category=WorkflowFailureCategory.STALE_EVIDENCE,
                retryable=False,
            )
        return source, target

    def _forge(self, epic: Issue) -> tuple[Any, Any, str]:
        project = self._project(epic)
        repo_url = _text(getattr(project, "repo_url", None))
        provider = detect_provider(
            repo_url,
            access_token=getattr(project, "access_token", None),
        )
        if provider is None:
            raise WorkflowActionError(
                "epic project has no supported forge provider",
                category=WorkflowFailureCategory.POLICY,
                retryable=False,
            )
        return project, provider, extract_repo_slug(repo_url)

    def _review_evidence(
        self,
        epic: Issue,
        facts: WorkflowFacts,
        *,
        expected_head: str | None = None,
        expected_review_id: str | None = None,
        accepted_states: tuple[str, ...] = ("open",),
    ) -> Mapping[str, Any] | None:
        source, target = self._branches(epic, facts)
        _project, provider, slug = self._forge(epic)
        try:
            review = provider.find_pr_for_branch(slug, source)
            source_head = provider.get_branch_head_sha(slug, source)
        except Exception as exc:  # noqa: BLE001 - typed forge boundary
            raise WorkflowActionError(
                f"epic review observation failed: {type(exc).__name__}",
                category=WorkflowFailureCategory.TRANSPORT,
                retryable=True,
            ) from exc
        if review is None:
            return None
        state = _text(getattr(review, "state", "open")).lower() or "open"
        review_source = _text(getattr(review, "source_branch", None))
        review_target = _text(getattr(review, "target_branch", None))
        review_head = _text(getattr(review, "head_sha", None))
        if (
            state not in accepted_states
            or review_source != source
            or review_target != target
        ):
            return None
        live_head = _text(source_head).lower()
        review_head = review_head.lower()
        if live_head and review_head and live_head != review_head:
            return None
        exact_head = live_head or review_head
        exact_head = exact_head.lower()
        review_id = _text(getattr(review, "id", None))
        if not review_id:
            raise WorkflowActionError(
                "epic review has no immutable identity",
                category=WorkflowFailureCategory.TRANSIENT,
                retryable=True,
            )
        if expected_review_id and review_id != expected_review_id:
            raise WorkflowActionSuperseded(
                "epic review identity changed after event delivery",
                replacement_generation=f"review:{review_id}",
            )
        if not _EXACT_HEAD_RE.fullmatch(exact_head):
            raise WorkflowActionError(
                "open epic review has no exact source head",
                category=WorkflowFailureCategory.TRANSIENT,
                retryable=True,
            )
        if expected_head and exact_head != expected_head:
            raise WorkflowActionError(
                "epic review source head changed after effect",
                category=WorkflowFailureCategory.STALE_EVIDENCE,
                retryable=False,
            )
        return {
            "effect": EpicAction.ROLLUP_REVIEW_CREATION.value,
            "review_id": review_id,
            "review_url": _text(getattr(review, "url", None)) or None,
            "source_branch": source,
            "target_branch": target,
            "source_head": exact_head,
        }

    def _expected_epic_head(self, epic: Issue, facts: WorkflowFacts) -> str:
        source, target = self._branches(epic, facts)
        landing = next(
            (
                item
                for item in facts.landings
                if item.source == source and item.target == target
            ),
            None,
        )
        revision = _text(getattr(landing, "revision", None)).lower()
        if not _EXACT_HEAD_RE.fullmatch(revision):
            raise WorkflowActionError(
                "epic review evidence has no exact source revision",
                category=WorkflowFailureCategory.TRANSIENT,
                retryable=True,
            )
        return revision

    def _landed_epic_head(self, epic: Issue, facts: WorkflowFacts) -> str:
        """Return the exact current source revision proven on its target."""

        source, target = self._branches(epic, facts)
        landing = next(
            (
                item
                for item in facts.landings
                if item.source == source
                and item.target == target
                and item.state is LandingState.LANDED
            ),
            None,
        )
        revision = _text(getattr(landing, "revision", None)).lower()
        if not _EXACT_HEAD_RE.fullmatch(revision):
            raise WorkflowActionError(
                "epic auto-close has no exact landed source revision",
                category=WorkflowFailureCategory.TRANSIENT,
                retryable=True,
            )
        return revision

    def _landed_review_retirement_snapshot(
        self,
        epic: Issue,
        facts: WorkflowFacts,
    ) -> Mapping[str, Any]:
        """Observe exact landed-review and capacity state for one epic.

        A source branch can have historical reviews for several targets and
        generations.  Landing of one exact source/target/head tuple authorizes
        retirement only of that tuple.  Any live same-source mismatch fails
        closed rather than freeing capacity or closing another generation.
        """

        source, target = self._branches(epic, facts)
        expected_head = self._landed_epic_head(epic, facts)
        _project, provider, slug = self._forge(epic)
        try:
            open_reviews = tuple(provider.list_open_reviews(slug) or ())
            if getattr(provider, "last_open_reviews_fetch_ok", True) is False:
                raise RuntimeError("forge open-review listing was not authoritative")
            live_head = _text(provider.get_branch_head_sha(slug, source)).lower()
        except Exception as exc:
            raise WorkflowActionError(
                f"landed epic review observation failed: {type(exc).__name__}",
                category=WorkflowFailureCategory.TRANSPORT,
                retryable=True,
            ) from exc
        if live_head and live_head != expected_head:
            raise WorkflowActionSuperseded(
                "epic source advanced after the landed auto-close decision",
                replacement_generation=f"head:{live_head}",
            )

        exact_reviews: list[dict[str, str]] = []
        for review in open_reviews:
            if _text(getattr(review, "state", "open")).lower() not in {
                "",
                "open",
            }:
                continue
            if _text(getattr(review, "source_branch", None)) != source:
                continue
            review_id = _text(getattr(review, "id", None))
            review_target = _text(getattr(review, "target_branch", None))
            review_head = _text(getattr(review, "head_sha", None)).lower()
            if not review_id:
                raise WorkflowActionError(
                    "open landed-epic review has no exact identity",
                    category=WorkflowFailureCategory.TRANSIENT,
                    retryable=True,
                )
            if not _EXACT_HEAD_RE.fullmatch(review_head):
                # GitHub's open-review list omits the immutable PR head even
                # though the single-review endpoint exposes it.  Resolve that
                # exact identity before authorizing close; the live branch tip
                # alone is insufficient because it may have advanced.
                try:
                    detail = provider.get_review(slug, review_id)
                except Exception as exc:
                    raise WorkflowActionError(
                        f"open epic review #{review_id} head lookup failed",
                        category=WorkflowFailureCategory.TRANSPORT,
                        retryable=True,
                    ) from exc
                if detail is None:
                    raise WorkflowActionError(
                        f"open epic review #{review_id} is no longer observable",
                        category=WorkflowFailureCategory.TRANSIENT,
                        retryable=True,
                    )
                detail_source = _text(getattr(detail, "source_branch", None))
                detail_target = _text(getattr(detail, "target_branch", None))
                if detail_source != source or detail_target != review_target:
                    raise WorkflowActionError(
                        f"open epic review #{review_id} identity changed during lookup",
                        category=WorkflowFailureCategory.STALE_EVIDENCE,
                        retryable=False,
                    )
                review_head = _text(getattr(detail, "head_sha", None)).lower()
            if not _EXACT_HEAD_RE.fullmatch(review_head):
                raise WorkflowActionError(
                    f"open epic review #{review_id} has no exact head",
                    category=WorkflowFailureCategory.TRANSIENT,
                    retryable=True,
                )
            if review_target != target:
                raise WorkflowActionError(
                    f"open epic review #{review_id} targets {review_target or '<missing>'}, "
                    f"not {target}",
                    category=WorkflowFailureCategory.STALE_EVIDENCE,
                    retryable=False,
                )
            if review_head != expected_head:
                raise WorkflowActionSuperseded(
                    f"open epic review #{review_id} belongs to a different source head",
                    replacement_generation=f"head:{review_head}",
                )
            exact_reviews.append(
                {
                    "review_id": review_id,
                    "source_branch": source,
                    "target_branch": target,
                    "source_head": review_head,
                }
            )

        try:
            active = tuple(
                self.orchestrator.review_capacity_store.active(self.project_id)
            )
        except Exception as exc:
            raise WorkflowActionError(
                f"landed epic review capacity observation failed: {type(exc).__name__}",
                category=WorkflowFailureCategory.TRANSIENT,
                retryable=True,
            ) from exc

        exact_review_ids = {item["review_id"] for item in exact_reviews}
        exact_reservations: list[dict[str, str | None]] = []
        for reservation in active:
            reservation_task = _text(getattr(reservation, "task_id", None))
            reservation_source = _text(
                getattr(reservation, "source_branch", None)
            )
            reservation_target = _text(
                getattr(reservation, "target_branch", None)
            )
            reservation_review_id = _text(getattr(reservation, "review_id", None))
            relevant = (
                reservation_task == epic.identifier
                or reservation_source == source
                or reservation_review_id in exact_review_ids
            )
            if not relevant:
                continue
            if (
                reservation_task != epic.identifier
                or reservation_source != source
                or reservation_target != target
            ):
                raise WorkflowActionError(
                    "landed epic capacity reservation has a conflicting route",
                    category=WorkflowFailureCategory.STALE_EVIDENCE,
                    retryable=False,
                )
            reservation_id = _text(getattr(reservation, "reservation_id", None))
            reservation_head = _text(getattr(reservation, "head_sha", None)).lower()
            if reservation_head and reservation_head != expected_head:
                raise WorkflowActionSuperseded(
                    "landed epic capacity reservation belongs to a different head",
                    replacement_generation=f"head:{reservation_head}",
                )
            if not reservation_head and reservation_review_id not in exact_review_ids:
                # Compatibility rows written before exact-head capacity
                # binding can still be recovered from their immutable review
                # identity.  Query that exact review instead of inferring from
                # a task or branch name.
                if not reservation_review_id:
                    raise WorkflowActionError(
                        "legacy epic capacity reservation has no exact review identity",
                        category=WorkflowFailureCategory.STALE_EVIDENCE,
                        retryable=False,
                    )
                try:
                    historical = provider.get_review(slug, reservation_review_id)
                except Exception as exc:
                    raise WorkflowActionError(
                        "legacy epic capacity review could not be verified",
                        category=WorkflowFailureCategory.TRANSPORT,
                        retryable=True,
                    ) from exc
                if (
                    historical is None
                    or _text(getattr(historical, "source_branch", None)) != source
                    or _text(getattr(historical, "target_branch", None)) != target
                    or _text(getattr(historical, "head_sha", None)).lower()
                    != expected_head
                ):
                    raise WorkflowActionError(
                        "legacy epic capacity reservation does not match the exact landing",
                        category=WorkflowFailureCategory.STALE_EVIDENCE,
                        retryable=False,
                    )
            exact_reservations.append(
                {
                    "reservation_id": reservation_id,
                    "review_id": reservation_review_id or None,
                    "head_sha": reservation_head or expected_head,
                }
            )

        return {
            "effect": EpicAction.AUTO_CLOSE.value,
            "source_branch": source,
            "target_branch": target,
            "source_head": expected_head,
            "open_reviews": tuple(exact_reviews),
            "active_reservations": tuple(exact_reservations),
            "review_retired": not exact_reviews and not exact_reservations,
        }

    def _retire_landed_review_under_authority(
        self,
        epic: Issue,
        facts: WorkflowFacts,
        *,
        idempotency_key: str,
    ) -> Mapping[str, Any]:
        """Close and release only reviews bound to the exact landed head."""

        issue_id = _text(getattr(epic, "id", None)) or epic.identifier
        with (
            self.orchestrator.issue_transition_lock(issue_id).sync(),
            self.orchestrator.project_store.project_write_lock(self.project_id),
        ):
                current = self._fresh_epic_authority(epic, facts)
                self._assert_terminal_containment_current(
                    current,
                    facts,
                    operation="landed review retirement",
                )
                snapshot = self._landed_review_retirement_snapshot(current, facts)
                source = _text(snapshot.get("source_branch"))
                target = _text(snapshot.get("target_branch"))
                expected_head = _text(snapshot.get("source_head")).lower()
                _project, provider, slug = self._forge(current)

                # Upgrade any legacy committed row before the forge mutation.
                # If the process exits after close but before release, restart
                # reconciliation can still identify this exact head safely.
                for review in snapshot.get("open_reviews", ()):
                    review_id = _text(review.get("review_id"))
                    existing = next(
                        (
                            item
                            for item in snapshot.get("active_reservations", ())
                            if _text(item.get("review_id")) == review_id
                        ),
                        None,
                    )
                    reservation_id = _text(
                        existing.get("reservation_id") if existing else None
                    ) or f"{idempotency_key}:landed-review:{review_id}"
                    try:
                        self.orchestrator.review_capacity_store.adopt(
                            project_id=self.project_id,
                            task_id=current.identifier,
                            source_branch=source,
                            target_branch=target,
                            review_id=review_id,
                            reservation_id=reservation_id,
                            authority_generation=issue_authority_version(current),
                            head_sha=expected_head,
                        )
                    except Exception as exc:
                        raise WorkflowActionError(
                            "exact landed-review capacity binding could not be persisted",
                            category=WorkflowFailureCategory.TRANSIENT,
                            retryable=True,
                        ) from exc

                for review in snapshot.get("open_reviews", ()):
                    review_id = _text(review.get("review_id"))
                    try:
                        outcome = provider.close_review(slug, review_id)
                    except Exception as exc:
                        raise WorkflowActionError(
                            f"landed epic review #{review_id} close failed: "
                            f"{type(exc).__name__}",
                            category=WorkflowFailureCategory.TRANSPORT,
                            retryable=True,
                        ) from exc
                    success = (
                        bool(outcome[0])
                        if isinstance(outcome, tuple)
                        else bool(outcome)
                    )
                    if not success:
                        raise WorkflowActionError(
                            f"landed epic review #{review_id} was not closed",
                            category=WorkflowFailureCategory.TRANSIENT,
                            retryable=True,
                        )
                    self.orchestrator.release_review_capacity(
                        self.project_id,
                        review_id,
                    )

                # Release by immutable reservation identity as well.  This is
                # exact even for an uncommitted or already-closed review row.
                for reservation in snapshot.get("active_reservations", ()):
                    reservation_id = _text(reservation.get("reservation_id"))
                    if reservation_id:
                        self.orchestrator._release_review_capacity(
                            self.project_id,
                            reservation_id=reservation_id,
                        )

                verified = self._landed_review_retirement_snapshot(current, facts)
                if not bool(verified.get("review_retired")):
                    raise WorkflowActionError(
                        "landed epic review retirement is not yet observable",
                        category=WorkflowFailureCategory.TRANSIENT,
                        retryable=True,
                    )
                return verified

    def _review_metadata_matches(
        self,
        epic: Issue,
        evidence: Mapping[str, Any],
    ) -> bool:
        current = self._tracker().fetch_issue_detail(epic.identifier)
        if current is None:
            return False
        return all(
            (
                _text(current.review_number) == _text(evidence.get("review_id")),
                _text(current.work_branch) == _text(evidence.get("source_branch")),
                _text(current.target_branch) == _text(evidence.get("target_branch")),
                _text(current.review_head).lower()
                == _text(evidence.get("source_head")).lower(),
            )
        )

    def _persist_review_metadata(
        self,
        epic: Issue,
        evidence: Mapping[str, Any],
    ) -> None:
        persisted = self.orchestrator._write_review_metadata(
            self._tracker(),
            epic.identifier,
            review_id=_text(evidence.get("review_id")) or None,
            review_url=_text(evidence.get("review_url")) or None,
            source_branch=_text(evidence.get("source_branch")) or None,
            target_branch=_text(evidence.get("target_branch")) or None,
            review_head=_text(evidence.get("source_head")) or None,
            strict=True,
        )
        if not persisted or not self._review_metadata_matches(epic, evidence):
            raise WorkflowActionError(
                "epic review metadata is not durably observable",
                category=WorkflowFailureCategory.TRANSIENT,
                retryable=True,
            )

    def _publish_review_metadata_change(self, epic: Issue) -> None:
        """Wake exact child/parent decisions after terminal-head CAS changes."""

        self.orchestrator.event_bus.emit(
            EventType.ISSUE_STATE_CHANGED,
            {
                "project_id": self.project_id,
                "identifier": epic.identifier,
                "parent_id": epic.parent_id,
                "change": "review-metadata-synchronized",
            },
        )

    def _tracker(self) -> Any:
        return self.orchestrator._tracker_for_project(self.project_id)

    def _fresh_epic_authority(self, epic: Issue, facts: WorkflowFacts) -> Issue:
        """Re-read containment and lifecycle authority at mutation time."""

        tracker = self._tracker()
        try:
            invalidate = getattr(tracker, "invalidate_read_cache", None)
            if callable(invalidate):
                invalidate()
            current = tracker.fetch_issue_detail(epic.identifier)
        except Exception as exc:  # noqa: BLE001 - tracker boundary fails closed
            raise WorkflowActionError(
                f"epic authority refresh failed: {type(exc).__name__}",
                category=WorkflowFailureCategory.TRANSIENT,
                retryable=True,
            ) from exc
        if not isinstance(current, Issue):
            raise WorkflowActionError(
                "epic authority is no longer observable",
                category=WorkflowFailureCategory.TRANSIENT,
                retryable=True,
            )
        try:
            expected = normalize_issue_project_scope(epic, self.project_id)
            current = normalize_issue_project_scope(current, self.project_id)
        except EpicProjectScopeError as exc:
            raise WorkflowActionSuperseded(
                "epic project, parent, status, or delivery authority changed",
                replacement_generation=(
                    f"authority:{issue_authority_version(current)}"
                ),
            ) from exc
        if (
            _text(current.identifier) != _text(expected.identifier)
            or not is_epic_rollup_issue(current, tracker=tracker)
            or issue_authority_version(current) != issue_authority_version(expected)
        ):
            raise WorkflowActionSuperseded(
                "epic project, parent, status, or delivery authority changed",
                replacement_generation=f"authority:{issue_authority_version(current)}",
            )
        source, target = self._branches(expected, facts)
        project = self._project(current)
        try:
            current_source = self.orchestrator._epic_branch_for_issue(current)
            current_target = self.orchestrator._resolve_epic_target_branch(
                current, project
            )
        except Exception as exc:  # noqa: BLE001 - containment fails closed
            raise WorkflowActionError(
                f"epic target refresh failed: {type(exc).__name__}",
                category=WorkflowFailureCategory.TRANSIENT,
                retryable=True,
            ) from exc
        if _text(current_source) != source or _text(current_target) != target:
            raise WorkflowActionSuperseded(
                "epic source or immediate target changed before mutation",
                replacement_generation=(
                    f"target:{_text(current_source)}:{_text(current_target)}"
                ),
            )
        return current

    def _assert_live_source_head(
        self,
        epic: Issue,
        *,
        source: str,
        expected_head: str,
    ) -> None:
        observed = self._remote_branch_head(epic, source)
        if observed is None:
            raise WorkflowActionError(
                "epic source head is unavailable before mutation",
                category=WorkflowFailureCategory.TRANSIENT,
                retryable=True,
            )
        if observed != expected_head:
            raise WorkflowActionSuperseded(
                "epic source head changed before mutation",
                replacement_generation=f"head:{observed}",
            )

    def _open_review_under_authority(
        self,
        epic: Issue,
        facts: WorkflowFacts,
        expected_head: str,
    ) -> int:
        issue_id = _text(getattr(epic, "id", None)) or epic.identifier
        with self.orchestrator.issue_transition_lock(issue_id).sync():
            with self.orchestrator.project_store.project_write_lock(self.project_id):
                current = self._fresh_epic_authority(epic, facts)
                self._assert_terminal_containment_current(
                    current,
                    facts,
                    operation="rollup review creation",
                )
                return self.orchestrator._open_one_epic_main_pr(
                    current,
                    persist_tracker_state=False,
                    fail_closed_review_lookup=True,
                    expected_source_head=expected_head,
                )

    def _persist_review_under_authority(
        self,
        epic: Issue,
        facts: WorkflowFacts,
        evidence: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        issue_id = _text(getattr(epic, "id", None)) or epic.identifier
        with self.orchestrator.issue_transition_lock(issue_id).sync():
            with self.orchestrator.project_store.project_write_lock(self.project_id):
                current = self._fresh_epic_authority(epic, facts)
                self._assert_terminal_containment_current(
                    current,
                    facts,
                    operation="review metadata persistence",
                )
                observed = self._review_evidence(
                    current,
                    facts,
                    expected_head=_text(evidence.get("source_head")) or None,
                    expected_review_id=_text(evidence.get("review_id")) or None,
                    accepted_states=("open", "merged", "closed_merged"),
                )
                if observed is None:
                    raise WorkflowActionError(
                        "epic review changed before metadata persistence",
                        category=WorkflowFailureCategory.STALE_EVIDENCE,
                        retryable=False,
                    )
                self._persist_review_metadata(current, observed)
                return observed

    def _delete_cleanup_child(
        self,
        epic: Issue,
        facts: WorkflowFacts,
        child: Issue,
        expected_revision: str,
    ) -> None:
        epic_issue_id = _text(getattr(epic, "id", None)) or epic.identifier
        child_issue_id = _text(getattr(child, "id", None)) or child.identifier
        # Cleanup always acquires containment authority before child authority.
        # The child lock precedes the project fence, matching accepted worker
        # submission (child -> project) and avoiding a project -> child / child
        # -> project deadlock with direct epic-maintenance completion.
        with self.orchestrator.issue_transition_lock(epic_issue_id).sync():
            with self.orchestrator.issue_transition_lock(child_issue_id).sync():
                with self.orchestrator.project_store.project_write_lock(
                    self.project_id
                ):
                    current_epic = self._fresh_epic_authority(epic, facts)
                    tracker = self._tracker()
                    invalidate = getattr(tracker, "invalidate_read_cache", None)
                    if callable(invalidate):
                        invalidate()
                    current = tracker.fetch_issue_detail(child.identifier)
                    try:
                        expected_child = normalize_issue_project_scope(
                            child, self.project_id
                        )
                    except EpicProjectScopeError as exc:
                        raise WorkflowActionSuperseded(
                            f"child {child.identifier} changed before branch deletion",
                            replacement_generation=(
                                f"cleanup:{issue_authority_version(child)}"
                            ),
                        ) from exc
                    if isinstance(current, Issue):
                        try:
                            current = normalize_issue_project_scope(
                                current, self.project_id
                            )
                        except EpicProjectScopeError as exc:
                            raise WorkflowActionSuperseded(
                                f"child {child.identifier} changed before "
                                "branch deletion",
                                replacement_generation=(
                                    f"cleanup:{issue_authority_version(current)}"
                                ),
                            ) from exc
                    current_head = (
                        _text(issue_exact_head(current)).lower()
                        if isinstance(current, Issue)
                        else ""
                    )
                    landing_revision = self._cleanup_landing_revision(
                        facts,
                        child.identifier,
                        expected_source=(
                            self.orchestrator.project_store.epic_child_branch_name(
                                current_epic.identifier,
                                child.identifier,
                            )
                        ),
                        expected_target=self._branches(current_epic, facts)[0],
                        expected_revision=expected_revision,
                    )
                    if (
                        not isinstance(current, Issue)
                        or _text(current.project_id) != self.project_id
                        or _text(current.parent_id) != current_epic.identifier
                        or canonicalize_status(current.state)
                        not in {DONE, MERGED, ARCHIVED}
                        or issue_authority_version(current)
                        != issue_authority_version(expected_child)
                        or (current_head and current_head != expected_revision)
                        or (
                            not current_head
                            and landing_revision != expected_revision
                        )
                    ):
                        replacement = (
                            issue_authority_version(current)
                            if isinstance(current, Issue)
                            else "unavailable"
                        )
                        raise WorkflowActionSuperseded(
                            f"child {child.identifier} changed before branch deletion",
                            replacement_generation=f"cleanup:{replacement}",
                        )
                    self.orchestrator.project_store.delete_epic_child_branch(
                        self.project_id,
                        current_epic.identifier,
                        child.identifier,
                        expected_head_sha=expected_revision,
                        require_target_branch=(
                            canonicalize_status(current.state) != ARCHIVED
                        ),
                    )

    def _cleanup_landing_revision(
        self,
        facts: WorkflowFacts,
        identifier: str,
        *,
        expected_source: str,
        expected_target: str,
        expected_revision: str = "",
    ) -> str | None:
        """Return one exact durable cleanup landing for a normal child."""

        children = self._containment(facts).get("children")
        if not isinstance(children, (list, tuple)):
            return None
        matching_children = tuple(
            item
            for item in children
            if isinstance(item, Mapping)
            and _text(item.get("identifier")) == identifier
        )
        if len(matching_children) != 1:
            return None
        child_fact = matching_children[0]
        if (
            canonicalize_status(child_fact.get("status")) == ARCHIVED
            or bool(child_fact.get("maintenance"))
            or _text(child_fact.get("landing_source")) != expected_source
            or _text(child_fact.get("landing_target")) != expected_target
        ):
            return None
        matching_landings = tuple(
            fact
            for fact in facts.landings
            if fact.source == expected_source and fact.target == expected_target
        )
        if len(matching_landings) != 1:
            return None
        landing = matching_landings[0]
        revision = _text(landing.revision).lower()
        expected = _text(expected_revision).lower()
        if (
            landing.state is not LandingState.LANDED
            or not landing.durable
            or not _EXACT_HEAD_RE.fullmatch(revision)
            or (expected and revision != expected)
        ):
            return None
        return revision

    def _cleanup_primary_under_authority(
        self,
        epic: Issue,
        facts: WorkflowFacts,
        *,
        source: str,
        target: str,
        expected_head: str,
        merge_commit_sha: str | None,
    ) -> tuple[bool, str | None]:
        issue_id = _text(getattr(epic, "id", None)) or epic.identifier
        with self.orchestrator.issue_transition_lock(issue_id).sync():
            with self.orchestrator.project_store.project_write_lock(self.project_id):
                current = self._fresh_epic_authority(epic, facts)
                self._assert_terminal_containment_current(
                    current,
                    facts,
                    operation="cleanup",
                )
                merged = canonicalize_status(current.state) == MERGED
                result = self.orchestrator.project_store.cleanup_terminal_issue(
                    self.project_id,
                    current.identifier,
                    branch_name=source,
                    is_epic=True,
                    target_branch=target if merged else None,
                    review_head=expected_head if merged else None,
                    merge_commit_sha=merge_commit_sha if merged else None,
                    # A Merged epic, including a top-level epic targeting the
                    # default branch, is removable only after exact target landing.
                    # Archived epics retain the explicit abandon-and-prune policy.
                    require_target_branch=merged,
                    expected_head_sha=expected_head,
                )
                skipped = (
                    isinstance(result, tuple)
                    and len(result) > 1
                    and bool(result[1])
                )
                if not skipped:
                    self.orchestrator._clear_epic_rebase_state(
                        current.identifier,
                        project_id=self.project_id,
                    )
                return result

    def _assert_terminal_containment_current(
        self,
        epic: Issue,
        facts: WorkflowFacts,
        *,
        operation: str,
    ) -> None:
        """Require an unchanged terminal direct-child generation for mutation.

        Epic record authority does not include its children.  Re-reading only
        the epic would therefore allow a child creation, reopen, reparent, or
        new implementation generation to race a rollup or cleanup mutation.
        """

        children = self._containment(facts).get("children")
        if not isinstance(children, (list, tuple)):
            raise WorkflowActionError(
                f"epic {operation} containment has no direct-child snapshot",
                category=WorkflowFailureCategory.TRANSIENT,
                retryable=True,
            )
        expected: dict[str, str] = {}
        expected_waivers: dict[str, Mapping[str, Any]] = {}
        for item in children:
            if not isinstance(item, Mapping):
                raise WorkflowActionError(
                    "epic cleanup containment contains an invalid child",
                    category=WorkflowFailureCategory.TRANSIENT,
                    retryable=True,
                )
            identifier = _text(item.get("identifier"))
            authority = _text(item.get("authority_version"))
            if not identifier or not authority:
                raise WorkflowActionError(
                    f"epic {operation} child has no stable authority generation",
                    category=WorkflowFailureCategory.TRANSIENT,
                    retryable=True,
                )
            if canonicalize_status(item.get("status")) not in {
                DONE,
                MERGED,
                ARCHIVED,
            }:
                raise WorkflowActionSuperseded(
                    f"epic child {identifier} is active during {operation}",
                    replacement_generation=f"cleanup-active:{identifier}",
                )
            expected[identifier] = authority
            waiver = retained_terminal_child_waiver(
                item,
                project_id=self.project_id,
                parent_id=epic.identifier,
            )
            if "retained_terminal_provenance" in item and waiver is None:
                raise WorkflowActionSuperseded(
                    f"epic child {identifier} has invalid retained provenance "
                    f"during {operation}",
                    replacement_generation=f"provenance-invalid:{identifier}",
                )
            if waiver is not None:
                expected_waivers[identifier] = waiver

        tracker = self._tracker()
        try:
            invalidate = getattr(tracker, "invalidate_read_cache", None)
            if callable(invalidate):
                invalidate()
            observed_children = tracker.fetch_children(epic.identifier)
        except Exception as exc:  # noqa: BLE001 - tracker evidence boundary
            raise WorkflowActionError(
                f"epic cleanup containment refresh failed: {type(exc).__name__}",
                category=WorkflowFailureCategory.TRANSIENT,
                retryable=True,
            ) from exc
        if not isinstance(observed_children, (list, tuple)):
            try:
                observed_children = list(observed_children)
            except TypeError as exc:
                raise WorkflowActionError(
                    f"epic {operation} containment refresh returned invalid children",
                    category=WorkflowFailureCategory.TRANSIENT,
                    retryable=True,
                ) from exc
        scoped_children = [
            child
            for child in observed_children
            if isinstance(child, Issue)
            and (
                not _text(child.project_id)
                or _text(child.project_id) == self.project_id
            )
            and _text(child.parent_id) == epic.identifier
        ]
        active = sorted(
            child.identifier
            for child in scoped_children
            if canonicalize_status(child.state) not in {DONE, MERGED, ARCHIVED}
        )
        if active:
            raise WorkflowActionSuperseded(
                f"epic direct-child containment changed and became active before "
                f"{operation}",
                replacement_generation="cleanup-active:" + ",".join(active),
            )
        # ``expected`` was collected from these same tracker-shaped child
        # records.  Keep this containment-only CAS raw/raw: blank native
        # project scope is admitted by the explicit filter above, while an
        # explicit foreign project is excluded and changes the child set.
        observed = {
            child.identifier: issue_authority_version(child)
            for child in scoped_children
        }
        if observed != expected:
            raise WorkflowActionSuperseded(
                f"epic direct-child containment changed before {operation}",
                replacement_generation=(
                    "cleanup-children:"
                    + hashlib.sha256(
                        json.dumps(
                            observed,
                            sort_keys=True,
                            separators=(",", ":"),
                        ).encode("utf-8")
                    ).hexdigest()
                ),
            )
        observed_by_id = {child.identifier: child for child in scoped_children}
        for identifier, waiver in expected_waivers.items():
            self._assert_retained_terminal_waiver_current(
                observed_by_id[identifier],
                waiver,
                tracker=tracker,
                operation=operation,
            )

    def _assert_retained_terminal_waiver_current(
        self,
        child: Issue,
        waiver: Mapping[str, Any],
        *,
        tracker: Any,
        operation: str,
    ) -> None:
        """Re-prove one owner marker under the project mutation fence."""

        source = getattr(self.orchestrator, "_provenance_suppression_status", None)
        if not callable(source):
            raise WorkflowActionError(
                f"retained child authority is unavailable during {operation}",
                category=WorkflowFailureCategory.TRANSIENT,
                retryable=True,
            )
        try:
            status = source(child, self.project_id, tracker)
        except Exception as exc:  # noqa: BLE001 - metadata authority boundary
            raise WorkflowActionError(
                f"retained child authority refresh failed during {operation}: "
                f"{type(exc).__name__}",
                category=WorkflowFailureCategory.TRANSIENT,
                retryable=True,
            ) from exc
        marker = getattr(status, "marker", None)
        actor = getattr(marker, "actor", None)
        generation = getattr(marker, "authority_generation", None)
        current = bool(
            getattr(status, "malformed", True) is False
            and getattr(status, "suppressed", False) is True
            and marker is not None
            and getattr(marker, "suppressed", False) is True
            and getattr(marker, "version", None) == waiver.get("marker_version")
            and isinstance(generation, int)
            and not isinstance(generation, bool)
            and generation == waiver.get("provenance_authority_generation")
            and actor is not None
            and _text(getattr(actor, "identity", None))
            == _text(waiver.get("authorized_by"))
            and _text(getattr(actor, "source", None))
            == _text(waiver.get("actor_source"))
        )
        if current:
            return
        replacement = (
            str(generation)
            if isinstance(generation, int) and not isinstance(generation, bool)
            else "unavailable"
        )
        raise WorkflowActionSuperseded(
            f"retained child {child.identifier} provenance changed before "
            f"{operation}",
            replacement_generation=(
                f"provenance:{child.identifier}:{replacement}"
            ),
        )

    def _rebase_workflow_key(self, helper: Issue) -> str:
        """Return the durable workflow identity stamped on one helper."""

        try:
            metadata = self._tracker().get_metadata(helper.identifier)
        except Exception as exc:  # noqa: BLE001 - tracker boundary fails closed
            raise WorkflowActionError(
                f"rebase helper metadata observation failed: {type(exc).__name__}",
                category=WorkflowFailureCategory.TRANSIENT,
                retryable=True,
            ) from exc
        return (
            _text(metadata.get("oompah.workflow_idempotency_key"))
            if isinstance(metadata, Mapping)
            else ""
        )

    def _rebase_bookkeeping_matches(
        self,
        epic: Issue,
        helper: Issue,
        *,
        target_branch: str,
        expected_workflow_key: str | None = None,
    ) -> bool:
        workflow_key = self._rebase_workflow_key(helper)
        expected_key = _text(expected_workflow_key)
        state = self.orchestrator._get_epic_rebase_state(
            epic.identifier, project_id=self.project_id
        )
        entry = self.orchestrator._epic_rebase_state_entry(
            epic.identifier, self.project_id
        )
        return bool(
            workflow_key
            and (not expected_key or workflow_key == expected_key)
            and state is EpicRebaseState.REBASING
            and entry is not None
            and _text(getattr(entry, "project_id", None)) == self.project_id
            and _text(getattr(entry, "target_branch", None)) == target_branch
            and (_text(getattr(entry, "target_parent_id", None)) or None)
            == (_text(epic.parent_id) or None)
            and _text(getattr(entry, "target_resolution", None))
            == "authoritative_parent"
            and _text(helper.parent_id) == epic.identifier
        )

    def _ensure_rebase_helper_under_authority(
        self,
        epic: Issue,
        facts: WorkflowFacts,
        *,
        source: str,
        target: str,
        expected_head: str,
        idempotency_key: str,
    ) -> Issue:
        issue_id = _text(getattr(epic, "id", None)) or epic.identifier
        with self.orchestrator.issue_transition_lock(issue_id).sync():
            with self.orchestrator.project_store.project_write_lock(self.project_id):
                current = self._fresh_epic_authority(epic, facts)
                self._assert_live_source_head(
                    current,
                    source=source,
                    expected_head=expected_head,
                )
                matching, wrong_target = self._rebase_helpers(
                    current, target_branch=target
                )
                if wrong_target or len(matching) > 1:
                    raise WorkflowActionError(
                        "rebase helper set changed during repair",
                        category=WorkflowFailureCategory.TRANSIENT,
                        retryable=True,
                    )
                helper = matching[0] if matching else None
                tracker = self._tracker()
                if helper is None:
                    helper = self.orchestrator._file_rebase_task(
                        tracker, current, source, target
                    )
                helper_id = _text(getattr(helper, "identifier", None)) or _text(
                    getattr(helper, "id", None)
                )
                if not helper_id:
                    raise WorkflowActionError(
                        "rebase helper has no immutable identity",
                        category=WorkflowFailureCategory.TRANSIENT,
                        retryable=True,
                    )
                # These writes are intentionally replayed even when the helper
                # already exists.  A crash after helper creation must repair every
                # missing durable field rather than mistaking existence for done.
                tracker.set_metadata_field(
                    helper_id,
                    "oompah.workflow_idempotency_key",
                    idempotency_key,
                )
                self.orchestrator._set_epic_rebase_state(
                    current.identifier,
                    EpicRebaseState.REBASING,
                    project_id=self.project_id,
                    reason="durable epic rebase repair",
                )
                self.orchestrator._record_epic_rebase_target(
                    current.identifier,
                    target_branch=target,
                    project_id=self.project_id,
                    parent_id=current.parent_id,
                )
                return helper

    def _rebase_evidence(
        self,
        epic: Issue,
        facts: WorkflowFacts,
        payload: Mapping[str, Any],
    ) -> Mapping[str, Any] | None:
        source, target = self._branches(epic, facts)
        requested_target = _text(payload.get("target_branch"))
        if requested_target != target:
            raise WorkflowActionSuperseded(
                "rebase request target no longer matches the immediate parent",
                replacement_generation=f"target:{target}",
            )
        matching, wrong_target = self._rebase_helpers(epic, target_branch=target)
        # The effect is complete only when one exact helper owns the current
        # target.  Observation remains pure; apply retires every stale/duplicate
        # helper through TaskTransitionService before returning this receipt.
        if len(matching) != 1 or wrong_target:
            return None
        helper = matching[0]
        workflow_key = self._rebase_workflow_key(helper)
        if not self._rebase_bookkeeping_matches(
            epic,
            helper,
            target_branch=target,
            expected_workflow_key=workflow_key,
        ):
            return None
        return {
            "effect": EpicAction.REBASE_REPAIR.value,
            "helper_id": helper.identifier,
            "workflow_idempotency_key": workflow_key,
            "source_branch": source,
            "target_branch": target,
        }

    def _verify_rebase_receipt(
        self,
        epic: Issue,
        facts: WorkflowFacts,
        payload: Mapping[str, Any],
        receipt: Mapping[str, Any],
    ) -> Mapping[str, Any] | None:
        """Verify the exact helper named by a durable effect receipt.

        Active-helper discovery is intentionally unsuitable here: the helper
        may already have advanced to review or a terminal state by the time
        the workflow worker verifies its create effect.  Conversely, accepting
        whichever active helper now happens to target the same branch lets a
        replacement helper satisfy an older receipt.  Bind restart authority
        to the immutable tracker identity and the workflow key stamped by the
        apply operation.
        """

        source, target = self._branches(epic, facts)
        if _text(payload.get("target_branch")) != target:
            raise WorkflowActionSuperseded(
                "rebase request target no longer matches the immediate parent",
                replacement_generation=f"target:{target}",
            )
        helper_id = _text(receipt.get("helper_id"))
        workflow_key = _text(receipt.get("workflow_idempotency_key"))
        if not helper_id or not workflow_key:
            return None
        try:
            helper = self._tracker().fetch_issue_detail(helper_id)
        except Exception as exc:  # noqa: BLE001 - tracker boundary fails closed
            raise WorkflowActionError(
                f"rebase receipt observation failed: {type(exc).__name__}",
                category=WorkflowFailureCategory.TRANSIENT,
                retryable=True,
            ) from exc
        if isinstance(helper, Issue):
            try:
                # Native Markdown records derive project identity from their
                # tracker/repository and therefore legitimately deserialize
                # with an empty ``project_id``.  Bind that implicit scope
                # before asking the orchestrator to recognize its exact,
                # server-issued rebase authority.  A conflicting explicit
                # project still fails closed below.
                helper = normalize_issue_project_scope(helper, self.project_id)
            except EpicProjectScopeError:
                return None
        if (
            not isinstance(helper, Issue)
            or _text(helper.parent_id) != epic.identifier
            or not self.orchestrator._is_epic_rebase_task(
                helper, epic.identifier
            )
            or self.orchestrator._epic_rebase_helper_target(helper) != target
            or self._rebase_workflow_key(helper) != workflow_key
        ):
            return None
        return {
            "effect": EpicAction.REBASE_REPAIR.value,
            "helper_id": helper.identifier,
            "workflow_idempotency_key": workflow_key,
            "source_branch": source,
            "target_branch": target,
        }

    def _rebase_helpers(
        self,
        epic: Issue,
        *,
        target_branch: str,
    ) -> tuple[tuple[Issue, ...], tuple[Issue, ...]]:
        """Read exact direct children without mutating stale helpers."""

        tracker = self._tracker()
        try:
            tracker.invalidate_read_cache()
        except Exception:  # noqa: BLE001 - optional tracker cache boundary
            pass
        try:
            children = tuple(tracker.fetch_children(epic.identifier) or ())
        except Exception as exc:  # noqa: BLE001 - typed tracker boundary
            raise WorkflowActionError(
                f"epic rebase helper observation failed: {type(exc).__name__}",
                category=WorkflowFailureCategory.TRANSIENT,
                retryable=True,
            ) from exc
        active = {OPEN, IN_PROGRESS, NEEDS_REBASE}
        matching: list[Issue] = []
        wrong_target: list[Issue] = []
        for helper in children:
            try:
                # Native Markdown children inherit the project from their
                # tracker and may deserialize without an explicit project id.
                # Bind that implicit scope before exact helper recognition so
                # persisted server authority remains observable after restart.
                helper = normalize_issue_project_scope(helper, self.project_id)
            except EpicProjectScopeError:
                continue
            if (
                _text(helper.parent_id) != epic.identifier
                or canonicalize_status(helper.state) not in active
                or not self.orchestrator._is_epic_rebase_task(helper, epic.identifier)
            ):
                continue
            if self.orchestrator._epic_rebase_helper_target(helper) == target_branch:
                matching.append(helper)
            else:
                wrong_target.append(helper)
        order = lambda item: (  # noqa: E731 - compact stable evidence ordering
            getattr(item, "created_at", None) or "",
            _text(getattr(item, "identifier", None) or getattr(item, "id", None)),
        )
        return tuple(sorted(matching, key=order)), tuple(
            sorted(wrong_target, key=order)
        )

    def recoverable_epic_effect(
        self,
        action: EpicAction,
        epic: Issue,
        facts: WorkflowFacts,
        payload: Mapping[str, Any],
    ) -> bool:
        """Return whether a partial artifact belongs to this stale generation."""

        if action is not EpicAction.REBASE_REPAIR:
            return False
        _source, target = self._branches(epic, facts)
        if _text(payload.get("target_branch")) != target:
            return False
        matching, _wrong_target = self._rebase_helpers(
            epic, target_branch=target
        )
        # One or more exact-target helpers are enough to resume apply. Apply
        # deterministically retires duplicates and repairs all durable fields.
        return bool(matching)

    async def _retire_wrong_rebase_helpers(
        self,
        epic: Issue,
        facts: WorkflowFacts,
        helpers: tuple[Issue, ...],
        *,
        target_branch: str,
        expected_head: str,
        idempotency_key: str,
        originating_job: str,
        evidence_generation: str | None,
    ) -> None:
        """Route stale-helper status changes through TaskTransitionService."""

        if not helpers:
            return
        if self.transition_service is None:
            raise WorkflowActionError(
                "epic rebase repair has no transition service",
                category=WorkflowFailureCategory.POLICY,
                retryable=False,
            )
        issue_id = _text(getattr(epic, "id", None)) or epic.identifier
        async with self.orchestrator.issue_transition_lock(issue_id):
            current = await self._blocking(
                self._fresh_epic_authority, epic, facts
            )
            source, _target = self._branches(epic, facts)
            await self._blocking(
                self._assert_live_source_head,
                current,
                source=source,
                expected_head=expected_head,
            )
            running = getattr(
                getattr(self.orchestrator, "state", None), "running", {}
            )
            claimed = getattr(
                getattr(self.orchestrator, "state", None), "claimed", {}
            )
            for helper in helpers:
                if helper.id in running or helper.id in claimed:
                    raise WorkflowActionError(
                        f"wrong-target rebase helper {helper.identifier} is claimed",
                        category=WorkflowFailureCategory.TRANSIENT,
                        retryable=True,
                    )
                outcome = await self.transition_service.execute(
                    TransitionIntent(
                        project_id=self.project_id,
                        task_id=helper.identifier,
                        expected_status=helper.state,
                        expected_version=issue_authority_version(helper),
                        requested_status=ARCHIVED,
                        actor="oompah",
                        authority=TransitionAuthority.ORCHESTRATOR,
                        reason_code="epic.rebase_target_superseded",
                        idempotency_key=(
                            f"{idempotency_key}:retire:{helper.identifier}:"
                            f"{target_branch}"
                        ),
                        originating_job=originating_job,
                        evidence_generation=evidence_generation,
                        # The coordinator evaluates this complete semantic fact
                        # generation while holding the project mutation fence.
                        # Another helper becoming the deterministic keeper, or
                        # the epic's immediate target changing, must cancel the
                        # stale retirement before it stages an audit.
                        precondition_revision=facts.facts_version,
                        exact_head=(
                            _text(issue_exact_head(helper)).lower()
                            if _EXACT_HEAD_RE.fullmatch(
                                _text(issue_exact_head(helper)).lower()
                            )
                            else None
                        ),
                    )
                )
                if outcome.disposition in {
                    TransitionDisposition.APPLIED,
                    TransitionDisposition.ALREADY_APPLIED,
                    TransitionDisposition.STAGED,
                    TransitionDisposition.RECOVERED,
                }:
                    continue
                if outcome.disposition in {
                    TransitionDisposition.RETRYABLE,
                    TransitionDisposition.WAITING,
                }:
                    raise WorkflowActionError(
                        f"wrong-target rebase helper retirement deferred: "
                        f"{outcome.reason_code}",
                        category=WorkflowFailureCategory.TRANSIENT,
                        retryable=True,
                    )
                if outcome.reason_code in {
                    "transition.stale_status",
                    "transition.stale_version",
                    "transition.stale_precondition",
                }:
                    raise WorkflowActionSuperseded(
                        "rebase helper retirement authority changed",
                        replacement_generation=(
                            f"reassess:{facts.facts_version}"
                        ),
                    )
                raise WorkflowActionError(
                    f"wrong-target rebase helper retirement rejected: "
                    f"{outcome.reason_code}",
                    category=WorkflowFailureCategory.POLICY,
                    retryable=False,
                )

    def _cleanup_children(
        self, epic: Issue, facts: WorkflowFacts
    ) -> tuple[tuple[Issue, str, str | None], ...]:
        children = self._containment(facts).get("children")
        if not isinstance(children, (list, tuple)):
            return ()
        expected_target = self._branches(epic, facts)[0]
        tracker = self._tracker()
        selected: list[tuple[Issue, str, str | None]] = []
        for item in children:
            if not isinstance(item, Mapping):
                continue
            identifier = _text(item.get("identifier"))
            status = canonicalize_status(item.get("status"))
            if not identifier or status not in {DONE, MERGED, ARCHIVED}:
                continue
            waiver = retained_terminal_child_waiver(
                item,
                project_id=self.project_id,
                parent_id=epic.identifier,
            )
            if "retained_terminal_provenance" in item and waiver is None:
                raise WorkflowActionError(
                    f"Terminal child {identifier} has invalid retained "
                    "provenance for cleanup",
                    category=WorkflowFailureCategory.TRANSIENT,
                    retryable=True,
                )
            if waiver is not None:
                # A retained historical child has no delivery effect to prune.
                # Its waiver is never branch-deletion or landing authority.
                continue
            child = tracker.fetch_issue_detail(identifier)
            if child is None or _text(child.parent_id) != epic.identifier:
                continue
            current_status = canonicalize_status(child.state)
            expected_authority = _text(item.get("authority_version"))
            # Collector containment and this selection refresh both retain the
            # tracker-native child shape, so their authority comparison is
            # deliberately raw/raw.  The branch-deletion mutation boundary
            # binds both copies to the project before its final CAS.
            current_authority = issue_authority_version(child)
            if current_status != status or (
                expected_authority and current_authority != expected_authority
            ):
                raise WorkflowActionSuperseded(
                    f"child {identifier} changed during epic cleanup",
                    replacement_generation=f"cleanup:{current_authority}",
                )
            expected = self.orchestrator.project_store.epic_child_branch_name(
                epic.identifier, identifier
            )
            record = getattr(child, "integration", None)
            recorded = _text(
                getattr(record, "task_branch", None) if record is not None else None
            ) or _text(child.work_branch)
            if recorded != expected:
                continue
            requires_landing = status != ARCHIVED and not bool(
                item.get("maintenance")
            )
            expected_revision = _text(item.get("revision")).lower()
            landing_revision = ""
            if requires_landing:
                landing_revision = self._cleanup_landing_revision(
                    facts,
                    identifier,
                    expected_source=expected,
                    expected_target=expected_target,
                    expected_revision=expected_revision,
                ) or ""
                if not landing_revision:
                    raise WorkflowActionError(
                        f"Terminal child {identifier} has no exact landing proof "
                        "for cleanup",
                        category=WorkflowFailureCategory.TRANSIENT,
                        retryable=True,
                    )
                # A canonical durable landing remains exact evidence after the
                # child ref and tracker head are intentionally pruned. Reuse
                # that same revision instead of requiring a second cleanup-
                # specific head path.
                expected_revision = expected_revision or landing_revision
            current_head = _text(issue_exact_head(child)).lower()
            if (
                not _EXACT_HEAD_RE.fullmatch(expected_revision)
                or (
                    current_head
                    and (
                        not _EXACT_HEAD_RE.fullmatch(current_head)
                        or current_head != expected_revision
                    )
                )
                or (not current_head and not requires_landing)
            ):
                raise WorkflowActionError(
                    f"child {identifier} has no stable exact head for cleanup",
                    category=WorkflowFailureCategory.TRANSIENT,
                    retryable=True,
                )
            selected.append((child, expected, expected_revision or None))
        return tuple(selected)

    def _remote_branch_head(self, epic: Issue, branch: str) -> str | None:
        project = self._project(epic)
        try:
            result = self.orchestrator._run_project_network_git(
                project,
                ["git", "ls-remote", "--heads", "origin", branch],
                cwd=os.fspath(project.repo_path),
                timeout=30,
            )
        except Exception as exc:  # noqa: BLE001 - typed Git transport boundary
            raise WorkflowActionError(
                f"epic cleanup branch observation failed: {type(exc).__name__}",
                category=WorkflowFailureCategory.TRANSPORT,
                retryable=True,
            ) from exc
        if result.returncode != 0:
            raise WorkflowActionError(
                "epic cleanup branch observation returned a Git error",
                category=WorkflowFailureCategory.TRANSPORT,
                retryable=True,
            )
        output = _text(result.stdout)
        return output.split(maxsplit=1)[0].lower() if output else None

    def _remote_branch_present(self, epic: Issue, branch: str) -> bool:
        return self._remote_branch_head(epic, branch) is not None

    def _local_branch_present(self, epic: Issue, branch: str) -> bool:
        project = self._project(epic)
        operation = getattr(self.orchestrator.project_store, "_ref_exists", None)
        if not callable(operation):
            raise WorkflowActionError(
                "epic cleanup cannot verify local branch removal",
                category=WorkflowFailureCategory.POLICY,
                retryable=False,
            )
        try:
            return bool(operation(project.repo_path, f"refs/heads/{branch}"))
        except Exception as exc:  # noqa: BLE001 - typed Git observation boundary
            raise WorkflowActionError(
                f"epic cleanup local-ref observation failed: {type(exc).__name__}",
                category=WorkflowFailureCategory.TRANSIENT,
                retryable=True,
            ) from exc

    def _cleanup_evidence(
        self, epic: Issue, facts: WorkflowFacts
    ) -> Mapping[str, Any] | None:
        pending: list[str] = []
        for child, branch, _revision in self._cleanup_children(epic, facts):
            worktree = self.orchestrator.project_store.worktree_path_for(
                self.project_id, child.identifier
            )
            if os.path.exists(worktree) or self._remote_branch_present(epic, branch):
                pending.append(child.identifier)
            elif self._local_branch_present(epic, branch):
                pending.append(child.identifier)
        source, target = self._branches(epic, facts)
        epic_worktree = self.orchestrator.project_store.epic_worktree_path_for(
            self.project_id, epic.identifier
        )
        if os.path.exists(epic_worktree):
            pending.append(epic.identifier)
        if self._local_branch_present(epic, source) or self._remote_branch_present(
            epic, source
        ):
            pending.append(f"branch:{source}")
        if (
            self.orchestrator._get_epic_rebase_state(
                epic.identifier, project_id=self.project_id
            )
            is not None
        ):
            pending.append("rebase-state")
        if pending:
            return None
        return {
            "effect": EpicAction.CLEANUP.value,
            "epic_id": epic.identifier,
            "terminal_status": canonicalize_status(epic.state),
            "source_branch": source,
            "target_branch": target,
            "cleanup_complete": True,
        }

    def inspect_epic_effect(
        self,
        action: EpicAction,
        epic: Issue,
        facts: WorkflowFacts,
        payload: Mapping[str, Any],
    ) -> Mapping[str, Any] | None:
        if action is EpicAction.AUTO_CLOSE:
            evidence = self._landed_review_retirement_snapshot(epic, facts)
            return evidence if bool(evidence.get("review_retired")) else None
        if action is EpicAction.ROLLUP_REVIEW_CREATION:
            evidence = self._review_evidence(epic, facts)
            if evidence is None or not self._review_metadata_matches(epic, evidence):
                return None
            return evidence
        if action is EpicAction.TERMINAL_VALIDATION:
            evidence = self._review_evidence(
                epic,
                facts,
                expected_review_id=_text(payload.get("review_id")) or None,
                accepted_states=("open", "merged", "closed_merged"),
            )
            if evidence is None:
                if not bool(payload.get("merged")):
                    return {"effect": action.value, "noop": True}
                return None
            if not self._review_metadata_matches(epic, evidence):
                return None
            return {**evidence, "effect": action.value}
        if action is EpicAction.REBASE_REPAIR:
            return self._rebase_evidence(epic, facts, payload)
        if action is EpicAction.CLEANUP:
            return self._cleanup_evidence(epic, facts)
        raise WorkflowActionError(
            f"{action.value} is not an external epic effect",
            category=WorkflowFailureCategory.POLICY,
            retryable=False,
        )

    async def apply_epic_effect(
        self,
        action: EpicAction,
        epic: Issue,
        facts: WorkflowFacts,
        payload: Mapping[str, Any],
        *,
        idempotency_key: str,
        originating_job: str | None = None,
        evidence_generation: str | None = None,
    ) -> Mapping[str, Any]:
        """Apply one mutation to completion even if the worker timeout fires.

        A timeout cancels the caller, not a production tracker/forge/Git write.
        Shielding and sharing the task by durable idempotency key prevents an
        overlapping retry while the first mutation is still completing.
        """

        key = (action.value, idempotency_key)
        mutation = self._mutation_tasks.get(key)
        if mutation is None:
            mutation = asyncio.create_task(
                self._apply_epic_effect_impl(
                    action,
                    epic,
                    facts,
                    payload,
                    idempotency_key=idempotency_key,
                    originating_job=originating_job,
                    evidence_generation=evidence_generation,
                )
            )
            self._mutation_tasks[key] = mutation
            mutation.add_done_callback(
                lambda completed, mutation_key=key: self._mutation_finished(
                    mutation_key, completed
                )
            )
        # The underlying non-cancellable side effect remains shared, but the
        # caller's cancellation must propagate so worker deadlines and drain
        # budgets stay bounded.  A retry with the same durable key awaits this
        # exact task instead of starting an overlapping mutation.
        return await asyncio.shield(mutation)

    async def _apply_epic_effect_impl(
        self,
        action: EpicAction,
        epic: Issue,
        facts: WorkflowFacts,
        payload: Mapping[str, Any],
        *,
        idempotency_key: str,
        originating_job: str | None = None,
        evidence_generation: str | None = None,
    ) -> Mapping[str, Any]:
        if action is EpicAction.AUTO_CLOSE:
            return await self._blocking(
                self._retire_landed_review_under_authority,
                epic,
                facts,
                idempotency_key=idempotency_key,
            )

        if action is EpicAction.ROLLUP_REVIEW_CREATION:
            before_head = self._expected_epic_head(epic, facts)
            await self._blocking(
                self._open_review_under_authority,
                epic,
                facts,
                expected_head=before_head,
            )
            evidence = await self._blocking(
                self._review_evidence, epic, facts, expected_head=before_head
            )
            if evidence is None:
                raise WorkflowActionError(
                    "epic rollup review was deferred",
                    category=WorkflowFailureCategory.TRANSIENT,
                    retryable=True,
                )
            evidence = await self._blocking(
                self._persist_review_under_authority, epic, facts, evidence
            )
            return evidence

        if action is EpicAction.TERMINAL_VALIDATION:
            evidence = await self._blocking(
                self._review_evidence,
                epic,
                facts,
                expected_review_id=_text(payload.get("review_id")) or None,
                accepted_states=("open", "merged", "closed_merged"),
            )
            if evidence is None:
                if not bool(payload.get("merged")):
                    return {"effect": action.value, "noop": True}
                raise WorkflowActionError(
                    "terminal epic review is not exactly observable",
                    category=WorkflowFailureCategory.TRANSIENT,
                    retryable=True,
                )
            evidence = await self._blocking(
                self._persist_review_under_authority, epic, facts, evidence
            )
            await self._blocking(self._publish_review_metadata_change, epic)
            return {**evidence, "effect": action.value}

        if action is EpicAction.REBASE_REPAIR:
            source, target = self._branches(epic, facts)
            expected_head = self._expected_epic_head(epic, facts)
            matching, wrong_target = await self._blocking(
                self._rebase_helpers, epic, target_branch=target
            )
            duplicate_matching = tuple(matching[1:])
            await self._retire_wrong_rebase_helpers(
                epic,
                facts,
                (*wrong_target, *duplicate_matching),
                target_branch=target,
                expected_head=expected_head,
                idempotency_key=idempotency_key,
                originating_job=originating_job or idempotency_key,
                evidence_generation=evidence_generation,
            )
            helper = await self._blocking(
                self._ensure_rebase_helper_under_authority,
                epic,
                facts,
                source=source,
                target=target,
                expected_head=expected_head,
                idempotency_key=idempotency_key,
            )
            # Creation and every bookkeeping write above are serialized under
            # exact epic authority. Return the immutable identity obtained
            # from that boundary instead of immediately rediscovering the task
            # through a potentially lagging children projection. The worker's
            # separate verify phase re-reads this exact identity and fails
            # closed until the tracker can prove it.
            helper_id = _text(getattr(helper, "identifier", None)) or _text(
                getattr(helper, "id", None)
            )
            if not helper_id:  # defensive: _ensure already enforces this
                raise WorkflowActionError(
                    "rebase helper has no immutable identity",
                    category=WorkflowFailureCategory.TRANSIENT,
                    retryable=True,
                )
            return {
                "effect": EpicAction.REBASE_REPAIR.value,
                "helper_id": helper_id,
                "workflow_idempotency_key": idempotency_key,
                "source_branch": source,
                "target_branch": target,
            }

        if action is EpicAction.CLEANUP:
            cleaned: list[str] = []
            source, target = self._branches(epic, facts)
            epic_status = canonicalize_status(epic.state)
            if epic_status not in {MERGED, ARCHIVED}:
                raise WorkflowActionSuperseded(
                    "epic is no longer terminal for cleanup",
                    replacement_generation=(
                        f"reassess:{issue_authority_version(epic)}"
                    ),
                )
            own_landing = next(
                (
                    item
                    for item in facts.landings
                    if item.source == source and item.target == target
                ),
                None,
            )
            if (
                epic_status == MERGED
                and (
                    own_landing is None
                    or own_landing.state is not LandingState.LANDED
                )
            ):
                raise WorkflowActionSuperseded(
                    "merged epic cleanup no longer has exact target landing authority",
                    replacement_generation="reassess:epic-landing",
                )
            cleanup_children = await self._blocking(self._cleanup_children, epic, facts)
            for child, _branch, expected_revision in cleanup_children:
                if expected_revision is None:
                    raise WorkflowActionError(
                        f"child {child.identifier} has no exact cleanup head",
                        category=WorkflowFailureCategory.TRANSIENT,
                        retryable=True,
                    )
                await self._blocking(
                    self._delete_cleanup_child,
                    epic,
                    facts,
                    child,
                    expected_revision,
                )
                cleaned.append(child.identifier)
            cleanup = getattr(
                self.orchestrator.project_store,
                "cleanup_terminal_issue",
                None,
            )
            if not callable(cleanup):
                raise WorkflowActionError(
                    "epic cleanup store has no exact-generation cleanup API",
                    category=WorkflowFailureCategory.POLICY,
                    retryable=False,
                )
            if callable(cleanup):
                proof = (
                    getattr(own_landing, "proof", {}) if own_landing is not None else {}
                )
                expected_head = _text(
                    getattr(own_landing, "revision", None)
                ).lower()
                if not _EXACT_HEAD_RE.fullmatch(expected_head):
                    raise WorkflowActionError(
                        "epic cleanup has no exact source head",
                        category=WorkflowFailureCategory.TRANSIENT,
                        retryable=True,
                    )
                cleanup_result = await self._blocking(
                    self._cleanup_primary_under_authority,
                    epic,
                    facts,
                    source=source,
                    target=target,
                    expected_head=expected_head,
                    merge_commit_sha=(
                        proof.get("merge_commit_sha")
                        if isinstance(proof, Mapping)
                        else None
                    ),
                )
                if (
                    isinstance(cleanup_result, tuple)
                    and len(cleanup_result) > 1
                    and cleanup_result[1]
                ):
                    raise WorkflowActionError(
                        f"epic cleanup retained its owned branch: {cleanup_result[1]}",
                        category=WorkflowFailureCategory.TRANSIENT,
                        retryable=True,
                    )
            evidence = await self._blocking(self._cleanup_evidence, epic, facts)
            if evidence is None:
                raise WorkflowActionError(
                    "epic cleanup is not yet fully observable",
                    category=WorkflowFailureCategory.TRANSIENT,
                    retryable=True,
                )
            return {**evidence, "children_cleaned": cleaned}

        raise WorkflowActionError(
            f"{action.value} is not an external epic effect",
            category=WorkflowFailureCategory.POLICY,
            retryable=False,
        )

    def verify_epic_effect(
        self,
        action: EpicAction,
        epic: Issue,
        facts: WorkflowFacts,
        payload: Mapping[str, Any],
        receipt: Mapping[str, Any],
    ) -> Mapping[str, Any] | None:
        if action is EpicAction.AUTO_CLOSE:
            evidence = self._landed_review_retirement_snapshot(epic, facts)
            if (
                not bool(evidence.get("review_retired"))
                or _text(evidence.get("source_head")).lower()
                != _text(receipt.get("source_head")).lower()
                or _text(evidence.get("source_branch"))
                != _text(receipt.get("source_branch"))
                or _text(evidence.get("target_branch"))
                != _text(receipt.get("target_branch"))
            ):
                return None
            return evidence
        if action is EpicAction.ROLLUP_REVIEW_CREATION:
            evidence = self._review_evidence(
                epic,
                facts,
                expected_head=_text(receipt.get("source_head")) or None,
                expected_review_id=_text(receipt.get("review_id")) or None,
            )
            if evidence is None or not self._review_metadata_matches(epic, evidence):
                return None
            return evidence
        if action is EpicAction.TERMINAL_VALIDATION:
            if bool(receipt.get("noop")):
                return {"effect": action.value, "noop": True}
            evidence = self._review_evidence(
                epic,
                facts,
                expected_head=_text(receipt.get("source_head")) or None,
                expected_review_id=(
                    _text(payload.get("review_id"))
                    or _text(receipt.get("review_id"))
                    or None
                ),
                accepted_states=("open", "merged", "closed_merged"),
            )
            if evidence is None or not self._review_metadata_matches(epic, evidence):
                return None
            return {**evidence, "effect": action.value}
        if action is EpicAction.REBASE_REPAIR:
            return self._verify_rebase_receipt(
                epic, facts, payload, receipt
            )
        if action is EpicAction.CLEANUP:
            return self._cleanup_evidence(epic, facts)
        return None


def build_epic_workflow_handlers(
    orchestrator: Any,
    binding: Any,
) -> dict[str, EpicWorkflowHandler]:
    """Return total, project-bound production coverage for epic actions."""

    if binding.epic_controller is None:
        return {}
    effects = OrchestratorEpicWorkflowEffects(
        orchestrator,
        project_id=binding.project_id,
        transition_service=binding.transition_service,
    )
    backend = ProductionEpicWorkflowBackend(
        controller=binding.epic_controller,
        tracker=binding.tracker,
        effects=effects,
        persist_evidence=True,
    )
    handler = EpicWorkflowHandler(backend)
    return {action: handler for action in sorted(EPIC_ACTIONS)}


class EpicWorkflowEventRouter:
    """Turn process events into idempotent, exact-epic durable wake jobs."""

    def __init__(self, orchestrator: Any, runtime: Any) -> None:
        self.orchestrator = orchestrator
        self.runtime = runtime
        pool = getattr(orchestrator, "_tick_pool", None)
        self._owned_pool: ThreadPoolExecutor | None = None
        if pool is None:
            self._owned_pool = ThreadPoolExecutor(
                max_workers=1, thread_name_prefix="epic-events"
            )
            pool = self._owned_pool
        self._event_pool = pool
        self._event_lock = threading.Lock()
        self._event_tail: Future[Any] | None = None
        self._closed = False

    def _submit_ordered(
        self, operation: Any, /, *args: Any, **kwargs: Any
    ) -> Future[Any]:
        """Run blocking event work off-loop in original delivery order."""

        with self._event_lock:
            if self._closed:
                rejected: Future[Any] = Future()
                rejected.set_result(None)
                return rejected
            predecessor = self._event_tail

            def ordered() -> Any:
                if predecessor is not None:
                    if not predecessor.cancelled():
                        predecessor.exception()
                return operation(*args, **kwargs)

            try:
                submitted = self._event_pool.submit(ordered)
            except RuntimeError as exc:
                # During graceful exec restart the shared orchestrator pool
                # may close just before the event bus stops delivering forge
                # events.  Restart reconciliation is authoritative for that
                # late suffix; do not turn normal drain ordering into a noisy
                # handler failure.
                if "shutdown" not in str(exc).lower():
                    raise
                self._closed = True
                rejected = Future()
                rejected.set_result(None)
                return rejected
            submitted.add_done_callback(self._report_event_failure)
            self._event_tail = submitted
            return submitted

    @staticmethod
    def _report_event_failure(completed: Future[Any]) -> None:
        if completed.cancelled():
            return
        failure = completed.exception()
        if failure is not None:
            logger.error(
                "Epic workflow event failed",
                exc_info=(type(failure), failure, failure.__traceback__),
            )

    def drain_events(self, timeout: float | None = None) -> None:
        """Wait for already-submitted event work; intended for drains/tests."""

        with self._event_lock:
            tail = self._event_tail
        if tail is not None:
            tail.result(timeout=timeout)

    def close(self) -> None:
        """Drain and close only a router-owned compatibility executor."""

        with self._event_lock:
            self._closed = True
            tail = self._event_tail
        if tail is not None:
            tail.result()
        if self._owned_pool is not None:
            self._owned_pool.shutdown(wait=True)

    def _binding(self, project_id: object) -> Any | None:
        return self.runtime.project_bindings.get(_text(project_id))

    def _resolve_issue(
        self, project_id: object, identifier: object
    ) -> tuple[Any, Any] | None:
        task_id = _text(identifier)
        if not task_id:
            return None
        binding = self._binding(project_id)
        if binding is None:
            return None
        issue = binding.tracker.fetch_issue_detail(task_id)
        return (binding, issue) if issue is not None else None

    @staticmethod
    def _generation(
        action: EpicAction,
        epic: Issue,
        source: str,
        payload: Mapping[str, Any],
    ) -> str:
        value = json.dumps(
            {
                "action": action.value,
                "authority": issue_authority_version(epic),
                "parent_id": _text(epic.parent_id) or None,
                "source": _text(source),
                "payload": dict(payload),
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        return f"epic-event:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"

    @staticmethod
    def _cleanup_schedule_head(binding: Any, epic: Issue) -> str | None:
        """Capture the exact cleanup generation before durable enqueue."""

        tracker_head = _text(issue_exact_head(epic)).lower()
        if _EXACT_HEAD_RE.fullmatch(tracker_head):
            return tracker_head
        controller = getattr(binding, "epic_controller", None)
        collector = getattr(controller, "collector", None)
        if collector is None:
            return None
        try:
            facts = collector.collect(epic.identifier)
            containment = facts.fact(FactDomain.CONTAINMENT)
        except Exception:  # noqa: BLE001 - event scheduling fails closed
            return None
        if (
            containment.state is not FactState.KNOWN
            or not isinstance(containment.value, Mapping)
        ):
            return None
        source = _text(containment.value.get("epic_branch"))
        target = _text(containment.value.get("target_branch"))
        revision = next(
            (
                _text(landing.revision).lower()
                for landing in facts.landings
                if landing.source == source and landing.target == target
            ),
            "",
        )
        return revision if _EXACT_HEAD_RE.fullmatch(revision) else None

    @staticmethod
    def _restart_cleanup_authority(binding: Any, epic: Issue) -> str:
        """Classify retained cleanup authority without tracker or Git I/O."""

        controller = getattr(binding, "epic_controller", None)
        store = getattr(controller, "store", None)
        collector = getattr(controller, "collector", None)
        project_id = _text(epic.project_id) or _text(
            getattr(collector, "project_id", None)
        )
        if store is None or not project_id:
            return "store_unavailable"
        try:
            jobs = store.list_jobs(
                project_id=project_id,
                task_id=epic.identifier,
                actions=(EpicAction.CLEANUP.value,),
                scheduling_lanes=(
                    f"epic-event:{EpicAction.CLEANUP.value}",
                ),
                newest_first=True,
                limit=1,
            )
        except Exception:  # noqa: BLE001 - startup evidence fails closed
            return "store_error"
        if not jobs:
            return "no_evidence"
        latest = jobs[0]
        expected_head = _text(getattr(latest, "expected_head_sha", None)).lower()
        exact_authority = bool(_EXACT_HEAD_RE.fullmatch(expected_head))
        if latest.state is WorkflowJobState.COMPLETED and exact_authority:
            return "completed"
        if latest.state in ACTIVE_JOB_STATES and exact_authority:
            return "active"
        if latest.state is WorkflowJobState.EXHAUSTED:
            return "exhausted"
        return f"{latest.state.value}_without_exact_authority"

    def _schedule(
        self,
        binding: Any,
        epic: Issue,
        action: EpicAction,
        *,
        source: str,
        payload: Mapping[str, Any] | None = None,
        expected_evidence_revision: str | None = None,
    ) -> bool:
        if not self.runtime.enforce or binding.epic_controller is None:
            return False
        event_payload = {"event_source": source, **dict(payload or {})}
        # A rebase request is fenced by its exact target, current epic
        # authority/source head, and the backend's fresh decision check.  The
        # collector's evidence revision may legitimately advance between this
        # targeted event callback and worker revalidation (for example after a
        # Git fetch) without changing any of those authorities.  Do not make
        # that mutable observation an additional generic worker CAS.
        if action is EpicAction.REBASE_REPAIR:
            expected_evidence_revision = None
            expected_head = _text(event_payload.get("source_head")).lower()
            if not _EXACT_HEAD_RE.fullmatch(expected_head):
                logger.warning(
                    "Deferred epic rebase scheduling for %s: exact live source "
                    "generation is unavailable",
                    epic.identifier,
                )
                return False
            # Advance the immutable event identity once so requests stranded
            # under former observation/source contracts do not replay their
            # already-terminal idempotency keys after upgrade.
            event_payload["revalidation_contract"] = (
                "target-source-head-native-helper-project-v5"
            )
        else:
            expected_head = issue_exact_head(epic)
        if action is EpicAction.CLEANUP:
            expected_head = self._cleanup_schedule_head(binding, epic)
            if expected_head is None:
                log = (
                    logger.debug
                    if source == "workflow-runtime-restart"
                    else logger.warning
                )
                log(
                    "Deferred epic cleanup scheduling for %s: exact source "
                    "generation is unavailable",
                    epic.identifier,
                )
                return False
            # The fallback live source head is not part of tracker authority.
            # Include it in event identity so a later source generation cannot
            # replay the same durable enqueue key.
            event_payload["cleanup_head_sha"] = expected_head
        controller = binding.epic_controller
        schedule_kwargs = {
            "task_id": epic.identifier,
            "action": action,
            "generation": self._generation(action, epic, source, event_payload),
            "expected_evidence_revision": expected_evidence_revision,
            "expected_head_sha": expected_head,
            "payload": event_payload,
        }
        schedule_write = getattr(type(controller), "schedule_action_write", None)
        if callable(schedule_write):
            write = controller.schedule_action_write(**schedule_kwargs)
            created = bool(write.created)
        else:
            # Compatibility for narrow injected controllers which implement the
            # original public protocol. Production uses schedule_action_write.
            controller.schedule_action(**schedule_kwargs)
            created = True
        binding.epic_controller.scheduler.wake(source)
        request_admission = getattr(
            self.orchestrator,
            "_request_workflow_batch_continuation",
            None,
        )
        if callable(request_admission):
            # This router has already performed the targeted fact collection
            # and durably scheduled the exact epic job.  Waking an ordinary
            # reconciliation here would turn transition UI notifications back
            # into full world scans; admit from the published cut instead.
            request_admission(reason=f"epic_workflow_event:{source}")
        else:
            # Compatibility for narrow adapter fixtures without a production
            # orchestrator event-intake owner.
            self.orchestrator.request_refresh()
        return created

    @staticmethod
    def _current_evaluation(binding: Any, epic: Issue) -> Any | None:
        """Evaluate one epic without replacing project-wide projections."""

        controller = EpicWorkflowController(
            collector=binding.epic_controller.collector,
            store=binding.epic_controller.store,
            scheduler=binding.epic_controller.scheduler,
            decision_limit=binding.epic_controller.decision_limit,
        )
        batch = controller.evaluate([epic], persist_evidence=True)
        return batch.tasks[0] if batch.tasks else None

    @staticmethod
    def _current_decision(binding: Any, epic: Issue) -> Any | None:
        evaluated = EpicWorkflowEventRouter._current_evaluation(binding, epic)
        return evaluated.decision if evaluated is not None else None

    def _schedule_current_decision(
        self,
        binding: Any,
        epic: Issue,
        *,
        source: str,
        payload: Mapping[str, Any] | None = None,
    ) -> int:
        """Collect and enqueue the exact epic's presently authorized action.

        Event-marker actions are useful restart evidence, but they cannot be
        the only work queued after a child or forge event: readiness may now
        authorize a review, terminal landing may authorize auto-close, and a
        changed child may require another exact landing observation.  Use an
        ephemeral controller so this one-epic event does not replace the
        persistent controller's project-wide projection cache.
        """

        if not self.runtime.enforce:
            return 0
        decision = self._current_decision(binding, epic)
        if decision is None:
            return 0
        evidence_payload = {
            **dict(payload or {}),
            "decision_reason": decision.reason_code,
            "evidence_revision": decision.evidence_revision,
        }
        scheduled = 0
        for action_name in decision.durable_jobs:
            if action_name not in EPIC_ACTIONS:
                continue
            scheduled += int(
                self._schedule(
                    binding,
                    epic,
                    EpicAction(action_name),
                    source=source,
                    payload=evidence_payload,
                    expected_evidence_revision=decision.evidence_revision,
                )
            )
        return scheduled

    def _wake_issue(self, payload: Mapping[str, Any], *, source: str) -> None:
        if not self.runtime.enforce:
            return
        resolved = self._resolve_issue(
            payload.get("project_id"),
            payload.get("identifier") or payload.get("issue_id"),
        )
        if resolved is None:
            return
        binding, issue = resolved
        impacted: list[Issue] = []
        if is_epic_rollup_issue(issue, tracker=binding.tracker):
            impacted.append(issue)
        parent_id = _text(issue.parent_id)
        if parent_id:
            parent = binding.tracker.fetch_issue_detail(parent_id)
            if parent is not None and is_epic_rollup_issue(
                parent, tracker=binding.tracker
            ):
                impacted.append(parent)
        wake_payload = {
            "trigger_identifier": issue.identifier,
            "trigger_authority": issue_authority_version(issue),
            "change": _text(payload.get("change")) or None,
        }
        for epic in {item.identifier: item for item in impacted}.values():
            if canonicalize_status(epic.state) in {MERGED, ARCHIVED}:
                self._schedule(
                    binding,
                    epic,
                    EpicAction.CLEANUP,
                    source=source,
                    payload=wake_payload,
                )
                continue
            self._schedule(
                binding,
                epic,
                EpicAction.READINESS,
                source=source,
                payload=wake_payload,
            )
            self._schedule(
                binding,
                epic,
                EpicAction.TARGET_RESOLUTION,
                source=source,
                payload=wake_payload,
            )
            self._schedule_current_decision(
                binding,
                epic,
                source=source,
                payload=wake_payload,
            )

    def _wake_issue_batch(
        self,
        payload: Mapping[str, Any],
        identifiers: tuple[str, ...],
        *,
        source: str,
    ) -> None:
        """Wake every impacted epic once for one committed task batch."""

        if not self.runtime.enforce:
            return
        impacted: dict[tuple[int, str], tuple[Any, Issue]] = {}
        trigger_authorities: dict[str, str] = {}
        project_id = payload.get("project_id")
        for identifier in identifiers:
            resolved = self._resolve_issue(project_id, identifier)
            if resolved is None:
                continue
            binding, issue = resolved
            trigger_authorities[issue.identifier] = issue_authority_version(issue)
            if is_epic_rollup_issue(issue, tracker=binding.tracker):
                impacted[(id(binding), issue.identifier)] = (binding, issue)
            parent_id = _text(issue.parent_id)
            if parent_id:
                parent = binding.tracker.fetch_issue_detail(parent_id)
                if parent is not None and is_epic_rollup_issue(
                    parent, tracker=binding.tracker
                ):
                    impacted[(id(binding), parent.identifier)] = (binding, parent)

        wake_payload = {
            "trigger_identifiers": list(trigger_authorities),
            "trigger_authorities": trigger_authorities,
            "change": _text(payload.get("change")) or None,
            "batch_id": _text(payload.get("batch_id")) or None,
        }
        for binding, epic in impacted.values():
            if canonicalize_status(epic.state) in {MERGED, ARCHIVED}:
                self._schedule(
                    binding,
                    epic,
                    EpicAction.CLEANUP,
                    source=source,
                    payload=wake_payload,
                )
                continue
            self._schedule(
                binding,
                epic,
                EpicAction.READINESS,
                source=source,
                payload=wake_payload,
            )
            self._schedule(
                binding,
                epic,
                EpicAction.TARGET_RESOLUTION,
                source=source,
                payload=wake_payload,
            )
            self._schedule_current_decision(
                binding,
                epic,
                source=source,
                payload=wake_payload,
            )

    def on_issue_changed(self, _event: object, payload: dict[str, Any]) -> None:
        if not self.runtime.enforce:
            return
        identifiers = payload.get("identifiers")
        if isinstance(identifiers, list):
            members = tuple(
                str(identifier).strip()
                for identifier in identifiers
                if str(identifier).strip()
            )
            if members:
                self._submit_ordered(
                    self._wake_issue_batch,
                    dict(payload),
                    members,
                    source="issue-state-changed",
                )
            return
        self._submit_ordered(
            self._wake_issue, dict(payload), source="issue-state-changed"
        )

    def on_agent_finished(self, _event: object, payload: dict[str, Any]) -> None:
        if not self.runtime.enforce:
            return
        self._submit_ordered(self._wake_issue, dict(payload), source="agent-finished")

    def on_forge_event(self, _event: object, payload: dict[str, Any]) -> None:
        if not self.runtime.enforce:
            return
        self._submit_ordered(self._on_forge_event, dict(payload))

    def _on_forge_event(self, payload: dict[str, Any]) -> None:
        if not self.runtime.enforce:
            return
        project_id = payload.get("project_id")
        source_branch = _text(payload.get("source_branch"))
        if not project_id or not source_branch.startswith("epic-"):
            return
        identifier = source_branch.removeprefix("epic-")
        resolved = self._resolve_issue(project_id, identifier)
        if resolved is None:
            return
        binding, epic = resolved
        if not is_epic_rollup_issue(epic, tracker=binding.tracker):
            return
        self._schedule(
            binding,
            epic,
            EpicAction.TERMINAL_VALIDATION,
            source="forge-review-changed",
            payload={
                "review_id": _text(payload.get("review_id")) or None,
                "source_branch": source_branch,
                "target_branch": _text(payload.get("target_branch")) or None,
                "action": _text(payload.get("action")) or None,
                "merged": bool(payload.get("merged")),
            },
        )
        # The nested epic and its immediate parent both consume this landing:
        # the child may auto-close, while the parent may now create its own
        # rollup review.  Route the exact issue through the same parent-aware
        # event path; generations remain evidence-fenced and project-bound.
        self._wake_issue(
            {
                "project_id": project_id,
                "identifier": epic.identifier,
                "change": "forge-review-changed",
            },
            source="forge-review-changed",
        )
        if bool(payload.get("merged")):
            self._schedule(
                binding,
                epic,
                EpicAction.CLEANUP,
                source="forge-review-merged",
                payload={
                    "review_id": _text(payload.get("review_id")) or None,
                    "source_branch": source_branch,
                    "target_branch": _text(payload.get("target_branch")) or None,
                },
            )

    def on_rebase_requested(self, _event: object, payload: dict[str, Any]) -> None:
        if not self.runtime.enforce:
            return
        self._submit_ordered(self._on_rebase_requested, dict(payload))

    def _on_rebase_requested(self, payload: dict[str, Any]) -> None:
        if not self.runtime.enforce:
            return
        resolved = self._resolve_issue(
            payload.get("project_id"), payload.get("identifier")
        )
        if resolved is None:
            return
        binding, epic = resolved
        if not is_epic_rollup_issue(epic, tracker=binding.tracker):
            return
        evaluated = self._current_evaluation(binding, epic)
        if evaluated is None:
            return
        decision = evaluated.decision
        containment = evaluated.facts.fact(FactDomain.CONTAINMENT)
        if (
            containment.state is not FactState.KNOWN
            or not isinstance(containment.value, Mapping)
        ):
            return
        source_branch = _text(containment.value.get("epic_branch"))
        target_branch = _text(payload.get("target_branch"))
        source_head = next(
            (
                _text(landing.revision).lower()
                for landing in evaluated.facts.landings
                if landing.source == source_branch
                and landing.target == target_branch
            ),
            "",
        )
        if not source_branch or not _EXACT_HEAD_RE.fullmatch(source_head):
            return
        self._schedule(
            binding,
            epic,
            EpicAction.REBASE_REPAIR,
            source="epic-rebase-requested",
            payload={
                "source_branch": source_branch,
                "source_head": source_head,
                "target_branch": target_branch,
                "request_source": _text(payload.get("source")) or None,
                "evidence_revision": decision.evidence_revision,
            },
            expected_evidence_revision=decision.evidence_revision,
        )

    def schedule_restart(self) -> Future[Any]:
        if not self.runtime.enforce:
            completed: Future[Any] = Future()
            completed.set_result(0)
            return completed
        return self._submit_ordered(self._schedule_restart)

    def _schedule_restart(self) -> int:
        scheduled = 0
        historical_cleanup: list[str] = []
        actionable_cleanup: list[tuple[str, str]] = []
        if not self.runtime.enforce:
            return scheduled
        for binding in self.runtime.project_bindings.values():
            operation = getattr(binding.tracker, "fetch_all_issues_enriched", None)
            if not callable(operation):
                operation = binding.tracker.fetch_all_issues
            for issue in operation():
                if not is_epic_rollup_issue(issue, tracker=binding.tracker):
                    continue
                if canonicalize_status(issue.state) in {MERGED, ARCHIVED}:
                    tracker_head = _text(issue_exact_head(issue)).lower()
                    if not _EXACT_HEAD_RE.fullmatch(tracker_head):
                        authority = self._restart_cleanup_authority(binding, issue)
                        if authority == "completed":
                            historical_cleanup.append(issue.identifier)
                        elif authority != "active":
                            actionable_cleanup.append((issue.identifier, authority))
                        continue
                    cleanup_scheduled = self._schedule(
                        binding,
                        issue,
                        EpicAction.CLEANUP,
                        source="workflow-runtime-restart",
                    )
                    scheduled += int(cleanup_scheduled)
                    continue
                scheduled += int(
                    self._schedule(
                        binding,
                        issue,
                        EpicAction.RESTART_RECONCILIATION,
                        source="workflow-runtime-restart",
                    )
                )
                # A forge webhook may have landed while the service was
                # stopped. Refresh the exact review head before an auto-close
                # generation is allowed to use that head as its terminal CAS.
                scheduled += int(
                    self._schedule(
                        binding,
                        issue,
                        EpicAction.TERMINAL_VALIDATION,
                        source="workflow-runtime-restart",
                        payload={
                            "merged": False,
                        },
                    )
                )
                scheduled += self._schedule_current_decision(
                    binding,
                    issue,
                    source="workflow-runtime-restart",
                )
        if historical_cleanup or actionable_cleanup:
            historical_examples = ", ".join(
                sorted(historical_cleanup)[:_RESTART_CLEANUP_LOG_SAMPLE]
            ) or "none"
            actionable_examples = ", ".join(
                f"{identifier}({reason})"
                for identifier, reason in sorted(actionable_cleanup)[
                    :_RESTART_CLEANUP_LOG_SAMPLE
                ]
            ) or "none"
            log = logger.warning if actionable_cleanup else logger.info
            log(
                "Epic restart cleanup seed summary: historical_completed=%d "
                "actionable_uncertain=%d; historical_examples=%s; "
                "actionable_examples=%s",
                len(historical_cleanup),
                len(actionable_cleanup),
                historical_examples,
                actionable_examples,
            )
        return scheduled


def attach_epic_workflow_events(
    orchestrator: Any, runtime: Any
) -> EpicWorkflowEventRouter:
    """Attach production event call sites once and seed restart reconciliation."""

    existing = getattr(orchestrator, "_epic_workflow_event_router", None)
    if isinstance(existing, EpicWorkflowEventRouter):
        return existing
    router = EpicWorkflowEventRouter(orchestrator, runtime)
    orchestrator.event_bus.subscribe(
        EventType.ISSUE_STATE_CHANGED, router.on_issue_changed
    )
    for event in (
        EventType.AGENT_COMPLETED,
        EventType.AGENT_FAILED,
        EventType.AGENT_TERMINATED,
    ):
        orchestrator.event_bus.subscribe(event, router.on_agent_finished)
    orchestrator.event_bus.subscribe(
        EventType.FORGE_WEBHOOK_RECEIVED, router.on_forge_event
    )
    orchestrator.event_bus.subscribe(
        "epic_rebase_requested", router.on_rebase_requested
    )
    orchestrator._epic_workflow_event_router = router
    router.schedule_restart()
    return router


__all__ = [
    "OrchestratorEpicWorkflowEffects",
    "EpicWorkflowEventRouter",
    "attach_epic_workflow_events",
    "build_epic_workflow_handlers",
]
