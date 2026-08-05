"""Durable startup enforcement for terminal-task audits.

The terminal-audit records in :mod:`oompah.terminal_audit` describe an audit,
but they do not answer the deployment question: which terminal tasks existed
before the enforcement feature was enabled?  This module owns that boundary.

On the first successful scan it records a versioned grandfather baseline in
``service_state.json``.  Later scans compare the current terminal state and
evidence fingerprint with that baseline.  A task which becomes non-terminal,
changes evidence, or is newly terminal is queued for a fresh audit.  The
tracker metadata remains the source of truth for audits already in ``In
Validation``; startup recovery only rebuilds the in-memory queue and never
creates a new attempt.
"""

from __future__ import annotations

import copy
import contextvars
import hashlib
import json
import logging
import os
import tempfile
import threading
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from oompah.models import Issue
from oompah.statuses import (
    ARCHIVED,
    DONE,
    IN_VALIDATION,
    MERGED,
    canonicalize_status,
    status_key,
)
from oompah.terminal_audit import (
    EvidenceFingerprint,
    OverrideRecord,
    RequestState,
    TerminalAuditRecord,
    TargetState,
    Verdict,
    compute_issue_evidence_fingerprint,
)
from oompah.terminal_audit_metadata import (
    METADATA_KEY,
    TerminalAuditMetadataStore,
    TerminalAuditMetadataQuarantinedError,
)
from oompah.tracker import TrackerProtocol


logger = logging.getLogger(__name__)

SERVICE_STATE_KEY = "terminal_audit_enforcement"
SERVICE_STATE_VERSION = 1
PENDING_REQUEST_STATES = frozenset({RequestState.PENDING, RequestState.IN_PROGRESS})
TERMINAL_OVERRIDE_RECORDS_KEY = "oompah.terminal_override_records"
TERMINAL_RETIREMENTS_KEY = "oompah.terminal_audit_retirements"
TERMINAL_RESULT_INTENTS_KEY = "oompah.terminal_audit_result_intents"
LIFECYCLE_RECONCILIATIONS_KEY = "oompah.lifecycle_reconciliations"
LIFECYCLE_RECONCILIATION_STATE_KEY = "lifecycle_reconciliation"
LIFECYCLE_RECONCILIATION_VERSION = 1
DEFAULT_LIFECYCLE_RECONCILIATION_BATCH_SIZE = 4
DEFAULT_LIFECYCLE_RECONCILIATION_MAX_ATTEMPTS = 5
DEFAULT_LIFECYCLE_RECONCILIATION_RETRY_BACKOFF_SECONDS = 30.0
DEFAULT_LIFECYCLE_RECONCILIATION_MAX_BACKOFF_SECONDS = 3600.0

_TERMINAL_STATUS_RANK = {
    status_key(DONE): 1,
    status_key(MERGED): 2,
    status_key(ARCHIVED): 3,
}

_STATE_LOCK_GUARD = threading.Lock()
_STATE_LOCKS: dict[str, threading.RLock] = {}

# Context variable to pass loaded issues snapshot during recovery
# so the lifecycle validator can access parent state without additional fetches
_recovery_snapshot: contextvars.ContextVar[dict[str, Issue] | None] = contextvars.ContextVar(
    "_recovery_snapshot", default=None
)


def _state_lock(path: str) -> threading.RLock:
    with _STATE_LOCK_GUARD:
        return _STATE_LOCKS.setdefault(os.path.abspath(path), threading.RLock())


def get_recovery_snapshot() -> dict[str, Issue] | None:
    """Get the current recovery snapshot if one is active.

    During terminal audit recovery, the snapshot contains all loaded issues
    indexed by their identifiers and IDs. The lifecycle validator uses this
    to resolve parent issues locally without additional tracker fetches,
    enabling durable parent evidence checks even when source branches are deleted.

    Returns None when called outside of a recovery context.
    """
    return _recovery_snapshot.get()


def _as_fingerprint(value: Any) -> EvidenceFingerprint:
    """Decode a fingerprint supplied by a tracker or a small test double.

    Real records use the versioned ``EvidenceFingerprint`` mapping.  Accepting
    a digest string is useful for tracker adapters that expose a precomputed
    fingerprint; arbitrary strings are hashed so a changed value still fails
    the grandfather comparison without weakening the digest invariant.
    """

    if isinstance(value, EvidenceFingerprint):
        return value
    if isinstance(value, Mapping):
        digest = value.get("digest", value.get("sha256", value.get("value")))
        if isinstance(digest, str):
            try:
                return EvidenceFingerprint.from_dict(
                    {
                        "version": int(value.get("version", 1)),
                        "algorithm": value.get("algorithm", "sha256"),
                        "digest": digest,
                    }
                )
            except (TypeError, ValueError):
                pass
    if isinstance(value, str):
        if len(value) == 64 and all(character in "0123456789abcdef" for character in value):
            return EvidenceFingerprint(value)
        return EvidenceFingerprint(hashlib.sha256(value.encode("utf-8")).hexdigest())
    raise ValueError("evidence fingerprint must be a digest, mapping, or EvidenceFingerprint")


def _fingerprint_from_raw(raw: Mapping[str, Any]) -> EvidenceFingerprint:
    value = raw.get("evidence_fingerprint", raw.get("fingerprint"))
    if value is None:
        raise ValueError("missing evidence_fingerprint")
    return _as_fingerprint(value)


def _task_key(project_id: str, task_id: str) -> tuple[str, str]:
    return (str(project_id), str(task_id))


def _target_state_value(state: str) -> str:
    """Return the canonical domain spelling where one exists."""

    canonical = canonicalize_status(state)
    try:
        return TargetState.from_raw(canonical).value
    except ValueError:
        # Configured custom terminal states are still enforced.  They cannot
        # be represented as a TargetState record, but the queue can retain the
        # tracker spelling and fail closed until an auditor handles it.
        return str(state).strip()


def _target_state_status(raw: Any) -> str | None:
    """Decode a persisted target state into its tracker status spelling."""

    try:
        return TargetState.from_raw(raw).value
    except (TypeError, ValueError):
        return None


_MIN_AUTHORITY_TIMESTAMP = datetime.min.replace(tzinfo=timezone.utc)


def _authority_key(
    created_at: object,
    persisted_id: tuple[str, ...],
) -> tuple[datetime, tuple[str, ...]]:
    """Return a deterministic recovery ordering for a persisted intent.

    Only timezone-aware ISO-8601 timestamps participate in chronological
    authority.  Missing, malformed, or timezone-naive values sort at the
    minimum; the validated persisted identity then provides a stable tie
    breaker independent of ledger list order.
    """

    if not persisted_id or any(not value for value in persisted_id):
        raise ValueError("persisted authority identity must be non-empty")
    parsed = _MIN_AUTHORITY_TIMESTAMP
    if isinstance(created_at, str):
        try:
            candidate = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except ValueError:
            candidate = None
        if candidate is not None and candidate.tzinfo is not None:
            offset = candidate.utcoffset()
            if offset is not None:
                parsed = candidate.astimezone(timezone.utc)
    return (parsed, persisted_id)


@dataclass(frozen=True)
class GrandfatherTuple:
    """The immutable tuple captured for an existing terminal task."""

    project_id: str
    task_id: str
    terminal_state: str
    evidence_fingerprint: EvidenceFingerprint

    def __post_init__(self) -> None:
        if not isinstance(self.project_id, str) or not self.project_id.strip():
            raise ValueError("GrandfatherTuple.project_id must be non-empty")
        if not isinstance(self.task_id, str) or not self.task_id.strip():
            raise ValueError("GrandfatherTuple.task_id must be non-empty")
        if not isinstance(self.terminal_state, str) or not self.terminal_state.strip():
            raise ValueError("GrandfatherTuple.terminal_state must be non-empty")
        if not isinstance(self.evidence_fingerprint, EvidenceFingerprint):
            raise TypeError("GrandfatherTuple.evidence_fingerprint must be EvidenceFingerprint")

    @property
    def key(self) -> tuple[str, str]:
        return _task_key(self.project_id, self.task_id)

    def matches(self, terminal_state: str, fingerprint: EvidenceFingerprint) -> bool:
        return (
            status_key(self.terminal_state) == status_key(terminal_state)
            and self.evidence_fingerprint == fingerprint
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SERVICE_STATE_VERSION,
            "project_id": self.project_id,
            "task_id": self.task_id,
            "terminal_state": self.terminal_state,
            "evidence_fingerprint": self.evidence_fingerprint.to_dict(),
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "GrandfatherTuple":
        if not isinstance(raw, Mapping):
            raise ValueError("grandfather tuple must be a mapping")
        version = raw.get("version", SERVICE_STATE_VERSION)
        if isinstance(version, bool) or version != SERVICE_STATE_VERSION:
            raise ValueError("unsupported grandfather tuple version")
        project_id = raw.get("project_id", raw.get("project"))
        task_id = raw.get("task_id", raw.get("task"))
        state = raw.get("terminal_state", raw.get("state"))
        if not all(isinstance(value, str) and value.strip() for value in (project_id, task_id, state)):
            raise ValueError("grandfather tuple requires project, task, and terminal state")
        return cls(
            project_id=project_id,
            task_id=task_id,
            terminal_state=state,
            evidence_fingerprint=_fingerprint_from_raw(raw),
        )


@dataclass
class PendingAudit:
    """One queued audit request, including its unchanged attempt history."""

    project_id: str
    task_id: str
    audit_id: str
    target_state: str
    evidence_fingerprint: EvidenceFingerprint
    attempt_ids: list[str] = field(default_factory=list)
    source: str = "enforcement"
    record: TerminalAuditRecord | None = None

    def __post_init__(self) -> None:
        if not self.project_id or not self.task_id or not self.audit_id:
            raise ValueError("PendingAudit requires project_id, task_id, and audit_id")
        if not isinstance(self.evidence_fingerprint, EvidenceFingerprint):
            raise TypeError("PendingAudit.evidence_fingerprint must be EvidenceFingerprint")
        self.attempt_ids = list(dict.fromkeys(str(value) for value in self.attempt_ids if value))

    @property
    def key(self) -> tuple[str, str, str, str]:
        return (
            self.project_id,
            self.task_id,
            status_key(self.target_state),
            self.evidence_fingerprint.digest,
        )

    @classmethod
    def from_record(cls, record: TerminalAuditRecord, *, source: str = "metadata") -> "PendingAudit":
        return cls(
            project_id=record.project_id,
            task_id=record.task_id,
            audit_id=record.audit_id,
            target_state=record.target_state.value,
            evidence_fingerprint=record.evidence_fingerprint,
            attempt_ids=[attempt.attempt_id for attempt in record.attempts],
            source=source,
            record=record,
        )

    def merge_record(self, record: TerminalAuditRecord) -> None:
        """Merge metadata recovery without manufacturing an attempt."""

        self.attempt_ids = list(
            dict.fromkeys(
                [*self.attempt_ids, *(attempt.attempt_id for attempt in record.attempts)]
            )
        )
        if self.record is None:
            self.record = record

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "version": SERVICE_STATE_VERSION,
            "project_id": self.project_id,
            "task_id": self.task_id,
            "audit_id": self.audit_id,
            "target_state": self.target_state,
            "evidence_fingerprint": self.evidence_fingerprint.to_dict(),
            "attempt_ids": list(self.attempt_ids),
            "source": self.source,
        }
        if self.record is not None:
            result["record"] = self.record.to_dict()
        return result

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "PendingAudit":
        if (
            not isinstance(raw, Mapping)
            or isinstance(raw.get("version"), bool)
            or raw.get("version") != SERVICE_STATE_VERSION
        ):
            raise ValueError("unsupported pending audit version")
        record_raw = raw.get("record")
        record = (
            TerminalAuditRecord.from_dict(record_raw)
            if isinstance(record_raw, Mapping)
            else None
        )
        project_id = raw.get("project_id")
        task_id = raw.get("task_id")
        audit_id = raw.get("audit_id")
        target_state = raw.get("target_state")
        if not all(
            isinstance(value, str) and value.strip()
            for value in (project_id, task_id, audit_id, target_state)
        ):
            raise ValueError("pending audit requires project, task, id, and target state")
        attempts = raw.get("attempt_ids", [])
        if not isinstance(attempts, list) or not all(isinstance(value, str) for value in attempts):
            raise ValueError("pending audit attempt_ids must be a list of strings")
        return cls(
            project_id=project_id,
            task_id=task_id,
            audit_id=audit_id,
            target_state=target_state,
            evidence_fingerprint=_fingerprint_from_raw(raw),
            attempt_ids=attempts,
            source=str(raw.get("source", "enforcement")),
            record=record,
        )


@dataclass
class TerminalAuditEnforcementState:
    """Versioned service-state payload owned by this coordinator."""

    grandfathered: list[GrandfatherTuple] = field(default_factory=list)
    invalidated: list[GrandfatherTuple] = field(default_factory=list)
    pending_audits: list[PendingAudit] = field(default_factory=list)
    baseline_initialized: bool = True
    quarantined: bool = False
    errors: list[str] = field(default_factory=list)
    # The legacy shared-epic repair queue is deliberately separate from the
    # audit queue.  It is a bounded, restart-safe projection: tracker metadata
    # remains authoritative for the actual lifecycle transition.
    lifecycle_reconciliation: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SERVICE_STATE_VERSION,
            "baseline_initialized": self.baseline_initialized,
            "grandfathered": [entry.to_dict() for entry in self.grandfathered],
            "invalidated": [entry.to_dict() for entry in self.invalidated],
            "pending_audits": [entry.to_dict() for entry in self.pending_audits],
            "quarantined": self.quarantined,
            "errors": list(dict.fromkeys(self.errors)),
            LIFECYCLE_RECONCILIATION_STATE_KEY: copy.deepcopy(
                self.lifecycle_reconciliation
            ),
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "TerminalAuditEnforcementState":
        if (
            not isinstance(raw, Mapping)
            or isinstance(raw.get("version"), bool)
            or raw.get("version") != SERVICE_STATE_VERSION
        ):
            raise ValueError("unsupported terminal-audit enforcement version")
        raw_grandfathered = raw.get("grandfathered", raw.get("baseline", []))
        raw_invalidated = raw.get("invalidated", [])
        raw_pending = raw.get("pending_audits", [])
        if not all(isinstance(value, list) for value in (raw_grandfathered, raw_invalidated, raw_pending)):
            raise ValueError("terminal-audit enforcement lists must be lists")
        errors = raw.get("errors", [])
        if not isinstance(errors, list) or not all(isinstance(value, str) for value in errors):
            raise ValueError("terminal-audit enforcement errors must be a list of strings")
        lifecycle_reconciliation = raw.get(LIFECYCLE_RECONCILIATION_STATE_KEY, {})
        if not isinstance(lifecycle_reconciliation, Mapping):
            raise ValueError("lifecycle reconciliation state must be a mapping")
        return cls(
            grandfathered=[GrandfatherTuple.from_dict(value) for value in raw_grandfathered],
            invalidated=[GrandfatherTuple.from_dict(value) for value in raw_invalidated],
            pending_audits=[PendingAudit.from_dict(value) for value in raw_pending],
            baseline_initialized=bool(raw.get("baseline_initialized", True)),
            quarantined=bool(raw.get("quarantined", False)),
            errors=list(errors),
            lifecycle_reconciliation=copy.deepcopy(dict(lifecycle_reconciliation)),
        )


class _NoopLock:
    def __enter__(self) -> "_NoopLock":
        return self

    def __exit__(self, *_args: object) -> None:
        return None


class _NoopProjectStore:
    def project_write_lock(self, _project_id: str) -> _NoopLock:
        return _NoopLock()


class TerminalAuditEnforcement:
    """Coordinate the durable baseline and tracker metadata recovery."""

    def __init__(
        self,
        state_path: str | None = None,
        *,
        service_state_path: str | None = None,
        terminal_states: Iterable[str] = (),
        project_store: Any | None = None,
        load_state: Callable[[], Mapping[str, Any]] | None = None,
        save_state: Callable[[Mapping[str, Any]], None] | None = None,
        validate_terminal_transition: Callable[[Issue, TargetState, str], str | None]
        | None = None,
    ) -> None:
        self.state_path = state_path or service_state_path
        if self.state_path is None and load_state is None:
            raise ValueError("state_path or load_state is required")
        self.terminal_states = tuple(str(value) for value in terminal_states)
        self.project_store = project_store or _NoopProjectStore()
        self._load_state_callback = load_state
        self._save_state_callback = save_state
        self._validate_terminal_transition = validate_terminal_transition
        self.state = TerminalAuditEnforcementState()
        self._state_loaded = False
        self.pending_audits: list[PendingAudit] = []
        self.errors: list[str] = []
        self.last_result: dict[str, Any] = {}
        self._state_corrupt = False
        # ``pending_audits`` is a dispatchable projection, not a durable work
        # queue in its own right.  Keep the outcome of the most recent
        # tracker/metadata scan so the orchestrator can avoid claiming a
        # complete health recovery after a partial read.
        self._recovery_scan_complete = True
        self._recovery_scan_error_count = 0
        self._lifecycle_lock = threading.RLock()
        self._lifecycle_state_lock = threading.RLock()
        # Counts are derived from the post-recovery metadata snapshot.  An
        # unapplied result intent is an actionable finalization failure, not a
        # provider transport or command-policy failure.
        self.finalization_failure_counts: dict[str, int] = {}

    def _load_root_state(self) -> dict[str, Any]:
        if self._load_state_callback is not None:
            try:
                raw = self._load_state_callback()
            except Exception as exc:  # pragma: no cover - defensive callback boundary
                self._error("service_state_unreadable", exc)
                self._state_corrupt = True
                return {}
            if not isinstance(raw, Mapping):
                self._error("service_state_not_a_mapping")
                self._state_corrupt = True
                return {}
            return copy.deepcopy(dict(raw))
        assert self.state_path is not None
        path = Path(self.state_path)
        if not path.exists():
            return {}
        try:
            with path.open("r", encoding="utf-8") as handle:
                raw = json.load(handle)
            if not isinstance(raw, dict):
                raise ValueError("service state root must be a mapping")
            return raw
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            self._error("service_state_corrupt", exc)
            self._state_corrupt = True
            return {}

    def _persist(self, root: Mapping[str, Any]) -> bool:
        if self._state_corrupt:
            logger.error(
                "terminal-audit enforcement state is quarantined; refusing to overwrite corrupt service state"
            )
            return False
        payload = self.state.to_dict()
        if self._save_state_callback is not None:
            try:
                self._save_state_callback({SERVICE_STATE_KEY: payload})
            except Exception as exc:  # pragma: no cover - defensive callback boundary
                self._error("service_state_write_failed", exc)
                return False
            return True
        assert self.state_path is not None
        path = Path(self.state_path)
        with _state_lock(str(path)):
            merged = dict(root)
            merged[SERVICE_STATE_KEY] = payload
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(merged, handle, indent=2)
                    handle.write("\n")
                os.replace(temp_name, path)
            finally:
                if os.path.exists(temp_name):
                    os.unlink(temp_name)
        return True

    def _error(self, code: str, exc: BaseException | None = None) -> None:
        if code not in self.errors:
            self.errors.append(code)
        detail = f" ({type(exc).__name__})" if exc is not None else ""
        logger.error("terminal-audit enforcement: %s%s", code, detail)

    def _load_enforcement_state(self, root: Mapping[str, Any]) -> TerminalAuditEnforcementState | None:
        raw = root.get(SERVICE_STATE_KEY)
        if raw is None:
            return None
        try:
            return TerminalAuditEnforcementState.from_dict(raw)
        except (TypeError, ValueError, KeyError) as exc:
            self._error("terminal_audit_enforcement_corrupt", exc)
            return TerminalAuditEnforcementState(
                baseline_initialized=False,
                quarantined=True,
                errors=list(self.errors),
            )

    def _all_issues(self, tracker: TrackerProtocol) -> list[Issue]:
        fetch = getattr(tracker, "fetch_all_issues_enriched", None)
        if fetch is None:
            fetch = getattr(tracker, "fetch_all_issues", None)
        if fetch is not None:
            issues = fetch()
        else:
            # Small tracker doubles and older adapters may only expose the
            # state-filtered read.  This fallback still covers all configured
            # terminal states and In Validation; full adapters should provide
            # fetch_all_issues so non-terminal transitions are observable.
            by_states = getattr(tracker, "fetch_issues_by_states", None)
            if by_states is None:
                raise AttributeError("tracker has no issue enumeration method")
            states = list(dict.fromkeys([*self.terminal_states, IN_VALIDATION]))
            issues = by_states(states)
        return [issue for issue in (issues or []) if isinstance(issue, Issue) or hasattr(issue, "identifier")]

    def _issue_fingerprint(
        self,
        issue: Issue,
        tracker: TrackerProtocol,
        *,
        project_id: str | None = None,
    ) -> EvidenceFingerprint:
        for name in ("evidence_fingerprint", "current_evidence_fingerprint"):
            value = getattr(issue, name, None)
            if value is not None:
                return _as_fingerprint(value)

        issue_metadata = getattr(issue, "metadata", None)
        if isinstance(issue_metadata, Mapping):
            for key in ("evidence_fingerprint", "oompah.evidence_fingerprint"):
                if issue_metadata.get(key) is not None:
                    return _as_fingerprint(issue_metadata[key])

        # Tracker metadata is consulted only for an explicit fingerprint.  In
        # particular, reading a terminal task must never reuse an old audit
        # chain fingerprint as proof of the current task revision.
        try:
            metadata = tracker.get_metadata(issue.identifier) or {}
            for key in ("oompah.evidence_fingerprint", "evidence_fingerprint"):
                if metadata.get(key) is not None:
                    return _as_fingerprint(metadata[key])
        except Exception as exc:  # fail closed below, with an observable marker
            self._error("evidence_read_failed", exc)
        return compute_issue_evidence_fingerprint(
            issue,
            str(project_id or getattr(issue, "project_id", None) or ""),
        )

    def _current_tasks(
        self, scopes: Iterable[tuple[str, TrackerProtocol]]
    ) -> tuple[list[tuple[str, TrackerProtocol, Issue, EvidenceFingerprint]], bool]:
        current: list[tuple[str, TrackerProtocol, Issue, EvidenceFingerprint]] = []
        complete = True
        for project_id, tracker in scopes:
            try:
                issues = self._all_issues(tracker)
            except Exception as exc:
                self._error(f"task_scan_failed:{project_id}", exc)
                complete = False
                continue
            for issue in issues:
                task_id = str(getattr(issue, "identifier", "") or "")
                if not task_id:
                    self._error(f"task_without_identifier:{project_id}")
                    complete = False
                    continue
                # A tracker adapter may omit project_id; the scope is the
                # authoritative identity and prevents overlapping IDs from
                # different projects colliding.
                try:
                    fingerprint = self._issue_fingerprint(
                        issue, tracker, project_id=str(project_id)
                    )
                except Exception as exc:
                    self._error(
                        f"evidence_fingerprint_failed:{project_id}:{task_id}", exc
                    )
                    complete = False
                    continue
                current.append((str(project_id), tracker, issue, fingerprint))
        return current, complete

    @staticmethod
    def _authoritative_recovery_fingerprint(
        issue: Issue,
        tracker: TrackerProtocol,
        *,
        project_id: str,
    ) -> EvidenceFingerprint | None:
        """Return current revision evidence only when the tracker persists it.

        Some adapters can reconstruct the complete terminal evidence from the
        freshly read issue, while older adapters expose only descriptive task
        fields.  Recomputing a digest from that incomplete projection would
        make every richer persisted audit look stale after restart.  Prefer an
        explicit adapter fingerprint; otherwise derive one only when an
        immutable source revision is present (including native Markdown's
        persisted integration head).
        """

        values: list[Any] = [
            getattr(issue, "evidence_fingerprint", None),
            getattr(issue, "current_evidence_fingerprint", None),
        ]
        try:
            metadata = tracker.get_metadata(issue.identifier) or {}
        except Exception:
            metadata = {}
        if isinstance(metadata, Mapping):
            values.extend(
                metadata.get(key)
                for key in ("oompah.evidence_fingerprint", "evidence_fingerprint")
            )
        for value in values:
            if isinstance(value, EvidenceFingerprint):
                return value
            if isinstance(value, Mapping):
                digest = value.get("digest", value.get("sha256"))
                if isinstance(digest, str) and len(digest) == 64:
                    try:
                        return _as_fingerprint(value)
                    except (TypeError, ValueError):
                        continue
            if (
                isinstance(value, str)
                and len(value) == 64
                and all(character in "0123456789abcdef" for character in value)
            ):
                return EvidenceFingerprint(value)

        integration = getattr(issue, "integration", None)
        source_revision = (
            getattr(issue, "source_sha", None)
            or getattr(integration, "head_sha", None)
        )
        if isinstance(source_revision, str) and source_revision.strip():
            return compute_issue_evidence_fingerprint(issue, project_id)

        source_branch = (
            getattr(issue, "source_branch", None)
            or getattr(issue, "work_branch", None)
            or getattr(integration, "task_branch", None)
            or getattr(issue, "branch_name", None)
        )
        if isinstance(source_branch, str) and source_branch.strip():
            # A branch without its immutable revision proves that this issue
            # projection cannot reproduce the persisted terminal evidence.
            # Retain the durable request rather than manufacturing a mismatch.
            return None
        # Branchless trackers can still provide a complete task-content-only
        # fingerprint, so description revisions remain authoritative there.
        return compute_issue_evidence_fingerprint(issue, project_id)

    def _is_terminal(self, state: str) -> bool:
        wanted = {status_key(value) for value in self.terminal_states}
        return status_key(state) in wanted

    def _lifecycle_conflict(
        self,
        issue: Issue,
        target_state: TargetState,
        project_id: str,
    ) -> str | None:
        """Return a fail-closed lifecycle conflict for recovery replay."""

        if target_state != TargetState.MERGED:
            return None
        validator = self._validate_terminal_transition
        if validator is None:
            return None
        try:
            conflict = validator(issue, target_state, project_id)
        except Exception as exc:  # recovery must not replay unverifiable Merged
            logger.warning(
                "Could not verify recovered Merged lifecycle for %s/%s: %s",
                project_id,
                issue.identifier,
                exc,
                exc_info=True,
            )
            return (
                f"Merged recovery for {issue.identifier} could not verify shared-epic "
                "landing evidence; the parent review must land on its configured "
                "target branch first."
            )
        if isinstance(conflict, str) and conflict.strip():
            return conflict.strip()
        if conflict is False:
            return (
                f"Merged recovery for {issue.identifier} is incompatible with the "
                "shared-epic lifecycle; the parent review must land on its "
                "configured target branch first."
            )
        return None

    @staticmethod
    def _tuple_for(
        project_id: str, issue: Issue, fingerprint: EvidenceFingerprint
    ) -> GrandfatherTuple:
        return GrandfatherTuple(
            project_id=project_id,
            task_id=str(issue.identifier),
            terminal_state=str(issue.state),
            evidence_fingerprint=fingerprint,
        )

    @staticmethod
    def _audit_id(entry: GrandfatherTuple) -> str:
        material = "|".join(
            (entry.project_id, entry.task_id, status_key(entry.terminal_state), entry.evidence_fingerprint.digest)
        )
        digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]
        return f"terminal-audit-{digest}"

    def _queue_for_tuple(self, entry: GrandfatherTuple, *, source: str = "enforcement") -> PendingAudit:
        target_state = _target_state_value(entry.terminal_state)
        candidate = PendingAudit(
            project_id=entry.project_id,
            task_id=entry.task_id,
            audit_id=self._audit_id(entry),
            target_state=target_state,
            evidence_fingerprint=entry.evidence_fingerprint,
            source=source,
        )
        for existing in self.pending_audits:
            if existing.key == candidate.key or existing.audit_id == candidate.audit_id:
                return existing
        self.pending_audits.append(candidate)
        return candidate

    def _queue_record(self, record: TerminalAuditRecord) -> None:
        candidate = PendingAudit.from_record(record)
        for existing in self.pending_audits:
            if existing.audit_id == candidate.audit_id or existing.key == candidate.key:
                existing.merge_record(record)
                return
        self.pending_audits.append(candidate)

    @staticmethod
    def _dedupe_pending(entries: Iterable[PendingAudit]) -> list[PendingAudit]:
        """Collapse duplicate durable queue rows without losing attempt IDs."""
        result: list[PendingAudit] = []
        for entry in entries:
            match = next(
                (
                    existing
                    for existing in result
                    if existing.audit_id == entry.audit_id or existing.key == entry.key
                ),
                None,
            )
            if match is None:
                result.append(entry)
                continue
            match.attempt_ids = list(
                dict.fromkeys([*match.attempt_ids, *entry.attempt_ids])
            )
            if match.record is None:
                match.record = entry.record
        return result

    def _reconcile_current(
        self,
        current: Iterable[tuple[str, TrackerProtocol, Issue, EvidenceFingerprint]],
        *,
        scope_project_ids: Iterable[str],
    ) -> None:
        baseline = {entry.key: entry for entry in self.state.grandfathered}
        invalidated = {entry.key: entry for entry in self.state.invalidated}
        scoped_projects = {str(project_id) for project_id in scope_project_ids}
        observed_keys: set[tuple[str, str]] = set()
        for project_id, _tracker, issue, fingerprint in current:
            key = _task_key(project_id, str(issue.identifier))
            observed_keys.add(key)
            state = str(getattr(issue, "state", "") or "")
            if not self._is_terminal(state):
                # Removing the baseline is what makes a later terminal return
                # require a new audit, even when its state/evidence is identical.
                baseline.pop(key, None)
                invalidated.pop(key, None)
                continue
            observed = self._tuple_for(project_id, issue, fingerprint)
            old = baseline.get(key)
            if old is not None and old.matches(state, fingerprint):
                continue
            baseline.pop(key, None)
            prior_invalidated = invalidated.get(key)
            if prior_invalidated is None or not prior_invalidated.matches(state, fingerprint):
                invalidated[key] = observed
        # Successful full scans authoritatively prove that an absent task is
        # no longer dispatchable.  Keep rows for scopes we did not inspect so
        # a temporary project/tracker outage cannot silently erase history.
        self.state.grandfathered = [
            entry
            for key, entry in baseline.items()
            if key[0] not in scoped_projects or key in observed_keys
        ]
        self.state.invalidated = [
            entry
            for key, entry in invalidated.items()
            if key[0] not in scoped_projects or key in observed_keys
        ]

    def recover_pending_audits(
        self,
        scopes: Iterable[tuple[str, TrackerProtocol]],
        *,
        persist: bool = True,
        reconcile_lifecycle: bool = True,
    ) -> list[PendingAudit]:
        """Recover pending/in-progress records from ``In Validation`` metadata.

        Recovery is intentionally read-only for valid metadata.  Existing
        ``AuditAttempt`` IDs are copied into the queue, never regenerated, so
        a restart cannot duplicate an auditor attempt.
        """

        raw_scopes = scopes.items() if isinstance(scopes, Mapping) else scopes
        scope_list = [(str(project_id), tracker) for project_id, tracker in raw_scopes]
        recovered: list[PendingAudit] = []
        self._recovery_scan_complete = True
        self._recovery_scan_error_count = 0
        self.finalization_failure_counts = {}
        for project_id, tracker in scope_list:
            try:
                all_issues = self._all_issues(tracker)
                issues = [
                    issue
                    for issue in all_issues
                    if status_key(getattr(issue, "state", "")) == status_key(IN_VALIDATION)
                ]
            except Exception as exc:
                self._error(f"validation_scan_failed:{project_id}", exc)
                self._recovery_scan_complete = False
                self._recovery_scan_error_count += 1
                continue
            store = TerminalAuditMetadataStore(
                tracker, self.project_store, str(project_id)
            )

            # Build a snapshot map so the lifecycle validator can resolve parents
            # locally during recovery without additional tracker fetches.
            # This ensures durable parent evidence (terminal MERGED/ARCHIVED state)
            # can be checked even when source branches have been deleted.
            snapshot: dict[str, Issue] = {}
            for candidate in all_issues:
                for alias in (
                    getattr(candidate, "id", None),
                    getattr(candidate, "identifier", None),
                ):
                    alias_text = str(alias or "").strip()
                    if alias_text:
                        snapshot[alias_text] = candidate

            # Set the recovery snapshot context so the validator can access it
            token = _recovery_snapshot.set(snapshot)
            try:
                # Recover the durable terminal mutations before rebuilding the
                # queue projection.  An override intent is authoritative even
                # while the task is still In Validation: the process may have
                # died between persisting the intent and writing its status.
                with self.project_store.project_write_lock(str(project_id)):
                    for issue in all_issues:
                        if reconcile_lifecycle:
                            self._reconcile_incompatible_shared_epic_merged(
                                store, tracker, issue, str(project_id)
                            )
                        self._recover_terminal_override(
                            store, tracker, issue, str(project_id)
                        )
                        self._recover_terminal_result(store, tracker, issue, str(project_id))
            finally:
                _recovery_snapshot.reset(token)
            for issue in issues:
                current_fingerprint = self._authoritative_recovery_fingerprint(
                    issue,
                    tracker,
                    project_id=str(project_id),
                )
                try:
                    document = store.read(str(issue.identifier))
                except TerminalAuditMetadataQuarantinedError:
                    self._error(f"metadata_quarantined:{project_id}:{issue.identifier}")
                    self._recovery_scan_complete = False
                    self._recovery_scan_error_count += 1
                    continue
                except Exception as exc:
                    self._error(f"metadata_read_failed:{project_id}:{issue.identifier}", exc)
                    self._recovery_scan_complete = False
                    self._recovery_scan_error_count += 1
                    continue
                raw_intents = document.unknown_fields.get(
                    TERMINAL_RESULT_INTENTS_KEY, []
                )
                if isinstance(raw_intents, list):
                    failures = sum(
                        1
                        for raw_intent in raw_intents
                        if isinstance(raw_intent, Mapping)
                        and raw_intent.get("applied", True) is False
                        and raw_intent.get("project_id") == str(project_id)
                        and raw_intent.get("task_id") == str(issue.identifier)
                    )
                    if failures:
                        self.finalization_failure_counts[str(project_id)] = (
                            self.finalization_failure_counts.get(str(project_id), 0)
                            + failures
                        )
                if document.is_quarantined:
                    self._error(f"metadata_quarantined:{project_id}:{issue.identifier}")
                    self._recovery_scan_complete = False
                    self._recovery_scan_error_count += 1
                    continue
                # An unapplied owner intent fences the audit chain until its
                # authorized terminal mutation is either completed or
                # explicitly repaired.  Do not dispatch a sibling while a
                # failed/restarted override is still waiting for its status
                # write.
                raw_overrides = document.unknown_fields.get(
                    TERMINAL_OVERRIDE_RECORDS_KEY, []
                )
                if any(
                    isinstance(raw, Mapping)
                    and raw.get("applied", True) is False
                    and raw.get("project_id") == str(project_id)
                    and raw.get("task_id") == str(issue.identifier)
                    for raw in raw_overrides
                    if isinstance(raw, Mapping)
                ):
                    continue
                for record in document.pending_chain:
                    if record.project_id != str(project_id) or record.task_id != str(issue.identifier):
                        self._error(f"metadata_identity_mismatch:{project_id}:{issue.identifier}")
                        self._recovery_scan_complete = False
                        self._recovery_scan_error_count += 1
                        continue
                    if (
                        current_fingerprint is not None
                        and record.evidence_fingerprint != current_fingerprint
                    ):
                        # The current native revision supersedes this request
                        # even if a crashed writer did not mark it SUPERSEDED.
                        continue
                    if record.request_state in PENDING_REQUEST_STATES:
                        recovered.append(PendingAudit.from_record(record))
        # Persisted ``pending_audits`` rows are a recovery cache only.  Never
        # merge them back into the live set: a task may have left In
        # Validation, been overridden, been archived, or received a newer
        # evidence revision since the service last wrote that cache.
        self.pending_audits = self._dedupe_pending(recovered)
        self.state.pending_audits = list(self.pending_audits)
        if persist:
            self._persist(self._load_root_state())
        return list(self.pending_audits)

    def lifecycle_reconciliation_status(self) -> dict[str, Any]:
        """Return a redacted, non-blocking view of lifecycle migration progress.

        The queue is intentionally exposed as counters and row identities only;
        tracker comments, evidence, and exception text never enter service
        health.  This method does not acquire the lifecycle worker lock so a
        slow tracker mutation cannot make a state snapshot wait behind it.
        """

        with self._lifecycle_state_lock:
            raw = copy.deepcopy(
                getattr(self.state, "lifecycle_reconciliation", {}) or {}
            )
        if not isinstance(raw, Mapping):
            return {
                "version": LIFECYCLE_RECONCILIATION_VERSION,
                "status": "degraded",
                "error": "invalid_persisted_state",
            }
        result = copy.deepcopy(dict(raw))
        result.pop("records", None)
        result["version"] = LIFECYCLE_RECONCILIATION_VERSION
        result.setdefault("status", "idle")
        result.setdefault("total", 0)
        result.setdefault("processed", 0)
        result.setdefault("reconciled", 0)
        result.setdefault("failed", 0)
        result.setdefault("pending", 0)
        result.setdefault("retry_pending", 0)
        result.setdefault("retry_due", 0)
        result.setdefault("exhausted", 0)
        result.setdefault("action_required", False)
        result.setdefault("next_retry_at", None)
        result.setdefault("errors", [])
        return result

    def _set_lifecycle_state(self, state: Mapping[str, Any]) -> None:
        with self._lifecycle_state_lock:
            self.state.lifecycle_reconciliation = copy.deepcopy(dict(state))

    @staticmethod
    def _lifecycle_key(project_id: str, task_id: str) -> str:
        return f"{project_id}\x00{task_id}"

    @staticmethod
    def _lifecycle_record(
        project_id: str,
        task_id: str,
    ) -> dict[str, Any]:
        return {
            "project_id": str(project_id),
            "task_id": str(task_id),
            "status": "pending",
            "attempts": 0,
            "last_error": None,
        }

    @staticmethod
    def _lifecycle_timestamp(value: Any) -> datetime | None:
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _lifecycle_retry_delay(
        attempts: int,
        *,
        retry_backoff_seconds: float,
        retry_max_backoff_seconds: float,
    ) -> float:
        exponent = max(int(attempts) - 1, 0)
        delay = float(retry_backoff_seconds)
        ceiling = float(retry_max_backoff_seconds)
        for _ in range(exponent):
            if delay >= ceiling / 2:
                return ceiling
            delay *= 2
        return min(delay, ceiling)

    @staticmethod
    def _lifecycle_source_fingerprint(tracker: TrackerProtocol, issue: Issue) -> str:
        """Fingerprint only inputs whose repair may be changed by an operator."""

        metadata: Any
        try:
            metadata = tracker.get_metadata(str(issue.identifier))
        except Exception as exc:  # noqa: BLE001 - a failed read is itself stable input
            metadata = {"unavailable": type(exc).__name__}
        terminal_metadata = (
            metadata.get(METADATA_KEY)
            if isinstance(metadata, Mapping)
            else {"invalid": type(metadata).__name__}
        )
        payload = {
            "state": canonicalize_status(getattr(issue, "state", "")),
            "parent_id": str(getattr(issue, "parent_id", "") or ""),
            "terminal_audit": terminal_metadata,
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @classmethod
    def _lifecycle_counts(
        cls,
        records: list[Mapping[str, Any]],
        *,
        now: datetime,
    ) -> dict[str, Any]:
        completed = sum(1 for row in records if row.get("status") == "completed")
        reconciled = sum(
            1
            for row in records
            if row.get("status") == "completed" and row.get("outcome") == "reconciled"
        )
        retry_rows = [row for row in records if row.get("status") == "failed"]
        exhausted = sum(1 for row in records if row.get("status") == "exhausted")
        failed = len(retry_rows) + exhausted
        pending = sum(1 for row in records if row.get("status") == "pending")
        retry_times = [
            retry_at
            for row in retry_rows
            if (retry_at := cls._lifecycle_timestamp(row.get("next_attempt_at")))
            is not None
        ]
        next_retry = min(retry_times) if retry_times else None
        return {
            "total": len(records),
            "processed": completed,
            "reconciled": reconciled,
            "failed": failed,
            "pending": pending,
            "retry_pending": len(retry_rows),
            "retry_due": sum(retry_at <= now for retry_at in retry_times),
            "exhausted": exhausted,
            "action_required": bool(exhausted),
            "next_retry_at": next_retry.isoformat() if next_retry is not None else None,
        }

    @classmethod
    def _refresh_lifecycle_summary(
        cls,
        queue: dict[str, Any],
        *,
        now: datetime,
        scan_errors: Iterable[str] = (),
    ) -> None:
        records = queue.get("records", [])
        queue.update(cls._lifecycle_counts(records, now=now))
        row_errors = [
            f"{row.get('project_id')}/{row.get('task_id')}: {row.get('last_error')}"
            for row in records
            if row.get("status") in {"failed", "exhausted"} and row.get("last_error")
        ]
        queue["errors"] = list(
            dict.fromkeys([*(str(value) for value in scan_errors), *row_errors])
        )[-50:]
        if not records:
            queue["status"] = "degraded" if queue["errors"] else "idle"
        elif queue["failed"] or queue["errors"]:
            queue["status"] = "degraded"
        elif queue["pending"]:
            queue["status"] = "migrating"
        else:
            queue["status"] = "complete"

    def _lifecycle_prepare_queue(
        self,
        scopes: list[tuple[str, TrackerProtocol]],
        *,
        now: datetime,
        max_attempts: int,
        retry_backoff_seconds: float,
        retry_max_backoff_seconds: float,
    ) -> tuple[
        dict[str, Any],
        dict[tuple[str, str], tuple[TrackerProtocol, Issue]],
        set[str],
        bool,
    ]:
        """Discover Merged rows and prepare one coalesced durable projection."""

        current: dict[tuple[str, str], tuple[TrackerProtocol, Issue]] = {}
        merged_keys: set[tuple[str, str]] = set()
        unavailable_projects: set[str] = set()
        scan_errors: list[str] = []
        for project_id, tracker in scopes:
            try:
                issues = self._all_issues(tracker)
            except Exception as exc:  # noqa: BLE001 - isolate one project
                unavailable_projects.add(str(project_id))
                scan_errors.append(f"scan_failed:{project_id}:{type(exc).__name__}")
                continue
            for issue in issues:
                identifier = str(getattr(issue, "identifier", "") or "")
                if not identifier:
                    continue
                current[(str(project_id), identifier)] = (tracker, issue)
                if canonicalize_status(getattr(issue, "state", "")) != MERGED:
                    continue
                merged_keys.add((str(project_id), identifier))

        raw = getattr(self.state, "lifecycle_reconciliation", {}) or {}
        if not isinstance(raw, Mapping) or raw.get("version") != LIFECYCLE_RECONCILIATION_VERSION:
            raw = {}
        records: list[dict[str, Any]] = []
        by_key: dict[str, dict[str, Any]] = {}
        for item in raw.get("records", []) if isinstance(raw.get("records", []), list) else []:
            if not isinstance(item, Mapping):
                continue
            project_id = item.get("project_id")
            task_id = item.get("task_id")
            if not isinstance(project_id, str) or not isinstance(task_id, str):
                continue
            row = dict(item)
            row.setdefault("status", "pending")
            row.setdefault("attempts", 0)
            row.setdefault("last_error", None)
            key = self._lifecycle_key(project_id, task_id)
            if key not in by_key:
                by_key[key] = row
                records.append(row)

        for project_id, task_id in sorted(merged_keys):
            key = self._lifecycle_key(project_id, task_id)
            if key not in by_key:
                row = self._lifecycle_record(project_id, task_id)
                by_key[key] = row
                records.append(row)

        # Additive migration for the original unbounded ledger.  Rows already
        # beyond the retry budget become actionable immediately on deployment
        # instead of receiving one more attempt.  A later operator change to
        # the relevant task/terminal-audit metadata automatically opens a new
        # bounded retry epoch.
        for row in records:
            status = str(row.get("status", "pending"))
            if status not in {"pending", "failed", "exhausted", "completed"}:
                status = "pending"
                row["status"] = status
            attempts = row.get("attempts", 0)
            if isinstance(attempts, bool):
                attempts = 0
            try:
                attempts = max(int(attempts), 0)
            except (TypeError, ValueError):
                attempts = 0
            row["attempts"] = attempts
            tracker_issue = current.get(
                (str(row.get("project_id", "")), str(row.get("task_id", "")))
            )
            if status == "failed" and attempts >= max_attempts:
                row["status"] = status = "exhausted"
                row.setdefault("exhausted_at", str(row.get("updated_at") or now.isoformat()))
                row.pop("next_attempt_at", None)
                if tracker_issue is not None:
                    row["failure_fingerprint"] = self._lifecycle_source_fingerprint(
                        *tracker_issue
                    )
            elif status == "failed" and self._lifecycle_timestamp(
                row.get("next_attempt_at")
            ) is None:
                updated_at = self._lifecycle_timestamp(row.get("updated_at")) or now
                delay = self._lifecycle_retry_delay(
                    attempts,
                    retry_backoff_seconds=retry_backoff_seconds,
                    retry_max_backoff_seconds=retry_max_backoff_seconds,
                )
                row["next_attempt_at"] = (updated_at + timedelta(seconds=delay)).isoformat()
            elif status == "exhausted" and tracker_issue is not None:
                fingerprint = self._lifecycle_source_fingerprint(*tracker_issue)
                previous = row.get("failure_fingerprint")
                task_reappeared = (
                    row.get("last_error") == "task_not_present_in_current_snapshot"
                )
                if task_reappeared or (
                    isinstance(previous, str) and previous and previous != fingerprint
                ):
                    try:
                        retry_epochs = (
                            max(int(row.get("retry_epochs", 0) or 0), 0) + 1
                        )
                    except (TypeError, ValueError):
                        retry_epochs = 1
                    row.update(
                        {
                            "status": "pending",
                            "attempts": 0,
                            "last_error": None,
                            "retry_epochs": retry_epochs,
                        }
                    )
                    for key in (
                        "next_attempt_at",
                        "exhausted_at",
                        "failure_fingerprint",
                    ):
                        row.pop(key, None)
                elif not isinstance(previous, str) or not previous:
                    row["failure_fingerprint"] = fingerprint

        try:
            cursor = max(int(raw.get("cursor", 0) or 0), 0)
        except (TypeError, ValueError):
            cursor = 0
        queue = {
            "version": LIFECYCLE_RECONCILIATION_VERSION,
            "records": records,
            "cursor": cursor,
            "updated_at": str(raw.get("updated_at") or now.isoformat()),
        }
        self._refresh_lifecycle_summary(queue, now=now, scan_errors=scan_errors)
        comparable_raw = dict(raw) if isinstance(raw, Mapping) else {}
        changed = comparable_raw != queue
        if changed:
            queue["updated_at"] = now.isoformat()
        self._set_lifecycle_state(queue)
        return queue, current, unavailable_projects, changed

    def reconcile_lifecycle_batch(
        self,
        scopes: Iterable[tuple[str, TrackerProtocol]],
        *,
        batch_size: int = DEFAULT_LIFECYCLE_RECONCILIATION_BATCH_SIZE,
        max_attempts: int = DEFAULT_LIFECYCLE_RECONCILIATION_MAX_ATTEMPTS,
        retry_backoff_seconds: float = (
            DEFAULT_LIFECYCLE_RECONCILIATION_RETRY_BACKOFF_SECONDS
        ),
        retry_max_backoff_seconds: float = (
            DEFAULT_LIFECYCLE_RECONCILIATION_MAX_BACKOFF_SECONDS
        ),
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Process a bounded, durable batch of legacy lifecycle repairs.

        Discovery, outcomes, and cursor movement share a coalesced end-of-batch
        checkpoint.  Only a repair intent immediately preceding an external
        status write receives its own fail-closed checkpoint.  A crash leaves
        that row recoverable because tracker status and lifecycle metadata are
        checked before the repair is repeated.  Failing rows use durable,
        bounded retry epochs and never prevent fresh pending rows converging.
        """

        if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size <= 0:
            raise ValueError("batch_size must be a positive integer")
        if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or max_attempts <= 0:
            raise ValueError("max_attempts must be a positive integer")
        retry_backoff_seconds = float(retry_backoff_seconds)
        retry_max_backoff_seconds = float(retry_max_backoff_seconds)
        if retry_backoff_seconds <= 0:
            raise ValueError("retry_backoff_seconds must be positive")
        if retry_max_backoff_seconds < retry_backoff_seconds:
            raise ValueError("retry_max_backoff_seconds must be at least retry_backoff_seconds")
        current_time = now or datetime.now(timezone.utc)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)
        current_time = current_time.astimezone(timezone.utc)
        scope_list = [(str(project_id), tracker) for project_id, tracker in (
            scopes.items() if isinstance(scopes, Mapping) else scopes
        )]
        with self._lifecycle_lock:
            root = self._load_root_state()
            if not self._state_loaded:
                loaded = self._load_enforcement_state(root)
                if loaded is not None:
                    self.state = loaded
                    self.errors = list(dict.fromkeys([*self.errors, *loaded.errors]))
                self._state_loaded = True
            (
                queue,
                current,
                unavailable_projects,
                prepared_changed,
            ) = self._lifecycle_prepare_queue(
                scope_list,
                now=current_time,
                max_attempts=max_attempts,
                retry_backoff_seconds=retry_backoff_seconds,
                retry_max_backoff_seconds=retry_max_backoff_seconds,
            )
            records = queue["records"]
            cursor = int(queue.get("cursor", 0) or 0)
            record_count = len(records)

            def _cursor_order(index: int) -> int:
                return (index - cursor) % record_count if record_count else 0

            pending = sorted(
                (
                    (index, row)
                    for index, row in enumerate(records)
                    if row.get("status") == "pending"
                    and str(row.get("project_id", "")) not in unavailable_projects
                ),
                key=lambda item: _cursor_order(item[0]),
            )
            eligible = pending[:batch_size]
            remaining = batch_size - len(eligible)
            if remaining:
                due_failed = sorted(
                    (
                        (index, row)
                        for index, row in enumerate(records)
                        if row.get("status") == "failed"
                        and str(row.get("project_id", "")) not in unavailable_projects
                        and (
                            self._lifecycle_timestamp(row.get("next_attempt_at"))
                            or current_time
                        )
                        <= current_time
                    ),
                    key=lambda item: (
                        self._lifecycle_timestamp(item[1].get("next_attempt_at"))
                        or current_time,
                        _cursor_order(item[0]),
                    ),
                )
                eligible.extend(due_failed[:remaining])
            for index, row in eligible:
                project_id = str(row["project_id"])
                task_id = str(row["task_id"])
                tracker_issue = current.get((project_id, task_id))
                outcome = "completed"
                error: str | None = None
                if tracker_issue is None:
                    error = "task_not_present_in_current_snapshot"
                else:
                    tracker, issue = tracker_issue
                    if canonicalize_status(getattr(issue, "state", "")) != MERGED:
                        # The status write may have succeeded immediately
                        # before metadata finalization failed.  Complete that
                        # second half without writing the tracker status again.
                        if row.get("conflict"):
                            store = TerminalAuditMetadataStore(
                                tracker, self.project_store, project_id
                            )
                            try:
                                with self.project_store.project_write_lock(project_id):
                                    document = store.read(task_id)
                                    done_records = [
                                        record
                                        for record in document.pending_chain
                                        if (
                                            record.project_id == project_id
                                            and record.task_id in {
                                                task_id,
                                                str(getattr(issue, "id", "") or ""),
                                            }
                                            and record.target_state == TargetState.DONE
                                            and record.request_state == RequestState.COMPLETED
                                            and any(
                                                attempt.verdict == Verdict.PASS
                                                for attempt in record.attempts
                                            )
                                        )
                                    ]
                                    if done_records and self._finalize_incompatible_shared_epic_merged(
                                        store,
                                        tracker,
                                        issue,
                                        project_id,
                                        str(row["conflict"]),
                                        done_records,
                                    ):
                                        outcome = "reconciled"
                                    else:
                                        error = "lifecycle_metadata_not_finalized"
                            except Exception as exc:  # noqa: BLE001 - row isolation
                                error = f"lifecycle_metadata_recovery_failed:{type(exc).__name__}"
                        else:
                            outcome = "state_changed"
                    else:
                        validator = self._validate_terminal_transition
                        if validator is None:
                            error = "lifecycle_validator_unavailable"
                        else:
                            try:
                                conflict = validator(issue, TargetState.MERGED, project_id)
                            except Exception as exc:  # noqa: BLE001 - row isolation
                                conflict = None
                                error = f"lifecycle_validation_failed:{type(exc).__name__}"
                            if error is None and not (
                                isinstance(conflict, str) and conflict.strip()
                            ):
                                outcome = "not_needed"
                            elif error is None:
                                row["conflict"] = str(conflict)
                                try:
                                    # Persist the classification before the
                                    # external status write.  If the process
                                    # dies after that write, a fresh worker
                                    # sees the persisted conflict and can
                                    # finish metadata without mutating status
                                    # a second time.
                                    queue["updated_at"] = current_time.isoformat()
                                    self._set_lifecycle_state(queue)
                                    if not self._persist(self._load_root_state()):
                                        raise RuntimeError(
                                            "lifecycle intent was not durably persisted"
                                        )
                                except Exception as exc:  # noqa: BLE001 - row isolation
                                    error = f"lifecycle_intent_persist_failed:{type(exc).__name__}"
                                if error is None:
                                    store = TerminalAuditMetadataStore(
                                        tracker, self.project_store, project_id
                                    )
                                    try:
                                        with self.project_store.project_write_lock(project_id):
                                            if self._reconcile_incompatible_shared_epic_merged(
                                                store, tracker, issue, project_id
                                            ):
                                                outcome = "reconciled"
                                            else:
                                                error = "lifecycle_repair_not_applied"
                                    except Exception as exc:  # noqa: BLE001 - row isolation
                                        error = f"lifecycle_repair_failed:{type(exc).__name__}"
                row["attempts"] = int(row.get("attempts", 0) or 0) + 1
                row["updated_at"] = current_time.isoformat()
                if error is None:
                    row.update(
                        {"status": "completed", "outcome": outcome, "last_error": None}
                    )
                    for key in (
                        "next_attempt_at",
                        "exhausted_at",
                        "failure_fingerprint",
                    ):
                        row.pop(key, None)
                else:
                    row.update(
                        {
                            "status": "failed",
                            "last_error": error,
                            "failure_fingerprint": (
                                self._lifecycle_source_fingerprint(*tracker_issue)
                                if tracker_issue is not None
                                else None
                            ),
                        }
                    )
                    if row["attempts"] >= max_attempts:
                        row["status"] = "exhausted"
                        row["exhausted_at"] = current_time.isoformat()
                        row.pop("next_attempt_at", None)
                    else:
                        delay = self._lifecycle_retry_delay(
                            row["attempts"],
                            retry_backoff_seconds=retry_backoff_seconds,
                            retry_max_backoff_seconds=retry_max_backoff_seconds,
                        )
                        row["next_attempt_at"] = (
                            current_time + timedelta(seconds=delay)
                        ).isoformat()
                queue["cursor"] = (index + 1) % record_count if record_count else 0
                self._refresh_lifecycle_summary(
                    queue,
                    now=current_time,
                    scan_errors=(
                        value
                        for value in queue.get("errors", [])
                        if str(value).startswith("scan_failed:")
                    ),
                )
                queue["updated_at"] = current_time.isoformat()
                self._set_lifecycle_state(queue)
            self._refresh_lifecycle_summary(
                queue,
                now=current_time,
                scan_errors=(
                    value
                    for value in queue.get("errors", [])
                    if str(value).startswith("scan_failed:")
                ),
            )
            if eligible:
                queue["updated_at"] = current_time.isoformat()
            self._set_lifecycle_state(queue)
            if prepared_changed or eligible:
                # Outcomes and cursor movement share one checkpoint.  The only
                # extra writes above are the fail-closed intent checkpoints
                # immediately preceding an external tracker mutation.
                self._persist(self._load_root_state())
            return self.lifecycle_reconciliation_status()

    def _finalize_incompatible_shared_epic_merged(
        self,
        store: TerminalAuditMetadataStore,
        tracker: TrackerProtocol,
        issue: Issue,
        project_id: str,
        conflict: str,
        done_records: list[TerminalAuditRecord],
    ) -> bool:
        """Finish metadata/audit retirement after a prior status write.

        This recovery half is separate from the tracker mutation so a process
        crash or metadata outage between the two durable writes can resume
        without issuing a second status mutation.
        """

        identifier = str(issue.identifier)
        now = datetime.now(timezone.utc).isoformat()
        reconciliation_created = False

        def _finalize(current):
            nonlocal reconciliation_created
            unknown = dict(current.unknown_fields)
            chain = [
                replace(record, request_state=RequestState.SUPERSEDED, updated_at=now)
                if (
                    record.project_id == project_id
                    and record.task_id in {identifier, str(getattr(issue, "id", "") or "")}
                    and record.target_state == TargetState.MERGED
                    and record.request_state
                    in {
                        RequestState.PENDING,
                        RequestState.IN_PROGRESS,
                        RequestState.COMPLETED,
                    }
                )
                else record
                for record in current.pending_chain
            ]

            raw_overrides = unknown.get(TERMINAL_OVERRIDE_RECORDS_KEY, [])
            overrides: list[dict[str, Any]] = []
            for raw in raw_overrides if isinstance(raw_overrides, list) else []:
                if not isinstance(raw, Mapping):
                    continue
                item = dict(raw)
                if (
                    item.get("project_id") == project_id
                    and item.get("task_id") == identifier
                    and item.get("target_state") == TargetState.MERGED.value
                ):
                    item.update(
                        {
                            "applied": True,
                            "lifecycle_reconciled": True,
                            "reconciled_to": DONE,
                            "retired_reason": "shared_epic_parent_not_landed",
                            "reconciled_at": now,
                        }
                    )
                overrides.append(item)
            unknown[TERMINAL_OVERRIDE_RECORDS_KEY] = overrides

            raw_retirements = unknown.get(TERMINAL_RETIREMENTS_KEY, [])
            retirements: list[dict[str, Any]] = []
            for raw in raw_retirements if isinstance(raw_retirements, list) else []:
                if not isinstance(raw, Mapping):
                    continue
                item = dict(raw)
                if (
                    item.get("project_id") == project_id
                    and item.get("task_id") == identifier
                    and item.get("target_state") == TargetState.MERGED.value
                ):
                    item.update(
                        {
                            "applied": False,
                            "lifecycle_reconciled": True,
                            "reconciled_to": DONE,
                            "retired_reason": "shared_epic_parent_not_landed",
                        }
                    )
                retirements.append(item)
            unknown[TERMINAL_RETIREMENTS_KEY] = retirements

            raw_intents = unknown.get(TERMINAL_RESULT_INTENTS_KEY, [])
            if isinstance(raw_intents, list):
                unknown[TERMINAL_RESULT_INTENTS_KEY] = [
                    {
                        **dict(raw),
                        "applied": True,
                        "retired_by_reconciliation": True,
                        "retired_reason": "shared_epic_parent_not_landed",
                        "reconciled_at": now,
                    }
                    if (
                        isinstance(raw, Mapping)
                        and raw.get("project_id") == project_id
                        and raw.get("task_id") == identifier
                        and raw.get("target_state") == TargetState.MERGED.value
                    )
                    else raw
                    for raw in raw_intents
                    if isinstance(raw, Mapping)
                ]

            rows = [
                dict(row)
                for row in (unknown.get(LIFECYCLE_RECONCILIATIONS_KEY) or [])
                if isinstance(row, Mapping)
            ]
            if not any(
                row.get("project_id") == project_id
                and row.get("task_id") == identifier
                and row.get("from") == MERGED
                and row.get("to") == DONE
                for row in rows
            ):
                reconciliation_created = True
                rows.append(
                    {
                        "project_id": project_id,
                        "task_id": identifier,
                        "from": MERGED,
                        "to": DONE,
                        "reason": "shared_epic_parent_not_landed",
                        "conflict": conflict,
                        "done_audit_ids": [record.audit_id for record in done_records],
                        "created_at": now,
                    }
                )
            unknown[LIFECYCLE_RECONCILIATIONS_KEY] = rows
            return replace(current, pending_chain=chain, unknown_fields=unknown)

        try:
            store.update(identifier, _finalize)
        except Exception:
            logger.warning(
                "Could not finalize incompatible Merged child repair %s/%s",
                project_id,
                identifier,
                exc_info=True,
            )
            return False
        if reconciliation_created:
            try:
                tracker.add_comment(
                    identifier,
                    f"Lifecycle reconciliation restored {identifier} to audited Done: {conflict}",
                    author="oompah",
                )
            except Exception:
                logger.debug(
                    "Could not post legacy lifecycle reconciliation comment for %s",
                    identifier,
                    exc_info=True,
                )
        return True

    def _reconcile_incompatible_shared_epic_merged(
        self,
        store: TerminalAuditMetadataStore,
        tracker: TrackerProtocol,
        issue: Issue,
        project_id: str,
    ) -> bool:
        """Restore legacy shared children to audited Done before recovery.

        Older service versions could persist a project-owner Merged override
        for a child whose work existed only on the epic branch.  If the child
        has a completed passing Done audit, Done is the safe durable state to
        restore.  The incompatible Merged rows remain in the audit ledger for
        history, while only that child's Merged rows/override/intents are
        retired so unrelated audits are untouched.
        """

        validator = self._validate_terminal_transition
        if validator is None or canonicalize_status(getattr(issue, "state", "")) != MERGED:
            return False

        try:
            conflict = validator(issue, TargetState.MERGED, project_id)
        except Exception:
            logger.warning(
                "Could not classify legacy Merged child %s/%s during recovery",
                project_id,
                issue.identifier,
                exc_info=True,
            )
            return False
        if not isinstance(conflict, str) or not conflict.strip():
            return False

        identifier = str(issue.identifier)
        try:
            document = store.read(identifier)
        except Exception:
            return False
        if document.is_quarantined:
            return False

        done_records = [
            record
            for record in document.pending_chain
            if record.project_id == project_id
            and record.task_id in {identifier, str(getattr(issue, "id", "") or "")}
            and record.target_state == TargetState.DONE
            and record.request_state == RequestState.COMPLETED
            and any(attempt.verdict == Verdict.PASS for attempt in record.attempts)
        ]
        if not done_records:
            return False

        try:
            # The completed Done audit is the evidence for this repair.  Do
            # not reopen implementation work or create a new audit attempt.
            # TERMINAL-AUDIT-ALLOW OOMPAH-725: serialized legacy reconciliation.
            tracker.update_issue(identifier, status=DONE)
        except Exception:
            logger.warning(
                "Could not restore incompatible Merged child %s/%s to Done",
                project_id,
                identifier,
                exc_info=True,
            )
            return False

        now = datetime.now(timezone.utc).isoformat()

        def _finalize(current):
            unknown = dict(current.unknown_fields)
            chain = [
                replace(record, request_state=RequestState.SUPERSEDED, updated_at=now)
                if (
                    record.project_id == project_id
                    and record.task_id in {identifier, str(getattr(issue, "id", "") or "")}
                    and record.target_state == TargetState.MERGED
                    and record.request_state
                    in {
                        RequestState.PENDING,
                        RequestState.IN_PROGRESS,
                        RequestState.COMPLETED,
                    }
                )
                else record
                for record in current.pending_chain
            ]

            raw_overrides = unknown.get(TERMINAL_OVERRIDE_RECORDS_KEY, [])
            overrides: list[dict[str, Any]] = []
            for raw in raw_overrides if isinstance(raw_overrides, list) else []:
                if not isinstance(raw, Mapping):
                    continue
                item = dict(raw)
                if (
                    item.get("project_id") == project_id
                    and item.get("task_id") == identifier
                    and item.get("target_state") == TargetState.MERGED.value
                ):
                    item.update(
                        {
                            "applied": True,
                            "lifecycle_reconciled": True,
                            "reconciled_to": DONE,
                            "retired_reason": "shared_epic_parent_not_landed",
                            "reconciled_at": now,
                        }
                    )
                overrides.append(item)
            unknown[TERMINAL_OVERRIDE_RECORDS_KEY] = overrides

            raw_retirements = unknown.get(TERMINAL_RETIREMENTS_KEY, [])
            retirements: list[dict[str, Any]] = []
            for raw in raw_retirements if isinstance(raw_retirements, list) else []:
                if not isinstance(raw, Mapping):
                    continue
                item = dict(raw)
                if (
                    item.get("project_id") == project_id
                    and item.get("task_id") == identifier
                    and item.get("target_state") == TargetState.MERGED.value
                ):
                    # Keep the historical identity but reopen its fence so a
                    # later, genuinely landed Merged request can proceed.
                    item.update(
                        {
                            "applied": False,
                            "lifecycle_reconciled": True,
                            "reconciled_to": DONE,
                            "retired_reason": "shared_epic_parent_not_landed",
                        }
                    )
                retirements.append(item)
            unknown[TERMINAL_RETIREMENTS_KEY] = retirements

            raw_intents = unknown.get(TERMINAL_RESULT_INTENTS_KEY, [])
            if isinstance(raw_intents, list):
                unknown[TERMINAL_RESULT_INTENTS_KEY] = [
                    {
                        **dict(raw),
                        "applied": True,
                        "retired_by_reconciliation": True,
                        "retired_reason": "shared_epic_parent_not_landed",
                        "reconciled_at": now,
                    }
                    if (
                        isinstance(raw, Mapping)
                        and raw.get("project_id") == project_id
                        and raw.get("task_id") == identifier
                        and raw.get("target_state") == TargetState.MERGED.value
                    )
                    else raw
                    for raw in raw_intents
                    if isinstance(raw, Mapping)
                ]

            rows = [
                dict(row)
                for row in (unknown.get(LIFECYCLE_RECONCILIATIONS_KEY) or [])
                if isinstance(row, Mapping)
            ]
            rows.append(
                {
                    "project_id": project_id,
                    "task_id": identifier,
                    "from": MERGED,
                    "to": DONE,
                    "reason": "shared_epic_parent_not_landed",
                    "conflict": conflict,
                    "done_audit_ids": [record.audit_id for record in done_records],
                    "created_at": now,
                }
            )
            unknown[LIFECYCLE_RECONCILIATIONS_KEY] = rows
            return replace(current, pending_chain=chain, unknown_fields=unknown)

        try:
            store.update(identifier, _finalize)
        except Exception:
            logger.warning(
                "Could not finalize incompatible Merged child repair %s/%s",
                project_id,
                identifier,
                exc_info=True,
            )
            return False

        try:
            tracker.add_comment(
                identifier,
                f"Lifecycle reconciliation restored {identifier} to audited Done: "
                f"{conflict}",
                author="oompah",
            )
        except Exception:
            logger.debug(
                "Could not post legacy lifecycle reconciliation comment for %s",
                identifier,
                exc_info=True,
            )
        logger.warning(
            "Reconciled incompatible shared-epic child %s/%s from Merged to Done",
            project_id,
            identifier,
        )
        return True

    def _recover_terminal_override(
        self,
        store: TerminalAuditMetadataStore,
        tracker: TrackerProtocol,
        issue: Issue,
        project_id: str,
    ) -> None:
        """Apply and complete an owner retirement interrupted at any boundary.

        The override record is written before the tracker mutation.  Recovery
        therefore owns both sides of that hand-off: it retries the terminal
        status while the issue is still In Validation, then retires the live
        audit chain and any older result intents from the current metadata
        document.  If the tracker write succeeded but metadata finalization
        failed, the status is already at (or beyond) the requested target and
        only the durable retirement step is needed.

        An override's evidence fingerprint must match the current canonical
        task evidence to be applicable.  If multiple unapplied overrides
        exist, validated timestamp plus persisted override ID selects one
        deterministically and every other candidate is retired.
        """

        identifier = str(issue.identifier)
        current_fingerprint = compute_issue_evidence_fingerprint(
            issue,
            project_id,
        )
        try:
            document = store.read(identifier)
        except Exception:
            return
        if document.is_quarantined:
            return
        raw_overrides = document.unknown_fields.get(TERMINAL_OVERRIDE_RECORDS_KEY, [])
        if not isinstance(raw_overrides, list):
            return

        valid_candidates: list[tuple[Mapping[str, Any], OverrideRecord]] = []
        retire_reasons: dict[str, str] = {}
        for raw in raw_overrides:
            if not isinstance(raw, Mapping) or raw.get("applied", True):
                continue
            if raw.get("project_id") != project_id or raw.get("task_id") != identifier:
                continue
            override_id = raw.get("override_id")
            if not isinstance(override_id, str) or not override_id:
                continue
            try:
                override = OverrideRecord.from_dict(raw)
            except (TypeError, ValueError):
                retire_reasons[override_id] = "invalid_override_record"
                continue
            if override.evidence_fingerprint != current_fingerprint:
                retire_reasons[override.override_id] = "evidence_mismatch"
                continue
            valid_candidates.append((raw, override))

        selected: tuple[Mapping[str, Any], OverrideRecord] | None = None
        if valid_candidates:
            selected = max(
                valid_candidates,
                key=lambda candidate: _authority_key(
                    candidate[0].get("created_at"),
                    (candidate[1].override_id,),
                ),
            )
            selected_id = selected[1].override_id
            for _raw, override in valid_candidates:
                if override.override_id != selected_id:
                    retire_reasons[override.override_id] = (
                        "superseded_by_newer_override"
                    )

        # Invalid, stale, and superseded rows never receive status authority.
        if not valid_candidates:
            if retire_reasons:
                self._retire_terminal_overrides(
                    store,
                    identifier,
                    project_id,
                    retire_reasons,
                )
            return
        assert selected is not None
        _target_raw, target_override = selected
        target_authority = _authority_key(
            _target_raw.get("created_at"),
            (target_override.override_id,),
        )
        target_state = target_override.target_state.value
        target_status = _target_state_status(target_state)
        assert target_status is not None

        lifecycle_conflict = self._lifecycle_conflict(
            issue, target_override.target_state, project_id
        )
        if lifecycle_conflict is not None:
            self._retire_terminal_overrides(
                store,
                identifier,
                project_id,
                {
                    target_override.override_id: (
                        f"lifecycle_incompatible: {lifecycle_conflict}"
                    )
                },
            )
            return

        current_status = str(getattr(issue, "state", "") or "")
        current_rank = _TERMINAL_STATUS_RANK.get(status_key(current_status), 0)
        target_rank = _TERMINAL_STATUS_RANK.get(status_key(target_status), 0)
        if (
            status_key(current_status) != status_key(target_status)
            and not (current_rank and target_rank and current_rank >= target_rank)
        ):
            try:
                # TERMINAL-AUDIT-ALLOW OOMPAH-483: this status is authorized
                # by the already persisted owner override evidence.
                tracker.update_issue(identifier, status=target_status)
            except Exception:
                logger.warning(
                    "terminal-audit override recovery status write failed for %s/%s",
                    project_id,
                    issue.identifier,
                    exc_info=True,
                )
                if retire_reasons:
                    self._retire_terminal_overrides(
                        store,
                        identifier,
                        project_id,
                        retire_reasons,
                    )
                return
        now = datetime.now(timezone.utc).isoformat()

        def _finalize(document):
            unknown = dict(document.unknown_fields)
            current_overrides = unknown.get(TERMINAL_OVERRIDE_RECORDS_KEY, [])
            overrides: list[dict[str, Any]] = []
            for raw in current_overrides if isinstance(current_overrides, list) else []:
                if not isinstance(raw, Mapping):
                    continue
                item = dict(raw)
                if item.get("applied", True) is not False:
                    overrides.append(item)
                    continue
                if (
                    item.get("project_id") != project_id
                    or item.get("task_id") != identifier
                ):
                    overrides.append(item)
                    continue
                try:
                    current_override = OverrideRecord.from_dict(item)
                except (TypeError, ValueError):
                    item["applied"] = True
                    item["retired_at"] = now
                    item["retired_reason"] = "invalid_override_record"
                    overrides.append(item)
                    continue

                if current_override.evidence_fingerprint != current_fingerprint:
                    item["applied"] = True
                    item["retired_at"] = now
                    item["retired_reason"] = "evidence_mismatch"
                elif current_override == target_override:
                    item["applied"] = True
                    item["applied_at"] = now
                elif (
                    _authority_key(
                        item.get("created_at"),
                        (current_override.override_id,),
                    )
                    <= target_authority
                ):
                    # Re-read classification is intentional.  An override can
                    # be appended after selection and the tracker status write
                    # but before this metadata update acquires its lock.  Only
                    # a strictly newer valid authority may remain actionable.
                    item["applied"] = True
                    item["retired_at"] = now
                    item["retired_reason"] = "superseded_by_newer_override"
                overrides.append(item)
            unknown[TERMINAL_OVERRIDE_RECORDS_KEY] = overrides

            live_ids = [
                record.audit_id
                for record in document.pending_chain
                if record.request_state in PENDING_REQUEST_STATES
            ]
            chain = [
                replace(record, request_state=RequestState.CANCELLED, updated_at=now)
                if record.audit_id in live_ids
                else record
                for record in document.pending_chain
            ]
            retirements = [
                dict(row)
                for row in (unknown.get(TERMINAL_RETIREMENTS_KEY) or [])
                if isinstance(row, Mapping)
            ]
            identity = {
                "project_id": project_id,
                "task_id": identifier,
                "target_state": target_state,
                "evidence_fingerprint": str(current_fingerprint.digest),
            }
            matching = next(
                (
                    row
                    for row in retirements
                    if all(row.get(key) == value for key, value in identity.items())
                ),
                None,
            )
            if matching is None:
                retirements.append(
                    {
                        **identity,
                        "audit_ids": live_ids,
                        "kind": "override",
                        "applied": True,
                        "retired_at": now,
                    }
                )
            else:
                matching["applied"] = True
                matching["kind"] = "override"
                matching["audit_ids"] = list(
                    dict.fromkeys(
                        [
                            *(
                                matching.get("audit_ids", [])
                                if isinstance(matching.get("audit_ids"), list)
                                else []
                            ),
                            *live_ids,
                        ]
                    )
                )
            # An owner override supersedes any result whose tracker status
            # acknowledgement was interrupted.  Otherwise restart recovery
            # could replay an older PASS after the override wins.
            intents = unknown.get(TERMINAL_RESULT_INTENTS_KEY, [])
            if isinstance(intents, list):
                unknown[TERMINAL_RESULT_INTENTS_KEY] = [
                    {
                        **dict(raw),
                        "applied": True,
                        "retired_by_override": True,
                    }
                    for raw in intents
                    if isinstance(raw, Mapping)
                ]
            unknown[TERMINAL_RETIREMENTS_KEY] = retirements
            return replace(document, pending_chain=chain, unknown_fields=unknown)

        try:
            store.update(identifier, _finalize)
        except Exception:
            logger.warning(
                "terminal-audit override recovery failed for %s/%s",
                project_id,
                issue.identifier,
                exc_info=True,
            )

    @staticmethod
    def _retire_terminal_overrides(
        store: TerminalAuditMetadataStore,
        identifier: str,
        project_id: str,
        retire_reasons: Mapping[str, str],
    ) -> None:
        """Retire override rows that cannot receive status authority."""
        now = datetime.now(timezone.utc).isoformat()

        def _finalize(document):
            unknown = dict(document.unknown_fields)
            current_overrides = unknown.get(TERMINAL_OVERRIDE_RECORDS_KEY, [])
            overrides = []
            for raw in current_overrides if isinstance(current_overrides, list) else []:
                if not isinstance(raw, Mapping):
                    continue
                item = dict(raw)
                override_id = item.get("override_id")
                if override_id in retire_reasons:
                    item["applied"] = True
                    item["retired_at"] = now
                    item["retired_reason"] = retire_reasons[override_id]
                overrides.append(item)
            unknown[TERMINAL_OVERRIDE_RECORDS_KEY] = overrides
            return replace(document, unknown_fields=unknown)

        try:
            store.update(identifier, _finalize)
        except Exception:
            logger.warning(
                "terminal-audit override retirement failed for %s/%s",
                project_id,
                identifier,
                exc_info=True,
            )

    def _recover_terminal_result(
        self,
        store: TerminalAuditMetadataStore,
        tracker: TrackerProtocol,
        issue: Issue,
        project_id: str,
    ) -> None:
        """Finish a result whose metadata commit preceded its status write.

        Tracker status and audit metadata are separate stores.  Result
        application records an unapplied intent before calling
        ``update_issue``; this recovery path owns the other half of that
        protocol and is deliberately serialized with coordinator mutations by
        the project lock.
        """

        identifier = str(issue.identifier)
        with self.project_store.project_write_lock(project_id):
            try:
                document = store.read(identifier)
            except Exception:
                return
            if document.is_quarantined:
                return
            raw_overrides = document.unknown_fields.get(TERMINAL_OVERRIDE_RECORDS_KEY, [])
            if any(
                isinstance(raw, Mapping)
                and raw.get("applied", True) is False
                and raw.get("project_id") == project_id
                and raw.get("task_id") == identifier
                for raw in raw_overrides
                if isinstance(raw, Mapping)
            ):
                # An owner override intent is the stronger authority.  Its
                # recovery pass will either finalize it or leave it visible
                # for a later scan; do not replay an older audit underneath it.
                return
            raw_intents = document.unknown_fields.get(TERMINAL_RESULT_INTENTS_KEY, [])
            if not isinstance(raw_intents, list):
                return

            current_status = str(getattr(issue, "state", "") or "")
            current_fingerprint = compute_issue_evidence_fingerprint(
                issue,
                project_id,
            )
            retire_keys: dict[tuple[str, str], str] = {}
            candidates: list[tuple[Mapping[str, Any], TerminalAuditRecord, str]] = []

            for raw_intent in raw_intents:
                if not isinstance(raw_intent, Mapping) or raw_intent.get("applied", True):
                    continue
                if (
                    raw_intent.get("project_id") != project_id
                    or raw_intent.get("task_id") != identifier
                ):
                    continue
                audit_id = raw_intent.get("audit_id")
                attempt_id = raw_intent.get("attempt_id")
                desired_status = raw_intent.get("status")
                identity = (audit_id, attempt_id)
                if not all(
                    isinstance(value, str) and value.strip()
                    for value in (audit_id, attempt_id, desired_status)
                ):
                    continue

                record = next(
                    (item for item in document.pending_chain if item.audit_id == audit_id),
                    None,
                )
                stale_reason: str | None = None
                target_state = _target_state_status(raw_intent.get("target_state"))
                intent_fingerprint: EvidenceFingerprint | None = None
                try:
                    intent_fingerprint = _as_fingerprint(
                        raw_intent.get("evidence_fingerprint")
                    )
                except (TypeError, ValueError):
                    stale_reason = "invalid_evidence_fingerprint"

                if record is None:
                    stale_reason = stale_reason or "missing_audit_record"
                elif record.project_id != project_id or record.task_id != identifier:
                    stale_reason = stale_reason or "audit_identity_mismatch"
                elif target_state is None or status_key(target_state) != status_key(
                    record.target_state.value
                ):
                    stale_reason = stale_reason or "target_mismatch"
                elif record.target_state == TargetState.MERGED:
                    stale_reason = self._lifecycle_conflict(
                        issue, record.target_state, project_id
                    )
                if stale_reason is None and (
                    intent_fingerprint is None
                    or intent_fingerprint != record.evidence_fingerprint
                ):
                    stale_reason = stale_reason or "audit_evidence_mismatch"
                elif stale_reason is None and current_fingerprint != record.evidence_fingerprint:
                    # The task was revised after the result was persisted.
                    # Never replay a terminal status for an obsolete revision.
                    stale_reason = "current_evidence_mismatch"
                elif stale_reason is None and record.request_state in (
                    RequestState.SUPERSEDED,
                    RequestState.CANCELLED,
                ):
                    stale_reason = "audit_record_retired"
                elif stale_reason is None and record.request_state != RequestState.COMPLETED:
                    # The result intent may be ahead of the record write.  It
                    # is not stale, but it is not replayable until completion
                    # is visible in the same durable document.
                    continue

                if stale_reason is not None:
                    retire_keys[identity] = stale_reason
                    continue
                assert record is not None
                candidates.append((raw_intent, record, desired_status))

            # The newest valid intent is the only result allowed to acquire
            # tracker-status authority.  Equal/malformed timestamps use the
            # stable audit/attempt identity, never ledger list position.
            selected: tuple[Mapping[str, Any], TerminalAuditRecord, str] | None = None
            if candidates:
                selected = max(
                    candidates,
                    key=lambda candidate: _authority_key(
                        candidate[0].get("created_at"),
                        (
                            str(candidate[0]["audit_id"]),
                            str(candidate[0]["attempt_id"]),
                        ),
                    ),
                )

            if selected is not None:
                selected_intent, _selected_record, desired_status = selected
                selected_key = (
                    str(selected_intent["audit_id"]),
                    str(selected_intent["attempt_id"]),
                )
                for raw_intent, _record, _status in candidates:
                    if (
                        str(raw_intent["audit_id"]),
                        str(raw_intent["attempt_id"]),
                    ) != selected_key:
                        retire_keys[(str(raw_intent["audit_id"]), str(raw_intent["attempt_id"]))] = (
                            "superseded_by_newer_intent"
                        )
                if status_key(current_status) != status_key(desired_status):
                    current_rank = _TERMINAL_STATUS_RANK.get(status_key(current_status), 0)
                    desired_rank = _TERMINAL_STATUS_RANK.get(status_key(desired_status), 0)
                    if not (
                        current_rank
                        and desired_rank
                        and current_rank >= desired_rank
                    ):
                        try:
                            # TERMINAL-AUDIT-ALLOW OOMPAH-483: replay only a
                            # current, completed terminal-audit decision.
                            tracker.update_issue(identifier, status=desired_status)
                        except Exception:
                            logger.warning(
                                "terminal-audit result recovery status write failed for %s/%s",
                                project_id,
                                identifier,
                                exc_info=True,
                            )
                            # Retire independently proven stale/superseded
                            # intents even when the selected status write is
                            # temporarily unavailable.
                            if retire_keys:
                                self._retire_result_intents(
                                    store, identifier, project_id, retire_keys
                                )
                            return
                    else:
                        retire_keys[selected_key] = "status_already_advanced"
                retire_keys[selected_key] = retire_keys.get(
                    selected_key, "recovered_current_intent"
                )

            if not retire_keys:
                return
            self._retire_result_intents(store, identifier, project_id, retire_keys)

    @staticmethod
    def _retire_result_intents(
        store: TerminalAuditMetadataStore,
        identifier: str,
        project_id: str,
        retire_keys: Mapping[tuple[str, str], str],
    ) -> None:
        """Mark stale or replayed result intents retired from current metadata."""

        now = datetime.now(timezone.utc).isoformat()

        def _finalize(current):
            unknown = dict(current.unknown_fields)
            current_intents = unknown.get(TERMINAL_RESULT_INTENTS_KEY, [])
            if isinstance(current_intents, list):
                updated_intents = []
                for raw in current_intents:
                    if not isinstance(raw, Mapping):
                        continue
                    item = dict(raw)
                    key = (item.get("audit_id"), item.get("attempt_id"))
                    if (
                        item.get("project_id") == project_id
                        and item.get("task_id") == identifier
                        and key in retire_keys
                    ):
                        item["applied"] = True
                        item["retired_at"] = now
                        item["retired_reason"] = retire_keys[key]
                        if retire_keys[key] != "recovered_current_intent":
                            item["retired_by_recovery"] = True
                    updated_intents.append(item)
                unknown[TERMINAL_RESULT_INTENTS_KEY] = updated_intents
            return replace(current, unknown_fields=unknown)

        try:
            store.update(identifier, _finalize)
        except Exception:
            logger.warning(
                "terminal-audit result recovery finalization failed for %s/%s",
                project_id,
                identifier,
                exc_info=True,
            )

    def _initialize(
        self,
        scopes: Iterable[tuple[str, TrackerProtocol]],
        *,
        defer_lifecycle_reconciliation: bool = False,
    ) -> dict[str, Any]:
        """Initialize or reconcile enforcement and recover pending audits."""

        raw_scopes = scopes.items() if isinstance(scopes, Mapping) else scopes
        scope_list = [(str(project_id), tracker) for project_id, tracker in raw_scopes]
        root = self._load_root_state()
        loaded = self._load_enforcement_state(root)
        first_startup = loaded is None
        self.errors = list(dict.fromkeys([*self.errors, *(loaded.errors if loaded else [])]))
        if loaded is not None:
            self.state = loaded
        self._state_loaded = True
        current, scan_complete = self._current_tasks(scope_list)
        if first_startup and scan_complete and not self._state_corrupt:
            self.state = TerminalAuditEnforcementState(
                grandfathered=[
                    self._tuple_for(project_id, issue, fingerprint)
                    for project_id, _tracker, issue, fingerprint in current
                    if self._is_terminal(str(getattr(issue, "state", "") or ""))
                ],
                pending_audits=[],
                errors=list(self.errors),
            )
        elif first_startup or self.state.quarantined or not scan_complete:
            # An incomplete or corrupt snapshot must not be treated as an
            # empty baseline: doing so would silently grandfather work we did
            # not inspect.  Queue observed terminal tasks and remain visible.
            self.state.baseline_initialized = False
            self.state.quarantined = True
            for project_id, _tracker, issue, fingerprint in current:
                if self._is_terminal(str(getattr(issue, "state", "") or "")):
                    observed = self._tuple_for(project_id, issue, fingerprint)
                    self.state.invalidated.append(observed)
        else:
            self._reconcile_current(
                current,
                scope_project_ids=(project_id for project_id, _tracker in scope_list),
            )
        self.state.errors = list(dict.fromkeys([*self.state.errors, *self.errors]))
        self.recover_pending_audits(
            scope_list,
            persist=False,
            reconcile_lifecycle=not defer_lifecycle_reconciliation,
        )
        self.state.errors = list(dict.fromkeys([*self.state.errors, *self.errors]))
        self._persist(root)
        completed_scan = scan_complete and self._recovery_scan_complete
        self.last_result = {
            "first_startup": first_startup,
            "baseline_initialized": self.state.baseline_initialized,
            "quarantined": self.state.quarantined or self._state_corrupt,
            "grandfathered": len(self.state.grandfathered),
            "pending_audits": len(self.pending_audits),
            "scan_complete": completed_scan,
            "scan_error_count": (
                (0 if scan_complete else 1) + self._recovery_scan_error_count
            ),
            "errors": list(self.state.errors),
            "lifecycle_reconciliation": self.lifecycle_reconciliation_status(),
        }
        return dict(self.last_result)

    def initialize(
        self,
        scopes: Iterable[tuple[str, TrackerProtocol]],
        *,
        defer_lifecycle_reconciliation: bool = False,
    ) -> dict[str, Any]:
        """Initialize enforcement while serializing durable lifecycle state."""

        # Periodic terminal-audit recovery and lifecycle repair share one
        # state document.  Keep their load/scan/persist transactions ordered
        # so a maintenance scan cannot overwrite a batch cursor or mutation
        # intent while the tracker write is in flight.  This lock is never
        # taken by lifecycle_reconciliation_status(), which keeps state reads
        # responsive during a slow tracker call.
        with self._lifecycle_lock:
            return self._initialize(
                scopes,
                defer_lifecycle_reconciliation=defer_lifecycle_reconciliation,
            )

    # Names used by startup-oriented callers and tests.
    startup = initialize
    initialize_grandfather_baseline = initialize
    snapshot_existing_terminal_tasks = initialize

    def is_grandfathered(
        self,
        project_id: str,
        issue: Issue,
        fingerprint: EvidenceFingerprint | str | Mapping[str, Any] | None = None,
    ) -> bool:
        """Return whether *issue* still matches the persisted baseline."""

        current_fingerprint = (
            _as_fingerprint(fingerprint)
            if fingerprint is not None
            else _as_fingerprint(getattr(issue, "evidence_fingerprint"))
            if getattr(issue, "evidence_fingerprint", None) is not None
            else compute_issue_evidence_fingerprint(issue, str(project_id))
        )
        key = _task_key(project_id, str(issue.identifier))
        return any(
            entry.key == key
            and entry.matches(str(getattr(issue, "state", "") or ""), current_fingerprint)
            for entry in self.state.grandfathered
        ) and not any(entry.key == key for entry in self.state.invalidated)

    def mark_audit_passed(
        self,
        project_id: str,
        issue: Issue,
        fingerprint: EvidenceFingerprint | str | Mapping[str, Any],
    ) -> None:
        """Promote a freshly audited terminal task into the active baseline."""

        entry = self._tuple_for(str(project_id), issue, _as_fingerprint(fingerprint))
        self.state.grandfathered = [item for item in self.state.grandfathered if item.key != entry.key]
        self.state.grandfathered.append(entry)
        self.state.invalidated = [item for item in self.state.invalidated if item.key != entry.key]
        self.pending_audits = [
            item
            for item in self.pending_audits
            if not (item.project_id == entry.project_id and item.task_id == entry.task_id)
        ]
        self.state.pending_audits = list(self.pending_audits)
        self._persist(self._load_root_state())


# Compatibility/readability alias for callers that prefer coordinator wording.
TerminalAuditEnforcementCoordinator = TerminalAuditEnforcement


__all__ = [
    "GrandfatherTuple",
    "PendingAudit",
    "SERVICE_STATE_KEY",
    "SERVICE_STATE_VERSION",
    "TerminalAuditEnforcement",
    "TerminalAuditEnforcementCoordinator",
    "TerminalAuditEnforcementState",
    "get_recovery_snapshot",
]
