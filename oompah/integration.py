"""Durable metadata for a completed worker's integration handoff."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field, replace
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
INTEGRATION_MODES = frozenset({"queue", "standalone"})

# ``working`` describes an implementation checkout that has not submitted a
# generation yet.  Every other record state names evidence that has crossed
# the submission boundary and therefore owns its branch identity until a
# later accepted submission replaces it.
ACCEPTED_SUBMISSION_STATES = INTEGRATION_STATES - {"working"}
REVIEW_GENERATION_REQUEUE_WAIT_REASON = "review_generation_requeue"
_EXACT_GIT_SHA_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")


def task_submit_required_message(identifier: object) -> str:
    """Return the common worker diagnostic for submission-owned lifecycle states."""

    task_identifier = str(identifier or "").strip() or "<task>"
    return (
        "spawned workers must use `oompah task submit "
        f'{task_identifier} --summary "..."` so committed and pushed git '
        "evidence is validated before completion"
    )


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def accepted_submission_branch(issue: object) -> str | None:
    """Return the immutable branch named by accepted generation evidence.

    ``Issue.work_branch`` is a tracker projection and can be missing or stale
    after a crash or an older-server submission.  A non-working integration
    record with both a branch and an exact head is the durable authority; a
    partial record is deliberately ignored so unsubmitted work cannot capture
    a branch merely by writing metadata.
    """

    existing = getattr(issue, "integration", None)
    if existing is None:
        return None
    state = str(getattr(existing, "state", "") or "").strip().lower()
    branch = _optional_text(getattr(existing, "task_branch", None))
    head_sha = _optional_text(getattr(existing, "head_sha", None))
    if state not in ACCEPTED_SUBMISSION_STATES or not branch or not head_sha:
        return None
    return branch


def assigned_work_branch(issue: object) -> str | None:
    """Return persisted branch authority for accepted or active work.

    Accepted evidence wins over the mutable tracker projection.  A ``working``
    record is also authoritative for restart of an already-allocated checkout,
    but is never treated as an accepted submission by
    :func:`accepted_submission_branch`.
    """

    accepted = accepted_submission_branch(issue)
    if accepted:
        return accepted
    existing = getattr(issue, "integration", None)
    if (
        existing is not None
        and str(getattr(existing, "state", "") or "").strip().lower()
        == "working"
    ):
        branch = _optional_text(getattr(existing, "task_branch", None))
        if branch:
            return branch
    return None


def expected_submission_branch(issue: object) -> str:
    """Return the branch a task is allowed to submit from.

    Dispatch persists ``work_branch`` before handing a task its worktree.
    Older tracker records may only have ``branch_name``; native tasks created
    before that metadata existed use their sanitized identifier, which is also
    ProjectStore's default branch name.
    """

    assigned = assigned_work_branch(issue)
    if assigned:
        return assigned
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
    assigned checkout.  Current helpers carry project-scoped creation metadata
    plus exact server-issued rebase target and authority records.  Those
    records support persisted non-convention branch names without widening
    this privileged classification to arbitrary title-shaped epic children.
    Legacy helpers without any explicit identity metadata retain the bounded
    canonical-title fallback.
    """

    def field(name: str) -> object:
        if isinstance(issue, Mapping):
            return issue.get(name)
        return getattr(issue, name, None)

    parent = str(field("parent_id") or "").strip()
    identifier = str(field("identifier") or field("id") or "").strip()
    observed_project_id = str(field("project_id") or "").strip()
    creation = field("create_once")
    target = field("epic_rebase_target")
    authority = field("epic_rebase_authority")
    explicit = any(value is not None for value in (creation, target, authority))
    if explicit:
        if not all(
            isinstance(value, Mapping) for value in (creation, target, authority)
        ):
            return False
        assert isinstance(creation, Mapping)
        assert isinstance(target, Mapping)
        assert isinstance(authority, Mapping)

        creation_project_id = str(creation.get("project_id") or "").strip()
        project_id = observed_project_id or creation_project_id

        def exact_version(value: Mapping[str, object]) -> bool:
            version = value.get("version")
            return (
                isinstance(version, int)
                and not isinstance(version, bool)
                and version == 1
            )

        epic_branch = str(target.get("epic_branch") or "").strip()
        target_branch = str(target.get("target_branch") or "").strip()
        generation = str(authority.get("generation") or "").strip().lower()
        epic_head = str(authority.get("epic_head") or "").strip().lower()
        target_head = str(authority.get("target_head") or "").strip().lower()
        marker = str(creation.get("creation_marker") or "").strip()
        if not (
            parent
            and identifier
            and project_id
            and creation_project_id == project_id
            and (
                not observed_project_id
                or observed_project_id == creation_project_id
            )
            and exact_version(creation)
            and exact_version(target)
            and exact_version(authority)
            and creation.get("operation_kind") == "epic_rebase_helper"
            and re.fullmatch(r"[0-9a-f]{64}", generation)
            and marker
            == "oompah-epic-rebase-reservation-v1:"
            + hashlib.sha256(
                "\0".join((project_id, parent, generation)).encode("utf-8")
            ).hexdigest()
            and authority.get("task_id") == identifier
            and target.get("epic_identifier") == parent
            and authority.get("epic_identifier") == parent
            and epic_branch
            and authority.get("epic_branch") == epic_branch
            and target_branch
            and authority.get("target_branch") == target_branch
            and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", epic_head)
            and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", target_head)
            and target.get("resolution")
            in {"authoritative_parent", "confirmed_top_level"}
        ):
            return False
        work_branch = str(field("work_branch") or "").strip()
        configured_target = str(field("target_branch") or "").strip()
        return bool(
            (not work_branch or work_branch == epic_branch)
            and (not configured_target or configured_target == target_branch)
        )

    title = str(field("title") or "").strip().lower()
    if not parent or not title.startswith("rebase "):
        return False
    epic_branch = "epic-" + re.sub(r"[^A-Za-z0-9._-]+", "_", parent).strip("._-")
    return bool(epic_branch) and epic_branch.lower() in title


def direct_epic_maintenance_handoff_ready(
    issue: object,
    integration: object | None = None,
) -> bool:
    """Return whether exact direct-maintenance evidence may request audit.

    The boolean proof is necessary but deliberately insufficient on its own.
    Bind it to the service-classified helper, its canonical parent branch, and
    one exact integrated revision so corrupt or ordinary task metadata cannot
    enter the privileged Open-to-audit recovery path.
    """

    if not is_direct_epic_maintenance_issue(issue):
        return False

    def field(subject: object, name: str) -> object:
        if isinstance(subject, Mapping):
            return subject.get(name)
        return getattr(subject, name, None)

    parent = str(field(issue, "parent_id") or "").strip()
    explicit_target = field(issue, "epic_rebase_target")
    if isinstance(explicit_target, Mapping):
        epic_branch = str(explicit_target.get("epic_branch") or "").strip()
    else:
        epic_branch = "epic-" + re.sub(
            r"[^A-Za-z0-9._-]+", "_", parent
        ).strip("._-")
    record = integration if integration is not None else field(issue, "integration")
    if record is None:
        return False
    state = str(field(record, "state") or "").strip().lower()
    mode = str(field(record, "mode") or "").strip().lower()
    task_branch = str(field(record, "task_branch") or "").strip()
    base_branch = str(field(record, "base_branch") or "").strip()
    head = str(field(record, "head_sha") or "").strip().lower()
    integrated = str(field(record, "integrated_sha") or "").strip().lower()
    proof = field(record, "maintenance_publication_proven") is True
    if not (
        state == "integrated"
        and mode == "queue"
        and proof
        and task_branch == epic_branch
        and base_branch == epic_branch
        and head == integrated
        and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", head)
    ):
        return False
    issue_expectations = [("work_branch", task_branch), ("head_sha", head)]
    if isinstance(explicit_target, Mapping):
        issue_expectations.append(
            (
                "target_branch",
                str(explicit_target.get("target_branch") or "").strip(),
            )
        )
    # A legacy helper's task target remains the branch the epic was rebased
    # onto (often ``main``), while its completed integration record is
    # intentionally rewritten to describe the authoritative epic branch.
    # The canonical-title classifier plus parent/work-branch/exact-head proof
    # provides the legacy boundary; comparing those two different targets
    # would make the first durable checkpoint non-idempotent.
    for issue_field, expected in issue_expectations:
        observed = str(field(issue, issue_field) or "").strip()
        if observed and observed.lower() != expected.lower():
            return False
    return True


def direct_epic_maintenance_completion_ready(
    issue: object,
    integration: object | None = None,
) -> bool:
    """Return whether an exact published helper still needs completion.

    A direct rebase submission first persists a ``ready`` record whose task
    branch is the authoritative epic branch and whose base is the recorded
    immediate target.  Unlike an ordinary queue submission, that published
    head must be reconciled by the dedicated maintenance completion primitive;
    it must never be interpreted as a child source awaiting a second landing.
    """

    if not is_direct_epic_maintenance_issue(issue):
        return False

    def field(subject: object, name: str) -> object:
        if isinstance(subject, Mapping):
            return subject.get(name)
        return getattr(subject, name, None)

    target = field(issue, "epic_rebase_target")
    record = integration if integration is not None else field(issue, "integration")
    if record is None:
        return False
    if isinstance(target, Mapping):
        epic_branch = str(target.get("epic_branch") or "").strip()
        target_branch = str(target.get("target_branch") or "").strip()
    else:
        parent = str(field(issue, "parent_id") or "").strip()
        epic_branch = "epic-" + re.sub(
            r"[^A-Za-z0-9._-]+", "_", parent
        ).strip("._-")
        target_branch = str(field(issue, "target_branch") or "").strip()
    task_branch = str(field(record, "task_branch") or "").strip()
    base_branch = str(field(record, "base_branch") or "").strip()
    head = str(field(record, "head_sha") or "").strip().lower()
    integrated = str(field(record, "integrated_sha") or "").strip().lower()
    return bool(
        str(field(record, "state") or "").strip().lower() == "ready"
        and str(field(record, "mode") or "").strip().lower() == "queue"
        and field(record, "maintenance_publication_proven") is not True
        and epic_branch
        and target_branch
        and task_branch == epic_branch
        and base_branch == target_branch
        and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", head)
        and not integrated
    )


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


def _compute_child_landing_fingerprint(
    project_id: str,
    epic_id: str,
    child_id: str,
    base_sha: str,
    source_sha: str,
    target_base_sha: str,
    target_sha: str,
    generation: str,
    created_at_utc: str,
) -> str:
    """Return the integrity digest for one direct-rebase child mapping."""

    content = "|".join(
        (
            project_id,
            epic_id,
            child_id,
            base_sha,
            source_sha,
            target_base_sha,
            target_sha,
            generation,
            created_at_utc,
        )
    )
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CanonicalChildLandingEvidence:
    """Service-authored evidence mapping one original child range to a rebase.

    A direct epic rebase changes commit identities without changing the child
    task identity.  This record preserves both ends of that mapping instead of
    rewriting the child's branch or replacing its original integration SHAs.
    The generation is fenced by the orchestrator's durable per-epic generation
    ledger, so a mapping from an older direct rebase cannot authorize a newer
    rollup accidentally.
    """

    project_id: str
    epic_id: str
    child_id: str
    base_sha: str
    source_sha: str
    target_base_sha: str
    target_sha: str
    generation: str
    created_at_utc: str
    evidence_fingerprint: str

    def __post_init__(self) -> None:
        for sha, name in (
            (self.base_sha, "base_sha"),
            (self.source_sha, "source_sha"),
            (self.target_base_sha, "target_base_sha"),
            (self.target_sha, "target_sha"),
        ):
            if not _is_valid_git_sha(sha):
                raise ValueError(
                    f"invalid git SHA for {name}: {sha!r} "
                    "(must be 40-character hexadecimal)"
                )
        for value, name in (
            (self.project_id, "project_id"),
            (self.epic_id, "epic_id"),
            (self.child_id, "child_id"),
            (self.generation, "generation"),
            (self.created_at_utc, "created_at_utc"),
        ):
            if not str(value or "").strip():
                raise ValueError(f"{name} is required and cannot be empty")
        if not _is_valid_git_sha(self.evidence_fingerprint, bits=256):
            raise ValueError(
                "invalid child landing evidence fingerprint "
                "(must be 64-character hexadecimal)"
            )
        expected = _compute_child_landing_fingerprint(
            str(self.project_id).strip(),
            str(self.epic_id).strip(),
            str(self.child_id).strip(),
            str(self.base_sha).strip().lower(),
            str(self.source_sha).strip().lower(),
            str(self.target_base_sha).strip().lower(),
            str(self.target_sha).strip().lower(),
            str(self.generation).strip(),
            str(self.created_at_utc).strip(),
        )
        if str(self.evidence_fingerprint).strip().lower() != expected:
            raise ValueError("child landing evidence fingerprint mismatch")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CanonicalChildLandingEvidence":
        if not isinstance(value, Mapping):
            raise ValueError("child landing evidence must be a mapping")

        def get(*keys: str) -> object:
            for key in keys:
                if key in value:
                    return value[key]
            return None

        required = {
            "project_id": get("project_id"),
            "epic_id": get("epic_id", "epic"),
            "child_id": get("child_id", "child"),
            "base_sha": get("base_sha", "base"),
            "source_sha": get("source_sha", "source"),
            "target_base_sha": get("target_base_sha"),
            "target_sha": get("target_sha", "target"),
            "generation": get("generation"),
            "created_at_utc": get("created_at_utc"),
            "evidence_fingerprint": get("evidence_fingerprint"),
        }
        if any(item is None for item in required.values()):
            missing = [key for key, item in required.items() if item is None]
            raise ValueError(
                "child landing evidence missing required fields: "
                + ", ".join(missing)
            )
        return cls(
            project_id=str(required["project_id"] or "").strip(),
            epic_id=str(required["epic_id"] or "").strip(),
            child_id=str(required["child_id"] or "").strip(),
            base_sha=str(required["base_sha"] or "").strip().lower(),
            source_sha=str(required["source_sha"] or "").strip().lower(),
            target_base_sha=str(required["target_base_sha"] or "").strip().lower(),
            target_sha=str(required["target_sha"] or "").strip().lower(),
            generation=str(required["generation"] or "").strip(),
            created_at_utc=str(required["created_at_utc"] or "").strip(),
            evidence_fingerprint=str(
                required["evidence_fingerprint"] or ""
            ).strip().lower(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "epic_id": self.epic_id,
            "child_id": self.child_id,
            "base_sha": self.base_sha,
            "source_sha": self.source_sha,
            "target_base_sha": self.target_base_sha,
            "target_sha": self.target_sha,
            "generation": self.generation,
            "created_at_utc": self.created_at_utc,
            "evidence_fingerprint": self.evidence_fingerprint,
        }

    def is_evidence_fresh(self, max_age_hours: int = 24) -> bool:
        try:
            created = datetime.fromisoformat(
                self.created_at_utc.replace("Z", "+00:00")
            )
            age = (datetime.now(timezone.utc) - created).total_seconds() / 3600
            return 0 <= age <= max_age_hours
        except (TypeError, ValueError):
            return False


def parse_canonical_child_landing_evidence(
    value: object,
) -> CanonicalChildLandingEvidence | None:
    """Parse child mapping evidence without allowing partial records through."""

    if not isinstance(value, Mapping):
        return None
    try:
        return CanonicalChildLandingEvidence.from_dict(value)
    except (TypeError, ValueError):
        return None


# Whitelist of known Oompah-authorized task IDs for which historical repair evidence
# can be loaded without trusting arbitrary human comments. This bounded list:
# - Is maintained by Oompah maintainers only (code review required)
# - Never trusts user-provided task IDs (must be exact match from whitelist)
# - Prevents social engineering to create backdoor evidence paths
# - Enables recovery from documented past cases (e.g., EXOCOMP-130)
#
# Each entry includes: task_id, old_base_sha, old_head_sha, new_base_sha, new_head_sha,
# target_epic_branch, created_at_utc (from authorized recovery process)
_BOUNDED_HISTORICAL_REPAIR_EVIDENCE: dict[str, dict[str, str]] = {
    # Future: Add specific known recovery cases here as authorized by maintainers.
    # Format: "OOMPAH-NNN": { "old_base_sha": "...", ... }
    # These must come from verified authorized epic maintenance completion,
    # not from human comments or external sources.
}


def load_bounded_historical_repair_evidence(
    task_id: str,
) -> CanonicalLandingEvidence | None:
    """Load repair evidence only for known authorized historical task IDs (fail-closed).

    This provides recovery for documented past cases without creating a security
    hole for arbitrary evidence injection via comments. The whitelist is:
    - Maintained in code (requires review for changes)
    - Validated against exact task ID (no pattern matching)
    - Only loaded for tasks in the whitelist (all others return None)
    - Never trusts human comments or arbitrary input

    Args:
        task_id: The task identifier to potentially load evidence for.

    Returns:
        CanonicalLandingEvidence if the task_id is in the whitelist and
        evidence is valid. None for unknown tasks or invalid evidence.
    """
    task_id_str = str(task_id or "").strip()
    if not task_id_str or task_id_str not in _BOUNDED_HISTORICAL_REPAIR_EVIDENCE:
        return None

    evidence_dict = _BOUNDED_HISTORICAL_REPAIR_EVIDENCE[task_id_str]
    return parse_canonical_landing_evidence(evidence_dict)


@dataclass(frozen=True)
class IntegrationRecord:
    """Versioned tracker record describing one task's integration state."""

    state: str
    # Durable delivery ownership selected by the service at submission time.
    # ``standalone`` opens a review directly; ``queue`` lands through an epic
    # integration row.  Legacy records may omit it and are derived from task
    # containment by the workflow fact collector.
    mode: str | None = None
    # Set only when the service reclassifies a child after this exact parent
    # landed on its immediate target.  Parentless standalone records omit it.
    post_landed_parent_id: str | None = None
    task_branch: str | None = None
    base_branch: str | None = None
    base_sha: str | None = None
    head_sha: str | None = None
    integrated_sha: str | None = None
    # Direct epic-maintenance publication crossed its special integration
    # boundary and is ready for the terminal-audit handoff.  This must be
    # durable service-authored evidence: deriving it from an Open status or a
    # surviving checkout would recreate the OOMPAH-731 restart deadlock.
    maintenance_publication_proven: bool = False
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
    # Exact gate cancellation is scheduling evidence, not a failed test
    # result.  Keep the distinction durable so restart reconciliation cannot
    # reinterpret a deliberately withdrawn gate as a CI repair request.
    gate_outcome: str | None = None
    # Service-authored provenance copied from the validation lease tombstone.
    # This is intentionally small, string-only metadata suitable for tracker
    # projections and comments.
    gate_cancellation: dict[str, str] | None = None
    # Canonical landing evidence for conflict-resolved epic child rebases.
    # Only set by oompah service in complete_direct_epic_maintenance_submission.
    # Must pass cryptographic fingerprint validation and freshness checks.
    # None means no evidence available; fail-closed validation treats this as
    # a missing landing proof until other validators pass.
    canonical_landing_evidence: dict[str, Any] | None = None
    # A nested-epic dispatch can be waiting for exact branch ancestry without
    # owning an implementation worker.  Persist the reason and generation so
    # WorkDecision/UI projections remain truthful across restarts.
    wait_reason: str | None = None
    wait_generation: str | None = None
    required_base_missing: tuple[str, ...] = ()
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
        if self.mode is not None and self.mode not in INTEGRATION_MODES:
            raise ValueError(f"unsupported integration mode: {self.mode!r}")
        if self.post_landed_parent_id is not None and self.mode != "standalone":
            raise ValueError(
                "post-landed parent authority requires standalone delivery mode"
            )
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

        raw_cancellation = value.get("gate_cancellation")
        cancellation = (
            {
                str(key): str(item).strip()
                for key, item in raw_cancellation.items()
                if str(key).strip() and str(item).strip()
            }
            if isinstance(raw_cancellation, Mapping)
            else None
        )
        raw_missing = value.get("required_base_missing")
        required_base_missing = (
            tuple(
                str(item).strip()
                for item in raw_missing
                if str(item).strip()
            )
            if isinstance(raw_missing, (list, tuple))
            else ()
        )

        # Always store as current version when loading (migration v1 -> v2)
        return cls(
            version=INTEGRATION_RECORD_VERSION,
            state=str(value.get("state") or "").strip().lower(),
            mode=_optional_text(value.get("mode")),
            post_landed_parent_id=_optional_text(
                value.get("post_landed_parent_id")
            ),
            task_branch=_optional_text(value.get("task_branch")),
            base_branch=_optional_text(value.get("base_branch")),
            base_sha=_optional_text(value.get("base_sha")),
            head_sha=_optional_text(value.get("head_sha")),
            integrated_sha=_optional_text(value.get("integrated_sha")),
            # This field gates a lifecycle transition, so persisted strings
            # such as ``"false"`` must not become truthy evidence.
            maintenance_publication_proven=(
                value.get("maintenance_publication_proven") is True
            ),
            attempts=attempts,
            submitted_at=_optional_text(value.get("submitted_at")),
            updated_at=_optional_text(value.get("updated_at")),
            last_error=_optional_text(value.get("last_error")),
            dependency_heads=dependency_heads,
            backoff_until=_optional_text(value.get("backoff_until")),
            repair_failure_reason=_optional_text(value.get("repair_failure_reason")),
            gate_outcome=_optional_text(value.get("gate_outcome")),
            gate_cancellation=cancellation,
            canonical_landing_evidence=landing_evidence,
            wait_reason=_optional_text(value.get("wait_reason")),
            wait_generation=_optional_text(value.get("wait_generation")),
            required_base_missing=required_base_missing,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the stable JSON/YAML representation stored by trackers."""

        result: dict[str, Any] = {
            "version": self.version,
            "state": self.state,
            "attempts": self.attempts,
        }
        for key in (
            "mode",
            "post_landed_parent_id",
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
            "gate_outcome",
            "wait_reason",
            "wait_generation",
        ):
            value = getattr(self, key)
            if value is not None:
                result[key] = value
        if self.maintenance_publication_proven:
            result["maintenance_publication_proven"] = True
        if self.dependency_heads:
            result["dependency_heads"] = dict(self.dependency_heads)
        if self.canonical_landing_evidence is not None:
            result["canonical_landing_evidence"] = dict(self.canonical_landing_evidence)
        if self.gate_cancellation is not None:
            result["gate_cancellation"] = dict(self.gate_cancellation)
        if self.required_base_missing:
            result["required_base_missing"] = list(self.required_base_missing)
        return result


def review_generation_requeue_marker(
    review_id: object,
    head_sha: object,
    base_sha: object,
) -> str | None:
    """Bind one restart-safe review requeue checkpoint to its exact generation."""

    review = str(review_id or "").strip()
    head = str(head_sha or "").strip().lower()
    base = str(base_sha or "").strip().lower()
    if (
        not review
        or _EXACT_GIT_SHA_RE.fullmatch(head) is None
        or _EXACT_GIT_SHA_RE.fullmatch(base) is None
    ):
        return None
    payload = "\0".join((review, head, base))
    return "review:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def requeue_standalone_review_generation(
    integration: IntegrationRecord,
    *,
    review_id: object,
    head_sha: object,
    base_sha: object,
    updated_at: str,
) -> IntegrationRecord:
    """Replace stale standalone authority with one exact ungated generation."""

    head = str(head_sha or "").strip().lower()
    base = str(base_sha or "").strip().lower()
    marker = review_generation_requeue_marker(review_id, head, base)
    if (
        integration.mode not in {None, "standalone"}
        or marker is None
        or not str(updated_at or "").strip()
    ):
        raise ValueError("exact standalone review generation is required")
    return replace(
        integration,
        state="ready",
        mode=integration.mode or "standalone",
        base_sha=base,
        head_sha=head,
        integrated_sha=None,
        maintenance_publication_proven=False,
        attempts=0,
        updated_at=str(updated_at).strip(),
        last_error=None,
        dependency_heads={},
        backoff_until=None,
        repair_failure_reason=None,
        gate_outcome=None,
        gate_cancellation=None,
        canonical_landing_evidence=None,
        wait_reason=REVIEW_GENERATION_REQUEUE_WAIT_REASON,
        wait_generation=marker,
        required_base_missing=(),
    )


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

    canonical_branch = assigned_work_branch(issue) or _optional_text(
        getattr(issue, "work_branch", None)
        or getattr(issue, "branch_name", None)
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
