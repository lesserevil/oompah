"""Tests for the cherry-pick + push + PR-open module (TASK-455.4 / TASK-455.5)."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from unittest.mock import MagicMock, call, patch

import pytest

from oompah.cherry_pick_pr_creator import (
    CherryPickConflictError,
    CherryPickError,
    _has_cherry_pick_in_progress,
    _has_new_commits,
    _sanitize_identifier,
    _write_child_backport_of,
    apply_cherry_pick,
    cherry_pick_push_and_open_pr,
    open_backport_pr,
    push_branch,
)
from oompah.models import Issue
from oompah.release_pick_schema import BackportEntry, ReleasePick
from oompah.statuses import IN_REVIEW, NEEDS_REBASE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _issue(
    identifier: str = "TASK-1",
    title: str = "Do something",
    state: str = "Open",
    target_branch: str | None = None,
    branch_name: str | None = None,
) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=title,
        description="desc",
        state=state,
        target_branch=target_branch,
        labels=[],
        project_id="proj-1",
    )


def _make_review(id: str = "42", url: str = "https://github.com/org/repo/pull/42"):
    rv = MagicMock()
    rv.id = id
    rv.url = url
    return rv


# ---------------------------------------------------------------------------
# _sanitize_identifier
# ---------------------------------------------------------------------------


class TestSanitizeIdentifier:
    def test_dot_replaced_with_itself(self):
        assert _sanitize_identifier("TASK-455.4") == "TASK-455.4"

    def test_spaces_become_underscores(self):
        result = _sanitize_identifier("task 1 2")
        assert " " not in result

    def test_empty_string_returns_unnamed(self):
        assert _sanitize_identifier("") == "unnamed"

    def test_leading_special_chars_stripped(self):
        result = _sanitize_identifier("__TASK-1")
        assert not result.startswith("_")


# ---------------------------------------------------------------------------
# _has_new_commits
# ---------------------------------------------------------------------------


class TestHasNewCommits:
    def test_returns_true_when_commits_ahead(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="3\n")
            assert _has_new_commits("/wt", "release/1.0") is True
            mock_run.assert_called_once_with(
                ["git", "rev-list", "--count", "HEAD", "^origin/release/1.0"],
                cwd="/wt",
                capture_output=True,
                text=True,
                timeout=30,
            )

    def test_returns_false_when_no_commits_ahead(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="0\n")
            assert _has_new_commits("/wt", "release/1.0") is False

    def test_returns_false_on_nonzero_exit(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="")
            assert _has_new_commits("/wt", "release/1.0") is False

    def test_returns_false_on_exception(self):
        with patch("subprocess.run", side_effect=OSError("no git")):
            assert _has_new_commits("/wt", "release/1.0") is False

    def test_returns_false_on_non_integer_output(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="not_a_number")
            assert _has_new_commits("/wt", "release/1.0") is False


# ---------------------------------------------------------------------------
# _has_cherry_pick_in_progress
# ---------------------------------------------------------------------------


class TestHasCherryPickInProgress:
    def test_returns_true_when_cherry_pick_head_exists(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="/wt/.git\n")
            with patch("os.path.exists", return_value=True) as mock_exists:
                result = _has_cherry_pick_in_progress("/wt")
                assert result is True
                mock_exists.assert_called_once_with("/wt/.git/CHERRY_PICK_HEAD")

    def test_returns_false_when_cherry_pick_head_absent(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="/wt/.git\n")
            with patch("os.path.exists", return_value=False):
                assert _has_cherry_pick_in_progress("/wt") is False

    def test_returns_false_when_git_dir_fails(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="")
            assert _has_cherry_pick_in_progress("/wt") is False

    def test_returns_false_on_exception(self):
        with patch("subprocess.run", side_effect=OSError("no git")):
            assert _has_cherry_pick_in_progress("/wt") is False

    def test_resolves_relative_git_dir(self):
        """Relative .git/worktrees paths are resolved relative to wt_path."""
        with patch("subprocess.run") as mock_run:
            # git worktrees return a relative path like ".git/worktrees/xxx"
            mock_run.return_value = MagicMock(
                returncode=0, stdout=".git/worktrees/child\n"
            )
            with patch("os.path.exists", return_value=True) as mock_exists:
                _has_cherry_pick_in_progress("/the/worktree")
                # Path must be resolved relative to wt_path
                called_path = mock_exists.call_args[0][0]
                assert called_path.startswith("/the/worktree/")
                assert "CHERRY_PICK_HEAD" in called_path


# ---------------------------------------------------------------------------
# apply_cherry_pick
# ---------------------------------------------------------------------------


class TestApplyCherryPick:
    def test_raises_value_error_for_empty_commits(self):
        with pytest.raises(ValueError, match="empty"):
            apply_cherry_pick("/wt", [])

    def test_success_calls_cherry_pick_with_all_commits(self):
        commits = ["abc1234", "def5678"]
        with patch("subprocess.run") as mock_run:
            # no cherry-pick in progress; upstream detection returns empty
            mock_run.side_effect = [
                MagicMock(returncode=1, stdout=""),  # rev-parse --git-dir (no CHERRY_PICK_HEAD)
                MagicMock(returncode=1, stdout=""),  # rev-parse upstream (no upstream)
                MagicMock(returncode=0, stdout="", stderr=""),  # cherry-pick
            ]
            with patch("os.path.exists", return_value=False):
                apply_cherry_pick("/wt", commits)
            # Third call should be the cherry-pick
            cherry_call = mock_run.call_args_list[2]
            assert cherry_call[0][0] == ["git", "cherry-pick", "abc1234", "def5678"]

    def test_raises_conflict_error_on_conflict_in_output(self):
        with patch("subprocess.run") as mock_run:
            # upstream detection fails (no upstream set)
            # cherry-pick exits 1 with conflict text — no abort call expected
            mock_run.side_effect = [
                MagicMock(returncode=1, stdout=""),  # rev-parse --git-dir (in-progress check)
                MagicMock(returncode=1, stdout=""),  # rev-parse upstream
                MagicMock(returncode=1, stdout="", stderr="CONFLICT (content)"),  # cherry-pick
            ]
            with patch("os.path.exists", return_value=False):
                with pytest.raises(CherryPickConflictError):
                    apply_cherry_pick("/wt", ["abc123"])

    def test_raises_cherry_pick_error_on_other_failure(self):
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=1, stdout=""),  # rev-parse --git-dir (in-progress check)
                MagicMock(returncode=1, stdout=""),  # rev-parse upstream
                MagicMock(returncode=1, stdout="", stderr="fatal: bad object"),  # cherry-pick
                MagicMock(returncode=0, stdout=""),  # cherry-pick --abort (non-conflict failure)
            ]
            with patch("os.path.exists", return_value=False):
                with pytest.raises(CherryPickError):
                    apply_cherry_pick("/wt", ["abc123"])

    def test_does_not_abort_on_conflict(self):
        """Cherry-pick --abort is NOT called when there are conflicts.

        The worktree must be left intact with conflict markers so the developer
        can inspect and resolve them.  Only non-conflict git failures trigger
        --abort.
        """
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=1, stdout=""),  # rev-parse --git-dir (in-progress check)
                MagicMock(returncode=1, stdout=""),  # rev-parse upstream
                MagicMock(returncode=1, stdout="CONFLICT found", stderr=""),  # cherry-pick
            ]
            with patch("os.path.exists", return_value=False):
                with pytest.raises(CherryPickConflictError):
                    apply_cherry_pick("/wt", ["abc123"])
            # Only 3 calls (git-dir check, upstream, cherry-pick) — no --abort
            assert mock_run.call_count == 3
            # Verify --abort was NOT called
            all_commands = [c[0][0] for c in mock_run.call_args_list]
            assert ["git", "cherry-pick", "--abort"] not in all_commands

    def test_aborts_on_non_conflict_failure(self):
        """Cherry-pick --abort IS called when the failure is not a conflict."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=1, stdout=""),  # rev-parse --git-dir (in-progress check)
                MagicMock(returncode=1, stdout=""),  # rev-parse upstream
                MagicMock(returncode=1, stdout="", stderr="fatal: bad object"),  # cherry-pick
                MagicMock(returncode=0, stdout=""),  # cherry-pick --abort
            ]
            with patch("os.path.exists", return_value=False):
                with pytest.raises(CherryPickError):
                    apply_cherry_pick("/wt", ["abc123"])
            # Verify --abort WAS called for non-conflict failure
            abort_call = mock_run.call_args_list[3]
            assert abort_call[0][0] == ["git", "cherry-pick", "--abort"]

    def test_skips_cherry_pick_when_new_commits_exist(self):
        """When the worktree already has commits ahead, cherry-pick is skipped."""
        with patch("subprocess.run") as mock_run:
            # upstream detection succeeds: origin/release/1.0
            mock_run.side_effect = [
                MagicMock(returncode=1, stdout=""),  # rev-parse --git-dir (in-progress check)
                MagicMock(returncode=0, stdout="origin/release/1.0\n"),  # rev-parse @{u}
                MagicMock(returncode=0, stdout="2\n"),  # rev-list --count (ahead)
            ]
            with patch("os.path.exists", return_value=False):
                apply_cherry_pick("/wt", ["abc123"])
            # 3 calls: git-dir check, upstream detection, rev-list count; no cherry-pick
            assert mock_run.call_count == 3

    def test_conflict_detected_via_patch_does_not_apply(self):
        """'patch does not apply' in stderr triggers conflict error without abort."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=1, stdout=""),  # rev-parse --git-dir (in-progress check)
                MagicMock(returncode=1, stdout=""),  # rev-parse upstream
                MagicMock(returncode=1, stdout="", stderr="error: patch does not apply"),
                # No abort expected for conflict failures
            ]
            with patch("os.path.exists", return_value=False):
                with pytest.raises(CherryPickConflictError):
                    apply_cherry_pick("/wt", ["abc123"])

    def test_raises_conflict_error_when_cherry_pick_in_progress(self):
        """When CHERRY_PICK_HEAD exists, raises CherryPickConflictError immediately."""
        with patch("subprocess.run") as mock_run:
            # rev-parse --git-dir succeeds; CHERRY_PICK_HEAD found
            mock_run.return_value = MagicMock(returncode=0, stdout="/wt/.git\n")
            with patch("os.path.exists", return_value=True):
                with pytest.raises(CherryPickConflictError, match="already in progress"):
                    apply_cherry_pick("/wt", ["abc123"])
            # Only 1 call: git-dir check; no cherry-pick attempted
            assert mock_run.call_count == 1


# ---------------------------------------------------------------------------
# push_branch
# ---------------------------------------------------------------------------


class TestPushBranch:
    def test_calls_git_push_with_correct_args(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            push_branch("/wt", "TASK-455.4")
            mock_run.assert_called_once_with(
                ["git", "push", "-u", "--force-with-lease", "origin", "TASK-455.4"],
                cwd="/wt",
                capture_output=True,
                text=True,
                check=True,
                timeout=120,
            )

    def test_raises_on_push_failure(self):
        with patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "git push"),
        ):
            with pytest.raises(subprocess.CalledProcessError):
                push_branch("/wt", "TASK-455_4")


# ---------------------------------------------------------------------------
# open_backport_pr
# ---------------------------------------------------------------------------


class TestOpenBackportPr:
    def test_returns_pr_url_on_success(self):
        source = _issue("TASK-10", "Fix a bug")
        child = _issue("TASK-10.1")
        entry = BackportEntry(branch="release/1.0", commits=["abc"])
        scm = MagicMock()
        scm.create_review.return_value = _make_review(
            id="99", url="https://github.com/org/repo/pull/99"
        )

        url = open_backport_pr(scm, "org/repo", source, child, entry)

        assert url == "https://github.com/org/repo/pull/99"

    def test_calls_create_review_with_correct_args(self):
        source = _issue("TASK-10", "Fix a bug")
        child = _issue("TASK-10.1")
        entry = BackportEntry(branch="release/2.0", commits=["abc"])
        scm = MagicMock()
        scm.create_review.return_value = _make_review()

        open_backport_pr(scm, "org/repo", source, child, entry)

        scm.create_review.assert_called_once()
        kwargs = scm.create_review.call_args
        # Positional: repo, title, source_branch; kw: target_branch, description
        assert kwargs.args[0] == "org/repo"
        assert "TASK-10.1" in kwargs.args[1]  # title contains child identifier
        assert kwargs.args[2] == "TASK-10.1"  # sanitized branch name (dot is allowed)
        assert kwargs.kwargs["target_branch"] == "release/2.0"

    def test_returns_none_when_scm_raises(self):
        source = _issue("TASK-10", "Fix a bug")
        child = _issue("TASK-10.1")
        entry = BackportEntry(branch="release/1.0", commits=["abc"])
        scm = MagicMock()
        scm.create_review.side_effect = RuntimeError("network error")

        url = open_backport_pr(scm, "org/repo", source, child, entry)

        assert url is None

    def test_returns_none_when_scm_returns_none(self):
        source = _issue("TASK-10", "Fix a bug")
        child = _issue("TASK-10.1")
        entry = BackportEntry(branch="release/1.0", commits=["abc"])
        scm = MagicMock()
        scm.create_review.return_value = None

        url = open_backport_pr(scm, "org/repo", source, child, entry)

        assert url is None

    def test_pr_title_includes_source_title_and_target_branch(self):
        source = _issue("TASK-10", "My important fix")
        child = _issue("TASK-10.1")
        entry = BackportEntry(branch="release/3.0", commits=["abc"])
        scm = MagicMock()
        scm.create_review.return_value = _make_review()

        open_backport_pr(scm, "org/repo", source, child, entry)

        title_arg = scm.create_review.call_args.args[1]
        assert "My important fix" in title_arg
        assert "release/3.0" in title_arg


# ---------------------------------------------------------------------------
# _write_child_backport_of
# ---------------------------------------------------------------------------


class TestWriteChildBackportOf:
    def test_writes_source_and_status(self):
        tracker = MagicMock()
        _write_child_backport_of(
            tracker, "TASK-10.1", "TASK-10", ReleasePick.PR_OPEN
        )
        tracker.set_metadata_field.assert_called_once_with(
            "TASK-10.1",
            "oompah.backport_of",
            {"source": "TASK-10", "status": "pr_open"},
        )

    def test_includes_pr_url_when_provided(self):
        tracker = MagicMock()
        _write_child_backport_of(
            tracker,
            "TASK-10.1",
            "TASK-10",
            ReleasePick.PR_OPEN,
            pr_url="https://example.com/pulls/1",
        )
        call_args = tracker.set_metadata_field.call_args
        assert call_args.args[2]["pr_url"] == "https://example.com/pulls/1"

    def test_no_pr_url_key_when_not_provided(self):
        tracker = MagicMock()
        _write_child_backport_of(
            tracker, "TASK-10.1", "TASK-10", ReleasePick.CONFLICT
        )
        call_args = tracker.set_metadata_field.call_args
        assert "pr_url" not in call_args.args[2]

    def test_swallows_tracker_exception(self):
        tracker = MagicMock()
        tracker.set_metadata_field.side_effect = RuntimeError("disk full")
        # Should not raise
        _write_child_backport_of(
            tracker, "TASK-10.1", "TASK-10", ReleasePick.PR_OPEN
        )


# ---------------------------------------------------------------------------
# cherry_pick_push_and_open_pr — success path
# ---------------------------------------------------------------------------


class TestCherryPickPushAndOpenPr:
    def _make_deps(self):
        tracker = MagicMock()
        project_store = MagicMock()
        project_store.worktree_path_for.return_value = "/wt/TASK-10_1"
        scm = MagicMock()
        scm.create_review.return_value = _make_review(
            id="55", url="https://github.com/org/repo/pull/55"
        )
        return tracker, project_store, scm

    def test_success_returns_pr_open_entry(self):
        source = _issue("TASK-10", "My feature")
        child = _issue("TASK-10.1")
        entry = BackportEntry(
            branch="release/1.0",
            status=ReleasePick.TASK_CREATED,
            task_id="TASK-10.1",
            commits=["abc123"],
        )
        tracker, project_store, scm = self._make_deps()

        with (
            patch("oompah.cherry_pick_pr_creator.apply_cherry_pick") as mock_cp,
            patch("oompah.cherry_pick_pr_creator.push_branch") as mock_push,
        ):
            result = cherry_pick_push_and_open_pr(
                tracker, source, entry, child,
                project_store=project_store,
                project_id="proj-1",
                scm=scm,
                repo="org/repo",
            )

        assert result.status == ReleasePick.PR_OPEN
        assert result.pr_url == "https://github.com/org/repo/pull/55"
        assert result.commits == ["abc123"]
        mock_cp.assert_called_once_with("/wt/TASK-10_1", ["abc123"])
        mock_push.assert_called_once_with("/wt/TASK-10_1", "TASK-10.1")

    def test_marks_child_in_review(self):
        source = _issue("TASK-10", "My feature")
        child = _issue("TASK-10.1")
        entry = BackportEntry(
            branch="release/1.0",
            status=ReleasePick.TASK_CREATED,
            task_id="TASK-10.1",
            commits=["abc123"],
        )
        tracker, project_store, scm = self._make_deps()

        with (
            patch("oompah.cherry_pick_pr_creator.apply_cherry_pick"),
            patch("oompah.cherry_pick_pr_creator.push_branch"),
        ):
            cherry_pick_push_and_open_pr(
                tracker, source, entry, child,
                project_store=project_store,
                project_id="proj-1",
                scm=scm,
                repo="org/repo",
            )

        tracker.update_issue.assert_called_once_with("TASK-10.1", status=IN_REVIEW)

    def test_writes_pr_url_to_child_metadata(self):
        source = _issue("TASK-10", "My feature")
        child = _issue("TASK-10.1")
        entry = BackportEntry(
            branch="release/1.0",
            status=ReleasePick.TASK_CREATED,
            task_id="TASK-10.1",
            commits=["abc123"],
        )
        tracker, project_store, scm = self._make_deps()

        with (
            patch("oompah.cherry_pick_pr_creator.apply_cherry_pick"),
            patch("oompah.cherry_pick_pr_creator.push_branch"),
        ):
            cherry_pick_push_and_open_pr(
                tracker, source, entry, child,
                project_store=project_store,
                project_id="proj-1",
                scm=scm,
                repo="org/repo",
            )

        meta_calls = [
            c for c in tracker.set_metadata_field.call_args_list
            if c.args[1] == "oompah.backport_of"
        ]
        assert len(meta_calls) == 1
        written = meta_calls[0].args[2]
        assert written["pr_url"] == "https://github.com/org/repo/pull/55"
        assert written["status"] == ReleasePick.PR_OPEN.value

    def test_returns_conflict_status_on_conflict(self):
        source = _issue("TASK-10", "My feature")
        child = _issue("TASK-10.1")
        entry = BackportEntry(
            branch="release/1.0",
            status=ReleasePick.TASK_CREATED,
            task_id="TASK-10.1",
            commits=["abc123"],
        )
        tracker, project_store, scm = self._make_deps()

        with patch(
            "oompah.cherry_pick_pr_creator.apply_cherry_pick",
            side_effect=CherryPickConflictError("conflict!"),
        ):
            result = cherry_pick_push_and_open_pr(
                tracker, source, entry, child,
                project_store=project_store,
                project_id="proj-1",
                scm=scm,
                repo="org/repo",
            )

        assert result.status == ReleasePick.CONFLICT
        assert result.commits == ["abc123"]

    def test_writes_conflict_metadata_to_child_on_conflict(self):
        source = _issue("TASK-10", "My feature")
        child = _issue("TASK-10.1")
        entry = BackportEntry(
            branch="release/1.0",
            status=ReleasePick.TASK_CREATED,
            task_id="TASK-10.1",
            commits=["abc123"],
        )
        tracker, project_store, scm = self._make_deps()

        with patch(
            "oompah.cherry_pick_pr_creator.apply_cherry_pick",
            side_effect=CherryPickConflictError("conflict!"),
        ):
            cherry_pick_push_and_open_pr(
                tracker, source, entry, child,
                project_store=project_store,
                project_id="proj-1",
                scm=scm,
                repo="org/repo",
            )

        meta_calls = [
            c for c in tracker.set_metadata_field.call_args_list
            if c.args[1] == "oompah.backport_of"
        ]
        assert len(meta_calls) == 1
        assert meta_calls[0].args[2]["status"] == ReleasePick.CONFLICT.value

    def test_marks_child_needs_rebase_on_conflict(self):
        """On conflict, the child task status is set to Needs Rebase."""
        source = _issue("TASK-10", "My feature")
        child = _issue("TASK-10.1")
        entry = BackportEntry(
            branch="release/1.0",
            status=ReleasePick.TASK_CREATED,
            task_id="TASK-10.1",
            commits=["abc123"],
        )
        tracker, project_store, scm = self._make_deps()

        with patch(
            "oompah.cherry_pick_pr_creator.apply_cherry_pick",
            side_effect=CherryPickConflictError("CONFLICT in foo.py"),
        ):
            cherry_pick_push_and_open_pr(
                tracker, source, entry, child,
                project_store=project_store,
                project_id="proj-1",
                scm=scm,
                repo="org/repo",
            )

        tracker.update_issue.assert_called_once_with(
            "TASK-10.1", status=NEEDS_REBASE
        )

    def test_adds_diagnostic_comment_on_conflict(self):
        """On conflict, a diagnostic comment is added to the child task."""
        source = _issue("TASK-10", "My feature")
        child = _issue("TASK-10.1")
        entry = BackportEntry(
            branch="release/1.0",
            status=ReleasePick.TASK_CREATED,
            task_id="TASK-10.1",
            commits=["abc123", "def456"],
        )
        tracker, project_store, scm = self._make_deps()

        with patch(
            "oompah.cherry_pick_pr_creator.apply_cherry_pick",
            side_effect=CherryPickConflictError("CONFLICT in src/foo.py"),
        ):
            cherry_pick_push_and_open_pr(
                tracker, source, entry, child,
                project_store=project_store,
                project_id="proj-1",
                scm=scm,
                repo="org/repo",
            )

        tracker.add_comment.assert_called_once()
        comment_args = tracker.add_comment.call_args
        assert comment_args.args[0] == "TASK-10.1"
        comment_text = comment_args.args[1]
        # Comment should mention the commits and branch
        assert "abc123" in comment_text
        assert "release/1.0" in comment_text
        # Comment should mention worktree path
        assert "/wt/TASK-10_1" in comment_text
        # Comment should include the conflict details
        assert "CONFLICT in src/foo.py" in comment_text

    def test_needs_rebase_failure_is_non_fatal_on_conflict(self):
        """A tracker failure when marking Needs Rebase is non-fatal."""
        source = _issue("TASK-10", "My feature")
        child = _issue("TASK-10.1")
        entry = BackportEntry(
            branch="release/1.0",
            status=ReleasePick.TASK_CREATED,
            task_id="TASK-10.1",
            commits=["abc123"],
        )
        tracker, project_store, scm = self._make_deps()
        tracker.update_issue.side_effect = RuntimeError("tracker down")

        with patch(
            "oompah.cherry_pick_pr_creator.apply_cherry_pick",
            side_effect=CherryPickConflictError("conflict!"),
        ):
            # Should not raise
            result = cherry_pick_push_and_open_pr(
                tracker, source, entry, child,
                project_store=project_store,
                project_id="proj-1",
                scm=scm,
                repo="org/repo",
            )

        assert result.status == ReleasePick.CONFLICT

    def test_diagnostic_comment_failure_is_non_fatal_on_conflict(self):
        """A failure adding the diagnostic comment is non-fatal."""
        source = _issue("TASK-10", "My feature")
        child = _issue("TASK-10.1")
        entry = BackportEntry(
            branch="release/1.0",
            status=ReleasePick.TASK_CREATED,
            task_id="TASK-10.1",
            commits=["abc123"],
        )
        tracker, project_store, scm = self._make_deps()
        tracker.add_comment.side_effect = RuntimeError("tracker down")

        with patch(
            "oompah.cherry_pick_pr_creator.apply_cherry_pick",
            side_effect=CherryPickConflictError("conflict!"),
        ):
            # Should not raise even when add_comment fails
            result = cherry_pick_push_and_open_pr(
                tracker, source, entry, child,
                project_store=project_store,
                project_id="proj-1",
                scm=scm,
                repo="org/repo",
            )

        assert result.status == ReleasePick.CONFLICT

    def test_propagates_cherry_pick_error(self):
        source = _issue("TASK-10", "My feature")
        child = _issue("TASK-10.1")
        entry = BackportEntry(
            branch="release/1.0",
            status=ReleasePick.TASK_CREATED,
            task_id="TASK-10.1",
            commits=["abc123"],
        )
        tracker, project_store, scm = self._make_deps()

        with patch(
            "oompah.cherry_pick_pr_creator.apply_cherry_pick",
            side_effect=CherryPickError("bad object"),
        ):
            with pytest.raises(CherryPickError):
                cherry_pick_push_and_open_pr(
                    tracker, source, entry, child,
                    project_store=project_store,
                    project_id="proj-1",
                    scm=scm,
                    repo="org/repo",
                )

    def test_propagates_push_error(self):
        source = _issue("TASK-10", "My feature")
        child = _issue("TASK-10.1")
        entry = BackportEntry(
            branch="release/1.0",
            status=ReleasePick.TASK_CREATED,
            task_id="TASK-10.1",
            commits=["abc123"],
        )
        tracker, project_store, scm = self._make_deps()

        with (
            patch("oompah.cherry_pick_pr_creator.apply_cherry_pick"),
            patch(
                "oompah.cherry_pick_pr_creator.push_branch",
                side_effect=subprocess.CalledProcessError(1, "git push"),
            ),
        ):
            with pytest.raises(subprocess.CalledProcessError):
                cherry_pick_push_and_open_pr(
                    tracker, source, entry, child,
                    project_store=project_store,
                    project_id="proj-1",
                    scm=scm,
                    repo="org/repo",
                )

    def test_cherry_picking_status_when_pr_url_is_none(self):
        """When SCM returns no URL, status is cherry_picking (not pr_open)."""
        source = _issue("TASK-10", "My feature")
        child = _issue("TASK-10.1")
        entry = BackportEntry(
            branch="release/1.0",
            status=ReleasePick.TASK_CREATED,
            task_id="TASK-10.1",
            commits=["abc123"],
        )
        tracker, project_store, scm = self._make_deps()
        scm.create_review.return_value = None  # SCM fails

        with (
            patch("oompah.cherry_pick_pr_creator.apply_cherry_pick"),
            patch("oompah.cherry_pick_pr_creator.push_branch"),
        ):
            result = cherry_pick_push_and_open_pr(
                tracker, source, entry, child,
                project_store=project_store,
                project_id="proj-1",
                scm=scm,
                repo="org/repo",
            )

        assert result.status == ReleasePick.CHERRY_PICKING
        assert result.pr_url is None

    def test_in_review_failure_does_not_raise(self):
        """A tracker failure when marking In Review is non-fatal."""
        source = _issue("TASK-10", "My feature")
        child = _issue("TASK-10.1")
        entry = BackportEntry(
            branch="release/1.0",
            status=ReleasePick.TASK_CREATED,
            task_id="TASK-10.1",
            commits=["abc123"],
        )
        tracker, project_store, scm = self._make_deps()
        tracker.update_issue.side_effect = RuntimeError("tracker down")

        with (
            patch("oompah.cherry_pick_pr_creator.apply_cherry_pick"),
            patch("oompah.cherry_pick_pr_creator.push_branch"),
        ):
            # Should not raise — update_issue failure is swallowed
            result = cherry_pick_push_and_open_pr(
                tracker, source, entry, child,
                project_store=project_store,
                project_id="proj-1",
                scm=scm,
                repo="org/repo",
            )

        assert result.status == ReleasePick.PR_OPEN

    def test_uses_worktree_path_from_project_store(self):
        """worktree_path_for is called with the correct project_id and child identifier."""
        source = _issue("TASK-10", "My feature")
        child = _issue("TASK-10.1")
        entry = BackportEntry(
            branch="release/1.0",
            status=ReleasePick.TASK_CREATED,
            task_id="TASK-10.1",
            commits=["abc123"],
        )
        tracker, project_store, scm = self._make_deps()

        with (
            patch("oompah.cherry_pick_pr_creator.apply_cherry_pick"),
            patch("oompah.cherry_pick_pr_creator.push_branch"),
        ):
            cherry_pick_push_and_open_pr(
                tracker, source, entry, child,
                project_store=project_store,
                project_id="my-proj",
                scm=scm,
                repo="org/repo",
            )

        project_store.worktree_path_for.assert_called_once_with("my-proj", "TASK-10.1")


# ---------------------------------------------------------------------------
# reconciler integration: task_created entries call cherry-pick+PR step
# ---------------------------------------------------------------------------


class TestReconcilerCherryPickIntegration:
    """Verify the reconciler correctly wires task_created → pr_open via cherry-pick."""

    def _issue(self, identifier, title="T", state="Open", target_branch=None):
        return Issue(
            id=identifier,
            identifier=identifier,
            title=title,
            description="",
            state=state,
            target_branch=target_branch,
            labels=[],
            project_id="proj-1",
        )

    def _make_tracker(self, all_issues, metadata_map):
        tracker = MagicMock()
        tracker.fetch_all_issues.return_value = list(all_issues)
        tracker.fetch_issue_detail.return_value = None
        meta = dict(metadata_map)
        tracker.get_metadata.side_effect = lambda id: meta.get(id, {})
        return tracker

    def test_advances_task_created_to_pr_open(self):
        from oompah.release_pick_reconciler import reconcile_release_picks
        from oompah.release_pick_schema import backports_to_raw

        source = self._issue("TASK-1", "My fix")
        child = self._issue("TASK-1.1", target_branch="release/1.0")
        entries_raw = backports_to_raw([
            BackportEntry(
                branch="release/1.0",
                status=ReleasePick.TASK_CREATED,
                task_id="TASK-1.1",
                commits=["abc123"],
            )
        ])
        tracker = self._make_tracker(
            all_issues=[source, child],
            metadata_map={
                "TASK-1": {"oompah.backports": entries_raw},
                "TASK-1.1": {
                    "oompah.backport_of": {"source": "TASK-1", "status": "task_created"}
                },
            },
        )

        project_store = MagicMock()
        project_store.worktree_path_for.return_value = "/wt/TASK-1_1"
        scm = MagicMock()
        scm.create_review.return_value = _make_review(
            id="7", url="https://github.com/org/repo/pull/7"
        )

        with (
            patch("oompah.cherry_pick_pr_creator.apply_cherry_pick"),
            patch("oompah.cherry_pick_pr_creator.push_branch"),
        ):
            result = reconcile_release_picks(
                tracker,
                project_store=project_store,
                project_id="proj-1",
                scm=scm,
                repo="org/repo",
            )

        assert result.advanced == 1
        assert result.errors == 0

        # Backports written back with pr_open
        from oompah.release_pick_schema import parse_backports
        source_calls = [
            c for c in tracker.set_metadata_field.call_args_list
            if c.args[0] == "TASK-1" and c.args[1] == "oompah.backports"
        ]
        assert len(source_calls) == 1
        written = parse_backports(source_calls[0].args[2])
        assert written[0].status == ReleasePick.PR_OPEN
        assert written[0].pr_url == "https://github.com/org/repo/pull/7"

    def test_skips_task_created_without_commits(self):
        """task_created entries without commits are not advanced."""
        from oompah.release_pick_reconciler import reconcile_release_picks
        from oompah.release_pick_schema import backports_to_raw

        source = self._issue("TASK-1", "My fix")
        child = self._issue("TASK-1.1", target_branch="release/1.0")
        entries_raw = backports_to_raw([
            BackportEntry(
                branch="release/1.0",
                status=ReleasePick.TASK_CREATED,
                task_id="TASK-1.1",
                commits=[],  # no commits
            )
        ])
        tracker = self._make_tracker(
            all_issues=[source, child],
            metadata_map={
                "TASK-1": {"oompah.backports": entries_raw},
                "TASK-1.1": {"oompah.backport_of": "TASK-1"},
            },
        )

        result = reconcile_release_picks(
            tracker,
            project_store=MagicMock(),
            project_id="proj-1",
            scm=MagicMock(),
            repo="org/repo",
        )

        assert result.advanced == 0

    def test_skips_task_created_without_scm(self):
        """Without an SCM provider, task_created entries are not advanced."""
        from oompah.release_pick_reconciler import reconcile_release_picks
        from oompah.release_pick_schema import backports_to_raw

        source = self._issue("TASK-1", "My fix")
        child = self._issue("TASK-1.1", target_branch="release/1.0")
        entries_raw = backports_to_raw([
            BackportEntry(
                branch="release/1.0",
                status=ReleasePick.TASK_CREATED,
                task_id="TASK-1.1",
                commits=["abc123"],
            )
])
        tracker = self._make_tracker(
            all_issues=[source, child],
            metadata_map={
                "TASK-1": {"oompah.backports": entries_raw},
                "TASK-1.1": {"oompah.backport_of": "TASK-1"},
            },
        )

        result = reconcile_release_picks(
            tracker,
            project_store=MagicMock(),
            project_id="proj-1",
            scm=None,  # no SCM
            repo="org/repo",
        )

        assert result.advanced == 0

    def test_conflict_from_cherry_pick_is_recorded(self):
        """A cherry-pick conflict advances the entry to conflict status."""
        from oompah.release_pick_reconciler import reconcile_release_picks
        from oompah.release_pick_schema import backports_to_raw, parse_backports

        source = self._issue("TASK-1", "My fix")
        child = self._issue("TASK-1.1", target_branch="release/1.0")
        entries_raw = backports_to_raw([
            BackportEntry(
                branch="release/1.0",
                status=ReleasePick.TASK_CREATED,
                task_id="TASK-1.1",
                commits=["abc123"],
            )
        ])
        tracker = self._make_tracker(
            all_issues=[source, child],
            metadata_map={
                "TASK-1": {"oompah.backports": entries_raw},
                "TASK-1.1": {"oompah.backport_of": "TASK-1"},
            },
        )

        project_store = MagicMock()
        project_store.worktree_path_for.return_value = "/wt/TASK-1_1"

        with patch(
            "oompah.cherry_pick_pr_creator.apply_cherry_pick",
            side_effect=CherryPickConflictError("conflict!"),
        ):
            result = reconcile_release_picks(
                tracker,
                project_store=project_store,
                project_id="proj-1",
                scm=MagicMock(),
                repo="org/repo",
            )

        assert result.advanced == 1
        source_calls = [
            c for c in tracker.set_metadata_field.call_args_list
            if c.args[0] == "TASK-1" and c.args[1] == "oompah.backports"
        ]
        assert source_calls
        written = parse_backports(source_calls[0].args[2])
        assert written[0].status == ReleasePick.CONFLICT

    def test_cherry_pick_error_increments_errors(self):
        """A non-conflict cherry-pick failure increments the error count."""
        from oompah.release_pick_reconciler import reconcile_release_picks
        from oompah.release_pick_schema import backports_to_raw

        source = self._issue("TASK-1", "My fix")
        child = self._issue("TASK-1.1", target_branch="release/1.0")
        entries_raw = backports_to_raw([
            BackportEntry(
                branch="release/1.0",
                status=ReleasePick.TASK_CREATED,
                task_id="TASK-1.1",
                commits=["abc123"],
            )
        ])
        tracker = self._make_tracker(
            all_issues=[source, child],
            metadata_map={
                "TASK-1": {"oompah.backports": entries_raw},
                "TASK-1.1": {"oompah.backport_of": "TASK-1"},
            },
        )

        project_store = MagicMock()
        project_store.worktree_path_for.return_value = "/wt/TASK-1_1"

        with patch(
            "oompah.cherry_pick_pr_creator.apply_cherry_pick",
            side_effect=CherryPickError("bad object"),
        ):
            result = reconcile_release_picks(
                tracker,
                project_store=project_store,
                project_id="proj-1",
                scm=MagicMock(),
                repo="org/repo",
            )

        assert result.errors >= 1
