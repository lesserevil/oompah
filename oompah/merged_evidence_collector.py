"""Read-only evidence collector for Merged completion audits.

Collects authoritative evidence that a task's source branch actually landed
on the configured target branch, as distinct from tracker labels or stale
review history alone.

Evidence gathered:
- Source branch and review (PR/MR) identification
- Intended target branch from task configuration
- Reviewed source SHA (HEAD at review time)
- Merge commit / result SHA
- Target HEAD SHA
- CI status at reviewed SHA
- Commit and content containment (are all source commits reachable from target?)

Failure modes detected:
- Wrong-target merge (PR targeted a different branch than configured)
- Open review (not yet merged)
- Closed-unmerged review (rejected or abandoned)
- Failed or pending CI at reviewed SHA
- Stale branch tip (source advanced after the review was opened)
- Deleted source branch with merged-review evidence
- Stranded unique commits not reachable from target HEAD

For epic and nested-epic rollups the collector also requires child Done audit
IDs and validates that each branch in the chain landed on the target.

All operations are read-only. Missing or invalid evidence is explicitly typed
rather than guessed, ensuring auditors receive clear failure signals.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Protocol

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Re-export shared evidence markers from done_evidence_collector
# ---------------------------------------------------------------------------
from oompah.done_evidence_collector import (  # noqa: E402
    EvidenceInvalid,
    EvidenceUnavailable,
)
from oompah.scm import CIStatus, ReviewRequest, SCMProvider  # noqa: E402
from oompah.terminal_audit import EvidenceFingerprint, Verdict  # noqa: E402

MaybeEvidence = str | int | float | bool | None | dict[str, Any] | list[Any] | EvidenceUnavailable | EvidenceInvalid


# ---------------------------------------------------------------------------
# Lightweight protocol for SCM so tests can inject fakes without subclassing
# ---------------------------------------------------------------------------

class _SCMProtocol(Protocol):
    """Minimal SCM capability subset required by MergedEvidenceCollector."""

    def find_pr_for_branch(
        self, repo: str, branch: str, target_branch: str | None = None
    ) -> ReviewRequest | None:
        ...

    def get_review(self, repo: str, review_id: str) -> ReviewRequest | None:
        ...

    def get_branch_head_sha(self, repo: str, branch: str) -> str | None:
        ...

    def get_ci_status_for_sha(self, repo: str, sha: str) -> CIStatus:
        ...

    def get_pr_commits(self, repo: str, review_id: str) -> list[str]:
        ...

    def get_review_head_sha(self, repo: str, review_id: str) -> str | None:
        """Return the PR/MR head SHA at review time (not the current branch HEAD).

        This is distinct from :meth:`get_branch_head_sha` because the source
        branch may have advanced after the review was opened.  Returns None
        when unavailable.
        """
        ...


# ---------------------------------------------------------------------------
# Failure mode enumeration
# ---------------------------------------------------------------------------

class FailureMode(str, Enum):
    """Precise failure modes detected by MergedEvidenceCollector."""

    WRONG_TARGET = "wrong_target"
    OPEN_REVIEW = "open_review"
    CLOSED_UNMERGED = "closed_unmerged"
    FAILED_CI = "failed_ci"
    PENDING_CI = "pending_ci"
    STALE_BRANCH_TIP = "stale_branch_tip"
    DELETED_BRANCH_NO_EVIDENCE = "deleted_branch_no_evidence"
    STRANDED_COMMITS = "stranded_commits"
    NO_DONE_AUDIT = "no_done_audit"
    DONE_AUDIT_NOT_PASSED = "done_audit_not_passed"
    FINGERPRINT_MISMATCH = "fingerprint_mismatch"
    NO_REVIEW_FOUND = "no_review_found"
    CHILD_NOT_LANDED = "child_not_landed"
    MISSING_EVIDENCE = "missing_evidence"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ReviewEvidence:
    """Evidence about a pull/merge request associated with the source branch."""

    review_id: str
    review_state: str  # "open", "closed", "merged"
    source_branch: str
    target_branch: str
    reviewed_source_sha: str  # PR head SHA when reviewed
    merge_commit_sha: Optional[str]  # SHA of the merge commit on target
    ci_status: CIStatus
    author: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.review_id, str) or not self.review_id.strip():
            raise ValueError("ReviewEvidence.review_id must be non-empty")
        if not isinstance(self.review_state, str) or self.review_state not in ("open", "closed", "merged"):
            raise ValueError(
                f"ReviewEvidence.review_state must be open/closed/merged, got {self.review_state!r}"
            )

    @property
    def is_merged(self) -> bool:
        return self.review_state == "merged"

    @property
    def is_open(self) -> bool:
        return self.review_state == "open"


@dataclass(frozen=True)
class ContainmentEvidence:
    """Evidence of commit containment in the target branch."""

    reviewed_sha_in_target: bool
    commits_from_review: list[str]  # All commit SHAs in the reviewed PR
    stranded_commits: list[str]  # Commits not reachable from target HEAD

    def __post_init__(self) -> None:
        if not isinstance(self.reviewed_sha_in_target, bool):
            raise TypeError("ContainmentEvidence.reviewed_sha_in_target must be bool")
        if not isinstance(self.commits_from_review, list):
            raise TypeError("ContainmentEvidence.commits_from_review must be a list")
        if not isinstance(self.stranded_commits, list):
            raise TypeError("ContainmentEvidence.stranded_commits must be a list")

    @property
    def all_landed(self) -> bool:
        return self.reviewed_sha_in_target and len(self.stranded_commits) == 0


@dataclass(frozen=True)
class ChildAuditEvidence:
    """Evidence for a single child task in an epic rollup."""

    child_task_id: str
    done_audit_id: str
    source_branch: str | EvidenceUnavailable | EvidenceInvalid
    landed_on_target: bool | EvidenceUnavailable | EvidenceInvalid
    failure_modes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MergedEvidenceSnapshot:
    """Complete evidence snapshot for a Merged audit."""

    # Link to the prior Done audit
    done_audit_id: str | EvidenceUnavailable | EvidenceInvalid
    done_audit_verdict: str | EvidenceUnavailable | EvidenceInvalid  # "pass" / "fail"
    done_audit_fingerprint: EvidenceFingerprint | EvidenceUnavailable | EvidenceInvalid

    # Source branch
    source_branch: str | EvidenceUnavailable | EvidenceInvalid
    source_sha_at_review: str | EvidenceUnavailable | EvidenceInvalid
    source_sha_current: str | EvidenceUnavailable | EvidenceInvalid

    # Target branch
    intended_target_branch: str | EvidenceUnavailable | EvidenceInvalid
    target_head_sha: str | EvidenceUnavailable | EvidenceInvalid

    # Review
    review: ReviewEvidence | EvidenceUnavailable | EvidenceInvalid

    # Merge result
    merge_commit_sha: str | None | EvidenceUnavailable | EvidenceInvalid

    # CI
    ci_status_at_review: CIStatus | EvidenceUnavailable | EvidenceInvalid

    # Containment
    containment: ContainmentEvidence | EvidenceUnavailable | EvidenceInvalid

    # Detected failure modes
    failure_modes: list[str] = field(default_factory=list)

    # Epic rollup
    child_done_audit_ids: list[str] | None = None
    child_evidence: list[ChildAuditEvidence] | EvidenceUnavailable | None = None

    # Metadata
    task_id: str = ""
    project_id: str = ""
    audit_id: str = ""
    collected_at: str = ""

    def passed(self) -> bool:
        """True when all checks pass and no failure modes were detected."""
        if self.failure_modes:
            return False
        if isinstance(self.review, ReviewEvidence) and not self.review.is_merged:
            return False
        if isinstance(self.containment, ContainmentEvidence) and not self.containment.all_landed:
            return False
        if isinstance(self.ci_status_at_review, CIStatus):
            if self.ci_status_at_review in (CIStatus.FAILED, CIStatus.PENDING):
                return False
        return True

    def has_failures(self) -> bool:
        """True when any evidence is marked unavailable/invalid or failure modes present."""
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


# ---------------------------------------------------------------------------
# Fake SCM for testing
# ---------------------------------------------------------------------------

@dataclass
class FakeSCMReview:
    """Fake review record for test fixtures."""

    review_id: str
    state: str  # open, closed, merged
    source_branch: str
    target_branch: str
    head_sha: str
    merge_commit_sha: Optional[str] = None
    ci_status: CIStatus = CIStatus.PASSED
    author: str = "author"
    commits: list[str] = field(default_factory=list)


class FakeSCMProvider:
    """In-memory fake SCM provider for testing MergedEvidenceCollector.

    Stores reviews keyed by repo+branch and by review_id. Simulates
    branch head lookups, CI status, and commit lookups.
    """

    def __init__(self) -> None:
        # repo -> list[FakeSCMReview]
        self._reviews: dict[str, list[FakeSCMReview]] = {}
        # repo -> branch -> sha
        self._branch_heads: dict[str, dict[str, str]] = {}
        # repo -> sha -> CIStatus
        self._ci_statuses: dict[str, dict[str, CIStatus]] = {}

    def add_review(self, repo: str, review: FakeSCMReview) -> None:
        """Register a fake review."""
        self._reviews.setdefault(repo, []).append(review)

    def set_branch_head(self, repo: str, branch: str, sha: str) -> None:
        """Set the HEAD SHA for a branch."""
        self._branch_heads.setdefault(repo, {})[branch] = sha

    def delete_branch(self, repo: str, branch: str) -> None:
        """Remove a branch (simulates deletion)."""
        self._branch_heads.get(repo, {}).pop(branch, None)

    def set_ci_status(self, repo: str, sha: str, status: CIStatus) -> None:
        """Set CI status for a SHA."""
        self._ci_statuses.setdefault(repo, {})[sha] = status

    def find_pr_for_branch(
        self, repo: str, branch: str, target_branch: str | None = None
    ) -> ReviewRequest | None:
        """Find the most recent review for a source branch."""
        reviews = self._reviews.get(repo, [])
        candidates = [r for r in reviews if r.source_branch == branch]
        if target_branch:
            # Prefer reviews targeting the intended branch
            targeted = [r for r in candidates if r.target_branch == target_branch]
            if targeted:
                candidates = targeted
        if not candidates:
            return None
        # Most recent = last added
        r = candidates[-1]
        return ReviewRequest(
            id=r.review_id,
            title=f"PR: {r.source_branch}",
            url=f"https://github.com/{repo}/pull/{r.review_id}",
            author=r.author,
            state=r.state,
            source_branch=r.source_branch,
            target_branch=r.target_branch,
            created_at="",
            updated_at="",
            ci_status=r.ci_status,
        )

    def get_review(self, repo: str, review_id: str) -> ReviewRequest | None:
        """Get a review by ID."""
        for r in self._reviews.get(repo, []):
            if r.review_id == review_id:
                return ReviewRequest(
                    id=r.review_id,
                    title=f"PR: {r.source_branch}",
                    url=f"https://github.com/{repo}/pull/{r.review_id}",
                    author=r.author,
                    state=r.state,
                    source_branch=r.source_branch,
                    target_branch=r.target_branch,
                    created_at="",
                    updated_at="",
                    ci_status=r.ci_status,
                )
        return None

    def get_branch_head_sha(self, repo: str, branch: str) -> str | None:
        """Get the HEAD SHA for a branch (None if branch deleted)."""
        return self._branch_heads.get(repo, {}).get(branch)

    def get_ci_status_for_sha(self, repo: str, sha: str) -> CIStatus:
        """Get CI status for a SHA."""
        return self._ci_statuses.get(repo, {}).get(sha, CIStatus.UNKNOWN)

    def get_pr_commits(self, repo: str, review_id: str) -> list[str]:
        """Get list of commit SHAs for a review."""
        for r in self._reviews.get(repo, []):
            if r.review_id == review_id:
                return list(r.commits)
        return []

    def get_review_head_sha(self, repo: str, review_id: str) -> str | None:
        """Return the head SHA recorded on the PR/MR at review time."""
        for r in self._reviews.get(repo, []):
            if r.review_id == review_id:
                return r.head_sha if r.head_sha else None
        return None


# ---------------------------------------------------------------------------
# Main collector
# ---------------------------------------------------------------------------

class MergedEvidenceCollector:
    """Read-only evidence collector for Merged completion audits.

    Verifies that a task's source branch actually landed on the configured
    target branch, detecting wrong-target merges, unmerged reviews, CI
    failures, stale tips, stranded commits, and more.

    For epics, validates that all child branches landed on the target.
    """

    def __init__(
        self,
        *,
        repo: str,
        intended_target_branch: str,
        task_id: str = "",
        project_id: str = "",
        scm_provider: _SCMProtocol | None = None,
        worktree_path: str | None = None,
    ) -> None:
        """Initialize collector.

        Args:
            repo: Repository identifier (e.g. "owner/repo") for SCM queries.
            intended_target_branch: The branch the task should have landed on.
            task_id: Task identifier being audited.
            project_id: Project identifier.
            scm_provider: SCM provider for review/CI lookups. If None, git
                operations only are used (no SCM review checks).
            worktree_path: Path to the git worktree for git operations. If
                None, git containment checks are skipped.
        """
        if not isinstance(repo, str) or not repo.strip():
            raise ValueError("MergedEvidenceCollector.repo must be non-empty")
        if not isinstance(intended_target_branch, str) or not intended_target_branch.strip():
            raise ValueError("MergedEvidenceCollector.intended_target_branch must be non-empty")

        self.repo = repo
        self.intended_target_branch = intended_target_branch
        self.task_id = task_id
        self.project_id = project_id
        self._scm = scm_provider
        self._worktree_path = Path(worktree_path).resolve() if worktree_path else None

    def collect(
        self,
        *,
        source_branch: str,
        done_audit_id: str = "",
        done_audit_verdict: str = "",
        done_audit_fingerprint: EvidenceFingerprint | None = None,
        review_id: str | None = None,
        child_done_audit_ids: list[str] | None = None,
        child_task_branches: dict[str, str] | None = None,
        audit_id: str = "",
        collected_at: str = "",
    ) -> MergedEvidenceSnapshot:
        """Collect a complete Merged evidence snapshot.

        Args:
            source_branch: The source branch that should have been merged.
            done_audit_id: ID of the Done audit that preceded this.
            done_audit_verdict: Verdict of the Done audit ("pass" / "fail").
            done_audit_fingerprint: Fingerprint of the Done audit.
            review_id: Optional explicit review/PR ID. If None, lookup by branch.
            child_done_audit_ids: For epics, Done audit IDs of child tasks.
            child_task_branches: For epics, mapping of task_id -> branch name.
            audit_id: This audit's ID.
            collected_at: ISO8601 timestamp.

        Returns:
            MergedEvidenceSnapshot with all collected evidence.
        """
        failure_modes: list[str] = []

        # 1. Validate Done audit presence and verdict
        done_audit_id_evidence, done_audit_verdict_evidence, done_fp_evidence = (
            self._validate_done_audit(
                done_audit_id, done_audit_verdict, done_audit_fingerprint, failure_modes
            )
        )

        # 2. Collect source branch evidence
        source_sha_current = self._collect_source_sha_current(source_branch)
        source_branch_evidence: str | EvidenceUnavailable | EvidenceInvalid = source_branch

        # 3. Collect intended target branch and its HEAD
        target_head_sha = self._collect_target_head_sha()

        # 4. Find and evaluate the review
        review_evidence = self._collect_review_evidence(
            source_branch, review_id, failure_modes
        )

        # 5. Extract reviewed source SHA from review
        source_sha_at_review = self._extract_reviewed_sha(review_evidence)

        # 6. Check for stale branch tip (source advanced after review)
        self._check_stale_branch_tip(
            source_sha_at_review, source_sha_current, failure_modes
        )

        # 7. Collect CI status at the reviewed SHA
        ci_status_at_review = self._collect_ci_status(review_evidence)

        # 8. Collect merge commit SHA
        merge_commit_sha = self._extract_merge_commit(review_evidence)

        # 9. Containment check
        containment = self._collect_containment(review_evidence, target_head_sha)
        self._check_containment_failures(containment, failure_modes)

        # 10. Epic rollup
        child_evidence = self._collect_child_evidence(
            child_done_audit_ids, child_task_branches, failure_modes
        )

        return MergedEvidenceSnapshot(
            done_audit_id=done_audit_id_evidence,
            done_audit_verdict=done_audit_verdict_evidence,
            done_audit_fingerprint=done_fp_evidence,
            source_branch=source_branch_evidence,
            source_sha_at_review=source_sha_at_review,
            source_sha_current=source_sha_current,
            intended_target_branch=self.intended_target_branch,
            target_head_sha=target_head_sha,
            review=review_evidence,
            merge_commit_sha=merge_commit_sha,
            ci_status_at_review=ci_status_at_review,
            containment=containment,
            failure_modes=failure_modes,
            child_done_audit_ids=child_done_audit_ids,
            child_evidence=child_evidence,
            task_id=self.task_id,
            project_id=self.project_id,
            audit_id=audit_id,
            collected_at=collected_at,
        )

    # ------------------------------------------------------------------
    # Private evidence collection methods
    # ------------------------------------------------------------------

    def _validate_done_audit(
        self,
        done_audit_id: str,
        done_audit_verdict: str,
        done_audit_fingerprint: EvidenceFingerprint | None,
        failure_modes: list[str],
    ) -> tuple[
        str | EvidenceUnavailable | EvidenceInvalid,
        str | EvidenceUnavailable | EvidenceInvalid,
        EvidenceFingerprint | EvidenceUnavailable | EvidenceInvalid,
    ]:
        """Validate that a passing Done audit exists for this task."""
        if not done_audit_id or not done_audit_id.strip():
            failure_modes.append(FailureMode.NO_DONE_AUDIT.value)
            return (
                EvidenceUnavailable("No Done audit ID provided"),
                EvidenceUnavailable("No Done audit"),
                EvidenceUnavailable("No Done audit"),
            )

        verdict_evidence: str | EvidenceUnavailable | EvidenceInvalid
        if not done_audit_verdict or not done_audit_verdict.strip():
            failure_modes.append(FailureMode.NO_DONE_AUDIT.value)
            verdict_evidence = EvidenceUnavailable("Done audit verdict not provided")
        elif done_audit_verdict.lower() not in ("pass", "passed"):
            failure_modes.append(FailureMode.DONE_AUDIT_NOT_PASSED.value)
            verdict_evidence = EvidenceInvalid(
                f"Done audit verdict is not passed: {done_audit_verdict!r}"
            )
        else:
            verdict_evidence = done_audit_verdict

        fp_evidence: EvidenceFingerprint | EvidenceUnavailable | EvidenceInvalid
        if done_audit_fingerprint is None:
            fp_evidence = EvidenceUnavailable("Done audit fingerprint not provided")
        elif not isinstance(done_audit_fingerprint, EvidenceFingerprint):
            fp_evidence = EvidenceInvalid("Done audit fingerprint is not an EvidenceFingerprint")
        else:
            fp_evidence = done_audit_fingerprint

        return done_audit_id, verdict_evidence, fp_evidence

    def _collect_source_sha_current(
        self, source_branch: str
    ) -> str | EvidenceUnavailable:
        """Collect the current HEAD SHA of the source branch."""
        # Try SCM provider first
        if self._scm is not None:
            sha = self._scm.get_branch_head_sha(self.repo, source_branch)
            if sha is not None:
                return sha
            # Branch is deleted on origin
            return EvidenceUnavailable(f"Branch {source_branch!r} not found on origin (deleted?)")

        # Fall back to git
        if self._worktree_path is not None:
            try:
                return self._run_git(["rev-parse", f"origin/{source_branch}"])
            except ValueError:
                try:
                    return self._run_git(["rev-parse", source_branch])
                except ValueError:
                    return EvidenceUnavailable(
                        f"Cannot resolve branch {source_branch!r} via git"
                    )

        return EvidenceUnavailable("No SCM provider or worktree path configured")

    def _collect_target_head_sha(self) -> str | EvidenceUnavailable:
        """Collect the current HEAD SHA of the intended target branch."""
        if self._scm is not None:
            sha = self._scm.get_branch_head_sha(self.repo, self.intended_target_branch)
            if sha is not None:
                return sha
            return EvidenceUnavailable(
                f"Target branch {self.intended_target_branch!r} not found"
            )

        if self._worktree_path is not None:
            try:
                return self._run_git(["rev-parse", f"origin/{self.intended_target_branch}"])
            except ValueError:
                try:
                    return self._run_git(["rev-parse", self.intended_target_branch])
                except ValueError:
                    return EvidenceUnavailable(
                        f"Cannot resolve target branch {self.intended_target_branch!r}"
                    )

        return EvidenceUnavailable("No SCM provider or worktree path configured")

    def _collect_review_evidence(
        self,
        source_branch: str,
        review_id: str | None,
        failure_modes: list[str],
    ) -> ReviewEvidence | EvidenceUnavailable | EvidenceInvalid:
        """Find and evaluate the review (PR/MR) for the source branch."""
        if self._scm is None:
            return EvidenceUnavailable("No SCM provider configured — cannot look up review")

        try:
            if review_id:
                rr = self._scm.get_review(self.repo, review_id)
            else:
                rr = self._scm.find_pr_for_branch(
                    self.repo, source_branch, self.intended_target_branch
                )

            if rr is None:
                failure_modes.append(FailureMode.NO_REVIEW_FOUND.value)
                return EvidenceUnavailable(
                    f"No review found for branch {source_branch!r} "
                    f"targeting {self.intended_target_branch!r}"
                )

            # Detect failure modes from review state
            if rr.state == "open":
                failure_modes.append(FailureMode.OPEN_REVIEW.value)
            elif rr.state == "closed":
                # closed without merge
                failure_modes.append(FailureMode.CLOSED_UNMERGED.value)

            # Wrong-target detection
            if rr.target_branch != self.intended_target_branch:
                failure_modes.append(FailureMode.WRONG_TARGET.value)

            # CI failure detection
            if rr.ci_status == CIStatus.FAILED:
                failure_modes.append(FailureMode.FAILED_CI.value)
            elif rr.ci_status == CIStatus.PENDING:
                failure_modes.append(FailureMode.PENDING_CI.value)

            # Extract merge commit SHA from SCM if possible
            merge_commit: str | None = None
            if rr.state == "merged":
                # Try to get merge commit from SCM review details
                review_dict = rr.to_dict()
                merge_commit = review_dict.get("merge_commit_sha")
                if not merge_commit:
                    # Some providers include it in the state dict; check common fields
                    # For FakeSCMProvider the merge_commit_sha is on the FakeSCMReview
                    # but ReviewRequest doesn't carry it natively. Use None as fallback.
                    merge_commit = None

            # Resolve the head SHA at review time.
            # Use get_review_head_sha when available (captures the SHA at review
            # creation time, which may differ from the current branch HEAD).
            head_sha = ""
            if hasattr(self._scm, "get_review_head_sha"):
                sha_at_review = self._scm.get_review_head_sha(self.repo, rr.id)
                if sha_at_review:
                    head_sha = sha_at_review
            if not head_sha:
                # Fallback: use current branch HEAD
                head_sha_via_scm = self._scm.get_branch_head_sha(self.repo, rr.source_branch)
                head_sha = head_sha_via_scm or ""

            return ReviewEvidence(
                review_id=rr.id,
                review_state=rr.state if rr.state in ("open", "closed", "merged") else "closed",
                source_branch=rr.source_branch,
                target_branch=rr.target_branch,
                reviewed_source_sha=head_sha,
                merge_commit_sha=merge_commit,
                ci_status=rr.ci_status,
                author=rr.author,
            )

        except Exception as exc:
            logger.exception("Failed to collect review evidence for branch %s", source_branch)
            return EvidenceInvalid(f"Review lookup failed: {exc}")

    def _extract_reviewed_sha(
        self, review: ReviewEvidence | EvidenceUnavailable | EvidenceInvalid
    ) -> str | EvidenceUnavailable | EvidenceInvalid:
        """Extract the reviewed source SHA from review evidence."""
        if isinstance(review, ReviewEvidence):
            if review.reviewed_source_sha:
                return review.reviewed_source_sha
            return EvidenceUnavailable("Reviewed source SHA not available from review")
        if isinstance(review, EvidenceUnavailable):
            return review
        return EvidenceInvalid("Cannot extract SHA from invalid review evidence")

    def _check_stale_branch_tip(
        self,
        sha_at_review: str | EvidenceUnavailable | EvidenceInvalid,
        sha_current: str | EvidenceUnavailable,
        failure_modes: list[str],
    ) -> None:
        """Detect if the source branch advanced after the review was opened."""
        if (
            isinstance(sha_at_review, str)
            and isinstance(sha_current, str)
            and sha_at_review
            and sha_current
            and sha_at_review != sha_current
        ):
            failure_modes.append(FailureMode.STALE_BRANCH_TIP.value)

    def _collect_ci_status(
        self, review: ReviewEvidence | EvidenceUnavailable | EvidenceInvalid
    ) -> CIStatus | EvidenceUnavailable | EvidenceInvalid:
        """Collect CI status at the reviewed SHA."""
        if isinstance(review, EvidenceUnavailable):
            return EvidenceUnavailable("Cannot determine CI status — no review")
        if isinstance(review, EvidenceInvalid):
            return EvidenceInvalid("Cannot determine CI status — invalid review")

        if self._scm is not None and review.reviewed_source_sha:
            try:
                return self._scm.get_ci_status_for_sha(self.repo, review.reviewed_source_sha)
            except Exception as exc:
                return EvidenceUnavailable(f"CI status lookup failed: {exc}")

        # Fall back to what the review already told us
        return review.ci_status

    def _extract_merge_commit(
        self, review: ReviewEvidence | EvidenceUnavailable | EvidenceInvalid
    ) -> str | None | EvidenceUnavailable | EvidenceInvalid:
        """Extract the merge commit SHA from review evidence."""
        if isinstance(review, ReviewEvidence):
            return review.merge_commit_sha  # may be None if not recorded
        if isinstance(review, EvidenceUnavailable):
            return review
        return EvidenceInvalid("Cannot extract merge commit from invalid review")

    def _collect_containment(
        self,
        review: ReviewEvidence | EvidenceUnavailable | EvidenceInvalid,
        target_head_sha: str | EvidenceUnavailable,
    ) -> ContainmentEvidence | EvidenceUnavailable | EvidenceInvalid:
        """Determine whether reviewed commits are contained in the target branch."""
        if isinstance(review, (EvidenceUnavailable, EvidenceInvalid)):
            return EvidenceUnavailable("Cannot check containment — review evidence unavailable")
        if isinstance(target_head_sha, EvidenceUnavailable):
            return EvidenceUnavailable("Cannot check containment — target HEAD unavailable")

        reviewed_sha = review.reviewed_source_sha

        # Get the list of commits in the review via SCM
        commits_from_review: list[str] = []
        if self._scm is not None:
            try:
                commits_from_review = self._scm.get_pr_commits(self.repo, review.review_id)
            except Exception:
                commits_from_review = []

        # If we have a git worktree, check containment directly
        if self._worktree_path is not None:
            return self._check_git_containment(
                reviewed_sha, target_head_sha, commits_from_review
            )

        # Without git, only check if the merge state tells us
        if review.is_merged and review.target_branch == self.intended_target_branch:
            # Trust the SCM: if merged to the right target, assume contained
            return ContainmentEvidence(
                reviewed_sha_in_target=True,
                commits_from_review=commits_from_review,
                stranded_commits=[],
            )

        if not review.is_merged:
            return ContainmentEvidence(
                reviewed_sha_in_target=False,
                commits_from_review=commits_from_review,
                stranded_commits=commits_from_review,  # All stranded
            )

        return EvidenceUnavailable(
            "Cannot verify containment without git worktree for non-trivial merge"
        )

    def _check_git_containment(
        self,
        reviewed_sha: str,
        target_head_sha: str,
        commits_from_review: list[str],
    ) -> ContainmentEvidence | EvidenceUnavailable | EvidenceInvalid:
        """Use git to check containment of reviewed SHA in target HEAD."""
        if not reviewed_sha:
            return EvidenceUnavailable("Reviewed source SHA is empty")

        try:
            # Check if reviewed_sha is an ancestor of target_head_sha
            result = subprocess.run(
                ["git", "merge-base", "--is-ancestor", reviewed_sha, target_head_sha],
                cwd=str(self._worktree_path),
                capture_output=True,
                text=True,
            )
            reviewed_sha_in_target = result.returncode == 0

            # Find stranded commits: commits from review not reachable from target
            stranded_commits: list[str] = []
            if commits_from_review:
                for sha in commits_from_review:
                    check = subprocess.run(
                        ["git", "merge-base", "--is-ancestor", sha, target_head_sha],
                        cwd=str(self._worktree_path),
                        capture_output=True,
                        text=True,
                    )
                    if check.returncode != 0:
                        stranded_commits.append(sha)

            return ContainmentEvidence(
                reviewed_sha_in_target=reviewed_sha_in_target,
                commits_from_review=commits_from_review,
                stranded_commits=stranded_commits,
            )
        except Exception as exc:
            return EvidenceInvalid(f"Git containment check failed: {exc}")

    def _check_containment_failures(
        self,
        containment: ContainmentEvidence | EvidenceUnavailable | EvidenceInvalid,
        failure_modes: list[str],
    ) -> None:
        """Add failure modes based on containment evidence."""
        if isinstance(containment, ContainmentEvidence):
            if containment.stranded_commits:
                failure_modes.append(FailureMode.STRANDED_COMMITS.value)
            if not containment.reviewed_sha_in_target and not containment.stranded_commits:
                # SHA not in target but no tracked commits stranded — still a miss
                if not containment.all_landed:
                    failure_modes.append(FailureMode.STRANDED_COMMITS.value)

    def _collect_child_evidence(
        self,
        child_done_audit_ids: list[str] | None,
        child_task_branches: dict[str, str] | None,
        failure_modes: list[str],
    ) -> list[ChildAuditEvidence] | EvidenceUnavailable | None:
        """Collect evidence for epic child tasks."""
        if child_done_audit_ids is None:
            return None  # Not an epic

        if not child_done_audit_ids:
            return []

        child_evidence: list[ChildAuditEvidence] = []
        child_task_branches = child_task_branches or {}

        for audit_id in child_done_audit_ids:
            # Try to match audit_id to a task ID in child_task_branches
            # The convention is audit_id contains the task_id as a prefix
            task_id = None
            branch: str | EvidenceUnavailable = EvidenceUnavailable(
                "No branch mapping provided for child"
            )

            for tid, tbranch in child_task_branches.items():
                if tid in audit_id or audit_id in tid:
                    task_id = tid
                    branch = tbranch
                    break

            if task_id is None:
                task_id = audit_id  # Use audit_id as task_id fallback

            # Check landing for this child
            child_failure_modes: list[str] = []
            landed: bool | EvidenceUnavailable | EvidenceInvalid

            if isinstance(branch, EvidenceUnavailable):
                landed = EvidenceUnavailable("Cannot check child landing — branch unknown")
            else:
                # Check if child's branch is in the target
                child_sha = self._collect_source_sha_current(branch)
                if isinstance(child_sha, EvidenceUnavailable):
                    # Branch deleted — check if we know from SCM it was merged
                    if self._scm is not None:
                        rr = self._scm.find_pr_for_branch(
                            self.repo, branch, self.intended_target_branch
                        )
                        if rr is not None and rr.state == "merged" and rr.target_branch == self.intended_target_branch:
                            landed = True
                        else:
                            landed = EvidenceUnavailable(
                                f"Child branch {branch!r} deleted and no merged review found"
                            )
                            child_failure_modes.append(FailureMode.DELETED_BRANCH_NO_EVIDENCE.value)
                    else:
                        landed = EvidenceUnavailable(
                            f"Child branch {branch!r} deleted and no SCM provider available"
                        )
                        child_failure_modes.append(FailureMode.DELETED_BRANCH_NO_EVIDENCE.value)
                else:
                    # Check containment via git
                    if self._worktree_path is not None:
                        target_sha = self._collect_target_head_sha()
                        if isinstance(target_sha, str) and isinstance(child_sha, str):
                            check = subprocess.run(
                                ["git", "merge-base", "--is-ancestor", child_sha, target_sha],
                                cwd=str(self._worktree_path),
                                capture_output=True,
                                text=True,
                            )
                            landed = check.returncode == 0
                            if not landed:
                                child_failure_modes.append(FailureMode.CHILD_NOT_LANDED.value)
                        else:
                            landed = EvidenceUnavailable("Cannot verify child containment")
                    elif self._scm is not None:
                        # Trust SCM review state
                        rr = self._scm.find_pr_for_branch(
                            self.repo, branch, self.intended_target_branch
                        )
                        if rr is not None and rr.state == "merged" and rr.target_branch == self.intended_target_branch:
                            landed = True
                        else:
                            landed = EvidenceUnavailable(
                                f"Child branch {branch!r} not confirmed landed via SCM"
                            )
                            child_failure_modes.append(FailureMode.CHILD_NOT_LANDED.value)
                    else:
                        landed = EvidenceUnavailable("No git or SCM available to verify child")

            if child_failure_modes:
                failure_modes.extend(child_failure_modes)

            child_evidence.append(ChildAuditEvidence(
                child_task_id=task_id,
                done_audit_id=audit_id,
                source_branch=branch,
                landed_on_target=landed,
                failure_modes=child_failure_modes,
            ))

        return child_evidence

    # ------------------------------------------------------------------
    # Git helper
    # ------------------------------------------------------------------

    def _run_git(self, args: list[str]) -> str:
        """Run a git command and return stripped output."""
        if self._worktree_path is None:
            raise ValueError("No worktree path configured")
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=str(self._worktree_path),
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as exc:
            raise ValueError(f"git {' '.join(args)} failed: {exc.stderr.strip()}")


__all__ = [
    "MergedEvidenceCollector",
    "MergedEvidenceSnapshot",
    "ReviewEvidence",
    "ContainmentEvidence",
    "ChildAuditEvidence",
    "FailureMode",
    "FakeSCMProvider",
    "FakeSCMReview",
    "EvidenceUnavailable",
    "EvidenceInvalid",
]
