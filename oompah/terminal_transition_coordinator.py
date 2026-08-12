"""Idempotent terminal-transition staging with durable audit chains.

The :class:`TerminalTransitionCoordinator` is the single entry point for
requesting terminal lifecycle transitions (``Done``, ``Merged``, ``Archived``)
for tracked tasks.  It stages each request by persisting an audit chain
*before* moving the task to ``In Validation`` status, ensuring safe recovery
after a process restart.

Concurrency model
-----------------
The project store's per-project ``threading.RLock`` serialises the complete
transition operation across the server and orchestrator event loops.  Async
entry points execute their synchronous tracker work in a worker thread while
holding that shared lock, so one coordinator can safely serve multiple event
loops without binding an ``asyncio.Lock`` to whichever loop happened to wait
first.  The inner
:class:`~oompah.terminal_audit_metadata.TerminalAuditMetadataStore` re-enters
the same lock for each metadata operation.

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
import hashlib
import json
import logging
import re
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any

from oompah.integration import is_direct_epic_maintenance_issue
from oompah.models import (
    Issue,
    EPIC_AUDIT_REPAIR_LABEL,
    EPIC_AUDIT_REPAIR_METADATA_KEY,
    EPIC_AUDIT_REPAIR_METADATA_VERSION,
)
from oompah.statuses import (
    ARCHIVED,
    DONE,
    IN_PROGRESS,
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
    AuditAttemptOrigin,
    AuditRevisionBinding,
    ContributorIdentity,
    EvidenceFingerprint,
    FailureClassification,
    OverrideRecord,
    RequestState,
    TargetState,
    TerminalAuditRecord,
    Verdict,
    archive_default_branch_fallback_authorized,
    build_revision_candidate_list,
    compute_integrated_evidence_fingerprint_variants,
    compute_issue_evidence_fingerprint,
    requires_workflow_revision,
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


class TerminalTransitionBusyError(RuntimeError):
    """Project mutation authority was not available within its control SLO."""

_QUEUED_COMMENT_KEY = "queued_comment_posted"
"""Metadata key that tracks whether the queued comment has been posted."""

_APPLIED_RESULTS_KEY = "applied_result_attempts"
"""Metadata key that records attempt IDs whose result has already been applied."""

_TERMINAL_RETIREMENTS_KEY = "oompah.terminal_audit_retirements"
"""Durable fingerprints for terminal decisions already applied to a task."""

_TERMINAL_RESULT_INTENTS_KEY = "oompah.terminal_audit_result_intents"
"""Durable status-write intents awaiting confirmation."""

_TERMINAL_REARM_HISTORY_KEY = "oompah.terminal_audit_rearm_history"
"""Durable actor/reason evidence for explicit terminal-audit re-arms."""

_TRACKER_EVIDENCE_PROJECTIONS_KEY = "oompah.terminal_audit_tracker_projections"
"""Per-audit canonical tracker projections used for result-boundary CAS."""

_EVIDENCE_REARM_CLASSES: frozenset[FailureClassification] = frozenset({
    FailureClassification.MISSING_EVIDENCE,
})
_AUDIT_REARM_CLASSES: frozenset[FailureClassification] = frozenset({
    FailureClassification.NO_AUDITOR,
    FailureClassification.INFRASTRUCTURE_ERROR,
    FailureClassification.POLICY_INCOMPATIBILITY,
    FailureClassification.MALFORMED_RESULT,
    FailureClassification.FINALIZATION_FAILURE,
    FailureClassification.SCHEDULER_PAUSE,
})


def _audit_recovery_classifications(
    record: TerminalAuditRecord,
) -> set[FailureClassification] | None:
    """Return a trustworthy failed-attempt classification set for *record*.

    Recovery authority is derived from the complete attempt history, not just
    the last classification written to a record.  Reject copied/corrupt rows
    whose target or fingerprint does not belong to the containing audit, and
    reject a PASS (or a verdict/classification combination that cannot have
    produced the advertised recovery state).
    """

    if not record.attempts:
        return None
    classifications: set[FailureClassification] = set()
    for attempt in record.attempts:
        if (
            attempt.target_state != record.target_state
            or attempt.evidence_fingerprint != record.evidence_fingerprint
        ):
            return None
        raw_classification = attempt.failure_classification
        if raw_classification is None and attempt.verdict == Verdict.ERROR:
            # Older execution failures predate durable classifications. ERROR
            # is itself a non-substantive transport/executor outcome; retain
            # owner recovery for those exact completed audit generations.
            classification = FailureClassification.INFRASTRUCTURE_ERROR
        else:
            try:
                classification = FailureClassification.from_raw(
                    raw_classification
                )
            except (TypeError, ValueError):
                return None
        verdict = attempt.verdict
        if verdict is None:
            if classification not in _AUDIT_REARM_CLASSES:
                return None
        if verdict == Verdict.PASS:
            return None
        if verdict == Verdict.NEEDS_HUMAN:
            if not (
                classification == FailureClassification.INFRASTRUCTURE_ERROR
                and attempt.origin
                == AuditAttemptOrigin.COORDINATOR_RETRY_EXHAUSTION
            ):
                return None
        elif verdict not in (None, Verdict.ERROR, Verdict.FAIL):
            return None
        classifications.add(classification)
    return classifications


def _classified_audit_recovery_action(record: TerminalAuditRecord) -> str:
    """Classify a completed or durably superseded failed audit record."""

    classifications = _audit_recovery_classifications(record)
    if not classifications:
        return "audit_override"
    if classifications <= _EVIDENCE_REARM_CLASSES:
        return "audit_retry_evidence_addendum"
    if classifications <= _AUDIT_REARM_CLASSES:
        return "audit_retry"
    return "audit_override"


def accepted_audit_recovery_action(record: TerminalAuditRecord) -> str:
    """Return the only owner recovery action accepted for *record*.

    The action vocabulary intentionally mirrors the terminal status API.  A
    recovery alert can therefore be rendered from this function without
    suggesting an evidence addendum for a record that the coordinator will
    reject.  Unknown, incomplete, or mixed failure histories fall back to an
    owner override, which preserves the fail-closed boundary.
    """

    if record.request_state != RequestState.COMPLETED:
        return "audit_override"
    return _classified_audit_recovery_action(record)

_OVERRIDE_RECORDS_KEY = "oompah.terminal_override_records"
"""Metadata key containing the historical owner-override ledger."""


def _normalize_evidence_addendum(
    raw: Mapping[str, Any],
    expected_fingerprint: EvidenceFingerprint,
) -> dict[str, Any]:
    """Validate and reduce the owner evidence-only rearm contract.

    The addendum is deliberately not evidence for the auditor and does not
    participate in the task fingerprint.  It is a signed-by-authorization
    statement that named quality-gate evidence was supplied after a
    ``MISSING_EVIDENCE`` result.  Persist only bounded, redacted fields so
    operator tails cannot become a second secret/prose storage path.
    """

    if not isinstance(raw, Mapping):
        raise TypeError("evidence_addendum must be a mapping")
    supplied = raw.get("evidence_fingerprint", raw.get("fingerprint"))
    if isinstance(supplied, Mapping):
        supplied = supplied.get("digest", supplied.get("sha256"))
    if supplied != expected_fingerprint.digest:
        raise ValueError("evidence_addendum fingerprint does not match current evidence")

    checks = raw.get("checks", raw.get("gates"))
    if not isinstance(checks, list) or not checks:
        raise ValueError("evidence_addendum requires a non-empty checks list")
    normalized_checks: list[dict[str, str]] = []
    for check in checks:
        if isinstance(check, str):
            name = check.strip()
            result = "pass"
            tail = None
        elif isinstance(check, Mapping):
            name = str(check.get("name", check.get("command", ""))).strip()
            result = str(
                check.get("result", check.get("status", check.get("verdict", "")))
            ).strip().lower()
            tail_raw = check.get("tail")
            tail = tail_raw if isinstance(tail_raw, str) else None
        else:
            raise TypeError("evidence_addendum checks must be strings or mappings")
        if not name or result not in {"pass", "passed", "ok", "success", "successful"}:
            raise ValueError("each evidence addendum check must be a successful named check")
        item = {
            "name": redact_terminal_audit_text(name),
            "result": "pass",
        }
        if tail is not None:
            item["tail"] = redact_terminal_audit_text(tail)
        normalized_checks.append(item)

    normalized: dict[str, Any] = {
        "version": 1,
        "evidence_fingerprint": expected_fingerprint.digest,
        "checks": normalized_checks,
    }
    summary = raw.get("summary")
    if summary is not None:
        if not isinstance(summary, str) or not summary.strip():
            raise ValueError("evidence_addendum summary must be a non-empty string")
        normalized["summary"] = redact_terminal_audit_text(summary.strip())
    return normalized

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
    FailureClassification.POLICY_INCOMPATIBILITY,
    FailureClassification.SCHEDULER_PAUSE,
})
_NON_SUBSTANTIVE_REARM_CLASSES: frozenset[FailureClassification] = (
    _NONTERMINAL_CLASSES
    | {
        FailureClassification.NO_AUDITOR,
        FailureClassification.FINALIZATION_FAILURE,
    }
)


def _is_non_substantive_retry_attempt(attempt: AuditAttempt) -> bool:
    """Return whether *attempt* contains only retry/execution evidence.

    A structured ``ERROR`` may legitimately have no classification.  Every
    other eligible attempt must carry one of the classifications that cannot
    repair or terminate implementation work.  Explicit PASS results and any
    substantive failure classification remain ineligible even if malformed
    producer data attached a contradictory retry-only field to the attempt.

    ``NEEDS_HUMAN`` with a retry-only classification is retained only for a
    durable exhaustion projection explicitly marked as coordinator-authored
    (for example, an exhausted finalization transport).  Model-submitted
    results cannot attach that provenance, so their requests for human judgment
    remain substantive even when they carry a contradictory retry-only class.
    """

    if attempt.verdict is Verdict.PASS:
        return False
    classification = attempt.failure_classification
    if attempt.verdict is Verdict.NEEDS_HUMAN:
        return bool(
            attempt.origin is AuditAttemptOrigin.COORDINATOR_RETRY_EXHAUSTION
            and classification in _NON_SUBSTANTIVE_REARM_CLASSES
        )
    if classification in _NON_SUBSTANTIVE_REARM_CLASSES:
        return True
    return attempt.verdict is Verdict.ERROR and classification is None


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


def _workflow_revision_migration_status(record: TerminalAuditRecord) -> str:
    """Return the strongest safe state predating an unbound workflow audit.

    Pre-cutover workflow requests cannot be completed because they lack the
    immutable workflow decision revision.  Recovery may restore a recorded
    terminal state only when it is strictly earlier than the requested target;
    otherwise ``Open`` is the conservative actionable fallback.
    """

    previous = (
        canonicalize_status(record.previous_state)
        if record.previous_state
        else ""
    )
    if previous and previous != IN_VALIDATION and previous not in TERMINAL_STATUSES:
        return previous
    if record.target_state is TargetState.MERGED and previous == DONE:
        return DONE
    if record.target_state is TargetState.ARCHIVED and previous in {DONE, MERGED}:
        return previous
    return OPEN


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

    idempotent: bool = False
    """``True`` when an already-applied identical override was replayed."""

    overridden_audit_ids: list[str] = field(default_factory=list)
    """Live audit records cancelled after this owner override."""

    retired_alert_audit_ids: list[str] = field(default_factory=list)
    """Historical identities whose actionable alerts were retired as well."""

    cleanup_diagnostics: list[dict[str, str]] = field(default_factory=list)
    """Best-effort post-commit cleanup issues that callers should surface."""

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
    DELIVERY_MUTATION_IN_PROGRESS = "delivery_mutation_in_progress"
    LIFECYCLE_INCOMPATIBLE = "lifecycle_incompatible"
    FINALIZATION_PENDING = "finalization_pending"


@dataclass
class TransitionResult:
    """Outcome of a :meth:`TerminalTransitionCoordinator.request_transition` call."""

    success: bool
    """``True`` when the request was staged or coalesced with an existing identical request."""

    audit_id: str | None = None
    """``audit_id`` of the first new record in the chain, or the coalesced record."""

    audit_ids: list[str] = field(default_factory=list)
    """All new audit IDs in this request, including multi-target chains."""

    queued_targets: list[TargetState] = field(default_factory=list)
    """Ordered list of :class:`~oompah.terminal_audit.TargetState` values in the new chain."""

    coalesced: bool = False
    """``True`` when the request was deduplicated against an identical pending audit."""

    status_repaired: bool = False
    """``True`` when a coalesced synchronous request restored In Validation."""

    applied_status: str | None = None
    """Exact status restored from an already-completed durable disposition."""

    status_staged: bool = False
    """``True`` when this call confirmed the task in ``In Validation``."""

    superseded_audit_id: str | None = None
    """Last prior audit superseded by changed evidence (compatibility field)."""

    superseded_audit_ids: list[str] = field(default_factory=list)
    """All prior audits superseded while normalizing the requested chain."""

    cancelled_audit_ids: list[str] = field(default_factory=list)
    """Live duplicate records retired while coalescing this request."""

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
    questions: tuple[str, ...] = ()
    instructions: tuple[str, ...] = ()
    attempt_origin: AuditAttemptOrigin | None = None

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
        if self.attempt_origin is not None:
            object.__setattr__(
                self,
                "attempt_origin",
                AuditAttemptOrigin.from_raw(self.attempt_origin),
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
        for field_name in ("questions", "instructions"):
            values = getattr(self, field_name)
            if isinstance(values, list):
                values = tuple(values)
                object.__setattr__(self, field_name, values)
            if not isinstance(values, tuple) or not all(
                isinstance(value, str) for value in values
            ):
                raise TypeError(f"AuditResult.{field_name} must be a sequence of strings")


def _is_safe_retry_exhaustion_escalation(result: AuditResult) -> bool:
    """Return whether evidence drift may safely escalate *result* to a human.

    This provenance can only be attached by the coordinator after bounded
    retry exhaustion.  The result cannot approve a terminal transition or
    reopen implementation work: it only moves an exact, still-pending audit
    generation from ``In Validation`` to ``Needs Human``.  That makes the
    escalation safe when a legacy audit predates the tracker-projection
    ledger or a forge/configuration cutover changed the live projection.
    """

    return bool(
        result.verdict is Verdict.NEEDS_HUMAN
        and result.attempt_origin
        is AuditAttemptOrigin.COORDINATOR_RETRY_EXHAUSTION
        and result.failure_classification in _NON_SUBSTANTIVE_REARM_CLASSES
    )


class ResultRejection:
    """Reason strings used when :meth:`apply_audit_result` rejects a result."""

    AUDIT_NOT_FOUND = "audit not found in pending chain"
    AUDIT_OWNERSHIP_MISMATCH = "audit does not belong to the requested task or project"
    TARGET_MISMATCH = "target state does not match audit"
    FINGERPRINT_MISMATCH = "evidence fingerprint does not match audit"
    REVISION_BINDING_MISMATCH = (
        "auditor attempt revision binding does not match audit authority"
    )
    STATE_MISMATCH = "audit is no longer pending or in progress"
    ISSUE_NOT_IN_VALIDATION = "issue is not in In Validation"
    CURRENT_EVIDENCE_UNAVAILABLE = "current task evidence could not be refreshed"
    PREREQUISITE_NOT_COMPLETED = "Done prerequisite has not passed for Merged audit"
    CURRENT_EVIDENCE_MISMATCH = "current task evidence no longer matches audit"
    WORKFLOW_REVISION_MISSING = (
        "workflow-authored audit lacks its completion decision revision"
    )
    MALFORMED_RESULT = "audit result is malformed"
    METADATA_QUARANTINED = "terminal-audit metadata is quarantined"
    NEEDS_HUMAN_NOT_ACTIONABLE = (
        "Needs Human comment must end with instructions or a question"
    )
    MISSING_CLASSIFICATION = "FAIL verdict requires a failure classification"
    UNPARSEABLE_VERDICT = "unparseable verdict"
    RETRY_CEILING = "retry ceiling reached; verdict left pending"
    LIFECYCLE_INCOMPATIBLE = "terminal lifecycle is incompatible with shared-epic landing"


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
    ``cancelled_audit_ids`` contains any sibling audits cancelled due to
    duplicate fingerprint detection.
    """

    success: bool
    audit_id: str | None = None
    applied_status: str | None = None
    posted_comment: bool = False
    idempotent: bool = False
    advanced_target: TargetState | None = None
    advanced_audit_id: str | None = None
    cancelled_audit_ids: list[str] = field(default_factory=list)
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
        "superseded_ids",
        "already_posted",
        "cancelled_audit_ids",
    )

    def __init__(self) -> None:
        self.early_result: TransitionResult | None = None
        self.new_entries: list[TerminalAuditRecord] = []
        self.superseded_id: str | None = None
        self.superseded_ids: list[str] = []
        self.already_posted: bool = False
        self.cancelled_audit_ids: list[str] = []


class _ResultDecision:
    """Internal mutable holder used to pass state out of the result updater."""

    __slots__ = (
        "outcome",
        "target_status",
        "comment_text",
        "audit_id",
        "advanced_target",
        "advanced_audit_id",
        "applied_attempt",
        "keep_in_validation",
        "cancelled_audit_ids",
    )

    def __init__(self) -> None:
        self.outcome: ResultOutcome | None = None
        self.target_status: str | None = None
        self.comment_text: str | None = None
        self.audit_id: str | None = None
        self.advanced_target: TargetState | None = None
        self.advanced_audit_id: str | None = None
        self.applied_attempt: bool = False
        self.keep_in_validation: bool = False
        self.cancelled_audit_ids: list[str] = []


# ---------------------------------------------------------------------------
# Coordinator
# ---------------------------------------------------------------------------


class TerminalTransitionCoordinator:
    """Stage terminal-status transitions into durable audit chains.

    One coordinator instance is created during server bootstrap and owned by
    the orchestrator.  It is safe for concurrent calls from different asyncio
    tasks and event loops because all per-project state mutations happen
    inside the project store's cross-thread reentrant lock.

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
        metrics: Any | None = None,
        revoke_delivery_authority: Callable[[str, str], bool | None] | None = None,
        revoke_auditor_authority: Callable[[str, str], None] | None = None,
        release_audit_budget_reservation: Callable[[str, str], None] | None = None,
        clear_audit_alert: Callable[[str, str, str], None] | None = None,
        clear_integrated_audit_recovery_alert: Callable[[str, str], None]
        | None = None,
        validate_terminal_transition: Callable[[Issue, TargetState, str], str | None]
        | None = None,
        owner_control_lock_timeout_seconds: float = 5.0,
    ) -> None:
        # The standalone API accepts one tracker, while the server passes a
        # project-aware factory because managed projects each have their own
        # tracker adapter.  Keeping both forms makes the coordinator useful in
        # small integrations and in the multi-project orchestrator.
        self._tracker = tracker
        self._project_store = project_store
        self._post_comments = post_comments
        # Optional observability sink.  Keeping this duck-typed preserves the
        # coordinator's tracker-neutral API for small integrations and older
        # callers while allowing the service to count lifecycle transitions.
        self._metrics = metrics
        # Delivery reconciliations may be executing a long quality gate in a
        # different thread.  Revoke their compare-and-swap ownership before
        # this coordinator acquires terminal authority so no stale result can
        # later overwrite an owner-approved terminal decision.
        self._revoke_delivery_authority = revoke_delivery_authority
        # Owner overrides acquire terminal authority over any currently
        # running independent auditor.  This callback is deliberately kept
        # separate from delivery revocation: applying an auditor result must
        # not revoke the very auditor that is submitting it.
        self._revoke_auditor_authority = revoke_auditor_authority
        # Run only after a successful owner override and after the project
        # mutation lock has been released. The service retains the claim when
        # a revoked auditor is still winding down and reconciles it on exit.
        self._release_audit_budget_reservation = release_audit_budget_reservation
        # This callback is intentionally optional for tracker-neutral users.
        # The service wires it to its alert registry so retirement clears the
        # in-memory dashboard identity while the durable metadata remains the
        # source of truth across a restart.
        self._clear_audit_alert = clear_audit_alert
        # Integrated delivery raises one task-level recovery alert in
        # addition to per-audit observability conditions.  Keep its cleanup
        # callback separate because it has no audit ID and must be cleared in
        # the same response that commits a retry or owner override.
        self._clear_integrated_audit_recovery_alert = (
            clear_integrated_audit_recovery_alert
        )
        # The orchestrator owns project/SCM-specific shared-epic knowledge.
        # Keep the coordinator as the single mutation boundary while letting
        # that owner supply a fail-closed lifecycle compatibility check.
        self._validate_terminal_transition = validate_terminal_transition
        timeout = float(owner_control_lock_timeout_seconds)
        if timeout <= 0:
            raise ValueError("owner_control_lock_timeout_seconds must be positive")
        self._owner_control_lock_timeout_seconds = timeout

    def _run_project_serialized(
        self,
        project_id: str,
        operation: Callable[[], Any],
    ) -> Any:
        """Run one complete transition under the cross-loop project lock."""

        with self._project_store.project_write_lock(project_id):
            return operation()

    def _run_owner_control_serialized(
        self,
        project_id: str,
        operation: Callable[[], Any],
    ) -> Any:
        """Run an authenticated owner-control mutation within its lock SLO."""

        lock = self._project_store.project_write_lock(project_id)
        acquire = getattr(lock, "acquire", None)
        release = getattr(lock, "release", None)
        if not callable(acquire) or not callable(release):
            # Compatibility for tracker-neutral context-manager doubles.
            wait_started = time.monotonic()
            with lock:
                acquired_at = time.monotonic()
                try:
                    return operation()
                finally:
                    self._record_metric(
                        "record_control_lock_timing",
                        project_id,
                        wait_seconds=acquired_at - wait_started,
                        hold_seconds=time.monotonic() - acquired_at,
                        timed_out=False,
                    )

        wait_started = time.monotonic()
        acquired = bool(
            acquire(timeout=self._owner_control_lock_timeout_seconds)
        )
        acquired_at = time.monotonic()
        if not acquired:
            self._record_metric(
                "record_control_lock_timing",
                project_id,
                wait_seconds=acquired_at - wait_started,
                hold_seconds=0.0,
                timed_out=True,
            )
            raise TerminalTransitionBusyError(
                "terminal control could not acquire project authority within "
                f"{self._owner_control_lock_timeout_seconds:g}s"
            )
        try:
            return operation()
        finally:
            released_at = time.monotonic()
            release()
            self._record_metric(
                "record_control_lock_timing",
                project_id,
                wait_seconds=acquired_at - wait_started,
                hold_seconds=released_at - acquired_at,
                timed_out=False,
            )

    def set_metrics(self, metrics: Any | None) -> None:
        """Attach or replace the service-owned audit metrics sink."""

        self._metrics = metrics

    def set_alert_clearer(
        self, callback: Callable[[str, str, str], None] | None
    ) -> None:
        """Attach the service alert-registry retirement callback."""

        self._clear_audit_alert = callback

    def _record_metric(self, method: str, *args: Any, **kwargs: Any) -> None:
        sink = self._metrics
        callback = getattr(sink, method, None) if sink is not None else None
        if callback is None:
            return
        try:
            callback(*args, **kwargs)
        except Exception:  # metrics must never change transition semantics
            logger.warning("terminal-audit metric %s failed", method, exc_info=True)

    def _clear_retired_alert(
        self, project_id: str, task_id: str, audit_id: str
    ) -> str | None:
        """Clear one retired audit from metrics and the live alert registry."""

        self._record_metric(
            "clear_actionable_alert", project_id, task_id, audit_id
        )
        callback = self._clear_audit_alert
        if callback is None:
            return None
        try:
            callback(project_id, task_id, audit_id)
        except Exception as exc:
            logger.warning(
                "terminal-audit alert cleanup failed for %s/%s/%s",
                project_id,
                task_id,
                audit_id,
                exc_info=True,
            )
            return str(exc)
        return None

    def _clear_integrated_recovery_alert(
        self, project_id: str, task_id: str
    ) -> None:
        """Clear the task-level integrated recovery alert after commit."""

        callback = self._clear_integrated_audit_recovery_alert
        if callback is None:
            return
        try:
            callback(project_id, task_id)
        except Exception:  # alert cleanup must not change transition semantics
            logger.warning(
                "integrated-audit recovery alert cleanup failed for %s/%s",
                project_id,
                task_id,
                exc_info=True,
            )

    def _revoke_delivery_for_terminal_transition(
        self,
        project_id: str,
        task_id: str,
    ) -> bool:
        """Withdraw delivery ownership or reject while an effect is admitted."""

        callback = self._revoke_delivery_authority
        if callback is None:
            return True
        try:
            return callback(project_id, task_id) is not False
        except Exception:  # terminal correctness must not depend on diagnostics
            logger.warning(
                "failed to revoke delivery authority for %s/%s",
                project_id,
                task_id,
                exc_info=True,
            )
            return False

    def _revoke_auditor_for_owner_override(
        self,
        project_id: str,
        task_id: str,
    ) -> None:
        """Withdraw live auditor authority before an owner override commits."""

        callback = self._revoke_auditor_authority
        if callback is None:
            return
        try:
            callback(project_id, task_id)
        except Exception:  # owner authority must remain fail-closed
            logger.warning(
                "failed to revoke auditor authority for %s/%s",
                project_id,
                task_id,
                exc_info=True,
            )

    def _lifecycle_conflict(
        self,
        current_issue: Issue,
        requested_target: TargetState,
        project_id: str,
    ) -> str | None:
        """Return a shared-epic lifecycle conflict before any mutation.

        Project/SCM-specific landing evidence belongs to the orchestrator, but
        every terminal boundary belongs to this coordinator.  The callback is
        therefore deliberately consulted by request, audit-result, override,
        and recovery callers.  A callback failure fails closed for Merged so a
        forge outage cannot turn unverifiable epic-branch work into a terminal
        child state.
        """

        if requested_target != TargetState.MERGED:
            return None
        callback = self._validate_terminal_transition
        if callback is None:
            return None
        try:
            conflict = callback(current_issue, requested_target, project_id)
        except Exception as exc:  # lifecycle enforcement must fail closed
            logger.warning(
                "Could not verify Merged lifecycle for %s/%s: %s",
                project_id,
                current_issue.identifier,
                exc,
                exc_info=True,
            )
            return (
                f"Merged transition for {current_issue.identifier} could not verify "
                "shared-epic landing evidence; the parent review must land on "
                "its configured target branch before this child can be Merged."
            )
        if isinstance(conflict, str) and conflict.strip():
            return conflict.strip()
        if conflict is False:
            return (
                f"Merged transition for {current_issue.identifier} is incompatible "
                "with the shared-epic lifecycle: the parent review must land on "
                "its configured target branch first."
            )
        return None

    def _resolve_revision_binding(
        self,
        issue: Issue,
        target: TargetState,
        project_id: str,
        *,
        previous_state: str | None,
        archive_default_branch_authorized: bool = False,
    ) -> AuditRevisionBinding | None:
        """Resolve request-time repository authority when the store supports it.

        Tracker-neutral embedders historically supplied only a project lock.
        They remain schema-compatible and are bound later by the orchestrator;
        the service ProjectStore binds here, before tracker refresh can alter
        normalized branch fields.
        """

        resolver_method = getattr(
            type(self._project_store),
            "resolve_audit_revision",
            None,
        )
        getter_method = getattr(type(self._project_store), "get", None)
        if resolver_method is None or getter_method is None:
            return None
        project = self._project_store.get(project_id)
        if project is None:
            raise ValueError(f"Unknown project: {project_id}")
        candidates = build_revision_candidate_list(
            issue,
            project_id,
            target_state=target,
            previous_state=previous_state,
            default_branch=project.default_branch,
            archive_default_branch_authorized=archive_default_branch_authorized,
        )
        unavailable: list[str] = []
        for candidate in candidates.candidates:
            try:
                selected_sha = self._project_store.resolve_audit_revision(
                    project_id,
                    candidate.revision,
                )
            except Exception as exc:  # noqa: BLE001 - duck-typed project store
                if "revision is unavailable" not in str(exc):
                    raise
                unavailable.append(candidate.revision)
                if candidates.immutable_shas_available:
                    break
                continue
            return AuditRevisionBinding(candidate.revision, selected_sha)
        tried = ", ".join(unavailable) if unavailable else "no permitted revision"
        raise ValueError(
            "terminal audit evidence has no safely resolvable revision "
            f"for {issue.identifier} (tried: {tried})"
        )

    def _request_revision_binding(
        self,
        store: TerminalAuditMetadataStore,
        issue: Issue,
        target: TargetState,
        project_id: str,
        fingerprint: EvidenceFingerprint,
        *,
        trigger_identity: ContributorIdentity,
        coalesce_pending_target: bool = False,
        workflow_revision: str | None = None,
    ) -> AuditRevisionBinding | None:
        """Reuse durable authority before resolving a new request binding."""

        try:
            document = store.read(issue.identifier)
        except TerminalAuditMetadataQuarantinedError:
            # Let _transition_locked preserve its canonical quarantine result.
            return None
        # Only active requests own reusable repository authority. A completed
        # row can share the canonical v1 fingerprint after its branch advances;
        # reusing that row's old SHA would acknowledge the new branch tip
        # without auditing it. Only fall back to a different fingerprint for
        # the live authority that ``coalesce_pending_target`` is specifically
        # meant to reuse.
        matching = next(
            (
                record
                for record in reversed(document.pending_chain)
                if record.target_state == target
                and record.request_state
                in (RequestState.PENDING, RequestState.IN_PROGRESS)
                and record.evidence_fingerprint == fingerprint
                and record.workflow_revision
                == workflow_revision
            ),
            None,
        )
        if matching is None and coalesce_pending_target:
            matching = next(
                (
                    record
                    for record in reversed(document.pending_chain)
                    if record.target_state == target
                    and record.request_state
                    in (RequestState.PENDING, RequestState.IN_PROGRESS)
                ),
                None,
            )
        if matching is not None:
            if matching.selected_ref is not None or matching.selected_sha is not None:
                return AuditRevisionBinding(
                    matching.selected_ref or "",
                    matching.selected_sha or "",
                )

        # If an active record needs a late legacy binding, its persisted
        # provenance—not a fresh coalescing caller—decides whether the aged
        # Done auto-archive exception can use the default branch.
        binding_authority_record = matching

        # A current immutable SHA can prove that an exact completed row still
        # names the request's authority without touching the repository. A
        # branch-backed completion cannot: resolve it again so
        # ``_transition_locked`` can compare bindings and either acknowledge
        # the exact completion or supersede/requeue the advanced revision.
        completed = next(
            (
                record
                for record in reversed(document.pending_chain)
                if record.target_state == target
                and record.request_state == RequestState.COMPLETED
                and record.evidence_fingerprint == fingerprint
                and record.workflow_revision
                == workflow_revision
            ),
            None,
        )
        if (
            completed is not None
            and completed.selected_ref is not None
            and completed.selected_sha is not None
        ):
            getter_method = getattr(type(self._project_store), "get", None)
            if getter_method is not None:
                project = self._project_store.get(project_id)
                if project is None:
                    raise ValueError(f"Unknown project: {project_id}")
                candidates = build_revision_candidate_list(
                    issue,
                    project_id,
                    target_state=target,
                    previous_state=completed.previous_state,
                    default_branch=project.default_branch,
                    archive_default_branch_authorized=(
                        archive_default_branch_fallback_authorized(
                            completed.previous_state,
                            completed.requested_by,
                        )
                    ),
                )
                if (
                    candidates.immutable_shas_available
                    and candidates.candidates
                    and candidates.candidates[0].revision
                    == completed.selected_sha
                ):
                    return AuditRevisionBinding(
                        completed.selected_ref,
                        completed.selected_sha,
                    )
        if binding_authority_record is not None:
            binding_previous_state = binding_authority_record.previous_state
            archive_default_branch_authorized = (
                archive_default_branch_fallback_authorized(
                    binding_authority_record.previous_state,
                    binding_authority_record.requested_by,
                )
            )
        elif completed is not None:
            binding_previous_state = completed.previous_state
            archive_default_branch_authorized = (
                archive_default_branch_fallback_authorized(
                    completed.previous_state,
                    completed.requested_by,
                )
            )
        else:
            binding_previous_state = issue.state or None
            archive_default_branch_authorized = (
                archive_default_branch_fallback_authorized(
                    issue.state or None,
                    trigger_identity,
                )
            )
        return self._resolve_revision_binding(
            issue,
            target,
            project_id,
            previous_state=binding_previous_state,
            archive_default_branch_authorized=archive_default_branch_authorized,
        )

    @staticmethod
    def _issue_exact_head(issue: Issue) -> str | None:
        """Return mutable task-owned revision authority, when present."""

        for value in (
            getattr(issue, "head_sha", None),
            getattr(issue, "review_head", None),
        ):
            rendered = str(value or "").strip().lower()
            if rendered:
                return rendered
        integration = getattr(issue, "integration", None)
        if isinstance(integration, Mapping):
            value = integration.get("head_sha")
        else:
            value = getattr(integration, "head_sha", None)
        return str(value or "").strip().lower() or None

    def _composed_landing_binding_conflict(
        self,
        issue: Issue,
        target: TargetState,
        trigger_identity: ContributorIdentity,
        project_id: str,
        mutation_guard: Callable[[], str | None] | None,
        binding: AuditRevisionBinding,
    ) -> str | None:
        """Re-prove the narrow lanes allowed external revision authority."""

        if target is not TargetState.MERGED:
            return "trusted composed landing revision requires a Merged transition"
        source = str(trigger_identity.source or "").strip().lower()
        parent_id = str(getattr(issue, "parent_id", None) or "").strip()
        if source == "orchestrator":
            if canonicalize_status(issue.state) != IN_PROGRESS:
                return (
                    "trusted root-epic landing revision requires a current "
                    "In Progress task"
                )
            if (
                str(getattr(issue, "issue_type", None) or "").strip().lower()
                != "epic"
            ):
                return "trusted root-epic landing revision requires an epic task"
            if parent_id:
                return "trusted root-epic landing revision requires a root epic"
        else:
            if canonicalize_status(issue.state) != DONE:
                return "trusted composed landing revision requires a current Done task"
            if not parent_id:
                return "trusted composed landing revision requires a parented task"
        if self._issue_exact_head(issue) is not None:
            return "trusted composed landing revision cannot replace a task-owned head"
        if str(getattr(issue, "project_id", None) or "").strip() != project_id:
            return "trusted composed landing revision project authority changed"
        if source not in {"integrator", "orchestrator"}:
            return "trusted composed landing revision requires integrator authority"
        if mutation_guard is None:
            return "trusted composed landing revision requires a workflow mutation guard"
        if binding.selected_ref != binding.selected_sha:
            return "trusted composed landing revision must use its exact SHA as the ref"
        resolver = getattr(self._project_store, "resolve_audit_revision", None)
        getter = getattr(self._project_store, "get", None)
        if not callable(resolver) or not callable(getter):
            return "trusted composed landing revision cannot be resolved for the project"
        if getter(project_id) is None:
            return "trusted composed landing revision project is unavailable"
        try:
            resolved = str(
                resolver(project_id, binding.selected_sha) or ""
            ).strip().lower()
        except Exception:  # noqa: BLE001 - project stores are duck-typed
            return "trusted composed landing revision is unavailable"
        if resolved != binding.selected_sha:
            return "trusted composed landing revision resolved to a different commit"
        return None

    def _landed_epic_validation_binding(
        self,
        issue: Issue,
        target: TargetState,
        trigger_identity: ContributorIdentity,
        project_id: str,
        mutation_guard: Callable[[], str | None] | None,
        landing_revision: str,
    ) -> AuditRevisionBinding:
        """Select the exact current target head for an already-landed epic.

        The landing SHA authorizes lifecycle containment; it does not freeze
        the target tree forever.  Root and nested epics therefore audit the
        freshly resolved default/parent-epic head after proving that head
        contains the immutable landing revision.  Ordinary task and
        standalone revision routing never enters this lane.
        """

        if target is not TargetState.MERGED:
            raise ValueError(
                "landed epic validation requires a Merged transition"
            )
        if (
            str(trigger_identity.source or "").strip().lower()
            != "orchestrator"
        ):
            raise ValueError(
                "landed epic validation requires orchestrator authority"
            )
        if str(getattr(issue, "issue_type", "") or "").strip().lower() != "epic":
            raise ValueError("landed epic validation requires an epic task")
        if canonicalize_status(issue.state) not in {
            IN_PROGRESS,
            IN_REVIEW,
            DONE,
        }:
            raise ValueError(
                "landed epic validation requires a current rollup state"
            )
        if str(getattr(issue, "project_id", "") or "").strip() != project_id:
            raise ValueError("landed epic validation project authority changed")
        if mutation_guard is None:
            raise ValueError(
                "landed epic validation requires a workflow mutation guard"
            )
        try:
            landing = AuditRevisionBinding(
                str(landing_revision or ""), str(landing_revision or "")
            ).selected_sha
        except ValueError as exc:
            raise ValueError(
                "landed epic validation requires an exact landing revision"
            ) from exc
        current_head = self._issue_exact_head(issue)
        if current_head is not None and current_head != landing:
            raise ValueError("landed epic validation task head changed")

        project = self._project_store.get(project_id)
        if project is None:
            raise ValueError("landed epic validation project is unavailable")
        parent_id = str(getattr(issue, "parent_id", None) or "").strip()
        if parent_id:
            tracker = self._tracker_for_project(project_id)
            fetch = getattr(tracker, "fetch_issue_detail", None)
            if not callable(fetch):
                raise ValueError(
                    "landed nested epic parent cannot be refreshed"
                )
            parent = fetch(parent_id)
            if (
                not isinstance(parent, Issue)
                or str(parent.identifier) != parent_id
                or str(getattr(parent, "issue_type", "") or "").strip().lower()
                != "epic"
                or (
                    str(getattr(parent, "project_id", "") or "").strip()
                    not in {"", project_id}
                )
            ):
                raise ValueError(
                    "landed nested epic parent topology is unavailable or changed"
                )
            branch_name = getattr(self._project_store, "epic_branch_name", None)
            if not callable(branch_name):
                raise ValueError(
                    "landed nested epic target routing is unavailable"
                )
            target_branch = str(branch_name(parent_id) or "").strip()
        else:
            target_branch = str(getattr(project, "default_branch", "") or "").strip()
        if not target_branch:
            raise ValueError("landed epic validation target is unavailable")
        target_ref = (
            target_branch
            if target_branch.startswith("origin/")
            else f"origin/{target_branch}"
        )
        resolver = getattr(
            self._project_store, "resolve_containing_audit_revision", None
        )
        if not callable(resolver):
            raise ValueError(
                "landed epic validation containment resolver is unavailable"
            )
        try:
            selected_sha = resolver(
                project_id,
                target_revision=target_ref,
                landing_revision=landing,
            )
        except Exception as exc:  # noqa: BLE001 - project stores are duck-typed
            raise ValueError(str(exc)) from exc
        return AuditRevisionBinding(target_ref, str(selected_sha or ""))

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
        *,
        mutation_guard: Callable[[], str | None] | None = None,
        revision_binding: AuditRevisionBinding | None = None,
        landing_revision: str | None = None,
        workflow_revision: str | None = None,
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

        def _operation() -> TransitionResult:
            if mutation_guard is not None:
                try:
                    precondition_conflict = mutation_guard()
                except Exception as exc:  # mutation authority must fail closed
                    precondition_conflict = (
                        "precondition verification failed: "
                        f"{type(exc).__name__}"
                    )
                if isinstance(precondition_conflict, str) and precondition_conflict.strip():
                    return TransitionResult(
                        success=False,
                        reason=(
                            "workflow_precondition_changed: "
                            + precondition_conflict.strip()
                        ),
                    )
            lifecycle_conflict = self._lifecycle_conflict(
                current_issue, requested_target, project_id
            )
            if lifecycle_conflict is not None:
                return TransitionResult(success=False, reason=lifecycle_conflict)
            selected_landing_revision = (
                str(landing_revision or "").strip().lower() or None
            )
            selected_binding = revision_binding
            if selected_landing_revision is not None:
                if revision_binding is not None:
                    return TransitionResult(
                        success=False,
                        reason=(
                            "landed epic validation cannot accept a caller-selected "
                            "validation binding"
                        ),
                    )
                try:
                    selected_binding = self._landed_epic_validation_binding(
                        current_issue,
                        requested_target,
                        trigger_identity,
                        project_id,
                        mutation_guard,
                        selected_landing_revision,
                    )
                except Exception as exc:  # noqa: BLE001 - fail closed before mutation
                    return TransitionResult(success=False, reason=str(exc))
            elif revision_binding is not None:
                binding_conflict = self._composed_landing_binding_conflict(
                    current_issue,
                    requested_target,
                    trigger_identity,
                    project_id,
                    mutation_guard,
                    revision_binding,
                )
                if binding_conflict is not None:
                    return TransitionResult(success=False, reason=binding_conflict)
            tracker = self._tracker_for_project(project_id)
            store = TerminalAuditMetadataStore(
                tracker, self._project_store, project_id
            )
            if selected_binding is None:
                try:
                    selected_binding = self._request_revision_binding(
                        store,
                        current_issue,
                        requested_target,
                        project_id,
                        evidence_fingerprint,
                        trigger_identity=trigger_identity,
                        workflow_revision=(
                            workflow_revision
                        ),
                    )
                except Exception as exc:  # noqa: BLE001 - fail closed before mutation
                    return TransitionResult(success=False, reason=str(exc))
            if not self._revoke_delivery_for_terminal_transition(
                project_id,
                current_issue.identifier,
            ):
                return TransitionResult(
                    success=False,
                    reason="delivery_mutation_in_progress",
                )
            outcome = self._transition_locked(
                store,
                tracker,
                current_issue,
                requested_target,
                trigger_identity,
                project_id,
                evidence_fingerprint,
                revision_binding=selected_binding,
                landing_revision=selected_landing_revision,
                workflow_revision=workflow_revision,
                ensure_validation_on_coalesce=True,
            )
            if outcome.success:
                superseded_ids = outcome.superseded_audit_ids or (
                    [outcome.superseded_audit_id]
                    if outcome.superseded_audit_id
                    else []
                )
                for superseded_audit_id in superseded_ids:
                    self._record_metric(
                        "record_stale_discarded",
                        project_id,
                        current_issue.identifier,
                        superseded_audit_id,
                    )
                    self._clear_retired_alert(
                        project_id,
                        current_issue.identifier,
                        superseded_audit_id,
                    )
                if not outcome.coalesced:
                    audit_ids = outcome.audit_ids or (
                        [outcome.audit_id] if outcome.audit_id else []
                    )
                    for audit_id in audit_ids:
                        self._record_metric(
                            "record_queued",
                            project_id,
                            current_issue.identifier,
                            audit_id,
                        )
            for cancelled_audit_id in outcome.cancelled_audit_ids:
                self._record_metric(
                    "record_stale_discarded",
                    project_id,
                    current_issue.identifier,
                    cancelled_audit_id,
                )
                self._clear_retired_alert(
                    project_id, current_issue.identifier, cancelled_audit_id
                )
            return outcome

        return await asyncio.to_thread(
            self._run_project_serialized,
            project_id,
            _operation,
        )

    def request_transition_sync(
        self,
        current_issue: Issue,
        requested_target: TargetState,
        trigger_identity: ContributorIdentity,
        project_id: str,
        evidence_fingerprint: EvidenceFingerprint,
        *,
        coalesce_pending_target: bool = False,
        ensure_validation_on_coalesce: bool = False,
        queued_comment: str | None = None,
    ) -> TransitionResult:
        """Stage a transition from a synchronous maintenance worker.

        Tracker metadata provides the cross-thread/project lock for the
        read-modify-write operation.  This entry point is intentionally for
        bounded maintenance work that cannot await :meth:`request_transition`.
        ``coalesce_pending_target`` is used by automatic retirement: a pending
        archive is never superseded merely because a later maintenance pass
        has a different timestamp in its retention evidence.
        """
        requested_target = TargetState.from_raw(requested_target)

        def _operation() -> TransitionResult:
            lifecycle_conflict = self._lifecycle_conflict(
                current_issue, requested_target, project_id
            )
            if lifecycle_conflict is not None:
                return TransitionResult(success=False, reason=lifecycle_conflict)
            tracker = self._tracker_for_project(project_id)
            store = TerminalAuditMetadataStore(
                tracker, self._project_store, project_id
            )
            try:
                revision_binding = self._request_revision_binding(
                    store,
                    current_issue,
                    requested_target,
                    project_id,
                    evidence_fingerprint,
                    trigger_identity=trigger_identity,
                    coalesce_pending_target=coalesce_pending_target,
                )
            except Exception as exc:  # noqa: BLE001 - fail closed before mutation
                return TransitionResult(success=False, reason=str(exc))
            if not self._revoke_delivery_for_terminal_transition(
                project_id,
                current_issue.identifier,
            ):
                return TransitionResult(
                    success=False,
                    reason="delivery_mutation_in_progress",
                )
            return self._transition_locked(
                store,
                tracker,
                current_issue,
                requested_target,
                trigger_identity,
                project_id,
                evidence_fingerprint,
                revision_binding=revision_binding,
                coalesce_pending_target=coalesce_pending_target,
                ensure_validation_on_coalesce=ensure_validation_on_coalesce,
                queued_comment=queued_comment,
            )

        return self._run_project_serialized(project_id, _operation)

    def reconcile_completed_recurrence_sync(
        self,
        current_issue: Issue,
        record: TerminalAuditRecord,
        project_id: str,
        *,
        applied_status: str,
        completed_audit_id: str | None = None,
        completed_attempt_id: str | None = None,
    ) -> TransitionResult:
        """Resolve a duplicate recurrence from an accepted durable result.

        The workflow ledger deliberately does not rearm completed semantic
        work merely because a fresh ``audit_id`` appeared.  A recovered
        metadata writer can nevertheless leave such a record pending after
        the exact target/evidence generation was already accepted.  Reconcile
        that row through the coordinator: retire the duplicate, persist a
        crash-replayable status intent backed by the completed audit record,
        and only then restore the audited terminal status.

        This path is intentionally unavailable for exhausted work.  A
        completed result which an intervening evidence generation marked
        ``SUPERSEDED`` remains usable only when the workflow names that exact
        audit and immutable attempt history proves the same deterministic
        disposition.  PASS may restore the requested terminal target (or
        ``In Validation`` for a live Done->Merged chain); substantive failures
        restore only their fail-closed repair status.  Other cases still
        require the normal owner rearm contract.
        """

        if not isinstance(record, TerminalAuditRecord):
            raise TypeError("record must be a TerminalAuditRecord")
        if not isinstance(project_id, str) or not project_id.strip():
            raise ValueError("project_id must be a non-empty string")
        if completed_audit_id is not None and (
            not isinstance(completed_audit_id, str)
            or not completed_audit_id.strip()
        ):
            raise ValueError("completed_audit_id must be non-empty when provided")
        if completed_attempt_id is not None and (
            not isinstance(completed_attempt_id, str)
            or not completed_attempt_id.strip()
        ):
            raise ValueError("completed_attempt_id must be non-empty when provided")
        if (
            record.project_id != project_id
            or record.task_id != current_issue.identifier
        ):
            return TransitionResult(
                success=False,
                audit_id=record.audit_id,
                reason="audit_ownership_mismatch",
            )
        if requires_workflow_revision(record) and record.workflow_revision is None:
            return TransitionResult(
                success=False,
                audit_id=record.audit_id,
                reason="workflow_revision_missing",
            )
        target_status = _target_state_to_status(record.target_state)
        if canonicalize_status(current_issue.state or "") != IN_VALIDATION:
            return TransitionResult(
                success=False,
                audit_id=record.audit_id,
                reason="issue_not_in_validation",
            )
        if getattr(current_issue, "project_id", None) and (
            str(current_issue.project_id) != project_id
        ):
            return TransitionResult(
                success=False,
                audit_id=record.audit_id,
                reason="project_mismatch",
            )

        def _operation() -> TransitionResult:
            tracker = self._tracker_for_project(project_id)
            locked_issue = current_issue
            fetch_issue_detail = getattr(tracker, "fetch_issue_detail", None)
            if not callable(fetch_issue_detail):
                return TransitionResult(
                    success=False,
                    audit_id=record.audit_id,
                    reason="tracker_read_failed",
                )
            if callable(fetch_issue_detail):
                try:
                    invalidate = getattr(tracker, "invalidate_read_cache", None)
                    if callable(invalidate):
                        invalidate()
                    refreshed = fetch_issue_detail(current_issue.identifier)
                except Exception:
                    logger.exception(
                        "Failed to refresh completed audit recurrence for %s",
                        current_issue.identifier,
                    )
                    return TransitionResult(
                        success=False,
                        audit_id=record.audit_id,
                        reason="tracker_read_failed",
                    )
                if not isinstance(refreshed, Issue):
                    return TransitionResult(
                        success=False,
                        audit_id=record.audit_id,
                        reason="tracker_read_failed",
                    )
                if (
                    refreshed.identifier != current_issue.identifier
                    or (
                        refreshed.project_id is not None
                        and str(refreshed.project_id) != project_id
                    )
                ):
                    return TransitionResult(
                        success=False,
                        audit_id=record.audit_id,
                        reason="audit_ownership_mismatch",
                    )
                refreshed.project_id = project_id
                locked_issue = refreshed
            if canonicalize_status(locked_issue.state or "") != IN_VALIDATION:
                return TransitionResult(
                    success=False,
                    audit_id=record.audit_id,
                    reason="issue_not_in_validation",
                )
            try:
                live_fingerprint = compute_issue_evidence_fingerprint(
                    locked_issue, project_id
                )
            except Exception:
                return TransitionResult(
                    success=False,
                    audit_id=record.audit_id,
                    reason="tracker_read_failed",
                )
            if live_fingerprint != record.evidence_fingerprint:
                return TransitionResult(
                    success=False,
                    audit_id=record.audit_id,
                    reason="evidence_fingerprint_mismatch",
                )
            lifecycle_conflict = self._lifecycle_conflict(
                locked_issue,
                record.target_state,
                project_id,
            )
            if lifecycle_conflict is not None:
                return TransitionResult(
                    success=False,
                    audit_id=record.audit_id,
                    reason=lifecycle_conflict,
                )
            if not self._revoke_delivery_for_terminal_transition(
                project_id,
                current_issue.identifier,
            ):
                return TransitionResult(
                    success=False,
                    audit_id=record.audit_id,
                    reason="delivery_mutation_in_progress",
                )
            store = TerminalAuditMetadataStore(
                tracker,
                self._project_store,
                project_id,
            )
            source_audit_id: str | None = None
            retired_ids: list[str] = []
            reconciled_status: str | None = None
            status_already_applied = False
            rejection_reason: str | None = None
            replay_attempt_id = f"workflow-recurrence:{record.audit_id}"

            def _updater(doc: TerminalAuditMetadata) -> TerminalAuditMetadata:
                nonlocal source_audit_id, retired_ids
                nonlocal reconciled_status, status_already_applied
                nonlocal rejection_reason
                chain = list(doc.pending_chain)
                current = next(
                    (
                        candidate
                        for candidate in chain
                        if candidate.audit_id == record.audit_id
                        and candidate.project_id == project_id
                        and candidate.task_id == current_issue.identifier
                        and candidate.target_state == record.target_state
                        and candidate.evidence_fingerprint
                        == record.evidence_fingerprint
                        and candidate.workflow_revision
                        == record.workflow_revision
                        and candidate.selected_ref == record.selected_ref
                        and candidate.selected_sha == record.selected_sha
                        and candidate.landing_revision == record.landing_revision
                        and candidate.request_state
                        in (RequestState.PENDING, RequestState.IN_PROGRESS)
                    ),
                    None,
                )
                if current is None:
                    return doc
                completed = [
                    candidate
                    for candidate in chain
                    if candidate.audit_id != record.audit_id
                    and (
                        completed_audit_id is None
                        or candidate.audit_id == completed_audit_id
                    )
                    and candidate.project_id == project_id
                    and candidate.task_id == current_issue.identifier
                    and candidate.target_state == record.target_state
                    and candidate.evidence_fingerprint
                    == record.evidence_fingerprint
                    and candidate.workflow_revision
                    == record.workflow_revision
                    and candidate.selected_ref == record.selected_ref
                    and candidate.selected_sha == record.selected_sha
                    and candidate.landing_revision == record.landing_revision
                    and candidate.request_state
                    in (RequestState.COMPLETED, RequestState.SUPERSEDED)
                ]
                if not completed:
                    return doc
                next_merged = next(
                    (
                        candidate
                        for candidate in chain
                        if candidate.audit_id != record.audit_id
                        and candidate.project_id == project_id
                        and candidate.task_id == current_issue.identifier
                        and candidate.target_state is TargetState.MERGED
                        and candidate.evidence_fingerprint
                        == record.evidence_fingerprint
                        and candidate.workflow_revision
                        == record.workflow_revision
                        and candidate.selected_ref == record.selected_ref
                        and candidate.selected_sha == record.selected_sha
                        and candidate.landing_revision == record.landing_revision
                        and candidate.request_state
                        in (RequestState.PENDING, RequestState.IN_PROGRESS)
                    ),
                    None,
                )

                def _accepted_disposition(
                    candidate: TerminalAuditRecord,
                ) -> str | None:
                    """Prove one exact terminal attempt and derive its safe status."""

                    for attempt in reversed(candidate.attempts):
                        if (
                            (
                                completed_attempt_id is not None
                                and attempt.attempt_id != completed_attempt_id
                            )
                            or attempt.request_state is not RequestState.COMPLETED
                            or attempt.verdict is None
                            or attempt.target_state != record.target_state
                            or attempt.evidence_fingerprint
                            != record.evidence_fingerprint
                        ):
                            continue
                        if attempt.verdict is Verdict.PASS:
                            return (
                                IN_VALIDATION
                                if record.target_state is TargetState.DONE
                                and next_merged is not None
                                else target_status
                            )
                        if attempt.verdict is Verdict.NEEDS_HUMAN:
                            return NEEDS_HUMAN
                        if (
                            attempt.verdict is Verdict.FAIL
                            and attempt.failure_classification is not None
                        ):
                            return classify_failure_to_status(
                                attempt.failure_classification,
                                candidate.previous_state,
                            )
                    return None

                validated = [
                    (candidate, disposition)
                    for candidate in completed
                    if (disposition := _accepted_disposition(candidate)) is not None
                ]
                matching_dispositions = [
                    (candidate, disposition)
                    for candidate, disposition in validated
                    if status_key(disposition) == status_key(applied_status)
                ]
                if validated and not matching_dispositions:
                    rejection_reason = "completed_workflow_status_mismatch"
                    return doc
                if not matching_dispositions:
                    return doc
                source, reconciled_status = max(
                    matching_dispositions,
                    key=lambda item: (
                        item[0].source_generation,
                        _active_audit_authority_key(item[0]),
                    ),
                )
                source_audit_id = source.audit_id
                now = _now_iso8601()
                retired_ids = [
                    candidate.audit_id
                    for candidate in chain
                    if candidate.audit_id != source.audit_id
                    and candidate.project_id == project_id
                    and candidate.task_id == current_issue.identifier
                    and candidate.target_state == record.target_state
                    and candidate.evidence_fingerprint
                    == record.evidence_fingerprint
                    and candidate.workflow_revision
                    == record.workflow_revision
                    and candidate.selected_ref == record.selected_ref
                    and candidate.selected_sha == record.selected_sha
                    and candidate.landing_revision == record.landing_revision
                    and candidate.request_state
                    in (RequestState.PENDING, RequestState.IN_PROGRESS)
                ]
                chain = [
                    replace(
                        candidate,
                        request_state=RequestState.SUPERSEDED,
                        updated_at=now,
                    )
                    if candidate.project_id == project_id
                    and candidate.task_id == current_issue.identifier
                    and candidate.audit_id in retired_ids
                    else candidate
                    for candidate in chain
                ]
                unknown = _record_terminal_retirement(
                    doc.unknown_fields,
                    project_id=project_id,
                    task_id=current_issue.identifier,
                    target_state=record.target_state,
                    evidence_fingerprint=record.evidence_fingerprint,
                    workflow_revision=(
                        record.workflow_revision
                    ),
                    selected_ref=record.selected_ref,
                    selected_sha=record.selected_sha,
                    landing_revision=record.landing_revision,
                    audit_ids=[source.audit_id, *retired_ids],
                    kind="completed_workflow_recurrence",
                )
                unknown = _record_terminal_result_intent(
                    unknown,
                    project_id=project_id,
                    task_id=current_issue.identifier,
                    audit_id=source.audit_id,
                    target_state=record.target_state,
                    evidence_fingerprint=record.evidence_fingerprint,
                    attempt_id=replay_attempt_id,
                    status=reconciled_status,
                    audit_ids=[source.audit_id, *retired_ids],
                )
                status_already_applied = (
                    canonicalize_status(locked_issue.state or "")
                    == canonicalize_status(reconciled_status)
                )
                if status_already_applied:
                    # The Done prerequisite deliberately left the task in
                    # validation for its Merged successor.  A no-op status
                    # intent must be acknowledged in this same metadata CAS;
                    # otherwise a crash before the later acknowledgement can
                    # replay In Validation after Merged has already landed.
                    unknown = _mark_terminal_result_intent_applied(
                        unknown,
                        project_id=project_id,
                        task_id=current_issue.identifier,
                        audit_id=source.audit_id,
                        attempt_id=replay_attempt_id,
                    )
                return replace(
                    doc,
                    pending_chain=chain,
                    unknown_fields=unknown,
                )

            try:
                store.update(current_issue.identifier, _updater)
            except TerminalAuditMetadataQuarantinedError:
                return TransitionResult(
                    success=False,
                    audit_id=record.audit_id,
                    reason="metadata_quarantined",
                )
            except Exception:
                logger.exception(
                    "Failed to persist completed audit recurrence for %s",
                    current_issue.identifier,
                )
                return TransitionResult(
                    success=False,
                    audit_id=record.audit_id,
                    reason="metadata_write_failed",
                )
            if rejection_reason is not None:
                return TransitionResult(
                    success=False,
                    audit_id=record.audit_id,
                    reason=rejection_reason,
                )
            if source_audit_id is None:
                return TransitionResult(
                    success=False,
                    audit_id=record.audit_id,
                    reason="completed_audit_evidence_missing",
                )

            assert reconciled_status is not None
            if not status_already_applied:
                try:
                    # TERMINAL-AUDIT-ALLOW OOMPAH-781: restore a status already
                    # authorized by the exact completed target/evidence workflow.
                    tracker.update_issue(
                        current_issue.identifier,
                        status=reconciled_status,
                    )
                except Exception:
                    logger.exception(
                        "Failed to restore completed audit recurrence status for %s",
                        current_issue.identifier,
                    )
                    return TransitionResult(
                        success=False,
                        audit_id=record.audit_id,
                        cancelled_audit_ids=retired_ids,
                        reason="status_update_failed",
                    )

            if not status_already_applied:
                try:
                    def _finalize(
                        doc: TerminalAuditMetadata,
                    ) -> TerminalAuditMetadata:
                        return replace(
                            doc,
                            unknown_fields=_mark_terminal_result_intent_applied(
                                doc.unknown_fields,
                                project_id=project_id,
                                task_id=current_issue.identifier,
                                audit_id=source_audit_id,
                                attempt_id=replay_attempt_id,
                            ),
                        )

                    store.update(current_issue.identifier, _finalize)
                except Exception:
                    # The terminal status already won.  Leave the intent
                    # pending so ordinary restart reconciliation can
                    # acknowledge it.
                    logger.exception(
                        "Failed to acknowledge completed audit recurrence for %s",
                        current_issue.identifier,
                    )
            return TransitionResult(
                success=True,
                audit_id=source_audit_id,
                coalesced=True,
                status_repaired=True,
                applied_status=reconciled_status,
                cancelled_audit_ids=retired_ids,
            )

        return self._run_project_serialized(project_id, _operation)

    def reconcile_missing_workflow_revision_sync(
        self,
        current_issue: Issue,
        record: TerminalAuditRecord | None,
        project_id: str,
    ) -> TransitionResult:
        """Retire and unwind a pre-cutover workflow audit without authority.

        Workflow-authored active records require ``workflow_revision``.  Old
        metadata can predate that fence, so it can neither be dispatched nor
        accept a result.  Under the project mutation lock, retire every such
        active record for the exact task, persist a status-write intent, and
        restore the recorded natural state (or a conservative actionable
        fallback).  Passing ``record=None`` replays a previously persisted
        migration intent after a crash between metadata and tracker writes.
        """

        if record is not None and not isinstance(record, TerminalAuditRecord):
            raise TypeError("record must be a TerminalAuditRecord or None")
        if not isinstance(project_id, str) or not project_id.strip():
            raise ValueError("project_id must be a non-empty string")
        if getattr(current_issue, "project_id", None) and (
            str(current_issue.project_id) != project_id
        ):
            return TransitionResult(success=False, reason="project_mismatch")
        if record is not None and (
            record.project_id != project_id
            or record.task_id != current_issue.identifier
        ):
            return TransitionResult(
                success=False,
                audit_id=record.audit_id,
                reason="audit_ownership_mismatch",
            )

        def _operation() -> TransitionResult:
            tracker = self._tracker_for_project(project_id)
            fetch_issue_detail = getattr(tracker, "fetch_issue_detail", None)
            if not callable(fetch_issue_detail):
                return TransitionResult(
                    success=False,
                    audit_id=record.audit_id if record is not None else None,
                    reason="tracker_read_failed",
                )
            try:
                invalidate = getattr(tracker, "invalidate_read_cache", None)
                if callable(invalidate):
                    invalidate()
                locked_issue = fetch_issue_detail(current_issue.identifier)
            except Exception:
                logger.exception(
                    "Failed to refresh workflow-revision migration for %s",
                    current_issue.identifier,
                )
                return TransitionResult(
                    success=False,
                    audit_id=record.audit_id if record is not None else None,
                    reason="tracker_read_failed",
                )
            if getattr(locked_issue, "project_id", None) and (
                str(locked_issue.project_id) != project_id
            ):
                return TransitionResult(
                    success=False,
                    audit_id=record.audit_id if record is not None else None,
                    reason="project_mismatch",
                )

            store = TerminalAuditMetadataStore(
                tracker,
                self._project_store,
                project_id,
            )
            source: TerminalAuditRecord | None = None
            retired_ids: list[str] = []
            desired_status: str | None = None
            migration_attempt_id: str | None = None
            status_already_resolved = False
            rejection_reason = "workflow_revision_migration_not_found"

            def _pending_intent(
                doc: TerminalAuditMetadata,
            ) -> tuple[Mapping[str, Any], TerminalAuditRecord] | None:
                raw_intents = doc.unknown_fields.get(
                    _TERMINAL_RESULT_INTENTS_KEY,
                    [],
                )
                if not isinstance(raw_intents, list):
                    return None
                for raw in reversed(raw_intents):
                    if not isinstance(raw, Mapping):
                        continue
                    if (
                        raw.get("applied", True) is not False
                        or raw.get("kind") != "workflow_revision_migration"
                        or raw.get("project_id") != project_id
                        or raw.get("task_id") != current_issue.identifier
                    ):
                        continue
                    audit_id = str(raw.get("audit_id") or "")
                    candidate = next(
                        (
                            item
                            for item in doc.pending_chain
                            if item.audit_id == audit_id
                            and item.project_id == project_id
                            and item.task_id == current_issue.identifier
                            and item.request_state is RequestState.SUPERSEDED
                            and requires_workflow_revision(item)
                            and item.workflow_revision is None
                            and raw.get("target_state")
                            == item.target_state.value
                            and raw.get("evidence_fingerprint")
                            == item.evidence_fingerprint.digest
                            and raw.get("attempt_id")
                            == f"workflow-revision-migration:{item.audit_id}"
                        ),
                        None,
                    )
                    if candidate is not None:
                        return raw, candidate
                return None

            def _updater(doc: TerminalAuditMetadata) -> TerminalAuditMetadata:
                nonlocal source
                nonlocal retired_ids
                nonlocal desired_status
                nonlocal migration_attempt_id
                nonlocal status_already_resolved
                nonlocal rejection_reason

                chain = list(doc.pending_chain)
                exact = None
                if record is not None:
                    exact = next(
                        (
                            candidate
                            for candidate in chain
                            if candidate.audit_id == record.audit_id
                            and candidate.project_id == project_id
                            and candidate.task_id == current_issue.identifier
                            and candidate.target_state == record.target_state
                            and candidate.evidence_fingerprint
                            == record.evidence_fingerprint
                            and candidate.request_state
                            in (RequestState.PENDING, RequestState.IN_PROGRESS)
                            and requires_workflow_revision(candidate)
                            and candidate.workflow_revision is None
                        ),
                        None,
                    )

                pending = _pending_intent(doc)
                if exact is None and pending is None:
                    return doc
                source = exact if exact is not None else pending[1]
                assert source is not None
                now = _now_iso8601()
                retired_ids = [
                    candidate.audit_id
                    for candidate in chain
                    if candidate.project_id == project_id
                    and candidate.task_id == current_issue.identifier
                    and candidate.request_state
                    in (RequestState.PENDING, RequestState.IN_PROGRESS)
                    and requires_workflow_revision(candidate)
                    and candidate.workflow_revision is None
                ]
                if retired_ids:
                    chain = [
                        replace(
                            candidate,
                            request_state=RequestState.SUPERSEDED,
                            updated_at=now,
                        )
                        if candidate.audit_id in retired_ids
                        and candidate.project_id == project_id
                        and candidate.task_id == current_issue.identifier
                        else candidate
                        for candidate in chain
                    ]
                remaining_live = any(
                    candidate.project_id == project_id
                    and candidate.task_id == current_issue.identifier
                    and candidate.request_state
                    in (RequestState.PENDING, RequestState.IN_PROGRESS)
                    for candidate in chain
                )
                desired_status = (
                    IN_VALIDATION
                    if remaining_live
                    else _workflow_revision_migration_status(source)
                )
                migration_attempt_id = (
                    f"workflow-revision-migration:{source.audit_id}"
                )
                unknown = _record_terminal_retirement(
                    doc.unknown_fields,
                    project_id=project_id,
                    task_id=current_issue.identifier,
                    target_state=source.target_state,
                    evidence_fingerprint=source.evidence_fingerprint,
                    workflow_revision=None,
                    selected_ref=source.selected_ref,
                    selected_sha=source.selected_sha,
                    landing_revision=source.landing_revision,
                    audit_ids=[source.audit_id, *retired_ids],
                    kind="workflow_revision_migration",
                )
                unknown = _record_terminal_result_intent(
                    unknown,
                    project_id=project_id,
                    task_id=current_issue.identifier,
                    audit_id=source.audit_id,
                    target_state=source.target_state,
                    evidence_fingerprint=source.evidence_fingerprint,
                    attempt_id=migration_attempt_id,
                    status=desired_status,
                    audit_ids=[source.audit_id, *retired_ids],
                    kind="workflow_revision_migration",
                )
                current_status = canonicalize_status(locked_issue.state or "")
                status_already_resolved = current_status == desired_status
                if current_status not in {IN_VALIDATION, desired_status}:
                    # Another lifecycle authority won after the audit scan.
                    # Retire the legacy audit but never overwrite that state.
                    desired_status = current_status
                    status_already_resolved = True
                if status_already_resolved:
                    unknown = _mark_terminal_result_intent_applied(
                        unknown,
                        project_id=project_id,
                        task_id=current_issue.identifier,
                        audit_id=source.audit_id,
                        attempt_id=migration_attempt_id,
                    )
                rejection_reason = ""
                return replace(
                    doc,
                    pending_chain=chain,
                    unknown_fields=unknown,
                )

            try:
                store.update(current_issue.identifier, _updater)
            except TerminalAuditMetadataQuarantinedError:
                return TransitionResult(
                    success=False,
                    audit_id=record.audit_id if record is not None else None,
                    reason="metadata_quarantined",
                )
            except Exception:
                logger.exception(
                    "Failed to persist workflow-revision migration for %s",
                    current_issue.identifier,
                )
                return TransitionResult(
                    success=False,
                    audit_id=record.audit_id if record is not None else None,
                    reason="metadata_write_failed",
                )
            if source is None or desired_status is None or migration_attempt_id is None:
                return TransitionResult(
                    success=False,
                    audit_id=record.audit_id if record is not None else None,
                    reason=rejection_reason,
                )

            if not status_already_resolved:
                try:
                    tracker.update_issue(
                        current_issue.identifier,
                        status=desired_status,
                    )
                except Exception:
                    logger.exception(
                        "Failed to restore state after workflow-revision "
                        "migration for %s",
                        current_issue.identifier,
                    )
                    return TransitionResult(
                        success=False,
                        audit_id=source.audit_id,
                        cancelled_audit_ids=retired_ids,
                        reason="status_update_failed",
                    )

                try:
                    def _finalize(
                        doc: TerminalAuditMetadata,
                    ) -> TerminalAuditMetadata:
                        return replace(
                            doc,
                            unknown_fields=_mark_terminal_result_intent_applied(
                                doc.unknown_fields,
                                project_id=project_id,
                                task_id=current_issue.identifier,
                                audit_id=source.audit_id,
                                attempt_id=migration_attempt_id,
                            ),
                        )

                    store.update(current_issue.identifier, _finalize)
                except Exception:
                    # The safe status already won. Leave the exact intent for
                    # bounded reconciliation if the task is observed again.
                    logger.exception(
                        "Failed to acknowledge workflow-revision migration for %s",
                        current_issue.identifier,
                    )

            return TransitionResult(
                success=True,
                audit_id=source.audit_id,
                coalesced=True,
                status_repaired=True,
                applied_status=desired_status,
                cancelled_audit_ids=retired_ids,
            )

        return self._run_project_serialized(project_id, _operation)

    async def retry_failed_audit(
        self,
        current_issue: Issue,
        requested_target: TargetState,
        authorized_actor: ContributorIdentity,
        project_id: str,
        reason: str,
        project: Any = None,
        *,
        evidence_fingerprint: EvidenceFingerprint | None = None,
        evidence_addendum: Mapping[str, Any] | None = None,
    ) -> TransitionResult:
        """Rearm an exhausted audit without reopening implementation work.

        This is an owner-authorized recovery operation for non-substantive
        audit execution, transport, or independent-auditor exhaustion.  It
        supersedes the completed rearmable record, preserves its attempt
        history, appends a fresh pending record for the exact same evidence
        fingerprint, and restores ``In Validation``.  A repeated request
        coalesces with that pending record.  PASS results and substantive
        audit failures are never rearmable through this recovery path.

        ``evidence_addendum`` is the explicit evidence-only recovery contract.
        It is accepted only for an audit whose completed attempts all failed
        with ``MISSING_EVIDENCE`` and only when the caller supplies the exact
        current canonical fingerprint.  The addendum records which named
        checks were supplied; it never changes the fingerprint or bypasses
        the independent auditor.
        """

        requested_target = TargetState.from_raw(requested_target)
        if not isinstance(authorized_actor, ContributorIdentity):
            raise TypeError("authorized_actor must be a ContributorIdentity")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("reason must be a non-empty string")
        if not isinstance(project_id, str) or not project_id.strip():
            raise ValueError("project_id must be a non-empty string")

        actor_login = authorized_actor.identity
        if not (
            is_authorized_status_actor(actor_login, project)
            and is_project_owner(actor_login, project)
        ):
            return TransitionResult(success=False, reason="unauthorized_actor")
        if getattr(current_issue, "project_id", None) and (
            str(current_issue.project_id) != project_id
        ):
            return TransitionResult(success=False, reason="project_mismatch")

        if evidence_addendum is not None and evidence_fingerprint is None:
            raise ValueError(
                "evidence_fingerprint is required with evidence_addendum"
            )
        if evidence_addendum is not None and not isinstance(
            evidence_addendum, Mapping
        ):
            raise TypeError("evidence_addendum must be a mapping")

        def _operation() -> TransitionResult:
            tracker = self._tracker_for_project(project_id)
            store = TerminalAuditMetadataStore(
                tracker, self._project_store, project_id
            )
            supplied_fingerprint = evidence_fingerprint
            if supplied_fingerprint is None:
                supplied_fingerprint = compute_issue_evidence_fingerprint(
                    current_issue, project_id
                )
            if not isinstance(supplied_fingerprint, EvidenceFingerprint):
                return TransitionResult(
                    success=False,
                    reason="evidence_fingerprint_mismatch",
                )
            refreshed_evidence = self._refresh_retry_evidence(
                tracker,
                current_issue,
                project_id,
                supplied_fingerprint,
            )
            if refreshed_evidence is None:
                return TransitionResult(
                    success=False,
                    reason="evidence_unavailable",
                )
            locked_issue, locked_fingerprint = refreshed_evidence
            if locked_fingerprint != supplied_fingerprint:
                return TransitionResult(
                    success=False,
                    reason="evidence_fingerprint_mismatch",
                )
            lifecycle_conflict = self._lifecycle_conflict(
                locked_issue, requested_target, project_id
            )
            if lifecycle_conflict is not None:
                return TransitionResult(success=False, reason=lifecycle_conflict)
            if not self._revoke_delivery_for_terminal_transition(
                project_id,
                current_issue.identifier,
            ):
                return TransitionResult(
                    success=False,
                    reason="delivery_mutation_in_progress",
                )
            if evidence_addendum is not None:
                addendum_fingerprint = evidence_addendum.get(
                    "evidence_fingerprint",
                    evidence_addendum.get("fingerprint"),
                )
                if isinstance(addendum_fingerprint, Mapping):
                    addendum_fingerprint = addendum_fingerprint.get(
                        "digest",
                        addendum_fingerprint.get("sha256"),
                    )
                if addendum_fingerprint != locked_fingerprint.digest:
                    return TransitionResult(
                        success=False,
                        reason="evidence_fingerprint_mismatch",
                    )
                try:
                    normalized_addendum = _normalize_evidence_addendum(
                        evidence_addendum,
                        locked_fingerprint,
                    )
                except (TypeError, ValueError):
                    return TransitionResult(
                        success=False,
                        reason="invalid_evidence_addendum",
                    )
            else:
                normalized_addendum = None
            decision = TransitionResult(success=False, reason="audit_not_retryable")
            retired_audit_id: str | None = None
            rearm_intent_id: str | None = None

            def _updater(doc: TerminalAuditMetadata) -> TerminalAuditMetadata:
                nonlocal decision, retired_audit_id, rearm_intent_id
                chain = list(doc.pending_chain)
                matching = [
                    record
                    for record in chain
                    if record.target_state == requested_target
                    and record.project_id == project_id
                    and record.task_id == current_issue.identifier
                    and record.request_state
                    not in (RequestState.SUPERSEDED, RequestState.CANCELLED)
                ]
                requested_action = (
                    "audit_retry_evidence_addendum"
                    if evidence_addendum is not None
                    else "audit_retry"
                )

                def _is_intervening_recurrence_source(
                    fresh: TerminalAuditRecord,
                    exhausted: TerminalAuditRecord,
                ) -> bool:
                    """Prove that *fresh* is an E1 recurrence after another source."""

                    return bool(
                        exhausted.source_generation < fresh.source_generation
                        and any(
                            record.project_id == project_id
                            and record.task_id == current_issue.identifier
                            and exhausted.source_generation
                            < record.source_generation
                            < fresh.source_generation
                            and (
                                record.target_state != fresh.target_state
                                or record.evidence_fingerprint
                                != fresh.evidence_fingerprint
                                or record.workflow_revision
                                != fresh.workflow_revision
                                or record.selected_ref != fresh.selected_ref
                                or record.selected_sha != fresh.selected_sha
                                or record.landing_revision
                                != fresh.landing_revision
                            )
                            for record in chain
                        )
                    )

                def _authorization(
                    fresh: TerminalAuditRecord,
                    exhausted: TerminalAuditRecord,
                    now: str,
                ) -> dict[str, Any]:
                    return {
                        "version": 2,
                        "audit_id": fresh.audit_id,
                        "superseded_audit_id": exhausted.audit_id,
                        "project_id": project_id,
                        "task_id": current_issue.identifier,
                        "target_state": requested_target.value,
                        "evidence_fingerprint": fresh.evidence_fingerprint.digest,
                        "workflow_revision": (
                            fresh.workflow_revision
                        ),
                        "selected_ref": fresh.selected_ref,
                        "selected_sha": fresh.selected_sha,
                        "landing_revision": fresh.landing_revision,
                        "source_generation": fresh.source_generation,
                        "actor": authorized_actor.to_dict(),
                        "reason": redact_terminal_audit_text(reason.strip()),
                        "authorized_at": now,
                        "mode": (
                            "evidence_addendum"
                            if normalized_addendum is not None
                            else "infrastructure_recovery"
                        ),
                        **(
                            {"evidence_addendum": normalized_addendum}
                            if normalized_addendum is not None
                            else {}
                        ),
                    }

                def _same_successor_authority(
                    successor: TerminalAuditRecord,
                    prerequisite: TerminalAuditRecord,
                ) -> bool:
                    return (
                        successor.evidence_fingerprint
                        == prerequisite.evidence_fingerprint
                        and successor.workflow_revision
                        == prerequisite.workflow_revision
                        and successor.selected_ref == prerequisite.selected_ref
                        and successor.selected_sha == prerequisite.selected_sha
                        and successor.landing_revision
                        == prerequisite.landing_revision
                    )

                def _rearm_successor(
                    prerequisite: TerminalAuditRecord,
                    *,
                    allowed_prerequisite_ids: set[str | None],
                ) -> tuple[TerminalAuditRecord | None, bool]:
                    """Select one pristine same-chain Merged edge or fail closed."""

                    if requested_target is not TargetState.DONE:
                        return None, True
                    named_ids = {
                        audit_id
                        for audit_id in allowed_prerequisite_ids
                        if audit_id is not None
                    }
                    candidates = [
                        record
                        for record in chain
                        if record.project_id == project_id
                        and record.task_id == current_issue.identifier
                        and record.target_state is TargetState.MERGED
                        and record.request_state
                        in (RequestState.PENDING, RequestState.IN_PROGRESS)
                        and (
                            _same_successor_authority(record, prerequisite)
                            or record.prerequisite_audit_id in named_ids
                        )
                    ]
                    if not candidates:
                        return None, True
                    if len(candidates) != 1:
                        return None, False
                    successor = candidates[0]
                    valid = (
                        _same_successor_authority(successor, prerequisite)
                        and successor.source_generation
                        == prerequisite.source_generation
                        and successor.request_state is RequestState.PENDING
                        and not successor.attempts
                        and successor.eligible_at is None
                        and successor.prerequisite_audit_id
                        in allowed_prerequisite_ids
                    )
                    return (successor if valid else None), valid

                def _bind_successor(
                    source_chain: list[TerminalAuditRecord],
                    successor: TerminalAuditRecord | None,
                    prerequisite: TerminalAuditRecord,
                    now: str,
                ) -> list[TerminalAuditRecord]:
                    if (
                        successor is None
                        or successor.prerequisite_audit_id
                        == prerequisite.audit_id
                    ):
                        return source_chain
                    return [
                        replace(
                            record,
                            prerequisite_audit_id=prerequisite.audit_id,
                            eligible_at=None,
                            updated_at=now,
                        )
                        if record.audit_id == successor.audit_id
                        and record.project_id == project_id
                        and record.task_id == current_issue.identifier
                        else record
                        for record in source_chain
                    ]

                authority = matching[-1] if matching else None
                if authority is None or authority.evidence_fingerprint != locked_fingerprint:
                    return doc
                # A fresh owner rearm must become the sole live authority for
                # this exact target/evidence key.  An older pending/in-progress
                # sibling has no durable rearm history and may already own an
                # auditor, so fail closed instead of appending a record that
                # restart deduplication could hide behind that older identity.
                if any(
                    record.audit_id != authority.audit_id
                    and record.evidence_fingerprint == locked_fingerprint
                    and record.workflow_revision
                    == authority.workflow_revision
                    and record.selected_ref == authority.selected_ref
                    and record.selected_sha == authority.selected_sha
                    and record.landing_revision == authority.landing_revision
                    and record.request_state
                    in (RequestState.PENDING, RequestState.IN_PROGRESS)
                    for record in matching
                ):
                    return doc

                if authority.request_state in (
                    RequestState.PENDING,
                    RequestState.IN_PROGRESS,
                ):
                    history = doc.unknown_fields.get(_TERMINAL_REARM_HISTORY_KEY, [])
                    if not isinstance(history, list):
                        return doc
                    history_row = next(
                        (
                            raw
                            for raw in reversed(history)
                            if isinstance(raw, Mapping)
                            and raw.get("audit_id") == authority.audit_id
                            and raw.get("project_id") == project_id
                            and raw.get("task_id") == current_issue.identifier
                            and raw.get("target_state") == requested_target.value
                        ),
                        None,
                    )
                    if history_row is None and (
                        authority.request_state == RequestState.PENDING
                        and not authority.attempts
                    ):
                        # E1 -> E2 -> E1 creates a fresh pending metadata row,
                        # while the durable workflow identity for E1 correctly
                        # remains exhausted. Explicit owner recovery authorizes
                        # that coalesced recurrence from its exact superseded
                        # failed source instead of creating another pending row.
                        exhausted_source = next(
                            (
                                record
                                for record in reversed(chain)
                                if record.audit_id != authority.audit_id
                                and record.project_id == project_id
                                and record.task_id == current_issue.identifier
                                and record.target_state == requested_target
                                and record.evidence_fingerprint
                                == locked_fingerprint
                                and record.workflow_revision
                                == authority.workflow_revision
                                and record.selected_ref == authority.selected_ref
                                and record.selected_sha == authority.selected_sha
                                and record.landing_revision
                                == authority.landing_revision
                                and record.request_state
                                == RequestState.SUPERSEDED
                                and _is_intervening_recurrence_source(
                                    authority,
                                    record,
                                )
                                and _classified_audit_recovery_action(record)
                                == requested_action
                            ),
                            None,
                        )
                        if exhausted_source is not None:
                            now = _now_iso8601()
                            successor, successor_valid = _rearm_successor(
                                authority,
                                allowed_prerequisite_ids={
                                    authority.audit_id,
                                    exhausted_source.audit_id,
                                    None,
                                },
                            )
                            if not successor_valid:
                                return doc
                            chain = _bind_successor(
                                chain,
                                successor,
                                authority,
                                now,
                            )
                            updated_history = list(history)
                            updated_history.append(
                                _authorization(
                                    authority,
                                    exhausted_source,
                                    now,
                                )
                            )
                            unknown_fields = dict(doc.unknown_fields)
                            unknown_fields[_TERMINAL_REARM_HISTORY_KEY] = (
                                updated_history
                            )
                            rearm_intent_id = f"audit-rearm:{authority.audit_id}"
                            unknown_fields = _record_terminal_result_intent(
                                unknown_fields,
                                project_id=project_id,
                                task_id=current_issue.identifier,
                                audit_id=authority.audit_id,
                                target_state=requested_target,
                                evidence_fingerprint=locked_fingerprint,
                                attempt_id=rearm_intent_id,
                                status=IN_VALIDATION,
                                audit_ids=[authority.audit_id],
                                kind="audit_rearm",
                            )
                            decision = TransitionResult(
                                success=True,
                                audit_id=authority.audit_id,
                                audit_ids=[authority.audit_id],
                                queued_targets=[requested_target],
                                coalesced=True,
                                status_staged=False,
                            )
                            return replace(
                                doc,
                                pending_chain=chain,
                                unknown_fields=unknown_fields,
                            )
                    if history_row is None:
                        return doc
                    mode = (
                        "evidence_addendum"
                        if evidence_addendum is not None
                        else "infrastructure_recovery"
                    )
                    # ``authority.requested_by`` is immutable transition
                    # provenance and may intentionally remain auto_archive so
                    # an unbound retention audit can later witness origin/main.
                    # The durable history row separately owns rearm
                    # authorization and exact-repeat identity.
                    history_version = history_row.get("version")
                    if history_version not in {1, 2}:
                        return doc
                    if (
                        history_version == 1
                        and authority.workflow_revision is not None
                    ):
                        return doc
                    if history_row.get("mode") != mode:
                        return doc
                    history_reason = history_row.get("reason")
                    if (
                        not isinstance(history_reason, str)
                        or history_reason
                        != redact_terminal_audit_text(reason.strip())
                    ):
                        return doc
                    if (
                        history_row.get("evidence_fingerprint")
                        != authority.evidence_fingerprint.digest
                    ):
                        return doc
                    if history_version == 2:
                        if (
                            history_row.get("workflow_revision")
                            != authority.workflow_revision
                        ):
                            return doc
                        if (
                            history_row.get("selected_ref")
                            != authority.selected_ref
                            or history_row.get("selected_sha")
                            != authority.selected_sha
                            or history_row.get("landing_revision")
                            != authority.landing_revision
                        ):
                            return doc
                    history_generation = history_row.get("source_generation")
                    if (
                        isinstance(history_generation, bool)
                        or history_generation != authority.source_generation
                    ):
                        return doc
                    if normalized_addendum is not None:
                        if history_row.get("evidence_addendum") != normalized_addendum:
                            return doc
                    elif "evidence_addendum" in history_row:
                        return doc
                    try:
                        history_actor = ContributorIdentity.from_dict(
                            history_row.get("actor")
                        )
                    except (TypeError, ValueError):
                        return doc
                    if history_actor != authorized_actor:
                        return doc
                    if not (
                        is_authorized_status_actor(history_actor.identity, project)
                        and is_project_owner(history_actor.identity, project)
                    ):
                        return doc
                    superseded_id = history_row.get("superseded_audit_id")
                    exhausted = next(
                        (
                            record
                            for record in chain
                            if record.audit_id == superseded_id
                            and record.project_id == project_id
                            and record.task_id == current_issue.identifier
                            and record.target_state == requested_target
                            and record.evidence_fingerprint == locked_fingerprint
                            and record.workflow_revision
                            == authority.workflow_revision
                            and record.selected_ref == authority.selected_ref
                            and record.selected_sha == authority.selected_sha
                            and record.landing_revision
                            == authority.landing_revision
                            and record.request_state == RequestState.SUPERSEDED
                            and _classified_audit_recovery_action(record)
                            == requested_action
                        ),
                        None,
                    )
                    if exhausted is None:
                        return doc
                    successor, successor_valid = _rearm_successor(
                        exhausted,
                        allowed_prerequisite_ids={
                            authority.audit_id,
                            exhausted.audit_id,
                            None,
                        },
                    )
                    if not successor_valid:
                        return doc
                    chain = _bind_successor(
                        chain,
                        successor,
                        authority,
                        _now_iso8601(),
                    )
                    decision = TransitionResult(
                        success=True,
                        audit_id=authority.audit_id,
                        audit_ids=[authority.audit_id],
                        queued_targets=[requested_target],
                        coalesced=True,
                        status_staged=False,
                    )
                    rearm_intent_id = f"audit-rearm:{authority.audit_id}"
                    unknown_fields = _record_terminal_result_intent(
                        doc.unknown_fields,
                        project_id=project_id,
                        task_id=current_issue.identifier,
                        audit_id=authority.audit_id,
                        target_state=requested_target,
                        evidence_fingerprint=locked_fingerprint,
                        attempt_id=rearm_intent_id,
                        status=IN_VALIDATION,
                        audit_ids=[authority.audit_id],
                        kind="audit_rearm",
                    )
                    return replace(
                        doc,
                        pending_chain=chain,
                        unknown_fields=unknown_fields,
                    )

                if (
                    authority.request_state != RequestState.COMPLETED
                    or accepted_audit_recovery_action(authority) != requested_action
                ):
                    return doc
                exhausted = authority
                successor, successor_valid = _rearm_successor(
                    exhausted,
                    allowed_prerequisite_ids={exhausted.audit_id, None},
                )
                if not successor_valid:
                    return doc

                now = _now_iso8601()
                retired_audit_id = exhausted.audit_id
                chain = [
                    replace(record, request_state=RequestState.SUPERSEDED, updated_at=now)
                    if record.project_id == project_id
                    and record.task_id == current_issue.identifier
                    and record.audit_id == exhausted.audit_id
                    else record
                    for record in chain
                ]
                # A rearm is owned by ``authorized_actor`` (recorded in the
                # durable history below), but a legacy unbound retention audit
                # must retain its original automatic-retention provenance.  It
                # is the narrow authority that permits the later binder to
                # witness origin/main for an aged Done task.  Do not carry
                # arbitrary prior requesters forward.
                retained_provenance = (
                    exhausted.requested_by
                    if (
                        exhausted.selected_ref is None
                        and exhausted.selected_sha is None
                        and archive_default_branch_fallback_authorized(
                            exhausted.previous_state,
                            exhausted.requested_by,
                        )
                    )
                    else authorized_actor
                )
                fresh = _make_record(
                    project_id,
                    current_issue.identifier,
                    requested_target,
                    exhausted.evidence_fingerprint,
                    retained_provenance,
                    exhausted.previous_state,
                    now,
                    selected_ref=exhausted.selected_ref,
                    selected_sha=exhausted.selected_sha,
                    landing_revision=exhausted.landing_revision,
                    workflow_revision=(
                        exhausted.workflow_revision
                    ),
                    source_generation=max(
                        (
                            record.source_generation
                            for record in chain
                            if record.project_id == project_id
                            and record.task_id == current_issue.identifier
                        ),
                        default=0,
                    )
                    + 1,
                )
                chain = _bind_successor(chain, successor, fresh, now)
                chain.append(fresh)
                rearm_history = list(
                    doc.unknown_fields.get(_TERMINAL_REARM_HISTORY_KEY, [])
                )
                rearm_history.append(_authorization(fresh, exhausted, now))
                unknown_fields = dict(doc.unknown_fields)
                unknown_fields[_TERMINAL_REARM_HISTORY_KEY] = rearm_history
                rearm_intent_id = f"audit-rearm:{fresh.audit_id}"
                unknown_fields = _record_terminal_result_intent(
                    unknown_fields,
                    project_id=project_id,
                    task_id=current_issue.identifier,
                    audit_id=fresh.audit_id,
                    target_state=requested_target,
                    evidence_fingerprint=locked_fingerprint,
                    attempt_id=rearm_intent_id,
                    status=IN_VALIDATION,
                    audit_ids=[fresh.audit_id],
                    kind="audit_rearm",
                )
                decision = TransitionResult(
                    success=True,
                    audit_id=fresh.audit_id,
                    audit_ids=[fresh.audit_id],
                    queued_targets=[requested_target],
                    superseded_audit_id=exhausted.audit_id,
                    status_staged=False,
                )
                return replace(
                    doc,
                    pending_chain=chain,
                    unknown_fields=unknown_fields,
                )

            try:
                store.update(current_issue.identifier, _updater)
            except TerminalAuditMetadataQuarantinedError:
                return TransitionResult(
                    success=False,
                    reason="metadata_quarantined",
                )

            if not decision.success:
                return decision

            try:
                tracker.update_issue(current_issue.identifier, status=IN_VALIDATION)
                decision.status_staged = True
            except Exception:
                logger.exception(
                    "Failed to restore In Validation for retried audit %s",
                    current_issue.identifier,
                )
                decision.success = False
                decision.reason = "status_stage_failed"
                return decision

            if decision.audit_id and rearm_intent_id:
                try:
                    def _finalize_rearm_intent(
                        doc: TerminalAuditMetadata,
                    ) -> TerminalAuditMetadata:
                        unknown_fields = _mark_terminal_result_intent_applied(
                            doc.unknown_fields,
                            project_id=project_id,
                            task_id=current_issue.identifier,
                            audit_id=decision.audit_id or "",
                            attempt_id=rearm_intent_id or "",
                        )
                        return replace(doc, unknown_fields=unknown_fields)

                    store.update(current_issue.identifier, _finalize_rearm_intent)
                except Exception:
                    logger.exception(
                        "Failed to finalize terminal-audit rearm intent for %s",
                        current_issue.identifier,
                    )

            if not decision.coalesced:
                try:
                    tracker.add_comment(
                        current_issue.identifier,
                        "Terminal audit rearmed by project owner after recovery: "
                        f"{reason.strip()}",
                        author="oompah",
                    )
                except Exception:
                    logger.exception(
                        "Failed to post terminal-audit retry comment for %s",
                        current_issue.identifier,
                    )
            if retired_audit_id:
                self._record_metric(
                    "record_stale_discarded",
                    project_id,
                    current_issue.identifier,
                    retired_audit_id,
                )
                self._clear_retired_alert(
                    project_id,
                    current_issue.identifier,
                    retired_audit_id,
                )
            self._clear_integrated_recovery_alert(
                project_id, current_issue.identifier
            )
            if decision.audit_id and not decision.coalesced:
                self._record_metric(
                    "record_queued",
                    project_id,
                    current_issue.identifier,
                    decision.audit_id,
                )
            return decision

        return await asyncio.to_thread(
            self._run_owner_control_serialized,
            project_id,
            _operation,
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

        def _operation() -> ResultOutcome:
            tracker = self._tracker_for_project(project_id)
            store = TerminalAuditMetadataStore(
                tracker, self._project_store, project_id
            )
            locked_issue = current_issue
            try:
                submitted_tracker_fingerprint = (
                    compute_issue_evidence_fingerprint(current_issue, project_id)
                )
            except Exception:
                submitted_tracker_fingerprint = None
            fetch_issue_detail = getattr(tracker, "fetch_issue_detail", None)
            if callable(fetch_issue_detail):
                # Result callbacks retain the issue snapshot used to launch the
                # auditor.  Refresh inside the same project lock used by the
                # metadata CAS so an operator status change, a replacement
                # integration generation, or a moved branch head cannot be
                # terminalized by that stale snapshot.
                invalidate = getattr(tracker, "invalidate_read_cache", None)
                try:
                    if callable(invalidate):
                        invalidate()
                    refreshed = fetch_issue_detail(current_issue.identifier)
                except Exception:
                    logger.exception(
                        "Failed to refresh terminal-audit result evidence for %s",
                        current_issue.identifier,
                    )
                    return ResultOutcome(
                        success=False,
                        audit_id=result.audit_id,
                        reason=ResultRejection.CURRENT_EVIDENCE_UNAVAILABLE,
                    )
                if not isinstance(refreshed, Issue):
                    return ResultOutcome(
                        success=False,
                        audit_id=result.audit_id,
                        reason=ResultRejection.CURRENT_EVIDENCE_UNAVAILABLE,
                    )
                if (
                    refreshed.identifier != current_issue.identifier
                    or (
                        refreshed.project_id is not None
                        and str(refreshed.project_id) != project_id
                    )
                ):
                    return ResultOutcome(
                        success=False,
                        audit_id=result.audit_id,
                        reason=ResultRejection.AUDIT_OWNERSHIP_MISMATCH,
                    )
                refreshed.project_id = project_id
                locked_issue = refreshed
                if canonicalize_status(locked_issue.state or "") == IN_VALIDATION:
                    try:
                        current_tracker_fingerprint = (
                            compute_issue_evidence_fingerprint(
                                locked_issue,
                                project_id,
                            )
                        )
                    except Exception:
                        return ResultOutcome(
                            success=False,
                            audit_id=result.audit_id,
                            reason=ResultRejection.CURRENT_EVIDENCE_UNAVAILABLE,
                        )
                    # Legacy audits may carry the exact tracker fingerprint
                    # without the newer durable projection ledger.  When the
                    # callback snapshot proves that exact generation and the
                    # live tracker has moved, reject it directly.  Richer audit
                    # fingerprints do not equal the callback projection; defer
                    # those to the locked ledger-aware comparison below.
                    if (
                        submitted_tracker_fingerprint == result.evidence_fingerprint
                        and current_tracker_fingerprint
                        != submitted_tracker_fingerprint
                        and not _is_safe_retry_exhaustion_escalation(result)
                    ):
                        try:
                            projection_present, _projection = (
                                _tracker_evidence_projection_for_audit(
                                    store.read(current_issue.identifier),
                                    audit_id=result.audit_id,
                                    project_id=project_id,
                                    task_id=current_issue.identifier,
                                )
                            )
                        except Exception:
                            # The ledger-aware path below owns quarantine and
                            # unavailable-metadata classification.
                            projection_present = True
                        if not projection_present:
                            return ResultOutcome(
                                success=False,
                                audit_id=result.audit_id,
                                reason=ResultRejection.FINGERPRINT_MISMATCH,
                            )
            outcome = self._apply_result_locked(
                store, tracker, locked_issue, result, project_id
            )
            if outcome.success and not outcome.idempotent:
                if result.verdict == Verdict.PASS:
                    self._record_metric(
                        "record_passed",
                        project_id,
                        current_issue.identifier,
                        result.audit_id,
                    )
                elif result.verdict == Verdict.FAIL:
                    if result.failure_classification == FailureClassification.NO_AUDITOR:
                        self._record_metric(
                            "record_no_independent_candidate",
                            project_id,
                            current_issue.identifier,
                            result.audit_id,
                        )
                    else:
                        self._record_metric(
                            "record_failed",
                            project_id,
                            current_issue.identifier,
                            result.audit_id,
                        )
                elif result.verdict == Verdict.NEEDS_HUMAN:
                    self._record_metric(
                        "record_failed",
                        project_id,
                        current_issue.identifier,
                        result.audit_id,
                    )
                else:
                    self._record_metric(
                        "record_retried",
                        project_id,
                        current_issue.identifier,
                        result.audit_id,
                    )
                # Retire duplicate siblings while the project lock is still held.
                # The outer API/ACP handlers also report these IDs for backwards
                # compatibility, but correctness does not depend on them running.
                for cancelled_audit_id in outcome.cancelled_audit_ids:
                    self._record_metric(
                        "record_stale_discarded",
                        project_id,
                        current_issue.identifier,
                        cancelled_audit_id,
                    )
                    self._clear_retired_alert(
                        project_id, current_issue.identifier, cancelled_audit_id
                    )
            elif outcome.success and outcome.idempotent:
                # A replay may be the first callback after a restart. Recover
                # sibling IDs from durable retirement metadata and clear their
                # alerts even though no lifecycle counter should increment.
                for cancelled_audit_id in outcome.cancelled_audit_ids:
                    self._clear_retired_alert(
                        project_id, current_issue.identifier, cancelled_audit_id
                    )
            if outcome.success and outcome.applied_status in TERMINAL_STATUSES:
                self._clear_integrated_recovery_alert(
                    project_id, current_issue.identifier
                )
            return outcome

        return await asyncio.to_thread(
            self._run_project_serialized,
            project_id,
            _operation,
        )

    # ------------------------------------------------------------------
    # Public API — override_transition
    # ------------------------------------------------------------------

    @staticmethod
    def _refresh_retry_evidence(
        tracker: TrackerProtocol,
        current_issue: Issue,
        project_id: str,
        evidence_fingerprint: EvidenceFingerprint,
    ) -> tuple[Issue, EvidenceFingerprint] | None:
        """Return authoritative retry evidence or fail closed when unreadable.

        Tracker-neutral embedders without a detail reader retain the explicit
        caller contract.  Once an adapter advertises the production detail
        reader, however, a failure or ambiguous response cannot prove that an
        exhausted audit still describes the current task revision.
        """

        fetch_issue_detail = getattr(tracker, "fetch_issue_detail", None)
        if not callable(fetch_issue_detail):
            return current_issue, evidence_fingerprint
        try:
            refreshed = fetch_issue_detail(current_issue.identifier)
        except Exception:  # noqa: BLE001 - retry authority must fail closed
            logger.warning(
                "Could not refresh issue evidence for audit retry %s",
                current_issue.identifier,
                exc_info=True,
            )
            return None
        if not isinstance(refreshed, Issue):
            return None
        if refreshed.identifier != current_issue.identifier:
            return None
        refreshed_project = str(getattr(refreshed, "project_id", "") or "")
        if refreshed_project and refreshed_project != project_id:
            return None
        return refreshed, compute_issue_evidence_fingerprint(refreshed, project_id)

    @staticmethod
    def _refresh_override_evidence(
        tracker: TrackerProtocol,
        current_issue: Issue,
        project_id: str,
        evidence_fingerprint: EvidenceFingerprint,
    ) -> tuple[Issue, EvidenceFingerprint]:
        """Refresh the issue and evidence at the project-lock boundary.

        The API and ACP callers normally resolve an issue before entering the
        coordinator.  That snapshot can race an auditor attempt exit or
        retry, especially for native trackers whose read generation advances
        when audit metadata/comments are written.  Attempt lifecycle data is
        not evidence, so use the tracker detail read performed while the
        coordinator's project lock is held and derive the fingerprint from
        that same issue.

        Tracker-neutral coordinator users and older test doubles may not
        expose ``fetch_issue_detail``.  Keep their explicit fingerprint as a
        compatibility fallback; production trackers all implement the detail
        read through :class:`TrackerProtocol`.
        """

        fetch_issue_detail = getattr(tracker, "fetch_issue_detail", None)
        if not callable(fetch_issue_detail):
            return current_issue, evidence_fingerprint
        try:
            refreshed = fetch_issue_detail(current_issue.identifier)
        except Exception:  # noqa: BLE001 - preserve tracker-neutral behavior
            logger.warning(
                "Could not refresh issue evidence for owner override %s; "
                "using the caller snapshot",
                current_issue.identifier,
                exc_info=True,
            )
            return current_issue, evidence_fingerprint
        if not isinstance(refreshed, Issue):
            return current_issue, evidence_fingerprint
        return refreshed, compute_issue_evidence_fingerprint(refreshed, project_id)

    @staticmethod
    def _legacy_done_override_fingerprint_equivalent(
        issue: Issue,
        requested_target: TargetState,
        project_id: str,
        historical_fingerprint: EvidenceFingerprint,
        current_fingerprint: EvidenceFingerprint,
    ) -> bool:
        """Recognize only the bounded pre/post-integration Done projection.

        OOMPAH-729 changed an integrated task's canonical fingerprint from its
        accepted work-branch projection to its landed base-branch projection.
        A project owner repairing a structurally Done-only epic maintenance
        helper must not be rejected solely because the active historical Done
        row uses that one legacy shape.  Every other target, task shape, label,
        or evidence drift remains an ordinary stale override.
        """

        if requested_target != TargetState.DONE:
            return False
        labels = {str(label).strip().lower() for label in issue.labels or []}
        if (
            not is_direct_epic_maintenance_issue(issue)
            or "ci-fix" in labels
            or "merge-conflict" in labels
        ):
            return False
        variants = compute_integrated_evidence_fingerprint_variants(
            issue, project_id
        )
        return bool(
            variants is not None
            and variants.integrated != variants.legacy_work_branch
            and current_fingerprint == variants.integrated
            and historical_fingerprint == variants.legacy_work_branch
        )

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
        persisting an override audit record, changing the task status, and
        only then posting the human-readable comment.

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

        def _operation() -> OverrideResult:
            tracker = self._tracker_for_project(project_id)
            store = TerminalAuditMetadataStore(
                tracker, self._project_store, project_id
            )
            locked_issue, locked_fingerprint = self._refresh_override_evidence(
                tracker,
                current_issue,
                project_id,
                evidence_fingerprint,
            )
            outcome = self._override_transition_locked(
                store,
                tracker,
                locked_issue,
                requested_target,
                authorized_actor,
                project_id,
                locked_fingerprint,
                reason,
                project,
            )
            if outcome.success and not outcome.idempotent:
                for audit_id in outcome.overridden_audit_ids or [outcome.override_id]:
                    if audit_id:
                        self._record_metric(
                            "record_overridden",
                            project_id,
                            current_issue.identifier,
                            audit_id,
                        )
            if outcome.success:
                for audit_id in outcome.retired_alert_audit_ids:
                    cleanup_error = self._clear_retired_alert(
                        project_id, current_issue.identifier, audit_id
                    )
                    if cleanup_error:
                        outcome.cleanup_diagnostics.append(
                            {
                                "operation": "retire_audit_alert",
                                "audit_id": audit_id,
                                "message": cleanup_error,
                            }
                        )
                self._clear_integrated_recovery_alert(
                    project_id, current_issue.identifier
                )
            return outcome

        outcome = await asyncio.to_thread(
            self._run_owner_control_serialized,
            project_id,
            _operation,
        )
        if outcome.success and self._release_audit_budget_reservation is not None:
            try:
                self._release_audit_budget_reservation(
                    project_id,
                    current_issue.identifier,
                )
            except Exception:  # accounting cleanup cannot roll back an override
                logger.warning(
                    "failed to reconcile audit budget after owner override for %s/%s",
                    project_id,
                    current_issue.identifier,
                    exc_info=True,
                )
        return outcome

    # ------------------------------------------------------------------
    # Internal helpers — all called while the project write lock is held
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
        *,
        revision_binding: AuditRevisionBinding | None = None,
        landing_revision: str | None = None,
        workflow_revision: str | None = None,
        coalesce_pending_target: bool = False,
        ensure_validation_on_coalesce: bool = False,
        queued_comment: str | None = None,
        revalidate_completed: bool = False,
    ) -> TransitionResult:
        identifier = current_issue.identifier
        decision = _Decision()

        # The audited fingerprint may deliberately contain richer evidence
        # than a tracker can reproduce.  Persist the tracker-reproducible
        # projection separately so result application can distinguish actual
        # tracker drift from an unchanged richer fingerprint after restart.
        supplied_tracker_projection = compute_issue_evidence_fingerprint(
            current_issue, project_id
        )
        projection_issue = current_issue
        fetch_issue_detail = getattr(tracker, "fetch_issue_detail", None)
        if callable(fetch_issue_detail):
            try:
                refreshed_projection = fetch_issue_detail(identifier)
            except Exception:
                logger.warning(
                    "Could not refresh tracker evidence while staging %s",
                    identifier,
                    exc_info=True,
                )
                return TransitionResult(
                    success=False,
                    reason=ResultRejection.CURRENT_EVIDENCE_UNAVAILABLE,
                )
            if (
                not isinstance(refreshed_projection, Issue)
                or str(refreshed_projection.identifier) != str(identifier)
                or (
                    getattr(refreshed_projection, "project_id", None)
                    and str(refreshed_projection.project_id) != project_id
                )
            ):
                return TransitionResult(
                    success=False,
                    reason=ResultRejection.CURRENT_EVIDENCE_UNAVAILABLE,
                )
            projection_issue = refreshed_projection
        tracker_projection_fingerprint = compute_issue_evidence_fingerprint(
            projection_issue, project_id
        )
        if (
            callable(fetch_issue_detail)
            and supplied_tracker_projection != tracker_projection_fingerprint
        ):
            # The caller may carry a richer fingerprint separately, but its
            # tracker-reproducible snapshot still has to match the fresh
            # projection observed at the project mutation boundary.  Never
            # bind a stale canonical fingerprint to newer tracker evidence.
            return TransitionResult(
                success=False,
                reason=ResultRejection.CURRENT_EVIDENCE_MISMATCH,
            )

        def _updater(doc: TerminalAuditMetadata) -> TerminalAuditMetadata:
            """Atomically decide and commit all metadata changes."""
            chain = list(doc.pending_chain)

            def _binding_matches(record: TerminalAuditRecord) -> bool:
                """Return whether *record* names this request's exact revision."""

                if revision_binding is None:
                    return True
                return (
                    record.selected_ref == revision_binding.selected_ref
                    and record.selected_sha == revision_binding.selected_sha
                    and record.landing_revision == landing_revision
                )

            def _completion_authority_matches(
                record: TerminalAuditRecord,
            ) -> bool:
                """Bind recurrence/coalescing to one workflow completion proof."""

                return (
                    record.workflow_revision
                    == workflow_revision
                )

            merged_prerequisite_ready = (
                requested_target != TargetState.MERGED
                or any(
                    record.target_state == TargetState.DONE
                    and record.project_id == project_id
                    and record.task_id == identifier
                    and record.evidence_fingerprint == evidence_fingerprint
                    and _binding_matches(record)
                    and _completion_authority_matches(record)
                    and record.request_state
                    in (
                        RequestState.PENDING,
                        RequestState.IN_PROGRESS,
                        RequestState.COMPLETED,
                    )
                    for record in chain
                )
            )

            # --- Stale-request rejection (identical target already completed) ---
            for record in chain:
                if (
                    not revalidate_completed
                    and record.target_state == requested_target
                    and record.project_id == project_id
                    and record.task_id == identifier
                    and record.request_state == RequestState.COMPLETED
                    and record.evidence_fingerprint == evidence_fingerprint
                    and _binding_matches(record)
                    and _completion_authority_matches(record)
                    and merged_prerequisite_ready
                ):
                    duplicate_ids = [
                        existing.audit_id
                        for existing in chain
                        if (
                            existing.audit_id != record.audit_id
                            and existing.project_id == project_id
                            and existing.task_id == identifier
                            and existing.target_state == requested_target
                            and existing.evidence_fingerprint == evidence_fingerprint
                            and _binding_matches(existing)
                            and _completion_authority_matches(existing)
                            and existing.request_state
                            in (RequestState.PENDING, RequestState.IN_PROGRESS)
                        )
                    ]
                    if duplicate_ids:
                        now = _now_iso8601()
                        chain = [
                            replace(existing, request_state=RequestState.SUPERSEDED, updated_at=now)
                            if existing.project_id == project_id
                            and existing.task_id == identifier
                            and existing.audit_id in duplicate_ids
                            else existing
                            for existing in chain
                        ]
                        decision.cancelled_audit_ids = duplicate_ids
                    decision.early_result = TransitionResult(
                        success=False,
                        audit_id=record.audit_id,
                        audit_ids=[],
                        cancelled_audit_ids=duplicate_ids,
                        reason="already completed",
                    )
                    return replace(doc, pending_chain=chain) if duplicate_ids else doc

            # Owner overrides have no completed audit row, so their durable
            # retirement ledger is also a stale-request fence.  This is what
            # prevents a native reconciliation pass after restart from
            # recreating an audit for an already-applied fingerprint.
            if not revalidate_completed and _has_terminal_retirement(
                doc,
                project_id,
                identifier,
                requested_target,
                evidence_fingerprint,
                revision_binding=revision_binding,
                landing_revision=landing_revision,
                workflow_revision=workflow_revision,
            ):
                decision.early_result = TransitionResult(
                    success=False,
                    cancelled_audit_ids=[],
                    reason="already completed",
                )
                return doc

            # --- Coalesce identical pending request ---
            # Recovery from older writers can expose more than one live row
            # for a canonical generation.  Prefer the row which already owns
            # an in-progress attempt (and then the newest durable activity),
            # not whichever list entry happened to be persisted first.  The
            # latter discarded OOMPAH-824's PASS-producing auditor in favour
            # of an older pending sibling and forced a second provider run.
            active_matches = [
                record
                for record in chain
                if (
                    record.target_state == requested_target
                    and record.project_id == project_id
                    and record.task_id == identifier
                    and record.request_state
                    in (RequestState.PENDING, RequestState.IN_PROGRESS)
                    and _binding_matches(record)
                    and _completion_authority_matches(record)
                    and merged_prerequisite_ready
                    and (
                        coalesce_pending_target
                        or record.evidence_fingerprint == evidence_fingerprint
                    )
                )
            ]
            if active_matches:
                record = max(active_matches, key=_active_audit_authority_key)
                if record is not None:
                    updated_chain = chain
                    superseded_id: str | None = None
                    superseded_ids: list[str] = []
                    if not coalesce_pending_target:
                        updated_chain = []
                        for existing in chain:
                            mismatched_chain_binding = (
                                revision_binding is not None
                                and existing.evidence_fingerprint
                                == evidence_fingerprint
                                and (
                                    existing.target_state == requested_target
                                    or (
                                        requested_target == TargetState.MERGED
                                        and existing.target_state
                                        == TargetState.DONE
                                    )
                                )
                                and not _binding_matches(existing)
                            )
                            mismatched_completion_authority = (
                                existing.evidence_fingerprint
                                == evidence_fingerprint
                                and (
                                    existing.target_state == requested_target
                                    or (
                                        requested_target == TargetState.MERGED
                                        and existing.target_state
                                        == TargetState.DONE
                                    )
                                )
                                and not _completion_authority_matches(existing)
                            )
                            dependent_merged = (
                                requested_target is TargetState.DONE
                                and existing.target_state is TargetState.MERGED
                                and existing.request_state
                                in (RequestState.PENDING, RequestState.IN_PROGRESS)
                            )
                            if (
                                existing.audit_id != record.audit_id
                                and existing.project_id == project_id
                                and existing.task_id == identifier
                                and (
                                    existing.target_state == requested_target
                                    or dependent_merged
                                )
                                and existing.request_state
                                in (
                                    RequestState.PENDING,
                                    RequestState.IN_PROGRESS,
                                    RequestState.COMPLETED,
                                )
                                and (
                                    existing.evidence_fingerprint
                                    != evidence_fingerprint
                                    or mismatched_chain_binding
                                    or mismatched_completion_authority
                                )
                            ):
                                updated_chain.append(
                                    replace(
                                        existing,
                                        request_state=RequestState.SUPERSEDED,
                                    )
                                )
                                superseded_id = existing.audit_id
                                superseded_ids.append(existing.audit_id)
                            else:
                                updated_chain.append(existing)
                    # A malformed/recovered document can contain duplicate
                    # live rows for one canonical fingerprint. Keep the
                    # strongest durable owner and retire every sibling
                    # atomically.
                    duplicate_ids = [
                        existing.audit_id
                        for existing in updated_chain
                        if (
                            existing.audit_id != record.audit_id
                            and existing.project_id == project_id
                            and existing.task_id == identifier
                            and existing.target_state == requested_target
                            and existing.evidence_fingerprint == record.evidence_fingerprint
                            and existing.workflow_revision
                            == record.workflow_revision
                            and existing.request_state
                            in (RequestState.PENDING, RequestState.IN_PROGRESS)
                        )
                    ]
                    if duplicate_ids:
                        now = _now_iso8601()
                        updated_chain = [
                            replace(existing, request_state=RequestState.SUPERSEDED, updated_at=now)
                            if existing.project_id == project_id
                            and existing.task_id == identifier
                            and existing.audit_id in duplicate_ids
                            else existing
                            for existing in updated_chain
                        ]
                        decision.cancelled_audit_ids = duplicate_ids
                    decision.early_result = TransitionResult(
                        success=True,
                        audit_id=record.audit_id,
                        audit_ids=[record.audit_id],
                        queued_targets=[requested_target],
                        coalesced=True,
                        superseded_audit_id=superseded_id,
                        superseded_audit_ids=superseded_ids,
                        cancelled_audit_ids=duplicate_ids,
                    )
                    if superseded_id is None and not duplicate_ids:
                        return doc
                    return replace(doc, pending_chain=updated_chain)

            # --- Supersede active/failed record with changed evidence ---
            superseded_id: str | None = None
            superseded_ids: list[str] = []
            updated_chain: list[TerminalAuditRecord] = []
            for record in chain:
                mismatched_target_binding = (
                    revision_binding is not None
                    and (
                        record.target_state == requested_target
                        or (
                            requested_target == TargetState.MERGED
                            and record.target_state == TargetState.DONE
                        )
                    )
                    and record.evidence_fingerprint == evidence_fingerprint
                    and not _binding_matches(record)
                )
                mismatched_completion_authority = (
                    (
                        record.target_state == requested_target
                        or (
                            requested_target == TargetState.MERGED
                            and record.target_state == TargetState.DONE
                        )
                    )
                    and record.evidence_fingerprint == evidence_fingerprint
                    and not _completion_authority_matches(record)
                )
                invalid_merged_prerequisite = (
                    record.project_id == project_id
                    and record.task_id == identifier
                    and requested_target == TargetState.MERGED
                    and not merged_prerequisite_ready
                    and record.target_state
                    in (TargetState.DONE, TargetState.MERGED)
                )
                dependent_merged = (
                    requested_target is TargetState.DONE
                    and record.target_state is TargetState.MERGED
                    and record.request_state
                    in (RequestState.PENDING, RequestState.IN_PROGRESS)
                )
                if (
                    record.project_id == project_id
                    and record.task_id == identifier
                    and (
                        record.target_state == requested_target
                        or dependent_merged
                        or (
                            requested_target == TargetState.MERGED
                            and record.target_state == TargetState.DONE
                        )
                    )
                    and record.request_state
                    in (
                        RequestState.PENDING,
                        RequestState.IN_PROGRESS,
                        RequestState.COMPLETED,
                    )
                    and (
                        record.evidence_fingerprint != evidence_fingerprint
                        or invalid_merged_prerequisite
                        or mismatched_target_binding
                        or mismatched_completion_authority
                    )
                ):
                    updated_chain.append(
                        replace(record, request_state=RequestState.SUPERSEDED)
                    )
                    superseded_id = record.audit_id
                    superseded_ids.append(record.audit_id)
                else:
                    updated_chain.append(record)
            decision.superseded_id = superseded_id
            decision.superseded_ids = superseded_ids

            # --- Build new chain entries for the requested target ---
            new_entries = _build_new_entries(
                updated_chain,
                current_issue,
                requested_target,
                trigger_identity,
                evidence_fingerprint,
                project_id,
                revision_binding=revision_binding,
                landing_revision=landing_revision,
                workflow_revision=workflow_revision,
            )
            decision.new_entries = new_entries

            final_chain = updated_chain + new_entries
            decision.already_posted = bool(
                doc.unknown_fields.get(_QUEUED_COMMENT_KEY, False)
            )

            # Mark that the queued comment has been (or will be) posted
            new_unknown = dict(doc.unknown_fields)
            new_unknown[_QUEUED_COMMENT_KEY] = True
            new_unknown = _record_tracker_evidence_projections(
                new_unknown,
                decision.new_entries,
                tracker_projection_fingerprint,
            )

            return replace(doc, pending_chain=final_chain, unknown_fields=new_unknown)

        # --- Step 5: Atomically persist chain (must precede status write) ---
        # The TerminalAuditMetadataStore.update() raises
        # TerminalAuditMetadataQuarantinedError before calling the updater
        # when the metadata document is quarantined.
        try:
            store.update(identifier, _updater)
        except TerminalAuditMetadataQuarantinedError:
            return TransitionResult(success=False, reason="metadata quarantined")

        # Return early if the updater decided to short-circuit (coalesce/stale).
        # A previous tracker write can fail after the durable audit has been
        # staged, or another writer can race the task out of In Validation.
        # Callers that explicitly request repair restore the staging status
        # without creating or superseding an audit.
        if decision.early_result is not None:
            issue_status = canonicalize_status(current_issue.state or "")
            decision.early_result.status_staged = issue_status == IN_VALIDATION
            can_stage = (
                requested_target == TargetState.ARCHIVED
                and issue_status != ARCHIVED
            ) or issue_status not in TERMINAL_STATUSES
            if (
                decision.early_result.coalesced
                and ensure_validation_on_coalesce
                and not decision.early_result.status_staged
                and can_stage
            ):
                try:
                    tracker.update_issue(identifier, status=IN_VALIDATION)
                    decision.early_result.status_repaired = True
                    decision.early_result.status_staged = True
                except Exception:
                    logger.exception(
                        "Failed to restore In Validation for pending terminal audit %s",
                        identifier,
                    )
            return decision.early_result

        # --- Step 6: Move task to In Validation (after persistence) ---
        issue_status = current_issue.state or ""
        # An Archived audit must be observable to the audit worker even when
        # retention starts from Done or Merged.  The only status that cannot
        # be staged again is already Archived (which callers reject first).
        status_staged = canonicalize_status(issue_status) == IN_VALIDATION
        if (
            requested_target == TargetState.ARCHIVED
            and canonicalize_status(issue_status) != ARCHIVED
        ) or canonicalize_status(issue_status) not in TERMINAL_STATUSES:
            try:
                tracker.update_issue(identifier, status=IN_VALIDATION)
                status_staged = True
            except Exception:
                logger.exception(
                    "Failed to move %s to In Validation; audit chain persisted",
                    identifier,
                )

        # --- Step 7: Post concise queued comment once ---
        if self._post_comments and not decision.already_posted:
            try:
                comment = queued_comment or (
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
            audit_ids=[entry.audit_id for entry in decision.new_entries],
            queued_targets=[r.target_state for r in decision.new_entries],
            coalesced=False,
            superseded_audit_id=decision.superseded_id,
            superseded_audit_ids=decision.superseded_ids,
            status_staged=status_staged,
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
        requested_identifier = identifier
        decision = _ResultDecision()

        # The caller resolves an Issue before it waits for the project fence.
        # A UI/ACP lifecycle write or a review/head update may win that race.
        # Production trackers expose a detail read, so refresh the complete
        # evidence snapshot at the actual mutation boundary.  Tracker-neutral
        # embedders without that optional method retain their supplied object.
        fetch_issue_detail = getattr(tracker, "fetch_issue_detail", None)
        if callable(fetch_issue_detail):
            try:
                refreshed_issue = fetch_issue_detail(identifier)
            except Exception:
                logger.warning(
                    "Could not refresh current audit-result evidence for %s",
                    identifier,
                    exc_info=True,
                )
                return ResultOutcome(
                    success=False,
                    audit_id=result.audit_id,
                    reason=ResultRejection.CURRENT_EVIDENCE_UNAVAILABLE,
                )
            if not isinstance(refreshed_issue, Issue):
                return ResultOutcome(
                    success=False,
                    audit_id=result.audit_id,
                    reason=ResultRejection.CURRENT_EVIDENCE_UNAVAILABLE,
                )
            if str(refreshed_issue.identifier) != str(requested_identifier):
                return ResultOutcome(
                    success=False,
                    audit_id=result.audit_id,
                    reason=ResultRejection.AUDIT_OWNERSHIP_MISMATCH,
                )
            current_issue = refreshed_issue
            identifier = current_issue.identifier

        # Task and project ownership are server-bound arguments, not model
        # payload fields. Reject a record copied into the wrong metadata
        # document before any tracker mutation can occur.
        issue_ids = {identifier}
        if getattr(current_issue, "id", None):
            issue_ids.add(str(current_issue.id))
        if getattr(current_issue, "project_id", None) and (
            str(current_issue.project_id) != project_id
        ):
            return ResultOutcome(
                success=False,
                audit_id=result.audit_id,
                reason=ResultRejection.AUDIT_OWNERSHIP_MISMATCH,
            )

        # --- CAS: verify the tracker still holds the issue in In Validation ---
        # The issue was refreshed above when the tracker supports a detail
        # read, so this status check shares the same project fence as the
        # metadata and lifecycle writes below.
        if canonicalize_status(current_issue.state or "") != IN_VALIDATION:
            # A replay after the first successful terminal update may carry a
            # refreshed Issue object whose state is no longer In Validation.
            # It is safe to acknowledge only an exact, already-recorded
            # idempotency key; all other stale submissions remain rejected.
            try:
                current_doc = store.read(identifier)
            except TerminalAuditMetadataQuarantinedError:
                current_doc = None
            if current_doc is not None:
                record = next(
                    (
                        item
                        for item in current_doc.pending_chain
                        if item.audit_id == result.audit_id
                        and item.project_id == project_id
                        and item.task_id == identifier
                    ),
                    None,
                )
                if (
                    record is not None
                    and record.task_id == identifier
                    and record.project_id == project_id
                    and (
                        project_id,
                        identifier,
                        result.audit_id,
                        _result_idempotency_key(result),
                    )
                    in _load_applied_attempt_log(current_doc)
                ):
                    return ResultOutcome(
                        success=True,
                        audit_id=result.audit_id,
                        applied_status=_last_applied_status(
                            current_doc,
                            result.audit_id,
                            project_id=project_id,
                            task_id=identifier,
                            attempt_id=_result_idempotency_key(result),
                        ),
                        idempotent=True,
                        cancelled_audit_ids=_retired_audit_ids_for_result(
                            current_doc, project_id, identifier, result
                        ),
                    )
            return ResultOutcome(
                success=False,
                audit_id=result.audit_id,
                reason=ResultRejection.ISSUE_NOT_IN_VALIDATION,
            )

        current_fingerprint = compute_issue_evidence_fingerprint(
            current_issue, project_id
        )
        try:
            current_doc = store.read(identifier)
        except TerminalAuditMetadataQuarantinedError:
            return ResultOutcome(
                success=False,
                audit_id=result.audit_id,
                reason=ResultRejection.METADATA_QUARANTINED,
            )
        projection_present, audited_tracker_projection = (
            _tracker_evidence_projection_for_audit(
                current_doc,
                audit_id=result.audit_id,
                project_id=project_id,
                task_id=identifier,
            )
        )
        if projection_present and audited_tracker_projection is None:
            return ResultOutcome(
                success=False,
                audit_id=result.audit_id,
                reason=ResultRejection.CURRENT_EVIDENCE_UNAVAILABLE,
            )
        expected_current_fingerprint = (
            audited_tracker_projection
            if audited_tracker_projection is not None
            else result.evidence_fingerprint
        )

        if callable(fetch_issue_detail) and (
            current_fingerprint != expected_current_fingerprint
        ):
            # First prove that this result still owns the exact live record it
            # names.  Evidence drift must not let a forged/stale audit ID
            # create new work in another task's chain.
            stale_record = next(
                (
                    record
                    for record in current_doc.pending_chain
                    if record.audit_id == result.audit_id
                ),
                None,
            )
            if stale_record is None:
                return ResultOutcome(
                    success=False,
                    audit_id=result.audit_id,
                    reason=ResultRejection.AUDIT_NOT_FOUND,
                )
            if (
                stale_record.task_id != identifier
                or stale_record.project_id != project_id
            ):
                return ResultOutcome(
                    success=False,
                    audit_id=result.audit_id,
                    reason=ResultRejection.AUDIT_OWNERSHIP_MISMATCH,
                )
            if stale_record.target_state != result.target_state:
                return ResultOutcome(
                    success=False,
                    audit_id=result.audit_id,
                    reason=ResultRejection.TARGET_MISMATCH,
                )
            if stale_record.evidence_fingerprint != result.evidence_fingerprint:
                return ResultOutcome(
                    success=False,
                    audit_id=result.audit_id,
                    reason=ResultRejection.FINGERPRINT_MISMATCH,
                )
            if stale_record.request_state not in (
                RequestState.PENDING,
                RequestState.IN_PROGRESS,
            ):
                return ResultOutcome(
                    success=False,
                    audit_id=result.audit_id,
                    reason=ResultRejection.STATE_MISMATCH,
                )

            # Retry-exhaustion escalation is deliberately different from an
            # auditor verdict.  It cannot approve the requested terminal
            # state and the exact audit identity above still has to match.
            # Permit that one coordinator-authored result to route to Needs
            # Human even when a legacy record has no reproducible tracker
            # projection or the live projection changed during a forge or
            # credential cutover.  Persisting the result completes the audit
            # once, so repeated recovery scans become idempotent instead of
            # continuously advancing terminal authority and superseding
            # unrelated workflow publications.
            if _is_safe_retry_exhaustion_escalation(result):
                pass

            # Retire the obsolete audit and immediately stage the same target
            # against the new canonical evidence.  This runs inside the same
            # project mutation fence as the refresh above, so no lifecycle or
            # metadata writer can interleave.  A prior completed record for a
            # coincidentally identical fingerprint is deliberately rechecked:
            # the intervening evidence generation revoked that authority.
            # A richer caller-owned fingerprint cannot be reconstructed from
            # tracker fields alone.  If its tracker projection changed, fail
            # closed and retain the original audit instead of silently
            # replacing it with weaker evidence.  Legacy records have no
            # projection and receive the same conservative treatment.
            else:
                if (
                    audited_tracker_projection is None
                    or audited_tracker_projection != result.evidence_fingerprint
                ):
                    return ResultOutcome(
                        success=False,
                        audit_id=result.audit_id,
                        reason=ResultRejection.CURRENT_EVIDENCE_UNAVAILABLE,
                    )
                replacement = self._transition_locked(
                    store,
                    tracker,
                    replace(
                        current_issue,
                        state=stale_record.previous_state or current_issue.state,
                    ),
                    result.target_state,
                    stale_record.requested_by
                    or ContributorIdentity("oompah", "terminal-audit-refresh"),
                    project_id,
                    current_fingerprint,
                    revision_binding=(
                        AuditRevisionBinding(
                            stale_record.selected_ref,
                            stale_record.selected_sha,
                        )
                        if stale_record.selected_ref is not None
                        and stale_record.selected_sha is not None
                        else None
                    ),
                    workflow_revision=stale_record.workflow_revision,
                    ensure_validation_on_coalesce=True,
                    revalidate_completed=True,
                )
                if not replacement.success:
                    return ResultOutcome(
                        success=False,
                        audit_id=result.audit_id,
                        reason=ResultRejection.CURRENT_EVIDENCE_UNAVAILABLE,
                    )
                superseded_ids = replacement.superseded_audit_ids or (
                    [replacement.superseded_audit_id]
                    if replacement.superseded_audit_id
                    else []
                )
                for superseded_audit_id in superseded_ids:
                    self._record_metric(
                        "record_stale_discarded",
                        project_id,
                        identifier,
                        superseded_audit_id,
                    )
                    self._clear_retired_alert(
                        project_id, identifier, superseded_audit_id
                    )
                if not replacement.coalesced:
                    replacement_ids = replacement.audit_ids or (
                        [replacement.audit_id] if replacement.audit_id else []
                    )
                    for replacement_audit_id in replacement_ids:
                        self._record_metric(
                            "record_queued",
                            project_id,
                            identifier,
                            replacement_audit_id,
                        )
                return ResultOutcome(
                    success=False,
                    audit_id=result.audit_id,
                    reason=ResultRejection.CURRENT_EVIDENCE_MISMATCH,
                    cancelled_audit_ids=superseded_ids,
                )

        if result.verdict == Verdict.PASS:
            lifecycle_conflict = self._lifecycle_conflict(
                current_issue, result.target_state, project_id
            )
            if lifecycle_conflict is not None:
                return ResultOutcome(
                    success=False,
                    audit_id=result.audit_id,
                    reason=lifecycle_conflict,
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
            idempotency_key = _result_idempotency_key(result)
            if (
                (
                    project_id,
                    identifier,
                    result.audit_id,
                    idempotency_key,
                )
                in applied_attempts
                and any(
                    record.audit_id == result.audit_id
                    and record.project_id == project_id
                    and record.task_id == identifier
                    for record in doc.pending_chain
                )
            ):
                decision.outcome = ResultOutcome(
                    success=True,
                    audit_id=result.audit_id,
                    applied_status=_last_applied_status(
                        doc,
                        result.audit_id,
                        project_id=project_id,
                        task_id=identifier,
                        attempt_id=idempotency_key,
                    ),
                    idempotent=True,
                    cancelled_audit_ids=_retired_audit_ids_for_result(
                        doc, project_id, identifier, result
                    ),
                )
                return doc

            # --- Locate the target record (CAS on audit_id/target/fingerprint) ---
            chain = list(doc.pending_chain)
            target_index: int | None = None
            audit_id_collision = False
            for index, record in enumerate(chain):
                if record.audit_id != result.audit_id:
                    continue
                if record.task_id != identifier or record.project_id != project_id:
                    audit_id_collision = True
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
                    reason=(
                        ResultRejection.AUDIT_OWNERSHIP_MISMATCH
                        if audit_id_collision
                        else ResultRejection.AUDIT_NOT_FOUND
                    ),
                )
                return doc

            record = chain[target_index]
            if requires_workflow_revision(record) and record.workflow_revision is None:
                decision.outcome = ResultOutcome(
                    success=False,
                    audit_id=result.audit_id,
                    reason=ResultRejection.WORKFLOW_REVISION_MISSING,
                )
                return doc
            launched_attempt = next(
                (
                    existing
                    for existing in record.attempts
                    if result.attempt_id is not None
                    and existing.attempt_id == result.attempt_id
                ),
                None,
            )
            if launched_attempt is not None and (
                record.selected_ref is None
                or record.selected_sha is None
                or launched_attempt.selected_ref != record.selected_ref
                or launched_attempt.selected_sha != record.selected_sha
                or launched_attempt.landing_revision != record.landing_revision
            ):
                decision.outcome = ResultOutcome(
                    success=False,
                    audit_id=result.audit_id,
                    reason=ResultRejection.REVISION_BINDING_MISMATCH,
                )
                return doc
            # A successful Merged audit may advance only after the exact Done
            # prerequisite passed at the same immutable revision. A failed
            # audit must still be accepted so it can route the task back to
            # its non-terminal repair state.
            if (
                result.verdict is Verdict.PASS
                and record.target_state is TargetState.MERGED
            ):
                passed_done = [
                    candidate
                    for candidate in chain
                    if (
                        candidate.project_id == project_id
                        and candidate.task_id in issue_ids
                        and candidate.target_state is TargetState.DONE
                        # Legacy Merged rows did not name a predecessor.  New
                        # rows do, and only that exact Done audit can satisfy
                        # their result-application gate.
                        and (
                            record.prerequisite_audit_id is None
                            or candidate.audit_id
                            == record.prerequisite_audit_id
                        )
                        and candidate.request_state is RequestState.COMPLETED
                        and candidate.evidence_fingerprint
                        == record.evidence_fingerprint
                        and candidate.workflow_revision
                        == record.workflow_revision
                        and any(
                            attempt.target_state is TargetState.DONE
                            and attempt.evidence_fingerprint
                            == record.evidence_fingerprint
                            and attempt.request_state is RequestState.COMPLETED
                            and attempt.verdict is Verdict.PASS
                            for attempt in candidate.attempts
                        )
                    )
                ]
                if not passed_done:
                    decision.outcome = ResultOutcome(
                        success=False,
                        audit_id=result.audit_id,
                        reason=ResultRejection.PREREQUISITE_NOT_COMPLETED,
                    )
                    return doc
                if not any(
                    candidate.selected_ref == record.selected_ref
                    and candidate.selected_sha == record.selected_sha
                    and candidate.landing_revision == record.landing_revision
                    for candidate in passed_done
                ):
                    decision.outcome = ResultOutcome(
                        success=False,
                        audit_id=result.audit_id,
                        reason=ResultRejection.REVISION_BINDING_MISMATCH,
                    )
                    return doc
            now = _now_iso8601()
            attempt = _make_attempt(result, now, attempt_id=idempotency_key)

            # --- Decide how to route the result ---
            action = _route_result(result, record.previous_state)

            if action.kind == "reject":
                decision.outcome = ResultOutcome(
                    success=False,
                    audit_id=result.audit_id,
                    reason=action.reason,
                )
                return doc

            # The exact project/task/audit/evidence identity and a typed
            # disposition now own this transition under the project lock.
            # Revoke delivery only after those fences, so stale, foreign, or
            # malformed callbacks are observationally read-only.
            if not self._revoke_delivery_for_terminal_transition(
                project_id,
                identifier,
            ):
                decision.outcome = ResultOutcome(
                    success=False,
                    audit_id=result.audit_id,
                    reason="delivery_mutation_in_progress",
                )
                return doc

            # Record the attempt on the audit record.  The verdict, message,
            # and safe evidence are all captured before we commit any tracker
            # write — that way a crash after this update but before the
            # tracker write still leaves an auditable trail.
            # A scheduler-created attempt already owns the launch identity.
            # Complete that same row when the auditor submits a result rather
            # than appending a second row with the same attempt ID.  This is
            # the idempotency fence used by restart recovery and keeps the
            # provider/model/branch provenance attached to the result.
            attempts = []
            merged = False
            for existing in record.attempts:
                if existing.attempt_id != attempt.attempt_id:
                    attempts.append(existing)
                    continue
                merged = True
                attempts.append(
                    replace(
                        attempt,
                        created_at=existing.created_at or attempt.created_at,
                        provider_id=existing.provider_id or attempt.provider_id,
                        model=existing.model or attempt.model,
                        started_at=existing.started_at or attempt.started_at,
                        branch_key=existing.branch_key or attempt.branch_key,
                        session_id=existing.session_id or attempt.session_id,
                        candidate_rotation_count=(
                            existing.candidate_rotation_count
                            or attempt.candidate_rotation_count
                        ),
                        selected_ref=existing.selected_ref,
                        selected_sha=existing.selected_sha,
                        landing_revision=existing.landing_revision,
                        ended_at=(
                            now
                            if attempt.request_state == RequestState.COMPLETED
                            else existing.ended_at
                        ),
                    )
                )
            if not merged:
                attempts.append(
                    replace(
                        attempt,
                        selected_ref=record.selected_ref,
                        selected_sha=record.selected_sha,
                        landing_revision=record.landing_revision,
                    )
                )
            updated_record = replace(record, attempts=attempts, updated_at=now)

            if action.kind == "nonterminal":
                # Retry ceilings and infrastructure errors are recorded as an
                # ended attempt and return the record to PENDING so the next
                # independent candidate can own it.  Leaving the record
                # IN_PROGRESS after completing its exact attempt creates a
                # split-brain state: the workflow lease becomes retryable but
                # AuditorDispatchLane sees no current attempt and refuses to
                # dispatch an IN_PROGRESS record forever.
                retry_attempts = [
                    replace(
                        existing,
                        request_state=RequestState.PENDING,
                        completed_at=None,
                        ended_at=existing.ended_at or now,
                        failure_reason=(
                            existing.failure_reason
                            or action.reason
                            or result.message
                            or "structured audit result requires retry"
                        ),
                    )
                    if existing.attempt_id == attempt.attempt_id
                    else existing
                    for existing in updated_record.attempts
                ]
                chain[target_index] = replace(
                    updated_record,
                    request_state=RequestState.PENDING,
                    attempts=retry_attempts,
                )
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
                new_unknown = _record_applied_attempt(
                    doc,
                    project_id=project_id,
                    task_id=identifier,
                    audit_id=result.audit_id,
                    attempt_id=idempotency_key,
                )
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

            # --- Cancel/supersede all sibling audits for the same target/fingerprint ---
            # When an audit PASS is recorded, any other pending/in-progress audits for the
            # same target state and evidence fingerprint must be cancelled to prevent
            # duplicate dispatches. This closes the race where multiple audits for the
            # same fingerprint exist in the chain and the second one gets dispatched
            # after the first one passes.
            target_record = record
            siblings_to_cancel = [
                idx for idx, r in enumerate(chain)
                if (
                    idx != target_index
                    and r.project_id == project_id
                    and r.task_id == identifier
                    and r.target_state == target_record.target_state
                    and r.evidence_fingerprint == target_record.evidence_fingerprint
                    and r.workflow_revision
                    == target_record.workflow_revision
                    and r.selected_ref == target_record.selected_ref
                    and r.selected_sha == target_record.selected_sha
                    and r.landing_revision == target_record.landing_revision
                    and r.request_state in (RequestState.PENDING, RequestState.IN_PROGRESS)
                )
            ]
            for sibling_idx in siblings_to_cancel:
                chain[sibling_idx] = replace(
                    chain[sibling_idx],
                    request_state=RequestState.SUPERSEDED,
                    updated_at=now,
                )
            decision.cancelled_audit_ids = [chain[idx].audit_id for idx in siblings_to_cancel]

            # Detect the next pending target so we can report it to the
            # caller and — for a passing Done in a Done→Merged chain — keep
            # the task in In Validation while the auditor drives Merged.
            successor_candidates = [
                candidate
                for candidate in chain
                if target_record.target_state is TargetState.DONE
                and candidate.target_state is TargetState.MERGED
                and candidate.project_id == project_id
                and candidate.task_id == identifier
                and candidate.evidence_fingerprint
                == target_record.evidence_fingerprint
                and candidate.workflow_revision
                == target_record.workflow_revision
                and candidate.selected_ref == target_record.selected_ref
                and candidate.selected_sha == target_record.selected_sha
                and candidate.landing_revision == target_record.landing_revision
                and candidate.request_state
                in (RequestState.PENDING, RequestState.IN_PROGRESS)
            ]
            # New-format chains name their exact predecessor.  A wrong or
            # stale ID must remain blocked even when another same-authority
            # Done audit passes.  Legacy rows have no ID; migrate only that
            # explicit format by binding it to the PASS being committed.
            next_pending = next(
                (
                    candidate
                    for candidate in successor_candidates
                    if candidate.prerequisite_audit_id
                    == target_record.audit_id
                ),
                None,
            )
            if next_pending is None:
                next_pending = next(
                    (
                        candidate
                        for candidate in successor_candidates
                        if candidate.prerequisite_audit_id is None
                    ),
                    None,
                )
            if action.kind == "pass" and next_pending is not None:
                # Eligibility is committed in the same metadata CAS as the
                # prerequisite PASS.  A process may die before the scheduler
                # wake, but restart recovery can now distinguish the newly
                # eligible stage from time it spent durably blocked.
                next_index = chain.index(next_pending)
                next_pending = replace(
                    next_pending,
                    eligible_at=now,
                    prerequisite_audit_id=target_record.audit_id,
                    updated_at=now,
                )
                chain[next_index] = next_pending
                decision.advanced_target = next_pending.target_state
                decision.advanced_audit_id = next_pending.audit_id

            new_unknown = _record_applied_attempt(
                doc,
                project_id=project_id,
                task_id=identifier,
                audit_id=result.audit_id,
                attempt_id=idempotency_key,
            )
            new_unknown = _record_terminal_retirement(
                new_unknown,
                project_id=project_id,
                task_id=identifier,
                target_state=result.target_state,
                evidence_fingerprint=result.evidence_fingerprint,
                workflow_revision=(
                    target_record.workflow_revision
                ),
                selected_ref=target_record.selected_ref,
                selected_sha=target_record.selected_sha,
                landing_revision=target_record.landing_revision,
                audit_ids=[
                    result.audit_id,
                    *decision.cancelled_audit_ids,
                ],
                kind="result",
            )
            # Metadata and tracker status live in different persistence
            # systems.  Record the status mutation as an intent before leaving
            # the project lock so a crash (or a failed tracker write) cannot
            # make the completed audit look as though its terminal status was
            # applied.  Recovery consumes this intent and marks it applied
            # only after the tracker accepts the status.
            applied_status = (
                IN_VALIDATION if action.kind == "pass" and next_pending is not None
                else action.status
            )
            new_unknown = _record_terminal_result_intent(
                new_unknown,
                project_id=project_id,
                task_id=identifier,
                audit_id=result.audit_id,
                target_state=result.target_state,
                evidence_fingerprint=result.evidence_fingerprint,
                attempt_id=idempotency_key,
                status=applied_status,
                audit_ids=[result.audit_id, *decision.cancelled_audit_ids],
            )
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
        # --- Apply the target status before any human-readable result
        # comment.  The metadata commit above is the durable verdict; this
        # tracker write is the authoritative lifecycle transition.  If it
        # fails, leave the intent unapplied for recovery and do not publish a
        # misleading PASS/FAIL comment while the issue remains In Validation.
        # For a passing Done+Merged chain we
        # keep the issue in In Validation so the auditor can drive Merged; a
        # single-target chain moves straight to its terminal state.
        applied_status = decision.target_status
        if decision.keep_in_validation:
            applied_status = IN_VALIDATION
        try:
            # TERMINAL-AUDIT-ALLOW OOMPAH-483: apply a validated, persisted
            # terminal-audit verdict (or its deterministic repair status).
            tracker.update_issue(identifier, status=applied_status)
            status_applied = True
        except Exception:
            status_applied = False
            logger.exception(
                "Failed to apply audit-result status %r for %s",
                applied_status,
                identifier,
                extra={
                    "error_class": "terminal_transition.status_apply_failed",
                    "incident_key": f"{project_id}/{identifier}",
                },
            )

        # --- Post the result comment only after the authoritative status was
        # accepted.  A comment failure is best-effort and cannot undo the
        # completed audit or the terminal status.
        posted = False
        if status_applied and self._post_comments and decision.comment_text:
            try:
                tracker.add_comment(
                    identifier, decision.comment_text, author="oompah"
                )
                posted = True
            except Exception:
                logger.exception(
                    "Failed to post audit-result comment for %s", identifier
                )

        if status_applied:
            try:
                def _finalize_result_intent(doc: TerminalAuditMetadata) -> TerminalAuditMetadata:
                    new_unknown = _mark_terminal_result_intent_applied(
                        doc.unknown_fields,
                        project_id=project_id,
                        task_id=identifier,
                        audit_id=result.audit_id,
                        attempt_id=_result_idempotency_key(result),
                    )
                    return replace(doc, unknown_fields=new_unknown)

                store.update(identifier, _finalize_result_intent)
            except Exception:
                # The status write already succeeded.  Leave the intent
                # durable and unapplied so restart recovery can finish the
                # metadata acknowledgement without repeating the result.
                logger.exception(
                    "Failed to finalize terminal-audit result intent for %s",
                    identifier,
                    extra={
                        "error_class": "terminal_transition.finalization_failed",
                        "incident_key": f"{project_id}/{identifier}",
                    },
                )

        # --- Epic-audit-repair signalling ---
        # When a failed audit reopens an epic as Open, mark it with the
        # audit:repair-needed label and persist the repair context so the
        # orchestrator can dispatch exactly one repair-planner run.
        if (
            applied_status == OPEN
            and (current_issue.issue_type or "").strip().lower() == "epic"
            and result.verdict == Verdict.FAIL
        ):
            _stamp_epic_audit_repair(
                tracker, identifier, result, decision.audit_id
            )

        return ResultOutcome(
            success=True,
            audit_id=decision.audit_id,
            applied_status=applied_status,
            posted_comment=posted,
            advanced_target=decision.advanced_target,
            advanced_audit_id=decision.advanced_audit_id,
            cancelled_audit_ids=decision.cancelled_audit_ids,
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

        lifecycle_conflict = self._lifecycle_conflict(
            current_issue, requested_target, project_id
        )
        if lifecycle_conflict is not None:
            return OverrideResult(
                success=False,
                reason=lifecycle_conflict,
                error_code=OverrideRejection.LIFECYCLE_INCOMPATIBLE,
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

        current_record_for_target = next(
            (
                record
                for record in reversed(document.pending_chain)
                if record.project_id == project_id
                and record.task_id == identifier
                and record.target_state == requested_target
                and record.request_state
                in (RequestState.PENDING, RequestState.IN_PROGRESS)
            ),
            None,
        )

        # A repeated callback for the same applied fingerprint is an
        # acknowledgement, not a second terminal decision.  This check is
        # durable and therefore works after a service restart as well as for
        # two API/ACP callers racing the same owner action.
        raw_overrides = document.unknown_fields.get(_OVERRIDE_RECORDS_KEY, [])
        validated_overrides: list[tuple[Mapping[str, Any], OverrideRecord]] = []
        if not isinstance(raw_overrides, list):
            return OverrideResult(
                success=False,
                reason="terminal-audit override metadata is malformed",
                error_code=OverrideRejection.METADATA_QUARANTINED,
            )
        for raw_override in raw_overrides:
            if not isinstance(raw_override, Mapping) or any(
                marker in raw_override
                and not isinstance(raw_override.get(marker), bool)
                for marker in ("applied", "lifecycle_reconciled")
            ):
                return OverrideResult(
                    success=False,
                    reason="terminal-audit override metadata is malformed",
                    error_code=OverrideRejection.METADATA_QUARANTINED,
                )
            try:
                persisted_override = OverrideRecord.from_dict(raw_override)
            except (TypeError, ValueError):
                return OverrideResult(
                    success=False,
                    reason="terminal-audit override metadata is malformed",
                    error_code=OverrideRejection.METADATA_QUARANTINED,
                )
            validated_overrides.append((raw_override, persisted_override))

        if any(
            raw_override.get("applied") is False
            for raw_override, _persisted_override in validated_overrides
        ):
            # An explicit false marker is an in-flight durable transaction,
            # not historical authority.  Appending a newer owner decision
            # before recovery finishes could let the older transaction replay
            # afterward and overwrite the newer target.  Fail closed so the
            # existing recovery owner can finish the ordered write first.
            return OverrideResult(
                success=False,
                reason="terminal-audit override finalization is pending",
                error_code=OverrideRejection.FINALIZATION_PENDING,
            )

        for raw_override, persisted_override in validated_overrides:
            if any(
                bool(raw_override.get(marker))
                for marker in (
                    "retired_at",
                    "retired_reason",
                    "retired_by_reconciliation",
                    "retired_by_override",
                    "retired_by_lifecycle",
                    "lifecycle_retired",
                    "lifecycle_reconciled",
                    "superseded",
                    "superseded_at",
                    "superseded_by",
                )
            ):
                # Retired and superseded rows remain in the immutable audit
                # ledger for history, but no longer carry current replay
                # authority.  A fresh owner request creates a fresh record.
                continue
            if (
                persisted_override.project_id == project_id
                and persisted_override.task_id == identifier
                and persisted_override.target_state == requested_target
                and persisted_override.evidence_fingerprint == evidence_fingerprint
                and (
                    current_record_for_target is None
                    or (
                        persisted_override.workflow_revision
                        == current_record_for_target.workflow_revision
                        and persisted_override.selected_ref
                        == current_record_for_target.selected_ref
                        and persisted_override.selected_sha
                        == current_record_for_target.selected_sha
                    )
                )
            ):
                # Idempotency acknowledges the same terminal decision; it
                # must not bless a tracker state that a stale recovery
                # writer regressed afterward.  Re-read under the caller's
                # per-task ownership fence and repair the recorded target
                # before reporting success.  This is intentionally the
                # same authorized, persisted override rather than a new
                # audit decision or override record.
                lookup_ids = list(
                    dict.fromkeys(
                        str(value)
                        for value in (
                            getattr(current_issue, "id", None),
                            identifier,
                        )
                        if value
                    )
                )
                latest_issue = current_issue
                try:
                    snapshots = tracker.fetch_issue_states_by_ids(lookup_ids)
                    latest_issue = next(
                        (
                            candidate
                            for candidate in snapshots
                            if str(getattr(candidate, "id", "")) in lookup_ids
                            or str(getattr(candidate, "identifier", "")) in lookup_ids
                        ),
                        current_issue,
                    )
                except Exception:
                    # The API supplied a freshly read issue.  Reapplying an
                    # already-authorized terminal target remains safe if a
                    # tracker cannot provide a second optimized snapshot.
                    logger.warning(
                        "Could not refresh tracker state while replaying "
                        "owner override for %s; using request snapshot",
                        identifier,
                        exc_info=True,
                    )

                target_status = _target_state_to_status(requested_target)
                if canonicalize_status(
                    getattr(latest_issue, "state", "") or ""
                ) != canonicalize_status(target_status):
                    if not self._revoke_delivery_for_terminal_transition(
                        project_id, identifier
                    ):
                        return OverrideResult(
                            success=False,
                            override_id=persisted_override.override_id,
                            reason="delivery mutation in progress",
                            error_code=(
                                OverrideRejection.DELIVERY_MUTATION_IN_PROGRESS
                            ),
                        )
                    try:
                        # TERMINAL-AUDIT-ALLOW OOMPAH-704: repair tracker
                        # state regressed after a persisted owner override.
                        tracker.update_issue(identifier, status=target_status)
                    except Exception:
                        logger.exception(
                            "Failed to restore idempotent override status %r for %s",
                            target_status,
                            identifier,
                        )
                        return OverrideResult(
                            success=False,
                            override_id=persisted_override.override_id,
                            reason="failed to restore overridden tracker status",
                            error_code=OverrideRejection.STATUS_UPDATE_FAILED,
                        )
                return OverrideResult(
                    success=True,
                    override_id=persisted_override.override_id,
                    applied_status=target_status,
                    idempotent=True,
                    retired_alert_audit_ids=[
                        item.audit_id
                        for item in document.pending_chain
                        if item.project_id == project_id and item.task_id == identifier
                    ],
                )

        # Check if the fingerprint matches the current active record for the
        # requested target. The "active" record is the one that is not
        # SUPERSEDED. Historical superseded records with different fingerprints
        # are ignored; only the current active record's fingerprint is checked.
        # This allows an override to proceed when evidence changes (fingerprint
        # updates) after some older audit attempts, as long as the current
        # active record matches.
        fingerprint_mismatch = False

        if current_record_for_target is not None:
            if current_record_for_target.evidence_fingerprint != evidence_fingerprint:
                fingerprint_mismatch = True

        if fingerprint_mismatch and not self._legacy_done_override_fingerprint_equivalent(
            current_issue,
            requested_target,
            project_id,
            current_record_for_target.evidence_fingerprint,
            evidence_fingerprint,
        ):
            return OverrideResult(
                success=False,
                reason="evidence fingerprint mismatch (stale override)",
                error_code=OverrideRejection.FINGERPRINT_MISMATCH,
            )

        # Preserve the immutable repository authority when this owner action
        # is capable of proving delivery.  Overrides remain valid for
        # metadata-only terminal work when no revision can be resolved, but an
        # unbound override is never reusable as a landing fact.  Reusing the
        # active audit binding also keeps override and auditor evidence on the
        # same exact generation.
        revision_binding: AuditRevisionBinding | None = None
        try:
            revision_binding = self._request_revision_binding(
                store,
                current_issue,
                requested_target,
                project_id,
                evidence_fingerprint,
                trigger_identity=authorized_actor,
                workflow_revision=(
                    current_record_for_target.workflow_revision
                    if current_record_for_target is not None
                    else None
                ),
            )
        except Exception:  # noqa: BLE001 - optional delivery provenance
            logger.debug(
                "Owner override for %s/%s has no revision-bound delivery provenance",
                project_id,
                identifier,
                exc_info=True,
            )

        # Validation has succeeded and this owner override is now about to
        # acquire terminal authority.  Revoke synchronously, before its first
        # durable mutation, so a concurrent standalone gate cannot publish a
        # stale outcome.  Invalid or stale override attempts intentionally do
        # not disturb a valid delivery claim.
        if not self._revoke_delivery_for_terminal_transition(project_id, identifier):
            return OverrideResult(
                success=False,
                reason="delivery mutation in progress",
                error_code=OverrideRejection.DELIVERY_MUTATION_IN_PROGRESS,
            )
        self._revoke_auditor_for_owner_override(project_id, identifier)

        overridden_audit_ids = [
            record.audit_id
            for record in document.pending_chain
            if record.project_id == project_id
            and record.task_id == identifier
            and record.request_state
            in (RequestState.PENDING, RequestState.IN_PROGRESS)
        ]
        # An owner override acquires terminal authority for the task, so every
        # historical sibling alert (including one from an older fingerprint or
        # chained target) is no longer actionable.
        retired_alert_audit_ids = [
            record.audit_id
            for record in document.pending_chain
            if record.project_id == project_id and record.task_id == identifier
        ]

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
            selected_ref=(
                revision_binding.selected_ref if revision_binding is not None else None
            ),
            selected_sha=(
                revision_binding.selected_sha if revision_binding is not None else None
            ),
            workflow_revision=(
                current_record_for_target.workflow_revision
                if current_record_for_target is not None
                else None
            ),
        )

        # Step 4: Persist override record in metadata before status change
        def _updater(doc: TerminalAuditMetadata) -> TerminalAuditMetadata:
            """Atomically add the override record to metadata."""
            new_unknown = dict(doc.unknown_fields)

            # Store override records in a list. ``applied`` is a small
            # recovery marker: a crash after the tracker status write but
            # before the final metadata update can be recognized on restart.
            overrides = new_unknown.get(_OVERRIDE_RECORDS_KEY, [])
            if not isinstance(overrides, list):
                overrides = []

            raw_override = override_record.to_dict()
            raw_override["applied"] = False
            overrides.append(raw_override)
            new_unknown[_OVERRIDE_RECORDS_KEY] = overrides

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

        # Step 5: Apply the status before any explanatory comment.  The owner
        # record is already durable, so a tracker/comment failure cannot make
        # human-readable history claim a terminal state that the tracker did
        # not accept.
        target_status = _target_state_to_status(requested_target)
        try:
            # TERMINAL-AUDIT-ALLOW OOMPAH-483: apply a validated, persisted
            # project-owner override.
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

        # Step 6: Post explanatory comment after the authoritative status.
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

        cleanup_diagnostics: list[dict[str, str]] = []
        try:
            def _finalize_override(doc: TerminalAuditMetadata) -> TerminalAuditMetadata:
                """Commit cancellation, alert retirement, and applied marker together."""
                new_unknown = dict(doc.unknown_fields)
                overrides = new_unknown.get(_OVERRIDE_RECORDS_KEY, [])
                if isinstance(overrides, list):
                    finalized: list[Any] = []
                    for raw in overrides:
                        if not isinstance(raw, Mapping):
                            continue
                        item = dict(raw)
                        if item.get("override_id") == override_record.override_id:
                            item["applied"] = True
                        finalized.append(item)
                    new_unknown[_OVERRIDE_RECORDS_KEY] = finalized
                new_chain = [
                    replace(record, request_state=RequestState.CANCELLED, updated_at=_now_iso8601())
                    if record.project_id == project_id
                    and record.task_id == identifier
                    and record.audit_id in overridden_audit_ids
                    and record.request_state in (RequestState.PENDING, RequestState.IN_PROGRESS)
                    else record
                    for record in doc.pending_chain
                ]
                new_unknown = _record_terminal_retirement(
                    new_unknown,
                    project_id=project_id,
                    task_id=identifier,
                    target_state=requested_target,
                    evidence_fingerprint=evidence_fingerprint,
                    workflow_revision=override_record.workflow_revision,
                    selected_ref=override_record.selected_ref,
                    selected_sha=override_record.selected_sha,
                    landing_revision=None,
                    audit_ids=retired_alert_audit_ids,
                    kind="override",
                )
                new_unknown = _mark_all_terminal_result_intents_applied(
                    new_unknown,
                    project_id=project_id,
                    task_id=identifier,
                )
                return replace(doc, pending_chain=new_chain, unknown_fields=new_unknown)

            store.update(identifier, _finalize_override)
        except Exception:
            # The tracker status is already terminal and the persisted override
            # intent remains available to restart reconciliation. Do not report
            # a failed owner override after its terminal write succeeded.
            logger.exception("Failed to finalize overridden audits for %s", identifier)
            cleanup_diagnostics.append(
                {
                    "operation": "finalize_audit_retirement",
                    "message": "audit retirement finalization failed; recovery will retry",
                }
            )

        return OverrideResult(
            success=True,
            override_id=override_record.override_id,
            applied_status=target_status,
            posted_comment=posted,
            overridden_audit_ids=overridden_audit_ids,
            retired_alert_audit_ids=retired_alert_audit_ids,
            cleanup_diagnostics=cleanup_diagnostics,
            error_code=None,
        )

    def _tracker_for_project(self, project_id: str) -> TrackerProtocol:
        """Resolve the tracker used for a project-scoped request."""
        # Trackers are normally not callable, but ``MagicMock`` test doubles
        # are.  A real tracker exposes metadata methods; only a callable that
        # does not look like a tracker is the project-aware factory variant.
        if callable(self._tracker) and not hasattr(self._tracker, "get_metadata"):
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


def _result_idempotency_key(result: AuditResult) -> str:
    """Return a stable key for replaying an identical result.

    New audit records do not have an attempt ID until their first result is
    received. Deriving a key from the complete typed result preserves
    idempotency for retries while still treating a changed verdict/message or
    evidence set as a conflicting submission.
    """

    if result.attempt_id:
        return result.attempt_id
    payload = {
        "audit_id": result.audit_id,
        "target_state": result.target_state.value,
        "evidence_fingerprint": result.evidence_fingerprint.digest,
        "verdict": result.verdict.value,
        "failure_classification": (
            result.failure_classification.value
            if result.failure_classification is not None
            else None
        ),
        "message": result.message,
        "safe_evidence": sorted(
            (str(key), str(value))
            for key, value in (result.safe_evidence or {}).items()
        ),
        "questions": list(result.questions),
        "instructions": list(result.instructions),
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"result-{digest}"


def _make_attempt(
    result: AuditResult, now: str, *, attempt_id: str | None = None
) -> AuditAttempt:
    """Build the persisted :class:`AuditAttempt` for *result*."""

    request_state = (
        RequestState.COMPLETED
        if result.verdict in (Verdict.PASS, Verdict.FAIL, Verdict.NEEDS_HUMAN)
        else RequestState.IN_PROGRESS
    )
    if result.verdict == Verdict.ERROR:
        request_state = RequestState.IN_PROGRESS
    attempt_id = attempt_id or result.attempt_id or f"attempt-{uuid.uuid4().hex[:12]}"
    return AuditAttempt(
        attempt_id=attempt_id,
        target_state=result.target_state,
        evidence_fingerprint=result.evidence_fingerprint,
        request_state=request_state,
        verdict=result.verdict,
        failure_classification=result.failure_classification,
        origin=result.attempt_origin,
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
    parts = [f"Audit PASS — {result.target_state.value}", _append_result_context(body, result)]
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
        f"Routing task to {target_status}.\n\n{_append_result_context(body, result)}"
    )


def _compose_needs_human_message(result: AuditResult) -> str:
    body = _sanitize_line(result.message) if result.message else ""
    header = f"Needs Human — {result.target_state.value} audit requires operator input."
    if not body:
        body = "The auditor could not produce a safe verdict."
    combined = f"{header}\n\n{_append_result_context(body, result)}"
    if not _ACTION_TAIL_RE.search(combined):
        combined = combined.rstrip() + _NEEDS_HUMAN_HINT
    return combined


def _sanitize_line(value: str) -> str:
    """Trim whitespace and collapse trailing punctuation for comment lines.

    The auditor is expected to have redacted its own output before calling
    the coordinator; this function only tidies whitespace.
    """

    return redact_terminal_audit_text(str(value).strip())


def _append_result_context(body: str, result: AuditResult) -> str:
    """Append bounded, coordinator-owned rendering of human follow-ups."""

    parts = [body]
    questions = [
        _sanitize_line(item) for item in result.questions if item.strip()
    ]
    instructions = [
        _sanitize_line(item) for item in result.instructions if item.strip()
    ]
    if questions:
        parts.append("Questions:\n" + "\n".join(f"- {item}" for item in questions))
    if instructions:
        parts.append(
            "Instructions:\n" + "\n".join(f"- {item}" for item in instructions)
        )
    return "\n\n".join(parts)


def _format_safe_evidence_line(safe: Mapping[str, Any] | None) -> str:
    if not safe:
        return ""
    items = []
    for key, value in safe.items():
        if isinstance(value, str) and value.strip():
            safe_key = redact_terminal_audit_text(str(key))
            safe_value = redact_terminal_audit_text(value.strip())
            items.append(f"- {safe_key}: {safe_value}")
    if not items:
        return ""
    return "Safe evidence:\n" + "\n".join(items)


# ------------------------------------------------------------------
# Applied-result attempt log helpers
# ------------------------------------------------------------------


AppliedAttemptIdentity = tuple[str, str, str, str]


def _applied_attempt_key(identity: AppliedAttemptIdentity) -> str:
    """Encode a complete attempt identity as one stable metadata-map key."""

    return json.dumps(identity, separators=(",", ":"), ensure_ascii=True)


def _load_applied_attempt_log(
    doc: TerminalAuditMetadata,
) -> dict[AppliedAttemptIdentity, str]:
    """Load exact applied identities, conservatively migrating legacy keys."""

    raw = doc.unknown_fields.get(_APPLIED_RESULTS_KEY)
    if not isinstance(raw, dict):
        return {}
    result: dict[AppliedAttemptIdentity, str] = {}
    legacy: list[tuple[str, str]] = []
    for key, value in raw.items():
        if not isinstance(key, str):
            continue
        try:
            decoded = json.loads(key)
        except (TypeError, ValueError):
            decoded = None
        if (
            isinstance(decoded, list)
            and len(decoded) == 4
            and all(isinstance(item, str) and item for item in decoded)
        ):
            identity = tuple(decoded)
            result[identity] = str(value)
        else:
            legacy.append((key, str(value)))

    # Pre-fence metadata used bare attempt IDs. Accept one only when immutable
    # attempt history resolves it to exactly one project/task/audit record;
    # collisions remain fail-closed rather than impersonating another scope.
    for attempt_id, applied_at in legacy:
        matches = {
            (
                record.project_id,
                record.task_id,
                record.audit_id,
                attempt_id,
            )
            for record in doc.pending_chain
            if any(
                attempt.attempt_id == attempt_id
                for attempt in record.attempts
            )
        }
        if len(matches) == 1:
            result[next(iter(matches))] = applied_at
    return result


def _tracker_evidence_projection_for_audit(
    doc: TerminalAuditMetadata,
    *,
    audit_id: str,
    project_id: str,
    task_id: str,
) -> tuple[bool, EvidenceFingerprint | None]:
    """Return a durable tracker projection and whether its ledger is present.

    Missing ledgers or missing per-audit rows identify backward-compatible
    legacy records.  A matching row that is malformed, duplicated, or
    cross-scope is reported as unavailable so result application fails closed
    instead of falling back to weaker evidence.
    """

    if _TRACKER_EVIDENCE_PROJECTIONS_KEY not in doc.unknown_fields:
        return False, None
    raw_rows = doc.unknown_fields.get(_TRACKER_EVIDENCE_PROJECTIONS_KEY)
    if not isinstance(raw_rows, list):
        return True, None
    matching = [
        row
        for row in raw_rows
        if isinstance(row, Mapping) and str(row.get("audit_id") or "") == audit_id
    ]
    # A document can legitimately contain both pre-ledger records and newer
    # records that caused the ledger key to be introduced.  No matching row
    # therefore retains the legacy exact-fingerprint path; a matching row
    # that is duplicated or malformed remains a fail-closed corruption.
    if not matching:
        return False, None
    if len(matching) != 1:
        return True, None
    row = matching[0]
    digest = row.get("digest")
    if (
        row.get("version") != 1
        or str(row.get("project_id") or "") != project_id
        or str(row.get("task_id") or "") != task_id
        or not isinstance(digest, str)
    ):
        return True, None
    try:
        return True, EvidenceFingerprint(digest)
    except (TypeError, ValueError):
        return True, None


def _record_tracker_evidence_projections(
    unknown_fields: Mapping[str, Any],
    records: Sequence[TerminalAuditRecord],
    fingerprint: EvidenceFingerprint,
) -> dict[str, Any]:
    """Append immutable per-audit tracker projections for newly staged work."""

    new_unknown = dict(unknown_fields)
    if not records:
        return new_unknown
    raw_rows = new_unknown.get(_TRACKER_EVIDENCE_PROJECTIONS_KEY, [])
    rows = (
        [dict(row) for row in raw_rows if isinstance(row, Mapping)]
        if isinstance(raw_rows, list)
        else []
    )
    new_ids = {record.audit_id for record in records}
    rows = [
        row for row in rows if str(row.get("audit_id") or "") not in new_ids
    ]
    rows.extend(
        {
            "version": 1,
            "audit_id": record.audit_id,
            "project_id": record.project_id,
            "task_id": record.task_id,
            "digest": fingerprint.digest,
        }
        for record in records
    )
    new_unknown[_TRACKER_EVIDENCE_PROJECTIONS_KEY] = rows
    return new_unknown


def _last_applied_status(
    doc: TerminalAuditMetadata,
    audit_id: str | None,
    *,
    project_id: str,
    task_id: str,
    attempt_id: str | None = None,
) -> str | None:
    """Return the exact persisted status intent for one applied result.

    Mapping the record's target back to a status is insufficient for the
    ``Done`` prerequisite of a ``Done -> Merged`` chain: its accepted PASS
    deliberately applies ``In Validation`` while the successor is pending.
    Result intents are the cross-store authority for the status actually
    requested, so duplicate/restart replay must consult the exact attempt
    before using the target-only legacy fallback.
    """

    raw_intents = doc.unknown_fields.get(_TERMINAL_RESULT_INTENTS_KEY, [])
    if isinstance(raw_intents, list):
        for raw in reversed(raw_intents):
            if (
                not isinstance(raw, Mapping)
                or raw.get("audit_id") != audit_id
                or raw.get("project_id") != project_id
                or raw.get("task_id") != task_id
            ):
                continue
            if attempt_id is not None and raw.get("attempt_id") != attempt_id:
                continue
            status = raw.get("status")
            if isinstance(status, str) and status.strip():
                return status
    for record in doc.pending_chain:
        if (
            record.audit_id == audit_id
            and record.project_id == project_id
            and record.task_id == task_id
            and record.request_state == RequestState.COMPLETED
        ):
            return _target_state_to_status(record.target_state)
    return None


def _record_applied_attempt(
    doc: TerminalAuditMetadata,
    *,
    project_id: str,
    task_id: str,
    audit_id: str,
    attempt_id: str | None,
) -> dict[str, Any]:
    """Return metadata with one complete applied-attempt identity recorded."""

    new_unknown = dict(doc.unknown_fields)
    if attempt_id is None:
        return new_unknown
    raw_log = doc.unknown_fields.get(_APPLIED_RESULTS_KEY)
    log = dict(raw_log) if isinstance(raw_log, dict) else {}
    identity = (project_id, task_id, audit_id, attempt_id)
    log[_applied_attempt_key(identity)] = _now_iso8601()
    if len(log) > _MAX_APPLIED_RESULTS_MEMORY:
        # Retain the newest half by insertion order.
        items = list(log.items())[-(_MAX_APPLIED_RESULTS_MEMORY // 2):]
        log = dict(items)
    new_unknown[_APPLIED_RESULTS_KEY] = log
    return new_unknown


def _retirement_rows(doc: TerminalAuditMetadata) -> list[Mapping[str, Any]]:
    """Return well-shaped durable retirement rows without trusting their prose."""

    raw = doc.unknown_fields.get(_TERMINAL_RETIREMENTS_KEY)
    if not isinstance(raw, list):
        return []
    return [row for row in raw if isinstance(row, Mapping)]


def _raw_fingerprint_digest(raw: Mapping[str, Any]) -> str | None:
    """Read a historical override fingerprint without trusting arbitrary data."""

    value = raw.get("evidence_fingerprint")
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        digest = value.get("digest", value.get("sha256", value.get("value")))
        return digest if isinstance(digest, str) else None
    return None


def _has_terminal_retirement(
    doc: TerminalAuditMetadata,
    project_id: str,
    task_id: str,
    target_state: TargetState,
    evidence_fingerprint: EvidenceFingerprint,
    *,
    revision_binding: AuditRevisionBinding | None = None,
    landing_revision: str | None = None,
    workflow_revision: str | None = None,
) -> bool:
    """Check the durable applied-fingerprint fence used by reconciliation.

    Owner overrides intentionally fence the whole evidence fingerprint. Result
    retirements fence only the exact revision authority that produced them;
    otherwise a recovered same-fingerprint generation at another SHA could be
    suppressed by an older terminal result. Within that exact revision, a
    retirement owns only its source generation: an E1 -> E2 -> E1 recurrence
    must be evaluated again instead of being suppressed forever. Legacy and
    override rows remain fail-closed.
    """

    for row in _retirement_rows(doc):
        if row.get("applied", True) is False:
            continue
        if (
            row.get("project_id") == project_id
            and row.get("task_id") == task_id
            and row.get("target_state") == target_state.value
            and row.get("evidence_fingerprint") == evidence_fingerprint.digest
            and row.get("workflow_revision")
            == workflow_revision
            and row.get("selected_ref")
            == (revision_binding.selected_ref if revision_binding else None)
            and row.get("selected_sha")
            == (revision_binding.selected_sha if revision_binding else None)
            and row.get("landing_revision") == landing_revision
        ):
            if row.get("kind") != "result":
                return True
            raw_ids = row.get("audit_ids", [])
            retired_ids = (
                {str(value) for value in raw_ids if isinstance(value, str)}
                if isinstance(raw_ids, list)
                else set()
            )
            retired_records = [
                record
                for record in doc.pending_chain
                if record.audit_id in retired_ids
                and record.project_id == project_id
                and record.task_id == task_id
                and record.target_state == target_state
                and record.evidence_fingerprint == evidence_fingerprint
                and record.workflow_revision
                == workflow_revision
                and record.landing_revision == landing_revision
                and (
                    revision_binding is None
                    or (
                        record.selected_ref == revision_binding.selected_ref
                        and record.selected_sha == revision_binding.selected_sha
                    )
                )
            ]
            if not retired_records:
                continue
            retired_generations = [
                record.source_generation for record in retired_records
            ]
            current_generations = [
                record.source_generation
                for record in doc.pending_chain
                if record.project_id == project_id
                and record.task_id == task_id
                and record.target_state == target_state
            ]
            retired_positions = [
                index
                for index, record in enumerate(doc.pending_chain)
                if record in retired_records
            ]
            legacy_intervening_generation = bool(
                retired_positions
                and any(
                    index > min(retired_positions)
                    and record.project_id == project_id
                    and record.task_id == task_id
                    and record.audit_id not in retired_ids
                    and record.target_state == target_state
                    and record.evidence_fingerprint != evidence_fingerprint
                    for index, record in enumerate(doc.pending_chain)
                )
            )
            if (
                retired_generations
                and current_generations
                and max(current_generations) > max(retired_generations)
            ) or legacy_intervening_generation:
                continue
            return True
    return False


def _retired_audit_ids_for_result(
    doc: TerminalAuditMetadata,
    project_id: str,
    task_id: str,
    result: AuditResult,
) -> list[str]:
    """Recover sibling IDs from the durable retirement row on callback replay."""

    source = next(
        (
            record
            for record in doc.pending_chain
            if record.audit_id == result.audit_id
            and record.project_id == project_id
            and record.task_id == task_id
            and record.target_state == result.target_state
            and record.evidence_fingerprint == result.evidence_fingerprint
        ),
        None,
    )
    if source is None:
        return []
    audit_ids: list[str] = []
    for row in _retirement_rows(doc):
        if (
            row.get("applied", True) is not False
            and row.get("project_id") == project_id
            and row.get("task_id") == task_id
            and row.get("target_state") == result.target_state.value
            and row.get("evidence_fingerprint") == result.evidence_fingerprint.digest
            and row.get("workflow_revision")
            == source.workflow_revision
            and row.get("selected_ref") == source.selected_ref
            and row.get("selected_sha") == source.selected_sha
            and row.get("landing_revision") == source.landing_revision
        ):
            raw_ids = row.get("audit_ids", [])
            if isinstance(raw_ids, list):
                audit_ids.extend(
                    value for value in raw_ids if isinstance(value, str)
                )
    return list(dict.fromkeys(audit_ids))


def _record_terminal_retirement(
    unknown_fields: Mapping[str, Any],
    *,
    project_id: str,
    task_id: str,
    target_state: TargetState,
    evidence_fingerprint: EvidenceFingerprint,
    workflow_revision: str | None = None,
    selected_ref: str | None = None,
    selected_sha: str | None = None,
    landing_revision: str | None = None,
    audit_ids: list[str],
    kind: str,
    applied: bool = True,
) -> dict[str, Any]:
    """Append/update one redacted durable terminal retirement identity."""

    new_unknown = dict(unknown_fields)
    rows = [
        dict(row)
        for row in (new_unknown.get(_TERMINAL_RETIREMENTS_KEY) or [])
        if isinstance(row, Mapping)
    ]
    identity = {
        "project_id": project_id,
        "task_id": task_id,
        "target_state": target_state.value,
        "evidence_fingerprint": evidence_fingerprint.digest,
        "workflow_revision": workflow_revision,
        "selected_ref": selected_ref,
        "selected_sha": selected_sha,
        "landing_revision": landing_revision,
    }
    matching = next(
        (
            row
            for row in rows
            if all(row.get(key) == value for key, value in identity.items())
        ),
        None,
    )
    if matching is None:
        matching = {
            **identity,
            "audit_ids": [],
            "kind": kind,
            "applied": applied,
            "retired_at": _now_iso8601(),
        }
        rows.append(matching)
    else:
        matching["applied"] = bool(matching.get("applied", False) or applied)
        matching["kind"] = kind
    existing_ids = matching.get("audit_ids", [])
    if not isinstance(existing_ids, list):
        existing_ids = []
    matching["audit_ids"] = list(
        dict.fromkeys(
            [str(value) for value in existing_ids if isinstance(value, str)]
            + [str(value) for value in audit_ids if value]
        )
    )
    new_unknown[_TERMINAL_RETIREMENTS_KEY] = rows
    return new_unknown


def _record_terminal_result_intent(
    unknown_fields: Mapping[str, Any],
    *,
    project_id: str,
    task_id: str,
    audit_id: str,
    target_state: TargetState,
    evidence_fingerprint: EvidenceFingerprint,
    attempt_id: str,
    status: str | None,
    audit_ids: list[str],
    kind: str = "result",
) -> dict[str, Any]:
    """Persist one result or owner-rearm intent before mutating the tracker.

    Tracker status and audit metadata cannot share a transaction.  The intent
    is therefore the durable hand-off between those two stores.  It remains
    queryable after completion, while ``applied`` tells restart recovery
    whether the tracker write was acknowledged.
    """

    if not status:
        return dict(unknown_fields)
    new_unknown = dict(unknown_fields)
    raw_intents = new_unknown.get(_TERMINAL_RESULT_INTENTS_KEY, [])
    intents = [dict(item) for item in raw_intents if isinstance(item, Mapping)]
    identity = {
        "project_id": project_id,
        "task_id": task_id,
        "audit_id": audit_id,
        "attempt_id": attempt_id,
    }
    matching = next(
        (
            item
            for item in intents
            if all(item.get(key) == value for key, value in identity.items())
        ),
        None,
    )
    if matching is None:
        matching = {
            **identity,
            "target_state": target_state.value,
            "evidence_fingerprint": evidence_fingerprint.digest,
            "status": status,
            "audit_ids": list(dict.fromkeys(audit_ids)),
            "kind": kind,
            "applied": False,
            "created_at": _now_iso8601(),
        }
        intents.append(matching)
    else:
        matching.update(
            {
                "target_state": target_state.value,
                "evidence_fingerprint": evidence_fingerprint.digest,
                "status": status,
                "kind": kind,
                "audit_ids": list(
                    dict.fromkeys(
                        [
                            *(
                                matching.get("audit_ids", [])
                                if isinstance(matching.get("audit_ids"), list)
                                else []
                            ),
                            *audit_ids,
                        ]
                    )
                ),
            }
        )
        if kind == "audit_rearm":
            # A coalesced owner retry is also an explicit request to repair a
            # diverged staging status.  Reopen the durable intent before the
            # tracker write; successful staging marks it applied again.
            matching["applied"] = False
            matching.pop("applied_at", None)
            matching.pop("retired_at", None)
            matching.pop("retired_reason", None)
            matching.pop("retired_by_recovery", None)
    new_unknown[_TERMINAL_RESULT_INTENTS_KEY] = intents
    return new_unknown


def _mark_terminal_result_intent_applied(
    unknown_fields: Mapping[str, Any],
    *,
    project_id: str,
    task_id: str,
    audit_id: str,
    attempt_id: str,
) -> dict[str, Any]:
    """Mark one result status intent acknowledged using current metadata."""

    new_unknown = dict(unknown_fields)
    raw_intents = new_unknown.get(_TERMINAL_RESULT_INTENTS_KEY, [])
    if not isinstance(raw_intents, list):
        return new_unknown
    intents: list[dict[str, Any]] = []
    for raw in raw_intents:
        if not isinstance(raw, Mapping):
            continue
        item = dict(raw)
        if (
            item.get("project_id") == project_id
            and item.get("task_id") == task_id
            and item.get("audit_id") == audit_id
            and item.get("attempt_id") == attempt_id
        ):
            item["applied"] = True
            item["applied_at"] = _now_iso8601()
        intents.append(item)
    new_unknown[_TERMINAL_RESULT_INTENTS_KEY] = intents
    return new_unknown


def _mark_all_terminal_result_intents_applied(
    unknown_fields: Mapping[str, Any],
    *,
    project_id: str,
    task_id: str,
) -> dict[str, Any]:
    """Retire only this task's intents when an owner override takes authority."""

    new_unknown = dict(unknown_fields)
    raw_intents = new_unknown.get(_TERMINAL_RESULT_INTENTS_KEY, [])
    if not isinstance(raw_intents, list):
        return new_unknown
    now = _now_iso8601()
    intents: list[dict[str, Any]] = []
    for raw in raw_intents:
        if not isinstance(raw, Mapping):
            continue
        item = dict(raw)
        if item.get("project_id") == project_id and item.get("task_id") == task_id:
            item.update(
                {
                    "applied": True,
                    "retired_by_override": True,
                    "applied_at": item.get("applied_at", now),
                }
            )
        intents.append(item)
    new_unknown[_TERMINAL_RESULT_INTENTS_KEY] = intents
    return new_unknown


# ------------------------------------------------------------------
# Chain-building helpers (module-level, no coordinator state required)
# ------------------------------------------------------------------


def _active_audit_authority_key(
    record: TerminalAuditRecord,
) -> tuple[int, int, int, float, str]:
    """Order duplicate live records by durable execution authority.

    A record with an in-progress launch outranks a merely pending sibling.
    Ties use the newest attempt/record timestamp and finally the stable audit
    id, so every process chooses the same survivor after restart.
    """

    in_progress = int(record.request_state is RequestState.IN_PROGRESS)
    attempts = tuple(record.attempts or ())
    active_attempt = int(
        any(
            attempt.request_state is RequestState.IN_PROGRESS
            and not attempt.ended_at
            for attempt in attempts
        )
    )
    timestamps = [record.updated_at, record.created_at]
    for attempt in attempts:
        timestamps.extend(
            (attempt.ended_at, attempt.started_at, attempt.created_at)
        )
    newest = float("-inf")
    for raw in timestamps:
        if not raw:
            continue
        try:
            parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            newest = max(newest, parsed.timestamp())
        except (TypeError, ValueError):
            continue
    return (
        active_attempt,
        in_progress,
        record.source_generation,
        newest,
        record.audit_id,
    )


def _build_new_entries(
    current_chain: list[TerminalAuditRecord],
    issue: Issue,
    target: TargetState,
    trigger: ContributorIdentity,
    fingerprint: EvidenceFingerprint,
    project_id: str,
    *,
    revision_binding: AuditRevisionBinding | None = None,
    landing_revision: str | None = None,
    workflow_revision: str | None = None,
) -> list[TerminalAuditRecord]:
    """Return the list of new :class:`~oompah.terminal_audit.TerminalAuditRecord` objects.

    The existing *current_chain* is used to decide whether a ``Done`` record
    can be reused for a ``Merged`` request.  New records are not appended here;
    the caller does that.
    """
    now = _now_iso8601()
    previous_state = issue.state or None
    selected_ref = revision_binding.selected_ref if revision_binding else None
    selected_sha = revision_binding.selected_sha if revision_binding else None
    source_generation = max(
        (
            record.source_generation
            for record in current_chain
            if record.project_id == project_id
            and record.task_id == issue.identifier
        ),
        default=0,
    ) + 1

    if target == TargetState.DONE:
        return [
            _make_record(
                project_id,
                issue.identifier,
                TargetState.DONE,
                fingerprint,
                trigger,
                previous_state,
                now,
                selected_ref=selected_ref,
                selected_sha=selected_sha,
                landing_revision=landing_revision,
                workflow_revision=workflow_revision,
                source_generation=source_generation,
            )
        ]

    if target == TargetState.MERGED:
        return _build_merged_entries(
            current_chain, project_id, issue.identifier,
            fingerprint, trigger, previous_state, now,
            revision_binding=revision_binding,
            landing_revision=landing_revision,
            workflow_revision=workflow_revision,
            source_generation=source_generation,
        )

    if target == TargetState.ARCHIVED:
        return [
            _make_record(
                project_id,
                issue.identifier,
                TargetState.ARCHIVED,
                fingerprint,
                trigger,
                previous_state,
                now,
                selected_ref=selected_ref,
                selected_sha=selected_sha,
                landing_revision=landing_revision,
                workflow_revision=workflow_revision,
                source_generation=source_generation,
            )
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
    *,
    revision_binding: AuditRevisionBinding | None = None,
    landing_revision: str | None = None,
    workflow_revision: str | None = None,
    source_generation: int,
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
            and r.project_id == project_id
            and r.task_id == task_id
            and r.request_state == RequestState.COMPLETED
            and r.evidence_fingerprint == fingerprint
            and r.workflow_revision
            == workflow_revision
            and r.landing_revision == landing_revision
            and (
                revision_binding is None
                or (
                    r.selected_ref == revision_binding.selected_ref
                    and r.selected_sha == revision_binding.selected_sha
                )
            )
        ),
        None,
    )
    active_done = next(
        (
            r for r in current_chain
            if r.target_state == TargetState.DONE
            and r.project_id == project_id
            and r.task_id == task_id
            and r.request_state in (RequestState.PENDING, RequestState.IN_PROGRESS)
            and r.evidence_fingerprint == fingerprint
            and r.workflow_revision
            == workflow_revision
            and r.landing_revision == landing_revision
            and (
                revision_binding is None
                or (
                    r.selected_ref == revision_binding.selected_ref
                    and r.selected_sha == revision_binding.selected_sha
                )
            )
        ),
        None,
    )

    entries: list[TerminalAuditRecord] = []
    selected_ref = revision_binding.selected_ref if revision_binding else None
    selected_sha = revision_binding.selected_sha if revision_binding else None
    if completed_done is None and active_done is None:
        # No completed Done — queue Done first so the auditor cannot skip it
        entries.append(
            _make_record(
                project_id,
                task_id,
                TargetState.DONE,
                fingerprint,
                trigger,
                previous_state,
                now,
                selected_ref=selected_ref,
                selected_sha=selected_sha,
                landing_revision=landing_revision,
                workflow_revision=workflow_revision,
                source_generation=source_generation,
            )
        )

    prerequisite = completed_done or active_done or entries[0]

    entries.append(
        _make_record(
            project_id,
            task_id,
            TargetState.MERGED,
            fingerprint,
            trigger,
            previous_state,
            now,
            selected_ref=selected_ref,
            selected_sha=selected_sha,
            landing_revision=landing_revision,
            workflow_revision=workflow_revision,
            source_generation=source_generation,
            eligible_at=(now if completed_done is not None else None),
            prerequisite_audit_id=prerequisite.audit_id,
        )
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
    *,
    selected_ref: str | None = None,
    selected_sha: str | None = None,
    landing_revision: str | None = None,
    workflow_revision: str | None = None,
    source_generation: int = 1,
    eligible_at: str | None = None,
    prerequisite_audit_id: str | None = None,
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
        eligible_at=(
            eligible_at
            if eligible_at is not None or prerequisite_audit_id is not None
            else created_at
        ),
        prerequisite_audit_id=prerequisite_audit_id,
        selected_ref=selected_ref,
        selected_sha=selected_sha,
        landing_revision=landing_revision,
        workflow_revision=workflow_revision,
        source_generation=source_generation,
    )


def _generate_audit_id() -> str:
    """Return a unique audit record identifier."""
    return f"audit-{uuid.uuid4().hex[:12]}"


def _stamp_epic_audit_repair(
    tracker: TrackerProtocol,
    identifier: str,
    result: AuditResult,
    audit_id: str | None,
) -> None:
    """Add the audit:repair-needed label and persist repair context.

    Called by :meth:`TerminalTransitionCoordinator._apply_result_locked`
    immediately after the epic is moved back to ``Open``.  A tracker failure
    is logged and swallowed — the repair label is advisory; the caller's
    ``ResultOutcome`` has already been decided and must not be affected.

    The repair context is a small, versioned document stored under
    :data:`~oompah.models.EPIC_AUDIT_REPAIR_METADATA_KEY`::

        {
            "version": 1,
            "audit_id": "<failed_audit_id>",
            "failure_classification": "<classification or null>",
            "findings_summary": "<brief human-readable audit message>",
            "claimed": False,
        }

    The ``claimed`` flag is set to ``True`` by the orchestrator's
    ``_should_dispatch_epic`` path when it claims the repair run, preventing
    duplicate dispatch on restart.
    """
    effective_audit_id = audit_id or (result.audit_id if result else "")
    # Summarise the failure for the repair-planner prompt.  Audit messages
    # can contain sensitive or large text — limit to 512 chars and strip
    # leading/trailing whitespace.  An empty message is stored as an empty
    # string so the planner knows a summary was unavailable.
    raw_message = (getattr(result, "message", None) or "").strip()
    findings_summary = raw_message[:512]

    classification_raw = getattr(result, "failure_classification", None)
    classification_str = (
        classification_raw.value
        if isinstance(classification_raw, FailureClassification)
        else (str(classification_raw) if classification_raw is not None else "")
    )

    repair_doc: dict[str, object] = {
        "version": EPIC_AUDIT_REPAIR_METADATA_VERSION,
        "audit_id": effective_audit_id,
        "failure_classification": classification_str,
        "findings_summary": findings_summary,
        "claimed": False,
    }
    try:
        tracker.set_metadata_field(
            identifier, EPIC_AUDIT_REPAIR_METADATA_KEY, repair_doc
        )
    except Exception:
        logger.exception(
            "Failed to persist audit-repair metadata for epic %s", identifier
        )
    try:
        tracker.add_label(identifier, EPIC_AUDIT_REPAIR_LABEL)
    except Exception:
        logger.exception(
            "Failed to add %r label to epic %s after failed audit",
            EPIC_AUDIT_REPAIR_LABEL,
            identifier,
        )


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
    "TerminalTransitionBusyError",
    "TransitionResult",
    "classify_failure_to_status",
    "route_failure_status",
    "_stamp_epic_audit_repair",
]
