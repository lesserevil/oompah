"""Durable, version-fenced ownership of task status transitions.

The transition service is the only workflow component that should decide to
commit a task status.  It records an immutable intent before touching the
tracker, fences concurrent writers with a durable per-task claim, and records
the observed outcome after verifying the tracker.  Replaying the same
idempotency key therefore recovers cleanly from a process death before or
after the tracker side effect.

Terminal targets remain subject to independent audit.  They are delegated to
``TerminalTransitionCoordinator`` through :class:`CoordinatorTerminalAdapter`
and are considered *staged* when the coordinator durably owns the request;
this service never writes a terminal tracker status directly.
"""

from __future__ import annotations

import asyncio
import contextlib
import contextvars
import hashlib
import inspect
import json
import logging
import os
import re
import sqlite3
import threading
import time
import uuid
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol

from oompah.integration import direct_epic_maintenance_handoff_ready
from oompah.models import Issue
from oompah.statuses import (
    ARCHIVED,
    BACKLOG,
    DONE,
    IN_PROGRESS,
    IN_VALIDATION,
    MERGED,
    NEEDS_CI_FIX,
    NEEDS_HUMAN,
    NEEDS_REBASE,
    OPEN,
    READY_TO_INTEGRATE,
    canonicalize_status,
)
from oompah.terminal_audit import (
    AuditRevisionBinding,
    ContributorIdentity,
    TargetState,
    compute_issue_evidence_fingerprint,
)
from oompah.tracker import TrackerProtocol
from oompah.workflow_contract import (
    CANONICAL_STATUSES,
    TransitionRequirement,
    transition_rule,
)

logger = logging.getLogger(__name__)

TRANSITION_JOURNAL_SCHEMA_VERSION = 1
DEFAULT_TRANSITION_CLAIM_TTL_SECONDS = 300.0
TERMINAL_TARGETS = frozenset({DONE, MERGED, ARCHIVED})
AUDIT_STAGING_REQUIRED_REASON = "transition.audit_staging_required"

_INITIALIZE_LOCK = threading.Lock()
_REASON_CODE_RE = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
_HEAD_RE = re.compile(r"^[0-9a-f]{40,64}$")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _required_text(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} is required")
    return text


def _optional_text(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _integration_projection(issue: Issue) -> dict[str, Any] | None:
    integration = getattr(issue, "integration", None)
    if integration is None:
        return None
    if hasattr(integration, "to_dict"):
        raw = integration.to_dict()
    elif isinstance(integration, Mapping):
        raw = dict(integration)
    else:
        raw = {
            name: getattr(integration, name, None)
            for name in (
                "version",
                "state",
                "mode",
                "task_branch",
                "base_branch",
                "head_sha",
                "base_sha",
                "integrated_sha",
                "maintenance_publication_proven",
            )
        }
    return {
        key: raw.get(key)
        for key in (
            "version",
            "state",
            "mode",
            "task_branch",
            "base_branch",
            "head_sha",
            "base_sha",
            "integrated_sha",
            "maintenance_publication_proven",
        )
        if raw.get(key) is not None
    }


def issue_authority_version(issue: Issue) -> str:
    """Return the stable version used for status compare-and-swap checks.

    Generic tracker timestamps are deliberately excluded.  A comment or
    other benign metadata write must not invalidate lifecycle authority.  The
    projection contains only task/project/parent identity, lifecycle state,
    epic-containment classification fields, implementation/review generation
    and head, delivery branches, integration authority, and the canonical
    terminal-audit evidence.  Including that evidence is important even for
    the pre-audit compare-and-swap: otherwise a requirements, contributor, or
    integrated-revision change could stage an audit for a stale snapshot.
    """

    projection = {
        "identifier": str(issue.identifier),
        "project_id": str(issue.project_id or ""),
        "parent_id": _optional_text(getattr(issue, "parent_id", None)),
        "issue_type": _optional_text(getattr(issue, "issue_type", None)),
        # Epic containment classifies maintenance children from their title and
        # labels.  Those fields therefore participate in transition/cleanup
        # authority just like parent, status, branch, and exact head.
        "title": _optional_text(getattr(issue, "title", None)),
        "maintenance_labels": sorted(
            str(label).strip().lower()
            for label in (getattr(issue, "labels", None) or ())
            if str(label).strip().lower() in {"merge-conflict", "ci-fix"}
        ),
        "status": canonicalize_status(issue.state),
        "lifecycle_revision": getattr(issue, "lifecycle_revision", None),
        "assignment_id": _optional_text(getattr(issue, "assignment_id", None)),
        "head_sha": _optional_text(getattr(issue, "head_sha", None)),
        "review_number": _optional_text(getattr(issue, "review_number", None)),
        "review_head": _optional_text(getattr(issue, "review_head", None)),
        "work_branch": _optional_text(getattr(issue, "work_branch", None)),
        "target_branch": _optional_text(getattr(issue, "target_branch", None)),
        "integration": _integration_projection(issue),
        "terminal_evidence": compute_issue_evidence_fingerprint(
            issue, str(issue.project_id or "legacy")
        ).digest,
    }
    return hashlib.sha256(_canonical_json(projection).encode("utf-8")).hexdigest()


def rollup_authority_generation(parent: Issue, children: Iterable[Issue]) -> str:
    """Bind one rollup decision to the current parent and child lineage."""

    child_versions = sorted(
        (
            str(child.id or child.identifier),
            issue_authority_version(child),
        )
        for child in children
    )
    payload = {
        "parent": issue_authority_version(parent),
        "children": child_versions,
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def issue_exact_head(issue: Issue) -> str | None:
    """Return the task's exact authority head when one is available."""

    direct = _optional_text(getattr(issue, "head_sha", None))
    if direct:
        return direct.lower()
    review_head = _optional_text(getattr(issue, "review_head", None))
    integration = getattr(issue, "integration", None)
    if isinstance(integration, Mapping):
        value = _optional_text(integration.get("head_sha"))
    else:
        value = _optional_text(getattr(integration, "head_sha", None))
    if value:
        return value.lower()
    # Review-created rollups may not have an implementation record of their
    # own.  Their persisted review head is nevertheless the exact immutable
    # source revision against which terminal landing was proven.
    return review_head.lower() if review_head else None


def _is_authorized_recovery_intent(intent: TransitionIntent) -> bool:
    """Return whether an intent belongs to the narrow compensation lane."""

    return (
        intent.authority is TransitionAuthority.AUDITOR
        and intent.reason_code.startswith("audit.")
        and intent.reason_code != "audit.owner_override_recovered"
    ) or (
        intent.authority is TransitionAuthority.PROJECT_OWNER
        and intent.reason_code
        in {
            "audit.owner_override_recovered",
            "provenance.owner_revision_authorized",
        }
    ) or (
        intent.authority is TransitionAuthority.SYSTEM
        and (
            intent.reason_code.startswith("intake.")
            or (
                intent.reason_code == "maintenance.container_cycle_restored"
                and canonicalize_status(intent.expected_status) == NEEDS_HUMAN
                and canonicalize_status(intent.requested_status)
                == READY_TO_INTEGRATE
            )
            or (
                intent.reason_code == "maintenance.unlanded_done_child_recovered"
                and canonicalize_status(intent.expected_status) == DONE
                and canonicalize_status(intent.requested_status) == NEEDS_HUMAN
            )
            or (
                intent.reason_code == "maintenance.landed_done_child_restored"
                and canonicalize_status(intent.expected_status) == NEEDS_HUMAN
                and canonicalize_status(intent.requested_status) == DONE
            )
        )
    )


class TransitionAuthority(str, Enum):
    """Authority class carried by every mutation intent."""

    PROJECT_OWNER = "project_owner"
    ORCHESTRATOR = "orchestrator"
    WORKER = "worker"
    AUDITOR = "auditor"
    INTEGRATOR = "integrator"
    WATCHDOG = "watchdog"
    API = "api"
    SYSTEM = "system"


class TransitionPhase(str, Enum):
    """Append-only journal phases for one intent."""

    REQUESTED = "requested"
    WAITING = "waiting"
    APPLYING = "applying"
    VERIFY_PENDING = "verify_pending"
    RETRY_SCHEDULED = "retry_scheduled"
    APPLIED = "applied"
    RECOVERED = "recovered"
    STAGED = "staged"
    REJECTED = "rejected"


FINAL_PHASES = frozenset(
    {
        TransitionPhase.APPLIED,
        TransitionPhase.RECOVERED,
        TransitionPhase.STAGED,
        TransitionPhase.REJECTED,
    }
)


class TransitionDisposition(str, Enum):
    """Public result of processing a transition intent."""

    APPLIED = "applied"
    ALREADY_APPLIED = "already_applied"
    STAGED = "staged"
    RECOVERED = "recovered"
    WAITING = "waiting"
    RETRYABLE = "retryable"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class TransitionIntent:
    """Immutable, complete request to change one task's lifecycle status."""

    project_id: str
    task_id: str
    expected_status: str
    expected_version: str
    requested_status: str
    actor: str
    authority: TransitionAuthority | str
    reason_code: str
    idempotency_key: str
    originating_job: str
    evidence_generation: str | None = None
    exact_head: str | None = None
    precondition_revision: str | None = None
    schema_version: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "project_id", _required_text(self.project_id, "project_id")
        )
        object.__setattr__(self, "task_id", _required_text(self.task_id, "task_id"))
        expected = canonicalize_status(self.expected_status)
        requested = canonicalize_status(self.requested_status)
        if expected not in CANONICAL_STATUSES:
            raise ValueError(f"unknown expected_status: {expected!r}")
        if requested not in CANONICAL_STATUSES:
            raise ValueError(f"unknown requested_status: {requested!r}")
        object.__setattr__(self, "expected_status", expected)
        object.__setattr__(self, "requested_status", requested)
        object.__setattr__(
            self,
            "expected_version",
            _required_text(self.expected_version, "expected_version"),
        )
        object.__setattr__(self, "actor", _required_text(self.actor, "actor"))
        try:
            authority = TransitionAuthority(self.authority)
        except ValueError as exc:
            raise ValueError(
                f"unknown transition authority: {self.authority!r}"
            ) from exc
        object.__setattr__(self, "authority", authority)
        code = _required_text(self.reason_code, "reason_code")
        if not _REASON_CODE_RE.fullmatch(code):
            raise ValueError("reason_code must be a stable dotted lowercase identifier")
        object.__setattr__(self, "reason_code", code)
        object.__setattr__(
            self,
            "idempotency_key",
            _required_text(self.idempotency_key, "idempotency_key"),
        )
        object.__setattr__(
            self,
            "originating_job",
            _required_text(self.originating_job, "originating_job"),
        )
        generation = _optional_text(self.evidence_generation)
        object.__setattr__(self, "evidence_generation", generation)
        exact_head = _optional_text(self.exact_head)
        if exact_head is not None:
            exact_head = exact_head.lower()
            if not _HEAD_RE.fullmatch(exact_head):
                raise ValueError(
                    "exact_head must be a 40-64 character hexadecimal revision"
                )
        object.__setattr__(self, "exact_head", exact_head)
        object.__setattr__(
            self,
            "precondition_revision",
            _optional_text(self.precondition_revision),
        )
        if self.schema_version != 1:
            raise ValueError("unsupported TransitionIntent schema_version")

    @property
    def revision(self) -> str:
        return hashlib.sha256(
            _canonical_json(self.to_dict()).encode("utf-8")
        ).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "schema_version": self.schema_version,
            "project_id": self.project_id,
            "task_id": self.task_id,
            "expected_status": self.expected_status,
            "expected_version": self.expected_version,
            "requested_status": self.requested_status,
            "actor": self.actor,
            "authority": self.authority.value,
            "reason_code": self.reason_code,
            "idempotency_key": self.idempotency_key,
            "originating_job": self.originating_job,
            "evidence_generation": self.evidence_generation,
            "exact_head": self.exact_head,
        }
        # Preserve the canonical revision of schema-v1 intents written before
        # this optional fence existed.  New auto-close intents include the
        # field; legacy and unrelated intents continue to hash byte-for-byte.
        if self.precondition_revision is not None:
            payload["precondition_revision"] = self.precondition_revision
        return payload

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "TransitionIntent":
        if not isinstance(raw, Mapping):
            raise ValueError("transition intent must be an object")
        return cls(**dict(raw))


def _guarded_landing_revision_lane(
    intent: TransitionIntent,
    issue: Issue,
) -> str | None:
    """Identify a narrowly authorized headless landing-revision intent.

    A supplied immutable landing SHA is external revision authority: it may
    replace a task-owned head only when the workflow intent binds both its
    durable job generation and the freshly revalidated evidence revision.
    The original composed-child lane remains unchanged.  A root epic gets the
    same exception only for its orchestrator-owned auto-close from the live
    ``In Progress`` rollup state.
    """

    if (
        intent.exact_head is None
        or issue_exact_head(issue) is not None
        or intent.requested_status != MERGED
        or intent.reason_code != "terminal.immediate_target_landing_proven"
        or intent.precondition_revision is None
        or intent.evidence_generation is None
    ):
        return None
    parent_id = str(getattr(issue, "parent_id", "") or "").strip()
    if (
        canonicalize_status(issue.state) == DONE
        and intent.authority is TransitionAuthority.INTEGRATOR
        and parent_id
    ):
        return "composed_child"
    if (
        canonicalize_status(issue.state) == IN_PROGRESS
        and intent.authority is TransitionAuthority.ORCHESTRATOR
        and not parent_id
        and str(getattr(issue, "issue_type", "") or "").strip().lower()
        == "epic"
    ):
        return "root_epic"
    return None


@dataclass(frozen=True, slots=True)
class TransitionOutcome:
    """Serializable result returned for new and replayed requests."""

    transition_id: str
    project_id: str
    task_id: str
    disposition: TransitionDisposition | str
    reason_code: str
    observed_status: str
    observed_version: str | None
    requested_status: str
    applied_status: str | None = None
    audit_id: str | None = None
    retryable: bool = False
    replayed: bool = False
    details: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "disposition", TransitionDisposition(self.disposition))

    def to_dict(self) -> dict[str, Any]:
        return {
            "transition_id": self.transition_id,
            "project_id": self.project_id,
            "task_id": self.task_id,
            "disposition": self.disposition.value,
            "reason_code": self.reason_code,
            "observed_status": self.observed_status,
            "observed_version": self.observed_version,
            "requested_status": self.requested_status,
            "applied_status": self.applied_status,
            "audit_id": self.audit_id,
            "retryable": self.retryable,
            "replayed": self.replayed,
            "details": dict(self.details or {}),
        }

    @classmethod
    def from_dict(
        cls, raw: Mapping[str, Any], *, replayed: bool = False
    ) -> "TransitionOutcome":
        values = dict(raw)
        values["replayed"] = replayed or bool(values.get("replayed", False))
        return cls(**values)


@dataclass(frozen=True, slots=True)
class TransitionJournalEvent:
    sequence: int
    transition_id: str
    project_id: str
    task_id: str
    phase: TransitionPhase
    reason_code: str
    outcome: TransitionOutcome | None
    created_at: str


@dataclass(frozen=True, slots=True)
class TerminalStageResult:
    success: bool
    audit_id: str | None = None
    reason_code: str = "transition.terminal_staged"
    detail: str | None = None


class TerminalTransitionAdapter(Protocol):
    async def stage(
        self, intent: TransitionIntent, issue: Issue
    ) -> TerminalStageResult:
        """Durably stage one terminal intent without directly writing its target."""


class DirectOwnerClaimGuard(Protocol):
    def __call__(self, intent: TransitionIntent, issue: Issue) -> str | None:
        """Return a stable rejection reason unless the exact live lease owns commit."""


class TransitionMutationGuard(Protocol):
    def __call__(self, intent: TransitionIntent, issue: Issue) -> str | None:
        """Return detail when live workflow authority no longer permits commit."""


class DirectOwnerRetirementGuard(Protocol):
    def __call__(self, intent: TransitionIntent, issue: Issue) -> str | None:
        """Persist exact owner-retirement authority before a Ready commit."""


class CoordinatorTerminalAdapter:
    """Adapt ``TerminalTransitionCoordinator`` to the service boundary."""

    def __init__(
        self,
        coordinator: Any,
        *,
        mutation_guard: Callable[[TransitionIntent], str | None] | None = None,
    ):
        self._coordinator = coordinator
        self._mutation_guard = mutation_guard

    async def stage(
        self, intent: TransitionIntent, issue: Issue
    ) -> TerminalStageResult:
        if (
            intent.reason_code == "terminal.immediate_target_landing_proven"
            and intent.precondition_revision is None
        ):
            return TerminalStageResult(
                success=False,
                reason_code="transition.stale_precondition",
                detail="workflow completion authority is missing",
            )
        fields = dict(
            current_issue=issue,
            requested_target=TargetState.from_raw(intent.requested_status),
            trigger_identity=ContributorIdentity(intent.actor, intent.authority.value),
            project_id=intent.project_id,
            evidence_fingerprint=compute_issue_evidence_fingerprint(
                issue, intent.project_id
            ),
        )
        if intent.precondition_revision is not None:
            fields["workflow_revision"] = (
                intent.precondition_revision
            )
        landed_epic_validation = bool(
            intent.requested_status == MERGED
            and intent.reason_code == "terminal.immediate_target_landing_proven"
            and intent.authority is TransitionAuthority.ORCHESTRATOR
            and str(getattr(issue, "issue_type", "") or "").strip().lower()
            == "epic"
            and intent.exact_head is not None
            and intent.precondition_revision is not None
            and self._mutation_guard is not None
        )
        if landed_epic_validation:
            # The immutable landing head authorizes containment.  The
            # coordinator resolves the current immediate-target head under
            # the project mutation fence and binds the audit workspace there.
            fields["landing_revision"] = intent.exact_head
        elif (
            _guarded_landing_revision_lane(intent, issue) is not None
            and self._mutation_guard is not None
        ):
            # A composed child no longer owns a mutable task head. Its guarded
            # workflow intent carries the immutable immediate-target landing
            # SHA, which must bind the audit itself.
            fields["revision_binding"] = AuditRevisionBinding(
                intent.exact_head,
                intent.exact_head,
            )
        if self._mutation_guard is not None:
            fields["mutation_guard"] = lambda: self._mutation_guard(intent)
        result = await self._coordinator.request_transition(**fields)
        reason = _optional_text(getattr(result, "reason", None))
        return TerminalStageResult(
            success=bool(result.success),
            audit_id=_optional_text(getattr(result, "audit_id", None)),
            reason_code=(
                "transition.terminal_staged"
                if result.success
                else "transition.stale_precondition"
                if reason and reason.startswith("workflow_precondition_changed:")
                else "transition.delivery_mutation_in_progress"
                if reason == "delivery_mutation_in_progress"
                else "transition.terminal_rejected"
            ),
            detail=reason,
        )


class TransitionJournalError(RuntimeError):
    """Base error for durable transition journal failures."""


class TransitionJournalCorruptionError(TransitionJournalError):
    """Raised when immutable journal content cannot be decoded safely."""


class TransitionJournalClosedError(TransitionJournalError):
    """Raised when journal work starts after retirement begins."""


_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS task_transition_requests (
    transition_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    intent_revision TEXT NOT NULL,
    intent_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(project_id, idempotency_key)
);
CREATE INDEX IF NOT EXISTS task_transition_request_task_idx
    ON task_transition_requests(project_id, task_id, created_at, transition_id);
CREATE TABLE IF NOT EXISTS task_transition_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    transition_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    phase TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    outcome_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(transition_id) REFERENCES task_transition_requests(transition_id)
);
CREATE INDEX IF NOT EXISTS task_transition_event_lookup_idx
    ON task_transition_events(transition_id, sequence);
CREATE TABLE IF NOT EXISTS task_transition_claims (
    project_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    transition_id TEXT NOT NULL,
    claim_token TEXT NOT NULL,
    claimed_at REAL NOT NULL,
    lease_expires_at REAL NOT NULL,
    PRIMARY KEY(project_id, task_id),
    FOREIGN KEY(transition_id) REFERENCES task_transition_requests(transition_id)
);
CREATE TRIGGER IF NOT EXISTS task_transition_requests_no_update
BEFORE UPDATE ON task_transition_requests BEGIN
    SELECT RAISE(ABORT, 'transition requests are append-only');
END;
CREATE TRIGGER IF NOT EXISTS task_transition_requests_no_delete
BEFORE DELETE ON task_transition_requests BEGIN
    SELECT RAISE(ABORT, 'transition requests are append-only');
END;
CREATE TRIGGER IF NOT EXISTS task_transition_events_no_update
BEFORE UPDATE ON task_transition_events BEGIN
    SELECT RAISE(ABORT, 'transition events are append-only');
END;
CREATE TRIGGER IF NOT EXISTS task_transition_events_no_delete
BEFORE DELETE ON task_transition_events BEGIN
    SELECT RAISE(ABORT, 'transition events are append-only');
END;
"""


@dataclass(frozen=True, slots=True)
class _BeginResult:
    transition_id: str
    claim_token: str | None
    replay: TransitionOutcome | None = None
    waiting: TransitionOutcome | None = None
    previous_phase: TransitionPhase | None = None
    recovery_transition_id: str | None = None
    recovery_intent: TransitionIntent | None = None
    recovery_previous_phase: TransitionPhase | None = None


class TransitionJournal:
    """SQLite-backed immutable intent/event journal with durable task claims."""

    def __init__(
        self,
        path: str,
        *,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.path = path if path == ":memory:" else os.path.abspath(path)
        if self.path != ":memory:":
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        self._clock = clock
        self._lock = threading.RLock()
        self._lifecycle_condition = threading.Condition(threading.RLock())
        self._active_uses = 0
        self._active_transition_leases: set[object] = set()
        self._transition_lease: contextvars.ContextVar[object | None] = (
            contextvars.ContextVar(
                f"transition-journal-lease-{id(self)}",
                default=None,
            )
        )
        self._closing = False
        self._closed = False
        self._conn = sqlite3.connect(self.path, check_same_thread=False, timeout=10)
        self._conn.row_factory = sqlite3.Row
        with _INITIALIZE_LOCK, self._lock:
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.execute("PRAGMA busy_timeout=10000")
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.executescript(_SCHEMA)
            self._conn.execute(
                "INSERT OR REPLACE INTO schema_meta(key, value) VALUES(?, ?)",
                ("task_transition_version", str(TRANSITION_JOURNAL_SCHEMA_VERSION)),
            )
            self._conn.commit()

    @contextlib.contextmanager
    def _admit_use(self) -> Iterator[None]:
        """Fence one complete public journal use against retirement."""

        with self._lifecycle_condition:
            # ``asyncio.to_thread`` copies context.  The live-set check lets
            # an admitted saga finish journal work after the close fence, but
            # prevents a worker carrying a stale, cancelled lease from doing
            # the same after its outer saga has exited.
            transition_lease = self._transition_lease.get()
            owns_active_transition = (
                transition_lease is not None
                and transition_lease in self._active_transition_leases
            )
            if (self._closing or self._closed) and not owns_active_transition:
                raise TransitionJournalClosedError(
                    "transition journal is closing or closed"
                )
            self._active_uses += 1
        try:
            yield
        finally:
            with self._lifecycle_condition:
                self._active_uses -= 1
                if self._active_uses == 0:
                    self._lifecycle_condition.notify_all()

    @contextlib.contextmanager
    def admit_transition(self) -> Iterator[None]:
        """Hold journal lifetime authority for one complete transition saga.

        A transition deliberately releases the SQLite lock while it performs
        tracker I/O.  Closing the connection based on lock ownership alone can
        therefore retire the journal between its durable intent and outcome
        writes.  This lease spans those gaps: retirement fences new sagas and
        waits for every already-admitted saga to record or recover its outcome.
        """

        lease = object()
        with self._lifecycle_condition:
            if self._closing or self._closed:
                raise TransitionJournalClosedError(
                    "transition journal is closing or closed"
                )
            self._active_transition_leases.add(lease)
            self._active_uses += 1
        context_token = self._transition_lease.set(lease)
        try:
            yield
        finally:
            self._transition_lease.reset(context_token)
            with self._lifecycle_condition:
                self._active_transition_leases.remove(lease)
                self._active_uses -= 1
                if self._active_uses == 0:
                    self._lifecycle_condition.notify_all()

    def _ensure_conn(self) -> None:
        """Re-open the connection if it was closed, preventing 'closed database' errors.
        
        This handles the race condition where an orchestrator is replaced and the
        old store may be garbage collected while API threads still hold references
        to it and try to access it.
        """
        try:
            # Test if the connection is alive by executing a simple query
            self._conn.execute("SELECT 1")
        except sqlite3.ProgrammingError:
            # Connection is closed, re-open it
            self._conn = sqlite3.connect(self.path, check_same_thread=False, timeout=10)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA busy_timeout=10000")
            self._conn.execute("PRAGMA journal_mode=WAL")

    def close(self) -> None:
        """Fence new uses, drain admitted work, and close exactly once."""

        with self._lifecycle_condition:
            while self._closing:
                self._lifecycle_condition.wait()
            if self._closed:
                return
            self._closing = True
        try:
            with self._lifecycle_condition:
                while self._active_uses:
                    self._lifecycle_condition.wait()
            with self._lock:
                self._conn.close()
        except BaseException:
            with self._lifecycle_condition:
                self._closing = False
                self._lifecycle_condition.notify_all()
            raise
        with self._lifecycle_condition:
            self._closed = True
            self._closing = False
            self._lifecycle_condition.notify_all()

    def _decode_outcome(
        self, raw: object, *, replayed: bool = False
    ) -> TransitionOutcome | None:
        if raw is None:
            return None
        try:
            value = json.loads(str(raw))
            if not isinstance(value, Mapping):
                raise TypeError("outcome is not an object")
            return TransitionOutcome.from_dict(value, replayed=replayed)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise TransitionJournalCorruptionError(
                "invalid transition outcome JSON"
            ) from exc

    def _event_from_row(
        self, row: sqlite3.Row, *, replayed: bool = False
    ) -> TransitionJournalEvent:
        try:
            phase = TransitionPhase(str(row["phase"]))
        except ValueError as exc:
            raise TransitionJournalCorruptionError(
                f"unknown transition journal phase: {row['phase']!r}"
            ) from exc
        return TransitionJournalEvent(
            sequence=int(row["sequence"]),
            transition_id=str(row["transition_id"]),
            project_id=str(row["project_id"]),
            task_id=str(row["task_id"]),
            phase=phase,
            reason_code=str(row["reason_code"]),
            outcome=self._decode_outcome(row["outcome_json"], replayed=replayed),
            created_at=str(row["created_at"]),
        )

    def _latest_event_locked(self, transition_id: str) -> TransitionJournalEvent | None:
        row = self._conn.execute(
            """
            SELECT * FROM task_transition_events
             WHERE transition_id = ? ORDER BY sequence DESC LIMIT 1
            """,
            (transition_id,),
        ).fetchone()
        return self._event_from_row(row) if row is not None else None

    def latest_event(self, transition_id: str) -> TransitionJournalEvent | None:
        with self._admit_use(), self._lock:
            return self._latest_event_locked(transition_id)

    def latest_committed_task_transition(
        self,
        project_id: str,
        task_id: str,
    ) -> tuple[TransitionIntent, TransitionJournalEvent] | None:
        """Return the newest transition that committed a lifecycle effect.

        Waiting, retryable, and rejected attempts do not supersede the task's
        last committed authority.  This distinction lets an idempotent recovery
        survive transient claim/transport failures while a later successful
        human, auditor, or system transition still consumes the old capability.
        """

        with self._admit_use(), self._lock:
            rows = self._conn.execute(
                """
                SELECT event.*
                  FROM task_transition_events AS event
                  JOIN task_transition_requests AS request
                    ON request.transition_id = event.transition_id
                 WHERE request.project_id = ? AND request.task_id = ?
                   AND event.outcome_json IS NOT NULL
                 ORDER BY event.sequence DESC
                """,
                (
                    _required_text(project_id, "project_id"),
                    _required_text(task_id, "task_id"),
                ),
            ).fetchall()
            for row in rows:
                event = self._event_from_row(row)
                if event.outcome is None or event.outcome.disposition not in {
                    TransitionDisposition.APPLIED,
                    TransitionDisposition.RECOVERED,
                    TransitionDisposition.STAGED,
                }:
                    continue
                intent_row = self._conn.execute(
                    "SELECT intent_json FROM task_transition_requests "
                    "WHERE transition_id = ?",
                    (event.transition_id,),
                ).fetchone()
                if intent_row is None:
                    raise TransitionJournalCorruptionError(
                        "transition event has no immutable request"
                    )
                try:
                    raw = json.loads(str(intent_row["intent_json"]))
                    intent = TransitionIntent.from_dict(raw)
                except (TypeError, ValueError, json.JSONDecodeError) as exc:
                    raise TransitionJournalCorruptionError(
                        "invalid transition intent JSON"
                    ) from exc
                return intent, event
            return None

    def committed_task_transitions(
        self,
        project_id: str,
        task_id: str,
    ) -> tuple[tuple[TransitionIntent, TransitionJournalEvent, str], ...]:
        """Return committed task transitions from newest to oldest."""

        with self._admit_use(), self._lock:
            rows = self._conn.execute(
                """
                SELECT event.*, request.intent_json,
                       request.created_at AS request_created_at
                  FROM task_transition_events AS event
                  JOIN task_transition_requests AS request
                    ON request.transition_id = event.transition_id
                 WHERE request.project_id = ? AND request.task_id = ?
                   AND event.outcome_json IS NOT NULL
                 ORDER BY event.sequence DESC
                """,
                (
                    _required_text(project_id, "project_id"),
                    _required_text(task_id, "task_id"),
                ),
            ).fetchall()
            committed: list[
                tuple[TransitionIntent, TransitionJournalEvent, str]
            ] = []
            for row in rows:
                event = self._event_from_row(row)
                if event.outcome is None or event.outcome.disposition not in {
                    TransitionDisposition.APPLIED,
                    TransitionDisposition.RECOVERED,
                    TransitionDisposition.STAGED,
                }:
                    continue
                try:
                    raw = json.loads(str(row["intent_json"]))
                    intent = TransitionIntent.from_dict(raw)
                except (TypeError, ValueError, json.JSONDecodeError) as exc:
                    raise TransitionJournalCorruptionError(
                        "invalid transition intent JSON"
                    ) from exc
                committed.append((intent, event, str(row["request_created_at"])))
            return tuple(committed)

    def events(self, transition_id: str) -> tuple[TransitionJournalEvent, ...]:
        with self._admit_use(), self._lock:
            rows = self._conn.execute(
                """
                SELECT * FROM task_transition_events
                 WHERE transition_id = ? ORDER BY sequence
                """,
                (transition_id,),
            ).fetchall()
            return tuple(self._event_from_row(row) for row in rows)

    def load_intent(self, transition_id: str) -> TransitionIntent:
        with self._admit_use(), self._lock:
            row = self._conn.execute(
                "SELECT intent_json FROM task_transition_requests WHERE transition_id = ?",
                (transition_id,),
            ).fetchone()
        if row is None:
            raise KeyError(transition_id)
        try:
            raw = json.loads(str(row["intent_json"]))
            return TransitionIntent.from_dict(raw)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise TransitionJournalCorruptionError(
                "invalid transition intent JSON"
            ) from exc

    def _append_locked(
        self,
        transition_id: str,
        project_id: str,
        task_id: str,
        phase: TransitionPhase,
        reason_code: str,
        outcome: TransitionOutcome | None = None,
    ) -> int:
        cursor = self._conn.execute(
            """
            INSERT INTO task_transition_events(
                transition_id, project_id, task_id, phase, reason_code,
                outcome_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                transition_id,
                project_id,
                task_id,
                phase.value,
                reason_code,
                _canonical_json(outcome.to_dict()) if outcome else None,
                _now_iso(),
            ),
        )
        return int(cursor.lastrowid)

    def append(
        self,
        transition_id: str,
        phase: TransitionPhase,
        reason_code: str,
        outcome: TransitionOutcome | None = None,
    ) -> int:
        with self._admit_use():
            return self._append_admitted(
                transition_id,
                phase,
                reason_code,
                outcome,
            )

    def _append_admitted(
        self,
        transition_id: str,
        phase: TransitionPhase,
        reason_code: str,
        outcome: TransitionOutcome | None = None,
    ) -> int:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT project_id, task_id FROM task_transition_requests
                 WHERE transition_id = ?
                """,
                (transition_id,),
            ).fetchone()
            if row is None:
                raise KeyError(transition_id)
            sequence = self._append_locked(
                transition_id,
                str(row["project_id"]),
                str(row["task_id"]),
                TransitionPhase(phase),
                _required_text(reason_code, "reason_code"),
                outcome,
            )
            self._conn.commit()
            return sequence

    def begin(
        self,
        intent: TransitionIntent,
        *,
        lease_ttl_seconds: float = DEFAULT_TRANSITION_CLAIM_TTL_SECONDS,
    ) -> _BeginResult:
        """Atomically register an idempotency key and acquire task ownership."""

        with self._admit_use():
            return self._begin_admitted(
                intent,
                lease_ttl_seconds=lease_ttl_seconds,
            )

    def active_claims_for_tasks(
        self,
        project_id: str,
        task_ids: Iterable[str],
    ) -> frozenset[str]:
        """Return requested task IDs with a live durable transition owner."""

        identifiers = tuple(
            sorted({str(task_id or "").strip() for task_id in task_ids if task_id})
        )
        if not identifiers:
            return frozenset()
        with self._admit_use(), self._lock:
            now = self._clock()
            rows = self._conn.execute(
                f"""
                SELECT task_id FROM task_transition_claims
                 WHERE project_id = ? AND lease_expires_at > ?
                   AND task_id IN ({','.join('?' for _ in identifiers)})
                """,
                (project_id, now, *identifiers),
            ).fetchall()
        return frozenset(str(row["task_id"]) for row in rows)

    def _begin_admitted(
        self,
        intent: TransitionIntent,
        *,
        lease_ttl_seconds: float = DEFAULT_TRANSITION_CLAIM_TTL_SECONDS,
    ) -> _BeginResult:
        """Begin a transition whose caller already owns lifecycle admission."""

        if lease_ttl_seconds <= 0:
            raise ValueError("lease_ttl_seconds must be positive")
        now = self._clock()
        transition_id = f"transition-{uuid.uuid4().hex}"
        claim_token = uuid.uuid4().hex
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._conn.execute(
                    """
                    SELECT * FROM task_transition_requests
                     WHERE project_id = ? AND idempotency_key = ?
                    """,
                    (intent.project_id, intent.idempotency_key),
                ).fetchone()
                if row is not None:
                    transition_id = str(row["transition_id"])
                    if str(row["intent_revision"]) != intent.revision:
                        latest = self._latest_event_locked(transition_id)
                        conflict = TransitionOutcome(
                            transition_id=transition_id,
                            project_id=intent.project_id,
                            task_id=intent.task_id,
                            disposition=TransitionDisposition.REJECTED,
                            reason_code="transition.idempotency_conflict",
                            observed_status="",
                            observed_version=None,
                            requested_status=intent.requested_status,
                            details={
                                "existing_task_id": str(row["task_id"]),
                                "existing_phase": latest.phase.value
                                if latest
                                else None,
                            },
                        )
                        # These bytes are not the registered request.  Do not
                        # append the conflict to the original transition or a
                        # later replay of the valid intent would observe this
                        # rejection as its own terminal outcome.
                        self._conn.commit()
                        return _BeginResult(transition_id, None, replay=conflict)
                    latest = self._latest_event_locked(transition_id)
                    if latest and latest.phase in FINAL_PHASES and latest.outcome:
                        # A process may die after appending its final event but
                        # before releasing the mutable claim.  A replay is
                        # authoritative evidence that the claim can be retired.
                        self._conn.execute(
                            """
                            DELETE FROM task_transition_claims
                             WHERE project_id = ? AND task_id = ?
                               AND transition_id = ?
                            """,
                            (intent.project_id, intent.task_id, transition_id),
                        )
                        self._conn.commit()
                        return _BeginResult(
                            transition_id,
                            None,
                            replay=TransitionOutcome.from_dict(
                                latest.outcome.to_dict(), replayed=True
                            ),
                        )
                else:
                    self._conn.execute(
                        """
                        INSERT INTO task_transition_requests(
                            transition_id, project_id, task_id, idempotency_key,
                            intent_revision, intent_json, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            transition_id,
                            intent.project_id,
                            intent.task_id,
                            intent.idempotency_key,
                            intent.revision,
                            _canonical_json(intent.to_dict()),
                            _now_iso(),
                        ),
                    )
                    self._append_locked(
                        transition_id,
                        intent.project_id,
                        intent.task_id,
                        TransitionPhase.REQUESTED,
                        intent.reason_code,
                    )

                active = self._conn.execute(
                    """
                    SELECT * FROM task_transition_claims
                     WHERE project_id = ? AND task_id = ?
                    """,
                    (intent.project_id, intent.task_id),
                ).fetchone()
                if active is not None:
                    active_transition = str(active["transition_id"])
                    active_until = float(active["lease_expires_at"])
                    if active_until > now:
                        waiting = TransitionOutcome(
                            transition_id=transition_id,
                            project_id=intent.project_id,
                            task_id=intent.task_id,
                            disposition=TransitionDisposition.WAITING,
                            reason_code="transition.owner_active",
                            observed_status="",
                            observed_version=None,
                            requested_status=intent.requested_status,
                            retryable=True,
                            details={"active_transition_id": active_transition},
                        )
                        self._append_locked(
                            transition_id,
                            intent.project_id,
                            intent.task_id,
                            TransitionPhase.WAITING,
                            waiting.reason_code,
                            waiting,
                        )
                        self._conn.commit()
                        return _BeginResult(transition_id, None, waiting=waiting)
                    if active_transition != transition_id:
                        active_request = self._conn.execute(
                            """
                            SELECT * FROM task_transition_requests
                             WHERE transition_id = ?
                            """,
                            (active_transition,),
                        ).fetchone()
                        if (
                            active_request is None
                            or str(active_request["project_id"]) != intent.project_id
                            or str(active_request["task_id"]) != intent.task_id
                        ):
                            raise TransitionJournalCorruptionError(
                                "transition claim does not match its immutable request"
                            )
                        active_latest = self._latest_event_locked(active_transition)
                        if active_latest is None:
                            raise TransitionJournalCorruptionError(
                                "transition claim has no immutable journal history"
                            )
                        try:
                            active_intent = TransitionIntent.from_dict(
                                json.loads(str(active_request["intent_json"]))
                            )
                        except (
                            TypeError,
                            ValueError,
                            json.JSONDecodeError,
                        ) as exc:
                            raise TransitionJournalCorruptionError(
                                "invalid intent for expired transition claim"
                            ) from exc
                        if (
                            active_intent.revision
                            != str(active_request["intent_revision"])
                            or active_intent.project_id != intent.project_id
                            or active_intent.task_id != intent.task_id
                        ):
                            raise TransitionJournalCorruptionError(
                                "intent mismatch for expired transition claim"
                            )
                        if active_latest.phase in FINAL_PHASES:
                            if active_latest.outcome is None:
                                raise TransitionJournalCorruptionError(
                                    "final expired transition has no durable outcome"
                                )
                        else:
                            expired = TransitionOutcome(
                                transition_id=active_transition,
                                project_id=active_intent.project_id,
                                task_id=active_intent.task_id,
                                disposition=TransitionDisposition.RETRYABLE,
                                reason_code="transition.claim_expired",
                                observed_status="",
                                observed_version=None,
                                requested_status=active_intent.requested_status,
                                retryable=True,
                                details={
                                    "replacement_transition_id": transition_id,
                                    "lease_expires_at": active_until,
                                },
                            )
                            self._append_locked(
                                active_transition,
                                active_intent.project_id,
                                active_intent.task_id,
                                TransitionPhase.RETRY_SCHEDULED,
                                expired.reason_code,
                                expired,
                            )
                            recovery_waiting = TransitionOutcome(
                                transition_id=transition_id,
                                project_id=intent.project_id,
                                task_id=intent.task_id,
                                disposition=TransitionDisposition.WAITING,
                                reason_code="transition.recovery_in_progress",
                                observed_status="",
                                observed_version=None,
                                requested_status=intent.requested_status,
                                retryable=True,
                                details={
                                    "recover_transition_id": active_transition,
                                },
                            )
                            self._append_locked(
                                transition_id,
                                intent.project_id,
                                intent.task_id,
                                TransitionPhase.WAITING,
                                recovery_waiting.reason_code,
                                recovery_waiting,
                            )
                            recovered = self._conn.execute(
                                """
                                UPDATE task_transition_claims
                                   SET claim_token = ?, claimed_at = ?,
                                       lease_expires_at = ?
                                 WHERE project_id = ? AND task_id = ?
                                   AND transition_id = ? AND claim_token = ?
                                   AND lease_expires_at = ?
                                """,
                                (
                                    claim_token,
                                    now,
                                    now + lease_ttl_seconds,
                                    intent.project_id,
                                    intent.task_id,
                                    active_transition,
                                    str(active["claim_token"]),
                                    active_until,
                                ),
                            )
                            if recovered.rowcount != 1:
                                raise TransitionJournalError(
                                    "expired transition claim changed during recovery"
                                )
                            self._conn.commit()
                            return _BeginResult(
                                transition_id,
                                claim_token,
                                recovery_transition_id=active_transition,
                                recovery_intent=active_intent,
                                recovery_previous_phase=active_latest.phase,
                            )
                    deleted = self._conn.execute(
                        """
                        DELETE FROM task_transition_claims
                         WHERE project_id = ? AND task_id = ?
                           AND transition_id = ? AND claim_token = ?
                           AND lease_expires_at = ?
                        """,
                        (
                            intent.project_id,
                            intent.task_id,
                            active_transition,
                            str(active["claim_token"]),
                            active_until,
                        ),
                    )
                    if deleted.rowcount != 1:
                        raise TransitionJournalError(
                            "expired transition claim changed during recovery"
                        )

                self._conn.execute(
                    """
                    INSERT INTO task_transition_claims(
                        project_id, task_id, transition_id, claim_token,
                        claimed_at, lease_expires_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        intent.project_id,
                        intent.task_id,
                        transition_id,
                        claim_token,
                        now,
                        now + lease_ttl_seconds,
                    ),
                )
                self._conn.commit()
                return _BeginResult(
                    transition_id,
                    claim_token,
                    previous_phase=latest.phase if row is not None and latest else None,
                )
            except Exception:
                self._conn.rollback()
                raise

    def release(self, project_id: str, task_id: str, claim_token: str) -> bool:
        with self._admit_use():
            return self._release_admitted(project_id, task_id, claim_token)

    def _release_admitted(
        self,
        project_id: str,
        task_id: str,
        claim_token: str,
    ) -> bool:
        with self._lock:
            cursor = self._conn.execute(
                """
                DELETE FROM task_transition_claims
                 WHERE project_id = ? AND task_id = ? AND claim_token = ?
                """,
                (project_id, task_id, claim_token),
            )
            self._conn.commit()
            return cursor.rowcount == 1

    def expire_for_retry(
        self,
        project_id: str,
        task_id: str,
        claim_token: str,
    ) -> bool:
        """Yield a claim while retaining its durable recovery obligation."""

        with self._admit_use():
            return self._expire_for_retry_admitted(
                project_id,
                task_id,
                claim_token,
            )

    def _expire_for_retry_admitted(
        self,
        project_id: str,
        task_id: str,
        claim_token: str,
    ) -> bool:
        """Expire a claim whose caller already owns lifecycle admission."""

        with self._lock:
            cursor = self._conn.execute(
                """
                UPDATE task_transition_claims
                   SET lease_expires_at = ?
                 WHERE project_id = ? AND task_id = ? AND claim_token = ?
                """,
                (self._clock(), project_id, task_id, claim_token),
            )
            self._conn.commit()
            return cursor.rowcount == 1

    def integrity_check(self) -> None:
        with self._admit_use(), self._lock:
            result = self._conn.execute("PRAGMA integrity_check").fetchone()
            if result is None or str(result[0]).lower() != "ok":
                raise TransitionJournalCorruptionError(
                    f"SQLite integrity check failed: {result[0] if result else 'no result'}"
                )
            request_rows = self._conn.execute(
                "SELECT transition_id, intent_revision, intent_json FROM task_transition_requests"
            ).fetchall()
            for row in request_rows:
                try:
                    intent = TransitionIntent.from_dict(
                        json.loads(str(row["intent_json"]))
                    )
                except (TypeError, ValueError, json.JSONDecodeError) as exc:
                    raise TransitionJournalCorruptionError(
                        f"invalid intent for {row['transition_id']}"
                    ) from exc
                if intent.revision != str(row["intent_revision"]):
                    raise TransitionJournalCorruptionError(
                        f"intent revision mismatch for {row['transition_id']}"
                    )
            event_rows = self._conn.execute(
                "SELECT * FROM task_transition_events ORDER BY sequence"
            ).fetchall()
            for row in event_rows:
                self._event_from_row(row)


class TaskTransitionService:
    """Project-scoped executor for durable transition intents."""

    def __init__(
        self,
        *,
        project_id: str,
        tracker: TrackerProtocol,
        journal: TransitionJournal,
        terminal_adapter: TerminalTransitionAdapter | None = None,
        write_lock: Callable[[], Any] | None = None,
        mutation_write_lock: Callable[[], Any] | None = None,
        direct_owner_write_lock: Callable[[], Any] | None = None,
        direct_owner_claim_guard: DirectOwnerClaimGuard | None = None,
        mutation_guard: TransitionMutationGuard | None = None,
        direct_owner_retirement_guard: DirectOwnerRetirementGuard | None = None,
        claim_ttl_seconds: float = DEFAULT_TRANSITION_CLAIM_TTL_SECONDS,
    ) -> None:
        self.project_id = _required_text(project_id, "project_id")
        self.tracker = tracker
        self.journal = journal
        self.terminal_adapter = terminal_adapter
        self._write_lock = write_lock
        self._mutation_write_lock = mutation_write_lock or write_lock
        self._direct_owner_write_lock = direct_owner_write_lock or write_lock
        self._direct_owner_claim_guard = direct_owner_claim_guard
        self._mutation_guard = mutation_guard
        self._direct_owner_retirement_guard = direct_owner_retirement_guard
        if claim_ttl_seconds <= 0:
            raise ValueError("claim_ttl_seconds must be positive")
        self.claim_ttl_seconds = claim_ttl_seconds

    async def _fetch(self, task_id: str) -> Issue | None:
        operation = self.tracker.fetch_issue_detail
        if inspect.iscoroutinefunction(operation):
            issue = await operation(task_id)
        else:
            issue = await asyncio.to_thread(operation, task_id)
        if issue is not None and not isinstance(issue, Issue):
            # Some compatibility adapters expose an incomplete detail method
            # but a correct point-read API.  Never hash an arbitrary proxy or
            # mock as lifecycle authority; fall back to the narrow state read
            # and fail closed when neither yields a concrete Issue.
            point_read = getattr(self.tracker, "fetch_issue_states_by_ids", None)
            if not callable(point_read):
                return None
            if inspect.iscoroutinefunction(point_read):
                candidates = await point_read([task_id])
            else:
                candidates = await asyncio.to_thread(point_read, [task_id])
            issue = next(
                (
                    candidate
                    for candidate in (candidates or [])
                    if isinstance(candidate, Issue)
                    and task_id
                    in {str(candidate.id), str(candidate.identifier)}
                ),
                None,
            )
        if issue is not None and not issue.project_id:
            issue.project_id = self.project_id
        return issue

    async def _try_fetch(self, task_id: str) -> tuple[Issue | None, Exception | None]:
        try:
            return await self._fetch(task_id), None
        except Exception as exc:  # noqa: BLE001 - tracker transport boundary
            return None, exc

    async def _try_fetch_children(
        self,
        parent: Issue,
    ) -> tuple[list[Issue] | None, Exception | None]:
        """Read current rollup lineage without trusting a caller projection."""

        operation = getattr(self.tracker, "fetch_children", None)
        if not callable(operation):
            return None, RuntimeError("tracker does not expose child lineage")
        try:
            parent_id = str(parent.id or parent.identifier)
            if inspect.iscoroutinefunction(operation):
                observed = await operation(parent_id)
            else:
                observed = await asyncio.to_thread(operation, parent_id)
            children = list(observed or ())
            if not all(isinstance(child, Issue) for child in children):
                raise TypeError("tracker returned invalid child lineage")
            return children, None
        except Exception as exc:  # noqa: BLE001 - tracker transport boundary
            return None, exc

    async def _update(self, task_id: str, status: str) -> None:
        operation = self.tracker.update_issue
        if inspect.iscoroutinefunction(operation):
            lock = self._write_lock() if self._write_lock is not None else None
            if lock is None:
                await operation(task_id, status=status)
                return
            with lock:
                await operation(task_id, status=status)
            return

        def update() -> None:
            context = (
                self._write_lock()
                if self._write_lock is not None
                else contextlib.nullcontext()
            )
            with context:
                operation(task_id, status=status)

        await asyncio.to_thread(update)

    @staticmethod
    def _is_direct_owner_claim_intent(intent: TransitionIntent) -> bool:
        return bool(
            intent.expected_status == BACKLOG
            and intent.requested_status == IN_PROGRESS
        )

    @staticmethod
    def _is_validation_submission_intent(intent: TransitionIntent) -> bool:
        return bool(
            intent.expected_status
            in {OPEN, IN_PROGRESS, NEEDS_CI_FIX, NEEDS_REBASE}
            and intent.requested_status == READY_TO_INTEGRATE
            and intent.reason_code == "implementation.validation_submission"
        )

    def _direct_owner_commit_conflict(
        self,
        intent: TransitionIntent,
        issue: Issue | None,
    ) -> tuple[str | None, bool]:
        """Re-prove direct-owner authority inside the tracker commit lane."""

        if issue is None:
            return "transition.task_missing", False
        if issue.project_id and str(issue.project_id) != intent.project_id:
            return "transition.project_mismatch", False
        if canonicalize_status(issue.state) != intent.expected_status:
            return "transition.stale_status", False
        if issue_authority_version(issue) != intent.expected_version:
            return "transition.stale_version", False
        if intent.authority not in (
            TransitionAuthority.PROJECT_OWNER,
            TransitionAuthority.API,
        ):
            return "transition.project_owner_authority_required", False
        if (
            intent.authority == TransitionAuthority.PROJECT_OWNER
            and intent.reason_code != "implementation.direct_owner_claim"
        ):
            return "transition.direct_owner_claim_authority_required", False
        if not str(getattr(issue, "description", None) or "").strip():
            return "transition.actionable_description_required", False
        
        # Only require owner claim guard validation for PROJECT_OWNER authority
        # API authority is used for system-initiated operations (oompah backend:server)
        # which don't need lease validation.
        if intent.authority == TransitionAuthority.PROJECT_OWNER:
            guard = self._direct_owner_claim_guard
            if guard is None:
                return "transition.owner_claim_authority_unavailable", False
            try:
                conflict = guard(intent, issue)
            except Exception:  # noqa: BLE001 - lease authority must fail closed
                return "transition.owner_claim_validation_failed", True
            reason = str(conflict or "").strip()
            return (reason or None), False
        
        # API authority path: no lease validation needed
        return None, False

    async def _commit_direct_owner_update(
        self,
        intent: TransitionIntent,
    ) -> tuple[Issue | None, str | None, bool]:
        """Validate the exact lease and update status under one project lock."""

        fetch = self.tracker.fetch_issue_detail
        update = self.tracker.update_issue
        if inspect.iscoroutinefunction(fetch) or inspect.iscoroutinefunction(update):
            context = (
                self._direct_owner_write_lock()
                if self._direct_owner_write_lock is not None
                else contextlib.nullcontext()
            )
            with context:
                issue = (
                    await fetch(intent.task_id)
                    if inspect.iscoroutinefunction(fetch)
                    else fetch(intent.task_id)
                )
                if isinstance(issue, Issue) and not issue.project_id:
                    issue.project_id = self.project_id
                concrete = issue if isinstance(issue, Issue) else None
                conflict, retryable = self._direct_owner_commit_conflict(
                    intent,
                    concrete,
                )
                if conflict is not None:
                    return concrete, conflict, retryable
                if inspect.iscoroutinefunction(update):
                    await update(intent.task_id, status=intent.requested_status)
                else:
                    update(intent.task_id, status=intent.requested_status)
                return concrete, None, False

        def commit() -> tuple[Issue | None, str | None, bool]:
            context = (
                self._direct_owner_write_lock()
                if self._direct_owner_write_lock is not None
                else contextlib.nullcontext()
            )
            with context:
                observed = fetch(intent.task_id)
                if isinstance(observed, Issue) and not observed.project_id:
                    observed.project_id = self.project_id
                issue = observed if isinstance(observed, Issue) else None
                conflict, retryable = self._direct_owner_commit_conflict(
                    intent,
                    issue,
                )
                if conflict is not None:
                    return issue, conflict, retryable
                update(intent.task_id, status=intent.requested_status)
                return issue, None, False

        return await asyncio.to_thread(commit)

    def _guarded_commit_conflict(
        self,
        intent: TransitionIntent,
        issue: Issue | None,
    ) -> tuple[str | None, bool, str | None]:
        """Re-prove tracker and workflow authority inside the write lane."""

        if issue is None:
            return "transition.task_missing", False, None
        if issue.project_id and str(issue.project_id) != intent.project_id:
            return "transition.project_mismatch", False, None
        if canonicalize_status(issue.state) != intent.expected_status:
            return "transition.stale_status", False, None
        if issue_authority_version(issue) != intent.expected_version:
            return "transition.stale_version", False, None
        observed_generation = _optional_text(getattr(issue, "assignment_id", None))
        if (
            intent.evidence_generation
            and observed_generation
            and intent.evidence_generation != observed_generation
        ):
            return "transition.generation_mismatch", False, None
        if intent.exact_head:
            observed_head = issue_exact_head(issue)
            guarded_landing_head = (
                _guarded_landing_revision_lane(intent, issue) is not None
            )
            if observed_head != intent.exact_head and not guarded_landing_head:
                return (
                    "transition.head_missing"
                    if observed_head is None
                    else "transition.head_mismatch",
                    False,
                    None,
                )
        guard = self._mutation_guard
        if guard is not None:
            try:
                detail = str(guard(intent, issue) or "").strip()
            except Exception:  # noqa: BLE001 - workflow authority must fail closed
                logger.exception(
                    "Task transition mutation guard failed project=%s task=%s "
                    "reason=%s",
                    intent.project_id,
                    intent.task_id,
                    intent.reason_code,
                )
                return "transition.mutation_guard_failed", True, None
            if detail:
                return "transition.stale_precondition", False, detail

        retirement_guard = self._direct_owner_retirement_guard
        if retirement_guard is None:
            return None, False, None
        try:
            retirement_conflict = str(
                retirement_guard(intent, issue) or ""
            ).strip()
        except Exception:  # noqa: BLE001 - durable retirement must fail closed
            return "transition.owner_retirement_persistence_failed", True, None
        return (retirement_conflict or None), False, None

    async def _commit_guarded_update(
        self,
        intent: TransitionIntent,
    ) -> tuple[Issue | None, str | None, bool, str | None]:
        """Validate workflow authority, retire its owner, and update atomically."""

        fetch = self.tracker.fetch_issue_detail
        update = self.tracker.update_issue
        if inspect.iscoroutinefunction(fetch) or inspect.iscoroutinefunction(update):
            write_lock = (
                self._mutation_write_lock
                if self._mutation_guard is not None
                else self._direct_owner_write_lock
            )
            context = (
                write_lock()
                if write_lock is not None
                else contextlib.nullcontext()
            )
            with context:
                observed = (
                    await fetch(intent.task_id)
                    if inspect.iscoroutinefunction(fetch)
                    else fetch(intent.task_id)
                )
                if isinstance(observed, Issue) and not observed.project_id:
                    observed.project_id = self.project_id
                issue = observed if isinstance(observed, Issue) else None
                conflict, retryable, detail = self._guarded_commit_conflict(
                    intent, issue
                )
                if conflict is not None:
                    return issue, conflict, retryable, detail
                if inspect.iscoroutinefunction(update):
                    await update(intent.task_id, status=intent.requested_status)
                else:
                    update(intent.task_id, status=intent.requested_status)
                return issue, None, False, None

        def commit() -> tuple[Issue | None, str | None, bool, str | None]:
            write_lock = (
                self._mutation_write_lock
                if self._mutation_guard is not None
                else self._direct_owner_write_lock
            )
            context = (
                write_lock()
                if write_lock is not None
                else contextlib.nullcontext()
            )
            with context:
                observed = fetch(intent.task_id)
                if isinstance(observed, Issue) and not observed.project_id:
                    observed.project_id = self.project_id
                issue = observed if isinstance(observed, Issue) else None
                conflict, retryable, detail = self._guarded_commit_conflict(
                    intent, issue
                )
                if conflict is not None:
                    return issue, conflict, retryable, detail
                update(intent.task_id, status=intent.requested_status)
                return issue, None, False, None

        return await asyncio.to_thread(commit)

    def _outcome(
        self,
        transition_id: str,
        intent: TransitionIntent,
        disposition: TransitionDisposition,
        reason_code: str,
        issue: Issue | None,
        **fields: Any,
    ) -> TransitionOutcome:
        return TransitionOutcome(
            transition_id=transition_id,
            project_id=intent.project_id,
            task_id=intent.task_id,
            disposition=disposition,
            reason_code=reason_code,
            observed_status=canonicalize_status(issue.state) if issue else "",
            observed_version=issue_authority_version(issue) if issue else None,
            requested_status=intent.requested_status,
            **fields,
        )

    async def _execute_recovery_claimed(
        self,
        intent: TransitionIntent,
        begin: _BeginResult,
    ) -> TransitionOutcome:
        """Resume an expired immutable intent through its original lane."""

        if _is_authorized_recovery_intent(intent):
            return await self._recover_authorized_claimed(
                intent,
                begin,
                retain_retryable_claim=True,
            )
        return await self._execute_claimed(
            intent,
            begin,
            retain_retryable_claim=True,
        )

    async def execute(self, intent: TransitionIntent) -> TransitionOutcome:
        """Run one ordinary transition under the journal lifetime lease."""

        with self.journal.admit_transition():
            return await self._execute_admitted(intent)

    async def _execute_admitted(self, intent: TransitionIntent) -> TransitionOutcome:
        """Journal, fence, apply, and verify one status transition."""

        if intent.project_id != self.project_id:
            return TransitionOutcome(
                transition_id="",
                project_id=intent.project_id,
                task_id=intent.task_id,
                disposition=TransitionDisposition.REJECTED,
                reason_code="transition.project_mismatch",
                observed_status="",
                observed_version=None,
                requested_status=intent.requested_status,
            )

        begin = await asyncio.to_thread(
            self.journal.begin,
            intent,
            lease_ttl_seconds=self.claim_ttl_seconds,
        )
        if begin.recovery_intent is not None:
            recovery = await self._execute_recovery_claimed(
                begin.recovery_intent,
                _BeginResult(
                    transition_id=_required_text(
                        begin.recovery_transition_id,
                        "recovery_transition_id",
                    ),
                    claim_token=begin.claim_token,
                    previous_phase=begin.recovery_previous_phase,
                ),
            )
            if recovery.retryable:
                pending = self._outcome(
                    begin.transition_id,
                    intent,
                    TransitionDisposition.WAITING,
                    "transition.recovery_pending",
                    None,
                    retryable=True,
                    details={
                        "recover_transition_id": recovery.transition_id,
                        "recovery_reason_code": recovery.reason_code,
                    },
                )
                await asyncio.to_thread(
                    self.journal.append,
                    begin.transition_id,
                    TransitionPhase.WAITING,
                    pending.reason_code,
                    pending,
                )
                return pending
            begin = await asyncio.to_thread(
                self.journal.begin,
                intent,
                lease_ttl_seconds=self.claim_ttl_seconds,
            )
        if begin.replay is not None:
            return begin.replay
        if begin.waiting is not None:
            return begin.waiting
        if begin.claim_token is None:
            raise TransitionJournalError("transition claim was not acquired")
        return await self._execute_claimed(intent, begin)

    async def _execute_claimed(
        self,
        intent: TransitionIntent,
        begin: _BeginResult,
        *,
        retain_retryable_claim: bool = False,
    ) -> TransitionOutcome:
        """Execute an intent whose exact durable task claim is already held."""

        if begin.claim_token is None:
            raise TransitionJournalError("transition claim was not acquired")

        transition_id = begin.transition_id
        claim_token = begin.claim_token
        outcome: TransitionOutcome | None = None
        try:
            issue, fetch_error = await self._try_fetch(intent.task_id)
            if fetch_error is not None:
                outcome = self._outcome(
                    transition_id,
                    intent,
                    TransitionDisposition.RETRYABLE,
                    "transition.tracker_read_failed",
                    None,
                    retryable=True,
                    details={"error_type": type(fetch_error).__name__},
                )
                await asyncio.to_thread(
                    self.journal.append,
                    transition_id,
                    TransitionPhase.RETRY_SCHEDULED,
                    outcome.reason_code,
                    outcome,
                )
                return outcome
            if issue is None:
                outcome = self._outcome(
                    transition_id,
                    intent,
                    TransitionDisposition.REJECTED,
                    "transition.task_missing",
                    None,
                )
                await asyncio.to_thread(
                    self.journal.append,
                    transition_id,
                    TransitionPhase.REJECTED,
                    outcome.reason_code,
                    outcome,
                )
                return outcome
            if issue.project_id and str(issue.project_id) != intent.project_id:
                outcome = self._outcome(
                    transition_id,
                    intent,
                    TransitionDisposition.REJECTED,
                    "transition.project_mismatch",
                    issue,
                )
                await asyncio.to_thread(
                    self.journal.append,
                    transition_id,
                    TransitionPhase.REJECTED,
                    outcome.reason_code,
                    outcome,
                )
                return outcome

            observed_status = canonicalize_status(issue.state)
            observed_version = issue_authority_version(issue)
            if observed_status == intent.requested_status:
                outcome = self._outcome(
                    transition_id,
                    intent,
                    TransitionDisposition.ALREADY_APPLIED,
                    "transition.already_applied",
                    issue,
                    applied_status=observed_status,
                )
                await asyncio.to_thread(
                    self.journal.append,
                    transition_id,
                    TransitionPhase.RECOVERED,
                    outcome.reason_code,
                    outcome,
                )
                return outcome
            if (
                intent.requested_status in TERMINAL_TARGETS
                and observed_status == IN_VALIDATION
                and begin.previous_phase
                in {
                    TransitionPhase.APPLYING,
                    TransitionPhase.VERIFY_PENDING,
                    TransitionPhase.RETRY_SCHEDULED,
                }
            ):
                outcome = self._outcome(
                    transition_id,
                    intent,
                    TransitionDisposition.RECOVERED,
                    "transition.terminal_stage_recovered",
                    issue,
                    applied_status=IN_VALIDATION,
                )
                await asyncio.to_thread(
                    self.journal.append,
                    transition_id,
                    TransitionPhase.RECOVERED,
                    outcome.reason_code,
                    outcome,
                )
                return outcome
            if observed_status != intent.expected_status:
                outcome = self._outcome(
                    transition_id,
                    intent,
                    TransitionDisposition.REJECTED,
                    "transition.stale_status",
                    issue,
                    details={"expected_status": intent.expected_status},
                )
                await asyncio.to_thread(
                    self.journal.append,
                    transition_id,
                    TransitionPhase.REJECTED,
                    outcome.reason_code,
                    outcome,
                )
                return outcome
            if observed_version != intent.expected_version:
                outcome = self._outcome(
                    transition_id,
                    intent,
                    TransitionDisposition.REJECTED,
                    "transition.stale_version",
                    issue,
                    details={"expected_version": intent.expected_version},
                )
                await asyncio.to_thread(
                    self.journal.append,
                    transition_id,
                    TransitionPhase.REJECTED,
                    outcome.reason_code,
                    outcome,
                )
                return outcome
            # ``In Validation`` is not an ordinary lifecycle destination.  The
            # terminal coordinator owns the single atomic operation that first
            # persists an audit request and then stages this tracker status.
            # Accepting a direct intent here would bypass that transaction and
            # leave the runtime with an auditor obligation that has no durable
            # request or job to materialize.  Callers must request the terminal
            # target instead; the terminal-adapter lane below remains the sole
            # staging path.
            if intent.requested_status == IN_VALIDATION:
                outcome = self._outcome(
                    transition_id,
                    intent,
                    TransitionDisposition.REJECTED,
                    AUDIT_STAGING_REQUIRED_REASON,
                    issue,
                )
                await asyncio.to_thread(
                    self.journal.append,
                    transition_id,
                    TransitionPhase.REJECTED,
                    outcome.reason_code,
                    outcome,
                )
                return outcome
            direct_rule = transition_rule(observed_status, intent.requested_status)
            staging_rule = (
                transition_rule(observed_status, IN_VALIDATION)
                if intent.requested_status in TERMINAL_TARGETS
                else None
            )
            if direct_rule is None and staging_rule is None:
                outcome = self._outcome(
                    transition_id,
                    intent,
                    TransitionDisposition.REJECTED,
                    "transition.illegal_edge",
                    issue,
                )
                await asyncio.to_thread(
                    self.journal.append,
                    transition_id,
                    TransitionPhase.REJECTED,
                    outcome.reason_code,
                    outcome,
                )
                return outcome

            epic_rollup_reason = (
                intent.reason_code == "rollup.epic_children_reconciled"
            )
            system_epic_rollup = (
                epic_rollup_reason
                and intent.authority is TransitionAuthority.SYSTEM
            )
            if epic_rollup_reason and not system_epic_rollup:
                outcome = self._outcome(
                    transition_id,
                    intent,
                    TransitionDisposition.REJECTED,
                    "transition.rollup_authority_required",
                    issue,
                )
                await asyncio.to_thread(
                    self.journal.append,
                    transition_id,
                    TransitionPhase.REJECTED,
                    outcome.reason_code,
                    outcome,
                )
                return outcome
            if system_epic_rollup:
                children, lineage_error = await self._try_fetch_children(issue)
                if lineage_error is not None:
                    outcome = self._outcome(
                        transition_id,
                        intent,
                        TransitionDisposition.RETRYABLE,
                        "transition.rollup_lineage_unavailable",
                        issue,
                        retryable=True,
                        details={"error_type": type(lineage_error).__name__},
                    )
                    await asyncio.to_thread(
                        self.journal.append,
                        transition_id,
                        TransitionPhase.RETRY_SCHEDULED,
                        outcome.reason_code,
                        outcome,
                    )
                    return outcome
                if not children:
                    outcome = self._outcome(
                        transition_id,
                        intent,
                        TransitionDisposition.REJECTED,
                        "transition.rollup_authority_required",
                        issue,
                    )
                    await asyncio.to_thread(
                        self.journal.append,
                        transition_id,
                        TransitionPhase.REJECTED,
                        outcome.reason_code,
                        outcome,
                    )
                    return outcome
                observed_rollup_generation = rollup_authority_generation(
                    issue,
                    children,
                )
                if intent.evidence_generation != observed_rollup_generation:
                    outcome = self._outcome(
                        transition_id,
                        intent,
                        TransitionDisposition.REJECTED,
                        "transition.rollup_generation_mismatch",
                        issue,
                        details={
                            "observed_rollup_generation": (
                                observed_rollup_generation
                            )
                        },
                    )
                    await asyncio.to_thread(
                        self.journal.append,
                        transition_id,
                        TransitionPhase.REJECTED,
                        outcome.reason_code,
                        outcome,
                    )
                    return outcome

            if (
                observed_status == OPEN
                and intent.requested_status == DONE
                and (
                    intent.authority is not TransitionAuthority.AUDITOR
                    or intent.reason_code != "maintenance.publication_proven"
                    or not direct_epic_maintenance_handoff_ready(issue)
                )
            ):
                outcome = self._outcome(
                    transition_id,
                    intent,
                    TransitionDisposition.REJECTED,
                    "transition.maintenance_audit_authority_required",
                    issue,
                )
                await asyncio.to_thread(
                    self.journal.append,
                    transition_id,
                    TransitionPhase.REJECTED,
                    outcome.reason_code,
                    outcome,
                )
                return outcome

            # A terminal request is not a direct tracker edge: the terminal
            # coordinator first stages the task in In Validation, then an
            # auditor applies the requested target.  Accept callers whose
            # current state has either the explicit terminal edge or the
            # staging edge, and retain the evidence requirements from both.
            # This lets legacy completion paths such as In Progress -> Done
            # enter audit without permitting Open -> Merged, while preserving
            # Merged's exact-head and containment requirements.
            requirements = frozenset(
                requirement
                for rule in (direct_rule, staging_rule)
                if rule is not None
                for requirement in rule.requirements
            )
            if (
                observed_status == BACKLOG
                and intent.requested_status == IN_PROGRESS
                and intent.authority not in (
                    TransitionAuthority.PROJECT_OWNER,
                    TransitionAuthority.API,
                )
            ):
                outcome = self._outcome(
                    transition_id,
                    intent,
                    TransitionDisposition.REJECTED,
                    "transition.project_owner_authority_required",
                    issue,
                )
                await asyncio.to_thread(
                    self.journal.append,
                    transition_id,
                    TransitionPhase.REJECTED,
                    outcome.reason_code,
                    outcome,
                )
                return outcome
            if (
                observed_status == OPEN
                and intent.requested_status == READY_TO_INTEGRATE
                and (
                    intent.authority is not TransitionAuthority.ORCHESTRATOR
                    or not self._is_validation_submission_intent(intent)
                )
            ):
                outcome = self._outcome(
                    transition_id,
                    intent,
                    TransitionDisposition.REJECTED,
                    "transition.validation_submission_authority_required",
                    issue,
                )
                await asyncio.to_thread(
                    self.journal.append,
                    transition_id,
                    TransitionPhase.REJECTED,
                    outcome.reason_code,
                    outcome,
                )
                return outcome
            if (
                TransitionRequirement.IMPLEMENTATION_GENERATION in requirements
                and not intent.evidence_generation
            ):
                outcome = self._outcome(
                    transition_id,
                    intent,
                    TransitionDisposition.REJECTED,
                    "transition.generation_required",
                    issue,
                )
                await asyncio.to_thread(
                    self.journal.append,
                    transition_id,
                    TransitionPhase.REJECTED,
                    outcome.reason_code,
                    outcome,
                )
                return outcome
            observed_generation = _optional_text(getattr(issue, "assignment_id", None))
            if (
                intent.evidence_generation
                and observed_generation
                and intent.evidence_generation != observed_generation
                and not system_epic_rollup
            ):
                outcome = self._outcome(
                    transition_id,
                    intent,
                    TransitionDisposition.REJECTED,
                    "transition.generation_mismatch",
                    issue,
                    details={"observed_generation": observed_generation},
                )
                await asyncio.to_thread(
                    self.journal.append,
                    transition_id,
                    TransitionPhase.REJECTED,
                    outcome.reason_code,
                    outcome,
                )
                return outcome
            head_required = bool(
                requirements
                & {
                    TransitionRequirement.ACCEPTED_SUBMISSION,
                    TransitionRequirement.LANDING_EVIDENCE,
                }
            )
            if head_required and not intent.exact_head:
                outcome = self._outcome(
                    transition_id,
                    intent,
                    TransitionDisposition.REJECTED,
                    "transition.head_required",
                    issue,
                )
                await asyncio.to_thread(
                    self.journal.append,
                    transition_id,
                    TransitionPhase.REJECTED,
                    outcome.reason_code,
                    outcome,
                )
                return outcome
            if intent.exact_head:
                observed_head = issue_exact_head(issue)
                guarded_landing_head = (
                    _guarded_landing_revision_lane(intent, issue) is not None
                )
                if observed_head != intent.exact_head and not guarded_landing_head:
                    outcome = self._outcome(
                        transition_id,
                        intent,
                        TransitionDisposition.REJECTED,
                        (
                            "transition.head_missing"
                            if observed_head is None
                            else "transition.head_mismatch"
                        ),
                        issue,
                        details={"observed_head": observed_head},
                    )
                    await asyncio.to_thread(
                        self.journal.append,
                        transition_id,
                        TransitionPhase.REJECTED,
                        outcome.reason_code,
                        outcome,
                    )
                    return outcome

            await asyncio.to_thread(
                self.journal.append,
                transition_id,
                TransitionPhase.APPLYING,
                intent.reason_code,
            )
            if intent.requested_status in TERMINAL_TARGETS:
                if self.terminal_adapter is None:
                    outcome = self._outcome(
                        transition_id,
                        intent,
                        TransitionDisposition.RETRYABLE,
                        "transition.terminal_service_unavailable",
                        issue,
                        retryable=True,
                    )
                    await asyncio.to_thread(
                        self.journal.append,
                        transition_id,
                        TransitionPhase.RETRY_SCHEDULED,
                        outcome.reason_code,
                        outcome,
                    )
                    return outcome
                try:
                    staged = await self.terminal_adapter.stage(intent, issue)
                except Exception as exc:  # noqa: BLE001 - durable retry boundary
                    latest, _ = await self._try_fetch(intent.task_id)
                    if latest and canonicalize_status(latest.state) == IN_VALIDATION:
                        outcome = self._outcome(
                            transition_id,
                            intent,
                            TransitionDisposition.RECOVERED,
                            "transition.terminal_stage_recovered",
                            latest,
                            applied_status=IN_VALIDATION,
                        )
                        await asyncio.to_thread(
                            self.journal.append,
                            transition_id,
                            TransitionPhase.RECOVERED,
                            outcome.reason_code,
                            outcome,
                        )
                        return outcome
                    outcome = self._outcome(
                        transition_id,
                        intent,
                        TransitionDisposition.RETRYABLE,
                        "transition.terminal_stage_failed",
                        latest or issue,
                        retryable=True,
                        details={"error_type": type(exc).__name__},
                    )
                    await asyncio.to_thread(
                        self.journal.append,
                        transition_id,
                        TransitionPhase.RETRY_SCHEDULED,
                        outcome.reason_code,
                        outcome,
                    )
                    return outcome
                latest, _ = await self._try_fetch(intent.task_id)
                if not staged.success:
                    delivery_busy = (
                        staged.reason_code == "transition.delivery_mutation_in_progress"
                    )
                    outcome = self._outcome(
                        transition_id,
                        intent,
                        (
                            TransitionDisposition.RETRYABLE
                            if delivery_busy
                            else TransitionDisposition.REJECTED
                        ),
                        staged.reason_code,
                        latest or issue,
                        retryable=delivery_busy,
                        details={"detail": staged.detail},
                    )
                    await asyncio.to_thread(
                        self.journal.append,
                        transition_id,
                        (
                            TransitionPhase.RETRY_SCHEDULED
                            if delivery_busy
                            else TransitionPhase.REJECTED
                        ),
                        outcome.reason_code,
                        outcome,
                    )
                    return outcome
                if latest is None or canonicalize_status(latest.state) != IN_VALIDATION:
                    outcome = self._outcome(
                        transition_id,
                        intent,
                        TransitionDisposition.RETRYABLE,
                        "transition.terminal_verify_pending",
                        latest or issue,
                        audit_id=staged.audit_id,
                        retryable=True,
                    )
                    await asyncio.to_thread(
                        self.journal.append,
                        transition_id,
                        TransitionPhase.VERIFY_PENDING,
                        outcome.reason_code,
                        outcome,
                    )
                    return outcome
                outcome = self._outcome(
                    transition_id,
                    intent,
                    TransitionDisposition.STAGED,
                    staged.reason_code,
                    latest,
                    applied_status=IN_VALIDATION,
                    audit_id=staged.audit_id,
                )
                await asyncio.to_thread(
                    self.journal.append,
                    transition_id,
                    TransitionPhase.STAGED,
                    outcome.reason_code,
                    outcome,
                )
                return outcome

            try:
                if self._is_direct_owner_claim_intent(intent):
                    guarded_issue, commit_conflict, retryable_conflict = (
                        await self._commit_direct_owner_update(intent)
                    )
                    if commit_conflict is not None:
                        outcome = self._outcome(
                            transition_id,
                            intent,
                            (
                                TransitionDisposition.RETRYABLE
                                if retryable_conflict
                                else TransitionDisposition.REJECTED
                            ),
                            commit_conflict,
                            guarded_issue or issue,
                            retryable=retryable_conflict,
                        )
                        await asyncio.to_thread(
                            self.journal.append,
                            transition_id,
                            (
                                TransitionPhase.RETRY_SCHEDULED
                                if retryable_conflict
                                else TransitionPhase.REJECTED
                            ),
                            outcome.reason_code,
                            outcome,
                        )
                        return outcome
                elif (
                    self._is_validation_submission_intent(intent)
                    and (
                        self._mutation_guard is not None
                        or self._direct_owner_retirement_guard is not None
                    )
                ):
                    (
                        guarded_issue,
                        commit_conflict,
                        retryable_conflict,
                        conflict_detail,
                    ) = await self._commit_guarded_update(intent)
                    if commit_conflict is not None:
                        outcome = self._outcome(
                            transition_id,
                            intent,
                            (
                                TransitionDisposition.RETRYABLE
                                if retryable_conflict
                                else TransitionDisposition.REJECTED
                            ),
                            commit_conflict,
                            guarded_issue or issue,
                            retryable=retryable_conflict,
                            details=(
                                {"detail": conflict_detail}
                                if conflict_detail
                                else {}
                            ),
                        )
                        await asyncio.to_thread(
                            self.journal.append,
                            transition_id,
                            (
                                TransitionPhase.RETRY_SCHEDULED
                                if retryable_conflict
                                else TransitionPhase.REJECTED
                            ),
                            outcome.reason_code,
                            outcome,
                        )
                        return outcome
                else:
                    if canonicalize_status(intent.requested_status) == NEEDS_HUMAN:
                        logger.info(
                            "Task escalation to Needs Human: "
                            "task=%s project=%s actor=%s authority=%s reason=%s",
                            intent.task_id,
                            intent.project_id,
                            intent.actor,
                            intent.authority,
                            intent.reason_code,
                        )
                    await self._update(intent.task_id, intent.requested_status)
            except Exception as exc:  # noqa: BLE001 - verify ambiguous tracker write
                latest, _ = await self._try_fetch(intent.task_id)
                if (
                    latest
                    and canonicalize_status(latest.state) == intent.requested_status
                ):
                    outcome = self._outcome(
                        transition_id,
                        intent,
                        TransitionDisposition.RECOVERED,
                        "transition.effect_recovered",
                        latest,
                        applied_status=intent.requested_status,
                    )
                    await asyncio.to_thread(
                        self.journal.append,
                        transition_id,
                        TransitionPhase.RECOVERED,
                        outcome.reason_code,
                        outcome,
                    )
                    return outcome
                outcome = self._outcome(
                    transition_id,
                    intent,
                    TransitionDisposition.RETRYABLE,
                    "transition.tracker_write_failed",
                    latest or issue,
                    retryable=True,
                    details={"error_type": type(exc).__name__},
                )
                await asyncio.to_thread(
                    self.journal.append,
                    transition_id,
                    TransitionPhase.RETRY_SCHEDULED,
                    outcome.reason_code,
                    outcome,
                )
                return outcome

            latest, _ = await self._try_fetch(intent.task_id)
            if (
                latest is None
                or canonicalize_status(latest.state) != intent.requested_status
            ):
                outcome = self._outcome(
                    transition_id,
                    intent,
                    TransitionDisposition.RETRYABLE,
                    "transition.verify_pending",
                    latest or issue,
                    retryable=True,
                )
                await asyncio.to_thread(
                    self.journal.append,
                    transition_id,
                    TransitionPhase.VERIFY_PENDING,
                    outcome.reason_code,
                    outcome,
                )
                return outcome
            outcome = self._outcome(
                transition_id,
                intent,
                TransitionDisposition.APPLIED,
                "transition.applied",
                latest,
                applied_status=intent.requested_status,
            )
            await asyncio.to_thread(
                self.journal.append,
                transition_id,
                TransitionPhase.APPLIED,
                outcome.reason_code,
                outcome,
            )
            return outcome
        finally:
            if retain_retryable_claim and outcome is not None and outcome.retryable:
                retained = await asyncio.to_thread(
                    self.journal.expire_for_retry,
                    intent.project_id,
                    intent.task_id,
                    claim_token,
                )
                if not retained:
                    raise TransitionJournalError(
                        "retryable recovery lost its durable task claim"
                    )
            else:
                await asyncio.to_thread(
                    self.journal.release,
                    intent.project_id,
                    intent.task_id,
                    claim_token,
                )

    async def recover_authorized(self, intent: TransitionIntent) -> TransitionOutcome:
        """Run one authorized recovery under the journal lifetime lease."""

        with self.journal.admit_transition():
            return await self._recover_authorized_admitted(intent)

    async def _recover_authorized_admitted(
        self,
        intent: TransitionIntent,
    ) -> TransitionOutcome:
        """Apply a pre-authorized recovery without re-running lifecycle policy.

        This narrow path exists for durable authorities that are themselves the
        source of truth for a compensating write: terminal-audit verdict/override
        recovery, cancelled intake retirement, and provenance owner rearm.  It
        retains the same immutable journal, per-task claim, status/version CAS,
        ambiguous-write recovery, and verification as ordinary transitions, but
        deliberately does not restage a terminal audit or require a normal graph
        edge that the recorded compensation is repairing.
        """

        if not _is_authorized_recovery_intent(intent):
            return TransitionOutcome(
                transition_id="",
                project_id=intent.project_id,
                task_id=intent.task_id,
                disposition=TransitionDisposition.REJECTED,
                reason_code="transition.recovery_authority_rejected",
                observed_status="",
                observed_version=None,
                requested_status=intent.requested_status,
            )
        if intent.project_id != self.project_id:
            return TransitionOutcome(
                transition_id="",
                project_id=intent.project_id,
                task_id=intent.task_id,
                disposition=TransitionDisposition.REJECTED,
                reason_code="transition.project_mismatch",
                observed_status="",
                observed_version=None,
                requested_status=intent.requested_status,
            )

        begin = await asyncio.to_thread(
            self.journal.begin,
            intent,
            lease_ttl_seconds=self.claim_ttl_seconds,
        )
        if begin.recovery_intent is not None:
            recovery = await self._execute_recovery_claimed(
                begin.recovery_intent,
                _BeginResult(
                    transition_id=_required_text(
                        begin.recovery_transition_id,
                        "recovery_transition_id",
                    ),
                    claim_token=begin.claim_token,
                    previous_phase=begin.recovery_previous_phase,
                ),
            )
            if recovery.retryable:
                pending = self._outcome(
                    begin.transition_id,
                    intent,
                    TransitionDisposition.WAITING,
                    "transition.recovery_pending",
                    None,
                    retryable=True,
                    details={
                        "recover_transition_id": recovery.transition_id,
                        "recovery_reason_code": recovery.reason_code,
                    },
                )
                await asyncio.to_thread(
                    self.journal.append,
                    begin.transition_id,
                    TransitionPhase.WAITING,
                    pending.reason_code,
                    pending,
                )
                return pending
            begin = await asyncio.to_thread(
                self.journal.begin,
                intent,
                lease_ttl_seconds=self.claim_ttl_seconds,
            )
        if begin.replay is not None:
            return begin.replay
        if begin.waiting is not None:
            return begin.waiting
        if begin.claim_token is None:
            raise TransitionJournalError("transition claim was not acquired")
        return await self._recover_authorized_claimed(intent, begin)

    async def _recover_authorized_claimed(
        self,
        intent: TransitionIntent,
        begin: _BeginResult,
        *,
        retain_retryable_claim: bool = False,
    ) -> TransitionOutcome:
        """Execute an authorized compensation whose durable claim is held."""

        if begin.claim_token is None:
            raise TransitionJournalError("transition claim was not acquired")

        transition_id = begin.transition_id
        claim_token = begin.claim_token
        outcome: TransitionOutcome | None = None
        try:
            issue, fetch_error = await self._try_fetch(intent.task_id)
            if fetch_error is not None:
                outcome = self._outcome(
                    transition_id,
                    intent,
                    TransitionDisposition.RETRYABLE,
                    "transition.tracker_read_failed",
                    None,
                    retryable=True,
                    details={"error_type": type(fetch_error).__name__},
                )
                await asyncio.to_thread(
                    self.journal.append,
                    transition_id,
                    TransitionPhase.RETRY_SCHEDULED,
                    outcome.reason_code,
                    outcome,
                )
                return outcome
            if issue is None:
                outcome = self._outcome(
                    transition_id,
                    intent,
                    TransitionDisposition.REJECTED,
                    "transition.task_missing",
                    None,
                )
                await asyncio.to_thread(
                    self.journal.append,
                    transition_id,
                    TransitionPhase.REJECTED,
                    outcome.reason_code,
                    outcome,
                )
                return outcome
            if issue.project_id and str(issue.project_id) != intent.project_id:
                outcome = self._outcome(
                    transition_id,
                    intent,
                    TransitionDisposition.REJECTED,
                    "transition.project_mismatch",
                    issue,
                )
                await asyncio.to_thread(
                    self.journal.append,
                    transition_id,
                    TransitionPhase.REJECTED,
                    outcome.reason_code,
                    outcome,
                )
                return outcome

            observed_status = canonicalize_status(issue.state)
            observed_version = issue_authority_version(issue)
            if observed_status == intent.requested_status:
                outcome = self._outcome(
                    transition_id,
                    intent,
                    TransitionDisposition.ALREADY_APPLIED,
                    "transition.already_applied",
                    issue,
                    applied_status=observed_status,
                )
                await asyncio.to_thread(
                    self.journal.append,
                    transition_id,
                    TransitionPhase.RECOVERED,
                    outcome.reason_code,
                    outcome,
                )
                return outcome
            stale_reason = None
            stale_details: dict[str, Any] = {}
            if observed_status != intent.expected_status:
                stale_reason = "transition.stale_status"
                stale_details["expected_status"] = intent.expected_status
            elif observed_version != intent.expected_version:
                stale_reason = "transition.stale_version"
                stale_details["expected_version"] = intent.expected_version
            if stale_reason is not None:
                outcome = self._outcome(
                    transition_id,
                    intent,
                    TransitionDisposition.REJECTED,
                    stale_reason,
                    issue,
                    details=stale_details,
                )
                await asyncio.to_thread(
                    self.journal.append,
                    transition_id,
                    TransitionPhase.REJECTED,
                    outcome.reason_code,
                    outcome,
                )
                return outcome

            await asyncio.to_thread(
                self.journal.append,
                transition_id,
                TransitionPhase.APPLYING,
                intent.reason_code,
            )
            try:
                if canonicalize_status(intent.requested_status) == NEEDS_HUMAN:
                    logger.info(
                        "Task escalation to Needs Human: "
                        "task=%s project=%s actor=%s authority=%s reason=%s",
                        intent.task_id,
                        intent.project_id,
                        intent.actor,
                        intent.authority,
                        intent.reason_code,
                    )
                await self._update(intent.task_id, intent.requested_status)
            except Exception as exc:  # noqa: BLE001 - verify ambiguous write
                latest, _ = await self._try_fetch(intent.task_id)
                if latest and canonicalize_status(latest.state) == intent.requested_status:
                    outcome = self._outcome(
                        transition_id,
                        intent,
                        TransitionDisposition.RECOVERED,
                        "transition.effect_recovered",
                        latest,
                        applied_status=intent.requested_status,
                    )
                    await asyncio.to_thread(
                        self.journal.append,
                        transition_id,
                        TransitionPhase.RECOVERED,
                        outcome.reason_code,
                        outcome,
                    )
                    return outcome
                outcome = self._outcome(
                    transition_id,
                    intent,
                    TransitionDisposition.RETRYABLE,
                    "transition.tracker_write_failed",
                    latest or issue,
                    retryable=True,
                    details={"error_type": type(exc).__name__},
                )
                await asyncio.to_thread(
                    self.journal.append,
                    transition_id,
                    TransitionPhase.RETRY_SCHEDULED,
                    outcome.reason_code,
                    outcome,
                )
                return outcome

            latest, _ = await self._try_fetch(intent.task_id)
            if latest is None or canonicalize_status(latest.state) != intent.requested_status:
                outcome = self._outcome(
                    transition_id,
                    intent,
                    TransitionDisposition.RETRYABLE,
                    "transition.verify_pending",
                    latest or issue,
                    retryable=True,
                )
                await asyncio.to_thread(
                    self.journal.append,
                    transition_id,
                    TransitionPhase.VERIFY_PENDING,
                    outcome.reason_code,
                    outcome,
                )
                return outcome
            outcome = self._outcome(
                transition_id,
                intent,
                TransitionDisposition.APPLIED,
                "transition.applied",
                latest,
                applied_status=intent.requested_status,
            )
            await asyncio.to_thread(
                self.journal.append,
                transition_id,
                TransitionPhase.APPLIED,
                outcome.reason_code,
                outcome,
            )
            return outcome
        finally:
            if retain_retryable_claim and outcome is not None and outcome.retryable:
                retained = await asyncio.to_thread(
                    self.journal.expire_for_retry,
                    intent.project_id,
                    intent.task_id,
                    claim_token,
                )
                if not retained:
                    raise TransitionJournalError(
                        "retryable recovery lost its durable task claim"
                    )
            else:
                await asyncio.to_thread(
                    self.journal.release,
                    intent.project_id,
                    intent.task_id,
                    claim_token,
                )
