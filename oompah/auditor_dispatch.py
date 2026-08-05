"""Durable scheduling policy for independent completion auditors.

The orchestrator owns tracker I/O and worker lifecycles; this module owns the
small state machine between those boundaries.  Keeping candidate exclusion,
attempt creation, and abandoned-session handling here makes the retry rules
testable without starting an agent or a tracker server.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Callable

from oompah.auditor_candidate_selector import (
    AuditorCandidateSelector,
    NoCandidateReason,
)
from oompah.integration import accepted_submission_branch
from oompah.roles import Candidate
from oompah.terminal_audit import (
    AuditAttempt,
    EvidenceFingerprint,
    RequestState,
    TargetState,
    TerminalAuditRecord,
)

if TYPE_CHECKING:
    from oompah.terminal_audit import FailureClassification


def utc_now() -> datetime:
    """Return an aware UTC timestamp; a seam for deterministic tests."""

    return datetime.now(timezone.utc)


def timestamp(value: datetime | None = None) -> str:
    """Serialize a scheduler timestamp in the canonical ISO-8601 form."""

    return (value or utc_now()).isoformat()


def parse_timestamp(value: str | None) -> datetime | None:
    """Parse a persisted timestamp, returning ``None`` for malformed data."""

    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def audit_branch_key(issue: Any) -> str:
    """Return the branch identity shared by auditors and implementation work."""

    accepted_branch = accepted_submission_branch(issue)
    if accepted_branch:
        return accepted_branch
    for attr in ("work_branch", "branch_name"):
        value = str(getattr(issue, attr, "") or "").strip()
        if value:
            return value
    parent = str(getattr(issue, "parent_id", "") or "").strip()
    if parent:
        return f"epic:{parent}"
    project = str(getattr(issue, "project_id", "") or "").strip()
    identifier = str(getattr(issue, "identifier", "") or getattr(issue, "id", ""))
    return f"{project}:{identifier}"


@dataclass(frozen=True)
class AuditDispatchPlan:
    """The immutable launch data persisted before a worker is started."""

    audit_id: str
    attempt_id: str
    target_state: TargetState
    evidence_fingerprint: EvidenceFingerprint
    candidate: Candidate
    rotation_count: int
    branch_key: str
    created_at: str
    previous_state: str | None = None


@dataclass(frozen=True)
class AuditRecovery:
    """Result of examining the latest durable attempt."""

    record: TerminalAuditRecord
    ready: bool
    reason: str | None = None
    attempt_id: str | None = None


class AuditorDispatchLane:
    """Implement independent-candidate dispatch and retry transitions."""

    def __init__(
        self,
        selector: AuditorCandidateSelector,
        *,
        max_attempts: int = 3,
        attempt_ttl_seconds: int = 3600,
        clock: Callable[[], datetime] = utc_now,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        if max_attempts <= 0:
            raise ValueError("max_attempts must be positive")
        if attempt_ttl_seconds <= 0:
            raise ValueError("attempt_ttl_seconds must be positive")
        self.selector = selector
        self.max_attempts = max_attempts
        self.attempt_ttl_seconds = attempt_ttl_seconds
        self.clock = clock
        self.id_factory = id_factory or (lambda: f"attempt-{uuid.uuid4().hex[:12]}")

    @staticmethod
    def pending_record(
        records: list[TerminalAuditRecord],
    ) -> TerminalAuditRecord | None:
        """Return the first pending or in-progress target in chain order."""

        for record in records:
            if record.request_state in (
                RequestState.PENDING,
                RequestState.IN_PROGRESS,
            ):
                return record
        return None

    @staticmethod
    def attempted_pairs(record: TerminalAuditRecord) -> set[tuple[str, str]]:
        """Return provider/model pairs already used by this audit."""

        return {
            (attempt.provider_id, attempt.model)
            for attempt in record.attempts
            if attempt.provider_id and attempt.model
        }

    def current_attempt(self, record: TerminalAuditRecord) -> AuditAttempt | None:
        """Return the latest launch attempt, if it is still in progress."""

        for attempt in reversed(record.attempts):
            if attempt.request_state == RequestState.IN_PROGRESS and not attempt.ended_at:
                return attempt
        return None

    def recover(
        self,
        record: TerminalAuditRecord,
        *,
        active_attempt_ids: set[str] | None = None,
        now: datetime | None = None,
    ) -> AuditRecovery:
        """Rehydrate a record and mark an abandoned launch ready for retry.

        When the caller supplies the live attempt IDs, an attempt absent from
        that set is abandoned immediately (including after a process restart).
        Callers without a live-worker registry can omit the set and use the
        TTL grace period instead.  A changed fingerprint is never allowed to
        complete an old attempt.
        """

        current = self.current_attempt(record)
        if current is None:
            now = now or self.clock()
            latest = record.attempts[-1] if record.attempts else None
            retry_at = parse_timestamp(latest.next_retry_at) if latest else None
            if retry_at is not None and now < retry_at:
                return AuditRecovery(
                    record,
                    False,
                    f"auditor retry backoff until {latest.next_retry_at}",
                    latest.attempt_id if latest else None,
                )
            return AuditRecovery(record, record.request_state == RequestState.PENDING, None)

        now = now or self.clock()
        started = parse_timestamp(current.started_at or current.created_at)
        fingerprint_changed = current.evidence_fingerprint != record.evidence_fingerprint
        age = (
            (now - started).total_seconds()
            if started is not None
            else float(self.attempt_ttl_seconds)
        )
        active = active_attempt_ids is not None and current.attempt_id in active_attempt_ids
        if active and fingerprint_changed:
            return AuditRecovery(
                record,
                False,
                "evidence fingerprint changed while auditor is running",
                current.attempt_id,
            )
        if fingerprint_changed:
            reason = "evidence fingerprint changed during auditor run"
        elif active and age >= self.attempt_ttl_seconds:
            return AuditRecovery(
                record,
                False,
                "auditor session exceeded TTL; termination required",
                current.attempt_id,
            )
        elif active:
            return AuditRecovery(record, False, "auditor already running", current.attempt_id)
        elif current.ended_at:
            reason = current.failure_reason or "auditor attempt ended"
        elif age >= self.attempt_ttl_seconds:
            reason = "auditor session abandoned after attempt TTL"
        elif active_attempt_ids is not None:
            reason = "auditor session abandoned; no live worker owns the attempt"
        else:
            return AuditRecovery(record, False, "recent auditor attempt presumed running", current.attempt_id)

        ended = replace(
            current,
            request_state=RequestState.PENDING,
            ended_at=current.ended_at or timestamp(now),
            failure_reason=reason,
        )
        attempts = [
            ended if attempt.attempt_id == current.attempt_id else attempt
            for attempt in record.attempts
        ]
        return AuditRecovery(
            replace(record, request_state=RequestState.PENDING, attempts=attempts),
            True,
            reason,
            current.attempt_id,
        )

    def plan(
        self,
        record: TerminalAuditRecord,
        contributors: list[Any] | None,
        *,
        branch_key: str,
        now: datetime | None = None,
    ) -> tuple[AuditDispatchPlan | None, NoCandidateReason | None]:
        """Select a fresh candidate and build the attempt to persist."""

        attempts = len(record.attempts)
        if attempts >= self.max_attempts:
            return None, NoCandidateReason(
                "all_attempted",
                f"Audit reached the maximum of {self.max_attempts} attempts.",
            )
        candidates, reason = self.selector.select_candidates(
            contributors, exclude=self.attempted_pairs(record)
        )
        if reason is not None or not candidates:
            return None, reason or NoCandidateReason(
                "empty_role", "Auditor role has no candidates."
            )
        candidate = candidates[0]
        created = timestamp(now or self.clock())
        return (
            AuditDispatchPlan(
                audit_id=record.audit_id,
                attempt_id=self.id_factory(),
                target_state=record.target_state,
                evidence_fingerprint=record.evidence_fingerprint,
                candidate=candidate,
                rotation_count=attempts,
                branch_key=branch_key,
                created_at=created,
                previous_state=record.previous_state,
            ),
            None,
        )

    @staticmethod
    def persist_plan(
        record: TerminalAuditRecord,
        plan: AuditDispatchPlan,
    ) -> TerminalAuditRecord:
        """Return the record with a launch identity in ``IN_PROGRESS`` state."""

        if plan.audit_id != record.audit_id:
            raise ValueError("dispatch plan belongs to a different audit")
        attempt = AuditAttempt(
            attempt_id=plan.attempt_id,
            target_state=plan.target_state,
            evidence_fingerprint=plan.evidence_fingerprint,
            request_state=RequestState.IN_PROGRESS,
            provider_id=plan.candidate.provider_id,
            model=plan.candidate.model,
            created_at=plan.created_at,
            started_at=plan.created_at,
            candidate_rotation_count=plan.rotation_count,
            branch_key=plan.branch_key,
        )
        return replace(
            record,
            request_state=RequestState.IN_PROGRESS,
            attempts=[*record.attempts, attempt],
            updated_at=plan.created_at,
        )

    @staticmethod
    def finish_attempt(
        record: TerminalAuditRecord,
        attempt_id: str,
        *,
        reason: str | None = None,
        ended_at: str | None = None,
        retry_after: str | None = None,
        failure_classification: "FailureClassification | None" = None,
    ) -> TerminalAuditRecord:
        """Mark a launched attempt ended without changing the audit verdict.
        
        When a transient failure occurs (launch error, transport error, timeout, etc.),
        set failure_classification to indicate the error type. The attempt is marked
        PENDING with next_retry_at to enable automatic rotation to the next candidate.
        The failure_classification persists for audit history even if the next attempt
        succeeds.
        """
        from oompah.terminal_audit import FailureClassification

        end = ended_at or timestamp()
        changed = False
        attempts: list[AuditAttempt] = []
        for attempt in record.attempts:
            if attempt.attempt_id != attempt_id:
                attempts.append(attempt)
                continue
            changed = True
            # Ensure failure_classification is set for transient failures
            classification = failure_classification
            if classification is not None and not isinstance(classification, FailureClassification):
                classification = FailureClassification.from_raw(classification)
            attempts.append(
                replace(
                    attempt,
                    request_state=RequestState.PENDING,
                    ended_at=end,
                    failure_reason=reason or attempt.failure_reason,
                    next_retry_at=retry_after,
                    failure_classification=classification or attempt.failure_classification,
                )
            )
        if not changed:
            return record
        return replace(record, request_state=RequestState.PENDING, attempts=attempts, updated_at=end)


__all__ = [
    "AuditDispatchPlan",
    "AuditRecovery",
    "AuditorDispatchLane",
    "audit_branch_key",
    "parse_timestamp",
]
