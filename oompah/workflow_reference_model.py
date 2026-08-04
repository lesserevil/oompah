"""Deterministic state-machine testing for the workflow contract.

The production workflow is intentionally split into fact collection, pure
evaluation, durable scheduling, and transition execution.  This module is a
small in-memory specification that composes those concerns for generative
tests.  It is not a second production orchestrator: it provides deterministic
event traces, replay, invariant checks, and trace minimisation without I/O or
third-party property-testing dependencies.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from oompah.workflow_contract import (
    ARCHIVED,
    BACKLOG,
    CANONICAL_STATUSES,
    DECOMPOSED,
    DONE,
    DUPLICATE_CANDIDATE,
    IN_PROGRESS,
    IN_REVIEW,
    IN_VALIDATION,
    LIFECYCLE_FINAL_STATUSES,
    MERGED,
    NEEDS_ANSWER,
    NEEDS_CI_FIX,
    NEEDS_HUMAN,
    NEEDS_REBASE,
    OPEN,
    PROPOSED,
    READY_TO_INTEGRATE,
    STATUS_CONTRACTS,
    TRANSITION_RULES,
    TaskDisposition,
    TransitionRequirement,
    canonicalize_status,
)

REFERENCE_TRACE_SCHEMA_VERSION = 1
DEFAULT_GENERATIVE_CASES = 64
DEFAULT_MAX_TASKS = 12
DEFAULT_MAX_EVENTS = 160


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode()).hexdigest()


class EventKind(str, Enum):
    CREATE_TASK = "create_task"
    SET_DEPENDENCIES = "set_dependencies"
    ROTATE_GENERATION = "rotate_generation"
    CLAIM_OWNER = "claim_owner"
    EXPIRE_OWNER = "expire_owner"
    RECORD_EVIDENCE = "record_evidence"
    TRANSITION = "transition"
    CALLBACK = "callback"
    SCHEDULE_RETRY = "schedule_retry"
    CLAIM_JOB = "claim_job"
    COMPLETE_JOB = "complete_job"
    FAULTS_CEASE = "faults_cease"
    RECONCILE = "reconcile"
    TICK = "tick"


class ViolationCode(str, Enum):
    ILLEGAL_TRANSITION = "illegal_transition_committed"
    STALE_VERSION = "stale_version_committed"
    STALE_GENERATION = "stale_generation_committed"
    DUPLICATE_OWNER = "duplicate_active_owner"
    MISSING_OWNER = "owned_status_without_owner"
    TERMINAL_EVIDENCE = "terminal_transition_without_evidence"
    HARD_START_BYPASS = "hard_start_dependency_bypassed"
    RETRY_WITHOUT_WAKEUP = "retry_without_durable_wakeup"
    JOB_GENERATION = "job_generation_not_fenced"
    UNKNOWN_STATUS = "status_without_total_disposition"
    NO_EVENTUAL_PROGRESS = "no_eventual_progress_after_faults_cease"


@dataclass(frozen=True, slots=True)
class FaultPolicy:
    """Seedable mutations used to prove that the harness catches regressions."""

    allow_illegal_transition: bool = False
    ignore_expected_version: bool = False
    ignore_generation: bool = False
    allow_duplicate_owner: bool = False
    allow_terminal_without_evidence: bool = False
    drop_retry_wakeup: bool = False


@dataclass(frozen=True, slots=True)
class ModelEvent:
    kind: EventKind | str
    task_id: str | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", EventKind(self.kind))
        object.__setattr__(self, "task_id", str(self.task_id) if self.task_id else None)
        object.__setattr__(self, "payload", dict(self.payload))

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "task_id": self.task_id,
            "payload": dict(self.payload),
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> ModelEvent:
        return cls(
            kind=str(raw["kind"]),
            task_id=raw.get("task_id"),
            payload=dict(raw.get("payload") or {}),
        )


@dataclass(frozen=True, slots=True)
class WorkflowTrace:
    seed: int
    events: tuple[ModelEvent, ...]
    schema_version: int = REFERENCE_TRACE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != REFERENCE_TRACE_SCHEMA_VERSION:
            raise ValueError("unsupported workflow trace schema_version")
        object.__setattr__(self, "events", tuple(self.events))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "seed": self.seed,
            "events": [event.to_dict() for event in self.events],
        }

    def stable_json(self) -> str:
        return _canonical_json(self.to_dict())

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> WorkflowTrace:
        return cls(
            seed=int(raw["seed"]),
            events=tuple(ModelEvent.from_dict(item) for item in raw["events"]),
            schema_version=int(raw.get("schema_version", 1)),
        )

    @classmethod
    def from_json(cls, raw: str) -> WorkflowTrace:
        value = json.loads(raw)
        if not isinstance(value, Mapping):
            raise ValueError("workflow trace must be a JSON object")
        return cls.from_dict(value)


@dataclass(frozen=True, slots=True)
class ModelViolation:
    code: ViolationCode
    step: int
    task_id: str | None
    detail: str


@dataclass(slots=True)
class ReferenceTask:
    task_id: str
    status: str = OPEN
    version: int = 0
    generation: int = 1
    parent_id: str | None = None
    issue_type: str = "task"
    finish_dependencies: set[str] = field(default_factory=set)
    hard_start_dependencies: set[str] = field(default_factory=set)
    evidence: dict[str, bool] = field(default_factory=dict)
    retry_due: bool = False
    action_required_reason: str | None = None


@dataclass(slots=True)
class ReferenceOwner:
    owner_id: str
    task_id: str
    generation: int
    active: bool = True


@dataclass(slots=True)
class ReferenceJob:
    job_id: str
    task_id: str
    generation: int
    action: str
    state: str = "queued"

    @property
    def active(self) -> bool:
        return self.state in {"queued", "running"}


@dataclass(frozen=True, slots=True)
class TransitionRecord:
    task_id: str
    source: str
    target: str
    version_before: int
    expected_version: int
    current_generation: int
    evidence_generation: int | None
    requirements: frozenset[TransitionRequirement]
    evidence: Mapping[str, bool]


@dataclass(frozen=True, slots=True)
class ReplayReport:
    trace: WorkflowTrace
    accepted: int
    rejected: int
    violations: tuple[ModelViolation, ...]
    final_state_digest: str

    @property
    def ok(self) -> bool:
        return not self.violations

    @property
    def violation_codes(self) -> frozenset[ViolationCode]:
        return frozenset(item.code for item in self.violations)


class ReferenceWorkflowModel:
    """In-memory executable specification of cross-subsystem workflow rules."""

    def __init__(self, *, policy: FaultPolicy = FaultPolicy()) -> None:
        self.policy = policy
        self.tasks: dict[str, ReferenceTask] = {}
        self.owners: list[ReferenceOwner] = []
        self.jobs: dict[str, ReferenceJob] = {}
        self.transitions: list[TransitionRecord] = []
        self.clock = 0
        self.faults_active = True
        self._violations: list[ModelViolation] = []

    def _task(self, task_id: str | None) -> ReferenceTask | None:
        return self.tasks.get(str(task_id)) if task_id else None

    def _active_owners(self, task_id: str) -> list[ReferenceOwner]:
        return [
            owner for owner in self.owners if owner.task_id == task_id and owner.active
        ]

    def _active_jobs(self, task_id: str) -> list[ReferenceJob]:
        return [
            job for job in self.jobs.values() if job.task_id == task_id and job.active
        ]

    def _dependencies_complete(self, dependencies: set[str]) -> bool:
        return all(
            dependency in self.tasks
            and self.tasks[dependency].status in {DONE, MERGED, ARCHIVED}
            for dependency in dependencies
        )

    def _has_cycle(self, task_id: str) -> bool:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(current: str) -> bool:
            if current in visiting:
                return True
            if current in visited or current not in self.tasks:
                return False
            visiting.add(current)
            task = self.tasks[current]
            for dependency in task.finish_dependencies | task.hard_start_dependencies:
                if visit(dependency):
                    return True
            visiting.remove(current)
            visited.add(current)
            return False

        return visit(task_id)

    def disposition(self, task: ReferenceTask) -> TaskDisposition:
        if self._has_cycle(task.task_id):
            return TaskDisposition.ACTION_REQUIRED
        if task.status == IN_PROGRESS and not self._active_owners(task.task_id):
            return TaskDisposition.RETRY_SCHEDULED
        if task.status == OPEN and not self._dependencies_complete(
            task.hard_start_dependencies
        ):
            return TaskDisposition.BLOCKED
        return STATUS_CONTRACTS[task.status].disposition

    def _record_violation(
        self,
        code: ViolationCode,
        step: int,
        task_id: str | None,
        detail: str,
    ) -> None:
        self._violations.append(ModelViolation(code, step, task_id, detail))

    def apply(self, event: ModelEvent, *, step: int) -> bool:
        """Apply one event, returning whether the reference machine accepted it."""

        accepted = self._apply(event)
        self._check_invariants(step)
        return accepted

    def _apply(self, event: ModelEvent) -> bool:
        payload = event.payload
        task = self._task(event.task_id)
        if event.kind is EventKind.CREATE_TASK:
            if not event.task_id or event.task_id in self.tasks:
                return False
            status = canonicalize_status(str(payload.get("status", OPEN)))
            if status not in STATUS_CONTRACTS:
                return False
            self.tasks[event.task_id] = ReferenceTask(
                task_id=event.task_id,
                status=status,
                parent_id=(
                    str(payload["parent_id"]) if payload.get("parent_id") else None
                ),
                issue_type=str(payload.get("issue_type", "task")),
            )
            return True
        if event.kind is EventKind.TICK:
            self.clock += max(1, int(payload.get("amount", 1)))
            return True
        if event.kind is EventKind.FAULTS_CEASE:
            self.faults_active = False
            return True
        if task is None:
            return False
        if event.kind is EventKind.SET_DEPENDENCIES:
            task.finish_dependencies = {str(item) for item in payload.get("finish", ())}
            task.hard_start_dependencies = {
                str(item) for item in payload.get("hard_start", ())
            }
            task.version += 1
            return True
        if event.kind is EventKind.ROTATE_GENERATION:
            retry_actions = [job.action for job in self._active_jobs(task.task_id)]
            task.generation += 1
            if not self.policy.ignore_generation:
                for owner in self._active_owners(task.task_id):
                    owner.active = False
                for job in self._active_jobs(task.task_id):
                    job.state = "superseded"
                for action in retry_actions:
                    key = f"{task.task_id}:{task.generation}:{action}"
                    self.jobs[key] = ReferenceJob(
                        key, task.task_id, task.generation, action
                    )
            return True
        if event.kind is EventKind.CLAIM_OWNER:
            if (
                self._active_owners(task.task_id)
                and not self.policy.allow_duplicate_owner
            ):
                return False
            generation = int(payload.get("generation", task.generation))
            if generation != task.generation and not self.policy.ignore_generation:
                return False
            self.owners.append(
                ReferenceOwner(
                    str(payload.get("owner_id", f"owner-{len(self.owners) + 1}")),
                    task.task_id,
                    generation,
                )
            )
            return True
        if event.kind is EventKind.EXPIRE_OWNER:
            owner_id = str(payload.get("owner_id", ""))
            matches = [
                owner
                for owner in self._active_owners(task.task_id)
                if not owner_id or owner.owner_id == owner_id
            ]
            for owner in matches:
                owner.active = False
            return bool(matches)
        if event.kind is EventKind.RECORD_EVIDENCE:
            name = str(payload.get("name", ""))
            if not name:
                return False
            task.evidence[name] = bool(payload.get("value", True))
            task.version += 1
            return True
        if event.kind in {EventKind.TRANSITION, EventKind.CALLBACK}:
            return self._transition(
                task, payload, callback=event.kind is EventKind.CALLBACK
            )
        if event.kind is EventKind.SCHEDULE_RETRY:
            generation = int(payload.get("generation", task.generation))
            if generation != task.generation and not self.policy.ignore_generation:
                return False
            task.retry_due = True
            if self.policy.drop_retry_wakeup:
                return True
            action = str(payload.get("action", "reconcile"))
            key = f"{task.task_id}:{generation}:{action}"
            if key not in self.jobs or not self.jobs[key].active:
                self.jobs[key] = ReferenceJob(key, task.task_id, generation, action)
            return True
        if event.kind in {EventKind.CLAIM_JOB, EventKind.COMPLETE_JOB}:
            job_id = str(payload.get("job_id", ""))
            job = self.jobs.get(job_id)
            if job is None or not job.active:
                return False
            generation = int(payload.get("generation", task.generation))
            if (
                generation != job.generation or job.generation != task.generation
            ) and not self.policy.ignore_generation:
                return False
            if event.kind is EventKind.CLAIM_JOB:
                if job.state != "queued":
                    return False
                job.state = "running"
            else:
                if job.state != "running":
                    return False
                job.state = "completed"
                task.retry_due = False
            return True
        if event.kind is EventKind.RECONCILE:
            return self._reconcile(task)
        return False

    def _transition(
        self, task: ReferenceTask, payload: Mapping[str, Any], *, callback: bool
    ) -> bool:
        source = task.status
        target = canonicalize_status(str(payload.get("to", "")))
        rule = TRANSITION_RULES.get((source, target))
        if rule is None and not self.policy.allow_illegal_transition:
            return False
        expected_version = int(payload.get("expected_version", task.version))
        if expected_version != task.version and not self.policy.ignore_expected_version:
            return False
        raw_generation = payload.get("generation")
        supplied_generation = (
            int(raw_generation) if raw_generation is not None else None
        )
        generation_required = callback or (
            rule is not None
            and TransitionRequirement.IMPLEMENTATION_GENERATION in rule.requirements
        )
        if generation_required and (
            supplied_generation != task.generation and not self.policy.ignore_generation
        ):
            return False
        evidence_generation = supplied_generation if generation_required else None
        requirements = rule.requirements if rule else frozenset()
        evidence = {
            **task.evidence,
            **{str(k): bool(v) for k, v in payload.get("evidence", {}).items()},
        }
        if not self._requirements_met(task, requirements, evidence):
            if not (
                self.policy.allow_terminal_without_evidence
                and target in {DONE, MERGED, ARCHIVED}
            ):
                return False
        task.status = target
        task.version += 1
        if target == IN_PROGRESS and not self._active_owners(task.task_id):
            # A faulty transition may expose this; the invariant reports it.
            pass
        if target in LIFECYCLE_FINAL_STATUSES:
            for owner in self._active_owners(task.task_id):
                owner.active = False
            for job in self._active_jobs(task.task_id):
                job.state = "superseded"
            task.retry_due = False
        self.transitions.append(
            TransitionRecord(
                task.task_id,
                source,
                target,
                task.version - 1,
                expected_version,
                task.generation,
                evidence_generation,
                requirements,
                evidence,
            )
        )
        return True

    def _requirements_met(
        self,
        task: ReferenceTask,
        requirements: frozenset[TransitionRequirement],
        evidence: Mapping[str, bool],
    ) -> bool:
        if TransitionRequirement.DEPENDENCIES_SATISFIED in requirements:
            if not self._dependencies_complete(task.hard_start_dependencies):
                return False
            if not self._active_owners(task.task_id):
                return False
        evidence_names = {
            TransitionRequirement.ACTIONABLE_DESCRIPTION: "actionable_description",
            TransitionRequirement.PROJECT_OWNER_AUTHORITY: "project_owner_authority",
            TransitionRequirement.ACCEPTED_SUBMISSION: "accepted_submission",
            TransitionRequirement.AUDIT_REQUEST: "audit_request",
            TransitionRequirement.AUDIT_PASS: "audit_pass",
            TransitionRequirement.LANDING_EVIDENCE: "landing_evidence",
            TransitionRequirement.CONTAINMENT_EVIDENCE: "containment_evidence",
            TransitionRequirement.CHILDREN_CREATED: "children_created",
            TransitionRequirement.CHILDREN_COMPLETE: "children_complete",
            TransitionRequirement.DUPLICATE_VERDICT: "duplicate_verdict",
            TransitionRequirement.OPERATOR_REASON: "operator_reason",
        }
        return all(
            requirement not in evidence_names
            or evidence.get(evidence_names[requirement], False)
            for requirement in requirements
        )

    def _reconcile(self, task: ReferenceTask) -> bool:
        if self.faults_active:
            return self._apply(
                ModelEvent(
                    EventKind.SCHEDULE_RETRY,
                    task.task_id,
                    {"generation": task.generation, "action": "reconcile"},
                )
            )
        if self._has_cycle(task.task_id):
            task.action_required_reason = "dependency_cycle"
            return True
        if task.status in LIFECYCLE_FINAL_STATUSES:
            return True
        if task.status in {PROPOSED, BACKLOG, NEEDS_ANSWER, NEEDS_HUMAN}:
            task.action_required_reason = "external_authority_required"
            return True
        if task.status == OPEN:
            if not self._dependencies_complete(task.hard_start_dependencies):
                return True
            if not self._active_owners(task.task_id):
                self._apply(
                    ModelEvent(
                        EventKind.CLAIM_OWNER,
                        task.task_id,
                        {"generation": task.generation, "owner_id": "reconciler"},
                    )
                )
            return self._transition(
                task,
                {
                    "to": IN_PROGRESS,
                    "expected_version": task.version,
                    "generation": task.generation,
                },
                callback=False,
            )
        if task.status in {NEEDS_CI_FIX, NEEDS_REBASE}:
            if not self._active_owners(task.task_id):
                self._apply(
                    ModelEvent(
                        EventKind.CLAIM_OWNER,
                        task.task_id,
                        {"generation": task.generation, "owner_id": "repair"},
                    )
                )
            return self._transition(
                task,
                {
                    "to": IN_PROGRESS,
                    "expected_version": task.version,
                    "generation": task.generation,
                },
                callback=False,
            )
        if task.status == IN_PROGRESS:
            task.evidence["audit_request"] = True
            return self._transition(
                task,
                {"to": IN_VALIDATION, "expected_version": task.version},
                callback=False,
            )
        if task.status in {IN_REVIEW, READY_TO_INTEGRATE}:
            task.evidence["audit_request"] = True
            return self._transition(
                task,
                {"to": IN_VALIDATION, "expected_version": task.version},
                callback=False,
            )
        if task.status == IN_VALIDATION:
            task.evidence.update(
                {
                    "audit_pass": True,
                    "landing_evidence": True,
                    "containment_evidence": True,
                }
            )
            return self._transition(
                task,
                {"to": MERGED, "expected_version": task.version},
                callback=False,
            )
        if task.status == DONE:
            task.evidence.update(
                {
                    "audit_pass": True,
                    "landing_evidence": True,
                    "containment_evidence": True,
                }
            )
            return self._transition(
                task,
                {"to": MERGED, "expected_version": task.version},
                callback=False,
            )
        if task.status in {DECOMPOSED, DUPLICATE_CANDIDATE}:
            task.evidence.update({"audit_pass": True, "duplicate_verdict": True})
            return self._transition(
                task,
                {"to": ARCHIVED, "expected_version": task.version},
                callback=False,
            )
        return False

    def settle_after_faults_cease(self, *, max_steps: int = 256) -> bool:
        """Reconcile until every task is final or explicitly externally blocked."""

        self.faults_active = False
        for step in range(max_steps):
            pending = [
                task
                for task in self.tasks.values()
                if task.status not in LIFECYCLE_FINAL_STATUSES
                and not task.action_required_reason
            ]
            if not pending:
                return True
            before = self.state_digest()
            # Dependencies first makes bounded convergence deterministic.
            for task in sorted(
                pending, key=lambda item: len(item.hard_start_dependencies)
            ):
                self._reconcile(task)
            self._check_invariants(step)
            if self.state_digest() == before:
                break
        return all(
            task.status in LIFECYCLE_FINAL_STATUSES or task.action_required_reason
            for task in self.tasks.values()
        )

    def _check_invariants(self, step: int) -> None:
        for task in self.tasks.values():
            if task.status not in STATUS_CONTRACTS:
                self._record_violation(
                    ViolationCode.UNKNOWN_STATUS, step, task.task_id, task.status
                )
                continue
            active_owners = self._active_owners(task.task_id)
            if len(active_owners) > 1:
                self._record_violation(
                    ViolationCode.DUPLICATE_OWNER,
                    step,
                    task.task_id,
                    f"{len(active_owners)} live owners",
                )
            if task.retry_due and not self._active_jobs(task.task_id):
                self._record_violation(
                    ViolationCode.RETRY_WITHOUT_WAKEUP,
                    step,
                    task.task_id,
                    "retry has no queued or running durable job",
                )
        for job in self.jobs.values():
            task = self.tasks.get(job.task_id)
            if job.active and task is not None and job.generation != task.generation:
                self._record_violation(
                    ViolationCode.JOB_GENERATION,
                    step,
                    job.task_id,
                    f"job generation {job.generation} != {task.generation}",
                )
        for record in self.transitions:
            if (record.source, record.target) not in TRANSITION_RULES:
                self._record_violation(
                    ViolationCode.ILLEGAL_TRANSITION,
                    step,
                    record.task_id,
                    f"{record.source} -> {record.target}",
                )
            if record.expected_version != record.version_before:
                self._record_violation(
                    ViolationCode.STALE_VERSION,
                    step,
                    record.task_id,
                    f"expected {record.expected_version}, observed {record.version_before}",
                )
            if record.evidence_generation is not None and (
                record.evidence_generation != record.current_generation
            ):
                self._record_violation(
                    ViolationCode.STALE_GENERATION,
                    step,
                    record.task_id,
                    f"evidence {record.evidence_generation}, current {record.current_generation}",
                )
            if (
                TransitionRequirement.DEPENDENCIES_SATISFIED in record.requirements
                and not self._dependencies_complete(
                    self.tasks[record.task_id].hard_start_dependencies
                )
            ):
                self._record_violation(
                    ViolationCode.HARD_START_BYPASS,
                    step,
                    record.task_id,
                    "ownership began before hard-start dependencies completed",
                )
            terminal_requirements = {
                TransitionRequirement.AUDIT_PASS: "audit_pass",
                TransitionRequirement.LANDING_EVIDENCE: "landing_evidence",
                TransitionRequirement.CONTAINMENT_EVIDENCE: "containment_evidence",
            }
            missing = [
                name
                for requirement, name in terminal_requirements.items()
                if requirement in record.requirements and not record.evidence.get(name)
            ]
            if missing:
                self._record_violation(
                    ViolationCode.TERMINAL_EVIDENCE,
                    step,
                    record.task_id,
                    ",".join(missing),
                )

    def state_digest(self) -> str:
        return _digest(
            {
                "clock": self.clock,
                "faults_active": self.faults_active,
                "tasks": {
                    key: {
                        "status": task.status,
                        "version": task.version,
                        "generation": task.generation,
                        "parent": task.parent_id,
                        "finish": sorted(task.finish_dependencies),
                        "hard_start": sorted(task.hard_start_dependencies),
                        "evidence": dict(sorted(task.evidence.items())),
                        "retry_due": task.retry_due,
                        "action_required": task.action_required_reason,
                    }
                    for key, task in sorted(self.tasks.items())
                },
                "owners": sorted(
                    (owner.owner_id, owner.task_id, owner.generation, owner.active)
                    for owner in self.owners
                ),
                "jobs": sorted(
                    (job.job_id, job.task_id, job.generation, job.action, job.state)
                    for job in self.jobs.values()
                ),
            }
        )

    @property
    def violations(self) -> tuple[ModelViolation, ...]:
        # The same persistent defect can be observed after many later events;
        # report its first observation to keep traces and CI output concise.
        unique: dict[tuple[ViolationCode, str | None, str], ModelViolation] = {}
        for violation in self._violations:
            unique.setdefault(
                (violation.code, violation.task_id, violation.detail), violation
            )
        return tuple(unique.values())


class WorkflowScenarioGenerator:
    """Bounded deterministic generator for valid and adversarial compositions."""

    def __init__(
        self,
        seed: int,
        *,
        max_tasks: int = DEFAULT_MAX_TASKS,
        max_events: int = DEFAULT_MAX_EVENTS,
    ) -> None:
        if max_tasks < 1 or max_events < max_tasks:
            raise ValueError("generator bounds must allow at least one event per task")
        self.seed = int(seed)
        self.max_tasks = min(int(max_tasks), DEFAULT_MAX_TASKS)
        self.max_events = min(int(max_events), DEFAULT_MAX_EVENTS)
        self.random = random.Random(self.seed)

    def generate(self) -> WorkflowTrace:
        task_count = self.random.randint(1, self.max_tasks)
        identifiers = [f"TASK-{index + 1}" for index in range(task_count)]
        events: list[ModelEvent] = []
        initial_statuses = (OPEN, OPEN, IN_REVIEW, IN_VALIDATION, READY_TO_INTEGRATE)
        for index, task_id in enumerate(identifiers):
            parent_id = (
                identifiers[self.random.randrange(index)]
                if index and self.random.random() < 0.3
                else None
            )
            events.append(
                ModelEvent(
                    EventKind.CREATE_TASK,
                    task_id,
                    {
                        "status": self.random.choice(initial_statuses),
                        "parent_id": parent_id,
                        "issue_type": "epic" if self.random.random() < 0.2 else "task",
                    },
                )
            )
        for index, task_id in enumerate(identifiers):
            prior = identifiers[:index]
            finish = self.random.sample(
                prior, k=min(len(prior), self.random.randint(0, 2))
            )
            hard = self.random.sample(
                prior, k=min(len(prior), self.random.randint(0, 1))
            )
            # Adversarial cases include self/cyclic dependency input; the model
            # must produce an explicit disposition rather than silently stall.
            if self.random.random() < 0.08:
                hard.append(task_id)
            events.append(
                ModelEvent(
                    EventKind.SET_DEPENDENCIES,
                    task_id,
                    {"finish": finish, "hard_start": hard},
                )
            )
        kinds = (
            EventKind.CLAIM_OWNER,
            EventKind.EXPIRE_OWNER,
            EventKind.ROTATE_GENERATION,
            EventKind.RECORD_EVIDENCE,
            EventKind.TRANSITION,
            EventKind.CALLBACK,
            EventKind.SCHEDULE_RETRY,
            EventKind.CLAIM_JOB,
            EventKind.COMPLETE_JOB,
            EventKind.RECONCILE,
            EventKind.TICK,
        )
        while len(events) < self.max_events:
            task_id = self.random.choice(identifiers)
            kind = self.random.choice(kinds)
            events.append(self._event(kind, task_id))
            if len(events) >= task_count * 6 and self.random.random() < 0.12:
                break
        events.extend(
            [
                ModelEvent(EventKind.FAULTS_CEASE),
                *(ModelEvent(EventKind.RECONCILE, task_id) for task_id in identifiers),
            ]
        )
        return WorkflowTrace(self.seed, tuple(events[: self.max_events]))

    def _event(self, kind: EventKind, task_id: str) -> ModelEvent:
        generation = self.random.randint(1, 4)
        version = self.random.randint(0, 12)
        if kind is EventKind.CLAIM_OWNER:
            return ModelEvent(
                kind,
                task_id,
                {
                    "owner_id": f"agent-{self.random.randint(1, 4)}",
                    "generation": generation,
                },
            )
        if kind is EventKind.RECORD_EVIDENCE:
            return ModelEvent(
                kind,
                task_id,
                {
                    "name": self.random.choice(
                        (
                            "audit_request",
                            "audit_pass",
                            "landing_evidence",
                            "containment_evidence",
                            "accepted_submission",
                        )
                    ),
                    "value": self.random.random() > 0.2,
                },
            )
        if kind in {EventKind.TRANSITION, EventKind.CALLBACK}:
            return ModelEvent(
                kind,
                task_id,
                {
                    "to": self.random.choice(CANONICAL_STATUSES),
                    "expected_version": version,
                    "generation": generation,
                    "evidence": {
                        "audit_pass": self.random.random() > 0.5,
                        "landing_evidence": self.random.random() > 0.5,
                        "containment_evidence": self.random.random() > 0.5,
                    },
                },
            )
        if kind is EventKind.SCHEDULE_RETRY:
            return ModelEvent(
                kind,
                task_id,
                {"generation": generation, "action": "reconcile"},
            )
        if kind in {EventKind.CLAIM_JOB, EventKind.COMPLETE_JOB}:
            return ModelEvent(
                kind,
                task_id,
                {
                    "generation": generation,
                    "job_id": f"{task_id}:{generation}:reconcile",
                },
            )
        return ModelEvent(kind, task_id)


def replay_trace(
    trace: WorkflowTrace,
    *,
    policy: FaultPolicy = FaultPolicy(),
    check_eventual_progress: bool = False,
) -> ReplayReport:
    model = ReferenceWorkflowModel(policy=policy)
    accepted = 0
    rejected = 0
    for step, event in enumerate(trace.events):
        if model.apply(event, step=step):
            accepted += 1
        else:
            rejected += 1
    if check_eventual_progress and not model.settle_after_faults_cease():
        model._record_violation(  # noqa: SLF001 - same-module report construction
            ViolationCode.NO_EVENTUAL_PROGRESS,
            len(trace.events),
            None,
            "bounded reconciliation did not reach a final or explicit action state",
        )
    return ReplayReport(
        trace,
        accepted,
        rejected,
        model.violations,
        model.state_digest(),
    )


def shrink_trace(
    trace: WorkflowTrace,
    *,
    fails: Callable[[WorkflowTrace], bool],
) -> WorkflowTrace:
    """Return a 1-minimal failing trace using deterministic chunk deletion."""

    if not fails(trace):
        raise ValueError("trace does not satisfy the failure predicate")
    events = list(trace.events)
    granularity = 2
    while len(events) >= 2:
        chunk_size = max(1, (len(events) + granularity - 1) // granularity)
        reduced = False
        for start in range(0, len(events), chunk_size):
            candidate = events[:start] + events[start + chunk_size :]
            if candidate and fails(WorkflowTrace(trace.seed, tuple(candidate))):
                events = candidate
                granularity = max(2, granularity - 1)
                reduced = True
                break
        if not reduced:
            if granularity >= len(events):
                break
            granularity = min(len(events), granularity * 2)
    # Finish with single-event deletion to guarantee 1-minimality.
    index = 0
    while index < len(events):
        candidate = events[:index] + events[index + 1 :]
        if candidate and fails(WorkflowTrace(trace.seed, tuple(candidate))):
            events = candidate
        else:
            index += 1
    return WorkflowTrace(trace.seed, tuple(events))


def known_bug_trace(name: str) -> tuple[WorkflowTrace, FaultPolicy, ViolationCode]:
    """Return a minimal seeded regression representing a historical bug class."""

    create = ModelEvent(EventKind.CREATE_TASK, "TASK-1", {"status": OPEN})
    cases: dict[str, tuple[tuple[ModelEvent, ...], FaultPolicy, ViolationCode]] = {
        "stale_callback": (
            (
                create,
                ModelEvent(EventKind.CLAIM_OWNER, "TASK-1", {"generation": 1}),
                ModelEvent(EventKind.ROTATE_GENERATION, "TASK-1"),
                ModelEvent(
                    EventKind.CALLBACK,
                    "TASK-1",
                    {"to": IN_PROGRESS, "expected_version": 0, "generation": 1},
                ),
            ),
            FaultPolicy(ignore_generation=True),
            ViolationCode.STALE_GENERATION,
        ),
        "duplicate_owner": (
            (
                create,
                ModelEvent(EventKind.CLAIM_OWNER, "TASK-1", {"owner_id": "a"}),
                ModelEvent(EventKind.CLAIM_OWNER, "TASK-1", {"owner_id": "b"}),
            ),
            FaultPolicy(allow_duplicate_owner=True),
            ViolationCode.DUPLICATE_OWNER,
        ),
        "lost_retry": (
            (create, ModelEvent(EventKind.SCHEDULE_RETRY, "TASK-1")),
            FaultPolicy(drop_retry_wakeup=True),
            ViolationCode.RETRY_WITHOUT_WAKEUP,
        ),
        "terminal_without_evidence": (
            (
                ModelEvent(EventKind.CREATE_TASK, "TASK-1", {"status": IN_VALIDATION}),
                ModelEvent(
                    EventKind.TRANSITION,
                    "TASK-1",
                    {"to": MERGED, "expected_version": 0},
                ),
            ),
            FaultPolicy(allow_terminal_without_evidence=True),
            ViolationCode.TERMINAL_EVIDENCE,
        ),
    }
    if name not in cases:
        raise KeyError(name)
    events, policy, violation = cases[name]
    seed = int.from_bytes(hashlib.sha256(name.encode()).digest()[:8], "big")
    return WorkflowTrace(seed, events), policy, violation


KNOWN_BUG_TRACES = frozenset(
    {"stale_callback", "duplicate_owner", "lost_retry", "terminal_without_evidence"}
)
