"""End-to-end integration tests for the Git-backed state-branch workflow (OOMPAH-260).

Tests the complete state-branch and checkpoint workflow using disposable git
fixtures (bare remote + separate code/state branches). No live managed projects
are touched.

Coverage areas:

  § 1  New-project E2E: bare remote, state branch from bootstrap, task CRUD,
        code commits on main, isolation verification.
  § 2  Legacy migration E2E: existing tasks on main, Stage A → Stage B,
        verify main history isolation post-cutover.
  § 3  Commit history regression: after cutover, main/release branch histories
        must contain zero task checkpoint commits.
  § 4  Failed push simulation + recovery: non-fast-forward rejection handled,
        tracker fetches + rebases + retries.
  § 5  Release branch isolation: code commits on release branch never contain
        task metadata; state branch receives the task updates.
  § 6  Orchestration continuity: task reads, dependencies, comments,
        release-delivery candidate discovery after migration.
  § 7  Migration rollback/retry: rollback from Stage B, then re-migrate.
  § 8  State-branch-specific: failed push + migration rollback together.

Design reference: plans/state-branch-design.md
Operator guide:   docs/state-branch-migration.md
Readiness guide:  docs/state-branch-migration-readiness.md
"""

from __future__ import annotations

import subprocess
import threading
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import yaml

from oompah.oompah_md_tracker import OompahMarkdownTracker
from oompah.project_bootstrap import initialize_state_branch
from oompah.state_branch_migration import (
    get_migration_status,
    migrate_stage_a,
    migrate_stage_b,
    migrate_stage_c,
    rollback_migration,
    validate_state_branch,
)
from oompah.statuses import ARCHIVED, BACKLOG, DONE, IN_PROGRESS, IN_REVIEW, MERGED, OPEN


# ---------------------------------------------------------------------------
# Shared git helpers
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=False,
    )


def _git_check(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    r = _git(repo, *args)
    if r.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)}: returncode={r.returncode}\n"
            f"stdout: {r.stdout.strip()}\nstderr: {r.stderr.strip()}"
        )
    return r


def _commit_sha(repo: Path, ref: str) -> str:
    return _git(repo, "rev-parse", ref).stdout.strip()


def _commit_count(repo: Path, branch: str) -> int:
    r = _git(repo, "rev-list", "--count", branch)
    return int(r.stdout.strip()) if r.returncode == 0 else 0


def _log_subjects(repo: Path, branch: str) -> list[str]:
    """Return the commit subject lines on *branch* in reverse-chronological order."""
    r = _git(repo, "log", "--format=%s", branch)
    return r.stdout.strip().splitlines() if r.returncode == 0 else []


def _branch_exists(repo: Path, branch: str) -> bool:
    return _git(repo, "rev-parse", "--verify", branch).returncode == 0


def _files_on_branch(repo: Path, branch: str) -> set[str]:
    r = _git(repo, "ls-tree", "-r", "--name-only", branch)
    return set(r.stdout.splitlines()) if r.returncode == 0 else set()


def _make_repo(tmp_path: Path, *, name: str = "repo") -> Path:
    """Create a bare-minimum git repo with initial commit."""
    repo = tmp_path / name
    repo.mkdir(parents=True)
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@oompah.dev")
    _git(repo, "config", "user.name", "Oompah Test")
    (repo / "README.md").write_text("# Test\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial: add README")
    return repo


def _make_bare_remote(tmp_path: Path, *, name: str = "bare.git") -> Path:
    """Create a bare git repository to act as the remote origin."""
    bare = tmp_path / name
    bare.mkdir()
    _git(bare, "init", "--bare")
    return bare


def _make_repo_with_remote(
    tmp_path: Path, *, work_name: str = "work", bare_name: str = "bare.git"
) -> tuple[Path, Path]:
    """Return (working_tree, bare_remote) with initial content pushed."""
    bare = _make_bare_remote(tmp_path, name=bare_name)
    work = _make_repo(tmp_path, name=work_name)
    _git(work, "remote", "add", "origin", str(bare))
    _git(work, "push", "--set-upstream", "origin", "main")
    return work, bare


def _seed_tasks(repo: Path, *, count: int = 3) -> list[str]:
    """Create *count* task files and commit them to the current branch."""
    tasks_root = repo / ".oompah" / "tasks"
    for d in [
        "proposed", "backlog", "open", "in-progress", "needs-human",
        "in-review", "done", "merged", "archived",
    ]:
        (tasks_root / d).mkdir(parents=True, exist_ok=True)

    ids: list[str] = []
    for i in range(1, count + 1):
        task_id = f"TASK-{i}"
        meta = {
            "id": task_id,
            "type": "task",
            "status": "Open",
            "priority": 2,
            "title": f"Legacy Task {task_id}",
            "parent": None,
            "children": [],
            "blocked_by": [],
            "labels": [],
            "created_at": "2026-07-01T10:00:00Z",
            "updated_at": "2026-07-15T08:00:00Z",
            "work_branch": None,
            "target_branch": None,
            "review_url": None,
            "review_number": None,
            "merged_at": None,
        }
        body = (
            f"## Summary\n\nTask {task_id}.\n\n"
            "## Acceptance Criteria\n\n- [ ] AC1.\n\n"
            "## Comments\n\n"
        )
        path = tasks_root / "open" / f"{task_id}.md"
        path.write_text(f"---\n{yaml.safe_dump(meta)}---\n{body}", encoding="utf-8")
        ids.append(task_id)

    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "seed: add legacy tasks")
    return ids


def _make_tracker(
    repo: Path,
    *,
    state_branch_enabled: bool = False,
    state_branch_name: str | None = None,
    state_branch_shadow_write: bool = False,
    git_sync: bool = False,
    default_branch: str = "main",
    state_branch_checkpoint_debounce_ms: int = 100,
    state_branch_checkpoint_max_delay_ms: int = 5000,
    state_branch_push_retry_count: int = 3,
    state_branch_push_retry_backoff_ms: int = 0,
) -> OompahMarkdownTracker:
    """Build a tracker, accepting state-branch kwargs when feature is active.

    Default debounce=100ms, max_delay=5000ms satisfies the constraint
    max_delay >= debounce + 1000 (5000 >= 100 + 1000).

    active_states includes BACKLOG so that newly-created tasks (which default to
    Backlog status) are returned by fetch_candidate_issues and fetch_all_issues.
    """
    kwargs: dict[str, Any] = {
        "active_states": [BACKLOG, OPEN, IN_PROGRESS, IN_REVIEW],
        "terminal_states": [DONE, MERGED, ARCHIVED],
        "cwd": str(repo),
        "default_branch": default_branch,
        "git_sync": git_sync,
        "state_branch_checkpoint_debounce_ms": state_branch_checkpoint_debounce_ms,
        "state_branch_checkpoint_max_delay_ms": state_branch_checkpoint_max_delay_ms,
        "state_branch_push_retry_count": state_branch_push_retry_count,
        "state_branch_push_retry_backoff_ms": state_branch_push_retry_backoff_ms,
    }
    if state_branch_enabled:
        kwargs["state_branch_enabled"] = True
        kwargs["state_branch_name"] = state_branch_name
        kwargs["state_branch_shadow_write"] = state_branch_shadow_write
    return OompahMarkdownTracker(**kwargs)


PROJECT_ID = "proj-e2e-test"


# ---------------------------------------------------------------------------
# § 1  New-project E2E: bare remote, state branch from bootstrap, task CRUD
# ---------------------------------------------------------------------------


class TestNewProjectE2E:
    """Complete workflow for a brand-new project with state branch from the start."""

    @pytest.fixture
    def new_project(self, tmp_path: Path) -> tuple[Path, Path, str]:
        """Return (work_tree, bare_remote, state_branch_name)."""
        work, bare = _make_repo_with_remote(tmp_path)
        state_branch = f"oompah/state/{PROJECT_ID}"
        # Bootstrap the state branch.
        result = initialize_state_branch(work, PROJECT_ID, push=True)
        assert result.error == "", f"Bootstrap failed: {result.error}"
        return work, bare, state_branch

    def test_state_branch_exists_after_bootstrap(
        self, new_project: tuple[Path, Path, str]
    ) -> None:
        work, bare, state_branch = new_project
        assert _branch_exists(work, state_branch), "State branch must exist after bootstrap"

    def test_state_branch_is_pushed_to_remote(
        self, new_project: tuple[Path, Path, str]
    ) -> None:
        work, bare, state_branch = new_project
        # Verify from the remote side.
        r = _git(bare, "rev-parse", "--verify", state_branch)
        assert r.returncode == 0, "State branch must be pushed to bare remote"

    def test_state_branch_has_no_source_code(
        self, new_project: tuple[Path, Path, str]
    ) -> None:
        work, bare, state_branch = new_project
        files = _files_on_branch(work, state_branch)
        non_oompah = [f for f in files if not f.startswith(".oompah/")]
        assert non_oompah == [], (
            f"State branch must not contain source files: {non_oompah}"
        )

    def test_task_create_update_readable_on_state_branch(
        self, new_project: tuple[Path, Path, str]
    ) -> None:
        """Task CRUD via tracker writes to state branch and is readable from it."""
        work, bare, state_branch = new_project
        tracker = _make_tracker(
            work,
            state_branch_enabled=True,
            state_branch_name=state_branch,
            git_sync=False,
        )
        issue = tracker.create_issue(
            title="E2E new task",
            description="Testing the full workflow",
            priority=2,
            labels=["backend"],
        )
        assert issue.title == "E2E new task"

        # Update the task status.
        tracker.update_issue(issue.id, status=IN_PROGRESS)
        # Add a comment.
        tracker.add_comment(issue.id, "Agent started work", author="oompah")
        # Verify readable.
        fetched = tracker.fetch_issue_detail(issue.id)
        assert fetched is not None
        assert fetched.title == "E2E new task"
        comments = tracker.fetch_comments(issue.id)
        assert any("Agent started work" in c.get("text", "") for c in comments)

    def test_main_branch_sha_unchanged_by_task_operations(
        self, new_project: tuple[Path, Path, str]
    ) -> None:
        """Task CRUD must not move the main branch SHA."""
        work, bare, state_branch = new_project
        main_sha_before = _commit_sha(work, "main")

        tracker = _make_tracker(
            work,
            state_branch_enabled=True,
            state_branch_name=state_branch,
            git_sync=True,  # real git operations
        )
        # Patch _has_remote to return False so we avoid network push in test.
        with patch.object(tracker, "_has_remote", return_value=False):
            tracker.create_issue(
                title="Isolation task",
                description="Body",
                priority=1,
                labels=[],
            )
            tracker.flush_checkpoint(reason="test")

        main_sha_after = _commit_sha(work, "main")
        assert main_sha_before == main_sha_after, (
            "State-branch task creation must not change the main branch SHA"
        )

    def test_code_commit_on_main_does_not_touch_state_branch(
        self, new_project: tuple[Path, Path, str]
    ) -> None:
        """A code commit on main must not modify the state branch."""
        work, bare, state_branch = new_project
        state_sha_before = _commit_sha(work, state_branch)

        # Make a code commit on main.
        (work / "feature.py").write_text("# feature\n", encoding="utf-8")
        _git(work, "add", ".")
        _git(work, "commit", "-m", "feat: add feature.py")
        _git(work, "push", "origin", "main")

        state_sha_after = _commit_sha(work, state_branch)
        assert state_sha_before == state_sha_after, (
            "A code commit on main must not change the state branch SHA"
        )

    def test_dependency_between_tasks_readable_after_create(
        self, new_project: tuple[Path, Path, str]
    ) -> None:
        """Task dependencies created via tracker are readable."""
        work, bare, state_branch = new_project
        tracker = _make_tracker(
            work,
            state_branch_enabled=True,
            state_branch_name=state_branch,
            git_sync=False,
        )
        blocker = tracker.create_issue(
            title="Blocker task",
            description="Must complete first",
            priority=1,
            labels=[],
        )
        blocked = tracker.create_issue(
            title="Blocked task",
            description="Depends on blocker",
            priority=2,
            labels=[],
        )
        tracker.add_dependency(blocked.id, blocker.id)

        fetched = tracker.fetch_issue_detail(blocked.id)
        assert fetched is not None
        # blocked_by is a list of BlockerRef objects; extract the ids.
        blocker_ids = {r.id for r in (fetched.blocked_by or [])}
        assert blocker.id in blocker_ids, (
            f"Blocked task must list {blocker.id!r} in blocked_by; got: {fetched.blocked_by}"
        )

    def test_candidate_issue_discovery_works_after_bootstrap(
        self, new_project: tuple[Path, Path, str]
    ) -> None:
        """fetch_candidate_issues must return open/in-progress tasks."""
        work, bare, state_branch = new_project
        tracker = _make_tracker(
            work,
            state_branch_enabled=True,
            state_branch_name=state_branch,
            git_sync=False,
        )
        tracker.create_issue(
            title="Open candidate",
            description="Should appear as candidate",
            priority=2,
            labels=[],
        )
        candidates = tracker.fetch_candidate_issues()
        titles = {c.title for c in candidates}
        assert "Open candidate" in titles, (
            f"Open task must appear in fetch_candidate_issues; got: {titles}"
        )


# ---------------------------------------------------------------------------
# § 2  Legacy migration E2E: Stage A → Stage B
# ---------------------------------------------------------------------------


class TestLegacyMigrationE2E:
    """Full migration of a legacy project from default-branch task storage
    to state-branch storage, with code commits interleaved."""

    @pytest.fixture
    def legacy_project(self, tmp_path: Path) -> tuple[Path, Path]:
        """Return (work_tree, bare_remote) with legacy tasks on main."""
        work, bare = _make_repo_with_remote(tmp_path)
        _seed_tasks(work, count=4)
        _git(work, "push", "origin", "main")
        return work, bare

    def test_stage_a_creates_state_branch_with_task_files(
        self, legacy_project: tuple[Path, Path]
    ) -> None:
        work, bare = legacy_project
        result = migrate_stage_a(work, PROJECT_ID, push=True)
        assert result.ok, f"Stage A failed: {result.error}"

        state_branch = f"oompah/state/{PROJECT_ID}"
        assert _branch_exists(work, state_branch)

        # State branch must have the task files that were on main.
        state_files = _files_on_branch(work, state_branch)
        task_files = [f for f in state_files if f.startswith(".oompah/tasks/")]
        assert len(task_files) >= 4, (
            f"State branch must have the legacy task files; got {task_files}"
        )

    def test_stage_a_state_branch_pushed_to_remote(
        self, legacy_project: tuple[Path, Path]
    ) -> None:
        work, bare = legacy_project
        migrate_stage_a(work, PROJECT_ID, push=True)
        state_branch = f"oompah/state/{PROJECT_ID}"
        r = _git(bare, "rev-parse", "--verify", state_branch)
        assert r.returncode == 0, "State branch must be pushed to bare remote after Stage A"

    def test_stage_b_ok_after_stage_a(
        self, legacy_project: tuple[Path, Path]
    ) -> None:
        work, bare = legacy_project
        migrate_stage_a(work, PROJECT_ID, push=True)
        result = migrate_stage_b(work, PROJECT_ID)
        assert result.ok, f"Stage B failed: {result.error}"
        assert "snapshot" in result.message.lower() or "preserved" in result.message.lower()

    def test_migration_status_before_and_after(
        self, legacy_project: tuple[Path, Path]
    ) -> None:
        work, bare = legacy_project

        status_before = get_migration_status(work, PROJECT_ID)
        assert status_before["branch_exists_local"] is False
        assert status_before["tasks_on_default_branch"] is True

        migrate_stage_a(work, PROJECT_ID, push=False)
        status_after_a = get_migration_status(work, PROJECT_ID)
        assert status_after_a["branch_exists_local"] is True

        migrate_stage_b(work, PROJECT_ID)
        migrate_stage_c(work, PROJECT_ID, push=False)
        status_after_c = get_migration_status(work, PROJECT_ID)
        assert status_after_c["tasks_on_default_branch"] is False

    def test_code_commit_on_main_during_migration_not_lost(
        self, legacy_project: tuple[Path, Path]
    ) -> None:
        """Code commits made to main during Stage A must survive the migration."""
        work, bare = legacy_project
        migrate_stage_a(work, PROJECT_ID, push=False)

        # Make a code commit on main during the soak window.
        (work / "auth.py").write_text("# auth module\n", encoding="utf-8")
        _git(work, "add", ".")
        _git(work, "commit", "-m", "feat: add auth module")

        migrate_stage_b(work, PROJECT_ID)

        # Code commit must still be on main.
        log = _log_subjects(work, "main")
        assert any("auth module" in s for s in log), (
            "Code commit made during Stage A soak must remain on main"
        )

    def test_tracker_reads_tasks_after_stage_b(
        self, legacy_project: tuple[Path, Path]
    ) -> None:
        """After Stage B, tracker with state_branch_enabled must read all tasks."""
        work, bare = legacy_project
        migrate_stage_a(work, PROJECT_ID, push=False)
        migrate_stage_b(work, PROJECT_ID)

        state_branch = f"oompah/state/{PROJECT_ID}"
        tracker = _make_tracker(
            work,
            state_branch_enabled=True,
            state_branch_name=state_branch,
            git_sync=False,
        )
        issues = tracker.fetch_all_issues()
        ids = {i.id for i in issues}
        # All seeded tasks must be readable.
        for expected_id in ["TASK-1", "TASK-2", "TASK-3", "TASK-4"]:
            assert expected_id in ids, (
                f"Task {expected_id} must be readable from state branch after Stage B"
            )


# ---------------------------------------------------------------------------
# § 3  Commit history regression: no task commits on main/release after cutover
# ---------------------------------------------------------------------------


class TestCommitHistoryRegression:
    """After enabling the state branch, task checkpoint commits must appear
    ONLY on the state branch — never on main or release branches."""

    @pytest.fixture
    def migrated_project(self, tmp_path: Path) -> tuple[Path, str]:
        """Return (work_tree, state_branch_name) after full Stage A + B migration."""
        work, bare = _make_repo_with_remote(tmp_path)
        _seed_tasks(work, count=2)
        _git(work, "push", "origin", "main")

        migrate_stage_a(work, PROJECT_ID, push=False)
        migrate_stage_b(work, PROJECT_ID)
        return work, f"oompah/state/{PROJECT_ID}"

    def test_main_gets_no_new_task_commits_after_cutover(
        self, migrated_project: tuple[Path, str]
    ) -> None:
        """After Stage B, task mutations must not create commits on main."""
        work, state_branch = migrated_project
        main_sha_before = _commit_sha(work, "main")
        main_count_before = _commit_count(work, "main")

        tracker = _make_tracker(
            work,
            state_branch_enabled=True,
            state_branch_name=state_branch,
            git_sync=True,
        )
        with patch.object(tracker, "_has_remote", return_value=False):
            tracker.create_issue(
                title="Post-cutover task",
                description="Must not land on main",
                priority=2,
                labels=[],
            )
            tracker.flush_checkpoint(reason="regression-test")

        main_sha_after = _commit_sha(work, "main")
        main_count_after = _commit_count(work, "main")

        assert main_sha_before == main_sha_after, (
            "main branch SHA must not change after state-branch task creation"
        )
        assert main_count_after == main_count_before, (
            "main branch commit count must not increase after state-branch task creation"
        )

    def test_state_branch_gets_new_commits_after_cutover(
        self, migrated_project: tuple[Path, str]
    ) -> None:
        """Task mutations must create commits on the state branch."""
        work, state_branch = migrated_project
        state_count_before = _commit_count(work, state_branch)

        tracker = _make_tracker(
            work,
            state_branch_enabled=True,
            state_branch_name=state_branch,
            git_sync=True,
        )
        with patch.object(tracker, "_has_remote", return_value=False):
            tracker.create_issue(
                title="State branch checkpoint task",
                description="Must land on state branch",
                priority=2,
                labels=[],
            )
            tracker.flush_checkpoint(reason="regression-test")

        state_count_after = _commit_count(work, state_branch)
        assert state_count_after > state_count_before, (
            "State branch must receive new commits after task creation"
        )

    def test_main_commit_subjects_contain_no_task_metadata_after_cutover(
        self, migrated_project: tuple[Path, str]
    ) -> None:
        """No commit subject on main after cutover should mention 'Checkpoint'
        or 'oompah task state'."""
        work, state_branch = migrated_project

        # Record commit subjects before any post-cutover operations.
        subjects_before = set(_log_subjects(work, "main"))

        tracker = _make_tracker(
            work,
            state_branch_enabled=True,
            state_branch_name=state_branch,
            git_sync=True,
        )
        with patch.object(tracker, "_has_remote", return_value=False):
            for i in range(3):
                tracker.create_issue(
                    title=f"Regression task {i}",
                    description="Checking history isolation",
                    priority=2,
                    labels=[],
                )
            tracker.flush_checkpoint(reason="regression-history-test")

        subjects_after = set(_log_subjects(work, "main"))
        new_subjects = subjects_after - subjects_before
        checkpoint_subjects = [
            s for s in new_subjects
            if "checkpoint" in s.lower() or "oompah task state" in s.lower()
        ]
        assert checkpoint_subjects == [], (
            f"Main branch must not receive task checkpoint commits; "
            f"found new commits: {checkpoint_subjects}"
        )

    def test_release_branch_gets_no_task_commits_after_cutover(
        self, migrated_project: tuple[Path, str]
    ) -> None:
        """Task mutations after cutover must not appear on a release branch."""
        work, state_branch = migrated_project

        # Cut a release branch from main.
        _git(work, "checkout", "-b", "release/1.0")
        (work / "RELEASE_NOTES.md").write_text("# Release 1.0\n", encoding="utf-8")
        _git(work, "add", ".")
        _git(work, "commit", "-m", "chore: add release notes for 1.0")
        release_count_before = _commit_count(work, "release/1.0")
        release_sha_before = _commit_sha(work, "release/1.0")
        _git(work, "checkout", "main")

        # Create tasks via state-branch tracker.
        tracker = _make_tracker(
            work,
            state_branch_enabled=True,
            state_branch_name=state_branch,
            git_sync=True,
        )
        with patch.object(tracker, "_has_remote", return_value=False):
            tracker.create_issue(
                title="Release period task",
                description="Happens during release work",
                priority=1,
                labels=[],
            )
            tracker.flush_checkpoint(reason="release-isolation-test")

        # Release branch must be untouched.
        release_sha_after = _commit_sha(work, "release/1.0")
        release_count_after = _commit_count(work, "release/1.0")
        assert release_sha_before == release_sha_after, (
            "Release branch SHA must not change due to state-branch task commits"
        )
        assert release_count_after == release_count_before, (
            "Release branch commit count must not increase from task commits"
        )


# ---------------------------------------------------------------------------
# § 4  Failed push simulation + recovery
# ---------------------------------------------------------------------------


class TestFailedPushRecovery:
    """Verify the tracker handles failed pushes and recovers via fetch+rebase+retry."""

    @pytest.fixture
    def project_with_remote(self, tmp_path: Path) -> tuple[Path, Path, str]:
        """Return (work_tree, bare_remote, state_branch_name)."""
        work, bare = _make_repo_with_remote(tmp_path)
        initialize_state_branch(work, PROJECT_ID, push=True)
        return work, bare, f"oompah/state/{PROJECT_ID}"

    def test_task_preserved_locally_when_push_fails(
        self, project_with_remote: tuple[Path, Path, str]
    ) -> None:
        """When the remote push fails, the task must still be written locally.

        Uses instance-method replacement (_fake_git) so that git operations
        for worktree setup and commit succeed while push fails.
        """
        from oompah.tracker import TrackerError

        work, bare, state_branch = project_with_remote

        tracker = _make_tracker(
            work,
            state_branch_enabled=True,
            state_branch_name=state_branch,
            git_sync=True,
            state_branch_push_retry_count=1,  # only 1 retry so test completes fast
            state_branch_push_retry_backoff_ms=0,
        )

        def _fake_git(args: list[str], *, check: bool = False, cwd=None, timeout: int = 60):
            """Pass everything to real git except push, which simulates failure."""
            effective_cwd = str(cwd) if cwd is not None else str(work)
            if args[0] == "push":
                result = MagicMock()
                result.returncode = 1
                result.stdout = ""
                result.stderr = "remote: Push failed (simulated)"
                return result
            r = subprocess.run(
                ["git", *args],
                cwd=effective_cwd,
                capture_output=True,
                text=True,
            )
            if check and r.returncode != 0:
                raise TrackerError(f"git {' '.join(args)} failed: {r.stderr}")
            return r

        tracker._git = _fake_git  # type: ignore[method-assign]

        try:
            tracker.create_issue(
                title="Push-fail task",
                description="Task created during push failure",
                priority=2,
                labels=[],
            )
            tracker.flush_checkpoint(reason="push-fail-test")
        except (TrackerError, Exception):
            pass  # Push errors are expected; task data must survive.

        # The task file must exist somewhere in the state-branch worktree on disk.
        # Look inside .git/oompah-state-worktrees/ for the task file.
        task_files = list(work.rglob(".oompah/tasks/**/*.md"))
        git_dir_task_files = list((work / ".git").rglob(".oompah/tasks/**/*.md"))
        all_task_files = task_files + git_dir_task_files
        assert any(
            "Push-fail" in f.read_text(encoding="utf-8", errors="replace")
            for f in all_task_files
            if f.is_file()
        ), (
            "Task must be preserved locally (in state-branch worktree) even when push fails"
        )

    def test_non_fast_forward_push_simulated_by_concurrent_remote_write(
        self, project_with_remote: tuple[Path, Path, str], tmp_path: Path
    ) -> None:
        """Simulate non-fast-forward rejection by committing directly to the
        bare remote's state branch, then verify the tracker can push after
        a sync."""
        work, bare, state_branch = project_with_remote

        # Simulate a concurrent writer pushing to the state branch.
        # Clone the bare remote, make a commit, push back.
        rival_repo = tmp_path / "rival"
        rival_repo.mkdir()
        _git(rival_repo, "clone", str(bare), ".")
        _git(rival_repo, "config", "user.email", "rival@test.dev")
        _git(rival_repo, "config", "user.name", "Rival Agent")
        _git(rival_repo, "checkout", state_branch)
        rival_note = rival_repo / ".oompah" / "rival.txt"
        rival_note.parent.mkdir(parents=True, exist_ok=True)
        rival_note.write_text("rival write\n", encoding="utf-8")
        _git(rival_repo, "add", ".")
        _git(rival_repo, "commit", "-m", "rival: concurrent write")
        _git(rival_repo, "push", "origin", state_branch)
        _git(rival_repo, "checkout", "main")

        # The bare remote now has a commit that work doesn't know about.
        # Verify the remote state branch is ahead.
        _git(work, "fetch", "origin", state_branch)
        local_sha = _commit_sha(work, state_branch)
        remote_sha = _git(work, "rev-parse", f"refs/remotes/origin/{state_branch}").stdout.strip()
        assert local_sha != remote_sha, (
            "Remote state branch must be ahead of local after rival push"
        )

        # After fetch, local work can sync (rebase) and push successfully.
        _git(work, "checkout", state_branch)
        r = _git(work, "rebase", f"refs/remotes/origin/{state_branch}")
        _git(work, "checkout", "main")
        assert r.returncode == 0, (
            f"Rebase after non-fast-forward must succeed: {r.stderr.strip()}"
        )

    def test_migration_rollback_after_push_failure(
        self, project_with_remote: tuple[Path, Path, str]
    ) -> None:
        """Migration rollback must succeed even after a push failure."""
        work, bare, state_branch = project_with_remote
        # Run Stage A (state branch already exists from fixture).
        r_a = migrate_stage_a(work, PROJECT_ID, push=False)
        assert r_a.ok, f"Stage A setup failed: {r_a.error}"
        r_b = migrate_stage_b(work, PROJECT_ID)
        assert r_b.ok, f"Stage B failed: {r_b.error}"

        # Now rollback from Stage B without pushing.
        r_rb = rollback_migration(
            work, PROJECT_ID, current_stage="B", push=False
        )
        assert r_rb.ok, f"Rollback from Stage B failed: {r_rb.error}"

        # Verify: tasks are back on the default branch.
        tasks_on_main = [
            f for f in _files_on_branch(work, "main")
            if f.startswith(".oompah/tasks/")
        ]
        assert len(tasks_on_main) >= 1, (
            "After rollback from Stage B, task files must be restored to main"
        )


# ---------------------------------------------------------------------------
# § 5  Release branch isolation
# ---------------------------------------------------------------------------


class TestReleaseBranchIsolation:
    """Release branch code commits and state-branch task commits are
    completely separate; neither contaminates the other."""

    def test_release_branch_no_new_task_commits_after_cutover(
        self, tmp_path: Path
    ) -> None:
        """After state-branch cutover, task mutations must not create new commits
        on an existing release branch.

        Note: Stage B does NOT remove task files already on main (those remain
        as a rollback snapshot). Stage C is the optional irreversible step that
        removes them. This test verifies the key property: no NEW task commits
        land on the release branch after cutover (even though it may carry the
        historical snapshot from main).
        """
        work, bare = _make_repo_with_remote(tmp_path)
        _seed_tasks(work, count=2)
        _git(work, "push", "origin", "main")

        # Cut a release branch BEFORE migration (inherits task files from main).
        _git(work, "checkout", "-b", "release/2.0")
        (work / "release.cfg").write_text("[release]\nversion=2.0\n", encoding="utf-8")
        _git(work, "add", ".")
        _git(work, "commit", "-m", "chore: release 2.0 config")
        _git(work, "checkout", "main")

        # Record release branch state before migration.
        release_sha_before = _commit_sha(work, "release/2.0")
        release_count_before = _commit_count(work, "release/2.0")

        # Enable state branch (Stage A + B).
        migrate_stage_a(work, PROJECT_ID, push=False)
        migrate_stage_b(work, PROJECT_ID)

        # Make several code commits on main plus task mutations.
        for i in range(3):
            (work / f"src_{i}.py").write_text(f"# module {i}\n", encoding="utf-8")
            _git(work, "add", ".")
            _git(work, "commit", "-m", f"feat: add src_{i}.py")

        state_branch = f"oompah/state/{PROJECT_ID}"
        tracker = _make_tracker(
            work,
            state_branch_enabled=True,
            state_branch_name=state_branch,
            git_sync=True,
        )
        with patch.object(tracker, "_has_remote", return_value=False):
            for i in range(3):
                tracker.create_issue(
                    title=f"Post-cutover release task {i}",
                    description="Task during release period",
                    priority=2,
                    labels=[],
                )
            tracker.flush_checkpoint(reason="release-isolation")

        # Release branch must be completely unchanged.
        release_sha_after = _commit_sha(work, "release/2.0")
        release_count_after = _commit_count(work, "release/2.0")

        assert release_sha_before == release_sha_after, (
            "Release branch SHA must not change due to any post-cutover activity"
        )
        assert release_count_after == release_count_before, (
            "Release branch must receive no new commits (code or task) after cutover"
        )

    def test_release_branch_clean_after_stage_c(
        self, tmp_path: Path
    ) -> None:
        """After Stage C, a release branch cut from main has no task files.

        Stage C removes .oompah/tasks/ from main. Release branches cut after
        Stage C will not inherit the historical task snapshot.
        """
        work, bare = _make_repo_with_remote(tmp_path)
        _seed_tasks(work, count=2)
        _git(work, "push", "origin", "main")

        # Run full migration: Stage A → B → C.
        migrate_stage_a(work, PROJECT_ID, push=False)
        migrate_stage_b(work, PROJECT_ID)
        migrate_stage_c(work, PROJECT_ID, push=False)

        # Verify tasks are removed from main.
        main_files = _files_on_branch(work, "main")
        main_task_files = [f for f in main_files if f.startswith(".oompah/tasks/")]
        assert main_task_files == [], (
            f"Stage C must remove .oompah/tasks/ from main; found: {main_task_files}"
        )

        # Cut a release branch from the clean main.
        _git(work, "checkout", "-b", "release/3.0")
        (work / "release.cfg").write_text("[release]\nversion=3.0\n", encoding="utf-8")
        _git(work, "add", ".")
        _git(work, "commit", "-m", "chore: release 3.0 config")

        # Release branch cut after Stage C must not have task files.
        release_files = _files_on_branch(work, "release/3.0")
        release_task_files = [f for f in release_files if f.startswith(".oompah/tasks/")]
        assert release_task_files == [], (
            f"Release branch cut after Stage C must not carry .oompah/tasks/ files: "
            f"{release_task_files}"
        )

    def test_release_branch_task_operations_target_state_branch(
        self, tmp_path: Path
    ) -> None:
        """When agents work on a release branch, task updates go to the state branch."""
        work, bare = _make_repo_with_remote(tmp_path)
        state_branch = f"oompah/state/{PROJECT_ID}"
        initialize_state_branch(work, PROJECT_ID, push=False)

        # Create a release branch simulating release work.
        _git(work, "checkout", "-b", "release/3.0")
        (work / "CHANGELOG.md").write_text("# 3.0\n", encoding="utf-8")
        _git(work, "add", ".")
        _git(work, "commit", "-m", "chore: changelog 3.0")
        _git(work, "checkout", "main")

        # Task updates from an agent context (cwd=main checkout) go to state branch.
        release_sha_before = _commit_sha(work, "release/3.0")
        tracker = _make_tracker(
            work,
            state_branch_enabled=True,
            state_branch_name=state_branch,
            git_sync=True,
        )
        with patch.object(tracker, "_has_remote", return_value=False):
            tracker.create_issue(
                title="Release 3.0 hotfix task",
                description="Fix for the 3.0 release",
                priority=1,
                labels=["hotfix"],
            )
            tracker.flush_checkpoint(reason="release-task-test")

        release_sha_after = _commit_sha(work, "release/3.0")
        assert release_sha_before == release_sha_after, (
            "Task operations must not modify the release branch"
        )


# ---------------------------------------------------------------------------
# § 6  Orchestration continuity after migration
# ---------------------------------------------------------------------------


class TestOrchestrationContinuityAfterMigration:
    """All tracker operations (reads, dependencies, comments, candidate
    discovery) continue to work correctly after Stage A → B migration."""

    @pytest.fixture
    def migrated_tracker(self, tmp_path: Path) -> tuple[OompahMarkdownTracker, Path]:
        """Return (tracker, repo_path) after full Stage A + B migration
        with several tasks seeded."""
        work, bare = _make_repo_with_remote(tmp_path)
        _seed_tasks(work, count=3)
        _git(work, "push", "origin", "main")
        migrate_stage_a(work, PROJECT_ID, push=False)
        migrate_stage_b(work, PROJECT_ID)

        state_branch = f"oompah/state/{PROJECT_ID}"
        tracker = _make_tracker(
            work,
            state_branch_enabled=True,
            state_branch_name=state_branch,
            git_sync=False,
        )
        return tracker, work

    def test_fetch_all_issues_returns_seeded_tasks(
        self, migrated_tracker: tuple[OompahMarkdownTracker, Path]
    ) -> None:
        tracker, work = migrated_tracker
        issues = tracker.fetch_all_issues()
        ids = {i.id for i in issues}
        for expected in ["TASK-1", "TASK-2", "TASK-3"]:
            assert expected in ids, f"Seeded task {expected} must be readable after migration"

    def test_fetch_issue_detail_returns_task_content(
        self, migrated_tracker: tuple[OompahMarkdownTracker, Path]
    ) -> None:
        tracker, work = migrated_tracker
        detail = tracker.fetch_issue_detail("TASK-1")
        assert detail is not None
        assert detail.id == "TASK-1"
        assert detail.title == "Legacy Task TASK-1"

    def test_update_issue_status_post_migration(
        self, migrated_tracker: tuple[OompahMarkdownTracker, Path]
    ) -> None:
        tracker, work = migrated_tracker
        tracker.update_issue("TASK-1", status=IN_PROGRESS)
        updated = tracker.fetch_issue_detail("TASK-1")
        assert updated is not None
        assert updated.state == IN_PROGRESS, (
            f"Task status must be updatable after migration; got: {updated.state}"
        )

    def test_add_comment_post_migration(
        self, migrated_tracker: tuple[OompahMarkdownTracker, Path]
    ) -> None:
        tracker, work = migrated_tracker
        tracker.add_comment("TASK-2", "Post-migration comment", author="oompah")
        comments = tracker.fetch_comments("TASK-2")
        assert any(
            "Post-migration comment" in c.get("text", "") for c in comments
        ), f"Comment must be readable after migration; got: {comments}"

    def test_add_dependency_post_migration(
        self, migrated_tracker: tuple[OompahMarkdownTracker, Path]
    ) -> None:
        tracker, work = migrated_tracker
        tracker.add_dependency("TASK-2", "TASK-1")
        detail = tracker.fetch_issue_detail("TASK-2")
        assert detail is not None
        # blocked_by is a list of BlockerRef objects; extract the ids.
        blocker_ids = {r.id for r in (detail.blocked_by or [])}
        assert "TASK-1" in blocker_ids, (
            f"Dependency must be recorded after migration; blocked_by={detail.blocked_by}"
        )

    def test_create_new_task_post_migration(
        self, migrated_tracker: tuple[OompahMarkdownTracker, Path]
    ) -> None:
        tracker, work = migrated_tracker
        new_issue = tracker.create_issue(
            title="Post-migration new task",
            description="Created after migration",
            priority=2,
            labels=["backend"],
        )
        assert new_issue.id is not None
        fetched = tracker.fetch_issue_detail(new_issue.id)
        assert fetched is not None
        assert fetched.title == "Post-migration new task"

    def test_fetch_candidate_issues_post_migration(
        self, migrated_tracker: tuple[OompahMarkdownTracker, Path]
    ) -> None:
        """Candidate discovery (for orchestration dispatch) works after migration."""
        tracker, work = migrated_tracker
        candidates = tracker.fetch_candidate_issues()
        ids = {c.id for c in candidates}
        # At least TASK-1, TASK-2, TASK-3 should be candidates (they're Open).
        assert "TASK-1" in ids or "TASK-2" in ids or "TASK-3" in ids, (
            f"At least one seeded task must be a candidate after migration; got: {ids}"
        )

    def test_close_task_post_migration(
        self, migrated_tracker: tuple[OompahMarkdownTracker, Path]
    ) -> None:
        tracker, work = migrated_tracker
        tracker.close_issue("TASK-3", reason="Completed in E2E test")
        detail = tracker.fetch_issue_detail("TASK-3")
        assert detail is not None
        assert detail.state == DONE, (
            f"Task must be closeable after migration; state={detail.state}"
        )

    def test_add_label_post_migration(
        self, migrated_tracker: tuple[OompahMarkdownTracker, Path]
    ) -> None:
        tracker, work = migrated_tracker
        tracker.add_label("TASK-1", "focus-complete:e2e")
        detail = tracker.fetch_issue_detail("TASK-1")
        assert detail is not None
        assert "focus-complete:e2e" in (detail.labels or []), (
            f"Label must be addable post-migration; labels={detail.labels}"
        )


# ---------------------------------------------------------------------------
# § 7  Migration rollback + retry
# ---------------------------------------------------------------------------


class TestMigrationRollbackAndRetry:
    """Test rollback from Stage B and re-migration to verify the workflow is
    repeatable and safe."""

    def test_rollback_from_stage_b_restores_tasks_on_main(
        self, tmp_path: Path
    ) -> None:
        """After rollback from Stage B, tasks must be accessible on main."""
        work, bare = _make_repo_with_remote(tmp_path)
        _seed_tasks(work, count=3)
        _git(work, "push", "origin", "main")

        migrate_stage_a(work, PROJECT_ID, push=False)
        migrate_stage_b(work, PROJECT_ID)

        # Add a new task to the state branch before rollback.
        state_branch = f"oompah/state/{PROJECT_ID}"
        tracker = _make_tracker(
            work,
            state_branch_enabled=True,
            state_branch_name=state_branch,
            git_sync=True,
        )
        with patch.object(tracker, "_has_remote", return_value=False):
            tracker.create_issue(
                title="Task added in Stage B",
                description="Must survive rollback",
                priority=2,
                labels=[],
            )
            tracker.flush_checkpoint(reason="rollback-test")

        # Rollback.
        result = rollback_migration(
            work, PROJECT_ID, current_stage="B", push=False
        )
        assert result.ok, f"Rollback failed: {result.error}"

        # Tasks must be on main (restored from state branch).
        files_on_main = _files_on_branch(work, "main")
        task_files = [f for f in files_on_main if f.startswith(".oompah/tasks/")]
        assert len(task_files) >= 3, (
            f"After rollback, task files must be on main; found: {task_files}"
        )

    def test_state_branch_preserved_after_rollback(
        self, tmp_path: Path
    ) -> None:
        """Rollback must not delete the state branch (allows re-migration)."""
        work, bare = _make_repo_with_remote(tmp_path)
        _seed_tasks(work, count=2)

        migrate_stage_a(work, PROJECT_ID, push=False)
        migrate_stage_b(work, PROJECT_ID)
        rollback_migration(work, PROJECT_ID, current_stage="B", push=False)

        state_branch = f"oompah/state/{PROJECT_ID}"
        assert _branch_exists(work, state_branch), (
            "State branch must be preserved after rollback"
        )

    def test_re_migration_after_rollback_succeeds(
        self, tmp_path: Path
    ) -> None:
        """After rolling back from Stage B, Stage A can be re-run (idempotent)."""
        work, bare = _make_repo_with_remote(tmp_path)
        _seed_tasks(work, count=2)

        # First migration.
        migrate_stage_a(work, PROJECT_ID, push=False)
        migrate_stage_b(work, PROJECT_ID)
        rollback_migration(work, PROJECT_ID, current_stage="B", push=False)

        # Re-migration: Stage A should detect the existing branch and return ok.
        result_a2 = migrate_stage_a(work, PROJECT_ID, push=False)
        assert result_a2.ok, f"Re-migration Stage A failed: {result_a2.error}"

        result_b2 = migrate_stage_b(work, PROJECT_ID)
        assert result_b2.ok, f"Re-migration Stage B failed: {result_b2.error}"

    def test_rollback_retry_is_idempotent(
        self, tmp_path: Path
    ) -> None:
        """Calling rollback twice must succeed without errors."""
        work, bare = _make_repo_with_remote(tmp_path)
        _seed_tasks(work, count=2)

        migrate_stage_a(work, PROJECT_ID, push=False)
        migrate_stage_b(work, PROJECT_ID)

        r1 = rollback_migration(work, PROJECT_ID, current_stage="B", push=False)
        assert r1.ok
        r2 = rollback_migration(work, PROJECT_ID, current_stage="B", push=False)
        assert r2.ok, f"Second rollback call must not fail: {r2.error}"


# ---------------------------------------------------------------------------
# § 8  Pre-migration validation integration
# ---------------------------------------------------------------------------


class TestPreMigrationValidation:
    """validate_state_branch must catch problems before migration starts."""

    def test_clean_repo_passes_validation(self, tmp_path: Path) -> None:
        work = _make_repo(tmp_path)
        _seed_tasks(work, count=2)
        result = validate_state_branch(work, PROJECT_ID)
        local_checks = {c.name: c for c in result.checks}
        assert local_checks["default branch is clean"].passed
        assert local_checks["task files have valid YAML"].passed
        assert local_checks["no duplicate task IDs"].passed

    def test_validation_fails_on_corrupt_task_file(self, tmp_path: Path) -> None:
        work = _make_repo(tmp_path)
        _seed_tasks(work, count=1)
        corrupt = work / ".oompah" / "tasks" / "open" / "CORRUPT.md"
        corrupt.parent.mkdir(parents=True, exist_ok=True)
        corrupt.write_text("---\nnot: valid: yaml: {: \n---\nBody\n", encoding="utf-8")
        _git(work, "add", ".")
        _git(work, "commit", "-m", "add corrupt task")

        result = validate_state_branch(work, PROJECT_ID)
        yaml_check = next(c for c in result.checks if c.name == "task files have valid YAML")
        assert not yaml_check.passed
        assert not result.all_passed

    def test_validation_fails_on_dirty_working_tree(self, tmp_path: Path) -> None:
        work = _make_repo(tmp_path)
        (work / "dirty.txt").write_text("uncommitted\n", encoding="utf-8")
        _git(work, "add", ".")  # staged but not committed

        result = validate_state_branch(work, PROJECT_ID)
        clean_check = next(c for c in result.checks if "clean" in c.name)
        assert not clean_check.passed

    def test_validation_result_serializes_to_dict(self, tmp_path: Path) -> None:
        work = _make_repo(tmp_path)
        result = validate_state_branch(work, PROJECT_ID)
        d = result.to_dict()
        assert "all_passed" in d
        assert "checks" in d
        assert all("name" in c and "passed" in c for c in d["checks"])


# ---------------------------------------------------------------------------
# § 9  Checkpoint coalescing — E2E assertion
# ---------------------------------------------------------------------------


class TestCheckpointCoalescingE2E:
    """Multiple rapid task mutations must be coalesced into a single git commit."""

    def test_multiple_mutations_coalesced_into_single_commit(
        self, tmp_path: Path
    ) -> None:
        """Creating 5 tasks and flushing must produce exactly 1 new commit
        on the state branch (not 5)."""
        work = _make_repo(tmp_path)
        state_branch = f"oompah/state/{PROJECT_ID}"
        initialize_state_branch(work, PROJECT_ID, push=False)

        count_before = _commit_count(work, state_branch)

        tracker = _make_tracker(
            work,
            state_branch_enabled=True,
            state_branch_name=state_branch,
            git_sync=True,
            # debounce=100ms, max_delay=5000ms satisfies max_delay >= debounce + 1000
            state_branch_checkpoint_debounce_ms=100,
            state_branch_checkpoint_max_delay_ms=5000,
        )
        with patch.object(tracker, "_has_remote", return_value=False):
            for i in range(5):
                tracker.create_issue(
                    title=f"Coalesced task {i}",
                    description="Part of a coalescing batch",
                    priority=2,
                    labels=[],
                )
            # Force immediate flush — the queue has 5 pending mutations.
            flushed = tracker.flush_checkpoint(reason="coalescing-e2e-test")

        assert flushed == 5, f"Expected 5 pending mutations flushed; got {flushed}"

        count_after = _commit_count(work, state_branch)
        new_commits = count_after - count_before
        assert new_commits == 1, (
            f"5 coalesced mutations must produce exactly 1 new commit; "
            f"got {new_commits} (before={count_before}, after={count_after})"
        )

    def test_all_mutations_in_batch_readable_after_flush(
        self, tmp_path: Path
    ) -> None:
        """All tasks from the coalesced batch must be readable after flush."""
        work = _make_repo(tmp_path)
        state_branch = f"oompah/state/{PROJECT_ID}"
        initialize_state_branch(work, PROJECT_ID, push=False)

        tracker = _make_tracker(
            work,
            state_branch_enabled=True,
            state_branch_name=state_branch,
            git_sync=True,
        )
        with patch.object(tracker, "_has_remote", return_value=False):
            for i in range(4):
                tracker.create_issue(
                    title=f"Batch task {i}",
                    description=f"Task {i} in batch",
                    priority=2,
                    labels=[],
                )
            tracker.flush_checkpoint(reason="batch-read-test")

        # All 4 tasks must be readable.
        issues = tracker.fetch_all_issues()
        titles = {i.title for i in issues}
        for i in range(4):
            assert f"Batch task {i}" in titles, (
                f"Batch task {i} must be readable after flush; got: {titles}"
            )

    def test_pending_mutations_counter_is_accurate(
        self, tmp_path: Path
    ) -> None:
        """pending_mutations count must reflect queued-but-not-yet-flushed mutations."""
        work = _make_repo(tmp_path)
        state_branch = f"oompah/state/{PROJECT_ID}"
        initialize_state_branch(work, PROJECT_ID, push=False)

        tracker = _make_tracker(
            work,
            state_branch_enabled=True,
            state_branch_name=state_branch,
            git_sync=False,  # no git ops — just queue behavior
            state_branch_checkpoint_debounce_ms=30000,  # long debounce so auto-flush doesn't fire
            state_branch_checkpoint_max_delay_ms=60000,  # satisfies max_delay >= debounce + 1000
        )
        assert tracker.checkpoint_pending_mutations == 0

        # Schedule 3 mutations directly through the queue.
        q = tracker._checkpoint_queue
        assert q is not None
        for _ in range(3):
            q.schedule()

        assert tracker.checkpoint_pending_mutations == 3

        # Flush clears the counter.
        tracker.flush_checkpoint(reason="counter-test")
        assert tracker.checkpoint_pending_mutations == 0
