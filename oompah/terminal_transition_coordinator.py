"""Idempotent terminal-transition staging with durable audit chains.

The :class:`TerminalTransitionCoordinator` is the single entry point for
requesting terminal lifecycle transitions (``Done``, ``Merged``, ``Archived``)
for tracked tasks.  It stages each request by persisting an audit chain
*before* moving the task to ``In Validation`` status, ensuring safe recovery
after a process restart.

Concurrency model
-----------------
Per-project :class:`asyncio.Lock` objects serialise concurrent requests for
tasks in the same project.  The lock is held for the whole duration of
:meth:`TerminalTransitionCoordinator.request_transition` so two concurrent
calls for the same project cannot interleave their read-modify-write cycles.
The inner :class:`~oompah.terminal_audit_metadata.TerminalAuditMetadataStore`
additionally holds the project write lock (a ``threading.RLock``) for each
individual metadata operation so external audit-record writers (e.g. the
auditor) do not corrupt the chain.

Coalescing and superseding
--------------------------
Identical requests (same target state *and* evidence fingerprint) **coalesce**:
the second call returns successfully without creating a duplicate audit record
or posting a duplicate comment.

Requests with the same target state but a *changed* fingerprint **supersede**
the pending record: the old record is marked :attr:`~oompah.terminal_audit.RequestState.SUPERSEDED`
and a fresh record is created with the new fingerprint.

Stale requests (target already ``COMPLETED`` in the chain) are rejected.

Terminal state chains
---------------------
``Done``     → one new :class:`~oompah.terminal_audit.TerminalAuditRecord`
``Merged``   → reuse an existing completed ``Done`` audit *or* queue
               ``Done`` followed by ``Merged`` (direct ``Merged`` cannot
               skip the completion check)
``Archived`` → append one ``Archived`` audit (runs after any pending non-
               archived targets already in the chain)
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any

from oompah.models import Issue
from oompah.statuses import IN_VALIDATION, TERMINAL_STATUSES, canonicalize_status
from oompah.terminal_audit import (
    ContributorIdentity,
    EvidenceFingerprint,
    RequestState,
    TargetState,
    TerminalAuditRecord,
)
from oompah.terminal_audit_metadata import (
    TerminalAuditMetadata,
    TerminalAuditMetadataQuarantinedError,
    TerminalAuditMetadataStore,
)
from oompah.tracker import TrackerProtocol

logger = logging.getLogger(__name__)

_QUEUED_COMMENT_KEY = "queued_comment_posted"
"""Metadata key that tracks whether the queued comment has been posted."""


@dataclass
class TransitionResult:
    """Outcome of a :meth:`TerminalTransitionCoordinator.request_transition` call."""

    success: bool
    """``True`` when the request was staged or coalesced with an existing identical request."""

    audit_id: str | None = None
    """``audit_id`` of the first new record in the chain, or the coalesced record."""

    queued_targets: list[TargetState] = field(default_factory=list)
    """Ordered list of :class:`~oompah.terminal_audit.TargetState` values in the new chain."""

    coalesced: bool = False
    """``True`` when the request was deduplicated against an identical pending audit."""

    superseded_audit_id: str | None = None
    """``audit_id`` of the pending record that was superseded (different fingerprint), if any."""

    reason: str | None = None
    """Human-readable explanation when ``success`` is ``False``."""


class _Decision:
    """Internal mutable holder used to pass state out of the updater closure."""

    __slots__ = (
        "early_result",
        "new_entries",
        "superseded_id",
        "already_posted",
    )

    def __init__(self) -> None:
        self.early_result: TransitionResult | None = None
        self.new_entries: list[TerminalAuditRecord] = []
        self.superseded_id: str | None = None
        self.already_posted: bool = False


class TerminalTransitionCoordinator:
    """Stage terminal-status transitions into durable audit chains.

    One coordinator instance is created during server bootstrap and owned by
    the orchestrator.  It is safe for concurrent calls from different asyncio
    tasks because all per-project state mutations happen inside a per-project
    :class:`asyncio.Lock`.

    Parameters
    ----------
    tracker:
        The :class:`~oompah.tracker.TrackerProtocol` adapter for the project.
    project_store:
        Any object that exposes ``project_write_lock(project_id)`` returning a
        context-manager-compatible (reentrant) lock, matching
        :class:`~oompah.terminal_audit_metadata.ProjectWriteLockProvider`.
    post_comments:
        Set to ``False`` to suppress the queued-transition comment.  Useful
        for testing.
    """

    def __init__(
        self,
        tracker: TrackerProtocol,
        project_store: Any,
        *,
        post_comments: bool = True,
    ) -> None:
        self._tracker = tracker
        self._project_store = project_store
        self._post_comments = post_comments
        self._async_locks: dict[str, asyncio.Lock] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def request_transition(
        self,
        current_issue: Issue,
        requested_target: TargetState,
        trigger_identity: ContributorIdentity,
        project_id: str,
        evidence_fingerprint: EvidenceFingerprint,
    ) -> TransitionResult:
        """Stage a terminal transition for *current_issue*.

        Atomically persists the audit chain **before** moving the task to
        ``In Validation`` status, guaranteeing recovery on restart.

        Parameters
        ----------
        current_issue:
            The task to transition.  ``current_issue.identifier`` is the
            tracker-facing identifier; ``current_issue.state`` is recorded as
            ``previous_state`` in new audit records.
        requested_target:
            The requested terminal lifecycle state.
        trigger_identity:
            Who or what triggered the transition.
        project_id:
            Managed-project ID that owns the issue.
        evidence_fingerprint:
            Deterministic SHA-256 digest of the auditable evidence.

        Returns
        -------
        TransitionResult
            ``.success`` is ``True`` when the request was staged or coalesced.
            ``False`` when the metadata is quarantined or the target is already
            completed.

        Raises
        ------
        ValueError
            If ``requested_target`` cannot be parsed as a
            :class:`~oompah.terminal_audit.TargetState`.
        """
        requested_target = TargetState.from_raw(requested_target)
        lock = self._async_locks.setdefault(project_id, asyncio.Lock())
        async with lock:
            store = TerminalAuditMetadataStore(
                self._tracker, self._project_store, project_id
            )
            return self._transition_locked(
                store,
                current_issue,
                requested_target,
                trigger_identity,
                project_id,
                evidence_fingerprint,
            )

    # ------------------------------------------------------------------
    # Internal helpers — all called while the per-project asyncio.Lock is held
    # ------------------------------------------------------------------

    def _transition_locked(
        self,
        store: TerminalAuditMetadataStore,
        current_issue: Issue,
        requested_target: TargetState,
        trigger_identity: ContributorIdentity,
        project_id: str,
        evidence_fingerprint: EvidenceFingerprint,
    ) -> TransitionResult:
        identifier = current_issue.identifier
        decision = _Decision()

        def _updater(doc: TerminalAuditMetadata) -> TerminalAuditMetadata:
            """Atomically decide and commit all metadata changes."""
            chain = list(doc.pending_chain)

            # --- Stale-request rejection (target already completed) ---
            for record in chain:
                if (
                    record.target_state == requested_target
                    and record.request_state == RequestState.COMPLETED
                ):
                    decision.early_result = TransitionResult(
                        success=False,
                        audit_id=record.audit_id,
                        reason="already completed",
                    )
                    return doc

            # --- Coalesce identical pending request ---
            for record in chain:
                if (
                    record.target_state == requested_target
                    and record.request_state == RequestState.PENDING
                    and record.evidence_fingerprint == evidence_fingerprint
                ):
                    decision.early_result = TransitionResult(
                        success=True,
                        audit_id=record.audit_id,
                        queued_targets=[requested_target],
                        coalesced=True,
                    )
                    return doc  # no metadata change needed

            # --- Supersede pending record with a changed fingerprint ---
            superseded_id: str | None = None
            updated_chain: list[TerminalAuditRecord] = []
            for record in chain:
                if (
                    record.target_state == requested_target
                    and record.request_state == RequestState.PENDING
                    and record.evidence_fingerprint != evidence_fingerprint
                ):
                    updated_chain.append(
                        replace(record, request_state=RequestState.SUPERSEDED)
                    )
                    superseded_id = record.audit_id
                else:
                    updated_chain.append(record)
            decision.superseded_id = superseded_id

            # --- Build new chain entries for the requested target ---
            new_entries = _build_new_entries(
                updated_chain,
                current_issue,
                requested_target,
                trigger_identity,
                evidence_fingerprint,
                project_id,
            )
            decision.new_entries = new_entries

            final_chain = updated_chain + new_entries
            decision.already_posted = bool(
                doc.unknown_fields.get(_QUEUED_COMMENT_KEY, False)
            )

            # Mark that the queued comment has been (or will be) posted
            new_unknown = dict(doc.unknown_fields)
            new_unknown[_QUEUED_COMMENT_KEY] = True

            return replace(doc, pending_chain=final_chain, unknown_fields=new_unknown)

        # --- Step 5: Atomically persist chain (must precede status write) ---
        # The TerminalAuditMetadataStore.update() raises
        # TerminalAuditMetadataQuarantinedError before calling the updater
        # when the metadata document is quarantined.
        try:
            store.update(identifier, _updater)
        except TerminalAuditMetadataQuarantinedError:
            return TransitionResult(success=False, reason="metadata quarantined")

        # Return early if the updater decided to short-circuit (coalesce/stale)
        if decision.early_result is not None:
            return decision.early_result

        # --- Step 6: Move task to In Validation (after persistence) ---
        issue_status = current_issue.state or ""
        if canonicalize_status(issue_status) not in TERMINAL_STATUSES:
            try:
                self._tracker.update_issue(identifier, status=IN_VALIDATION)
            except Exception:
                logger.exception(
                    "Failed to move %s to In Validation; audit chain persisted",
                    identifier,
                )

        # --- Step 7: Post concise queued comment once ---
        if self._post_comments and not decision.already_posted:
            try:
                comment = (
                    f"Queued for terminal transition to "
                    f"{requested_target.value}. "
                    "An auditor will review and apply the terminal status."
                )
                self._tracker.add_comment(identifier, comment, author="oompah")
            except Exception:
                logger.exception(
                    "Failed to post queued transition comment for %s", identifier
                )

        return TransitionResult(
            success=True,
            audit_id=(
                decision.new_entries[0].audit_id if decision.new_entries else None
            ),
            queued_targets=[r.target_state for r in decision.new_entries],
            coalesced=False,
            superseded_audit_id=decision.superseded_id,
        )


# ------------------------------------------------------------------
# Module-level helpers (no coordinator state required)
# ------------------------------------------------------------------


def _build_new_entries(
    current_chain: list[TerminalAuditRecord],
    issue: Issue,
    target: TargetState,
    trigger: ContributorIdentity,
    fingerprint: EvidenceFingerprint,
    project_id: str,
) -> list[TerminalAuditRecord]:
    """Return the list of new :class:`~oompah.terminal_audit.TerminalAuditRecord` objects.

    The existing *current_chain* is used to decide whether a ``Done`` record
    can be reused for a ``Merged`` request.  New records are not appended here;
    the caller does that.
    """
    now = _now_iso8601()
    previous_state = issue.state or None

    if target == TargetState.DONE:
        return [
            _make_record(project_id, issue.identifier, TargetState.DONE,
                         fingerprint, trigger, previous_state, now)
        ]

    if target == TargetState.MERGED:
        return _build_merged_entries(
            current_chain, project_id, issue.identifier,
            fingerprint, trigger, previous_state, now,
        )

    if target == TargetState.ARCHIVED:
        return [
            _make_record(project_id, issue.identifier, TargetState.ARCHIVED,
                         fingerprint, trigger, previous_state, now)
        ]

    raise ValueError(f"Unknown target state: {target!r}")


def _build_merged_entries(
    current_chain: list[TerminalAuditRecord],
    project_id: str,
    task_id: str,
    fingerprint: EvidenceFingerprint,
    trigger: ContributorIdentity,
    previous_state: str | None,
    now: str,
) -> list[TerminalAuditRecord]:
    """Build the new entries for a ``Merged`` request.

    * If a ``COMPLETED`` ``Done`` audit already exists in *current_chain*, reuse it
      and create only the ``Merged`` record.
    * Otherwise queue ``Done`` followed by ``Merged`` so completion auditing is
      never skipped for a direct-Merged request.
    """
    completed_done = next(
        (
            r for r in current_chain
            if r.target_state == TargetState.DONE
            and r.request_state == RequestState.COMPLETED
        ),
        None,
    )

    entries: list[TerminalAuditRecord] = []
    if completed_done is None:
        # No completed Done — queue Done first so the auditor cannot skip it
        entries.append(
            _make_record(project_id, task_id, TargetState.DONE,
                         fingerprint, trigger, previous_state, now)
        )

    entries.append(
        _make_record(project_id, task_id, TargetState.MERGED,
                     fingerprint, trigger, previous_state, now)
    )
    return entries


def _make_record(
    project_id: str,
    task_id: str,
    target: TargetState,
    fingerprint: EvidenceFingerprint,
    trigger: ContributorIdentity,
    previous_state: str | None,
    created_at: str,
) -> TerminalAuditRecord:
    """Create a new :class:`~oompah.terminal_audit.TerminalAuditRecord` in ``PENDING`` state."""
    return TerminalAuditRecord(
        audit_id=_generate_audit_id(),
        project_id=project_id,
        task_id=task_id,
        target_state=target,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.PENDING,
        requested_by=trigger,
        previous_state=previous_state,
        created_at=created_at,
    )


def _generate_audit_id() -> str:
    """Return a unique audit record identifier."""
    return f"audit-{uuid.uuid4().hex[:12]}"


def _now_iso8601() -> str:
    """Return the current UTC time in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "TerminalTransitionCoordinator",
    "TransitionResult",
]
