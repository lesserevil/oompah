"""Tests for oompah's canonical Backlog.md statuses."""

from oompah.statuses import (
    ARCHIVED,
    BACKLOG,
    DONE,
    DUPLICATE_CANDIDATE,
    IN_PROGRESS,
    MERGED,
    NEEDS_ANSWER,
    NEEDS_CI_FIX,
    NEEDS_REBASE,
    OPEN,
    canonicalize_status,
    is_dispatchable_status,
    is_terminal_status,
)


def test_legacy_statuses_canonicalize_to_backlog_lifecycle_statuses():
    assert canonicalize_status("To Do") == BACKLOG
    assert canonicalize_status("deferred") == BACKLOG
    assert canonicalize_status("open") == OPEN
    assert canonicalize_status("in_progress") == IN_PROGRESS
    assert canonicalize_status("asking_question") == NEEDS_ANSWER
    assert canonicalize_status("ci-fix") == NEEDS_CI_FIX
    assert canonicalize_status("merge-conflict") == NEEDS_REBASE
    assert canonicalize_status("duplicate-candidate") == DUPLICATE_CANDIDATE
    assert canonicalize_status("closed") == DONE
    assert canonicalize_status("merged") == MERGED
    assert canonicalize_status("archive:yes") == ARCHIVED


def test_dispatchable_and_terminal_status_sets_are_explicit():
    assert is_dispatchable_status("Open")
    assert is_dispatchable_status("Needs CI Fix")
    assert is_dispatchable_status("Needs Rebase")
    assert not is_dispatchable_status("Backlog")
    assert not is_dispatchable_status("Needs Answer")

    assert is_terminal_status("Done")
    assert is_terminal_status("Merged")
    assert is_terminal_status("Archived")
    assert not is_terminal_status("In Progress")
