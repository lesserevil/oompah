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

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Mapping

from oompah.statuses import TERMINAL_STATUSES, canonicalize_status
from oompah.terminal_audit import ContributorIdentity
from oompah.terminal_audit_metadata import (
    METADATA_KEY,
    TerminalAuditMetadata,
    TerminalAuditMetadataQuarantinedError,
    TerminalAuditMetadataStore,
)


def _probe_metadata_shape(
    store: TerminalAuditMetadataStore, identifier: str
) -> tuple[bool, Mapping[str, Any]]:
    """Return ``(ok, payload)`` describing the tracker metadata surface.

    ``ok`` is ``False`` when the tracker does not expose a Mapping-shaped
    ``get_metadata`` result — the fence returns a permissive status in
    that case rather than trigger a quarantine write for a transient
    tracker misconfiguration or test double.
    """

    tracker = getattr(store, "_tracker", None)
    if tracker is None:
        return False, {}
    getter = getattr(tracker, "get_metadata", None)
    if not callable(getter):
        return False, {}
    try:
        raw = getter(identifier)
    except Exception:  # noqa: BLE001 - callable is external
        return False, {}
    if not isinstance(raw, Mapping):
        return False, {}
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
                f"RevisionAuthorization.actor is invalid: {exc}"
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
        if self.version != MARKER_VERSION:
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
        if version != MARKER_VERSION:
            raise ProvenanceSuppressionError(
                f"unsupported ProvenanceSuppression version {version!r}; "
                f"expected {MARKER_VERSION}"
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
                    f"ProvenanceSuppression.actor is invalid: {exc}"
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
            version=MARKER_VERSION,
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

    raw = document.unknown_fields.get(PROVENANCE_SUPPRESSION_KEY)
    if raw is None:
        return None
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
            suppressed=False,
            malformed=False,
            malformed_reason="",
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
    except ProvenanceSuppressionError as exc:
        return SuppressionStatus(
            suppressed=True,
            malformed=True,
            malformed_reason=str(exc),
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

    reason = status.malformed_reason or "malformed provenance-suppression metadata"
    return (
        f"Provenance-suppression metadata for {identifier} is malformed and cannot "
        "be honored automatically; leaving status unchanged. "
        f"Reason: {reason}. An operator must resolve the metadata before any "
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
                f"malformed: {exc}"
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
                f"marker is malformed: {exc}"
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
            # Preserve the last owner actor of record for audit history so
            # a downstream operator can see who originally marked the
            # task provenance-only; the revising actor lives in `history`.
            actor=existing.actor if existing is not None else None,
            reason=(
                existing.reason if existing is not None else ""
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


def issue_is_terminal(issue: Any) -> bool:
    """Return whether ``issue`` currently occupies a terminal lifecycle state."""

    state = getattr(issue, "state", "") or ""
    return canonicalize_status(state) in TERMINAL_STATUSES


__all__ = [
    "MARKER_VERSION",
    "PROVENANCE_SUPPRESSION_KEY",
    "ProvenanceSuppression",
    "ProvenanceSuppressionError",
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
