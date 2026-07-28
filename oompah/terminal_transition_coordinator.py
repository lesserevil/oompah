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

Result application
------------------
:meth:`TerminalTransitionCoordinator.apply_audit_result` accepts an auditor's
verdict for a specific pending audit and drives the terminal state machine
without any fail-open path.  A verdict is only honoured when the tracker's
current status is ``In Validation`` and the ``(audit_id, target, fingerprint)``
tuple matches a pending or in-progress record — otherwise the result is
rejected and the record remains nonterminal.  Failures are mapped through
:func:`classify_failure_to_status` to a deterministic repair state
(``Open``, ``Needs CI Fix``, ``Needs Rebase``, ``In Review``, ``Needs Human``,
or the recorded pre-audit state for an unsafe archive), and a ``Needs Human``
comment must end with actionable instructions or a question or the coordinator
refuses to route there.  ``ERROR`` verdicts, unparseable payloads, malformed
results, infrastructure errors, and retry ceilings all leave the audit record
pending — the item stays in ``In Validation`` and never reaches a terminal
state on the strength of a failure.
"""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any

from oompah.models import Issue
from oompah.statuses import (
    ARCHIVED,
    DONE,
    IN_REVIEW,
    IN_VALIDATION,
    MERGED,
    NEEDS_CI_FIX,
    NEEDS_HUMAN,
    NEEDS_REBASE,
    OPEN,
    TERMINAL_STATUSES,
    canonicalize_status,
    status_key,
)
from oompah.terminal_audit import (
    AuditAttempt,
    ContributorIdentity,
    EvidenceFingerprint,
    FailureClassification,
    OverrideRecord,
    RequestState,
    TargetState,
    TerminalAuditRecord,
    Verdict,
)
from oompah.terminal_audit_metadata import (
    TerminalAuditMetadata,
    TerminalAuditMetadataQuarantinedError,
    TerminalAuditMetadataStore,
    redact_terminal_audit_text,
)
from oompah.label_auth import is_authorized_status_actor
from oompah.transition_gate import is_project_owner
from oompah.tracker import TrackerProtocol, validate_needs_human_comment

logger = logging.getLogger(__name__)

_QUEUED_COMMENT_KEY = "queued_comment_posted"
"""Metadata key that tracks whether the queued comment has been posted."""

_APPLIED_RESULTS_KEY = "applied_result_attempts"
"""Metadata key that records attempt IDs whose result has already been applied."""

_MAX_APPLIED_RESULTS_MEMORY = 200
"""Retained size of the applied-result attempt log inside metadata."""

_NEEDS_HUMAN_HINT = (
    " Please review the audit output, decide the next step, and update this "
    "task with your instructions."
)
"""Fallback instructions appended when a ``Needs Human`` message is empty."""


# ---------------------------------------------------------------------------
# Failure-classification routing
# ---------------------------------------------------------------------------


_OPEN_CLASSES: frozenset[FailureClassification] = frozenset({
    FailureClassification.INCOMPLETE,
    FailureClassification.MISSING_TESTS,
    FailureClassification.UNPUSHED,
    FailureClassification.MISSING_EVIDENCE,
})
_NEEDS_HUMAN_CLASSES: frozenset[FailureClassification] = frozenset({
    FailureClassification.AMBIGUOUS_REQUIREMENTS,
    FailureClassification.EXTERNAL_CAPABILITY,
    FailureClassification.NO_AUDITOR,
})
_NEEDS_REBASE_CLASSES: frozenset[FailureClassification] = frozenset({
    FailureClassification.CONFLICT,
    FailureClassification.OUT_OF_DATE,
})
_NONTERMINAL_CLASSES: frozenset[FailureClassification] = frozenset({
    FailureClassification.MALFORMED_RESULT,
    FailureClassification.INFRASTRUCTURE_ERROR,
})


def classify_failure_to_status(
    classification: FailureClassification,
    previous_state: str | None = None,
) -> str | None:
    """Map a :class:`FailureClassification` to a canonical repair status.

    Returns ``None`` for classifications that leave the item nonterminal
    (``MALFORMED_RESULT`` and ``INFRASTRUCTURE_ERROR``).  These never route a
    task away from ``In Validation`` because we cannot pick a safe repair
    state without knowing the underlying reason.

    ``UNSAFE_ARCHIVE`` restores the recorded pre-audit state (from
    ``previous_state``) unless it is missing or itself terminal, in which
    case the item is routed to ``Needs Human`` for the operator to decide.
    """

    classification = FailureClassification.from_raw(classification)
    if classification in _NONTERMINAL_CLASSES:
        return None
    if classification in _OPEN_CLASSES:
        return OPEN
    if classification == FailureClassification.CI_FAILURE:
        return NEEDS_CI_FIX
    if classification in _NEEDS_REBASE_CLASSES:
        return NEEDS_REBASE
    if classification == FailureClassification.HEALTHY_UNMERGED_REVIEW:
        return IN_REVIEW
    if classification in _NEEDS_HUMAN_CLASSES:
        return NEEDS_HUMAN
    if classification == FailureClassification.UNSAFE_ARCHIVE:
        # "Unsafe archive restores the recorded pre-audit state unless
        # another class is more specific."  When the caller reports a more
        # specific classification we route on that; here we only have
        # UNSAFE_ARCHIVE and must fall back to the persisted previous state.
        canonical = canonicalize_status(previous_state) if previous_state else ""
        if canonical and canonical not in TERMINAL_STATUSES:
            return canonical
        # No safe pre-audit state to restore — hand off to a human rather
        # than leaving the item in a terminal or unknown state.
        return NEEDS_HUMAN
    # Any newly added classification must be routed explicitly — refusing
    # unknown values here keeps this a fail-closed switch.
    raise ValueError(
        f"No routing defined for FailureClassification {classification!r}"
    )


# ---------------------------------------------------------------------------
# Public result types
# ---------------------------------------------------------------------------


@dataclass
class OverrideResult:
    """Outcome of a :meth:`TerminalTransitionCoordinator.override_transition` call."""

    success: bool
    """``True`` when the override was applied successfully."""

    override_id: str | None = None
    """``override_id`` of the persisted override record."""

    applied_status: str | None = None
    """The terminal status that was applied to the tracker."""

    posted_comment: bool = False
    """``True`` when the override explanation comment was posted."""

    reason: str | None = None
    """Human-readable explanation when ``success`` is ``False``."""

    error_code: str | None = None
    """Stable machine-readable rejection code for API/CLI callers."""


class OverrideRejection:
    """Stable error codes returned by :meth:`override_transition`."""

    UNAUTHORIZED_ACTOR = "unauthorized_actor"
    METADATA_QUARANTINED = "metadata_quarantined"
    METADATA_READ_FAILED = "metadata_read_failed"
    FINGERPRINT_MISMATCH = "fingerprint_mismatch"
    METADATA_WRITE_FAILED = "metadata_write_failed"
    COMMENT_FAILED = "comment_failed"
    STATUS_UPDATE_FAILED = "status_update_failed"


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


@dataclass(frozen=True)
class AuditResult:
    """A tracker-neutral, machine-readable result submitted by an auditor.

    ``audit_id``, ``target_state``, and ``evidence_fingerprint`` together
    identify the pending audit record that produced this result.  Any drift
    from the persisted values causes
    :meth:`TerminalTransitionCoordinator.apply_audit_result` to reject the
    result without changing state.

    ``verdict`` is authoritative: only :attr:`~oompah.terminal_audit.Verdict.PASS`
    reaches a terminal status.  ``FAIL`` requires a ``failure_classification``
    which is mapped through :func:`classify_failure_to_status`.  ``ERROR``
    and unparseable results never route to a terminal status; the audit
    stays pending in ``In Validation``.

    ``attempt_id`` is an idempotency key.  Two calls with the same ``attempt_id``
    produce the same outcome and never apply two attempts to the record.
    ``message`` carries the auditor's human-readable explanation and is
    trusted to have been redacted upstream.
    """

    audit_id: str
    target_state: TargetState
    evidence_fingerprint: EvidenceFingerprint
    verdict: Verdict
    failure_classification: FailureClassification | None = None
    message: str = ""
    safe_evidence: Mapping[str, Any] | None = None
    auditor: ContributorIdentity | None = None
    attempt_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.audit_id, str) or not self.audit_id.strip():
            raise ValueError("AuditResult.audit_id must be a non-empty string")
        object.__setattr__(self, "target_state", TargetState.from_raw(self.target_state))
        object.__setattr__(self, "verdict", Verdict.from_raw(self.verdict))
        if not isinstance(self.evidence_fingerprint, EvidenceFingerprint):
            raise TypeError(
                "AuditResult.evidence_fingerprint must be an EvidenceFingerprint"
            )
        if self.failure_classification is not None:
            object.__setattr__(
                self,
                "failure_classification",
                FailureClassification.from_raw(self.failure_classification),
            )
        if self.auditor is not None and not isinstance(self.auditor, ContributorIdentity):
            raise TypeError("AuditResult.auditor must be ContributorIdentity or None")
        if self.attempt_id is not None and (
            not isinstance(self.attempt_id, str) or not self.attempt_id.strip()
        ):
            raise ValueError("AuditResult.attempt_id must be a non-empty string or None")
        if not isinstance(self.message, str):
            raise TypeError("AuditResult.message must be a string")
        if self.safe_evidence is not None and not isinstance(self.safe_evidence, Mapping):
            raise TypeError("AuditResult.safe_evidence must be a mapping or None")


class ResultRejection:
    """Reason strings used when :meth:`apply_audit_result` rejects a result."""

    AUDIT_NOT_FOUND = "audit not found in pending chain"
    TARGET_MISMATCH = "target state does not match audit"
    FINGERPRINT_MISMATCH = "evidence fingerprint does not match audit"
    STATE_MISMATCH = "audit is no longer pending or in progress"
    ISSUE_NOT_IN_VALIDATION = "issue is not in In Validation"
    MALFORMED_RESULT = "audit result is malformed"
    METADATA_QUARANTINED = "terminal-audit metadata is quarantined"
    NEEDS_HUMAN_NOT_ACTIONABLE = (
        "Needs Human comment must end with instructions or a question"
    )
    MISSING_CLASSIFICATION = "FAIL verdict requires a failure classification"
    UNPARSEABLE_VERDICT = "unparseable verdict"
    RETRY_CEILING = "retry ceiling reached; verdict left pending"


@dataclass
class ResultOutcome:
    """Outcome of a :meth:`TerminalTransitionCoordinator.apply_audit_result` call.

    ``applied_status`` is the final status the coordinator asked the tracker
    to set (or ``None`` if the audit stayed non-terminal because the result
    was infrastructural, malformed, an unparseable ``ERROR``, or the retry
    ceiling was reached).  ``idempotent`` is ``True`` when the exact same
    ``attempt_id`` had already been applied and the coordinator short-
    circuited without re-applying tracker state.  ``advanced_target`` is
    populated when a passing audit leaves further work pending in the chain.
    """

    success: bool
    audit_id: str | None = None
    applied_status: str | None = None
    posted_comment: bool = False
    idempotent: bool = False
    advanced_target: TargetState | None = None
    reason: str | None = None


# ---------------------------------------------------------------------------
# Internal decision holders
# ---------------------------------------------------------------------------


class _Decision:
    """Internal mutable holder used to pass state out of the request updater."""

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


class _ResultDecision:
    """Internal mutable holder used to pass state out of the result updater."""

    __slots__ = (
        "outcome",
        "target_status",
        "comment_text",
        "audit_id",
        "advanced_target",
        "applied_attempt",
        "keep_in_validation",
    )

    def __init__(self) -> None:
        self.outcome: ResultOutcome | None = None
        self.target_status: str | None = None
        self.comment_text: str | None = None
        self.audit_id: str | None = None
        self.advanced_target: TargetState | None = None
        self.applied_attempt: bool = False
        self.keep_in_validation: bool = False


# ---------------------------------------------------------------------------
# Coordinator
# ---------------------------------------------------------------------------


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
        tracker: TrackerProtocol | Callable[[str], TrackerProtocol],
        project_store: Any,
        *,
        post_comments: bool = True,
    ) -> None:
        # The standalone API accepts one tracker, while the server passes a
        # project-aware factory because managed projects each have their own
        # tracker adapter.  Keeping both forms makes the coordinator useful in
        # small integrations and in the multi-project orchestrator.
        self._tracker = tracker
        self._project_store = project_store
        self._post_comments = post_comments
        self._async_locks: dict[str, asyncio.Lock] = {}

    # ------------------------------------------------------------------
    # Public API — request_transition
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
            tracker = self._tracker_for_project(project_id)
            store = TerminalAuditMetadataStore(
                tracker, self._project_store, project_id
            )
            return self._transition_locked(
                store,
                tracker,
                current_issue,
                requested_target,
                trigger_identity,
                project_id,
                evidence_fingerprint,
            )

    # ------------------------------------------------------------------
    # Public API — apply_audit_result
    # ------------------------------------------------------------------

    async def apply_audit_result(
        self,
        current_issue: Issue,
        result: AuditResult,
        project_id: str,
    ) -> ResultOutcome:
        """Route an auditor's verdict for *current_issue*.

        The result is applied only when

        1. *current_issue*'s tracker status is ``In Validation``, and
        2. the ``(audit_id, target_state, evidence_fingerprint)`` tuple
           matches a pending or in-progress record in the audit chain.

        On :attr:`~oompah.terminal_audit.Verdict.PASS` the coordinator marks
        the matching record ``COMPLETED``, applies the audited terminal
        status to the tracker, and posts a concise result comment.  Any
        remaining pending target in the chain is left pending so a later
        auditor invocation can drive the next step; the returned
        ``advanced_target`` reports that next target for observability.

        On :attr:`~oompah.terminal_audit.Verdict.FAIL` the coordinator routes
        the tracker status through :func:`classify_failure_to_status` and
        marks the record ``COMPLETED`` with the classification recorded on
        the attempt.

        :attr:`~oompah.terminal_audit.Verdict.NEEDS_HUMAN` is rejected unless
        the ``message`` ends with actionable instructions or a question.

        ``ERROR`` verdicts, unparseable payloads, ``MALFORMED_RESULT``,
        ``INFRASTRUCTURE_ERROR``, and retry ceilings never apply a terminal
        status: the record stays pending and the task remains in
        ``In Validation`` so the auditor can retry (or a human can
        intervene) without the coordinator ever fail-open-ing to a pass.
        """

        if not isinstance(result, AuditResult):
            raise TypeError("result must be an AuditResult instance")

        lock = self._async_locks.setdefault(project_id, asyncio.Lock())
        async with lock:
            tracker = self._tracker_for_project(project_id)
            store = TerminalAuditMetadataStore(
                tracker, self._project_store, project_id
            )
            return self._apply_result_locked(
                store, tracker, current_issue, result, project_id
            )

    # ------------------------------------------------------------------
    # Public API — override_transition
    # ------------------------------------------------------------------

    async def override_transition(
        self,
        current_issue: Issue,
        requested_target: TargetState,
        authorized_actor: ContributorIdentity,
        project_id: str,
        evidence_fingerprint: EvidenceFingerprint,
        reason: str,
        project: Any = None,
    ) -> OverrideResult:
        """Apply an authorized owner override to bypass auditing.

        Directly applies a terminal status when authorized by a project owner,
        persisting an override audit record and human-readable comment before
        changing the task status.

        Parameters
        ----------
        current_issue:
            The task to override.  ``current_issue.identifier`` and
            ``current_issue.state`` are used for the override record.
        requested_target:
            The requested terminal lifecycle state.
        authorized_actor:
            The project owner requesting the override. Will be validated as
            authorized via project-owner rules.
        project_id:
            Managed-project ID that owns the issue.
        evidence_fingerprint:
            Current SHA-256 digest of the auditable evidence. Must match the
            task's current evidence to prevent stale overrides.
        reason:
            Non-empty human-readable justification for the override.
        project:
            Optional project object for authorization checks. If provided, must
            have ``status_label_authorized_logins``, ``status_actor_login``, or
            ``tracker_owner`` attributes.

        Returns
        -------
        OverrideResult
            ``.success`` is ``True`` when the override was persisted and applied.
            ``False`` when authorization failed, reason was blank, fingerprint was
            stale, or a tracker operation failed.

        Raises
        ------
        ValueError
            If ``requested_target`` cannot be parsed as a
            :class:`~oompah.terminal_audit.TargetState`, or if ``reason`` is
            blank/None.
        TypeError
            If ``authorized_actor`` is not a
            :class:`~oompah.terminal_audit.ContributorIdentity`.
        """
        requested_target = TargetState.from_raw(requested_target)
        if not isinstance(authorized_actor, ContributorIdentity):
            raise TypeError("authorized_actor must be a ContributorIdentity")
        if not isinstance(evidence_fingerprint, EvidenceFingerprint):
            raise TypeError("evidence_fingerprint must be an EvidenceFingerprint")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("reason must be a non-empty string")
        if not isinstance(project_id, str) or not project_id.strip():
            raise ValueError("project_id must be a non-empty string")

        lock = self._async_locks.setdefault(project_id, asyncio.Lock())
        async with lock:
            tracker = self._tracker_for_project(project_id)
            store = TerminalAuditMetadataStore(
                tracker, self._project_store, project_id
            )
            return self._override_transition_locked(
                store,
                tracker,
                current_issue,
                requested_target,
                authorized_actor,
                project_id,
                evidence_fingerprint,
                reason,
                project,
            )

    # ------------------------------------------------------------------
    # Internal helpers — all called while the per-project asyncio.Lock is held
    # ------------------------------------------------------------------

    def _transition_locked(
        self,
        store: TerminalAuditMetadataStore,
        tracker: TrackerProtocol,
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
                tracker.update_issue(identifier, status=IN_VALIDATION)
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
                tracker.add_comment(identifier, comment, author="oompah")
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
    # Result-application internals
    # ------------------------------------------------------------------

    def _apply_result_locked(
        self,
        store: TerminalAuditMetadataStore,
        tracker: TrackerProtocol,
        current_issue: Issue,
        result: AuditResult,
        project_id: str,
    ) -> ResultOutcome:
        identifier = current_issue.identifier
        decision = _ResultDecision()

        # --- CAS: verify the tracker still holds the issue in In Validation ---
        # We deliberately trust the caller's Issue payload here because the
        # coordinator owns the transition into In Validation and no other
        # writer moves an issue out of it while a chain is pending.  If the
        # caller passed a stale Issue the metadata update below will still
        # catch a chain drift; this is a fast reject for the common case.
        if canonicalize_status(current_issue.state or "") != IN_VALIDATION:
            return ResultOutcome(
                success=False,
                audit_id=result.audit_id,
                reason=ResultRejection.ISSUE_NOT_IN_VALIDATION,
            )

        # --- Needs-Human comments must be actionable before any state write ---
        if result.verdict == Verdict.NEEDS_HUMAN or (
            result.verdict == Verdict.FAIL
            and result.failure_classification in _NEEDS_HUMAN_CLASSES
        ):
            comment_text = _compose_needs_human_message(result)
            try:
                validate_needs_human_comment(comment_text)
            except Exception:  # tracker.TrackerError or ValueError
                return ResultOutcome(
                    success=False,
                    audit_id=result.audit_id,
                    reason=ResultRejection.NEEDS_HUMAN_NOT_ACTIONABLE,
                )

        def _updater(doc: TerminalAuditMetadata) -> TerminalAuditMetadata:
            # --- Duplicate-result idempotency ---
            applied_attempts = _load_applied_attempt_log(doc)
            if (
                result.attempt_id is not None
                and result.attempt_id in applied_attempts
            ):
                decision.outcome = ResultOutcome(
                    success=True,
                    audit_id=result.audit_id,
                    applied_status=_last_applied_status(doc, result.audit_id),
                    idempotent=True,
                )
                return doc

            # --- Locate the target record (CAS on audit_id/target/fingerprint) ---
            chain = list(doc.pending_chain)
            target_index: int | None = None
            for index, record in enumerate(chain):
                if record.audit_id != result.audit_id:
                    continue
                if record.target_state != result.target_state:
                    decision.outcome = ResultOutcome(
                        success=False,
                        audit_id=result.audit_id,
                        reason=ResultRejection.TARGET_MISMATCH,
                    )
                    return doc
                if record.evidence_fingerprint != result.evidence_fingerprint:
                    decision.outcome = ResultOutcome(
                        success=False,
                        audit_id=result.audit_id,
                        reason=ResultRejection.FINGERPRINT_MISMATCH,
                    )
                    return doc
                if record.request_state not in (
                    RequestState.PENDING,
                    RequestState.IN_PROGRESS,
                ):
                    decision.outcome = ResultOutcome(
                        success=False,
                        audit_id=result.audit_id,
                        reason=ResultRejection.STATE_MISMATCH,
                    )
                    return doc
                target_index = index
                break

            if target_index is None:
                decision.outcome = ResultOutcome(
                    success=False,
                    audit_id=result.audit_id,
                    reason=ResultRejection.AUDIT_NOT_FOUND,
                )
                return doc

            record = chain[target_index]
            now = _now_iso8601()
            attempt = _make_attempt(result, now)

            # --- Decide how to route the result ---
            action = _route_result(result, record.previous_state)

            if action.kind == "reject":
                decision.outcome = ResultOutcome(
                    success=False,
                    audit_id=result.audit_id,
                    reason=action.reason,
                )
                return doc

            # Record the attempt on the audit record.  The verdict, message,
            # and safe evidence are all captured before we commit any tracker
            # write — that way a crash after this update but before the
            # tracker write still leaves an auditable trail.
            updated_record = replace(
                record,
                attempts=[*record.attempts, attempt],
                updated_at=now,
            )

            if action.kind == "nonterminal":
                # Retry ceilings and infrastructure errors are recorded as an
                # attempt but the record stays PENDING/IN_PROGRESS so the
                # auditor can retry.  The task stays in In Validation.
                chain[target_index] = updated_record
                decision.outcome = ResultOutcome(
                    success=True,
                    audit_id=result.audit_id,
                    applied_status=None,
                    posted_comment=False,
                    reason=action.reason,
                )
                decision.keep_in_validation = True
                decision.applied_attempt = True
                # Record attempt_id in the applied log so a duplicate submit
                # is not routed a second time.
                new_unknown = _record_applied_attempt(doc, result.attempt_id)
                return replace(
                    doc, pending_chain=chain, unknown_fields=new_unknown
                )

            # Terminal decision.  Mark the record COMPLETED and, for FAIL
            # verdicts, also stamp the classification on it.
            completed = replace(
                updated_record,
                request_state=RequestState.COMPLETED,
                updated_at=now,
            )
            chain[target_index] = completed

            # Detect the next pending target so we can report it to the
            # caller and — for a passing Done in a Done→Merged chain — keep
            # the task in In Validation while the auditor drives Merged.
            next_pending = next(
                (
                    r for r in chain
                    if r.request_state
                    in (RequestState.PENDING, RequestState.IN_PROGRESS)
                ),
                None,
            )
            decision.advanced_target = (
                next_pending.target_state if next_pending is not None else None
            )

            new_unknown = _record_applied_attempt(doc, result.attempt_id)
            decision.target_status = action.status
            decision.comment_text = action.comment
            decision.audit_id = result.audit_id
            decision.applied_attempt = True
            decision.keep_in_validation = (
                action.kind == "pass" and next_pending is not None
            )
            return replace(doc, pending_chain=chain, unknown_fields=new_unknown)

        try:
            store.update(identifier, _updater)
        except TerminalAuditMetadataQuarantinedError:
            return ResultOutcome(
                success=False,
                audit_id=result.audit_id,
                reason=ResultRejection.METADATA_QUARANTINED,
            )

        if decision.outcome is not None:
            return decision.outcome

        assert decision.target_status is not None
        # --- Post the result comment before mutating status.  A tracker
        # failure to accept the comment must not leave the record without an
        # explanation, so we log and continue — the audit record already
        # holds the verdict and classification.
        posted = False
        if self._post_comments and decision.comment_text:
            try:
                tracker.add_comment(
                    identifier, decision.comment_text, author="oompah"
                )
                posted = True
            except Exception:
                logger.exception(
                    "Failed to post audit-result comment for %s", identifier
                )

        # --- Apply the target status.  For a passing Done+Merged chain we
        # keep the issue in In Validation so the auditor can drive Merged; a
        # single-target chain moves straight to its terminal state.
        applied_status = decision.target_status
        if decision.keep_in_validation:
            applied_status = IN_VALIDATION
        try:
            tracker.update_issue(identifier, status=applied_status)
        except Exception:
            logger.exception(
                "Failed to apply audit-result status %r for %s",
                applied_status,
                identifier,
            )

        return ResultOutcome(
            success=True,
            audit_id=decision.audit_id,
            applied_status=applied_status,
            posted_comment=posted,
            advanced_target=decision.advanced_target,
        )

    def _override_transition_locked(
        self,
        store: TerminalAuditMetadataStore,
        tracker: TrackerProtocol,
        current_issue: Issue,
        requested_target: TargetState,
        authorized_actor: ContributorIdentity,
        project_id: str,
        evidence_fingerprint: EvidenceFingerprint,
        reason: str,
        project: Any,
    ) -> OverrideResult:
        identifier = current_issue.identifier

        # Step 1: Validate both layers of the existing authorization model.
        # ``is_authorized_status_actor`` intentionally trusts the bot for
        # ordinary status-label reconciliation.  An override is stronger:
        # it must also pass ``is_project_owner``, which excludes bot-only and
        # auditor-only identities unless the project explicitly names them as
        # an owner.
        actor_login = authorized_actor.identity
        if not (
            is_authorized_status_actor(actor_login, project)
            and is_project_owner(actor_login, project)
        ):
            return OverrideResult(
                success=False,
                reason="actor is not authorized as project owner",
                error_code=OverrideRejection.UNAUTHORIZED_ACTOR,
            )

        # Step 2: Verify fingerprint matches current state
        try:
            document = store.read(identifier)
        except TerminalAuditMetadataQuarantinedError:
            return OverrideResult(
                success=False,
                reason="terminal-audit metadata is quarantined",
                error_code=OverrideRejection.METADATA_QUARANTINED,
            )
        except Exception:
            logger.exception("Failed to read terminal-audit metadata for %s", identifier)
            return OverrideResult(
                success=False,
                reason="failed to read metadata",
                error_code=OverrideRejection.METADATA_READ_FAILED,
            )

        # Check if the fingerprint matches any record for the requested target.
        fingerprint_mismatch = False
        for record in document.pending_chain:
            if (
                record.target_state == requested_target
                and record.evidence_fingerprint != evidence_fingerprint
            ):
                fingerprint_mismatch = True
                break

        if fingerprint_mismatch:
            return OverrideResult(
                success=False,
                reason="evidence fingerprint mismatch (stale override)",
                error_code=OverrideRejection.FINGERPRINT_MISMATCH,
            )

        # Step 3: Create and persist the override record
        now = _now_iso8601()
        override_record = OverrideRecord(
            override_id=_generate_override_id(),
            project_id=project_id,
            task_id=identifier,
            target_state=requested_target,
            evidence_fingerprint=evidence_fingerprint,
            authorized_by=authorized_actor,
            reason=reason,
            created_at=now,
        )

        # Step 4: Persist override record in metadata before status change
        def _updater(doc: TerminalAuditMetadata) -> TerminalAuditMetadata:
            """Atomically add the override record to metadata."""
            new_unknown = dict(doc.unknown_fields)

            # Store override records in a list
            overrides = new_unknown.get("oompah.terminal_override_records", [])
            if not isinstance(overrides, list):
                overrides = []

            overrides.append(override_record.to_dict())
            new_unknown["oompah.terminal_override_records"] = overrides

            return replace(doc, unknown_fields=new_unknown)

        try:
            store.update(identifier, _updater)
        except TerminalAuditMetadataQuarantinedError:
            return OverrideResult(
                success=False,
                reason="terminal-audit metadata is quarantined",
                error_code=OverrideRejection.METADATA_QUARANTINED,
            )
        except Exception:
            logger.exception("Failed to persist override record for %s", identifier)
            return OverrideResult(
                success=False,
                reason="failed to persist override record",
                error_code=OverrideRejection.METADATA_WRITE_FAILED,
            )

        # Step 5: Post explanatory comment before status change
        posted = False
        if self._post_comments:
            safe_actor = redact_terminal_audit_text(authorized_actor.identity)
            safe_reason = redact_terminal_audit_text(reason)
            comment = (
                f"Override by {safe_actor}: terminal transition to "
                f"{requested_target.value} applied by project owner.\n\n"
                f"Reason: {safe_reason}"
            )
            try:
                tracker.add_comment(identifier, comment, author="oompah")
                posted = True
            except Exception:
                logger.exception("Failed to post override comment for %s", identifier)
                return OverrideResult(
                    success=False,
                    override_id=override_record.override_id,
                    reason="failed to post override comment",
                    error_code=OverrideRejection.COMMENT_FAILED,
                )

        # Step 6: Apply terminal status
        target_status = _target_state_to_status(requested_target)
        try:
            tracker.update_issue(identifier, status=target_status)
        except Exception:
            logger.exception(
                "Failed to apply override status %r for %s",
                target_status,
                identifier,
            )
            return OverrideResult(
                success=False,
                reason="failed to update tracker status",
                error_code=OverrideRejection.STATUS_UPDATE_FAILED,
            )

        return OverrideResult(
            success=True,
            override_id=override_record.override_id,
            applied_status=target_status,
            posted_comment=posted,
            error_code=None,
        )

    def _tracker_for_project(self, project_id: str) -> TrackerProtocol:
        """Resolve the tracker used for a project-scoped request."""
        if callable(self._tracker):
            return self._tracker(project_id)
        return self._tracker


# ------------------------------------------------------------------
# Result routing helpers
# ------------------------------------------------------------------


@dataclass(frozen=True)
class _RoutingAction:
    """The routing decision derived from an :class:`AuditResult`.

    ``kind`` is one of ``"pass"``, ``"fail"``, ``"nonterminal"``, or
    ``"reject"``.  ``status`` is the tracker status to apply on ``pass`` or
    ``fail``.  ``comment`` is the safe result-comment text.  ``reason``
    carries the rejection reason for ``reject`` or the observability reason
    for ``nonterminal``.
    """

    kind: str
    status: str | None
    comment: str | None
    reason: str | None


def _route_result(
    result: AuditResult, previous_state: str | None
) -> _RoutingAction:
    """Return the routing decision for *result* — no fail-open path."""

    verdict = result.verdict

    if verdict == Verdict.PASS:
        return _RoutingAction(
            kind="pass",
            status=_target_state_to_status(result.target_state),
            comment=_compose_pass_message(result),
            reason=None,
        )

    if verdict == Verdict.NEEDS_HUMAN:
        return _RoutingAction(
            kind="fail",
            status=NEEDS_HUMAN,
            comment=_compose_needs_human_message(result),
            reason=None,
        )

    if verdict == Verdict.ERROR:
        # ERROR is explicitly listed as "never a pass" and never routes to a
        # terminal.  We keep the audit non-terminal and pending so a later
        # retry can supersede it.
        return _RoutingAction(
            kind="nonterminal",
            status=None,
            comment=None,
            reason=ResultRejection.UNPARSEABLE_VERDICT,
        )

    if verdict == Verdict.FAIL:
        if result.failure_classification is None:
            return _RoutingAction(
                kind="reject",
                status=None,
                comment=None,
                reason=ResultRejection.MISSING_CLASSIFICATION,
            )
        classification = result.failure_classification
        target_status = classify_failure_to_status(classification, previous_state)
        if target_status is None:
            # MALFORMED_RESULT / INFRASTRUCTURE_ERROR — leave nonterminal.
            return _RoutingAction(
                kind="nonterminal",
                status=None,
                comment=None,
                reason=(
                    ResultRejection.MALFORMED_RESULT
                    if classification == FailureClassification.MALFORMED_RESULT
                    else ResultRejection.RETRY_CEILING
                ),
            )
        if target_status == NEEDS_HUMAN:
            return _RoutingAction(
                kind="fail",
                status=NEEDS_HUMAN,
                comment=_compose_needs_human_message(result),
                reason=None,
            )
        return _RoutingAction(
            kind="fail",
            status=target_status,
            comment=_compose_fail_message(result, classification, target_status),
            reason=None,
        )

    # Any verdict not covered above (e.g. a future value the coordinator
    # does not yet understand) fails closed by leaving the audit nonterminal.
    return _RoutingAction(
        kind="nonterminal",
        status=None,
        comment=None,
        reason=ResultRejection.UNPARSEABLE_VERDICT,
    )


def _target_state_to_status(target: TargetState) -> str:
    if target == TargetState.DONE:
        return DONE
    if target == TargetState.MERGED:
        return MERGED
    if target == TargetState.ARCHIVED:
        return ARCHIVED
    raise ValueError(f"Unknown target state: {target!r}")


def _make_attempt(result: AuditResult, now: str) -> AuditAttempt:
    """Build the persisted :class:`AuditAttempt` for *result*."""

    request_state = (
        RequestState.COMPLETED
        if result.verdict in (Verdict.PASS, Verdict.FAIL, Verdict.NEEDS_HUMAN)
        else RequestState.IN_PROGRESS
    )
    if result.verdict == Verdict.ERROR:
        request_state = RequestState.IN_PROGRESS
    attempt_id = result.attempt_id or f"attempt-{uuid.uuid4().hex[:12]}"
    return AuditAttempt(
        attempt_id=attempt_id,
        target_state=result.target_state,
        evidence_fingerprint=result.evidence_fingerprint,
        request_state=request_state,
        verdict=result.verdict,
        failure_classification=result.failure_classification,
        requested_by=result.auditor,
        created_at=now,
        completed_at=(
            now
            if request_state == RequestState.COMPLETED
            else None
        ),
    )


# ------------------------------------------------------------------
# Comment composition
# ------------------------------------------------------------------


_ACTION_TAIL_RE = re.compile(
    r"(?:\?|\b(?:human action required|required|please|you (?:must|need to|should)|"
    r"(?:review|confirm|provide|answer|choose|approve|decide|inspect|resolve|add|"
    r"move|close|retry|run|restore|archive|update)\b))",
    re.IGNORECASE,
)


def _compose_pass_message(result: AuditResult) -> str:
    """Compose the result comment posted on ``PASS``.

    Only the auditor's message (which is trusted to be redacted) is echoed
    verbatim.  Safe-evidence keys are surfaced separately when present.
    """

    body = _sanitize_line(result.message) if result.message else "Audit verdict: PASS."
    parts = [f"Audit PASS — {result.target_state.value}", body]
    evidence_line = _format_safe_evidence_line(result.safe_evidence)
    if evidence_line:
        parts.append(evidence_line)
    return "\n\n".join(parts)


def _compose_fail_message(
    result: AuditResult,
    classification: FailureClassification,
    target_status: str,
) -> str:
    body = (
        _sanitize_line(result.message)
        if result.message
        else "Audit verdict: FAIL."
    )
    return (
        f"Audit FAIL — {classification.value.replace('_', ' ')}. "
        f"Routing task to {target_status}.\n\n{body}"
    )


def _compose_needs_human_message(result: AuditResult) -> str:
    body = _sanitize_line(result.message) if result.message else ""
    header = f"Needs Human — {result.target_state.value} audit requires operator input."
    if not body:
        body = "The auditor could not produce a safe verdict."
    combined = f"{header}\n\n{body}"
    if not _ACTION_TAIL_RE.search(combined):
        combined = combined.rstrip() + _NEEDS_HUMAN_HINT
    return combined


def _sanitize_line(value: str) -> str:
    """Trim whitespace and collapse trailing punctuation for comment lines.

    The auditor is expected to have redacted its own output before calling
    the coordinator; this function only tidies whitespace.
    """

    return str(value).strip()


def _format_safe_evidence_line(safe: Mapping[str, Any] | None) -> str:
    if not safe:
        return ""
    items = []
    for key, value in safe.items():
        if isinstance(value, str) and value.strip():
            items.append(f"- {key}: {value.strip()}")
    if not items:
        return ""
    return "Safe evidence:\n" + "\n".join(items)


# ------------------------------------------------------------------
# Applied-result attempt log helpers
# ------------------------------------------------------------------


def _load_applied_attempt_log(doc: TerminalAuditMetadata) -> dict[str, str]:
    raw = doc.unknown_fields.get(_APPLIED_RESULTS_KEY)
    if not isinstance(raw, dict):
        return {}
    return {str(key): str(value) for key, value in raw.items() if isinstance(key, str)}


def _last_applied_status(
    doc: TerminalAuditMetadata, audit_id: str | None
) -> str | None:
    for record in doc.pending_chain:
        if record.audit_id == audit_id and record.request_state == RequestState.COMPLETED:
            return _target_state_to_status(record.target_state)
    return None


def _record_applied_attempt(
    doc: TerminalAuditMetadata, attempt_id: str | None
) -> dict[str, Any]:
    """Return an updated ``unknown_fields`` dict with *attempt_id* recorded."""

    new_unknown = dict(doc.unknown_fields)
    if attempt_id is None:
        return new_unknown
    log = _load_applied_attempt_log(doc)
    log[attempt_id] = _now_iso8601()
    if len(log) > _MAX_APPLIED_RESULTS_MEMORY:
        # Retain the newest half by insertion order.
        items = list(log.items())[-(_MAX_APPLIED_RESULTS_MEMORY // 2):]
        log = dict(items)
    new_unknown[_APPLIED_RESULTS_KEY] = log
    return new_unknown


# ------------------------------------------------------------------
# Chain-building helpers (module-level, no coordinator state required)
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
    * If a ``PENDING`` or ``IN_PROGRESS`` ``Done`` audit exists, reuse that
      queued completion work and create only the ``Merged`` record.  This keeps
      retries from scheduling duplicate Done audits.
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
    active_done = next(
        (
            r for r in current_chain
            if r.target_state == TargetState.DONE
            and r.request_state in (RequestState.PENDING, RequestState.IN_PROGRESS)
        ),
        None,
    )

    entries: list[TerminalAuditRecord] = []
    if completed_done is None and active_done is None:
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


def _generate_override_id() -> str:
    """Return a unique override record identifier."""
    return f"override-{uuid.uuid4().hex[:12]}"


def _now_iso8601() -> str:
    """Return the current UTC time in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


# Compatibility alias for callers that reason in terms of the FAIL routing
# helper name used by the spec rather than the private function.
def route_failure_status(
    classification: FailureClassification,
    previous_state: str | None = None,
) -> str | None:
    """Alias for :func:`classify_failure_to_status`."""

    return classify_failure_to_status(classification, previous_state)


__all__ = [
    "AuditResult",
    "OverrideRejection",
    "OverrideResult",
    "ResultOutcome",
    "ResultRejection",
    "TerminalTransitionCoordinator",
    "TransitionResult",
    "classify_failure_to_status",
    "route_failure_status",
]
