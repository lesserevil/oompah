"""Tracker-backed persistence for terminal-audit state.

The terminal-audit domain types deliberately do not know where they are
stored.  This module is their single tracker-facing persistence boundary.  It
stores a small, versioned document in ``oompah.terminal_audit`` and never
derives audit state from human comments.

All read-modify-write operations acquire the owning project's write lock.
That matters for polling: two concurrent audit workers must not overwrite one
another's attempt history after each has read an earlier document.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from typing import Any, Protocol

from oompah.terminal_audit import AuditAttempt, TerminalAuditRecord
from oompah.tracker import TrackerProtocol


METADATA_KEY = "oompah.terminal_audit"
"""The one tracker metadata field owned by the terminal-audit coordinator."""

METADATA_VERSION = 1
"""Current version of the terminal-audit metadata envelope."""

DEFAULT_MAX_ATTEMPT_HISTORY = 50
"""Maximum retained audit attempts, both globally and per pending record."""

_REDACTED = "[REDACTED]"
_SENSITIVE_KEY_RE = re.compile(
    r"(?:api[_-]?key|authorization|credential|password|secret|token|"
    r"prompt|response|completion|diff)",
    re.IGNORECASE,
)
_SENSITIVE_VALUE_RE = re.compile(
    r"(?:\bbearer\s+\S+|"
    r"\b(?:api[_-]?key|authorization|password|secret|token)\b\s*[:=]\s*\S+|"
    r"\bgh[pousr]_[A-Za-z0-9_]+\b|\bglpat-[A-Za-z0-9_-]+\b)",
    re.IGNORECASE,
)
_MODEL_PROSE_RE = re.compile(r"\b(?:assistant|model)\s+(?:response|output)\b", re.IGNORECASE)
_MAX_PERSISTED_TEXT_LENGTH = 512


class ProjectWriteLockProvider(Protocol):
    """The narrow project-store surface needed for serialized updates."""

    def project_write_lock(self, project_id: str) -> Any:
        """Return a context-manager-compatible reentrant write lock."""


class TerminalAuditMetadataError(ValueError):
    """Raised when a terminal-audit metadata document is invalid."""


class TerminalAuditMetadataQuarantinedError(TerminalAuditMetadataError):
    """Raised when a caller tries to mutate state quarantined as malformed."""


@dataclass(frozen=True)
class MetadataQuarantine:
    """A safe marker for a malformed document, without retaining its contents."""

    fingerprint: str
    reason: str = "malformed terminal-audit metadata"

    def __post_init__(self) -> None:
        if (
            not isinstance(self.fingerprint, str)
            or len(self.fingerprint) != 64
            or any(character not in "0123456789abcdef" for character in self.fingerprint)
        ):
            raise TerminalAuditMetadataError("quarantine fingerprint must be a SHA-256 digest")
        if not isinstance(self.reason, str) or not self.reason:
            raise TerminalAuditMetadataError("quarantine reason must be a non-empty string")

    def to_dict(self) -> dict[str, str | int]:
        return {
            "version": METADATA_VERSION,
            "reason": self.reason,
            "fingerprint": self.fingerprint,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "MetadataQuarantine":
        if not isinstance(raw, Mapping):
            raise TerminalAuditMetadataError("quarantine must be a mapping")
        if raw.get("version") != METADATA_VERSION:
            raise TerminalAuditMetadataError("unsupported quarantine version")
        fingerprint = raw.get("fingerprint")
        reason = raw.get("reason")
        if not isinstance(fingerprint, str) or not isinstance(reason, str):
            raise TerminalAuditMetadataError("quarantine requires fingerprint and reason")
        return cls(fingerprint=fingerprint, reason=reason)


@dataclass
class TerminalAuditMetadata:
    """The durable terminal-audit metadata envelope.

    ``pending_chain`` holds the ordered target requests. ``attempt_history``
    is a bounded cross-chain audit ledger useful for recovery and deduplication.
    ``unknown_fields`` and ``_raw`` retain forward-compatible fields while a
    current coordinator updates known fields.
    """

    pending_chain: list[TerminalAuditRecord] = field(default_factory=list)
    attempt_history: list[AuditAttempt] = field(default_factory=list)
    quarantine: MetadataQuarantine | None = None
    unknown_fields: dict[str, Any] = field(default_factory=dict, repr=False)
    _raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.pending_chain, list) or not all(
            isinstance(record, TerminalAuditRecord) for record in self.pending_chain
        ):
            raise TerminalAuditMetadataError(
                "pending_chain must be a list of TerminalAuditRecord"
            )
        if not isinstance(self.attempt_history, list) or not all(
            isinstance(attempt, AuditAttempt) for attempt in self.attempt_history
        ):
            raise TerminalAuditMetadataError(
                "attempt_history must be a list of AuditAttempt"
            )
        if self.quarantine is not None and not isinstance(
            self.quarantine, MetadataQuarantine
        ):
            raise TerminalAuditMetadataError("quarantine must be MetadataQuarantine or null")
        if not isinstance(self.unknown_fields, dict):
            raise TerminalAuditMetadataError("unknown_fields must be a dictionary")

    @property
    def is_quarantined(self) -> bool:
        """Whether this document must fail closed until an operator resolves it."""

        return self.quarantine is not None

    @classmethod
    def empty(cls) -> "TerminalAuditMetadata":
        """Return the empty document used when tracker metadata is absent."""

        return cls()

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "TerminalAuditMetadata":
        """Decode a metadata envelope while retaining unknown future fields."""

        if not isinstance(raw, Mapping):
            raise TerminalAuditMetadataError("terminal-audit metadata must be a mapping")
        if raw.get("version") != METADATA_VERSION:
            raise TerminalAuditMetadataError("unsupported terminal-audit metadata version")

        raw_chain = raw.get("pending_chain", [])
        raw_history = raw.get("attempt_history", [])
        if not isinstance(raw_chain, list):
            raise TerminalAuditMetadataError("pending_chain must be a list")
        if not isinstance(raw_history, list):
            raise TerminalAuditMetadataError("attempt_history must be a list")

        quarantine_raw = raw.get("quarantine")
        known_keys = {"version", "pending_chain", "attempt_history", "quarantine"}
        return cls(
            pending_chain=[TerminalAuditRecord.from_dict(item) for item in raw_chain],
            attempt_history=[AuditAttempt.from_dict(item) for item in raw_history],
            quarantine=(
                MetadataQuarantine.from_dict(quarantine_raw)
                if quarantine_raw is not None
                else None
            ),
            unknown_fields={
                str(key): copy.deepcopy(value)
                for key, value in raw.items()
                if key not in known_keys
            },
            _raw=copy.deepcopy(dict(raw)),
        )

    def to_dict(self) -> dict[str, Any]:
        """Encode the envelope, preserving unknown fields at every known level."""

        result = copy.deepcopy(self.unknown_fields)
        result.update(
            {
                "version": METADATA_VERSION,
                "pending_chain": _merge_serialized_list(
                    self._raw.get("pending_chain"),
                    self.pending_chain,
                    "audit_id",
                ),
                "attempt_history": _merge_serialized_list(
                    self._raw.get("attempt_history"),
                    self.attempt_history,
                    "attempt_id",
                ),
            }
        )
        if self.quarantine is not None:
            result["quarantine"] = self.quarantine.to_dict()
        else:
            result.pop("quarantine", None)
        return _redact_for_storage(result)

    def bounded(self, max_attempt_history: int) -> "TerminalAuditMetadata":
        """Return a copy retaining only the newest configured number of attempts."""

        _validate_max_attempt_history(max_attempt_history)
        bounded_chain = [
            replace(record, attempts=list(record.attempts[-max_attempt_history:]))
            for record in self.pending_chain
        ]
        return replace(
            self,
            pending_chain=bounded_chain,
            attempt_history=list(self.attempt_history[-max_attempt_history:]),
        )


class TerminalAuditMetadataStore:
    """Read and mutate :data:`METADATA_KEY` through tracker metadata methods.

    The supplied project store provides the existing per-project lock.  The
    lock covers tracker reads and writes, not just the final write, so two
    appenders cannot silently discard one another's attempts.
    """

    def __init__(
        self,
        tracker: TrackerProtocol,
        project_store: ProjectWriteLockProvider,
        project_id: str,
        *,
        max_attempt_history: int = DEFAULT_MAX_ATTEMPT_HISTORY,
    ) -> None:
        if not isinstance(project_id, str) or not project_id.strip():
            raise ValueError("project_id must be a non-empty string")
        _validate_max_attempt_history(max_attempt_history)
        self._tracker = tracker
        self._project_store = project_store
        self._project_id = project_id
        self._max_attempt_history = max_attempt_history

    def read(self, identifier: str) -> TerminalAuditMetadata:
        """Read the current document, safely quarantining malformed payloads."""

        with self._project_store.project_write_lock(self._project_id):
            return self._read_unlocked(identifier)

    def write(self, identifier: str, document: TerminalAuditMetadata) -> bool:
        """Persist *document* when it differs, returning whether a write occurred."""

        if not isinstance(document, TerminalAuditMetadata):
            raise TypeError("document must be TerminalAuditMetadata")
        with self._project_store.project_write_lock(self._project_id):
            current = self._read_unlocked(identifier)
            self._raise_if_quarantined(current)
            return self._write_unlocked(identifier, document)

    def update(
        self,
        identifier: str,
        updater: Callable[[TerminalAuditMetadata], TerminalAuditMetadata],
    ) -> TerminalAuditMetadata:
        """Atomically apply *updater* and return the resulting document."""

        with self._project_store.project_write_lock(self._project_id):
            current = self._read_unlocked(identifier)
            self._raise_if_quarantined(current)
            updated = updater(copy.deepcopy(current))
            if not isinstance(updated, TerminalAuditMetadata):
                raise TypeError("terminal-audit metadata updater must return TerminalAuditMetadata")
            self._write_unlocked(identifier, updated)
            return updated.bounded(self._max_attempt_history)

    def upsert_pending_audit(
        self, identifier: str, record: TerminalAuditRecord
    ) -> TerminalAuditMetadata:
        """Add or replace one pending-chain record by ``audit_id`` atomically."""

        if not isinstance(record, TerminalAuditRecord):
            raise TypeError("record must be TerminalAuditRecord")

        def _upsert(document: TerminalAuditMetadata) -> TerminalAuditMetadata:
            chain = list(document.pending_chain)
            index = next(
                (i for i, existing in enumerate(chain) if existing.audit_id == record.audit_id),
                None,
            )
            if index is None:
                chain.append(record)
            else:
                chain[index] = record
            return replace(document, pending_chain=chain)

        return self.update(identifier, _upsert)

    def append_attempt(
        self, identifier: str, attempt: AuditAttempt
    ) -> TerminalAuditMetadata:
        """Append or replace an attempt by ID without losing concurrent appends."""

        if not isinstance(attempt, AuditAttempt):
            raise TypeError("attempt must be AuditAttempt")

        def _append(document: TerminalAuditMetadata) -> TerminalAuditMetadata:
            history = [
                existing
                for existing in document.attempt_history
                if existing.attempt_id != attempt.attempt_id
            ]
            history.append(attempt)
            return replace(document, attempt_history=history)

        return self.update(identifier, _append)

    # A descriptive alias matches coordinator wording without adding a second
    # persistence path.
    append_audit_attempt = append_attempt

    def _read_unlocked(self, identifier: str) -> TerminalAuditMetadata:
        raw = (self._tracker.get_metadata(identifier) or {}).get(METADATA_KEY)
        if raw is None:
            return TerminalAuditMetadata.empty()
        try:
            return TerminalAuditMetadata.from_dict(raw)
        except (TypeError, ValueError, TerminalAuditMetadataError):
            quarantine = TerminalAuditMetadata(
                quarantine=MetadataQuarantine(fingerprint=_fingerprint_raw(raw))
            )
            # Do not retain malformed contents or exception text: either can
            # include credentials or model prose.  This is deliberately the
            # only write performed by a read path, and it occurs once because
            # a valid quarantine document parses successfully on later polls.
            self._write_raw_if_changed_unlocked(identifier, quarantine.to_dict(), raw)
            return quarantine

    def _write_unlocked(self, identifier: str, document: TerminalAuditMetadata) -> bool:
        serialized = document.bounded(self._max_attempt_history).to_dict()
        current_raw = (self._tracker.get_metadata(identifier) or {}).get(METADATA_KEY)
        return self._write_raw_if_changed_unlocked(identifier, serialized, current_raw)

    def _write_raw_if_changed_unlocked(
        self, identifier: str, serialized: dict[str, Any], current_raw: object
    ) -> bool:
        if current_raw == serialized:
            return False
        self._tracker.set_metadata_field(identifier, METADATA_KEY, serialized)
        return True

    @staticmethod
    def _raise_if_quarantined(document: TerminalAuditMetadata) -> None:
        if document.quarantine is not None:
            raise TerminalAuditMetadataQuarantinedError(
                "terminal-audit metadata is quarantined; resolve it before mutating audit state"
            )


def read_terminal_audit_metadata(
    tracker: TrackerProtocol,
    project_store: ProjectWriteLockProvider,
    project_id: str,
    identifier: str,
    *,
    max_attempt_history: int = DEFAULT_MAX_ATTEMPT_HISTORY,
) -> TerminalAuditMetadata:
    """Convenience wrapper for a one-off tracker-neutral metadata read."""

    return TerminalAuditMetadataStore(
        tracker, project_store, project_id, max_attempt_history=max_attempt_history
    ).read(identifier)


def write_terminal_audit_metadata(
    tracker: TrackerProtocol,
    project_store: ProjectWriteLockProvider,
    project_id: str,
    identifier: str,
    document: TerminalAuditMetadata,
    *,
    max_attempt_history: int = DEFAULT_MAX_ATTEMPT_HISTORY,
) -> bool:
    """Convenience wrapper for a one-off tracker-neutral metadata write."""

    return TerminalAuditMetadataStore(
        tracker, project_store, project_id, max_attempt_history=max_attempt_history
    ).write(identifier, document)


def _merge_serialized_list(
    raw_items: object,
    items: list[TerminalAuditRecord] | list[AuditAttempt] | list[Mapping[str, Any]],
    key: str,
) -> list[dict[str, Any]]:
    existing = {
        value[key]: value
        for value in raw_items
        if isinstance(value, Mapping) and isinstance(value.get(key), str)
    } if isinstance(raw_items, list) else {}
    serialized: list[dict[str, Any]] = []
    for item in items:
        current = dict(item) if isinstance(item, Mapping) else item.to_dict()
        identifier = item.get(key) if isinstance(item, Mapping) else getattr(item, key)
        serialized.append(_merge_serialized_mapping(existing.get(identifier), current))
    return serialized


def _merge_serialized_mapping(
    raw: Mapping[str, Any] | None, current: Mapping[str, Any]
) -> dict[str, Any]:
    """Overlay known current fields without dropping unknown nested fields."""

    merged = copy.deepcopy(dict(raw)) if isinstance(raw, Mapping) else {}
    for key, value in current.items():
        raw_value = merged.get(key)
        if isinstance(value, Mapping):
            merged[key] = _merge_serialized_mapping(
                raw_value if isinstance(raw_value, Mapping) else None, value
            )
        elif key == "attempts" and isinstance(value, list):
            merged[key] = _merge_serialized_list(raw_value, value, "attempt_id")
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _validate_max_attempt_history(value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("max_attempt_history must be a positive integer")


def _fingerprint_raw(raw: object) -> str:
    try:
        encoded = json.dumps(raw, sort_keys=True, separators=(",", ":"), default=repr)
    except (TypeError, ValueError):
        encoded = repr(type(raw).__name__)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _redact_for_storage(value: Any, key: str | None = None) -> Any:
    """Return JSON-safe metadata without credentials or model-response prose."""

    if key is not None and _SENSITIVE_KEY_RE.search(key):
        return _REDACTED
    if isinstance(value, Mapping):
        return {
            str(child_key): _redact_for_storage(child_value, str(child_key))
            for child_key, child_value in value.items()
        }
    if isinstance(value, list):
        return [_redact_for_storage(item, key) for item in value]
    if isinstance(value, tuple):
        return [_redact_for_storage(item, key) for item in value]
    if isinstance(value, str):
        if (
            len(value) > _MAX_PERSISTED_TEXT_LENGTH
            or "\n" in value
            or _SENSITIVE_VALUE_RE.search(value)
            or _MODEL_PROSE_RE.search(value)
        ):
            return _REDACTED
        return value
    try:
        json.dumps(value)
    except (TypeError, ValueError) as exc:
        raise TerminalAuditMetadataError(
            f"terminal-audit metadata contains a non-JSON value: {type(value).__name__}"
        ) from exc
    return value


def redact_terminal_audit_text(value: str) -> str:
    """Redact sensitive or oversized text before placing it in a comment.

    Metadata serialization already applies this policy to persisted audit
    records.  Coordinator-generated comments need the same boundary because
    a human-supplied override reason is otherwise copied to the tracker
    verbatim.
    """
    if not isinstance(value, str):
        raise TypeError("terminal-audit text must be a string")
    redacted = _redact_for_storage(value)
    assert isinstance(redacted, str)  # _redact_for_storage preserves strings
    return redacted


__all__ = [
    "DEFAULT_MAX_ATTEMPT_HISTORY",
    "METADATA_KEY",
    "METADATA_VERSION",
    "MetadataQuarantine",
    "ProjectWriteLockProvider",
    "TerminalAuditMetadata",
    "TerminalAuditMetadataError",
    "TerminalAuditMetadataQuarantinedError",
    "TerminalAuditMetadataStore",
    "redact_terminal_audit_text",
    "read_terminal_audit_metadata",
    "write_terminal_audit_metadata",
]
