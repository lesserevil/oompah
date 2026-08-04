"""Authoritative contract for the main task lifecycle.

This module deliberately separates the business status stored by the tracker
from the execution phase and disposition that the workflow engine derives
from it.  A status is durable business history; a phase/disposition describes
which subsystem owns the next action and how liveness is maintained.

The contract is data, not an enforcement implementation.  Transition writers
and reconcilers can import the tables below while they are migrated to the
single transition service.  Keeping the complete graph and its invariants in
one dependency-light module prevents each subsystem from inventing a subtly
different lifecycle.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType


# Canonical tracker statuses.  ``oompah.statuses`` re-exports these names as a
# compatibility facade; new lifecycle code should import this module.
PROPOSED = "Proposed"
BACKLOG = "Backlog"
OPEN = "Open"
IN_PROGRESS = "In Progress"
NEEDS_ANSWER = "Needs Answer"
NEEDS_HUMAN = "Needs Human"
NEEDS_CI_FIX = "Needs CI Fix"
NEEDS_REBASE = "Needs Rebase"
IN_REVIEW = "In Review"
IN_VALIDATION = "In Validation"
READY_TO_INTEGRATE = "Ready to Integrate"
DECOMPOSED = "Decomposed"
DUPLICATE_CANDIDATE = "Duplicate Candidate"
DONE = "Done"
MERGED = "Merged"
ARCHIVED = "Archived"

CANONICAL_STATUSES: tuple[str, ...] = (
    PROPOSED,
    BACKLOG,
    OPEN,
    IN_PROGRESS,
    NEEDS_ANSWER,
    NEEDS_HUMAN,
    NEEDS_CI_FIX,
    NEEDS_REBASE,
    IN_REVIEW,
    IN_VALIDATION,
    READY_TO_INTEGRATE,
    DECOMPOSED,
    DUPLICATE_CANDIDATE,
    DONE,
    MERGED,
    ARCHIVED,
)

DEFAULT_STATUS = BACKLOG


class ExecutionPhase(str, Enum):
    """Subsystem phase responsible for advancing a task."""

    INTAKE = "intake"
    PRIORITIZATION = "prioritization"
    DISPATCH = "dispatch"
    IMPLEMENTATION = "implementation"
    WAITING = "waiting"
    REPAIR = "repair"
    REVIEW = "review"
    VALIDATION = "validation"
    INTEGRATION = "integration"
    ROLLUP = "rollup"
    DUPLICATE_REVIEW = "duplicate_review"
    COMPLETE = "complete"


class TaskDisposition(str, Enum):
    """Total high-level answer to "what can make this task advance?"""

    RUNNABLE = "runnable"
    OWNED = "owned"
    BLOCKED = "blocked"
    RETRY_SCHEDULED = "retry_scheduled"
    ACTION_REQUIRED = "action_required"
    TERMINAL = "terminal"


class WorkflowOwner(str, Enum):
    """Authority expected to own the next action for a status."""

    INTAKE = "intake"
    PROJECT_OWNER = "project_owner"
    DISPATCHER = "dispatcher"
    IMPLEMENTER = "implementer"
    DIRECT_OWNER = "direct_owner"
    REQUESTOR = "requestor"
    OPERATOR = "operator"
    REPAIR_WORKER = "repair_worker"
    REVIEW_MONITOR = "review_monitor"
    AUDITOR = "auditor"
    INTEGRATOR = "integrator"
    ROLLUP = "rollup"
    DUPLICATE_INVESTIGATOR = "duplicate_investigator"
    NONE = "none"


class ReassessmentTrigger(str, Enum):
    """Durable event or timer that causes a status to be reconsidered."""

    INTAKE_EVENT = "intake_event"
    OWNER_PROMOTION = "owner_promotion"
    DISPATCH_TICK = "dispatch_tick"
    LEASE_EXPIRY = "lease_expiry"
    REQUESTOR_RESPONSE = "requestor_response"
    OPERATOR_ACTION = "operator_action"
    RETRY_DUE = "retry_due"
    REVIEW_EVENT_OR_POLL = "review_event_or_poll"
    AUDIT_EVENT_OR_LEASE = "audit_event_or_lease"
    INTEGRATION_JOB_OR_LEASE = "integration_job_or_lease"
    CHILD_OR_DEPENDENCY_EVENT = "child_or_dependency_event"
    DUPLICATE_VERDICT_OR_LEASE = "duplicate_verdict_or_lease"
    LANDING_EVENT_OR_POLL = "landing_event_or_poll"
    NEVER = "never"


class TransitionRequirement(str, Enum):
    """Evidence required before a transition may commit."""

    ACTIONABLE_DESCRIPTION = "actionable_description"
    PROJECT_OWNER_AUTHORITY = "project_owner_authority"
    DEPENDENCIES_SATISFIED = "dependencies_satisfied"
    VALID_OWNER_LEASE = "valid_owner_lease"
    IMPLEMENTATION_GENERATION = "implementation_generation"
    ACCEPTED_SUBMISSION = "accepted_submission"
    REVIEW_EVIDENCE = "review_evidence"
    AUDIT_REQUEST = "audit_request"
    AUDIT_PASS = "audit_pass"
    LANDING_EVIDENCE = "landing_evidence"
    CONTAINMENT_EVIDENCE = "containment_evidence"
    CHILDREN_CREATED = "children_created"
    CHILDREN_COMPLETE = "children_complete"
    DUPLICATE_VERDICT = "duplicate_verdict"
    OPERATOR_REASON = "operator_reason"
    EXPECTED_VERSION = "expected_version"


@dataclass(frozen=True, slots=True)
class ReassessmentContract:
    """How a non-final task is guaranteed another decision opportunity."""

    trigger: ReassessmentTrigger
    slo_key: str | None
    stall_reason_code: str | None
    durable: bool = True


@dataclass(frozen=True, slots=True)
class StatusContract:
    """Lifecycle meaning shared by every workflow subsystem."""

    status: str
    phase: ExecutionPhase
    disposition: TaskDisposition
    owners: frozenset[WorkflowOwner]
    reassessment: ReassessmentContract
    dispatchable: bool = False
    working: bool = False
    waiting: bool = False
    review: bool = False
    tracker_terminal: bool = False
    lifecycle_final: bool = False
    blocked_by: str | None = None


@dataclass(frozen=True, slots=True)
class TransitionRule:
    """One legal edge in the canonical status graph."""

    from_status: str
    to_status: str
    requirements: frozenset[TransitionRequirement]
    reason_code: str
    idempotent: bool = False


@dataclass(frozen=True, slots=True)
class WorkflowInvariant:
    """Machine-addressable safety or eventual-progress invariant."""

    code: str
    kind: str
    description: str
    applies_to: frozenset[TaskDisposition] = frozenset()


def _reassessment(
    trigger: ReassessmentTrigger,
    slo_key: str | None,
    reason: str | None,
    *,
    durable: bool = True,
) -> ReassessmentContract:
    return ReassessmentContract(trigger, slo_key, reason, durable)


# Status-only dispositions are the default interpretation.  The later
# WorkDecision evaluator refines them with facts (for example an Open task with
# an unmet hard-start dependency becomes BLOCKED rather than RUNNABLE).
STATUS_CONTRACTS: Mapping[str, StatusContract] = MappingProxyType(
    {
        PROPOSED: StatusContract(
            PROPOSED,
            ExecutionPhase.INTAKE,
            TaskDisposition.BLOCKED,
            frozenset({WorkflowOwner.INTAKE}),
            _reassessment(
                ReassessmentTrigger.INTAKE_EVENT,
                "intake_reassessment",
                "awaiting_intake_decision",
            ),
            blocked_by="intake_acceptance",
        ),
        BACKLOG: StatusContract(
            BACKLOG,
            ExecutionPhase.PRIORITIZATION,
            TaskDisposition.BLOCKED,
            frozenset({WorkflowOwner.PROJECT_OWNER}),
            _reassessment(
                ReassessmentTrigger.OWNER_PROMOTION,
                "prioritization_visibility",
                "awaiting_owner_promotion",
            ),
            blocked_by="project_owner_priority",
        ),
        OPEN: StatusContract(
            OPEN,
            ExecutionPhase.DISPATCH,
            TaskDisposition.RUNNABLE,
            frozenset({WorkflowOwner.DISPATCHER}),
            _reassessment(
                ReassessmentTrigger.DISPATCH_TICK,
                "dispatch_latency",
                "dispatch_not_selected",
            ),
            dispatchable=True,
        ),
        IN_PROGRESS: StatusContract(
            IN_PROGRESS,
            ExecutionPhase.IMPLEMENTATION,
            TaskDisposition.OWNED,
            frozenset({WorkflowOwner.IMPLEMENTER, WorkflowOwner.DIRECT_OWNER}),
            _reassessment(
                ReassessmentTrigger.LEASE_EXPIRY,
                "implementation_lease",
                "implementation_owner_stale",
            ),
            working=True,
        ),
        NEEDS_ANSWER: StatusContract(
            NEEDS_ANSWER,
            ExecutionPhase.WAITING,
            TaskDisposition.ACTION_REQUIRED,
            frozenset({WorkflowOwner.REQUESTOR}),
            _reassessment(
                ReassessmentTrigger.REQUESTOR_RESPONSE,
                "requestor_visibility",
                "awaiting_requestor_answer",
            ),
            waiting=True,
            blocked_by="requestor_answer",
        ),
        NEEDS_HUMAN: StatusContract(
            NEEDS_HUMAN,
            ExecutionPhase.WAITING,
            TaskDisposition.ACTION_REQUIRED,
            frozenset({WorkflowOwner.OPERATOR}),
            _reassessment(
                ReassessmentTrigger.OPERATOR_ACTION,
                "operator_visibility",
                "awaiting_operator_action",
            ),
            waiting=True,
            blocked_by="operator_action",
        ),
        NEEDS_CI_FIX: StatusContract(
            NEEDS_CI_FIX,
            ExecutionPhase.REPAIR,
            TaskDisposition.RUNNABLE,
            frozenset({WorkflowOwner.REPAIR_WORKER, WorkflowOwner.DISPATCHER}),
            _reassessment(
                ReassessmentTrigger.DISPATCH_TICK,
                "repair_dispatch_latency",
                "ci_repair_not_selected",
            ),
            dispatchable=True,
            review=True,
        ),
        NEEDS_REBASE: StatusContract(
            NEEDS_REBASE,
            ExecutionPhase.REPAIR,
            TaskDisposition.RUNNABLE,
            frozenset({WorkflowOwner.REPAIR_WORKER, WorkflowOwner.DISPATCHER}),
            _reassessment(
                ReassessmentTrigger.DISPATCH_TICK,
                "repair_dispatch_latency",
                "rebase_repair_not_selected",
            ),
            dispatchable=True,
            review=True,
        ),
        IN_REVIEW: StatusContract(
            IN_REVIEW,
            ExecutionPhase.REVIEW,
            TaskDisposition.OWNED,
            frozenset({WorkflowOwner.REVIEW_MONITOR}),
            _reassessment(
                ReassessmentTrigger.REVIEW_EVENT_OR_POLL,
                "review_reassessment",
                "review_monitor_stale",
            ),
            review=True,
        ),
        IN_VALIDATION: StatusContract(
            IN_VALIDATION,
            ExecutionPhase.VALIDATION,
            TaskDisposition.OWNED,
            frozenset({WorkflowOwner.AUDITOR}),
            _reassessment(
                ReassessmentTrigger.AUDIT_EVENT_OR_LEASE,
                "audit_lease",
                "audit_owner_stale",
            ),
        ),
        READY_TO_INTEGRATE: StatusContract(
            READY_TO_INTEGRATE,
            ExecutionPhase.INTEGRATION,
            TaskDisposition.RETRY_SCHEDULED,
            frozenset({WorkflowOwner.INTEGRATOR}),
            _reassessment(
                ReassessmentTrigger.INTEGRATION_JOB_OR_LEASE,
                "integration_lease",
                "integration_job_stale",
            ),
        ),
        DECOMPOSED: StatusContract(
            DECOMPOSED,
            ExecutionPhase.ROLLUP,
            TaskDisposition.BLOCKED,
            frozenset({WorkflowOwner.ROLLUP}),
            _reassessment(
                ReassessmentTrigger.CHILD_OR_DEPENDENCY_EVENT,
                "rollup_reassessment",
                "decomposed_children_stale",
            ),
            blocked_by="child_completion",
        ),
        DUPLICATE_CANDIDATE: StatusContract(
            DUPLICATE_CANDIDATE,
            ExecutionPhase.DUPLICATE_REVIEW,
            TaskDisposition.OWNED,
            frozenset({WorkflowOwner.DUPLICATE_INVESTIGATOR}),
            _reassessment(
                ReassessmentTrigger.DUPLICATE_VERDICT_OR_LEASE,
                "duplicate_investigation_lease",
                "duplicate_investigation_stale",
            ),
        ),
        DONE: StatusContract(
            DONE,
            ExecutionPhase.COMPLETE,
            TaskDisposition.TERMINAL,
            frozenset({WorkflowOwner.ROLLUP}),
            _reassessment(
                ReassessmentTrigger.LANDING_EVENT_OR_POLL,
                "landing_reassessment",
                "completed_work_not_landed",
            ),
            tracker_terminal=True,
        ),
        MERGED: StatusContract(
            MERGED,
            ExecutionPhase.COMPLETE,
            TaskDisposition.TERMINAL,
            frozenset({WorkflowOwner.NONE}),
            _reassessment(ReassessmentTrigger.NEVER, None, None),
            tracker_terminal=True,
            lifecycle_final=True,
        ),
        ARCHIVED: StatusContract(
            ARCHIVED,
            ExecutionPhase.COMPLETE,
            TaskDisposition.TERMINAL,
            frozenset({WorkflowOwner.NONE}),
            _reassessment(ReassessmentTrigger.NEVER, None, None),
            tracker_terminal=True,
            lifecycle_final=True,
        ),
    }
)


# Compatibility categories are projections of the authoritative table, not a
# second set of handwritten lifecycle decisions.
DISPATCHABLE_STATUSES: frozenset[str] = frozenset(
    status for status, contract in STATUS_CONTRACTS.items() if contract.dispatchable
)
WORKING_STATUSES: frozenset[str] = frozenset(
    status for status, contract in STATUS_CONTRACTS.items() if contract.working
)
WAITING_STATUSES: frozenset[str] = frozenset(
    status for status, contract in STATUS_CONTRACTS.items() if contract.waiting
)
REVIEW_STATUSES: frozenset[str] = frozenset(
    status for status, contract in STATUS_CONTRACTS.items() if contract.review
)
TERMINAL_STATUSES: frozenset[str] = frozenset(
    status for status, contract in STATUS_CONTRACTS.items() if contract.tracker_terminal
)
LIFECYCLE_FINAL_STATUSES: frozenset[str] = frozenset(
    status for status, contract in STATUS_CONTRACTS.items() if contract.lifecycle_final
)


def status_key(status: str | None) -> str:
    return str(status or "").strip().lower().replace("-", " ").replace("_", " ")


STATUS_ALIASES: Mapping[str, str] = MappingProxyType(
    {
        "": DEFAULT_STATUS,
        "proposed": PROPOSED,
        "to do": BACKLOG,
        "todo": BACKLOG,
        "deferred": BACKLOG,
        "backlog": BACKLOG,
        "open": OPEN,
        "in progress": IN_PROGRESS,
        "doing": IN_PROGRESS,
        "started": IN_PROGRESS,
        "asking question": NEEDS_ANSWER,
        "needs answer": NEEDS_ANSWER,
        "needs info": NEEDS_ANSWER,
        "needs information": NEEDS_ANSWER,
        "human only": NEEDS_HUMAN,
        "needs human": NEEDS_HUMAN,
        "ci fix": NEEDS_CI_FIX,
        "needs ci fix": NEEDS_CI_FIX,
        "merge conflict": NEEDS_REBASE,
        "needs rebase": NEEDS_REBASE,
        "in review": IN_REVIEW,
        "review": IN_REVIEW,
        "in validation": IN_VALIDATION,
        "validation": IN_VALIDATION,
        "ready to integrate": READY_TO_INTEGRATE,
        "ready for integration": READY_TO_INTEGRATE,
        "decomposed": DECOMPOSED,
        "duplicate candidate": DUPLICATE_CANDIDATE,
        "closed": DONE,
        "done": DONE,
        "merged": MERGED,
        "archive:yes": ARCHIVED,
        "archived": ARCHIVED,
    }
)


def canonicalize_status(status: str | None) -> str:
    """Return the canonical status for a user- or tracker-supplied value."""

    key = status_key(status)
    return STATUS_ALIASES.get(
        key,
        str(status or DEFAULT_STATUS).strip() or DEFAULT_STATUS,
    )


def canonical_statuses_with(existing: Iterable[str] | None = None) -> list[str]:
    """Return canonical statuses followed by distinct custom statuses."""

    values = list(CANONICAL_STATUSES)
    seen = {status_key(value) for value in values}
    for raw in existing or []:
        value = str(raw).strip()
        if not value:
            continue
        canonical = canonicalize_status(value)
        key = status_key(canonical)
        if key in seen:
            continue
        seen.add(key)
        values.append(value)
    return values


def status_contract(status: str | None) -> StatusContract | None:
    """Return the contract for a canonical/aliased status, or ``None``."""

    return STATUS_CONTRACTS.get(canonicalize_status(status))


def is_dispatchable_status(status: str | None) -> bool:
    contract = status_contract(status)
    return bool(contract and contract.dispatchable)


def is_working_status(status: str | None) -> bool:
    contract = status_contract(status)
    return bool(contract and contract.working)


def is_terminal_status(status: str | None) -> bool:
    contract = status_contract(status)
    return bool(contract and contract.tracker_terminal)


def is_lifecycle_final_status(status: str | None) -> bool:
    contract = status_contract(status)
    return bool(contract and contract.lifecycle_final)


_STATUS_RANK = {status: index for index, status in enumerate(CANONICAL_STATUSES)}


def status_rank(status: str | None) -> int:
    """Position of *status* in the compatibility display order, or ``-1``."""

    return _STATUS_RANK.get(canonicalize_status(status), -1)


def more_advanced_status(a: str | None, b: str | None) -> str:
    """Return whichever status is later in the compatibility display order."""

    return a if status_rank(a) >= status_rank(b) else b  # type: ignore[return-value]


# The table is intentionally permissive enough to describe existing recovery
# paths.  Enforcement may impose additional evidence requirements from
# ``TRANSITION_RULES`` but must never invent an edge outside this graph.
VALID_TRANSITIONS: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        PROPOSED: frozenset({BACKLOG, DUPLICATE_CANDIDATE, ARCHIVED}),
        BACKLOG: frozenset({OPEN, DUPLICATE_CANDIDATE, ARCHIVED}),
        OPEN: frozenset(
            {
                IN_PROGRESS,
                DUPLICATE_CANDIDATE,
                DECOMPOSED,
                NEEDS_CI_FIX,
                NEEDS_REBASE,
                NEEDS_HUMAN,
                ARCHIVED,
            }
        ),
        IN_PROGRESS: frozenset(
            {
                OPEN,
                NEEDS_ANSWER,
                NEEDS_HUMAN,
                NEEDS_CI_FIX,
                NEEDS_REBASE,
                IN_REVIEW,
                IN_VALIDATION,
                READY_TO_INTEGRATE,
                DECOMPOSED,
            }
        ),
        NEEDS_ANSWER: frozenset({OPEN, IN_PROGRESS, NEEDS_HUMAN, ARCHIVED}),
        NEEDS_HUMAN: frozenset({OPEN, IN_PROGRESS, NEEDS_ANSWER, ARCHIVED}),
        NEEDS_CI_FIX: frozenset(
            {
                IN_PROGRESS,
                IN_REVIEW,
                IN_VALIDATION,
                READY_TO_INTEGRATE,
                NEEDS_HUMAN,
                ARCHIVED,
            }
        ),
        NEEDS_REBASE: frozenset(
            {
                IN_PROGRESS,
                IN_REVIEW,
                IN_VALIDATION,
                READY_TO_INTEGRATE,
                NEEDS_HUMAN,
                ARCHIVED,
            }
        ),
        IN_REVIEW: frozenset(
            {
                OPEN,
                IN_PROGRESS,
                NEEDS_CI_FIX,
                NEEDS_REBASE,
                IN_VALIDATION,
                READY_TO_INTEGRATE,
                NEEDS_HUMAN,
                MERGED,
                ARCHIVED,
            }
        ),
        IN_VALIDATION: frozenset(
            {
                OPEN,
                IN_PROGRESS,
                NEEDS_CI_FIX,
                NEEDS_REBASE,
                IN_REVIEW,
                READY_TO_INTEGRATE,
                NEEDS_HUMAN,
                DONE,
                MERGED,
                ARCHIVED,
            }
        ),
        READY_TO_INTEGRATE: frozenset(
            {
                OPEN,
                IN_PROGRESS,
                NEEDS_CI_FIX,
                NEEDS_REBASE,
                IN_REVIEW,
                IN_VALIDATION,
                NEEDS_HUMAN,
                ARCHIVED,
            }
        ),
        DECOMPOSED: frozenset({ARCHIVED}),
        DUPLICATE_CANDIDATE: frozenset(
            {PROPOSED, BACKLOG, OPEN, NEEDS_HUMAN, ARCHIVED}
        ),
        DONE: frozenset(
            {OPEN, NEEDS_CI_FIX, NEEDS_REBASE, IN_REVIEW, IN_VALIDATION, MERGED, ARCHIVED}
        ),
        # ``Merged`` is normally final, but the review reconciler may prove
        # that the recorded terminal state is false (for example an open PR
        # remains ahead of its target).  These are evidence-backed repair
        # edges, not ordinary lifecycle regression.
        MERGED: frozenset({OPEN, NEEDS_CI_FIX, NEEDS_REBASE, IN_REVIEW, ARCHIVED}),
        ARCHIVED: frozenset(),
    }
)


_DEFAULT_REQUIREMENTS = frozenset({TransitionRequirement.EXPECTED_VERSION})


def _requirements_for(
    from_status: str, to_status: str
) -> frozenset[TransitionRequirement]:
    requirements = set(_DEFAULT_REQUIREMENTS)
    if to_status in {BACKLOG, OPEN} and from_status in {PROPOSED, BACKLOG}:
        requirements.update(
            {
                TransitionRequirement.PROJECT_OWNER_AUTHORITY,
                TransitionRequirement.ACTIONABLE_DESCRIPTION,
            }
        )
    if to_status == IN_PROGRESS:
        requirements.update(
            {
                TransitionRequirement.DEPENDENCIES_SATISFIED,
                TransitionRequirement.VALID_OWNER_LEASE,
                TransitionRequirement.IMPLEMENTATION_GENERATION,
            }
        )
    if to_status == READY_TO_INTEGRATE:
        requirements.add(TransitionRequirement.ACCEPTED_SUBMISSION)
    if to_status == IN_VALIDATION:
        requirements.add(TransitionRequirement.AUDIT_REQUEST)
    if to_status in {DONE, MERGED, ARCHIVED}:
        requirements.add(TransitionRequirement.AUDIT_PASS)
    if to_status == MERGED:
        requirements.update(
            {
                TransitionRequirement.LANDING_EVIDENCE,
                TransitionRequirement.CONTAINMENT_EVIDENCE,
            }
        )
    if to_status == DECOMPOSED:
        requirements.add(TransitionRequirement.CHILDREN_CREATED)
    if from_status == DECOMPOSED:
        requirements.add(TransitionRequirement.CHILDREN_COMPLETE)
    if from_status == DUPLICATE_CANDIDATE:
        requirements.add(TransitionRequirement.DUPLICATE_VERDICT)
    if to_status == NEEDS_HUMAN:
        requirements.add(TransitionRequirement.OPERATOR_REASON)
    return frozenset(requirements)


TRANSITION_RULES: Mapping[tuple[str, str], TransitionRule] = MappingProxyType(
    {
        (source, target): TransitionRule(
            source,
            target,
            _requirements_for(source, target),
            f"{status_key(source).replace(' ', '_')}_to_{status_key(target).replace(' ', '_')}",
        )
        for source, targets in VALID_TRANSITIONS.items()
        for target in targets
    }
)

# No main-task self-transition currently represents a lifecycle edge.  API
# commands may still be transport-idempotent by returning the existing result;
# that is distinct from committing a new transition journal entry.
IDEMPOTENT_TRANSITIONS: frozenset[tuple[str, str]] = frozenset()


def transition_rule(
    from_status: str | None, to_status: str | None
) -> TransitionRule | None:
    """Return the canonical transition rule, or ``None`` for an illegal edge."""

    source = canonicalize_status(from_status)
    target = canonicalize_status(to_status)
    return TRANSITION_RULES.get((source, target))


def is_valid_transition(
    from_status: str | None,
    to_status: str | None,
    *,
    allow_idempotent: bool = False,
) -> bool:
    """Return whether the canonical lifecycle permits the requested edge."""

    source = canonicalize_status(from_status)
    target = canonicalize_status(to_status)
    if source == target:
        return allow_idempotent and (source, target) in IDEMPOTENT_TRANSITIONS
    return target in VALID_TRANSITIONS.get(source, frozenset())


SAFETY_INVARIANTS: tuple[WorkflowInvariant, ...] = (
    WorkflowInvariant(
        "single_status_writer",
        "safety",
        "Every status commit is owned by the transition service and journaled once.",
    ),
    WorkflowInvariant(
        "expected_version_compare_and_swap",
        "safety",
        "A transition commits only against the facts version it evaluated.",
    ),
    WorkflowInvariant(
        "single_active_owner",
        "safety",
        "Owned work has at most one live authority lease for its generation.",
        frozenset({TaskDisposition.OWNED}),
    ),
    WorkflowInvariant(
        "stale_generation_fenced",
        "safety",
        "Callbacks and retries from superseded generations cannot mutate current state.",
    ),
    WorkflowInvariant(
        "terminal_evidence_required",
        "safety",
        "Terminal commits require durable audit and target-specific completion evidence.",
        frozenset({TaskDisposition.TERMINAL}),
    ),
    WorkflowInvariant(
        "containment_before_rollup",
        "safety",
        "Child and nested-epic completion is accepted only with target-branch containment evidence.",
    ),
    WorkflowInvariant(
        "hard_start_dependencies_gate_ownership",
        "safety",
        "Implementation ownership cannot begin while a hard-start dependency is incomplete.",
    ),
    WorkflowInvariant(
        "final_states_do_not_auto_reopen",
        "safety",
        "Lifecycle-final tasks require an explicit authorized recovery intent to reopen.",
        frozenset({TaskDisposition.TERMINAL}),
    ),
)


LIVENESS_INVARIANTS: tuple[WorkflowInvariant, ...] = (
    WorkflowInvariant(
        "total_disposition",
        "liveness",
        "Every canonical status has exactly one default disposition.",
    ),
    WorkflowInvariant(
        "owned_has_lease",
        "liveness",
        "Owned work has a durable renewable lease and expiry recovery path.",
        frozenset({TaskDisposition.OWNED}),
    ),
    WorkflowInvariant(
        "retry_has_wakeup",
        "liveness",
        "Retry-scheduled work has a durable due time and claimable job.",
        frozenset({TaskDisposition.RETRY_SCHEDULED}),
    ),
    WorkflowInvariant(
        "blocked_has_prerequisite",
        "liveness",
        "Blocked work names the prerequisite and the event that reassesses it.",
        frozenset({TaskDisposition.BLOCKED}),
    ),
    WorkflowInvariant(
        "action_required_is_visible",
        "liveness",
        "Action-required work exposes a stable reason and responsible party.",
        frozenset({TaskDisposition.ACTION_REQUIRED}),
    ),
    WorkflowInvariant(
        "bounded_wait_is_reassessed",
        "liveness",
        "Every bounded wait is re-evaluated within its configured SLO.",
    ),
    WorkflowInvariant(
        "restart_reconstructs_work",
        "liveness",
        "A restart reconstructs pending work from durable facts without process-local memory.",
    ),
)


def validate_workflow_contract(
    *,
    status_contracts: Mapping[str, StatusContract] = STATUS_CONTRACTS,
    valid_transitions: Mapping[str, frozenset[str]] = VALID_TRANSITIONS,
    transition_rules: Mapping[tuple[str, str], TransitionRule] = TRANSITION_RULES,
    aliases: Mapping[str, str] = STATUS_ALIASES,
) -> tuple[str, ...]:
    """Return structural contract violations; an empty tuple means valid."""

    errors: list[str] = []
    canonical = set(CANONICAL_STATUSES)
    contract_keys = set(status_contracts)
    transition_keys = set(valid_transitions)
    if len(canonical) != len(CANONICAL_STATUSES):
        errors.append("CANONICAL_STATUSES contains duplicates")
    if contract_keys != canonical:
        errors.append(
            "STATUS_CONTRACTS mismatch: "
            f"missing={sorted(canonical - contract_keys)!r} "
            f"extra={sorted(contract_keys - canonical)!r}"
        )
    if transition_keys != canonical:
        errors.append(
            "VALID_TRANSITIONS mismatch: "
            f"missing={sorted(canonical - transition_keys)!r} "
            f"extra={sorted(transition_keys - canonical)!r}"
        )
    for status, contract in status_contracts.items():
        if contract.status != status:
            errors.append(f"contract key/status mismatch for {status!r}")
        if not contract.owners:
            errors.append(f"{status!r} has no owner contract")
        if contract.lifecycle_final and not contract.tracker_terminal:
            errors.append(f"{status!r} is final but not tracker-terminal")
        if (
            contract.lifecycle_final
            and contract.reassessment.trigger != ReassessmentTrigger.NEVER
        ):
            errors.append(f"{status!r} is final but has a reassessment trigger")
        if contract.disposition == TaskDisposition.BLOCKED and not contract.blocked_by:
            errors.append(f"blocked status {status!r} has no named prerequisite")
        if (
            not contract.lifecycle_final
            and contract.reassessment.trigger == ReassessmentTrigger.NEVER
        ):
            errors.append(f"non-final status {status!r} has no reassessment path")
        if not contract.lifecycle_final and not contract.reassessment.slo_key:
            errors.append(
                f"non-final status {status!r} has no bounded reassessment SLO"
            )
    for source, targets in valid_transitions.items():
        if source in targets:
            errors.append(f"implicit self-transition for {source!r}")
        unknown = set(targets) - canonical
        if unknown:
            errors.append(f"{source!r} targets unknown statuses {sorted(unknown)!r}")
        for target in targets:
            rule = transition_rules.get((source, target))
            if rule is None:
                errors.append(f"missing TransitionRule for {source!r} -> {target!r}")
            elif TransitionRequirement.EXPECTED_VERSION not in rule.requirements:
                errors.append(
                    f"transition lacks expected-version fence: {source!r} -> {target!r}"
                )
    extra_rules = set(transition_rules) - {
        (source, target)
        for source, targets in valid_transitions.items()
        for target in targets
    }
    if extra_rules:
        errors.append(f"rules exist for illegal transitions: {sorted(extra_rules)!r}")
    for alias, target in aliases.items():
        if target not in canonical:
            errors.append(f"alias {alias!r} targets unknown status {target!r}")
    invariant_codes = [
        invariant.code for invariant in (*SAFETY_INVARIANTS, *LIVENESS_INVARIANTS)
    ]
    if len(invariant_codes) != len(set(invariant_codes)):
        errors.append("workflow invariant codes are not unique")
    return tuple(errors)


def assert_valid_workflow_contract() -> None:
    """Raise ``ValueError`` when the static lifecycle contract is malformed."""

    errors = validate_workflow_contract()
    if errors:
        raise ValueError("invalid workflow contract: " + "; ".join(errors))


assert_valid_workflow_contract()
