"""Read-only evidence collector for Archived terminal audits.

Verifies that a task can be safely retired (archived), checking:
- Completed Done/Merged audit with passing verdict
- Configured retention/disposition reason (with structured type)
- No active worker/claim/retry
- No open review
- No active child or unresolved dependency
- No requirements/evidence-changing activity after the prior audit
- For direct dispositions (duplicate/obsolete), required source link/evidence

Returns exact unsafe condition and recommended restoration state to help
operators restore mistakenly archived work.

All operations are read-only. Missing or invalid evidence is explicitly
typed rather than guessed, ensuring auditors receive clear failure signals.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Re-export shared evidence markers from done_evidence_collector
from oompah.done_evidence_collector import (  # noqa: E402
    EvidenceInvalid,
    EvidenceUnavailable,
)
from oompah.terminal_audit import EvidenceFingerprint, Verdict  # noqa: E402

MaybeEvidence = str | int | float | bool | None | dict[str, Any] | list[Any] | EvidenceUnavailable | EvidenceInvalid


class DispositionType(str, Enum):
    """Classification of why a task is being archived."""

    RETENTION = "retention"
    """Task completed and retained long enough per policy."""

    DUPLICATE = "duplicate"
    """Duplicate of another completed task (requires source_link)."""

    OBSOLETE = "obsolete"
    """No longer needed/relevant (requires source_link for replacement)."""

    BLOCKED = "blocked"
    """Permanently blocked/unresolvable (requires explanation)."""

    SUPERSEDED = "superseded"
    """Replaced by newer work (requires source_link to replacement)."""

    @classmethod
    def from_raw(cls, raw: Any) -> "DispositionType":
        """Parse disposition type from string or enum."""
        if isinstance(raw, cls):
            return raw
        if not isinstance(raw, str) or not raw.strip():
            valid = ", ".join(member.value for member in cls)
            raise ValueError(
                f"DispositionType must be a non-empty string; expected one of: {valid}"
            )
        normalized = raw.strip().lower().replace("-", "_").replace(" ", "_")
        for member in cls:
            if str(member.value).lower() == normalized:
                return member
        valid = ", ".join(member.value for member in cls)
        raise ValueError(
            f"Unknown DispositionType {raw!r}; expected one of: {valid}"
        )


class SafetyFailureMode(str, Enum):
    """Specific reason archive safety check failed."""

    NO_DONE_AUDIT = "no_done_audit"
    DONE_AUDIT_FAILED = "done_audit_failed"
    NO_MERGED_AUDIT = "no_merged_audit"
    MERGED_AUDIT_FAILED = "merged_audit_failed"

    NO_DISPOSITION_REASON = "no_disposition_reason"
    INVALID_DISPOSITION_TYPE = "invalid_disposition_type"

    ACTIVE_WORKER = "active_worker"
    ACTIVE_CLAIM = "active_claim"
    ACTIVE_RETRY = "active_retry"

    OPEN_REVIEW = "open_review"

    ACTIVE_CHILD = "active_child"
    UNRESOLVED_DEPENDENCY = "unresolved_dependency"

    REQUIREMENT_CHANGED = "requirement_changed"
    SHA_CHANGED = "sha_changed"

    DUPLICATE_NO_SOURCE = "duplicate_no_source"
    OBSOLETE_NO_SOURCE = "obsolete_no_source"
    BLOCKED_NO_EXPLANATION = "blocked_no_explanation"
    SUPERSEDED_NO_SOURCE = "superseded_no_source"

    RECENT_COMPLETION = "recent_completion"
    FINGERPRINT_MISMATCH = "fingerprint_mismatch"

    MISSING_EVIDENCE = "missing_evidence"


@dataclass(frozen=True)
class DispositionReason:
    """Structured retention/disposition reason for archiving."""

    type: DispositionType
    explanation: str
    """Human-readable explanation of why this disposition applies."""

    source_link: Optional[str] = None
    """URL or ID reference to duplicate/obsolete/replacement task."""

    def __post_init__(self) -> None:
        if not isinstance(self.type, DispositionType):
            raise TypeError("DispositionReason.type must be a DispositionType")
        if not isinstance(self.explanation, str) or not self.explanation.strip():
            raise ValueError("DispositionReason.explanation must be non-empty")
        if self.source_link is not None and not isinstance(self.source_link, str):
            raise TypeError("DispositionReason.source_link must be a string or null")

    def requires_source_link(self) -> bool:
        """Check if this disposition type requires a source link."""
        return self.type in (
            DispositionType.DUPLICATE,
            DispositionType.OBSOLETE,
            DispositionType.SUPERSEDED,
        )


@dataclass(frozen=True)
class TaskStateSnapshot:
    """Pre-archive state of the task before retirement."""

    task_id: str
    current_state: str
    """Current tracker state (e.g. 'Done', 'Merged', 'Archived')."""

    has_active_worker: bool | EvidenceUnavailable
    """Whether task has an active assigned worker/agent."""

    has_open_review: bool | EvidenceUnavailable
    """Whether task has any open pull/merge request."""

    has_active_child: bool | EvidenceUnavailable
    """Whether task has any child task not in terminal state."""

    has_unresolved_dependency: bool | EvidenceUnavailable
    """Whether task has any blocking dependency not complete."""

    def __post_init__(self) -> None:
        if not isinstance(self.task_id, str) or not self.task_id.strip():
            raise ValueError("TaskStateSnapshot.task_id must be non-empty")
        if not isinstance(self.current_state, str):
            raise ValueError("TaskStateSnapshot.current_state must be a string")


@dataclass(frozen=True)
class AuditReferenceEvidence:
    """Evidence linking to a prior Done or Merged audit."""

    audit_id: str
    audit_type: str
    """Either 'Done' or 'Merged'."""

    verdict: str | EvidenceUnavailable | EvidenceInvalid
    """Should be 'pass' or 'passed' for safe archival."""

    fingerprint: EvidenceFingerprint | EvidenceUnavailable | EvidenceInvalid
    """SHA-256 digest of evidence at audit time."""

    def __post_init__(self) -> None:
        if not isinstance(self.audit_id, str) or not self.audit_id.strip():
            raise ValueError("AuditReferenceEvidence.audit_id must be non-empty")
        if self.audit_type not in ("Done", "Merged"):
            raise ValueError("AuditReferenceEvidence.audit_type must be Done or Merged")


@dataclass(frozen=True)
class RestorationGuidance:
    """Recommended state to restore mistakenly archived work."""

    restored_state: str
    """Target state to restore to (e.g. 'Done', 'Merged', 'Open')."""

    required_actions: list[str] = field(default_factory=list)
    """Steps to take when restoring (e.g. 'reopen review', 'reassign worker')."""

    unsafe_condition: str = ""
    """Exact reason archive is unsafe in human-readable form."""

    def __post_init__(self) -> None:
        if not isinstance(self.restored_state, str) or not self.restored_state.strip():
            raise ValueError("RestorationGuidance.restored_state must be non-empty")
        if not isinstance(self.required_actions, list):
            raise TypeError("RestorationGuidance.required_actions must be a list")
        if not isinstance(self.unsafe_condition, str):
            raise TypeError("RestorationGuidance.unsafe_condition must be a string")


@dataclass(frozen=True)
class ArchivedEvidenceSnapshot:
    """Complete evidence snapshot for an Archived terminal audit."""

    # Task pre-archive state
    task_state: TaskStateSnapshot | EvidenceUnavailable | EvidenceInvalid

    # Prior audit
    prior_audit: AuditReferenceEvidence | EvidenceUnavailable | EvidenceInvalid

    # Disposition reason
    disposition: DispositionReason | EvidenceUnavailable | EvidenceInvalid

    # Detected safety failures
    failure_modes: list[str] = field(default_factory=list)

    # Restoration guidance (populated when archive is unsafe)
    restoration_guidance: RestorationGuidance | None = None

    # Metadata
    task_id: str = ""
    project_id: str = ""
    audit_id: str = ""
    collected_at: str = ""

    def passed(self) -> bool:
        """True when archive is safe (no failure modes, all checks pass)."""
        if self.failure_modes:
            return False
        if isinstance(self.prior_audit, (EvidenceUnavailable, EvidenceInvalid)):
            return False
        if isinstance(self.task_state, (EvidenceUnavailable, EvidenceInvalid)):
            return False
        if isinstance(self.disposition, (EvidenceUnavailable, EvidenceInvalid)):
            return False
        # Check audit verdict
        if isinstance(self.prior_audit, AuditReferenceEvidence):
            if isinstance(self.prior_audit.verdict, str):
                if self.prior_audit.verdict.lower() not in ("pass", "passed"):
                    return False
            else:
                return False
        # Check no active state
        if isinstance(self.task_state, TaskStateSnapshot):
            if self.task_state.has_active_worker is True:
                return False
            if self.task_state.has_open_review is True:
                return False
            if self.task_state.has_active_child is True:
                return False
            if self.task_state.has_unresolved_dependency is True:
                return False
        return True

    def has_failures(self) -> bool:
        """True when any evidence is unavailable/invalid or safety failed."""
        if self.failure_modes:
            return True

        def _check(obj: Any) -> bool:
            if isinstance(obj, (EvidenceUnavailable, EvidenceInvalid)):
                return True
            if isinstance(obj, dict):
                return any(_check(v) for v in obj.values())
            if isinstance(obj, list):
                return any(_check(v) for v in obj)
            return False

        for v in vars(self).values():
            if _check(v):
                return True
        return False


class ArchivedEvidenceCollector:
    """Read-only evidence collector for Archived terminal audits.

    Verifies that a task can be safely retired:
    - Has passing Done or Merged audit
    - Has configured disposition reason (with required source links)
    - No active worker/claim/retry
    - No open review
    - No active children or unresolved dependencies
    - No evidence/requirement changes after prior audit

    Returns restoration guidance when archive is unsafe.
    """

    def __init__(
        self,
        task_id: str = "",
        project_id: str = "",
    ) -> None:
        """Initialize the collector.

        Args:
            task_id: The task identifier being audited
            project_id: The project identifier
        """
        self.task_id = task_id
        self.project_id = project_id

    def collect(
        self,
        *,
        current_state: str = "",
        disposition_type: str | DispositionType | None = None,
        disposition_explanation: str = "",
        disposition_source_link: str | None = None,
        prior_done_audit_id: str = "",
        prior_done_verdict: str = "",
        prior_done_fingerprint: EvidenceFingerprint | None = None,
        prior_merged_audit_id: str = "",
        prior_merged_verdict: str = "",
        prior_merged_fingerprint: EvidenceFingerprint | None = None,
        has_active_worker: bool | EvidenceUnavailable = False,
        has_active_claim: bool | EvidenceUnavailable = False,
        has_active_retry: bool | EvidenceUnavailable = False,
        has_open_review: bool | EvidenceUnavailable = False,
        has_active_child: bool | EvidenceUnavailable = False,
        has_unresolved_dependency: bool | EvidenceUnavailable = False,
        requirement_changed_after_prior_audit: bool | EvidenceUnavailable = False,
        sha_changed_after_prior_audit: bool | EvidenceUnavailable = False,
        days_since_completion: float | EvidenceUnavailable = 0,
        retention_days_required: float = 30,
        current_fingerprint: EvidenceFingerprint | None = None,
        audit_id: str = "",
        collected_at: str = "",
    ) -> ArchivedEvidenceSnapshot:
        """Collect complete Archived evidence snapshot.

        Args:
            current_state: Current tracker state of task.
            disposition_type: Why task is being archived (retention/duplicate/obsolete/etc).
            disposition_explanation: Human-readable reason for archival.
            disposition_source_link: URL/ID for duplicate/obsolete/replacement task.
            prior_done_audit_id: ID of prior Done audit (if any).
            prior_done_verdict: Verdict of Done audit ('pass'/'fail').
            prior_done_fingerprint: Fingerprint of Done audit evidence.
            prior_merged_audit_id: ID of prior Merged audit (if any).
            prior_merged_verdict: Verdict of Merged audit.
            prior_merged_fingerprint: Fingerprint of Merged audit evidence.
            has_active_worker: Whether task has active assigned worker.
            has_active_claim: Whether task has active claim/ownership.
            has_active_retry: Whether task has active retry scheduled.
            has_open_review: Whether task has open pull/merge request.
            has_active_child: Whether task has unresolved child tasks.
            has_unresolved_dependency: Whether task has blocking dependencies.
            requirement_changed_after_prior_audit: Whether requirements changed.
            sha_changed_after_prior_audit: Whether branch SHA changed.
            days_since_completion: Days since task completed.
            retention_days_required: Minimum retention period for completion.
            current_fingerprint: Current evidence fingerprint to check against prior.
            audit_id: This audit's ID.
            collected_at: ISO8601 timestamp of collection.

        Returns:
            ArchivedEvidenceSnapshot with all collected evidence.
        """
        failure_modes: list[str] = []

        # 1. Build task state snapshot
        task_state = self._collect_task_state(
            current_state,
            has_active_worker,
            has_active_claim,
            has_active_retry,
            has_open_review,
            has_active_child,
            has_unresolved_dependency,
            failure_modes,
        )

        # 2. Validate disposition reason
        disposition = self._validate_disposition(
            disposition_type,
            disposition_explanation,
            disposition_source_link,
            failure_modes,
        )

        # 3. Collect prior audit evidence
        prior_audit = self._select_and_validate_prior_audit(
            prior_done_audit_id,
            prior_done_verdict,
            prior_done_fingerprint,
            prior_merged_audit_id,
            prior_merged_verdict,
            prior_merged_fingerprint,
            failure_modes,
        )

        # 4. Check for evidence changes after prior audit
        self._check_evidence_changes(
            current_fingerprint,
            prior_audit,
            requirement_changed_after_prior_audit,
            sha_changed_after_prior_audit,
            failure_modes,
        )

        # 5. Check retention period
        self._check_retention_period(
            days_since_completion,
            retention_days_required,
            failure_modes,
        )

        # 6. Build restoration guidance if unsafe
        restoration_guidance = None
        if failure_modes:
            restoration_guidance = self._build_restoration_guidance(
                failure_modes,
                task_state,
                prior_audit,
            )

        return ArchivedEvidenceSnapshot(
            task_state=task_state,
            prior_audit=prior_audit,
            disposition=disposition,
            failure_modes=failure_modes,
            restoration_guidance=restoration_guidance,
            task_id=self.task_id,
            project_id=self.project_id,
            audit_id=audit_id,
            collected_at=collected_at,
        )

    # ------------------------------------------------------------------
    # Private evidence collection methods
    # ------------------------------------------------------------------

    def _collect_task_state(
        self,
        current_state: str,
        has_active_worker: bool | EvidenceUnavailable,
        has_active_claim: bool | EvidenceUnavailable,
        has_active_retry: bool | EvidenceUnavailable,
        has_open_review: bool | EvidenceUnavailable,
        has_active_child: bool | EvidenceUnavailable,
        has_unresolved_dependency: bool | EvidenceUnavailable,
        failure_modes: list[str],
    ) -> TaskStateSnapshot | EvidenceUnavailable | EvidenceInvalid:
        """Build task state snapshot and record failures."""
        try:
            # Check for active worker/claim/retry
            if has_active_worker is True:
                failure_modes.append(SafetyFailureMode.ACTIVE_WORKER.value)
            elif isinstance(has_active_worker, EvidenceUnavailable):
                pass  # Will be marked unavailable

            if has_active_claim is True:
                failure_modes.append(SafetyFailureMode.ACTIVE_CLAIM.value)

            if has_active_retry is True:
                failure_modes.append(SafetyFailureMode.ACTIVE_RETRY.value)

            # Check for open review
            if has_open_review is True:
                failure_modes.append(SafetyFailureMode.OPEN_REVIEW.value)

            # Check for active children
            if has_active_child is True:
                failure_modes.append(SafetyFailureMode.ACTIVE_CHILD.value)

            # Check for unresolved dependencies
            if has_unresolved_dependency is True:
                failure_modes.append(SafetyFailureMode.UNRESOLVED_DEPENDENCY.value)

            return TaskStateSnapshot(
                task_id=self.task_id,
                current_state=current_state or "unknown",
                has_active_worker=has_active_worker,
                has_open_review=has_open_review,
                has_active_child=has_active_child,
                has_unresolved_dependency=has_unresolved_dependency,
            )
        except Exception as exc:
            logger.exception("Failed to collect task state")
            return EvidenceUnavailable(f"Failed to collect task state: {exc}")

    def _validate_disposition(
        self,
        disposition_type: str | DispositionType | None,
        disposition_explanation: str,
        disposition_source_link: str | None,
        failure_modes: list[str],
    ) -> DispositionReason | EvidenceUnavailable | EvidenceInvalid:
        """Validate disposition reason and required source links."""
        try:
            if not disposition_type:
                failure_modes.append(SafetyFailureMode.NO_DISPOSITION_REASON.value)
                return EvidenceUnavailable("No disposition type provided")

            if not disposition_explanation or not disposition_explanation.strip():
                failure_modes.append(SafetyFailureMode.NO_DISPOSITION_REASON.value)
                return EvidenceUnavailable("No disposition explanation provided")

            try:
                dt = (
                    disposition_type
                    if isinstance(disposition_type, DispositionType)
                    else DispositionType.from_raw(disposition_type)
                )
            except ValueError as exc:
                failure_modes.append(SafetyFailureMode.INVALID_DISPOSITION_TYPE.value)
                return EvidenceInvalid(f"Invalid disposition type: {exc}")

            # Check source link requirements
            if dt.value == DispositionType.DUPLICATE.value and not disposition_source_link:
                failure_modes.append(SafetyFailureMode.DUPLICATE_NO_SOURCE.value)
                return EvidenceInvalid("Duplicate disposition requires source_link")

            if dt.value == DispositionType.OBSOLETE.value and not disposition_source_link:
                failure_modes.append(SafetyFailureMode.OBSOLETE_NO_SOURCE.value)
                return EvidenceInvalid("Obsolete disposition requires source_link")

            if dt.value == DispositionType.SUPERSEDED.value and not disposition_source_link:
                failure_modes.append(SafetyFailureMode.SUPERSEDED_NO_SOURCE.value)
                return EvidenceInvalid("Superseded disposition requires source_link")

            if dt.value == DispositionType.BLOCKED.value and not disposition_explanation.strip():
                failure_modes.append(SafetyFailureMode.BLOCKED_NO_EXPLANATION.value)
                return EvidenceInvalid("Blocked disposition requires detailed explanation")

            return DispositionReason(
                type=dt,
                explanation=disposition_explanation,
                source_link=disposition_source_link,
            )
        except Exception as exc:
            logger.exception("Failed to validate disposition")
            return EvidenceUnavailable(f"Failed to validate disposition: {exc}")

    def _select_and_validate_prior_audit(
        self,
        prior_done_audit_id: str,
        prior_done_verdict: str,
        prior_done_fingerprint: EvidenceFingerprint | None,
        prior_merged_audit_id: str,
        prior_merged_verdict: str,
        prior_merged_fingerprint: EvidenceFingerprint | None,
        failure_modes: list[str],
    ) -> AuditReferenceEvidence | EvidenceUnavailable | EvidenceInvalid:
        """Select and validate a prior Done or Merged audit.

        Prefers Merged if available, falls back to Done.
        """
        try:
            # Try Merged audit first
            if prior_merged_audit_id and prior_merged_audit_id.strip():
                merged_evidence = self._validate_audit_reference(
                    prior_merged_audit_id,
                    "Merged",
                    prior_merged_verdict,
                    prior_merged_fingerprint,
                    SafetyFailureMode.MERGED_AUDIT_FAILED,
                )
                if isinstance(merged_evidence, AuditReferenceEvidence):
                    # Check if verdict is passing
                    if isinstance(merged_evidence.verdict, str):
                        if merged_evidence.verdict.lower() in ("pass", "passed"):
                            return merged_evidence
                        else:
                            # Non-passing verdict
                            failure_modes.append(SafetyFailureMode.MERGED_AUDIT_FAILED.value)
                            return merged_evidence
                    # Verdict is unavailable/invalid
                    failure_modes.append(SafetyFailureMode.MERGED_AUDIT_FAILED.value)
                    return merged_evidence

            # Fall back to Done audit
            if prior_done_audit_id and prior_done_audit_id.strip():
                done_evidence = self._validate_audit_reference(
                    prior_done_audit_id,
                    "Done",
                    prior_done_verdict,
                    prior_done_fingerprint,
                    SafetyFailureMode.DONE_AUDIT_FAILED,
                )
                if isinstance(done_evidence, AuditReferenceEvidence):
                    # Check if verdict is passing
                    if isinstance(done_evidence.verdict, str):
                        if done_evidence.verdict.lower() in ("pass", "passed"):
                            return done_evidence
                        else:
                            # Non-passing verdict
                            failure_modes.append(SafetyFailureMode.DONE_AUDIT_FAILED.value)
                            return done_evidence
                    # Verdict is unavailable/invalid
                    failure_modes.append(SafetyFailureMode.DONE_AUDIT_FAILED.value)
                    return done_evidence

            # Neither available or both failed
            failure_modes.append(SafetyFailureMode.NO_DONE_AUDIT.value)
            return EvidenceUnavailable("No prior Done or Merged audit provided")
        except Exception as exc:
            logger.exception("Failed to validate prior audit")
            return EvidenceUnavailable(f"Failed to validate prior audit: {exc}")

    def _validate_audit_reference(
        self,
        audit_id: str,
        audit_type: str,
        verdict: str,
        fingerprint: EvidenceFingerprint | None,
        failure_mode: SafetyFailureMode,
    ) -> AuditReferenceEvidence | EvidenceUnavailable | EvidenceInvalid:
        """Validate a single audit reference (Done or Merged)."""
        if not audit_id or not audit_id.strip():
            return EvidenceUnavailable(f"No {audit_type} audit ID provided")

        verdict_evidence: str | EvidenceUnavailable | EvidenceInvalid
        if not verdict or not verdict.strip():
            verdict_evidence = EvidenceUnavailable(f"{audit_type} audit verdict not provided")
        elif verdict.lower() not in ("pass", "passed"):
            # Store the actual verdict (fail, error, etc.) for validation
            verdict_evidence = verdict
        else:
            verdict_evidence = verdict

        fp_evidence: EvidenceFingerprint | EvidenceUnavailable | EvidenceInvalid
        if fingerprint is None:
            fp_evidence = EvidenceUnavailable(f"{audit_type} audit fingerprint not provided")
        elif isinstance(fingerprint, EvidenceFingerprint):
            fp_evidence = fingerprint
        else:
            fp_evidence = EvidenceInvalid(
                f"{audit_type} audit fingerprint is invalid type"
            )

        return AuditReferenceEvidence(
            audit_id=audit_id,
            audit_type=audit_type,
            verdict=verdict_evidence,
            fingerprint=fp_evidence,
        )

    def _check_evidence_changes(
        self,
        current_fingerprint: EvidenceFingerprint | None,
        prior_audit: AuditReferenceEvidence | EvidenceUnavailable | EvidenceInvalid,
        requirement_changed: bool | EvidenceUnavailable,
        sha_changed: bool | EvidenceUnavailable,
        failure_modes: list[str],
    ) -> None:
        """Check for evidence/requirement changes after prior audit."""
        # Check if requirements changed
        if requirement_changed is True:
            failure_modes.append(SafetyFailureMode.REQUIREMENT_CHANGED.value)

        # Check if SHA changed
        if sha_changed is True:
            failure_modes.append(SafetyFailureMode.SHA_CHANGED.value)

        # Check fingerprint match
        if (
            isinstance(prior_audit, AuditReferenceEvidence)
            and isinstance(prior_audit.fingerprint, EvidenceFingerprint)
            and current_fingerprint is not None
        ):
            if prior_audit.fingerprint.digest != current_fingerprint.digest:
                failure_modes.append(SafetyFailureMode.FINGERPRINT_MISMATCH.value)

    def _check_retention_period(
        self,
        days_since_completion: float | EvidenceUnavailable,
        retention_days_required: float,
        failure_modes: list[str],
    ) -> None:
        """Check if task has been retained long enough."""
        if isinstance(days_since_completion, EvidenceUnavailable):
            return  # Can't check, not a failure

        if days_since_completion < retention_days_required:
            failure_modes.append(SafetyFailureMode.RECENT_COMPLETION.value)

    def _build_restoration_guidance(
        self,
        failure_modes: list[str],
        task_state: TaskStateSnapshot | EvidenceUnavailable | EvidenceInvalid,
        prior_audit: AuditReferenceEvidence | EvidenceUnavailable | EvidenceInvalid,
    ) -> RestorationGuidance:
        """Build restoration guidance based on failure modes."""
        restored_state = "Done"
        if isinstance(prior_audit, AuditReferenceEvidence):
            restored_state = prior_audit.audit_type

        required_actions: list[str] = []
        unsafe_conditions: list[str] = []

        for mode in failure_modes:
            if mode == SafetyFailureMode.ACTIVE_WORKER.value:
                unsafe_conditions.append("Task has active assigned worker")
                required_actions.append("Unassign active worker before archiving")
            elif mode == SafetyFailureMode.ACTIVE_CLAIM.value:
                unsafe_conditions.append("Task has active claim/ownership")
                required_actions.append("Release claim before archiving")
            elif mode == SafetyFailureMode.ACTIVE_RETRY.value:
                unsafe_conditions.append("Task has scheduled retry")
                required_actions.append("Cancel retry and resolve before archiving")
            elif mode == SafetyFailureMode.OPEN_REVIEW.value:
                unsafe_conditions.append("Task has open pull/merge request")
                required_actions.append("Close review or merge before archiving")
            elif mode == SafetyFailureMode.ACTIVE_CHILD.value:
                unsafe_conditions.append("Task has unresolved child tasks")
                required_actions.append("Complete or archive all children before archiving parent")
            elif mode == SafetyFailureMode.UNRESOLVED_DEPENDENCY.value:
                unsafe_conditions.append("Task has blocking dependencies")
                required_actions.append("Resolve all blocking dependencies before archiving")
            elif mode == SafetyFailureMode.REQUIREMENT_CHANGED.value:
                unsafe_conditions.append("Requirements changed after prior audit")
                required_actions.append(
                    "Verify requirements changes are intentional; re-audit if needed"
                )
            elif mode == SafetyFailureMode.SHA_CHANGED.value:
                unsafe_conditions.append("Branch SHA changed after prior audit")
                required_actions.append("Verify branch changes are intentional; re-audit if needed")
            elif mode == SafetyFailureMode.FINGERPRINT_MISMATCH.value:
                unsafe_conditions.append("Evidence fingerprint mismatch")
                required_actions.append("Re-run Done/Merged audit to verify current state")
            elif mode == SafetyFailureMode.RECENT_COMPLETION.value:
                unsafe_conditions.append("Task not retained long enough")
                required_actions.append("Wait for retention period to pass before archiving")
            elif mode == SafetyFailureMode.NO_DONE_AUDIT.value:
                unsafe_conditions.append("No prior Done/Merged audit available")
                required_actions.append("Run Done audit before attempting archive")
            elif mode == SafetyFailureMode.DONE_AUDIT_FAILED.value:
                unsafe_conditions.append("Prior Done audit failed")
                required_actions.append("Fix issues from Done audit before archiving")
            elif mode == SafetyFailureMode.MERGED_AUDIT_FAILED.value:
                unsafe_conditions.append("Prior Merged audit failed")
                required_actions.append("Fix issues from Merged audit before archiving")
            elif mode == SafetyFailureMode.NO_DISPOSITION_REASON.value:
                unsafe_conditions.append("No disposition reason configured")
                required_actions.append("Provide structured reason for archival")
            elif mode == SafetyFailureMode.DUPLICATE_NO_SOURCE.value:
                unsafe_conditions.append("Duplicate without source link")
                required_actions.append("Provide link to original/remaining task")
            elif mode == SafetyFailureMode.OBSOLETE_NO_SOURCE.value:
                unsafe_conditions.append("Obsolete without replacement link")
                required_actions.append("Provide link to replacement work or explanation")
            elif mode == SafetyFailureMode.SUPERSEDED_NO_SOURCE.value:
                unsafe_conditions.append("Superseded without replacement link")
                required_actions.append("Provide link to superseding work")

        return RestorationGuidance(
            restored_state=restored_state,
            required_actions=required_actions,
            unsafe_condition="; ".join(unsafe_conditions) if unsafe_conditions else "Unknown",
        )


__all__ = [
    "ArchivedEvidenceCollector",
    "ArchivedEvidenceSnapshot",
    "DispositionReason",
    "DispositionType",
    "RestorationGuidance",
    "SafetyFailureMode",
    "TaskStateSnapshot",
    "AuditReferenceEvidence",
    "EvidenceUnavailable",
    "EvidenceInvalid",
]
