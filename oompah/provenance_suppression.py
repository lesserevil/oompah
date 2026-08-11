"""Terminal provenance-only suppression for merged/archived task records.

A task that has already reached a terminal lifecycle state (``Done``,
``Merged``, ``Archived``) and is retained by an operator purely as
historical provenance must not be reopened, redispatched, or re-validated
by any watchdog, reconciliation sweep, dependency rollup, or restart-
recovery path.

This module defines the durable :class:`ProvenanceSuppression` marker
persisted inside the versioned :class:`~oompah.terminal_audit_metadata
.TerminalAuditMetadata` document under
:data:`PROVENANCE_SUPPRESSION_KEY`, along with pure functions that every
reopen/dispatch path consults before mutating status.

Design invariants
-----------------

* The marker is written and cleared only through this module.  The
  authority generation is a monotonically increasing integer captured in
  the durable record: every explicit owner-authorized revision bumps it,
  so a fresh revision is a strictly new authority regardless of restart
  or replay.
* A suppressed record cannot be reopened by any watchdog, review
  reconciliation, or shared-worktree absorption path.  Stale branch or
  historical review observations for the *previous* generation are
  therefore inert.
* :func:`authorize_new_revision` is the only way to remove suppression.
  It requires an authorized project owner and always bumps the
  generation, so a later replay of an older watchdog decision (even
  after a service restart) cannot re-activate the record.
* Malformed marker payloads leave status untouched and surface an
  operator-facing alert (see :func:`describe_malformed_marker`).  This
  composes with the existing ``MetadataQuarantine`` fail-closed path in
  :class:`~oompah.terminal_audit_metadata.TerminalAuditMetadataStore`,
  which quarantines the whole envelope when the whole document is
  unparseable.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
import time
from typing import Any, Mapping

from oompah.models import Issue
from oompah.statuses import OPEN, TERMINAL_STATUSES, canonicalize_status
from oompah.terminal_audit import ContributorIdentity
from oompah.terminal_audit_metadata import (
    METADATA_KEY,
    TerminalAuditMetadata,
    TerminalAuditMetadataQuarantinedError,
    TerminalAuditMetadataStore,
)
from oompah.tracker import TrackerError, TrackerProtocol


def _probe_metadata_shape(
    store: TerminalAuditMetadataStore, identifier: str
) -> tuple[bool, Mapping[str, Any]]:
    """Return ``(ok, payload)`` describing the tracker metadata surface.

    ``ok`` is ``False`` only when reading the tracker metadata raised.  A
    tracker that does not expose a Mapping-shaped ``get_metadata`` result is
    treated as an unconfigured legacy metadata surface and returns an empty,
    permissive payload.  That distinction is important: failing closed on a
    *failed read* protects an existing durable marker, while treating an
    unavailable metadata capability as a malformed marker would block every
    unrelated lifecycle transition for legacy adapters and test doubles.
    """

    tracker = getattr(store, "_tracker", None)
    if tracker is None:
        return True, {}
    getter = getattr(tracker, "get_metadata", None)
    if not callable(getter):
        return True, {}
    try:
        raw = getter(identifier)
    except Exception:  # noqa: BLE001 - callable is external
        return False, {}
    if not isinstance(raw, Mapping):
        return True, {}
    return True, raw


PROVENANCE_SUPPRESSION_KEY = "oompah.terminal_provenance_suppression"
"""Metadata key holding the durable provenance-only suppression marker."""

MARKER_VERSION = 1
"""Current schema version for the persisted marker."""

_MAX_REASON_LENGTH = 512
_MAX_HISTORY_ENTRIES = 32


class ProvenanceSuppressionError(ValueError):
    """Raised when the persisted suppression marker is structurally invalid.

    Callers never surface this error to end users.  Instead they treat the
    presence of a malformed marker as fail-closed (do not mutate status)
    and emit an operator-facing alert via
    :func:`describe_malformed_marker`.
    """


@dataclass(frozen=True)
class RevisionAuthorization:
    """One recorded owner-authorized action on the suppression marker.

    The ``kind`` is either ``"mark"`` (an owner declaring the task
    provenance-only) or ``"revise"`` (an owner explicitly starting a new
    revision, which clears suppression and bumps the authority
    generation).  ``actor`` is the durable owner identity that took the
    action, and ``reason`` is a short human-readable justification
    persisted in the durable record for audit history.
    """

    kind: str
    actor: ContributorIdentity
    reason: str
    recorded_at: str
    authority_generation: int

    _ALLOWED_KINDS: tuple[str, ...] = ("mark", "revise")

    def __post_init__(self) -> None:
        if self.kind not in self._ALLOWED_KINDS:
            raise ProvenanceSuppressionError(
                f"RevisionAuthorization.kind must be one of {self._ALLOWED_KINDS}"
            )
        if not isinstance(self.actor, ContributorIdentity):
            raise ProvenanceSuppressionError(
                "RevisionAuthorization.actor must be a ContributorIdentity"
            )
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ProvenanceSuppressionError(
                "RevisionAuthorization.reason must be a non-empty string"
            )
        if not isinstance(self.recorded_at, str) or not self.recorded_at.strip():
            raise ProvenanceSuppressionError(
                "RevisionAuthorization.recorded_at must be a non-empty ISO-8601 string"
            )
        if (
            isinstance(self.authority_generation, bool)
            or not isinstance(self.authority_generation, int)
            or self.authority_generation < 0
        ):
            raise ProvenanceSuppressionError(
                "RevisionAuthorization.authority_generation must be a non-negative int"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "actor": self.actor.to_dict(),
            "reason": self.reason,
            "recorded_at": self.recorded_at,
            "authority_generation": int(self.authority_generation),
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "RevisionAuthorization":
        if not isinstance(raw, Mapping):
            raise ProvenanceSuppressionError(
                "RevisionAuthorization payload must be a mapping"
            )
        actor_raw = raw.get("actor")
        if not isinstance(actor_raw, Mapping):
            raise ProvenanceSuppressionError(
                "RevisionAuthorization.actor must be a mapping"
            )
        try:
            actor = ContributorIdentity.from_dict(actor_raw)
        except (TypeError, ValueError) as exc:
            raise ProvenanceSuppressionError(
                "RevisionAuthorization.actor is structurally invalid"
            ) from exc
        kind = raw.get("kind")
        reason = raw.get("reason")
        recorded_at = raw.get("recorded_at")
        generation = raw.get("authority_generation")
        if not isinstance(kind, str):
            raise ProvenanceSuppressionError(
                "RevisionAuthorization.kind must be a string"
            )
        if not isinstance(reason, str):
            raise ProvenanceSuppressionError(
                "RevisionAuthorization.reason must be a string"
            )
        if not isinstance(recorded_at, str):
            raise ProvenanceSuppressionError(
                "RevisionAuthorization.recorded_at must be a string"
            )
        if isinstance(generation, bool) or not isinstance(generation, int):
            raise ProvenanceSuppressionError(
                "RevisionAuthorization.authority_generation must be an integer"
            )
        return cls(
            kind=kind,
            actor=actor,
            reason=reason,
            recorded_at=recorded_at,
            authority_generation=int(generation),
        )


@dataclass(frozen=True)
class ProvenanceSuppression:
    """The durable provenance-only suppression marker for one task.

    ``suppressed`` reflects whether the task is currently retained only
    as terminal provenance.  ``authority_generation`` is a strictly
    increasing counter — a new owner-requested revision bumps it,
    creating a fresh authority so stale watchdog decisions bound to a
    prior generation cannot mutate status.

    ``history`` is a bounded ledger of every :class:`RevisionAuthorization`
    that touched the marker, so operators can audit the sequence of
    owner actions without reading the tracker comment stream.  Free-form
    ``reason`` strings are truncated at :data:`_MAX_REASON_LENGTH` before
    persistence to bound tracker payload size.
    """

    version: int = MARKER_VERSION
    suppressed: bool = False
    authority_generation: int = 0
    actor: ContributorIdentity | None = None
    reason: str = ""
    marked_at: str = ""
    updated_at: str = ""
    history: tuple[RevisionAuthorization, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.version, int)
            or isinstance(self.version, bool)
            or self.version != MARKER_VERSION
        ):
            raise ProvenanceSuppressionError(
                f"ProvenanceSuppression.version must be {MARKER_VERSION}"
            )
        if not isinstance(self.suppressed, bool):
            raise ProvenanceSuppressionError(
                "ProvenanceSuppression.suppressed must be a bool"
            )
        if (
            isinstance(self.authority_generation, bool)
            or not isinstance(self.authority_generation, int)
            or self.authority_generation < 0
        ):
            raise ProvenanceSuppressionError(
                "ProvenanceSuppression.authority_generation must be a non-negative int"
            )
        if self.actor is not None and not isinstance(self.actor, ContributorIdentity):
            raise ProvenanceSuppressionError(
                "ProvenanceSuppression.actor must be a ContributorIdentity or None"
            )
        if not isinstance(self.reason, str):
            raise ProvenanceSuppressionError(
                "ProvenanceSuppression.reason must be a string"
            )
        if not isinstance(self.marked_at, str) or not isinstance(self.updated_at, str):
            raise ProvenanceSuppressionError(
                "ProvenanceSuppression timestamps must be strings"
            )
        if not isinstance(self.history, tuple) or any(
            not isinstance(entry, RevisionAuthorization) for entry in self.history
        ):
            raise ProvenanceSuppressionError(
                "ProvenanceSuppression.history must be a tuple of RevisionAuthorization"
            )
        if self.suppressed and self.actor is None:
            raise ProvenanceSuppressionError(
                "a suppressed marker requires a recorded owner actor"
            )
        if not self.suppressed and self.authority_generation < 1:
            raise ProvenanceSuppressionError(
                "a persisted non-suppressed marker requires a new-revision generation"
            )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "version": self.version,
            "suppressed": self.suppressed,
            "authority_generation": int(self.authority_generation),
            "reason": _truncate_reason(self.reason),
            "marked_at": self.marked_at,
            "updated_at": self.updated_at,
            "history": [entry.to_dict() for entry in self.history],
        }
        if self.actor is not None:
            payload["actor"] = self.actor.to_dict()
        return payload

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "ProvenanceSuppression":
        if not isinstance(raw, Mapping):
            raise ProvenanceSuppressionError(
                "provenance suppression payload must be a mapping"
            )
        version = raw.get("version")
        if (
            not isinstance(version, int)
            or isinstance(version, bool)
            or version != MARKER_VERSION
        ):
            # Persisted tracker metadata is untrusted.  Never interpolate the
            # attacker-controlled value into an exception that may become an
            # operator alert or log line.
            raise ProvenanceSuppressionError(
                f"unsupported ProvenanceSuppression version; expected {MARKER_VERSION}"
            )
        suppressed = raw.get("suppressed")
        if not isinstance(suppressed, bool):
            raise ProvenanceSuppressionError(
                "ProvenanceSuppression.suppressed must be a boolean"
            )
        generation = raw.get("authority_generation")
        if isinstance(generation, bool) or not isinstance(generation, int):
            raise ProvenanceSuppressionError(
                "ProvenanceSuppression.authority_generation must be an integer"
            )
        reason = raw.get("reason", "")
        marked_at = raw.get("marked_at", "")
        updated_at = raw.get("updated_at", "")
        if not isinstance(reason, str) or not isinstance(marked_at, str) or not isinstance(updated_at, str):
            raise ProvenanceSuppressionError(
                "ProvenanceSuppression string fields must be strings"
            )
        raw_actor = raw.get("actor")
        actor: ContributorIdentity | None = None
        if raw_actor is not None:
            if not isinstance(raw_actor, Mapping):
                raise ProvenanceSuppressionError(
                    "ProvenanceSuppression.actor must be a mapping or null"
                )
            try:
                actor = ContributorIdentity.from_dict(raw_actor)
            except (TypeError, ValueError) as exc:
                raise ProvenanceSuppressionError(
                    "ProvenanceSuppression.actor is structurally invalid"
                ) from exc
        raw_history = raw.get("history", [])
        if not isinstance(raw_history, list):
            raise ProvenanceSuppressionError(
                "ProvenanceSuppression.history must be a list"
            )
        history = tuple(
            RevisionAuthorization.from_dict(entry) for entry in raw_history
        )
        return cls(
            version=version,
            suppressed=suppressed,
            authority_generation=int(generation),
            actor=actor,
            reason=reason,
            marked_at=marked_at,
            updated_at=updated_at,
            history=history,
        )


def read_provenance_suppression(
    document: TerminalAuditMetadata,
) -> ProvenanceSuppression | None:
    """Return the marker persisted in ``document`` or ``None`` when absent.

    Raises :class:`ProvenanceSuppressionError` when a marker payload is
    present but structurally malformed.  Callers must treat that error as
    fail-closed for status mutation and surface an operator alert.
    """

    if PROVENANCE_SUPPRESSION_KEY not in document.unknown_fields:
        return None
    raw = document.unknown_fields[PROVENANCE_SUPPRESSION_KEY]
    return ProvenanceSuppression.from_dict(raw)


def is_dispatch_suppressed(document: TerminalAuditMetadata) -> bool:
    """Return whether the task's stored marker forbids dispatch/reopen.

    A missing marker returns ``False``.  A malformed marker also returns
    ``False`` — the caller must consult :func:`describe_malformed_marker`
    to explicitly emit an operator alert instead of silently blocking or
    reopening.  This function is deliberately narrow so the reopen paths
    can call it under a project lock without additional exception
    handling; callers that want the malformed alert must call
    :func:`load_provenance_suppression_status` instead.
    """

    try:
        marker = read_provenance_suppression(document)
    except ProvenanceSuppressionError:
        return False
    return bool(marker and marker.suppressed)


@dataclass(frozen=True)
class SuppressionStatus:
    """Rich reopen-eligibility view derived from the persisted marker.

    ``suppressed`` is ``True`` when the caller must refuse to reopen the
    task.  ``malformed`` is ``True`` when the marker payload is
    structurally invalid; callers should treat the situation as
    fail-closed for status mutation and emit an alert.
    ``authority_generation`` is the current generation from a healthy
    marker (0 when absent).
    """

    suppressed: bool
    malformed: bool
    malformed_reason: str
    marker: ProvenanceSuppression | None
    authority_generation: int


def load_provenance_suppression_status(
    store: TerminalAuditMetadataStore, identifier: str
) -> SuppressionStatus:
    """Read the marker safely, returning a full :class:`SuppressionStatus`.

    A quarantined envelope is treated as fail-closed: ``suppressed`` and
    ``malformed`` are both ``True`` so the caller refuses reopen and can
    surface an alert.  When the underlying tracker metadata surface cannot
    provide a mapping (e.g. an unconfigured legacy backend returning a
    non-dict), the fence returns a permissive status.  A separate probe of
    the payload's shape prevents the metadata store's quarantine write
    from firing for that transient tracker shape.
    """

    ok, payload = _probe_metadata_shape(store, identifier)
    if not ok:
        return SuppressionStatus(
            suppressed=True,
            malformed=True,
            malformed_reason=(
                "provenance-suppression metadata could not be read safely"
            ),
            marker=None,
            authority_generation=0,
        )
    # When the payload has no oompah.terminal_audit envelope at all there
    # is nothing to consult; treat as no suppression without triggering the
    # quarantine write path from a normal read.
    if METADATA_KEY not in payload:
        return SuppressionStatus(
            suppressed=False,
            malformed=False,
            malformed_reason="",
            marker=None,
            authority_generation=0,
        )
    try:
        document = store.read(identifier)
    except TerminalAuditMetadataQuarantinedError:
        return SuppressionStatus(
            suppressed=True,
            malformed=True,
            malformed_reason=(
                "terminal-audit metadata is quarantined; refuse status mutation"
            ),
            marker=None,
            authority_generation=0,
        )
    # A quarantined envelope parses successfully on later reads, but its
    # payload is intentionally empty except for the quarantine marker.
    # Fail closed: a caller that would otherwise reopen or dispatch must
    # instead surface an operator alert and leave status untouched.
    if document.is_quarantined:
        return SuppressionStatus(
            suppressed=True,
            malformed=True,
            malformed_reason=(
                "terminal-audit metadata is quarantined; refuse status mutation"
            ),
            marker=None,
            authority_generation=0,
        )
    try:
        marker = read_provenance_suppression(document)
    except ProvenanceSuppressionError:
        return SuppressionStatus(
            suppressed=True,
            malformed=True,
            malformed_reason=(
                "stored provenance-suppression marker is malformed"
            ),
            marker=None,
            authority_generation=0,
        )
    if marker is None:
        return SuppressionStatus(
            suppressed=False,
            malformed=False,
            malformed_reason="",
            marker=None,
            authority_generation=0,
        )
    return SuppressionStatus(
        suppressed=bool(marker.suppressed),
        malformed=False,
        malformed_reason="",
        marker=marker,
        authority_generation=int(marker.authority_generation),
    )


def describe_malformed_marker(status: SuppressionStatus, identifier: str) -> str:
    """Return an operator alert body for a malformed marker.

    Deliberately avoids echoing any payload details — the alert only
    exposes structural information so credentials or model prose that
    landed inside the malformed payload cannot leak.  Callers that need
    a per-task alert with the identifier already scoped it in.
    """

    return (
        f"Provenance-suppression metadata for {identifier} is malformed and cannot "
        "be honored automatically; leaving status unchanged. "
        "The marker is unsupported, structurally invalid, or temporarily "
        "unreadable. An operator must resolve the metadata before any "
        "watchdog or reconciliation path may reopen or redispatch this task."
    )


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _truncate_reason(reason: str) -> str:
    if len(reason) <= _MAX_REASON_LENGTH:
        return reason
    return reason[: _MAX_REASON_LENGTH - 3].rstrip() + "..."


def _append_history(
    history: tuple[RevisionAuthorization, ...],
    entry: RevisionAuthorization,
) -> tuple[RevisionAuthorization, ...]:
    combined = (*history, entry)
    if len(combined) > _MAX_HISTORY_ENTRIES:
        combined = combined[-_MAX_HISTORY_ENTRIES:]
    return combined


def _empty_marker() -> ProvenanceSuppression:
    return ProvenanceSuppression()


@dataclass(frozen=True)
class SuppressionMutationResult:
    """Return value for the durable mutation helpers."""

    marker: ProvenanceSuppression
    changed: bool


def mark_provenance_only(
    store: TerminalAuditMetadataStore,
    identifier: str,
    actor: ContributorIdentity,
    reason: str,
    *,
    now: str | None = None,
) -> SuppressionMutationResult:
    """Persist a durable provenance-only marker for ``identifier``.

    Idempotent: a repeated call with the same actor/generation returns
    the existing marker unchanged.  Rewriting an already-suppressed
    marker does not bump the authority generation — only
    :func:`authorize_new_revision` does that.
    """

    if not isinstance(actor, ContributorIdentity):
        raise TypeError("actor must be a ContributorIdentity")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("reason must be a non-empty string")
    recorded_at = now or _now_iso_utc()

    outcome: dict[str, Any] = {"marker": None, "changed": False}

    def _updater(document: TerminalAuditMetadata) -> TerminalAuditMetadata:
        try:
            existing = read_provenance_suppression(document)
        except ProvenanceSuppressionError as exc:
            raise ProvenanceSuppressionError(
                "cannot mark a task provenance-only while its stored marker is "
                "structurally invalid"
            ) from exc
        if existing is not None and existing.suppressed:
            outcome["marker"] = existing
            outcome["changed"] = False
            return document
        base_history = existing.history if existing is not None else tuple()
        base_generation = (
            existing.authority_generation if existing is not None else 0
        )
        marked_at = (
            existing.marked_at
            if existing is not None and existing.marked_at
            else recorded_at
        )
        entry = RevisionAuthorization(
            kind="mark",
            actor=actor,
            reason=_truncate_reason(reason),
            recorded_at=recorded_at,
            authority_generation=base_generation,
        )
        marker = ProvenanceSuppression(
            version=MARKER_VERSION,
            suppressed=True,
            authority_generation=base_generation,
            actor=actor,
            reason=_truncate_reason(reason),
            marked_at=marked_at,
            updated_at=recorded_at,
            history=_append_history(base_history, entry),
        )
        unknown = dict(document.unknown_fields)
        unknown[PROVENANCE_SUPPRESSION_KEY] = marker.to_dict()
        outcome["marker"] = marker
        outcome["changed"] = True
        return replace(document, unknown_fields=unknown)

    store.update(identifier, _updater)
    marker = outcome["marker"]
    assert isinstance(marker, ProvenanceSuppression)  # narrowed by _updater
    return SuppressionMutationResult(marker=marker, changed=bool(outcome["changed"]))


def authorize_new_revision(
    store: TerminalAuditMetadataStore,
    identifier: str,
    actor: ContributorIdentity,
    reason: str,
    *,
    now: str | None = None,
) -> SuppressionMutationResult:
    """Clear provenance suppression and bump the authority generation.

    This is the only path that returns a suppressed record to a
    dispatchable state.  It always bumps
    :attr:`ProvenanceSuppression.authority_generation` even when the
    task was not previously suppressed, so a stale watchdog decision
    bound to a prior generation is inert.
    """

    if not isinstance(actor, ContributorIdentity):
        raise TypeError("actor must be a ContributorIdentity")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("reason must be a non-empty string")
    recorded_at = now or _now_iso_utc()

    outcome: dict[str, Any] = {"marker": None, "changed": False}

    def _updater(document: TerminalAuditMetadata) -> TerminalAuditMetadata:
        try:
            existing = read_provenance_suppression(document)
        except ProvenanceSuppressionError as exc:
            raise ProvenanceSuppressionError(
                "cannot authorize a new revision while the stored provenance "
                "marker is structurally invalid"
            ) from exc
        base_history = existing.history if existing is not None else tuple()
        base_generation = (
            existing.authority_generation if existing is not None else 0
        )
        marked_at = existing.marked_at if existing is not None else ""
        new_generation = int(base_generation) + 1
        entry = RevisionAuthorization(
            kind="revise",
            actor=actor,
            reason=_truncate_reason(reason),
            recorded_at=recorded_at,
            authority_generation=new_generation,
        )
        marker = ProvenanceSuppression(
            version=MARKER_VERSION,
            suppressed=False,
            authority_generation=new_generation,
            # Preserve the last retaining owner for an existing marker; when
            # revision authority starts from absence, establish the revising
            # owner as the marker's durable identity as well as in history.
            actor=existing.actor if existing is not None else actor,
            reason=(
                existing.reason
                if existing is not None
                else _truncate_reason(reason)
            ),
            marked_at=marked_at,
            updated_at=recorded_at,
            history=_append_history(base_history, entry),
        )
        unknown = dict(document.unknown_fields)
        unknown[PROVENANCE_SUPPRESSION_KEY] = marker.to_dict()
        outcome["marker"] = marker
        outcome["changed"] = True
        return replace(document, unknown_fields=unknown)

    store.update(identifier, _updater)
    marker = outcome["marker"]
    assert isinstance(marker, ProvenanceSuppression)
    return SuppressionMutationResult(marker=marker, changed=bool(outcome["changed"]))


class ProvenanceSuppressionBlockedError(TrackerError):
    """A durable provenance fence refused a tracker status mutation."""


class ProvenanceOwnerRevisionNotFoundError(TrackerError):
    """The owner-authorized revision target does not exist in the project."""


class ProvenanceOwnerRevisionStateError(TrackerError):
    """The target is not in a state eligible for an owner revision."""


class ProvenanceControlBusyError(TrackerError):
    """Owner provenance authority was busy past its bounded wait."""


class ProvenanceGuardedTracker:
    """Project-scoped tracker facade enforcing provenance suppression.

    Individual watchdog and reconciliation callers are useful places to emit
    domain-specific diagnostics, but they are not a sufficient authority
    boundary: new recovery paths can otherwise forget the marker and reopen a
    terminal record.  Every managed-project tracker returned by the
    orchestrator is wrapped in this facade, making ``update_issue`` and the
    protocol's status-changing convenience methods share one durable fence.

    The dedicated :meth:`authorize_owner_revision` operation keeps its
    fail-safe Open write fenced between two project-lock phases; callers cannot
    obtain a general-purpose raw status writer from this facade.  Releasing the
    project lock for the journaled status transition is required because that
    transition may perform its tracker write on another thread.  Suppression
    remains active throughout that phase and is revalidated under the lock
    before it is cleared.  Every ordinary status-changing method is frozen
    while suppression is active, including terminal-to-terminal audit or
    auto-archive writes.  Malformed or unreadable marker metadata likewise
    rejects all status mutations until an operator repairs it; error text
    never includes the persisted payload.
    """

    def __init__(
        self,
        tracker: TrackerProtocol,
        project_store: Any,
        project_id: str,
        *,
        control_lock_timeout_seconds: float = 5.0,
        control_lock_observer: Callable[..., None] | None = None,
    ) -> None:
        if not isinstance(project_id, str) or not project_id.strip():
            raise ValueError("project_id must be a non-empty string")
        self._provenance_tracker = tracker
        self._provenance_project_store = project_store
        self._provenance_project_id = project_id
        timeout = float(control_lock_timeout_seconds)
        if timeout <= 0:
            raise ValueError("control_lock_timeout_seconds must be positive")
        self._control_lock_timeout_seconds = timeout
        self._control_lock_observer = control_lock_observer

    def __getattr__(self, name: str) -> Any:
        return getattr(self._provenance_tracker, name)

    def get_publication_revision(self) -> int | None:
        """Return the quiescent managed tracker mutation epoch."""

        source = getattr(
            self._provenance_project_store, "tracker_publication_revision", None
        )
        if callable(source):
            revision = source(self._provenance_project_id)
            return int(revision) if revision is not None else None
        fallback = getattr(
            self._provenance_project_store, "tracker_authority_revision", None
        )
        return int(fallback(self._provenance_project_id)) if callable(fallback) else 0

    @staticmethod
    def _mutation_task_ids(
        args: tuple[Any, ...],
        kwargs: Mapping[str, Any],
        *,
        count: int = 1,
    ) -> tuple[str, ...] | None:
        identifiers = [
            str(value or "").strip()
            for value in args[:count]
            if str(value or "").strip()
        ]
        if not identifiers:
            for key in (
                "identifier",
                "child_id",
                "parent_id",
                "blocked_id",
                "blocker_id",
            ):
                value = str(kwargs.get(key) or "").strip()
                if value:
                    identifiers.append(value)
                if len(identifiers) >= count:
                    break
        return tuple(identifiers) if len(identifiers) == count else None

    def publication_task_changes_since(
        self,
        revision: int,
    ) -> tuple[int, frozenset[str] | None]:
        """Expose the managed mutation journal for task-scoped publication."""

        source = getattr(
            self._provenance_project_store,
            "tracker_authority_changes_since",
            None,
        )
        if not callable(source):
            return self.get_publication_revision() or 0, None
        return source(self._provenance_project_id, revision)

    def _advance_publication_revision(
        self,
        task_ids: tuple[str, ...] | None = None,
    ) -> None:
        advance = getattr(
            self._provenance_project_store,
            "advance_tracker_authority_revision",
            None,
        )
        if callable(advance):
            advance(self._provenance_project_id, task_ids)

    def _publication_mutation(
        self,
        operation: Callable[[], Any],
        *,
        task_ids: tuple[str, ...] | None = None,
    ) -> Any:
        """Fence one external tracker write without retaining project authority."""

        admit = getattr(
            self._provenance_project_store,
            "admit_tracker_authority_mutation",
            None,
        )
        finalize = getattr(
            self._provenance_project_store,
            "finalize_tracker_authority_mutation",
            None,
        )
        if not callable(admit) or not callable(finalize):
            result = operation()
            self._advance_publication_revision(task_ids)
            return result
        token = str(admit(self._provenance_project_id, task_ids))
        try:
            return operation()
        finally:
            finalize(self._provenance_project_id, token)

    def create_issue(self, *args: Any, **kwargs: Any) -> Issue:
        return self._publication_mutation(
            lambda: self._provenance_tracker.create_issue(*args, **kwargs)
        )

    def create_issue_once(self, *args: Any, **kwargs: Any) -> Issue:
        return self._publication_mutation(
            lambda: self._provenance_tracker.create_issue_once(*args, **kwargs)
        )

    def add_comment(self, *args: Any, **kwargs: Any) -> dict:
        return self._publication_mutation(
            lambda: self._provenance_tracker.add_comment(*args, **kwargs),
            task_ids=self._mutation_task_ids(args, kwargs),
        )

    def append_comment(self, *args: Any, **kwargs: Any) -> Any:
        return self._publication_mutation(
            lambda: self._provenance_tracker.append_comment(*args, **kwargs),
            task_ids=self._mutation_task_ids(args, kwargs),
        )

    def add_label(self, *args: Any, **kwargs: Any) -> None:
        self._publication_mutation(
            lambda: self._provenance_tracker.add_label(*args, **kwargs),
            task_ids=self._mutation_task_ids(args, kwargs),
        )

    def remove_label(self, *args: Any, **kwargs: Any) -> None:
        self._publication_mutation(
            lambda: self._provenance_tracker.remove_label(*args, **kwargs),
            task_ids=self._mutation_task_ids(args, kwargs),
        )

    def add_parent_child(self, *args: Any, **kwargs: Any) -> None:
        self._publication_mutation(
            lambda: self._provenance_tracker.add_parent_child(*args, **kwargs),
            task_ids=self._mutation_task_ids(args, kwargs, count=2),
        )

    def add_dependency(self, *args: Any, **kwargs: Any) -> None:
        self._publication_mutation(
            lambda: self._provenance_tracker.add_dependency(*args, **kwargs),
            task_ids=self._mutation_task_ids(args, kwargs, count=2),
        )

    def remove_dependency(self, *args: Any, **kwargs: Any) -> None:
        self._publication_mutation(
            lambda: self._provenance_tracker.remove_dependency(*args, **kwargs),
            task_ids=self._mutation_task_ids(args, kwargs, count=2),
        )

    def add_start_dependency(self, *args: Any, **kwargs: Any) -> None:
        self._publication_mutation(
            lambda: self._provenance_tracker.add_start_dependency(*args, **kwargs),
            task_ids=self._mutation_task_ids(args, kwargs, count=2),
        )

    def remove_start_dependency(self, *args: Any, **kwargs: Any) -> None:
        self._publication_mutation(
            lambda: self._provenance_tracker.remove_start_dependency(*args, **kwargs),
            task_ids=self._mutation_task_ids(args, kwargs, count=2),
        )

    def set_attachments(self, *args: Any, **kwargs: Any) -> None:
        self._publication_mutation(
            lambda: self._provenance_tracker.set_attachments(*args, **kwargs),
            task_ids=self._mutation_task_ids(args, kwargs),
        )

    def set_metadata_field(self, *args: Any, **kwargs: Any) -> None:
        self._publication_mutation(
            lambda: self._provenance_tracker.set_metadata_field(*args, **kwargs),
            task_ids=self._mutation_task_ids(args, kwargs),
        )

    @contextmanager
    def owner_control_lock(self):
        """Acquire project authority with a bounded, observable owner wait."""

        lock = self._provenance_project_store.project_write_lock(
            self._provenance_project_id
        )
        wait_started = time.monotonic()
        acquired = lock.acquire(timeout=self._control_lock_timeout_seconds)
        acquired_at = time.monotonic()
        if not acquired:
            observer = self._control_lock_observer
            if callable(observer):
                observer(
                    self._provenance_project_id,
                    wait_seconds=acquired_at - wait_started,
                    hold_seconds=0.0,
                    timed_out=True,
                )
            raise ProvenanceControlBusyError(
                "terminal provenance control is busy; retry the request"
            )
        try:
            yield
        finally:
            released_at = time.monotonic()
            lock.release()
            observer = self._control_lock_observer
            if callable(observer):
                observer(
                    self._provenance_project_id,
                    wait_seconds=acquired_at - wait_started,
                    hold_seconds=released_at - acquired_at,
                    timed_out=False,
                )

    def _assert_status_mutation_allowed(
        self,
        identifier: str,
    ) -> None:
        with self._provenance_project_store.project_write_lock(
            self._provenance_project_id
        ):
            store = TerminalAuditMetadataStore(
                self._provenance_tracker,
                self._provenance_project_store,
                self._provenance_project_id,
            )
            status = load_provenance_suppression_status(store, identifier)
            if status.malformed:
                raise ProvenanceSuppressionBlockedError(
                    f"Status mutation for {identifier} is blocked because its "
                    "provenance-suppression metadata is malformed or unreadable."
                )
            if status.suppressed:
                raise ProvenanceSuppressionBlockedError(
                    f"Status mutation for {identifier} is blocked because the task "
                    "is retained only as terminal provenance; a project owner must "
                    "authorize a new revision first."
                )

    def update_issue(self, identifier: str, **fields: str) -> None:
        if "status" not in fields:
            self._publication_mutation(
                lambda: self._provenance_tracker.update_issue(identifier, **fields),
                task_ids=(str(identifier),),
            )
            return
        with self._provenance_project_store.project_write_lock(
            self._provenance_project_id
        ):
            self._assert_status_mutation_allowed(identifier)
            self._provenance_tracker.update_issue(identifier, **fields)
            self._advance_publication_revision((str(identifier),))

    def reopen_issue(self, identifier: str) -> None:
        with self._provenance_project_store.project_write_lock(
            self._provenance_project_id
        ):
            self._assert_status_mutation_allowed(identifier)
            self._provenance_tracker.reopen_issue(identifier)
            self._advance_publication_revision((str(identifier),))

    def mark_needs_human(
        self,
        identifier: str,
        comment: str,
        author: str = "oompah",
    ) -> None:
        with self._provenance_project_store.project_write_lock(
            self._provenance_project_id
        ):
            self._assert_status_mutation_allowed(identifier)
            self._provenance_tracker.mark_needs_human(
                identifier,
                comment,
                author=author,
            )
            self._advance_publication_revision((str(identifier),))

    def close_issue(self, identifier: str, *, reason: str | None = None) -> None:
        with self._provenance_project_store.project_write_lock(
            self._provenance_project_id
        ):
            self._assert_status_mutation_allowed(identifier)
            self._provenance_tracker.close_issue(identifier, reason=reason)
            self._advance_publication_revision((str(identifier),))

    def archive_issue(self, identifier: str) -> None:
        with self._provenance_project_store.project_write_lock(
            self._provenance_project_id
        ):
            self._assert_status_mutation_allowed(identifier)
            self._provenance_tracker.archive_issue(identifier)
            self._advance_publication_revision((str(identifier),))

    def authorize_owner_revision(
        self,
        identifier: str,
        actor: ContributorIdentity,
        reason: str,
        *,
        status_transition: Callable[..., object] | None = None,
    ) -> SuppressionMutationResult:
        """Open one suppressed record and durably authorize its new revision.

        The caller must authenticate ``actor`` as the project owner before
        invoking this method.  The narrowly scoped operation deliberately
        exposes neither the underlying tracker nor an arbitrary status value.
        Open is persisted before suppression is cleared, so an interrupted
        request remains fail-closed as Open + suppressed and can be retried.
        """

        if not isinstance(actor, ContributorIdentity):
            raise TypeError("actor must be a ContributorIdentity")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("reason must be a non-empty string")

        with self.owner_control_lock():
            current = self._provenance_tracker.fetch_issue_detail(identifier)
            if current is None:
                raise ProvenanceOwnerRevisionNotFoundError(
                    "owner revision target was not found"
                )
            store = TerminalAuditMetadataStore(
                self._provenance_tracker,
                self._provenance_project_store,
                self._provenance_project_id,
            )
            suppression = load_provenance_suppression_status(store, identifier)
            if suppression.malformed:
                raise ProvenanceSuppressionError(
                    "stored provenance-suppression metadata is structurally invalid"
                )
            if not suppression.suppressed:
                raise ProvenanceOwnerRevisionStateError(
                    "owner revision requires an actively suppressed record"
                )
            current_status = canonicalize_status(current.state)
            if current_status != OPEN and current_status not in TERMINAL_STATUSES:
                raise ProvenanceOwnerRevisionStateError(
                    "owner revision requires a terminal or Open retry state"
                )
            if current_status != OPEN:
                if not callable(status_transition):
                    raise ProvenanceSuppressionError(
                        "task transition recovery service is unavailable"
                    )
            authority_generation = suppression.authority_generation

        if current_status != OPEN:
            assert status_transition is not None
            status_transition(
                current,
                OPEN,
                tracker=self._provenance_tracker,
                project_id=self._provenance_project_id,
                actor=actor.identity,
                reason_code="provenance.owner_revision_authorized",
                idempotency_key=(
                    f"provenance-owner-revision:{self._provenance_project_id}:"
                    f"{identifier}:{authority_generation + 1}"
                ),
                write_lock=self.owner_control_lock,
            )

        with self.owner_control_lock():
            current = self._provenance_tracker.fetch_issue_detail(identifier)
            if current is None:
                raise ProvenanceOwnerRevisionNotFoundError(
                    "owner revision target was not found"
                )
            if canonicalize_status(current.state) != OPEN:
                raise ProvenanceOwnerRevisionStateError(
                    "owner revision status transition did not commit Open"
                )
            suppression = load_provenance_suppression_status(store, identifier)
            if suppression.malformed:
                raise ProvenanceSuppressionError(
                    "stored provenance-suppression metadata is structurally invalid"
                )
            if (
                not suppression.suppressed
                or suppression.authority_generation != authority_generation
            ):
                raise ProvenanceOwnerRevisionStateError(
                    "owner revision authority changed during status transition"
                )
            result = authorize_new_revision(store, identifier, actor, reason)
            self._advance_publication_revision((str(identifier),))
            return result


def issue_is_terminal(issue: Any) -> bool:
    """Return whether ``issue`` currently occupies a terminal lifecycle state."""

    state = getattr(issue, "state", "") or ""
    return canonicalize_status(state) in TERMINAL_STATUSES


__all__ = [
    "MARKER_VERSION",
    "PROVENANCE_SUPPRESSION_KEY",
    "ProvenanceGuardedTracker",
    "ProvenanceSuppression",
    "ProvenanceSuppressionBlockedError",
    "ProvenanceSuppressionError",
    "ProvenanceOwnerRevisionNotFoundError",
    "ProvenanceOwnerRevisionStateError",
    "ProvenanceControlBusyError",
    "RevisionAuthorization",
    "SuppressionMutationResult",
    "SuppressionStatus",
    "authorize_new_revision",
    "describe_malformed_marker",
    "is_dispatch_suppressed",
    "issue_is_terminal",
    "load_provenance_suppression_status",
    "mark_provenance_only",
    "read_provenance_suppression",
]
