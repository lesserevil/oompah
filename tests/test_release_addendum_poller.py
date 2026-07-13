"""Tests for :mod:`oompah.release_addendum_poller` (OOMPAH-179).

Covers:
- Merged PR outcome: transitions in_review → merged, records completed_at,
  posts oompah comment.
- Open PR outcome: no state change (idempotent).
- Closed-unmerged PR outcome: updates error field, stays in_review, posts comment.
- Non-in_review addendum: no-op.
- SCM failures are absorbed without crashing.
- Duplicate poll idempotency (merged/closed called twice).
- Immutable commits across all transitions.
- Comment content: branch, PR URL, transition, and error where applicable.
- _update_addendum_evidence helper: updates fields without status change.
- _post_source_comment: uses author="oompah", swallows exceptions.
- Poller does not create child tasks or alter source task status.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from oompah.release_addendum_poller import (
    CLOSED_UNMERGED_ERROR_PREFIX,
    _handle_closed,
    _handle_merged,
    _post_source_comment,
    _update_addendum_evidence,
    poll_addendum_pr,
)
from oompah.release_addendum_schema import (
    AddendumRepository,
    AddendumStatus,
    ReleaseAddendum,
    make_addendum_id,
    make_work_branch,
    make_worktree_key,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

NOW = datetime(2026, 7, 13, 10, 0, 0, tzinfo=timezone.utc)

_COMMIT_A = "a" * 40
_COMMIT_B = "b" * 40
_PR_URL = "https://github.com/org/repo/pull/42"
_WORK_BRANCH = "oompah/release/FOO-10/release-1.0"


def _addendum(
    status: AddendumStatus = AddendumStatus.IN_REVIEW,
    *,
    target: str = "release/1.0",
    commits: list[str] | None = None,
    pr_url: str | None = _PR_URL,
    error: str | None = None,
    source_id: str = "FOO-10",
) -> ReleaseAddendum:
    if commits is None:
        commits = [_COMMIT_A, _COMMIT_B]
    return ReleaseAddendum(
        id=make_addendum_id(source_id, target),
        source_branch="main",
        target_branch=target,
        status=status,
        commits=commits,
        work_branch=make_work_branch(source_id, target),
        worktree_key=make_worktree_key(source_id, target),
        queued_at=NOW.isoformat(),
        pr_url=pr_url,
        error=error,
    )


class _Tracker:
    """Minimal in-memory tracker for poller tests."""

    def __init__(self, addendums: list[ReleaseAddendum]) -> None:
        self._lock = threading.Lock()
        self._metadata: dict[str, object] = {
            "oompah.release_addendums": [a.to_raw() for a in addendums]
        }
        self.comments: list[dict] = []
        self.writes: int = 0
        # Guard: must never be called.
        self.create_issue_calls: int = 0
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
        self.comments.append(
            {"identifier": identifier, "message": message, "author": author}
        )

    def create_issue(self, **_kwargs) -> object:
        self.create_issue_calls += 1
        return SimpleNamespace(identifier="MUST-NOT-EXIST")

    def update_issue(self, _identifier: str, **_kwargs) -> None:
        self.update_issue_calls += 1


def _make_scm(state: str = "open") -> MagicMock:
    pr = MagicMock()
    pr.state = state
    pr.url = _PR_URL
    scm = MagicMock()
    scm.find_pr_for_branch.return_value = pr
    return scm


def _make_scm_none() -> MagicMock:
    """SCM that returns None (no PR found)."""
    scm = MagicMock()
    scm.find_pr_for_branch.return_value = None
    return scm


# ---------------------------------------------------------------------------
# Tests: _post_source_comment
# ---------------------------------------------------------------------------


class TestPostSourceComment:
    def test_posts_comment_with_oompah_author(self):
        tracker = _Tracker([])
        _post_source_comment(tracker, "FOO-10", "hello world")
        assert len(tracker.comments) == 1
        assert tracker.comments[0]["author"] == "oompah"
        assert tracker.comments[0]["message"] == "hello world"
        assert tracker.comments[0]["identifier"] == "FOO-10"

    def test_swallows_exception_without_raising(self):
        bad_tracker = MagicMock()
        bad_tracker.add_comment.side_effect = RuntimeError("disk full")
        # Must not raise
        _post_source_comment(bad_tracker, "FOO-10", "msg")


# ---------------------------------------------------------------------------
# Tests: _update_addendum_evidence
# ---------------------------------------------------------------------------


class TestUpdateAddendumEvidence:
    def test_updates_error_field_without_changing_status(self):
        addendum = _addendum(status=AddendumStatus.IN_REVIEW, error=None)
        tracker = _Tracker([addendum])
        result = _update_addendum_evidence(tracker, "FOO-10", addendum.id, error="oops")
        assert result is not None
        assert result.status == AddendumStatus.IN_REVIEW
        assert result.error == "oops"

    def test_preserves_commits(self):
        addendum = _addendum(status=AddendumStatus.IN_REVIEW)
        tracker = _Tracker([addendum])
        result = _update_addendum_evidence(tracker, "FOO-10", addendum.id, error="x")
        assert result.commits == addendum.commits

    def test_preserves_pr_url(self):
        addendum = _addendum(status=AddendumStatus.IN_REVIEW, pr_url=_PR_URL)
        tracker = _Tracker([addendum])
        result = _update_addendum_evidence(tracker, "FOO-10", addendum.id, error="x")
        assert result.pr_url == _PR_URL

    def test_returns_none_when_addendum_not_found(self):
        tracker = _Tracker([])
        result = _update_addendum_evidence(tracker, "FOO-10", "nonexistent-id", error="x")
        assert result is None

    def test_writes_to_tracker_exactly_once(self):
        addendum = _addendum()
        tracker = _Tracker([addendum])
        tracker.writes = 0
        _update_addendum_evidence(tracker, "FOO-10", addendum.id, error="x")
        assert tracker.writes == 1


# ---------------------------------------------------------------------------
# Tests: poll_addendum_pr — not in_review
# ---------------------------------------------------------------------------


class TestPollAddendumPrNotInReview:
    def test_open_addendum_is_returned_unchanged(self):
        addendum = _addendum(status=AddendumStatus.OPEN)
        tracker = _Tracker([addendum])
        scm = _make_scm()
        result = poll_addendum_pr(tracker, "FOO-10", addendum, scm=scm, repo="org/repo")
        assert result.status == AddendumStatus.OPEN
        scm.find_pr_for_branch.assert_not_called()

    def test_blocked_addendum_is_returned_unchanged(self):
        addendum = _addendum(status=AddendumStatus.BLOCKED)
        tracker = _Tracker([addendum])
        scm = _make_scm()
        result = poll_addendum_pr(tracker, "FOO-10", addendum, scm=scm, repo="org/repo")
        assert result.status == AddendumStatus.BLOCKED
        scm.find_pr_for_branch.assert_not_called()

    def test_merged_addendum_is_returned_unchanged(self):
        addendum = _addendum(status=AddendumStatus.MERGED)
        tracker = _Tracker([addendum])
        scm = _make_scm()
        result = poll_addendum_pr(tracker, "FOO-10", addendum, scm=scm, repo="org/repo")
        assert result.status == AddendumStatus.MERGED
        scm.find_pr_for_branch.assert_not_called()

    def test_archived_addendum_is_returned_unchanged(self):
        addendum = _addendum(status=AddendumStatus.ARCHIVED)
        tracker = _Tracker([addendum])
        scm = _make_scm()
        result = poll_addendum_pr(tracker, "FOO-10", addendum, scm=scm, repo="org/repo")
        assert result.status == AddendumStatus.ARCHIVED
        scm.find_pr_for_branch.assert_not_called()

    def test_no_pr_url_skips_poll(self):
        addendum = _addendum(status=AddendumStatus.IN_REVIEW, pr_url=None)
        tracker = _Tracker([addendum])
        scm = _make_scm()
        result = poll_addendum_pr(tracker, "FOO-10", addendum, scm=scm, repo="org/repo")
        assert result.status == AddendumStatus.IN_REVIEW
        scm.find_pr_for_branch.assert_not_called()
        assert tracker.writes == 0

    def test_no_comment_posted_when_not_in_review(self):
        addendum = _addendum(status=AddendumStatus.OPEN)
        tracker = _Tracker([addendum])
        scm = _make_scm()
        poll_addendum_pr(tracker, "FOO-10", addendum, scm=scm, repo="org/repo")
        assert len(tracker.comments) == 0


# ---------------------------------------------------------------------------
# Tests: poll_addendum_pr — open PR
# ---------------------------------------------------------------------------


class TestPollAddendumPrOpen:
    def test_open_pr_leaves_status_unchanged(self):
        addendum = _addendum(status=AddendumStatus.IN_REVIEW)
        tracker = _Tracker([addendum])
        scm = _make_scm(state="open")
        result = poll_addendum_pr(tracker, "FOO-10", addendum, scm=scm, repo="org/repo")
        assert result.status == AddendumStatus.IN_REVIEW
        assert tracker.writes == 0

    def test_open_pr_posts_no_comment(self):
        addendum = _addendum(status=AddendumStatus.IN_REVIEW)
        tracker = _Tracker([addendum])
        scm = _make_scm(state="open")
        poll_addendum_pr(tracker, "FOO-10", addendum, scm=scm, repo="org/repo")
        assert len(tracker.comments) == 0

    def test_scm_queried_with_work_branch(self):
        addendum = _addendum(status=AddendumStatus.IN_REVIEW)
        tracker = _Tracker([addendum])
        scm = _make_scm(state="open")
        poll_addendum_pr(tracker, "FOO-10", addendum, scm=scm, repo="org/repo")
        scm.find_pr_for_branch.assert_called_once_with("org/repo", addendum.work_branch)

    def test_no_pr_found_returns_unchanged(self):
        addendum = _addendum(status=AddendumStatus.IN_REVIEW)
        tracker = _Tracker([addendum])
        scm = _make_scm_none()
        result = poll_addendum_pr(tracker, "FOO-10", addendum, scm=scm, repo="org/repo")
        assert result.status == AddendumStatus.IN_REVIEW
        assert tracker.writes == 0

    def test_scm_exception_returns_unchanged(self):
        addendum = _addendum(status=AddendumStatus.IN_REVIEW)
        tracker = _Tracker([addendum])
        scm = MagicMock()
        scm.find_pr_for_branch.side_effect = RuntimeError("network error")
        result = poll_addendum_pr(tracker, "FOO-10", addendum, scm=scm, repo="org/repo")
        assert result.status == AddendumStatus.IN_REVIEW
        assert tracker.writes == 0


# ---------------------------------------------------------------------------
# Tests: poll_addendum_pr — merged PR
# ---------------------------------------------------------------------------


class TestPollAddendumPrMerged:
    def test_merged_pr_transitions_to_merged(self):
        addendum = _addendum(status=AddendumStatus.IN_REVIEW)
        tracker = _Tracker([addendum])
        scm = _make_scm(state="merged")
        result = poll_addendum_pr(
            tracker, "FOO-10", addendum, scm=scm, repo="org/repo", now=NOW
        )
        assert result.status == AddendumStatus.MERGED

    def test_merged_pr_records_completed_at(self):
        addendum = _addendum(status=AddendumStatus.IN_REVIEW)
        tracker = _Tracker([addendum])
        scm = _make_scm(state="merged")
        result = poll_addendum_pr(
            tracker, "FOO-10", addendum, scm=scm, repo="org/repo", now=NOW
        )
        assert result.completed_at == NOW.isoformat()

    def test_merged_pr_preserves_commits(self):
        commits = [_COMMIT_A, _COMMIT_B]
        addendum = _addendum(status=AddendumStatus.IN_REVIEW, commits=commits)
        tracker = _Tracker([addendum])
        scm = _make_scm(state="merged")
        result = poll_addendum_pr(
            tracker, "FOO-10", addendum, scm=scm, repo="org/repo", now=NOW
        )
        assert result.commits == commits

    def test_merged_pr_posts_oompah_comment(self):
        addendum = _addendum(status=AddendumStatus.IN_REVIEW)
        tracker = _Tracker([addendum])
        scm = _make_scm(state="merged")
        poll_addendum_pr(tracker, "FOO-10", addendum, scm=scm, repo="org/repo", now=NOW)
        assert len(tracker.comments) == 1
        comment = tracker.comments[0]
        assert comment["author"] == "oompah"
        assert comment["identifier"] == "FOO-10"

    def test_merged_comment_includes_branch(self):
        addendum = _addendum(status=AddendumStatus.IN_REVIEW, target="release/1.0")
        tracker = _Tracker([addendum])
        scm = _make_scm(state="merged")
        poll_addendum_pr(tracker, "FOO-10", addendum, scm=scm, repo="org/repo", now=NOW)
        assert "release/1.0" in tracker.comments[0]["message"]

    def test_merged_comment_includes_pr_url(self):
        addendum = _addendum(status=AddendumStatus.IN_REVIEW, pr_url=_PR_URL)
        tracker = _Tracker([addendum])
        scm = _make_scm(state="merged")
        poll_addendum_pr(tracker, "FOO-10", addendum, scm=scm, repo="org/repo", now=NOW)
        assert _PR_URL in tracker.comments[0]["message"]

    def test_merged_pr_writes_to_tracker(self):
        addendum = _addendum(status=AddendumStatus.IN_REVIEW)
        tracker = _Tracker([addendum])
        scm = _make_scm(state="merged")
        tracker.writes = 0
        poll_addendum_pr(tracker, "FOO-10", addendum, scm=scm, repo="org/repo", now=NOW)
        assert tracker.writes >= 1

    def test_duplicate_poll_merged_is_idempotent(self):
        """Calling poll twice on an already-merged addendum is a no-op."""
        addendum = _addendum(status=AddendumStatus.IN_REVIEW)
        tracker = _Tracker([addendum])
        scm = _make_scm(state="merged")
        # First poll transitions to merged
        poll_addendum_pr(tracker, "FOO-10", addendum, scm=scm, repo="org/repo", now=NOW)
        # The addendum is now merged; refresh state
        current = AddendumRepository(tracker).read("FOO-10")
        merged_addendum = next(a for a in current if a.id == addendum.id)
        assert merged_addendum.status == AddendumStatus.MERGED
        # Second poll: already merged, not IN_REVIEW → immediate no-op
        initial_writes = tracker.writes
        poll_addendum_pr(
            tracker, "FOO-10", merged_addendum, scm=scm, repo="org/repo", now=NOW
        )
        assert tracker.writes == initial_writes  # no additional write

    def test_duplicate_comment_posted_only_once_per_merge(self):
        addendum = _addendum(status=AddendumStatus.IN_REVIEW)
        tracker = _Tracker([addendum])
        scm = _make_scm(state="merged")
        # First poll
        poll_addendum_pr(tracker, "FOO-10", addendum, scm=scm, repo="org/repo", now=NOW)
        # Second poll with merged state (but addendum is now merged so early-return)
        current = AddendumRepository(tracker).read("FOO-10")
        merged_addendum = next(a for a in current if a.id == addendum.id)
        poll_addendum_pr(
            tracker, "FOO-10", merged_addendum, scm=scm, repo="org/repo", now=NOW
        )
        # Only one comment posted
        assert len(tracker.comments) == 1

    def test_merged_does_not_create_child_task(self):
        addendum = _addendum(status=AddendumStatus.IN_REVIEW)
        tracker = _Tracker([addendum])
        scm = _make_scm(state="merged")
        poll_addendum_pr(tracker, "FOO-10", addendum, scm=scm, repo="org/repo", now=NOW)
        assert tracker.create_issue_calls == 0

    def test_merged_does_not_alter_source_task_status(self):
        addendum = _addendum(status=AddendumStatus.IN_REVIEW)
        tracker = _Tracker([addendum])
        scm = _make_scm(state="merged")
        poll_addendum_pr(tracker, "FOO-10", addendum, scm=scm, repo="org/repo", now=NOW)
        assert tracker.update_issue_calls == 0


# ---------------------------------------------------------------------------
# Tests: poll_addendum_pr — closed-unmerged PR
# ---------------------------------------------------------------------------


class TestPollAddendumPrClosed:
    def test_closed_pr_keeps_in_review_status(self):
        addendum = _addendum(status=AddendumStatus.IN_REVIEW)
        tracker = _Tracker([addendum])
        scm = _make_scm(state="closed")
        result = poll_addendum_pr(tracker, "FOO-10", addendum, scm=scm, repo="org/repo")
        assert result.status == AddendumStatus.IN_REVIEW

    def test_closed_pr_sets_error_field(self):
        addendum = _addendum(status=AddendumStatus.IN_REVIEW, pr_url=_PR_URL)
        tracker = _Tracker([addendum])
        scm = _make_scm(state="closed")
        result = poll_addendum_pr(tracker, "FOO-10", addendum, scm=scm, repo="org/repo")
        assert result.error is not None
        assert CLOSED_UNMERGED_ERROR_PREFIX in result.error
        assert _PR_URL in result.error

    def test_closed_pr_preserves_commits(self):
        commits = [_COMMIT_A, _COMMIT_B]
        addendum = _addendum(status=AddendumStatus.IN_REVIEW, commits=commits)
        tracker = _Tracker([addendum])
        scm = _make_scm(state="closed")
        result = poll_addendum_pr(tracker, "FOO-10", addendum, scm=scm, repo="org/repo")
        assert result.commits == commits

    def test_closed_pr_posts_oompah_comment(self):
        addendum = _addendum(status=AddendumStatus.IN_REVIEW)
        tracker = _Tracker([addendum])
        scm = _make_scm(state="closed")
        poll_addendum_pr(tracker, "FOO-10", addendum, scm=scm, repo="org/repo")
        assert len(tracker.comments) == 1
        assert tracker.comments[0]["author"] == "oompah"

    def test_closed_comment_includes_branch(self):
        addendum = _addendum(status=AddendumStatus.IN_REVIEW, target="release/1.0")
        tracker = _Tracker([addendum])
        scm = _make_scm(state="closed")
        poll_addendum_pr(tracker, "FOO-10", addendum, scm=scm, repo="org/repo")
        assert "release/1.0" in tracker.comments[0]["message"]

    def test_closed_comment_includes_pr_url(self):
        addendum = _addendum(status=AddendumStatus.IN_REVIEW, pr_url=_PR_URL)
        tracker = _Tracker([addendum])
        scm = _make_scm(state="closed")
        poll_addendum_pr(tracker, "FOO-10", addendum, scm=scm, repo="org/repo")
        assert _PR_URL in tracker.comments[0]["message"]

    def test_closed_comment_mentions_retry(self):
        addendum = _addendum(status=AddendumStatus.IN_REVIEW)
        tracker = _Tracker([addendum])
        scm = _make_scm(state="closed")
        poll_addendum_pr(tracker, "FOO-10", addendum, scm=scm, repo="org/repo")
        msg = tracker.comments[0]["message"].lower()
        assert "retry" in msg

    def test_closed_comment_says_no_replacement_pr(self):
        addendum = _addendum(status=AddendumStatus.IN_REVIEW)
        tracker = _Tracker([addendum])
        scm = _make_scm(state="closed")
        poll_addendum_pr(tracker, "FOO-10", addendum, scm=scm, repo="org/repo")
        msg = tracker.comments[0]["message"].lower()
        # Should mention that no replacement PR was opened
        assert "replacement" in msg or "automatically" in msg

    def test_duplicate_closed_poll_is_idempotent_no_second_write(self):
        """Calling poll_addendum_pr twice on a closed PR does not re-write or re-comment."""
        addendum = _addendum(status=AddendumStatus.IN_REVIEW, error=None)
        tracker = _Tracker([addendum])
        scm = _make_scm(state="closed")
        # First poll: sets error
        result1 = poll_addendum_pr(tracker, "FOO-10", addendum, scm=scm, repo="org/repo")
        writes_after_first = tracker.writes
        comments_after_first = len(tracker.comments)

        # Second poll: error already starts with CLOSED_UNMERGED_ERROR_PREFIX
        result2 = poll_addendum_pr(tracker, "FOO-10", result1, scm=scm, repo="org/repo")
        # No additional writes or comments
        assert tracker.writes == writes_after_first
        assert len(tracker.comments) == comments_after_first
        assert result2.status == AddendumStatus.IN_REVIEW

    def test_closed_does_not_create_replacement_pr(self):
        """No new PR should be opened after a closed-unmerged PR."""
        addendum = _addendum(status=AddendumStatus.IN_REVIEW)
        tracker = _Tracker([addendum])
        scm = _make_scm(state="closed")
        poll_addendum_pr(tracker, "FOO-10", addendum, scm=scm, repo="org/repo")
        # find_pr_for_branch called to check state, but create_review must not be called
        assert not scm.create_review.called

    def test_closed_does_not_create_child_task(self):
        addendum = _addendum(status=AddendumStatus.IN_REVIEW)
        tracker = _Tracker([addendum])
        scm = _make_scm(state="closed")
        poll_addendum_pr(tracker, "FOO-10", addendum, scm=scm, repo="org/repo")
        assert tracker.create_issue_calls == 0

    def test_closed_does_not_alter_source_task_status(self):
        addendum = _addendum(status=AddendumStatus.IN_REVIEW)
        tracker = _Tracker([addendum])
        scm = _make_scm(state="closed")
        poll_addendum_pr(tracker, "FOO-10", addendum, scm=scm, repo="org/repo")
        assert tracker.update_issue_calls == 0

    def test_closed_writes_to_tracker(self):
        addendum = _addendum(status=AddendumStatus.IN_REVIEW)
        tracker = _Tracker([addendum])
        scm = _make_scm(state="closed")
        tracker.writes = 0
        poll_addendum_pr(tracker, "FOO-10", addendum, scm=scm, repo="org/repo")
        assert tracker.writes == 1


# ---------------------------------------------------------------------------
# Tests: immutable commits across all transitions
# ---------------------------------------------------------------------------


class TestCommitImmutability:
    """Commits must never be changed by poll_addendum_pr regardless of PR state."""

    def _assert_commits_unchanged(self, state: str) -> None:
        original_commits = [_COMMIT_A, _COMMIT_B]
        addendum = _addendum(
            status=AddendumStatus.IN_REVIEW, commits=list(original_commits)
        )
        tracker = _Tracker([addendum])
        scm = _make_scm(state=state)
        result = poll_addendum_pr(
            tracker, "FOO-10", addendum, scm=scm, repo="org/repo", now=NOW
        )
        assert result.commits == original_commits, (
            f"Commits changed after poll with PR state={state!r}"
        )

    def test_commits_unchanged_after_merged_pr(self):
        self._assert_commits_unchanged("merged")

    def test_commits_unchanged_after_open_pr(self):
        self._assert_commits_unchanged("open")

    def test_commits_unchanged_after_closed_pr(self):
        self._assert_commits_unchanged("closed")

    def test_commits_unchanged_after_retry_simulation(self):
        """Simulate retry → reopen → re-poll; commits must stay the same throughout."""
        original_commits = [_COMMIT_A, _COMMIT_B]
        addendum = _addendum(status=AddendumStatus.IN_REVIEW, commits=list(original_commits))
        tracker = _Tracker([addendum])

        # Step 1: Closed PR detected
        scm = _make_scm(state="closed")
        closed_result = poll_addendum_pr(tracker, "FOO-10", addendum, scm=scm, repo="org/repo")
        assert closed_result.commits == original_commits

        # Step 2: Simulate retry (in_review → open via AddendumRepository.transition)
        repo = AddendumRepository(tracker)
        after_retry = repo.transition(
            "FOO-10", addendum.id, AddendumStatus.OPEN, error=None, claimed_by=None
        )
        retried = next(a for a in after_retry if a.id == addendum.id)
        assert retried.commits == original_commits

    def test_only_one_active_addendum_per_branch_after_poll(self):
        """The in-place error update must not introduce duplicate addendums."""
        addendum = _addendum(status=AddendumStatus.IN_REVIEW)
        tracker = _Tracker([addendum])
        scm = _make_scm(state="closed")
        poll_addendum_pr(tracker, "FOO-10", addendum, scm=scm, repo="org/repo")
        all_addendums = AddendumRepository(tracker).read("FOO-10")
        active = [a for a in all_addendums if a.status.is_active]
        assert len(active) == 1


# ---------------------------------------------------------------------------
# Tests: _handle_merged and _handle_closed directly
# ---------------------------------------------------------------------------


class TestHandleMergedDirect:
    def test_race_condition_already_merged_does_not_raise(self):
        """If addendum is already merged, InvalidTransitionError is caught."""
        addendum = _addendum(status=AddendumStatus.MERGED)
        tracker = _Tracker([addendum])
        # Should not raise even with an already-merged addendum
        result = _handle_merged(tracker, "FOO-10", addendum, now=NOW)
        # Returns the stored merged addendum
        assert result.status == AddendumStatus.MERGED

    def test_handle_merged_write_failure_returns_original(self):
        addendum = _addendum(status=AddendumStatus.IN_REVIEW)
        bad_tracker = MagicMock()
        bad_tracker.get_metadata.return_value = {
            "oompah.release_addendums": [addendum.to_raw()]
        }
        bad_tracker.set_metadata_field.side_effect = RuntimeError("write error")
        result = _handle_merged(bad_tracker, "FOO-10", addendum, now=NOW)
        # Returns the original addendum unchanged
        assert result is addendum


class TestHandleClosedDirect:
    def test_already_closed_error_is_idempotent(self):
        existing_error = f"{CLOSED_UNMERGED_ERROR_PREFIX} {_PR_URL}"
        addendum = _addendum(status=AddendumStatus.IN_REVIEW, error=existing_error)
        tracker = _Tracker([addendum])
        result = _handle_closed(tracker, "FOO-10", addendum)
        # No write: already marked
        assert tracker.writes == 0
        assert result.error == existing_error

    def test_handle_closed_write_failure_returns_original(self):
        addendum = _addendum(status=AddendumStatus.IN_REVIEW, error=None)
        bad_tracker = MagicMock()
        bad_tracker.get_metadata.return_value = {
            "oompah.release_addendums": [addendum.to_raw()]
        }
        bad_tracker.set_metadata_field.side_effect = RuntimeError("write error")
        result = _handle_closed(bad_tracker, "FOO-10", addendum)
        assert result is addendum
