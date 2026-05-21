"""Tests for epic branch staleness detection (oompah-zlz_2-82dr.1).

Covers the pure-function ``check_epic_branch_staleness()`` in
``oompah/epic_staleness.py``. Uses a real git repo fixture so the
git commands exercised by the function actually run.
"""

from __future__ import annotations

import os
import subprocess
import time

import pytest

from oompah.epic_staleness import StalenessResult, check_epic_branch_staleness


# ---------------------------------------------------------------------------
# Helpers: build a real git repo for testing
# ---------------------------------------------------------------------------


def _git(repo_path: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_path,
        capture_output=True,
        text=True,
        timeout=10,
    )


def _make_repo(tmp_path) -> str:
    """Create a git repo with 'main' as the initial branch."""
    repo = str(tmp_path / "repo")
    os.makedirs(repo)
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    return repo


def _commit(repo: str, msg: str, filename: str | None = None, content: str = "data"):
    """Create a commit with an optional file change."""
    if filename:
        path = os.path.join(repo, filename)
        with open(path, "w") as f:
            f.write(content)
        _git(repo, "add", filename)
    _git(repo, "commit", "-m", msg)
    time.sleep(0.01)  # ensure distinct commit timestamps


def _create_epic_branch(repo: str, branch_name: str, commits: int):
    """Create an epic branch with N commits off main."""
    _git(repo, "checkout", "-b", branch_name)
    for i in range(commits):
        _commit(repo, f"epic commit {i}", f"epic_file_{i}.txt")
    _git(repo, "checkout", "main")


# ---------------------------------------------------------------------------
# Test: Not stale when branch is up to date
# ---------------------------------------------------------------------------


class TestNotStaleWhenUpToDate:
    def test_no_commits_behind(self, tmp_path):
        repo = _make_repo(tmp_path)
        _commit(repo, "initial", "readme.txt")
        _create_epic_branch(repo, "epic-abc", 1)

        result = check_epic_branch_staleness(
            repo, "epic-abc", "main", threshold_commits=5
        )

        assert result.stale is False
        assert result.commits_behind == 0
        assert result.shared_files == ()
        assert result.error == ""
        assert result.threshold == 5

    def test_epic_ahead_of_main(self, tmp_path):
        """Epic branch has commits that main doesn't, but main hasn't moved past the merge-base."""
        repo = _make_repo(tmp_path)
        _commit(repo, "initial", "readme.txt")
        _create_epic_branch(repo, "epic-abc", 3)
        # main is at the merge-base, epic is ahead
        # commits_behind should be 0 (main hasn't moved past merge-base)

        result = check_epic_branch_staleness(
            repo, "epic-abc", "main", threshold_commits=5
        )

        assert result.stale is False
        assert result.commits_behind == 0


# ---------------------------------------------------------------------------
# Test: Stale when behind by threshold commits
# ---------------------------------------------------------------------------


class TestStaleByCommitThreshold:
    def test_stale_at_threshold(self, tmp_path):
        repo = _make_repo(tmp_path)
        _commit(repo, "initial", "readme.txt")
        _create_epic_branch(repo, "epic-abc", 1)
        # Add exactly 5 commits to main (threshold=5)
        for i in range(5):
            _commit(repo, f"main commit {i}", f"main_{i}.txt")

        result = check_epic_branch_staleness(
            repo, "epic-abc", "main", threshold_commits=5
        )

        assert result.stale is True
        assert result.commits_behind == 5
        assert result.threshold == 5

    def test_stale_above_threshold(self, tmp_path):
        repo = _make_repo(tmp_path)
        _commit(repo, "initial", "readme.txt")
        _create_epic_branch(repo, "epic-abc", 1)
        for i in range(10):
            _commit(repo, f"main commit {i}", f"main_{i}.txt")

        result = check_epic_branch_staleness(
            repo, "epic-abc", "main", threshold_commits=5
        )

        assert result.stale is True
        assert result.commits_behind == 10

    def test_not_stale_below_threshold(self, tmp_path):
        repo = _make_repo(tmp_path)
        _commit(repo, "initial", "readme.txt")
        _create_epic_branch(repo, "epic-abc", 1)
        for i in range(3):
            _commit(repo, f"main commit {i}", f"main_{i}.txt")

        result = check_epic_branch_staleness(
            repo, "epic-abc", "main", threshold_commits=5
        )

        assert result.stale is False
        assert result.commits_behind == 3


# ---------------------------------------------------------------------------
# Test: File overlap detection
# ---------------------------------------------------------------------------


class TestFileOverlap:
    def test_stale_by_file_overlap_with_enough_commits(self, tmp_path):
        """File overlap is checked when commits_behind >= threshold."""
        repo = _make_repo(tmp_path)
        _commit(repo, "initial", "shared.txt", "original")
        # Create epic branch that modifies shared.txt
        _git(repo, "checkout", "-b", "epic-abc")
        _commit(repo, "epic modifies shared", "shared.txt", "epic version")
        _git(repo, "checkout", "main")
        # Add 5 commits to main (meets threshold=5), last one touches shared
        for i in range(4):
            _commit(repo, f"main commit {i}", f"main_{i}.txt")
        _commit(repo, "main modifies shared", "shared.txt", "main version")

        result = check_epic_branch_staleness(
            repo, "epic-abc", "main", threshold_commits=5
        )

        assert result.stale is True
        assert result.commits_behind == 5
        assert "shared.txt" in result.shared_files

    def test_file_overlap_only_checked_at_threshold(self, tmp_path):
        """File overlap is NOT checked when commits_behind < threshold > 0."""
        repo = _make_repo(tmp_path)
        _commit(repo, "initial", "shared.txt", "original")
        _git(repo, "checkout", "-b", "epic-abc")
        _commit(repo, "epic modifies shared", "shared.txt", "epic version")
        _git(repo, "checkout", "main")
        # Only 1 commit to main (below threshold=5)
        _commit(repo, "main modifies shared", "shared.txt", "main version")

        result = check_epic_branch_staleness(
            repo, "epic-abc", "main", threshold_commits=5
        )

        # Fast-path skips file overlap when commits_behind < threshold
        assert result.stale is False
        assert result.commits_behind == 1
        assert result.shared_files == ()

    def test_no_file_overlap(self, tmp_path):
        """Commits touch different files, no staleness by overlap."""
        repo = _make_repo(tmp_path)
        _commit(repo, "initial", "readme.txt")
        _create_epic_branch(repo, "epic-abc", 1)  # epic_file_0.txt
        # Add commits to main that touch DIFFERENT files
        for i in range(3):
            _commit(repo, f"main {i}", f"other_{i}.txt")

        result = check_epic_branch_staleness(
            repo, "epic-abc", "main", threshold_commits=5
        )

        # Not stale: below threshold AND no file overlap
        assert result.stale is False
        assert result.commits_behind == 3
        assert result.shared_files == ()

    def test_multiple_shared_files(self, tmp_path):
        repo = _make_repo(tmp_path)
        _commit(repo, "initial", "a.txt", "orig")
        _commit(repo, "initial2", "b.txt", "orig")
        _git(repo, "checkout", "-b", "epic-abc")
        _commit(repo, "epic a", "a.txt", "epic")
        _commit(repo, "epic b", "b.txt", "epic")
        _git(repo, "checkout", "main")
        # Need >= threshold_commits to trigger file overlap check
        for i in range(8):
            _commit(repo, f"main padding {i}", f"pad_{i}.txt")
        _commit(repo, "main a", "a.txt", "main")
        _commit(repo, "main b", "b.txt", "main")

        result = check_epic_branch_staleness(
            repo, "epic-abc", "main", threshold_commits=10
        )

        assert result.stale is True
        assert result.commits_behind == 10
        assert "a.txt" in result.shared_files
        assert "b.txt" in result.shared_files


# ---------------------------------------------------------------------------
# Test: Threshold = 0 (disable commit-count trigger)
# ---------------------------------------------------------------------------


class TestZeroThreshold:
    def test_zero_threshold_no_overlap(self, tmp_path):
        """threshold=0 means commit count always triggers staleness."""
        repo = _make_repo(tmp_path)
        _commit(repo, "initial", "readme.txt")
        _create_epic_branch(repo, "epic-abc", 1)
        for i in range(20):
            _commit(repo, f"main {i}", f"main_{i}.txt")

        result = check_epic_branch_staleness(
            repo, "epic-abc", "main", threshold_commits=0
        )

        # threshold=0 → behind_by_commits is always True (0 <= 0)
        assert result.stale is True
        assert result.commits_behind == 20
        assert result.shared_files == ()

    def test_zero_threshold_with_overlap(self, tmp_path):
        repo = _make_repo(tmp_path)
        _commit(repo, "initial", "shared.txt", "orig")
        _git(repo, "checkout", "-b", "epic-abc")
        _commit(repo, "epic", "shared.txt", "epic")
        _git(repo, "checkout", "main")
        _commit(repo, "main", "shared.txt", "main")

        result = check_epic_branch_staleness(
            repo, "epic-abc", "main", threshold_commits=0
        )

        assert result.stale is True
        assert "shared.txt" in result.shared_files


# ---------------------------------------------------------------------------
# Test: Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def test_nonexistent_branch(self, tmp_path):
        repo = _make_repo(tmp_path)
        _commit(repo, "initial", "readme.txt")

        result = check_epic_branch_staleness(
            repo, "does-not-exist", "main", threshold_commits=5
        )

        assert result.stale is False
        assert result.error != ""

    def test_nonexistent_repo(self, tmp_path):
        """A non-existent repo path raises FileNotFoundError — the function
        does not catch OSError from subprocess.run when the cwd doesn't exist."""
        with pytest.raises(FileNotFoundError):
            check_epic_branch_staleness(
                str(tmp_path / "nope"), "main", "main", threshold_commits=5
            )


# ---------------------------------------------------------------------------
# Test: StalenessResult dataclass
# ---------------------------------------------------------------------------


class TestStalenessResult:
    def test_frozen(self):
        r = StalenessResult(
            stale=True, commits_behind=10, shared_files=("a.txt",), threshold=5
        )
        with pytest.raises(Exception):
            r.stale = False  # type: ignore

    def test_shared_files_is_tuple(self):
        r = StalenessResult(
            stale=False, commits_behind=0, shared_files=("x.txt", "y.txt"),
            threshold=5,
        )
        assert isinstance(r.shared_files, tuple)
