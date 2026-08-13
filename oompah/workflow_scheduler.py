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
from datetime import datetime
from typing import Any

from oompah.work_decision import WorkDecision, decision_scheduling_revision
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
        "decision_revision": cursor.decision_revision,
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
    snapshot_accepted: bool
    decisions_seen: int
    decisions_applied: int
    stale_rejected: int
    jobs_created: int
    jobs_replayed: int
    jobs_superseded: int
    jobs_required: int
    jobs_materialized: int
    schedules_required: int
    schedules_materialized: int
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
    """Turn total decisions into durable jobs and fairly drive their worker.

    One decision activation owns zero or one job. This keeps liveness proof
    atomic: no mixed set of completed, exhausted, and active sibling jobs can
    ambiguously satisfy one decision.
    """

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
        policy_epoch: str = "standalone-v1",
        protected_event_lane_prefixes: Sequence[str] = (),
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
        self._policy_epoch = self._normalize_policy_epoch(policy_epoch)
        self._protected_event_lane_prefixes = tuple(
            sorted(
                {
                    str(prefix or "").strip()
                    for prefix in protected_event_lane_prefixes
                    if str(prefix or "").strip()
                }
            )
        )
        # Publication transactions hold this lock while reconcile re-enters it
        # so scheduler metrics can be restored with the durable job-store cut.
        self._metrics_lock = threading.RLock()
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

    @staticmethod
    def _normalize_policy_epoch(value: object) -> str:
        epoch = str(value or "").strip()
        if not epoch:
            raise ValueError("policy_epoch is required")
        return epoch

    @property
    def policy_epoch(self) -> str:
        with self._metrics_lock:
            return self._policy_epoch

    def configure_policy_epoch(self, policy_epoch: str) -> None:
        """Bind scheduling semantics to one immutable liveness-policy cut."""

        normalized = self._normalize_policy_epoch(policy_epoch)
        with self._metrics_lock:
            self._policy_epoch = normalized

    def decision_revision(self, decision: WorkDecision) -> str:
        """Return the exact semantic revision used by cursors and proofs."""

        return decision_scheduling_revision(
            decision, policy_epoch=self.policy_epoch
        )

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
                reason_code=decision.reason_code,
            )
            for action in decision.durable_jobs
        )

    def accept_snapshot_generation(self, snapshot_generation: int) -> bool:
        """Claim the newest captured generation before evaluating its rows."""

        return self.store.accept_snapshot_generation(snapshot_generation)

    def snapshot_generation_is_current(self, snapshot_generation: int) -> bool:
        return self.store.snapshot_generation_is_current(snapshot_generation)

    @staticmethod
    def _ordered_decisions(
        decisions: Sequence[WorkDecision],
    ) -> list[WorkDecision]:
        normalized = tuple(decisions)
        if any(not isinstance(item, WorkDecision) for item in normalized):
            raise TypeError("decisions must contain WorkDecision values")
        if any(len(item.durable_jobs) > 1 for item in normalized):
            raise ValueError(
                "one WorkDecision scheduler activation may require at most "
                "one durable job"
            )
        by_task: dict[tuple[str, str], WorkDecision] = {}
        for decision in normalized:
            key = (decision.project_id, decision.task_id)
            previous = by_task.get(key)
            if previous is not None and (
                previous.decision_revision != decision.decision_revision
            ):
                raise ValueError(
                    "one snapshot contains conflicting task decisions"
                )
            by_task[key] = decision
        return [by_task[key] for key in sorted(by_task)]

    def _materialized_totals(
        self, decisions: Sequence[WorkDecision]
    ) -> tuple[int, int]:
        schedules = jobs = 0
        for decision in decisions:
            cursor = self.store.schedule_cursor(
                project_id=decision.project_id,
                task_id=decision.task_id,
            )
            if (
                cursor is None
                or cursor.decision_revision
                != self.decision_revision(decision)
                or not cursor.materialized
            ):
                continue
            specs = self._specs(decision, cursor)
            exact_materialized = self.store.schedule_specs_materialized(
                project_id=decision.project_id,
                task_id=decision.task_id,
                decision_revision=self.decision_revision(decision),
                job_generation=cursor.job_generation,
                idempotency_keys=tuple(
                    spec.idempotency_key for spec in specs
                ),
            )
            substitute_materialized = bool(
                not exact_materialized
                and len(specs) == 1
                and self._protected_event_lane_prefixes
                and self.store.schedule_substitute_materialized(
                    project_id=decision.project_id,
                    task_id=decision.task_id,
                    decision_revision=self.decision_revision(decision),
                    job_generation=cursor.job_generation,
                    action=specs[0].action,
                    scheduling_lanes=tuple(
                        f"{prefix}{specs[0].action}"
                        for prefix in self._protected_event_lane_prefixes
                    ),
                )
            )
            if not exact_materialized and not substitute_materialized:
                continue
            schedules += 1
            jobs += len(specs)
        return schedules, jobs

    @staticmethod
    def _rejected_result(
        generation: int,
        ordered: Sequence[WorkDecision],
        *,
        truncated: bool,
    ) -> WorkflowReconcileResult:
        return WorkflowReconcileResult(
            snapshot_generation=generation,
            snapshot_accepted=False,
            decisions_seen=0,
            decisions_applied=0,
            stale_rejected=len(ordered),
            jobs_created=0,
            jobs_replayed=0,
            jobs_superseded=0,
            jobs_required=sum(
                len(decision.durable_jobs) for decision in ordered
            ),
            jobs_materialized=0,
            schedules_required=len(ordered),
            schedules_materialized=0,
            truncated=truncated,
        )

    def rejected_snapshot(
        self,
        snapshot_generation: int,
        decisions: Sequence[WorkDecision] = (),
    ) -> WorkflowReconcileResult:
        """Describe a stale pass without mutating scheduler metrics or work."""

        if (
            isinstance(snapshot_generation, bool)
            or int(snapshot_generation) < 1
        ):
            raise ValueError("snapshot_generation must be a positive integer")
        ordered = self._ordered_decisions(decisions)
        return self._rejected_result(
            int(snapshot_generation),
            ordered,
            truncated=len(ordered) > self.decision_limit,
        )

    def reconcile(
        self,
        decisions: Sequence[WorkDecision],
        *,
        snapshot_generation: int | None = None,
        authoritative_project_ids: Sequence[str] | None = None,
        expected_identities: Sequence[tuple[str, str]] | None = None,
        lifecycle_final_tasks: Sequence[tuple[str, str, str]] = (),
    ) -> WorkflowReconcileResult:
        """Claim and boundedly materialize one globally fenced snapshot."""

        generation = (
            self.begin_scan() if snapshot_generation is None else snapshot_generation
        )
        if isinstance(generation, bool) or int(generation) < 1:
            raise ValueError("snapshot_generation must be a positive integer")
        generation = int(generation)
        ordered = self._ordered_decisions(decisions)
        membership = (
            tuple(expected_identities)
            if expected_identities is not None
            else tuple((item.project_id, item.task_id) for item in ordered)
        )
        authoritative = (
            tuple(authoritative_project_ids)
            if authoritative_project_ids is not None
            else tuple(sorted({project_id for project_id, _task_id in membership}))
        )
        if not self.accept_snapshot_generation(generation):
            return self._rejected_result(
                generation,
                ordered,
                truncated=len(ordered) > self.decision_limit,
            )
        result = self.reconcile_accepted(
            ordered,
            snapshot_generation=generation,
            record_metrics=False,
            authoritative_project_ids=authoritative,
            expected_identities=membership,
            lifecycle_final_tasks=lifecycle_final_tasks,
        )
        if not result.snapshot_accepted:
            return result
        published, _ = self.store.publish_snapshot_generation(
            generation,
            lambda: None,
        )
        if not published:
            return self._rejected_result(
                generation,
                ordered,
                truncated=result.truncated,
            )
        self.record_reconcile_metrics(result)
        return result

    def reconcile_accepted(
        self,
        decisions: Sequence[WorkDecision],
        *,
        snapshot_generation: int,
        record_metrics: bool = True,
        authoritative_project_ids: Sequence[str] | None = None,
        expected_identities: Sequence[tuple[str, str]] | None = None,
        lifecycle_final_tasks: Sequence[tuple[str, str, str]] = (),
    ) -> WorkflowReconcileResult:
        """Materialize a generation already claimed before evaluation."""

        if isinstance(snapshot_generation, bool) or int(snapshot_generation) < 1:
            raise ValueError("snapshot_generation must be a positive integer")
        generation = int(snapshot_generation)
        all_decisions = self._ordered_decisions(decisions)
        bounded_window = len(all_decisions) > self.decision_limit
        if not self.snapshot_generation_is_current(generation):
            return self._rejected_result(
                generation, all_decisions, truncated=bounded_window
            )
        if (authoritative_project_ids is None) != (expected_identities is None):
            raise ValueError(
                "authoritative_project_ids and expected_identities must be provided together"
            )
        final_tasks = tuple(
            sorted(
                {
                    (
                        str(project_id).strip(),
                        str(task_id).strip(),
                        str(status).strip(),
                    )
                    for project_id, task_id, status in lifecycle_final_tasks
                }
            )
        )
        if any(not all(item) for item in final_tasks):
            raise ValueError("lifecycle_final_tasks must contain non-empty values")
        membership_superseded = 0
        if authoritative_project_ids is not None and expected_identities is not None:
            expected_identity_set = set(expected_identities)
            membership = self.store.reconcile_snapshot_membership(
                snapshot_generation=generation,
                authoritative_project_ids=authoritative_project_ids,
                expected_identities=expected_identities,
                evaluated_identities=tuple(
                    (item.project_id, item.task_id)
                    for item in all_decisions
                    if (item.project_id, item.task_id) in expected_identity_set
                ),
            )
            if not membership.accepted:
                return self._rejected_result(
                    generation, all_decisions, truncated=bounded_window
                )
            membership_superseded = membership.jobs_superseded
        selected = all_decisions
        if bounded_window:
            offset = self.store.allocate_decision_window(
                total=len(all_decisions),
                limit=self.decision_limit,
                snapshot_generation=generation,
            )
            if offset is None:
                return self._rejected_result(
                    generation, all_decisions, truncated=True
                )
            selected = (
                all_decisions[offset:] + all_decisions[:offset]
            )[: self.decision_limit]
        applied = stale = created = replayed = 0
        superseded = membership_superseded
        activated: dict[tuple[str, str], WorkflowScheduleCursor] = {}
        # Stage every evaluated semantic cursor before publication. Job creation
        # remains bounded below, but an unselected changed task's older job can
        # no longer pass the generic claim fence in the interim.
        with self.store.scheduling_batch():
            for project_id, task_id, status in final_tasks:
                self.store.record_lifecycle_final_authority(
                    project_id=project_id,
                    task_id=task_id,
                    status=status,
                    snapshot_generation=generation,
                )
            for decision in all_decisions:
                cursor = self.store.activate_schedule(
                    project_id=decision.project_id,
                    task_id=decision.task_id,
                    decision_revision=self.decision_revision(decision),
                    snapshot_generation=generation,
                    next_reassessment_at=(
                        datetime.fromisoformat(
                            decision.next_reassessment_at.replace("Z", "+00:00")
                        ).timestamp()
                        if decision.next_reassessment_at is not None
                        else None
                    ),
                )
                if not cursor.accepted:
                    stale += 1
                    continue
                activated[(decision.project_id, decision.task_id)] = cursor
            for decision in selected:
                cursor = activated.get((decision.project_id, decision.task_id))
                if cursor is None:
                    continue
                specs = self._specs(decision, cursor)
                write = self.store.reconcile_schedule(
                    project_id=decision.project_id,
                    task_id=decision.task_id,
                    snapshot_generation=generation,
                    job_generation=cursor.job_generation,
                    specs=specs,
                    record_authority_cut=(
                        decision.reason_code
                        not in {
                            "retry.exhausted",
                            "controller.evaluation_failed",
                            "evidence.conflicting_task_facts",
                        }
                    ),
                    authority_kind=(
                        "managed_decision" if specs else "managed_zero_job"
                    ),
                )
                if not write.accepted:
                    stale += 1
                    continue
                applied += 1
                created += write.created
                replayed += write.replayed
                superseded += write.superseded
        if not self.snapshot_generation_is_current(generation):
            return self._rejected_result(
                generation, all_decisions, truncated=bounded_window
            )
        schedules_materialized, jobs_materialized = (
            self._materialized_totals(all_decisions)
        )
        if not self.snapshot_generation_is_current(generation):
            return self._rejected_result(
                generation, all_decisions, truncated=bounded_window
            )
        jobs_required = sum(
            len(decision.durable_jobs) for decision in all_decisions
        )
        truncated = (
            schedules_materialized < len(all_decisions)
            or jobs_materialized < jobs_required
        )
        result = WorkflowReconcileResult(
            snapshot_generation=generation,
            snapshot_accepted=True,
            decisions_seen=len(selected),
            decisions_applied=applied,
            stale_rejected=stale,
            jobs_created=created,
            jobs_replayed=replayed,
            jobs_superseded=superseded,
            jobs_required=jobs_required,
            jobs_materialized=jobs_materialized,
            schedules_required=len(all_decisions),
            schedules_materialized=schedules_materialized,
            truncated=truncated,
        )
        if record_metrics:
            self.record_reconcile_metrics(result)
        return result

    def record_reconcile_metrics(self, result: WorkflowReconcileResult) -> None:
        """Commit counters only after the caller's authority publish succeeds."""

        if not result.snapshot_accepted:
            return
        with self._metrics_lock:
            self._reconciled_decisions += result.decisions_applied
            self._stale_decisions += result.stale_rejected
            self._last_error = None

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
