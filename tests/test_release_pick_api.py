"""Tests for the release-pick API helper module (TASK-456.1).

Covers:
  - _extract_pr_id: happy path, edge cases, None/empty input
  - _normalise_entry: all fields, derived pr_id, validation fields
  - get_release_pick_detail: empty metadata, backports only, backport_of only,
    both present, with/without project validation
  - update_release_pick_entry: add new entry, update existing, branch validation,
    allow_new=False guard, empty branch guard
  - update_release_picks_bulk: single/multiple entries, validation failures,
    empty branch error, merge with existing
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from oompah.release_pick_api import (
    _extract_pr_id,
    _normalise_entry,
    get_release_pick_detail,
    update_release_pick_entry,
    update_release_picks_bulk,
)
from oompah.release_pick_schema import BackportEntry, ReleasePick
from oompah.models import Project


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
