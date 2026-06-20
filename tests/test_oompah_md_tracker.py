"""Tests for the native oompah Markdown tracker."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest
import yaml

from oompah.oompah_md_tracker import OompahMarkdownTracker
from oompah.statuses import BACKLOG, DONE, OPEN
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

        refreshed = tracker.fetch_issue_detail(child.identifier)
        assert refreshed.parent_id == parent.identifier
        assert refreshed.blocked_by[0].identifier == "REPO-99"
        assert "backend" in refreshed.labels
        assert refreshed.work_branch == "oompah/repo-1"
        assert tracker.get_metadata(child.identifier)["oompah.work_branch"] == "oompah/repo-1"

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
        """A diverged branch (ff-only fails) must raise TrackerError with actionable text.

        This is the OOMPAH-10 regression: the old 'git pull --rebase origin main'
        would fail with 'Cannot rebase onto multiple branches' on clean managed
        repos.  The new ff-only path must instead raise a TrackerError that
        surfaces the problem without silently aborting dispatch.
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
                # Simulates a diverged local branch — analogous to what
                # `git pull --rebase` would report as
                # "Cannot rebase onto multiple branches".
                return _make_completed_process(
                    1, "", "fatal: Not possible to fast-forward, aborting."
                )
            return _make_completed_process(0)

        tracker._git = _fake_git  # type: ignore[method-assign]

        with pytest.raises(TrackerError, match="Cannot sync native tracker") as exc_info:
            tracker._prepare_default_branch_for_write()

        error_msg = str(exc_info.value)
        assert "ff-only" in error_msg or "fast-forward" in error_msg.lower() or "ff_only" in error_msg
        assert "Remediation" in error_msg or "remediation" in error_msg.lower()

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
        """_commit_and_push retry path must also use fetch+ff-only, not pull --rebase."""
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
        # After push failure, must sync via fetch + ff-only
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
