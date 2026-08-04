"""Universal totality and liveness controller for workflow decisions.

The controller is deliberately small in scope.  ``evaluate_task`` remains a
pure policy function and ``WorkflowJobStore`` remains the ownership boundary;
this module joins them for the server runtime.  It evaluates every task in a
bounded snapshot, repairs recoverable omissions by enqueueing generation-
fenced jobs, and turns conditions that cannot be repaired automatically into
an actionable decision with named evidence.

No method in this module writes tracker status.  A decision is the only
output of policy evaluation and all automatic side effects go through the
durable scheduler.
"""

from __future__ import annotations

import inspect
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from oompah.models import Issue
from oompah.statuses import canonicalize_status
from oompah.work_decision import (
    PermittedAction,
    UnmetPrerequisite,
    WorkDecision,
    evaluate_task,
)
from oompah.workflow_contract import (
    LIFECYCLE_FINAL_STATUSES,
    TaskDisposition,
    WorkflowOwner,
)
from oompah.workflow_facts import (
    FactDomain,
    FactObservation,
    FactState,
    REQUIRED_FACT_DOMAINS,
    WorkflowFacts,
)
from oompah.workflow_jobs import WorkflowJobState, WorkflowJobStore
from oompah.workflow_reasons import AlertSeverity
from oompah.workflow_scheduler import (
    WorkflowJobScheduler,
    WorkflowReconcileResult,
)


DEFAULT_CONTROLLER_LIMIT = 100
MAX_CONTROLLER_LIMIT = 1000
_NONTERMINAL_DISPOSITIONS = frozenset(
    {
        TaskDisposition.RUNNABLE,
        TaskDisposition.OWNED,
        TaskDisposition.BLOCKED,
        TaskDisposition.RETRY_SCHEDULED,
        TaskDisposition.ACTION_REQUIRED,
    }
)


class WorkflowFactsProvider(Protocol):
    def collect(self, task_id: str) -> WorkflowFacts: ...


FactsSource = Mapping[Any, WorkflowFacts] | Callable[[Issue | Mapping[str, Any]], WorkflowFacts]


@dataclass(frozen=True, slots=True)
class ControllerEscalation:
    """Concrete evidence explaining why automation could not continue."""

    project_id: str
    task_id: str
    reason_code: str
    evidence: tuple[UnmetPrerequisite, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "task_id": self.task_id,
            "reason_code": self.reason_code,
            "evidence": [item.to_dict() for item in self.evidence],
        }


@dataclass(frozen=True, slots=True)
class ControllerPass:
    """One bounded event or full-sync controller pass."""

    snapshot_generation: int
    decisions: tuple[WorkDecision, ...]
    reconciliation: WorkflowReconcileResult
    escalations: tuple[ControllerEscalation, ...]
    truncated: bool

    @property
    def action_required(self) -> tuple[WorkDecision, ...]:
        return tuple(
            decision
            for decision in self.decisions
            if decision.disposition is TaskDisposition.ACTION_REQUIRED
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_generation": self.snapshot_generation,
            "decisions": [decision.to_dict() for decision in self.decisions],
            "reconciliation": {
                "decisions_seen": self.reconciliation.decisions_seen,
                "decisions_applied": self.reconciliation.decisions_applied,
                "jobs_created": self.reconciliation.jobs_created,
                "jobs_replayed": self.reconciliation.jobs_replayed,
                "jobs_superseded": self.reconciliation.jobs_superseded,
                "stale_rejected": self.reconciliation.stale_rejected,
                "truncated": self.reconciliation.truncated,
            },
            "escalations": [item.to_dict() for item in self.escalations],
            "truncated": self.truncated,
        }


def _required_text(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} is required")
    return text


def _parse_time(value: object, name: str) -> datetime:
    raw = _required_text(value, name)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{name} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _task_identity(task: Issue | Mapping[str, Any]) -> tuple[str, str]:
    if isinstance(task, Issue):
        return str(task.project_id or ""), _required_text(task.identifier, "task_id")
    if not isinstance(task, Mapping):
        raise TypeError("tasks must contain Issue or mapping values")
    return (
        str(task.get("project_id") or ""),
        _required_text(task.get("identifier", task.get("task_id")), "task_id"),
    )


def _task_status(task: Issue | Mapping[str, Any]) -> str:
    raw = task.state if isinstance(task, Issue) else task.get("status", task.get("state"))
    return canonicalize_status(raw)


def _task_dependencies(task: Issue | Mapping[str, Any]) -> tuple[str, ...]:
    if isinstance(task, Issue):
        values = (*task.blocked_by, *task.start_blocked_by)
        return tuple(
            sorted(
                {
                    str(item.identifier or item.id).strip()
                    for item in values
                    if str(item.identifier or item.id or "").strip()
                }
            )
        )
    values: list[Any] = []
    for key in ("blocked_by", "start_blocked_by", "dependencies", "hard_start"):
        raw = task.get(key, ())
        if isinstance(raw, (list, tuple, set)):
            values.extend(raw)
        elif key == "dependencies" and isinstance(raw, Mapping):
            for nested in raw.values():
                if isinstance(nested, (list, tuple, set)):
                    values.extend(nested)
    result: set[str] = set()
    for item in values:
        if isinstance(item, Mapping):
            value = item.get("identifier", item.get("id", item.get("task_id")))
        else:
            value = item
        text = str(value or "").strip()
        if text:
            result.add(text)
    return tuple(sorted(result))


def _cycle_members(tasks: Sequence[Issue | Mapping[str, Any]]) -> set[tuple[str, str]]:
    """Return only vertices participating in a dependency cycle."""

    identities = {_task_identity(task) for task in tasks}
    by_project_identifier = {
        (identity[0], identity[1]): identity for identity in identities
    }
    edges: dict[tuple[str, str], set[tuple[str, str]]] = {}
    for task in tasks:
        identity = _task_identity(task)
        edges[identity] = {
            by_project_identifier[(identity[0], dependency)]
            for dependency in _task_dependencies(task)
            if (identity[0], dependency) in by_project_identifier
        }
    colour: dict[tuple[str, str], int] = {}
    stack: list[tuple[str, str]] = []
    cycles: set[tuple[str, str]] = set()

    def visit(node: tuple[str, str]) -> None:
        colour[node] = 1
        stack.append(node)
        for child in edges.get(node, ()):
            state = colour.get(child, 0)
            if state == 0:
                visit(child)
            elif state == 1:
                try:
                    start = stack.index(child)
                except ValueError:  # defensive: the stack is local and ordered
                    continue
                cycles.update(stack[start:])
        stack.pop()
        colour[node] = 2

    for identity in sorted(identities):
        if colour.get(identity, 0) == 0:
            visit(identity)
    return cycles


def _fact_mapping(facts: WorkflowFacts, domain: FactDomain) -> Mapping[str, Any] | None:
    observation = facts.fact(domain)
    if observation.state is not FactState.KNOWN or not isinstance(observation.value, Mapping):
        return None
    return observation.value


def _ownership_problem(facts: WorkflowFacts) -> tuple[str, tuple[UnmetPrerequisite, ...]] | None:
    value = _fact_mapping(facts, FactDomain.IMPLEMENTATION_AUTHORITY)
    if value is None:
        return None
    if bool(value.get("ownership_impossible")) or bool(value.get("impossible")):
        return (
            "ownership.impossible",
            (UnmetPrerequisite("ownership.impossible", facts.task_id),),
        )
    if bool(value.get("ownership_conflict")) or bool(value.get("conflicting")):
        return (
            "ownership.conflict",
            (UnmetPrerequisite("ownership.conflict", facts.task_id),),
        )

    claims: list[Any] = []
    for key in ("owners", "owner_ids", "claims", "leases"):
        raw = value.get(key)
        if isinstance(raw, (list, tuple, set, frozenset)):
            claims.extend(raw)
        elif isinstance(raw, Mapping):
            claims.extend(
                {"owner_id": key, **item} if isinstance(item, Mapping) else key
                for key, item in raw.items()
            )
    owner_id = str(value.get("owner_id") or value.get("owner") or "").strip()
    if owner_id:
        claims.append(owner_id)
    if len(claims) > 1:
        subjects: list[str] = []
        for claim in claims:
            if isinstance(claim, Mapping):
                subject = claim.get("owner_id", claim.get("id", claim.get("owner")))
            else:
                subject = claim
            text = str(subject or "unknown").strip() or "unknown"
            subjects.append(text)
        return (
            "ownership.conflict",
            tuple(
                UnmetPrerequisite("ownership.conflict", subject)
                for subject in sorted(subjects)
            ),
        )
    return None


def _required_job_missing(facts: WorkflowFacts, decision: WorkDecision) -> bool:
    """Recognize explicit queue absence without guessing from missing data."""

    checks = {
        FactDomain.REVIEW_CI: ("review_job_present", "job_present", "queue_present"),
        FactDomain.TERMINAL_AUDIT: ("audit_job_present", "job_present", "queue_present"),
        FactDomain.INTEGRATION: ("integration_job_present", "job_present", "queue_present"),
    }
    domain = {
        "review_refresh": FactDomain.REVIEW_CI,
        "review_monitor": FactDomain.REVIEW_CI,
        "terminal_audit": FactDomain.TERMINAL_AUDIT,
        "terminal_audit_recovery": FactDomain.TERMINAL_AUDIT,
        "integration_attempt": FactDomain.INTEGRATION,
        "integration_recovery": FactDomain.INTEGRATION,
    }
    selected = next((domain[action] for action in decision.durable_jobs if action in domain), None)
    if selected is None:
        return False
    value = _fact_mapping(facts, selected)
    if value is None:
        return False
    return any(key in value and value[key] is False for key in checks[selected])


def _retry_exhausted(facts: WorkflowFacts, max_attempts: int) -> bool:
    value = _fact_mapping(facts, FactDomain.RETRY_BUDGET)
    if value is None:
        return False
    if bool(value.get("exhausted")):
        return True
    try:
        attempts = int(value.get("attempts", 0) or 0)
    except (TypeError, ValueError):
        return True
    budget = value.get("max_attempts", max_attempts)
    try:
        return attempts >= int(budget)
    except (TypeError, ValueError):
        return True


def _graph_problem(facts: WorkflowFacts) -> tuple[str, ...] | None:
    value = _fact_mapping(facts, FactDomain.DEPENDENCIES)
    if value is None:
        return None
    if bool(value.get("cycle")) or bool(value.get("graph_impossible")):
        raw = value.get("cycle_members", (facts.task_id,))
        if not isinstance(raw, (list, tuple, set, frozenset)):
            raw = (facts.task_id,)
        return tuple(sorted(str(item).strip() for item in raw if str(item).strip()))
    return None


def _stored_retry_exhausted(
    store: WorkflowJobStore, decision: WorkDecision
) -> bool:
    """Check exhaustion for the current activation, not historical jobs."""

    if not decision.durable_jobs:
        return False
    cursor = store.schedule_cursor(
        project_id=decision.project_id, task_id=decision.task_id
    )
    if cursor is None or cursor.decision_revision != decision.decision_revision:
        return False
    current = store.list_jobs(
        project_id=decision.project_id,
        task_id=decision.task_id,
        generation=cursor.job_generation,
        limit=1000,
    )
    return any(
        job.state is WorkflowJobState.EXHAUSTED
        and job.action in decision.durable_jobs
        for job in current
    )


def _replace(
    decision: WorkDecision,
    *,
    disposition: TaskDisposition,
    reason_code: str,
    owner: WorkflowOwner,
    prerequisites: Sequence[UnmetPrerequisite] = (),
    actions: Sequence[PermittedAction] = (),
    alert: AlertSeverity = AlertSeverity.NONE,
    durable_jobs: Sequence[str] = (),
) -> WorkDecision:
    """Rebuild a decision while deliberately invalidating its content hash."""

    from dataclasses import replace

    return replace(
        decision,
        disposition=disposition,
        reason_code=reason_code,
        responsible_owner=owner,
        unmet_prerequisites=tuple(prerequisites),
        permitted_actions=tuple(actions),
        action_required=disposition is TaskDisposition.ACTION_REQUIRED,
        alert_level=alert,
        durable_jobs=tuple(durable_jobs),
        decision_revision=None,
    )


class UniversalTotalityLivenessController:
    """Evaluate and reconcile all non-final task decisions.

    ``facts`` may be a mapping keyed by ``(project_id, task_id)`` or by task
    identifier.  A callable or collector object can be supplied instead for
    server use.  The controller is safe to call from event handlers and the
    periodic full-sync: both paths use the same durable generation fence.
    """

    def __init__(
        self,
        *,
        store: WorkflowJobStore,
        scheduler: WorkflowJobScheduler | None = None,
        facts_provider: FactsSource | None = None,
        decision_limit: int = DEFAULT_CONTROLLER_LIMIT,
        max_attempts: int = 5,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if isinstance(decision_limit, bool) or not 1 <= int(decision_limit) <= MAX_CONTROLLER_LIMIT:
            raise ValueError(f"decision_limit must be between 1 and {MAX_CONTROLLER_LIMIT}")
        if isinstance(max_attempts, bool) or int(max_attempts) < 1:
            raise ValueError("max_attempts must be positive")
        self.store = store
        self.scheduler = scheduler or WorkflowJobScheduler(
            store=store, decision_limit=int(decision_limit), max_attempts=int(max_attempts)
        )
        self.facts_provider = facts_provider
        self.decision_limit = int(decision_limit)
        self.max_attempts = int(max_attempts)
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = threading.RLock()
        self._evaluated = 0
        self._passes = 0
        self._escalated = 0
        self._last_pass: ControllerPass | None = None
        self._last_error: str | None = None

    @staticmethod
    def _is_final(task: Issue | Mapping[str, Any]) -> bool:
        return _task_status(task) in LIFECYCLE_FINAL_STATUSES

    def _resolve_facts(
        self,
        task: Issue | Mapping[str, Any],
        facts: FactsSource | None,
    ) -> WorkflowFacts:
        project_id, task_id = _task_identity(task)
        if isinstance(facts, Mapping):
            for key in ((project_id, task_id), task_id):
                value = facts.get(key)
                if value is not None:
                    if not isinstance(value, WorkflowFacts):
                        raise TypeError("facts mapping must contain WorkflowFacts values")
                    return value
            raise KeyError(f"missing workflow facts for {project_id}/{task_id}")
        source = facts or self.facts_provider
        if source is None:
            raise ValueError("facts or facts_provider is required")
        if callable(source):
            value = source(task)
        elif hasattr(source, "collect"):
            value = source.collect(task_id)  # type: ignore[union-attr]
        else:
            raise TypeError("facts_provider must be callable or provide collect")
        if inspect.isawaitable(value):
            raise TypeError("async facts providers must be resolved before reconcile")
        if not isinstance(value, WorkflowFacts):
            raise TypeError("facts provider must return WorkflowFacts")
        return value

    def _decide(
        self,
        task: Issue | Mapping[str, Any],
        facts: WorkflowFacts,
        *,
        cycles: set[tuple[str, str]],
        now: datetime,
    ) -> WorkDecision:
        decision = evaluate_task(task, facts, now=now)
        identity = _task_identity(task)
        if decision.disposition is TaskDisposition.TERMINAL:
            return decision
        if (
            _task_status(task) == "In Progress"
            and decision.disposition is TaskDisposition.OWNED
            and (authority := _fact_mapping(facts, FactDomain.IMPLEMENTATION_AUTHORITY))
            and not any(
                str(authority.get(key) or "").strip()
                for key in ("owner_id", "owner", "owners", "owner_ids", "claims")
            )
        ):
            return _replace(
                decision,
                disposition=TaskDisposition.RETRY_SCHEDULED,
                reason_code="implementation.recovery_scheduled",
                owner=WorkflowOwner.DISPATCHER,
                prerequisites=(
                    UnmetPrerequisite("ownership.missing", identity[1]),
                ),
                actions=(PermittedAction.RECOVER_IMPLEMENTATION,),
                alert=AlertSeverity.INFO,
                durable_jobs=("implementation_recovery",),
            )
        fact_cycle = _graph_problem(facts)
        if (
            (identity in cycles or fact_cycle is not None)
            and decision.disposition is not TaskDisposition.ACTION_REQUIRED
        ):
            return _replace(
                decision,
                disposition=TaskDisposition.ACTION_REQUIRED,
                reason_code="graph.impossible",
                owner=WorkflowOwner.OPERATOR,
                prerequisites=(
                    UnmetPrerequisite(
                        "dependencies.cycle",
                        identity[1],
                        ",".join(fact_cycle or (identity[0],)),
                    ),
                ),
                actions=(PermittedAction.RESOLVE_OPERATOR_ACTION,),
                alert=AlertSeverity.CRITICAL,
            )

        ownership = _ownership_problem(facts)
        if ownership is not None and decision.disposition is not TaskDisposition.ACTION_REQUIRED:
            reason, evidence = ownership
            return _replace(
                decision,
                disposition=TaskDisposition.ACTION_REQUIRED,
                reason_code=reason,
                owner=WorkflowOwner.OPERATOR,
                prerequisites=evidence,
                actions=(PermittedAction.RESOLVE_OPERATOR_ACTION,),
                alert=AlertSeverity.CRITICAL,
            )

        if (
            (_retry_exhausted(facts, self.max_attempts) or _stored_retry_exhausted(self.store, decision))
            and decision.durable_jobs
        ):
            return _replace(
                decision,
                disposition=TaskDisposition.ACTION_REQUIRED,
                reason_code="retry.exhausted",
                owner=WorkflowOwner.OPERATOR,
                prerequisites=(
                    UnmetPrerequisite("retry.exhausted", identity[1]),
                ),
                actions=(PermittedAction.RESOLVE_OPERATOR_ACTION,),
                alert=AlertSeverity.CRITICAL,
            )

        if _required_job_missing(facts, decision) and decision.disposition is not TaskDisposition.ACTION_REQUIRED:
            return _replace(
                decision,
                disposition=TaskDisposition.RETRY_SCHEDULED,
                reason_code=decision.reason_code,
                owner=decision.responsible_owner,
                prerequisites=(
                    UnmetPrerequisite("recovery.job_missing", identity[1]),
                ),
                actions=decision.permitted_actions,
                alert=AlertSeverity.INFO,
                durable_jobs=decision.durable_jobs,
            )

        if (
            decision.disposition is TaskDisposition.RETRY_SCHEDULED
            and not decision.durable_jobs
        ):
            return _replace(
                decision,
                disposition=TaskDisposition.ACTION_REQUIRED,
                reason_code="automation.unavailable",
                owner=WorkflowOwner.OPERATOR,
                prerequisites=(
                    UnmetPrerequisite("automation.unavailable", identity[1]),
                ),
                actions=(PermittedAction.RESOLVE_OPERATOR_ACTION,),
                alert=AlertSeverity.WARNING,
            )

        deadline = decision.next_reassessment_at
        if deadline is not None and now > _parse_time(deadline, "next_reassessment_at"):
            if decision.reason_code != "liveness.reassessment_overdue":
                return _replace(
                    decision,
                    disposition=TaskDisposition.ACTION_REQUIRED,
                    reason_code="liveness.reassessment_overdue",
                    owner=WorkflowOwner.OPERATOR,
                    prerequisites=(
                        UnmetPrerequisite("liveness.previous_reason", decision.reason_code),
                        UnmetPrerequisite("liveness.deadline", deadline),
                    ),
                    actions=(PermittedAction.RESOLVE_OPERATOR_ACTION,),
                    alert=AlertSeverity.WARNING,
                )

        if decision.disposition not in _NONTERMINAL_DISPOSITIONS:
            # This is a controller invariant breach.  Fail closed with a
            # concrete operator handoff rather than allowing an unclassified
            # status to leave the bounded pass.
            return _replace(
                decision,
                disposition=TaskDisposition.ACTION_REQUIRED,
                reason_code="ownership.impossible",
                owner=WorkflowOwner.OPERATOR,
                prerequisites=(
                    UnmetPrerequisite("controller.invalid_disposition", identity[1]),
                ),
                actions=(PermittedAction.RESOLVE_OPERATOR_ACTION,),
                alert=AlertSeverity.CRITICAL,
            )
        return decision

    def evaluate(
        self,
        tasks: Sequence[Issue | Mapping[str, Any]],
        *,
        facts: FactsSource | None = None,
        facts_by_task: Mapping[Any, WorkflowFacts] | None = None,
        now: datetime | None = None,
    ) -> tuple[WorkDecision, ...]:
        """Evaluate every supplied non-final task exactly once."""

        if facts is not None and facts_by_task is not None:
            raise ValueError("provide facts or facts_by_task, not both")
        facts = facts_by_task or facts
        current = now or self._clock()
        if current.tzinfo is None:
            raise ValueError("now must include a timezone")
        current = current.astimezone(timezone.utc)
        normalized = tuple(tasks)
        by_identity: dict[tuple[str, str], Issue | Mapping[str, Any]] = {}
        conflict_ids: set[tuple[str, str]] = set()
        for task in normalized:
            identity = _task_identity(task)
            previous = by_identity.get(identity)
            if previous is not None and (
                _task_status(previous) != _task_status(task)
                or _task_dependencies(previous) != _task_dependencies(task)
            ):
                conflict_ids.add(identity)
            by_identity[identity] = task
        ordered_candidates = tuple(
            task for identity, task in sorted(by_identity.items()) if not self._is_final(task)
        )
        if len(ordered_candidates) > self.decision_limit:
            offset = self.store.allocate_decision_window(
                total=len(ordered_candidates), limit=self.decision_limit
            )
            candidates = (
                ordered_candidates[offset:] + ordered_candidates[:offset]
            )[: self.decision_limit]
        else:
            candidates = ordered_candidates
        cycles = _cycle_members(candidates)
        decisions: list[WorkDecision] = []
        for task in candidates:
            identity = _task_identity(task)
            try:
                workflow_facts = self._resolve_facts(task, facts)
                decision = self._decide(task, workflow_facts, cycles=cycles, now=current)
            except Exception:
                # A collector or malformed snapshot cannot make a task vanish
                # from the totality pass.  Re-read through a provider where
                # possible; if that also fails, produce a stable actionable
                # fallback so the task remains visible in the pass.
                if isinstance(facts, Mapping):
                    workflow_facts = facts.get(identity) or facts.get(identity[1])
                else:
                    workflow_facts = None
                if not isinstance(workflow_facts, WorkflowFacts):
                    observed_at = current.isoformat()
                    project_id = identity[0] or "unknown-project"
                    workflow_facts = WorkflowFacts(
                        project_id,
                        identity[1],
                        observed_at,
                        {
                            domain: FactObservation.error(
                                domain,
                                observed_at=observed_at,
                                source="universal_controller",
                                error_code="controller_evidence_unavailable",
                            )
                            for domain in REQUIRED_FACT_DOMAINS
                        },
                    )
                decision = _replace(
                    evaluate_task(task, workflow_facts, now=current),
                    disposition=TaskDisposition.ACTION_REQUIRED,
                    reason_code="controller.evaluation_failed",
                    owner=WorkflowOwner.OPERATOR,
                    prerequisites=(
                        UnmetPrerequisite("controller.evaluation_failed", identity[1]),
                    ),
                    actions=(PermittedAction.RESOLVE_OPERATOR_ACTION,),
                    alert=AlertSeverity.CRITICAL,
                )
            if identity in conflict_ids:
                decision = _replace(
                    decision,
                    disposition=TaskDisposition.ACTION_REQUIRED,
                    reason_code="evidence.conflicting_task_facts",
                    owner=WorkflowOwner.OPERATOR,
                    prerequisites=(
                        UnmetPrerequisite("evidence.conflicting_task_facts", identity[1]),
                    ),
                    actions=(PermittedAction.RESOLVE_OPERATOR_ACTION,),
                    alert=AlertSeverity.CRITICAL,
                )
            decisions.append(decision)
        with self._lock:
            self._evaluated += len(decisions)
        return tuple(decisions)

    def reconcile(
        self,
        tasks: Sequence[Issue | Mapping[str, Any]],
        *,
        facts: FactsSource | None = None,
        facts_by_task: Mapping[Any, WorkflowFacts] | None = None,
        now: datetime | None = None,
        snapshot_generation: int | None = None,
    ) -> ControllerPass:
        """Run one event/full-sync pass and materialize automatic recovery."""

        if snapshot_generation is None:
            generation = self.scheduler.begin_scan()
        else:
            if isinstance(snapshot_generation, bool):
                raise ValueError("snapshot_generation must be positive")
            generation = int(snapshot_generation)
        if generation < 1:
            raise ValueError("snapshot_generation must be positive")
        nonfinal_count = len(
            {
                _task_identity(task)
                for task in tasks
                if not self._is_final(task)
            }
        )
        decisions = self.evaluate(
            tasks, facts=facts, facts_by_task=facts_by_task, now=now
        )
        reconciliation = self.scheduler.reconcile(
            decisions, snapshot_generation=generation
        )
        escalations = tuple(
            ControllerEscalation(
                decision.project_id,
                decision.task_id,
                decision.reason_code,
                decision.unmet_prerequisites,
            )
            for decision in decisions
            if decision.disposition is TaskDisposition.ACTION_REQUIRED
        )
        result = ControllerPass(
            generation,
            decisions,
            reconciliation,
            escalations,
            reconciliation.truncated or nonfinal_count > self.decision_limit,
        )
        with self._lock:
            self._passes += 1
            self._escalated += len(escalations)
            self._last_pass = result
            self._last_error = None
        return result

    def on_event(
        self,
        tasks: Sequence[Issue | Mapping[str, Any]],
        *,
        facts: FactsSource | None = None,
        facts_by_task: Mapping[Any, WorkflowFacts] | None = None,
        now: datetime | None = None,
    ) -> ControllerPass:
        """Evaluate a relevant event immediately while retaining coalescing."""

        self.scheduler.wake("workflow event")
        return self.reconcile(
            tasks, facts=facts, facts_by_task=facts_by_task, now=now
        )

    def full_sync(
        self,
        tasks: Sequence[Issue | Mapping[str, Any]],
        *,
        facts: FactsSource | None = None,
        facts_by_task: Mapping[Any, WorkflowFacts] | None = None,
        now: datetime | None = None,
    ) -> ControllerPass:
        """Run the bounded correctness pass used as the liveness safety net."""

        return self.reconcile(
            tasks, facts=facts, facts_by_task=facts_by_task, now=now
        )

    def recover_startup(self) -> dict[str, int]:
        """Reconstruct durable ownership after an exclusive restart."""

        return self.scheduler.recover_startup(abandoned=True)

    def health_snapshot(self) -> dict[str, Any]:
        with self._lock:
            summary = {
                "evaluated": self._evaluated,
                "passes": self._passes,
                "escalated": self._escalated,
                "last_error": self._last_error,
                "last_pass_generation": (
                    self._last_pass.snapshot_generation if self._last_pass else None
                ),
            }
        return {"controller": summary, **self.scheduler.health_snapshot()}


# Short aliases make the policy boundary discoverable without creating two
# implementations or two state stores.
UniversalWorkflowController = UniversalTotalityLivenessController
TotalityLivenessController = UniversalTotalityLivenessController


__all__ = [
    "ControllerEscalation",
    "ControllerPass",
    "UniversalTotalityLivenessController",
    "UniversalWorkflowController",
    "TotalityLivenessController",
]
