"""Durable event-to-decision-to-job scheduling.

Events are latency hints only.  Every scheduling pass receives a generation
allocated by the durable job store, and per-task cursors reject an older pass
that finishes after a newer one.  The job ledger remains the sole execution
authority; process-local events and locks only coalesce work.
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import threading
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from oompah.work_decision import WorkDecision
from oompah.workflow_jobs import (
    WorkflowJobSpec,
    WorkflowJobStore,
    WorkflowScheduleCursor,
)
from oompah.workflow_worker import (
    DurableWorkflowWorker,
    WorkflowRunDisposition,
    WorkflowRunResult,
)


DEFAULT_DECISION_LIMIT = 100
DEFAULT_JOB_BATCH_SIZE = 100
MAX_SCHEDULER_LIMIT = 1000
MAX_SCHEDULER_CONCURRENCY = 64


def _bounded(value: int, name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")
    normalized = int(value)
    if normalized < 1 or normalized > MAX_SCHEDULER_LIMIT:
        raise ValueError(f"{name} must be between 1 and {MAX_SCHEDULER_LIMIT}")
    return normalized


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _job_key(
    decision: WorkDecision,
    cursor: WorkflowScheduleCursor,
    action: str,
    *,
    priority: int,
    max_attempts: int,
) -> str:
    payload = {
        "project_id": decision.project_id,
        "task_id": decision.task_id,
        "job_generation": cursor.job_generation,
        "decision_revision": decision.decision_revision,
        "evidence_revision": decision.evidence_revision,
        "action": action,
        "priority": priority,
        "max_attempts": max_attempts,
    }
    digest = hashlib.sha256(_canonical_json(payload).encode()).hexdigest()
    return f"workflow-decision:{digest}"


@dataclass(frozen=True, slots=True)
class WorkflowReconcileResult:
    snapshot_generation: int
    decisions_seen: int
    decisions_applied: int
    stale_rejected: int
    jobs_created: int
    jobs_replayed: int
    jobs_superseded: int
    truncated: bool


@dataclass(frozen=True, slots=True)
class WorkflowRunBatch:
    requested: int
    attempted: int
    idle: int
    dispositions: Mapping[str, int]
    results: tuple[WorkflowRunResult, ...]


DecisionSource = Callable[
    [], Sequence[WorkDecision] | Awaitable[Sequence[WorkDecision]]
]


class WorkflowJobScheduler:
    """Turn total decisions into durable jobs and fairly drive their worker."""

    def __init__(
        self,
        *,
        store: WorkflowJobStore,
        worker: DurableWorkflowWorker | None = None,
        decision_limit: int = DEFAULT_DECISION_LIMIT,
        job_batch_size: int = DEFAULT_JOB_BATCH_SIZE,
        concurrency: int = 4,
        default_priority: int = 100,
        max_attempts: int = 5,
    ) -> None:
        self.store = store
        self.worker = worker
        self.decision_limit = _bounded(decision_limit, "decision_limit")
        self.job_batch_size = _bounded(job_batch_size, "job_batch_size")
        self.concurrency = _bounded(concurrency, "concurrency")
        if self.concurrency > MAX_SCHEDULER_CONCURRENCY:
            raise ValueError(f"concurrency cannot exceed {MAX_SCHEDULER_CONCURRENCY}")
        if isinstance(default_priority, bool):
            raise ValueError("default_priority must be an integer")
        self.default_priority = int(default_priority)
        self.max_attempts = _bounded(max_attempts, "max_attempts")
        self._metrics_lock = threading.Lock()
        self._wakeup = asyncio.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._run_lock = asyncio.Lock()
        self._accepting = True
        self._wakeups = 0
        self._coalesced_wakeups = 0
        self._wake_pending = False
        self._full_syncs = 0
        self._reconciled_decisions = 0
        self._stale_decisions = 0
        self._last_error: str | None = None

    @property
    def accepting(self) -> bool:
        return self._accepting

    def begin_scan(self) -> int:
        """Allocate the durable fence before fetching a possibly slow snapshot."""

        return self.store.allocate_snapshot_generation()

    def wake(self, reason: str = "event") -> None:
        """Coalesce a latency hint without making it correctness authority."""

        if not str(reason or "").strip():
            raise ValueError("wakeup reason is required")
        with self._metrics_lock:
            self._wakeups += 1
            if self._wake_pending:
                self._coalesced_wakeups += 1
            self._wake_pending = True
        loop = self._loop
        if loop is not None and loop.is_running():
            loop.call_soon_threadsafe(self._wakeup.set)
        else:
            self._wakeup.set()

    def _specs(
        self,
        decision: WorkDecision,
        cursor: WorkflowScheduleCursor,
    ) -> tuple[WorkflowJobSpec, ...]:
        return tuple(
            WorkflowJobSpec(
                project_id=decision.project_id,
                task_id=decision.task_id,
                generation=cursor.job_generation,
                action=action,
                idempotency_key=_job_key(
                    decision,
                    cursor,
                    action,
                    priority=self.default_priority,
                    max_attempts=self.max_attempts,
                ),
                expected_evidence_revision=decision.evidence_revision,
                priority=self.default_priority,
                max_attempts=self.max_attempts,
            )
            for action in decision.durable_jobs
        )

    def reconcile(
        self,
        decisions: Sequence[WorkDecision],
        *,
        snapshot_generation: int | None = None,
    ) -> WorkflowReconcileResult:
        """Boundedly materialize one snapshot with durable stale-scan fencing."""

        generation = (
            self.begin_scan() if snapshot_generation is None else snapshot_generation
        )
        if isinstance(generation, bool) or int(generation) < 1:
            raise ValueError("snapshot_generation must be a positive integer")
        generation = int(generation)
        normalized = tuple(decisions)
        if any(not isinstance(item, WorkDecision) for item in normalized):
            raise TypeError("decisions must contain WorkDecision values")
        by_task: dict[tuple[str, str], WorkDecision] = {}
        for decision in normalized:
            key = (decision.project_id, decision.task_id)
            previous = by_task.get(key)
            if previous is not None and (
                previous.decision_revision != decision.decision_revision
            ):
                raise ValueError("one snapshot contains conflicting task decisions")
            by_task[key] = decision
        ordered = [by_task[key] for key in sorted(by_task)]
        truncated = len(ordered) > self.decision_limit
        if truncated:
            offset = self.store.allocate_decision_window(
                total=len(ordered), limit=self.decision_limit
            )
            ordered = (ordered[offset:] + ordered[:offset])[: self.decision_limit]
        applied = stale = created = replayed = superseded = 0
        if ordered:
            with self.store.scheduling_batch():
                for decision in ordered:
                    cursor = self.store.activate_schedule(
                        project_id=decision.project_id,
                        task_id=decision.task_id,
                        decision_revision=decision.decision_revision,
                        snapshot_generation=generation,
                    )
                    if not cursor.accepted:
                        stale += 1
                        continue
                    write = self.store.reconcile_schedule(
                        project_id=decision.project_id,
                        task_id=decision.task_id,
                        snapshot_generation=generation,
                        job_generation=cursor.job_generation,
                        specs=self._specs(decision, cursor),
                    )
                    if not write.accepted:
                        stale += 1
                        continue
                    applied += 1
                    created += write.created
                    replayed += write.replayed
                    superseded += write.superseded
        with self._metrics_lock:
            self._reconciled_decisions += applied
            self._stale_decisions += stale
            self._last_error = None
        return WorkflowReconcileResult(
            snapshot_generation=generation,
            decisions_seen=len(ordered),
            decisions_applied=applied,
            stale_rejected=stale,
            jobs_created=created,
            jobs_replayed=replayed,
            jobs_superseded=superseded,
            truncated=truncated,
        )

    async def run_due(self, *, limit: int | None = None) -> WorkflowRunBatch:
        """Run a bounded fair batch; durable claims serialize each task."""

        requested = self.job_batch_size if limit is None else _bounded(limit, "limit")
        if self.worker is None or not self._accepting:
            return WorkflowRunBatch(requested, 0, 0, {}, ())
        results: list[WorkflowRunResult] = []
        attempted = 0
        async with self._run_lock:
            while attempted < requested and self._accepting:
                width = min(self.concurrency, requested - attempted)
                batch = await asyncio.gather(
                    *(
                        self.worker.run_once(fair_across_projects=True)
                        for _ in range(width)
                    )
                )
                results.extend(batch)
                batch_attempted = sum(
                    result.disposition
                    not in {
                        WorkflowRunDisposition.IDLE,
                        WorkflowRunDisposition.STOPPED,
                    }
                    for result in batch
                )
                attempted += batch_attempted
                if not batch_attempted or any(
                    result.disposition is WorkflowRunDisposition.STOPPED
                    for result in batch
                ):
                    break
        dispositions: dict[str, int] = {}
        for result in results:
            key = result.disposition.value
            dispositions[key] = dispositions.get(key, 0) + 1
        idle = dispositions.get(WorkflowRunDisposition.IDLE.value, 0)
        return WorkflowRunBatch(
            requested,
            attempted,
            idle,
            dict(sorted(dispositions.items())),
            tuple(results),
        )

    def recover_startup(self, *, abandoned: bool = False) -> dict[str, int]:
        """Recover durable ownership after an exclusive scheduler restart."""

        expired = self.store.recover_expired(limit=self.job_batch_size)
        abandoned_count = (
            self.store.recover_abandoned(limit=self.job_batch_size) if abandoned else 0
        )
        return {"expired": expired, "abandoned": abandoned_count}

    async def _read_decisions(self, source: DecisionSource) -> Sequence[WorkDecision]:
        value = source()
        if inspect.isawaitable(value):
            value = await value
        if not isinstance(value, Sequence):
            raise TypeError("decision source must return a sequence")
        return value

    async def serve(
        self,
        source: DecisionSource,
        *,
        full_sync_interval_seconds: float,
        max_cycles: int | None = None,
    ) -> None:
        """Reconcile immediately, on wakeups, and after every bounded timeout."""

        if full_sync_interval_seconds <= 0:
            raise ValueError("full_sync_interval_seconds must be positive")
        if max_cycles is not None and max_cycles < 1:
            raise ValueError("max_cycles must be positive")
        self._loop = asyncio.get_running_loop()
        cycles = 0
        while self._accepting:
            with self._metrics_lock:
                self._wakeup.clear()
                self._wake_pending = False
            generation = self.begin_scan()
            try:
                decisions = await self._read_decisions(source)
                self.reconcile(decisions, snapshot_generation=generation)
                await self.run_due()
                with self._metrics_lock:
                    self._full_syncs += 1
                    self._last_error = None
            except Exception as exc:  # noqa: BLE001 - durable loop retries next wake
                with self._metrics_lock:
                    self._last_error = type(exc).__name__
            cycles += 1
            if max_cycles is not None and cycles >= max_cycles:
                return
            try:
                await asyncio.wait_for(
                    self._wakeup.wait(), timeout=full_sync_interval_seconds
                )
            except TimeoutError:
                pass

    async def drain(self, *, timeout_seconds: float | None = None) -> bool:
        """Stop new cycles/claims and let an active durable worker finish safely."""

        self._accepting = False
        self._wakeup.set()
        if self.worker is None:
            return True
        return await self.worker.drain(timeout_seconds=timeout_seconds)

    def health_snapshot(self) -> dict[str, Any]:
        with self._metrics_lock:
            scheduler = {
                "accepting": self._accepting,
                "wakeups": self._wakeups,
                "coalesced_wakeups": self._coalesced_wakeups,
                "full_syncs": self._full_syncs,
                "reconciled_decisions": self._reconciled_decisions,
                "stale_decisions": self._stale_decisions,
                "last_error": self._last_error,
            }
        scheduler["active_workers"] = (
            self.worker.active_count if self.worker is not None else 0
        )
        return {"scheduler": scheduler, "jobs": self.store.health_snapshot()}
