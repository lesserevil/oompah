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
import logging
import re
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from oompah.models import Issue
from oompah.integration import ACCEPTED_SUBMISSION_STATES
from oompah.statuses import canonicalize_status
from oompah.work_decision import (
    PermittedAction,
    REVIEW_ACTION_JOBS,
    UnmetPrerequisite,
    WorkDecision,
    evaluate_task,
)
from oompah.workflow_contract import (
    LIFECYCLE_FINAL_STATUSES,
    TaskDisposition,
    WorkflowOwner,
)
from oompah.workflow_fact_model import (
    FactDomain,
    FactObservation,
    FactState,
    REQUIRED_FACT_DOMAINS,
    WorkflowFacts,
)
from oompah.workflow_jobs import (
    WorkflowFailureCategory,
    WorkflowJob,
    WorkflowJobStore,
    WorkflowSnapshotPublication,
)
from oompah.workflow_liveness_metrics import (
    DEFAULT_MAX_PROJECT_RECORDS,
    DEFAULT_MAX_TASK_RECORDS,
    DEFAULT_SNAPSHOT_STALE_SECONDS,
    DecisionLivenessFacts,
    WorkflowLivenessHealth,
    WorkflowLivenessTracker,
)
from oompah.workflow_reasons import (
    AlertSeverity,
    LivenessPolicy,
    build_liveness_policy,
)
from oompah.workflow_scheduler import (
    WorkflowJobScheduler,
    WorkflowReconcileResult,
)

logger = logging.getLogger(__name__)


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


class WorkflowProjectionPublicationRejected(RuntimeError):
    """The canonical decision projection rejected a controller generation."""

    def __init__(self, reason: str) -> None:
        self.reason = _required_text(reason, "projection rejection reason")
        super().__init__(self.reason)


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
    def accepted(self) -> bool:
        return self.reconciliation.snapshot_accepted

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
            "accepted": self.accepted,
            "decisions": [decision.to_dict() for decision in self.decisions],
            "reconciliation": {
                "snapshot_accepted": self.reconciliation.snapshot_accepted,
                "decisions_seen": self.reconciliation.decisions_seen,
                "decisions_applied": self.reconciliation.decisions_applied,
                "jobs_created": self.reconciliation.jobs_created,
                "jobs_replayed": self.reconciliation.jobs_replayed,
                "jobs_superseded": self.reconciliation.jobs_superseded,
                "jobs_required": self.reconciliation.jobs_required,
                "jobs_materialized": self.reconciliation.jobs_materialized,
                "schedules_required": self.reconciliation.schedules_required,
                "schedules_materialized": (
                    self.reconciliation.schedules_materialized
                ),
                "stale_rejected": self.reconciliation.stale_rejected,
                "truncated": self.reconciliation.truncated,
            },
            "escalations": [item.to_dict() for item in self.escalations],
            "truncated": self.truncated,
        }


@dataclass(frozen=True, slots=True)
class ControllerObservation:
    """Prepared totality evidence for one runtime-owned snapshot.

    The durable runtime, rather than this controller's scheduler, owns job
    materialization after the production cutover.  This value lets that owner
    prepare universal decisions before its single snapshot publication and
    stage only the liveness/projection side of the controller transaction.
    """

    snapshot_generation: int
    decisions: tuple[WorkDecision, ...]
    decision_facts: Mapping[tuple[str, str], DecisionLivenessFacts]
    expected_identities: tuple[tuple[str, str], ...]
    escalations: tuple[ControllerEscalation, ...]
    source_scan_complete: bool
    source_errors: Mapping[str, str]
    excluded_projects: Mapping[str, str]
    observed_at: datetime
    policy_epoch: str
    source_scan_deferred: bool = False

    @property
    def truncated(self) -> bool:
        return (
            not self.source_scan_complete
            or len(self.decisions) < len(self.expected_identities)
        )


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
    decision: WorkDecision,
    exhausted: Sequence[WorkflowJob],
    *,
    prospective_authority_cut: bool,
    successor_generation_proven: bool = False,
) -> bool:
    """Check exhaustion without letting an unpublished cursor retire it.

    A reconcile pass may prospectively replace exhausted work only when its
    canonical decision no longer requires that action.  The actual retirement
    remains invisible until the snapshot and its per-job proofs publish.  A
    read-only evaluation, or a decision which still needs the exhausted
    action, stays fail closed.
    """

    if not exhausted:
        return False
    if not prospective_authority_cut:
        return True
    if successor_generation_proven:
        return False
    required = set(decision.durable_jobs)
    return bool(required and any(job.action in required for job in exhausted))


_EXACT_HEAD_RE = re.compile(r"^[0-9a-f]{40,64}$")


def _review_successor_generation_proven(
    decision: WorkDecision,
    facts: WorkflowFacts,
    exhausted: Sequence[WorkflowJob],
) -> bool:
    """Prove a current exact review generation may replace stale exhaustion.

    Retry exhaustion remains fail closed by default.  The sole automatic
    rearm is a stale review generation whose freshly observed, same-repository
    identity is complete and whose scheduling evidence or action changed.
    This keeps malformed, forked, conflicting, and provider-error evidence on
    the actionable path while allowing ordinary synchronize/base races to
    obtain a fresh generation-scoped budget.
    """

    if (
        len(decision.durable_jobs) != 1
        or decision.durable_jobs[0] not in REVIEW_ACTION_JOBS
    ):
        return False
    if not exhausted or any(
        job.action not in REVIEW_ACTION_JOBS
        or job.failure_category is not WorkflowFailureCategory.STALE_EVIDENCE
        or (
            job.action == decision.durable_jobs[0]
            and job.expected_evidence_revision == decision.evidence_revision
        )
        for job in exhausted
    ):
        return False
    review = _fact_mapping(facts, FactDomain.REVIEW_CI)
    task = _fact_mapping(facts, FactDomain.TASK)
    integration = _fact_mapping(facts, FactDomain.INTEGRATION)
    if review is None or task is None or integration is None:
        return False
    state = str(review.get("state") or "").strip().lower()
    mergeable_state = str(review.get("mergeable_state") or "").strip().lower()
    if (
        state != "open"
        or bool(review.get("source_deleted"))
        or bool(review.get("conflict"))
        or bool(review.get("needs_rebase"))
        or review.get("mergeable") is False
        or mergeable_state in {"dirty", "behind"}
    ):
        return False
    expected_review = str(task.get("review_number") or "").strip()
    expected_head = str(task.get("review_head") or "").strip().lower()
    expected_source = str(
        task.get("work_branch") or task.get("branch_name") or decision.task_id
    ).strip()
    expected_target = str(task.get("target_branch") or "").strip()
    observed_head = str(review.get("head_sha") or "").strip().lower()
    observed_base = str(review.get("base_sha") or "").strip().lower()
    integration_head = str(integration.get("head_sha") or "").strip().lower()
    integration_base = str(integration.get("base_sha") or "").strip().lower()
    integration_target = str(integration.get("base_branch") or "").strip()
    source_repository = str(
        review.get("source_repository") or ""
    ).strip().casefold()
    target_repository = str(
        review.get("target_repository") or ""
    ).strip().casefold()
    return bool(
        str(integration.get("state") or "").strip().lower()
        in ACCEPTED_SUBMISSION_STATES
        and str(integration.get("mode") or "standalone").strip().lower()
        == "standalone"
        and expected_review
        and expected_review == str(review.get("review_id") or "").strip()
        and expected_source
        and expected_source == str(review.get("source_branch") or "").strip()
        and expected_source
        == str(integration.get("task_branch") or "").strip()
        and expected_target
        and expected_target == str(review.get("target_branch") or "").strip()
        and integration_target in {"", expected_target}
        and source_repository
        and source_repository == target_repository
        and _EXACT_HEAD_RE.fullmatch(expected_head)
        and expected_head == integration_head
        and _EXACT_HEAD_RE.fullmatch(observed_head)
        and _EXACT_HEAD_RE.fullmatch(observed_base)
        and (not integration_base or _EXACT_HEAD_RE.fullmatch(integration_base))
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
        liveness_max_task_records: int = DEFAULT_MAX_TASK_RECORDS,
        liveness_max_project_records: int = DEFAULT_MAX_PROJECT_RECORDS,
        liveness_snapshot_stale_seconds: int = DEFAULT_SNAPSHOT_STALE_SECONDS,
        liveness_slo_seconds: Mapping[str, int] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if isinstance(decision_limit, bool) or not 1 <= int(decision_limit) <= MAX_CONTROLLER_LIMIT:
            raise ValueError(f"decision_limit must be between 1 and {MAX_CONTROLLER_LIMIT}")
        if isinstance(max_attempts, bool) or int(max_attempts) < 1:
            raise ValueError("max_attempts must be positive")
        if scheduler is not None and scheduler.store is not store:
            raise ValueError(
                "controller and scheduler must share one workflow job store"
            )
        self.store = store
        self.scheduler = scheduler or WorkflowJobScheduler(
            store=store, decision_limit=int(decision_limit), max_attempts=int(max_attempts)
        )
        self.facts_provider = facts_provider
        self.decision_limit = int(decision_limit)
        self.max_attempts = int(max_attempts)
        self._liveness_lock = threading.RLock()
        self._liveness_policy = build_liveness_policy(liveness_slo_seconds)
        self.scheduler.configure_policy_epoch(self._liveness_policy.epoch)
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self.liveness = WorkflowLivenessTracker(
            max_task_records=liveness_max_task_records,
            max_project_records=liveness_max_project_records,
            snapshot_stale_seconds=liveness_snapshot_stale_seconds,
            policy=self._liveness_policy,
            shared_lock=self._liveness_lock,
            clock=self._clock,
        )
        self._lock = threading.RLock()
        self._evaluated = 0
        self._passes = 0
        self._escalated = 0
        self._last_pass: ControllerPass | None = None
        self._last_error: str | None = None
        self._inflight_generations: set[int] = set()

    @property
    def liveness_policy(self) -> LivenessPolicy:
        with self._liveness_lock:
            return self._liveness_policy

    @property
    def liveness_slo_seconds(self) -> Mapping[str, int]:
        """Read-only compatibility projection of the active policy."""

        with self._liveness_lock:
            return self._liveness_policy.seconds

    @property
    def liveness_observation_lock(self) -> threading.RLock:
        """Lock shared by policy reload, evaluation, and tracker observation."""

        return self._liveness_lock

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
        policy: LivenessPolicy,
        prospective_authority_cut: bool,
    ) -> WorkDecision:
        decision = evaluate_task(
            task,
            facts,
            now=now,
            liveness_slo_seconds=policy.seconds,
        )
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

        # Bind both successor eligibility and ordinary exhaustion handling to
        # one immutable authority read.  A worker may exhaust a replacement
        # generation while this snapshot is being evaluated; independently
        # re-reading here would let proof about the prior rows suppress that
        # replacement's bounded failure.
        current_exhaustion = self.scheduler.store.current_exhausted_jobs(
            project_id=decision.project_id,
            task_id=decision.task_id,
        )
        successor_generation_proven = bool(
            prospective_authority_cut
            and _review_successor_generation_proven(
                decision,
                facts,
                current_exhaustion,
            )
        )
        if _stored_retry_exhausted(
            decision,
            current_exhaustion,
            prospective_authority_cut=prospective_authority_cut,
            successor_generation_proven=successor_generation_proven,
        ) or (
            decision.durable_jobs
            and _retry_exhausted(facts, self.max_attempts)
            and not successor_generation_proven
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

    def _evaluate_with_liveness_facts(
        self,
        tasks: Sequence[Issue | Mapping[str, Any]],
        *,
        facts: FactsSource | None = None,
        facts_by_task: Mapping[Any, WorkflowFacts] | None = None,
        now: datetime | None = None,
        decision_limit: int,
        policy: LivenessPolicy,
        snapshot_generation: int | None = None,
    ) -> tuple[
        tuple[WorkDecision, ...],
        dict[tuple[str, str], DecisionLivenessFacts],
    ]:
        """Evaluate one bounded set and retain its exact deadline facts."""

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
        if len(ordered_candidates) > decision_limit:
            offset = self.store.allocate_decision_window(
                total=len(ordered_candidates),
                limit=decision_limit,
                snapshot_generation=snapshot_generation,
            )
            if offset is None:
                return (), {}
            candidates = (
                ordered_candidates[offset:] + ordered_candidates[:offset]
            )[:decision_limit]
        else:
            candidates = ordered_candidates
        if (
            snapshot_generation is not None
            and not self.scheduler.snapshot_generation_is_current(
                snapshot_generation
            )
        ):
            return (), {}
        cycles = _cycle_members(candidates)
        decisions: list[WorkDecision] = []
        liveness_facts: dict[
            tuple[str, str], DecisionLivenessFacts
        ] = {}
        for task in candidates:
            if (
                snapshot_generation is not None
                and not self.scheduler.snapshot_generation_is_current(
                    snapshot_generation
                )
            ):
                return (), {}
            identity = _task_identity(task)
            try:
                workflow_facts = self._resolve_facts(task, facts)
                decision = self._decide(
                    task,
                    workflow_facts,
                    cycles=cycles,
                    now=current,
                    policy=policy,
                    prospective_authority_cut=(snapshot_generation is not None),
                )
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
                    evaluate_task(
                        task,
                        workflow_facts,
                        now=current,
                        liveness_slo_seconds=policy.seconds,
                    ),
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
            liveness_facts[identity] = DecisionLivenessFacts.from_workflow_facts(
                decision,
                workflow_facts,
            )
        return tuple(decisions), liveness_facts

    def evaluate(
        self,
        tasks: Sequence[Issue | Mapping[str, Any]],
        *,
        facts: FactsSource | None = None,
        facts_by_task: Mapping[Any, WorkflowFacts] | None = None,
        now: datetime | None = None,
    ) -> tuple[WorkDecision, ...]:
        """Evaluate the controller's bounded scheduling window."""

        with self._liveness_lock:
            decisions, _ = self._evaluate_with_liveness_facts(
                tasks,
                facts=facts,
                facts_by_task=facts_by_task,
                now=now,
                decision_limit=self.decision_limit,
                policy=self._liveness_policy,
            )
            with self._lock:
                self._evaluated += len(decisions)
        return decisions

    def _rejected_pass(
        self,
        generation: int,
        decisions: Sequence[WorkDecision] = (),
    ) -> ControllerPass:
        reconciliation = self.scheduler.rejected_snapshot(
            generation, decisions
        )
        return ControllerPass(
            generation,
            (),
            reconciliation,
            (),
            reconciliation.truncated,
        )

    def reconcile(
        self,
        tasks: Sequence[Issue | Mapping[str, Any]],
        *,
        facts: FactsSource | None = None,
        facts_by_task: Mapping[Any, WorkflowFacts] | None = None,
        now: datetime | None = None,
        snapshot_generation: int | None = None,
        source_scan_complete: bool = True,
        source_errors: Mapping[str, str] | None = None,
        excluded_projects: Mapping[str, str] | None = None,
        authoritative_project_ids: Sequence[str] | None = None,
        full_coverage: bool = True,
        persist_liveness_state: Callable[
            [Mapping[str, Any]], None
        ] | None = None,
        publish_projection: Callable[[ControllerPass], Any] | None = None,
    ) -> ControllerPass:
        """Prepare outside the authority lock, then atomically publish once."""

        if snapshot_generation is None:
            generation = self.scheduler.begin_scan()
        else:
            if isinstance(snapshot_generation, bool):
                raise ValueError("snapshot_generation must be positive")
            generation = int(snapshot_generation)
        if generation < 1:
            raise ValueError("snapshot_generation must be positive")
        with self._liveness_lock:
            if not self.scheduler.accept_snapshot_generation(generation):
                return self._rejected_pass(generation)
            self._inflight_generations = {generation}
            policy = self._liveness_policy
        source_scan_complete = bool(source_scan_complete and not source_errors)
        current = now or self._clock()
        if current.tzinfo is None:
            raise ValueError("now must include a timezone")
        current = current.astimezone(timezone.utc)
        all_task_identities = tuple(
            sorted({_task_identity(task) for task in tasks})
        )
        statuses_by_identity: dict[tuple[str, str], set[str]] = {}
        for task in tasks:
            statuses_by_identity.setdefault(_task_identity(task), set()).add(
                _task_status(task)
            )
        expected_identities = tuple(
            sorted(
                {
                    _task_identity(task)
                    for task in tasks
                    if not self._is_final(task)
                }
            )
        )
        if authoritative_project_ids is not None:
            authoritative_projects = tuple(
                sorted(
                    {
                        str(item).strip()
                        for item in authoritative_project_ids
                        if str(item).strip()
                    }
                )
            )
        else:
            task_projects = {
                _task_identity(task)[0]
                for task in tasks
            }
            if not source_scan_complete and not source_errors:
                task_projects.clear()
            if full_coverage and source_scan_complete and not task_projects:
                task_projects.update(
                    project_id
                    for project_id, _task_id, _generation in (
                        self.store.snapshot_membership()
                    )
                )
            authoritative_projects = tuple(
                sorted(task_projects - set(source_errors or {}))
            )
        lifecycle_final_tasks = tuple(
            sorted(
                (
                    *identity,
                    next(iter(statuses)),
                )
                for identity, statuses in statuses_by_identity.items()
                if len(statuses) == 1
                and next(iter(statuses)) in LIFECYCLE_FINAL_STATUSES
                and identity[0] in authoritative_projects
            )
        )
        authority_identities = tuple(
            identity
            for identity in all_task_identities
            if identity[0] in authoritative_projects
        )
        membership_identities = tuple(
            identity
            for identity in expected_identities
            if identity[0] in authoritative_projects
        )
        nonfinal_count = len(expected_identities)
        evaluation_limit = self.decision_limit
        if full_coverage and nonfinal_count <= self.liveness.max_task_records:
            evaluation_limit = max(evaluation_limit, nonfinal_count)
        decisions, decision_liveness_facts = self._evaluate_with_liveness_facts(
            tasks,
            facts=facts,
            facts_by_task=facts_by_task,
            now=current,
            decision_limit=evaluation_limit,
            policy=policy,
            snapshot_generation=generation,
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
        with self._liveness_lock:
            if (
                self._liveness_policy is not policy
                or not self.scheduler.snapshot_generation_is_current(
                    generation
                )
            ):
                self._inflight_generations.discard(generation)
                return self._rejected_pass(generation, decisions)
            with self.store.snapshot_authority_guard():
                # A degraded source scan has no authoritative project-wide
                # membership, yet it may still materialize the evaluated
                # task-local recovery jobs. Capture that narrower scope so
                # publication failure can restore it.
                authority_is_project_wide = bool(
                    full_coverage and authoritative_projects
                )
                authority_checkpoint = self.store.capture_snapshot_authority(
                    authoritative_project_ids=(
                        authoritative_projects if authority_is_project_wide else ()
                    ),
                    evaluated_identities=authority_identities,
                    full_project_scope=authority_is_project_wide,
                )
                try:
                    reconciliation = self.scheduler.reconcile_accepted(
                        decisions,
                        snapshot_generation=generation,
                        record_metrics=False,
                        authoritative_project_ids=(
                            authoritative_projects if full_coverage else None
                        ),
                        expected_identities=(
                            membership_identities if full_coverage else None
                        ),
                        lifecycle_final_tasks=(
                            lifecycle_final_tasks if full_coverage else ()
                        ),
                    )
                except Exception:
                    # Reconciliation intentionally uses several short SQLite
                    # transactions.  A later write can therefore fail after an
                    # earlier membership, cursor, or job write committed.  Put
                    # the last published authority back before the caller turns
                    # this accepted generation into a durable scan-failure
                    # publication.  If restoration itself cannot be proven,
                    # discard the in-memory handoff: the accepted-but-unpublished
                    # generation then remains ineligible for worker claims.
                    try:
                        restored = self.store.restore_snapshot_authority(
                            authority_checkpoint,
                            snapshot_generation=generation,
                        )
                    except Exception:
                        self._inflight_generations.discard(generation)
                        raise
                    if not restored:
                        self._inflight_generations.discard(generation)
                        raise RuntimeError(
                            "failed workflow reconciliation could not restore "
                            "its durable authority checkpoint"
                        )
                    raise
                if (
                    not reconciliation.snapshot_accepted
                    or self._liveness_policy is not policy
                ):
                    self._inflight_generations.discard(generation)
                    return self._rejected_pass(generation, decisions)
                result = ControllerPass(
                    generation,
                    decisions,
                    reconciliation,
                    escalations,
                    (
                        reconciliation.truncated
                        or len(decisions) < nonfinal_count
                        or not source_scan_complete
                    ),
                )

                def rollback_authority() -> None:
                    self.store.restore_snapshot_authority(
                        authority_checkpoint,
                        snapshot_generation=generation,
                    )

                projection_publication: Any | None = None

                def publish() -> WorkflowSnapshotPublication:
                    nonlocal projection_publication
                    if not full_coverage:
                        return WorkflowSnapshotPublication(
                            rollback_authority=rollback_authority
                        )
                    checkpoint = self.liveness.transaction_checkpoint()
                    prior_state = self.liveness.to_state()

                    def rollback() -> None:
                        rollback_errors: list[Exception] = []
                        if projection_publication is not None:
                            try:
                                projection_publication.rollback()
                            except Exception as exc:
                                rollback_errors.append(exc)
                        try:
                            self.liveness.restore_transaction_checkpoint(checkpoint)
                        except Exception as exc:
                            rollback_errors.append(exc)
                        if persist_liveness_state is not None:
                            try:
                                persist_liveness_state(prior_state)
                            except Exception as exc:
                                rollback_errors.append(exc)
                        if len(rollback_errors) == 1:
                            raise rollback_errors[0]
                        if rollback_errors:
                            raise ExceptionGroup(
                                "workflow snapshot compensators failed",
                                rollback_errors,
                            )

                    try:
                        self.liveness.observe(
                            decisions,
                            expected_identities=expected_identities,
                            snapshot_generation=generation,
                            source_scan_complete=source_scan_complete,
                            reconciliation_complete=(
                                reconciliation.jobs_required
                                == reconciliation.jobs_materialized
                                and reconciliation.schedules_required
                                == reconciliation.schedules_materialized
                            ),
                            required_recovery_count=(
                                reconciliation.jobs_required
                            ),
                            materialized_recovery_count=(
                                reconciliation.jobs_materialized
                            ),
                            decision_facts=decision_liveness_facts,
                            source_errors=source_errors,
                            excluded_projects=excluded_projects,
                            now=current,
                        )
                        if persist_liveness_state is not None:
                            persist_liveness_state(
                                self.liveness.to_state()
                            )
                        if publish_projection is not None:
                            projection_publication = publish_projection(result)
                            if not bool(
                                getattr(projection_publication, "accepted", False)
                            ):
                                raise WorkflowProjectionPublicationRejected(
                                    str(
                                        getattr(
                                            projection_publication,
                                            "rejection",
                                            None,
                                        )
                                        or "projection_rejected"
                                    )
                                )
                            # Publish cache memory before returning control to
                            # the job-store transaction. A waiting worker can
                            # observe the committed generation as soon as that
                            # transaction releases its authority guard, so the
                            # matching canonical projection must already be
                            # visible. The publication rollback below restores
                            # both memory and durable availability if the
                            # SQLite marker commit subsequently fails.
                            projection_publication.commit_memory()
                    except Exception:
                        rollback()
                        raise
                    return WorkflowSnapshotPublication(
                        rollback=rollback,
                        rollback_authority=rollback_authority,
                    )

                try:
                    published, _ = self.store.publish_snapshot_generation(
                        generation,
                        publish,
                        rollback_authority=rollback_authority,
                    )
                except Exception:
                    # Keep the accepted in-memory handoff until the caller has
                    # a chance to publish a versioned scan failure.  Durable
                    # compensation reset store acceptance to the prior
                    # published generation, so record_liveness_scan_failure()
                    # will re-accept this capture only when no newer scan has
                    # superseded it.
                    raise
                if not published:
                    self._inflight_generations.discard(generation)
                    return self._rejected_pass(generation, decisions)
                self.scheduler.record_reconcile_metrics(reconciliation)
                with self._lock:
                    self._evaluated += len(decisions)
                    self._passes += 1
                    self._escalated += len(escalations)
                    self._last_pass = result
                    self._last_error = None
                self._inflight_generations.discard(generation)
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
            tasks,
            facts=facts,
            facts_by_task=facts_by_task,
            now=now,
            full_coverage=False,
        )

    def full_sync(
        self,
        tasks: Sequence[Issue | Mapping[str, Any]],
        *,
        facts: FactsSource | None = None,
        facts_by_task: Mapping[Any, WorkflowFacts] | None = None,
        now: datetime | None = None,
        source_scan_complete: bool = True,
        source_errors: Mapping[str, str] | None = None,
        excluded_projects: Mapping[str, str] | None = None,
        authoritative_project_ids: Sequence[str] | None = None,
        snapshot_generation: int | None = None,
        persist_liveness_state: Callable[
            [Mapping[str, Any]], None
        ] | None = None,
        publish_projection: Callable[[ControllerPass], Any] | None = None,
    ) -> ControllerPass:
        """Run the bounded correctness pass used as the liveness safety net."""

        return self.reconcile(
            tasks,
            facts=facts,
            facts_by_task=facts_by_task,
            now=now,
            source_scan_complete=source_scan_complete,
            source_errors=source_errors,
            excluded_projects=excluded_projects,
            authoritative_project_ids=authoritative_project_ids,
            full_coverage=True,
            snapshot_generation=snapshot_generation,
            persist_liveness_state=persist_liveness_state,
            publish_projection=publish_projection,
        )

    def prepare_runtime_observation(
        self,
        tasks: Sequence[Issue | Mapping[str, Any]],
        *,
        snapshot_generation: int,
        facts: FactsSource | None = None,
        facts_by_task: Mapping[Any, WorkflowFacts] | None = None,
        now: datetime | None = None,
        source_scan_complete: bool = True,
        source_errors: Mapping[str, str] | None = None,
        excluded_projects: Mapping[str, str] | None = None,
    ) -> ControllerObservation | None:
        """Prepare totality evidence without reconciling durable jobs.

        Production ``WorkflowRuntime`` has already accepted ``generation``
        and its domain controllers are the sole job authority.  Returning
        ``None`` fences a stale generation or concurrent policy cut without
        mutating liveness state.
        """

        if isinstance(snapshot_generation, bool) or int(snapshot_generation) < 1:
            raise ValueError("snapshot_generation must be positive")
        generation = int(snapshot_generation)
        current = now or self._clock()
        if current.tzinfo is None:
            raise ValueError("now must include a timezone")
        current = current.astimezone(timezone.utc)
        errors = {
            str(project_id): str(error)
            for project_id, error in (source_errors or {}).items()
        }
        complete = bool(source_scan_complete and not errors)
        excluded = {
            str(project_id): str(reason or "excluded")
            for project_id, reason in (excluded_projects or {}).items()
        }
        expected = tuple(
            sorted(
                {
                    _task_identity(task)
                    for task in tasks
                    if not self._is_final(task)
                }
            )
        )
        with self._liveness_lock:
            if not self.scheduler.snapshot_generation_is_current(generation):
                return None
            policy = self._liveness_policy
            evaluation_limit = self.decision_limit
            if len(expected) <= self.liveness.max_task_records:
                evaluation_limit = max(evaluation_limit, len(expected))
            decisions, decision_facts = self._evaluate_with_liveness_facts(
                tasks,
                facts=facts,
                facts_by_task=facts_by_task,
                now=current,
                decision_limit=evaluation_limit,
                policy=policy,
                snapshot_generation=generation,
            )
            if (
                self._liveness_policy is not policy
                or not self.scheduler.snapshot_generation_is_current(generation)
            ):
                return None
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
            self._inflight_generations.add(generation)
            return ControllerObservation(
                generation,
                decisions,
                decision_facts,
                expected,
                escalations,
                complete,
                errors,
                excluded,
                current,
                policy.epoch,
            )

    def stage_runtime_observation(
        self,
        observation: ControllerObservation,
        *,
        reconciliation: WorkflowReconcileResult,
        persist_liveness_state: Callable[[Mapping[str, Any]], None] | None = None,
    ) -> WorkflowSnapshotPublication:
        """Stage liveness for the runtime's existing snapshot transaction."""

        generation = observation.snapshot_generation
        with self._liveness_lock:
            if (
                generation not in self._inflight_generations
                or observation.policy_epoch != self._liveness_policy.epoch
                or not self.scheduler.snapshot_generation_is_current(generation)
                or not reconciliation.snapshot_accepted
                or reconciliation.snapshot_generation != generation
            ):
                raise WorkflowProjectionPublicationRejected(
                    "stale_runtime_observation"
                )
            checkpoint = self.liveness.transaction_checkpoint()
            prior_state = self.liveness.to_state()

            def rollback() -> None:
                self.liveness.restore_transaction_checkpoint(checkpoint)
                if persist_liveness_state is not None:
                    persist_liveness_state(prior_state)

            result = ControllerPass(
                generation,
                observation.decisions,
                reconciliation,
                observation.escalations,
                observation.truncated or reconciliation.truncated,
            )
            try:
                self.liveness.observe(
                    observation.decisions,
                    expected_identities=observation.expected_identities,
                    snapshot_generation=generation,
                    source_scan_complete=observation.source_scan_complete,
                    reconciliation_complete=(
                        reconciliation.jobs_required
                        == reconciliation.jobs_materialized
                        and reconciliation.schedules_required
                        == reconciliation.schedules_materialized
                    ),
                    required_recovery_count=reconciliation.jobs_required,
                    materialized_recovery_count=(
                        reconciliation.jobs_materialized
                    ),
                    decision_facts=observation.decision_facts,
                    source_errors=observation.source_errors,
                    excluded_projects=observation.excluded_projects,
                    source_scan_deferred=observation.source_scan_deferred,
                    now=observation.observed_at,
                )
                if persist_liveness_state is not None:
                    persist_liveness_state(self.liveness.to_state())
            except Exception:
                rollback()
                raise
            return WorkflowSnapshotPublication(result=result, rollback=rollback)

    def commit_runtime_observation(
        self, observation: ControllerObservation, result: ControllerPass
    ) -> bool:
        """Publish post-marker counters without reopening committed authority.

        The durable snapshot marker and liveness state are already committed
        when this method runs.  Bookkeeping must therefore be best-effort:
        rejecting or raising here would incorrectly route a successful
        publication through pre-commit compensation.
        """

        with self._liveness_lock:
            if observation.snapshot_generation != result.snapshot_generation:
                logger.error(
                    "Runtime liveness bookkeeping generation mismatch: %s != %s",
                    observation.snapshot_generation,
                    result.snapshot_generation,
                )
                self._inflight_generations.discard(
                    observation.snapshot_generation
                )
                return False
            try:
                with self._lock:
                    self._evaluated += len(result.decisions)
                    self._passes += 1
                    self._escalated += len(result.escalations)
                    self._last_pass = result
                    self._last_error = None
            except Exception:  # pragma: no cover - defensive post-commit fence
                logger.exception(
                    "Runtime liveness bookkeeping failed after snapshot commit"
                )
                return False
            finally:
                self._inflight_generations.discard(
                    observation.snapshot_generation
                )
            return True

    def abort_runtime_observation(self, snapshot_generation: int) -> None:
        """Discard one uncommitted runtime observation handoff."""

        with self._liveness_lock:
            self._inflight_generations.discard(int(snapshot_generation))

    def begin_scan(self) -> int:
        """Capture a global generation before any tracker source is read."""

        return self.scheduler.begin_scan()

    def invalidate_inflight_scans(self) -> int:
        """Fence prepared work before an atomic policy/config reload."""

        return self.scheduler.begin_scan()

    def recover_startup(self) -> dict[str, int]:
        """Reconstruct durable ownership after an exclusive restart."""

        return self.scheduler.recover_startup(abandoned=True)

    def restore_liveness_state(self, raw: object) -> None:
        """Restore persisted ages while requiring a fresh coverage cycle."""

        with self._liveness_lock:
            self.liveness.restore(raw)

    def reconfigure_liveness(
        self,
        *,
        max_task_records: int,
        max_project_records: int,
        snapshot_stale_seconds: int,
        slo_seconds: Mapping[str, int] | None = None,
        persist_liveness_state: Callable[
            [Mapping[str, Any]], None
        ] | None = None,
    ) -> None:
        """Apply live liveness settings without losing persisted task ages.

        When supplied, ``persist_liveness_state`` participates in the policy
        cut.  A persistence failure restores the exact prior tracker limits,
        policy, records, and counters before the liveness lock is released.
        The durable scan-generation bump follows persistence, so a rejected
        state-file write does not disturb the prior job authority.
        """

        with self._liveness_lock:
            checkpoint = self.liveness.transaction_checkpoint()
            previous_policy = self._liveness_policy
            previous_scheduler_epoch = self.scheduler.policy_epoch
            previous_limits = (
                self.liveness.max_task_records,
                self.liveness.max_project_records,
                self.liveness.snapshot_stale_seconds,
            )
            replacement = (
                build_liveness_policy(slo_seconds)
                if slo_seconds is not None
                else self._liveness_policy
            )
            try:
                self.liveness.reconfigure(
                    max_task_records=max_task_records,
                    max_project_records=max_project_records,
                    snapshot_stale_seconds=snapshot_stale_seconds,
                    policy=replacement,
                )
                self._liveness_policy = replacement
                if persist_liveness_state is not None:
                    persist_liveness_state(self.liveness.to_state())
                self.invalidate_inflight_scans()
                self.scheduler.configure_policy_epoch(replacement.epoch)
                self._inflight_generations.clear()
            except Exception:
                self.liveness.reconfigure(
                    max_task_records=previous_limits[0],
                    max_project_records=previous_limits[1],
                    snapshot_stale_seconds=previous_limits[2],
                    policy=previous_policy,
                )
                self.liveness.restore_transaction_checkpoint(checkpoint)
                self._liveness_policy = previous_policy
                self.scheduler.configure_policy_epoch(
                    previous_scheduler_epoch
                )
                raise

    def record_liveness_scan_failure(
        self,
        error: str,
        *,
        snapshot_generation: int | None = None,
        persist_liveness_state: Callable[
            [Mapping[str, Any]], None
        ] | None = None,
    ) -> WorkflowLivenessHealth:
        """Version and durably publish a current source-scan failure."""

        generation = (
            self.scheduler.begin_scan()
            if snapshot_generation is None
            else snapshot_generation
        )
        if isinstance(generation, bool) or int(generation) < 1:
            raise ValueError("snapshot_generation must be positive")
        generation = int(generation)
        with self._liveness_lock:
            current_health = self.liveness.snapshot()
            self._inflight_generations.discard(generation)
            if (
                current_health.snapshot_generation is not None
                and generation <= current_health.snapshot_generation
            ):
                return current_health
            if not self.scheduler.snapshot_generation_is_current(generation):
                # A failed publication compensates acceptance back to the last
                # published marker. Re-accept the same capture only if it is
                # still the newest allocation; a reload/new scan makes this
                # fail closed without publishing stale failure authority.
                if not self.scheduler.accept_snapshot_generation(generation):
                    return current_health

            def publish_failure() -> WorkflowSnapshotPublication:
                checkpoint = self.liveness.transaction_checkpoint()
                prior_state = self.liveness.to_state()

                def rollback() -> None:
                    self.liveness.restore_transaction_checkpoint(checkpoint)
                    if persist_liveness_state is not None:
                        persist_liveness_state(prior_state)

                try:
                    health = self.liveness.record_scan_failure(
                        error,
                        snapshot_generation=generation,
                    )
                    if persist_liveness_state is not None:
                        persist_liveness_state(self.liveness.to_state())
                except Exception:
                    rollback()
                    raise
                return WorkflowSnapshotPublication(
                    result=health,
                    rollback=rollback,
                )

            published, health = self.store.publish_snapshot_generation(
                generation, publish_failure
            )
            return (
                health
                if published and isinstance(health, WorkflowLivenessHealth)
                else current_health
            )

    def liveness_snapshot(self) -> WorkflowLivenessHealth:
        return self.liveness.snapshot()

    def liveness_state(self) -> dict[str, Any]:
        return self.liveness.to_state()

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
        return {
            "controller": summary,
            "liveness": self.liveness.snapshot().to_dict(),
            **self.scheduler.health_snapshot(),
        }


# Short aliases make the policy boundary discoverable without creating two
# implementations or two state stores.
UniversalWorkflowController = UniversalTotalityLivenessController
TotalityLivenessController = UniversalTotalityLivenessController


__all__ = [
    "ControllerObservation",
    "ControllerEscalation",
    "ControllerPass",
    "WorkflowProjectionPublicationRejected",
    "UniversalTotalityLivenessController",
    "UniversalWorkflowController",
    "TotalityLivenessController",
]
