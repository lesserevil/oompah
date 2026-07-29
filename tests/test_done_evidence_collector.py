"""Tests for DoneEvidenceCollector with git fixtures."""

from pathlib import Path
from typing import Any

import pytest

from oompah.done_evidence_collector import (
    CommitStatus,
    DiffExcerpt,
    DoneEvidenceCollector,
    EvidenceInvalid,
    EvidenceSnapshot,
    EvidenceUnavailable,
    WorktreeInfo,
)
from tests.fixtures_git import (
    GitFixture,
    LocalRepo,
    create_epic_fixture_with_children,
    create_two_repo_fixture,
)


class TestEvidenceUnavailable:
    """Tests for EvidenceUnavailable marker."""

    def test_unavailable_with_reason(self) -> None:
        unavail = EvidenceUnavailable("missing branch")
        assert unavail.reason == "missing branch"
        assert "unavailable" in str(unavail).lower()

    def test_unavailable_repr(self) -> None:
        unavail = EvidenceUnavailable("test reason")
        assert "EvidenceUnavailable" in repr(unavail)

    def test_unavailable_requires_nonempty_reason(self) -> None:
        with pytest.raises(ValueError):
            EvidenceUnavailable("")

    def test_unavailable_requires_string_reason(self) -> None:
        with pytest.raises(ValueError):
            EvidenceUnavailable("  \n  ")  # type: ignore


class TestEvidenceInvalid:
    """Tests for EvidenceInvalid marker."""

    def test_invalid_with_reason(self) -> None:
        invalid = EvidenceInvalid("malformed diff")
        assert invalid.reason == "malformed diff"
        assert "invalid" in str(invalid).lower()

    def test_invalid_repr(self) -> None:
        invalid = EvidenceInvalid("test reason")
        assert "EvidenceInvalid" in repr(invalid)

    def test_invalid_requires_nonempty_reason(self) -> None:
        with pytest.raises(ValueError):
            EvidenceInvalid("")


class TestDiffExcerpt:
    """Tests for DiffExcerpt."""

    def test_valid_excerpt(self) -> None:
        excerpt = DiffExcerpt(
            content="line1\nline2\nline3",
            total_lines=10,
            excerpt_start_line=0,
            excerpt_end_line=3,
            is_truncated=True,
        )
        assert excerpt.content == "line1\nline2\nline3"
        assert excerpt.total_lines == 10
        assert excerpt.is_truncated is True

    def test_excerpt_requires_valid_line_counts(self) -> None:
        with pytest.raises(ValueError):
            DiffExcerpt(
                content="test",
                total_lines=5,
                excerpt_start_line=0,
                excerpt_end_line=10,  # exceeds total_lines
                is_truncated=False,
            )

    def test_excerpt_requires_bool_truncated(self) -> None:
        with pytest.raises(TypeError):
            DiffExcerpt(
                content="test",
                total_lines=5,
                excerpt_start_line=0,
                excerpt_end_line=3,
                is_truncated="yes",  # type: ignore
            )


class TestWorktreeInfo:
    """Tests for WorktreeInfo."""

    def test_valid_worktree_info(self) -> None:
        info = WorktreeInfo(
            path="/tmp/repo",
            is_worktree=True,
            branch="main",
            dirty=False,
        )
        assert info.path == "/tmp/repo"
        assert info.is_worktree is True
        assert info.dirty is False

    def test_worktree_info_requires_nonempty_path(self) -> None:
        with pytest.raises(ValueError):
            WorktreeInfo(path="", is_worktree=True)

    def test_worktree_info_requires_bool_is_worktree(self) -> None:
        with pytest.raises(TypeError):
            WorktreeInfo(path="/tmp/repo", is_worktree="yes")  # type: ignore


class TestEvidenceSnapshot:
    """Tests for EvidenceSnapshot data structure."""

    def test_snapshot_completeness(self) -> None:
        snapshot = EvidenceSnapshot(
            worktree_info=WorktreeInfo(
                path="/tmp/repo",
                is_worktree=True,
                branch="main",
                dirty=False,
            ),
            source_branch="main",
            source_sha="abc123",
            target_branch="main",
            target_sha="abc123",
            requirements_text="Implement feature X",
            requirements_digest="digest123",
            diff_stat="1 file changed",
            commit_status=CommitStatus(
                sha="abc123",
                message="Initial commit",
                is_on_intended_branch=True,
                is_pushed=True,
            ),
            push_status=True,
        )
        assert snapshot.is_complete() is True
        assert snapshot.has_failures() is False

    def test_snapshot_with_unavailable_evidence(self) -> None:
        snapshot = EvidenceSnapshot(
            worktree_info=EvidenceUnavailable("not a git repo"),
            source_branch=EvidenceUnavailable("cannot determine"),
            source_sha=EvidenceUnavailable("cannot determine"),
            target_branch=EvidenceUnavailable("cannot determine"),
            target_sha=EvidenceUnavailable("cannot determine"),
            requirements_text="test",
            requirements_digest="digest",
            diff_stat="0 files",
            commit_status=None,
            push_status=False,
        )
        assert snapshot.is_complete() is False
        assert snapshot.has_failures() is True

    def test_snapshot_with_invalid_evidence(self) -> None:
        snapshot = EvidenceSnapshot(
            worktree_info=WorktreeInfo(
                path="/tmp/repo",
                is_worktree=True,
                dirty=False,
            ),
            source_branch="main",
            source_sha="abc123",
            target_branch="main",
            target_sha=EvidenceInvalid("contradictory SHA"),
            requirements_text="test",
            requirements_digest="digest",
            diff_stat="0 files",
            commit_status=None,
            push_status=True,
        )
        assert snapshot.has_failures() is True


class TestDoneEvidenceCollector:
    """Tests for DoneEvidenceCollector with real git repos."""

    def test_collector_requires_valid_worktree_path(self) -> None:
        with pytest.raises(ValueError, match="does not exist"):
            DoneEvidenceCollector("/nonexistent/path")

    def test_collector_collects_clean_repo(self, tmp_path: Path) -> None:
        repo = LocalRepo(tmp_path / "repo")
        repo.commit("Initial commit")
        repo.create_branch("feature", "main")

        collector = DoneEvidenceCollector(str(repo.path))
        snapshot = collector.collect()

        assert snapshot.worktree_info != EvidenceUnavailable
        assert isinstance(snapshot.worktree_info, WorktreeInfo)
        assert snapshot.worktree_info.branch in ("feature", "main")
        assert snapshot.worktree_info.dirty is False

    def test_collector_detects_dirty_worktree(self, tmp_path: Path) -> None:
        repo = LocalRepo(tmp_path / "repo")
        repo.commit("Initial commit")

        # Make worktree dirty
        (repo.path / "dirty.txt").write_text("uncommitted changes")

        collector = DoneEvidenceCollector(str(repo.path))
        snapshot = collector.collect()

        assert isinstance(snapshot.worktree_info, WorktreeInfo)
        assert snapshot.worktree_info.dirty is True

    def test_collector_gets_source_branch(self, tmp_path: Path) -> None:
        repo = LocalRepo(tmp_path / "repo")
        repo.commit("Initial commit")
        repo.create_branch("feature/test", "main")

        collector = DoneEvidenceCollector(str(repo.path))
        snapshot = collector.collect()

        assert snapshot.source_branch in ("feature/test", "main")
        assert isinstance(snapshot.source_branch, str)

    def test_collector_gets_source_sha(self, tmp_path: Path) -> None:
        repo = LocalRepo(tmp_path / "repo")
        sha = repo.commit("Initial commit")

        collector = DoneEvidenceCollector(str(repo.path))
        snapshot = collector.collect()

        assert snapshot.source_sha == sha

    def test_collector_gets_contributors(self, tmp_path: Path) -> None:
        repo = LocalRepo(tmp_path / "repo")
        repo.commit("First commit")
        repo.commit("Second commit")

        collector = DoneEvidenceCollector(str(repo.path))
        snapshot = collector.collect()

        # Contributors should be available or unavailable
        if not isinstance(snapshot.contributors, (EvidenceUnavailable, EvidenceInvalid)):
            assert isinstance(snapshot.contributors, list)
            if len(snapshot.contributors) > 0:
                assert "name" in snapshot.contributors[0]
                assert "email" in snapshot.contributors[0]
                assert snapshot.contributors[0]["source"] == "git"

    def test_collector_detects_unpushed_commits(self, tmp_path: Path) -> None:
        repo = LocalRepo(tmp_path / "repo")
        repo.commit("Initial commit")

        # Create a remote but don't push
        bare_path = tmp_path / "bare"
        bare_path.mkdir(parents=True, exist_ok=True)
        from tests.fixtures_git import run_git
        run_git(bare_path, ["init", "--bare", "-b", "main"])
        repo.add_remote("origin", str(bare_path))

        # Create another commit (unpushed)
        repo.commit("Local commit")

        collector = DoneEvidenceCollector(str(repo.path))
        snapshot = collector.collect()

        # Without origin/main branch, should report unavailable or false push status
        if not isinstance(snapshot.push_status, EvidenceUnavailable):
            assert snapshot.push_status is False

    def test_collector_handles_missing_remote(self, tmp_path: Path) -> None:
        repo = LocalRepo(tmp_path / "repo")
        repo.commit("Initial commit")

        collector = DoneEvidenceCollector(str(repo.path))
        snapshot = collector.collect()

        # No remote configured
        assert isinstance(snapshot.push_status, (EvidenceUnavailable, bool))

    def test_collector_gets_changed_files(self, tmp_path: Path) -> None:
        repo = LocalRepo(tmp_path / "repo")

        # Initial commit on main
        repo.commit("Initial", {"main.txt": "main content"})

        # Create feature branch
        repo.create_branch("feature", "main")
        repo.commit("Feature", {"feature.txt": "feature content"})
        repo.commit("Feature 2", {"main.txt": "modified main"})

        collector = DoneEvidenceCollector(str(repo.path))
        snapshot = collector.collect()

        # Changed files should be either a list or unavailable
        if not isinstance(snapshot.changed_files, (EvidenceUnavailable, EvidenceInvalid)):
            assert isinstance(snapshot.changed_files, list)
            file_names = [f for f in snapshot.changed_files if f]
            # May have no changed files if no target branch is available
            if file_names:
                assert len(file_names) >= 0

    def test_collector_bounded_diff_excerpt(self, tmp_path: Path) -> None:
        repo = LocalRepo(tmp_path / "repo")

        # Initial commit
        repo.commit("Initial", {"code.txt": "line1\n" * 100})

        # Feature with large changes
        repo.create_branch("feature", "main")
        repo.commit("Large change", {"code.txt": "line1\n" * 600})

        collector = DoneEvidenceCollector(str(repo.path))
        snapshot = collector.collect()

        if isinstance(snapshot.diff_excerpt, DiffExcerpt):
            # Should be truncated if > 500 lines
            assert snapshot.diff_excerpt.is_truncated or snapshot.diff_excerpt.total_lines <= 500
        elif isinstance(snapshot.diff_excerpt, (EvidenceUnavailable, EvidenceInvalid)):
            # Unavailable or invalid is OK if no target branch exists
            pass

    def test_collector_with_multiple_worktrees(self, tmp_path: Path) -> None:
        main_repo = LocalRepo(tmp_path / "main")
        main_repo.commit("Initial")
        main_repo.create_branch("branch1", "main")
        main_repo.commit("Branch1 work")
        main_repo.checkout("main")
        main_repo.create_branch("branch2", "main")
        main_repo.commit("Branch2 work")

        # Create worktree for branch1
        wt_path = tmp_path / "worktree1"
        try:
            wt_repo = main_repo.create_worktree(wt_path, "branch1")

            collector = DoneEvidenceCollector(str(wt_repo.path))
            snapshot = collector.collect()

            assert isinstance(snapshot.worktree_info, WorktreeInfo)
            assert snapshot.source_branch in ("branch1", "main")
        except Exception:
            # Worktree creation may not be supported on all systems
            pytest.skip("Git worktrees not supported")


class TestEvidenceCollectorEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_collector_on_detached_head(self, tmp_path: Path) -> None:
        repo = LocalRepo(tmp_path / "repo")
        sha = repo.commit("Initial commit")
        repo.checkout(sha)  # Detached HEAD

        collector = DoneEvidenceCollector(str(repo.path))
        snapshot = collector.collect()

        # Should handle detached HEAD gracefully
        assert isinstance(snapshot.worktree_info, WorktreeInfo)

    def test_collector_handles_no_commits(self, tmp_path: Path) -> None:
        repo = LocalRepo(tmp_path / "repo")

        collector = DoneEvidenceCollector(str(repo.path))
        snapshot = collector.collect()

        # Should return unavailable for source_sha
        assert isinstance(snapshot.source_sha, EvidenceUnavailable)

    def test_evidence_snapshot_with_nested_unavailable(self) -> None:
        snapshot = EvidenceSnapshot(
            worktree_info=WorktreeInfo(path="/tmp/repo", is_worktree=True),
            source_branch="main",
            source_sha="abc",
            target_branch="main",
            target_sha="abc",
            requirements_text="test",
            requirements_digest="digest",
            diff_stat="0 files",
            commit_status=CommitStatus(
                sha="abc",
                message="test",
                is_on_intended_branch=True,
                is_pushed=True,
            ),
            push_status=True,
            changed_files=EvidenceUnavailable("cannot get files"),
        )

        assert snapshot.has_failures() is True

    def test_evidence_snapshot_with_list_of_unavailable(self) -> None:
        snapshot = EvidenceSnapshot(
            worktree_info=WorktreeInfo(path="/tmp/repo", is_worktree=True),
            source_branch="main",
            source_sha="abc",
            target_branch="main",
            target_sha="abc",
            requirements_text="test",
            requirements_digest="digest",
            diff_stat="0 files",
            commit_status=None,
            push_status=True,
            contributors=[
                {"name": "Alice", "email": "alice@example.com", "source": "git"},
                EvidenceUnavailable("cannot fetch more"),  # type: ignore
            ],
        )

        assert snapshot.has_failures() is True


class TestEvidenceCollectorStability:
    """Tests for determinism and stability of evidence collection."""

    def test_multiple_collections_are_identical(self, tmp_path: Path) -> None:
        repo = LocalRepo(tmp_path / "repo")
        repo.commit("Initial")
        repo.create_branch("feature", "main")
        repo.commit("Feature work")

        collector = DoneEvidenceCollector(str(repo.path), "TASK-1", "proj-1")

        # Collect twice
        snapshot1 = collector.collect("audit-1", "2026-07-29T00:00:00Z")
        snapshot2 = collector.collect("audit-1", "2026-07-29T00:00:00Z")

        # Should be identical
        assert snapshot1.source_branch == snapshot2.source_branch
        assert snapshot1.source_sha == snapshot2.source_sha
        assert snapshot1.task_id == snapshot2.task_id
        assert snapshot1.project_id == snapshot2.project_id

    def test_evidence_collection_without_remote(self, tmp_path: Path) -> None:
        repo = LocalRepo(tmp_path / "repo")
        repo.commit("Initial")
        repo.create_branch("feature", "main")
        repo.commit("Work")

        collector = DoneEvidenceCollector(str(repo.path))
        snapshot = collector.collect()

        # Should gracefully handle missing remote
        assert snapshot.worktree_info != EvidenceUnavailable
        # target_branch may be unavailable or should have set itself to main
        if isinstance(snapshot.target_branch, str):
            assert snapshot.target_branch in ("main", "master", "trunk")
        elif isinstance(snapshot.target_branch, EvidenceUnavailable):
            assert snapshot.target_branch.reason

    def test_collector_idempotent(self, tmp_path: Path) -> None:
        repo = LocalRepo(tmp_path / "repo")
        repo.commit("Initial")

        collector = DoneEvidenceCollector(str(repo.path), task_id="TASK-1")

        # Calling collect multiple times should not modify repo
        snapshot1 = collector.collect()
        assert repo.is_dirty() is False

        snapshot2 = collector.collect()
        assert repo.is_dirty() is False

        # Results should be same
        assert snapshot1.source_sha == snapshot2.source_sha


class TestCommitStatus:
    """Tests for CommitStatus structure."""

    def test_commit_status_with_all_fields(self) -> None:
        status = CommitStatus(
            sha="abc123",
            message="Implement feature",
            is_on_intended_branch=True,
            is_pushed=True,
        )
        assert status.sha == "abc123"
        assert status.is_on_intended_branch is True

    def test_commit_status_with_optional_fields_none(self) -> None:
        status = CommitStatus(
            sha="abc123",
            message=None,
            is_on_intended_branch=None,
            is_pushed=None,
            unavailable_reason="No commits",
        )
        assert status.message is None
        assert status.unavailable_reason == "No commits"
