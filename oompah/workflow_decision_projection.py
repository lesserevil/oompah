"""Authoritative publication and projection of workflow decisions.

The workflow controller and shadow evaluator produce decisions, but neither
owns their public representation.  This module is the single coordinator for
generation-fenced publication, durable availability metadata, immutable API
projection, and operator-actionable alerts.

The coordinator deliberately depends on a small structural host protocol
instead of importing :mod:`oompah.orchestrator`.  ``Orchestrator`` retains
compatibility attributes and delegate methods while this module owns the
publication transaction and read model.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Protocol

from oompah.work_decision import WorkDecision
from oompah.work_decision_projection import (
    project_work_decision,
    work_decision_alert,
)
from oompah.workflow_jobs import WorkflowJobPublicationError

logger = logging.getLogger(__name__)


class WorkDecisionProjectionHost(Protocol):
    """Compatibility state required by the projection coordinator."""

    config: Any
    _work_decisions_lock: Any
    _work_decisions: dict[tuple[str, str], WorkDecision]
    _work_decision_source: str | None
    _work_decision_generation: int
    _work_decision_publication_epoch: int
    _work_decision_updated_at: str | None
    _work_decision_unavailable_projects: set[str]
    _work_decision_incomplete_projects: set[str]
    _work_decision_incomplete_keys: set[tuple[str, str]]
    _work_decision_incomplete_reason: str | None
    _work_decision_snapshot_complete: bool
    _workflow_shadow_scan_cursor: int

    def _save_state(self, **updates: Any) -> bool | None: ...


@dataclass(frozen=True, slots=True)
class WorkDecisionPublication:
    """Result and compensators for one public projection transaction."""

    accepted: bool
    changed: bool
    rejection: str | None = None
    _commit_memory: Callable[[], None] | None = field(
        default=None, repr=False, compare=False
    )
    _rollback: Callable[[], None] | None = field(
        default=None, repr=False, compare=False
    )

    def commit_memory(self) -> None:
        if self._commit_memory is not None:
            self._commit_memory()

    def rollback(self) -> None:
        if self._rollback is not None:
            self._rollback()


@dataclass(frozen=True, slots=True)
class _NormalizedPublication:
    source: str
    generation: int
    epoch: int
    shadow_cursor: int | None
    live_keys: frozenset[tuple[str, str]]
    incoming: dict[tuple[str, str], WorkDecision]
    preserved_projects: frozenset[str]
    incomplete_keys: frozenset[tuple[str, str]]
    incomplete_projects: frozenset[str]
    incomplete_reason: str | None
    complete: bool


@dataclass(frozen=True, slots=True)
class _ProjectionCut:
    decisions: dict[tuple[str, str], WorkDecision]
    unavailable_projects: frozenset[str]
    complete: bool
    incomplete_keys: frozenset[tuple[str, str]]
    incomplete_projects: frozenset[str]
    incomplete_reason: str | None
    source: str | None
    generation: int
    updated_at: str | None
    shadow_cursor: int
    availability: dict[str, Any]


@dataclass(frozen=True, slots=True)
class _PreparedPublication:
    decisions: dict[tuple[str, str], WorkDecision]
    complete: bool
    changed: bool
    updated_at: str | None
    availability: dict[str, Any]


class WorkDecisionProjectionCoordinator:
    """Own the decision registry's durable/public consistency boundary."""

    @staticmethod
    def _normalize(
        decisions: tuple[WorkDecision, ...] | list[WorkDecision],
        generation: int,
        *,
        source: str,
        live_keys: set[tuple[str, str]],
        publication_epoch: int,
        failed_projects: set[str] | None,
        scan_complete: bool,
        incomplete_keys: set[tuple[str, str]] | None,
        incomplete_reason: str | None,
        shadow_scan_cursor: int | None,
    ) -> _NormalizedPublication:
        normalized_source = str(source or "").strip().lower()
        snapshot_generation = int(generation)
        if snapshot_generation < 1:
            raise ValueError("work-decision generation must be positive")
        captured_epoch = int(publication_epoch)
        if captured_epoch < 1:
            raise ValueError("work-decision publication epoch must be positive")
        normalized_cursor = (
            int(shadow_scan_cursor) if shadow_scan_cursor is not None else None
        )
        if normalized_cursor is not None and normalized_cursor < 0:
            raise ValueError("shadow scan cursor must be nonnegative")

        normalized_live_keys = frozenset(
            (str(project_id or "legacy"), str(task_id).strip())
            for project_id, task_id in live_keys
            if str(task_id or "").strip()
        )
        incoming = {
            (str(decision.project_id or "legacy"), decision.task_id): decision
            for decision in decisions
        }
        if any(key not in normalized_live_keys for key in incoming):
            raise ValueError("work decisions must belong to the live snapshot")
        preserved_projects = frozenset(
            str(project_id or "legacy")
            for project_id in (failed_projects or set())
        )
        explicit_incomplete = frozenset(
            (str(project_id or "legacy"), str(task_id).strip())
            for project_id, task_id in (incomplete_keys or set())
            if str(task_id or "").strip()
        )
        if any(key not in normalized_live_keys for key in explicit_incomplete):
            raise ValueError(
                "incomplete work decisions must belong to the live snapshot"
            )
        omitted = normalized_live_keys - incoming.keys()
        next_incomplete = frozenset(omitted | explicit_incomplete)
        if not scan_complete and not next_incomplete:
            next_incomplete = normalized_live_keys
        complete = bool(scan_complete) and not omitted and not explicit_incomplete
        reason = incomplete_reason
        if not complete and not reason:
            reason = (
                f"bounded {normalized_source} scan evaluated {len(incoming)} of "
                f"{len(normalized_live_keys)} live tasks; omitted tasks will be "
                "evaluated by rotating future sweeps"
            )
        normalized_reason = (
            str(reason).strip()
            if not complete and str(reason or "").strip()
            else None
        )
        return _NormalizedPublication(
            source=normalized_source,
            generation=snapshot_generation,
            epoch=captured_epoch,
            shadow_cursor=normalized_cursor,
            live_keys=normalized_live_keys,
            incoming=incoming,
            preserved_projects=preserved_projects,
            incomplete_keys=next_incomplete,
            incomplete_projects=frozenset(key[0] for key in next_incomplete),
            incomplete_reason=normalized_reason,
            complete=complete,
        )

    @staticmethod
    def _availability_payload(
        *,
        source: str | None,
        complete: bool,
        unavailable_projects: frozenset[str] | set[str],
        incomplete_projects: frozenset[str] | set[str],
        incomplete_keys: frozenset[tuple[str, str]] | set[tuple[str, str]],
        incomplete_reason: str | None,
        epoch: int,
        updated_at: str | None,
        shadow_cursor: int,
    ) -> dict[str, Any]:
        return {
            "source": source,
            "complete": complete,
            "unavailable_projects": sorted(unavailable_projects),
            "incomplete_projects": sorted(incomplete_projects),
            "incomplete_tasks": [
                {"project_id": project_id, "task_id": task_id}
                for project_id, task_id in sorted(incomplete_keys)
            ],
            "incomplete_reason": incomplete_reason,
            "publication_epoch": epoch,
            "updated_at": updated_at,
            "shadow_scan_cursor_version": 1,
            "shadow_scan_cursor": shadow_cursor,
        }

    def _capture_cut(self, host: WorkDecisionProjectionHost) -> _ProjectionCut:
        unavailable = frozenset(
            getattr(host, "_work_decision_unavailable_projects", set())
        )
        incomplete_keys = frozenset(
            getattr(host, "_work_decision_incomplete_keys", set())
        )
        incomplete_projects = frozenset(
            getattr(host, "_work_decision_incomplete_projects", set())
        )
        incomplete_reason = getattr(host, "_work_decision_incomplete_reason", None)
        cursor = int(getattr(host, "_workflow_shadow_scan_cursor", 0))
        return _ProjectionCut(
            decisions=dict(host._work_decisions),
            unavailable_projects=unavailable,
            complete=bool(getattr(host, "_work_decision_snapshot_complete", False)),
            incomplete_keys=incomplete_keys,
            incomplete_projects=incomplete_projects,
            incomplete_reason=incomplete_reason,
            source=host._work_decision_source,
            generation=host._work_decision_generation,
            updated_at=host._work_decision_updated_at,
            shadow_cursor=cursor,
            availability=self._availability_payload(
                source=host._work_decision_source,
                complete=bool(
                    getattr(host, "_work_decision_snapshot_complete", False)
                ),
                unavailable_projects=unavailable,
                incomplete_projects=incomplete_projects,
                incomplete_keys=incomplete_keys,
                incomplete_reason=incomplete_reason,
                epoch=host._work_decision_publication_epoch,
                updated_at=host._work_decision_updated_at,
                shadow_cursor=cursor,
            ),
        )

    @staticmethod
    def _expected_source(host: WorkDecisionProjectionHost) -> str | None:
        mode = str(host.config.workflow_engine_mode or "off").lower()
        if mode == "enforce":
            return "controller"
        if mode == "shadow":
            return "shadow"
        return None

    def _prepare(
        self,
        host: WorkDecisionProjectionHost,
        normalized: _NormalizedPublication,
        previous: _ProjectionCut,
    ) -> _PreparedPublication:
        if previous.source != normalized.source:
            updated: dict[tuple[str, str], WorkDecision] = {}
        else:
            updated = {
                key: decision
                for key, decision in previous.decisions.items()
                if key in normalized.live_keys
                or key[0] in normalized.preserved_projects
            }
        updated.update(normalized.incoming)
        complete = normalized.complete and not normalized.preserved_projects
        changed = any(
            (
                updated != previous.decisions,
                normalized.preserved_projects != previous.unavailable_projects,
                normalized.incomplete_keys != previous.incomplete_keys,
                normalized.incomplete_projects != previous.incomplete_projects,
                normalized.incomplete_reason != previous.incomplete_reason,
                complete != previous.complete,
                normalized.source != previous.source,
            )
        )
        updated_at = (
            datetime.now(timezone.utc).isoformat()
            if changed
            else host._work_decision_updated_at
        )
        cursor = (
            normalized.shadow_cursor
            if normalized.shadow_cursor is not None
            else previous.shadow_cursor
        )
        return _PreparedPublication(
            decisions=updated,
            complete=complete,
            changed=changed,
            updated_at=updated_at,
            availability=self._availability_payload(
                source=normalized.source,
                complete=complete,
                unavailable_projects=normalized.preserved_projects,
                incomplete_projects=normalized.incomplete_projects,
                incomplete_keys=normalized.incomplete_keys,
                incomplete_reason=normalized.incomplete_reason,
                epoch=normalized.epoch,
                updated_at=updated_at,
                shadow_cursor=cursor,
            ),
        )

    @staticmethod
    def _persist(
        host: WorkDecisionProjectionHost, payload: dict[str, Any]
    ) -> bool:
        if not hasattr(host, "_state_io_lock"):
            return True
        return host._save_state(work_decision_availability=payload) is not False

    def _commit_producer(
        self,
        host: WorkDecisionProjectionHost,
        producer_transaction: Any,
        previous: _ProjectionCut,
    ) -> str | None:
        try:
            producer_transaction.commit()
            return None
        except Exception as exc:  # noqa: BLE001 - typed at the durable boundary
            logger.exception(
                "Rejected workflow decision publication because its durable "
                "producer cut could not commit"
            )
            try:
                restored = self._persist(host, previous.availability)
            except Exception:  # noqa: BLE001 - preserve explicit failure state
                logger.exception(
                    "Prior workflow decision availability restoration raised"
                )
                restored = False
            rollback_failed = (
                isinstance(exc, WorkflowJobPublicationError)
                and exc.rollback_failed
            )
            if not restored:
                logger.critical(
                    "Workflow decision durable commit failed and the prior "
                    "availability cut could not be restored"
                )
                return (
                    "durable_commit_and_store_rollback_failed"
                    if rollback_failed
                    else "durable_commit_state_rollback_failed"
                )
            return (
                "durable_commit_rollback_failed"
                if rollback_failed
                else "durable_commit_failed"
            )

    def publish(
        self,
        host: WorkDecisionProjectionHost,
        decisions: tuple[WorkDecision, ...] | list[WorkDecision],
        generation: int,
        *,
        source: str,
        live_keys: set[tuple[str, str]],
        publication_epoch: int,
        failed_projects: set[str] | None = None,
        scan_complete: bool = True,
        incomplete_keys: set[tuple[str, str]] | None = None,
        incomplete_reason: str | None = None,
        shadow_scan_cursor: int | None = None,
        producer_transaction: Any | None = None,
        defer_memory: bool = False,
    ) -> WorkDecisionPublication:
        """Publish one exact generation while preserving durable/public parity."""

        normalized = self._normalize(
            decisions,
            generation,
            source=source,
            live_keys=live_keys,
            publication_epoch=publication_epoch,
            failed_projects=failed_projects,
            scan_complete=scan_complete,
            incomplete_keys=incomplete_keys,
            incomplete_reason=incomplete_reason,
            shadow_scan_cursor=shadow_scan_cursor,
        )
        with host._work_decisions_lock:
            rejection = self._publication_rejection(host, normalized)
            if rejection is not None:
                return WorkDecisionPublication(False, False, rejection)
            previous = self._capture_cut(host)
            prepared = self._prepare(host, normalized, previous)
            if not self._persist(host, prepared.availability):
                logger.error(
                    "Rejected workflow decision publication because its "
                    "availability cut could not be persisted"
                )
                return WorkDecisionPublication(False, False, "persistence_failed")
            if producer_transaction is not None:
                rejection = self._commit_producer(
                    host, producer_transaction, previous
                )
                if rejection is not None:
                    return WorkDecisionPublication(False, False, rejection)
            memory_committed = False

            def commit_memory() -> None:
                nonlocal memory_committed
                with host._work_decisions_lock:
                    if memory_committed:
                        return
                    host._work_decisions = dict(prepared.decisions)
                    host._work_decision_source = normalized.source
                    host._work_decision_generation = normalized.generation
                    host._work_decision_unavailable_projects = set(
                        normalized.preserved_projects
                    )
                    host._work_decision_incomplete_projects = set(
                        normalized.incomplete_projects
                    )
                    host._work_decision_incomplete_keys = set(
                        normalized.incomplete_keys
                    )
                    host._work_decision_incomplete_reason = (
                        normalized.incomplete_reason
                    )
                    host._work_decision_snapshot_complete = prepared.complete
                    host._work_decision_updated_at = prepared.updated_at
                    if normalized.shadow_cursor is not None:
                        host._workflow_shadow_scan_cursor = normalized.shadow_cursor
                    memory_committed = True

            def rollback() -> None:
                nonlocal memory_committed
                with host._work_decisions_lock:
                    restoration_error: Exception | None = None
                    try:
                        if not self._persist(host, previous.availability):
                            raise OSError(
                                "prior workflow decision availability was not restored"
                            )
                    except Exception as exc:  # noqa: BLE001 - restore memory too
                        restoration_error = exc
                    self._restore_memory(host, previous)
                    memory_committed = False
                    if restoration_error is not None:
                        raise restoration_error

            publication = WorkDecisionPublication(
                True,
                prepared.changed,
                _commit_memory=commit_memory,
                _rollback=rollback,
            )
            if not defer_memory:
                publication.commit_memory()
            return publication

    def _publication_rejection(
        self,
        host: WorkDecisionProjectionHost,
        normalized: _NormalizedPublication,
    ) -> str | None:
        if normalized.epoch != host._work_decision_publication_epoch:
            return "stale_epoch"
        if normalized.source != self._expected_source(host):
            return "wrong_source"
        if (
            host._work_decision_source == normalized.source
            and normalized.generation <= host._work_decision_generation
        ):
            return "stale_generation"
        return None

    @staticmethod
    def _restore_memory(
        host: WorkDecisionProjectionHost, previous: _ProjectionCut
    ) -> None:
        host._work_decisions = dict(previous.decisions)
        host._work_decision_source = previous.source
        host._work_decision_generation = previous.generation
        host._work_decision_unavailable_projects = set(
            previous.unavailable_projects
        )
        host._work_decision_incomplete_projects = set(
            previous.incomplete_projects
        )
        host._work_decision_incomplete_keys = set(previous.incomplete_keys)
        host._work_decision_incomplete_reason = previous.incomplete_reason
        host._work_decision_snapshot_complete = previous.complete
        host._work_decision_updated_at = previous.updated_at
        host._workflow_shadow_scan_cursor = previous.shadow_cursor

    @staticmethod
    def projection(
        host: WorkDecisionProjectionHost,
        project_id: str | None,
        task_id: str,
    ) -> dict[str, Any] | None:
        project = str(project_id or "legacy")
        identifier = str(task_id or "").strip()
        if not identifier:
            return None
        with host._work_decisions_lock:
            if project in getattr(
                host, "_work_decision_unavailable_projects", set()
            ):
                return None
            if (project, identifier) in getattr(
                host, "_work_decision_incomplete_keys", set()
            ):
                return None
            decision = host._work_decisions.get((project, identifier))
        return project_work_decision(decision) if decision is not None else None

    @staticmethod
    def availability(
        host: WorkDecisionProjectionHost,
        project_id: str | None,
        task_id: str | None = None,
    ) -> str:
        project = str(project_id or "legacy")
        identifier = str(task_id or "").strip()
        with host._work_decisions_lock:
            mode = str(host.config.workflow_engine_mode or "off").lower()
            source = host._work_decision_source
            unavailable = project in getattr(
                host, "_work_decision_unavailable_projects", set()
            )
            incomplete_projects = getattr(
                host, "_work_decision_incomplete_projects", set()
            )
            incomplete_keys = getattr(
                host, "_work_decision_incomplete_keys", set()
            )
            has_decision = (project, identifier) in host._work_decisions
        if mode == "off":
            return "disabled"
        if unavailable:
            return "unavailable"
        if identifier and (project, identifier) in incomplete_keys:
            return "incomplete"
        if identifier and has_decision:
            return "available"
        if project in incomplete_projects:
            return "incomplete"
        if source is None:
            return "pending"
        if identifier:
            return "unavailable"
        return "available"

    @staticmethod
    def snapshot(
        host: WorkDecisionProjectionHost,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        with host._work_decisions_lock:
            incomplete_keys = set(
                getattr(host, "_work_decision_incomplete_keys", set())
            )
            unavailable = set(
                getattr(host, "_work_decision_unavailable_projects", set())
            )
            values = tuple(
                decision
                for key, decision in host._work_decisions.items()
                if key not in incomplete_keys and key[0] not in unavailable
            )
            source = host._work_decision_source
            generation = host._work_decision_generation
            publication_epoch = host._work_decision_publication_epoch
            updated_at = host._work_decision_updated_at
            unavailable_projects = tuple(sorted(unavailable))
            complete = bool(
                getattr(host, "_work_decision_snapshot_complete", False)
            )
            incomplete_projects = tuple(
                sorted(
                    getattr(host, "_work_decision_incomplete_projects", set())
                )
            )
            incomplete_reason = getattr(
                host, "_work_decision_incomplete_reason", None
            )
            configured_mode = str(
                host.config.workflow_engine_mode or "off"
            ).lower()
        availability = WorkDecisionProjectionCoordinator._snapshot_availability(
            configured_mode=configured_mode,
            source=source,
            unavailable_projects=unavailable_projects,
            incomplete_projects=incomplete_projects,
            incomplete_reason=incomplete_reason,
        )
        ordered = tuple(
            sorted(values, key=lambda item: (item.project_id, item.task_id))
        )
        items = [project_work_decision(decision) for decision in ordered]
        alerts = [
            alert
            for decision in ordered
            if (alert := work_decision_alert(decision)) is not None
        ]
        return (
            {
                "schema_version": 1,
                "source": source,
                "snapshot_generation": generation,
                "publication_epoch": publication_epoch,
                "updated_at": updated_at,
                "complete": complete and availability == "ready",
                "availability": availability,
                "unavailable_projects": list(unavailable_projects),
                "incomplete_projects": list(incomplete_projects),
                "incomplete_tasks": [
                    {"project_id": project_id, "task_id": task_id}
                    for project_id, task_id in sorted(incomplete_keys)
                ],
                "incomplete_reason": incomplete_reason,
                "items": items,
            },
            alerts,
        )

    @staticmethod
    def _snapshot_availability(
        *,
        configured_mode: str,
        source: str | None,
        unavailable_projects: tuple[str, ...],
        incomplete_projects: tuple[str, ...],
        incomplete_reason: str | None,
    ) -> str:
        if configured_mode == "off":
            return "disabled"
        if source is None and unavailable_projects:
            return "unavailable"
        if source is None and (incomplete_projects or incomplete_reason):
            return "incomplete"
        if source is None:
            return "pending"
        if unavailable_projects:
            return "partial"
        if incomplete_projects or incomplete_reason:
            return "incomplete"
        return "ready"


WORK_DECISION_PROJECTIONS = WorkDecisionProjectionCoordinator()
