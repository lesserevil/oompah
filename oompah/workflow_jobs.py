"""Durable, leased workflow jobs with restart-safe ownership semantics.

The workflow-job store is intentionally domain-neutral.  Schedulers enqueue an
exact action for an exact task/evidence generation; workers receive an opaque
lease token and every worker-side mutation is fenced by that token and its
expiry.  Terminal rows are immutable through the public API, so retries and
duplicate wakeups cannot revive cancelled or superseded work.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
import threading
import time
import uuid
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any

from oompah.workflow_fact_model import LandingFact

try:  # pragma: no cover - the service runtime is POSIX-only today
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]

WORKFLOW_JOB_SCHEMA_VERSION = 8
DEFAULT_SCAN_LIMIT = 100
MAX_SCAN_LIMIT = 1000
_MAX_ADMINISTRATIVE_BACKOFF_EXPONENT = 10
_INITIALIZE_LOCK = threading.Lock()
_REASSESSMENT_GENERATION_MARKER = ":reassess="
_AUTHORITY_RETIREMENT_KINDS = frozenset(
    {
        "managed_decision",
        "managed_zero_job",
        "terminal_audit_handoff",
        "lifecycle_final",
    }
)
_LIFECYCLE_FINAL_AUTHORITY_REVISIONS = frozenset(
    {"lifecycle-final:Merged", "lifecycle-final:Archived"}
)
_LIFECYCLE_FINAL_ARCHIVED_REVISION = "lifecycle-final:Archived"
# Persisted high-water mark for the monotonic ``workflow_job_events.sequence``.
# Archival relocates the tail of the ledger into cold storage, so ``MAX``
# across the hot table alone can regress.  This meta key preserves the true
# global maximum so the snapshot-authority ABA fence never observes a lower
# sequence after archival.
_JOB_EVENT_HIGHWATER_KEY = "workflow_job_events_highwater_sequence"

# One exhausted ledger row stops being current only after an exact retirement
# proof is published, or when a published durable lane cursor names another
# fully materialized generation with a concrete, non-retired job. Cursor
# movement and staged proofs are not execution authority: evaluation may
# advance a decision revision before reconciliation, and publication may still
# roll back. Unknown, legacy, and partially written authority therefore remain
# current (fail closed). Keep this predicate shared by the per-task lookup and
# global health telemetry so their meanings cannot drift apart again.
_DURABLE_RETIREMENT_PROOF_PREDICATE = """
(
    (
        retirement.authority_kind = 'event_handoff'
        AND retirement.snapshot_generation IS NULL
        AND job.workflow_managed = 0
        AND EXISTS (
            SELECT 1
              FROM workflow_event_cursors cursor
              JOIN workflow_jobs handoff
                ON handoff.project_id = cursor.project_id
               AND handoff.task_id = cursor.task_id
               AND handoff.scheduling_lane = cursor.event_namespace
               AND handoff.generation = cursor.event_generation
             WHERE cursor.project_id = retirement.project_id
               AND cursor.task_id = retirement.task_id
               AND cursor.event_generation = retirement.decision_revision
               AND handoff.workflow_managed = 0
               AND handoff.state NOT IN ('superseded', 'cancelled')
        )
    )
    OR (
        retirement.authority_kind = 'terminal_audit_handoff'
        AND retirement.snapshot_generation IS NULL
        AND EXISTS (
            SELECT 1
              FROM workflow_jobs handoff
             WHERE handoff.project_id = retirement.project_id
               AND handoff.task_id = retirement.task_id
               AND handoff.workflow_managed = 0
               AND handoff.action = 'terminal_audit'
               AND handoff.scheduling_lane LIKE 'terminal-audit:%'
               AND handoff.generation = retirement.decision_revision
        )
    )
    OR (
        retirement.authority_kind IN (
            'managed_decision', 'managed_zero_job'
        )
        AND retirement.snapshot_generation IS NOT NULL
        AND job.workflow_managed = 1
        AND EXISTS (
            SELECT 1
              FROM workflow_snapshot_publications publication
             WHERE publication.snapshot_generation =
                   retirement.snapshot_generation
        )
        AND EXISTS (
            SELECT 1
              FROM workflow_retirement_authority_cuts authority_cut
             WHERE authority_cut.project_id = retirement.project_id
               AND authority_cut.task_id = retirement.task_id
               AND authority_cut.snapshot_generation =
                   retirement.snapshot_generation
               AND authority_cut.authority_kind =
                   retirement.authority_kind
               AND authority_cut.decision_revision =
                   retirement.decision_revision
               AND authority_cut.job_generation IS NOT NULL
               AND authority_cut.job_generation != job.generation
        )
    )
    OR (
        retirement.authority_kind = 'lifecycle_final'
        AND retirement.snapshot_generation IS NOT NULL
        AND retirement.decision_revision IN (
            'lifecycle-final:Merged', 'lifecycle-final:Archived'
        )
        AND EXISTS (
            SELECT 1
              FROM workflow_snapshot_publications publication
             WHERE publication.snapshot_generation =
                   retirement.snapshot_generation
        )
        AND EXISTS (
            SELECT 1
              FROM workflow_retirement_authority_cuts authority_cut
             WHERE authority_cut.project_id = retirement.project_id
               AND authority_cut.task_id = retirement.task_id
               AND authority_cut.snapshot_generation =
                   retirement.snapshot_generation
               AND authority_cut.authority_kind = 'lifecycle_final'
               AND authority_cut.decision_revision =
                   retirement.decision_revision
               AND authority_cut.job_generation IS NULL
        )
    )
)
"""

_CURRENT_EXHAUSTION_PREDICATE = f"""
job.state = 'exhausted'
AND NOT (
    EXISTS (
        SELECT 1
          FROM workflow_job_retirements retirement
         WHERE retirement.job_id = job.job_id
           AND retirement.project_id = job.project_id
           AND retirement.task_id = job.task_id
           AND {_DURABLE_RETIREMENT_PROOF_PREDICATE}
    )
    OR
    (job.workflow_managed = 1 AND EXISTS (
        SELECT 1
          FROM workflow_schedule_cursors cursor
         WHERE cursor.project_id = job.project_id
           AND cursor.task_id = job.task_id
           AND EXISTS (
               SELECT 1
                 FROM workflow_snapshot_publications publication
                WHERE publication.snapshot_generation =
                      cursor.snapshot_generation
           )
           AND cursor.job_generation != job.generation
           AND cursor.materialized_job_generation = cursor.job_generation
           AND EXISTS (
               SELECT 1
                 FROM workflow_jobs replacement
                WHERE replacement.project_id = job.project_id
                  AND replacement.task_id = job.task_id
                  AND replacement.workflow_managed = 1
                  AND replacement.generation = cursor.job_generation
                  AND replacement.state IN (
                      'queued', 'running', 'retry_wait',
                      'completed', 'exhausted'
                  )
           )
    ))
    OR
    (job.workflow_managed = 0 AND EXISTS (
        SELECT 1
          FROM workflow_event_cursors cursor
         WHERE cursor.project_id = job.project_id
           AND cursor.task_id = job.task_id
           AND cursor.event_namespace = job.scheduling_lane
           AND cursor.event_generation != job.generation
           AND EXISTS (
               SELECT 1
                 FROM workflow_jobs replacement
                WHERE replacement.project_id = job.project_id
                  AND replacement.task_id = job.task_id
                  AND replacement.workflow_managed = 0
                  AND replacement.scheduling_lane = job.scheduling_lane
                  AND replacement.generation = cursor.event_generation
                  AND replacement.state IN (
                      'queued', 'running', 'retry_wait',
                      'completed', 'exhausted'
                  )
           )
    ))
    OR
    (job.workflow_managed = 0 AND NOT EXISTS (
        SELECT 1
          FROM workflow_event_cursors cursor
         WHERE cursor.project_id = job.project_id
           AND cursor.task_id = job.task_id
           AND cursor.event_namespace = job.scheduling_lane
    ) AND EXISTS (
        SELECT 1
          FROM workflow_event_ordering ordering
         WHERE ordering.project_id = job.project_id
           AND ordering.task_id = job.task_id
           AND ordering.ordering_namespace = job.scheduling_lane
           AND ordering.decision_revision != job.generation
           AND EXISTS (
               SELECT 1
                 FROM workflow_jobs replacement
                WHERE replacement.project_id = job.project_id
                  AND replacement.task_id = job.task_id
                  AND replacement.workflow_managed = 0
                  AND replacement.scheduling_lane = job.scheduling_lane
                  AND replacement.generation = ordering.decision_revision
                  AND replacement.state IN (
                      'queued', 'running', 'retry_wait',
                      'completed', 'exhausted'
                  )
           )
    ))
)
"""


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


def _schedule_reassessment_deadline(value: object) -> float | None:
    raw = str(value or "")
    if _REASSESSMENT_GENERATION_MARKER not in raw:
        return None
    try:
        deadline = float(raw.rsplit(_REASSESSMENT_GENERATION_MARKER, 1)[1])
    except ValueError:
        return None
    return deadline if math.isfinite(deadline) else None


def _job_row_proves_live_authority(
    row: Mapping[str, Any] | sqlite3.Row,
    *,
    now: float,
    completed_until: float | None = None,
) -> bool:
    state = WorkflowJobState(str(row["state"]))
    if state in {WorkflowJobState.QUEUED, WorkflowJobState.RETRY_WAIT}:
        return True
    if state is WorkflowJobState.RUNNING:
        return bool(
            str(row["lease_owner"] or "").strip()
            and row["lease_expires_at"] is not None
            and float(row["lease_expires_at"]) > now
        )
    return bool(
        state is WorkflowJobState.COMPLETED
        and completed_until is not None
        and now < completed_until
    )


def _freeze_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType(
            {
                str(key): _freeze_json(item)
                for key, item in sorted(value.items(), key=lambda item: str(item[0]))
            }
        )
    if isinstance(value, list | tuple):
        return tuple(_freeze_json(item) for item in value)
    return value


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw_json(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_thaw_json(item) for item in value]
    return value


def _canonical_json(value: object) -> str:
    return json.dumps(
        _thaw_json(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def _json_object(
    value: Mapping[str, Any] | None, name: str
) -> Mapping[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    # Round-tripping also rejects values SQLite could persist but workers could
    # not later reproduce (sets, byte strings, custom objects, and NaN).
    try:
        raw = json.dumps(
            _thaw_json(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
        decoded = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be JSON serializable") from exc
    if not isinstance(decoded, dict):
        raise TypeError(f"{name} must be a JSON object")
    return _freeze_json(decoded)


def _decode_json_object(value: object, name: str) -> Mapping[str, Any] | None:
    if value is None:
        return None
    try:
        decoded = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise WorkflowJobCorruptionError(f"invalid {name} JSON") from exc
    if not isinstance(decoded, dict):
        raise WorkflowJobCorruptionError(f"{name} must be a JSON object")
    return _freeze_json(decoded)


def _bounded_limit(limit: int) -> int:
    if isinstance(limit, bool):
        raise ValueError("limit must be an integer")
    value = int(limit)
    if value < 1 or value > MAX_SCAN_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_SCAN_LIMIT}")
    return value


class WorkflowJobState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    RETRY_WAIT = "retry_wait"
    COMPLETED = "completed"
    EXHAUSTED = "exhausted"
    SUPERSEDED = "superseded"
    CANCELLED = "cancelled"


ACTIVE_JOB_STATES = frozenset(
    {
        WorkflowJobState.QUEUED,
        WorkflowJobState.RUNNING,
        WorkflowJobState.RETRY_WAIT,
    }
)
TERMINAL_JOB_STATES = frozenset(set(WorkflowJobState) - ACTIVE_JOB_STATES)


class WorkflowFailureCategory(str, Enum):
    TRANSIENT = "transient"
    TIMEOUT = "timeout"
    TRANSPORT = "transport"
    AUTHORIZATION = "authorization"
    POLICY = "policy"
    STALE_EVIDENCE = "stale_evidence"
    PERMANENT = "permanent"
    LEASE_EXPIRED = "lease_expired"
    ABANDONED = "abandoned"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class WorkflowJobSpec:
    """Immutable identity and execution fence for one workflow action."""

    project_id: str
    task_id: str
    generation: str
    action: str
    idempotency_key: str
    phase: str = "intent"
    expected_evidence_revision: str | None = None
    expected_head_sha: str | None = None
    priority: int = 100
    max_attempts: int = 5
    # Stable policy reason carried with recovery work. It is stored inside
    # the immutable spec payload so old SQLite rows remain readable.
    reason_code: str | None = None
    payload: Mapping[str, Any] | None = None
    scheduling_lane: str = "decision"

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "project_id", _required_text(self.project_id, "project_id")
        )
        object.__setattr__(self, "task_id", _required_text(self.task_id, "task_id"))
        object.__setattr__(
            self, "generation", _required_text(self.generation, "generation")
        )
        object.__setattr__(self, "action", _required_text(self.action, "action"))
        object.__setattr__(
            self,
            "idempotency_key",
            _required_text(self.idempotency_key, "idempotency_key"),
        )
        object.__setattr__(self, "phase", _required_text(self.phase, "phase"))
        object.__setattr__(self, "payload", _json_object(self.payload, "payload"))
        object.__setattr__(
            self,
            "scheduling_lane",
            _required_text(self.scheduling_lane, "scheduling_lane"),
        )
        object.__setattr__(
            self,
            "expected_evidence_revision",
            _optional_text(self.expected_evidence_revision),
        )
        object.__setattr__(
            self, "expected_head_sha", _optional_text(self.expected_head_sha)
        )
        object.__setattr__(self, "reason_code", _optional_text(self.reason_code))
        if isinstance(self.priority, bool):
            raise ValueError("priority must be an integer")
        object.__setattr__(self, "priority", int(self.priority))
        if isinstance(self.max_attempts, bool) or int(self.max_attempts) < 1:
            raise ValueError("max_attempts must be a positive integer")
        object.__setattr__(self, "max_attempts", int(self.max_attempts))

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "project_id": self.project_id,
            "task_id": self.task_id,
            "generation": self.generation,
            "action": self.action,
            "idempotency_key": self.idempotency_key,
            "phase": self.phase,
            "payload": _thaw_json(self.payload),
            "scheduling_lane": self.scheduling_lane,
            "expected_evidence_revision": self.expected_evidence_revision,
            "expected_head_sha": self.expected_head_sha,
            "priority": self.priority,
            "max_attempts": self.max_attempts,
        }
        if self.reason_code is not None:
            payload["reason_code"] = self.reason_code
        return payload

    @property
    def revision(self) -> str:
        return hashlib.sha256(_canonical_json(self.to_dict()).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class WorkflowJob:
    job_id: str
    enqueue_sequence: int
    project_id: str
    task_id: str
    generation: str
    action: str
    phase: str
    payload: Mapping[str, Any] | None
    scheduling_lane: str
    idempotency_key: str
    spec_revision: str
    expected_evidence_revision: str | None
    expected_head_sha: str | None
    state: WorkflowJobState
    priority: int
    attempts: int
    max_attempts: int
    lease_owner: str | None
    lease_token: str | None
    lease_expires_at: float | None
    retry_at: float | None
    failure_category: WorkflowFailureCategory | None
    last_error: str | None
    checkpoint: Mapping[str, Any] | None
    result_transition: Mapping[str, Any] | None
    superseded_by_generation: str | None
    workflow_managed: bool
    created_at: float
    updated_at: float
    completed_at: float | None
    reason_code: str | None = None

    @property
    def is_active(self) -> bool:
        return self.state in ACTIVE_JOB_STATES

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_JOB_STATES

    @property
    def reassessment_deadline(self) -> float | None:
        """Return the durable recurring-generation deadline, when present."""

        return _schedule_reassessment_deadline(self.generation)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "enqueue_sequence": self.enqueue_sequence,
            "project_id": self.project_id,
            "task_id": self.task_id,
            "generation": self.generation,
            "action": self.action,
            "phase": self.phase,
            "payload": _thaw_json(self.payload),
            "scheduling_lane": self.scheduling_lane,
            "idempotency_key": self.idempotency_key,
            "spec_revision": self.spec_revision,
            "expected_evidence_revision": self.expected_evidence_revision,
            "expected_head_sha": self.expected_head_sha,
            "state": self.state.value,
            "priority": self.priority,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "lease_owner": self.lease_owner,
            "lease_token": self.lease_token,
            "lease_expires_at": self.lease_expires_at,
            "retry_at": self.retry_at,
            "failure_category": (
                self.failure_category.value if self.failure_category else None
            ),
            "last_error": self.last_error,
            "checkpoint": _thaw_json(self.checkpoint),
            "result_transition": _thaw_json(self.result_transition),
            "superseded_by_generation": self.superseded_by_generation,
            "workflow_managed": self.workflow_managed,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "reason_code": self.reason_code,
        }


@dataclass(frozen=True, slots=True)
class WorkflowJobEvent:
    sequence: int
    job_id: str
    project_id: str
    task_id: str
    event_type: str
    state: WorkflowJobState
    phase: str
    lease_owner: str | None
    payload: Mapping[str, Any] | None
    created_at: float


@dataclass(frozen=True, slots=True)
class WorkflowScheduleCursor:
    """Durable ordering fence for one task's latest evaluated decision."""

    project_id: str
    task_id: str
    snapshot_generation: int
    decision_revision: str
    job_generation: str
    changed: bool
    accepted: bool = True
    materialized: bool = False


@dataclass(frozen=True, slots=True)
class WorkflowScheduleWrite:
    """Result of atomically materializing one accepted scheduling cursor."""

    project_id: str
    task_id: str
    snapshot_generation: int
    job_generation: str
    accepted: bool
    created: int = 0
    replayed: int = 0
    superseded: int = 0


@dataclass(frozen=True, slots=True)
class WorkflowSnapshotMembershipWrite:
    """Result of replacing authoritative membership for one full snapshot."""

    snapshot_generation: int
    accepted: bool
    members: int = 0
    cursors_retired: int = 0
    jobs_superseded: int = 0


@dataclass(frozen=True, slots=True)
class WorkflowSnapshotAuthority:
    """Pre-publication durable authority for one reversible scan scope.

    Job events deliberately remain append-only, so a failed publication is
    represented by compensating events while the current cursor, membership,
    and managed-job authority is restored exactly to this checkpoint.
    """

    project_ids: tuple[str, ...]
    identities: tuple[tuple[str, str], ...]
    full_project_scope: bool
    cursors: tuple[dict[str, Any], ...]
    memberships: tuple[dict[str, Any], ...]
    jobs: tuple[dict[str, Any], ...]
    retirements: tuple[dict[str, Any], ...] = ()
    job_event_sequence: int = 0


@dataclass(frozen=True, slots=True)
class WorkflowSnapshotPublication:
    """Publication result with external and durable compensation operations."""

    result: Any = None
    rollback: Callable[[], None] | None = None
    rollback_authority: Callable[[], None] | None = None


@dataclass(frozen=True, slots=True)
class WorkflowEventWrite:
    """Atomic materialization result for one semantic event lane."""

    job: WorkflowJob | None
    accepted: bool
    created: bool
    superseded: int


class WorkflowJobStoreError(RuntimeError):
    """Base class for workflow-job persistence errors."""


class WorkflowJobPublicationError(WorkflowJobStoreError):
    """A staged workflow publication could not commit or roll back cleanly."""

    def __init__(self, message: str, *, rollback_failed: bool = False) -> None:
        super().__init__(message)
        self.rollback_failed = bool(rollback_failed)


class WorkflowJobIdempotencyConflict(WorkflowJobStoreError):
    """An idempotency key was reused for different immutable work."""


class WorkflowJobLeaseLost(WorkflowJobStoreError):
    """A worker attempted to mutate work it no longer owns."""


class WorkflowJobCorruptionError(WorkflowJobStoreError):
    """Persisted workflow-job content cannot be decoded safely."""


class WorkflowRolloutGateError(WorkflowJobStoreError):
    """A requested enforce cutover lacks persisted shadow evidence."""


_CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS workflow_jobs (
    enqueue_sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL UNIQUE,
    project_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    generation TEXT NOT NULL,
    action TEXT NOT NULL,
    phase TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    spec_revision TEXT NOT NULL,
    spec_json TEXT NOT NULL,
    payload_json TEXT,
    scheduling_lane TEXT NOT NULL DEFAULT 'decision',
    expected_evidence_revision TEXT,
    expected_head_sha TEXT,
    state TEXT NOT NULL,
    priority INTEGER NOT NULL,
    attempts INTEGER NOT NULL,
    max_attempts INTEGER NOT NULL,
    lease_owner TEXT,
    lease_token TEXT,
    lease_expires_at REAL,
    retry_at REAL,
    failure_category TEXT,
    last_error TEXT,
    checkpoint_json TEXT,
    result_transition_json TEXT,
    superseded_by_generation TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    completed_at REAL,
    UNIQUE(project_id, idempotency_key)
);
"""

_CREATE_V2_OBJECTS = """
CREATE TABLE IF NOT EXISTS workflow_job_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    state TEXT NOT NULL,
    phase TEXT NOT NULL,
    lease_owner TEXT,
    payload_json TEXT,
    created_at REAL NOT NULL,
    FOREIGN KEY(job_id) REFERENCES workflow_jobs(job_id)
);
CREATE INDEX IF NOT EXISTS workflow_jobs_due_idx
    ON workflow_jobs(state, retry_at, priority, enqueue_sequence);
CREATE INDEX IF NOT EXISTS workflow_jobs_project_due_idx
    ON workflow_jobs(project_id, state, retry_at, priority, enqueue_sequence);
CREATE INDEX IF NOT EXISTS workflow_jobs_task_idx
    ON workflow_jobs(project_id, task_id, generation, enqueue_sequence);
CREATE INDEX IF NOT EXISTS workflow_job_events_job_idx
    ON workflow_job_events(job_id, sequence);
CREATE INDEX IF NOT EXISTS workflow_job_events_task_idx
    ON workflow_job_events(project_id, task_id, sequence);
CREATE TRIGGER IF NOT EXISTS workflow_job_events_no_update
BEFORE UPDATE ON workflow_job_events BEGIN
    SELECT RAISE(ABORT, 'workflow job events are append-only');
END;
-- Events are append-only.  The sole sanctioned exception is the archival
-- maintenance path, which relocates rows for lifecycle-final Archived tasks
-- into ``workflow_job_events_archive``.  That path sets a transaction-scoped
-- guard flag in ``workflow_job_events_delete_guard`` before deleting; every
-- other DELETE is rejected.
CREATE TABLE IF NOT EXISTS workflow_job_events_delete_guard (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    allowed INTEGER NOT NULL DEFAULT 0
);
INSERT OR IGNORE INTO workflow_job_events_delete_guard(id, allowed) VALUES (1, 0);
CREATE TRIGGER IF NOT EXISTS workflow_job_events_no_delete
BEFORE DELETE ON workflow_job_events
WHEN NOT EXISTS (
    SELECT 1 FROM workflow_job_events_delete_guard WHERE id = 1 AND allowed = 1
)
BEGIN
    SELECT RAISE(ABORT, 'workflow job events are append-only');
END;
"""

_CREATE_V3_OBJECTS = """
CREATE TABLE IF NOT EXISTS workflow_schedule_cursors (
    project_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    snapshot_generation INTEGER NOT NULL,
    decision_revision TEXT NOT NULL,
    job_generation TEXT NOT NULL,
    materialized_job_generation TEXT,
    updated_at REAL NOT NULL,
    PRIMARY KEY(project_id, task_id)
);
CREATE TABLE IF NOT EXISTS workflow_project_fairness (
    project_id TEXT PRIMARY KEY,
    claim_sequence INTEGER NOT NULL,
    updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS workflow_schedule_generation_idx
    ON workflow_schedule_cursors(snapshot_generation, project_id, task_id);
CREATE TABLE IF NOT EXISTS workflow_landing_facts (
    project_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    source TEXT NOT NULL,
    target TEXT NOT NULL,
    evidence_revision TEXT NOT NULL,
    fact_json TEXT NOT NULL,
    recorded_at REAL NOT NULL,
    PRIMARY KEY(project_id, task_id, source, target, evidence_revision)
);
CREATE INDEX IF NOT EXISTS workflow_landing_facts_lookup_idx
    ON workflow_landing_facts(project_id, task_id, source, target, recorded_at);
"""

_CREATE_V5_OBJECTS = """
CREATE TABLE IF NOT EXISTS workflow_snapshot_membership (
    project_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    snapshot_generation INTEGER NOT NULL,
    updated_at REAL NOT NULL,
    PRIMARY KEY(project_id, task_id)
);
CREATE INDEX IF NOT EXISTS workflow_snapshot_membership_generation_idx
    ON workflow_snapshot_membership(snapshot_generation, project_id, task_id);
CREATE TABLE IF NOT EXISTS workflow_event_cursors (
    project_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    event_namespace TEXT NOT NULL,
    event_revision TEXT NOT NULL,
    event_generation TEXT NOT NULL,
    event_sequence INTEGER NOT NULL,
    updated_at REAL NOT NULL,
    PRIMARY KEY(project_id, task_id, event_namespace)
);
CREATE INDEX IF NOT EXISTS idx_workflow_event_cursors_sequence
    ON workflow_event_cursors(event_sequence, project_id, task_id);
CREATE TABLE IF NOT EXISTS workflow_event_ordering (
    project_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    ordering_namespace TEXT NOT NULL,
    source_generation INTEGER NOT NULL,
    decision_revision TEXT NOT NULL,
    updated_at REAL NOT NULL,
    PRIMARY KEY(project_id, task_id, ordering_namespace)
);
"""

_CREATE_V7_OBJECTS = """
CREATE TABLE IF NOT EXISTS workflow_snapshot_publications (
    snapshot_generation INTEGER PRIMARY KEY,
    published_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS workflow_retirement_authority_cuts (
    snapshot_generation INTEGER NOT NULL,
    project_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    authority_kind TEXT NOT NULL,
    decision_revision TEXT NOT NULL,
    job_generation TEXT,
    recorded_at REAL NOT NULL,
    PRIMARY KEY(snapshot_generation, project_id, task_id)
);
CREATE TABLE IF NOT EXISTS workflow_job_retirements (
    job_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    authority_kind TEXT NOT NULL,
    decision_revision TEXT NOT NULL,
    snapshot_generation INTEGER,
    retired_at REAL NOT NULL,
    FOREIGN KEY(job_id) REFERENCES workflow_jobs(job_id)
);
CREATE INDEX IF NOT EXISTS workflow_job_retirements_task_idx
    ON workflow_job_retirements(project_id, task_id, snapshot_generation);
"""

# Rollout evidence is an additive compatibility schema rather than a new
# workflow-job schema generation.  A pre-rollout binary safely ignores this
# table during an operator rollback, while the current binary can resume a
# partially completed canary after any startup interruption.
_CREATE_ROLLOUT_OBJECTS = """
CREATE TABLE IF NOT EXISTS workflow_rollout_domains (
    domain TEXT PRIMARY KEY,
    mode TEXT NOT NULL,
    mode_started_at REAL NOT NULL,
    successful_shadow_sweeps INTEGER NOT NULL DEFAULT 0,
    failed_shadow_sweeps INTEGER NOT NULL DEFAULT 0,
    last_success_at REAL,
    last_failure_at REAL,
    last_error TEXT,
    updated_at REAL NOT NULL
);
"""

# Cold storage for workflow job events belonging to lifecycle-final Archived
# tasks.  Rows are relocated here verbatim (original ``sequence`` preserved) so
# the audit history survives while the hot ``workflow_job_events`` table stays
# small.  The archive intentionally omits the append-only triggers: it is only
# ever written by the sanctioned archival maintenance path.
_CREATE_V8_OBJECTS = """
CREATE TABLE IF NOT EXISTS workflow_job_events_archive (
    sequence INTEGER PRIMARY KEY,
    job_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    state TEXT NOT NULL,
    phase TEXT NOT NULL,
    lease_owner TEXT,
    payload_json TEXT,
    created_at REAL NOT NULL,
    archived_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS workflow_job_events_archive_task_idx
    ON workflow_job_events_archive(project_id, task_id, sequence);
"""

_V2_COLUMNS: dict[str, str] = {
    "expected_evidence_revision": "TEXT",
    "expected_head_sha": "TEXT",
    "checkpoint_json": "TEXT",
    "result_transition_json": "TEXT",
    "superseded_by_generation": "TEXT",
}

_V4_COLUMNS: dict[str, str] = {
    "payload_json": "TEXT",
}

_V5_COLUMNS: dict[str, str] = {
    "scheduling_lane": "TEXT NOT NULL DEFAULT 'decision'",
}

_V4_SCHEDULE_COLUMNS: dict[str, str] = {
    "materialized_job_generation": "TEXT",
}

_V5_JOB_COLUMNS: dict[str, str] = {
    "workflow_managed": "INTEGER NOT NULL DEFAULT 0",
}


class WorkflowJobStore:
    """SQLite repository for generation-fenced, resumable workflow work."""

    def __init__(
        self,
        path: str,
        *,
        clock: Callable[[], float] = time.time,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        if fcntl is None:
            raise WorkflowJobStoreError(
                "workflow snapshot authority requires POSIX flock support"
            )
        self.path = os.path.realpath(os.path.abspath(path))
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        self._clock = clock
        self._id_factory = id_factory or (lambda: f"workflow-job-{uuid.uuid4().hex}")
        self._lock = threading.RLock()
        self._authority_lock_fd = self._open_authority_lock()
        self._authority_lock_depth = 0
        try:
            self._conn = sqlite3.connect(
                self.path,
                check_same_thread=False,
                timeout=10,
            )
            self._conn.row_factory = sqlite3.Row
            with _INITIALIZE_LOCK, self._authority_mutation_guard():
                self._conn.execute("PRAGMA foreign_keys=ON")
                self._conn.execute("PRAGMA busy_timeout=10000")
                self._conn.execute("PRAGMA journal_mode=WAL")
                # WAL mode provides crash safety without requiring a full
                # fsync on every commit. NORMAL keeps bounded workflow scans
                # fast while retaining SQLite WAL recovery semantics.
                self._conn.execute("PRAGMA synchronous=NORMAL")
                self._initialize()
        except Exception:
            if hasattr(self, "_conn"):
                self._conn.close()
            if self._authority_lock_fd >= 0:
                try:
                    os.close(self._authority_lock_fd)
                finally:
                    # Failed construction is also an ownership boundary.
                    # Mark the descriptor retired before a wrapper/finalizer
                    # can retry cleanup and close a reused unrelated fd.
                    self._authority_lock_fd = -1
            raise

    def _open_authority_lock(self) -> int:
        """Open the process-local handle for the cross-process authority lock."""

        lock_flags = os.O_CREAT | os.O_RDWR
        if hasattr(os, "O_CLOEXEC"):
            lock_flags |= os.O_CLOEXEC
        if hasattr(os, "O_NOFOLLOW"):
            lock_flags |= os.O_NOFOLLOW
        return os.open(f"{self.path}.authority.lock", lock_flags, 0o600)

    def _ensure_conn(self) -> None:
        """Re-open SQLite after a stale reference observes orchestrator close."""

        try:
            self._conn.execute("SELECT 1")
        except sqlite3.ProgrammingError:
            self._conn = sqlite3.connect(
                self.path,
                check_same_thread=False,
                timeout=10,
            )
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.execute("PRAGMA busy_timeout=10000")
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")

    @contextmanager
    def _authority_mutation_guard(self) -> Iterator[None]:
        """Serialize authority writes and recover stale replacement handles."""

        with self._lock:
            outermost = self._authority_lock_depth == 0
            acquired_fd: int | None = None
            if outermost:
                if self._authority_lock_fd < 0:
                    self._authority_lock_fd = self._open_authority_lock()
                acquired_fd = self._authority_lock_fd
                fcntl.flock(acquired_fd, fcntl.LOCK_EX)
                try:
                    self._ensure_conn()
                except Exception:
                    fcntl.flock(acquired_fd, fcntl.LOCK_UN)
                    raise
            self._authority_lock_depth += 1
            try:
                yield
            finally:
                self._authority_lock_depth -= 1
                if outermost and acquired_fd is not None:
                    fcntl.flock(acquired_fd, fcntl.LOCK_UN)

    @contextmanager
    def snapshot_authority_guard(self) -> Iterator[None]:
        """Serialize snapshot publication with every durable authority writer."""

        with self._authority_mutation_guard():
            yield

    def _initialize(self) -> None:
        self._conn.executescript(_CREATE_TABLES)
        version_row = self._conn.execute(
            "SELECT value FROM schema_meta WHERE key = 'workflow_jobs_version'"
        ).fetchone()
        version = int(version_row["value"]) if version_row is not None else 1
        if version > WORKFLOW_JOB_SCHEMA_VERSION:
            raise WorkflowJobStoreError(
                f"workflow job schema {version} is newer than supported "
                f"version {WORKFLOW_JOB_SCHEMA_VERSION}"
            )
        columns = {
            str(row["name"])
            for row in self._conn.execute("PRAGMA table_info(workflow_jobs)")
        }
        # Version metadata, not only column presence, drives data migration.
        # A killed process may have committed SQLite's ALTER TABLE before it
        # rewrote legacy specs.  Retrying from the older version marker makes
        # that interrupted startup idempotent and restart-safe.
        migrate_payloads = version < 4 or "payload_json" not in columns
        migrate_lanes = version < 5 or "scheduling_lane" not in columns
        for name, declaration in _V2_COLUMNS.items():
            if name not in columns:
                self._conn.execute(
                    f"ALTER TABLE workflow_jobs ADD COLUMN {name} {declaration}"
                )
        for name, declaration in _V4_COLUMNS.items():
            if name not in columns:
                self._conn.execute(
                    f"ALTER TABLE workflow_jobs ADD COLUMN {name} {declaration}"
                )
        for name, declaration in _V5_COLUMNS.items():
            if name not in columns:
                self._conn.execute(
                    f"ALTER TABLE workflow_jobs ADD COLUMN {name} {declaration}"
                )
        # The V8 archival path relaxes the events DELETE trigger to consult a
        # guard row.  ``CREATE TRIGGER IF NOT EXISTS`` will not replace a
        # pre-existing unconditional trigger, so drop it first and let the V2
        # object script recreate the guarded form.  Idempotent across restarts.
        self._conn.execute("DROP TRIGGER IF EXISTS workflow_job_events_no_delete")
        self._conn.executescript(_CREATE_V2_OBJECTS)
        self._conn.executescript(_CREATE_V3_OBJECTS)
        schedule_columns = {
            str(row["name"])
            for row in self._conn.execute(
                "PRAGMA table_info(workflow_schedule_cursors)"
            )
        }
        for name, declaration in _V4_SCHEDULE_COLUMNS.items():
            if name not in schedule_columns:
                self._conn.execute(
                    "ALTER TABLE workflow_schedule_cursors "
                    f"ADD COLUMN {name} {declaration}"
                )
        job_columns = {
            str(row["name"])
            for row in self._conn.execute("PRAGMA table_info(workflow_jobs)")
        }
        for name, declaration in _V5_JOB_COLUMNS.items():
            if name not in job_columns:
                self._conn.execute(
                    f"ALTER TABLE workflow_jobs ADD COLUMN {name} {declaration}"
                )
        self._conn.executescript(_CREATE_V5_OBJECTS)
        self._conn.executescript(_CREATE_V7_OBJECTS)
        self._conn.executescript(_CREATE_ROLLOUT_OBJECTS)
        self._conn.executescript(_CREATE_V8_OBJECTS)
        # Seed the persisted high-water mark from the live tables so an
        # already-populated store adopts a correct global maximum before any
        # archival can relocate the tail of the ledger.
        highwater_row = self._conn.execute(
            "SELECT value FROM schema_meta WHERE key = ?",
            (_JOB_EVENT_HIGHWATER_KEY,),
        ).fetchone()
        if highwater_row is None:
            observed = self._conn.execute(
                "SELECT COALESCE(MAX(sequence), 0) AS sequence FROM ("
                "  SELECT MAX(sequence) AS sequence FROM workflow_job_events"
                "  UNION ALL"
                "  SELECT MAX(sequence) AS sequence FROM workflow_job_events_archive"
                ")"
            ).fetchone()
            self._conn.execute(
                "INSERT OR REPLACE INTO schema_meta(key, value) VALUES(?, ?)",
                (_JOB_EVENT_HIGHWATER_KEY, str(int(observed["sequence"] or 0))),
            )
        published_row = self._conn.execute(
            "SELECT value FROM schema_meta "
            "WHERE key = 'workflow_snapshot_published_generation'"
        ).fetchone()
        if published_row is not None and int(published_row["value"]) > 0:
            self._conn.execute(
                """
                INSERT OR IGNORE INTO workflow_snapshot_publications(
                    snapshot_generation, published_at
                ) VALUES (?, ?)
                """,
                (int(published_row["value"]), float(self._clock())),
            )
        # Version 4 did not persist ownership provenance.  Do not infer it
        # from a task cursor or a caller-controlled idempotency key: doing so
        # reclassifies a direct enqueue as scheduler authority after restart
        # and lets reconciliation supersede it.  Legacy rows remain direct;
        # a later authoritative scan creates explicitly managed replacements.
        if migrate_payloads:
            self._migrate_v4_payloads()
        if migrate_lanes:
            self._migrate_v5_lanes()
        self._conn.execute(
            "INSERT OR REPLACE INTO schema_meta(key, value) VALUES(?, ?)",
            ("workflow_jobs_version", str(WORKFLOW_JOB_SCHEMA_VERSION)),
        )
        self._conn.commit()

    def prepare_rollout(
        self,
        domain_modes: Mapping[str, object],
        *,
        require_qualification: bool,
        min_shadow_sweeps: int,
        min_shadow_seconds: int,
    ) -> tuple[dict[str, Any], ...]:
        """Persist desired domain modes and fence unsafe enforce promotion.

        Shadow evidence is stored in the durable job database so a graceful
        restart cannot reset the qualification clock or sample count.  Mode
        changes are committed atomically across domains; an unsafe promotion
        leaves every prior row untouched.
        """

        from oompah.workflow_shadow import normalize_workflow_domain_modes

        modes = normalize_workflow_domain_modes(domain_modes)
        required_sweeps = max(int(min_shadow_sweeps), 1)
        required_seconds = max(int(min_shadow_seconds), 0)
        now = float(self._clock())
        with self._authority_mutation_guard():
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                rows = {
                    str(row["domain"]): row
                    for row in self._conn.execute(
                        "SELECT * FROM workflow_rollout_domains"
                    ).fetchall()
                }
                failures: list[str] = []
                if require_qualification:
                    for domain, target in modes.items():
                        if target != "enforce":
                            continue
                        row = rows.get(domain)
                        successes = int(
                            row["successful_shadow_sweeps"] if row else 0
                        )
                        started_at = float(row["mode_started_at"] if row else now)
                        last_success = row["last_success_at"] if row else None
                        last_failure = row["last_failure_at"] if row else None
                        prior_mode = str(row["mode"] if row else "off")
                        if prior_mode not in {"shadow", "enforce"}:
                            failures.append(f"{domain}: shadow mode has not run")
                        elif successes < required_sweeps:
                            failures.append(
                                f"{domain}: {successes}/{required_sweeps} "
                                "successful shadow sweeps"
                            )
                        elif now - started_at < required_seconds:
                            failures.append(
                                f"{domain}: shadow soak is "
                                f"{int(now - started_at)}/{required_seconds}s"
                            )
                        elif last_success is None or (
                            last_failure is not None
                            and float(last_failure) >= float(last_success)
                        ):
                            failures.append(
                                f"{domain}: latest shadow sweep did not succeed"
                            )
                if failures:
                    raise WorkflowRolloutGateError(
                        "workflow enforce qualification failed: "
                        + "; ".join(failures)
                    )

                for domain, target in modes.items():
                    row = rows.get(domain)
                    if row is None:
                        compatibility_enforce = (
                            target == "enforce" and not require_qualification
                        )
                        self._conn.execute(
                            """
                            INSERT INTO workflow_rollout_domains(
                                domain, mode, mode_started_at,
                                successful_shadow_sweeps, last_success_at,
                                updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            (
                                domain,
                                target,
                                (
                                    now - required_seconds
                                    if compatibility_enforce
                                    else now
                                ),
                                required_sweeps if compatibility_enforce else 0,
                                now if compatibility_enforce else None,
                                now,
                            ),
                        )
                        continue
                    prior = str(row["mode"])
                    if prior == target:
                        if target == "enforce" and not require_qualification:
                            self._conn.execute(
                                """
                                UPDATE workflow_rollout_domains
                                   SET mode_started_at = MIN(mode_started_at, ?),
                                       successful_shadow_sweeps = MAX(
                                           successful_shadow_sweeps, ?
                                       ),
                                       last_success_at = COALESCE(
                                           last_success_at, ?
                                       ),
                                       updated_at = ?
                                 WHERE domain = ?
                                """,
                                (
                                    now - required_seconds,
                                    required_sweeps,
                                    now,
                                    now,
                                    domain,
                                ),
                            )
                        else:
                            self._conn.execute(
                                "UPDATE workflow_rollout_domains "
                                "SET updated_at = ? WHERE domain = ?",
                                (now, domain),
                            )
                        continue
                    reset = target in {"off", "shadow"}
                    self._conn.execute(
                        """
                        UPDATE workflow_rollout_domains
                           SET mode = ?,
                               mode_started_at = ?,
                               successful_shadow_sweeps = ?,
                               failed_shadow_sweeps = ?,
                               last_success_at = ?,
                               last_failure_at = ?,
                               last_error = ?,
                               updated_at = ?
                         WHERE domain = ?
                        """,
                        (
                            target,
                            now if reset else float(row["mode_started_at"]),
                            0 if reset else int(row["successful_shadow_sweeps"]),
                            0 if reset else int(row["failed_shadow_sweeps"]),
                            None if reset else row["last_success_at"],
                            None if reset else row["last_failure_at"],
                            None if reset else row["last_error"],
                            now,
                            domain,
                        ),
                    )
                self._conn.commit()
            except BaseException:
                self._conn.rollback()
                raise
        return self.rollout_snapshot()

    def record_rollout_sweep(
        self,
        outcomes: Mapping[str, str | None],
    ) -> tuple[dict[str, Any], ...]:
        """Record one bounded shadow outcome per configured domain."""

        now = float(self._clock())
        with self._authority_mutation_guard():
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                for domain, error in outcomes.items():
                    row = self._conn.execute(
                        "SELECT mode FROM workflow_rollout_domains WHERE domain = ?",
                        (str(domain),),
                    ).fetchone()
                    if row is None or str(row["mode"]) != "shadow":
                        continue
                    if error is None:
                        self._conn.execute(
                            """
                            UPDATE workflow_rollout_domains
                               SET successful_shadow_sweeps =
                                       successful_shadow_sweeps + 1,
                                   last_success_at = ?, last_error = NULL,
                                   updated_at = ?
                             WHERE domain = ?
                            """,
                            (now, now, str(domain)),
                        )
                    else:
                        self._conn.execute(
                            """
                            UPDATE workflow_rollout_domains
                               SET failed_shadow_sweeps = failed_shadow_sweeps + 1,
                                   last_failure_at = ?, last_error = ?,
                                   updated_at = ?
                             WHERE domain = ?
                            """,
                            (now, str(error)[:1000], now, str(domain)),
                        )
                self._conn.commit()
            except BaseException:
                self._conn.rollback()
                raise
        return self.rollout_snapshot()

    def rollout_snapshot(self) -> tuple[dict[str, Any], ...]:
        """Return redacted persisted rollout evidence in stable domain order."""

        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM workflow_rollout_domains ORDER BY domain"
            ).fetchall()
        return tuple(
            {
                "domain": str(row["domain"]),
                "mode": str(row["mode"]),
                "mode_started_at": float(row["mode_started_at"]),
                "successful_shadow_sweeps": int(
                    row["successful_shadow_sweeps"]
                ),
                "failed_shadow_sweeps": int(row["failed_shadow_sweeps"]),
                "last_success_at": row["last_success_at"],
                "last_failure_at": row["last_failure_at"],
                "last_error": row["last_error"],
                "updated_at": float(row["updated_at"]),
            }
            for row in rows
        )

    def rollout_readiness(
        self,
        *,
        min_shadow_sweeps: int,
        min_shadow_seconds: int,
        now: float | None = None,
    ) -> dict[str, Any]:
        """Project persisted evidence into the public canary gate result."""

        from oompah.workflow_shadow import WORKFLOW_DOMAIN_NAMES

        required_sweeps = max(int(min_shadow_sweeps), 1)
        required_seconds = max(int(min_shadow_seconds), 0)
        timestamp = float(self._clock() if now is None else now)
        domains: dict[str, dict[str, Any]] = {}
        rollout = self.rollout_snapshot()
        for row in rollout:
            last_success = row["last_success_at"]
            last_failure = row["last_failure_at"]
            latest_succeeded = last_success is not None and (
                last_failure is None or float(last_success) > float(last_failure)
            )
            soak_age = max(0.0, timestamp - float(row["mode_started_at"]))
            ready = row["mode"] == "enforce" or (
                row["mode"] == "shadow"
                and row["successful_shadow_sweeps"] >= required_sweeps
                and soak_age >= required_seconds
                and latest_succeeded
            )
            domains[row["domain"]] = {
                "mode": row["mode"],
                "ready": ready,
                "successful_shadow_sweeps": row[
                    "successful_shadow_sweeps"
                ],
                "shadow_soak_age_seconds": soak_age,
                "latest_succeeded": latest_succeeded,
            }
        return {
            "min_shadow_sweeps": required_sweeps,
            "min_shadow_seconds": required_seconds,
            "all_domains_ready": set(domains) == set(WORKFLOW_DOMAIN_NAMES)
            and all(value["ready"] for value in domains.values()),
            "domains": domains,
            "rollout": list(rollout),
        }

    @contextmanager
    def scheduling_batch(self):
        """Commit one bounded decision scan as a single durable transaction."""

        with self._authority_mutation_guard():
            if self._conn.in_transaction:
                raise WorkflowJobStoreError(
                    "cannot nest a workflow scheduling transaction"
                )
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                yield
                self._conn.commit()
            except BaseException:
                self._conn.rollback()
                raise

    def _migrate_v4_payloads(self) -> None:
        """Canonicalize legacy specs after payload joins their identity."""

        rows = self._conn.execute(
            "SELECT job_id, spec_json FROM workflow_jobs"
        ).fetchall()
        for row in rows:
            try:
                raw_spec = json.loads(str(row["spec_json"]))
                if not isinstance(raw_spec, dict):
                    raise TypeError("workflow job spec must be a JSON object")
                raw_spec.setdefault("payload", None)
                spec = WorkflowJobSpec(**raw_spec)
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                raise WorkflowJobCorruptionError(
                    f"invalid workflow job spec: {row['job_id']}"
                ) from exc
            self._conn.execute(
                """
                UPDATE workflow_jobs
                   SET spec_revision = ?, spec_json = ?, payload_json = ?
                 WHERE job_id = ?
                """,
                (
                    spec.revision,
                    _canonical_json(spec.to_dict()),
                    (
                        _canonical_json(spec.payload)
                        if spec.payload is not None
                        else None
                    ),
                    row["job_id"],
                ),
            )

    def _migrate_v5_lanes(self) -> None:
        """Add the decision lane to legacy immutable spec identities."""

        rows = self._conn.execute(
            "SELECT job_id, spec_json FROM workflow_jobs"
        ).fetchall()
        for row in rows:
            try:
                raw_spec = json.loads(str(row["spec_json"]))
                if not isinstance(raw_spec, dict):
                    raise TypeError("workflow job spec must be a JSON object")
                raw_spec.setdefault("payload", None)
                raw_spec.setdefault("scheduling_lane", "decision")
                spec = WorkflowJobSpec(**raw_spec)
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                raise WorkflowJobCorruptionError(
                    f"invalid workflow job spec: {row['job_id']}"
                ) from exc
            self._conn.execute(
                """
                UPDATE workflow_jobs
                   SET spec_revision = ?, spec_json = ?, scheduling_lane = ?
                 WHERE job_id = ?
                """,
                (
                    spec.revision,
                    _canonical_json(spec.to_dict()),
                    spec.scheduling_lane,
                    row["job_id"],
                ),
            )

    def close(self) -> None:
        with self._lock:
            if self._authority_lock_depth:
                raise WorkflowJobStoreError(
                    "cannot close workflow job store during an authority mutation"
                )
            self._conn.close()
            authority_fd = self._authority_lock_fd
            self._authority_lock_fd = -1
            if authority_fd >= 0:
                os.close(authority_fd)


    def record_landing_facts(
        self,
        *,
        project_id: str,
        task_id: str,
        facts: Sequence[Mapping[str, Any]],
        now: float | None = None,
    ) -> int:
        """Append durable positive landing evidence for later source pruning.

        Landing proof is immutable evidence, so recording a newer observation
        never overwrites an older proof.  This lets a restarted collector
        recover the exact prior fact before asking Git about a ref that may no
        longer exist.
        """

        project = _required_text(project_id, "project_id")
        task = _required_text(task_id, "task_id")
        timestamp = float(self._clock() if now is None else now)
        rows = self._landing_fact_rows(
            project_id=project,
            facts=facts,
            require_durable=False,
        )
        if not rows:
            return 0
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                inserted = self._insert_landing_fact_rows_locked(
                    project_id=project,
                    task_id=task,
                    rows=rows,
                    recorded_at=timestamp,
                )
                self._conn.commit()
                return inserted
            except Exception:
                self._conn.rollback()
                raise

    @staticmethod
    def _landing_fact_rows(
        *,
        project_id: str,
        facts: Sequence[Mapping[str, Any]],
        require_durable: bool,
    ) -> tuple[tuple[str, str, str, str], ...]:
        """Validate immutable fact content before entering a write transaction."""

        rows: list[tuple[str, str, str, str]] = []
        for raw in facts:
            value = _json_object(raw, "landing_fact")
            if value is None:
                raise ValueError("landing_fact must be a mapping")
            try:
                fact = LandingFact.from_dict(value)
            except (TypeError, ValueError) as exc:
                raise WorkflowJobStoreError(
                    "landing fact schema or evidence revision is invalid"
                ) from exc
            if fact.project_id != project_id:
                raise WorkflowJobStoreError("landing fact escaped project scope")
            if require_durable and not fact.durable:
                raise WorkflowJobStoreError(
                    "job completion can publish only durable landing proof"
                )
            rows.append(
                (
                    fact.source,
                    fact.target,
                    str(fact.evidence_revision),
                    _canonical_json(fact.to_dict()),
                )
            )
        return tuple(rows)

    def _insert_landing_fact_rows_locked(
        self,
        *,
        project_id: str,
        task_id: str,
        rows: Sequence[tuple[str, str, str, str]],
        recorded_at: float,
    ) -> int:
        """Insert validated facts inside the caller's authority transaction."""

        inserted = 0
        for source, target, revision, encoded in rows:
            cursor = self._conn.execute(
                """
                INSERT OR IGNORE INTO workflow_landing_facts(
                    project_id, task_id, source, target,
                    evidence_revision, fact_json, recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    task_id,
                    source,
                    target,
                    revision,
                    encoded,
                    recorded_at,
                ),
            )
            if cursor.rowcount == 1:
                inserted += 1
                continue
            existing = self._conn.execute(
                """
                SELECT fact_json FROM workflow_landing_facts
                 WHERE project_id = ? AND task_id = ? AND source = ?
                   AND target = ? AND evidence_revision = ?
                """,
                (project_id, task_id, source, target, revision),
            ).fetchone()
            if existing is None:
                raise WorkflowJobCorruptionError(
                    "landing fact identity conflicts with stored content"
                )
            try:
                existing_value = json.loads(str(existing["fact_json"]))
                incoming_value = json.loads(encoded)
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                raise WorkflowJobCorruptionError(
                    "landing fact identity conflicts with stored content"
                ) from exc
            # ``observed_at`` deliberately does not contribute to the
            # content-addressed evidence revision.  A fresh observation of
            # the same immutable proof is an idempotent replay, not ledger
            # corruption; every other field must remain byte-for-byte equal.
            existing_value.pop("observed_at", None)
            incoming_value.pop("observed_at", None)
            if existing_value != incoming_value:
                raise WorkflowJobCorruptionError(
                    "landing fact identity conflicts with stored content"
                )
        return inserted

    def landing_facts(
        self,
        *,
        project_id: str,
        task_id: str,
        limit: int = DEFAULT_SCAN_LIMIT,
    ) -> tuple[dict[str, Any], ...]:
        """Return bounded immutable landing evidence for one task."""

        project = _required_text(project_id, "project_id")
        task = _required_text(task_id, "task_id")
        bounded = _bounded_limit(limit)
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT fact_json FROM workflow_landing_facts
                 WHERE project_id = ? AND task_id = ?
                 ORDER BY recorded_at DESC, source DESC, target DESC,
                          evidence_revision DESC
                 LIMIT ?
                """,
                (project, task, bounded),
            ).fetchall()
        values: list[dict[str, Any]] = []
        # Callers fold this bounded history into one fact per source/target.
        # Return the newest window in chronological order so the final value
        # wins without an old prefix starving recent evidence.
        for row in reversed(rows):
            value = _decode_json_object(row["fact_json"], "landing_fact")
            if value is None or str(value.get("project_id") or "") != project:
                raise WorkflowJobCorruptionError("landing fact project scope is invalid")
            values.append(value)
        return tuple(values)

    def latest_landing_facts(
        self,
        *,
        project_id: str,
        task_id: str,
        limit: int = MAX_SCAN_LIMIT,
    ) -> tuple[dict[str, Any], ...]:
        """Return the newest durable fact for each source/target pair.

        ``landing_facts`` intentionally exposes a bounded history window.  A
        workflow recovery pass needs a different projection: one current row
        for every landing obligation.  Limiting raw history can otherwise let
        one churning branch evict the only durable proof for a pruned peer.
        """

        project = _required_text(project_id, "project_id")
        task = _required_text(task_id, "task_id")
        bounded = _bounded_limit(limit)
        with self._lock:
            rows = self._conn.execute(
                """
                WITH ranked AS (
                    SELECT fact_json, source, target,
                           ROW_NUMBER() OVER (
                               PARTITION BY source, target
                               ORDER BY recorded_at DESC,
                                        evidence_revision DESC
                           ) AS pair_rank
                      FROM workflow_landing_facts
                     WHERE project_id = ? AND task_id = ?
                       AND json_extract(fact_json, '$.durable') = 1
                )
                SELECT fact_json FROM ranked
                 WHERE pair_rank = 1
                 ORDER BY source, target
                 LIMIT ?
                """,
                (project, task, bounded),
            ).fetchall()
        values: list[dict[str, Any]] = []
        for row in rows:
            value = _decode_json_object(row["fact_json"], "landing_fact")
            if value is None or str(value.get("project_id") or "") != project:
                raise WorkflowJobCorruptionError(
                    "landing fact project scope is invalid"
                )
            values.append(value)
        return tuple(values)

    def latest_landing_facts_for_pair(
        self,
        *,
        project_id: str,
        task_id: str,
        source: str,
        target: str,
    ) -> tuple[dict[str, Any], ...]:
        """Return the newest durable fact for one exact landing obligation.

        Pair-scoped recovery must not scan the bounded all-obligation
        projection: a task with more than ``MAX_SCAN_LIMIT`` distinct pairs
        could otherwise hide a lexically later exact match forever.  The
        lookup remains bounded to one row by constraining the indexed
        source/target identity in SQL.

        A tuple keeps the evidence boundary fail closed: callers still reject
        any store implementation that supplies more than one current row for
        the supposedly exact pair.
        """

        project = _required_text(project_id, "project_id")
        task = _required_text(task_id, "task_id")
        expected_source = _required_text(source, "source")
        expected_target = _required_text(target, "target")
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT fact_json FROM workflow_landing_facts
                 WHERE project_id = ? AND task_id = ?
                   AND source = ? AND target = ?
                   AND json_extract(fact_json, '$.durable') = 1
                 ORDER BY recorded_at DESC, evidence_revision DESC
                 LIMIT 1
                """,
                (project, task, expected_source, expected_target),
            ).fetchall()
        values: list[dict[str, Any]] = []
        for row in rows:
            value = _decode_json_object(row["fact_json"], "landing_fact")
            if value is None or str(value.get("project_id") or "") != project:
                raise WorkflowJobCorruptionError(
                    "landing fact project scope is invalid"
                )
            values.append(value)
        return tuple(values)

    @property
    def schema_version(self) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT value FROM schema_meta WHERE key = 'workflow_jobs_version'"
            ).fetchone()
        if row is None:
            raise WorkflowJobCorruptionError("workflow job schema version is missing")
        return int(row["value"])

    def _next_counter_locked(self, key: str) -> int:
        row = self._conn.execute(
            "SELECT value FROM schema_meta WHERE key = ?", (key,)
        ).fetchone()
        current = int(row["value"]) if row is not None else 0
        value = current + 1
        self._conn.execute(
            "INSERT OR REPLACE INTO schema_meta(key, value) VALUES(?, ?)",
            (key, str(value)),
        )
        return value

    def _next_ordering_generation_locked(self, key: str) -> int:
        """Advance one counter beyond every persisted event-ordering fence."""

        counter = self._conn.execute(
            """
            SELECT COALESCE(MAX(CAST(value AS INTEGER)), 0) AS generation
              FROM schema_meta
             WHERE key IN (
                'workflow_snapshot_generation',
                'workflow_event_generation'
             )
            """
        ).fetchone()
        ordering = self._conn.execute(
            """
            SELECT COALESCE(MAX(source_generation), 0) AS generation
              FROM workflow_event_ordering
            """
        ).fetchone()
        value = max(
            int(counter["generation"] or 0) if counter is not None else 0,
            int(ordering["generation"] or 0) if ordering is not None else 0,
        ) + 1
        self._conn.execute(
            "INSERT OR REPLACE INTO schema_meta(key, value) VALUES(?, ?)",
            (key, str(value)),
        )
        return value

    def allocate_snapshot_generation(self) -> int:
        """Return a process-independent, monotonically increasing scan fence."""

        with self._authority_mutation_guard():
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                value = self._next_ordering_generation_locked(
                    "workflow_snapshot_generation"
                )
                self._conn.commit()
                return value
            except Exception:
                self._conn.rollback()
                raise

    def allocate_event_generation(self) -> int:
        """Return a durable event identity without advancing the scan fence."""

        with self._authority_mutation_guard():
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                value = self._next_ordering_generation_locked(
                    "workflow_event_generation"
                )
                self._conn.commit()
                return value
            except Exception:
                self._conn.rollback()
                raise

    def accept_snapshot_generation(self, snapshot_generation: int) -> bool:
        """Claim the latest captured scan exactly once for evaluation.

        Allocation happens before source I/O. A slow scan is therefore stale
        as soon as a newer scan is captured, including when the newer snapshot
        contains no row for a task present in the older scan.
        """

        if isinstance(snapshot_generation, bool) or int(snapshot_generation) < 1:
            raise ValueError("snapshot_generation must be a positive integer")
        generation = int(snapshot_generation)
        with self._authority_mutation_guard():
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                allocated_row = self._conn.execute(
                    "SELECT value FROM schema_meta "
                    "WHERE key = 'workflow_snapshot_generation'"
                ).fetchone()
                accepted_row = self._conn.execute(
                    "SELECT value FROM schema_meta "
                    "WHERE key = 'workflow_snapshot_accepted_generation'"
                ).fetchone()
                allocated = (
                    int(allocated_row["value"])
                    if allocated_row is not None
                    else 0
                )
                accepted = (
                    int(accepted_row["value"])
                    if accepted_row is not None
                    else 0
                )
                if generation != allocated or generation <= accepted:
                    self._conn.commit()
                    return False
                self._conn.execute(
                    "INSERT OR REPLACE INTO schema_meta(key, value) "
                    "VALUES('workflow_snapshot_accepted_generation', ?)",
                    (str(generation),),
                )
                self._conn.commit()
                return True
            except Exception:
                self._conn.rollback()
                raise

    def snapshot_generation_is_current(self, snapshot_generation: int) -> bool:
        """Return whether a claimed generation is still the newest capture."""

        if isinstance(snapshot_generation, bool) or int(snapshot_generation) < 1:
            raise ValueError("snapshot_generation must be a positive integer")
        generation = int(snapshot_generation)
        with self._authority_mutation_guard():
            row = self._conn.execute(
                """
                SELECT
                    MAX(CASE WHEN key = 'workflow_snapshot_generation'
                             THEN CAST(value AS INTEGER) ELSE 0 END) AS allocated,
                    MAX(CASE WHEN key = 'workflow_snapshot_accepted_generation'
                             THEN CAST(value AS INTEGER) ELSE 0 END) AS accepted
                  FROM schema_meta
                """
            ).fetchone()
        allocated = int(row["allocated"] or 0) if row is not None else 0
        accepted = int(row["accepted"] or 0) if row is not None else 0
        return allocated == generation == accepted

    def published_snapshot_generation_is_current(
        self, snapshot_generation: int
    ) -> bool:
        """Return whether one generation is the accepted published authority.

        Allocation captures intent to build a newer world snapshot, but does
        not authorize that snapshot or mutate its membership/cursors.  The
        existing published cut therefore remains admissible until the newer
        generation is accepted.  Acceptance and claims share the authority
        transaction, so once acceptance advances this predicate fences the
        old cut before any replacement authority can be staged.
        """

        if isinstance(snapshot_generation, bool) or int(snapshot_generation) < 1:
            raise ValueError("snapshot_generation must be a positive integer")
        generation = int(snapshot_generation)
        with self._lock:
            row = self._conn.execute(
                """
                SELECT
                    MAX(CASE WHEN key = 'workflow_snapshot_accepted_generation'
                             THEN CAST(value AS INTEGER) ELSE 0 END) AS accepted,
                    MAX(CASE WHEN key = 'workflow_snapshot_published_generation'
                             THEN CAST(value AS INTEGER) ELSE 0 END) AS published
                  FROM schema_meta
                """
            ).fetchone()
        if row is None:
            return False
        return (
            int(row["accepted"] or 0)
            == int(row["published"] or 0)
            == generation
        )

    def _snapshot_generation_is_current_locked(self, generation: int) -> bool:
        allocated_row = self._conn.execute(
            "SELECT value FROM schema_meta "
            "WHERE key = 'workflow_snapshot_generation'"
        ).fetchone()
        accepted_row = self._conn.execute(
            "SELECT value FROM schema_meta "
            "WHERE key = 'workflow_snapshot_accepted_generation'"
        ).fetchone()
        return (
            allocated_row is not None
            and accepted_row is not None
            and int(allocated_row["value"]) == generation
            and int(accepted_row["value"]) == generation
        )

    def publish_snapshot_generation(
        self,
        snapshot_generation: int,
        publisher: Callable[[], Any | WorkflowSnapshotPublication],
        *,
        rollback_authority: Callable[[], None] | None = None,
    ) -> tuple[bool, Any | None]:
        """Publish external state and the durable marker as one reversible unit.

        SQLite cannot share a physical transaction with the service-state file.
        A publisher which mutates external state therefore returns compensating
        operations. External state is restored while the write fence is held;
        after rolling back the failed marker transaction, durable cursor/job
        authority is quarantined before this store lock is released.
        """

        if isinstance(snapshot_generation, bool) or int(snapshot_generation) < 1:
            raise ValueError("snapshot_generation must be a positive integer")
        if not callable(publisher):
            raise TypeError("publisher must be callable")
        if rollback_authority is not None and not callable(rollback_authority):
            raise TypeError("rollback_authority must be callable")
        generation = int(snapshot_generation)
        with self._authority_mutation_guard():
            self._conn.execute("BEGIN IMMEDIATE")
            publication: WorkflowSnapshotPublication | None = None
            result: Any | None = None
            try:
                published_row = self._conn.execute(
                    "SELECT value FROM schema_meta "
                    "WHERE key = 'workflow_snapshot_published_generation'"
                ).fetchone()
                published = (
                    int(published_row["value"])
                    if published_row is not None
                    else 0
                )
                if (
                    not self._snapshot_generation_is_current_locked(generation)
                    or published >= generation
                ):
                    self._conn.commit()
                    return False, None
                raw_result = publisher()
                if isinstance(raw_result, WorkflowSnapshotPublication):
                    publication = raw_result
                    result = raw_result.result
                else:
                    result = raw_result
                self._conn.execute(
                    "INSERT OR REPLACE INTO schema_meta(key, value) "
                    "VALUES('workflow_snapshot_published_generation', ?)",
                    (str(generation),),
                )
                self._conn.execute(
                    """
                    INSERT OR IGNORE INTO workflow_snapshot_publications(
                        snapshot_generation, published_at
                    ) VALUES (?, ?)
                    """,
                    (generation, float(self._clock())),
                )
                self._conn.commit()
                return True, result
            except Exception as publish_error:
                # A connection wrapper or storage layer may report an error
                # after SQLite committed successfully. In that case the marker
                # and external publication are already coherent; compensating
                # them would create the split-brain state this protocol avoids.
                if not self._conn.in_transaction:
                    committed_row = self._conn.execute(
                        "SELECT value FROM schema_meta "
                        "WHERE key = 'workflow_snapshot_published_generation'"
                    ).fetchone()
                    if (
                        committed_row is not None
                        and int(committed_row["value"]) >= generation
                    ):
                        return True, result
                rollback_errors: list[Exception] = []
                try:
                    # Compensate while the SQLite write transaction still
                    # excludes another process from allocating/publishing a
                    # newer generation. Releasing SQLite first would let this
                    # file rollback overwrite that newer authority.
                    if publication is not None and publication.rollback is not None:
                        publication.rollback()
                except Exception as exc:
                    rollback_errors.append(exc)
                finally:
                    self._conn.rollback()
                try:
                    durable_rollback = (
                        publication.rollback_authority
                        if publication is not None
                        and publication.rollback_authority is not None
                        else rollback_authority
                    )
                    if durable_rollback is not None:
                        durable_rollback()
                except Exception as exc:
                    rollback_errors.append(exc)
                    self._conn.rollback()
                publisher_rollback_failed = bool(
                    isinstance(publish_error, WorkflowJobPublicationError)
                    and publish_error.rollback_failed
                )
                if rollback_errors or publisher_rollback_failed:
                    # A failed compensator must never leave the generation
                    # publishable: otherwise a subsequent scan-failure publish
                    # could authorize successful-generation jobs accidentally.
                    self._conn.execute("BEGIN IMMEDIATE")
                    try:
                        if self._snapshot_generation_is_current_locked(generation):
                            published_row = self._conn.execute(
                                "SELECT value FROM schema_meta "
                                "WHERE key = 'workflow_snapshot_published_generation'"
                            ).fetchone()
                            durable_published = (
                                int(published_row["value"])
                                if published_row is not None
                                else 0
                            )
                            self._conn.execute(
                                "INSERT OR REPLACE INTO schema_meta(key, value) "
                                "VALUES('workflow_snapshot_accepted_generation', ?)",
                                (str(durable_published),),
                            )
                        self._conn.commit()
                    except Exception:
                        self._conn.rollback()
                    cause = (
                        rollback_errors[0]
                        if rollback_errors
                        else publish_error
                    )
                    raise WorkflowJobStoreError(
                        "workflow snapshot publication failed and its "
                        "compensating rollback also failed"
                    ) from cause
                raise

    def allocate_decision_window(
        self,
        *,
        total: int,
        limit: int,
        snapshot_generation: int | None = None,
        scope: str | None = None,
    ) -> int | None:
        """Return and advance a durable fair offset for a bounded task scan."""

        if isinstance(total, bool) or int(total) < 1:
            raise ValueError("total must be a positive integer")
        bounded = _bounded_limit(limit)
        count = int(total)
        if snapshot_generation is not None and (
            isinstance(snapshot_generation, bool)
            or int(snapshot_generation) < 1
        ):
            raise ValueError("snapshot_generation must be a positive integer")
        generation = (
            int(snapshot_generation)
            if snapshot_generation is not None
            else None
        )
        key = "workflow_decision_window_offset"
        if scope is not None:
            key = f"{key}:{_required_text(scope, 'scope')}"
        with self._authority_mutation_guard():
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                if (
                    generation is not None
                    and not self._snapshot_generation_is_current_locked(
                        generation
                    )
                ):
                    self._conn.commit()
                    return None
                row = self._conn.execute(
                    """
                    SELECT value FROM schema_meta
                     WHERE key = ?
                    """,
                    (key,),
                ).fetchone()
                offset = (int(row["value"]) if row is not None else 0) % count
                next_offset = (offset + min(bounded, count)) % count
                self._conn.execute(
                    """
                    INSERT OR REPLACE INTO schema_meta(key, value)
                    VALUES(?, ?)
                    """,
                    (key, str(next_offset)),
                )
                self._conn.commit()
                return offset
            except Exception:
                self._conn.rollback()
                raise

    def reconcile_snapshot_membership(
        self,
        *,
        snapshot_generation: int,
        authoritative_project_ids: Sequence[str],
        expected_identities: Sequence[tuple[str, str]],
        evaluated_identities: Sequence[tuple[str, str]] | None = None,
        now: float | None = None,
    ) -> WorkflowSnapshotMembershipWrite:
        """Replace successfully scanned project membership and retire omissions.

        Projects whose source failed are deliberately omitted from
        ``authoritative_project_ids`` so their last-known membership survives.
        For an authoritative project, absence is proof: active managed jobs are
        superseded, running leases are revoked, and the obsolete cursor is
        deleted in the same transaction as the new bounded membership set.
        """

        if isinstance(snapshot_generation, bool) or int(snapshot_generation) < 1:
            raise ValueError("snapshot_generation must be a positive integer")
        snapshot = int(snapshot_generation)
        projects = tuple(
            sorted(
                {
                    _required_text(project_id, "authoritative project_id")
                    for project_id in authoritative_project_ids
                }
            )
        )
        expected = {
            (
                _required_text(project_id, "expected project_id"),
                _required_text(task_id, "expected task_id"),
            )
            for project_id, task_id in expected_identities
        }
        evaluated = (
            {
                (
                    _required_text(project_id, "evaluated project_id"),
                    _required_text(task_id, "evaluated task_id"),
                )
                for project_id, task_id in evaluated_identities
            }
            if evaluated_identities is not None
            else set(expected)
        )
        if not evaluated <= expected:
            raise ValueError("evaluated identities escaped expected membership")
        unexpected_projects = {project_id for project_id, _task_id in expected} - set(
            projects
        )
        if unexpected_projects:
            raise ValueError(
                "expected identities escaped authoritative projects: "
                + ", ".join(sorted(unexpected_projects))
            )
        timestamp = float(self._clock() if now is None else now)
        replacement_generation = f"snapshot:{snapshot}"
        message = "task absent from newer authoritative workflow snapshot"
        with self._authority_mutation_guard():
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                if not self._snapshot_generation_is_current_locked(snapshot):
                    self._conn.commit()
                    return WorkflowSnapshotMembershipWrite(snapshot, accepted=False)
                cursors_retired = 0
                jobs_superseded = 0
                for project in projects:
                    expected_tasks = {
                        task_id
                        for project_id, task_id in expected
                        if project_id == project
                    }
                    prior_membership = {
                        str(row["task_id"]): int(row["snapshot_generation"])
                        for row in self._conn.execute(
                            """
                            SELECT task_id, snapshot_generation
                              FROM workflow_snapshot_membership
                             WHERE project_id = ?
                            """,
                            (project,),
                        ).fetchall()
                    }
                    known_tasks = {
                        str(row["task_id"])
                        for row in self._conn.execute(
                            """
                            SELECT task_id FROM workflow_schedule_cursors
                             WHERE project_id = ?
                            UNION
                            SELECT task_id FROM workflow_snapshot_membership
                             WHERE project_id = ?
                            UNION
                            SELECT task_id FROM workflow_jobs
                             WHERE project_id = ? AND workflow_managed = 1
                               AND state IN (?, ?, ?)
                            """,
                            (
                                project,
                                project,
                                project,
                                WorkflowJobState.QUEUED.value,
                                WorkflowJobState.RUNNING.value,
                                WorkflowJobState.RETRY_WAIT.value,
                            ),
                        ).fetchall()
                    }
                    for task in sorted(known_tasks - expected_tasks):
                        active_rows = self._conn.execute(
                            """
                            SELECT * FROM workflow_jobs
                             WHERE project_id = ? AND task_id = ?
                               AND workflow_managed = 1
                               AND state IN (?, ?, ?)
                             ORDER BY enqueue_sequence
                            """,
                            (
                                project,
                                task,
                                WorkflowJobState.QUEUED.value,
                                WorkflowJobState.RUNNING.value,
                                WorkflowJobState.RETRY_WAIT.value,
                            ),
                        ).fetchall()
                        for selected in active_rows:
                            if (
                                str(selected["state"])
                                == WorkflowJobState.RUNNING.value
                                and str(selected["phase"]) == "quarantined"
                            ):
                                continue
                            self._conn.execute(
                                """
                                UPDATE workflow_jobs
                                   SET state = ?, lease_owner = NULL,
                                       lease_token = NULL, lease_expires_at = NULL,
                                       retry_at = NULL,
                                       superseded_by_generation = ?,
                                       last_error = ?, updated_at = ?,
                                       completed_at = ?
                                 WHERE job_id = ?
                                """,
                                (
                                    WorkflowJobState.SUPERSEDED.value,
                                    replacement_generation,
                                    message,
                                    timestamp,
                                    timestamp,
                                    selected["job_id"],
                                ),
                            )
                            updated = self._row_locked(str(selected["job_id"]))
                            self._append_event_locked(
                                updated,
                                "superseded",
                                payload={
                                    "replacement_generation": replacement_generation,
                                    "reason": message,
                                },
                                now=timestamp,
                            )
                            jobs_superseded += 1
                        deleted = self._conn.execute(
                            """
                            DELETE FROM workflow_schedule_cursors
                             WHERE project_id = ? AND task_id = ?
                            """,
                            (project, task),
                        )
                        cursors_retired += max(0, int(deleted.rowcount))
                    self._conn.execute(
                        "DELETE FROM workflow_snapshot_membership WHERE project_id = ?",
                        (project,),
                    )
                    self._conn.executemany(
                        """
                        INSERT INTO workflow_snapshot_membership(
                            project_id, task_id, snapshot_generation, updated_at
                        ) VALUES (?, ?, ?, ?)
                        """,
                        (
                            (
                                project,
                                task,
                                (
                                    snapshot
                                    if (project, task) in evaluated
                                    else prior_membership.get(task, snapshot)
                                ),
                                timestamp,
                            )
                            for task in sorted(expected_tasks)
                        ),
                    )
                self._conn.commit()
                return WorkflowSnapshotMembershipWrite(
                    snapshot,
                    accepted=True,
                    members=len(expected),
                    cursors_retired=cursors_retired,
                    jobs_superseded=jobs_superseded,
                )
            except Exception:
                self._conn.rollback()
                raise

    def snapshot_membership(self) -> tuple[tuple[str, str, int], ...]:
        """Return the bounded current full-snapshot membership for diagnostics."""

        with self._authority_mutation_guard():
            rows = self._conn.execute(
                """
                SELECT project_id, task_id, snapshot_generation
                  FROM workflow_snapshot_membership
                 ORDER BY project_id, task_id
                """
            ).fetchall()
        return tuple(
            (
                str(row["project_id"]),
                str(row["task_id"]),
                int(row["snapshot_generation"]),
            )
            for row in rows
        )

    def capture_snapshot_authority(
        self,
        *,
        authoritative_project_ids: Sequence[str] = (),
        evaluated_identities: Sequence[tuple[str, str]] = (),
        full_project_scope: bool,
    ) -> WorkflowSnapshotAuthority:
        """Capture current durable authority before independently committed writes.

        Scheduler membership, cursor, and job writes use short SQLite
        transactions before the service-state file can be published.  Keeping
        this small in-memory checkpoint lets a failed publication restore the
        prior *published* authority instead of deleting it and leaving an
        unrelated recovery scan to reconstruct it later.
        """

        projects = tuple(
            sorted(
                {
                    _required_text(project_id, "authoritative project_id")
                    for project_id in authoritative_project_ids
                }
            )
        )
        identities = tuple(
            sorted(
                {
                    (
                        _required_text(project_id, "evaluated project_id"),
                        _required_text(task_id, "evaluated task_id"),
                    )
                    for project_id, task_id in evaluated_identities
                }
            )
        )
        if not full_project_scope and not identities:
            return WorkflowSnapshotAuthority(
                projects, identities, False, (), (), ()
            )
        if full_project_scope and not projects:
            return WorkflowSnapshotAuthority(
                projects, identities, True, (), (), ()
            )

        if full_project_scope:
            placeholders = ",".join("?" for _ in projects)
            where = f"project_id IN ({placeholders})"
            params: tuple[Any, ...] = projects
        else:
            predicates = " OR ".join(
                "(project_id = ? AND task_id = ?)" for _ in identities
            )
            where = f"({predicates})"
            params = tuple(item for identity in identities for item in identity)

        with self._authority_mutation_guard():
            cursors = tuple(
                dict(row)
                for row in self._conn.execute(
                    f"SELECT * FROM workflow_schedule_cursors WHERE {where}", params
                ).fetchall()
            )
            memberships = tuple(
                dict(row)
                for row in self._conn.execute(
                    f"SELECT * FROM workflow_snapshot_membership WHERE {where}", params
                ).fetchall()
            )
            jobs = tuple(
                dict(row)
                for row in self._conn.execute(
                    f"SELECT * FROM workflow_jobs WHERE {where} AND workflow_managed = 1",
                    params,
                ).fetchall()
            )
            retirements = tuple(
                dict(row)
                for row in self._conn.execute(
                    "SELECT * FROM workflow_job_retirements WHERE "
                    f"{where} AND snapshot_generation IS NOT NULL",
                    params,
                ).fetchall()
            )
            event_row = self._conn.execute(
                "SELECT COALESCE(MAX(sequence), 0) AS sequence "
                "FROM workflow_job_events"
            ).fetchone()
            highwater_row = self._conn.execute(
                "SELECT value FROM schema_meta WHERE key = ?",
                (_JOB_EVENT_HIGHWATER_KEY,),
            ).fetchone()
            live_sequence = int(event_row["sequence"] if event_row else 0)
            persisted_highwater = (
                int(highwater_row["value"]) if highwater_row is not None else 0
            )
            # Archival relocates the tail of the ledger into cold storage, so
            # the persisted high-water mark is the authoritative global maximum.
            job_event_sequence = max(live_sequence, persisted_highwater)
        return WorkflowSnapshotAuthority(
            projects,
            identities,
            full_project_scope,
            cursors,
            memberships,
            jobs,
            retirements,
            job_event_sequence,
        )

    def restore_snapshot_authority(
        self,
        authority: WorkflowSnapshotAuthority,
        *,
        snapshot_generation: int,
        now: float | None = None,
    ) -> bool:
        """Restore a pre-publication authority checkpoint under the generation fence."""

        if not isinstance(authority, WorkflowSnapshotAuthority):
            raise TypeError("authority must be a WorkflowSnapshotAuthority")
        if isinstance(snapshot_generation, bool) or int(snapshot_generation) < 1:
            raise ValueError("snapshot_generation must be a positive integer")
        snapshot = int(snapshot_generation)
        timestamp = float(self._clock() if now is None else now)
        if authority.full_project_scope:
            if not authority.project_ids:
                return True
            placeholders = ",".join("?" for _ in authority.project_ids)
            where = f"project_id IN ({placeholders})"
            params: tuple[Any, ...] = authority.project_ids
        else:
            if not authority.identities:
                return True
            predicates = " OR ".join(
                "(project_id = ? AND task_id = ?)" for _ in authority.identities
            )
            where = f"({predicates})"
            params = tuple(item for identity in authority.identities for item in identity)

        before_jobs = {str(row["job_id"]): row for row in authority.jobs}
        with self._authority_mutation_guard():
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                published_row = self._conn.execute(
                    "SELECT value FROM schema_meta "
                    "WHERE key = 'workflow_snapshot_published_generation'"
                ).fetchone()
                published = int(published_row["value"]) if published_row else 0
                if (
                    published >= snapshot
                    or not self._snapshot_generation_is_current_locked(snapshot)
                ):
                    self._conn.commit()
                    return False

                # Job events are append-only, making the capture sequence a
                # durable ABA fence. An explicit rearm after this checkpoint
                # is newer execution authority: rollback may remove writes
                # staged by the failed snapshot, but it must not restore the
                # captured terminal state or retirement proof over that rearm.
                rearmed_after_capture = {
                    str(row["job_id"])
                    for row in self._conn.execute(
                        "SELECT DISTINCT job_id FROM workflow_job_events "
                        "WHERE event_type = 'rearmed' AND sequence > ? AND "
                        f"{where}",
                        (authority.job_event_sequence, *params),
                    ).fetchall()
                }

                current_jobs = self._conn.execute(
                    f"SELECT * FROM workflow_jobs WHERE {where} AND workflow_managed = 1",
                    params,
                ).fetchall()
                # Collect affected job ids per task and emit a single aggregate
                # rollback event per task below, rather than one event per job.
                rolled_back: dict[tuple[str, str], list[str]] = {}
                for current in current_jobs:
                    job_id = str(current["job_id"])
                    if (
                        str(current["state"]) == WorkflowJobState.RUNNING.value
                        and str(current["phase"]) == "quarantined"
                    ):
                        # The detached adapter call still owns this task.  A
                        # failed snapshot may restore scheduler authority, but
                        # it cannot make the in-flight external call overlap a
                        # replacement by restoring its pre-quarantine lease or
                        # superseding a job created after the checkpoint.
                        continue
                    if job_id in rearmed_after_capture:
                        continue
                    prior = before_jobs.get(job_id)
                    if prior is not None:
                        columns = [
                            key
                            for key in prior
                            if key not in {"enqueue_sequence", "job_id"}
                        ]
                        self._conn.execute(
                            "UPDATE workflow_jobs SET "
                            + ", ".join(f"{column} = ?" for column in columns)
                            + " WHERE job_id = ?",
                            tuple(prior[column] for column in columns) + (job_id,),
                        )
                        rolled_back.setdefault(
                            (str(current["project_id"]), str(current["task_id"])),
                            [],
                        ).append(job_id)
                        continue
                    if str(current["state"]) in {
                        state.value for state in ACTIVE_JOB_STATES
                    }:
                        self._conn.execute(
                            """
                            UPDATE workflow_jobs
                               SET state = ?, lease_owner = NULL,
                                   lease_token = NULL, lease_expires_at = NULL,
                                   retry_at = NULL,
                                   superseded_by_generation = ?, last_error = ?,
                                   updated_at = ?, completed_at = ?
                             WHERE job_id = ?
                            """,
                            (
                                WorkflowJobState.SUPERSEDED.value,
                                f"publication-rollback:{snapshot}",
                                "workflow snapshot publication did not commit",
                                timestamp,
                                timestamp,
                                job_id,
                            ),
                        )
                        rolled_back.setdefault(
                            (str(current["project_id"]), str(current["task_id"])),
                            [],
                        ).append(job_id)
                for (proj, task), job_ids in sorted(rolled_back.items()):
                    self._append_rollback_summary_locked(
                        project_id=proj,
                        task_id=task,
                        job_ids=job_ids,
                        snapshot=snapshot,
                        reason=None,
                        now=timestamp,
                    )

                self._conn.execute(
                    f"DELETE FROM workflow_schedule_cursors WHERE {where}", params
                )
                self._conn.execute(
                    f"DELETE FROM workflow_snapshot_membership WHERE {where}", params
                )
                self._conn.execute(
                    "DELETE FROM workflow_job_retirements WHERE "
                    f"{where} AND snapshot_generation IS NOT NULL",
                    params,
                )
                self._conn.execute(
                    "DELETE FROM workflow_retirement_authority_cuts WHERE "
                    f"{where} AND snapshot_generation = ?",
                    (*params, snapshot),
                )
                captured_retirements = tuple(
                    row
                    for row in authority.retirements
                    if str(row["job_id"]) not in rearmed_after_capture
                )
                for table, rows in (
                    ("workflow_schedule_cursors", authority.cursors),
                    ("workflow_snapshot_membership", authority.memberships),
                    ("workflow_job_retirements", captured_retirements),
                ):
                    if not rows:
                        continue
                    columns = tuple(rows[0])
                    self._conn.executemany(
                        f"INSERT INTO {table} ({', '.join(columns)}) "
                        f"VALUES ({', '.join('?' for _ in columns)})",
                        [tuple(row[column] for column in columns) for row in rows],
                    )
                # Reconciliation accepts a generation before its independently
                # committed membership, cursor, and job writes begin.  Once a
                # later publication step fails, restoring those rows is not
                # enough: leaving the accepted marker at ``snapshot`` would
                # make the generation look current before a retry publishes a
                # new liveness/WorkDecision cut.  Return acceptance to the last
                # published generation so managed jobs remain unclaimable and
                # the same capture can be re-accepted for a versioned failure
                # publication.
                self._conn.execute(
                    "INSERT OR REPLACE INTO schema_meta(key, value) "
                    "VALUES('workflow_snapshot_accepted_generation', ?)",
                    (str(published),),
                )
                self._conn.commit()
                return True
            except Exception:
                self._conn.rollback()
                raise

    def rollback_snapshot_authority(
        self,
        *,
        snapshot_generation: int,
        authoritative_project_ids: Sequence[str] = (),
        evaluated_identities: Sequence[tuple[str, str]] = (),
        now: float | None = None,
    ) -> bool:
        """Quarantine mutations whose external publication did not commit.

        Full-snapshot projects are invalidated as a unit. This intentionally
        favors fail-closed recovery over reconstructing superseded leases from
        stale pre-snapshot rows. A subsequent complete generation rebuilds the
        membership and cursor authority. Unmanaged direct-enqueue jobs are not
        part of workflow snapshot authority and are never changed here.
        """

        if isinstance(snapshot_generation, bool) or int(snapshot_generation) < 1:
            raise ValueError("snapshot_generation must be a positive integer")
        snapshot = int(snapshot_generation)
        projects = {
            _required_text(project_id, "authoritative project_id")
            for project_id in authoritative_project_ids
        }
        identities = {
            (
                _required_text(project_id, "evaluated project_id"),
                _required_text(task_id, "evaluated task_id"),
            )
            for project_id, task_id in evaluated_identities
        }
        timestamp = float(self._clock() if now is None else now)
        replacement_generation = f"publication-rollback:{snapshot}"
        message = "workflow snapshot publication did not commit"
        with self._authority_mutation_guard():
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                published_row = self._conn.execute(
                    "SELECT value FROM schema_meta "
                    "WHERE key = 'workflow_snapshot_published_generation'"
                ).fetchone()
                published = (
                    int(published_row["value"])
                    if published_row is not None
                    else 0
                )
                if (
                    published >= snapshot
                    or not self._snapshot_generation_is_current_locked(snapshot)
                ):
                    self._conn.commit()
                    return False

                affected = set(identities)
                for project in sorted(projects):
                    rows = self._conn.execute(
                        """
                        SELECT project_id, task_id FROM workflow_schedule_cursors
                         WHERE project_id = ?
                        UNION
                        SELECT project_id, task_id FROM workflow_snapshot_membership
                         WHERE project_id = ?
                        UNION
                        SELECT project_id, task_id FROM workflow_jobs
                         WHERE project_id = ? AND workflow_managed = 1
                           AND state IN (?, ?, ?)
                        """,
                        (
                            project,
                            project,
                            project,
                            WorkflowJobState.QUEUED.value,
                            WorkflowJobState.RUNNING.value,
                            WorkflowJobState.RETRY_WAIT.value,
                        ),
                    ).fetchall()
                    affected.update(
                        (str(row["project_id"]), str(row["task_id"]))
                        for row in rows
                    )

                for project, task in sorted(affected):
                    active_rows = self._conn.execute(
                        """
                        SELECT * FROM workflow_jobs
                         WHERE project_id = ? AND task_id = ?
                           AND workflow_managed = 1
                           AND state IN (?, ?, ?)
                         ORDER BY enqueue_sequence
                        """,
                        (
                            project,
                            task,
                            WorkflowJobState.QUEUED.value,
                            WorkflowJobState.RUNNING.value,
                            WorkflowJobState.RETRY_WAIT.value,
                        ),
                    ).fetchall()
                    rolled_back_ids: list[str] = []
                    for selected in active_rows:
                        if (
                            str(selected["state"])
                            == WorkflowJobState.RUNNING.value
                            and str(selected["phase"]) == "quarantined"
                        ):
                            continue
                        self._conn.execute(
                            """
                            UPDATE workflow_jobs
                               SET state = ?, lease_owner = NULL,
                                   lease_token = NULL, lease_expires_at = NULL,
                                   retry_at = NULL,
                                   superseded_by_generation = ?, last_error = ?,
                                   updated_at = ?, completed_at = ?
                             WHERE job_id = ?
                            """,
                            (
                                WorkflowJobState.SUPERSEDED.value,
                                replacement_generation,
                                message,
                                timestamp,
                                timestamp,
                                selected["job_id"],
                            ),
                        )
                        rolled_back_ids.append(str(selected["job_id"]))
                    self._append_rollback_summary_locked(
                        project_id=project,
                        task_id=task,
                        job_ids=rolled_back_ids,
                        snapshot=snapshot,
                        reason=message,
                        now=timestamp,
                    )
                    self._conn.execute(
                        "DELETE FROM workflow_schedule_cursors "
                        "WHERE project_id = ? AND task_id = ?",
                        (project, task),
                    )
                    self._conn.execute(
                        "DELETE FROM workflow_snapshot_membership "
                        "WHERE project_id = ? AND task_id = ?",
                        (project, task),
                    )
                    self._conn.execute(
                        "DELETE FROM workflow_job_retirements "
                        "WHERE project_id = ? AND task_id = ? "
                        "AND snapshot_generation = ?",
                        (project, task, snapshot),
                    )
                    self._conn.execute(
                        "DELETE FROM workflow_retirement_authority_cuts "
                        "WHERE project_id = ? AND task_id = ? "
                        "AND snapshot_generation = ?",
                        (project, task, snapshot),
                    )
                for project in sorted(projects):
                    self._conn.execute(
                        "DELETE FROM workflow_schedule_cursors WHERE project_id = ?",
                        (project,),
                    )
                    self._conn.execute(
                        "DELETE FROM workflow_snapshot_membership WHERE project_id = ?",
                        (project,),
                    )
                    self._conn.execute(
                        "DELETE FROM workflow_job_retirements "
                        "WHERE project_id = ? AND snapshot_generation = ?",
                        (project, snapshot),
                    )
                    self._conn.execute(
                        "DELETE FROM workflow_retirement_authority_cuts "
                        "WHERE project_id = ? AND snapshot_generation = ?",
                        (project, snapshot),
                    )
                self._conn.commit()
                return True
            except Exception:
                self._conn.rollback()
                raise

    @staticmethod
    def _schedule_cursor_from_row(
        row: sqlite3.Row, *, changed: bool, accepted: bool = True
    ) -> WorkflowScheduleCursor:
        return WorkflowScheduleCursor(
            project_id=str(row["project_id"]),
            task_id=str(row["task_id"]),
            snapshot_generation=int(row["snapshot_generation"]),
            decision_revision=str(row["decision_revision"]),
            job_generation=str(row["job_generation"]),
            changed=changed,
            accepted=accepted,
            materialized=(
                str(row["materialized_job_generation"] or "")
                == str(row["job_generation"])
            ),
        )

    def schedule_cursor(
        self, *, project_id: str, task_id: str
    ) -> WorkflowScheduleCursor | None:
        project = _required_text(project_id, "project_id")
        task = _required_text(task_id, "task_id")
        with self._lock:
            row = self._conn.execute(
                """
                SELECT * FROM workflow_schedule_cursors
                 WHERE project_id = ? AND task_id = ?
                """,
                (project, task),
            ).fetchone()
        return (
            self._schedule_cursor_from_row(row, changed=False)
            if row is not None
            else None
        )

    def event_lane_materialized(
        self,
        *,
        project_id: str,
        task_id: str,
        ordering_namespace: str,
        scheduling_lane: str,
        source_revision: str,
        actions: Sequence[str],
        now: float | None = None,
    ) -> bool:
        """Prove the latest ordered event lane and its exact durable job.

        This is a read-only evidence seam for liveness.  Matching a historical
        job by action is insufficient: the ordering revision, event cursor,
        cursor generation, lane, and live job must all describe the latest
        disposition for the task.
        """

        project = _required_text(project_id, "project_id")
        task = _required_text(task_id, "task_id")
        ordering = _required_text(ordering_namespace, "ordering_namespace")
        lane = _required_text(scheduling_lane, "scheduling_lane")
        revision = _required_text(source_revision, "source_revision")
        normalized_actions = tuple(
            sorted({_required_text(action, "action") for action in actions})
        )
        if not normalized_actions:
            raise ValueError("actions cannot be empty")
        timestamp = float(self._clock() if now is None else now)
        with self._lock:
            ordered = self._conn.execute(
                """
                SELECT decision_revision
                  FROM workflow_event_ordering
                 WHERE project_id = ? AND task_id = ?
                   AND ordering_namespace = ?
                """,
                (project, task, ordering),
            ).fetchone()
            if ordered is None or str(ordered["decision_revision"]) != revision:
                return False
            cursor = self._conn.execute(
                """
                SELECT event_generation
                  FROM workflow_event_cursors
                 WHERE project_id = ? AND task_id = ?
                   AND event_namespace = ?
                """,
                (project, task, lane),
            ).fetchone()
            if cursor is None:
                return False
            rows = self._conn.execute(
                f"""
                SELECT action, state, lease_owner, lease_expires_at
                  FROM workflow_jobs
                 WHERE project_id = ? AND task_id = ?
                   AND generation = ? AND scheduling_lane = ?
                   AND action IN ({','.join('?' for _ in normalized_actions)})
                """,
                (
                    project,
                    task,
                    str(cursor["event_generation"]),
                    lane,
                    *normalized_actions,
                ),
            ).fetchall()
        return (
            len(rows) == len(normalized_actions)
            and {str(row["action"]) for row in rows}
            == set(normalized_actions)
            and all(
                _job_row_proves_live_authority(row, now=timestamp)
                for row in rows
            )
        )

    def protected_event_lane_materialized(
        self,
        *,
        project_id: str,
        task_id: str,
        ordering_namespace: str,
        source_revision: str,
        scheduling_lanes: Sequence[str],
        actions: Sequence[str],
        now: float | None = None,
    ) -> bool:
        """Prove a live protected event as substitute execution authority.

        A fact-derived implementation decision may advance the shared ordering
        cursor while an active imperative event deliberately prevents creation
        of a replacement fact job.  In that case the protected event, rather
        than the absent fact lane, is the exact authority that must drain
        before the fact decision can take effect.  Bind the proof to the
        current ordering revision so an older scan cannot borrow a newer
        imperative job.
        """

        project = _required_text(project_id, "project_id")
        task = _required_text(task_id, "task_id")
        ordering = _required_text(ordering_namespace, "ordering_namespace")
        revision = _required_text(source_revision, "source_revision")
        lanes = tuple(
            sorted(
                {
                    _required_text(lane, "scheduling_lane")
                    for lane in scheduling_lanes
                }
            )
        )
        normalized_actions = tuple(
            sorted({_required_text(action, "action") for action in actions})
        )
        if not lanes:
            raise ValueError("scheduling_lanes cannot be empty")
        if not normalized_actions:
            raise ValueError("actions cannot be empty")
        timestamp = float(self._clock() if now is None else now)
        with self._lock:
            ordered = self._conn.execute(
                """
                SELECT decision_revision
                  FROM workflow_event_ordering
                 WHERE project_id = ? AND task_id = ?
                   AND ordering_namespace = ?
                """,
                (project, task, ordering),
            ).fetchone()
            if ordered is None or str(ordered["decision_revision"]) != revision:
                return False
            row = self._conn.execute(
                f"""
                SELECT action, state, lease_owner, lease_expires_at
                  FROM workflow_jobs
                 WHERE project_id = ? AND task_id = ?
                   AND scheduling_lane IN (
                       {','.join('?' for _ in lanes)}
                   )
                   AND action IN (
                       {','.join('?' for _ in normalized_actions)}
                   )
                   AND state IN (
                       {','.join('?' for _ in ACTIVE_JOB_STATES)}
                   )
                 ORDER BY enqueue_sequence DESC LIMIT 1
                """,
                (
                    project,
                    task,
                    *lanes,
                    *normalized_actions,
                    *(state.value for state in ACTIVE_JOB_STATES),
                ),
            ).fetchone()
        return bool(
            row is not None
            and _job_row_proves_live_authority(row, now=timestamp)
        )

    def reconcile_event_handoff_retirements(
        self,
        *,
        project_id: str,
        task_id: str,
        authority_scheduling_lanes: Sequence[str],
        retired_scheduling_lanes: Sequence[str],
        actions: Sequence[str],
        now: float | None = None,
    ) -> int:
        """Retire exhausted lanes behind the current exact event authority.

        This also repairs handoffs written by an older service version: the
        active event cursor and its concrete non-retired job are sufficient
        durable authority. Only explicitly named sibling lanes are retired.
        """

        project = _required_text(project_id, "project_id")
        task = _required_text(task_id, "task_id")
        authority_lanes = tuple(
            sorted(
                {
                    _required_text(lane, "authority_scheduling_lane")
                    for lane in authority_scheduling_lanes
                }
            )
        )
        retired_lanes = tuple(
            sorted(
                {
                    _required_text(lane, "retired_scheduling_lane")
                    for lane in retired_scheduling_lanes
                }
            )
        )
        normalized_actions = tuple(
            sorted({_required_text(action, "action") for action in actions})
        )
        if not authority_lanes:
            raise ValueError("authority_scheduling_lanes cannot be empty")
        if not retired_lanes:
            raise ValueError("retired_scheduling_lanes cannot be empty")
        if not normalized_actions:
            raise ValueError("actions cannot be empty")
        timestamp = float(self._clock() if now is None else now)
        with self._authority_mutation_guard():
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                authority = self._conn.execute(
                    f"""
                    SELECT job.generation, job.scheduling_lane,
                           job.enqueue_sequence
                      FROM workflow_jobs job
                      JOIN workflow_event_cursors cursor
                        ON cursor.project_id = job.project_id
                       AND cursor.task_id = job.task_id
                       AND cursor.event_namespace = job.scheduling_lane
                       AND cursor.event_generation = job.generation
                     WHERE job.project_id = ? AND job.task_id = ?
                       AND job.workflow_managed = 0
                       AND job.scheduling_lane IN (
                           {','.join('?' for _ in authority_lanes)}
                       )
                       AND job.action IN (
                           {','.join('?' for _ in normalized_actions)}
                       )
                       AND job.state NOT IN (?, ?)
                     ORDER BY job.enqueue_sequence DESC LIMIT 1
                    """,
                    (
                        project,
                        task,
                        *authority_lanes,
                        *normalized_actions,
                        WorkflowJobState.SUPERSEDED.value,
                        WorkflowJobState.CANCELLED.value,
                    ),
                ).fetchone()
                if authority is None:
                    self._conn.commit()
                    return 0
                retired = self._record_event_handoff_retirements_locked(
                    project_id=project,
                    task_id=task,
                    authority_generation=str(authority["generation"]),
                    authority_scheduling_lane=str(authority["scheduling_lane"]),
                    authority_enqueue_sequence=int(
                        authority["enqueue_sequence"]
                    ),
                    retired_scheduling_lanes=retired_lanes,
                    now=timestamp,
                )
                self._conn.commit()
                return retired
            except Exception:
                self._conn.rollback()
                raise

    def terminal_audit_lane_materialized(
        self,
        *,
        project_id: str,
        task_id: str,
        audit_id: str,
        target_state: str,
        evidence_fingerprint: str,
        audit_generation: str,
        source_generation: int,
        obligation_action: str = "terminal_audit",
        now: float | None = None,
    ) -> bool:
        """Prove the current exact audit lane has live execution authority."""

        project = _required_text(project_id, "project_id")
        task = _required_text(task_id, "task_id")
        audit = _required_text(audit_id, "audit_id")
        target = _required_text(target_state, "target_state")
        evidence = _required_text(
            evidence_fingerprint, "evidence_fingerprint"
        )
        generation = _required_text(audit_generation, "audit_generation")
        obligation = _required_text(obligation_action, "obligation_action")
        if obligation not in {"terminal_audit", "terminal_audit_recovery"}:
            raise ValueError("unsupported terminal-audit obligation action")
        if isinstance(source_generation, bool) or int(source_generation) < 1:
            raise ValueError("source_generation must be a positive integer")
        lane = f"terminal-audit:{target}"
        with self._lock:
            ordered = self._conn.execute(
                """
                SELECT source_generation, decision_revision
                  FROM workflow_event_ordering
                 WHERE project_id = ? AND task_id = ?
                   AND ordering_namespace = ?
                """,
                (project, task, lane),
            ).fetchone()
            if (
                ordered is None
                or int(ordered["source_generation"]) != int(source_generation)
                or str(ordered["decision_revision"]) != generation
            ):
                return False
            latest = self._conn.execute(
                """
                SELECT action, generation, scheduling_lane,
                       expected_evidence_revision, state, phase,
                       lease_owner, lease_expires_at, checkpoint_json
                  FROM workflow_jobs
                 WHERE project_id = ? AND task_id = ?
                   AND scheduling_lane = ?
                 ORDER BY enqueue_sequence DESC
                 LIMIT 1
                """,
                (project, task, lane),
            ).fetchone()
        exact = bool(
            latest is not None
            and str(latest["action"]) == "terminal_audit"
            and str(latest["generation"]) == generation
            and str(latest["scheduling_lane"]) == lane
            and str(latest["expected_evidence_revision"] or "") == evidence
            and str(latest["state"])
            not in {
                WorkflowJobState.SUPERSEDED.value,
                WorkflowJobState.CANCELLED.value,
            }
        )
        if not exact:
            return False
        state = WorkflowJobState(str(latest["state"]))
        if state in {
            WorkflowJobState.QUEUED,
            WorkflowJobState.RETRY_WAIT,
        }:
            return True
        timestamp = float(self._clock() if now is None else now)
        checkpoint = _decode_json_object(
            latest["checkpoint_json"], "checkpoint"
        ) or {}
        return bool(
            state is WorkflowJobState.RUNNING
            and str(latest["phase"] or "") in {"running", "finalizing"}
            and str(checkpoint.get("audit_id") or "") == audit
            and str(latest["lease_owner"] or "").strip()
            and latest["lease_expires_at"] is not None
            and float(latest["lease_expires_at"]) > timestamp
        )

    def schedule_specs_materialized(
        self,
        *,
        project_id: str,
        task_id: str,
        decision_revision: str,
        job_generation: str,
        idempotency_keys: Sequence[str],
        now: float | None = None,
    ) -> bool:
        """Verify the durable semantic cursor and all of its required jobs."""

        project = _required_text(project_id, "project_id")
        task = _required_text(task_id, "task_id")
        revision = _required_text(decision_revision, "decision_revision")
        generation = _required_text(job_generation, "job_generation")
        raw_keys = tuple(
            _required_text(key, "idempotency_key")
            for key in idempotency_keys
        )
        keys = tuple(sorted(set(raw_keys)))
        if len(keys) != len(raw_keys):
            raise ValueError("idempotency_keys must be unique")
        if len(keys) > 1:
            raise ValueError(
                "one scheduler activation may materialize at most one job"
            )
        timestamp = float(self._clock() if now is None else now)
        completed_until = _schedule_reassessment_deadline(generation)
        with self._lock:
            cursor = self._conn.execute(
                """
                SELECT * FROM workflow_schedule_cursors
                 WHERE project_id = ? AND task_id = ?
                """,
                (project, task),
            ).fetchone()
            if (
                cursor is None
                or str(cursor["decision_revision"]) != revision
                or str(cursor["job_generation"]) != generation
                or str(cursor["materialized_job_generation"] or "")
                != generation
            ):
                return False
            if not keys:
                return True
            rows = self._conn.execute(
                f"""
                SELECT idempotency_key, state, lease_owner, lease_expires_at
                  FROM workflow_jobs
                 WHERE project_id = ?
                   AND idempotency_key IN ({','.join('?' for _ in keys)})
                """,
                (project, *keys),
            ).fetchall()
        return bool(
            {str(row["idempotency_key"]) for row in rows} == set(keys)
            and all(
                _job_row_proves_live_authority(
                    row,
                    now=timestamp,
                    completed_until=completed_until,
                )
                for row in rows
            )
        )

    def schedule_substitute_materialized(
        self,
        *,
        project_id: str,
        task_id: str,
        decision_revision: str,
        job_generation: str,
        action: str,
        scheduling_lanes: Sequence[str],
        now: float | None = None,
    ) -> bool:
        """Prove a protected event job owns one managed schedule obligation.

        Some domain event routers intentionally supersede a managed decision
        job after publication.  The event remains the execution authority that
        must drain.  Bind that substitute proof to the current managed cursor
        and require the exact action in an explicitly configured event lane so
        neither a stale scan nor unrelated maintenance work can satisfy it.
        """

        project = _required_text(project_id, "project_id")
        task = _required_text(task_id, "task_id")
        revision = _required_text(decision_revision, "decision_revision")
        generation = _required_text(job_generation, "job_generation")
        normalized_action = _required_text(action, "action")
        lanes = tuple(
            sorted(
                {
                    _required_text(lane, "scheduling_lane")
                    for lane in scheduling_lanes
                }
            )
        )
        if not lanes:
            raise ValueError("scheduling_lanes cannot be empty")
        timestamp = float(self._clock() if now is None else now)
        with self._lock:
            cursor = self._conn.execute(
                """
                SELECT * FROM workflow_schedule_cursors
                 WHERE project_id = ? AND task_id = ?
                """,
                (project, task),
            ).fetchone()
            if (
                cursor is None
                or str(cursor["decision_revision"]) != revision
                or str(cursor["job_generation"]) != generation
                or str(cursor["materialized_job_generation"] or "")
                != generation
            ):
                return False
            row = self._conn.execute(
                f"""
                SELECT state, lease_owner, lease_expires_at
                  FROM workflow_jobs
                 WHERE project_id = ? AND task_id = ? AND action = ?
                   AND scheduling_lane IN (
                       {','.join('?' for _ in lanes)}
                   )
                   AND state IN (
                       {','.join('?' for _ in ACTIVE_JOB_STATES)}
                   )
                 ORDER BY enqueue_sequence DESC LIMIT 1
                """,
                (
                    project,
                    task,
                    normalized_action,
                    *lanes,
                    *(state.value for state in ACTIVE_JOB_STATES),
                ),
            ).fetchone()
        return bool(
            row is not None
            and _job_row_proves_live_authority(row, now=timestamp)
        )

    def activate_schedule(
        self,
        *,
        project_id: str,
        task_id: str,
        decision_revision: str,
        snapshot_generation: int,
        next_reassessment_at: float | None = None,
        protected_action: str | None = None,
        protected_scheduling_lanes: Sequence[str] = (),
        now: float | None = None,
    ) -> WorkflowScheduleCursor:
        """CAS one decision into the durable task scheduling cursor.

        A decision can recur after an intervening generation was superseded.
        In that case it receives a new activation generation even though its
        semantic decision revision is identical to an older historical row.
        """

        project = _required_text(project_id, "project_id")
        task = _required_text(task_id, "task_id")
        revision = _required_text(decision_revision, "decision_revision")
        if isinstance(snapshot_generation, bool) or int(snapshot_generation) < 1:
            raise ValueError("snapshot_generation must be a positive integer")
        snapshot = int(snapshot_generation)
        deadline = (
            None
            if next_reassessment_at is None
            else float(next_reassessment_at)
        )
        protected_lanes = tuple(
            sorted(
                {
                    _required_text(lane, "protected_scheduling_lane")
                    for lane in protected_scheduling_lanes
                }
            )
        )
        protected_job_action = (
            _required_text(protected_action, "protected_action")
            if protected_action is not None
            else None
        )
        if (protected_job_action is None) != (not protected_lanes):
            raise ValueError(
                "protected_action and protected_scheduling_lanes must be "
                "supplied together"
            )
        timestamp = float(self._clock() if now is None else now)

        def job_generation(deadline_at: float | None) -> str:
            suffix = (
                ""
                if deadline_at is None
                else (
                    f"{_REASSESSMENT_GENERATION_MARKER}"
                    f"{deadline_at:.6f}"
                )
            )
            return f"{revision}:{snapshot}{suffix}"

        with self._authority_mutation_guard():
            owns_transaction = not self._conn.in_transaction
            if owns_transaction:
                self._conn.execute("BEGIN IMMEDIATE")
            try:
                existing = self._conn.execute(
                    """
                    SELECT * FROM workflow_schedule_cursors
                     WHERE project_id = ? AND task_id = ?
                    """,
                    (project, task),
                ).fetchone()
                if not self._snapshot_generation_is_current_locked(snapshot):
                    if owns_transaction:
                        self._conn.commit()
                    if existing is not None:
                        return self._schedule_cursor_from_row(
                            existing, changed=False, accepted=False
                        )
                    return WorkflowScheduleCursor(
                        project_id=project,
                        task_id=task,
                        snapshot_generation=snapshot,
                        decision_revision=revision,
                        job_generation="stale",
                        changed=False,
                        accepted=False,
                        materialized=False,
                    )
                if existing is not None:
                    previous_snapshot = int(existing["snapshot_generation"])
                    if snapshot < previous_snapshot:
                        if owns_transaction:
                            self._conn.commit()
                        return self._schedule_cursor_from_row(
                            existing, changed=False, accepted=False
                        )
                    if snapshot == previous_snapshot:
                        if str(existing["decision_revision"]) != revision:
                            raise WorkflowJobStoreError(
                                "one snapshot generation produced conflicting decisions"
                            )
                        if owns_transaction:
                            self._conn.commit()
                        return self._schedule_cursor_from_row(existing, changed=False)
                    changed = str(existing["decision_revision"]) != revision
                    existing_generation = str(existing["job_generation"])
                    recurrence_due = False
                    if not changed:
                        rows = self._conn.execute(
                            """
                            SELECT state
                              FROM workflow_jobs
                             WHERE project_id = ? AND task_id = ?
                               AND generation = ?
                               AND scheduling_lane = 'decision'
                               AND workflow_managed = 1
                            """,
                            (project, task, existing_generation),
                        ).fetchall()
                        states = {
                            WorkflowJobState(str(row["state"])) for row in rows
                        }
                        scheduled_deadline = _schedule_reassessment_deadline(
                            existing_generation
                        )
                        # Worker revalidation may supersede a recurring job
                        # before its next deadline without changing the
                        # semantic decision.  That row no longer proves live
                        # restart authority, so rotate immediately unless an
                        # exact event generation still owns execution.  An
                        # explicit cancellation or exhaustion remains a fence,
                        # while normal completion retains deadline semantics.
                        live_replacement = False
                        if protected_job_action is not None:
                            replacements = self._conn.execute(
                                f"""
                                SELECT state, phase, lease_owner, lease_expires_at
                                  FROM workflow_jobs
                                 WHERE project_id = ? AND task_id = ?
                                   AND action = ? AND workflow_managed = 0
                                   AND scheduling_lane IN (
                                       {','.join('?' for _ in protected_lanes)}
                                   )
                                   AND state IN (
                                       {','.join('?' for _ in ACTIVE_JOB_STATES)}
                                   )
                                 ORDER BY enqueue_sequence DESC
                                """,
                                (
                                    project,
                                    task,
                                    protected_job_action,
                                    *protected_lanes,
                                    *(state.value for state in ACTIVE_JOB_STATES),
                                ),
                            ).fetchall()
                            live_replacement = any(
                                _job_row_proves_live_authority(
                                    replacement, now=timestamp
                                )
                                or (
                                    str(replacement["state"])
                                    == WorkflowJobState.RUNNING.value
                                    and str(replacement["phase"])
                                    == "quarantined"
                                )
                                for replacement in replacements
                            )
                        authority_retired = bool(
                            WorkflowJobState.SUPERSEDED in states
                            and not live_replacement
                            and scheduled_deadline is not None
                        )
                        recurrence_due = authority_retired or bool(
                            states == {WorkflowJobState.COMPLETED}
                            and not live_replacement
                            and scheduled_deadline is not None
                            and timestamp >= scheduled_deadline
                        )
                    changed = changed or recurrence_due
                    job_generation_value = (
                        job_generation(deadline)
                        if changed
                        else existing_generation
                    )
                else:
                    changed = True
                    job_generation_value = job_generation(deadline)
                self._conn.execute(
                    """
                    INSERT INTO workflow_schedule_cursors(
                        project_id, task_id, snapshot_generation,
                        decision_revision, job_generation,
                        materialized_job_generation, updated_at
                    ) VALUES (?, ?, ?, ?, ?, NULL, ?)
                    ON CONFLICT(project_id, task_id) DO UPDATE SET
                        snapshot_generation = excluded.snapshot_generation,
                        decision_revision = excluded.decision_revision,
                        job_generation = excluded.job_generation,
                        materialized_job_generation = CASE
                            WHEN workflow_schedule_cursors.job_generation
                                 = excluded.job_generation
                            THEN workflow_schedule_cursors.materialized_job_generation
                            ELSE NULL
                        END,
                        updated_at = excluded.updated_at
                    """,
                    (
                        project,
                        task,
                        snapshot,
                        revision,
                        job_generation_value,
                        timestamp,
                    ),
                )
                row = self._conn.execute(
                    """
                    SELECT * FROM workflow_schedule_cursors
                     WHERE project_id = ? AND task_id = ?
                    """,
                    (project, task),
                ).fetchone()
                assert row is not None
                if owns_transaction:
                    self._conn.commit()
                return self._schedule_cursor_from_row(row, changed=changed)
            except Exception:
                if owns_transaction:
                    self._conn.rollback()
                raise

    @staticmethod
    def _from_row(row: sqlite3.Row) -> WorkflowJob:
        failure_raw = row["failure_category"]
        try:
            failure = WorkflowFailureCategory(str(failure_raw)) if failure_raw else None
            state = WorkflowJobState(str(row["state"]))
        except ValueError as exc:
            raise WorkflowJobCorruptionError(
                "unknown workflow job state/category"
            ) from exc
        spec_payload = _decode_json_object(row["spec_json"], "workflow job spec") or {}
        return WorkflowJob(
            job_id=str(row["job_id"]),
            enqueue_sequence=int(row["enqueue_sequence"]),
            project_id=str(row["project_id"]),
            task_id=str(row["task_id"]),
            generation=str(row["generation"]),
            action=str(row["action"]),
            phase=str(row["phase"]),
            payload=_decode_json_object(row["payload_json"], "payload"),
            scheduling_lane=str(row["scheduling_lane"]),
            idempotency_key=str(row["idempotency_key"]),
            spec_revision=str(row["spec_revision"]),
            expected_evidence_revision=_optional_text(
                row["expected_evidence_revision"]
            ),
            expected_head_sha=_optional_text(row["expected_head_sha"]),
            state=state,
            priority=int(row["priority"]),
            attempts=int(row["attempts"]),
            max_attempts=int(row["max_attempts"]),
            lease_owner=_optional_text(row["lease_owner"]),
            lease_token=_optional_text(row["lease_token"]),
            lease_expires_at=(
                float(row["lease_expires_at"])
                if row["lease_expires_at"] is not None
                else None
            ),
            retry_at=float(row["retry_at"]) if row["retry_at"] is not None else None,
            failure_category=failure,
            last_error=_optional_text(row["last_error"]),
            checkpoint=_decode_json_object(row["checkpoint_json"], "checkpoint"),
            result_transition=_decode_json_object(
                row["result_transition_json"], "result_transition"
            ),
            superseded_by_generation=_optional_text(row["superseded_by_generation"]),
            workflow_managed=bool(row["workflow_managed"]),
            created_at=float(row["created_at"]),
            updated_at=float(row["updated_at"]),
            completed_at=(
                float(row["completed_at"]) if row["completed_at"] is not None else None
            ),
            reason_code=_optional_text(spec_payload.get("reason_code")),
        )

    @staticmethod
    def _event_from_row(row: sqlite3.Row) -> WorkflowJobEvent:
        try:
            state = WorkflowJobState(str(row["state"]))
        except ValueError as exc:
            raise WorkflowJobCorruptionError(
                "unknown workflow job event state"
            ) from exc
        return WorkflowJobEvent(
            sequence=int(row["sequence"]),
            job_id=str(row["job_id"]),
            project_id=str(row["project_id"]),
            task_id=str(row["task_id"]),
            event_type=str(row["event_type"]),
            state=state,
            phase=str(row["phase"]),
            lease_owner=_optional_text(row["lease_owner"]),
            payload=_decode_json_object(row["payload_json"], "event payload"),
            created_at=float(row["created_at"]),
        )

    def _append_event_locked(
        self,
        row: sqlite3.Row,
        event_type: str,
        *,
        payload: Mapping[str, Any] | None = None,
        now: float,
    ) -> None:
        clean_payload = _json_object(payload, "event payload")
        cursor = self._conn.execute(
            """
            INSERT INTO workflow_job_events(
                job_id, project_id, task_id, event_type, state, phase,
                lease_owner, payload_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["job_id"],
                row["project_id"],
                row["task_id"],
                _required_text(event_type, "event_type"),
                row["state"],
                row["phase"],
                row["lease_owner"],
                _canonical_json(clean_payload) if clean_payload is not None else None,
                now,
            ),
        )
        # Advance the persisted high-water mark so archival of the ledger tail
        # can never regress the global sequence the ABA fence relies on.
        self._conn.execute(
            """
            INSERT INTO schema_meta(key, value) VALUES(?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            WHERE CAST(excluded.value AS INTEGER) > CAST(schema_meta.value AS INTEGER)
            """,
            (_JOB_EVENT_HIGHWATER_KEY, str(int(cursor.lastrowid))),
        )

    def _append_rollback_summary_locked(
        self,
        *,
        project_id: str,
        task_id: str,
        job_ids: Sequence[str],
        snapshot: int,
        reason: str | None,
        now: float,
    ) -> None:
        """Record one aggregate ``publication_rollback`` event for a task.

        The original implementation appended one event per superseded job.  A
        publish/rollback livelock on a busy task (thousands of managed jobs)
        could therefore append thousands of rows per rollback and, across
        repeated supersessions, grow ``workflow_job_events`` without bound.

        ``publication_rollback`` events are audit-only (never read back), so a
        single summary row per task+snapshot preserves the forensic trail
        while bounding growth to O(1) per rollback.  The affected job ids are
        retained in the payload for diagnostics.
        """

        if not job_ids:
            return
        payload: dict[str, Any] = {
            "snapshot_generation": snapshot,
            "job_count": len(job_ids),
            "job_ids": [str(job_id) for job_id in job_ids],
        }
        if reason is not None:
            payload["reason"] = reason
        clean_payload = _json_object(payload, "event payload")
        cursor = self._conn.execute(
            """
            INSERT INTO workflow_job_events(
                job_id, project_id, task_id, event_type, state, phase,
                lease_owner, payload_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(job_ids[0]),
                project_id,
                task_id,
                "publication_rollback",
                WorkflowJobState.SUPERSEDED.value,
                "publication_rollback",
                None,
                _canonical_json(clean_payload),
                now,
            ),
        )
        self._conn.execute(
            """
            INSERT INTO schema_meta(key, value) VALUES(?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            WHERE CAST(excluded.value AS INTEGER) > CAST(schema_meta.value AS INTEGER)
            """,
            (_JOB_EVENT_HIGHWATER_KEY, str(int(cursor.lastrowid))),
        )

    def _row_locked(self, job_id: str) -> sqlite3.Row:
        row = self._conn.execute(
            "SELECT * FROM workflow_jobs WHERE job_id = ?", (job_id,)
        ).fetchone()
        if row is None:
            raise KeyError(job_id)
        return row

    def get(self, job_id: str) -> WorkflowJob:
        with self._lock:
            return self._from_row(self._row_locked(_required_text(job_id, "job_id")))

    def events(
        self, job_id: str, *, limit: int = MAX_SCAN_LIMIT
    ) -> tuple[WorkflowJobEvent, ...]:
        bounded = _bounded_limit(limit)
        with self._lock:
            if (
                self._conn.execute(
                    "SELECT 1 FROM workflow_jobs WHERE job_id = ?", (job_id,)
                ).fetchone()
                is None
            ):
                raise KeyError(job_id)
            rows = self._conn.execute(
                """
                SELECT * FROM workflow_job_events
                 WHERE job_id = ? ORDER BY sequence LIMIT ?
                """,
                (job_id, bounded),
            ).fetchall()
        return tuple(self._event_from_row(row) for row in rows)

    def _enqueue_locked(
        self,
        spec: WorkflowJobSpec,
        *,
        now: float,
        workflow_managed: bool = False,
    ) -> tuple[WorkflowJob, bool]:
        if not isinstance(spec, WorkflowJobSpec):
            raise TypeError("spec must be a WorkflowJobSpec")
        existing = self._conn.execute(
            """
            SELECT * FROM workflow_jobs
             WHERE project_id = ? AND idempotency_key = ?
            """,
            (spec.project_id, spec.idempotency_key),
        ).fetchone()
        if existing is not None:
            if str(existing["spec_revision"]) != spec.revision:
                raise WorkflowJobIdempotencyConflict(
                    f"idempotency key {spec.idempotency_key!r} already describes "
                    "different workflow work"
                )
            if workflow_managed and not bool(existing["workflow_managed"]):
                self._conn.execute(
                    "UPDATE workflow_jobs SET workflow_managed = 1 WHERE job_id = ?",
                    (existing["job_id"],),
                )
                existing = self._row_locked(str(existing["job_id"]))
            return self._from_row(existing), False
        job_id = _required_text(self._id_factory(), "generated job_id")
        self._conn.execute(
            """
            INSERT INTO workflow_jobs(
                job_id, project_id, task_id, generation, action, phase,
                idempotency_key, spec_revision, spec_json, payload_json,
                scheduling_lane,
                expected_evidence_revision, expected_head_sha, state,
                priority, attempts, max_attempts, workflow_managed,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?)
            """,
            (
                job_id,
                spec.project_id,
                spec.task_id,
                spec.generation,
                spec.action,
                spec.phase,
                spec.idempotency_key,
                spec.revision,
                _canonical_json(spec.to_dict()),
                _canonical_json(spec.payload) if spec.payload is not None else None,
                spec.scheduling_lane,
                spec.expected_evidence_revision,
                spec.expected_head_sha,
                WorkflowJobState.QUEUED.value,
                spec.priority,
                spec.max_attempts,
                int(workflow_managed),
                now,
                now,
            ),
        )
        row = self._row_locked(job_id)
        self._append_event_locked(row, "enqueued", now=now)
        return self._from_row(row), True

    def enqueue(self, spec: WorkflowJobSpec) -> WorkflowJob:
        """Atomically insert immutable work or replay an identical enqueue."""

        if not isinstance(spec, WorkflowJobSpec):
            raise TypeError("spec must be a WorkflowJobSpec")
        now = float(self._clock())
        with self._authority_mutation_guard():
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                job, _created = self._enqueue_locked(spec, now=now)
                self._conn.commit()
                return job
            except Exception:
                self._conn.rollback()
                raise

    def enqueue_replacing_lane(
        self,
        spec: WorkflowJobSpec,
        *,
        source_generation: int,
        require_source_advance: bool = False,
        retire_managed_exhaustion: bool = False,
        terminal_audit_binding_upgrade_from: str | None = None,
        reason: str = "superseded by a newer workflow generation",
        now: float | None = None,
    ) -> WorkflowEventWrite:
        """Enqueue one event-lane job and supersede only that lane's old work.

        Imperative workflow owners often have several independent lanes for
        one task.  Terminal auditing, for example, may legitimately own a
        ``Done`` job and a ``Merged`` job at the same time.  The broader task
        generation helpers intentionally reconcile the generic decision lane;
        this narrower transaction gives those imperative owners an atomic
        compare/enqueue/supersede boundary without disturbing sibling lanes.

        Replaying a generation which was already terminal or superseded never
        revives it and never displaces the currently active generation.  Only
        the first observation of a genuinely new immutable spec can replace
        active work in the same scheduling lane.
        """

        if not isinstance(spec, WorkflowJobSpec):
            raise TypeError("spec must be a WorkflowJobSpec")
        if isinstance(source_generation, bool) or int(source_generation) < 1:
            raise ValueError("source_generation must be a positive integer")
        if not isinstance(require_source_advance, bool):
            raise TypeError("require_source_advance must be a boolean")
        if not isinstance(retire_managed_exhaustion, bool):
            raise TypeError("retire_managed_exhaustion must be a boolean")
        binding_upgrade_from = _optional_text(
            terminal_audit_binding_upgrade_from
        )
        if binding_upgrade_from is not None and spec.action != "terminal_audit":
            raise ValueError(
                "terminal-audit binding upgrades require a terminal_audit spec"
            )
        incoming_generation = int(source_generation)
        message = _required_text(reason, "reason")
        timestamp = float(self._clock() if now is None else now)
        with self._authority_mutation_guard():
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                ordered = self._conn.execute(
                    """
                    SELECT * FROM workflow_event_ordering
                     WHERE project_id = ? AND task_id = ?
                       AND ordering_namespace = ?
                    """,
                    (spec.project_id, spec.task_id, spec.scheduling_lane),
                ).fetchone()
                if ordered is not None:
                    observed_generation = int(ordered["source_generation"])
                    observed_revision = str(ordered["decision_revision"])
                    if (
                        require_source_advance
                        and incoming_generation <= observed_generation
                    ):
                        existing_activation = self._conn.execute(
                            """
                            SELECT * FROM workflow_jobs
                             WHERE project_id = ? AND idempotency_key = ?
                            """,
                            (spec.project_id, spec.idempotency_key),
                        ).fetchone()
                        if (
                            incoming_generation == observed_generation
                            and existing_activation is not None
                            and str(existing_activation["spec_revision"])
                            == spec.revision
                        ):
                            replay = self._from_row(existing_activation)
                            if retire_managed_exhaustion:
                                self._record_job_retirements_locked(
                                    project_id=spec.project_id,
                                    task_id=spec.task_id,
                                    authority_kind="terminal_audit_handoff",
                                    decision_revision=spec.generation,
                                    snapshot_generation=None,
                                    workflow_managed=True,
                                    now=timestamp,
                                )
                            self._conn.commit()
                            return WorkflowEventWrite(
                                replay,
                                accepted=True,
                                created=False,
                                superseded=0,
                            )
                        self._conn.commit()
                        return WorkflowEventWrite(
                            None,
                            accepted=False,
                            created=False,
                            superseded=0,
                        )
                    if incoming_generation < observed_generation:
                        stale_job, created = self._enqueue_locked(
                            spec,
                            now=timestamp,
                        )
                        if (
                            stale_job.state in ACTIVE_JOB_STATES
                            and stale_job.phase != "quarantined"
                            and stale_job.generation != observed_revision
                        ):
                            self._conn.execute(
                                """
                                UPDATE workflow_jobs
                                   SET state = ?, lease_owner = NULL,
                                       lease_token = NULL,
                                       lease_expires_at = NULL, retry_at = NULL,
                                       superseded_by_generation = ?,
                                       last_error = ?, updated_at = ?,
                                       completed_at = ?
                                 WHERE job_id = ?
                                """,
                                (
                                    WorkflowJobState.SUPERSEDED.value,
                                    observed_revision,
                                    "stale terminal-audit source generation",
                                    timestamp,
                                    timestamp,
                                    stale_job.job_id,
                                ),
                            )
                            row = self._row_locked(stale_job.job_id)
                            self._append_event_locked(
                                row,
                                "superseded",
                                payload={
                                    "replacement_generation": observed_revision,
                                    "reason": (
                                        "stale terminal-audit source generation"
                                    ),
                                },
                                now=timestamp,
                            )
                            stale_job = self._from_row(row)
                        self._conn.commit()
                        return WorkflowEventWrite(
                            stale_job,
                            accepted=False,
                            created=created,
                            superseded=int(
                                stale_job.state is WorkflowJobState.SUPERSEDED
                            ),
                        )
                    if (
                        incoming_generation == observed_generation
                        and observed_revision != spec.generation
                    ):
                        # A deployed pre-binding terminal-audit generation can
                        # already be ordered before tracker metadata acquires
                        # its immutable ref/SHA pair.  Permit exactly that one
                        # monotonic identity upgrade at the same metadata
                        # generation.  The caller must name the observed
                        # legacy generation, and a matching durable job must
                        # prove that the only payload change is acquisition of
                        # the complete binding.  All other same-generation
                        # evidence changes remain conflicts.
                        incoming_payload = dict(spec.payload or {})
                        selected_ref = _optional_text(
                            incoming_payload.pop("selected_ref", None)
                        )
                        selected_sha = _optional_text(
                            incoming_payload.pop("selected_sha", None)
                        )
                        legacy_rows = ()
                        if (
                            binding_upgrade_from == observed_revision
                            and selected_ref is not None
                            and selected_sha is not None
                        ):
                            legacy_rows = self._conn.execute(
                                """
                                SELECT * FROM workflow_jobs
                                 WHERE project_id = ? AND task_id = ?
                                   AND scheduling_lane = ? AND action = ?
                                   AND generation = ?
                                   AND expected_evidence_revision IS ?
                                """,
                                (
                                    spec.project_id,
                                    spec.task_id,
                                    spec.scheduling_lane,
                                    spec.action,
                                    observed_revision,
                                    spec.expected_evidence_revision,
                                ),
                            ).fetchall()
                        valid_binding_upgrade = any(
                            dict(
                                _decode_json_object(
                                    row["payload_json"], "payload"
                                )
                                or {}
                            )
                            == incoming_payload
                            for row in legacy_rows
                        )
                        if not valid_binding_upgrade:
                            raise WorkflowJobStoreError(
                                "one terminal-audit source generation produced "
                                "conflicting evidence"
                            )
                elif require_source_advance and incoming_generation <= 1:
                    # A terminal tombstone without an ordering row can only
                    # be a pre-ordering generation.  Require proof that the
                    # metadata source has advanced before creating a fresh
                    # activation identity for it.
                    self._conn.commit()
                    return WorkflowEventWrite(
                        None,
                        accepted=False,
                        created=False,
                        superseded=0,
                    )

                self._conn.execute(
                    """
                    INSERT INTO workflow_event_ordering(
                        project_id, task_id, ordering_namespace,
                        source_generation, decision_revision, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(
                        project_id, task_id, ordering_namespace
                    ) DO UPDATE SET
                        source_generation = excluded.source_generation,
                        decision_revision = excluded.decision_revision,
                        updated_at = excluded.updated_at
                    """,
                    (
                        spec.project_id,
                        spec.task_id,
                        spec.scheduling_lane,
                        incoming_generation,
                        spec.generation,
                        timestamp,
                    ),
                )
                job, created = self._enqueue_locked(spec, now=timestamp)
                active_rows = self._conn.execute(
                    f"""
                    SELECT * FROM workflow_jobs
                     WHERE project_id = ? AND task_id = ?
                       AND scheduling_lane = ?
                       AND state IN ({','.join('?' for _ in ACTIVE_JOB_STATES)})
                     ORDER BY enqueue_sequence
                    """,
                    (
                        spec.project_id,
                        spec.task_id,
                        spec.scheduling_lane,
                        *(state.value for state in ACTIVE_JOB_STATES),
                    ),
                ).fetchall()
                superseded = 0
                for selected in active_rows:
                    if str(selected["job_id"]) == job.job_id:
                        continue
                    if (
                        str(selected["state"]) == WorkflowJobState.RUNNING.value
                        and str(selected["phase"]) == "quarantined"
                    ):
                        continue
                    self._conn.execute(
                        """
                        UPDATE workflow_jobs
                           SET state = ?, lease_owner = NULL, lease_token = NULL,
                               lease_expires_at = NULL, retry_at = NULL,
                               superseded_by_generation = ?, last_error = ?,
                               updated_at = ?, completed_at = ?
                         WHERE job_id = ?
                        """,
                        (
                            WorkflowJobState.SUPERSEDED.value,
                            spec.generation,
                            message,
                            timestamp,
                            timestamp,
                            selected["job_id"],
                        ),
                    )
                    updated = self._row_locked(str(selected["job_id"]))
                    self._append_event_locked(
                        updated,
                        "superseded",
                        payload={
                            "replacement_generation": spec.generation,
                            "reason": message,
                        },
                        now=timestamp,
                    )
                    superseded += 1
                result = self._from_row(self._row_locked(job.job_id))
                if retire_managed_exhaustion:
                    self._record_job_retirements_locked(
                        project_id=spec.project_id,
                        task_id=spec.task_id,
                        authority_kind="terminal_audit_handoff",
                        decision_revision=spec.generation,
                        snapshot_generation=None,
                        workflow_managed=True,
                        now=timestamp,
                    )
                self._conn.commit()
                return WorkflowEventWrite(
                    result,
                    accepted=True,
                    created=created,
                    superseded=superseded,
                )
            except Exception:
                self._conn.rollback()
                raise

    def rearm_exhausted_job(
        self,
        job_id: str,
        *,
        generation: str,
        phase: str,
        reason: str,
        now: float | None = None,
    ) -> WorkflowJob:
        """Reset one completed/exhausted generation after an authorized proof.

        The caller must prove that the same semantic target/evidence generation
        has fresh execution authority. Superseded and cancelled jobs are
        deliberately not rearmable: those states represent replacement or
        revocation, not an exhausted provider decision.
        """

        identifier = _required_text(job_id, "job_id")
        expected = _required_text(generation, "generation")
        queued_phase = _required_text(phase, "phase")
        message = _required_text(reason, "reason")
        timestamp = float(self._clock() if now is None else now)
        with self._authority_mutation_guard():
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                existing = self._row_locked(identifier)
                if str(existing["generation"]) != expected:
                    raise WorkflowJobStoreError(
                        "workflow job generation does not match"
                    )
                state = WorkflowJobState(str(existing["state"]))
                if state in ACTIVE_JOB_STATES:
                    self._conn.commit()
                    return self._from_row(existing)
                if state not in {
                    WorkflowJobState.COMPLETED,
                    WorkflowJobState.EXHAUSTED,
                }:
                    raise WorkflowJobStoreError(
                        f"workflow job is not rearmable from {state.value}"
                    )
                self._conn.execute(
                    """
                    UPDATE workflow_jobs
                       SET state = ?, phase = ?, attempts = 0,
                           lease_owner = NULL, lease_token = NULL,
                           lease_expires_at = NULL, retry_at = NULL,
                           failure_category = NULL, last_error = NULL,
                           checkpoint_json = NULL, result_transition_json = NULL,
                           superseded_by_generation = NULL, updated_at = ?,
                           completed_at = NULL
                     WHERE job_id = ? AND generation = ?
                    """,
                    (
                        WorkflowJobState.QUEUED.value,
                        queued_phase,
                        timestamp,
                        identifier,
                        expected,
                    ),
                )
                # A fresh authorized activation is new execution authority for
                # this otherwise immutable row.  Any prior handoff tombstone
                # described the terminal activation, not this ABA-safe rearm.
                self._conn.execute(
                    "DELETE FROM workflow_job_retirements WHERE job_id = ?",
                    (identifier,),
                )
                row = self._row_locked(identifier)
                self._append_event_locked(
                    row,
                    "rearmed",
                    payload={"reason": message},
                    now=timestamp,
                )
                self._conn.commit()
                return self._from_row(row)
            except Exception:
                self._conn.rollback()
                raise

    def rearm_terminal_job(
        self,
        job_id: str,
        *,
        generation: str,
        phase: str,
        reason: str,
        now: float | None = None,
    ) -> WorkflowJob:
        """Compatibility wrapper for terminal-audit authorized rearms."""

        return self.rearm_exhausted_job(
            job_id,
            generation=generation,
            phase=phase,
            reason=reason,
            now=now,
        )

    def materialize_event(
        self,
        *,
        project_id: str,
        task_id: str,
        decision_revision: str,
        action: str,
        idempotency_namespace: str,
        scheduling_lane: str | None = None,
        ordering_namespace: str | None = None,
        source_generation: int | None = None,
        source_revision: str | None = None,
        supersede_scheduling_lanes: Sequence[str] = (),
        protected_scheduling_lanes: Sequence[str] = (),
        payload: Mapping[str, Any] | None = None,
        expected_evidence_revision: str | None = None,
        expected_head_sha: str | None = None,
        priority: int = 100,
        max_attempts: int = 5,
        reason: str = "superseded by a newer workflow event",
        now: float | None = None,
    ) -> WorkflowEventWrite:
        """Atomically activate, enqueue, and fence one semantic task event.

        Imperative workflow events cannot safely use the scheduler's three-call
        scan protocol: a process death between cursor activation and enqueue
        would lose the event payload.  This transaction gives repeated equal
        live events one generation/job and gives an intervening different
        event a fresh generation while superseding every older active
        disposition.  When a newer source cut still requires an equal event
        whose exact activation is absent or terminal, it also receives a
        fresh generation: replaying a retired row cannot prove live authority
        or let restart reconstruction converge.
        """

        project = _required_text(project_id, "project_id")
        task = _required_text(task_id, "task_id")
        revision = _required_text(decision_revision, "decision_revision")
        normalized_action = _required_text(action, "action")
        namespace = _required_text(idempotency_namespace, "idempotency_namespace")
        lane = (
            _required_text(scheduling_lane, "scheduling_lane")
            if scheduling_lane is not None
            else f"event:{namespace}"
        )
        message = _required_text(reason, "reason")
        if (ordering_namespace is None) is not (source_generation is None):
            raise ValueError(
                "ordering_namespace and source_generation must be supplied together"
            )
        ordering = (
            _required_text(ordering_namespace, "ordering_namespace")
            if ordering_namespace is not None
            else None
        )
        ordering_revision = (
            _required_text(source_revision, "source_revision")
            if source_revision is not None
            else revision
        )
        supersede_lanes = {
            _required_text(value, "supersede_scheduling_lane")
            for value in supersede_scheduling_lanes
        }
        protected_lanes = {
            _required_text(value, "protected_scheduling_lane")
            for value in protected_scheduling_lanes
        }
        if source_generation is not None and (
            isinstance(source_generation, bool) or int(source_generation) < 1
        ):
            raise ValueError("source_generation must be a positive integer")
        timestamp = float(self._clock() if now is None else now)
        with self._authority_mutation_guard():
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                source_advanced = False
                if ordering is not None:
                    ordered = self._conn.execute(
                        """
                        SELECT * FROM workflow_event_ordering
                         WHERE project_id = ? AND task_id = ?
                           AND ordering_namespace = ?
                        """,
                        (project, task, ordering),
                    ).fetchone()
                    if ordered is not None and int(source_generation) < int(
                        ordered["source_generation"]
                    ):
                        if str(ordered["decision_revision"]) == ordering_revision:
                            cursor = self._conn.execute(
                                """
                                SELECT * FROM workflow_event_cursors
                                 WHERE project_id = ? AND task_id = ?
                                   AND event_namespace = ?
                                   AND event_revision = ?
                                """,
                                (project, task, lane, revision),
                            ).fetchone()
                            if cursor is not None:
                                current_key = (
                                    f"{namespace}:{revision}:"
                                    f"{cursor['event_generation']}"
                                )
                                current = self._conn.execute(
                                    """
                                    SELECT * FROM workflow_jobs
                                     WHERE project_id = ? AND idempotency_key = ?
                                    """,
                                    (project, current_key),
                                ).fetchone()
                                if current is not None:
                                    self._conn.commit()
                                    return WorkflowEventWrite(
                                        self._from_row(current), True, False, 0
                                    )
                        self._conn.commit()
                        return WorkflowEventWrite(None, False, False, 0)
                    if (
                        ordered is not None
                        and int(source_generation)
                        == int(ordered["source_generation"])
                        and str(ordered["decision_revision"]) != ordering_revision
                    ):
                        raise WorkflowJobStoreError(
                            "one event snapshot produced conflicting decisions"
                        )
                    source_advanced = bool(
                        ordered is not None
                        and int(source_generation)
                        > int(ordered["source_generation"])
                    )
                    self._conn.execute(
                        """
                        INSERT INTO workflow_event_ordering(
                            project_id, task_id, ordering_namespace,
                            source_generation, decision_revision, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        ON CONFLICT(
                            project_id, task_id, ordering_namespace
                        ) DO UPDATE SET
                            source_generation = excluded.source_generation,
                            decision_revision = excluded.decision_revision,
                            updated_at = excluded.updated_at
                        """,
                        (
                            project,
                            task,
                            ordering,
                            int(source_generation),
                            ordering_revision,
                            timestamp,
                        ),
                    )
                if protected_lanes:
                    protected = self._conn.execute(
                        f"""
                        SELECT * FROM workflow_jobs
                         WHERE project_id = ? AND task_id = ?
                           AND scheduling_lane IN (
                               {','.join('?' for _ in protected_lanes)}
                           )
                           AND state IN (
                               {','.join('?' for _ in ACTIVE_JOB_STATES)}
                           )
                         ORDER BY enqueue_sequence DESC LIMIT 1
                        """,
                        (
                            project,
                            task,
                            *sorted(protected_lanes),
                            *(state.value for state in ACTIVE_JOB_STATES),
                        ),
                    ).fetchone()
                    if protected is not None:
                        protected_payload = _decode_json_object(
                            protected["payload_json"], "payload"
                        )
                        same_event = (
                            str(protected["action"]) == normalized_action
                            and _thaw_json(protected_payload)
                            == _thaw_json(payload)
                            and _optional_text(protected["expected_head_sha"])
                            == _optional_text(expected_head_sha)
                        )
                        self._conn.commit()
                        return WorkflowEventWrite(
                            self._from_row(protected) if same_event else None,
                            True,
                            False,
                            0,
                        )
                sequence = self._next_counter_locked("workflow_event_sequence")
                existing = self._conn.execute(
                    """
                    SELECT * FROM workflow_event_cursors
                     WHERE project_id = ? AND task_id = ? AND event_namespace = ?
                    """,
                    (project, task, lane),
                ).fetchone()
                changed = (
                    existing is None
                    or str(existing["event_revision"]) != revision
                )
                if not changed and source_advanced:
                    existing_generation = str(existing["event_generation"])
                    existing_key = (
                        f"{namespace}:{revision}:{existing_generation}"
                    )
                    current = self._conn.execute(
                        """
                        SELECT state FROM workflow_jobs
                         WHERE project_id = ? AND idempotency_key = ?
                        """,
                        (project, existing_key),
                    ).fetchone()
                    changed = bool(
                        current is None
                        or WorkflowJobState(str(current["state"]))
                        not in ACTIVE_JOB_STATES
                    )
                generation = (
                    f"{revision}:{sequence}"
                    if changed
                    else str(existing["event_generation"])
                )
                self._conn.execute(
                    """
                    INSERT INTO workflow_event_cursors(
                        project_id, task_id, event_namespace, event_revision,
                        event_generation, event_sequence, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(project_id, task_id, event_namespace) DO UPDATE SET
                        event_revision = excluded.event_revision,
                        event_generation = excluded.event_generation,
                        event_sequence = excluded.event_sequence,
                        updated_at = excluded.updated_at
                    """,
                    (
                        project,
                        task,
                        lane,
                        revision,
                        generation,
                        sequence,
                        timestamp,
                    ),
                )
                key = f"{namespace}:{revision}:{generation}"
                spec = WorkflowJobSpec(
                    project_id=project,
                    task_id=task,
                    generation=generation,
                    action=normalized_action,
                    idempotency_key=key,
                    payload=payload,
                    scheduling_lane=lane,
                    expected_evidence_revision=expected_evidence_revision,
                    expected_head_sha=expected_head_sha,
                    priority=priority,
                    max_attempts=max_attempts,
                )
                job, created = self._enqueue_locked(spec, now=timestamp)
                selected_lanes = {spec.scheduling_lane, "decision", *supersede_lanes}
                active_rows = self._conn.execute(
                    f"""
                    SELECT * FROM workflow_jobs
                     WHERE project_id = ? AND task_id = ?
                       AND scheduling_lane IN (
                           {','.join('?' for _ in selected_lanes)}
                       )
                       AND state IN ({','.join('?' for _ in ACTIVE_JOB_STATES)})
                     ORDER BY enqueue_sequence
                    """,
                    (
                        project,
                        task,
                        *sorted(selected_lanes),
                        *(state.value for state in ACTIVE_JOB_STATES),
                    ),
                ).fetchall()
                superseded = 0
                for selected in active_rows:
                    if (
                        str(selected["generation"]) == generation
                        and str(selected["idempotency_key"]) == key
                    ):
                        continue
                    if (
                        str(selected["state"]) == WorkflowJobState.RUNNING.value
                        and str(selected["phase"]) == "quarantined"
                    ):
                        continue
                    self._conn.execute(
                        """
                        UPDATE workflow_jobs
                           SET state = ?, lease_owner = NULL, lease_token = NULL,
                               lease_expires_at = NULL, retry_at = NULL,
                               superseded_by_generation = ?, last_error = ?,
                               updated_at = ?, completed_at = ?
                         WHERE job_id = ?
                        """,
                        (
                            WorkflowJobState.SUPERSEDED.value,
                            generation,
                            message,
                            timestamp,
                            timestamp,
                            selected["job_id"],
                        ),
                    )
                    updated = self._row_locked(str(selected["job_id"]))
                    self._append_event_locked(
                        updated,
                        "superseded",
                        payload={
                            "replacement_generation": generation,
                            "reason": message,
                        },
                        now=timestamp,
                    )
                    superseded += 1
                result = self._from_row(self._row_locked(job.job_id))
                if supersede_lanes:
                    self._record_event_handoff_retirements_locked(
                        project_id=project,
                        task_id=task,
                        authority_generation=generation,
                        authority_scheduling_lane=lane,
                        authority_enqueue_sequence=job.enqueue_sequence,
                        retired_scheduling_lanes=tuple(supersede_lanes),
                        now=timestamp,
                    )
                self._conn.commit()
                return WorkflowEventWrite(result, True, created, superseded)
            except Exception:
                self._conn.rollback()
                raise

    def retire_event_lane(
        self,
        *,
        project_id: str,
        task_id: str,
        scheduling_lane: str,
        ordering_namespace: str,
        source_generation: int,
        decision_revision: str,
        reason: str = "retired by a newer workflow decision",
        now: float | None = None,
    ) -> WorkflowEventWrite:
        """Atomically order a no-job decision and retire its fact-derived lane."""

        project = _required_text(project_id, "project_id")
        task = _required_text(task_id, "task_id")
        lane = _required_text(scheduling_lane, "scheduling_lane")
        ordering = _required_text(ordering_namespace, "ordering_namespace")
        revision = _required_text(decision_revision, "decision_revision")
        message = _required_text(reason, "reason")
        if isinstance(source_generation, bool) or int(source_generation) < 1:
            raise ValueError("source_generation must be a positive integer")
        generation = int(source_generation)
        timestamp = float(self._clock() if now is None else now)
        replacement = f"decision:{generation}:{revision}"
        with self._authority_mutation_guard():
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                ordered = self._conn.execute(
                    """
                    SELECT * FROM workflow_event_ordering
                     WHERE project_id = ? AND task_id = ?
                       AND ordering_namespace = ?
                    """,
                    (project, task, ordering),
                ).fetchone()
                if ordered is not None and generation < int(
                    ordered["source_generation"]
                ):
                    self._conn.commit()
                    return WorkflowEventWrite(None, False, False, 0)
                if (
                    ordered is not None
                    and generation == int(ordered["source_generation"])
                    and str(ordered["decision_revision"]) != revision
                ):
                    raise WorkflowJobStoreError(
                        "one event snapshot produced conflicting decisions"
                    )
                self._conn.execute(
                    """
                    INSERT INTO workflow_event_ordering(
                        project_id, task_id, ordering_namespace,
                        source_generation, decision_revision, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(
                        project_id, task_id, ordering_namespace
                    ) DO UPDATE SET
                        source_generation = excluded.source_generation,
                        decision_revision = excluded.decision_revision,
                        updated_at = excluded.updated_at
                    """,
                    (project, task, ordering, generation, revision, timestamp),
                )
                active_rows = self._conn.execute(
                    """
                    SELECT * FROM workflow_jobs
                     WHERE project_id = ? AND task_id = ?
                       AND scheduling_lane IN (?, 'decision')
                       AND state IN (?, ?)
                     ORDER BY enqueue_sequence
                    """,
                    (
                        project,
                        task,
                        lane,
                        WorkflowJobState.QUEUED.value,
                        WorkflowJobState.RETRY_WAIT.value,
                    ),
                ).fetchall()
                retired_rows = []
                for selected in active_rows:
                    if str(selected["state"]) == WorkflowJobState.RETRY_WAIT.value:
                        checkpoint = _decode_json_object(
                            selected["checkpoint_json"], "checkpoint"
                        )
                        if isinstance(checkpoint, Mapping) and isinstance(
                            checkpoint.get("verification"), Mapping
                        ):
                            continue
                    self._conn.execute(
                        """
                        UPDATE workflow_jobs
                           SET state = ?, lease_owner = NULL, lease_token = NULL,
                               lease_expires_at = NULL, retry_at = NULL,
                               superseded_by_generation = ?, last_error = ?,
                               updated_at = ?, completed_at = ?
                         WHERE job_id = ?
                        """,
                        (
                            WorkflowJobState.SUPERSEDED.value,
                            replacement,
                            message,
                            timestamp,
                            timestamp,
                            selected["job_id"],
                        ),
                    )
                    updated = self._row_locked(str(selected["job_id"]))
                    self._append_event_locked(
                        updated,
                        "superseded",
                        payload={
                            "replacement_generation": replacement,
                            "reason": message,
                        },
                        now=timestamp,
                    )
                    retired_rows.append(selected)
                self._conn.commit()
                return WorkflowEventWrite(
                    None, True, False, len(retired_rows)
                )
            except Exception:
                self._conn.rollback()
                raise

    def activate_event_order(
        self,
        *,
        project_id: str,
        task_id: str,
        ordering_namespace: str,
        source_generation: int,
        decision_revision: str,
        now: float | None = None,
    ) -> bool:
        """Fence slow event-producing decisions before they materialize jobs."""

        project = _required_text(project_id, "project_id")
        task = _required_text(task_id, "task_id")
        namespace = _required_text(ordering_namespace, "ordering_namespace")
        revision = _required_text(decision_revision, "decision_revision")
        if isinstance(source_generation, bool) or int(source_generation) < 1:
            raise ValueError("source_generation must be a positive integer")
        generation = int(source_generation)
        timestamp = float(self._clock() if now is None else now)
        with self._authority_mutation_guard():
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                existing = self._conn.execute(
                    """
                    SELECT * FROM workflow_event_ordering
                     WHERE project_id = ? AND task_id = ?
                       AND ordering_namespace = ?
                    """,
                    (project, task, namespace),
                ).fetchone()
                if existing is not None:
                    observed_generation = int(existing["source_generation"])
                    if generation < observed_generation:
                        self._conn.commit()
                        return False
                    if generation == observed_generation:
                        if str(existing["decision_revision"]) != revision:
                            raise WorkflowJobStoreError(
                                "one event snapshot produced conflicting decisions"
                            )
                        self._conn.commit()
                        return True
                self._conn.execute(
                    """
                    INSERT INTO workflow_event_ordering(
                        project_id, task_id, ordering_namespace,
                        source_generation, decision_revision, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(project_id, task_id, ordering_namespace) DO UPDATE SET
                        source_generation = excluded.source_generation,
                        decision_revision = excluded.decision_revision,
                        updated_at = excluded.updated_at
                    """,
                    (project, task, namespace, generation, revision, timestamp),
                )
                self._conn.commit()
                return True
            except Exception:
                self._conn.rollback()
                raise

    def _job_has_durable_retirement_locked(self, job_id: str) -> bool:
        """Return whether one row already has immutable published authority."""

        return self._conn.execute(
            f"""
            SELECT 1
              FROM workflow_job_retirements retirement
              JOIN workflow_jobs job ON job.job_id = retirement.job_id
             WHERE retirement.job_id = ?
               AND retirement.project_id = job.project_id
               AND retirement.task_id = job.task_id
               AND {_DURABLE_RETIREMENT_PROOF_PREDICATE}
             LIMIT 1
            """,
            (_required_text(job_id, "job_id"),),
        ).fetchone() is not None

    def _record_job_retirements_locked(
        self,
        *,
        project_id: str,
        task_id: str,
        authority_kind: str,
        decision_revision: str,
        snapshot_generation: int | None,
        workflow_managed: bool | None = None,
        excluded_job_ids: Sequence[str] = (),
        now: float,
    ) -> int:
        """Bind every existing superseded job to exact replacement authority.

        Recording the proof before a still-running job reaches ``exhausted``
        closes the completion/publication race. Per-job identity keeps work
        created or rearmed after this authority cut actionable.
        """

        project = _required_text(project_id, "project_id")
        task = _required_text(task_id, "task_id")
        revision = _required_text(decision_revision, "decision_revision")
        if authority_kind not in _AUTHORITY_RETIREMENT_KINDS:
            raise ValueError("authority_kind is not supported")
        cut_job_generation: str | None = None
        if authority_kind == "terminal_audit_handoff":
            if snapshot_generation is not None:
                raise ValueError(
                    "terminal_audit_handoff requires immediate authority"
                )
            if workflow_managed is not True:
                raise ValueError(
                    "terminal_audit_handoff must retire managed authority"
                )
            handoff = self._conn.execute(
                """
                SELECT 1 FROM workflow_jobs
                 WHERE project_id = ? AND task_id = ?
                   AND workflow_managed = 0
                   AND action = 'terminal_audit'
                   AND scheduling_lane LIKE 'terminal-audit:%'
                   AND generation = ?
                 LIMIT 1
                """,
                (project, task, revision),
            ).fetchone()
            if handoff is None:
                raise WorkflowJobStoreError(
                    "terminal-audit retirement lost its exact handoff job"
                )
        else:
            if (
                snapshot_generation is None
                or isinstance(snapshot_generation, bool)
                or int(snapshot_generation) < 1
            ):
                raise ValueError(
                    f"{authority_kind} requires a positive snapshot generation"
                )
            snapshot_generation = int(snapshot_generation)
            if authority_kind in {"managed_decision", "managed_zero_job"}:
                if workflow_managed is not True:
                    raise ValueError(
                        "managed retirement proof must select managed jobs"
                    )
                cursor = self._conn.execute(
                    """
                    SELECT job_generation, materialized_job_generation
                      FROM workflow_schedule_cursors
                     WHERE project_id = ? AND task_id = ?
                       AND snapshot_generation = ?
                       AND decision_revision = ?
                    """,
                    (project, task, snapshot_generation, revision),
                ).fetchone()
                if (
                    cursor is None
                    or str(cursor["materialized_job_generation"] or "")
                    != str(cursor["job_generation"])
                ):
                    raise WorkflowJobStoreError(
                        "managed retirement lost its exact materialized cursor"
                    )
                cut_job_generation = str(cursor["job_generation"])
                replacement = self._conn.execute(
                    """
                    SELECT 1 FROM workflow_jobs
                     WHERE project_id = ? AND task_id = ?
                       AND workflow_managed = 1 AND generation = ?
                     LIMIT 1
                    """,
                    (project, task, str(cursor["job_generation"])),
                ).fetchone()
                if (authority_kind == "managed_decision") != (
                    replacement is not None
                ):
                    raise WorkflowJobStoreError(
                        "managed retirement kind does not match its exact job cut"
                    )
            elif revision not in _LIFECYCLE_FINAL_AUTHORITY_REVISIONS:
                raise ValueError(
                    "lifecycle_final requires an exact final-status revision"
                )
            elif self._conn.execute(
                """
                SELECT 1 FROM workflow_snapshot_membership
                 WHERE project_id = ? AND task_id = ?
                 LIMIT 1
                """,
                (project, task),
            ).fetchone() is not None:
                raise WorkflowJobStoreError(
                    "lifecycle-final authority conflicts with active membership"
                )
        clauses = [
            "project_id = ?",
            "task_id = ?",
        ]
        values: list[object] = [
            project,
            task,
        ]
        if workflow_managed is not None:
            clauses.append("workflow_managed = ?")
            values.append(int(workflow_managed))
        excluded = tuple(
            _required_text(job_id, "excluded job_id") for job_id in excluded_job_ids
        )
        if excluded:
            clauses.append(
                f"job_id NOT IN ({','.join('?' for _ in excluded)})"
            )
            values.extend(excluded)
        rows = self._conn.execute(
            f"""
            SELECT job_id FROM workflow_jobs
             WHERE {' AND '.join(clauses)}
             ORDER BY enqueue_sequence
            """,
            values,
        ).fetchall()
        rows = [
            row
            for row in rows
            if not self._job_has_durable_retirement_locked(str(row["job_id"]))
        ]
        if not rows:
            return 0
        if snapshot_generation is not None:
            self._conn.execute(
                """
                INSERT OR IGNORE INTO workflow_retirement_authority_cuts(
                    snapshot_generation, project_id, task_id,
                    authority_kind, decision_revision, job_generation,
                    recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot_generation,
                    project,
                    task,
                    authority_kind,
                    revision,
                    cut_job_generation,
                    now,
                ),
            )
            authority_cut = self._conn.execute(
                """
                SELECT authority_kind, decision_revision, job_generation
                  FROM workflow_retirement_authority_cuts
                 WHERE snapshot_generation = ?
                   AND project_id = ? AND task_id = ?
                """,
                (snapshot_generation, project, task),
            ).fetchone()
            expected_cut = (
                authority_kind,
                revision,
                cut_job_generation,
            )
            observed_cut = (
                (
                    str(authority_cut["authority_kind"]),
                    str(authority_cut["decision_revision"]),
                    _optional_text(authority_cut["job_generation"]),
                )
                if authority_cut is not None
                else None
            )
            if observed_cut != expected_cut:
                raise WorkflowJobStoreError(
                    "snapshot contains conflicting retirement authority cuts"
                )
        for row in rows:
            self._conn.execute(
                """
                INSERT INTO workflow_job_retirements(
                    job_id, project_id, task_id, authority_kind,
                    decision_revision, snapshot_generation, retired_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    project_id = excluded.project_id,
                    task_id = excluded.task_id,
                    authority_kind = excluded.authority_kind,
                    decision_revision = excluded.decision_revision,
                    snapshot_generation = excluded.snapshot_generation,
                    retired_at = excluded.retired_at
                """,
                (
                    str(row["job_id"]),
                    project,
                    task,
                    authority_kind,
                    revision,
                    snapshot_generation,
                    now,
                ),
            )
        return len(rows)

    def _record_event_handoff_retirements_locked(
        self,
        *,
        project_id: str,
        task_id: str,
        authority_generation: str,
        authority_scheduling_lane: str,
        authority_enqueue_sequence: int,
        retired_scheduling_lanes: Sequence[str],
        now: float,
    ) -> int:
        """Bind named event lanes to one exact current event successor."""

        project = _required_text(project_id, "project_id")
        task = _required_text(task_id, "task_id")
        generation = _required_text(authority_generation, "authority_generation")
        authority_lane = _required_text(
            authority_scheduling_lane, "authority_scheduling_lane"
        )
        if (
            isinstance(authority_enqueue_sequence, bool)
            or int(authority_enqueue_sequence) < 1
        ):
            raise ValueError("authority_enqueue_sequence must be positive")
        authority_sequence = int(authority_enqueue_sequence)
        retired_lanes = tuple(
            sorted(
                {
                    _required_text(lane, "retired_scheduling_lane")
                    for lane in retired_scheduling_lanes
                }
            )
        )
        if not retired_lanes:
            raise ValueError("retired_scheduling_lanes cannot be empty")
        authority = self._conn.execute(
            """
            SELECT job.enqueue_sequence
              FROM workflow_event_cursors cursor
              JOIN workflow_jobs job
                ON job.project_id = cursor.project_id
               AND job.task_id = cursor.task_id
               AND job.scheduling_lane = cursor.event_namespace
               AND job.generation = cursor.event_generation
             WHERE cursor.project_id = ? AND cursor.task_id = ?
               AND cursor.event_namespace = ?
               AND cursor.event_generation = ?
               AND job.workflow_managed = 0
               AND job.state NOT IN (?, ?)
             LIMIT 1
            """,
            (
                project,
                task,
                authority_lane,
                generation,
                WorkflowJobState.SUPERSEDED.value,
                WorkflowJobState.CANCELLED.value,
            ),
        ).fetchone()
        if authority is None:
            raise WorkflowJobStoreError(
                "event handoff retirement lost its exact successor job"
            )
        rows = self._conn.execute(
            f"""
            SELECT job_id
              FROM workflow_jobs
             WHERE project_id = ? AND task_id = ?
               AND workflow_managed = 0
                AND scheduling_lane IN (
                   {','.join('?' for _ in retired_lanes)}
               )
               AND enqueue_sequence < ?
               AND NOT (
                   scheduling_lane = ? AND generation = ?
               )
             ORDER BY enqueue_sequence
            """,
            (
                project,
                task,
                *retired_lanes,
                authority_sequence,
                authority_lane,
                generation,
            ),
        ).fetchall()
        rows = [
            row
            for row in rows
            if not self._job_has_durable_retirement_locked(str(row["job_id"]))
        ]
        for row in rows:
            self._conn.execute(
                """
                INSERT INTO workflow_job_retirements(
                    job_id, project_id, task_id, authority_kind,
                    decision_revision, snapshot_generation, retired_at
                ) VALUES (?, ?, ?, 'event_handoff', ?, NULL, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    project_id = excluded.project_id,
                    task_id = excluded.task_id,
                    authority_kind = excluded.authority_kind,
                    decision_revision = excluded.decision_revision,
                    snapshot_generation = NULL,
                    retired_at = excluded.retired_at
                """,
                (str(row["job_id"]), project, task, generation, now),
            )
        return len(rows)

    def record_lifecycle_final_authority(
        self,
        *,
        project_id: str,
        task_id: str,
        status: str,
        snapshot_generation: int,
        now: float | None = None,
    ) -> int:
        """Stage exact retirement proof for one lifecycle-final observation."""

        project = _required_text(project_id, "project_id")
        task = _required_text(task_id, "task_id")
        final_status = _required_text(status, "status")
        final_revision = f"lifecycle-final:{final_status}"
        if final_revision not in _LIFECYCLE_FINAL_AUTHORITY_REVISIONS:
            raise ValueError("status must be lifecycle-final (Merged or Archived)")
        if isinstance(snapshot_generation, bool) or int(snapshot_generation) < 1:
            raise ValueError("snapshot_generation must be a positive integer")
        snapshot = int(snapshot_generation)
        timestamp = float(self._clock() if now is None else now)
        with self._authority_mutation_guard():
            owns_transaction = not self._conn.in_transaction
            if owns_transaction:
                self._conn.execute("BEGIN IMMEDIATE")
            try:
                if not self._snapshot_generation_is_current_locked(snapshot):
                    if owns_transaction:
                        self._conn.commit()
                    return 0
                count = self._record_job_retirements_locked(
                    project_id=project,
                    task_id=task,
                    authority_kind="lifecycle_final",
                    decision_revision=final_revision,
                    snapshot_generation=snapshot,
                    now=timestamp,
                )
                if owns_transaction:
                    self._conn.commit()
                return count
            except Exception:
                if owns_transaction:
                    self._conn.rollback()
                raise

    def archive_lifecycle_final_events(
        self,
        *,
        max_tasks: int = 25,
        max_events: int = 5000,
        now: float | None = None,
    ) -> dict[str, int]:
        """Relocate job events for lifecycle-final Archived tasks into cold storage.

        Events for tasks whose durable retirement proof is
        ``lifecycle-final:Archived`` are copied verbatim (preserving their
        original ``sequence``) into ``workflow_job_events_archive`` and removed
        from the hot ``workflow_job_events`` table.  The persisted sequence
        high-water mark guarantees the snapshot-authority ABA fence never
        observes a lower maximum after the tail is relocated.

        The scan is bounded by ``max_tasks`` (distinct Archived tasks per call)
        and ``max_events`` (rows relocated per call) so the maintenance loop
        makes steady, restart-safe progress against a large backlog.  Returns a
        summary with ``tasks`` and ``events`` counts actually archived.
        """

        task_budget = max(1, int(max_tasks))
        event_budget = max(1, int(max_events))
        timestamp = float(self._clock() if now is None else now)
        archived_tasks = 0
        archived_events = 0
        with self._authority_mutation_guard():
            owns_transaction = not self._conn.in_transaction
            if owns_transaction:
                self._conn.execute("BEGIN IMMEDIATE")
            try:
                candidates = self._conn.execute(
                    """
                    SELECT DISTINCT project_id, task_id
                      FROM workflow_job_retirements
                     WHERE authority_kind = 'lifecycle_final'
                       AND decision_revision = ?
                     ORDER BY project_id, task_id
                     LIMIT ?
                    """,
                    (_LIFECYCLE_FINAL_ARCHIVED_REVISION, task_budget),
                ).fetchall()

                self._conn.execute(
                    "UPDATE workflow_job_events_delete_guard "
                    "SET allowed = 1 WHERE id = 1"
                )
                try:
                    for candidate in candidates:
                        if archived_events >= event_budget:
                            break
                        project = str(candidate["project_id"])
                        task = str(candidate["task_id"])
                        remaining = event_budget - archived_events
                        rows = self._conn.execute(
                            """
                            SELECT sequence, job_id, project_id, task_id,
                                   event_type, state, phase, lease_owner,
                                   payload_json, created_at
                              FROM workflow_job_events
                             WHERE project_id = ? AND task_id = ?
                             ORDER BY sequence
                             LIMIT ?
                            """,
                            (project, task, remaining),
                        ).fetchall()
                        if not rows:
                            continue
                        self._conn.executemany(
                            """
                            INSERT OR IGNORE INTO workflow_job_events_archive(
                                sequence, job_id, project_id, task_id,
                                event_type, state, phase, lease_owner,
                                payload_json, created_at, archived_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            [
                                (
                                    int(r["sequence"]),
                                    r["job_id"],
                                    r["project_id"],
                                    r["task_id"],
                                    r["event_type"],
                                    r["state"],
                                    r["phase"],
                                    r["lease_owner"],
                                    r["payload_json"],
                                    float(r["created_at"]),
                                    timestamp,
                                )
                                for r in rows
                            ],
                        )
                        sequences = [int(r["sequence"]) for r in rows]
                        # Range delete scoped to this task avoids SQLite's
                        # bound-variable limit on a large IN-list.  Every one of
                        # this task's events in [lo, hi] was just archived above
                        # (selection was project+task ORDER BY sequence LIMIT).
                        lo = min(sequences)
                        hi = max(sequences)
                        self._conn.execute(
                            "DELETE FROM workflow_job_events "
                            "WHERE project_id = ? AND task_id = ? "
                            "AND sequence >= ? AND sequence <= ?",
                            (project, task, lo, hi),
                        )
                        archived_events += len(sequences)
                        archived_tasks += 1
                finally:
                    self._conn.execute(
                        "UPDATE workflow_job_events_delete_guard "
                        "SET allowed = 0 WHERE id = 1"
                    )
                if owns_transaction:
                    self._conn.commit()
            except Exception:
                if owns_transaction:
                    self._conn.rollback()
                raise
        return {"tasks": archived_tasks, "events": archived_events}

    def archive_rollback_events(
        self,
        *,
        max_events: int = 20000,
        keep_recent: int = 1000,
        now: float | None = None,
    ) -> dict[str, int]:
        """Relocate old ``publication_rollback`` audit events into cold storage.

        ``publication_rollback`` events are audit-only: no code path reads them
        back (the snapshot-authority ABA fence keys on ``rearmed`` events and
        the global sequence high-water mark, not on rollback rows).  A historic
        publish/rollback livelock can therefore leave the hot ledger dominated
        by millions of rollback rows for otherwise-live tasks, which the
        Archived-only maintenance path cannot reclaim.

        This relocates the oldest rollback rows (by ``sequence``) into
        ``workflow_job_events_archive`` and deletes them from the hot table,
        retaining the newest ``keep_recent`` rollback rows for forensics.  The
        scan is bounded by ``max_events`` per call so the maintenance loop makes
        steady, restart-safe progress.  The persisted high-water mark keeps the
        ABA fence monotonic after the relocation.  Returns the number of rows
        relocated as ``{"events": n}``.
        """

        event_budget = max(1, int(max_events))
        retained = max(0, int(keep_recent))
        timestamp = float(self._clock() if now is None else now)
        archived_events = 0
        with self._authority_mutation_guard():
            owns_transaction = not self._conn.in_transaction
            if owns_transaction:
                self._conn.execute("BEGIN IMMEDIATE")
            try:
                # Determine the cutoff so the newest ``retained`` rollback rows
                # stay in the hot table.  Only rows at or below the cutoff are
                # eligible for relocation.
                cutoff_row = self._conn.execute(
                    """
                    SELECT MIN(sequence) AS cutoff FROM (
                        SELECT sequence FROM workflow_job_events
                         WHERE event_type = 'publication_rollback'
                         ORDER BY sequence DESC
                         LIMIT ?
                    )
                    """,
                    (retained,),
                ).fetchone()
                cutoff = cutoff_row["cutoff"] if cutoff_row else None
                if retained == 0:
                    # No retention window: everything is eligible.
                    where_seq = ""
                    seq_params: tuple[Any, ...] = ()
                elif cutoff is None:
                    # Fewer rollback rows than the retention window: nothing to do.
                    if owns_transaction:
                        self._conn.commit()
                    return {"events": 0}
                else:
                    where_seq = "AND sequence < ?"
                    seq_params = (int(cutoff),)

                rows = self._conn.execute(
                    f"""
                    SELECT sequence, job_id, project_id, task_id,
                           event_type, state, phase, lease_owner,
                           payload_json, created_at
                      FROM workflow_job_events
                     WHERE event_type = 'publication_rollback' {where_seq}
                     ORDER BY sequence
                     LIMIT ?
                    """,
                    (*seq_params, event_budget),
                ).fetchall()
                if not rows:
                    if owns_transaction:
                        self._conn.commit()
                    return {"events": 0}

                self._conn.execute(
                    "UPDATE workflow_job_events_delete_guard "
                    "SET allowed = 1 WHERE id = 1"
                )
                try:
                    self._conn.executemany(
                        """
                        INSERT OR IGNORE INTO workflow_job_events_archive(
                            sequence, job_id, project_id, task_id,
                            event_type, state, phase, lease_owner,
                            payload_json, created_at, archived_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        [
                            (
                                int(r["sequence"]),
                                r["job_id"],
                                r["project_id"],
                                r["task_id"],
                                r["event_type"],
                                r["state"],
                                r["phase"],
                                r["lease_owner"],
                                r["payload_json"],
                                float(r["created_at"]),
                                timestamp,
                            )
                            for r in rows
                        ],
                    )
                    sequences = [int(r["sequence"]) for r in rows]
                    # Delete by bounded sequence range rather than an IN-list:
                    # the selected rollback rows are contiguous by ``sequence``
                    # (ORDER BY sequence LIMIT), so a range predicate avoids
                    # SQLite's bound-variable limit ("too many SQL variables")
                    # that a large IN-list would hit.  The event_type filter
                    # keeps any interleaved non-rollback rows untouched, and
                    # every rollback row in [lo, hi] was just archived above.
                    lo = min(sequences)
                    hi = max(sequences)
                    self._conn.execute(
                        "DELETE FROM workflow_job_events "
                        "WHERE event_type = 'publication_rollback' "
                        "AND sequence >= ? AND sequence <= ?",
                        (lo, hi),
                    )
                    archived_events += len(sequences)
                finally:
                    self._conn.execute(
                        "UPDATE workflow_job_events_delete_guard "
                        "SET allowed = 0 WHERE id = 1"
                    )
                if owns_transaction:
                    self._conn.commit()
            except Exception:
                if owns_transaction:
                    self._conn.rollback()
                raise
        return {"events": archived_events}

    def prune_archived_events(
        self,
        *,
        older_than: float,
        max_events: int = 50000,
    ) -> int:
        """Delete a bounded batch of expired cold audit events.

        The archive is operational history rather than scheduling authority.
        Deletion is intentionally restricted to the cold table and bounded by
        both age and row count; the persisted event high-water mark keeps ABA
        protection monotonic after old rows are removed.
        """

        cutoff = float(older_than)
        event_budget = max(1, int(max_events))
        with self._authority_mutation_guard():
            owns_transaction = not self._conn.in_transaction
            if owns_transaction:
                self._conn.execute("BEGIN IMMEDIATE")
            try:
                rows = self._conn.execute(
                    """
                    SELECT sequence
                      FROM workflow_job_events_archive
                     WHERE archived_at < ?
                     ORDER BY sequence
                     LIMIT ?
                    """,
                    (cutoff, event_budget),
                ).fetchall()
                if not rows:
                    if owns_transaction:
                        self._conn.commit()
                    return 0
                lo = min(int(row["sequence"]) for row in rows)
                hi = max(int(row["sequence"]) for row in rows)
                cursor = self._conn.execute(
                    """
                    DELETE FROM workflow_job_events_archive
                     WHERE archived_at < ?
                       AND sequence >= ? AND sequence <= ?
                    """,
                    (cutoff, lo, hi),
                )
                deleted = int(cursor.rowcount)
                if owns_transaction:
                    self._conn.commit()
                return deleted
            except Exception:
                if owns_transaction:
                    self._conn.rollback()
                raise

    def vacuum(self) -> None:
        """Reclaim free pages after large archival deletes.

        Runs outside any transaction under the authority guard.  SQLite does
        not shrink the database file on DELETE alone; a periodic VACUUM returns
        the freed space to the filesystem once archival has drained a large
        backlog.
        """

        with self._authority_mutation_guard():
            if self._conn.in_transaction:
                self._conn.commit()
            self._conn.execute("VACUUM")

    def reconcile_schedule(
        self,
        *,
        project_id: str,
        task_id: str,
        snapshot_generation: int,
        job_generation: str,
        specs: Sequence[WorkflowJobSpec],
        record_authority_cut: bool = False,
        authority_kind: str | None = None,
        reason: str = "superseded by a newer workflow decision",
        now: float | None = None,
    ) -> WorkflowScheduleWrite:
        """Materialize one cursor and fence every non-current task job atomically."""

        project = _required_text(project_id, "project_id")
        task = _required_text(task_id, "task_id")
        generation = _required_text(job_generation, "job_generation")
        message = _required_text(reason, "reason")
        if isinstance(snapshot_generation, bool) or int(snapshot_generation) < 1:
            raise ValueError("snapshot_generation must be a positive integer")
        snapshot = int(snapshot_generation)
        normalized_specs = tuple(specs)
        if not isinstance(record_authority_cut, bool):
            raise TypeError("record_authority_cut must be a boolean")
        normalized_authority_kind = (
            _required_text(authority_kind, "authority_kind")
            if authority_kind is not None
            else ("managed_decision" if normalized_specs else "managed_zero_job")
        )
        expected_authority_kind = (
            "managed_decision" if normalized_specs else "managed_zero_job"
        )
        if normalized_authority_kind != expected_authority_kind:
            raise ValueError(
                "managed authority_kind does not match the scheduled job cut"
            )
        if any(not isinstance(spec, WorkflowJobSpec) for spec in normalized_specs):
            raise TypeError("specs must contain WorkflowJobSpec values")
        for spec in normalized_specs:
            if (
                spec.project_id != project
                or spec.task_id != task
                or spec.generation != generation
            ):
                raise WorkflowJobStoreError(
                    "scheduled job spec escaped its task activation generation"
                )
            if spec.scheduling_lane != "decision":
                raise WorkflowJobStoreError(
                    "decision reconciliation cannot materialize an event lane"
                )
        expected_keys = {spec.idempotency_key for spec in normalized_specs}
        if len(expected_keys) != len(normalized_specs):
            raise WorkflowJobStoreError("scheduled job specs contain duplicate keys")
        timestamp = float(self._clock() if now is None else now)
        with self._authority_mutation_guard():
            owns_transaction = not self._conn.in_transaction
            if owns_transaction:
                self._conn.execute("BEGIN IMMEDIATE")
            try:
                cursor = self._conn.execute(
                    """
                    SELECT * FROM workflow_schedule_cursors
                     WHERE project_id = ? AND task_id = ?
                    """,
                    (project, task),
                ).fetchone()
                if (
                    not self._snapshot_generation_is_current_locked(snapshot)
                    or
                    cursor is None
                    or int(cursor["snapshot_generation"]) != snapshot
                    or str(cursor["job_generation"]) != generation
                ):
                    if owns_transaction:
                        self._conn.commit()
                    return WorkflowScheduleWrite(
                        project,
                        task,
                        snapshot,
                        generation,
                        accepted=False,
                    )

                created = 0
                replayed = 0
                authoritative_job_ids: set[str] = set()
                for spec in normalized_specs:
                    authoritative_job, inserted = self._enqueue_locked(
                        spec, now=timestamp, workflow_managed=True
                    )
                    authoritative_job_ids.add(authoritative_job.job_id)
                    created += int(inserted)
                    replayed += int(not inserted)

                active_rows = self._conn.execute(
                    f"""
                    SELECT * FROM workflow_jobs
                     WHERE project_id = ? AND task_id = ?
                       AND workflow_managed = 1
                       AND state IN ({",".join("?" for _ in ACTIVE_JOB_STATES)})
                     ORDER BY enqueue_sequence
                    """,
                    (
                        project,
                        task,
                        *(state.value for state in ACTIVE_JOB_STATES),
                    ),
                ).fetchall()
                superseded = 0
                for selected in active_rows:
                    if str(selected["scheduling_lane"]) != "decision":
                        continue
                    is_current = (
                        str(selected["generation"]) == generation
                        and str(selected["idempotency_key"]) in expected_keys
                    )
                    if is_current:
                        continue
                    if (
                        str(selected["state"]) == WorkflowJobState.RUNNING.value
                        and str(selected["phase"]) == "quarantined"
                    ):
                        continue
                    self._conn.execute(
                        """
                        UPDATE workflow_jobs
                           SET state = ?, lease_owner = NULL, lease_token = NULL,
                               lease_expires_at = NULL, retry_at = NULL,
                               superseded_by_generation = ?, last_error = ?,
                               updated_at = ?, completed_at = ?
                         WHERE job_id = ?
                        """,
                        (
                            WorkflowJobState.SUPERSEDED.value,
                            generation,
                            message,
                            timestamp,
                            timestamp,
                            selected["job_id"],
                        ),
                    )
                    updated = self._row_locked(str(selected["job_id"]))
                    self._append_event_locked(
                        updated,
                        "superseded",
                        payload={
                            "replacement_generation": generation,
                            "reason": message,
                        },
                        now=timestamp,
                    )
                    superseded += 1
                self._conn.execute(
                    """
                    UPDATE workflow_schedule_cursors
                       SET materialized_job_generation = ?, updated_at = ?
                     WHERE project_id = ? AND task_id = ?
                       AND snapshot_generation = ? AND job_generation = ?
                    """,
                    (
                        generation,
                        timestamp,
                        project,
                        task,
                        snapshot,
                        generation,
                    ),
                )
                if record_authority_cut:
                    self._record_job_retirements_locked(
                        project_id=project,
                        task_id=task,
                        authority_kind=normalized_authority_kind,
                        decision_revision=str(cursor["decision_revision"]),
                        snapshot_generation=snapshot,
                        workflow_managed=True,
                        excluded_job_ids=tuple(authoritative_job_ids),
                        now=timestamp,
                    )
                if owns_transaction:
                    self._conn.commit()
                return WorkflowScheduleWrite(
                    project,
                    task,
                    snapshot,
                    generation,
                    accepted=True,
                    created=created,
                    replayed=replayed,
                    superseded=superseded,
                )
            except Exception:
                if owns_transaction:
                    self._conn.rollback()
                raise

    def list_jobs(
        self,
        *,
        project_id: str | None = None,
        task_id: str | None = None,
        generation: str | None = None,
        states: Sequence[WorkflowJobState | str] | None = None,
        actions: Sequence[str] | None = None,
        phases: Sequence[str] | None = None,
        scheduling_lanes: Sequence[str] | None = None,
        expected_evidence_revisions: Sequence[str] | None = None,
        limit: int = DEFAULT_SCAN_LIMIT,
        newest_first: bool = False,
    ) -> tuple[WorkflowJob, ...]:
        bounded = _bounded_limit(limit)
        clauses: list[str] = []
        values: list[object] = []
        for column, value in (
            ("project_id", project_id),
            ("task_id", task_id),
            ("generation", generation),
        ):
            if value is not None:
                clauses.append(f"{column} = ?")
                values.append(_required_text(value, column))
        if states:
            normalized = tuple(WorkflowJobState(state).value for state in states)
            clauses.append(f"state IN ({','.join('?' for _ in normalized)})")
            values.extend(normalized)
        for column, candidates in (
            ("action", actions),
            ("phase", phases),
            ("scheduling_lane", scheduling_lanes),
            ("expected_evidence_revision", expected_evidence_revisions),
        ):
            if isinstance(candidates, (str, bytes)):
                raise TypeError(f"{column}s must be a sequence of names")
            if candidates is None:
                continue
            normalized_names = tuple(
                sorted({_required_text(value, column) for value in candidates})
            )
            if not normalized_names:
                raise ValueError(f"{column}s cannot be empty")
            clauses.append(
                f"{column} IN ({','.join('?' for _ in normalized_names)})"
            )
            values.extend(normalized_names)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        order = "DESC" if newest_first else "ASC"
        with self._lock:
            rows = self._conn.execute(
                f"""
                SELECT * FROM workflow_jobs {where}
                 ORDER BY enqueue_sequence {order} LIMIT ?
                """,
                (*values, bounded),
            ).fetchall()
        return tuple(self._from_row(row) for row in rows)

    def current_exhausted_jobs(
        self, *, project_id: str, task_id: str
    ) -> tuple[WorkflowJob, ...]:
        """Return this task's authoritative current exhausted generations.

        Historical ledger rows remain immutable.  They are excluded here only
        when their lane cursor and a concrete replacement row agree that a
        distinct generation owns subsequent recovery.  Any partial or
        ambiguous cursor state remains actionable.
        """

        project = _required_text(project_id, "project_id")
        task = _required_text(task_id, "task_id")
        with self._lock:
            rows = self._conn.execute(
                f"""
                SELECT *
                  FROM workflow_jobs job
                 WHERE job.project_id = ? AND job.task_id = ?
                   AND {_CURRENT_EXHAUSTION_PREDICATE}
                 ORDER BY job.enqueue_sequence
                """,
                (project, task),
            ).fetchall()
        return tuple(self._from_row(row) for row in rows)

    def due_jobs(
        self,
        *,
        now: float | None = None,
        project_id: str | None = None,
        limit: int = DEFAULT_SCAN_LIMIT,
    ) -> tuple[WorkflowJob, ...]:
        """Return a bounded, deterministic projection without claiming rows."""

        timestamp = float(self._clock() if now is None else now)
        bounded = _bounded_limit(limit)
        project_clause = "AND project_id = ?" if project_id is not None else ""
        values: list[object] = [
            WorkflowJobState.QUEUED.value,
            WorkflowJobState.RETRY_WAIT.value,
            timestamp,
        ]
        if project_id is not None:
            values.append(_required_text(project_id, "project_id"))
        values.append(bounded)
        with self._lock:
            rows = self._conn.execute(
                f"""
                SELECT * FROM workflow_jobs
                 WHERE (
                    state = ? OR (state = ? AND retry_at IS NOT NULL AND retry_at <= ?)
                 )
                 {project_clause}
                 AND attempts < max_attempts
                 ORDER BY priority,
                          CASE WHEN retry_at IS NULL THEN created_at ELSE retry_at END,
                          enqueue_sequence
                 LIMIT ?
                """,
                values,
            ).fetchall()
        return tuple(self._from_row(row) for row in rows)

    def _recover_rows_locked(
        self,
        rows: Sequence[sqlite3.Row],
        *,
        category: WorkflowFailureCategory,
        error: str,
        now: float,
        phase: str | None = None,
    ) -> int:
        recovered = 0
        for selected in rows:
            # A terminal-audit FINALIZING lease owns a complete typed result.
            # Generic lease recovery must not turn that result back into
            # provider work (or into retry exhaustion).  The terminal-audit
            # replay lane proves the exact job/token/attempt identity and
            # rotates this lease with ``reclaim_abandoned`` instead.
            if (
                str(selected["action"]) == "terminal_audit"
                and str(selected["phase"]) == "finalizing"
            ):
                continue
            exhausted = int(selected["attempts"]) >= int(selected["max_attempts"])
            state = WorkflowJobState.EXHAUSTED if exhausted else WorkflowJobState.QUEUED
            cursor = self._conn.execute(
                """
                UPDATE workflow_jobs
                   SET state = ?, lease_owner = NULL, lease_token = NULL,
                       lease_expires_at = NULL, retry_at = NULL,
                       phase = COALESCE(?, phase),
                       failure_category = ?, last_error = ?, updated_at = ?,
                       completed_at = ?
                 WHERE job_id = ? AND state = ? AND lease_token = ?
                """,
                (
                    state.value,
                    phase,
                    category.value,
                    error,
                    now,
                    now if exhausted else None,
                    selected["job_id"],
                    WorkflowJobState.RUNNING.value,
                    selected["lease_token"],
                ),
            )
            if cursor.rowcount != 1:
                continue
            row = self._row_locked(str(selected["job_id"]))
            self._append_event_locked(
                row,
                "exhausted" if exhausted else "recovered",
                payload={"failure_category": category.value},
                now=now,
            )
            recovered += 1
        return recovered

    def _recover_expired_locked(
        self,
        *,
        now: float,
        limit: int,
        project_id: str | None = None,
        actions: Sequence[str] | None = None,
        phases: Sequence[str] | None = None,
    ) -> int:
        clauses = [
            "state = ?",
            "lease_expires_at IS NOT NULL",
            "lease_expires_at <= ?",
            "NOT (action = 'terminal_audit' AND phase = 'finalizing')",
        ]
        values: list[object] = [WorkflowJobState.RUNNING.value, now]
        if project_id is not None:
            clauses.append("project_id = ?")
            values.append(_required_text(project_id, "project_id"))
        for column, raw_values in (("action", actions), ("phase", phases)):
            if isinstance(raw_values, (str, bytes)):
                raise TypeError(f"{column}s must be a sequence")
            if raw_values is None:
                continue
            normalized = tuple(
                sorted({_required_text(value, column) for value in raw_values})
            )
            if not normalized:
                raise ValueError(f"{column}s cannot be empty")
            clauses.append(
                f"{column} IN ({','.join('?' for _ in normalized)})"
            )
            values.extend(normalized)
        values.append(limit)
        rows = self._conn.execute(
            f"""
            SELECT * FROM workflow_jobs
             WHERE {' AND '.join(clauses)}
             ORDER BY lease_expires_at, enqueue_sequence LIMIT ?
            """,
            values,
        ).fetchall()
        return self._recover_rows_locked(
            rows,
            category=WorkflowFailureCategory.LEASE_EXPIRED,
            error="workflow job lease expired before acknowledgement",
            now=now,
        )

    def recover_expired(
        self,
        *,
        project_id: str | None = None,
        actions: Sequence[str] | None = None,
        phases: Sequence[str] | None = None,
        now: float | None = None,
        limit: int = DEFAULT_SCAN_LIMIT,
    ) -> int:
        timestamp = float(self._clock() if now is None else now)
        bounded = _bounded_limit(limit)
        with self._authority_mutation_guard():
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                recovered = self._recover_expired_locked(
                    now=timestamp,
                    limit=bounded,
                    project_id=project_id,
                    actions=actions,
                    phases=phases,
                )
                self._conn.commit()
                return recovered
            except Exception:
                self._conn.rollback()
                raise

    def recover_abandoned(
        self,
        *,
        lease_owner: str | None = None,
        phase: str | None = None,
        project_id: str | None = None,
        actions: Sequence[str] | None = None,
        phases: Sequence[str] | None = None,
        now: float | None = None,
        limit: int = DEFAULT_SCAN_LIMIT,
    ) -> int:
        """Recover leases known abandoned after an exclusive process restart."""

        timestamp = float(self._clock() if now is None else now)
        bounded = _bounded_limit(limit)
        owner_clause = "AND lease_owner = ?" if lease_owner is not None else ""
        project_clause = "AND project_id = ?" if project_id is not None else ""
        if isinstance(actions, (str, bytes)):
            raise TypeError("actions must be a sequence of action names")
        normalized_actions = (
            tuple(sorted({_required_text(value, "action") for value in actions}))
            if actions is not None
            else ()
        )
        if actions is not None and not normalized_actions:
            raise ValueError("actions cannot be empty")
        action_clause = (
            f"AND action IN ({','.join('?' for _ in normalized_actions)})"
            if normalized_actions
            else ""
        )
        if isinstance(phases, (str, bytes)):
            raise TypeError("phases must be a sequence of phase names")
        normalized_phases = (
            tuple(sorted({_required_text(value, "phase") for value in phases}))
            if phases is not None
            else ()
        )
        if phases is not None and not normalized_phases:
            raise ValueError("phases cannot be empty")
        phases_clause = (
            f"AND phase IN ({','.join('?' for _ in normalized_phases)})"
            if normalized_phases
            else ""
        )
        values: list[object] = [WorkflowJobState.RUNNING.value]
        if lease_owner is not None:
            values.append(_required_text(lease_owner, "lease_owner"))
        if project_id is not None:
            values.append(_required_text(project_id, "project_id"))
        values.extend(normalized_actions)
        values.extend(normalized_phases)
        values.append(bounded)
        with self._authority_mutation_guard():
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                rows = self._conn.execute(
                    f"""
                    SELECT * FROM workflow_jobs
                     WHERE state = ? {owner_clause} {project_clause} {action_clause}
                       {phases_clause}
                       AND NOT (
                           action = 'terminal_audit' AND phase = 'finalizing'
                       )
                     ORDER BY enqueue_sequence LIMIT ?
                    """,
                    values,
                ).fetchall()
                recovered = self._recover_rows_locked(
                    rows,
                    category=WorkflowFailureCategory.ABANDONED,
                    error="workflow job lease was abandoned during restart",
                    now=timestamp,
                    phase=phase,
                )
                self._conn.commit()
                return recovered
            except Exception:
                self._conn.rollback()
                raise

    def reclaim_abandoned(
        self,
        job_id: str,
        lease_token: str,
        *,
        lease_owner: str,
        lease_seconds: float,
        expected_phase: str | None = None,
        now: float | None = None,
    ) -> WorkflowJob:
        """Rotate one known-abandoned lease without changing its attempt.

        This is intentionally narrower than :meth:`recover_abandoned`.  A
        restart recovery path that has proved one exact worker is gone may
        take over only that job/token pair; it cannot disturb unrelated jobs
        which happen to share a process-level ``lease_owner`` string.  The
        checkpoint and phase are retained so an already-produced result can
        be replayed instead of launching another provider attempt.
        """

        identifier = _required_text(job_id, "job_id")
        previous_token = _required_text(lease_token, "lease_token")
        owner = _required_text(lease_owner, "lease_owner")
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        phase = (
            _required_text(expected_phase, "expected_phase")
            if expected_phase is not None
            else None
        )
        timestamp = float(self._clock() if now is None else now)
        replacement_token = uuid.uuid4().hex
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                existing = self._row_locked(identifier)
                if (
                    str(existing["state"]) != WorkflowJobState.RUNNING.value
                    or str(existing["lease_token"] or "") != previous_token
                    or (phase is not None and str(existing["phase"]) != phase)
                ):
                    raise WorkflowJobLeaseLost(
                        f"workflow job lease is not reclaimable: {identifier}"
                    )
                self._conn.execute(
                    """
                    UPDATE workflow_jobs
                       SET lease_owner = ?, lease_token = ?, lease_expires_at = ?,
                           updated_at = ?
                     WHERE job_id = ? AND state = ? AND lease_token = ?
                    """,
                    (
                        owner,
                        replacement_token,
                        timestamp + float(lease_seconds),
                        timestamp,
                        identifier,
                        WorkflowJobState.RUNNING.value,
                        previous_token,
                    ),
                )
                row = self._row_locked(identifier)
                self._append_event_locked(
                    row,
                    "reclaimed",
                    payload={"previous_lease_owner": existing["lease_owner"]},
                    now=timestamp,
                )
                self._conn.commit()
                return self._from_row(row)
            except Exception:
                self._conn.rollback()
                raise

    def cancel_owned(
        self,
        job_id: str,
        lease_token: str,
        *,
        reason: str,
        now: float | None = None,
    ) -> WorkflowJob:
        """Cancel one running job only while the caller owns its exact lease."""

        identifier = _required_text(job_id, "job_id")
        message = _required_text(reason, "reason")
        timestamp = float(self._clock() if now is None else now)
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                self._owned_row_locked(identifier, lease_token, now=timestamp)
                self._conn.execute(
                    """
                    UPDATE workflow_jobs
                       SET state = ?, phase = 'complete', lease_owner = NULL,
                           lease_token = NULL, lease_expires_at = NULL,
                           retry_at = NULL, last_error = ?, updated_at = ?,
                           completed_at = ?
                     WHERE job_id = ?
                    """,
                    (
                        WorkflowJobState.CANCELLED.value,
                        message,
                        timestamp,
                        timestamp,
                        identifier,
                    ),
                )
                row = self._row_locked(identifier)
                self._append_event_locked(
                    row, "cancelled", payload={"reason": message}, now=timestamp
                )
                self._conn.commit()
                return self._from_row(row)
            except Exception:
                self._conn.rollback()
                raise

    def claim_next(
        self,
        *,
        lease_owner: str,
        lease_seconds: float,
        project_id: str | None = None,
        project_ids: Sequence[str] | None = None,
        task_id: str | None = None,
        generation: str | None = None,
        actions: Sequence[str] | None = None,
        compatible_running_actions: Sequence[str] | None = None,
        required_snapshot_generation: int | None = None,
        fair_across_projects: bool = False,
        now: float | None = None,
        recovery_limit: int = DEFAULT_SCAN_LIMIT,
    ) -> WorkflowJob | None:
        """Atomically recover expired rows and lease the first exact match."""

        owner = _required_text(lease_owner, "lease_owner")
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        bounded_recovery = _bounded_limit(recovery_limit)
        lease_token = uuid.uuid4().hex
        with self._authority_mutation_guard():
            # Eligibility is evaluated only after the authority lock is held.
            # A retry can become due while a concurrent writer owns that lock;
            # sampling before the wait would incorrectly hide it for a pass.
            timestamp = float(self._clock() if now is None else now)
            clauses, values, normalized_project_ids, normalized_actions = (
                self._claim_candidate_filter(
                    project_id=project_id,
                    project_ids=project_ids,
                    task_id=task_id,
                    generation=generation,
                    actions=actions,
                    compatible_running_actions=compatible_running_actions,
                    required_snapshot_generation=required_snapshot_generation,
                    now=timestamp,
                )
            )
            fairness_order = (
                "COALESCE((SELECT fairness.claim_sequence "
                "FROM workflow_project_fairness fairness "
                "WHERE fairness.project_id = candidate.project_id), 0),"
                if fair_across_projects and project_id is None
                else ""
            )
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                recovery_projects = normalized_project_ids or (project_id,)
                for recovery_project in recovery_projects:
                    self._recover_expired_locked(
                        now=timestamp,
                        limit=bounded_recovery,
                        project_id=recovery_project,
                        actions=normalized_actions,
                    )
                selected = self._conn.execute(
                    f"""
                    SELECT candidate.* FROM workflow_jobs candidate
                     WHERE {" AND ".join(clauses)}
                     ORDER BY {fairness_order} candidate.priority,
                              CASE WHEN candidate.retry_at IS NULL
                                   THEN candidate.created_at
                                   ELSE candidate.retry_at END,
                              candidate.enqueue_sequence
                     LIMIT 1
                    """,
                    values,
                ).fetchone()
                if selected is None:
                    self._conn.commit()
                    return None
                cursor = self._conn.execute(
                    """
                    UPDATE workflow_jobs
                       SET state = ?, lease_owner = ?, lease_token = ?,
                           lease_expires_at = ?, retry_at = NULL,
                           attempts = attempts + 1, updated_at = ?
                     WHERE job_id = ? AND state = ?
                    """,
                    (
                        WorkflowJobState.RUNNING.value,
                        owner,
                        lease_token,
                        timestamp + float(lease_seconds),
                        timestamp,
                        selected["job_id"],
                        selected["state"],
                    ),
                )
                if cursor.rowcount != 1:
                    self._conn.rollback()
                    return None
                row = self._row_locked(str(selected["job_id"]))
                if fair_across_projects and project_id is None:
                    claim_sequence = self._next_counter_locked(
                        "workflow_fair_claim_sequence"
                    )
                    self._conn.execute(
                        """
                        INSERT INTO workflow_project_fairness(
                            project_id, claim_sequence, updated_at
                        ) VALUES (?, ?, ?)
                        ON CONFLICT(project_id) DO UPDATE SET
                            claim_sequence = excluded.claim_sequence,
                            updated_at = excluded.updated_at
                        """,
                        (row["project_id"], claim_sequence, timestamp),
                    )
                self._append_event_locked(
                    row,
                    "claimed",
                    payload={"attempt": int(row["attempts"])},
                    now=timestamp,
                )
                self._conn.commit()
                return self._from_row(row)
            except Exception:
                self._conn.rollback()
                raise

    def has_claimable(
        self,
        *,
        project_id: str | None = None,
        project_ids: Sequence[str] | None = None,
        task_id: str | None = None,
        generation: str | None = None,
        actions: Sequence[str] | None = None,
        compatible_running_actions: Sequence[str] | None = None,
        required_snapshot_generation: int | None = None,
        now: float | None = None,
    ) -> bool:
        """Return whether an exact claim candidate exists without mutating it.

        Admission uses this probe only after filling a bounded execution lane.
        Sharing the claim predicate is important: a broad queued-row count can
        otherwise turn future retries, paused snapshot generations, or a
        second effect for an already-running task into a continuation loop.
        Expired lease recovery remains exclusive to :meth:`claim_next`.
        """

        with self._lock:
            timestamp = float(self._clock() if now is None else now)
            clauses, values, _project_ids, _actions = self._claim_candidate_filter(
                project_id=project_id,
                project_ids=project_ids,
                task_id=task_id,
                generation=generation,
                actions=actions,
                compatible_running_actions=compatible_running_actions,
                required_snapshot_generation=required_snapshot_generation,
                now=timestamp,
            )
            row = self._conn.execute(
                f"""
                SELECT 1 FROM workflow_jobs candidate
                 WHERE {" AND ".join(clauses)}
                 LIMIT 1
                """,
                values,
            ).fetchone()
        return row is not None

    @staticmethod
    def _claim_candidate_filter(
        *,
        project_id: str | None,
        project_ids: Sequence[str] | None,
        task_id: str | None,
        generation: str | None,
        actions: Sequence[str] | None,
        compatible_running_actions: Sequence[str] | None,
        required_snapshot_generation: int | None,
        now: float,
    ) -> tuple[
        list[str],
        list[object],
        tuple[str, ...],
        tuple[str, ...] | None,
    ]:
        """Build the one authoritative claim-eligibility predicate."""

        if project_id is not None and project_ids is not None:
            raise ValueError("project_id and project_ids are mutually exclusive")
        if isinstance(project_ids, (str, bytes)):
            raise TypeError("project_ids must be a sequence")
        normalized_project_ids = (
            tuple(
                sorted(
                    {
                        _required_text(value, "project_id")
                        for value in project_ids
                    }
                )
            )
            if project_ids is not None
            else ()
        )
        if project_ids is not None and not normalized_project_ids:
            raise ValueError("project_ids cannot be empty")
        normalized_compatible_actions = (
            tuple(
                sorted(
                    {
                        _required_text(action, "compatible_running_action")
                        for action in compatible_running_actions
                    }
                )
            )
            if compatible_running_actions
            else ()
        )
        running_compatibility_clause = ""
        if normalized_compatible_actions:
            running_compatibility_clause = (
                " AND owned.action NOT IN ("
                + ",".join("?" for _ in normalized_compatible_actions)
                + ") "
            )
        clauses = [
            "(candidate.state = ? OR (candidate.state = ? "
            "AND candidate.retry_at IS NOT NULL AND candidate.retry_at <= ?))",
            "candidate.attempts < candidate.max_attempts",
            "(candidate.workflow_managed = 0 OR ("
            "EXISTS (SELECT 1 FROM workflow_snapshot_membership member "
            "JOIN workflow_schedule_cursors cursor "
            "ON cursor.project_id = member.project_id "
            "AND cursor.task_id = member.task_id "
            "WHERE member.project_id = candidate.project_id "
            "AND member.task_id = candidate.task_id "
            "AND cursor.snapshot_generation = member.snapshot_generation "
            "AND cursor.job_generation = candidate.generation "
            "AND cursor.materialized_job_generation = candidate.generation) "
            "AND (SELECT CAST(value AS INTEGER) FROM schema_meta "
            "WHERE key = 'workflow_snapshot_accepted_generation') = "
            "(SELECT CAST(value AS INTEGER) FROM schema_meta "
            "WHERE key = 'workflow_snapshot_published_generation'))) ",
            "NOT EXISTS ("
            "SELECT 1 FROM workflow_jobs owned "
            "WHERE owned.project_id = candidate.project_id "
            "AND owned.task_id = candidate.task_id "
            "AND owned.state = 'running'"
            f"{running_compatibility_clause}"
            ")",
        ]
        values: list[object] = [
            WorkflowJobState.QUEUED.value,
            WorkflowJobState.RETRY_WAIT.value,
            now,
        ]
        values.extend(normalized_compatible_actions)
        for column, value in (
            ("project_id", project_id),
            ("task_id", task_id),
            ("generation", generation),
        ):
            if value is not None:
                clauses.append(f"candidate.{column} = ?")
                values.append(_required_text(value, column))
        if normalized_project_ids:
            clauses.append(
                "candidate.project_id IN ("
                + ",".join("?" for _ in normalized_project_ids)
                + ")"
            )
            values.extend(normalized_project_ids)
        normalized_actions: tuple[str, ...] | None = (
            tuple(_required_text(action, "action") for action in actions)
            if actions
            else None
        )
        if normalized_actions:
            clauses.append(
                f"candidate.action IN ({','.join('?' for _ in normalized_actions)})"
            )
            values.extend(normalized_actions)
        if required_snapshot_generation is not None:
            if (
                isinstance(required_snapshot_generation, bool)
                or int(required_snapshot_generation) < 1
            ):
                raise ValueError(
                    "required_snapshot_generation must be a positive integer"
                )
            snapshot = int(required_snapshot_generation)
            # A fast admission continuation is authorized by one exact,
            # already-published world snapshot.  Bind the claim itself to
            # that cut, rather than relying on a check before entering this
            # transaction: another process may accept/publish a replacement
            # generation between those two operations.  Mere allocation is
            # not authority and leaves the accepted published cut admissible.
            for key in (
                "workflow_snapshot_accepted_generation",
                "workflow_snapshot_published_generation",
            ):
                clauses.append(
                    "(SELECT CAST(value AS INTEGER) FROM schema_meta "
                    "WHERE key = ?) = ?"
                )
                values.extend((key, snapshot))
        return clauses, values, normalized_project_ids, normalized_actions

    def _owned_row_locked(
        self, job_id: str, lease_token: str, *, now: float
    ) -> sqlite3.Row:
        row = self._row_locked(_required_text(job_id, "job_id"))
        if (
            str(row["state"]) != WorkflowJobState.RUNNING.value
            or str(row["lease_token"] or "")
            != _required_text(lease_token, "lease_token")
            or row["lease_expires_at"] is None
            or float(row["lease_expires_at"]) <= now
        ):
            raise WorkflowJobLeaseLost(f"workflow job lease is not active: {job_id}")
        return row

    def owns_live_lease(
        self,
        job_id: str,
        lease_token: str,
        *,
        now: float | None = None,
    ) -> bool:
        """Check the exact durable token and expiry at a commit boundary."""

        timestamp = float(self._clock() if now is None else now)
        with self._lock:
            try:
                self._owned_row_locked(job_id, lease_token, now=timestamp)
            except (WorkflowJobLeaseLost, WorkflowJobStoreError, ValueError):
                return False
        return True

    def quarantine_owned(
        self,
        job_id: str,
        lease_token: str,
        *,
        category: WorkflowFailureCategory | str,
        error: str,
        now: float | None = None,
    ) -> WorkflowJob:
        """Durably make a non-returning invocation non-reclaimable in-process.

        The exact owner/token remain as crash-recovery evidence, while a NULL
        expiry prevents ordinary expiry recovery from overlapping an adapter
        thread which Python cannot terminate. Startup may recover the row only
        after proving the recorded runtime owner is dead.
        """

        timestamp = float(self._clock() if now is None else now)
        failure = WorkflowFailureCategory(category)
        message = _required_text(error, "error")
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._row_locked(_required_text(job_id, "job_id"))
                if (
                    str(row["state"]) != WorkflowJobState.RUNNING.value
                    or str(row["lease_token"] or "")
                    != _required_text(lease_token, "lease_token")
                ):
                    raise WorkflowJobLeaseLost(
                        f"workflow job lease is no longer owned: {job_id}"
                    )
                self._conn.execute(
                    """
                    UPDATE workflow_jobs
                       SET phase = 'quarantined', lease_expires_at = NULL,
                           retry_at = NULL, failure_category = ?,
                           last_error = ?, updated_at = ?
                     WHERE job_id = ? AND state = ? AND lease_token = ?
                    """,
                    (
                        failure.value,
                        message,
                        timestamp,
                        job_id,
                        WorkflowJobState.RUNNING.value,
                        lease_token,
                    ),
                )
                row = self._row_locked(job_id)
                self._append_event_locked(
                    row,
                    "quarantined",
                    payload={"failure_category": failure.value, "error": message},
                    now=timestamp,
                )
                self._conn.commit()
                return self._from_row(row)
            except Exception:
                self._conn.rollback()
                raise

    def settle_quarantined_call(
        self,
        job_id: str,
        lease_token: str,
        *,
        operation: str,
        effect_receipt: Mapping[str, Any] | None = None,
        failure_category: WorkflowFailureCategory | str = (
            WorkflowFailureCategory.UNKNOWN
        ),
        error: str | None = None,
        retryable: bool = True,
        retry_delay_seconds: float = 0,
        now: float | None = None,
    ) -> WorkflowJob:
        """Release one quarantine only after its exact detached call returns.

        A timed-out synchronous adapter may continue after its bounded worker
        await returns.  Quarantine deliberately removes the lease deadline
        so no replacement can overlap that call.  Its eventual completion is
        the one safe in-process release edge: bind settlement to the original
        token and quarantined phase, checkpoint an exact apply receipt before
        requeueing, and clear ownership in the same transaction.

        Successful calls resume the interrupted attempt, so the next claim
        does not spend an additional retry merely to verify an already-returned
        receipt.  Failed calls use the ordinary attempt budget and can become
        terminal; either outcome removes the per-task running fence only after
        the old invocation is proven finished.
        """

        identifier = _required_text(job_id, "job_id")
        token = _required_text(lease_token, "lease_token")
        call_operation = _required_text(operation, "operation")
        if retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds cannot be negative")
        if effect_receipt is not None and not isinstance(effect_receipt, Mapping):
            raise TypeError("effect_receipt must be a mapping")
        timestamp = float(self._clock() if now is None else now)
        succeeded = effect_receipt is not None or error is None
        category = WorkflowFailureCategory(failure_category)
        message = str(error or "").strip()
        if not succeeded and not message:
            raise ValueError("error is required for failed quarantine settlement")

        with self._authority_mutation_guard():
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                selected = self._row_locked(identifier)
                if (
                    str(selected["state"]) != WorkflowJobState.RUNNING.value
                    or str(selected["phase"]) != "quarantined"
                    or str(selected["lease_token"] or "") != token
                ):
                    raise WorkflowJobLeaseLost(
                        f"workflow quarantine is no longer owned: {identifier}"
                    )
                checkpoint = dict(
                    _decode_json_object(selected["checkpoint_json"], "checkpoint")
                    or {}
                )
                # A recycle request belongs to one exact lease token.  It is
                # historical once that detached call has returned and must
                # never survive into a later claim/quarantine ABA cycle.
                checkpoint.pop("quarantine_recycle", None)
                phase = "quarantine_recovered"
                retry_at: float | None = None
                completed_at: float | None = None
                attempts = int(selected["attempts"])
                if succeeded:
                    state = WorkflowJobState.QUEUED
                    # The next claim resumes this same interrupted attempt.
                    attempts = max(attempts - 1, 0)
                    if effect_receipt is not None:
                        checkpoint["effect"] = dict(effect_receipt)
                        phase = "effect_returned"
                    stored_category: str | None = None
                    stored_error: str | None = None
                    outcome = "returned"
                else:
                    exhausted = (
                        not retryable
                        or attempts >= int(selected["max_attempts"])
                    )
                    state = (
                        WorkflowJobState.EXHAUSTED
                        if exhausted
                        else WorkflowJobState.RETRY_WAIT
                    )
                    retry_at = (
                        None
                        if exhausted
                        else timestamp + float(retry_delay_seconds)
                    )
                    completed_at = timestamp if exhausted else None
                    stored_category = category.value
                    stored_error = message
                    outcome = "failed"
                self._conn.execute(
                    """
                    UPDATE workflow_jobs
                       SET state = ?, phase = ?, checkpoint_json = ?,
                           lease_owner = NULL, lease_token = NULL,
                           lease_expires_at = NULL, retry_at = ?, attempts = ?,
                           failure_category = ?, last_error = ?, updated_at = ?,
                           completed_at = ?
                     WHERE job_id = ? AND state = ? AND phase = 'quarantined'
                       AND lease_token = ?
                    """,
                    (
                        state.value,
                        phase,
                        _canonical_json(checkpoint),
                        retry_at,
                        attempts,
                        stored_category,
                        stored_error,
                        timestamp,
                        completed_at,
                        identifier,
                        WorkflowJobState.RUNNING.value,
                        token,
                    ),
                )
                row = self._row_locked(identifier)
                self._append_event_locked(
                    row,
                    "quarantine_settled",
                    payload={"operation": call_operation, "outcome": outcome},
                    now=timestamp,
                )
                self._conn.commit()
                return self._from_row(row)
            except Exception:
                self._conn.rollback()
                raise

    def mark_quarantine_recycle_requested(
        self,
        job_id: str,
        lease_token: str,
        *,
        now: float | None = None,
    ) -> WorkflowJob:
        """Durably bind one coalesced process-recycle request to a quarantine."""

        identifier = _required_text(job_id, "job_id")
        token = _required_text(lease_token, "lease_token")
        timestamp = float(self._clock() if now is None else now)
        with self._authority_mutation_guard():
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                selected = self._row_locked(identifier)
                if (
                    str(selected["state"]) != WorkflowJobState.RUNNING.value
                    or str(selected["phase"]) != "quarantined"
                    or str(selected["lease_token"] or "") != token
                ):
                    raise WorkflowJobLeaseLost(
                        f"workflow quarantine is no longer owned: {identifier}"
                    )
                checkpoint = dict(
                    _decode_json_object(selected["checkpoint_json"], "checkpoint")
                    or {}
                )
                marker = checkpoint.get("quarantine_recycle")
                lease_owner = str(selected["lease_owner"] or "")
                if (
                    isinstance(marker, Mapping)
                    and str(marker.get("lease_owner") or "") == lease_owner
                    and str(marker.get("lease_token") or "") == token
                ):
                    self._conn.commit()
                    return self._from_row(selected)
                checkpoint["quarantine_recycle"] = {
                    "lease_owner": lease_owner,
                    "lease_token": token,
                    "requested_at": timestamp,
                }
                self._conn.execute(
                    """
                    UPDATE workflow_jobs
                       SET checkpoint_json = ?, updated_at = ?
                     WHERE job_id = ? AND state = ? AND phase = 'quarantined'
                       AND lease_token = ?
                    """,
                    (
                        _canonical_json(checkpoint),
                        timestamp,
                        identifier,
                        WorkflowJobState.RUNNING.value,
                        token,
                    ),
                )
                row = self._row_locked(identifier)
                self._append_event_locked(
                    row,
                    "quarantine_recycle_requested",
                    payload={
                        "lease_owner": str(row["lease_owner"] or ""),
                        "replaced_stale_marker": marker is not None,
                    },
                    now=timestamp,
                )
                self._conn.commit()
                return self._from_row(row)
            except Exception:
                self._conn.rollback()
                raise

    def renew(
        self,
        job_id: str,
        lease_token: str,
        *,
        lease_seconds: float,
        now: float | None = None,
    ) -> WorkflowJob:
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        with self._authority_mutation_guard():
            # Resolve implicit time only after acquiring the serialization lock.
            # A heartbeat that waited behind another short transaction must not
            # validate against its pre-wait timestamp and write a renewal that is
            # already expired when it becomes visible.
            timestamp = float(self._clock() if now is None else now)
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                self._owned_row_locked(job_id, lease_token, now=timestamp)
                self._conn.execute(
                    """
                    UPDATE workflow_jobs SET lease_expires_at = ?, updated_at = ?
                     WHERE job_id = ?
                    """,
                    (timestamp + float(lease_seconds), timestamp, job_id),
                )
                row = self._row_locked(job_id)
                self._append_event_locked(row, "renewed", now=timestamp)
                self._conn.commit()
                return self._from_row(row)
            except Exception:
                self._conn.rollback()
                raise

    def checkpoint(
        self,
        job_id: str,
        lease_token: str,
        *,
        phase: str,
        checkpoint: Mapping[str, Any],
        now: float | None = None,
    ) -> WorkflowJob:
        clean_checkpoint = _json_object(checkpoint, "checkpoint")
        assert clean_checkpoint is not None
        normalized_phase = _required_text(phase, "phase")
        with self._authority_mutation_guard():
            timestamp = float(self._clock() if now is None else now)
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                self._owned_row_locked(job_id, lease_token, now=timestamp)
                self._conn.execute(
                    """
                    UPDATE workflow_jobs SET phase = ?, checkpoint_json = ?, updated_at = ?
                     WHERE job_id = ?
                    """,
                    (
                        normalized_phase,
                        _canonical_json(clean_checkpoint),
                        timestamp,
                        job_id,
                    ),
                )
                row = self._row_locked(job_id)
                self._append_event_locked(
                    row,
                    "checkpointed",
                    payload={"checkpoint": clean_checkpoint},
                    now=timestamp,
                )
                self._conn.commit()
                return self._from_row(row)
            except Exception:
                self._conn.rollback()
                raise

    def complete(
        self,
        job_id: str,
        lease_token: str,
        *,
        result_transition: Mapping[str, Any] | None = None,
        landing_facts: Sequence[Mapping[str, Any]] = (),
        now: float | None = None,
    ) -> WorkflowJob:
        result = _json_object(result_transition, "result_transition")
        if isinstance(landing_facts, (str, bytes)):
            raise TypeError("landing_facts must be a sequence")
        with self._authority_mutation_guard():
            timestamp = float(self._clock() if now is None else now)
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                owned = self._owned_row_locked(job_id, lease_token, now=timestamp)
                landing_rows = self._landing_fact_rows(
                    project_id=str(owned["project_id"]),
                    facts=landing_facts,
                    require_durable=True,
                )
                inserted_landing_facts = self._insert_landing_fact_rows_locked(
                    project_id=str(owned["project_id"]),
                    task_id=str(owned["task_id"]),
                    rows=landing_rows,
                    recorded_at=timestamp,
                )
                self._conn.execute(
                    """
                    UPDATE workflow_jobs
                       SET state = ?, phase = 'complete', lease_owner = NULL,
                           lease_token = NULL, lease_expires_at = NULL,
                           result_transition_json = ?, updated_at = ?, completed_at = ?
                     WHERE job_id = ?
                    """,
                    (
                        WorkflowJobState.COMPLETED.value,
                        _canonical_json(result) if result is not None else None,
                        timestamp,
                        timestamp,
                        job_id,
                    ),
                )
                row = self._row_locked(job_id)
                completion_payload: dict[str, Any] = {}
                if result is not None:
                    completion_payload["result_transition"] = result
                if landing_rows:
                    completion_payload.update(
                        {
                            "landing_facts": len(landing_rows),
                            "landing_facts_inserted": inserted_landing_facts,
                        }
                    )
                self._append_event_locked(
                    row,
                    "completed",
                    payload=completion_payload or None,
                    now=timestamp,
                )
                self._conn.commit()
                return self._from_row(row)
            except Exception:
                self._conn.rollback()
                raise

    def fail(
        self,
        job_id: str,
        lease_token: str,
        *,
        category: WorkflowFailureCategory | str,
        error: str,
        retryable: bool,
        retry_delay_seconds: float = 0,
        phase: str | None = None,
        now: float | None = None,
    ) -> WorkflowJob:
        failure = WorkflowFailureCategory(category)
        message = _required_text(error, "error")
        if retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds cannot be negative")
        normalized_phase = (
            _required_text(phase, "phase") if phase is not None else None
        )
        with self._authority_mutation_guard():
            timestamp = float(self._clock() if now is None else now)
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                owned = self._owned_row_locked(job_id, lease_token, now=timestamp)
                can_retry = bool(
                    retryable and int(owned["attempts"]) < int(owned["max_attempts"])
                )
                state = (
                    WorkflowJobState.RETRY_WAIT
                    if can_retry
                    else WorkflowJobState.EXHAUSTED
                )
                retry_at = timestamp + float(retry_delay_seconds) if can_retry else None
                self._conn.execute(
                    """
                    UPDATE workflow_jobs
                    SET state = ?, lease_owner = NULL, lease_token = NULL,
                           lease_expires_at = NULL, retry_at = ?,
                           phase = COALESCE(?, phase),
                           failure_category = ?, last_error = ?, updated_at = ?,
                           completed_at = ?
                     WHERE job_id = ?
                    """,
                    (
                        state.value,
                        retry_at,
                        normalized_phase,
                        failure.value,
                        message,
                        timestamp,
                        None if can_retry else timestamp,
                        job_id,
                    ),
                )
                row = self._row_locked(job_id)
                self._append_event_locked(
                    row,
                    "retry_scheduled" if can_retry else "exhausted",
                    payload={
                        "failure_category": failure.value,
                        "retry_at": retry_at,
                    },
                    now=timestamp,
                )
                self._conn.commit()
                return self._from_row(row)
            except Exception:
                self._conn.rollback()
                raise

    def requeue_owned_without_attempt(
        self,
        job_id: str,
        lease_token: str,
        *,
        expected_phase: str,
        phase: str,
        reason: str,
        now: float | None = None,
    ) -> WorkflowJob:
        """Release an exact lease when local lifecycle stopped the invocation.

        ``claim_next`` increments ``attempts`` at the execution boundary.  An
        operator pause or graceful lifecycle drain before a durable result is
        not an execution failure, so this exact inverse transition restores
        the prior count while clearing the callback-bearing checkpoint.  The
        running lease token is required, which fences late output and makes a
        repeated recovery observationally idempotent.
        """

        required_phase = _required_text(expected_phase, "expected_phase")
        normalized_phase = _required_text(phase, "phase")
        message = _required_text(reason, "reason")
        with self._authority_mutation_guard():
            timestamp = float(self._clock() if now is None else now)
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                owned = self._owned_row_locked(job_id, lease_token, now=timestamp)
                if str(owned["phase"]) != required_phase:
                    raise WorkflowJobLeaseLost(
                        f"workflow job phase is no longer owned: {job_id}"
                    )
                restored_attempts = max(int(owned["attempts"]) - 1, 0)
                self._conn.execute(
                    """
                    UPDATE workflow_jobs
                       SET state = ?, phase = ?, attempts = ?,
                           lease_owner = NULL, lease_token = NULL,
                           lease_expires_at = NULL, retry_at = NULL,
                           failure_category = NULL, last_error = NULL,
                           checkpoint_json = NULL,
                           result_transition_json = NULL,
                           updated_at = ?, completed_at = NULL
                     WHERE job_id = ? AND state = ? AND lease_token = ?
                       AND phase = ?
                    """,
                    (
                        WorkflowJobState.QUEUED.value,
                        normalized_phase,
                        restored_attempts,
                        timestamp,
                        job_id,
                        WorkflowJobState.RUNNING.value,
                        lease_token,
                        required_phase,
                    ),
                )
                row = self._row_locked(job_id)
                self._append_event_locked(
                    row,
                    "lifecycle_requeued",
                    payload={
                        "reason": message,
                        "restored_attempts": restored_attempts,
                    },
                    now=timestamp,
                )
                self._conn.commit()
                return self._from_row(row)
            except Exception:
                self._conn.rollback()
                raise

    def defer_owned_without_attempt(
        self,
        job_id: str,
        lease_token: str,
        *,
        reason: str,
        retry_delay_seconds: float,
        now: float | None = None,
    ) -> WorkflowJob:
        """Release an exact pre-effect lease without charging failure budget.

        A claim is the execution-attempt boundary and therefore increments the
        durable attempt count.  Administrative admission failures (operator
        pause, quiesce, lifecycle drain, and equivalent resource deferrals)
        happen before the external effect has started, so they invert only
        that increment.  The exact phase and checkpoint remain intact for the
        resumed invocation, while an append-only event records why ownership
        was released.

        Repeated deferrals retain exponential backoff independently of the
        substantive failure-attempt budget.  The exponent is capped so a long
        administrative outage cannot overflow or grow without bound.
        """

        message = _required_text(reason, "reason")
        if retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds cannot be negative")
        with self._authority_mutation_guard():
            timestamp = float(self._clock() if now is None else now)
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                owned = self._owned_row_locked(job_id, lease_token, now=timestamp)
                restored_attempts = max(int(owned["attempts"]) - 1, 0)
                prior_deferrals = int(
                    self._conn.execute(
                        """
                        SELECT COUNT(*) FROM workflow_job_events
                         WHERE job_id = ? AND event_type = 'administrative_deferred'
                        """,
                        (job_id,),
                    ).fetchone()[0]
                )
                exponent = min(
                    prior_deferrals, _MAX_ADMINISTRATIVE_BACKOFF_EXPONENT
                )
                retry_delay = float(retry_delay_seconds) * (2**exponent)
                retry_at = timestamp + retry_delay
                cursor = self._conn.execute(
                    """
                    UPDATE workflow_jobs
                       SET state = ?, attempts = ?,
                           lease_owner = NULL, lease_token = NULL,
                           lease_expires_at = NULL, retry_at = ?,
                           failure_category = NULL, last_error = NULL,
                           updated_at = ?, completed_at = NULL
                     WHERE job_id = ? AND state = ? AND lease_token = ?
                    """,
                    (
                        WorkflowJobState.RETRY_WAIT.value,
                        restored_attempts,
                        retry_at,
                        timestamp,
                        job_id,
                        WorkflowJobState.RUNNING.value,
                        lease_token,
                    ),
                )
                if cursor.rowcount != 1:
                    raise WorkflowJobLeaseLost(
                        f"workflow job lease is no longer owned: {job_id}"
                    )
                row = self._row_locked(job_id)
                self._append_event_locked(
                    row,
                    "administrative_deferred",
                    payload={
                        "reason": message,
                        "restored_attempts": restored_attempts,
                        "deferral_count": prior_deferrals + 1,
                        "retry_delay_seconds": retry_delay,
                        "retry_at": retry_at,
                    },
                    now=timestamp,
                )
                self._conn.commit()
                return self._from_row(row)
            except Exception:
                self._conn.rollback()
                raise

    def defer_owned_until(
        self,
        job_id: str,
        lease_token: str,
        *,
        reason: str,
        retry_at: float,
        now: float | None = None,
    ) -> WorkflowJob:
        """Release a pre-effect lease until one exact authoritative deadline.

        A fresh worker cut can ask to reassess the same durable generation
        without naming a replacement generation.  Persist that bounded wait
        as active ``RETRY_WAIT`` authority so restart reconstruction remains
        truthful and world scans cannot amplify the same transient mismatch
        into a stream of replacement jobs.
        """

        message = _required_text(reason, "reason")
        deadline = float(retry_at)
        if not math.isfinite(deadline):
            raise ValueError("retry_at must be finite")
        with self._authority_mutation_guard():
            timestamp = float(self._clock() if now is None else now)
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                owned = self._owned_row_locked(job_id, lease_token, now=timestamp)
                restored_attempts = max(int(owned["attempts"]) - 1, 0)
                deadline_due = deadline <= timestamp
                next_state = (
                    WorkflowJobState.SUPERSEDED
                    if deadline_due
                    else WorkflowJobState.RETRY_WAIT
                )
                replacement = (
                    f"reassess:{str(owned['generation'])}"
                    if deadline_due
                    else None
                )
                cursor = self._conn.execute(
                    """
                    UPDATE workflow_jobs
                       SET state = ?, attempts = ?,
                           lease_owner = NULL, lease_token = NULL,
                           lease_expires_at = NULL, retry_at = ?,
                           failure_category = NULL, last_error = ?,
                           superseded_by_generation = ?, updated_at = ?,
                           completed_at = ?
                     WHERE job_id = ? AND state = ? AND lease_token = ?
                    """,
                    (
                        next_state.value,
                        restored_attempts,
                        None if deadline_due else deadline,
                        message,
                        replacement,
                        timestamp,
                        timestamp if deadline_due else None,
                        job_id,
                        WorkflowJobState.RUNNING.value,
                        lease_token,
                    ),
                )
                if cursor.rowcount != 1:
                    raise WorkflowJobLeaseLost(
                        f"workflow job lease is no longer owned: {job_id}"
                    )
                row = self._row_locked(job_id)
                self._append_event_locked(
                    row,
                    (
                        "reassessment_due"
                        if deadline_due
                        else "reassessment_deferred"
                    ),
                    payload={
                        "reason": message,
                        "restored_attempts": restored_attempts,
                        "retry_at": deadline,
                        "replacement_generation": replacement,
                    },
                    now=timestamp,
                )
                self._conn.commit()
                return self._from_row(row)
            except Exception:
                self._conn.rollback()
                raise

    def supersede(
        self,
        job_id: str,
        *,
        generation: str,
        replacement_generation: str,
        reason: str,
        now: float | None = None,
    ) -> WorkflowJob:
        """Terminally fence an active exact generation without worker authority."""

        timestamp = float(self._clock() if now is None else now)
        expected = _required_text(generation, "generation")
        replacement = _required_text(replacement_generation, "replacement_generation")
        message = _required_text(reason, "reason")
        with self._authority_mutation_guard():
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                existing = self._row_locked(job_id)
                if str(existing["generation"]) != expected:
                    raise WorkflowJobStoreError(
                        "workflow job generation does not match"
                    )
                if WorkflowJobState(str(existing["state"])) in TERMINAL_JOB_STATES:
                    self._conn.commit()
                    return self._from_row(existing)
                if (
                    str(existing["state"]) == WorkflowJobState.RUNNING.value
                    and str(existing["phase"]) == "quarantined"
                ):
                    raise WorkflowJobStoreError(
                        "a quarantined workflow call cannot be superseded "
                        "before exact settlement or process recovery"
                    )
                self._conn.execute(
                    """
                    UPDATE workflow_jobs
                       SET state = ?, lease_owner = NULL, lease_token = NULL,
                           lease_expires_at = NULL, retry_at = NULL,
                           superseded_by_generation = ?, last_error = ?,
                           updated_at = ?, completed_at = ?
                     WHERE job_id = ? AND generation = ?
                    """,
                    (
                        WorkflowJobState.SUPERSEDED.value,
                        replacement,
                        message,
                        timestamp,
                        timestamp,
                        job_id,
                        expected,
                    ),
                )
                row = self._row_locked(job_id)
                self._append_event_locked(
                    row,
                    "superseded",
                    payload={"replacement_generation": replacement, "reason": message},
                    now=timestamp,
                )
                self._conn.commit()
                return self._from_row(row)
            except Exception:
                self._conn.rollback()
                raise

    def supersede_task_generation(
        self,
        *,
        project_id: str,
        task_id: str,
        keep_generation: str,
        reason: str,
        now: float | None = None,
        limit: int = DEFAULT_SCAN_LIMIT,
    ) -> int:
        """Boundedly supersede all active work older than one current generation."""

        timestamp = float(self._clock() if now is None else now)
        bounded = _bounded_limit(limit)
        project = _required_text(project_id, "project_id")
        task = _required_text(task_id, "task_id")
        current = _required_text(keep_generation, "keep_generation")
        message = _required_text(reason, "reason")
        with self._authority_mutation_guard():
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                rows = self._conn.execute(
                    f"""
                    SELECT * FROM workflow_jobs
                     WHERE project_id = ? AND task_id = ? AND generation != ?
                       AND state IN ({",".join("?" for _ in ACTIVE_JOB_STATES)})
                     ORDER BY enqueue_sequence LIMIT ?
                    """,
                    (
                        project,
                        task,
                        current,
                        *(state.value for state in ACTIVE_JOB_STATES),
                        bounded,
                    ),
                ).fetchall()
                superseded = 0
                for selected in rows:
                    if (
                        str(selected["state"]) == WorkflowJobState.RUNNING.value
                        and str(selected["phase"]) == "quarantined"
                    ):
                        continue
                    self._conn.execute(
                        """
                        UPDATE workflow_jobs
                           SET state = ?, lease_owner = NULL, lease_token = NULL,
                               lease_expires_at = NULL, retry_at = NULL,
                               superseded_by_generation = ?, last_error = ?,
                               updated_at = ?, completed_at = ?
                         WHERE job_id = ?
                        """,
                        (
                            WorkflowJobState.SUPERSEDED.value,
                            current,
                            message,
                            timestamp,
                            timestamp,
                            selected["job_id"],
                        ),
                    )
                    updated = self._row_locked(str(selected["job_id"]))
                    self._append_event_locked(
                        updated,
                        "superseded",
                        payload={"replacement_generation": current, "reason": message},
                        now=timestamp,
                    )
                    superseded += 1
                self._conn.commit()
                return superseded
            except Exception:
                self._conn.rollback()
                raise

    def cancel(
        self,
        job_id: str,
        *,
        generation: str,
        reason: str,
        now: float | None = None,
    ) -> WorkflowJob:
        timestamp = float(self._clock() if now is None else now)
        expected = _required_text(generation, "generation")
        message = _required_text(reason, "reason")
        with self._authority_mutation_guard():
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                existing = self._row_locked(job_id)
                if str(existing["generation"]) != expected:
                    raise WorkflowJobStoreError(
                        "workflow job generation does not match"
                    )
                if WorkflowJobState(str(existing["state"])) in TERMINAL_JOB_STATES:
                    self._conn.commit()
                    return self._from_row(existing)
                if (
                    str(existing["state"]) == WorkflowJobState.RUNNING.value
                    and str(existing["phase"]) == "quarantined"
                ):
                    raise WorkflowJobStoreError(
                        "a quarantined workflow call cannot be cancelled "
                        "before exact settlement or process recovery"
                    )
                self._conn.execute(
                    """
                    UPDATE workflow_jobs
                       SET state = ?, lease_owner = NULL, lease_token = NULL,
                           lease_expires_at = NULL, retry_at = NULL,
                           last_error = ?, updated_at = ?, completed_at = ?
                     WHERE job_id = ? AND generation = ?
                    """,
                    (
                        WorkflowJobState.CANCELLED.value,
                        message,
                        timestamp,
                        timestamp,
                        job_id,
                        expected,
                    ),
                )
                row = self._row_locked(job_id)
                self._append_event_locked(
                    row,
                    "cancelled",
                    payload={"reason": message},
                    now=timestamp,
                )
                self._conn.commit()
                return self._from_row(row)
            except Exception:
                self._conn.rollback()
                raise

    def health_snapshot(
        self,
        *,
        now: float | None = None,
        project_limit: int = MAX_SCAN_LIMIT,
    ) -> dict[str, Any]:
        """Return bounded queue, lease, retry, and fairness telemetry."""

        timestamp = float(self._clock() if now is None else now)
        bounded_projects = _bounded_limit(project_limit)
        with self._lock:
            state_rows = self._conn.execute(
                """
                SELECT state, COUNT(*) AS count
                  FROM workflow_jobs GROUP BY state ORDER BY state
                """
            ).fetchall()
            # ``states`` is the immutable ledger-history projection, while
            # ``current_states`` uses the same authoritative predicate as the
            # per-task liveness lookup.
            current_exhausted = self._conn.execute(
                f"""
                SELECT COUNT(*) AS count
                  FROM workflow_jobs job
                 WHERE {_CURRENT_EXHAUSTION_PREDICATE}
                """
            ).fetchone()
            phase_rows = self._conn.execute(
                """
                SELECT action, phase, COUNT(*) AS count
                  FROM workflow_jobs
                 GROUP BY action, phase ORDER BY action, phase
                """
            ).fetchall()
            project_rows = self._conn.execute(
                """
                SELECT project_id, state, COUNT(*) AS count
                  FROM workflow_jobs
                 GROUP BY project_id, state
                 ORDER BY project_id, state
                 LIMIT ?
                """,
                (bounded_projects,),
            ).fetchall()
            lease = self._conn.execute(
                """
                SELECT
                    SUM(CASE WHEN state = 'running' THEN 1 ELSE 0 END) AS running,
                    SUM(CASE WHEN state = 'running' AND lease_expires_at <= ?
                             THEN 1 ELSE 0 END) AS expired,
                    SUM(CASE WHEN state = 'running' AND phase = 'quarantined'
                             THEN 1 ELSE 0 END) AS quarantined,
                    MIN(CASE WHEN state = 'running' AND phase = 'quarantined'
                             THEN updated_at END) AS oldest_quarantined_at
                  FROM workflow_jobs
                """,
                (timestamp,),
            ).fetchone()
            retry = self._conn.execute(
                """
                SELECT
                    SUM(CASE WHEN state = 'retry_wait' THEN 1 ELSE 0 END) AS waiting,
                    SUM(CASE WHEN state = 'retry_wait' AND retry_at <= ?
                             THEN 1 ELSE 0 END) AS due
                  FROM workflow_jobs
                """,
                (timestamp,),
            ).fetchone()
            oldest = self._conn.execute(
                """
                SELECT MIN(CASE WHEN state = 'queued' THEN created_at
                                WHEN state = 'retry_wait' AND retry_at <= ?
                                THEN retry_at END) AS available_at
                  FROM workflow_jobs
                """,
                (timestamp,),
            ).fetchone()
            cursors = self._conn.execute(
                """
                SELECT COUNT(*) AS count,
                       COALESCE(MAX(snapshot_generation), 0) AS generation
                  FROM workflow_schedule_cursors
                """
            ).fetchone()
            membership = self._conn.execute(
                "SELECT COUNT(*) AS count FROM workflow_snapshot_membership"
            ).fetchone()
            fairness = self._conn.execute(
                "SELECT COUNT(*) AS count FROM workflow_project_fairness"
            ).fetchone()
            generation_rows = {
                str(row["key"]): int(row["value"])
                for row in self._conn.execute(
                    """
                    SELECT key, value FROM schema_meta
                     WHERE key IN (
                        'workflow_snapshot_generation',
                        'workflow_snapshot_accepted_generation',
                        'workflow_snapshot_published_generation'
                     )
                    """
                )
            }
        per_project: dict[str, dict[str, int]] = {}
        for row in project_rows:
            per_project.setdefault(str(row["project_id"]), {})[str(row["state"])] = int(
                row["count"]
            )
        phases: dict[str, dict[str, int]] = {}
        for row in phase_rows:
            phases.setdefault(str(row["action"]), {})[str(row["phase"])] = int(
                row["count"]
            )
        available_at = (
            float(oldest["available_at"])
            if oldest is not None and oldest["available_at"] is not None
            else None
        )
        return {
            "schema_version": self.schema_version,
            "states": {str(row["state"]): int(row["count"]) for row in state_rows},
            "current_states": {
                "exhausted": int(current_exhausted["count"] or 0)
                if current_exhausted is not None
                else 0,
            },
            "phases": phases,
            "terminal_audit_phases": phases.get("terminal_audit", {}),
            "leases": {
                "running": int(lease["running"] or 0) if lease is not None else 0,
                "expired": int(lease["expired"] or 0) if lease is not None else 0,
                "quarantined": (
                    int(lease["quarantined"] or 0) if lease is not None else 0
                ),
                "oldest_quarantined_age_seconds": (
                    max(0.0, timestamp - float(lease["oldest_quarantined_at"]))
                    if lease is not None
                    and lease["oldest_quarantined_at"] is not None
                    else None
                ),
            },
            "retries": {
                "waiting": int(retry["waiting"] or 0) if retry is not None else 0,
                "due": int(retry["due"] or 0) if retry is not None else 0,
            },
            "oldest_available_age_seconds": (
                max(0.0, timestamp - available_at) if available_at is not None else None
            ),
            "schedule_cursor_count": int(cursors["count"] or 0),
            "snapshot_membership_count": int(membership["count"] or 0),
            "latest_snapshot_generation": int(cursors["generation"] or 0),
            "captured_snapshot_generation": generation_rows.get(
                "workflow_snapshot_generation", 0
            ),
            "accepted_snapshot_generation": generation_rows.get(
                "workflow_snapshot_accepted_generation", 0
            ),
            "published_snapshot_generation": generation_rows.get(
                "workflow_snapshot_published_generation", 0
            ),
            "fair_project_count": int(fairness["count"] or 0),
            "projects": per_project,
            "projects_truncated": len(project_rows) >= bounded_projects,
            "rollout": list(self.rollout_snapshot()),
        }

    def integrity_check(self) -> None:
        with self._lock:
            result = self._conn.execute("PRAGMA integrity_check").fetchone()
            if result is None or str(result[0]).lower() != "ok":
                raise WorkflowJobCorruptionError(
                    f"SQLite integrity check failed: {result[0] if result else 'no result'}"
                )
            rows = self._conn.execute("SELECT * FROM workflow_jobs").fetchall()
            for row in rows:
                job = self._from_row(row)
                try:
                    spec = WorkflowJobSpec(**json.loads(str(row["spec_json"])))
                except (TypeError, ValueError, json.JSONDecodeError) as exc:
                    raise WorkflowJobCorruptionError(
                        f"invalid workflow job spec: {job.job_id}"
                    ) from exc
                if spec.revision != job.spec_revision:
                    raise WorkflowJobCorruptionError(
                        f"workflow job spec revision mismatch: {job.job_id}"
                    )
                if spec.payload != job.payload:
                    raise WorkflowJobCorruptionError(
                        f"workflow job payload mismatch: {job.job_id}"
                    )
                if spec.scheduling_lane != job.scheduling_lane:
                    raise WorkflowJobCorruptionError(
                        f"workflow job scheduling lane mismatch: {job.job_id}"
                    )
                if job.state is WorkflowJobState.RUNNING:
                    if (
                        not job.lease_owner
                        or not job.lease_token
                        or (
                            job.phase != "quarantined"
                            and job.lease_expires_at is None
                        )
                        or (
                            job.phase == "quarantined"
                            and job.lease_expires_at is not None
                        )
                    ):
                        raise WorkflowJobCorruptionError(
                            f"running workflow job lacks a complete lease: {job.job_id}"
                        )
                elif (
                    job.lease_owner
                    or job.lease_token
                    or job.lease_expires_at is not None
                ):
                    raise WorkflowJobCorruptionError(
                        f"inactive workflow job retained lease authority: {job.job_id}"
                    )
