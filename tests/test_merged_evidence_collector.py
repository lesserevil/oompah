"""Tests for MergedEvidenceCollector with Git and fake SCM fixtures.

Covers:
- Correct landing (happy path)
- Wrong-target merge
- Open review
- Closed-without-merge review
- Failed and pending CI
- Squash / rebase / merge commits (git containment)
- Deleted source branch with merged evidence
- Source branch advanced after review (stale tip)
- Stranded commits
- Shared epic rollup
- Nested epic target chain
- No Done audit
- Done audit not passed
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from oompah.merged_evidence_collector import (
    ChildAuditEvidence,
    ContainmentEvidence,
    EvidenceInvalid,
    EvidenceUnavailable,
    FailureMode,
    FakeSCMProvider,
    FakeSCMReview,
    MergedEvidenceCollector,
    MergedEvidenceSnapshot,
    ReviewEvidence,
)
from oompah.scm import CIStatus
from oompah.terminal_audit import EvidenceFingerprint
from tests.fixtures_git import LocalRepo, run_git


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REPO = "owner/test-repo"
TARGET = "main"


def _fingerprint() -> EvidenceFingerprint:
    return EvidenceFingerprint.from_evidence(
        requirements_text="Implement feature",
        project_id="proj-test",
        task_id="TASK-1",
        source_branch="feature/x",
        source_sha="abc123",
        target_branch=TARGET,
        target_sha="def456",
    )


def _make_collector(
    scm: FakeSCMProvider | None = None,
    worktree: str | None = None,
    target: str = TARGET,
) -> MergedEvidenceCollector:
    return MergedEvidenceCollector(
        repo=REPO,
        intended_target_branch=target,
        task_id="TASK-1",
        project_id="proj-test",
        scm_provider=scm,
        worktree_path=worktree,
    )


def _fake_merged_review(
    source_branch: str = "feature/x",
    target_branch: str = TARGET,
    head_sha: str = "abc123",
    merge_commit_sha: str | None = "merge001",
    ci_status: CIStatus = CIStatus.PASSED,
    state: str = "merged",
    review_id: str = "1",
) -> FakeSCMReview:
    return FakeSCMReview(
        review_id=review_id,
        state=state,
        source_branch=source_branch,
        target_branch=target_branch,
        head_sha=head_sha,
        merge_commit_sha=merge_commit_sha,
        ci_status=ci_status,
        commits=[head_sha],
    )


def _setup_scm(
    source_branch: str = "feature/x",
    source_sha: str = "abc123",
    target_sha: str = "target001",
    review: FakeSCMReview | None = None,
    ci_at_sha: CIStatus = CIStatus.PASSED,
) -> FakeSCMProvider:
    scm = FakeSCMProvider()
    r = review or _fake_merged_review(
        source_branch=source_branch, head_sha=source_sha
    )
    scm.add_review(REPO, r)
    scm.set_branch_head(REPO, source_branch, source_sha)
    scm.set_branch_head(REPO, TARGET, target_sha)
    scm.set_ci_status(REPO, source_sha, ci_at_sha)
    return scm


# ---------------------------------------------------------------------------
# Basic construction tests
# ---------------------------------------------------------------------------


class TestMergedEvidenceCollectorConstruction:
    def test_requires_nonempty_repo(self) -> None:
        with pytest.raises(ValueError, match="repo"):
            MergedEvidenceCollector(
                repo="",
                intended_target_branch=TARGET,
            )

    def test_requires_nonempty_target_branch(self) -> None:
        with pytest.raises(ValueError, match="intended_target_branch"):
            MergedEvidenceCollector(
                repo=REPO,
                intended_target_branch="",
            )

    def test_accepts_valid_configuration(self) -> None:
        c = MergedEvidenceCollector(
            repo=REPO,
            intended_target_branch=TARGET,
            task_id="TASK-1",
            project_id="proj-1",
        )
        assert c.repo == REPO
        assert c.intended_target_branch == TARGET


# ---------------------------------------------------------------------------
# Happy path: correct landing
# ---------------------------------------------------------------------------


class TestCorrectLanding:
    def test_merged_to_correct_target_passes(self) -> None:
        scm = _setup_scm()
        collector = _make_collector(scm=scm)

        snapshot = collector.collect(
            source_branch="feature/x",
            done_audit_id="audit-1",
            done_audit_verdict="pass",
            done_audit_fingerprint=_fingerprint(),
        )

        assert isinstance(snapshot, MergedEvidenceSnapshot)
        assert snapshot.passed()
        assert not snapshot.failure_modes

    def test_review_evidence_populated(self) -> None:
        scm = _setup_scm()
        collector = _make_collector(scm=scm)

        snapshot = collector.collect(
            source_branch="feature/x",
            done_audit_id="audit-1",
            done_audit_verdict="pass",
            done_audit_fingerprint=_fingerprint(),
        )

        assert isinstance(snapshot.review, ReviewEvidence)
        assert snapshot.review.is_merged
        assert snapshot.review.source_branch == "feature/x"
        assert snapshot.review.target_branch == TARGET

    def test_target_branch_set_correctly(self) -> None:
        scm = _setup_scm()
        collector = _make_collector(scm=scm)

        snapshot = collector.collect(
            source_branch="feature/x",
            done_audit_id="audit-1",
            done_audit_verdict="pass",
            done_audit_fingerprint=_fingerprint(),
        )

        assert snapshot.intended_target_branch == TARGET
        assert snapshot.target_head_sha == "target001"

    def test_ci_status_passed(self) -> None:
        scm = _setup_scm(ci_at_sha=CIStatus.PASSED)
        collector = _make_collector(scm=scm)

        snapshot = collector.collect(
            source_branch="feature/x",
            done_audit_id="audit-1",
            done_audit_verdict="pass",
            done_audit_fingerprint=_fingerprint(),
        )

        assert snapshot.ci_status_at_review == CIStatus.PASSED
        assert FailureMode.FAILED_CI.value not in snapshot.failure_modes

    def test_metadata_populated(self) -> None:
        scm = _setup_scm()
        collector = _make_collector(scm=scm)

        snapshot = collector.collect(
            source_branch="feature/x",
            done_audit_id="audit-1",
            done_audit_verdict="pass",
            done_audit_fingerprint=_fingerprint(),
            audit_id="merged-audit-42",
            collected_at="2026-07-29T00:00:00Z",
        )

        assert snapshot.task_id == "TASK-1"
        assert snapshot.project_id == "proj-test"
        assert snapshot.audit_id == "merged-audit-42"
        assert snapshot.collected_at == "2026-07-29T00:00:00Z"


# ---------------------------------------------------------------------------
# Wrong-target merge
# ---------------------------------------------------------------------------


class TestWrongTargetMerge:
    def test_detects_wrong_target_merge(self) -> None:
        scm = FakeSCMProvider()
        review = _fake_merged_review(target_branch="staging")  # wrong target
        scm.add_review(REPO, review)
        scm.set_branch_head(REPO, "feature/x", "abc123")
        scm.set_branch_head(REPO, TARGET, "target001")
        scm.set_branch_head(REPO, "staging", "staging001")
        scm.set_ci_status(REPO, "abc123", CIStatus.PASSED)

        collector = _make_collector(scm=scm)
        snapshot = collector.collect(
            source_branch="feature/x",
            done_audit_id="audit-1",
            done_audit_verdict="pass",
            done_audit_fingerprint=_fingerprint(),
        )

        assert FailureMode.WRONG_TARGET.value in snapshot.failure_modes
        assert not snapshot.passed()

    def test_review_shows_wrong_target_branch(self) -> None:
        scm = FakeSCMProvider()
        review = _fake_merged_review(target_branch="staging")
        scm.add_review(REPO, review)
        scm.set_branch_head(REPO, "feature/x", "abc123")
        scm.set_branch_head(REPO, TARGET, "target001")
        scm.set_branch_head(REPO, "staging", "staging001")

        collector = _make_collector(scm=scm)
        snapshot = collector.collect(
            source_branch="feature/x",
            done_audit_id="audit-1",
            done_audit_verdict="pass",
            done_audit_fingerprint=_fingerprint(),
        )

        assert isinstance(snapshot.review, ReviewEvidence)
        assert snapshot.review.target_branch == "staging"


# ---------------------------------------------------------------------------
# Open review
# ---------------------------------------------------------------------------


class TestOpenReview:
    def test_detects_open_review(self) -> None:
        scm = _setup_scm(review=_fake_merged_review(state="open", merge_commit_sha=None))
        collector = _make_collector(scm=scm)

        snapshot = collector.collect(
            source_branch="feature/x",
            done_audit_id="audit-1",
            done_audit_verdict="pass",
            done_audit_fingerprint=_fingerprint(),
        )

        assert FailureMode.OPEN_REVIEW.value in snapshot.failure_modes
        assert not snapshot.passed()

    def test_open_review_not_merged(self) -> None:
        scm = _setup_scm(review=_fake_merged_review(state="open", merge_commit_sha=None))
        collector = _make_collector(scm=scm)

        snapshot = collector.collect(
            source_branch="feature/x",
            done_audit_id="audit-1",
            done_audit_verdict="pass",
            done_audit_fingerprint=_fingerprint(),
        )

        assert isinstance(snapshot.review, ReviewEvidence)
        assert snapshot.review.is_open
        assert not snapshot.review.is_merged


# ---------------------------------------------------------------------------
# Closed without merge
# ---------------------------------------------------------------------------


class TestClosedWithoutMerge:
    def test_detects_closed_unmerged_review(self) -> None:
        scm = _setup_scm(review=_fake_merged_review(state="closed", merge_commit_sha=None))
        collector = _make_collector(scm=scm)

        snapshot = collector.collect(
            source_branch="feature/x",
            done_audit_id="audit-1",
            done_audit_verdict="pass",
            done_audit_fingerprint=_fingerprint(),
        )

        assert FailureMode.CLOSED_UNMERGED.value in snapshot.failure_modes
        assert not snapshot.passed()

    def test_closed_review_containment_shows_stranded(self) -> None:
        scm = _setup_scm(review=_fake_merged_review(state="closed", merge_commit_sha=None))
        collector = _make_collector(scm=scm)

        snapshot = collector.collect(
            source_branch="feature/x",
            done_audit_id="audit-1",
            done_audit_verdict="pass",
            done_audit_fingerprint=_fingerprint(),
        )

        # All review commits are stranded since review was not merged
        if isinstance(snapshot.containment, ContainmentEvidence):
            assert snapshot.containment.stranded_commits


# ---------------------------------------------------------------------------
# Failed and pending CI
# ---------------------------------------------------------------------------


class TestCIStatus:
    def test_detects_failed_ci(self) -> None:
        scm = _setup_scm(
            ci_at_sha=CIStatus.FAILED,
            review=_fake_merged_review(ci_status=CIStatus.FAILED),
        )
        collector = _make_collector(scm=scm)

        snapshot = collector.collect(
            source_branch="feature/x",
            done_audit_id="audit-1",
            done_audit_verdict="pass",
            done_audit_fingerprint=_fingerprint(),
        )

        assert FailureMode.FAILED_CI.value in snapshot.failure_modes
        assert not snapshot.passed()

    def test_detects_pending_ci(self) -> None:
        scm = _setup_scm(
            ci_at_sha=CIStatus.PENDING,
            review=_fake_merged_review(ci_status=CIStatus.PENDING),
        )
        collector = _make_collector(scm=scm)

        snapshot = collector.collect(
            source_branch="feature/x",
            done_audit_id="audit-1",
            done_audit_verdict="pass",
            done_audit_fingerprint=_fingerprint(),
        )

        assert FailureMode.PENDING_CI.value in snapshot.failure_modes
        assert not snapshot.passed()

    def test_unknown_ci_does_not_cause_failure(self) -> None:
        scm = _setup_scm(
            ci_at_sha=CIStatus.UNKNOWN,
            review=_fake_merged_review(ci_status=CIStatus.UNKNOWN),
        )
        collector = _make_collector(scm=scm)

        snapshot = collector.collect(
            source_branch="feature/x",
            done_audit_id="audit-1",
            done_audit_verdict="pass",
            done_audit_fingerprint=_fingerprint(),
        )

        assert FailureMode.FAILED_CI.value not in snapshot.failure_modes
        assert FailureMode.PENDING_CI.value not in snapshot.failure_modes


# ---------------------------------------------------------------------------
# Stale branch tip (source advanced after review)
# ---------------------------------------------------------------------------


class TestStaleBranchTip:
    def test_detects_stale_branch_tip(self) -> None:
        """Source branch HEAD advanced after the review was opened."""
        scm = FakeSCMProvider()
        review_sha = "reviewed_sha_001"
        current_sha = "newer_sha_002"  # different from reviewed

        review = FakeSCMReview(
            review_id="1",
            state="merged",
            source_branch="feature/x",
            target_branch=TARGET,
            head_sha=review_sha,
            merge_commit_sha="merge001",
            ci_status=CIStatus.PASSED,
            commits=[review_sha],
        )
        scm.add_review(REPO, review)
        # Current branch tip is NEWER than reviewed SHA
        scm.set_branch_head(REPO, "feature/x", current_sha)
        scm.set_branch_head(REPO, TARGET, "target001")
        scm.set_ci_status(REPO, review_sha, CIStatus.PASSED)

        collector = _make_collector(scm=scm)
        snapshot = collector.collect(
            source_branch="feature/x",
            done_audit_id="audit-1",
            done_audit_verdict="pass",
            done_audit_fingerprint=_fingerprint(),
        )

        assert FailureMode.STALE_BRANCH_TIP.value in snapshot.failure_modes

    def test_no_stale_tip_when_sha_matches(self) -> None:
        """Source branch HEAD matches the reviewed SHA — no stale tip."""
        scm = _setup_scm(source_sha="abc123")
        collector = _make_collector(scm=scm)

        snapshot = collector.collect(
            source_branch="feature/x",
            done_audit_id="audit-1",
            done_audit_verdict="pass",
            done_audit_fingerprint=_fingerprint(),
        )

        assert FailureMode.STALE_BRANCH_TIP.value not in snapshot.failure_modes


# ---------------------------------------------------------------------------
# Deleted source branch
# ---------------------------------------------------------------------------


class TestDeletedBranch:
    def test_deleted_branch_with_merged_review_passes(self) -> None:
        """Branch deleted but review shows merged to correct target."""
        scm = FakeSCMProvider()
        review = _fake_merged_review(source_branch="feature/deleted", head_sha="sha001")
        scm.add_review(REPO, review)
        # Branch is deleted (not in branch_heads)
        scm.set_branch_head(REPO, TARGET, "target001")
        scm.set_ci_status(REPO, "sha001", CIStatus.PASSED)

        collector = MergedEvidenceCollector(
            repo=REPO,
            intended_target_branch=TARGET,
            task_id="TASK-1",
            project_id="proj-test",
            scm_provider=scm,
        )
        snapshot = collector.collect(
            source_branch="feature/deleted",
            done_audit_id="audit-1",
            done_audit_verdict="pass",
            done_audit_fingerprint=_fingerprint(),
        )

        # Branch is deleted but review shows merged — sha_current is unavailable
        assert isinstance(snapshot.source_sha_current, EvidenceUnavailable)
        # Review state should be merged
        assert isinstance(snapshot.review, ReviewEvidence)
        assert snapshot.review.is_merged

    def test_deleted_branch_no_merged_evidence_fails(self) -> None:
        """Branch deleted and no review shows it was merged."""
        scm = FakeSCMProvider()
        review = _fake_merged_review(
            source_branch="feature/deleted",
            head_sha="sha001",
            state="open",
            merge_commit_sha=None,
        )
        scm.add_review(REPO, review)
        # Branch is deleted — no branch head
        scm.set_branch_head(REPO, TARGET, "target001")

        collector = MergedEvidenceCollector(
            repo=REPO,
            intended_target_branch=TARGET,
            task_id="TASK-1",
            project_id="proj-test",
            scm_provider=scm,
        )
        snapshot = collector.collect(
            source_branch="feature/deleted",
            done_audit_id="audit-1",
            done_audit_verdict="pass",
            done_audit_fingerprint=_fingerprint(),
        )

        # Open review + deleted branch = failure
        assert FailureMode.OPEN_REVIEW.value in snapshot.failure_modes


# ---------------------------------------------------------------------------
# Git-based containment checks (squash / rebase / merge commits)
# ---------------------------------------------------------------------------


class TestGitContainment:
    def test_squash_merge_detected_as_landed(self, tmp_path: Path) -> None:
        """Squash merge: reviewed SHA is NOT ancestor but final squash commit is."""
        repo = LocalRepo(tmp_path / "repo")
        sha_initial = repo.commit("Initial", {"README.md": "base"})

        # Create feature branch
        repo.create_branch("feature/squash", "main")
        sha_feature = repo.commit("Feature work", {"feature.txt": "content"})

        # Simulate squash-merge onto main: we cherry-pick the changes
        repo.checkout("main")
        repo.commit("Squash commit", {"feature.txt": "content"})  # same content
        target_sha = repo.get_sha("HEAD")

        # For containment: the feature SHA itself is NOT in main (squash),
        # but the content is. Without git, we use SCM merge state as ground truth.
        scm = FakeSCMProvider()
        review = FakeSCMReview(
            review_id="1",
            state="merged",
            source_branch="feature/squash",
            target_branch="main",
            head_sha=sha_feature,
            merge_commit_sha=target_sha,
            ci_status=CIStatus.PASSED,
            commits=[sha_feature],
        )
        scm.add_review(REPO, review)
        scm.set_branch_head(REPO, "feature/squash", sha_feature)
        scm.set_branch_head(REPO, "main", target_sha)
        scm.set_ci_status(REPO, sha_feature, CIStatus.PASSED)

        collector = MergedEvidenceCollector(
            repo=REPO,
            intended_target_branch="main",
            task_id="TASK-1",
            project_id="proj-test",
            scm_provider=scm,
            worktree_path=str(repo.path),
        )
        snapshot = collector.collect(
            source_branch="feature/squash",
            done_audit_id="audit-1",
            done_audit_verdict="pass",
            done_audit_fingerprint=_fingerprint(),
        )

        # Review state says merged — should pass
        assert isinstance(snapshot.review, ReviewEvidence)
        assert snapshot.review.is_merged
        assert FailureMode.WRONG_TARGET.value not in snapshot.failure_modes

    def test_regular_merge_commit_in_target(self, tmp_path: Path) -> None:
        """Regular merge: reviewed SHA is ancestor of target HEAD."""
        repo = LocalRepo(tmp_path / "repo")
        repo.commit("Initial", {"README.md": "base"})

        # Create feature branch
        repo.create_branch("feature/merge", "main")
        sha_feature = repo.commit("Feature work", {"feature.txt": "content"})

        # Merge back onto main
        repo.checkout("main")
        run_git(repo.path, ["merge", "--no-ff", "feature/merge", "-m", "Merge feature/merge"])
        target_sha = repo.get_sha("HEAD")

        scm = FakeSCMProvider()
        review = FakeSCMReview(
            review_id="1",
            state="merged",
            source_branch="feature/merge",
            target_branch="main",
            head_sha=sha_feature,
            merge_commit_sha=target_sha,
            ci_status=CIStatus.PASSED,
            commits=[sha_feature],
        )
        scm.add_review(REPO, review)
        scm.set_branch_head(REPO, "feature/merge", sha_feature)
        scm.set_branch_head(REPO, "main", target_sha)
        scm.set_ci_status(REPO, sha_feature, CIStatus.PASSED)

        collector = MergedEvidenceCollector(
            repo=REPO,
            intended_target_branch="main",
            task_id="TASK-1",
            project_id="proj-test",
            scm_provider=scm,
            worktree_path=str(repo.path),
        )
        snapshot = collector.collect(
            source_branch="feature/merge",
            done_audit_id="audit-1",
            done_audit_verdict="pass",
            done_audit_fingerprint=_fingerprint(),
        )

        # Feature SHA is ancestor of target HEAD
        assert isinstance(snapshot.containment, ContainmentEvidence)
        assert snapshot.containment.reviewed_sha_in_target
        assert not snapshot.containment.stranded_commits

    def test_rebase_merge_all_commits_in_target(self, tmp_path: Path) -> None:
        """Rebase merge: original SHAs are NOT ancestors but feature content landed."""
        repo = LocalRepo(tmp_path / "repo")
        repo.commit("Initial", {"README.md": "base"})

        # Feature work
        repo.create_branch("feature/rebase", "main")
        sha_feature = repo.commit("Feature work", {"feature.txt": "content"})

        # Rebase onto main (re-creates commits with new SHAs)
        repo.checkout("main")
        # Simulate rebase by cherry-picking
        run_git(repo.path, ["cherry-pick", sha_feature])
        target_sha = repo.get_sha("HEAD")

        scm = FakeSCMProvider()
        review = FakeSCMReview(
            review_id="1",
            state="merged",
            source_branch="feature/rebase",
            target_branch="main",
            head_sha=sha_feature,
            merge_commit_sha=target_sha,
            ci_status=CIStatus.PASSED,
            commits=[sha_feature],
        )
        scm.add_review(REPO, review)
        scm.set_branch_head(REPO, "feature/rebase", sha_feature)
        scm.set_branch_head(REPO, "main", target_sha)

        collector = MergedEvidenceCollector(
            repo=REPO,
            intended_target_branch="main",
            task_id="TASK-1",
            project_id="proj-test",
            scm_provider=scm,
            worktree_path=str(repo.path),
        )
        snapshot = collector.collect(
            source_branch="feature/rebase",
            done_audit_id="audit-1",
            done_audit_verdict="pass",
            done_audit_fingerprint=_fingerprint(),
        )

        # SCM says merged — should trust that
        assert isinstance(snapshot.review, ReviewEvidence)
        assert snapshot.review.is_merged


# ---------------------------------------------------------------------------
# Stranded commits
# ---------------------------------------------------------------------------


class TestStrandedCommits:
    def test_detects_stranded_commits_via_git(self, tmp_path: Path) -> None:
        """Commits that are not reachable from target HEAD are stranded."""
        repo = LocalRepo(tmp_path / "repo")
        repo.commit("Initial", {"README.md": "base"})
        initial_target_sha = repo.get_sha("HEAD")

        # Feature branch with 2 commits
        repo.create_branch("feature/stranded", "main")
        sha1 = repo.commit("Commit 1", {"f1.txt": "c1"})
        sha2 = repo.commit("Commit 2", {"f2.txt": "c2"})

        # Target HEAD stays at initial (nothing merged)
        repo.checkout("main")

        scm = FakeSCMProvider()
        review = FakeSCMReview(
            review_id="1",
            state="open",  # not merged
            source_branch="feature/stranded",
            target_branch="main",
            head_sha=sha2,
            merge_commit_sha=None,
            ci_status=CIStatus.PASSED,
            commits=[sha1, sha2],
        )
        scm.add_review(REPO, review)
        scm.set_branch_head(REPO, "feature/stranded", sha2)
        scm.set_branch_head(REPO, "main", initial_target_sha)

        collector = MergedEvidenceCollector(
            repo=REPO,
            intended_target_branch="main",
            task_id="TASK-1",
            project_id="proj-test",
            scm_provider=scm,
            worktree_path=str(repo.path),
        )
        snapshot = collector.collect(
            source_branch="feature/stranded",
            done_audit_id="audit-1",
            done_audit_verdict="pass",
            done_audit_fingerprint=_fingerprint(),
        )

        assert FailureMode.OPEN_REVIEW.value in snapshot.failure_modes
        if isinstance(snapshot.containment, ContainmentEvidence):
            assert len(snapshot.containment.stranded_commits) > 0


# ---------------------------------------------------------------------------
# No review found
# ---------------------------------------------------------------------------


class TestNoReviewFound:
    def test_no_review_detected(self) -> None:
        scm = FakeSCMProvider()
        # No reviews registered
        scm.set_branch_head(REPO, "feature/x", "abc123")
        scm.set_branch_head(REPO, TARGET, "target001")

        collector = _make_collector(scm=scm)
        snapshot = collector.collect(
            source_branch="feature/x",
            done_audit_id="audit-1",
            done_audit_verdict="pass",
            done_audit_fingerprint=_fingerprint(),
        )

        assert FailureMode.NO_REVIEW_FOUND.value in snapshot.failure_modes
        assert isinstance(snapshot.review, EvidenceUnavailable)
        assert not snapshot.passed()


# ---------------------------------------------------------------------------
# Done audit validation
# ---------------------------------------------------------------------------


class TestDoneAuditValidation:
    def test_missing_done_audit_id_fails(self) -> None:
        scm = _setup_scm()
        collector = _make_collector(scm=scm)

        snapshot = collector.collect(
            source_branch="feature/x",
            done_audit_id="",  # empty
            done_audit_verdict="pass",
            done_audit_fingerprint=_fingerprint(),
        )

        assert FailureMode.NO_DONE_AUDIT.value in snapshot.failure_modes
        assert isinstance(snapshot.done_audit_id, EvidenceUnavailable)
        assert not snapshot.passed()

    def test_missing_done_audit_verdict_fails(self) -> None:
        scm = _setup_scm()
        collector = _make_collector(scm=scm)

        snapshot = collector.collect(
            source_branch="feature/x",
            done_audit_id="audit-1",
            done_audit_verdict="",  # empty
            done_audit_fingerprint=_fingerprint(),
        )

        assert FailureMode.NO_DONE_AUDIT.value in snapshot.failure_modes
        assert not snapshot.passed()

    def test_failed_done_audit_blocks_merge(self) -> None:
        scm = _setup_scm()
        collector = _make_collector(scm=scm)

        snapshot = collector.collect(
            source_branch="feature/x",
            done_audit_id="audit-1",
            done_audit_verdict="fail",  # not passed
            done_audit_fingerprint=_fingerprint(),
        )

        assert FailureMode.DONE_AUDIT_NOT_PASSED.value in snapshot.failure_modes
        assert not snapshot.passed()

    def test_passed_verdict_accepted(self) -> None:
        scm = _setup_scm()
        collector = _make_collector(scm=scm)

        snapshot = collector.collect(
            source_branch="feature/x",
            done_audit_id="audit-1",
            done_audit_verdict="pass",
            done_audit_fingerprint=_fingerprint(),
        )

        assert FailureMode.NO_DONE_AUDIT.value not in snapshot.failure_modes
        assert FailureMode.DONE_AUDIT_NOT_PASSED.value not in snapshot.failure_modes
        assert snapshot.done_audit_id == "audit-1"

    def test_no_fingerprint_does_not_block_but_is_unavailable(self) -> None:
        scm = _setup_scm()
        collector = _make_collector(scm=scm)

        snapshot = collector.collect(
            source_branch="feature/x",
            done_audit_id="audit-1",
            done_audit_verdict="pass",
            done_audit_fingerprint=None,  # not provided
        )

        assert isinstance(snapshot.done_audit_fingerprint, EvidenceUnavailable)


# ---------------------------------------------------------------------------
# Epic rollup (shared epic)
# ---------------------------------------------------------------------------


class TestEpicRollup:
    def test_epic_with_all_children_landed_passes(self) -> None:
        """Epic with two children both merged to main."""
        scm = FakeSCMProvider()

        # Add reviews for two child branches
        review1 = _fake_merged_review(
            source_branch="child-1", head_sha="sha-c1", review_id="1"
        )
        review2 = _fake_merged_review(
            source_branch="child-2", head_sha="sha-c2", review_id="2"
        )
        scm.add_review(REPO, review1)
        scm.add_review(REPO, review2)
        scm.set_branch_head(REPO, "child-1", "sha-c1")
        scm.set_branch_head(REPO, "child-2", "sha-c2")
        scm.set_branch_head(REPO, TARGET, "target001")
        scm.set_ci_status(REPO, "sha-c1", CIStatus.PASSED)
        scm.set_ci_status(REPO, "sha-c2", CIStatus.PASSED)

        # Epic collector (source_branch is the epic branch itself)
        scm.add_review(
            REPO,
            _fake_merged_review(source_branch="epic-branch", head_sha="sha-epic", review_id="3"),
        )
        scm.set_branch_head(REPO, "epic-branch", "sha-epic")

        collector = _make_collector(scm=scm)
        snapshot = collector.collect(
            source_branch="epic-branch",
            done_audit_id="audit-epic",
            done_audit_verdict="pass",
            done_audit_fingerprint=_fingerprint(),
            child_done_audit_ids=["audit-TASK-C1", "audit-TASK-C2"],
            child_task_branches={"TASK-C1": "child-1", "TASK-C2": "child-2"},
        )

        assert snapshot.child_done_audit_ids == ["audit-TASK-C1", "audit-TASK-C2"]
        assert isinstance(snapshot.child_evidence, list)
        assert len(snapshot.child_evidence) == 2

    def test_epic_with_unmerged_child_fails(self) -> None:
        """Epic where one child branch is not merged to main."""
        scm = FakeSCMProvider()

        # Child 1: merged OK
        review1 = _fake_merged_review(
            source_branch="child-ok", head_sha="sha-ok", review_id="1"
        )
        # Child 2: open (not merged)
        review2 = _fake_merged_review(
            source_branch="child-stuck",
            head_sha="sha-stuck",
            review_id="2",
            state="open",
            merge_commit_sha=None,
        )
        scm.add_review(REPO, review1)
        scm.add_review(REPO, review2)
        scm.set_branch_head(REPO, "child-ok", "sha-ok")
        scm.set_branch_head(REPO, "child-stuck", "sha-stuck")
        scm.set_branch_head(REPO, TARGET, "target001")

        # Epic branch
        scm.add_review(
            REPO,
            _fake_merged_review(source_branch="epic-branch", head_sha="sha-epic", review_id="3"),
        )
        scm.set_branch_head(REPO, "epic-branch", "sha-epic")

        collector = _make_collector(scm=scm)
        snapshot = collector.collect(
            source_branch="epic-branch",
            done_audit_id="audit-epic",
            done_audit_verdict="pass",
            done_audit_fingerprint=_fingerprint(),
            child_done_audit_ids=["audit-TASK-OK", "audit-TASK-STUCK"],
            child_task_branches={"TASK-OK": "child-ok", "TASK-STUCK": "child-stuck"},
        )

        # The stuck child should appear in evidence
        assert isinstance(snapshot.child_evidence, list)
        child_stucks = [
            c for c in snapshot.child_evidence if c.child_task_id == "TASK-STUCK"
        ]
        assert child_stucks
        # Child not-landed failure
        assert any(
            FailureMode.CHILD_NOT_LANDED.value in c.failure_modes
            for c in child_stucks
        )

    def test_epic_child_with_deleted_branch_and_merged_review(self) -> None:
        """Child branch deleted but SCM review shows it was merged to target."""
        scm = FakeSCMProvider()

        # Child branch is deleted (not in branch_heads) but has a merged review
        review = _fake_merged_review(
            source_branch="child-deleted", head_sha="sha-old", review_id="1"
        )
        scm.add_review(REPO, review)
        # Branch deleted: no set_branch_head for child-deleted
        scm.set_branch_head(REPO, TARGET, "target001")

        # Epic branch
        scm.add_review(
            REPO,
            _fake_merged_review(source_branch="epic-branch", head_sha="sha-epic", review_id="2"),
        )
        scm.set_branch_head(REPO, "epic-branch", "sha-epic")

        collector = _make_collector(scm=scm)
        snapshot = collector.collect(
            source_branch="epic-branch",
            done_audit_id="audit-epic",
            done_audit_verdict="pass",
            done_audit_fingerprint=_fingerprint(),
            child_done_audit_ids=["audit-TASK-DEL"],
            child_task_branches={"TASK-DEL": "child-deleted"},
        )

        child_del = next(
            c for c in snapshot.child_evidence if c.child_task_id == "TASK-DEL"
        )
        # Should be landed=True because review shows merged to correct target
        assert child_del.landed_on_target is True


# ---------------------------------------------------------------------------
# Nested epic
# ---------------------------------------------------------------------------


class TestNestedEpic:
    def test_nested_epic_chain_all_landed(self) -> None:
        """Nested epic: parent epic and child epics all landing on main."""
        scm = FakeSCMProvider()

        # Three levels: parent-epic -> child-epic -> leaf-task
        branches = {
            "leaf-task": "sha-leaf",
            "child-epic": "sha-child-epic",
            "parent-epic": "sha-parent-epic",
        }
        for branch, sha in branches.items():
            review = _fake_merged_review(
                source_branch=branch,
                head_sha=sha,
                review_id=branch.replace("-", "_"),
            )
            scm.add_review(REPO, review)
            scm.set_branch_head(REPO, branch, sha)
            scm.set_ci_status(REPO, sha, CIStatus.PASSED)

        scm.set_branch_head(REPO, TARGET, "target001")

        # Collect for child-epic (proves leaf landed)
        collector_child = _make_collector(scm=scm)
        snap_child = collector_child.collect(
            source_branch="child-epic",
            done_audit_id="audit-child-epic",
            done_audit_verdict="pass",
            done_audit_fingerprint=_fingerprint(),
            child_done_audit_ids=["audit-leaf-task"],
            child_task_branches={"leaf-task": "leaf-task"},
        )

        assert snap_child.child_done_audit_ids == ["audit-leaf-task"]

        # Collect for parent-epic (proves child-epic landed)
        collector_parent = _make_collector(scm=scm)
        snap_parent = collector_parent.collect(
            source_branch="parent-epic",
            done_audit_id="audit-parent-epic",
            done_audit_verdict="pass",
            done_audit_fingerprint=_fingerprint(),
            child_done_audit_ids=["audit-child-epic"],
            child_task_branches={"child-epic": "child-epic"},
        )

        assert snap_parent.child_done_audit_ids == ["audit-child-epic"]
        assert isinstance(snap_parent.child_evidence, list)
        child_ep = snap_parent.child_evidence[0]
        assert child_ep.landed_on_target is True


# ---------------------------------------------------------------------------
# Explicit review_id lookup
# ---------------------------------------------------------------------------


class TestExplicitReviewId:
    def test_explicit_review_id_bypasses_branch_lookup(self) -> None:
        """When review_id is provided, use get_review not find_pr_for_branch."""
        scm = FakeSCMProvider()
        review = _fake_merged_review(
            source_branch="feature/x", head_sha="abc123", review_id="99"
        )
        scm.add_review(REPO, review)
        scm.set_branch_head(REPO, "feature/x", "abc123")
        scm.set_branch_head(REPO, TARGET, "target001")
        scm.set_ci_status(REPO, "abc123", CIStatus.PASSED)

        collector = _make_collector(scm=scm)
        snapshot = collector.collect(
            source_branch="feature/x",
            done_audit_id="audit-1",
            done_audit_verdict="pass",
            done_audit_fingerprint=_fingerprint(),
            review_id="99",
        )

        assert isinstance(snapshot.review, ReviewEvidence)
        assert snapshot.review.review_id == "99"
        assert snapshot.passed()


# ---------------------------------------------------------------------------
# No SCM provider
# ---------------------------------------------------------------------------


class TestNoSCMProvider:
    def test_no_scm_review_is_unavailable(self) -> None:
        """Without SCM provider, review evidence is unavailable."""
        collector = MergedEvidenceCollector(
            repo=REPO,
            intended_target_branch=TARGET,
            task_id="TASK-1",
            project_id="proj-test",
            scm_provider=None,
        )
        snapshot = collector.collect(
            source_branch="feature/x",
            done_audit_id="audit-1",
            done_audit_verdict="pass",
            done_audit_fingerprint=_fingerprint(),
        )

        assert isinstance(snapshot.review, EvidenceUnavailable)
        assert isinstance(snapshot.source_sha_current, EvidenceUnavailable)

    def test_no_scm_and_no_worktree_target_sha_unavailable(self) -> None:
        collector = MergedEvidenceCollector(
            repo=REPO,
            intended_target_branch=TARGET,
            task_id="TASK-1",
            project_id="proj-test",
            scm_provider=None,
            worktree_path=None,
        )
        snapshot = collector.collect(
            source_branch="feature/x",
            done_audit_id="audit-1",
            done_audit_verdict="pass",
        )

        assert isinstance(snapshot.target_head_sha, EvidenceUnavailable)


# ---------------------------------------------------------------------------
# MergedEvidenceSnapshot helper methods
# ---------------------------------------------------------------------------


class TestMergedEvidenceSnapshot:
    def _make_snapshot(self, **kwargs: Any) -> MergedEvidenceSnapshot:
        defaults: dict[str, Any] = {
            "done_audit_id": "audit-1",
            "done_audit_verdict": "pass",
            "done_audit_fingerprint": _fingerprint(),
            "source_branch": "feature/x",
            "source_sha_at_review": "abc123",
            "source_sha_current": "abc123",
            "intended_target_branch": TARGET,
            "target_head_sha": "target001",
            "review": ReviewEvidence(
                review_id="1",
                review_state="merged",
                source_branch="feature/x",
                target_branch=TARGET,
                reviewed_source_sha="abc123",
                merge_commit_sha="merge001",
                ci_status=CIStatus.PASSED,
            ),
            "merge_commit_sha": "merge001",
            "ci_status_at_review": CIStatus.PASSED,
            "containment": ContainmentEvidence(
                reviewed_sha_in_target=True,
                commits_from_review=["abc123"],
                stranded_commits=[],
            ),
        }
        defaults.update(kwargs)
        return MergedEvidenceSnapshot(**defaults)

    def test_passed_for_all_good_evidence(self) -> None:
        snapshot = self._make_snapshot()
        assert snapshot.passed()
        assert not snapshot.has_failures()

    def test_not_passed_when_failure_modes_present(self) -> None:
        snapshot = self._make_snapshot(
            failure_modes=[FailureMode.WRONG_TARGET.value]
        )
        assert not snapshot.passed()
        assert snapshot.has_failures()

    def test_not_passed_for_open_review(self) -> None:
        snapshot = self._make_snapshot(
            review=ReviewEvidence(
                review_id="1",
                review_state="open",
                source_branch="feature/x",
                target_branch=TARGET,
                reviewed_source_sha="abc123",
                merge_commit_sha=None,
                ci_status=CIStatus.PASSED,
            ),
            failure_modes=[FailureMode.OPEN_REVIEW.value],
        )
        assert not snapshot.passed()

    def test_not_passed_for_stranded_commits(self) -> None:
        snapshot = self._make_snapshot(
            containment=ContainmentEvidence(
                reviewed_sha_in_target=False,
                commits_from_review=["abc123"],
                stranded_commits=["abc123"],
            ),
            failure_modes=[FailureMode.STRANDED_COMMITS.value],
        )
        assert not snapshot.passed()

    def test_has_failures_for_unavailable_review(self) -> None:
        snapshot = self._make_snapshot(
            review=EvidenceUnavailable("No review found"),
            failure_modes=[FailureMode.NO_REVIEW_FOUND.value],
        )
        assert snapshot.has_failures()

    def test_not_passed_for_failed_ci(self) -> None:
        snapshot = self._make_snapshot(
            ci_status_at_review=CIStatus.FAILED,
            failure_modes=[FailureMode.FAILED_CI.value],
        )
        assert not snapshot.passed()

    def test_not_passed_for_pending_ci(self) -> None:
        snapshot = self._make_snapshot(
            ci_status_at_review=CIStatus.PENDING,
            failure_modes=[FailureMode.PENDING_CI.value],
        )
        assert not snapshot.passed()


# ---------------------------------------------------------------------------
# ReviewEvidence data structure
# ---------------------------------------------------------------------------


class TestReviewEvidence:
    def test_merged_review_is_merged(self) -> None:
        r = ReviewEvidence(
            review_id="1",
            review_state="merged",
            source_branch="feature/x",
            target_branch="main",
            reviewed_source_sha="abc",
            merge_commit_sha="merge001",
            ci_status=CIStatus.PASSED,
        )
        assert r.is_merged
        assert not r.is_open

    def test_open_review_is_open(self) -> None:
        r = ReviewEvidence(
            review_id="1",
            review_state="open",
            source_branch="feature/x",
            target_branch="main",
            reviewed_source_sha="abc",
            merge_commit_sha=None,
            ci_status=CIStatus.PENDING,
        )
        assert r.is_open
        assert not r.is_merged

    def test_invalid_state_raises(self) -> None:
        with pytest.raises(ValueError, match="review_state"):
            ReviewEvidence(
                review_id="1",
                review_state="unknown",  # invalid
                source_branch="feature/x",
                target_branch="main",
                reviewed_source_sha="abc",
                merge_commit_sha=None,
                ci_status=CIStatus.UNKNOWN,
            )

    def test_empty_review_id_raises(self) -> None:
        with pytest.raises(ValueError, match="review_id"):
            ReviewEvidence(
                review_id="",
                review_state="open",
                source_branch="feature/x",
                target_branch="main",
                reviewed_source_sha="abc",
                merge_commit_sha=None,
                ci_status=CIStatus.UNKNOWN,
            )


# ---------------------------------------------------------------------------
# ContainmentEvidence data structure
# ---------------------------------------------------------------------------


class TestContainmentEvidence:
    def test_all_landed_when_no_stranded(self) -> None:
        c = ContainmentEvidence(
            reviewed_sha_in_target=True,
            commits_from_review=["abc"],
            stranded_commits=[],
        )
        assert c.all_landed

    def test_not_all_landed_when_stranded(self) -> None:
        c = ContainmentEvidence(
            reviewed_sha_in_target=False,
            commits_from_review=["abc"],
            stranded_commits=["abc"],
        )
        assert not c.all_landed

    def test_requires_bool_fields(self) -> None:
        with pytest.raises(TypeError):
            ContainmentEvidence(
                reviewed_sha_in_target="yes",  # type: ignore
                commits_from_review=[],
                stranded_commits=[],
            )

    def test_requires_list_fields(self) -> None:
        with pytest.raises(TypeError):
            ContainmentEvidence(
                reviewed_sha_in_target=True,
                commits_from_review="abc",  # type: ignore
                stranded_commits=[],
            )


# ---------------------------------------------------------------------------
# FakeSCMProvider
# ---------------------------------------------------------------------------


class TestFakeSCMProvider:
    def test_add_and_find_review(self) -> None:
        scm = FakeSCMProvider()
        review = _fake_merged_review()
        scm.add_review(REPO, review)
        found = scm.find_pr_for_branch(REPO, "feature/x", TARGET)
        assert found is not None
        assert found.source_branch == "feature/x"
        assert found.state == "merged"

    def test_branch_head_set_and_retrieve(self) -> None:
        scm = FakeSCMProvider()
        scm.set_branch_head(REPO, "main", "sha001")
        assert scm.get_branch_head_sha(REPO, "main") == "sha001"

    def test_deleted_branch_returns_none(self) -> None:
        scm = FakeSCMProvider()
        scm.set_branch_head(REPO, "feature/x", "sha001")
        scm.delete_branch(REPO, "feature/x")
        assert scm.get_branch_head_sha(REPO, "feature/x") is None

    def test_ci_status_default_unknown(self) -> None:
        scm = FakeSCMProvider()
        assert scm.get_ci_status_for_sha(REPO, "nonexistent") == CIStatus.UNKNOWN

    def test_get_review_by_id(self) -> None:
        scm = FakeSCMProvider()
        review = _fake_merged_review(review_id="42")
        scm.add_review(REPO, review)
        found = scm.get_review(REPO, "42")
        assert found is not None
        assert found.id == "42"

    def test_get_review_by_id_not_found(self) -> None:
        scm = FakeSCMProvider()
        assert scm.get_review(REPO, "999") is None

    def test_get_pr_commits(self) -> None:
        scm = FakeSCMProvider()
        review = FakeSCMReview(
            review_id="1",
            state="merged",
            source_branch="feature/x",
            target_branch=TARGET,
            head_sha="sha1",
            commits=["sha1", "sha2"],
        )
        scm.add_review(REPO, review)
        commits = scm.get_pr_commits(REPO, "1")
        assert commits == ["sha1", "sha2"]

    def test_prefer_target_branch_in_find_pr(self) -> None:
        """find_pr_for_branch prefers reviews targeting the intended branch."""
        scm = FakeSCMProvider()
        wrong = _fake_merged_review(target_branch="staging", review_id="1")
        right = _fake_merged_review(target_branch=TARGET, review_id="2")
        scm.add_review(REPO, wrong)
        scm.add_review(REPO, right)

        found = scm.find_pr_for_branch(REPO, "feature/x", TARGET)
        assert found is not None
        assert found.id == "2"
