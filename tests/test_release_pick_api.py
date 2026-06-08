"""Tests for the release-pick API helper module (TASK-456.1, TASK-456.4).

Covers:
  - _extract_pr_id: happy path, edge cases, None/empty input
  - _normalise_entry: all fields, derived pr_id, validation fields
  - get_release_pick_detail: empty metadata, backports only, backport_of only,
    both present, with/without project validation
  - update_release_pick_entry: add new entry, update existing, branch validation,
    allow_new=False guard, empty branch guard
  - update_release_picks_bulk: single/multiple entries, validation failures,
    empty branch error, merge with existing
  - get_epic_release_pick_matrix: no children, single child, multi-child,
    missing branches filled with None, branch validation
  - apply_release_picks_to_all_children: all waiting, skip_children skipped,
    branch validation, empty branches error, no writes when unchanged
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, call

from oompah.release_pick_api import (
    _extract_pr_id,
    _normalise_entry,
    get_release_pick_detail,
    update_release_pick_entry,
    update_release_picks_bulk,
    get_epic_release_pick_matrix,
    apply_release_picks_to_all_children,
)
from oompah.release_pick_schema import BackportEntry, ReleasePick
from oompah.models import Issue, Project
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_tracker(meta: dict | None = None) -> MagicMock:
    """Return a minimal mock tracker with get_metadata / set_metadata_field."""
    tracker = MagicMock()
    tracker.get_metadata = MagicMock(return_value=meta or {})
    tracker.set_metadata_field = MagicMock()
    return tracker


def _make_project(
    *,
    branches: list[str] | None = None,
    default_branch: str = "main",
) -> Project:
    """Return a minimal Project for validation tests."""
    return Project(
        id="proj-1",
        name="Test Project",
        repo_url="https://github.com/org/repo",
        repo_path="/tmp/repo",
        branches=branches or ["release/*", "hotfix/*", "main"],
        default_branch=default_branch,
    )


# ---------------------------------------------------------------------------
# _extract_pr_id
# ---------------------------------------------------------------------------


class TestExtractPrId:
    def test_standard_github_url(self):
        assert _extract_pr_id("https://github.com/org/repo/pull/42") == "42"

    def test_url_with_trailing_slash(self):
        assert _extract_pr_id("https://github.com/org/repo/pull/99/") == "99"

    def test_url_with_query_string(self):
        assert _extract_pr_id("https://github.com/org/repo/pull/7?tab=files") == "7"

    def test_url_with_fragment(self):
        assert _extract_pr_id("https://github.com/org/repo/pull/13#discussion") == "13"

    def test_large_pr_number(self):
        assert _extract_pr_id("https://github.com/org/repo/pull/99999") == "99999"

    def test_none_returns_none(self):
        assert _extract_pr_id(None) is None

    def test_empty_string_returns_none(self):
        assert _extract_pr_id("") is None

    def test_non_pr_url_returns_none(self):
        assert _extract_pr_id("https://github.com/org/repo/issues/5") is None

    def test_bare_branch_name_returns_none(self):
        assert _extract_pr_id("release/1.0") is None


# ---------------------------------------------------------------------------
# _normalise_entry
# ---------------------------------------------------------------------------


class TestNormaliseEntry:
    def test_full_entry_no_validation(self):
        entry = BackportEntry(
            branch="release/1.0",
            status=ReleasePick.PR_OPEN,
            task_id="TASK-10.1",
            pr_url="https://github.com/org/repo/pull/42",
        )
        result = _normalise_entry(entry)
        assert result["branch"] == "release/1.0"
        assert result["status"] == "pr_open"
        assert result["task_id"] == "TASK-10.1"
        assert result["pr_url"] == "https://github.com/org/repo/pull/42"
        assert result["pr_id"] == "42"
        assert result["is_valid"] is True
        assert result["validation_error"] is None

    def test_minimal_entry_defaults(self):
        entry = BackportEntry(branch="release/2.0")
        result = _normalise_entry(entry)
        assert result["status"] == "waiting"
        assert result["task_id"] is None
        assert result["pr_url"] is None
        assert result["pr_id"] is None
        assert result["is_valid"] is True

    def test_with_failing_validation(self):
        from oompah.release_pick_validation import ReleaseBranchValidationResult

        entry = BackportEntry(branch="unknown-branch")
        validation = ReleaseBranchValidationResult(
            valid=False,
            target_branch="unknown-branch",
            reason="untracked_branch",
            error="Branch 'unknown-branch' does not match patterns",
        )
        result = _normalise_entry(entry, validation)
        assert result["is_valid"] is False
        assert "unknown-branch" in result["validation_error"]

    def test_with_passing_validation(self):
        from oompah.release_pick_validation import ReleaseBranchValidationResult

        entry = BackportEntry(branch="release/3.0")
        validation = ReleaseBranchValidationResult(valid=True, target_branch="release/3.0")
        result = _normalise_entry(entry, validation)
        assert result["is_valid"] is True
        assert result["validation_error"] is None


# ---------------------------------------------------------------------------
# get_release_pick_detail
# ---------------------------------------------------------------------------


class TestGetReleasePickDetail:
    def test_empty_metadata(self):
        tracker = _make_tracker({})
        result = get_release_pick_detail(tracker, "TASK-1")
        assert result["identifier"] == "TASK-1"
        assert result["backports"] == []
        assert result["backport_of"] is None

    def test_none_metadata(self):
        tracker = _make_tracker(None)
        result = get_release_pick_detail(tracker, "TASK-2")
        assert result["backports"] == []
        assert result["backport_of"] is None

    def test_empty_identifier_raises(self):
        tracker = _make_tracker()
        with pytest.raises(ValueError, match="identifier"):
            get_release_pick_detail(tracker, "")

    def test_backports_scalar_string(self):
        tracker = _make_tracker({"oompah.backports": "release/1.0"})
        result = get_release_pick_detail(tracker, "TASK-3")
        assert len(result["backports"]) == 1
        assert result["backports"][0]["branch"] == "release/1.0"
        assert result["backports"][0]["status"] == "waiting"

    def test_backports_list_of_strings(self):
        tracker = _make_tracker({"oompah.backports": ["release/1.0", "release/2.0"]})
        result = get_release_pick_detail(tracker, "TASK-4")
        assert len(result["backports"]) == 2
        branches = [e["branch"] for e in result["backports"]]
        assert "release/1.0" in branches
        assert "release/2.0" in branches

    def test_backports_full_dict(self):
        tracker = _make_tracker({
            "oompah.backports": [
                {
                    "branch": "release/1.0",
                    "status": "pr_open",
                    "task_id": "TASK-5.1",
                    "pr_url": "https://github.com/org/repo/pull/17",
                }
            ]
        })
        result = get_release_pick_detail(tracker, "TASK-5")
        entry = result["backports"][0]
        assert entry["branch"] == "release/1.0"
        assert entry["status"] == "pr_open"
        assert entry["task_id"] == "TASK-5.1"
        assert entry["pr_url"] == "https://github.com/org/repo/pull/17"
        assert entry["pr_id"] == "17"

    def test_backport_of_scalar(self):
        tracker = _make_tracker({"oompah.backport_of": "TASK-100"})
        result = get_release_pick_detail(tracker, "TASK-100.1")
        assert result["backport_of"] is not None
        assert result["backport_of"]["source"] == "TASK-100"
        assert result["backport_of"]["status"] == "waiting"

    def test_backport_of_dict(self):
        tracker = _make_tracker({
            "oompah.backport_of": {"source": "TASK-200", "status": "cherry_picking"}
        })
        result = get_release_pick_detail(tracker, "TASK-200.1")
        assert result["backport_of"]["source"] == "TASK-200"
        assert result["backport_of"]["status"] == "cherry_picking"

    def test_both_backports_and_backport_of(self):
        tracker = _make_tracker({
            "oompah.backports": [{"branch": "release/1.0", "status": "merged"}],
            "oompah.backport_of": "TASK-50",
        })
        result = get_release_pick_detail(tracker, "TASK-99")
        assert len(result["backports"]) == 1
        assert result["backport_of"]["source"] == "TASK-50"

    def test_with_project_valid_branches(self):
        tracker = _make_tracker({
            "oompah.backports": ["release/1.0", "release/2.0"]
        })
        project = _make_project(branches=["release/*"])
        result = get_release_pick_detail(tracker, "TASK-6", project=project)
        for entry in result["backports"]:
            assert entry["is_valid"] is True

    def test_with_project_invalid_branch(self):
        tracker = _make_tracker({
            "oompah.backports": ["release/1.0", "unknown-branch"]
        })
        project = _make_project(branches=["release/*"])
        result = get_release_pick_detail(tracker, "TASK-7", project=project)
        by_branch = {e["branch"]: e for e in result["backports"]}
        assert by_branch["release/1.0"]["is_valid"] is True
        assert by_branch["unknown-branch"]["is_valid"] is False
        assert by_branch["unknown-branch"]["validation_error"] is not None


# ---------------------------------------------------------------------------
# update_release_pick_entry
# ---------------------------------------------------------------------------


class TestUpdateReleasePickEntry:
    def test_add_new_entry_to_empty_list(self):
        tracker = _make_tracker({})
        result = update_release_pick_entry(
            tracker, "TASK-10", branch="release/1.0", status="waiting"
        )
        tracker.set_metadata_field.assert_called_once()
        call_args = tracker.set_metadata_field.call_args
        assert call_args[0][1] == "oompah.backports"
        assert result["identifier"] == "TASK-10"
        assert len(result["backports"]) == 1
        assert result["backports"][0]["branch"] == "release/1.0"

    def test_add_new_entry_with_all_fields(self):
        tracker = _make_tracker({})
        update_release_pick_entry(
            tracker,
            "TASK-11",
            branch="release/2.0",
            status="pr_open",
            task_id="TASK-11.1",
            pr_url="https://github.com/org/repo/pull/99",
        )
        call_args = tracker.set_metadata_field.call_args
        written = call_args[0][2]
        assert len(written) == 1
        # Written as dict because non-default fields are set
        entry_raw = written[0]
        assert isinstance(entry_raw, dict)
        assert entry_raw["branch"] == "release/2.0"
        assert entry_raw["status"] == "pr_open"
        assert entry_raw["task_id"] == "TASK-11.1"

    def test_update_existing_status(self):
        existing_meta = {
            "oompah.backports": [
                {"branch": "release/1.0", "status": "task_created", "task_id": "TASK-12.1"}
            ]
        }
        tracker = _make_tracker(existing_meta)
        result = update_release_pick_entry(
            tracker, "TASK-12", branch="release/1.0", status="cherry_picking"
        )
        call_args = tracker.set_metadata_field.call_args
        written = call_args[0][2]
        assert written[0]["status"] == "cherry_picking"
        # task_id was not overwritten
        assert written[0]["task_id"] == "TASK-12.1"

    def test_update_preserves_other_entries(self):
        existing_meta = {
            "oompah.backports": [
                {"branch": "release/1.0", "status": "waiting"},
                {"branch": "release/2.0", "status": "merged"},
            ]
        }
        tracker = _make_tracker(existing_meta)
        result = update_release_pick_entry(
            tracker, "TASK-13", branch="release/1.0", status="task_created"
        )
        call_args = tracker.set_metadata_field.call_args
        written = call_args[0][2]
        assert len(written) == 2
        by_branch = {e["branch"] if isinstance(e, dict) else e: e for e in written}
        assert by_branch["release/2.0"]["status"] == "merged"

    def test_empty_branch_raises(self):
        tracker = _make_tracker({})
        with pytest.raises(ValueError, match="branch must not be empty"):
            update_release_pick_entry(tracker, "TASK-14", branch="")

    def test_none_branch_raises(self):
        tracker = _make_tracker({})
        with pytest.raises(ValueError, match="branch must not be empty"):
            update_release_pick_entry(tracker, "TASK-15", branch=None)

    def test_allow_new_false_raises_when_not_found(self):
        tracker = _make_tracker({})
        with pytest.raises(ValueError, match="No existing backport entry"):
            update_release_pick_entry(
                tracker, "TASK-16", branch="release/1.0", allow_new=False
            )

    def test_allow_new_false_succeeds_when_found(self):
        existing_meta = {
            "oompah.backports": [{"branch": "release/1.0", "status": "waiting"}]
        }
        tracker = _make_tracker(existing_meta)
        # Should not raise
        update_release_pick_entry(
            tracker, "TASK-17", branch="release/1.0", status="task_created", allow_new=False
        )
        tracker.set_metadata_field.assert_called_once()

    def test_with_valid_project_branch(self):
        tracker = _make_tracker({})
        project = _make_project(branches=["release/*"])
        result = update_release_pick_entry(
            tracker, "TASK-18", branch="release/1.0", project=project
        )
        assert result["backports"][0]["is_valid"] is True

    def test_with_invalid_project_branch_raises(self):
        tracker = _make_tracker({})
        project = _make_project(branches=["release/*"])
        with pytest.raises(ValueError, match="Branch validation failed"):
            update_release_pick_entry(
                tracker, "TASK-19", branch="unknown-branch", project=project
            )

    def test_pr_id_derived_in_result(self):
        tracker = _make_tracker({})
        result = update_release_pick_entry(
            tracker,
            "TASK-20",
            branch="release/1.0",
            pr_url="https://github.com/org/repo/pull/55",
        )
        assert result["backports"][0]["pr_id"] == "55"


# ---------------------------------------------------------------------------
# update_release_picks_bulk
# ---------------------------------------------------------------------------


class TestUpdateReleasePicksBulk:
    def test_empty_backports_raises(self):
        tracker = _make_tracker({})
        with pytest.raises(ValueError, match="must not be empty"):
            update_release_picks_bulk(tracker, "TASK-30", backports=[])

    def test_entry_missing_branch_raises(self):
        tracker = _make_tracker({})
        with pytest.raises(ValueError, match="non-empty 'branch' key"):
            update_release_picks_bulk(
                tracker, "TASK-31", backports=[{"status": "waiting"}]
            )

    def test_single_new_entry(self):
        tracker = _make_tracker({})
        result = update_release_picks_bulk(
            tracker,
            "TASK-32",
            backports=[{"branch": "release/1.0", "status": "pr_open", "task_id": "TASK-32.1"}],
        )
        assert len(result["backports"]) == 1
        assert result["backports"][0]["branch"] == "release/1.0"
        assert result["backports"][0]["status"] == "pr_open"

    def test_multiple_new_entries(self):
        tracker = _make_tracker({})
        result = update_release_picks_bulk(
            tracker,
            "TASK-33",
            backports=[
                {"branch": "release/1.0"},
                {"branch": "release/2.0", "status": "task_created"},
            ],
        )
        assert len(result["backports"]) == 2

    def test_merge_with_existing_entries(self):
        existing_meta = {
            "oompah.backports": [
                {"branch": "release/1.0", "status": "waiting"},
                {"branch": "release/2.0", "status": "merged"},
            ]
        }
        tracker = _make_tracker(existing_meta)
        result = update_release_picks_bulk(
            tracker,
            "TASK-34",
            backports=[
                {"branch": "release/1.0", "status": "task_created"},
                {"branch": "release/3.0"},
            ],
        )
        # Should have 3 entries total: updated 1.0, preserved 2.0, new 3.0
        assert len(result["backports"]) == 3

    def test_branch_validation_success(self):
        tracker = _make_tracker({})
        project = _make_project(branches=["release/*"])
        result = update_release_picks_bulk(
            tracker,
            "TASK-35",
            backports=[
                {"branch": "release/1.0"},
                {"branch": "release/2.0"},
            ],
            project=project,
        )
        for entry in result["backports"]:
            assert entry["is_valid"] is True

    def test_branch_validation_failure_raises(self):
        tracker = _make_tracker({})
        project = _make_project(branches=["release/*"])
        with pytest.raises(ValueError, match="Branch validation failed"):
            update_release_picks_bulk(
                tracker,
                "TASK-36",
                backports=[
                    {"branch": "release/1.0"},
                    {"branch": "bad-branch"},
                ],
                project=project,
            )
        # No write should occur
        tracker.set_metadata_field.assert_not_called()

    def test_pr_url_and_pr_id_in_result(self):
        tracker = _make_tracker({})
        result = update_release_picks_bulk(
            tracker,
            "TASK-37",
            backports=[
                {
                    "branch": "release/1.0",
                    "pr_url": "https://github.com/org/repo/pull/77",
                }
            ],
        )
        entry = result["backports"][0]
        assert entry["pr_url"] == "https://github.com/org/repo/pull/77"
        assert entry["pr_id"] == "77"

    def test_null_task_id_does_not_clear_existing(self):
        """When task_id is not in the update dict, existing value is preserved."""
        existing_meta = {
            "oompah.backports": [
                {"branch": "release/1.0", "status": "cherry_picking", "task_id": "TASK-38.1"}
            ]
        }
        tracker = _make_tracker(existing_meta)
        result = update_release_picks_bulk(
            tracker,
            "TASK-38",
            backports=[{"branch": "release/1.0", "status": "pr_open"}],
        )
        # task_id omitted from update, existing value should be preserved
        assert result["backports"][0]["task_id"] == "TASK-38.1"


# ---------------------------------------------------------------------------
# Helpers for epic matrix tests
# ---------------------------------------------------------------------------


def _make_child(identifier: str, title: str = "Child task", state: str = "open") -> Issue:
    """Return a minimal Issue representing a child task."""
    return Issue(
        id=identifier,
        identifier=identifier,
        title=title,
        state=state,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )


def _make_epic_tracker(children: list, meta_by_id: dict | None = None) -> MagicMock:
    """Return a mock tracker wired for epic matrix tests.

    Args:
        children: List of Issue objects returned by fetch_children.
        meta_by_id: Dict mapping child identifier → metadata dict.  Missing
                    identifiers default to an empty dict (no backports).
    """
    meta_by_id = meta_by_id or {}
    tracker = MagicMock()
    tracker.fetch_children = MagicMock(return_value=children)
    tracker.get_metadata = MagicMock(
        side_effect=lambda ident: meta_by_id.get(ident, {})
    )
    tracker.set_metadata_field = MagicMock()
    return tracker


# ---------------------------------------------------------------------------
# get_epic_release_pick_matrix
# ---------------------------------------------------------------------------


class TestGetEpicReleasePickMatrix:
    def test_empty_epic_returns_empty_matrix(self):
        tracker = _make_epic_tracker(children=[])
        result = get_epic_release_pick_matrix(tracker, "TASK-456")
        assert result["epic_identifier"] == "TASK-456"
        assert result["branches"] == []
        assert result["rows"] == []

    def test_empty_identifier_raises(self):
        tracker = _make_epic_tracker(children=[])
        with pytest.raises(ValueError, match="epic_identifier"):
            get_epic_release_pick_matrix(tracker, "")

    def test_single_child_no_backports(self):
        child = _make_child("TASK-456.1", title="First child")
        tracker = _make_epic_tracker([child])
        result = get_epic_release_pick_matrix(tracker, "TASK-456")
        assert result["branches"] == []
        assert len(result["rows"]) == 1
        row = result["rows"][0]
        assert row["identifier"] == "TASK-456.1"
        assert row["title"] == "First child"
        assert row["entries"] == {}

    def test_single_child_with_backports(self):
        child = _make_child("TASK-456.1")
        meta = {
            "TASK-456.1": {
                "oompah.backports": [
                    {"branch": "release/1.0", "status": "pr_open"},
                    {"branch": "release/2.0", "status": "waiting"},
                ]
            }
        }
        tracker = _make_epic_tracker([child], meta)
        result = get_epic_release_pick_matrix(tracker, "TASK-456")
        assert result["branches"] == ["release/1.0", "release/2.0"]
        row = result["rows"][0]
        assert row["entries"]["release/1.0"]["status"] == "pr_open"
        assert row["entries"]["release/2.0"]["status"] == "waiting"

    def test_multiple_children_branches_merged(self):
        """All unique branches across children appear as columns."""
        child1 = _make_child("TASK-456.1")
        child2 = _make_child("TASK-456.2")
        meta = {
            "TASK-456.1": {"oompah.backports": "release/1.0"},
            "TASK-456.2": {"oompah.backports": ["release/1.0", "release/2.0"]},
        }
        tracker = _make_epic_tracker([child1, child2], meta)
        result = get_epic_release_pick_matrix(tracker, "TASK-456")
        assert result["branches"] == ["release/1.0", "release/2.0"]
        assert len(result["rows"]) == 2

    def test_missing_branch_for_child_is_none(self):
        """A child missing an entry for a branch gets None in that column."""
        child1 = _make_child("TASK-456.1")
        child2 = _make_child("TASK-456.2")
        meta = {
            "TASK-456.1": {"oompah.backports": "release/1.0"},
            "TASK-456.2": {"oompah.backports": "release/2.0"},
        }
        tracker = _make_epic_tracker([child1, child2], meta)
        result = get_epic_release_pick_matrix(tracker, "TASK-456")
        assert result["branches"] == ["release/1.0", "release/2.0"]
        rows_by_id = {r["identifier"]: r for r in result["rows"]}
        assert rows_by_id["TASK-456.1"]["entries"]["release/2.0"] is None
        assert rows_by_id["TASK-456.2"]["entries"]["release/1.0"] is None

    def test_branches_sorted_alphabetically(self):
        child = _make_child("TASK-456.1")
        meta = {
            "TASK-456.1": {
                "oompah.backports": ["release/3.0", "release/1.0", "release/2.0"]
            }
        }
        tracker = _make_epic_tracker([child], meta)
        result = get_epic_release_pick_matrix(tracker, "TASK-456")
        assert result["branches"] == ["release/1.0", "release/2.0", "release/3.0"]

    def test_child_state_preserved_in_row(self):
        child = _make_child("TASK-456.1", state="done")
        tracker = _make_epic_tracker([child])
        result = get_epic_release_pick_matrix(tracker, "TASK-456")
        assert result["rows"][0]["state"] == "done"

    def test_with_project_validation(self):
        child = _make_child("TASK-456.1")
        meta = {
            "TASK-456.1": {
                "oompah.backports": ["release/1.0", "bad-branch"]
            }
        }
        tracker = _make_epic_tracker([child], meta)
        project = _make_project(branches=["release/*"])
        result = get_epic_release_pick_matrix(tracker, "TASK-456", project=project)
        rows_by_id = {r["identifier"]: r for r in result["rows"]}
        entries = rows_by_id["TASK-456.1"]["entries"]
        assert entries["release/1.0"]["is_valid"] is True
        assert entries["bad-branch"]["is_valid"] is False
        assert entries["bad-branch"]["validation_error"] is not None

    def test_entry_has_all_normalised_fields(self):
        child = _make_child("TASK-456.1")
        meta = {
            "TASK-456.1": {
                "oompah.backports": [
                    {
                        "branch": "release/1.0",
                        "status": "pr_open",
                        "task_id": "TASK-456.1.1",
                        "pr_url": "https://github.com/org/repo/pull/42",
                    }
                ]
            }
        }
        tracker = _make_epic_tracker([child], meta)
        result = get_epic_release_pick_matrix(tracker, "TASK-456")
        entry = result["rows"][0]["entries"]["release/1.0"]
        assert entry["branch"] == "release/1.0"
        assert entry["status"] == "pr_open"
        assert entry["task_id"] == "TASK-456.1.1"
        assert entry["pr_url"] == "https://github.com/org/repo/pull/42"
        assert entry["pr_id"] == "42"
        assert entry["is_valid"] is True
        assert entry["validation_error"] is None


# ---------------------------------------------------------------------------
# apply_release_picks_to_all_children
# ---------------------------------------------------------------------------


class TestApplyReleasePicksToAllChildren:
    def test_empty_epic_identifier_raises(self):
        tracker = _make_epic_tracker(children=[])
        with pytest.raises(ValueError, match="epic_identifier"):
            apply_release_picks_to_all_children(tracker, "", branches=["release/1.0"])

    def test_empty_branches_raises(self):
        tracker = _make_epic_tracker(children=[])
        with pytest.raises(ValueError, match="branches"):
            apply_release_picks_to_all_children(tracker, "TASK-456", branches=[])

    def test_blank_branch_name_raises(self):
        child = _make_child("TASK-456.1")
        tracker = _make_epic_tracker([child])
        with pytest.raises(ValueError, match="non-empty"):
            apply_release_picks_to_all_children(tracker, "TASK-456", branches=[""])

    def test_applies_waiting_to_all_children(self):
        child1 = _make_child("TASK-456.1")
        child2 = _make_child("TASK-456.2")
        tracker = _make_epic_tracker([child1, child2])
        result = apply_release_picks_to_all_children(
            tracker, "TASK-456", branches=["release/1.0"]
        )
        # Both children should have had set_metadata_field called
        assert tracker.set_metadata_field.call_count == 2
        # Result is the updated matrix
        assert result["epic_identifier"] == "TASK-456"

    def test_skip_children_get_skipped_status(self):
        child1 = _make_child("TASK-456.1")
        child2 = _make_child("TASK-456.2")
        tracker = _make_epic_tracker([child1, child2])
        apply_release_picks_to_all_children(
            tracker,
            "TASK-456",
            branches=["release/1.0"],
            skip_children=["TASK-456.2"],
        )
        # Find the call for TASK-456.2
        calls_by_id: dict[str, list] = {}
        for c in tracker.set_metadata_field.call_args_list:
            ident = c[0][0]
            calls_by_id.setdefault(ident, []).append(c)
        assert "TASK-456.2" in calls_by_id
        written = calls_by_id["TASK-456.2"][0][0][2]  # third positional arg
        # Written list should have a dict entry with status=skipped
        assert any(
            (e if isinstance(e, dict) else {}).get("status") == "skipped"
            for e in written
        )

    def test_non_skipped_child_gets_waiting_status(self):
        child1 = _make_child("TASK-456.1")
        tracker = _make_epic_tracker([child1])
        apply_release_picks_to_all_children(
            tracker,
            "TASK-456",
            branches=["release/1.0"],
        )
        written = tracker.set_metadata_field.call_args[0][2]
        # Simple string (waiting is default compact form) or dict with waiting
        entry = written[0]
        if isinstance(entry, dict):
            assert entry.get("status", "waiting") == "waiting"
        else:
            assert entry == "release/1.0"

    def test_no_write_when_branch_already_exists_and_not_skipped(self):
        """No set_metadata_field call when all branches already present and not skipped."""
        child = _make_child("TASK-456.1")
        meta = {
            "TASK-456.1": {"oompah.backports": "release/1.0"}
        }
        tracker = _make_epic_tracker([child], meta)
        apply_release_picks_to_all_children(
            tracker, "TASK-456", branches=["release/1.0"]
        )
        # No write needed — entry already exists
        tracker.set_metadata_field.assert_not_called()

    def test_branch_validation_failure_prevents_all_writes(self):
        child = _make_child("TASK-456.1")
        tracker = _make_epic_tracker([child])
        project = _make_project(branches=["release/*"])
        with pytest.raises(ValueError, match="Branch validation failed"):
            apply_release_picks_to_all_children(
                tracker,
                "TASK-456",
                branches=["release/1.0", "bad-branch"],
                project=project,
            )
        tracker.set_metadata_field.assert_not_called()

    def test_skipping_existing_entry_updates_status(self):
        """Skipping a child with an existing 'waiting' entry changes it to 'skipped'."""
        child = _make_child("TASK-456.1")
        meta = {
            "TASK-456.1": {
                "oompah.backports": [{"branch": "release/1.0", "status": "waiting"}]
            }
        }
        tracker = _make_epic_tracker([child], meta)
        apply_release_picks_to_all_children(
            tracker,
            "TASK-456",
            branches=["release/1.0"],
            skip_children=["TASK-456.1"],
        )
        tracker.set_metadata_field.assert_called_once()
        written = tracker.set_metadata_field.call_args[0][2]
        entry = written[0]
        if isinstance(entry, dict):
            assert entry["status"] == "skipped"

    def test_returns_matrix_with_applied_branches(self):
        child = _make_child("TASK-456.1")
        tracker = _make_epic_tracker([child])
        # After apply the tracker.get_metadata for child should return the
        # updated metadata — simulate by configuring side_effect to return
        # the written value on the second call.
        call_count = {"n": 0}
        def _meta(ident):
            call_count["n"] += 1
            if call_count["n"] <= 1:
                return {}
            # Return what was written
            if tracker.set_metadata_field.called:
                written = tracker.set_metadata_field.call_args[0][2]
                return {"oompah.backports": written}
            return {}
        tracker.get_metadata.side_effect = _meta
        result = apply_release_picks_to_all_children(
            tracker, "TASK-456", branches=["release/1.0"]
        )
        assert result["epic_identifier"] == "TASK-456"
        # "release/1.0" should appear in the branches list returned by matrix
        assert "release/1.0" in result["branches"]

    def test_multiple_branches_applied(self):
        child = _make_child("TASK-456.1")
        tracker = _make_epic_tracker([child])
        apply_release_picks_to_all_children(
            tracker, "TASK-456", branches=["release/1.0", "release/2.0"]
        )
        tracker.set_metadata_field.assert_called_once()
        written = tracker.set_metadata_field.call_args[0][2]
        # Both branches should be in the written list
        written_branches = [
            (e["branch"] if isinstance(e, dict) else e) for e in written
        ]
        assert "release/1.0" in written_branches
        assert "release/2.0" in written_branches
