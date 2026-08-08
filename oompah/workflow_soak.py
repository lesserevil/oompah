"""Deterministic qualification workload for the durable workflow engine.

The soak drives production ``WorkDecision`` serialization, bounded durable
scheduling, fair SQLite job claims, retry fencing, restart recovery, and the
operator-alert boundary.  External providers are intentionally represented by
deterministic outcomes so the bounded profile can run in CI without network or
model dependencies while the larger profile can be repeated by operators.
"""

from __future__ import annotations

import hashlib
import json
import os
import tracemalloc
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from oompah.work_decision import PermittedAction, UnmetPrerequisite, WorkDecision
from oompah.work_decision_projection import (
    operator_actionable_alerts,
    project_work_decision,
    work_decision_alert,
)
from oompah.workflow_contract import TaskDisposition, WorkflowOwner
from oompah.workflow_jobs import (
    WorkflowFailureCategory,
    WorkflowJobState,
    WorkflowJobStore,
)
from oompah.workflow_reasons import AlertSeverity
from oompah.workflow_scheduler import MAX_SCHEDULER_LIMIT, WorkflowJobScheduler


_ACTION_SEQUENCE = (
    "implementation_recovery",
    "review_merge",
    "terminal_audit",
    "integration_attempt",
    "branch_prune",
)
_TERMINAL = "terminal"
_ESCALATED = "escalated"
_PENDING = "pending"


class WorkflowSoakError(RuntimeError):
    """Raised when a qualification invariant does not hold."""


class DeterministicClock:
    """Small controllable clock used by the production durable store."""

    def __init__(self, now: float = 1_000.0) -> None:
        self.now = float(now)

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float = 1.0) -> None:
        self.now += float(seconds)


@dataclass(frozen=True, slots=True)
class WorkflowSoakProfile:
    """Bounded workload and objective resource limits."""

    name: str
    task_count: int
    project_count: int
    decision_limit: int
    batch_size: int
    max_cycles: int
    max_attempts: int = 4
    sqlite_base_bytes: int = 524_288
    sqlite_bytes_per_task: int = 65_536
    memory_base_bytes: int = 33_554_432
    memory_bytes_per_task: int = 524_288

    def __post_init__(self) -> None:
        if self.task_count < 100:
            raise ValueError("workflow soak requires at least 100 tasks")
        if self.project_count < 2 or self.project_count > self.task_count // 10:
            raise ValueError("project_count must be between 2 and task_count / 10")
        for value, label in (
            (self.decision_limit, "decision_limit"),
            (self.batch_size, "batch_size"),
            (self.max_cycles, "max_cycles"),
            (self.max_attempts, "max_attempts"),
        ):
            if isinstance(value, bool) or int(value) < 1:
                raise ValueError(f"{label} must be a positive integer")
        if self.decision_limit > MAX_SCHEDULER_LIMIT:
            raise ValueError(
                f"decision_limit cannot exceed {MAX_SCHEDULER_LIMIT}"
            )
        if self.batch_size > MAX_SCHEDULER_LIMIT:
            raise ValueError(f"batch_size cannot exceed {MAX_SCHEDULER_LIMIT}")
        for value, label in (
            (self.sqlite_base_bytes, "sqlite_base_bytes"),
            (self.sqlite_bytes_per_task, "sqlite_bytes_per_task"),
            (self.memory_base_bytes, "memory_base_bytes"),
            (self.memory_bytes_per_task, "memory_bytes_per_task"),
        ):
            if isinstance(value, bool) or int(value) < 1:
                raise ValueError(f"{label} must be a positive integer")

    @property
    def max_sqlite_bytes(self) -> int:
        return self.sqlite_base_bytes + self.sqlite_bytes_per_task * self.task_count

    @property
    def max_peak_memory_bytes(self) -> int:
        return self.memory_base_bytes + self.memory_bytes_per_task * self.task_count

    @property
    def max_task_latency_seconds(self) -> int:
        return self.task_count * (self.max_attempts + 2)

    @classmethod
    def named(cls, name: str) -> "WorkflowSoakProfile":
        normalized = str(name or "").strip().lower()
        if normalized == "ci":
            return cls(
                name="ci",
                task_count=120,
                project_count=4,
                decision_limit=37,
                batch_size=32,
                max_cycles=100,
            )
        if normalized == "operator":
            return cls(
                name="operator",
                task_count=1_000,
                project_count=8,
                decision_limit=100,
                batch_size=64,
                max_cycles=500,
            )
        raise ValueError("workflow soak profile must be 'ci' or 'operator'")

    @classmethod
    def from_env(cls, name: str) -> "WorkflowSoakProfile":
        """Load optional operator tuning from the documented ``.env`` keys."""

        base = cls.named(name)
        values = asdict(base)
        keys = {
            "task_count": "OOMPAH_WORKFLOW_SOAK_TASK_COUNT",
            "project_count": "OOMPAH_WORKFLOW_SOAK_PROJECT_COUNT",
            "decision_limit": "OOMPAH_WORKFLOW_SOAK_DECISION_LIMIT",
            "batch_size": "OOMPAH_WORKFLOW_SOAK_BATCH_SIZE",
            "max_cycles": "OOMPAH_WORKFLOW_SOAK_MAX_CYCLES",
            "sqlite_bytes_per_task": "OOMPAH_WORKFLOW_SOAK_SQLITE_BYTES_PER_TASK",
            "memory_bytes_per_task": "OOMPAH_WORKFLOW_SOAK_MEMORY_BYTES_PER_TASK",
        }
        for field, key in keys.items():
            raw = os.environ.get(key)
            if raw is None or not raw.strip():
                continue
            try:
                values[field] = int(raw)
            except ValueError as exc:
                raise ValueError(f"{key} must be an integer") from exc
        return cls(**values)


@dataclass(frozen=True, slots=True)
class SoakTaskSpec:
    project_id: str
    task_id: str
    ordinal: int
    action: str
    issue_type: str
    parent_id: str | None
    dependencies: tuple[str, ...]
    transient_failures: int = 0
    deliberately_unrecoverable: bool = False


@dataclass(slots=True)
class _TaskRuntime:
    spec: SoakTaskSpec
    state: str = _PENDING
    failure_count: int = 0
    completed_at: float | None = None


@dataclass(frozen=True, slots=True)
class WorkflowSoakReport:
    profile: str
    task_count: int
    project_count: int
    terminal_recoverable_tasks: int
    expected_escalations: int
    unexplained_tasks: tuple[str, ...]
    cycles: int
    reconcile_passes: int
    attempts: int
    transient_failures: int
    restart_recoveries: int
    max_queue_age_seconds: float
    max_task_latency_seconds: float
    contended_fairness_repeats: int
    max_project_claim_skew: int
    projection_checks: int
    projection_mismatches: int
    actionable_alerts: int
    sqlite_bytes: int
    sqlite_limit_bytes: int
    peak_memory_bytes: int
    peak_memory_limit_bytes: int
    action_counts: dict[str, int]
    issue_type_counts: dict[str, int]
    cross_project_dependencies: int
    nested_epics: int
    branch_prunes: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _digest(value: object) -> str:
    serialized = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def build_workload(profile: WorkflowSoakProfile) -> tuple[SoakTaskSpec, ...]:
    """Build a stable, acyclic workload with mixed workflow ownership lanes."""

    per_project, remainder = divmod(profile.task_count, profile.project_count)
    tasks: list[SoakTaskSpec] = []
    ordinal = 0
    project_leaves: list[list[str]] = []
    for project_index in range(profile.project_count):
        project_id = f"soak-project-{project_index + 1:02d}"
        local_count = per_project + (1 if project_index < remainder else 0)
        leaf_count = local_count - 2
        leaves = [
            f"SOAK-{project_index + 1:02d}-{index + 1:04d}"
            for index in range(leaf_count)
        ]
        nested_id = f"SOAK-{project_index + 1:02d}-NESTED"
        root_id = f"SOAK-{project_index + 1:02d}-EPIC"
        project_leaves.append(leaves)
        split = max(4, leaf_count // 2)
        for leaf_index, task_id in enumerate(leaves):
            dependencies: list[str] = []
            if project_index and leaf_index == 6:
                dependencies.append(project_leaves[project_index - 1][4])
            parent_id = None
            if leaf_index >= 3:
                parent_id = nested_id if leaf_index < split else root_id
            deliberately_unrecoverable = project_index == 0 and leaf_index == 0
            transient_failures = (
                2 if ordinal % 41 == 0 else 1 if ordinal % 13 == 0 else 0
            )
            if deliberately_unrecoverable:
                transient_failures = 0
            tasks.append(
                SoakTaskSpec(
                    project_id=project_id,
                    task_id=task_id,
                    ordinal=ordinal,
                    action=_ACTION_SEQUENCE[ordinal % len(_ACTION_SEQUENCE)],
                    issue_type="task",
                    parent_id=parent_id,
                    dependencies=tuple(dependencies),
                    transient_failures=transient_failures,
                    deliberately_unrecoverable=deliberately_unrecoverable,
                )
            )
            ordinal += 1
        nested_children = tuple(leaves[3:split])
        tasks.append(
            SoakTaskSpec(
                project_id=project_id,
                task_id=nested_id,
                ordinal=ordinal,
                action="rollup_reconciliation",
                issue_type="epic",
                parent_id=root_id,
                dependencies=nested_children,
            )
        )
        ordinal += 1
        root_children = (nested_id, *leaves[split:])
        tasks.append(
            SoakTaskSpec(
                project_id=project_id,
                task_id=root_id,
                ordinal=ordinal,
                action="rollup_reconciliation",
                issue_type="epic",
                parent_id=None,
                dependencies=tuple(root_children),
            )
        )
        ordinal += 1
    if len(tasks) != profile.task_count:
        raise AssertionError("workflow soak builder did not preserve task_count")
    return tuple(tasks)


def _status_and_owner(
    task: SoakTaskSpec,
) -> tuple[str, str, WorkflowOwner, PermittedAction, AlertSeverity]:
    if task.action == "review_merge":
        return (
            "In Review",
            "review.ready_to_merge",
            WorkflowOwner.REVIEW_MONITOR,
            PermittedAction.MERGE_REVIEW,
            AlertSeverity.NONE,
        )
    if task.action == "terminal_audit":
        return (
            "In Validation",
            "validation.retry_scheduled",
            WorkflowOwner.AUDITOR,
            PermittedAction.RETRY_AUDIT,
            AlertSeverity.INFO,
        )
    if task.action == "integration_attempt":
        return (
            "Ready to Integrate",
            "integration.retry_scheduled",
            WorkflowOwner.INTEGRATOR,
            PermittedAction.CLAIM_INTEGRATION,
            AlertSeverity.INFO,
        )
    if task.action == "rollup_reconciliation":
        return (
            "Decomposed",
            "rollup.children_complete",
            WorkflowOwner.ROLLUP,
            PermittedAction.ROLLUP_CHILDREN,
            AlertSeverity.NONE,
        )
    return (
        "In Progress",
        "implementation.recovery_scheduled",
        WorkflowOwner.IMPLEMENTER,
        PermittedAction.RECOVER_IMPLEMENTATION,
        AlertSeverity.INFO,
    )


def _decision_for(
    runtime: _TaskRuntime,
    all_tasks: dict[str, _TaskRuntime],
) -> WorkDecision | None:
    if runtime.state == _TERMINAL:
        return None
    task = runtime.spec
    if runtime.state == _ESCALATED:
        return WorkDecision(
            project_id=task.project_id,
            task_id=task.task_id,
            status="Needs Human",
            disposition=TaskDisposition.ACTION_REQUIRED,
            reason_code="retry.exhausted",
            responsible_owner=WorkflowOwner.OPERATOR,
            unmet_prerequisites=(
                UnmetPrerequisite(
                    "retry.exhausted",
                    task.task_id,
                    str(runtime.failure_count),
                ),
            ),
            evidence_revision=_digest(
                {
                    "task": task.task_id,
                    "state": runtime.state,
                    "failures": runtime.failure_count,
                }
            ),
            next_reassessment_at=None,
            permitted_actions=(PermittedAction.RESOLVE_OPERATOR_ACTION,),
            action_required=True,
            alert_level=AlertSeverity.WARNING,
        )
    incomplete = tuple(
        dependency
        for dependency in task.dependencies
        if all_tasks[dependency].state != _TERMINAL
    )
    evidence = _digest(
        {
            "task": task.task_id,
            "state": runtime.state,
            "dependencies": [
                (dependency, all_tasks[dependency].state)
                for dependency in task.dependencies
            ],
        }
    )
    if incomplete:
        epic = task.issue_type == "epic"
        return WorkDecision(
            project_id=task.project_id,
            task_id=task.task_id,
            status="Decomposed" if epic else "Open",
            disposition=TaskDisposition.BLOCKED,
            reason_code=(
                "rollup.waiting_children" if epic else "dispatch.dependencies_blocked"
            ),
            responsible_owner=(
                WorkflowOwner.ROLLUP if epic else WorkflowOwner.DISPATCHER
            ),
            unmet_prerequisites=tuple(
                UnmetPrerequisite("dependency.incomplete", dependency)
                for dependency in incomplete
            ),
            evidence_revision=evidence,
            next_reassessment_at=None,
            permitted_actions=(
                (PermittedAction.ROLLUP_CHILDREN,)
                if epic
                else (PermittedAction.WAIT_DEPENDENCY,)
            ),
            action_required=False,
            alert_level=AlertSeverity.NONE if epic else AlertSeverity.INFO,
        )
    status, reason, owner, action, severity = _status_and_owner(task)
    return WorkDecision(
        project_id=task.project_id,
        task_id=task.task_id,
        status=status,
        disposition=(
            TaskDisposition.RETRY_SCHEDULED
            if severity is AlertSeverity.INFO
            else TaskDisposition.RUNNABLE
        ),
        reason_code=reason,
        responsible_owner=owner,
        unmet_prerequisites=(),
        evidence_revision=evidence,
        next_reassessment_at=None,
        permitted_actions=(action,),
        action_required=False,
        alert_level=severity,
        durable_jobs=(task.action,),
    )


def _database_size(path: Path) -> int:
    return sum(
        candidate.stat().st_size
        for candidate in (path, Path(f"{path}-wal"), Path(f"{path}-shm"))
        if candidate.exists()
    )


def _claimable_projects(health: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    for project_id, states in health["jobs"]["projects"].items():
        if int(states.get("queued", 0)) or int(states.get("retry_wait", 0)):
            result.add(project_id)
    return result


def run_workflow_soak(
    profile: WorkflowSoakProfile,
    *,
    database_path: str | os.PathLike[str],
) -> WorkflowSoakReport:
    """Run one qualification workload and fail closed on any violated bound."""

    path = Path(database_path)
    if path.exists():
        raise ValueError(f"workflow soak database already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    specs = build_workload(profile)
    tasks = {spec.task_id: _TaskRuntime(spec) for spec in specs}
    projects = tuple(sorted({spec.project_id for spec in specs}))
    clock = DeterministicClock()
    started_at = clock()
    store: WorkflowJobStore | None = None
    scheduler: WorkflowJobScheduler | None = None
    already_tracing = tracemalloc.is_tracing()
    if not already_tracing:
        tracemalloc.start()
    baseline_memory, _ = tracemalloc.get_traced_memory()
    cycles = reconcile_passes = attempts = transient_failures = 0
    restart_recoveries = projection_checks = projection_mismatches = 0
    contended_fairness_repeats = 0
    max_queue_age = 0.0
    last_claim_project: str | None = None
    claim_counts: Counter[str] = Counter()
    restart_performed = False
    restart_due_after = max(1, profile.task_count // 3)
    try:
        store = WorkflowJobStore(str(path), clock=clock)
        scheduler = WorkflowJobScheduler(
            store=store,
            decision_limit=profile.decision_limit,
            job_batch_size=profile.batch_size,
            max_attempts=profile.max_attempts,
        )
        while cycles < profile.max_cycles:
            cycles += 1
            decisions = tuple(
                decision
                for runtime in tasks.values()
                if (decision := _decision_for(runtime, tasks)) is not None
            )
            for decision in decisions:
                projection = project_work_decision(decision)
                projection_checks += 1
                if any(
                    (
                        projection.get("project_id") != decision.project_id,
                        projection.get("task_id") != decision.task_id,
                        projection.get("reason_code") != decision.reason_code,
                        projection.get("owner") != decision.responsible_owner.value,
                        projection.get("decision_revision") != decision.decision_revision,
                        bool(projection.get("global_alert")) != decision.action_required,
                    )
                ):
                    projection_mismatches += 1
            result = scheduler.reconcile(
                decisions,
                authoritative_project_ids=projects,
            )
            reconcile_passes += 1
            while result.truncated:
                if reconcile_passes > profile.max_cycles * (
                    profile.task_count // profile.decision_limit + 3
                ):
                    raise WorkflowSoakError("bounded scheduler did not converge")
                result = scheduler.reconcile(
                    decisions,
                    authoritative_project_ids=projects,
                )
                reconcile_passes += 1

            completed = sum(runtime.state == _TERMINAL for runtime in tasks.values())
            escalated = sum(runtime.state == _ESCALATED for runtime in tasks.values())
            if completed + escalated == profile.task_count:
                break

            attempted_this_cycle = 0
            restart_now = False
            while attempted_this_cycle < profile.batch_size:
                health = scheduler.health_snapshot()
                queue_age = health["jobs"].get("oldest_available_age_seconds")
                if queue_age is not None:
                    max_queue_age = max(max_queue_age, float(queue_age))
                claimable_projects = _claimable_projects(health)
                claimed = store.claim_next(
                    lease_owner=f"soak-worker-{attempts % 8}",
                    lease_seconds=30,
                    fair_across_projects=True,
                )
                if claimed is None:
                    break
                attempts += 1
                attempted_this_cycle += 1
                claim_counts[claimed.project_id] += 1
                if (
                    len(claimable_projects) > 1
                    and last_claim_project == claimed.project_id
                ):
                    contended_fairness_repeats += 1
                last_claim_project = claimed.project_id
                runtime = tasks[claimed.task_id]

                if not restart_performed and completed >= restart_due_after:
                    restart_performed = True
                    restart_now = True
                    store.close()
                    store = WorkflowJobStore(str(path), clock=clock)
                    scheduler = WorkflowJobScheduler(
                        store=store,
                        decision_limit=profile.decision_limit,
                        job_batch_size=profile.batch_size,
                        max_attempts=profile.max_attempts,
                    )
                    recovered = scheduler.recover_startup(abandoned=True)
                    restart_recoveries += int(recovered["abandoned"])
                    clock.advance()
                    break

                if runtime.spec.deliberately_unrecoverable:
                    failed = store.fail(
                        claimed.job_id,
                        claimed.lease_token,
                        category=WorkflowFailureCategory.PERMANENT,
                        error="deterministic deliberately unrecoverable fixture",
                        retryable=False,
                    )
                    if failed.state is not WorkflowJobState.EXHAUSTED:
                        raise WorkflowSoakError("unrecoverable job did not exhaust")
                    runtime.failure_count += 1
                    runtime.state = _ESCALATED
                elif runtime.failure_count < runtime.spec.transient_failures:
                    failed = store.fail(
                        claimed.job_id,
                        claimed.lease_token,
                        category=WorkflowFailureCategory.TRANSPORT,
                        error="deterministic transient provider failure",
                        retryable=True,
                        retry_delay_seconds=1,
                    )
                    if failed.state is not WorkflowJobState.RETRY_WAIT:
                        raise WorkflowSoakError("recoverable failure was not retried")
                    runtime.failure_count += 1
                    transient_failures += 1
                else:
                    completed_job = store.complete(
                        claimed.job_id,
                        claimed.lease_token,
                        result_transition={
                            "status": (
                                "Merged"
                                if runtime.spec.action
                                in {"integration_attempt", "branch_prune"}
                                else "Done"
                            ),
                            "branch_pruned": runtime.spec.action == "branch_prune",
                        },
                    )
                    if completed_job.state is not WorkflowJobState.COMPLETED:
                        raise WorkflowSoakError("completed job was not terminal")
                    runtime.state = _TERMINAL
                    runtime.completed_at = clock()
                    completed += 1
                clock.advance()
            if restart_now:
                continue
            if attempted_this_cycle == 0:
                pending = tuple(
                    runtime.spec.task_id
                    for runtime in tasks.values()
                    if runtime.state == _PENDING
                )
                if pending:
                    raise WorkflowSoakError(
                        "workflow made no progress with pending tasks: "
                        + ", ".join(pending[:10])
                    )
        else:
            raise WorkflowSoakError(
                f"workflow exceeded its {profile.max_cycles}-cycle liveness bound"
            )

        final_decisions = tuple(
            decision
            for runtime in tasks.values()
            if (decision := _decision_for(runtime, tasks)) is not None
        )
        alerts = [
            alert
            for decision in final_decisions
            if (alert := work_decision_alert(decision)) is not None
        ]
        actionable = operator_actionable_alerts(
            [
                {
                    "level": "warning",
                    "source": "soak:normal-retry",
                    "message": "normal retry telemetry",
                    "action_required": False,
                    "action": "none",
                },
                *alerts,
            ]
        )
        unexplained = tuple(
            runtime.spec.task_id
            for runtime in tasks.values()
            if runtime.state not in {_TERMINAL, _ESCALATED}
        )
        expected_escalations = sum(
            runtime.state == _ESCALATED for runtime in tasks.values()
        )
        terminal_recoverable = sum(
            runtime.state == _TERMINAL for runtime in tasks.values()
        )
        if terminal_recoverable != profile.task_count - 1:
            raise WorkflowSoakError("not all recoverable tasks reached terminal state")
        if expected_escalations != 1 or len(actionable) != 1:
            raise WorkflowSoakError(
                "only the deliberately unrecoverable task may escalate"
            )
        if unexplained:
            raise WorkflowSoakError("the soak left unexplained tasks")
        if projection_mismatches:
            raise WorkflowSoakError("decision and UI projections diverged")
        if contended_fairness_repeats:
            raise WorkflowSoakError("fair claims repeated a project under contention")
        if restart_recoveries != 1:
            raise WorkflowSoakError("restart did not recover exactly one abandoned lease")
        max_latency = max(
            (runtime.completed_at or clock()) - started_at
            for runtime in tasks.values()
        )
        if max_latency > profile.max_task_latency_seconds:
            raise WorkflowSoakError("task liveness latency exceeded its documented SLO")
        store.integrity_check()
        store.close()
        store = None
        sqlite_bytes = _database_size(path)
        _, peak_memory = tracemalloc.get_traced_memory()
        peak_delta = max(0, peak_memory - baseline_memory)
        if sqlite_bytes > profile.max_sqlite_bytes:
            raise WorkflowSoakError("SQLite growth exceeded its documented bound")
        if peak_delta > profile.max_peak_memory_bytes:
            raise WorkflowSoakError("Python peak memory exceeded its documented bound")
        action_counts = Counter(spec.action for spec in specs)
        issue_type_counts = Counter(spec.issue_type for spec in specs)
        cross_project_dependencies = sum(
            1
            for spec in specs
            for dependency in spec.dependencies
            if tasks[dependency].spec.project_id != spec.project_id
        )
        counts = tuple(claim_counts.values())
        return WorkflowSoakReport(
            profile=profile.name,
            task_count=profile.task_count,
            project_count=profile.project_count,
            terminal_recoverable_tasks=terminal_recoverable,
            expected_escalations=expected_escalations,
            unexplained_tasks=unexplained,
            cycles=cycles,
            reconcile_passes=reconcile_passes,
            attempts=attempts,
            transient_failures=transient_failures,
            restart_recoveries=restart_recoveries,
            max_queue_age_seconds=max_queue_age,
            max_task_latency_seconds=max_latency,
            contended_fairness_repeats=contended_fairness_repeats,
            max_project_claim_skew=(max(counts) - min(counts)) if counts else 0,
            projection_checks=projection_checks,
            projection_mismatches=projection_mismatches,
            actionable_alerts=len(actionable),
            sqlite_bytes=sqlite_bytes,
            sqlite_limit_bytes=profile.max_sqlite_bytes,
            peak_memory_bytes=peak_delta,
            peak_memory_limit_bytes=profile.max_peak_memory_bytes,
            action_counts=dict(sorted(action_counts.items())),
            issue_type_counts=dict(sorted(issue_type_counts.items())),
            cross_project_dependencies=cross_project_dependencies,
            nested_epics=sum(
                spec.issue_type == "epic" and spec.parent_id is not None
                for spec in specs
            ),
            branch_prunes=sum(
                runtime.state == _TERMINAL
                and runtime.spec.action == "branch_prune"
                for runtime in tasks.values()
            ),
        )
    finally:
        if store is not None:
            store.close()
        if not already_tracing:
            tracemalloc.stop()


__all__ = [
    "SoakTaskSpec",
    "WorkflowSoakError",
    "WorkflowSoakProfile",
    "WorkflowSoakReport",
    "build_workload",
    "run_workflow_soak",
]
