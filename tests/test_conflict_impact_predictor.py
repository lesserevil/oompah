"""Tests for conflict_impact_predictor (oompah-zlz_2-vm1p.1).

Uses real git repos in tmp dirs to exercise git merge-tree end-to-end.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from oompah.cache import TTLCache
from oompah.conflict_impact_predictor import (
    ConflictImpactPredictor,
    ConflictImpactResult,
    ConflictPrediction,
    _check_conflict,
    _resolve_head_sha,
)


# ---------------------------------------------------------------------------
# Helpers — create a git repo with branches
# ---------------------------------------------------------------------------

def _git(*args: str, cwd: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git"] + list(args),
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )


def _make_repo(tmp_path: Path) -> str:
    """Create a bare-bones git repo with main + initial commit."""
    repo = str(tmp_path / "repo")
    os.makedirs(repo, exist_ok=True)
    _git("init", "-b", "main", cwd=repo)
    _git("config", "user.email", "test@test.com", cwd=repo)
    _git("config", "user.name", "Test", cwd=repo)
    (Path(repo) / "README.md").write_text("hello\n")
    _git("add", ".", cwd=repo)
    _git("commit", "-m", "initial", cwd=repo)
    return repo


def _create_branch(repo: str, branch: str, files: dict[str, str], base: str = "main") -> None:
    """Create a branch from *base* with given file contents."""
    _git("checkout", base, cwd=repo)
    _git("checkout", "-b", branch, cwd=repo)
    for name, content in files.items():
        (Path(repo) / name).write_text(content)
    _git("add", ".", cwd=repo)
    _git("commit", "-m", f"work on {branch}", cwd=repo)


def _create_branch_no_commit(repo: str, branch: str, base: str = "main") -> None:
    """Create a branch that shares a commit with base (no new commits)."""
    _git("checkout", base, cwd=repo)
    _git("checkout", "-b", branch, cwd=repo)


# ---------------------------------------------------------------------------
# Test _resolve_head_sha
# ---------------------------------------------------------------------------

class TestResolveHeadSha:
    def test_valid_branch(self, tmp_path: Path):
        repo = _make_repo(tmp_path)
        _create_branch(repo, "feature/a", {"a.txt": "A"})
        sha, err = _resolve_head_sha(repo, "feature/a")
        assert not err
        assert len(sha) == 40

    def test_valid_main(self, tmp_path: Path):
        repo = _make_repo(tmp_path)
        sha, err = _resolve_head_sha(repo, "main")
        assert not err
        assert len(sha) == 40

    def test_nonexistent_branch(self, tmp_path: Path):
        repo = _make_repo(tmp_path)
        sha, err = _resolve_head_sha(repo, "nonexistent")
        assert sha == ""
        assert err

    def test_invalid_repo(self, tmp_path: Path):
        sha, err = _resolve_head_sha("/no/such/repo", "main")
        assert sha == ""
        assert err


# ---------------------------------------------------------------------------
# Test _check_conflict
# ---------------------------------------------------------------------------

class TestCheckConflict:
    def test_no_conflict_different_files(self, tmp_path: Path):
        """Merging branches that touch different files has no conflict."""
        repo = _make_repo(tmp_path)
        _create_branch(repo, "branch-a", {"a.txt": "content A"})
        _create_branch(repo, "branch-b", {"b.txt": "content B"})
        a_sha, _ = _resolve_head_sha(repo, "branch-a")
        b_sha, _ = _resolve_head_sha(repo, "branch-b")
        has_conflict, files, err = _check_conflict(repo, a_sha, b_sha)
        assert not err
        assert not has_conflict
        assert not files

    def test_conflict_same_file(self, tmp_path: Path):
        """Merging branches that modify the same file line produces a conflict."""
        repo = _make_repo(tmp_path)
        (Path(repo) / "shared.txt").write_text("line1\nline2\nline3\n")
        _git("add", ".", cwd=repo)
        _git("commit", "-m", "add shared", cwd=repo)
        _create_branch(repo, "branch-a", {"shared.txt": "line1\nmodified A\nline3\n"})
        _create_branch(repo, "branch-b", {"shared.txt": "line1\nmodified B\nline3\n"})
        a_sha, _ = _resolve_head_sha(repo, "branch-a")
        b_sha, _ = _resolve_head_sha(repo, "branch-b")
        has_conflict, files, err = _check_conflict(repo, a_sha, b_sha)
        assert not err
        assert has_conflict
        assert "shared.txt" in files

    def test_no_conflict_no_error_empty_error(self, tmp_path: Path):
        """On clean merge, error is empty string."""
        repo = _make_repo(tmp_path)
        _create_branch(repo, "x", {"x.txt": "x"})
        x_sha, _ = _resolve_head_sha(repo, "x")
        main_sha, _ = _resolve_head_sha(repo, "main")
        _, _, err = _check_conflict(repo, main_sha, x_sha)
        assert err == ""


# ---------------------------------------------------------------------------
# Test ConflictImpactPredictor.predict
# ---------------------------------------------------------------------------

class TestConflictImpactPredictorPredict:
    def test_empty_other_branches(self):
        """Empty other_branches returns score 0 immediately."""
        p = ConflictImpactPredictor()
        result = p.predict("/any/path", "main", [])
        assert result.score == 0
        assert result.total_checked == 0
        assert not result.error

    def test_clean_merge_no_conflicts(self, tmp_path: Path):
        """Different-file branches produce score 0."""
        repo = _make_repo(tmp_path)
        _create_branch(repo, "feature/a", {"a.txt": "A"})
        _create_branch(repo, "feature/b", {"b.txt": "B"})
        p = ConflictImpactPredictor()
        result = p.predict(repo, "feature/a", ["feature/b"])
        assert result.score == 0
        assert result.total_checked == 1

    def test_conflict_detected(self, tmp_path: Path):
        """Same-file branches produce score > 0."""
        repo = _make_repo(tmp_path)
        (Path(repo) / "shared.txt").write_text("line1\nline2\nline3\n")
        _git("add", ".", cwd=repo)
        _git("commit", "-m", "add shared", cwd=repo)
        _create_branch(repo, "feature/a", {"shared.txt": "line1\ndiverge A\nline3\n"})
        _create_branch(repo, "feature/b", {"shared.txt": "line1\ndiverge B\nline3\n"})
        p = ConflictImpactPredictor()
        result = p.predict(repo, "feature/a", ["feature/b"])
        assert result.score == 1
        assert result.total_checked == 1
        assert result.predictions[0].has_conflict
        assert "shared.txt" in result.predictions[0].conflicting_files

    def test_multiple_branches_mixed(self, tmp_path: Path):
        """Score counts only conflicting branches."""
        repo = _make_repo(tmp_path)
        (Path(repo) / "shared.txt").write_text("line1\nline2\nline3\n")
        _git("add", ".", cwd=repo)
        _git("commit", "-m", "add shared", cwd=repo)
        # feature/a conflicts with feature/b, not with feature/c
        _create_branch(repo, "feature/a", {"shared.txt": "line1\ndiverge A\nline3\n"})
        _create_branch(repo, "feature/b", {"shared.txt": "line1\ndiverge B\nline3\n"})
        _create_branch(repo, "feature/c", {"c_only.txt": "C"})
        p = ConflictImpactPredictor()
        result = p.predict(repo, "feature/a", ["feature/b", "feature/c"])
        assert result.score == 1
        assert result.total_checked == 2

    def test_self_comparison_skipped(self, tmp_path: Path):
        """Target branch listed in other_branches is skipped."""
        repo = _make_repo(tmp_path)
        _create_branch(repo, "feature/a", {"a.txt": "A"})
        p = ConflictImpactPredictor()
        result = p.predict(repo, "feature/a", ["feature/a"])
        assert result.total_checked == 0
        assert result.score == 0

    def test_nonexistent_branch_error(self, tmp_path: Path):
        """Nonexistent other branch produces an error prediction, not score."""
        repo = _make_repo(tmp_path)
        _create_branch(repo, "feature/a", {"a.txt": "A"})
        p = ConflictImpactPredictor()
        result = p.predict(repo, "feature/a", ["feature/ghost"])
        assert result.total_checked == 1
        assert result.score == 0
        assert result.predictions[0].error

    def test_nonexistent_target_error(self, tmp_path: Path):
        """Nonexistent target branch returns error in result."""
        p = ConflictImpactPredictor()
        result = p.predict("/any/path", "does-not-exist", ["other"])
        assert result.error

    def test_conflicting_predictions_subset(self, tmp_path: Path):
        """conflicting_predictions contains only conflicting entries."""
        repo = _make_repo(tmp_path)
        (Path(repo) / "shared.txt").write_text("line1\nline2\nline3\n")
        _git("add", ".", cwd=repo)
        _git("commit", "-m", "add shared", cwd=repo)
        _create_branch(repo, "feature/a", {"shared.txt": "line1\ndiverge A\nline3\n"})
        _create_branch(repo, "feature/b", {"shared.txt": "line1\ndiverge B\nline3\n"})
        _create_branch(repo, "feature/c", {"c_only.txt": "C"})
        p = ConflictImpactPredictor()
        result = p.predict(repo, "feature/a", ["feature/b", "feature/c"])
        assert len(result.conflicting_predictions) == 1
        assert result.conflicting_predictions[0].branch == "feature/b"


# ---------------------------------------------------------------------------
# Test caching
# ---------------------------------------------------------------------------

class TestConflictImpactPredictorCaching:
    def test_cache_hit(self, tmp_path: Path):
        """Second call with same branches uses cache."""
        repo = _make_repo(tmp_path)
        _create_branch(repo, "feature/a", {"a.txt": "A"})
        _create_branch(repo, "feature/b", {"b.txt": "B"})
        cache = TTLCache()
        p = ConflictImpactPredictor(cache=cache)
        p.predict(repo, "feature/a", ["feature/b"])
        # Verify cache has entry
        a_sha, _ = _resolve_head_sha(repo, "feature/a")
        b_sha, _ = _resolve_head_sha(repo, "feature/b")
        key = f"cip:{repo}:{a_sha}:{b_sha}"
        assert cache.get(key) is not None

    def test_cache_invalidation_on_clear(self, tmp_path: Path):
        """clear() empties all predictions."""
        repo = _make_repo(tmp_path)
        _create_branch(repo, "feature/a", {"a.txt": "A"})
        _create_branch(repo, "feature/b", {"b.txt": "B"})
        cache = TTLCache()
        p = ConflictImpactPredictor(cache=cache)
        p.predict(repo, "feature/a", ["feature/b"])
        p.clear()
        a_sha, _ = _resolve_head_sha(repo, "feature/a")
        b_sha, _ = _resolve_head_sha(repo, "feature/b")
        key = f"cip:{repo}:{a_sha}:{b_sha}"
        assert cache.get(key) is None


# ---------------------------------------------------------------------------
# Test to_dict serialization
# ---------------------------------------------------------------------------

class TestConflictImpactResultToDict:
    def test_serialization(self):
        r = ConflictImpactResult(
            target_branch="feature/a",
            score=1,
            total_checked=2,
            predictions=[
                ConflictPrediction(branch="b", head_sha="abc123", has_conflict=True, conflicting_files=["x.txt"]),
                ConflictPrediction(branch="c", head_sha="def456", has_conflict=False),
            ],
            conflicting_predictions=[
                ConflictPrediction(branch="b", head_sha="abc123", has_conflict=True, conflicting_files=["x.txt"]),
            ],
        )
        d = r.to_dict()
        assert d["target_branch"] == "feature/a"
        assert d["score"] == 1
        assert d["total_checked"] == 2
        assert len(d["predictions"]) == 2
        assert d["predictions"][0]["has_conflict"] is True
        assert d["predictions"][0]["conflicting_files"] == ["x.txt"]
        assert d["predictions"][1]["has_conflict"] is False
