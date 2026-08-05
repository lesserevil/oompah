"""Tests for recovery snapshot object transfer (OOMPAH-817).

Verifies that recovery snapshots are durable across linked worktrees and
standalone clones by transferring snapshot objects to the authoritative
repository before publishing recovery refs.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from oompah.models import Project
from oompah.projects import (
    ProjectStore,
    _transfer_recovery_snapshot_objects,
)


@pytest.fixture
def temp_repos():
    """Create a temporary directory with authoritative repo and worktree."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create authoritative repository
        auth_repo = tmpdir / "auth"
        auth_repo.mkdir()
        subprocess.run(
            ["git", "init", "--initial-branch=main"],
            cwd=auth_repo,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=auth_repo,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=auth_repo,
            capture_output=True,
            check=True,
        )
        
        # Create initial commit in authoritative repo
        test_file = auth_repo / "test.txt"
        test_file.write_text("initial")
        subprocess.run(
            ["git", "add", "."],
            cwd=auth_repo,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=auth_repo,
            capture_output=True,
            check=True,
        )
        
        # Create a linked worktree (which has shared object database by default)
        worktree_path = tmpdir / "worktree"
        subprocess.run(
            ["git", "worktree", "add", str(worktree_path), "-b", "task/test"],
            cwd=auth_repo,
            capture_output=True,
            check=True,
        )
        
        # Configure worktree git
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=worktree_path,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=worktree_path,
            capture_output=True,
            check=True,
        )
        
        yield auth_repo, worktree_path


@pytest.fixture
def standalone_repos():
    """Create a standalone clone (with separate object database)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create authoritative repository
        auth_repo = tmpdir / "auth"
        auth_repo.mkdir()
        subprocess.run(
            ["git", "init", "--initial-branch=main", "--bare"],
            cwd=auth_repo,
            capture_output=True,
            check=True,
        )
        
        # Create a temporary central repo to push to
        central_repo = tmpdir / "central"
        central_repo.mkdir()
        subprocess.run(
            ["git", "init", "--initial-branch=main"],
            cwd=central_repo,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=central_repo,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=central_repo,
            capture_output=True,
            check=True,
        )
        
        # Create initial commit
        test_file = central_repo / "test.txt"
        test_file.write_text("initial")
        subprocess.run(
            ["git", "add", "."],
            cwd=central_repo,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=central_repo,
            capture_output=True,
            check=True,
        )
        
        # Push to bare repo
        subprocess.run(
            ["git", "remote", "add", "origin", str(auth_repo)],
            cwd=central_repo,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "push", "-u", "origin", "main"],
            cwd=central_repo,
            capture_output=True,
            check=True,
        )
        
        # Create standalone clone (will have separate object database)
        standalone = tmpdir / "standalone"
        subprocess.run(
            ["git", "clone", str(auth_repo), str(standalone)],
            cwd=tmpdir,
            capture_output=True,
            check=True,
        )
        
        # Configure standalone clone
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=standalone,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=standalone,
            capture_output=True,
            check=True,
        )
        
        yield auth_repo, standalone


def test_transfer_recovery_snapshot_objects_with_linked_worktree(temp_repos):
    """Test object transfer with linked worktree (shared object database)."""
    auth_repo, worktree_path = temp_repos
    
    # Create a new commit in the worktree
    test_file = worktree_path / "new_file.txt"
    test_file.write_text("new content")
    subprocess.run(
        ["git", "add", "."],
        cwd=worktree_path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "New commit in worktree"],
        cwd=worktree_path,
        capture_output=True,
        check=True,
    )
    
    # Get the commit SHA
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=worktree_path,
        capture_output=True,
        text=True,
        check=True,
    )
    commit_sha = result.stdout.strip()
    
    # Object should already exist in auth_repo (shared database)
    check = subprocess.run(
        ["git", "cat-file", "-e", commit_sha],
        cwd=auth_repo,
        capture_output=True,
        text=True,
        check=False,
    )
    # For linked worktree, object already exists
    is_redundant = check.returncode == 0
    
    # Transfer (should be redundant but still succeed)
    transferred = _transfer_recovery_snapshot_objects(
        commit_sha,
        worktree_path,
        auth_repo,
    )
    
    # Verify result
    if is_redundant:
        assert not transferred, "Should return False when object already exists"
    else:
        assert transferred, "Should return True when object was transferred"
    
    # Verify object is readable in auth_repo
    verify = subprocess.run(
        ["git", "cat-file", "-e", commit_sha],
        cwd=auth_repo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert verify.returncode == 0, "Object should be readable after transfer"


def test_transfer_recovery_snapshot_objects_with_standalone_clone(standalone_repos):
    """Test object transfer with standalone clone (separate object database)."""
    auth_repo, standalone = standalone_repos
    
    # Create a new commit in the standalone clone
    test_file = standalone / "new_file.txt"
    test_file.write_text("standalone content")
    subprocess.run(
        ["git", "add", "."],
        cwd=standalone,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "New commit in standalone"],
        cwd=standalone,
        capture_output=True,
        check=True,
    )
    
    # Get the commit SHA
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=standalone,
        capture_output=True,
        text=True,
        check=True,
    )
    commit_sha = result.stdout.strip()
    
    # Verify object does NOT exist in auth_repo yet
    check_before = subprocess.run(
        ["git", "cat-file", "-e", commit_sha],
        cwd=auth_repo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert check_before.returncode != 0, "Object should not exist in auth_repo before transfer"
    
    # Transfer the object
    transferred = _transfer_recovery_snapshot_objects(
        commit_sha,
        standalone,
        auth_repo,
    )
    
    # Should have transferred
    assert transferred, "Should return True when object was transferred"
    
    # Verify object is now readable in auth_repo
    check_after = subprocess.run(
        ["git", "cat-file", "-e", commit_sha],
        cwd=auth_repo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert check_after.returncode == 0, "Object should be readable in auth_repo after transfer"


def test_transfer_recovery_snapshot_objects_idempotent(standalone_repos):
    """Test that transferring the same object twice is idempotent."""
    auth_repo, standalone = standalone_repos
    
    # Create a commit in standalone
    test_file = standalone / "file1.txt"
    test_file.write_text("content1")
    subprocess.run(
        ["git", "add", "."],
        cwd=standalone,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "Commit 1"],
        cwd=standalone,
        capture_output=True,
        check=True,
    )
    
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=standalone,
        capture_output=True,
        text=True,
        check=True,
    )
    commit_sha = result.stdout.strip()
    
    # First transfer
    transferred1 = _transfer_recovery_snapshot_objects(
        commit_sha,
        standalone,
        auth_repo,
    )
    assert transferred1, "First transfer should succeed"
    
    # Second transfer should be idempotent (redundant)
    transferred2 = _transfer_recovery_snapshot_objects(
        commit_sha,
        standalone,
        auth_repo,
    )
    assert not transferred2, "Second transfer should be redundant"
    
    # Verify object still readable
    verify = subprocess.run(
        ["git", "cat-file", "-e", commit_sha],
        cwd=auth_repo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert verify.returncode == 0, "Object should still be readable"


def test_transfer_recovery_snapshot_objects_invalid_params():
    """Test that transfer fails gracefully with invalid parameters."""
    from oompah.projects import ProjectError
    
    # Test with missing SHA
    with pytest.raises(ProjectError, match="missing required parameters"):
        _transfer_recovery_snapshot_objects("", "/path", "/path")
    
    # Test with missing worktree path
    with pytest.raises(ProjectError, match="missing required parameters"):
        _transfer_recovery_snapshot_objects("abc123", "", "/path")
    
    # Test with missing repo path
    with pytest.raises(ProjectError, match="missing required parameters"):
        _transfer_recovery_snapshot_objects("abc123", "/path", "")


def test_transfer_recovery_snapshot_objects_nonexistent_worktree():
    """Test that transfer fails with clear error for nonexistent worktree."""
    from oompah.projects import ProjectError
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create auth repo
        auth_repo = tmpdir / "auth"
        auth_repo.mkdir()
        subprocess.run(
            ["git", "init"],
            cwd=auth_repo,
            capture_output=True,
            check=True,
        )
        
        # Try to transfer with nonexistent worktree
        nonexistent = tmpdir / "nonexistent"
        with pytest.raises(ProjectError):
            _transfer_recovery_snapshot_objects(
                "abc123def456",
                nonexistent,
                auth_repo,
            )


def test_transfer_recovery_snapshot_objects_transitive_deps(standalone_repos):
    """Test that transfer includes transitive object dependencies."""
    auth_repo, standalone = standalone_repos
    
    # Create a chain of commits
    for i in range(3):
        test_file = standalone / f"file{i}.txt"
        test_file.write_text(f"content{i}")
        subprocess.run(
            ["git", "add", "."],
            cwd=standalone,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", f"Commit {i}"],
            cwd=standalone,
            capture_output=True,
            check=True,
        )
    
    # Get final HEAD
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=standalone,
        capture_output=True,
        text=True,
        check=True,
    )
    head_sha = result.stdout.strip()
    
    # Get parent commits
    parents = subprocess.run(
        ["git", "rev-list", "--parents", "-n", "1", head_sha],
        cwd=standalone,
        capture_output=True,
        text=True,
        check=True,
    )
    parent_shas = parents.stdout.strip().split()[1:]  # Skip the HEAD SHA itself
    
    # Transfer only HEAD
    _transfer_recovery_snapshot_objects(
        head_sha,
        standalone,
        auth_repo,
    )
    
    # Verify HEAD and all parents are readable in auth_repo
    for sha in [head_sha] + parent_shas:
        verify = subprocess.run(
            ["git", "cat-file", "-e", sha],
            cwd=auth_repo,
            capture_output=True,
            text=True,
            check=False,
        )
        assert verify.returncode == 0, f"Parent object {sha} should be readable"


def test_preserve_worktree_changes_transfers_objects_before_update_ref():
    """Test that preserve_worktree_changes transfers objects before publishing ref.
    
    This is the integration test that verifies the fix for OOMPAH-817.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create authoritative repo
        auth_repo = tmpdir / "auth"
        auth_repo.mkdir()
        subprocess.run(
            ["git", "init", "--initial-branch=main"],
            cwd=auth_repo,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=auth_repo,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=auth_repo,
            capture_output=True,
            check=True,
        )
        
        # Create initial commit
        test_file = auth_repo / "test.txt"
        test_file.write_text("initial")
        subprocess.run(
            ["git", "add", "."],
            cwd=auth_repo,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "Initial"],
            cwd=auth_repo,
            capture_output=True,
            check=True,
        )
        
        # Create a linked worktree
        worktree_path = tmpdir / "wt"
        subprocess.run(
            ["git", "worktree", "add", str(worktree_path), "-b", "task/TASK-1"],
            cwd=auth_repo,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=worktree_path,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=worktree_path,
            capture_output=True,
            check=True,
        )
        
        # Create a dirty worktree (changes that need recovery)
        dirty_file = worktree_path / "dirty.txt"
        dirty_file.write_text("dirty changes")
        subprocess.run(
            ["git", "add", "."],
            cwd=worktree_path,
            capture_output=True,
            check=True,
        )
        
        # Use ProjectStore to preserve changes
        project = Project(
            id="test-project",
            name="test-project",
            repo_url="",
            repo_path=str(auth_repo),
            default_branch="main",
        )
        
        store = ProjectStore(path=str(tmpdir / "projects.json"))
        store._projects["test-project"] = project
        
        # This should now successfully transfer objects before creating the ref
        recovery_context = store._preserve_dirty_worktree_locked(
            project,
            "TASK-1",
            str(worktree_path),
        )
        
        # Verify recovery context was created
        assert recovery_context is not None
        assert "recovery_ref" in recovery_context
        assert "snapshot_head" in recovery_context
        
        # Verify the recovery ref exists in auth_repo
        snapshot_sha = recovery_context["snapshot_head"]
        verify = subprocess.run(
            ["git", "cat-file", "-e", snapshot_sha],
            cwd=auth_repo,
            capture_output=True,
            text=True,
            check=False,
        )
        assert verify.returncode == 0, "Snapshot object should be readable in auth_repo"
        
        # Verify the recovery ref was created
        ref_result = subprocess.run(
            ["git", "rev-parse", recovery_context["recovery_ref"]],
            cwd=auth_repo,
            capture_output=True,
            text=True,
            check=False,
        )
        assert ref_result.returncode == 0, "Recovery ref should exist"
        assert ref_result.stdout.strip() == snapshot_sha, "Recovery ref should point to snapshot"
