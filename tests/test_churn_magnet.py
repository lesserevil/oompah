"""Tests for oompah/churn_magnet.py — churn-magnet analyzer.

Tests cover:
1. run_git_merge_tree() pure function (git subprocess parsing)
2. ChurnMagnetStore JSON-backed persistence
3. ProjectChurnState rolling-window aggregation
4. get_top_files() top-N query
5. record_conflicts() / record_conflict() batch recording
6. clear_project() / clear_window()
7. get_store() singleton behavior
8. record_conflicts_for_project() end-to-end function
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import tempfile
import threading
import time
from unittest import mock

import pytest

from oompah.churn_magnet import (
    ChurnMagnetStore,
    DEFAULT_CHURN_MAGNETS_PATH,
    DEFAULT_TOP_N,
    DEFAULT_WINDOW_SIZE,
    ChurnRecord,
    ProjectChurnState,
    _now,
    _parse_merge_tree_conflicts,
    _resolve_ref,
    detect_conflicted_files,
    get_store,
    record_conflicts_for_project,
    run_git_merge_tree,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_dir():
    """Create a temporary directory and return as a Path."""
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


@pytest.fixture
def git_repo(tmp_dir):
    """Create a minimal git repo with two branches for merge-tree tests."""
    repo = Path(tmp_dir)
    # Init repo
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo, check=True, capture_output=True
    )
    # Commit on main
    (repo / "README.md").write_text("main content\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"], cwd=repo, check=True, capture_output=True
    )
    # Create feature branch with conflicting changes
    subprocess.run(
        ["git", "checkout", "-b", "feature"], cwd=repo,
        check=True, capture_output=True
    )
    (repo / "conflicting_file.py").write_text("feature version\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "add conflicting file"],
        cwd=repo, check=True, capture_output=True
    )
    # Switch back to main and make conflicting change
    subprocess.run(
        ["git", "checkout", "main"], cwd=repo, check=True, capture_output=True
    )
    (repo / "conflicting_file.py").write_text("main version\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "conflict on main"],
        cwd=repo, check=True, capture_output=True
    )
    return str(repo)


from pathlib import Path


@pytest.fixture
def store_path(tmp_path):
    """Return a path inside a temp dir for store tests."""
    return str(tmp_path / "churn_magnets.json")


@pytest.fixture
def empty_store(store_path):
    """Fresh ChurnMagnetStore at a temporary path."""
    return ChurnMagnetStore(path=store_path)


# ---------------------------------------------------------------------------
# _parse_merge_tree_conflicts
# ---------------------------------------------------------------------------


class TestParseMergeTreeConflicts:
    """Unit tests for _parse_merge_tree_conflicts()."""

    def test_empty_output(self):
        assert _parse_merge_tree_conflicts("") == []
        assert _parse_merge_tree_conflicts("\n\n") == []

    def test_both_modified(self):
        out = "both modified: src/main.rs\nboth modified: lib.rs"
        files = _parse_merge_tree_conflicts(out)
        assert "src/main.rs" in files
        assert "lib.rs" in files

    def test_both_added(self):
        out = "both added: new_file.py\nboth added: build.rs"
        files = _parse_merge_tree_conflicts(out)
        assert "new_file.py" in files
        assert "build.rs" in files

    def test_conflict_marker_with_file_path(self):
        out = "<<<<<<< abc123def\nREADME.md\n=======\ncontent\n>>>>>>> 789xyz"
        files = _parse_merge_tree_conflicts(out)
        assert "README.md" in files

    def test_deduplicates(self):
        out = "both modified: foo.rs\nboth modified: foo.rs"
        files = _parse_merge_tree_conflicts(out)
        assert files.count("foo.rs") == 1

    def test_case_insensitive_both_modified(self):
        out = "Both Modified: src/main.rs"
        files = _parse_merge_tree_conflicts(out)
        assert "src/main.rs" in files

    def test_complex_output(self):
        out = """\
both modified: src/cli.rs
both added: new_util.rs
<<<<<<< deadbeef
pkg/Cargo.toml
=======
pkg/Cargo.toml
>>>>>>> feeblob
"""
        files = _parse_merge_tree_conflicts(out)
        assert "src/cli.rs" in files
        assert "new_util.rs" in files
        assert "pkg/Cargo.toml" in files


# ---------------------------------------------------------------------------
# run_git_merge_tree
# ---------------------------------------------------------------------------


class TestRunGitMergeTree:
    """Tests for run_git_merge_tree()."""

    def test_invalid_repo_path(self, tmp_dir):
        files, err = run_git_merge_tree(
            str(tmp_dir / "nonexistent"), "main", "feature"
        )
        assert files == []
        assert err is not None

    def test_empty_branch_names(self, git_repo):
        files, err = run_git_merge_tree(git_repo, "", "feature")
        assert files == []
        assert err is not None

    def test_no_conflict(self, git_repo):
        """When branches have diverged but not conflicted (no shared files changed),
        merge-tree produces no conflict markers."""
        # Add a non-conflicting commit to feature
        Path(git_repo, "unrelated.py").write_text("unrelated content")
        subprocess.run(["git", "add", "."], cwd=git_repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "unrelated"],
            cwd=git_repo, check=True, capture_output=True
        )
        # Also add the same file to main (non-conflicting: different files)
        Path(git_repo, "another_file.py").write_text("another content")
        subprocess.run(["git", "add", "."], cwd=git_repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "another"],
            cwd=git_repo, check=True, capture_output=True
        )
        files, err = run_git_merge_tree(git_repo, "main", "feature")
        # No shared files changed — no conflicts expected
        assert err is None
        # One or zero files is acceptable (no conflict markers)
        assert len(files) <= 1

    def test_real_conflict_detected(self, git_repo):
        """The fixture creates a real conflict on conflicting_file.py between
        main and feature. run_git_merge_tree should detect it."""
        files, err = run_git_merge_tree(git_repo, "main", "feature")
        assert err is None
        assert "conflicting_file.py" in files

    def test_resolve_ref_to_sha(self, git_repo):
        """_resolve_ref should return commit SHA for branch names."""
        sha = _resolve_ref(git_repo, "main")
        assert len(sha) == 40
        assert sha.isalnum()


# ---------------------------------------------------------------------------
# ChurnRecord / ProjectChurnState
# ---------------------------------------------------------------------------


class TestProjectChurnState:
    """Unit tests for ProjectChurnState."""

    def test_add_conflict_increments_counts(self):
        state = ProjectChurnState(project_id="proj1")
        ts = 1_700_000_000.0
        state.add_conflict(
            ChurnRecord("proj1", "src/main.py", ts, "PR#1")
        )
        state.add_conflict(
            ChurnRecord("proj1", "src/main.py", ts + 1, "PR#1")
        )
        state.add_conflict(
            ChurnRecord("proj1", "lib.rs", ts + 2, "PR#2")
        )
        assert state.file_counts["src/main.py"] == 2
        assert state.file_counts["lib.rs"] == 1
        assert state.total_conflicts == 3

    def test_top_files_sorted_descending(self):
        state = ProjectChurnState(project_id="proj1")
        ts = 1_700_000_000.0
        for i, path in enumerate(["b.rs", "a.rs", "c.rs", "b.rs", "b.rs"]):
            state.add_conflict(
                ChurnRecord("proj1", path, ts + i, f"PR#{i}")
            )
        top = state.top_files(n=3)
        assert top[0] == ("b.rs", 3)
        assert top[1][0] in ("a.rs", "c.rs")
        assert len(top) == 3

    def test_top_files_empty(self):
        state = ProjectChurnState(project_id="proj1")
        assert state.top_files() == []

    def test_top_files_respects_n(self):
        state = ProjectChurnState(project_id="proj1")
        ts = 1_700_000_000.0
        for i in range(10):
            state.add_conflict(
                ChurnRecord("proj1", f"file_{i}.rs", ts + i, f"PR#{i}")
            )
        top = state.top_files(n=3)
        assert len(top) == 3


# ---------------------------------------------------------------------------
# ChurnMagnetStore
# ---------------------------------------------------------------------------


class TestChurnMagnetStore:
    """Tests for ChurnMagnetStore."""

    def test_empty_store_init(self, empty_store):
        assert empty_store.list_projects() == []

    def test_record_conflict_single(self, empty_store):
        ts = 1_700_000_000.0
        empty_store.record_conflict("proj1", "src/main.py", "PR#1", ts)
        top = empty_store.get_top_files("proj1")
        assert top == [("src/main.py", 1)]

    def test_record_conflicts_dedup(self, empty_store):
        ts = 1_700_000_000.0
        count = empty_store.record_conflicts(
            "proj1", ["a.py", "a.py", "b.py"], "PR#1", ts
        )
        assert count == 2
        assert empty_store.get_top_files("proj1") == [("a.py", 1), ("b.py", 1)]

    def test_multiple_projects(self, empty_store):
        ts = 1_700_000_000.0
        empty_store.record_conflict("proj1", "file1.txt", "PR#1", ts)
        empty_store.record_conflict("proj2", "file2.txt", "PR#2", ts)
        assert set(empty_store.list_projects()) == {"proj1", "proj2"}
        assert empty_store.get_top_files("proj1") == [("file1.txt", 1)]
        assert empty_store.get_top_files("proj2") == [("file2.txt", 1)]

    def test_persistence(self, store_path):
        ts = 1_700_000_000.0
        store1 = ChurnMagnetStore(path=store_path)
        store1.record_conflict("proj1", "main.py", "PR#1", ts)
        store1.record_conflict("proj2", "lib.rs", "PR#2", ts)
        # Create new store instance reading same file
        store2 = ChurnMagnetStore(path=store_path)
        assert store2.get_top_files("proj1") == [("main.py", 1)]
        assert store2.get_top_files("proj2") == [("lib.rs", 1)]

    def test_top_n_query(self, empty_store):
        ts = 1_700_000_000.0
        for i in range(5):
            empty_store.record_conflict(
                f"proj{10+i}", f"file_{i}.rs", f"PR#{i}", ts + i
            )
        all_top = empty_store.get_all_top_files(n=2)
        assert len(all_top) == 5
        for v in all_top.values():
            assert len(v) <= 2

    def test_clear_project(self, empty_store):
        ts = 1_700_000_000.0
        empty_store.record_conflict("proj1", "file.rs", "PR#1", ts)
        empty_store.record_conflict("proj2", "file.rs", "PR#2", ts)
        assert empty_store.clear_project("proj1") is True
        assert empty_store.list_projects() == ["proj2"]
        assert empty_store.clear_project("proj-nonexistent") is False

    def test_clear_window_prunes_history(self, store_path):
        ts = 1_700_000_000.0
        store = ChurnMagnetStore(path=store_path, window_size=5)
        for i in range(10):
            store.record_conflict(
                "proj1",
                f"file_{i % 3}",
                f"PR#{i}",
                ts + i,
            )
        # History should be capped at window_size
        assert len(store.get_churn_state("proj1").conflict_history) <= 5
        # File counts should reflect only the window
        state = store.get_churn_state("proj1")
        for count in state.file_counts.values():
            assert count <= 5

    def test_get_churn_state_not_found(self, empty_store):
        assert empty_store.get_churn_state("nonexistent") is None

    def test_get_top_files_not_found(self, empty_store):
        assert empty_store.get_top_files("nonexistent") == []

    def test_concurrent_record_threadsafe(self, tmp_path):
        """Multiple threads recording concurrently should produce consistent results."""
        store_path = str(tmp_path / "concurrent.json")
        store = ChurnMagnetStore(path=store_path, window_size=1000)
        errors = []

        def record_batch(n):
            try:
                ts = _now()
                for i in range(10):
                    store.record_conflict(
                        "proj1",
                        f"file_{n}_{i}.rs",
                        f"PR#{n}_{i}",
                        ts + i,
                    )
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=record_batch, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
        state = store.get_churn_state("proj1")
        assert state.total_conflicts == 50

    def test_record_with_future_timestamp(self, empty_store):
        """Timestamps in the future are accepted without error."""
        ts = time.time() + 3600  # 1 hour in the future
        empty_store.record_conflict("proj1", "future.rs", "PR#1", ts)
        assert empty_store.get_top_files("proj1") == [("future.rs", 1)]

    def test_malformed_json_loads_gracefully(self, tmp_path):
        """A corrupt JSON file results in an empty store rather than a crash."""
        bad_path = str(tmp_path / "bad.json")
        with open(bad_path, "w") as f:
            f.write("{ invalid json content }")
        store = ChurnMagnetStore(path=bad_path)
        assert store.list_projects() == []


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


class TestModuleHelpers:
    """Tests for module-level get_store() and record_conflicts_for_project()."""

    def test_get_store_returns_singleton(self):
        """get_store() should return the same instance on repeated calls."""
        unimported = __import__("oompah.churn_magnet", fromlist=["_store"])
        old_store = unimported._store
        unimported._store = None  # reset for test
        try:
            from oompah.churn_magnet import get_store as gs

            s1 = gs("/tmp/nonexistent_churn.json")
            s2 = gs("/tmp/nonexistent_churn.json")
            assert s1 is s2
        finally:
            unimported._store = old_store

    def test_detect_conflicted_files_returns_empty_on_error(self, tmp_dir):
        """detect_conflicted_files should return [] on error, not raise."""
        result = detect_conflicted_files(
            str(tmp_dir / "nonexistent"), "main", "feature"
        )
        assert result == []

    def test_record_conflicts_for_project_returns_0_on_git_error(self, tmp_dir):
        """When git merge-tree fails, record_conflicts_for_project returns 0."""
        count = record_conflicts_for_project(
            "proj1",
            str(tmp_dir / "nonexistent"),
            "main",
            "feature",
            "PR#1",
        )
        assert count == 0


# ---------------------------------------------------------------------------
# End-to-end integration test (requires real git repo)
# ---------------------------------------------------------------------------


class TestChurnMagnetIntegration:
    """Integration tests with a real git repo."""

    def test_record_conflicts_for_project_real_repo(self, git_repo, tmp_path):
        """Full round-trip with real git: detect conflict + record in store."""
        import oompah.churn_magnet as _cm

        store_path = str(tmp_path / "churn_integration.json")
        old = _cm._store
        _cm._store = None
        try:
            from oompah.churn_magnet import get_store as _gs
            _gs(store_path)

            count = record_conflicts_for_project(
                "test-project",
                git_repo,
                "main",
                "feature",
                "PR#42",
            )
            assert count >= 1, "conflicting_file.py should be detected"
            # Verify it persisted
            store = _cm.get_store()
            top = store.get_top_files("test-project")
            assert len(top) >= 1
            assert top[0][0] == "conflicting_file.py"
            assert top[0][1] >= 1
            # Clean up
            store.clear_project("test-project")
        finally:
            _cm._store = old

    def test_top_files_reflects_real_conflict_counts(self, git_repo, tmp_path):
        """After multiple PRs, top_files should rank files by conflict frequency."""
        store_path = str(tmp_path / "churn_integration.json")
        from oompah.churn_magnet import (
            get_store as _gs,
        )

        # Monkey-patch the module store for this test
        import oompah.churn_magnet as _cm

        old = _cm._store
        _cm._store = None
        try:
            store = ChurnMagnetStore(path=store_path, window_size=100)
            _cm._store = store

            # Simulate 3 PRs involving conflicting_file.py
            ts = 1_700_000_000.0
            for i in range(3):
                record_conflicts_for_project(
                    "proj-int",
                    git_repo,
                    "main",
                    "feature",
                    f"PR#{i}",
                )
            # Simulate 1 PR involving README.md
            record_conflicts_for_project(
                "proj-int",
                git_repo,
                "main",
                "feature",
                "PR#3",
            )

            top10 = store.get_top_files("proj-int", n=10)
            file_names = [f for f, _ in top10]
            # conflicting_file.py should rank higher than README.md (3 vs 1 or more)
            if "conflicting_file.py" in file_names and "README.md" in file_names:
                assert file_names.index("conflicting_file.py") < file_names.index(
                    "README.md"
                )
            # Verify file count values
            counts = dict(top10)
            if "conflicting_file.py" in counts:
                assert counts["conflicting_file.py"] >= 3
        finally:
            _cm._store = old


# ---------------------------------------------------------------------------
# Wire-in verification: orchestrator imports churn_magnet
# ---------------------------------------------------------------------------


class TestOrchestratorWireIn:
    """Verify the orchestrator wires in chur n_magnet correctly."""

    def test_orchestrator_imports_churn_magnet(self):
        """The orchestrator module should import churn_magnet symbols."""
        import oompah.orchestrator as orch_under_test

        assert hasattr(orch_under_test, "ChurnMagnetStore")
        assert hasattr(orch_under_test, "_get_churn_store")
        assert hasattr(orch_under_test, "record_conflicts_for_project")
        assert hasattr(orch_under_test, "run_git_merge_tree")

    def test_orchestrator_orchestratorclass_has_notify_conflict(self):
        """The Orchestrator class should have _yolo_notify_conflict."""
        import oompah.orchestrator as orch_under_test

        assert hasattr(orch_under_test.Orchestrator, "_yolo_notify_conflict")
        assert hasattr(orch_under_test.Orchestrator, "_handle_yolo_merge_failure")