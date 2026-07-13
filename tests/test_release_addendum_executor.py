"""Tests for :mod:`oompah.release_addendum_executor`.

Covers:
- Correct target base and commit order (worktree created with correct args).
- Existing worktree/PR reuse (idempotent re-run).
- Successful state/evidence updates (in_review, pr_url, result_commits).
- Conflict preservation (blocked + worktree left intact).
- Non-conflict failure (blocked, no worktree preservation assumed).
- Proof no tracker task is created or source task status altered.
"""

from __future__ import annotations

import subprocess
import threading
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest

from oompah.release_addendum_executor import (
    _find_existing_pr,
    _get_result_commits,
    _open_release_pr,
    _persist_blocked,
    _post_source_comment,
    cherry_pick_addendum,
)
from oompah.cherry_pick_pr_creator import CherryPickConflictError, CherryPickError
from oompah.release_addendum_schema import (
    AddendumRepository,
    AddendumStatus,
    ReleaseAddendum,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

NOW = datetime(2026, 7, 13, tzinfo=timezone.utc)

_COMMIT_A = "a" * 40
_COMMIT_B = "b" * 40


def _addendum(
    status: AddendumStatus = AddendumStatus.IN_PROGRESS,
    *,
    target: str = "release/1.0",
    commits: list[str] | None = None,
    pr_url: str | None = None,
    work_branch: str = "oompah/release/FOO-10/release-1.0",
    worktree_key: str = "release-FOO-10-release-1.0",
    addendum_id: str | None = None,
) -> ReleaseAddendum:
    if commits is None:
        commits = [_COMMIT_A, _COMMIT_B]
    aid = addendum_id or f"FOO-10/{target}"
    return ReleaseAddendum(
        id=aid,
        source_branch="main",
        target_branch=target,
        status=status,
        commits=commits,
        work_branch=work_branch,
        worktree_key=worktree_key,
        queued_at=NOW.isoformat(),
        pr_url=pr_url,
        claimed_by="worker-1",
        lease_expires_at=(NOW.isoformat()),
    )


class _Tracker:
    """Minimal in-memory tracker for executor tests."""

    def __init__(self, addendums: list[ReleaseAddendum]) -> None:
        self._lock = threading.Lock()
        self._metadata: dict[str, object] = {
            "oompah.release_addendums": [a.to_raw() for a in addendums]
        }
        self.comments: list[dict] = []
        self.writes: int = 0
        # Track whether create_issue was ever called (it must not be).
        self.create_issue_calls: int = 0
        # Track whether update_issue was ever called on source (it must not be).
        self.update_issue_calls: int = 0

    def get_metadata(self, _identifier: str) -> dict:
        with self._lock:
            meta = {}
            for k, v in self._metadata.items():
                meta[k] = list(v) if isinstance(v, list) else v
            return meta

    def set_metadata_field(self, _identifier: str, key: str, value: object) -> None:
        with self._lock:
            self._metadata[key] = value
            self.writes += 1

    def add_comment(self, identifier: str, message: str, *, author: str) -> None:
        self.comments.append({"identifier": identifier, "message": message, "author": author})

    def create_issue(self, **_kwargs) -> object:
        self.create_issue_calls += 1
        return SimpleNamespace(identifier="SHOULD-NOT-EXIST")

    def update_issue(self, identifier: str, **_kwargs) -> None:
        self.update_issue_calls += 1


def _project_store(wt_path: str = "/wt/release-FOO-10-release-1.0") -> MagicMock:
    ps = MagicMock()
    ps.create_worktree.return_value = wt_path
    ps.worktree_path_for.return_value = wt_path
    return ps


def _make_pr(
    id: str = "99",
    url: str = "https://github.com/org/repo/pull/99",
    state: str = "open",
) -> MagicMock:
    pr = MagicMock()
    pr.id = id
    pr.url = url
    pr.state = state
    return pr


def _scm(
    existing_pr: MagicMock | None = None,
    new_pr: MagicMock | None = None,
) -> MagicMock:
    scm = MagicMock()
    scm.find_pr_for_branch.return_value = existing_pr
    scm.create_review.return_value = new_pr or _make_pr()
    return scm


# ---------------------------------------------------------------------------
# _get_result_commits
# ---------------------------------------------------------------------------


class TestGetResultCommits:
    def test_returns_commits_ahead_of_target(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=f"{_COMMIT_A}\n{_COMMIT_B}\n",
            )
            result = _get_result_commits("/wt", "release/1.0")
        assert result == [_COMMIT_A, _COMMIT_B]
        cmd = mock_run.call_args[0][0]
        assert "^origin/release/1.0" in cmd

    def test_returns_empty_on_failure(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="")
            result = _get_result_commits("/wt", "release/1.0")
        assert result == []

    def test_returns_empty_on_exception(self):
        with patch("subprocess.run", side_effect=OSError("no git")):
            result = _get_result_commits("/wt", "release/1.0")
        assert result == []

    def test_strips_whitespace_and_empty_lines(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=f"  {_COMMIT_A}  \n\n{_COMMIT_B}\n",
            )
            result = _get_result_commits("/wt", "release/1.0")
        assert result == [_COMMIT_A, _COMMIT_B]

    def test_oldest_commit_first(self):
        """rev-list --reverse returns oldest first; we preserve that order."""
        sha1 = "1" * 40
        sha2 = "2" * 40
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=f"{sha1}\n{sha2}\n",
            )
            result = _get_result_commits("/wt", "release/1.0")
        assert result == [sha1, sha2]


# ---------------------------------------------------------------------------
# _find_existing_pr
# ---------------------------------------------------------------------------


class TestFindExistingPr:
    def test_returns_open_pr(self):
        pr = _make_pr(state="open")
        scm = _scm(existing_pr=pr)
        result = _find_existing_pr(scm, "org/repo", "oompah/release/FOO-10/release-1.0")
        assert result is pr

    def test_returns_none_for_closed_pr(self):
        pr = _make_pr(state="closed")
        scm = _scm(existing_pr=pr)
        result = _find_existing_pr(scm, "org/repo", "oompah/release/FOO-10/release-1.0")
        assert result is None

    def test_returns_none_for_merged_pr(self):
        pr = _make_pr(state="merged")
        scm = _scm(existing_pr=pr)
        result = _find_existing_pr(scm, "org/repo", "oompah/release/FOO-10/release-1.0")
        assert result is None

    def test_returns_none_when_no_pr(self):
        scm = _scm(existing_pr=None)
        result = _find_existing_pr(scm, "org/repo", "oompah/release/FOO-10/release-1.0")
        assert result is None

    def test_returns_none_on_scm_exception(self):
        scm = MagicMock()
        scm.find_pr_for_branch.side_effect = RuntimeError("network error")
        result = _find_existing_pr(scm, "org/repo", "work-branch")
        assert result is None

    def test_passes_work_branch_to_scm(self):
        scm = _scm(existing_pr=None)
        _find_existing_pr(scm, "org/repo", "oompah/release/FOO-10/release-1.0")
        scm.find_pr_for_branch.assert_called_once_with(
            "org/repo", "oompah/release/FOO-10/release-1.0"
        )


# ---------------------------------------------------------------------------
# _open_release_pr
# ---------------------------------------------------------------------------


class TestOpenReleasePr:
    def test_returns_pr_url_on_success(self):
        addendum = _addendum()
        scm = MagicMock()
        scm.create_review.return_value = _make_pr(url="https://github.com/pr/1")
        url = _open_release_pr(scm, "org/repo", "FOO-10", "My feature", addendum)
        assert url == "https://github.com/pr/1"

    def test_targets_target_branch(self):
        addendum = _addendum(target="release/2.0")
        scm = MagicMock()
        scm.create_review.return_value = _make_pr()
        _open_release_pr(scm, "org/repo", "FOO-10", "My feature", addendum)
        kwargs = scm.create_review.call_args.kwargs
        assert kwargs.get("target_branch") == "release/2.0"

    def test_uses_work_branch_as_source(self):
        addendum = _addendum()
        scm = MagicMock()
        scm.create_review.return_value = _make_pr()
        _open_release_pr(scm, "org/repo", "FOO-10", "My feature", addendum)
        pos_args = scm.create_review.call_args.args
        # source_branch is positional arg 3 (after repo, title)
        assert pos_args[2] == addendum.work_branch

    def test_includes_source_title_in_pr_title(self):
        addendum = _addendum()
        scm = MagicMock()
        scm.create_review.return_value = _make_pr()
        _open_release_pr(scm, "org/repo", "FOO-10", "My important fix", addendum)
        title = scm.create_review.call_args.args[1]
        assert "My important fix" in title

    def test_includes_target_branch_in_pr_title(self):
        addendum = _addendum(target="release/3.0")
        scm = MagicMock()
        scm.create_review.return_value = _make_pr()
        _open_release_pr(scm, "org/repo", "FOO-10", "Fix", addendum)
        title = scm.create_review.call_args.args[1]
        assert "release/3.0" in title

    def test_returns_none_on_exception(self):
        addendum = _addendum()
        scm = MagicMock()
        scm.create_review.side_effect = RuntimeError("network error")
        result = _open_release_pr(scm, "org/repo", "FOO-10", "Fix", addendum)
        assert result is None

    def test_returns_none_when_scm_returns_none(self):
        addendum = _addendum()
        scm = MagicMock()
        scm.create_review.return_value = None
        result = _open_release_pr(scm, "org/repo", "FOO-10", "Fix", addendum)
        assert result is None

    def test_description_includes_commit_shas(self):
        addendum = _addendum(commits=[_COMMIT_A, _COMMIT_B])
        scm = MagicMock()
        scm.create_review.return_value = _make_pr()
        _open_release_pr(scm, "org/repo", "FOO-10", "Fix", addendum)
        desc = scm.create_review.call_args.kwargs.get("description", "")
        assert _COMMIT_A in desc
        assert _COMMIT_B in desc


# ---------------------------------------------------------------------------
# _persist_blocked
# ---------------------------------------------------------------------------


class TestPersistBlocked:
    def test_transitions_to_blocked_with_error(self):
        addendum = _addendum()
        tracker = _Tracker([addendum])
        result = _persist_blocked(tracker, "FOO-10", addendum, error="something broke")
        assert result.status is AddendumStatus.BLOCKED
        assert result.error == "something broke"

    def test_returns_original_on_transition_failure(self):
        addendum = _addendum()
        tracker = MagicMock()
        tracker.get_metadata.side_effect = RuntimeError("tracker down")
        # Should not raise — returns the original addendum
        result = _persist_blocked(tracker, "FOO-10", addendum, error="boom")
        assert result is addendum


# ---------------------------------------------------------------------------
# _post_source_comment
# ---------------------------------------------------------------------------


class TestPostSourceComment:
    def test_posts_comment_with_oompah_author(self):
        tracker = MagicMock()
        _post_source_comment(tracker, "FOO-10", "hello")
        tracker.add_comment.assert_called_once_with("FOO-10", "hello", author="oompah")

    def test_swallows_exception(self):
        tracker = MagicMock()
        tracker.add_comment.side_effect = RuntimeError("disk full")
        # Should not raise
        _post_source_comment(tracker, "FOO-10", "hello")


# ---------------------------------------------------------------------------
# cherry_pick_addendum — worktree creation
# ---------------------------------------------------------------------------


class TestCherryPickAddendumWorktree:
    def test_creates_worktree_with_correct_base_branch(self):
        """Worktree is rooted at origin/<target_branch>."""
        addendum = _addendum(target="release/1.0")
        tracker = _Tracker([addendum])
        ps = _project_store()
        scm = _scm()

        with (
            patch("oompah.release_addendum_executor._has_new_commits", return_value=False),
            patch("oompah.release_addendum_executor.apply_cherry_pick"),
            patch("oompah.release_addendum_executor.push_branch"),
            patch("oompah.release_addendum_executor._get_result_commits", return_value=[_COMMIT_A]),
        ):
            cherry_pick_addendum(
                tracker,
                "FOO-10",
                addendum,
                project_store=ps,
                project_id="proj-1",
                scm=scm,
                repo="org/repo",
            )

        ps.create_worktree.assert_called_once_with(
            "proj-1",
            addendum.worktree_key,
            base_branch=addendum.target_branch,
            branch_name=addendum.work_branch,
        )

    def test_uses_worktree_key_as_path_key(self):
        """worktree_key (not source identifier) is used as the path key."""
        addendum = _addendum(worktree_key="release-FOO-10-release-1.0")
        tracker = _Tracker([addendum])
        ps = _project_store()
        scm = _scm()

        with (
            patch("oompah.release_addendum_executor._has_new_commits", return_value=False),
            patch("oompah.release_addendum_executor.apply_cherry_pick"),
            patch("oompah.release_addendum_executor.push_branch"),
            patch("oompah.release_addendum_executor._get_result_commits", return_value=[]),
        ):
            cherry_pick_addendum(
                tracker,
                "FOO-10",
                addendum,
                project_store=ps,
                project_id="proj-1",
                scm=scm,
                repo="org/repo",
            )

        call_args = ps.create_worktree.call_args
        assert call_args.args[1] == "release-FOO-10-release-1.0"

    def test_worktree_creation_failure_persists_blocked(self):
        addendum = _addendum()
        tracker = _Tracker([addendum])
        ps = MagicMock()
        ps.create_worktree.side_effect = RuntimeError("git failed")
        scm = _scm()

        result = cherry_pick_addendum(
            tracker,
            "FOO-10",
            addendum,
            project_store=ps,
            project_id="proj-1",
            scm=scm,
            repo="org/repo",
        )

        assert result.status is AddendumStatus.BLOCKED
        assert "worktree" in (result.error or "").lower()

    def test_worktree_creation_failure_posts_comment_on_source(self):
        addendum = _addendum()
        tracker = _Tracker([addendum])
        ps = MagicMock()
        ps.create_worktree.side_effect = RuntimeError("git failed")
        scm = _scm()

        cherry_pick_addendum(
            tracker,
            "FOO-10",
            addendum,
            project_store=ps,
            project_id="proj-1",
            scm=scm,
            repo="org/repo",
        )

        assert any(c["identifier"] == "FOO-10" for c in tracker.comments)

    def test_worktree_creation_failure_does_not_create_task(self):
        addendum = _addendum()
        tracker = _Tracker([addendum])
        ps = MagicMock()
        ps.create_worktree.side_effect = RuntimeError("git failed")
        scm = _scm()

        cherry_pick_addendum(
            tracker,
            "FOO-10",
            addendum,
            project_store=ps,
            project_id="proj-1",
            scm=scm,
            repo="org/repo",
        )

        assert tracker.create_issue_calls == 0


# ---------------------------------------------------------------------------
# cherry_pick_addendum — existing PR reuse
# ---------------------------------------------------------------------------


class TestCherryPickAddendumPrReuse:
    def test_reuses_existing_open_pr(self):
        """When an open PR already exists, it is reused without opening a new one."""
        existing = _make_pr(state="open", url="https://github.com/pr/existing")
        addendum = _addendum()
        tracker = _Tracker([addendum])
        ps = _project_store()
        scm = _scm(existing_pr=existing)

        with patch(
            "oompah.release_addendum_executor._get_result_commits",
            return_value=[_COMMIT_A],
        ):
            result = cherry_pick_addendum(
                tracker,
                "FOO-10",
                addendum,
                project_store=ps,
                project_id="proj-1",
                scm=scm,
                repo="org/repo",
            )

        assert result.status is AddendumStatus.IN_REVIEW
        assert result.pr_url == "https://github.com/pr/existing"
        # create_review must NOT have been called
        scm.create_review.assert_not_called()

    def test_reuse_persists_result_commits(self):
        existing = _make_pr(state="open", url="https://github.com/pr/existing")
        addendum = _addendum()
        tracker = _Tracker([addendum])
        ps = _project_store()
        scm = _scm(existing_pr=existing)

        with patch(
            "oompah.release_addendum_executor._get_result_commits",
            return_value=[_COMMIT_A, _COMMIT_B],
        ):
            result = cherry_pick_addendum(
                tracker,
                "FOO-10",
                addendum,
                project_store=ps,
                project_id="proj-1",
                scm=scm,
                repo="org/repo",
            )

        assert result.result_commits == [_COMMIT_A, _COMMIT_B]

    def test_reuse_does_not_call_cherry_pick(self):
        existing = _make_pr(state="open")
        addendum = _addendum()
        tracker = _Tracker([addendum])
        ps = _project_store()
        scm = _scm(existing_pr=existing)

        with (
            patch("oompah.release_addendum_executor.apply_cherry_pick") as mock_cp,
            patch("oompah.release_addendum_executor._get_result_commits", return_value=[]),
        ):
            cherry_pick_addendum(
                tracker,
                "FOO-10",
                addendum,
                project_store=ps,
                project_id="proj-1",
                scm=scm,
                repo="org/repo",
            )

        mock_cp.assert_not_called()

    def test_reuse_does_not_call_push(self):
        existing = _make_pr(state="open")
        addendum = _addendum()
        tracker = _Tracker([addendum])
        ps = _project_store()
        scm = _scm(existing_pr=existing)

        with (
            patch("oompah.release_addendum_executor.push_branch") as mock_push,
            patch("oompah.release_addendum_executor._get_result_commits", return_value=[]),
        ):
            cherry_pick_addendum(
                tracker,
                "FOO-10",
                addendum,
                project_store=ps,
                project_id="proj-1",
                scm=scm,
                repo="org/repo",
            )

        mock_push.assert_not_called()

    def test_closed_pr_does_not_count_as_existing(self):
        """A closed (unmerged) PR is not reused — we proceed to create a new one."""
        closed_pr = _make_pr(state="closed")
        addendum = _addendum()
        tracker = _Tracker([addendum])
        ps = _project_store()
        # find_pr_for_branch returns a closed PR; create_review should still be called
        scm = MagicMock()
        scm.find_pr_for_branch.return_value = closed_pr
        scm.create_review.return_value = _make_pr(state="open", url="https://new/pr")

        with (
            patch("oompah.release_addendum_executor._has_new_commits", return_value=False),
            patch("oompah.release_addendum_executor.apply_cherry_pick"),
            patch("oompah.release_addendum_executor.push_branch"),
            patch("oompah.release_addendum_executor._get_result_commits", return_value=[]),
        ):
            cherry_pick_addendum(
                tracker,
                "FOO-10",
                addendum,
                project_store=ps,
                project_id="proj-1",
                scm=scm,
                repo="org/repo",
            )

        scm.create_review.assert_called_once()

    def test_queries_work_branch_for_existing_pr(self):
        """find_pr_for_branch is called with the addendum's work_branch."""
        addendum = _addendum(work_branch="oompah/release/FOO-10/release-1.0")
        tracker = _Tracker([addendum])
        ps = _project_store()
        scm = _scm(existing_pr=None)

        with (
            patch("oompah.release_addendum_executor._has_new_commits", return_value=False),
            patch("oompah.release_addendum_executor.apply_cherry_pick"),
            patch("oompah.release_addendum_executor.push_branch"),
            patch("oompah.release_addendum_executor._get_result_commits", return_value=[]),
        ):
            cherry_pick_addendum(
                tracker,
                "FOO-10",
                addendum,
                project_store=ps,
                project_id="proj-1",
                scm=scm,
                repo="org/repo",
            )

        scm.find_pr_for_branch.assert_called_once_with(
            "org/repo", "oompah/release/FOO-10/release-1.0"
        )


# ---------------------------------------------------------------------------
# cherry_pick_addendum — cherry-pick order
# ---------------------------------------------------------------------------


class TestCherryPickAddendumCommitOrder:
    def test_cherry_pick_uses_commits_from_addendum(self):
        """apply_cherry_pick is called with addendum.commits in order."""
        commits = [_COMMIT_A, _COMMIT_B]
        addendum = _addendum(commits=commits)
        tracker = _Tracker([addendum])
        ps = _project_store()
        scm = _scm()

        with (
            patch("oompah.release_addendum_executor._has_new_commits", return_value=False),
            patch("oompah.release_addendum_executor.apply_cherry_pick") as mock_cp,
            patch("oompah.release_addendum_executor.push_branch"),
            patch("oompah.release_addendum_executor._get_result_commits", return_value=commits),
        ):
            cherry_pick_addendum(
                tracker,
                "FOO-10",
                addendum,
                project_store=ps,
                project_id="proj-1",
                scm=scm,
                repo="org/repo",
            )

        mock_cp.assert_called_once()
        _, called_commits = mock_cp.call_args.args
        assert called_commits == commits

    def test_cherry_pick_skipped_when_commits_already_applied(self):
        """When the worktree already has commits ahead, cherry-pick is skipped."""
        addendum = _addendum()
        tracker = _Tracker([addendum])
        ps = _project_store()
        scm = _scm()

        with (
            patch(
                "oompah.release_addendum_executor._has_new_commits",
                return_value=True,  # commits already applied
            ),
            patch("oompah.release_addendum_executor.apply_cherry_pick") as mock_cp,
            patch("oompah.release_addendum_executor.push_branch"),
            patch("oompah.release_addendum_executor._get_result_commits", return_value=[_COMMIT_A]),
        ):
            result = cherry_pick_addendum(
                tracker,
                "FOO-10",
                addendum,
                project_store=ps,
                project_id="proj-1",
                scm=scm,
                repo="org/repo",
            )

        mock_cp.assert_not_called()
        assert result.status is AddendumStatus.IN_REVIEW

    def test_result_commits_reflect_target_base(self):
        """_get_result_commits is called with target_branch (not work_branch)."""
        addendum = _addendum(target="release/2.0")
        tracker = _Tracker([addendum])
        ps = _project_store()
        scm = _scm()

        with (
            patch("oompah.release_addendum_executor._has_new_commits", return_value=False),
            patch("oompah.release_addendum_executor.apply_cherry_pick"),
            patch("oompah.release_addendum_executor.push_branch"),
            patch(
                "oompah.release_addendum_executor._get_result_commits",
                return_value=[_COMMIT_A],
            ) as mock_rc,
        ):
            cherry_pick_addendum(
                tracker,
                "FOO-10",
                addendum,
                project_store=ps,
                project_id="proj-1",
                scm=scm,
                repo="org/repo",
            )

        mock_rc.assert_called()
        _, called_branch = mock_rc.call_args.args
        assert called_branch == "release/2.0"

    def test_push_uses_work_branch(self):
        """push_branch is called with addendum.work_branch."""
        addendum = _addendum(work_branch="oompah/release/FOO-10/release-1.0")
        tracker = _Tracker([addendum])
        ps = _project_store()
        scm = _scm()

        with (
            patch("oompah.release_addendum_executor._has_new_commits", return_value=False),
            patch("oompah.release_addendum_executor.apply_cherry_pick"),
            patch("oompah.release_addendum_executor.push_branch") as mock_push,
            patch("oompah.release_addendum_executor._get_result_commits", return_value=[]),
        ):
            cherry_pick_addendum(
                tracker,
                "FOO-10",
                addendum,
                project_store=ps,
                project_id="proj-1",
                scm=scm,
                repo="org/repo",
            )

        mock_push.assert_called_once()
        _, called_branch = mock_push.call_args.args
        assert called_branch == "oompah/release/FOO-10/release-1.0"


# ---------------------------------------------------------------------------
# cherry_pick_addendum — successful state/evidence updates
# ---------------------------------------------------------------------------


class TestCherryPickAddendumSuccess:
    def _run_success(
        self,
        addendum: ReleaseAddendum | None = None,
        pr_url: str = "https://github.com/pr/55",
        result_commits: list[str] | None = None,
    ) -> tuple[ReleaseAddendum, "_Tracker"]:
        if addendum is None:
            addendum = _addendum()
        if result_commits is None:
            result_commits = [_COMMIT_A, _COMMIT_B]
        tracker = _Tracker([addendum])
        ps = _project_store()
        scm = _scm(new_pr=_make_pr(url=pr_url))

        with (
            patch("oompah.release_addendum_executor._has_new_commits", return_value=False),
            patch("oompah.release_addendum_executor.apply_cherry_pick"),
            patch("oompah.release_addendum_executor.push_branch"),
            patch(
                "oompah.release_addendum_executor._get_result_commits",
                return_value=result_commits,
            ),
        ):
            result = cherry_pick_addendum(
                tracker,
                "FOO-10",
                addendum,
                project_store=ps,
                project_id="proj-1",
                scm=scm,
                repo="org/repo",
                source_title="My feature",
            )

        return result, tracker

    def test_transitions_to_in_review(self):
        result, _ = self._run_success()
        assert result.status is AddendumStatus.IN_REVIEW

    def test_persists_pr_url(self):
        result, _ = self._run_success(pr_url="https://github.com/pr/99")
        assert result.pr_url == "https://github.com/pr/99"

    def test_persists_result_commits(self):
        result, _ = self._run_success(result_commits=[_COMMIT_A, _COMMIT_B])
        assert result.result_commits == [_COMMIT_A, _COMMIT_B]

    def test_no_child_task_created(self):
        """No child tracker task is created during a successful execution."""
        _, tracker = self._run_success()
        assert tracker.create_issue_calls == 0

    def test_source_task_status_not_updated(self):
        """The source task's status is never modified."""
        _, tracker = self._run_success()
        assert tracker.update_issue_calls == 0

    def test_no_comment_on_success(self):
        """Successful execution does not post a comment on the source task."""
        _, tracker = self._run_success()
        assert tracker.comments == []

    def test_success_with_none_pr_url(self):
        """When SCM returns no URL, addendum still reaches in_review."""
        addendum = _addendum()
        tracker = _Tracker([addendum])
        ps = _project_store()
        scm = MagicMock()
        scm.find_pr_for_branch.return_value = None
        scm.create_review.return_value = None  # no URL

        with (
            patch("oompah.release_addendum_executor._has_new_commits", return_value=False),
            patch("oompah.release_addendum_executor.apply_cherry_pick"),
            patch("oompah.release_addendum_executor.push_branch"),
            patch("oompah.release_addendum_executor._get_result_commits", return_value=[]),
        ):
            result = cherry_pick_addendum(
                tracker,
                "FOO-10",
                addendum,
                project_store=ps,
                project_id="proj-1",
                scm=scm,
                repo="org/repo",
            )

        assert result.status is AddendumStatus.IN_REVIEW
        assert result.pr_url is None


# ---------------------------------------------------------------------------
# cherry_pick_addendum — conflict preservation
# ---------------------------------------------------------------------------


class TestCherryPickAddendumConflict:
    def _run_conflict(
        self,
        addendum: ReleaseAddendum | None = None,
        error_message: str = "CONFLICT in foo.py",
    ) -> tuple[ReleaseAddendum, "_Tracker"]:
        if addendum is None:
            addendum = _addendum()
        tracker = _Tracker([addendum])
        ps = _project_store()
        scm = _scm()

        with (
            patch("oompah.release_addendum_executor._has_new_commits", return_value=False),
            patch(
                "oompah.release_addendum_executor.apply_cherry_pick",
                side_effect=CherryPickConflictError(error_message),
            ),
        ):
            result = cherry_pick_addendum(
                tracker,
                "FOO-10",
                addendum,
                project_store=ps,
                project_id="proj-1",
                scm=scm,
                repo="org/repo",
            )

        return result, tracker

    def test_transitions_to_blocked_on_conflict(self):
        result, _ = self._run_conflict()
        assert result.status is AddendumStatus.BLOCKED

    def test_persists_error_diagnostic(self):
        result, _ = self._run_conflict(error_message="CONFLICT in src/foo.py")
        assert result.error is not None
        assert "CONFLICT" in result.error or "conflict" in result.error.lower()

    def test_posts_actionable_comment_on_source_task(self):
        _, tracker = self._run_conflict()
        assert any(c["identifier"] == "FOO-10" for c in tracker.comments)

    def test_comment_mentions_target_branch(self):
        _, tracker = self._run_conflict()
        comment_text = " ".join(c["message"] for c in tracker.comments)
        assert "release/1.0" in comment_text

    def test_comment_mentions_worktree_path(self):
        _, tracker = self._run_conflict()
        comment_text = " ".join(c["message"] for c in tracker.comments)
        # The worktree path should be mentioned for operator inspection
        assert "/wt/" in comment_text or "worktree" in comment_text.lower()

    def test_comment_mentions_commits(self):
        addendum = _addendum(commits=[_COMMIT_A, _COMMIT_B])
        _, tracker = self._run_conflict(addendum=addendum)
        comment_text = " ".join(c["message"] for c in tracker.comments)
        assert _COMMIT_A in comment_text or _COMMIT_B in comment_text

    def test_comment_posted_to_source_not_child(self):
        """Comment is posted to the source identifier, never to a child task."""
        _, tracker = self._run_conflict()
        for comment in tracker.comments:
            assert comment["identifier"] == "FOO-10"

    def test_no_child_task_created_on_conflict(self):
        _, tracker = self._run_conflict()
        assert tracker.create_issue_calls == 0

    def test_source_task_status_not_updated_on_conflict(self):
        _, tracker = self._run_conflict()
        assert tracker.update_issue_calls == 0

    def test_push_not_called_after_conflict(self):
        addendum = _addendum()
        tracker = _Tracker([addendum])
        ps = _project_store()
        scm = _scm()

        with (
            patch("oompah.release_addendum_executor._has_new_commits", return_value=False),
            patch(
                "oompah.release_addendum_executor.apply_cherry_pick",
                side_effect=CherryPickConflictError("CONFLICT"),
            ),
            patch("oompah.release_addendum_executor.push_branch") as mock_push,
        ):
            cherry_pick_addendum(
                tracker,
                "FOO-10",
                addendum,
                project_store=ps,
                project_id="proj-1",
                scm=scm,
                repo="org/repo",
            )

        mock_push.assert_not_called()

    def test_create_review_not_called_after_conflict(self):
        """PR is not opened after a cherry-pick conflict."""
        addendum = _addendum()
        tracker = _Tracker([addendum])
        ps = _project_store()
        scm = _scm()

        with (
            patch("oompah.release_addendum_executor._has_new_commits", return_value=False),
            patch(
                "oompah.release_addendum_executor.apply_cherry_pick",
                side_effect=CherryPickConflictError("CONFLICT"),
            ),
        ):
            cherry_pick_addendum(
                tracker,
                "FOO-10",
                addendum,
                project_store=ps,
                project_id="proj-1",
                scm=scm,
                repo="org/repo",
            )

        scm.create_review.assert_not_called()


# ---------------------------------------------------------------------------
# cherry_pick_addendum — non-conflict failure
# ---------------------------------------------------------------------------


class TestCherryPickAddendumNonConflictFailure:
    def test_cherry_pick_error_persists_blocked(self):
        """A non-conflict cherry-pick failure (bad SHA etc.) blocks the addendum."""
        addendum = _addendum()
        tracker = _Tracker([addendum])
        ps = _project_store()
        scm = _scm()

        with (
            patch("oompah.release_addendum_executor._has_new_commits", return_value=False),
            patch(
                "oompah.release_addendum_executor.apply_cherry_pick",
                side_effect=CherryPickError("fatal: bad object abc123"),
            ),
        ):
            result = cherry_pick_addendum(
                tracker,
                "FOO-10",
                addendum,
                project_store=ps,
                project_id="proj-1",
                scm=scm,
                repo="org/repo",
            )

        assert result.status is AddendumStatus.BLOCKED

    def test_cherry_pick_error_persists_error_message(self):
        addendum = _addendum()
        tracker = _Tracker([addendum])
        ps = _project_store()
        scm = _scm()

        with (
            patch("oompah.release_addendum_executor._has_new_commits", return_value=False),
            patch(
                "oompah.release_addendum_executor.apply_cherry_pick",
                side_effect=CherryPickError("fatal: bad object"),
            ),
        ):
            result = cherry_pick_addendum(
                tracker,
                "FOO-10",
                addendum,
                project_store=ps,
                project_id="proj-1",
                scm=scm,
                repo="org/repo",
            )

        assert result.error is not None

    def test_cherry_pick_error_posts_comment_on_source(self):
        addendum = _addendum()
        tracker = _Tracker([addendum])
        ps = _project_store()
        scm = _scm()

        with (
            patch("oompah.release_addendum_executor._has_new_commits", return_value=False),
            patch(
                "oompah.release_addendum_executor.apply_cherry_pick",
                side_effect=CherryPickError("fatal: bad object"),
            ),
        ):
            cherry_pick_addendum(
                tracker,
                "FOO-10",
                addendum,
                project_store=ps,
                project_id="proj-1",
                scm=scm,
                repo="org/repo",
            )

        assert any(c["identifier"] == "FOO-10" for c in tracker.comments)

    def test_non_conflict_cherry_pick_error_no_child_task(self):
        addendum = _addendum()
        tracker = _Tracker([addendum])
        ps = _project_store()
        scm = _scm()

        with (
            patch("oompah.release_addendum_executor._has_new_commits", return_value=False),
            patch(
                "oompah.release_addendum_executor.apply_cherry_pick",
                side_effect=CherryPickError("fatal: bad object"),
            ),
        ):
            cherry_pick_addendum(
                tracker,
                "FOO-10",
                addendum,
                project_store=ps,
                project_id="proj-1",
                scm=scm,
                repo="org/repo",
            )

        assert tracker.create_issue_calls == 0

    def test_push_failure_persists_blocked(self):
        addendum = _addendum()
        tracker = _Tracker([addendum])
        ps = _project_store()
        scm = _scm()

        with (
            patch("oompah.release_addendum_executor._has_new_commits", return_value=False),
            patch("oompah.release_addendum_executor.apply_cherry_pick"),
            patch(
                "oompah.release_addendum_executor.push_branch",
                side_effect=subprocess.CalledProcessError(1, "git push"),
            ),
        ):
            result = cherry_pick_addendum(
                tracker,
                "FOO-10",
                addendum,
                project_store=ps,
                project_id="proj-1",
                scm=scm,
                repo="org/repo",
            )

        assert result.status is AddendumStatus.BLOCKED

    def test_push_failure_posts_comment_on_source(self):
        addendum = _addendum()
        tracker = _Tracker([addendum])
        ps = _project_store()
        scm = _scm()

        with (
            patch("oompah.release_addendum_executor._has_new_commits", return_value=False),
            patch("oompah.release_addendum_executor.apply_cherry_pick"),
            patch(
                "oompah.release_addendum_executor.push_branch",
                side_effect=subprocess.CalledProcessError(1, "git push"),
            ),
        ):
            cherry_pick_addendum(
                tracker,
                "FOO-10",
                addendum,
                project_store=ps,
                project_id="proj-1",
                scm=scm,
                repo="org/repo",
            )

        assert any(c["identifier"] == "FOO-10" for c in tracker.comments)

    def test_push_failure_no_child_task(self):
        addendum = _addendum()
        tracker = _Tracker([addendum])
        ps = _project_store()
        scm = _scm()

        with (
            patch("oompah.release_addendum_executor._has_new_commits", return_value=False),
            patch("oompah.release_addendum_executor.apply_cherry_pick"),
            patch(
                "oompah.release_addendum_executor.push_branch",
                side_effect=subprocess.CalledProcessError(1, "git push"),
            ),
        ):
            cherry_pick_addendum(
                tracker,
                "FOO-10",
                addendum,
                project_store=ps,
                project_id="proj-1",
                scm=scm,
                repo="org/repo",
            )

        assert tracker.create_issue_calls == 0

    def test_unexpected_error_in_cherry_pick_persists_blocked(self):
        addendum = _addendum()
        tracker = _Tracker([addendum])
        ps = _project_store()
        scm = _scm()

        with (
            patch("oompah.release_addendum_executor._has_new_commits", return_value=False),
            patch(
                "oompah.release_addendum_executor.apply_cherry_pick",
                side_effect=RuntimeError("unexpected"),
            ),
        ):
            result = cherry_pick_addendum(
                tracker,
                "FOO-10",
                addendum,
                project_store=ps,
                project_id="proj-1",
                scm=scm,
                repo="org/repo",
            )

        assert result.status is AddendumStatus.BLOCKED


# ---------------------------------------------------------------------------
# cherry_pick_addendum — no tracker task created (cross-cutting)
# ---------------------------------------------------------------------------


class TestNoTrackerTaskCreated:
    """Proof that no tracker task is ever created, regardless of outcome."""

    def _run(
        self,
        *,
        cherry_pick_side_effect: type | Exception | None = None,
        push_side_effect: type | Exception | None = None,
        worktree_side_effect: type | Exception | None = None,
        existing_pr: MagicMock | None = None,
    ) -> "_Tracker":
        addendum = _addendum()
        tracker = _Tracker([addendum])
        ps = _project_store()
        if worktree_side_effect is not None:
            ps.create_worktree.side_effect = worktree_side_effect

        scm = _scm(existing_pr=existing_pr)

        patches = []
        if worktree_side_effect is None:
            if cherry_pick_side_effect is not None:
                patches.append(
                    patch(
                        "oompah.release_addendum_executor.apply_cherry_pick",
                        side_effect=cherry_pick_side_effect,
                    )
                )
            else:
                patches.append(
                    patch("oompah.release_addendum_executor.apply_cherry_pick")
                )
            if push_side_effect is not None:
                patches.append(
                    patch(
                        "oompah.release_addendum_executor.push_branch",
                        side_effect=push_side_effect,
                    )
                )
            else:
                patches.append(patch("oompah.release_addendum_executor.push_branch"))
            patches.append(
                patch("oompah.release_addendum_executor._has_new_commits", return_value=False)
            )
            if existing_pr is None and push_side_effect is None and cherry_pick_side_effect is None:
                patches.append(
                    patch(
                        "oompah.release_addendum_executor._get_result_commits",
                        return_value=[],
                    )
                )

        from contextlib import ExitStack
        with ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            cherry_pick_addendum(
                tracker,
                "FOO-10",
                addendum,
                project_store=ps,
                project_id="proj-1",
                scm=scm,
                repo="org/repo",
            )

        return tracker

    def test_no_task_on_success(self):
        tracker = self._run()
        assert tracker.create_issue_calls == 0

    def test_no_task_on_conflict(self):
        tracker = self._run(cherry_pick_side_effect=CherryPickConflictError("c"))
        assert tracker.create_issue_calls == 0

    def test_no_task_on_cherry_pick_error(self):
        tracker = self._run(cherry_pick_side_effect=CherryPickError("bad"))
        assert tracker.create_issue_calls == 0

    def test_no_task_on_push_failure(self):
        tracker = self._run(
            push_side_effect=subprocess.CalledProcessError(1, "git push")
        )
        assert tracker.create_issue_calls == 0

    def test_no_task_on_worktree_failure(self):
        tracker = self._run(worktree_side_effect=RuntimeError("git failed"))
        assert tracker.create_issue_calls == 0

    def test_no_task_on_pr_reuse(self):
        tracker = self._run(existing_pr=_make_pr(state="open"))
        assert tracker.create_issue_calls == 0

    def test_source_status_never_updated_on_success(self):
        tracker = self._run()
        assert tracker.update_issue_calls == 0

    def test_source_status_never_updated_on_conflict(self):
        tracker = self._run(cherry_pick_side_effect=CherryPickConflictError("c"))
        assert tracker.update_issue_calls == 0
