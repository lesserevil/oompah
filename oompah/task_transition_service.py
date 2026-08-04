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
import hashlib
import inspect
import json
import os
import re
import sqlite3
import threading
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol

from oompah.models import Issue
from oompah.statuses import (
    ARCHIVED,
    DONE,
    IN_VALIDATION,
    MERGED,
    canonicalize_status,
)
from oompah.terminal_audit import (
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

TRANSITION_JOURNAL_SCHEMA_VERSION = 1
DEFAULT_TRANSITION_CLAIM_TTL_SECONDS = 300.0
TERMINAL_TARGETS = frozenset({DONE, MERGED, ARCHIVED})

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
                "task_branch",
                "base_branch",
                "head_sha",
                "base_sha",
            )
        }
    return {
        key: raw.get(key)
        for key in (
            "version",
            "state",
            "task_branch",
            "base_branch",
            "head_sha",
            "base_sha",
        )
        if raw.get(key) is not None
    }


def issue_authority_version(issue: Issue) -> str:
    """Return the stable version used for status compare-and-swap checks.

    Generic tracker timestamps are deliberately excluded.  A comment or
    other benign metadata write must not invalidate lifecycle authority.  The
    projection contains only task identity, lifecycle state, implementation
    generation/head, delivery branches, and integration authority.
    """

    projection = {
        "identifier": str(issue.identifier),
        "project_id": str(issue.project_id or ""),
        "status": canonicalize_status(issue.state),
        "assignment_id": _optional_text(getattr(issue, "assignment_id", None)),
        "head_sha": _optional_text(getattr(issue, "head_sha", None)),
        "work_branch": _optional_text(getattr(issue, "work_branch", None)),
        "target_branch": _optional_text(getattr(issue, "target_branch", None)),
        "integration": _integration_projection(issue),
    }
    return hashlib.sha256(_canonical_json(projection).encode("utf-8")).hexdigest()


def issue_exact_head(issue: Issue) -> str | None:
    """Return the task's exact authority head when one is available."""

    direct = _optional_text(getattr(issue, "head_sha", None))
    if direct:
        return direct.lower()
    integration = getattr(issue, "integration", None)
    if isinstance(integration, Mapping):
        value = _optional_text(integration.get("head_sha"))
    else:
        value = _optional_text(getattr(integration, "head_sha", None))
    return value.lower() if value else None


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
        if self.schema_version != 1:
            raise ValueError("unsupported TransitionIntent schema_version")

    @property
    def revision(self) -> str:
        return hashlib.sha256(
            _canonical_json(self.to_dict()).encode("utf-8")
        ).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
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

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "TransitionIntent":
        if not isinstance(raw, Mapping):
            raise ValueError("transition intent must be an object")
        return cls(**dict(raw))


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


class CoordinatorTerminalAdapter:
    """Adapt ``TerminalTransitionCoordinator`` to the service boundary."""

    def __init__(self, coordinator: Any):
        self._coordinator = coordinator

    async def stage(
        self, intent: TransitionIntent, issue: Issue
    ) -> TerminalStageResult:
        result = await self._coordinator.request_transition(
            current_issue=issue,
            requested_target=TargetState.from_raw(intent.requested_status),
            trigger_identity=ContributorIdentity(intent.actor, intent.authority.value),
            project_id=intent.project_id,
            evidence_fingerprint=compute_issue_evidence_fingerprint(
                issue, intent.project_id
            ),
        )
        return TerminalStageResult(
            success=bool(result.success),
            audit_id=_optional_text(getattr(result, "audit_id", None)),
            reason_code=(
                "transition.terminal_staged"
                if result.success
                else "transition.terminal_rejected"
            ),
            detail=_optional_text(getattr(result, "reason", None)),
        )


class TransitionJournalError(RuntimeError):
    """Base error for durable transition journal failures."""


class TransitionJournalCorruptionError(TransitionJournalError):
    """Raised when immutable journal content cannot be decoded safely."""


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

    def close(self) -> None:
        with self._lock:
            self._conn.close()

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
        with self._lock:
            return self._latest_event_locked(transition_id)

    def events(self, transition_id: str) -> tuple[TransitionJournalEvent, ...]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT * FROM task_transition_events
                 WHERE transition_id = ? ORDER BY sequence
                """,
                (transition_id,),
            ).fetchall()
            return tuple(self._event_from_row(row) for row in rows)

    def load_intent(self, transition_id: str) -> TransitionIntent:
        with self._lock:
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
                        waiting = TransitionOutcome(
                            transition_id=transition_id,
                            project_id=intent.project_id,
                            task_id=intent.task_id,
                            disposition=TransitionDisposition.WAITING,
                            reason_code="transition.recovery_required",
                            observed_status="",
                            observed_version=None,
                            requested_status=intent.requested_status,
                            retryable=True,
                            details={"recover_transition_id": active_transition},
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
                    self._conn.execute(
                        "DELETE FROM task_transition_claims WHERE project_id = ? AND task_id = ?",
                        (intent.project_id, intent.task_id),
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

    def integrity_check(self) -> None:
        with self._lock:
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
        claim_ttl_seconds: float = DEFAULT_TRANSITION_CLAIM_TTL_SECONDS,
    ) -> None:
        self.project_id = _required_text(project_id, "project_id")
        self.tracker = tracker
        self.journal = journal
        self.terminal_adapter = terminal_adapter
        if claim_ttl_seconds <= 0:
            raise ValueError("claim_ttl_seconds must be positive")
        self.claim_ttl_seconds = claim_ttl_seconds

    async def _fetch(self, task_id: str) -> Issue | None:
        operation = self.tracker.fetch_issue_detail
        if inspect.iscoroutinefunction(operation):
            issue = await operation(task_id)
        else:
            issue = await asyncio.to_thread(operation, task_id)
        if issue is None or isinstance(issue, Issue):
            return issue

        # Some tracker adapters implement their authoritative point lookup via
        # the batched state API.  Fall back to that protocol surface when the
        # detail adapter returns an invalid sentinel, but never manufacture a
        # snapshot: the transition still requires a fresh tracker read.
        fallback = self.tracker.fetch_issue_states_by_ids
        if inspect.iscoroutinefunction(fallback):
            candidates = await fallback([task_id])
        else:
            candidates = await asyncio.to_thread(fallback, [task_id])
        if isinstance(candidates, (list, tuple)):
            for candidate in candidates:
                if not isinstance(candidate, Issue):
                    continue
                if task_id in {str(candidate.id), str(candidate.identifier)}:
                    return candidate
        raise TypeError("tracker returned an invalid task detail snapshot")

    async def _try_fetch(self, task_id: str) -> tuple[Issue | None, Exception | None]:
        try:
            return await self._fetch(task_id), None
        except Exception as exc:  # noqa: BLE001 - tracker transport boundary
            return None, exc

    async def _update(self, task_id: str, status: str) -> None:
        operation = self.tracker.update_issue
        if inspect.iscoroutinefunction(operation):
            await operation(task_id, status=status)
            return
        await asyncio.to_thread(operation, task_id, status=status)

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

    async def execute(self, intent: TransitionIntent) -> TransitionOutcome:
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
        if begin.replay is not None:
            return begin.replay
        if begin.waiting is not None:
            return begin.waiting
        if begin.claim_token is None:
            raise TransitionJournalError("transition claim was not acquired")

        transition_id = begin.transition_id
        claim_token = begin.claim_token
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
                if observed_head != intent.exact_head:
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
                    outcome = self._outcome(
                        transition_id,
                        intent,
                        TransitionDisposition.REJECTED,
                        staged.reason_code,
                        latest or issue,
                        details={"detail": staged.detail},
                    )
                    await asyncio.to_thread(
                        self.journal.append,
                        transition_id,
                        TransitionPhase.REJECTED,
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
            await asyncio.to_thread(
                self.journal.release,
                intent.project_id,
                intent.task_id,
                claim_token,
            )
