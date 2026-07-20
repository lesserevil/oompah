"""Tests for state-branch-aware OompahMarkdownTracker (OOMPAH-256).

These tests define the acceptance contracts for extending the native Markdown
tracker so that:

  - A project configured with ``state_branch_enabled=True`` routes all reads
    and writes through its dedicated ``oompah/state/<project-id>`` branch.
  - Code ``main`` (and all other code branches) remain byte-for-byte unchanged
    by normal tracker operations.
  - Legacy projects (``state_branch_enabled=False``) continue to work exactly
    as before: reads and writes use the configured default branch.

Tests that exercise the not-yet-implemented state-branch routing are marked
``@pytest.mark.xfail(strict=False)`` so that:

  1. They are informative today — they document the expected contract and fail
     with a clear reason when the feature is missing.
  2. They automatically convert to passing tests once the feature agent adds
     the ``state_branch_enabled`` / ``state_branch_name`` parameters to
     ``OompahMarkdownTracker.__init__`` and implements the routing logic.
  3. CI continues to pass in the meantime (``strict=False`` marks an xfail as
     *expected* rather than a hard failure).

Coverage areas:
  § 1  Feature detection helpers
  § 2  Integration fixture — state branch isolates writes from main
  § 3  Legacy fixture — default-branch behavior is unchanged
  § 4  Failure handling — missing branch, auth error, non-fast-forward push
  § 5  Concurrency — simultaneous code fetch and tracker write
  § 6  Orchestrator wiring — _new_tracker_for_project passes state-branch params
"""

from __future__ import annotations

import inspect
import subprocess
import threading
import time
from pathlib import Path
from typing import Iterator
from unittest.mock import MagicMock, call, patch

import pytest
import yaml

from oompah.oompah_md_tracker import OompahMarkdownTracker
from oompah.statuses import DONE, IN_PROGRESS, IN_REVIEW, OPEN
from oompah.tracker import TrackerError


# ---------------------------------------------------------------------------
# § 1 — Feature detection
#
# Detect whether the implementation has added state_branch_enabled to the
# OompahMarkdownTracker constructor.  This drives the xfail markers below.
# ---------------------------------------------------------------------------

_TRACKER_SIG = inspect.signature(OompahMarkdownTracker.__init__)
_STATE_BRANCH_TRACKER_IMPLEMENTED = (
    "state_branch_enabled" in _TRACKER_SIG.parameters
)

#: Decorator: skip-on-fail if state-branch routing is not yet implemented.
state_branch_not_implemented = pytest.mark.xfail(
    not _STATE_BRANCH_TRACKER_IMPLEMENTED,
    strict=False,
    reason=(
        "OompahMarkdownTracker.state_branch_enabled not yet implemented (OOMPAH-256). "
        "Remove xfail once the feature agent adds the parameter and routing logic."
    ),
)


# ---------------------------------------------------------------------------
# § 0 — Shared test helpers / fixtures
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=check,
    )


def _commit_sha(repo: Path, branch: str) -> str:
    """Return the current commit SHA for *branch* in *repo*."""
    result = _git(repo, "rev-parse", branch)
    return result.stdout.strip()


def _make_completed_process(returncode: int, stdout: str = "", stderr: str = "") -> MagicMock:
    """Build a mock CompletedProcess for _git() to return."""
    proc = MagicMock()
    proc.returncode = returncode
    proc.stdout = stdout
    proc.stderr = stderr
    return proc


def _init_git_repo(root: Path, *, branch: str = "main") -> Path:
    """Initialise a bare-minimum git repo in *root* and return the path."""
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-b", branch)
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test Agent")
    # Create an initial commit so the branch exists
    readme = root / "README.md"
    readme.write_text("# test\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "Initial commit")
    return root


def _create_state_branch(repo: Path, state_branch: str) -> None:
    """Create an orphan state branch seeded from the repo's .oompah/ content.

    The state branch is an orphan so it shares no history with main.
    Only .oompah/ content is included (no source files).
    """
    # Create the state branch as an orphan
    _git(repo, "checkout", "--orphan", state_branch)
    _git(repo, "reset", "--hard")  # unstage everything from previous tree

    # Seed .oompah/ if it exists on main
    tasks_root = repo / ".oompah" / "tasks"
    tasks_root.mkdir(parents=True, exist_ok=True)
    for subdir in [
        "proposed", "backlog", "open", "in-progress", "needs-human",
        "needs-ci-fix", "needs-rebase", "in-review", "decomposed",
        "duplicate-candidate", "done", "merged", "archived",
    ]:
        (tasks_root / subdir).mkdir(exist_ok=True)
        # Git requires at least one file to track an empty directory
        (tasks_root / subdir / ".gitkeep").write_text("", encoding="utf-8")

    _git(repo, "add", ".oompah/")
    _git(repo, "commit", "-m", f"Bootstrap oompah state branch")

    # Return to main
    _git(repo, "checkout", "main")


def _make_tracker(
    repo: Path,
    *,
    state_branch_enabled: bool = False,
    state_branch_name: str | None = None,
    git_sync: bool = False,
    default_branch: str = "main",
) -> OompahMarkdownTracker:
    """Instantiate an OompahMarkdownTracker with optional state-branch support.

    When state_branch_enabled=True, passes the appropriate kwargs to the
    tracker constructor.  These kwargs are the expected future API:
      - state_branch_enabled: bool
      - state_branch_name: str  (e.g. "oompah/state/proj-test")
    """
    if state_branch_enabled:
        if not _STATE_BRANCH_TRACKER_IMPLEMENTED:
            pytest.xfail(
                "OompahMarkdownTracker.state_branch_enabled not yet implemented "
                "(OOMPAH-256)"
            )
        return OompahMarkdownTracker(
            active_states=[OPEN],
            terminal_states=[DONE],
            cwd=str(repo),
            default_branch=default_branch,
            git_sync=git_sync,
            state_branch_enabled=True,
            state_branch_name=state_branch_name,
        )
    return OompahMarkdownTracker(
        active_states=[OPEN],
        terminal_states=[DONE],
        cwd=str(repo),
        default_branch=default_branch,
        git_sync=git_sync,
    )


# ---------------------------------------------------------------------------
# § 2 — Integration fixture: state branch isolates writes from code main
#
# Contract:
#   - All task mutations (create, update status, add comment, dependency)
#     create commits ONLY on the configured state branch.
#   - The code main branch HEAD SHA is never changed by normal tracker ops.
#   - The tracker reads tasks from the state branch (not from main).
# ---------------------------------------------------------------------------


@pytest.fixture
def state_branch_repo(tmp_path: Path) -> tuple[Path, str]:
    """Create a git repo with main and a state branch.

    Returns (repo_path, state_branch_name).
    The repo has:
    - main: initial commit with README.md + empty .oompah/
    - oompah/state/proj-test: orphan branch with .oompah/tasks/ structure
    """
    repo = tmp_path / "state-branch-repo"
    _init_git_repo(repo)
    state_branch = "oompah/state/proj-test"
    _create_state_branch(repo, state_branch)
    return repo, state_branch


class TestStateBranchTrackerIntegration:
    """Integration tests for state-branch-aware tracker routing.

    All tests in this class require the feature implementation.  They are
    marked xfail until OompahMarkdownTracker accepts state_branch_enabled.
    """

    @state_branch_not_implemented
    def test_task_creation_commits_only_to_state_branch_not_main(
        self, state_branch_repo: tuple[Path, str]
    ) -> None:
        """Creating a task must commit to the state branch and leave main unchanged.

        This is the primary acceptance criterion for OOMPAH-256: task mutations
        for a migrated project create commits only on the configured state branch.
        """
        repo, state_branch = state_branch_repo
        main_sha_before = _commit_sha(repo, "main")

        tracker = _make_tracker(repo, state_branch_enabled=True, state_branch_name=state_branch, git_sync=True)
        issue = tracker.create_issue("Test task for state branch isolation")

        # Main must be unchanged
        main_sha_after = _commit_sha(repo, "main")
        assert main_sha_after == main_sha_before, (
            f"main branch SHA changed after create_issue(): "
            f"{main_sha_before!r} → {main_sha_after!r}. "
            "Task commits must only land on the state branch."
        )

        # State branch must have a new commit
        state_sha_after = _commit_sha(repo, state_branch)
        # We can verify the task file exists on the state branch via git show
        task_id = issue.identifier
        show = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", state_branch],
            cwd=str(repo), capture_output=True, text=True,
        )
        assert show.returncode == 0
        state_files = show.stdout.splitlines()
        oompah_files = [f for f in state_files if ".oompah/tasks/" in f]
        assert any(task_id in f for f in oompah_files), (
            f"Expected task file containing {task_id!r} on state branch "
            f"{state_branch!r}, found: {oompah_files}"
        )

        # The task file must NOT be on main
        main_show = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", "main"],
            cwd=str(repo), capture_output=True, text=True,
        )
        main_files = main_show.stdout.splitlines()
        assert not any(task_id in f for f in main_files), (
            f"Task file {task_id!r} must NOT appear on main branch. "
            f"Found: {[f for f in main_files if task_id in f]}"
        )

    @state_branch_not_implemented
    def test_status_update_commits_only_to_state_branch(
        self, state_branch_repo: tuple[Path, str]
    ) -> None:
        """Status changes must create commits on the state branch, not main."""
        repo, state_branch = state_branch_repo
        tracker = _make_tracker(repo, state_branch_enabled=True, state_branch_name=state_branch, git_sync=True)
        issue = tracker.create_issue("Task to transition")
        main_sha_before = _commit_sha(repo, "main")

        tracker.update_issue(issue.identifier, status=IN_PROGRESS)

        main_sha_after = _commit_sha(repo, "main")
        assert main_sha_after == main_sha_before, (
            "Status update must not change main branch HEAD"
        )

    @state_branch_not_implemented
    def test_add_comment_commits_only_to_state_branch(
        self, state_branch_repo: tuple[Path, str]
    ) -> None:
        """Adding a comment must create a commit on the state branch, not main."""
        repo, state_branch = state_branch_repo
        tracker = _make_tracker(repo, state_branch_enabled=True, state_branch_name=state_branch, git_sync=True)
        issue = tracker.create_issue("Task needing comment")
        main_sha_before = _commit_sha(repo, "main")

        tracker.add_comment(issue.identifier, "Test progress comment", author="oompah")

        main_sha_after = _commit_sha(repo, "main")
        assert main_sha_after == main_sha_before, (
            "Adding a comment must not change main branch HEAD"
        )

    @state_branch_not_implemented
    def test_add_label_commits_only_to_state_branch(
        self, state_branch_repo: tuple[Path, str]
    ) -> None:
        """Adding a label must commit to the state branch, not main."""
        repo, state_branch = state_branch_repo
        tracker = _make_tracker(repo, state_branch_enabled=True, state_branch_name=state_branch, git_sync=True)
        issue = tracker.create_issue("Task needing label")
        main_sha_before = _commit_sha(repo, "main")

        tracker.add_label(issue.identifier, "needs:review")

        main_sha_after = _commit_sha(repo, "main")
        assert main_sha_after == main_sha_before, (
            "Adding a label must not change main branch HEAD"
        )

    @state_branch_not_implemented
    def test_set_dependency_commits_only_to_state_branch(
        self, state_branch_repo: tuple[Path, str]
    ) -> None:
        """Setting a dependency must commit to the state branch, not main."""
        repo, state_branch = state_branch_repo
        tracker = _make_tracker(repo, state_branch_enabled=True, state_branch_name=state_branch, git_sync=True)
        parent = tracker.create_issue("Parent task")
        child = tracker.create_issue("Child task")
        main_sha_before = _commit_sha(repo, "main")

        tracker.add_parent_child(child.identifier, parent.identifier)

        main_sha_after = _commit_sha(repo, "main")
        assert main_sha_after == main_sha_before, (
            "Setting parent/dependency must not change main branch HEAD"
        )

    @state_branch_not_implemented
    def test_main_branch_unchanged_after_multiple_mutations(
        self, state_branch_repo: tuple[Path, str]
    ) -> None:
        """Main branch HEAD must be byte-for-byte identical after multiple mutations.

        This is the core regression guard: *any* tracker operation that commits
        to main while state_branch_enabled=True is a contract violation.
        """
        repo, state_branch = state_branch_repo
        main_sha_before = _commit_sha(repo, "main")

        tracker = _make_tracker(repo, state_branch_enabled=True, state_branch_name=state_branch, git_sync=True)

        # Multiple mutations in sequence
        t1 = tracker.create_issue("Alpha task", description="First task")
        t2 = tracker.create_issue("Beta task", issue_type="bug")
        tracker.update_issue(t1.identifier, status=IN_PROGRESS)
        tracker.add_comment(t1.identifier, "Progress note", author="oompah")
        tracker.add_label(t2.identifier, "bug:confirmed")
        tracker.update_issue(t1.identifier, status=IN_REVIEW)
        tracker.update_issue(t1.identifier, status=DONE)

        main_sha_after = _commit_sha(repo, "main")
        assert main_sha_after == main_sha_before, (
            f"main branch HEAD changed after {7} tracker mutations: "
            f"{main_sha_before!r} → {main_sha_after!r}. "
            "State-branch tracker must NEVER write to code main."
        )

    @state_branch_not_implemented
    def test_reads_tasks_from_state_branch_only(
        self, state_branch_repo: tuple[Path, str]
    ) -> None:
        """Task discovery must read from the state branch, not from main.

        Write a task directly to the state branch (bypassing the tracker) and
        verify the tracker discovers it.  Write a different task directly to
        main (bypassing the tracker) and verify the tracker does NOT see it.
        """
        repo, state_branch = state_branch_repo

        # Seed a task directly on the state branch (simulating a prior commit)
        _git(repo, "checkout", state_branch)
        tasks_dir = repo / ".oompah" / "tasks" / "open"
        tasks_dir.mkdir(parents=True, exist_ok=True)
        task_meta = {
            "id": "STATE-1",
            "type": "task",
            "status": "Open",
            "priority": 2,
            "title": "Task seeded directly on state branch",
            "parent": None, "children": [], "blocked_by": [], "labels": [],
            "created_at": "2026-07-01T10:00:00Z",
            "updated_at": "2026-07-01T10:00:00Z",
        }
        (tasks_dir / "STATE-1.md").write_text(
            f"---\n{yaml.safe_dump(task_meta)}---\n## Summary\n\nState-branch only.\n",
            encoding="utf-8",
        )
        _git(repo, "add", ".oompah/")
        _git(repo, "commit", "-m", "Seed STATE-1 on state branch")

        # Seed a DIFFERENT task directly on main (should NOT be visible via state-branch tracker)
        _git(repo, "checkout", "main")
        main_tasks_dir = repo / ".oompah" / "tasks" / "open"
        main_tasks_dir.mkdir(parents=True, exist_ok=True)
        main_task_meta = {
            "id": "MAIN-1",
            "type": "task",
            "status": "Open",
            "priority": 2,
            "title": "Task seeded directly on main",
            "parent": None, "children": [], "blocked_by": [], "labels": [],
            "created_at": "2026-07-01T10:00:00Z",
            "updated_at": "2026-07-01T10:00:00Z",
        }
        (main_tasks_dir / "MAIN-1.md").write_text(
            f"---\n{yaml.safe_dump(main_task_meta)}---\n## Summary\n\nMain branch only.\n",
            encoding="utf-8",
        )
        _git(repo, "add", ".oompah/")
        _git(repo, "commit", "-m", "Seed MAIN-1 on main branch")

        tracker = _make_tracker(
            repo, state_branch_enabled=True, state_branch_name=state_branch, git_sync=False
        )
        all_issues = tracker.fetch_all_issues()
        identifiers = {issue.identifier for issue in all_issues}

        # Must see task from state branch
        assert "STATE-1" in identifiers, (
            f"Tracker with state_branch_enabled=True must read tasks from the state branch. "
            f"STATE-1 was seeded directly on {state_branch!r} but not found. "
            f"Found: {identifiers}"
        )

        # Must NOT see task from main (it lives only on main, not on state branch)
        assert "MAIN-1" not in identifiers, (
            f"Tracker with state_branch_enabled=True must NOT read tasks from main. "
            f"MAIN-1 was seeded only on main and should not be visible. "
            f"Found: {identifiers}"
        )

    @state_branch_not_implemented
    def test_state_branch_worktree_does_not_switch_main_checkout(
        self, state_branch_repo: tuple[Path, str]
    ) -> None:
        """Tracker operations must not switch the main checkout to the state branch.

        A write that calls ``git checkout state_branch`` on the shared code
        checkout would corrupt concurrent code operations.  The implementation
        must use a worktree or an equivalent isolation mechanism so the shared
        checkout remains on main.
        """
        repo, state_branch = state_branch_repo
        tracker = _make_tracker(
            repo, state_branch_enabled=True, state_branch_name=state_branch, git_sync=True
        )

        tracker.create_issue("Isolation check")

        # The shared checkout must still be on main (or at least not on state branch)
        current_branch = _git(repo, "symbolic-ref", "--short", "HEAD").stdout.strip()
        assert current_branch != state_branch, (
            f"After tracker write, the shared repo checkout is on {current_branch!r}. "
            "The tracker must not switch the main checkout to the state branch. "
            "Use a separate git worktree or equivalent mechanism."
        )


# ---------------------------------------------------------------------------
# § 3 — Legacy fixture: default-branch behavior is unchanged
#
# Contract:
#   - Tracker instantiated without state_branch_enabled (default=False) must
#     behave identically to the current implementation.
#   - Specifically, it must write to the default branch, NOT a state branch.
#   - No regression is acceptable for legacy projects.
# ---------------------------------------------------------------------------


class TestLegacyTrackerWithoutStateBranch:
    """Tests for the legacy (non-state-branch) tracker behavior.

    These tests MUST pass whether or not the feature is implemented.
    They are the regression guard for OOMPAH-256 requirement:
    'Legacy projects continue to work without migration.'
    """

    def test_tracker_default_state_branch_enabled_is_false(self, tmp_path: Path) -> None:
        """OompahMarkdownTracker must default to state_branch_enabled=False.

        When the feature is implemented, the constructor must not opt in to
        state-branch behavior unless explicitly requested.  This ensures backward
        compatibility for callers that have not been updated to pass the param.
        """
        tracker = OompahMarkdownTracker(
            active_states=[OPEN],
            terminal_states=[DONE],
            cwd=str(tmp_path / "repo"),
        )
        # The attribute must exist and be False (or the feature hasn't landed yet
        # and the attribute doesn't exist — either is acceptable pre-implementation)
        if hasattr(tracker, "state_branch_enabled"):
            assert tracker.state_branch_enabled is False, (
                "OompahMarkdownTracker must default state_branch_enabled to False"
            )

    def test_legacy_tracker_creates_task_in_local_filesystem(self, tmp_path: Path) -> None:
        """Legacy tracker (no state_branch_enabled) must write task files locally.

        This verifies the existing behavior is not disturbed when state_branch
        support is added: creating a task without state_branch_enabled=True
        must still write task files under repo/.oompah/tasks/ using the
        current filesystem-local approach.
        """
        root = tmp_path / "repo"
        root.mkdir()
        tracker = OompahMarkdownTracker(
            active_states=[OPEN],
            terminal_states=[DONE],
            cwd=str(root),
            default_branch="main",
            git_sync=False,
        )
        issue = tracker.create_issue("Legacy task creation")
        assert issue.identifier
        # The task file must exist in the filesystem under .oompah/tasks/
        task_files = list((root / ".oompah" / "tasks").rglob("*.md"))
        assert task_files, (
            "Legacy tracker must write task files under .oompah/tasks/ on the local filesystem"
        )

    def test_legacy_tracker_reads_from_local_filesystem(self, tmp_path: Path) -> None:
        """Legacy tracker must read tasks from the local filesystem, not a git branch."""
        root = tmp_path / "repo"
        root.mkdir()
        tracker = OompahMarkdownTracker(
            active_states=[OPEN],
            terminal_states=[DONE],
            cwd=str(root),
            default_branch="main",
            git_sync=False,
        )
        issue = tracker.create_issue("Readable task")
        fetched = tracker.fetch_issue_detail(issue.identifier)
        assert fetched is not None, (
            "Legacy tracker must be able to read back a task it created"
        )
        assert fetched.identifier == issue.identifier

    def test_legacy_tracker_git_sync_writes_to_default_branch(self, tmp_path: Path) -> None:
        """Legacy tracker with git_sync=True must commit to the default branch.

        This is the existing behavior: create_issue on main must add a commit
        to main, not to any state branch.
        """
        root = tmp_path / "repo"
        _init_git_repo(root)

        tracker = OompahMarkdownTracker(
            active_states=[OPEN],
            terminal_states=[DONE],
            cwd=str(root),
            default_branch="main",
            git_sync=True,
        )

        # Mock _has_remote to avoid network calls
        with patch.object(tracker, "_has_remote", return_value=False):
            main_sha_before = _commit_sha(root, "main")
            tracker.create_issue("Task on default branch")
            main_sha_after = _commit_sha(root, "main")

        assert main_sha_after != main_sha_before, (
            "Legacy tracker with git_sync=True must commit task changes to main"
        )

    def test_explicit_state_branch_enabled_false_behaves_as_legacy(
        self, tmp_path: Path
    ) -> None:
        """Explicitly setting state_branch_enabled=False must use legacy behavior.

        When the feature is implemented, callers may pass state_branch_enabled=False
        explicitly.  This must result in identical behavior to not passing the param.
        """
        if not _STATE_BRANCH_TRACKER_IMPLEMENTED:
            pytest.skip("state_branch_enabled not yet a tracker parameter")

        root = tmp_path / "repo"
        root.mkdir()
        tracker = OompahMarkdownTracker(
            active_states=[OPEN],
            terminal_states=[DONE],
            cwd=str(root),
            default_branch="main",
            git_sync=False,
            state_branch_enabled=False,
        )
        issue = tracker.create_issue("Legacy-explicit task")
        assert issue.identifier
        task_files = list((root / ".oompah" / "tasks").rglob("*.md"))
        assert task_files, "state_branch_enabled=False must use legacy local-filesystem writes"


# ---------------------------------------------------------------------------
# § 4 — Failure handling
#
# Contract:
#   - When the state branch does not exist, the tracker raises a clear,
#     actionable TrackerError.  Normal reads must NOT create the branch.
#   - Authentication failure (push rejected 403) is handled gracefully:
#     the task write is committed locally; task data is not corrupted.
#   - Non-fast-forward push triggers fetch + rebase + push retry.
#   - If rebase fails, TrackerError is raised with actionable message.
#   - No reset --hard is ever used (local state preserved on failure).
# ---------------------------------------------------------------------------


class TestStateBranchTrackerFailures:
    """Failure-mode tests for state-branch-aware tracker routing."""

    @state_branch_not_implemented
    def test_missing_state_branch_raises_actionable_error(
        self, tmp_path: Path
    ) -> None:
        """A missing state branch must raise TrackerError, not silently fall back.

        Normal reads must NOT create the remote state branch (that's the
        bootstrap flow, not the read/write flow).  A clear error must tell
        the operator which branch is missing and how to create it.
        """
        root = tmp_path / "repo"
        _init_git_repo(root)

        tracker = _make_tracker(
            root,
            state_branch_enabled=True,
            state_branch_name="oompah/state/proj-missing",
            git_sync=False,  # git_sync=False avoids remote calls, but branch still missing locally
        )

        with pytest.raises(TrackerError) as exc_info:
            tracker.fetch_all_issues()

        error_msg = str(exc_info.value)
        assert "oompah/state/proj-missing" in error_msg, (
            f"Error must name the missing state branch; got: {error_msg!r}"
        )
        # Error must suggest how to fix it (bootstrap or migration)
        assert any(word in error_msg.lower() for word in ("bootstrap", "migrate", "branch", "create")), (
            f"Error must be actionable (mention bootstrap/migrate/create); got: {error_msg!r}"
        )

    @state_branch_not_implemented
    def test_task_data_not_corrupted_when_push_fails_with_auth_error(
        self, tmp_path: Path
    ) -> None:
        """Authentication failure on push must not corrupt task data.

        The task must be committed locally even if the remote push fails.
        The task data must be readable after the push failure.
        """
        root = tmp_path / "repo"
        _init_git_repo(root)
        state_branch = "oompah/state/proj-auth"
        _create_state_branch(root, state_branch)

        tracker = _make_tracker(
            root,
            state_branch_enabled=True,
            state_branch_name=state_branch,
            git_sync=True,
        )

        def _fake_git(args: list[str], *, check: bool, **kwargs) -> MagicMock:
            """Return success for all operations except push, which simulates auth failure."""
            cmd = args[0] if args else ""
            cwd = kwargs.get("cwd", root)
            effective_cwd = str(cwd) if cwd is not None else str(root)
            if cmd == "push":
                return _make_completed_process(
                    1, "", "remote: Permission to org/repo.git denied."
                )
            # Run real git for everything else
            result = subprocess.run(
                ["git", *args],
                cwd=effective_cwd,
                capture_output=True,
                text=True,
            )
            if check and result.returncode != 0:
                raise TrackerError(f"git {' '.join(args)} failed: {result.stderr}")
            return result  # type: ignore[return-value]

        tracker._git = _fake_git  # type: ignore[method-assign]

        # Push will fail, but the task should still be created
        try:
            issue = tracker.create_issue("Task with push failure")
        except TrackerError as exc:
            # A TrackerError for push is acceptable; we just need the data intact
            pass

        # The task file must exist locally (data not corrupted).
        # The state branch tracker writes to a git worktree inside .git/; look there.
        task_files = list((root / ".oompah" / "tasks").rglob("*.md"))
        all_task_files = list(root.rglob(".oompah/tasks/**/*.md"))
        # At minimum, some task data must exist
        assert task_files or all_task_files, (
            "Task data must be preserved locally even when remote push fails"
        )

    @state_branch_not_implemented
    def test_non_fast_forward_push_triggers_rebase_and_retry(
        self, tmp_path: Path
    ) -> None:
        """A push rejection (non-fast-forward) must trigger fetch + rebase + push retry.

        This simulates the scenario where the state branch was advanced by a
        concurrent commit (e.g. service restart mid-push).  The tracker must:
        1. Attempt the push.
        2. On rejection, fetch + rebase.
        3. Retry the push.

        No destructive reset --hard must be used at any point.
        """
        root = tmp_path / "repo"
        _init_git_repo(root)
        state_branch = "oompah/state/proj-nff"
        _create_state_branch(root, state_branch)

        tracker = _make_tracker(
            root,
            state_branch_enabled=True,
            state_branch_name=state_branch,
            git_sync=True,
        )

        push_attempt = 0
        git_calls: list[str] = []

        def _fake_git(args: list[str], *, check: bool, **kwargs) -> MagicMock:
            nonlocal push_attempt
            cmd = args[0] if args else ""
            arg_str = " ".join(args)
            git_calls.append(arg_str)
            cwd = kwargs.get("cwd", root)
            effective_cwd = str(cwd) if cwd is not None else str(root)

            if cmd == "push":
                push_attempt += 1
                if push_attempt == 1:
                    # First push: simulate non-fast-forward rejection
                    return _make_completed_process(
                        1,
                        "",
                        "! [rejected] oompah/state/proj-nff -> oompah/state/proj-nff "
                        "(non-fast-forward)",
                    )
                # Second push (after rebase): succeed
                return _make_completed_process(0)

            if cmd == "rebase" and "--abort" not in args:
                return _make_completed_process(0)

            # Fake "origin" existing so _has_remote() returns True and push is attempted.
            if cmd == "remote" and "get-url" in args:
                return _make_completed_process(0, "https://example.com/fake-remote.git")

            # Fake fetch success (real fetch would fail without an actual remote).
            if cmd == "fetch":
                return _make_completed_process(0)

            # Run real git for commit, symbolic-ref, rev-parse, merge, etc.
            result = subprocess.run(
                ["git", *args],
                cwd=effective_cwd,
                capture_output=True,
                text=True,
            )
            if check and result.returncode != 0:
                raise TrackerError(f"git {' '.join(args)} failed: {result.stderr}")
            return result  # type: ignore[return-value]

        tracker._git = _fake_git  # type: ignore[method-assign]

        # Should succeed (push succeeds on retry after rebase)
        issue = tracker.create_issue("Non-fast-forward recovery test")
        assert issue is not None

        # Must have attempted push more than once (initial + retry)
        push_calls = [c for c in git_calls if c.startswith("push")]
        assert len(push_calls) >= 2, (
            f"Expected ≥2 push attempts (initial rejection + retry after rebase); "
            f"got push calls: {push_calls}"
        )

        # Must NOT have used reset --hard (which would discard local commits)
        reset_hard_calls = [c for c in git_calls if "reset" in c and "--hard" in c]
        assert not reset_hard_calls, (
            f"Tracker must NEVER use 'git reset --hard' during non-ff push recovery; "
            f"found: {reset_hard_calls}"
        )

        # Rebase must have been attempted
        rebase_calls = [c for c in git_calls if c.startswith("rebase") and "--abort" not in c]
        assert rebase_calls, (
            f"Tracker must attempt 'git rebase' after push rejection; "
            f"rebase calls: {rebase_calls}, all calls: {git_calls}"
        )

    @state_branch_not_implemented
    def test_both_push_and_rebase_fail_raises_actionable_tracker_error(
        self, tmp_path: Path
    ) -> None:
        """When push + rebase both fail, TrackerError must be raised with actionable text.

        The local branch and working tree must be preserved (no reset --hard).
        """
        root = tmp_path / "repo"
        _init_git_repo(root)
        state_branch = "oompah/state/proj-broken"
        _create_state_branch(root, state_branch)

        tracker = _make_tracker(
            root,
            state_branch_enabled=True,
            state_branch_name=state_branch,
            git_sync=True,
        )

        git_calls: list[str] = []

        def _fake_git(args: list[str], *, check: bool, **kwargs) -> MagicMock:
            cmd = args[0] if args else ""
            git_calls.append(" ".join(args))
            cwd = kwargs.get("cwd", root)
            effective_cwd = str(cwd) if cwd is not None else str(root)

            if cmd == "push":
                return _make_completed_process(1, "", "[rejected] (non-fast-forward)")
            if cmd == "rebase" and "--abort" not in args:
                return _make_completed_process(
                    1, "", "error: could not apply abc123... task state update"
                )
            if cmd == "rebase" and "--abort" in args:
                return _make_completed_process(0)

            # Fake "origin" existing so _has_remote() returns True and push is attempted.
            if cmd == "remote" and "get-url" in args:
                return _make_completed_process(0, "https://example.com/fake-remote.git")

            # Fake fetch success (real fetch would fail without an actual remote).
            if cmd == "fetch":
                return _make_completed_process(0)

            result = subprocess.run(
                ["git", *args],
                cwd=effective_cwd,
                capture_output=True,
                text=True,
            )
            if check and result.returncode != 0:
                raise TrackerError(f"git {' '.join(args)} failed: {result.stderr}")
            return result  # type: ignore[return-value]

        tracker._git = _fake_git  # type: ignore[method-assign]

        with pytest.raises(TrackerError) as exc_info:
            tracker.create_issue("Broken push and rebase")

        error_msg = str(exc_info.value)

        # Error must be actionable
        assert any(
            word in error_msg.lower()
            for word in ("remediation", "rebase", "push", "conflict", "resolve")
        ), f"Error must be actionable; got: {error_msg!r}"

        # Must have aborted the rebase (not left it in-progress)
        rebase_abort_calls = [c for c in git_calls if "rebase" in c and "--abort" in c]
        assert rebase_abort_calls, (
            "Tracker must call 'git rebase --abort' after a failed rebase "
            "(to avoid leaving the repo in a mid-rebase state)"
        )

        # Must NOT have used reset --hard
        reset_hard_calls = [c for c in git_calls if "reset" in c and "--hard" in c]
        assert not reset_hard_calls, (
            f"Tracker must NEVER use 'git reset --hard' during failure recovery; "
            f"found: {reset_hard_calls}"
        )

    @state_branch_not_implemented
    def test_fetch_failure_raises_tracker_error_mentioning_state_branch(
        self, tmp_path: Path
    ) -> None:
        """A failed fetch for the state branch must raise a clear TrackerError."""
        root = tmp_path / "repo"
        _init_git_repo(root)
        state_branch = "oompah/state/proj-fetch-fail"
        _create_state_branch(root, state_branch)

        tracker = _make_tracker(
            root,
            state_branch_enabled=True,
            state_branch_name=state_branch,
            git_sync=True,
        )

        def _fake_git(args: list[str], *, check: bool, **kwargs) -> MagicMock:
            cmd = args[0] if args else ""
            cwd = kwargs.get("cwd", root)
            effective_cwd = str(cwd) if cwd is not None else str(root)
            if cmd == "fetch":
                return _make_completed_process(1, "", "fatal: unable to connect to github.com")
            # Fake "origin" existing so _has_remote() returns True and sync is attempted.
            if cmd == "remote" and "get-url" in args:
                return _make_completed_process(0, "https://example.com/fake-remote.git")
            result = subprocess.run(
                ["git", *args],
                cwd=effective_cwd,
                capture_output=True,
                text=True,
            )
            if check and result.returncode != 0:
                raise TrackerError(f"git {' '.join(args)} failed: {result.stderr}")
            return result  # type: ignore[return-value]

        tracker._git = _fake_git  # type: ignore[method-assign]

        with pytest.raises(TrackerError) as exc_info:
            tracker.create_issue("Fetch failure test")

        error_msg = str(exc_info.value)
        # Error must mention the state branch or the sync operation
        assert any(
            word in error_msg.lower()
            for word in ("fetch", "sync", "state", "oompah/state")
        ), f"Fetch error must mention the state branch or sync; got: {error_msg!r}"


# ---------------------------------------------------------------------------
# § 5 — Concurrency
#
# Contract:
#   - A tracker write on the state branch must not be disturbed by a
#     concurrent code fetch/rebase operation on the main checkout.
#   - The write lock must prevent state corruption from concurrent writes.
# ---------------------------------------------------------------------------


class TestStateBranchTrackerConcurrency:
    """Tests for thread safety with state-branch tracker routing."""

    @state_branch_not_implemented
    def test_concurrent_tracker_write_and_code_fetch_succeed(
        self, tmp_path: Path
    ) -> None:
        """Simultaneous tracker write and code fetch must both succeed without corruption.

        This test verifies the isolation contract: the state-branch worktree
        (or equivalent) does not conflict with a concurrent git fetch on the
        shared code checkout.

        Thread 1: tracker.create_issue() — writes to state branch
        Thread 2: git fetch + ff-only on main (simulated)

        Both must complete; the tracker issue must be readable after.
        """
        root = tmp_path / "repo"
        _init_git_repo(root)
        state_branch = "oompah/state/proj-concurrent"
        _create_state_branch(root, state_branch)

        tracker = _make_tracker(
            root,
            state_branch_enabled=True,
            state_branch_name=state_branch,
            git_sync=False,  # Disable real remote for this test
        )

        errors: list[Exception] = []
        results: list[str] = []

        def _tracker_write() -> None:
            try:
                # Add a small sleep to ensure threads overlap
                time.sleep(0.05)
                issue = tracker.create_issue("Concurrent write test")
                results.append(issue.identifier)
            except Exception as exc:
                errors.append(exc)

        def _code_fetch_simulation() -> None:
            """Simulate a code fetch on main that runs concurrently with the tracker write."""
            try:
                # Simulate git operations on the main checkout (no-op without remote)
                time.sleep(0.03)
                # Read the main branch status (simulating what a code fetch would do)
                result = subprocess.run(
                    ["git", "log", "--oneline", "-3"],
                    cwd=str(root),
                    capture_output=True,
                    text=True,
                )
                # Just reading — must not fail even during a concurrent write
                if result.returncode != 0:
                    errors.append(RuntimeError(f"Code fetch simulation failed: {result.stderr}"))
            except Exception as exc:
                errors.append(exc)

        t1 = threading.Thread(target=_tracker_write, name="tracker-write")
        t2 = threading.Thread(target=_code_fetch_simulation, name="code-fetch")
        t1.start()
        t2.start()
        t1.join(timeout=30)
        t2.join(timeout=30)

        # Neither thread should have raised an exception
        assert not errors, (
            f"Concurrent write + fetch raised exceptions: {errors}"
        )
        # The tracker write must have produced a result
        assert results, "Tracker write thread must complete and produce an issue identifier"

    @state_branch_not_implemented
    def test_concurrent_tracker_writes_are_serialized(
        self, tmp_path: Path
    ) -> None:
        """Multiple concurrent tracker writes must be serialized without data loss.

        The _write_lock must ensure that two simultaneous create_issue() calls
        both succeed and both tasks are readable after completion.
        """
        root = tmp_path / "repo"
        _init_git_repo(root)
        state_branch = "oompah/state/proj-serial"
        _create_state_branch(root, state_branch)

        tracker = _make_tracker(
            root,
            state_branch_enabled=True,
            state_branch_name=state_branch,
            git_sync=False,
        )

        errors: list[Exception] = []
        results: list[str] = []

        def _write(title: str) -> None:
            try:
                issue = tracker.create_issue(title)
                results.append(issue.identifier)
            except Exception as exc:
                errors.append(exc)

        threads = [
            threading.Thread(target=_write, args=(f"Concurrent task {i}",))
            for i in range(3)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert not errors, f"Concurrent writes raised errors: {errors}"
        assert len(results) == 3, (
            f"Expected 3 successful task creations; got {len(results)}: {results}"
        )
        # All identifiers must be unique (no collision)
        assert len(set(results)) == 3, (
            f"Concurrent writes produced duplicate identifiers: {results}"
        )

        # All tasks must be readable
        all_issues = tracker.fetch_all_issues()
        found_ids = {issue.identifier for issue in all_issues}
        for task_id in results:
            assert task_id in found_ids, (
                f"Task {task_id!r} created during concurrent write is not readable"
            )


# ---------------------------------------------------------------------------
# § 6 — Orchestrator wiring
#
# Contract:
#   - _new_tracker_for_project() must pass state_branch_enabled and
#     state_branch_name to the tracker factory when the project has the feature
#     enabled.
#   - Legacy projects (state_branch_enabled=False) must receive the same
#     factory call as today (no new kwargs added).
# ---------------------------------------------------------------------------


class TestOrchestratorStateBranchWiring:
    """Tests for the orchestrator wiring that passes state-branch params to the tracker.

    These tests verify two things:
    (a) The Project model provides the right values (already implemented in OOMPAH-255).
    (b) The orchestrator's _new_tracker_for_project() passes those values to the factory
        (requires the feature implementation from OOMPAH-256).
    """

    # --- Tests that pass today (model wiring, no tracker param required) ---

    def test_project_state_branch_name_is_derived_from_id(self, tmp_path: Path) -> None:
        """Project.state_branch_name must be deterministically derived from project.id.

        This documents the naming contract that _new_tracker_for_project() must use
        when passing state_branch_name to the factory: it must use project.state_branch_name,
        not a hardcoded value.
        """
        from oompah.models import Project

        project = Project(
            id="proj-naming-test",
            name="naming-repo",
            repo_url="https://github.com/org/naming.git",
            repo_path=str(tmp_path / "naming"),
            default_branch="main",
            state_branch_enabled=True,
        )

        assert project.state_branch_name == "oompah/state/proj-naming-test", (
            f"Project.state_branch_name must be 'oompah/state/<project-id>'; "
            f"got {project.state_branch_name!r}"
        )

    def test_legacy_project_has_state_branch_name_but_not_enabled(
        self, tmp_path: Path
    ) -> None:
        """Legacy project must have a valid state_branch_name even when not enabled.

        The orchestrator must check state_branch_enabled before passing state_branch_name.
        A legacy project has state_branch_enabled=False and must not opt in.
        """
        from oompah.models import Project

        project = Project(
            id="proj-legacy-wiring",
            name="legacy-repo",
            repo_url="https://github.com/org/legacy.git",
            repo_path=str(tmp_path / "legacy"),
            default_branch="main",
            state_branch_enabled=False,
        )

        # The property exists on all projects but must only be used when enabled
        assert project.state_branch_name == "oompah/state/proj-legacy-wiring"
        assert project.state_branch_enabled is False

    def test_legacy_tracker_construction_unchanged(self, tmp_path: Path) -> None:
        """The existing OompahMarkdownTracker constructor must not be broken by OOMPAH-256.

        Legacy callers that do not pass state_branch_enabled must continue to work.
        This is a non-regression test for the orchestrator's existing call path.
        """
        tracker = OompahMarkdownTracker(
            active_states=[OPEN],
            terminal_states=[DONE],
            cwd=str(tmp_path / "legacy"),
            default_branch="main",
            git_sync=False,
        )
        assert tracker is not None

    # --- Tests that require the feature implementation ---

    @state_branch_not_implemented
    def test_orchestrator_passes_state_branch_enabled_to_oompah_md_factory(
        self, tmp_path: Path
    ) -> None:
        """_new_tracker_for_project must pass state_branch_enabled=True for enabled projects.

        This tests the wiring layer (oompah/orchestrator.py) that translates a
        Project's state_branch_enabled=True into a factory call that includes
        state_branch_enabled=True and state_branch_name="oompah/state/<id>".
        """
        from oompah.models import Project
        from oompah.orchestrator import ADAPTER_REGISTRY

        project = Project(
            id="proj-wiring-test",
            name="wiring-repo",
            repo_url="https://github.com/org/wiring.git",
            repo_path=str(tmp_path / "wiring"),
            default_branch="main",
            state_branch_enabled=True,
        )
        (tmp_path / "wiring").mkdir()

        factory_kwargs_received: list[dict] = []

        def _capturing_factory(**kwargs):
            factory_kwargs_received.append(dict(kwargs))
            # Create the tracker with only the params it accepts today
            return OompahMarkdownTracker(
                active_states=kwargs.get("active_states", [OPEN]),
                terminal_states=kwargs.get("terminal_states", [DONE]),
                cwd=kwargs.get("cwd"),
                default_branch=kwargs.get("default_branch"),
                git_sync=False,
            )

        # Patch the registry so our capturing factory is called instead
        patched_registry = dict(ADAPTER_REGISTRY)
        patched_registry["oompah_md"] = _capturing_factory

        with patch("oompah.orchestrator.ADAPTER_REGISTRY", patched_registry):
            from oompah.orchestrator import Orchestrator as _Orch

            orch = MagicMock()
            orch.config = MagicMock()
            orch.config.tracker_active_states = [OPEN]
            orch.config.tracker_terminal_states = [DONE]
            orch.config.tracker_kind = "oompah_md"

            # Call _new_tracker_for_project bound to the mock orchestrator
            _Orch._new_tracker_for_project(orch, project)

        assert factory_kwargs_received, "_new_tracker_for_project must call the factory"
        call_kwargs = factory_kwargs_received[0]

        assert call_kwargs.get("state_branch_enabled") is True, (
            f"Factory must receive state_branch_enabled=True for an enabled project; "
            f"got factory kwargs: {call_kwargs}"
        )
        assert call_kwargs.get("state_branch_name") == "oompah/state/proj-wiring-test", (
            f"Factory must receive the correct state_branch_name; "
            f"got factory kwargs: {call_kwargs}"
        )

    @state_branch_not_implemented
    def test_tracker_stores_state_branch_name_attribute(
        self, tmp_path: Path
    ) -> None:
        """OompahMarkdownTracker must store state_branch_name when passed.

        This validates that the tracker constructor correctly stores the
        state_branch_name so internal methods can route to the correct branch.
        """
        from oompah.models import Project

        project = Project(
            id="proj-attr-test",
            name="attr-repo",
            repo_url="https://github.com/org/attr.git",
            repo_path=str(tmp_path / "attr"),
            default_branch="main",
            state_branch_enabled=True,
        )
        repo = tmp_path / "attr"
        repo.mkdir()

        tracker = OompahMarkdownTracker(
            active_states=[OPEN],
            terminal_states=[DONE],
            cwd=str(repo),
            default_branch="main",
            git_sync=False,
            state_branch_enabled=True,
            state_branch_name=project.state_branch_name,
        )
        assert getattr(tracker, "state_branch_name", None) == "oompah/state/proj-attr-test", (
            "Tracker must store the state_branch_name it was given"
        )
        assert getattr(tracker, "state_branch_enabled", None) is True, (
            "Tracker must store state_branch_enabled=True"
        )


# ---------------------------------------------------------------------------
# § 7 — Acceptance criteria verification
#
# These tests directly map to the task's acceptance criteria (OOMPAH-256):
#   AC1. Task mutations for a migrated project create commits only on its
#        configured state branch.
#   AC2. Code branch heads are not changed by normal native tracker operations.
#   AC3. Legacy projects continue to work without migration.
#   AC4. make test passes.
# ---------------------------------------------------------------------------


class TestAcceptanceCriteria:
    """Direct verification of OOMPAH-256 acceptance criteria."""

    @state_branch_not_implemented
    def test_ac1_task_mutations_commit_only_to_state_branch(
        self, state_branch_repo: tuple[Path, str]
    ) -> None:
        """AC1: Task mutations must create commits only on the configured state branch."""
        repo, state_branch = state_branch_repo
        main_sha_before = _commit_sha(repo, "main")

        tracker = _make_tracker(
            repo, state_branch_enabled=True, state_branch_name=state_branch, git_sync=True
        )
        with patch.object(tracker, "_has_remote", return_value=False):
            task = tracker.create_issue("AC1 task")
            tracker.update_issue(task.identifier, status=IN_PROGRESS)
            tracker.add_comment(task.identifier, "AC1 comment", author="oompah")
            tracker.update_issue(task.identifier, status=DONE)

        # AC1: No commit on main
        main_sha_after = _commit_sha(repo, "main")
        assert main_sha_after == main_sha_before, "AC1 violated: main SHA changed"

        # AC1: Commits exist on state branch
        state_sha_after = _commit_sha(repo, state_branch)
        state_log = _git(repo, "log", "--oneline", state_branch).stdout
        assert task.identifier in state_log or "AC1" in state_log, (
            f"AC1 violated: no task commit found on state branch log: {state_log}"
        )

    @state_branch_not_implemented
    def test_ac2_code_branch_heads_unchanged(
        self, state_branch_repo: tuple[Path, str]
    ) -> None:
        """AC2: Code branch heads must not be changed by tracker operations."""
        repo, state_branch = state_branch_repo

        # Record code branch SHAs before any tracker operation
        main_sha = _commit_sha(repo, "main")

        # Create a feature branch (simulates an in-flight PR)
        _git(repo, "checkout", "-b", "feature/my-pr")
        (repo / "feature.py").write_text("# feature\n", encoding="utf-8")
        _git(repo, "add", ".")
        _git(repo, "commit", "-m", "Add feature")
        feature_sha = _commit_sha(repo, "feature/my-pr")
        _git(repo, "checkout", "main")

        tracker = _make_tracker(
            repo, state_branch_enabled=True, state_branch_name=state_branch, git_sync=False
        )
        task = tracker.create_issue("AC2 task")
        tracker.update_issue(task.identifier, status=IN_PROGRESS)
        tracker.update_issue(task.identifier, status=DONE)

        # AC2: Both code branches must be unchanged
        assert _commit_sha(repo, "main") == main_sha, (
            "AC2 violated: main branch HEAD changed after tracker operations"
        )
        assert _commit_sha(repo, "feature/my-pr") == feature_sha, (
            "AC2 violated: feature branch HEAD changed after tracker operations"
        )

    def test_ac3_legacy_projects_work_without_migration(self, tmp_path: Path) -> None:
        """AC3: Legacy projects (no state branch) must work exactly as before."""
        root = tmp_path / "repo"
        root.mkdir()

        # Use the tracker exactly as it would be used before OOMPAH-256
        tracker = OompahMarkdownTracker(
            active_states=[OPEN],
            terminal_states=[DONE],
            cwd=str(root),
            default_branch="main",
            git_sync=False,
        )

        # All operations must work
        task = tracker.create_issue("Legacy task", description="AC3 test")
        assert task.identifier

        tracker.update_issue(task.identifier, status=IN_PROGRESS)
        updated = tracker.fetch_issue_detail(task.identifier)
        assert updated is not None and updated.state == IN_PROGRESS

        tracker.add_comment(task.identifier, "AC3 comment", author="oompah")
        comments = tracker.fetch_comments(task.identifier)
        assert comments, "Legacy tracker must support comments"

        tracker.update_issue(task.identifier, status=DONE)
        done = tracker.fetch_issue_detail(task.identifier)
        assert done is not None and done.state == DONE

        # AC3: No state branch interaction whatsoever
        if _STATE_BRANCH_TRACKER_IMPLEMENTED:
            state_branch_attr = getattr(tracker, "state_branch_enabled", None)
            assert not state_branch_attr, (
                "Legacy tracker must have state_branch_enabled=False (or unset)"
            )
