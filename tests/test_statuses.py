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


# ---------------------------------------------------------------------------
# epic_rollup_state / more_advanced_status (epic state derived from children)
# ---------------------------------------------------------------------------

from oompah.statuses import epic_rollup_state, more_advanced_status  # noqa: E402


def test_epic_rollup_all_backlog_is_backlog():
    assert epic_rollup_state(["Backlog", "Backlog"]) == "Backlog"


def test_epic_rollup_all_done_is_done():
    assert epic_rollup_state(["Done", "Done", "Done"]) == "Done"


def test_epic_rollup_done_plus_merged_is_done():
    # complete but not all merged -> Done (ready to merge). Mirrors epic-706.
    assert epic_rollup_state(["Done", "Done", "Merged", "Done"]) == "Done"


def test_epic_rollup_all_merged_is_merged():
    assert epic_rollup_state(["Merged", "Merged"]) == "Merged"


def test_epic_rollup_any_open_is_open():
    assert epic_rollup_state(["Backlog", "Open", "Done"]) == "Open"


def test_epic_rollup_in_progress_beats_open():
    assert epic_rollup_state(["Open", "In Progress"]) == "In Progress"


def test_epic_rollup_any_in_progress_is_in_progress():
    assert epic_rollup_state(["Backlog", "In Progress"]) == "In Progress"


def test_epic_rollup_needs_states_count_as_in_progress():
    assert epic_rollup_state(["Open", "Needs CI Fix"]) == "In Progress"


def test_epic_rollup_mixed_done_backlog_is_in_progress():
    # started but incomplete, nothing open/active -> In Progress
    assert epic_rollup_state(["Done", "Backlog"]) == "In Progress"


def test_epic_rollup_no_children_is_none():
    assert epic_rollup_state([]) is None


def test_more_advanced_status_picks_further_along():
    assert more_advanced_status("Open", "Done") == "Done"
    assert more_advanced_status("Open", "Backlog") == "Open"
    assert more_advanced_status("Merged", "Backlog") == "Merged"
    assert more_advanced_status("In Progress", "In Progress") == "In Progress"
