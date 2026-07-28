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
import hashlib
import json
import logging
import os
import tempfile
import threading
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from oompah.models import Issue
from oompah.statuses import IN_VALIDATION, canonicalize_status, status_key
from oompah.terminal_audit import (
    EvidenceFingerprint,
    RequestState,
    TerminalAuditRecord,
    TargetState,
    compute_evidence_fingerprint,
)
from oompah.terminal_audit_metadata import (
    TerminalAuditMetadataStore,
    TerminalAuditMetadataQuarantinedError,
)
from oompah.tracker import TrackerProtocol


logger = logging.getLogger(__name__)

SERVICE_STATE_KEY = "terminal_audit_enforcement"
SERVICE_STATE_VERSION = 1
PENDING_REQUEST_STATES = frozenset({RequestState.PENDING, RequestState.IN_PROGRESS})

_STATE_LOCK_GUARD = threading.Lock()
_STATE_LOCKS: dict[str, threading.RLock] = {}


def _state_lock(path: str) -> threading.RLock:
    with _STATE_LOCK_GUARD:
        return _STATE_LOCKS.setdefault(os.path.abspath(path), threading.RLock())


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

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SERVICE_STATE_VERSION,
            "baseline_initialized": self.baseline_initialized,
            "grandfathered": [entry.to_dict() for entry in self.grandfathered],
            "invalidated": [entry.to_dict() for entry in self.invalidated],
            "pending_audits": [entry.to_dict() for entry in self.pending_audits],
            "quarantined": self.quarantined,
            "errors": list(dict.fromkeys(self.errors)),
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
        return cls(
            grandfathered=[GrandfatherTuple.from_dict(value) for value in raw_grandfathered],
            invalidated=[GrandfatherTuple.from_dict(value) for value in raw_invalidated],
            pending_audits=[PendingAudit.from_dict(value) for value in raw_pending],
            baseline_initialized=bool(raw.get("baseline_initialized", True)),
            quarantined=bool(raw.get("quarantined", False)),
            errors=list(errors),
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
    ) -> None:
        self.state_path = state_path or service_state_path
        if self.state_path is None and load_state is None:
            raise ValueError("state_path or load_state is required")
        self.terminal_states = tuple(str(value) for value in terminal_states)
        self.project_store = project_store or _NoopProjectStore()
        self._load_state_callback = load_state
        self._save_state_callback = save_state
        self.state = TerminalAuditEnforcementState()
        self.pending_audits: list[PendingAudit] = []
        self.errors: list[str] = []
        self.last_result: dict[str, Any] = {}
        self._state_corrupt = False

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

    def _persist(self, root: Mapping[str, Any]) -> None:
        if self._state_corrupt:
            logger.error(
                "terminal-audit enforcement state is quarantined; refusing to overwrite corrupt service state"
            )
            return
        payload = self.state.to_dict()
        if self._save_state_callback is not None:
            try:
                self._save_state_callback({SERVICE_STATE_KEY: payload})
            except Exception as exc:  # pragma: no cover - defensive callback boundary
                self._error("service_state_write_failed", exc)
            return
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
        # particular, reading a terminal task must never create an audit record.
        try:
            metadata = tracker.get_metadata(issue.identifier) or {}
            for key in ("oompah.evidence_fingerprint", "evidence_fingerprint"):
                if metadata.get(key) is not None:
                    return _as_fingerprint(metadata[key])
            raw_audit = metadata.get("oompah.terminal_audit")
            if isinstance(raw_audit, Mapping):
                raw_chain = raw_audit.get("pending_chain", [])
                if isinstance(raw_chain, list):
                    for raw_record in raw_chain:
                        if isinstance(raw_record, Mapping):
                            try:
                                return _fingerprint_from_raw(raw_record)
                            except ValueError:
                                continue
        except Exception as exc:  # fail closed below, with an observable marker
            self._error("evidence_read_failed", exc)

        contributors = getattr(issue, "contributors", ()) or ()
        if isinstance(contributors, str):
            contributors = (contributors,)
        child_digests = getattr(issue, "child_audit_digests", ()) or ()
        if isinstance(child_digests, str):
            child_digests = (child_digests,)
        return compute_evidence_fingerprint(
            requirements_text=str(getattr(issue, "description", None) or ""),
            project_id=str(project_id or getattr(issue, "project_id", None) or ""),
            task_id=str(getattr(issue, "identifier", "")),
            source_branch=str(
                getattr(issue, "source_branch", None)
                or getattr(issue, "work_branch", None)
                or getattr(issue, "branch_name", None)
                or ""
            ),
            source_sha=str(getattr(issue, "source_sha", None) or ""),
            target_branch=str(getattr(issue, "target_branch", None) or ""),
            target_sha=str(getattr(issue, "target_sha", None) or ""),
            review_id=str(
                getattr(issue, "review_id", None)
                or getattr(issue, "review_number", None)
                or ""
            ),
            review_state=str(getattr(issue, "review_state", None) or ""),
            child_audit_digests=child_digests,
            contributors=contributors,
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

    def _is_terminal(self, state: str) -> bool:
        wanted = {status_key(value) for value in self.terminal_states}
        return status_key(state) in wanted

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
    ) -> None:
        baseline = {entry.key: entry for entry in self.state.grandfathered}
        invalidated = {entry.key: entry for entry in self.state.invalidated}
        for project_id, _tracker, issue, fingerprint in current:
            key = _task_key(project_id, str(issue.identifier))
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
                self._queue_for_tuple(observed)
            elif not any(item.key == prior_invalidated.key for item in self.pending_audits):
                self._queue_for_tuple(prior_invalidated)
        self.state.grandfathered = list(baseline.values())
        self.state.invalidated = list(invalidated.values())

    def recover_pending_audits(
        self, scopes: Iterable[tuple[str, TrackerProtocol]], *, persist: bool = True
    ) -> list[PendingAudit]:
        """Recover pending/in-progress records from ``In Validation`` metadata.

        Recovery is intentionally read-only for valid metadata.  Existing
        ``AuditAttempt`` IDs are copied into the queue, never regenerated, so
        a restart cannot duplicate an auditor attempt.
        """

        raw_scopes = scopes.items() if isinstance(scopes, Mapping) else scopes
        for project_id, tracker in raw_scopes:
            try:
                issues = [
                    issue
                    for issue in self._all_issues(tracker)
                    if status_key(getattr(issue, "state", "")) == status_key(IN_VALIDATION)
                ]
            except Exception as exc:
                self._error(f"validation_scan_failed:{project_id}", exc)
                continue
            store = TerminalAuditMetadataStore(
                tracker, self.project_store, str(project_id)
            )
            for issue in issues:
                try:
                    document = store.read(str(issue.identifier))
                except TerminalAuditMetadataQuarantinedError:
                    self._error(f"metadata_quarantined:{project_id}:{issue.identifier}")
                    continue
                except Exception as exc:
                    self._error(f"metadata_read_failed:{project_id}:{issue.identifier}", exc)
                    continue
                if document.is_quarantined:
                    self._error(f"metadata_quarantined:{project_id}:{issue.identifier}")
                    continue
                for record in document.pending_chain:
                    if record.project_id != str(project_id) or record.task_id != str(issue.identifier):
                        self._error(f"metadata_identity_mismatch:{project_id}:{issue.identifier}")
                        continue
                    if record.request_state in PENDING_REQUEST_STATES:
                        self._queue_record(record)
        self.pending_audits = self._dedupe_pending(self.pending_audits)
        self.state.pending_audits = list(self.pending_audits)
        if persist:
            self._persist(self._load_root_state())
        return list(self.pending_audits)

    def initialize(
        self, scopes: Iterable[tuple[str, TrackerProtocol]]
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
            self.pending_audits = self._dedupe_pending(loaded.pending_audits)
        current, scan_complete = self._current_tasks(scope_list)
        if first_startup and scan_complete and not self._state_corrupt:
            self.state = TerminalAuditEnforcementState(
                grandfathered=[
                    self._tuple_for(project_id, issue, fingerprint)
                    for project_id, _tracker, issue, fingerprint in current
                    if self._is_terminal(str(getattr(issue, "state", "") or ""))
                ],
                pending_audits=list(self.pending_audits),
                errors=list(self.errors),
            )
            self.pending_audits = list(self.state.pending_audits)
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
                    self._queue_for_tuple(observed)
        else:
            self._reconcile_current(current)
        self.state.errors = list(dict.fromkeys([*self.state.errors, *self.errors]))
        self.pending_audits = self._dedupe_pending(self.pending_audits)
        self.state.pending_audits = list(self.pending_audits)
        self.recover_pending_audits(scope_list, persist=False)
        self.state.errors = list(dict.fromkeys([*self.state.errors, *self.errors]))
        self._persist(root)
        self.last_result = {
            "first_startup": first_startup,
            "baseline_initialized": self.state.baseline_initialized,
            "quarantined": self.state.quarantined or self._state_corrupt,
            "grandfathered": len(self.state.grandfathered),
            "pending_audits": len(self.pending_audits),
            "errors": list(self.state.errors),
        }
        return dict(self.last_result)

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
            else compute_evidence_fingerprint(
                requirements_text=str(getattr(issue, "description", None) or ""),
                project_id=str(project_id),
                task_id=str(issue.identifier),
            )
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
]
