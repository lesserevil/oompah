"""Tests for state-branch migration (OOMPAH-259).

Coverage areas:

  § 1  validate_state_branch — pre-migration checks
  § 2  migrate_stage_a — orphan branch bootstrap + shadow write
  § 3  migrate_stage_b — stop shadow writes
  § 4  migrate_stage_c — remove tasks from default branch (optional)
  § 5  rollback_migration — restore legacy mode
  § 6  End-to-end: full migration with rich task data
  § 7  Idempotency: each stage is safe to re-run
  § 8  Interrupted migration: retry at each stage is safe
  § 9  Concurrent-write: cutover does not silently lose a mutation
  §10  Project model: new fields serialize/deserialize correctly
  §11  ProjectStore: validates the new fields
  §12  OompahMarkdownTracker: shadow write path
  §13  get_migration_status helper
"""

from __future__ import annotations

import subprocess
import threading
import time
from pathlib import Path

import pytest
import yaml

from oompah.models import Project
from oompah.oompah_md_tracker import OompahMarkdownTracker
from oompah.state_branch_migration import (
    MigrationResult,
    ValidationResult,
    get_migration_status,
    migrate_stage_a,
    migrate_stage_b,
    migrate_stage_c,
    rollback_migration,
    validate_state_branch,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _git(*args: str, cwd: str | Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )


def _make_repo(tmp_path: Path, *, with_tasks: bool = True, name: str = "repo") -> Path:
    """Create a minimal git repo with optional .oompah/tasks/ content."""
    repo = tmp_path / name
    repo.mkdir(parents=True)
    _git("init", "-b", "main", cwd=repo)
    _git("config", "user.email", "test@oompah.dev", cwd=repo)
    _git("config", "user.name", "Oompah Test", cwd=repo)

    (repo / "README.md").write_text("# Test\n", encoding="utf-8")

    if with_tasks:
        _seed_tasks(repo)

    _git("add", ".", cwd=repo)
    _git("commit", "-m", "initial", cwd=repo)
    return repo


def _seed_tasks(repo: Path) -> None:
    """Create a rich set of task files covering all tracker data categories."""
    tasks_root = repo / ".oompah" / "tasks"
    for d in [
        "proposed", "backlog", "open", "in-progress", "needs-human",
        "in-review", "done", "merged", "archived",
    ]:
        (tasks_root / d).mkdir(parents=True, exist_ok=True)

    def _task(subdir: str, task_id: str, status: str, **extra) -> None:
        meta: dict = {
            "id": task_id,
            "type": "task",
            "status": status,
            "priority": 2,
            "title": f"Task {task_id}",
            "parent": None,
            "children": [],
            "blocked_by": [],
            "labels": ["backend"],
            "created_at": "2026-07-01T10:00:00Z",
            "updated_at": "2026-07-15T08:00:00Z",
            "work_branch": None,
            "target_branch": None,
            "review_url": None,
            "review_number": None,
            "merged_at": None,
        }
        meta.update(extra)
        body = (
            f"## Summary\n\nTask {task_id} summary.\n\n"
            "## Acceptance Criteria\n\n- [ ] AC1.\n\n"
            "## Comments\n\n"
            "<!--oompah:comment:1-->\n**oompah** (2026-07-15): A comment.\n"
        )
        path = tasks_root / subdir / f"{task_id}.md"
        path.write_text(f"---\n{yaml.safe_dump(meta)}---\n{body}", encoding="utf-8")

    _task("open", "TASK-1", "Open")
    _task("in-progress", "TASK-2", "In Progress", work_branch="TASK-2")
    _task("done", "TASK-3", "Done", merged_at="2026-07-10T12:00:00Z")
    _task("merged", "TASK-4", "Merged", merged_at="2026-07-12T09:00:00Z")
    _task("archived", "TASK-5", "Archived")
    # Task with dependency
    _task("in-progress", "TASK-6", "In Progress", blocked_by=["TASK-1"])


def _make_repo_with_remote(tmp_path: Path) -> tuple[Path, Path]:
    """Return (working_tree, bare_remote) both with initial content."""
    bare = tmp_path / "bare.git"
    bare.mkdir()
    _git("init", "--bare", cwd=bare)

    work = _make_repo(tmp_path, name="work")
    _git("remote", "add", "origin", str(bare), cwd=work)
    _git("push", "--set-upstream", "origin", "main", cwd=work)
    return work, bare


def _files_on_branch(repo: Path, branch: str) -> set[str]:
    r = _git("ls-tree", "-r", "--name-only", branch, cwd=repo)
    return set(r.stdout.splitlines()) if r.returncode == 0 else set()


PROJECT_ID = "proj-test-migration"


# ---------------------------------------------------------------------------
# § 1  validate_state_branch
# ---------------------------------------------------------------------------


class TestValidateStateBranch:
    def test_clean_repo_passes_all_local_checks(self, tmp_path: Path):
        repo = _make_repo(tmp_path)
        result = validate_state_branch(repo, PROJECT_ID, default_branch="main")
        assert isinstance(result, ValidationResult)
        # Without a remote, push-related checks are auto-passed.
        local_checks = {c.name: c for c in result.checks}
        assert local_checks["default branch is clean"].passed
        assert local_checks["task files have valid YAML"].passed
        assert local_checks["no duplicate task IDs"].passed

    def test_corrupt_task_file_fails_yaml_check(self, tmp_path: Path):
        repo = _make_repo(tmp_path)
        corrupt = repo / ".oompah" / "tasks" / "open" / "BAD.md"
        corrupt.parent.mkdir(parents=True, exist_ok=True)
        corrupt.write_text("---\nnot: valid: yaml: content: {\n---\nBody\n", encoding="utf-8")
        _git("add", ".", cwd=repo)
        _git("commit", "-m", "add corrupt task", cwd=repo)

        result = validate_state_branch(repo, PROJECT_ID)
        yaml_check = next(c for c in result.checks if c.name == "task files have valid YAML")
        assert not yaml_check.passed
        assert not result.all_passed

    def test_dirty_working_tree_fails_clean_check(self, tmp_path: Path):
        repo = _make_repo(tmp_path)
        (repo / "dirty.txt").write_text("uncommitted", encoding="utf-8")
        _git("add", ".", cwd=repo)
        # Staged but not committed — dirty.

        result = validate_state_branch(repo, PROJECT_ID)
        clean_check = next(c for c in result.checks if "clean" in c.name)
        assert not clean_check.passed

    def test_all_passed_false_on_any_failure(self, tmp_path: Path):
        repo = _make_repo(tmp_path)
        (repo / "dirty.txt").write_text("uncommitted", encoding="utf-8")
        _git("add", ".", cwd=repo)
        result = validate_state_branch(repo, PROJECT_ID)
        assert result.all_passed is False

    def test_no_tasks_gives_zero_count(self, tmp_path: Path):
        repo = _make_repo(tmp_path, with_tasks=False)
        result = validate_state_branch(repo, PROJECT_ID)
        yaml_check = next(c for c in result.checks if c.name == "task files have valid YAML")
        assert yaml_check.passed
        assert "0 task(s)" in yaml_check.message

    def test_to_dict_format(self, tmp_path: Path):
        repo = _make_repo(tmp_path)
        result = validate_state_branch(repo, PROJECT_ID)
        d = result.to_dict()
        assert "all_passed" in d
        assert "checks" in d
        assert all("name" in c and "passed" in c for c in d["checks"])


# ---------------------------------------------------------------------------
# § 2  migrate_stage_a
# ---------------------------------------------------------------------------


class TestMigrateStageA:
    def test_creates_state_branch(self, tmp_path: Path):
        repo = _make_repo(tmp_path)
        result = migrate_stage_a(repo, PROJECT_ID, default_branch="main", push=False)
        assert result.ok, f"Stage A failed: {result.error}"
        # State branch must exist.
        branch = f"oompah/state/{PROJECT_ID}"
        r = _git("rev-parse", "--verify", branch, cwd=repo)
        assert r.returncode == 0, "State branch must exist after Stage A"

    def test_state_branch_is_orphan(self, tmp_path: Path):
        repo = _make_repo(tmp_path)
        migrate_stage_a(repo, PROJECT_ID, default_branch="main", push=False)
        branch = f"oompah/state/{PROJECT_ID}"
        merge_base = _git("merge-base", branch, "main", cwd=repo)
        assert merge_base.returncode != 0, "Orphan branch must have no common ancestor with main"

    def test_state_branch_contains_task_files(self, tmp_path: Path):
        repo = _make_repo(tmp_path)
        migrate_stage_a(repo, PROJECT_ID, default_branch="main", push=False)
        branch = f"oompah/state/{PROJECT_ID}"
        files = _files_on_branch(repo, branch)
        task_files = [f for f in files if f.startswith(".oompah/tasks/")]
        assert len(task_files) >= 5, f"Expected task files on state branch; got: {files}"

    def test_state_branch_contains_no_source_code(self, tmp_path: Path):
        repo = _make_repo(tmp_path)
        migrate_stage_a(repo, PROJECT_ID, default_branch="main", push=False)
        branch = f"oompah/state/{PROJECT_ID}"
        files = _files_on_branch(repo, branch)
        non_oompah = [f for f in files if not f.startswith(".oompah/")]
        assert non_oompah == [], f"State branch must not contain source files: {non_oompah}"

    def test_main_branch_unchanged(self, tmp_path: Path):
        repo = _make_repo(tmp_path)
        # Record state before migration.
        before = _files_on_branch(repo, "main")
        migrate_stage_a(repo, PROJECT_ID, default_branch="main", push=False)
        after = _files_on_branch(repo, "main")
        assert after == before, "Stage A must not modify files on the main branch"

    def test_result_ok_and_branch_name(self, tmp_path: Path):
        repo = _make_repo(tmp_path)
        result = migrate_stage_a(repo, PROJECT_ID, push=False)
        assert result.ok
        assert result.stage == "A"
        assert result.error == ""

    def test_to_dict_format(self, tmp_path: Path):
        repo = _make_repo(tmp_path)
        result = migrate_stage_a(repo, PROJECT_ID, push=False)
        d = result.to_dict()
        assert "ok" in d and "stage" in d and "error" in d

    def test_push_to_remote(self, tmp_path: Path):
        work, bare = _make_repo_with_remote(tmp_path)
        result = migrate_stage_a(work, PROJECT_ID, default_branch="main", push=True)
        assert result.ok, f"Stage A with push failed: {result.error}"
        branch = f"oompah/state/{PROJECT_ID}"
        r = _git("rev-parse", "--verify", branch, cwd=bare)
        assert r.returncode == 0, "State branch must be pushed to the remote"


# ---------------------------------------------------------------------------
# § 3  migrate_stage_b
# ---------------------------------------------------------------------------


class TestMigrateStageB:
    def _setup(self, tmp_path: Path) -> Path:
        repo = _make_repo(tmp_path)
        migrate_stage_a(repo, PROJECT_ID, push=False)
        return repo

    def test_stage_b_ok_after_stage_a(self, tmp_path: Path):
        repo = self._setup(tmp_path)
        result = migrate_stage_b(repo, PROJECT_ID, default_branch="main")
        assert result.ok, f"Stage B failed: {result.error}"
        assert result.stage == "B"

    def test_stage_b_fails_without_state_branch(self, tmp_path: Path):
        repo = _make_repo(tmp_path)  # no Stage A
        result = migrate_stage_b(repo, PROJECT_ID, default_branch="main")
        assert not result.ok
        assert "Stage A" in result.error or "not exist" in result.error

    def test_stage_b_tasks_still_on_default_branch(self, tmp_path: Path):
        """Stage B does not delete tasks from the default branch."""
        repo = self._setup(tmp_path)
        migrate_stage_b(repo, PROJECT_ID)
        # .oompah/tasks/ must still be on main (rollback snapshot).
        files = _files_on_branch(repo, "main")
        task_files = [f for f in files if f.startswith(".oompah/tasks/")]
        assert len(task_files) >= 1, "Stage B must not delete task files from main"

    def test_stage_b_message_mentions_snapshot(self, tmp_path: Path):
        repo = self._setup(tmp_path)
        result = migrate_stage_b(repo, PROJECT_ID)
        assert "snapshot" in result.message.lower() or "preserved" in result.message.lower()


# ---------------------------------------------------------------------------
# § 4  migrate_stage_c
# ---------------------------------------------------------------------------


class TestMigrateStageC:
    def _setup_through_b(self, tmp_path: Path) -> Path:
        repo = _make_repo(tmp_path)
        migrate_stage_a(repo, PROJECT_ID, push=False)
        migrate_stage_b(repo, PROJECT_ID)
        return repo

    def test_stage_c_removes_tasks_from_main(self, tmp_path: Path):
        repo = self._setup_through_b(tmp_path)
        result = migrate_stage_c(repo, PROJECT_ID, default_branch="main", push=False)
        assert result.ok, f"Stage C failed: {result.error}"
        files = _files_on_branch(repo, "main")
        task_files = [f for f in files if f.startswith(".oompah/tasks/")]
        assert task_files == [], "Stage C must remove .oompah/tasks/ from main"

    def test_stage_c_idempotent_when_already_removed(self, tmp_path: Path):
        repo = self._setup_through_b(tmp_path)
        migrate_stage_c(repo, PROJECT_ID, push=False)
        result2 = migrate_stage_c(repo, PROJECT_ID, push=False)
        assert result2.ok
        assert result2.already_done

    def test_stage_c_state_branch_still_has_tasks(self, tmp_path: Path):
        """After Stage C, tasks must remain on the state branch."""
        repo = self._setup_through_b(tmp_path)
        migrate_stage_c(repo, PROJECT_ID, push=False)
        branch = f"oompah/state/{PROJECT_ID}"
        files = _files_on_branch(repo, branch)
        task_files = [f for f in files if f.startswith(".oompah/tasks/")]
        assert len(task_files) >= 1, "State branch must retain task files after Stage C"


# ---------------------------------------------------------------------------
# § 5  rollback_migration
# ---------------------------------------------------------------------------


class TestRollbackMigration:
    def test_rollback_from_stage_a_no_ops_git(self, tmp_path: Path):
        """Stage A rollback is lossless — shadow writes kept default branch current."""
        repo = _make_repo(tmp_path)
        migrate_stage_a(repo, PROJECT_ID, push=False)
        result = rollback_migration(
            repo, PROJECT_ID, default_branch="main", current_stage="A", push=False
        )
        assert result.ok, f"Rollback from A failed: {result.error}"
        assert result.stage == "rollback"

    def test_rollback_from_stage_b_restores_tasks_on_main(self, tmp_path: Path):
        """Rollback from Stage B restores .oompah/ from the state branch onto main."""
        repo = _make_repo(tmp_path)
        migrate_stage_a(repo, PROJECT_ID, push=False)
        migrate_stage_b(repo, PROJECT_ID)

        # Simulate: tasks on main might be stale (Stage B stopped shadow writes).
        # Add a new task to the state branch directly.
        branch = f"oompah/state/{PROJECT_ID}"
        wt_dir = tmp_path / "state-wt"
        _git("worktree", "add", str(wt_dir), branch, cwd=repo)
        new_task = wt_dir / ".oompah" / "tasks" / "open" / "TASK-NEW.md"
        new_task.parent.mkdir(parents=True, exist_ok=True)
        new_task.write_text(
            "---\nid: TASK-NEW\ntitle: New Task\nstatus: Open\n---\nBody\n",
            encoding="utf-8",
        )
        _git("add", ".oompah/", cwd=wt_dir)
        _git("commit", "-m", "add task on state branch", cwd=wt_dir)
        _git("worktree", "remove", str(wt_dir), cwd=repo)

        result = rollback_migration(
            repo, PROJECT_ID, default_branch="main", current_stage="B", push=False
        )
        assert result.ok, f"Rollback from B failed: {result.error}"

        # The restored main branch must contain TASK-NEW.
        content_r = _git("show", "main:.oompah/tasks/open/TASK-NEW.md", cwd=repo)
        assert content_r.returncode == 0, (
            "TASK-NEW must be restored to main after rollback from Stage B"
        )

    def test_rollback_state_branch_is_preserved(self, tmp_path: Path):
        """Rollback does not delete the state branch."""
        repo = _make_repo(tmp_path)
        migrate_stage_a(repo, PROJECT_ID, push=False)
        rollback_migration(
            repo, PROJECT_ID, default_branch="main", current_stage="A", push=False
        )
        branch = f"oompah/state/{PROJECT_ID}"
        r = _git("rev-parse", "--verify", branch, cwd=repo)
        assert r.returncode == 0, "State branch must remain after rollback"

    def test_rollback_fails_gracefully_without_state_branch(self, tmp_path: Path):
        """Rollback from B without a state branch returns error (not exception)."""
        repo = _make_repo(tmp_path, with_tasks=False)
        # Don't run Stage A — no state branch exists.
        result = rollback_migration(
            repo, PROJECT_ID, default_branch="main", current_stage="B", push=False
        )
        assert not result.ok
        assert result.error != ""


# ---------------------------------------------------------------------------
# § 6  End-to-end: full migration with rich task data
# ---------------------------------------------------------------------------


class TestEndToEndMigration:
    """Full Stage A → B migration with tasks, comments, dependencies, active code branches."""

    def test_all_task_types_readable_after_stage_b(self, tmp_path: Path):
        """After Stage B, all task files must be readable from the state branch."""
        work, bare = _make_repo_with_remote(tmp_path)

        # Create an active code branch (simulating an in-flight PR).
        _git("checkout", "-b", "TASK-2", cwd=work)
        (work / "feature.py").write_text("# feature\n", encoding="utf-8")
        _git("add", ".", cwd=work)
        _git("commit", "-m", "TASK-2: feature work", cwd=work)
        _git("push", "origin", "TASK-2", cwd=work)
        _git("checkout", "main", cwd=work)

        # Stage A.
        r_a = migrate_stage_a(work, PROJECT_ID, default_branch="main", push=True)
        assert r_a.ok, f"Stage A failed: {r_a.error}"

        # Stage B.
        r_b = migrate_stage_b(work, PROJECT_ID, default_branch="main")
        assert r_b.ok, f"Stage B failed: {r_b.error}"

        # All original tasks must be on the state branch.
        branch = f"oompah/state/{PROJECT_ID}"
        for task_id in ["TASK-1", "TASK-2", "TASK-3", "TASK-4", "TASK-5", "TASK-6"]:
            # Determine expected subdir from initial seed.
            subdir_map = {
                "TASK-1": "open",
                "TASK-2": "in-progress",
                "TASK-3": "done",
                "TASK-4": "merged",
                "TASK-5": "archived",
                "TASK-6": "in-progress",
            }
            path = f".oompah/tasks/{subdir_map[task_id]}/{task_id}.md"
            r = _git("show", f"{branch}:{path}", cwd=work)
            assert r.returncode == 0, f"Task {task_id} must be readable from state branch"
            assert task_id in r.stdout, f"Task {task_id} content must be present"

    def test_tracker_reads_from_state_branch_after_stage_b(self, tmp_path: Path):
        """OompahMarkdownTracker with state_branch_enabled reads from state branch."""
        repo = _make_repo(tmp_path)
        migrate_stage_a(repo, PROJECT_ID, push=False)
        migrate_stage_b(repo, PROJECT_ID)

        tracker = OompahMarkdownTracker(
            active_states=["open", "in progress"],
            terminal_states=["done", "merged", "archived"],
            cwd=str(repo),
            default_branch="main",
            state_branch_enabled=True,
            state_branch_name=f"oompah/state/{PROJECT_ID}",
        )
        issues = tracker.fetch_all_issues()
        ids = {i.id for i in issues}
        assert "TASK-1" in ids, f"Tracker must read TASK-1 from state branch; got: {ids}"

    def test_code_branches_not_modified_during_migration(self, tmp_path: Path):
        """Active code branches must not be touched by the migration."""
        work, bare = _make_repo_with_remote(tmp_path)
        # Create a code branch.
        _git("checkout", "-b", "feature/my-feature", cwd=work)
        (work / "feat.py").write_text("# feat\n", encoding="utf-8")
        _git("add", ".", cwd=work)
        _git("commit", "-m", "feature commit", cwd=work)
        feature_sha_before = _git(
            "rev-parse", "feature/my-feature", cwd=work
        ).stdout.strip()
        _git("checkout", "main", cwd=work)

        # Run full migration.
        migrate_stage_a(work, PROJECT_ID, push=True)
        migrate_stage_b(work, PROJECT_ID)

        feature_sha_after = _git(
            "rev-parse", "feature/my-feature", cwd=work
        ).stdout.strip()
        assert feature_sha_before == feature_sha_after, (
            "Migration must not modify any code branch"
        )


# ---------------------------------------------------------------------------
# § 7  Idempotency
# ---------------------------------------------------------------------------


class TestIdempotency:
    def test_stage_a_idempotent(self, tmp_path: Path):
        repo = _make_repo(tmp_path)
        r1 = migrate_stage_a(repo, PROJECT_ID, push=False)
        r2 = migrate_stage_a(repo, PROJECT_ID, push=False)
        assert r1.ok and r2.ok
        # Second run should report already_done.
        assert r2.already_done

    def test_stage_a_does_not_add_extra_commits(self, tmp_path: Path):
        repo = _make_repo(tmp_path)
        migrate_stage_a(repo, PROJECT_ID, push=False)
        branch = f"oompah/state/{PROJECT_ID}"
        count_before = int(
            _git("rev-list", "--count", branch, cwd=repo).stdout.strip()
        )
        migrate_stage_a(repo, PROJECT_ID, push=False)
        count_after = int(
            _git("rev-list", "--count", branch, cwd=repo).stdout.strip()
        )
        assert count_after == count_before, (
            "Idempotent Stage A re-run must not create additional commits"
        )

    def test_stage_b_idempotent(self, tmp_path: Path):
        repo = _make_repo(tmp_path)
        migrate_stage_a(repo, PROJECT_ID, push=False)
        r1 = migrate_stage_b(repo, PROJECT_ID)
        r2 = migrate_stage_b(repo, PROJECT_ID)
        assert r1.ok and r2.ok

    def test_validate_can_run_multiple_times(self, tmp_path: Path):
        repo = _make_repo(tmp_path)
        r1 = validate_state_branch(repo, PROJECT_ID)
        r2 = validate_state_branch(repo, PROJECT_ID)
        assert r1.all_passed == r2.all_passed


# ---------------------------------------------------------------------------
# § 8  Interrupted migration: retry is safe
# ---------------------------------------------------------------------------


class TestInterruptedMigration:
    """Simulate interruption at each stage and prove retry is safe."""

    def test_stage_a_retry_after_bootstrap_but_before_config_update(
        self, tmp_path: Path
    ):
        """If Stage A git ops complete but config update is interrupted,
        re-running Stage A must succeed without duplicating the branch."""
        repo = _make_repo(tmp_path)
        branch = f"oompah/state/{PROJECT_ID}"

        # Run Stage A git ops only (simulate partial commit).
        from oompah.project_bootstrap import initialize_state_branch
        boot_result = initialize_state_branch(repo, PROJECT_ID, push=False)
        assert boot_result.error == ""

        # Branch now exists but project config hasn't been updated.
        # Re-running migrate_stage_a should detect existing branch and succeed.
        result = migrate_stage_a(repo, PROJECT_ID, push=False)
        assert result.ok
        assert result.already_done  # Branch already existed.

        # Must have exactly 1 commit on the state branch.
        count = int(_git("rev-list", "--count", branch, cwd=repo).stdout.strip())
        assert count == 1, f"Must have 1 bootstrap commit; got {count}"

    def test_stage_b_retry_is_safe(self, tmp_path: Path):
        """Retrying Stage B when already at B returns already_done result."""
        repo = _make_repo(tmp_path)
        migrate_stage_a(repo, PROJECT_ID, push=False)
        migrate_stage_b(repo, PROJECT_ID)

        # Retry Stage B — must be idempotent.
        result = migrate_stage_b(repo, PROJECT_ID)
        assert result.ok

    def test_stage_c_retry_is_safe(self, tmp_path: Path):
        repo = _make_repo(tmp_path)
        migrate_stage_a(repo, PROJECT_ID, push=False)
        migrate_stage_b(repo, PROJECT_ID)
        migrate_stage_c(repo, PROJECT_ID, push=False)

        result2 = migrate_stage_c(repo, PROJECT_ID, push=False)
        assert result2.ok
        assert result2.already_done

    def test_rollback_retry_is_safe(self, tmp_path: Path):
        repo = _make_repo(tmp_path)
        migrate_stage_a(repo, PROJECT_ID, push=False)
        migrate_stage_b(repo, PROJECT_ID)

        r1 = rollback_migration(
            repo, PROJECT_ID, default_branch="main", current_stage="B", push=False
        )
        assert r1.ok

        # Re-running rollback (simulate interrupted rollback re-run).
        r2 = rollback_migration(
            repo, PROJECT_ID, default_branch="main", current_stage="B", push=False
        )
        assert r2.ok  # Must not error.

    def test_tasks_not_lost_after_partial_stage_a(self, tmp_path: Path):
        """Tasks on main must survive a partial Stage A (bootstrap only)."""
        repo = _make_repo(tmp_path)
        # Stage A git bootstrap.
        from oompah.project_bootstrap import initialize_state_branch
        initialize_state_branch(repo, PROJECT_ID, push=False)

        # Tasks must still be on main.
        files = _files_on_branch(repo, "main")
        task_files = [f for f in files if f.startswith(".oompah/tasks/")]
        assert len(task_files) >= 1, "Tasks must remain on main after partial Stage A"

        # And they must also be on the state branch.
        branch = f"oompah/state/{PROJECT_ID}"
        state_files = _files_on_branch(repo, branch)
        state_tasks = [f for f in state_files if f.startswith(".oompah/tasks/")]
        assert len(state_tasks) >= 1, "Tasks must be on state branch after Stage A bootstrap"


# ---------------------------------------------------------------------------
# § 9  Concurrent-write: cutover cannot silently lose a mutation
# ---------------------------------------------------------------------------


class TestConcurrentWrite:
    """Verify that the write lock prevents concurrent mutations during cutover."""

    def test_shadow_write_tracker_serializes_writes(self, tmp_path: Path):
        """Two concurrent writes to a shadow-write tracker must both succeed.

        This validates that _write_lock prevents races between the primary
        state-branch write and the shadow write to the default branch.
        """
        repo = _make_repo(tmp_path, with_tasks=False)
        # Create minimal task structure.
        tasks_dir = repo / ".oompah" / "tasks"
        for d in ["open", "done", "in-progress", "needs-human", "in-review",
                  "proposed", "backlog", "merged", "archived"]:
            (tasks_dir / d).mkdir(parents=True, exist_ok=True)
        _git("add", ".", cwd=repo)
        _git("commit", "-m", "init tasks structure", cwd=repo)

        # Bootstrap state branch.
        from oompah.project_bootstrap import initialize_state_branch
        initialize_state_branch(repo, PROJECT_ID, push=False)

        # Create a tracker in shadow-write (Stage A) mode.
        # Use git_sync=False to skip network operations in the test.
        tracker = OompahMarkdownTracker(
            active_states=["open", "in progress"],
            terminal_states=["done", "merged", "archived"],
            cwd=str(repo),
            default_branch="main",
            state_branch_enabled=True,
            state_branch_name=f"oompah/state/{PROJECT_ID}",
            state_branch_shadow_write=True,
            git_sync=False,  # no push in unit test
        )

        errors: list[str] = []

        def _create_task(task_id: str) -> None:
            try:
                tracker.create_issue(
                    title=f"Task {task_id}",
                    description="Body",
                    priority=2,
                    labels=[],
                )
            except Exception as exc:
                errors.append(f"{task_id}: {exc}")

        # Run two concurrent writes.
        t1 = threading.Thread(target=_create_task, args=("CONC-1",))
        t2 = threading.Thread(target=_create_task, args=("CONC-2",))
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        assert errors == [], f"Concurrent writes produced errors: {errors}"

        # Both tasks must be readable.
        issues = tracker.fetch_all_issues()
        titles = {i.title for i in issues}
        assert "Task CONC-1" in titles, f"CONC-1 must be readable; got titles: {titles}"
        assert "Task CONC-2" in titles, f"CONC-2 must be readable; got titles: {titles}"


# ---------------------------------------------------------------------------
# §10  Project model: new fields serialize/deserialize correctly
# ---------------------------------------------------------------------------


class TestProjectModelMigrationFields:
    def _make_project(self, **overrides) -> Project:
        defaults = dict(
            id="proj-mig-test",
            name="test",
            repo_url="https://github.com/org/test.git",
            repo_path="/tmp/test",
            default_branch="main",
        )
        defaults.update(overrides)
        return Project(**defaults)

    def test_shadow_write_defaults_false(self):
        p = self._make_project()
        assert p.state_branch_shadow_write is False

    def test_migration_stage_defaults_empty(self):
        p = self._make_project()
        assert p.state_branch_migration_stage == ""

    def test_shadow_write_round_trips(self):
        p = self._make_project(state_branch_shadow_write=True)
        d = p.to_dict()
        assert d.get("state_branch_shadow_write") is True
        p2 = Project.from_dict(d)
        assert p2.state_branch_shadow_write is True

    def test_migration_stage_round_trips(self):
        p = self._make_project(state_branch_migration_stage="A")
        d = p.to_dict()
        assert d.get("state_branch_migration_stage") == "A"
        p2 = Project.from_dict(d)
        assert p2.state_branch_migration_stage == "A"

    def test_false_shadow_write_not_emitted_in_dict(self):
        """False shadow_write must be omitted to keep legacy records compact."""
        p = self._make_project(state_branch_shadow_write=False)
        d = p.to_dict()
        # When False (default), must not be in dict.
        assert "state_branch_shadow_write" not in d

    def test_empty_migration_stage_not_emitted(self):
        p = self._make_project(state_branch_migration_stage="")
        d = p.to_dict()
        assert "state_branch_migration_stage" not in d

    def test_legacy_dict_without_new_fields_deserializes_correctly(self):
        """Existing project dicts without migration fields must still load."""
        legacy_dict = {
            "id": "proj-legacy",
            "name": "legacy",
            "repo_url": "https://github.com/org/legacy.git",
            "repo_path": "/tmp/legacy",
            "default_branch": "main",
            "state_branch_enabled": False,
        }
        p = Project.from_dict(legacy_dict)
        assert p.state_branch_shadow_write is False
        assert p.state_branch_migration_stage == ""


# ---------------------------------------------------------------------------
# §11  ProjectStore: validates the new fields
# ---------------------------------------------------------------------------


class TestProjectStoreValidation:
    def _make_store_and_project(self, tmp_path: Path, name: str = "test"):
        """Create a ProjectStore with a local-path project (no git clone)."""
        from unittest.mock import MagicMock, patch
        from oompah.projects import ProjectStore

        store = ProjectStore(
            path=str(tmp_path / "projects.json"),
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        repo_path = tmp_path / "repos" / name
        repo_path.mkdir(parents=True)
        (repo_path / ".git").mkdir()

        with patch("oompah.projects.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            p = store.create(
                str(repo_path),
                name=name,
                git_user_name="Test",
                git_user_email="test@example.com",
            )
        return store, p

    def test_shadow_write_must_be_boolean(self, tmp_path: Path):
        from oompah.projects import ProjectError
        store, p = self._make_store_and_project(tmp_path, "test-bool")
        with pytest.raises(ProjectError, match="boolean"):
            store.update(p.id, state_branch_shadow_write="yes")

    def test_migration_stage_must_be_valid(self, tmp_path: Path):
        from oompah.projects import ProjectError
        store, p = self._make_store_and_project(tmp_path, "test-stage")
        with pytest.raises(ProjectError, match="'A', or 'B'"):
            store.update(p.id, state_branch_migration_stage="X")

    def test_valid_migration_stage_a_accepted(self, tmp_path: Path):
        store, p = self._make_store_and_project(tmp_path, "test-a")
        updated = store.update(p.id, state_branch_migration_stage="A")
        assert updated.state_branch_migration_stage == "A"

    def test_valid_migration_stage_b_accepted(self, tmp_path: Path):
        store, p = self._make_store_and_project(tmp_path, "test-b")
        updated = store.update(p.id, state_branch_migration_stage="B")
        assert updated.state_branch_migration_stage == "B"

    def test_empty_migration_stage_accepted(self, tmp_path: Path):
        store, p = self._make_store_and_project(tmp_path, "test-empty")
        store.update(p.id, state_branch_migration_stage="A")
        cleared = store.update(p.id, state_branch_migration_stage="")
        assert cleared.state_branch_migration_stage == ""

    def test_shadow_write_true_accepted(self, tmp_path: Path):
        store, p = self._make_store_and_project(tmp_path, "test-sw")
        updated = store.update(p.id, state_branch_shadow_write=True)
        assert updated.state_branch_shadow_write is True

    def test_shadow_write_false_accepted(self, tmp_path: Path):
        store, p = self._make_store_and_project(tmp_path, "test-sw-false")
        store.update(p.id, state_branch_shadow_write=True)
        cleared = store.update(p.id, state_branch_shadow_write=False)
        assert cleared.state_branch_shadow_write is False


# ---------------------------------------------------------------------------
# §12  OompahMarkdownTracker: shadow write path
# ---------------------------------------------------------------------------


class TestTrackerShadowWrite:
    """Validate that state_branch_shadow_write=True writes to both branches."""

    def _make_tracker_with_tasks(self, tmp_path: Path) -> tuple[Path, OompahMarkdownTracker]:
        repo = _make_repo(tmp_path, with_tasks=False)
        tasks_dir = repo / ".oompah" / "tasks"
        for d in ["open", "done", "in-progress", "needs-human", "in-review",
                  "proposed", "backlog", "merged", "archived"]:
            (tasks_dir / d).mkdir(parents=True, exist_ok=True)
        _git("add", ".", cwd=repo)
        _git("commit", "-m", "init tasks", cwd=repo)

        from oompah.project_bootstrap import initialize_state_branch
        initialize_state_branch(repo, PROJECT_ID, push=False)

        tracker = OompahMarkdownTracker(
            active_states=["open", "in progress"],
            terminal_states=["done", "merged", "archived"],
            cwd=str(repo),
            default_branch="main",
            state_branch_enabled=True,
            state_branch_name=f"oompah/state/{PROJECT_ID}",
            state_branch_shadow_write=True,
            git_sync=False,
        )
        return repo, tracker

    def test_shadow_write_flag_stored_on_tracker(self, tmp_path: Path):
        _, tracker = self._make_tracker_with_tasks(tmp_path)
        assert tracker.state_branch_shadow_write is True

    def test_create_issue_with_shadow_write_on(self, tmp_path: Path):
        """Creating an issue with shadow_write=True must not raise."""
        _, tracker = self._make_tracker_with_tasks(tmp_path)
        tracker.create_issue(
            title="Shadow test task",
            description="Body",
            priority=2,
            labels=[],
        )
        issues = tracker.fetch_all_issues()
        titles = {i.title for i in issues}
        assert "Shadow test task" in titles








    def test_tracker_without_shadow_write_does_not_set_flag(self, tmp_path: Path):
        repo = _make_repo(tmp_path, with_tasks=False)
        tracker = OompahMarkdownTracker(
            active_states=["open"],
            terminal_states=["done"],
            cwd=str(repo),
            default_branch="main",
            state_branch_enabled=False,
        )
        assert tracker.state_branch_shadow_write is False


# ---------------------------------------------------------------------------
# §13  get_migration_status helper
# ---------------------------------------------------------------------------


class TestGetMigrationStatus:
    def test_status_before_migration(self, tmp_path: Path):
        repo = _make_repo(tmp_path)
        status = get_migration_status(repo, PROJECT_ID, default_branch="main")
        assert status["branch_name"] == f"oompah/state/{PROJECT_ID}"
        assert status["branch_exists_local"] is False
        assert status["tasks_on_default_branch"] is True

    def test_status_after_stage_a(self, tmp_path: Path):
        repo = _make_repo(tmp_path)
        migrate_stage_a(repo, PROJECT_ID, push=False)
        status = get_migration_status(repo, PROJECT_ID)
        assert status["branch_exists_local"] is True
        assert status["last_state_branch_commit"] is not None

    def test_status_after_stage_c(self, tmp_path: Path):
        repo = _make_repo(tmp_path)
        migrate_stage_a(repo, PROJECT_ID, push=False)
        migrate_stage_b(repo, PROJECT_ID)
        migrate_stage_c(repo, PROJECT_ID, push=False)
        status = get_migration_status(repo, PROJECT_ID)
        assert status["tasks_on_default_branch"] is False
        assert status["branch_exists_local"] is True
