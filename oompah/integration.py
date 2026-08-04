"""Durable metadata for a completed worker's integration handoff."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping


INTEGRATION_RECORD_VERSION = 2
INTEGRATION_STATES = frozenset(
    {
        "working",
        "ready",
        "queued",
        "integrating",
        "blocked",
        "integrated",
        "needs_human",
    }
)


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def expected_submission_branch(issue: object) -> str:
    """Return the branch a task is allowed to submit from.

    Dispatch persists ``work_branch`` before handing a task its worktree.
    Older tracker records may only have ``branch_name``; native tasks created
    before that metadata existed use their sanitized identifier, which is also
    ProjectStore's default branch name.
    """

    for attribute in ("work_branch", "branch_name"):
        value = str(getattr(issue, attribute, "") or "").strip()
        if value:
            return value
    identifier = str(getattr(issue, "identifier", "") or "").strip()
    if not identifier:
        raise ValueError("task identifier is required to validate task_branch")
    return re.sub(r"[^A-Za-z0-9._-]+", "_", identifier).strip("._-") or "unnamed"


def validate_submission_branch(issue: object, task_branch: object) -> str:
    """Reject evidence captured from a checkout other than the task's branch."""

    submitted = str(task_branch or "").strip()
    if not submitted:
        raise ValueError("task_branch is required for task submission")
    expected = expected_submission_branch(issue)
    if submitted != expected:
        raise ValueError(
            f"submitted branch {submitted!r} does not match the task's expected "
            f"work branch {expected!r}; submit from the assigned task checkout"
        )
    return submitted


def is_direct_epic_maintenance_issue(issue: object) -> bool:
    """Return whether an issue is the auto-filed shared-epic rebase helper.

    These tasks intentionally publish the parent epic branch from their own
    assigned checkout.  The title/parent shape is the durable classification
    available to submission callers, and keeps ordinary epic children on the
    normal integration queue.
    """

    parent = str(getattr(issue, "parent_id", None) or "").strip()
    title = str(getattr(issue, "title", None) or "").strip().lower()
    if not parent or not title.startswith("rebase "):
        return False
    epic_branch = "epic-" + re.sub(r"[^A-Za-z0-9._-]+", "_", parent).strip("._-")
    return bool(epic_branch) and epic_branch.lower() in title


def _compute_evidence_fingerprint(
    old_base_sha: str,
    old_head_sha: str,
    new_base_sha: str,
    new_head_sha: str,
    target_epic_branch: str,
    rebase_task_id: str,
    created_at_utc: str,
) -> str:
    """Compute SHA256 fingerprint for canonical landing evidence.
    
    Fingerprint validates evidence integrity against tampering and provides
    cryptographic proof of the exact mapping. All parameters must be
    canonicalized (lowercase SHAs, stripped strings).
    """
    content = f"{old_base_sha}|{old_head_sha}|{new_base_sha}|{new_head_sha}|{target_epic_branch}|{rebase_task_id}|{created_at_utc}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CanonicalLandingEvidence:
    """Service-authored cryptographic evidence of conflict-resolved child landing.
    
    Persisted during direct epic maintenance completion to prove that a child's
    commits were validly rebased with conflict resolution into canonical epic
    commits. This evidence is fail-closed: missing, stale, partial, or forged
    evidence blocks landing validation until human recovery.
    
    All fields are immutable (frozen=True) and must be set at creation time.
    Evidence is only created by oompah service, never loaded from untrusted
    sources (e.g., human comments, user input, or tracker metadata edits).
    
    Attributes:
        old_base_sha: Original child base commit SHA before rebase (40-char hex).
        old_head_sha: Original child head commit SHA before rebase (40-char hex).
        new_base_sha: New base commit in canonical epic after rebase (40-char hex).
        new_head_sha: New head commit in canonical epic after rebase (40-char hex).
        target_epic_branch: Epic branch name this evidence is valid for (e.g., "epic-EPIC-123").
            Prevents cross-epic injection attacks; any mismatch blocks landing.
        rebase_task_id: Oompah task ID that authorized this rebase evidence (e.g., "OOMPAH-456").
            Used for authorization audit trail and historical repair whitelist.
        created_at_utc: ISO 8601 UTC timestamp when oompah created this evidence.
            Evidence older than MAX_EVIDENCE_AGE_DAYS is invalidated (fail-closed).
        evidence_fingerprint: SHA256 hash of all parameters above, excluding this field.
            Detects tampering; fingerprint mismatch blocks landing and invalidates evidence.
    """
    
    old_base_sha: str
    old_head_sha: str
    new_base_sha: str
    new_head_sha: str
    target_epic_branch: str
    rebase_task_id: str
    created_at_utc: str
    evidence_fingerprint: str

    def __post_init__(self) -> None:
        """Validate all fields and verify fingerprint on instantiation.
        
        This is called automatically by dataclass after __init__.
        Fail-closed: any validation failure raises ValueError.
        """
        # Validate SHAs are 40-character hex strings
        for sha, name in [
            (self.old_base_sha, "old_base_sha"),
            (self.old_head_sha, "old_head_sha"),
            (self.new_base_sha, "new_base_sha"),
            (self.new_head_sha, "new_head_sha"),
        ]:
            if not _is_valid_git_sha(sha):
                raise ValueError(
                    f"invalid git SHA for {name}: {sha!r} "
                    "(must be 40-character hexadecimal)"
                )
        
        # Validate string fields are non-empty after stripping
        for text, name in [
            (self.target_epic_branch, "target_epic_branch"),
            (self.rebase_task_id, "rebase_task_id"),
            (self.created_at_utc, "created_at_utc"),
        ]:
            if not str(text or "").strip():
                raise ValueError(f"{name} is required and cannot be empty")
        
        # Validate fingerprint format (64-character hex from SHA256)
        if not _is_valid_git_sha(self.evidence_fingerprint, bits=256):
            raise ValueError(
                f"invalid fingerprint: {self.evidence_fingerprint!r} "
                "(must be 64-character hexadecimal)"
            )
        
        # Verify fingerprint matches computed value (critical: detect tampering)
        expected_fp = _compute_evidence_fingerprint(
            self.old_base_sha,
            self.old_head_sha,
            self.new_base_sha,
            self.new_head_sha,
            self.target_epic_branch,
            self.rebase_task_id,
            self.created_at_utc,
        )
        if self.evidence_fingerprint != expected_fp:
            raise ValueError(
                f"evidence fingerprint mismatch: {self.evidence_fingerprint!r} "
                f"!= {expected_fp!r} (evidence is corrupted or tampered)"
            )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CanonicalLandingEvidence":
        """Parse stored evidence while rejecting malformed data (fail-closed).
        
        This is the only public way to load evidence from storage.
        Any parsing error raises ValueError; no partial/degraded loading.
        """
        required_fields = {
            "old_base_sha",
            "old_head_sha",
            "new_base_sha",
            "new_head_sha",
            "target_epic_branch",
            "rebase_task_id",
            "created_at_utc",
            "evidence_fingerprint",
        }
        if not isinstance(value, Mapping):
            raise ValueError(
                "evidence must be a mapping (dict), not {!r}".format(type(value))
            )
        
        missing = required_fields - set(value.keys())
        if missing:
            raise ValueError(
                f"evidence missing required fields: {', '.join(sorted(missing))}"
            )
        
        return cls(
            old_base_sha=str(value.get("old_base_sha") or "").strip().lower(),
            old_head_sha=str(value.get("old_head_sha") or "").strip().lower(),
            new_base_sha=str(value.get("new_base_sha") or "").strip().lower(),
            new_head_sha=str(value.get("new_head_sha") or "").strip().lower(),
            target_epic_branch=str(value.get("target_epic_branch") or "").strip(),
            rebase_task_id=str(value.get("rebase_task_id") or "").strip(),
            created_at_utc=str(value.get("created_at_utc") or "").strip(),
            evidence_fingerprint=str(
                value.get("evidence_fingerprint") or ""
            ).strip().lower(),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the stable JSON/YAML representation for storage."""
        return {
            "old_base_sha": self.old_base_sha,
            "old_head_sha": self.old_head_sha,
            "new_base_sha": self.new_base_sha,
            "new_head_sha": self.new_head_sha,
            "target_epic_branch": self.target_epic_branch,
            "rebase_task_id": self.rebase_task_id,
            "created_at_utc": self.created_at_utc,
            "evidence_fingerprint": self.evidence_fingerprint,
        }

    def is_valid_for_epic(self, current_epic_branch: str) -> bool:
        """Return True if evidence is valid for the given epic branch.
        
        Fail-closed: any mismatch returns False (blocks landing).
        Epic branch name changes invalidate evidence (prevents drift attacks).
        """
        if not current_epic_branch:
            return False
        return self.target_epic_branch == current_epic_branch

    def is_evidence_fresh(self, max_age_hours: int = 24) -> bool:
        """Return True if evidence age is within max_age_hours (fail-closed).
        
        Args:
            max_age_hours: Maximum age in hours before evidence is invalidated.
                Defaults to 24 hours; should be small to prevent stale evidence
                attacks.
        
        Returns:
            False if evidence is too old or timestamp is invalid (fail-closed).
        """
        try:
            created = datetime.fromisoformat(self.created_at_utc.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            age = (now - created).total_seconds() / 3600  # hours
            return age >= 0 and age <= max_age_hours
        except (ValueError, TypeError):
            return False


def _is_valid_git_sha(sha: str, bits: int = 160) -> bool:
    """Return True if sha is a valid git commit hash.
    
    Args:
        sha: The string to validate.
        bits: Hash bit length (160 for SHA1 -> 40 hex chars, 256 for SHA256 -> 64 hex chars).
    
    Returns:
        True if sha is the correct length of valid hex characters.
    """
    expected_len = bits // 4  # 4 bits per hex character
    try:
        text = str(sha or "").strip().lower()
        if len(text) != expected_len:
            return False
        return all(c in "0123456789abcdef" for c in text)
    except (TypeError, AttributeError):
        return False


def parse_canonical_landing_evidence(
    value: object,
) -> CanonicalLandingEvidence | None:
    """Parse landing evidence, returning None for invalid/missing data (fail-closed).
    
    This safe wrapper prevents malformed evidence from crashing callers.
    Callers should treat None as "no evidence" and maintain fail-closed behavior.
    """
    if not isinstance(value, Mapping):
        return None
    try:
        return CanonicalLandingEvidence.from_dict(value)
    except ValueError:
        return None


@dataclass(frozen=True)
class IntegrationRecord:
    """Versioned tracker record describing one task's integration state."""

    state: str
    task_branch: str | None = None
    base_branch: str | None = None
    base_sha: str | None = None
    head_sha: str | None = None
    integrated_sha: str | None = None
    attempts: int = 0
    submitted_at: str | None = None
    updated_at: str | None = None
    last_error: str | None = None
    dependency_heads: dict[str, str] = field(default_factory=dict)
    # Timestamp (ISO 8601) when this repair becomes eligible for retry after
    # a recoverable infrastructure failure. None means no active backoff.
    backoff_until: str | None = None
    # Classification of the last failure type for repair conflicts:
    # "conflict", "auth_failed", "rate_limited", "overloaded", "timeout",
    # "provider_unavailable", "missing_credentials", or None.
    repair_failure_reason: str | None = None
    # Canonical landing evidence for conflict-resolved epic child rebases.
    # Only set by oompah service in complete_direct_epic_maintenance_submission.
    # Must pass cryptographic fingerprint validation and freshness checks.
    # None means no evidence available; fail-closed validation treats this as
    # a missing landing proof until other validators pass.
    canonical_landing_evidence: dict[str, Any] | None = None
    version: int = INTEGRATION_RECORD_VERSION

    def __post_init__(self) -> None:
        # Version should always match current version (from_dict migrates old versions)
        if self.version != INTEGRATION_RECORD_VERSION:
            raise ValueError(
                f"unsupported integration record version: {self.version} "
                f"(expected: {INTEGRATION_RECORD_VERSION})"
            )
        if self.state not in INTEGRATION_STATES:
            raise ValueError(f"unsupported integration state: {self.state!r}")
        if self.attempts < 0:
            raise ValueError("integration attempts cannot be negative")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "IntegrationRecord":
        """Parse persisted metadata while ignoring unknown future fields."""

        raw_heads = value.get("dependency_heads")
        dependency_heads = (
            {
                str(identifier): str(sha)
                for identifier, sha in raw_heads.items()
                if str(identifier).strip() and str(sha).strip()
            }
            if isinstance(raw_heads, Mapping)
            else {}
        )
        try:
            version = int(value.get("version", INTEGRATION_RECORD_VERSION))
            attempts = int(value.get("attempts", 0) or 0)
        except (TypeError, ValueError) as exc:
            raise ValueError("integration version and attempts must be integers") from exc
        
        # Validate version is in supported range (1-current)
        if version < 1 or version > INTEGRATION_RECORD_VERSION:
            raise ValueError(
                f"unsupported integration record version: {version} "
                f"(supported: 1-{INTEGRATION_RECORD_VERSION})"
            )
        
        # Parse canonical landing evidence (fail-closed: invalid evidence = None)
        raw_evidence = value.get("canonical_landing_evidence")
        landing_evidence = None
        if isinstance(raw_evidence, Mapping):
            parsed = parse_canonical_landing_evidence(raw_evidence)
            # Only include evidence if it parsed successfully (fail-closed)
            if parsed is not None:
                landing_evidence = parsed.to_dict()
        
        # Always store as current version when loading (migration v1 -> v2)
        return cls(
            version=INTEGRATION_RECORD_VERSION,
            state=str(value.get("state") or "").strip().lower(),
            task_branch=_optional_text(value.get("task_branch")),
            base_branch=_optional_text(value.get("base_branch")),
            base_sha=_optional_text(value.get("base_sha")),
            head_sha=_optional_text(value.get("head_sha")),
            integrated_sha=_optional_text(value.get("integrated_sha")),
            attempts=attempts,
            submitted_at=_optional_text(value.get("submitted_at")),
            updated_at=_optional_text(value.get("updated_at")),
            last_error=_optional_text(value.get("last_error")),
            dependency_heads=dependency_heads,
            backoff_until=_optional_text(value.get("backoff_until")),
            repair_failure_reason=_optional_text(value.get("repair_failure_reason")),
            canonical_landing_evidence=landing_evidence,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the stable JSON/YAML representation stored by trackers."""

        result: dict[str, Any] = {
            "version": self.version,
            "state": self.state,
            "attempts": self.attempts,
        }
        for key in (
            "task_branch",
            "base_branch",
            "base_sha",
            "head_sha",
            "integrated_sha",
            "submitted_at",
            "updated_at",
            "last_error",
            "backoff_until",
            "repair_failure_reason",
        ):
            value = getattr(self, key)
            if value is not None:
                result[key] = value
        if self.dependency_heads:
            result["dependency_heads"] = dict(self.dependency_heads)
        if self.canonical_landing_evidence is not None:
            result["canonical_landing_evidence"] = dict(self.canonical_landing_evidence)
        return result


def parse_integration_record(value: object) -> IntegrationRecord | None:
    """Return a valid record, or ``None`` for missing/malformed metadata."""

    if not isinstance(value, Mapping):
        return None
    try:
        return IntegrationRecord.from_dict(value)
    except ValueError:
        return None


def validate_task_branch_authority(issue: object, task_branch: str) -> None:
    """Reject submission evidence from a branch owned by another task."""

    canonical_branch = _optional_text(
        getattr(issue, "work_branch", None)
        or getattr(issue, "branch_name", None)
    )
    if canonical_branch is None:
        existing = getattr(issue, "integration", None)
        canonical_branch = _optional_text(
            getattr(existing, "task_branch", None)
        )
    if canonical_branch is not None and task_branch != canonical_branch:
        raise ValueError(
            "task_branch does not match the task's canonical work branch"
        )


def classify_conflict_repair_failure(error_message: str) -> str | None:
    """Classify a conflict repair worker failure as recoverable or real.

    Returns one of:
    - "conflict": real merge conflict that needs human resolution
    - "auth_failed": authentication/authorization failure (401, 403)
    - "rate_limited": rate limit exceeded (429)
    - "timeout": operation timeout
    - "overloaded": provider overloaded (503, 504, 529)
    - "provider_unavailable": provider not available or unreachable
    - "missing_credentials": missing auth credentials
    - "invalid_model": invalid model configuration
    - None: unclassifiable failure

    Recoverable failures (everything except "conflict") should trigger
    backoff and retry instead of permanent blocking.
    """
    if not error_message:
        return None

    msg_lower = error_message.lower()

    # Real conflict indicators (check first, before anything else)
    if any(
        indicator in msg_lower
        for indicator in (
            "merge conflict",
            "automatic merge failed",
            "cannot merge",
            "conflict markers",
            "resolve the conflicts",
            "rebase conflict",
        )
    ):
        return "conflict"

    # Infrastructure/auth failures (recoverable)
    if any(
        indicator in msg_lower
        for indicator in (
            "unauthorized",
            "authentication failed",
            "auth failed",
            "401",
            "403",
        )
    ):
        return "auth_failed"

    if any(
        indicator in msg_lower
        for indicator in (
            "rate limit",
            "rate_limited",
            "429",
            "too many requests",
        )
    ):
        return "rate_limited"

    # Overload indicators (check before timeout because 503, 504, 529 are also error codes)
    if any(
        indicator in msg_lower
        for indicator in (
            "overloaded",
            "503",
            "504",
            "529",
            "service unavailable",
        )
    ):
        return "overloaded"

    # Timeout (after overload to not catch 504)
    if any(
        indicator in msg_lower
        for indicator in (
            "timed out",
            "timeout",
            "deadline exceeded",
            "time limit",
        )
    ):
        return "timeout"

    if any(
        indicator in msg_lower
        for indicator in (
            "not available",
            "unavailable",
            "connection refused",
            "cannot connect",
            "no such host",
            "500",
        )
    ):
        return "provider_unavailable"

    if any(
        indicator in msg_lower
        for indicator in (
            "missing credential",
            "missing credentials",
            "api key",
            "api_key",
            "no credentials",
        )
    ):
        return "missing_credentials"

    if any(
        indicator in msg_lower
        for indicator in (
            "invalid model",
            "model not found",
            "unknown model",
            "unsupported model",
        )
    ):
        return "invalid_model"

    return None
