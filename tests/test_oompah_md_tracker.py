"""Tests for the native oompah Markdown tracker."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest
import yaml

from oompah.oompah_md_tracker import OompahMarkdownTracker
from oompah.statuses import (
    ARCHIVED,
    BACKLOG,
    DECOMPOSED,
    DONE,
    DUPLICATE_CANDIDATE,
    IN_PROGRESS,
    IN_REVIEW,
    MERGED,
    NEEDS_ANSWER,
    NEEDS_CI_FIX,
    NEEDS_HUMAN,
    NEEDS_REBASE,
    OPEN,
    PROPOSED,
)
from oompah.tracker import TrackerError


def _tracker(tmp_path, *, git_sync: bool = False) -> OompahMarkdownTracker:
    root = tmp_path / "repo"
    root.mkdir()
    return OompahMarkdownTracker(
        active_states=[OPEN],
        terminal_states=[DONE],
        cwd=str(root),
        default_branch="main",
        git_sync=git_sync,
    )


def _frontmatter(path):
    content = path.read_text(encoding="utf-8")
    assert content.startswith("---\n")
    end = content.find("\n---", 4)
    assert end > 0
    return yaml.safe_load(content[4:end])


def _make_completed_process(returncode: int, stdout: str = "", stderr: str = "") -> MagicMock:
    """Build a mock CompletedProcess-like object for _git() to return."""
    proc = MagicMock()
    proc.returncode = returncode
    proc.stdout = stdout
    proc.stderr = stderr
    return proc


class TestOompahMarkdownTrackerCreate:
    def test_create_issue_writes_markdown_task_file(self, tmp_path):
        tracker = _tracker(tmp_path)

        issue = tracker.create_issue(
            "Normalize task priority creation",
            issue_type="bug",
            description="The CLI rejects documented priorities.",
            priority=1,
            labels=["cli"],
        )

        assert issue.identifier == "REPO-1"
        assert issue.state == BACKLOG
        assert issue.issue_type == "bug"
        assert issue.description == "The CLI rejects documented priorities."
        assert issue.priority == 1
        assert issue.tracker_kind == "oompah_md"

        path = tmp_path / "repo" / ".oompah" / "tasks" / "backlog" / "REPO-1.md"
        assert path.exists()
        meta = _frontmatter(path)
        assert meta["id"] == "REPO-1"
        assert meta["status"] == BACKLOG
        assert meta["type"] == "bug"
        assert meta["labels"] == ["cli"]

    def test_create_issue_uses_next_numeric_id(self, tmp_path):
        tracker = _tracker(tmp_path)

        first = tracker.create_issue("First")
        second = tracker.create_issue("Second")

        assert first.identifier == "REPO-1"
        assert second.identifier == "REPO-2"


class TestOompahMarkdownTrackerMutations:
    def test_duplicate_task_id_uses_most_recent_record_once(self, tmp_path):
        """A stale status-directory copy cannot create a second board card."""
        tracker = _tracker(tmp_path)
        issue = tracker.create_issue("Moved task")
        tracker.update_issue(issue.identifier, status=MERGED)

        merged_path = (
            tmp_path / "repo" / ".oompah" / "tasks" / "merged" / "REPO-1.md"
        )
        stale_path = (
            tmp_path / "repo" / ".oompah" / "tasks" / "open" / "REPO-1.md"
        )
        stale_meta = _frontmatter(merged_path)
        stale_meta["status"] = OPEN
        stale_meta["updated_at"] = "2026-01-01T00:00:00Z"
        _write_markdown(stale_path, stale_meta, "## Summary\n\nStale copy\n")
        tracker.invalidate_read_cache()

        issues = [item for item in tracker.fetch_all_issues() if item.identifier == issue.identifier]

        assert len(issues) == 1
        assert issues[0].state == MERGED
        assert tracker.fetch_issue_detail(issue.identifier).state == MERGED

    def test_setting_unchanged_metadata_does_not_commit_or_update_timestamp(
        self, tmp_path
    ):
        """Repeated review reconciliation must not churn the default branch."""
        tracker = _tracker(tmp_path)
        issue = tracker.create_issue("Already linked to a review")

        with patch.object(tracker, "_commit_and_push") as commit:
            tracker.set_metadata_field(
                issue.identifier,
                "oompah.review_url",
                "https://github.com/example/repo/pull/7",
            )
            path = tmp_path / "repo" / ".oompah" / "tasks" / "backlog" / "REPO-1.md"
            first_meta = _frontmatter(path)

            tracker.set_metadata_field(
                issue.identifier,
                "oompah.review_url",
                "https://github.com/example/repo/pull/7",
            )

        assert commit.call_count == 1
        assert _frontmatter(path)["updated_at"] == first_meta["updated_at"]

    def test_update_status_moves_file_between_status_directories(self, tmp_path):
        tracker = _tracker(tmp_path)
        issue = tracker.create_issue("Move me")

        tracker.update_issue(issue.identifier, status=OPEN)

        old_path = tmp_path / "repo" / ".oompah" / "tasks" / "backlog" / "REPO-1.md"
        new_path = tmp_path / "repo" / ".oompah" / "tasks" / "open" / "REPO-1.md"
        assert not old_path.exists()
        assert new_path.exists()
        assert tracker.fetch_issue_detail("REPO-1").state == OPEN

    def test_labels_dependencies_parent_and_metadata_round_trip(self, tmp_path):
        tracker = _tracker(tmp_path)
        parent = tracker.create_issue("Epic", issue_type="epic")
        child = tracker.create_issue("Child")

        tracker.add_parent_child(child.identifier, parent.identifier)
        tracker.add_dependency(child.identifier, "REPO-99")
        tracker.add_label(child.identifier, "backend")
        tracker.set_metadata_field(child.identifier, "oompah.work_branch", "oompah/repo-1")
        tracker.set_metadata_field(
            child.identifier,
            "oompah.review_url",
            "https://github.com/org/repo/pull/7",
        )
        tracker.set_metadata_field(child.identifier, "oompah.review_number", "7")

        refreshed = tracker.fetch_issue_detail(child.identifier)
        assert refreshed.parent_id == parent.identifier
        assert refreshed.blocked_by[0].identifier == "REPO-99"
        assert "backend" in refreshed.labels
        assert refreshed.work_branch == "oompah/repo-1"
        assert refreshed.review_url == "https://github.com/org/repo/pull/7"
        assert refreshed.review_number == "7"
        assert tracker.get_metadata(child.identifier)["oompah.work_branch"] == "oompah/repo-1"
        assert (
            tracker.get_metadata(child.identifier)["oompah.review_url"]
            == "https://github.com/org/repo/pull/7"
        )
        assert tracker.get_metadata(child.identifier)["oompah.review_number"] == "7"

        parent_refreshed = tracker.fetch_issue_detail(parent.identifier)
        parent_path = (
            tmp_path / "repo" / ".oompah" / "tasks" / "backlog" / "REPO-1.md"
        )
        assert child.identifier in _frontmatter(parent_path)["children"]
        assert parent_refreshed.issue_type == "epic"

    def test_external_github_metadata_normalizes_provider_fields(self, tmp_path):
        tracker = _tracker(tmp_path)
        issue = tracker.create_issue("Imported issue")

        tracker.set_metadata_field(
            issue.identifier,
            "oompah.external.github",
            {
                "owner": "example-org",
                "repo": "customer-app",
                "number": "42",
                "url": "https://github.com/example-org/customer-app/issues/42",
                "requestor_login": "alice",
            },
        )

        refreshed = tracker.fetch_issue_detail(issue.identifier)
        assert refreshed.tracker_owner == "example-org"
        assert refreshed.tracker_repo == "customer-app"
        assert refreshed.issue_number == "42"
        assert refreshed.provider_url == "https://github.com/example-org/customer-app/issues/42"
        assert refreshed.requestor_login == "alice"

    def test_comments_are_appended_and_parsed(self, tmp_path):
        tracker = _tracker(tmp_path)
        issue = tracker.create_issue("Needs comment")

        tracker.add_comment(issue.identifier, "Please fix this.", author="oompah")

        comments = tracker.fetch_comments(issue.identifier)
        assert len(comments) == 1
        assert comments[0]["author"] == "oompah"
        assert comments[0]["text"] == "Please fix this."

    def test_candidate_fetch_uses_active_states_only(self, tmp_path):
        tracker = _tracker(tmp_path)
        open_issue = tracker.create_issue("Open", initial_status=OPEN)
        tracker.create_issue("Backlog")

        candidates = tracker.fetch_candidate_issues()

        assert [issue.identifier for issue in candidates] == [open_issue.identifier]

    def test_fetch_in_progress_issues_returns_only_in_progress(self, tmp_path):
        tracker = _tracker(tmp_path)
        tracker.create_issue("Open", initial_status=OPEN)
        in_progress = tracker.create_issue("Stuck", initial_status="In Progress")

        issues = tracker.fetch_in_progress_issues()

        assert [issue.identifier for issue in issues] == [in_progress.identifier]
        path = tmp_path / "repo" / ".oompah" / "tasks" / "in-progress" / "REPO-2.md"
        assert path.exists()

    def test_close_issue_uses_terminal_state(self, tmp_path):
        tracker = _tracker(tmp_path)
        issue = tracker.create_issue("Close me", initial_status=OPEN)

        tracker.close_issue(issue.identifier)

        refreshed = tracker.fetch_issue_detail(issue.identifier)
        assert refreshed.state == DONE
        assert refreshed.closed_at is not None


class TestOompahMarkdownTrackerDefaultBranchGuard:
    def test_git_synced_writes_require_default_branch(self, tmp_path):
        root = tmp_path / "repo"
        root.mkdir()
        subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=root,
            check=True,
        )
        subprocess.run(["git", "checkout", "-b", "feature"], cwd=root, check=True)
        tracker = OompahMarkdownTracker(
            active_states=[OPEN],
            terminal_states=[DONE],
            cwd=str(root),
            default_branch="main",
            git_sync=True,
        )

        with pytest.raises(TrackerError, match="default branch"):
            tracker.create_issue("Should fail")


class TestOompahMarkdownTrackerGitSync:
    """Tests for the fetch/fast-forward sync strategy (OOMPAH-10 regression).

    Verifies that the tracker uses a deterministic fetch + merge --ff-only
    instead of the brittle ``git pull --rebase origin main`` which fails with
    ``fatal: Cannot rebase onto multiple branches`` on clean default branches.
    """

    def _mock_git_for_sync(self, tracker: OompahMarkdownTracker, *, fetch_rc: int = 0, ff_rc: int = 0, fetch_stderr: str = "", ff_stderr: str = "") -> list[tuple]:
        """Patch _git to record calls and return controlled results."""
        calls: list[tuple] = []

        def _fake_git(args: list[str], *, check: bool) -> MagicMock:
            calls.append(tuple(args))
            cmd = args[0] if args else ""
            if cmd == "rev-parse":
                # _is_git_repo
                return _make_completed_process(0, "true")
            if cmd == "symbolic-ref" and "--short" in args and "refs/remotes" not in " ".join(args):
                # current branch is main
                return _make_completed_process(0, "main")
            if cmd == "remote":
                # _has_remote("origin") → True
                return _make_completed_process(0, "git@example.com:org/repo.git")
            if cmd == "fetch":
                return _make_completed_process(fetch_rc, "", fetch_stderr)
            if cmd == "merge" and "--ff-only" in args:
                return _make_completed_process(ff_rc, "", ff_stderr)
            # For add, diff, commit, push — succeed silently
            return _make_completed_process(0)

        tracker._git = _fake_git  # type: ignore[method-assign]
        return calls

    def test_sync_uses_fetch_then_ff_only_not_pull_rebase(self, tmp_path):
        """_prepare_default_branch_for_write must use fetch+ff-only, never pull --rebase."""
        tracker = _tracker(tmp_path, git_sync=True)
        calls: list[tuple] = []

        def _fake_git(args: list[str], *, check: bool) -> MagicMock:
            calls.append(tuple(args))
            cmd = args[0] if args else ""
            if cmd == "rev-parse":
                return _make_completed_process(0, "true")
            if cmd == "symbolic-ref":
                return _make_completed_process(0, "main")
            if cmd == "remote":
                return _make_completed_process(0, "git@example.com:org/repo.git")
            return _make_completed_process(0)

        tracker._git = _fake_git  # type: ignore[method-assign]
        tracker._prepare_default_branch_for_write()

        arg_strings = [" ".join(c) for c in calls]
        # Must use fetch + merge --ff-only
        assert any("fetch" in s and "origin" in s for s in arg_strings), (
            f"Expected a 'git fetch origin ...' call, got: {arg_strings}"
        )
        assert any("merge" in s and "--ff-only" in s for s in arg_strings), (
            f"Expected a 'git merge --ff-only ...' call, got: {arg_strings}"
        )
        # Must NOT use 'git pull --rebase'
        assert not any("pull" in s and "rebase" in s for s in arg_strings), (
            f"Expected no 'git pull --rebase' call, got: {arg_strings}"
        )

    def test_fetch_failure_raises_tracker_error_with_remediation(self, tmp_path):
        """A failed git fetch must raise TrackerError with actionable text."""
        tracker = _tracker(tmp_path, git_sync=True)

        def _fake_git(args: list[str], *, check: bool) -> MagicMock:
            cmd = args[0] if args else ""
            if cmd == "rev-parse":
                return _make_completed_process(0, "true")
            if cmd == "symbolic-ref":
                return _make_completed_process(0, "main")
            if cmd == "remote":
                return _make_completed_process(0, "git@example.com:org/repo.git")
            if cmd == "fetch":
                return _make_completed_process(1, "", "fatal: unable to connect to origin")
            return _make_completed_process(0)

        tracker._git = _fake_git  # type: ignore[method-assign]

        with pytest.raises(TrackerError, match="Cannot sync native tracker") as exc_info:
            tracker._prepare_default_branch_for_write()

        error_msg = str(exc_info.value)
        assert "fetch" in error_msg.lower()
        assert "Remediation" in error_msg or "remediation" in error_msg.lower()

    def test_ff_only_failure_raises_tracker_error_with_remediation(self, tmp_path):
        """ff-only failure followed by rebase failure must raise TrackerError.

        This is the OOMPAH-10 regression: the old 'git pull --rebase origin main'
        would fail with 'Cannot rebase onto multiple branches' on clean managed
        repos.  The new path tries ff-only first, then rebase as a fallback.
        When both fail, it must raise a TrackerError with actionable text.
        """
        tracker = _tracker(tmp_path, git_sync=True)

        def _fake_git(args: list[str], *, check: bool) -> MagicMock:
            cmd = args[0] if args else ""
            if cmd == "rev-parse":
                return _make_completed_process(0, "true")
            if cmd == "symbolic-ref":
                return _make_completed_process(0, "main")
            if cmd == "remote":
                return _make_completed_process(0, "git@example.com:org/repo.git")
            if cmd == "fetch":
                return _make_completed_process(0)
            if cmd == "merge" and "--ff-only" in args:
                # Simulates a diverged local branch.
                return _make_completed_process(
                    1, "", "fatal: Not possible to fast-forward, aborting."
                )
            if cmd == "rebase" and "--abort" not in args:
                # Rebase fallback also fails (e.g. conflicting changes).
                return _make_completed_process(
                    1, "", "error: could not apply abc1234... task update"
                )
            # rebase --abort and other commands succeed.
            return _make_completed_process(0)

        tracker._git = _fake_git  # type: ignore[method-assign]

        with pytest.raises(TrackerError, match="Cannot sync native tracker") as exc_info:
            tracker._prepare_default_branch_for_write()

        error_msg = str(exc_info.value)
        assert "ff-only" in error_msg or "fast-forward" in error_msg.lower() or "ff_only" in error_msg
        assert "Remediation" in error_msg or "remediation" in error_msg.lower()

    def test_ff_only_failure_rebase_recovery_succeeds(self, tmp_path):
        """When ff-only fails but rebase succeeds, _sync_from_remote must recover silently.

        This is the OOMPAH-204 fix: when local main has diverged from origin
        (e.g. a previous task commit was not pushed), a rebase of the local
        commits onto origin/main puts the checkout back in a pushable state
        without raising a TrackerError that would be filed by error_watcher.
        """
        tracker = _tracker(tmp_path, git_sync=True)
        calls: list[tuple] = []

        def _fake_git(args: list[str], *, check: bool) -> MagicMock:
            calls.append(tuple(args))
            cmd = args[0] if args else ""
            if cmd == "rev-parse":
                return _make_completed_process(0, "true")
            if cmd == "symbolic-ref":
                return _make_completed_process(0, "main")
            if cmd == "remote":
                return _make_completed_process(0, "git@example.com:org/repo.git")
            if cmd == "fetch":
                return _make_completed_process(0)
            if cmd == "merge" and "--ff-only" in args:
                # Diverged — fast-forward not possible.
                return _make_completed_process(
                    1, "", "fatal: Not possible to fast-forward, aborting."
                )
            if cmd == "rebase" and "--abort" not in args:
                # Rebase fallback succeeds.
                return _make_completed_process(0)
            return _make_completed_process(0)

        tracker._git = _fake_git  # type: ignore[method-assign]

        # Must NOT raise — rebase should have recovered the diverged state.
        tracker._prepare_default_branch_for_write()

        arg_strings = [" ".join(c) for c in calls]
        # Rebase fallback must have been attempted.
        assert any("rebase" in s and "--abort" not in s for s in arg_strings), (
            f"Expected rebase fallback call, got: {arg_strings}"
        )
        # Must never call 'git pull --rebase' (OOMPAH-10 regression guard).
        assert not any("pull" in s and "rebase" in s for s in arg_strings), (
            f"Must not use 'git pull --rebase', got: {arg_strings}"
        )

    def test_clean_ff_succeeds_without_pull_rebase(self, tmp_path):
        """A clean up-to-date repo must sync without error and never call pull --rebase."""
        tracker = _tracker(tmp_path, git_sync=True)
        calls: list[tuple] = []

        def _fake_git(args: list[str], *, check: bool) -> MagicMock:
            calls.append(tuple(args))
            cmd = args[0] if args else ""
            if cmd == "rev-parse":
                return _make_completed_process(0, "true")
            if cmd == "symbolic-ref":
                return _make_completed_process(0, "main")
            if cmd == "remote":
                return _make_completed_process(0, "git@example.com:org/repo.git")
            return _make_completed_process(0)

        tracker._git = _fake_git  # type: ignore[method-assign]

        # Should not raise
        tracker._prepare_default_branch_for_write()

        arg_strings = [" ".join(c) for c in calls]
        assert not any("pull" in s for s in arg_strings), (
            f"Expected no 'git pull' call on clean repo, got: {arg_strings}"
        )

    def test_commit_and_push_retry_uses_ff_only_not_pull_rebase(self, tmp_path):
        """_commit_and_push retry path must use fetch+ff-only (or rebase), not pull --rebase."""
        tracker = _tracker(tmp_path, git_sync=True)
        calls: list[tuple] = []
        push_count = [0]

        def _fake_git(args: list[str], *, check: bool) -> MagicMock:
            calls.append(tuple(args))
            cmd = args[0] if args else ""
            if cmd == "rev-parse":
                return _make_completed_process(0, "true")
            if cmd == "symbolic-ref":
                return _make_completed_process(0, "main")
            if cmd == "remote":
                return _make_completed_process(0, "git@example.com:org/repo.git")
            if cmd == "add":
                return _make_completed_process(0)
            if cmd == "diff":
                # Simulate staged changes so commit runs
                return _make_completed_process(1)
            if cmd == "commit":
                return _make_completed_process(0)
            if cmd == "push":
                push_count[0] += 1
                if push_count[0] == 1:
                    # First push fails (rejected)
                    return _make_completed_process(1, "", "! [rejected] main -> main (fetch first)")
                # Second push succeeds
                return _make_completed_process(0)
            if cmd == "fetch":
                return _make_completed_process(0)
            if cmd == "merge" and "--ff-only" in args:
                return _make_completed_process(0)
            return _make_completed_process(0)

        tracker._git = _fake_git  # type: ignore[method-assign]

        tracker._commit_and_push("Test subject")

        arg_strings = [" ".join(c) for c in calls]
        # After push failure, must sync via fetch + ff-only (or rebase fallback)
        assert any("fetch" in s and "origin" in s for s in arg_strings), (
            f"Expected git fetch after push failure, got: {arg_strings}"
        )
        assert any("merge" in s and "--ff-only" in s for s in arg_strings), (
            f"Expected git merge --ff-only after push failure, got: {arg_strings}"
        )
        # Must NOT use 'git pull --rebase' in retry
        assert not any("pull" in s and "rebase" in s for s in arg_strings), (
            f"Expected no 'git pull --rebase' in retry path, got: {arg_strings}"
        )

    def test_commit_and_push_retry_rebase_recovery_on_diverged_branch(self, tmp_path):
        """When push is rejected and ff-only fails (diverged local+origin), rebase recovers.

        This is the OOMPAH-204 scenario: _commit_and_push commits a task
        update, the push is rejected because origin has new commits, and now
        local main has diverged (our task commit + origin's new commits).
        The ff-only merge fails, but the rebase fallback puts our commit on top
        of origin so the second push succeeds.
        """
        tracker = _tracker(tmp_path, git_sync=True)
        calls: list[tuple] = []
        push_count = [0]

        def _fake_git(args: list[str], *, check: bool) -> MagicMock:
            calls.append(tuple(args))
            cmd = args[0] if args else ""
            if cmd == "rev-parse":
                return _make_completed_process(0, "true")
            if cmd == "symbolic-ref":
                return _make_completed_process(0, "main")
            if cmd == "remote":
                return _make_completed_process(0, "git@example.com:org/repo.git")
            if cmd == "add":
                return _make_completed_process(0)
            if cmd == "diff":
                # Simulate staged changes so commit runs.
                return _make_completed_process(1)
            if cmd == "commit":
                return _make_completed_process(0)
            if cmd == "push":
                push_count[0] += 1
                if push_count[0] == 1:
                    # First push rejected: origin has new commits since our base.
                    return _make_completed_process(
                        1, "", "! [rejected] main -> main (fetch first)"
                    )
                # Second push (after rebase) succeeds.
                return _make_completed_process(0)
            if cmd == "fetch":
                return _make_completed_process(0)
            if cmd == "merge" and "--ff-only" in args:
                # Diverged: our task commit + origin's new commits → can't ff.
                return _make_completed_process(
                    1, "", "fatal: Not possible to fast-forward, aborting."
                )
            if cmd == "rebase" and "--abort" not in args:
                # Rebase puts our task commit on top of origin/main.
                return _make_completed_process(0)
            return _make_completed_process(0)

        tracker._git = _fake_git  # type: ignore[method-assign]

        # Must not raise — the rebase fallback should recover the diverged branch.
        tracker._commit_and_push("Test subject")

        assert push_count[0] == 2, (
            f"Expected 2 push attempts (first rejected, second after rebase), got {push_count[0]}"
        )
        arg_strings = [" ".join(c) for c in calls]
        # Rebase fallback must have been attempted.
        assert any("rebase" in s and "--abort" not in s for s in arg_strings), (
            f"Expected rebase fallback in retry path, got: {arg_strings}"
        )
        # Must NOT use 'git pull --rebase' (OOMPAH-10 regression guard).
        assert not any("pull" in s and "rebase" in s for s in arg_strings), (
            f"Must not use 'git pull --rebase', got: {arg_strings}"
        )


# ---------------------------------------------------------------------------
# OOMPAH-28: Comprehensive native tracker state transition audit
# ---------------------------------------------------------------------------


class TestOompahMarkdownTrackerAllStatusDirectories:
    """Verify that every canonical status maps to the correct on-disk directory.

    This test class directly covers the OOMPAH-28 audit requirement: each
    named status in the 1.0 lifecycle must round-trip through the native
    tracker by placing task files in the expected subdirectory of
    ``.oompah/tasks``.
    """

    # Maps canonical status name → expected subdirectory under .oompah/tasks
    _STATUS_DIR_MATRIX = [
        (PROPOSED,           "proposed"),
        (BACKLOG,            "backlog"),
        (OPEN,               "open"),
        (IN_PROGRESS,        "in-progress"),
        (NEEDS_ANSWER,       "needs-answer"),
        (NEEDS_HUMAN,        "needs-human"),
        (NEEDS_CI_FIX,       "needs-ci-fix"),
        (NEEDS_REBASE,       "needs-rebase"),
        (IN_REVIEW,          "in-review"),
        (DECOMPOSED,         "decomposed"),
        (DUPLICATE_CANDIDATE, "duplicate-candidate"),
        (DONE,               "done"),
        (MERGED,             "merged"),
        (ARCHIVED,           "archived"),
    ]

    @pytest.mark.parametrize("status,expected_dir", _STATUS_DIR_MATRIX)
    def test_initial_status_places_file_in_correct_directory(
        self, tmp_path, status, expected_dir
    ):
        """Creating a task with *status* must write the file under tasks/<expected_dir>/."""
        tracker = _tracker(tmp_path)

        issue = tracker.create_issue(f"Task for {status}", initial_status=status)

        path = tmp_path / "repo" / ".oompah" / "tasks" / expected_dir / f"{issue.identifier}.md"
        assert path.exists(), (
            f"Expected file at tasks/{expected_dir}/{issue.identifier}.md "
            f"for status {status!r}"
        )
        meta = _frontmatter(path)
        assert meta["status"] == status

    @pytest.mark.parametrize("status,expected_dir", _STATUS_DIR_MATRIX)
    def test_update_status_moves_file_to_correct_directory(
        self, tmp_path, status, expected_dir
    ):
        """Transitioning an existing task to *status* must move the file to
        tasks/<expected_dir>/ and remove it from the old location."""
        tracker = _tracker(tmp_path)
        issue = tracker.create_issue(f"Transition to {status}", initial_status=BACKLOG)
        old_path = tmp_path / "repo" / ".oompah" / "tasks" / "backlog" / f"{issue.identifier}.md"
        assert old_path.exists(), "Precondition: task starts in backlog/"

        tracker.update_issue(issue.identifier, status=status)

        new_path = (
            tmp_path / "repo" / ".oompah" / "tasks" / expected_dir / f"{issue.identifier}.md"
        )
        assert new_path.exists(), (
            f"Expected file at tasks/{expected_dir}/{issue.identifier}.md "
            f"after transitioning to {status!r}"
        )
        if expected_dir != "backlog":
            assert not old_path.exists(), (
                f"Old file at tasks/backlog/{issue.identifier}.md should have been removed "
                f"when status moved to {status!r}"
            )
        refreshed = tracker.fetch_issue_detail(issue.identifier)
        assert refreshed is not None
        assert refreshed.state == status

    @pytest.mark.parametrize("status,expected_dir", _STATUS_DIR_MATRIX)
    def test_fetch_issue_detail_reads_from_any_status_directory(
        self, tmp_path, status, expected_dir
    ):
        """fetch_issue_detail must locate and return a task in any status directory."""
        tracker = _tracker(tmp_path)
        issue = tracker.create_issue(f"Findable task in {status}", initial_status=status)

        found = tracker.fetch_issue_detail(issue.identifier)

        assert found is not None, f"task with status {status!r} was not found"
        assert found.state == status


class TestOompahMarkdownTrackerFullLifecycle:
    """Walk a task through the canonical 1.0 lifecycle end-to-end."""

    def test_proposed_to_backlog_to_open_to_in_progress_to_in_review_to_merged(
        self, tmp_path
    ):
        """Task advances through the normal feature-development lifecycle.

        Each transition must move the file to the correct directory and
        fetch_issue_detail must reflect the new state after each hop.
        """
        tracker = _tracker(tmp_path)
        tasks_root = tmp_path / "repo" / ".oompah" / "tasks"

        issue = tracker.create_issue("Feature work", initial_status=PROPOSED)
        assert (tasks_root / "proposed" / f"{issue.identifier}.md").exists()

        for status, expected_dir in [
            (BACKLOG,       "backlog"),
            (OPEN,          "open"),
            (IN_PROGRESS,   "in-progress"),
            (IN_REVIEW,     "in-review"),
            (MERGED,        "merged"),
        ]:
            tracker.update_issue(issue.identifier, status=status)
            path = tasks_root / expected_dir / f"{issue.identifier}.md"
            assert path.exists(), (
                f"Expected tasks/{expected_dir}/{issue.identifier}.md after moving to {status}"
            )
            refreshed = tracker.fetch_issue_detail(issue.identifier)
            assert refreshed.state == status, (
                f"Expected state {status!r}, got {refreshed.state!r}"
            )

    def test_task_can_be_archived_from_any_non_terminal_state(self, tmp_path):
        """archive_issue must move any non-terminal task to archived/."""
        tracker = _tracker(tmp_path)
        tasks_root = tmp_path / "repo" / ".oompah" / "tasks"

        for start_status, start_dir in [
            (OPEN,        "open"),
            (IN_PROGRESS, "in-progress"),
            (NEEDS_HUMAN, "needs-human"),
        ]:
            issue = tracker.create_issue(
                f"Archive from {start_status}", initial_status=start_status
            )
            assert (tasks_root / start_dir / f"{issue.identifier}.md").exists()

            tracker.archive_issue(issue.identifier)

            assert (tasks_root / "archived" / f"{issue.identifier}.md").exists(), (
                f"Task should be in archived/ after archiving from {start_status}"
            )
            refreshed = tracker.fetch_issue_detail(issue.identifier)
            assert refreshed.state == ARCHIVED

    def test_terminal_state_retransition_is_allowed(self, tmp_path):
        """Transitioning away from a terminal state (un-archiving/re-opening) must work.

        The native tracker intentionally allows re-transition from terminal
        states so operators can recover accidentally-closed or archived tasks.
        """
        tracker = _tracker(tmp_path)
        tasks_root = tmp_path / "repo" / ".oompah" / "tasks"

        issue = tracker.create_issue("Terminal re-transition", initial_status=DONE)
        assert (tasks_root / "done" / f"{issue.identifier}.md").exists()

        # Re-open from Done → Open
        tracker.update_issue(issue.identifier, status=OPEN)
        assert (tasks_root / "open" / f"{issue.identifier}.md").exists()
        assert tracker.fetch_issue_detail(issue.identifier).state == OPEN

        # Archive from Done
        tracker.update_issue(issue.identifier, status=DONE)
        tracker.update_issue(issue.identifier, status=ARCHIVED)
        assert (tasks_root / "archived" / f"{issue.identifier}.md").exists()

        # Un-archive back to Backlog
        tracker.update_issue(issue.identifier, status=BACKLOG)
        assert (tasks_root / "backlog" / f"{issue.identifier}.md").exists()
        assert tracker.fetch_issue_detail(issue.identifier).state == BACKLOG


class TestOompahMarkdownTrackerProposedStatus:
    """Proposed tasks must be excluded from dispatch but visible in fetch_all_issues."""

    def test_proposed_tasks_are_excluded_from_dispatch_candidates(self, tmp_path):
        """fetch_candidate_issues must never return Proposed tasks."""
        tracker = _tracker(tmp_path)
        tracker.create_issue("Proposed task", initial_status=PROPOSED)
        tracker.create_issue("Open task", initial_status=OPEN)

        candidates = tracker.fetch_candidate_issues()

        identifiers = [i.identifier for i in candidates]
        assert "REPO-1" not in identifiers, "Proposed task must not be dispatched"
        assert "REPO-2" in identifiers, "Open task must be available for dispatch"

    def test_proposed_tasks_appear_in_fetch_all_issues(self, tmp_path):
        """fetch_all_issues must include Proposed tasks (they are visible but not dispatchable)."""
        tracker = _tracker(tmp_path)
        tracker.create_issue("Proposed task", initial_status=PROPOSED)

        all_issues = tracker.fetch_all_issues()

        states = [i.state for i in all_issues]
        assert PROPOSED in states, "Proposed task must appear in fetch_all_issues"

    def test_proposed_tasks_appear_in_fetch_issues_by_states(self, tmp_path):
        """fetch_issues_by_states([Proposed]) must return Proposed tasks."""
        tracker = _tracker(tmp_path)
        tracker.create_issue("Proposed task", initial_status=PROPOSED)
        tracker.create_issue("Backlog task", initial_status=BACKLOG)

        proposed = tracker.fetch_issues_by_states([PROPOSED])

        assert len(proposed) == 1
        assert proposed[0].state == PROPOSED


class TestOompahMarkdownTrackerDecomposedAndDuplicateStatuses:
    """Decomposed and Duplicate Candidate tasks must round-trip correctly."""

    def test_decomposed_task_is_excluded_from_dispatch(self, tmp_path):
        """Decomposed tasks must not be returned as dispatch candidates."""
        tracker = _tracker(tmp_path)
        tracker.create_issue("Decomposed", initial_status=DECOMPOSED)
        tracker.create_issue("Open", initial_status=OPEN)

        candidates = tracker.fetch_candidate_issues()

        identifiers = [i.identifier for i in candidates]
        assert "REPO-1" not in identifiers, "Decomposed task must not be dispatched"
        assert "REPO-2" in identifiers

    def test_duplicate_candidate_task_is_excluded_from_dispatch(self, tmp_path):
        """Duplicate Candidate tasks must not be returned as dispatch candidates."""
        tracker = _tracker(tmp_path)
        tracker.create_issue("Duplicate Candidate task", initial_status=DUPLICATE_CANDIDATE)
        tracker.create_issue("Open", initial_status=OPEN)

        candidates = tracker.fetch_candidate_issues()

        identifiers = [i.identifier for i in candidates]
        assert "REPO-1" not in identifiers, "Duplicate Candidate task must not be dispatched"
        assert "REPO-2" in identifiers

    def test_decomposed_epic_children_carry_correct_state(self, tmp_path):
        """An epic transitioned to Decomposed must still show Decomposed state."""
        tracker = _tracker(tmp_path)
        epic = tracker.create_issue("Big Epic", issue_type="epic", initial_status=BACKLOG)

        tracker.update_issue(epic.identifier, status=DECOMPOSED)

        refreshed = tracker.fetch_issue_detail(epic.identifier)
        assert refreshed.state == DECOMPOSED
        path = (
            tmp_path / "repo" / ".oompah" / "tasks" / "decomposed" / f"{epic.identifier}.md"
        )
        assert path.exists()


class TestOompahMarkdownTrackerWaitingStatuses:
    """Needs Answer / Needs Human tasks represent the 'awaiting' intake sub-states.

    In the native tracker, 'awaiting owner' conceptually maps to Needs Human
    and 'awaiting requestor' conceptually maps to Needs Answer.  Both must:
    - place the task file in the correct directory
    - be retrievable via fetch_issue_detail
    - NOT appear as dispatch candidates
    - be recoverable (transitionable back to Open or In Progress)
    """

    def test_needs_answer_task_lands_in_correct_directory(self, tmp_path):
        tracker = _tracker(tmp_path)
        issue = tracker.create_issue("Awaiting requestor", initial_status=NEEDS_ANSWER)
        path = (
            tmp_path / "repo" / ".oompah" / "tasks" / "needs-answer" / f"{issue.identifier}.md"
        )
        assert path.exists()
        assert tracker.fetch_issue_detail(issue.identifier).state == NEEDS_ANSWER

    def test_needs_human_task_lands_in_correct_directory(self, tmp_path):
        tracker = _tracker(tmp_path)
        issue = tracker.create_issue("Awaiting owner", initial_status=NEEDS_HUMAN)
        path = (
            tmp_path / "repo" / ".oompah" / "tasks" / "needs-human" / f"{issue.identifier}.md"
        )
        assert path.exists()
        assert tracker.fetch_issue_detail(issue.identifier).state == NEEDS_HUMAN

    def test_needs_answer_is_not_a_dispatch_candidate(self, tmp_path):
        tracker = _tracker(tmp_path)
        tracker.create_issue("Awaiting requestor", initial_status=NEEDS_ANSWER)
        candidates = tracker.fetch_candidate_issues()
        assert candidates == []

    def test_needs_human_is_not_a_dispatch_candidate(self, tmp_path):
        tracker = _tracker(tmp_path)
        tracker.create_issue("Awaiting owner", initial_status=NEEDS_HUMAN)
        candidates = tracker.fetch_candidate_issues()
        assert candidates == []

    def test_mark_needs_human_transitions_task_and_adds_comment(self, tmp_path):
        """mark_needs_human convenience method must update status and add a comment."""
        tracker = _tracker(tmp_path)
        issue = tracker.create_issue("In progress task", initial_status=IN_PROGRESS)

        tracker.mark_needs_human(issue.identifier, "Needs owner decision on approach.")

        refreshed = tracker.fetch_issue_detail(issue.identifier)
        assert refreshed.state == NEEDS_HUMAN
        comments = tracker.fetch_comments(issue.identifier)
        assert any("Needs owner decision" in c["text"] for c in comments)

    def test_needs_answer_task_can_return_to_in_progress(self, tmp_path):
        """A task blocked on an answer can be recovered to In Progress."""
        tracker = _tracker(tmp_path)
        issue = tracker.create_issue("Blocked task", initial_status=NEEDS_ANSWER)

        tracker.update_issue(issue.identifier, status=IN_PROGRESS)

        refreshed = tracker.fetch_issue_detail(issue.identifier)
        assert refreshed.state == IN_PROGRESS
        path = (
            tmp_path / "repo" / ".oompah" / "tasks" / "in-progress" / f"{issue.identifier}.md"
        )
        assert path.exists()

    def test_needs_human_task_can_return_to_open(self, tmp_path):
        """A task waiting on a human can be returned to Open after the human acts."""
        tracker = _tracker(tmp_path)
        issue = tracker.create_issue("Waiting for decision", initial_status=NEEDS_HUMAN)

        tracker.update_issue(issue.identifier, status=OPEN)

        refreshed = tracker.fetch_issue_detail(issue.identifier)
        assert refreshed.state == OPEN
        path = tmp_path / "repo" / ".oompah" / "tasks" / "open" / f"{issue.identifier}.md"
        assert path.exists()


class TestOompahMarkdownTrackerReviewPipelineStatuses:
    """In Review / Needs CI Fix / Needs Rebase cover the PR-review pipeline."""

    def test_in_review_task_lands_in_in_review_directory(self, tmp_path):
        tracker = _tracker(tmp_path)
        issue = tracker.create_issue("Under review", initial_status=IN_REVIEW)
        path = (
            tmp_path / "repo" / ".oompah" / "tasks" / "in-review" / f"{issue.identifier}.md"
        )
        assert path.exists()
        assert tracker.fetch_issue_detail(issue.identifier).state == IN_REVIEW

    def test_needs_ci_fix_task_lands_in_needs_ci_fix_directory(self, tmp_path):
        tracker = _tracker(tmp_path)
        issue = tracker.create_issue("CI failing", initial_status=NEEDS_CI_FIX)
        path = (
            tmp_path / "repo" / ".oompah" / "tasks" / "needs-ci-fix" / f"{issue.identifier}.md"
        )
        assert path.exists()
        assert tracker.fetch_issue_detail(issue.identifier).state == NEEDS_CI_FIX

    def test_needs_rebase_task_lands_in_needs_rebase_directory(self, tmp_path):
        tracker = _tracker(tmp_path)
        issue = tracker.create_issue("Conflicting PR", initial_status=NEEDS_REBASE)
        path = (
            tmp_path / "repo" / ".oompah" / "tasks" / "needs-rebase" / f"{issue.identifier}.md"
        )
        assert path.exists()
        assert tracker.fetch_issue_detail(issue.identifier).state == NEEDS_REBASE

    def test_review_pipeline_full_path_in_progress_to_merged(self, tmp_path):
        """Task walks through In Progress → In Review → Needs CI Fix → In Review → Merged."""
        tracker = _tracker(tmp_path)
        tasks_root = tmp_path / "repo" / ".oompah" / "tasks"
        issue = tracker.create_issue("PR lifecycle", initial_status=IN_PROGRESS)

        for status, expected_dir in [
            (IN_REVIEW,     "in-review"),
            (NEEDS_CI_FIX,  "needs-ci-fix"),
            (IN_REVIEW,     "in-review"),
            (MERGED,        "merged"),
        ]:
            tracker.update_issue(issue.identifier, status=status)
            assert (tasks_root / expected_dir / f"{issue.identifier}.md").exists(), (
                f"Expected tasks/{expected_dir}/{issue.identifier}.md after moving to {status}"
            )
            assert tracker.fetch_issue_detail(issue.identifier).state == status


# ---------------------------------------------------------------------------
# Atomic write tests
# ---------------------------------------------------------------------------


class TestAtomicWrite:
    """_write_markdown must use atomic rename so a failed write never corrupts
    the original file."""

    def test_write_failure_leaves_original_file_intact(self, tmp_path):
        """When Path.replace raises (e.g. disk full after temp write), the
        original task file must remain untouched."""
        from unittest.mock import patch
        import pathlib

        tracker = _tracker(tmp_path)
        issue = tracker.create_issue("Original task")
        path = (
            tmp_path / "repo" / ".oompah" / "tasks" / "backlog"
            / f"{issue.identifier}.md"
        )
        original_content = path.read_text(encoding="utf-8")
        assert original_content.startswith("---\n")

        # Patch Path.replace to simulate a failure during the rename step.
        original_replace = pathlib.Path.replace

        def failing_replace(self_path, target):
            raise OSError("Simulated disk full")

        with patch.object(pathlib.Path, "replace", failing_replace):
            with pytest.raises(TrackerError, match="Cannot write native task"):
                tracker.update_issue(issue.identifier, description="NEW content")

        # The original file must be unchanged.
        assert path.read_text(encoding="utf-8") == original_content

    def test_write_failure_does_not_leave_temp_files_behind(self, tmp_path):
        """A failed write must clean up any temp file it created."""
        from unittest.mock import patch
        import pathlib

        tracker = _tracker(tmp_path)
        issue = tracker.create_issue("Temp cleanup test")
        tasks_dir = tmp_path / "repo" / ".oompah" / "tasks" / "backlog"

        original_replace = pathlib.Path.replace

        def failing_replace(self_path, target):
            raise OSError("Simulated failure")

        with patch.object(pathlib.Path, "replace", failing_replace):
            with pytest.raises(TrackerError):
                tracker.update_issue(issue.identifier, description="trigger write")

        # No .tmp orphan files should remain.
        tmp_files = list(tasks_dir.glob(".oompah_tmp_*.tmp"))
        assert tmp_files == [], f"Orphan temp files found: {tmp_files}"

    def test_successful_write_replaces_file_content(self, tmp_path):
        """A successful write must produce the expected file content."""
        tracker = _tracker(tmp_path)
        issue = tracker.create_issue("Replace me", description="Original description")
        path = (
            tmp_path / "repo" / ".oompah" / "tasks" / "backlog"
            / f"{issue.identifier}.md"
        )
        assert issue.description == "Original description"

        tracker.update_issue(issue.identifier, description="Updated description")

        refreshed = tracker.fetch_issue_detail(issue.identifier)
        assert refreshed is not None
        assert refreshed.description == "Updated description"
        # Verify the file on disk reflects the update.
        assert "Updated description" in path.read_text(encoding="utf-8")

    def test_write_does_not_use_md_suffix_for_temp_files(self, tmp_path):
        """Temp files during write must NOT use .md suffix to avoid being
        picked up by the */*.md glob in _read_records."""
        from unittest.mock import patch
        import pathlib

        tracker = _tracker(tmp_path)
        issue = tracker.create_issue("Glob safety")
        tasks_dir = tmp_path / "repo" / ".oompah" / "tasks" / "backlog"

        def capturing_replace(self_path, target):
            # Record the temp file name, then succeed.
            capturing_replace.tmp_names.append(self_path.name)
            original_replace(self_path, target)

        original_replace = pathlib.Path.replace
        capturing_replace.tmp_names = []

        with patch.object(pathlib.Path, "replace", capturing_replace):
            tracker.update_issue(issue.identifier, description="trigger write")

        for name in capturing_replace.tmp_names:
            assert not name.endswith(".md"), (
                f"Temp file used .md suffix: {name!r} — would be picked up by */*.md glob"
            )


# ---------------------------------------------------------------------------
# Corrupt file handling tests
# ---------------------------------------------------------------------------


class TestCorruptFileHandling:
    """Tests for corrupt/unreadable task file detection and ID-reuse prevention."""

    def test_corrupt_file_does_not_block_valid_tasks(self, tmp_path):
        """A corrupt task file must not prevent valid tasks from being fetched."""
        tracker = _tracker(tmp_path)
        valid = tracker.create_issue("Valid task")
        # Corrupt the file by zeroing it.
        path = (
            tmp_path / "repo" / ".oompah" / "tasks" / "backlog"
            / f"{valid.identifier}.md"
        )
        path.write_text("", encoding="utf-8")

        # Create a second, fully valid task.
        second = tracker.create_issue("Second task")
        tracker.invalidate_read_cache()

        issues = tracker.fetch_all_issues()
        ids = {i.identifier for i in issues}
        assert second.identifier in ids
        # The corrupt first task is NOT in the valid list.
        assert valid.identifier not in ids

    def test_corrupt_file_appears_in_list_corrupt_stubs(self, tmp_path):
        """Corrupt task files must be listed by list_corrupt_stubs()."""
        tracker = _tracker(tmp_path)
        issue = tracker.create_issue("Will be corrupted")
        path = (
            tmp_path / "repo" / ".oompah" / "tasks" / "backlog"
            / f"{issue.identifier}.md"
        )
        path.write_text("", encoding="utf-8")  # Zero bytes — no front matter
        tracker.invalidate_read_cache()

        tracker.fetch_all_issues()  # Populates corrupt stubs
        stubs = tracker.list_corrupt_stubs()

        assert len(stubs) == 1
        assert stubs[0]["stem"] == issue.identifier

    def test_zero_byte_task_file_appears_in_corrupt_stubs(self, tmp_path):
        """Exactly-zero-byte files are treated as corrupt (missing front matter)."""
        tracker = _tracker(tmp_path)
        issue = tracker.create_issue("Zero byte test")
        path = (
            tmp_path / "repo" / ".oompah" / "tasks" / "backlog"
            / f"{issue.identifier}.md"
        )
        assert path.stat().st_size > 0
        path.write_bytes(b"")  # Explicitly zero out
        assert path.stat().st_size == 0
        tracker.invalidate_read_cache()

        tracker.fetch_all_issues()
        stubs = tracker.list_corrupt_stubs()

        assert any(s["stem"] == issue.identifier for s in stubs)

    def test_next_identifier_skips_corrupt_file_stem(self, tmp_path):
        """_next_identifier must not reuse the ID of a corrupt file.

        This is the primary guard against the TRICKLE-8 failure mode: a
        zero-byte in-progress file becomes invisible to _read_records but its
        stem (REPO-1) should still prevent REPO-1 from being assigned to a
        brand-new task.
        """
        tracker = _tracker(tmp_path)
        # Create REPO-1 and then corrupt it.
        issue = tracker.create_issue("Will be corrupted")
        assert issue.identifier == "REPO-1"
        path = (
            tmp_path / "repo" / ".oompah" / "tasks" / "backlog"
            / f"{issue.identifier}.md"
        )
        path.write_text("", encoding="utf-8")
        tracker.invalidate_read_cache()

        # Valid records scan sees nothing (REPO-1 is corrupt).
        valid_ids = {i.identifier for i in tracker.fetch_all_issues()}
        assert "REPO-1" not in valid_ids

        # But _next_identifier must scan file stems and skip REPO-1.
        second = tracker.create_issue("New task after corruption")
        assert second.identifier == "REPO-2", (
            f"Expected REPO-2 but got {second.identifier!r} — "
            "corrupt file stem REPO-1 should not be reused"
        )

    def test_invalidate_read_cache_also_clears_corrupt_stubs(self, tmp_path):
        """invalidate_read_cache must clear both read cache and corrupt stubs."""
        tracker = _tracker(tmp_path)
        issue = tracker.create_issue("Will be corrupted")
        path = (
            tmp_path / "repo" / ".oompah" / "tasks" / "backlog"
            / f"{issue.identifier}.md"
        )
        path.write_text("", encoding="utf-8")
        tracker.invalidate_read_cache()
        tracker.fetch_all_issues()
        assert len(tracker.list_corrupt_stubs()) == 1

        # After repairing the file and invalidating the cache, stubs should be empty.
        from oompah.oompah_md_tracker import _write_markdown
        meta = {"id": issue.identifier, "status": "Backlog", "title": "Repaired"}
        _write_markdown(path, meta, "## Summary\n\nRepaired.\n")
        tracker.invalidate_read_cache()
        tracker.fetch_all_issues()
        assert tracker.list_corrupt_stubs() == []


# ---------------------------------------------------------------------------
# Import index tests
# ---------------------------------------------------------------------------


class TestImportIndex:
    """Tests for the external-imports.yml import index."""

    def test_record_external_import_creates_index_file(self, tmp_path):
        """record_external_import must persist the mapping to the index file."""
        import yaml

        tracker = _tracker(tmp_path)
        tracker.create_issue("Imported task")  # Ensure tasks_root exists.
        tracker.record_external_import("example-org/app#42", "REPO-1")

        index_path = tmp_path / "repo" / ".oompah" / "tasks" / "external-imports.yml"
        assert index_path.exists()
        data = yaml.safe_load(index_path.read_text(encoding="utf-8"))
        assert data["example-org/app#42"] == "REPO-1"

    def test_find_imported_task_id_for_external_returns_recorded_id(self, tmp_path):
        """find_imported_task_id_for_external must return the last recorded ID."""
        tracker = _tracker(tmp_path)
        tracker.create_issue("Imported task")
        tracker.record_external_import("example-org/app#42", "REPO-1")

        result = tracker.find_imported_task_id_for_external("example-org/app#42")
        assert result == "REPO-1"

    def test_find_imported_task_id_returns_none_for_unknown(self, tmp_path):
        """find_imported_task_id_for_external returns None for unknown external IDs."""
        tracker = _tracker(tmp_path)
        result = tracker.find_imported_task_id_for_external("never-seen/repo#999")
        assert result is None

    def test_record_external_import_is_idempotent(self, tmp_path):
        """Calling record_external_import twice with the same args must not
        produce duplicate entries."""
        import yaml

        tracker = _tracker(tmp_path)
        tracker.create_issue("Task")
        tracker.record_external_import("org/repo#1", "REPO-1")
        tracker.record_external_import("org/repo#1", "REPO-1")

        index_path = tmp_path / "repo" / ".oompah" / "tasks" / "external-imports.yml"
        data = yaml.safe_load(index_path.read_text(encoding="utf-8"))
        assert list(data.keys()).count("org/repo#1") == 1

    def test_import_index_survives_task_file_corruption(self, tmp_path):
        """The import index file itself is not affected when a task file is
        corrupted."""
        tracker = _tracker(tmp_path)
        issue = tracker.create_issue("Task will be corrupted")
        tracker.record_external_import("example-org/app#99", issue.identifier)

        # Corrupt the task file.
        path = (
            tmp_path / "repo" / ".oompah" / "tasks" / "backlog"
            / f"{issue.identifier}.md"
        )
        path.write_text("", encoding="utf-8")
        tracker.invalidate_read_cache()

        # Import index still resolves the mapping.
        result = tracker.find_imported_task_id_for_external("example-org/app#99")
        assert result == issue.identifier

    def test_index_file_is_written_atomically(self, tmp_path):
        """record_external_import must use atomic write (no truncation-before-write)."""
        from unittest.mock import patch
        import pathlib

        tracker = _tracker(tmp_path)
        tracker.create_issue("Task")
        # Write a first entry successfully.
        tracker.record_external_import("org/repo#1", "REPO-1")

        index_path = tmp_path / "repo" / ".oompah" / "tasks" / "external-imports.yml"
        original_content = index_path.read_text(encoding="utf-8")

        original_replace = pathlib.Path.replace

        def failing_replace(self_path, target):
            raise OSError("Simulated disk full")

        # A failed write of a second entry must not corrupt the first entry.
        # record_external_import swallows the OSError and logs a warning so
        # the caller is not disrupted.  The original index content must survive.
        with patch.object(pathlib.Path, "replace", failing_replace):
            tracker.record_external_import("org/repo#2", "REPO-2")  # fails silently

        assert index_path.read_text(encoding="utf-8") == original_content
