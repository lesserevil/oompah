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
import os
import sqlite3
import threading
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any


WORKFLOW_JOB_SCHEMA_VERSION = 5
DEFAULT_SCAN_LIMIT = 100
MAX_SCAN_LIMIT = 1000
_INITIALIZE_LOCK = threading.Lock()


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
        if isinstance(self.priority, bool):
            raise ValueError("priority must be an integer")
        object.__setattr__(self, "priority", int(self.priority))
        if isinstance(self.max_attempts, bool) or int(self.max_attempts) < 1:
            raise ValueError("max_attempts must be a positive integer")
        object.__setattr__(self, "max_attempts", int(self.max_attempts))

    def to_dict(self) -> dict[str, Any]:
        return {
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
    created_at: float
    updated_at: float
    completed_at: float | None

    @property
    def is_active(self) -> bool:
        return self.state in ACTIVE_JOB_STATES

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_JOB_STATES

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
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
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
class WorkflowEventWrite:
    """Atomic materialization result for one semantic event lane."""

    job: WorkflowJob | None
    accepted: bool
    created: bool
    superseded: int


class WorkflowJobStoreError(RuntimeError):
    """Base class for workflow-job persistence errors."""


class WorkflowJobIdempotencyConflict(WorkflowJobStoreError):
    """An idempotency key was reused for different immutable work."""


class WorkflowJobLeaseLost(WorkflowJobStoreError):
    """A worker attempted to mutate work it no longer owns."""


class WorkflowJobCorruptionError(WorkflowJobStoreError):
    """Persisted workflow-job content cannot be decoded safely."""


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
CREATE TRIGGER IF NOT EXISTS workflow_job_events_no_update
BEFORE UPDATE ON workflow_job_events BEGIN
    SELECT RAISE(ABORT, 'workflow job events are append-only');
END;
CREATE TRIGGER IF NOT EXISTS workflow_job_events_no_delete
BEFORE DELETE ON workflow_job_events BEGIN
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


class WorkflowJobStore:
    """SQLite repository for generation-fenced, resumable workflow work."""

    def __init__(
        self,
        path: str,
        *,
        clock: Callable[[], float] = time.time,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.path = os.path.abspath(path)
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        self._clock = clock
        self._id_factory = id_factory or (lambda: f"workflow-job-{uuid.uuid4().hex}")
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False, timeout=10)
        self._conn.row_factory = sqlite3.Row
        with _INITIALIZE_LOCK, self._lock:
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.execute("PRAGMA busy_timeout=10000")
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._initialize()

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
        self._conn.executescript(_CREATE_V2_OBJECTS)
        self._conn.executescript(_CREATE_V3_OBJECTS)
        self._conn.executescript(_CREATE_V5_OBJECTS)
        if version < 4:
            self._migrate_v4_payloads()
        if version < 5:
            self._migrate_v5_lanes()
        self._conn.execute(
            "INSERT OR REPLACE INTO schema_meta(key, value) VALUES(?, ?)",
            ("workflow_jobs_version", str(WORKFLOW_JOB_SCHEMA_VERSION)),
        )
        self._conn.commit()

    @contextmanager
    def scheduling_batch(self):
        """Commit one bounded decision scan as a single durable transaction."""

        with self._lock:
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
            self._conn.close()

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
        rows: list[tuple[str, str, str, str]] = []
        for raw in facts:
            value = _json_object(raw, "landing_fact")
            if value is None:
                raise ValueError("landing_fact must be a mapping")
            if str(value.get("project_id") or "") != project:
                raise WorkflowJobStoreError("landing fact escaped project scope")
            source = _required_text(value.get("source"), "landing source")
            target = _required_text(value.get("target"), "landing target")
            revision = _required_text(
                value.get("evidence_revision"), "landing evidence_revision"
            )
            rows.append((source, target, revision, _canonical_json(value)))
        if not rows:
            return 0
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                inserted = 0
                for source, target, revision, encoded in rows:
                    cursor = self._conn.execute(
                        """
                        INSERT OR IGNORE INTO workflow_landing_facts(
                            project_id, task_id, source, target,
                            evidence_revision, fact_json, recorded_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (project, task, source, target, revision, encoded, timestamp),
                    )
                    inserted += int(cursor.rowcount == 1)
                self._conn.commit()
                return inserted
            except Exception:
                self._conn.rollback()
                raise

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

    def allocate_snapshot_generation(self) -> int:
        """Return a process-independent, monotonically increasing scan fence."""

        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                value = self._next_counter_locked("workflow_snapshot_generation")
                self._conn.commit()
                return value
            except Exception:
                self._conn.rollback()
                raise

    def allocate_decision_window(self, *, total: int, limit: int) -> int:
        """Return and advance a durable fair offset for a bounded task scan."""

        if isinstance(total, bool) or int(total) < 1:
            raise ValueError("total must be a positive integer")
        bounded = _bounded_limit(limit)
        count = int(total)
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._conn.execute(
                    """
                    SELECT value FROM schema_meta
                     WHERE key = 'workflow_decision_window_offset'
                    """
                ).fetchone()
                offset = (int(row["value"]) if row is not None else 0) % count
                next_offset = (offset + min(bounded, count)) % count
                self._conn.execute(
                    """
                    INSERT OR REPLACE INTO schema_meta(key, value)
                    VALUES('workflow_decision_window_offset', ?)
                    """,
                    (str(next_offset),),
                )
                self._conn.commit()
                return offset
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

    def activate_schedule(
        self,
        *,
        project_id: str,
        task_id: str,
        decision_revision: str,
        snapshot_generation: int,
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
        timestamp = float(self._clock() if now is None else now)
        with self._lock:
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
                    job_generation = (
                        f"{revision}:{snapshot}"
                        if changed
                        else str(existing["job_generation"])
                    )
                else:
                    changed = True
                    job_generation = f"{revision}:{snapshot}"
                self._conn.execute(
                    """
                    INSERT INTO workflow_schedule_cursors(
                        project_id, task_id, snapshot_generation,
                        decision_revision, job_generation, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(project_id, task_id) DO UPDATE SET
                        snapshot_generation = excluded.snapshot_generation,
                        decision_revision = excluded.decision_revision,
                        job_generation = excluded.job_generation,
                        updated_at = excluded.updated_at
                    """,
                    (
                        project,
                        task,
                        snapshot,
                        revision,
                        job_generation,
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
            created_at=float(row["created_at"]),
            updated_at=float(row["updated_at"]),
            completed_at=(
                float(row["completed_at"]) if row["completed_at"] is not None else None
            ),
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
        self._conn.execute(
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
        self, spec: WorkflowJobSpec, *, now: float
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
            return self._from_row(existing), False
        job_id = _required_text(self._id_factory(), "generated job_id")
        self._conn.execute(
            """
            INSERT INTO workflow_jobs(
                job_id, project_id, task_id, generation, action, phase,
                idempotency_key, spec_revision, spec_json, payload_json,
                scheduling_lane,
                expected_evidence_revision, expected_head_sha, state,
                priority, attempts, max_attempts, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
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
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                job, _created = self._enqueue_locked(spec, now=now)
                self._conn.commit()
                return job
            except Exception:
                self._conn.rollback()
                raise

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
        events one generation/job and gives an intervening different event a
        fresh generation while superseding every older active disposition.
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
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
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
        with self._lock:
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
        with self._lock:
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

    def reconcile_schedule(
        self,
        *,
        project_id: str,
        task_id: str,
        snapshot_generation: int,
        job_generation: str,
        specs: Sequence[WorkflowJobSpec],
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
        with self._lock:
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
                for spec in normalized_specs:
                    _job, inserted = self._enqueue_locked(spec, now=timestamp)
                    created += int(inserted)
                    replayed += int(not inserted)

                active_rows = self._conn.execute(
                    f"""
                    SELECT * FROM workflow_jobs
                     WHERE project_id = ? AND task_id = ?
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
    ) -> int:
        recovered = 0
        for selected in rows:
            exhausted = int(selected["attempts"]) >= int(selected["max_attempts"])
            state = WorkflowJobState.EXHAUSTED if exhausted else WorkflowJobState.QUEUED
            cursor = self._conn.execute(
                """
                UPDATE workflow_jobs
                   SET state = ?, lease_owner = NULL, lease_token = NULL,
                       lease_expires_at = NULL, retry_at = NULL,
                       failure_category = ?, last_error = ?, updated_at = ?,
                       completed_at = ?
                 WHERE job_id = ? AND state = ? AND lease_token = ?
                """,
                (
                    state.value,
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

    def _recover_expired_locked(self, *, now: float, limit: int) -> int:
        rows = self._conn.execute(
            """
            SELECT * FROM workflow_jobs
             WHERE state = ? AND lease_expires_at IS NOT NULL
               AND lease_expires_at <= ?
             ORDER BY lease_expires_at, enqueue_sequence LIMIT ?
            """,
            (WorkflowJobState.RUNNING.value, now, limit),
        ).fetchall()
        return self._recover_rows_locked(
            rows,
            category=WorkflowFailureCategory.LEASE_EXPIRED,
            error="workflow job lease expired before acknowledgement",
            now=now,
        )

    def recover_expired(
        self, *, now: float | None = None, limit: int = DEFAULT_SCAN_LIMIT
    ) -> int:
        timestamp = float(self._clock() if now is None else now)
        bounded = _bounded_limit(limit)
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                recovered = self._recover_expired_locked(now=timestamp, limit=bounded)
                self._conn.commit()
                return recovered
            except Exception:
                self._conn.rollback()
                raise

    def recover_abandoned(
        self,
        *,
        lease_owner: str | None = None,
        project_id: str | None = None,
        actions: Sequence[str] | None = None,
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
        values: list[object] = [WorkflowJobState.RUNNING.value]
        if lease_owner is not None:
            values.append(_required_text(lease_owner, "lease_owner"))
        if project_id is not None:
            values.append(_required_text(project_id, "project_id"))
        values.extend(normalized_actions)
        values.append(bounded)
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                rows = self._conn.execute(
                    f"""
                    SELECT * FROM workflow_jobs
                     WHERE state = ? {owner_clause} {project_clause} {action_clause}
                     ORDER BY enqueue_sequence LIMIT ?
                    """,
                    values,
                ).fetchall()
                recovered = self._recover_rows_locked(
                    rows,
                    category=WorkflowFailureCategory.ABANDONED,
                    error="workflow job lease was abandoned during restart",
                    now=timestamp,
                )
                self._conn.commit()
                return recovered
            except Exception:
                self._conn.rollback()
                raise

    def claim_next(
        self,
        *,
        lease_owner: str,
        lease_seconds: float,
        project_id: str | None = None,
        task_id: str | None = None,
        generation: str | None = None,
        actions: Sequence[str] | None = None,
        fair_across_projects: bool = False,
        now: float | None = None,
        recovery_limit: int = DEFAULT_SCAN_LIMIT,
    ) -> WorkflowJob | None:
        """Atomically recover expired rows and lease the first exact match."""

        owner = _required_text(lease_owner, "lease_owner")
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        timestamp = float(self._clock() if now is None else now)
        bounded_recovery = _bounded_limit(recovery_limit)
        clauses = [
            "(candidate.state = ? OR (candidate.state = ? "
            "AND candidate.retry_at IS NOT NULL AND candidate.retry_at <= ?))",
            "candidate.attempts < candidate.max_attempts",
            "NOT EXISTS ("
            "SELECT 1 FROM workflow_jobs owned "
            "WHERE owned.project_id = candidate.project_id "
            "AND owned.task_id = candidate.task_id "
            "AND owned.state = 'running'"
            ")",
        ]
        values: list[object] = [
            WorkflowJobState.QUEUED.value,
            WorkflowJobState.RETRY_WAIT.value,
            timestamp,
        ]
        for column, value in (
            ("project_id", project_id),
            ("task_id", task_id),
            ("generation", generation),
        ):
            if value is not None:
                clauses.append(f"candidate.{column} = ?")
                values.append(_required_text(value, column))
        if actions:
            normalized_actions = tuple(
                _required_text(action, "action") for action in actions
            )
            clauses.append(
                f"candidate.action IN ({','.join('?' for _ in normalized_actions)})"
            )
            values.extend(normalized_actions)
        fairness_order = (
            "COALESCE((SELECT fairness.claim_sequence "
            "FROM workflow_project_fairness fairness "
            "WHERE fairness.project_id = candidate.project_id), 0),"
            if fair_across_projects and project_id is None
            else ""
        )
        lease_token = uuid.uuid4().hex
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                self._recover_expired_locked(now=timestamp, limit=bounded_recovery)
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
        timestamp = float(self._clock() if now is None else now)
        with self._lock:
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
        timestamp = float(self._clock() if now is None else now)
        clean_checkpoint = _json_object(checkpoint, "checkpoint")
        assert clean_checkpoint is not None
        normalized_phase = _required_text(phase, "phase")
        with self._lock:
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
        now: float | None = None,
    ) -> WorkflowJob:
        timestamp = float(self._clock() if now is None else now)
        result = _json_object(result_transition, "result_transition")
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                self._owned_row_locked(job_id, lease_token, now=timestamp)
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
                self._append_event_locked(
                    row,
                    "completed",
                    payload={"result_transition": result}
                    if result is not None
                    else None,
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
        now: float | None = None,
    ) -> WorkflowJob:
        timestamp = float(self._clock() if now is None else now)
        failure = WorkflowFailureCategory(category)
        message = _required_text(error, "error")
        if retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds cannot be negative")
        with self._lock:
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
                           failure_category = ?, last_error = ?, updated_at = ?,
                           completed_at = ?
                     WHERE job_id = ?
                    """,
                    (
                        state.value,
                        retry_at,
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
        with self._lock:
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
        with self._lock:
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
                for selected in rows:
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
                self._conn.commit()
                return len(rows)
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
        with self._lock:
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
                             THEN 1 ELSE 0 END) AS expired
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
            fairness = self._conn.execute(
                "SELECT COUNT(*) AS count FROM workflow_project_fairness"
            ).fetchone()
        per_project: dict[str, dict[str, int]] = {}
        for row in project_rows:
            per_project.setdefault(str(row["project_id"]), {})[str(row["state"])] = int(
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
            "leases": {
                "running": int(lease["running"] or 0) if lease is not None else 0,
                "expired": int(lease["expired"] or 0) if lease is not None else 0,
            },
            "retries": {
                "waiting": int(retry["waiting"] or 0) if retry is not None else 0,
                "due": int(retry["due"] or 0) if retry is not None else 0,
            },
            "oldest_available_age_seconds": (
                max(0.0, timestamp - available_at) if available_at is not None else None
            ),
            "schedule_cursor_count": int(cursors["count"] or 0),
            "latest_snapshot_generation": int(cursors["generation"] or 0),
            "fair_project_count": int(fairness["count"] or 0),
            "projects": per_project,
            "projects_truncated": len(project_rows) >= bounded_projects,
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
                        or job.lease_expires_at is None
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
