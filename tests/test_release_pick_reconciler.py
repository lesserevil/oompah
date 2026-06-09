"""Tests for the release-pick reconciliation loop (TASK-455.1).

Covers:
  - reconcile_release_picks: all advancement scenarios and idempotency
  - _build_child_index: correct indexing of backport children
  - _most_terminal_child / _best_live_child: selection helpers
  - _create_backport_child: title, labels, metadata written
  - Orchestrator._reconcile_release_picks_pass: wired into the background tick
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from unittest.mock import MagicMock, call, patch

import pytest

from oompah.models import Issue
from oompah.release_pick_reconciler import (
    ReconcileResult,
    _best_live_child,
    _build_child_index,
    _check_pr_outcome,
    _create_backport_child,
    _create_backport_worktree,
    _most_terminal_child,
    reconcile_release_picks,
)
from oompah.release_pick_schema import (
    BackportEntry,
    ReleasePick,
    backports_to_raw,
    parse_backports,
)
from oompah.scm import ReviewRequest
from oompah.statuses import ARCHIVED, BACKLOG, DONE, MERGED, NEEDS_HUMAN, OPEN


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _issue(
    identifier: str = "TASK-1",
    title: str = "Do something",
    state: str = OPEN,
    target_branch: str | None = None,
    parent_id: str | None = None,
    labels: list[str] | None = None,
    project_id: str | None = None,
) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=title,
        description="desc",
        state=state,
        target_branch=target_branch,
        parent_id=parent_id,
        labels=labels or [],
        project_id=project_id,
    )


def _make_tracker(
    all_issues: list[Issue] | None = None,
    metadata_map: dict[str, dict] | None = None,
    created_issues: list[Issue] | None = None,
) -> MagicMock:
    """Build a mock tracker with pre-configured return values.

    Args:
        all_issues: List returned by fetch_all_issues().
        metadata_map: Maps identifier → oompah metadata dict (returned by
            get_metadata()).
        created_issues: Issues returned in sequence by create_issue() calls.
    """
    tracker = MagicMock()
    tracker.fetch_all_issues.return_value = list(all_issues or [])
    tracker.fetch_issue_detail.return_value = None

    _meta = dict(metadata_map or {})

    def _get_meta(identifier: str) -> dict:
        return _meta.get(identifier, {})

    tracker.get_metadata.side_effect = _get_meta

    _created = list(created_issues or [])
    _create_idx = [0]

    def _create_issue(*args, **kwargs):
        idx = _create_idx[0]
        if idx < len(_created):
            issue = _created[idx]
            _create_idx[0] += 1
            return issue
        # Return a generic child if not enough pre-built ones
        auto_id = f"TASK-AUTO-{idx}"
        _create_idx[0] += 1
        return _issue(identifier=auto_id, title=kwargs.get("title", "child"))

    tracker.create_issue.side_effect = _create_issue
    return tracker


# ---------------------------------------------------------------------------
# ReconcileResult
# ---------------------------------------------------------------------------


class TestReconcileResult:
    def test_changed_false_when_empty(self):
        r = ReconcileResult()
        assert r.changed is False

    def test_changed_true_when_advanced(self):
        r = ReconcileResult(advanced=1)
        assert r.changed is True

    def test_changed_true_when_created(self):
        r = ReconcileResult(created=1)
        assert r.changed is True

    def test_changed_false_errors_only(self):
        r = ReconcileResult(errors=3)
        assert r.changed is False


# ---------------------------------------------------------------------------
# _most_terminal_child
# ---------------------------------------------------------------------------


class TestMostTerminalChild:
    def test_returns_none_for_empty_list(self):
        assert _most_terminal_child([]) is None

    def test_returns_none_for_all_live_children(self):
        children = [_issue(state=OPEN), _issue(identifier="B", state=BACKLOG)]
        assert _most_terminal_child(children) is None

    def test_returns_merged_over_done(self):
        merged = _issue(identifier="M", state=MERGED)
        done = _issue(identifier="D", state=DONE)
        result = _most_terminal_child([done, merged])
        assert result is merged

    def test_returns_archived_over_done(self):
        archived = _issue(identifier="A", state=ARCHIVED)
        done = _issue(identifier="D", state=DONE)
        result = _most_terminal_child([done, archived])
        assert result is archived

    def test_returns_merged_over_archived(self):
        merged = _issue(identifier="M", state=MERGED)
        archived = _issue(identifier="A", state=ARCHIVED)
        result = _most_terminal_child([archived, merged])
        assert result is merged

    def test_single_terminal_child(self):
        child = _issue(state=MERGED)
        assert _most_terminal_child([child]) is child


# ---------------------------------------------------------------------------
# _best_live_child
# ---------------------------------------------------------------------------


class TestBestLiveChild:
    def test_returns_none_for_empty_list(self):
        assert _best_live_child([]) is None

    def test_returns_none_for_all_terminal(self):
        children = [
            _issue(state=MERGED),
            _issue(identifier="B", state=DONE),
            _issue(identifier="C", state=ARCHIVED),
        ]
        assert _best_live_child(children) is None

    def test_returns_first_live_child(self):
        live = _issue(identifier="L", state=OPEN)
        terminal = _issue(identifier="T", state=MERGED)
        result = _best_live_child([live, terminal])
        assert result is live

    def test_returns_backlog_as_live(self):
        child = _issue(state=BACKLOG)
        assert _best_live_child([child]) is child


# ---------------------------------------------------------------------------
# _build_child_index
# ---------------------------------------------------------------------------


class TestBuildChildIndex:
    def test_empty_when_no_issues(self):
        tracker = _make_tracker()
        index = _build_child_index(tracker, [])
        assert index == {}

    def test_indexes_child_by_source_and_branch(self):
        child = _issue(identifier="TASK-2", target_branch="release/1.0")
        tracker = _make_tracker(
            all_issues=[child],
            metadata_map={
                "TASK-2": {"oompah.backport_of": {"source": "TASK-1", "status": "task_created"}},
            },
        )
        index = _build_child_index(tracker, [child])
        assert ("TASK-1", "release/1.0") in index
        assert child in index[("TASK-1", "release/1.0")]

    def test_lookup_key_is_uppercase_source_id(self):
        child = _issue(identifier="TASK-2", target_branch="release/2.0")
        tracker = _make_tracker(
            all_issues=[child],
            metadata_map={
                "TASK-2": {"oompah.backport_of": "task-1"},  # lowercase
            },
        )
        index = _build_child_index(tracker, [child])
        # Key should be uppercased
        assert ("TASK-1", "release/2.0") in index

    def test_skips_issues_without_backport_of(self):
        issue = _issue(identifier="TASK-3", target_branch="release/1.0")
        tracker = _make_tracker(
            all_issues=[issue],
            metadata_map={"TASK-3": {}},
        )
        index = _build_child_index(tracker, [issue])
        assert index == {}

    def test_multiple_children_same_source_different_branches(self):
        child1 = _issue(identifier="TASK-2", target_branch="release/1.0")
        child2 = _issue(identifier="TASK-3", target_branch="release/2.0")
        tracker = _make_tracker(
            all_issues=[child1, child2],
            metadata_map={
                "TASK-2": {"oompah.backport_of": "TASK-1"},
                "TASK-3": {"oompah.backport_of": "TASK-1"},
            },
        )
        index = _build_child_index(tracker, [child1, child2])
        assert ("TASK-1", "release/1.0") in index
        assert ("TASK-1", "release/2.0") in index

    def test_handles_metadata_exception_gracefully(self):
        issue = _issue()
        tracker = MagicMock()
        tracker.get_metadata.side_effect = Exception("oops")
        # Should not raise; just skip the issue
        index = _build_child_index(tracker, [issue])
        assert index == {}


# ---------------------------------------------------------------------------
# _create_backport_child
# ---------------------------------------------------------------------------


class TestCreateBackportChild:
    def test_creates_issue_with_correct_title(self):
        source = _issue(identifier="TASK-10", title="Fix important bug")
        entry = BackportEntry(branch="release/1.0")
        child = _issue(identifier="TASK-10.1")
        tracker = _make_tracker(created_issues=[child])
        tracker.fetch_issue_detail.return_value = child

        result = _create_backport_child(tracker, source, entry)

        tracker.create_issue.assert_called_once()
        call_kwargs = tracker.create_issue.call_args
        assert call_kwargs.kwargs.get("title") or call_kwargs.args[0] == (
            "Backport Fix important bug to release/1.0"
        )

    def test_creates_with_backport_label(self):
        source = _issue(identifier="TASK-10", title="Fix bug")
        entry = BackportEntry(branch="release/2.0")
        child = _issue(identifier="TASK-10.1")
        tracker = _make_tracker(created_issues=[child])
        tracker.fetch_issue_detail.return_value = child

        _create_backport_child(tracker, source, entry)

        call_kwargs = tracker.create_issue.call_args
        labels = call_kwargs.kwargs.get("labels") or []
        assert "backport" in labels

    def test_creates_with_source_as_parent(self):
        source = _issue(identifier="TASK-10", title="Fix bug")
        entry = BackportEntry(branch="release/2.0")
        child = _issue(identifier="TASK-10.1")
        tracker = _make_tracker(created_issues=[child])
        tracker.fetch_issue_detail.return_value = child

        _create_backport_child(tracker, source, entry)

        call_kwargs = tracker.create_issue.call_args
        parent = call_kwargs.kwargs.get("parent")
        assert parent == "TASK-10"

    def test_sets_backport_of_metadata(self):
        source = _issue(identifier="TASK-10", title="Fix bug")
        entry = BackportEntry(branch="release/1.0")
        child = _issue(identifier="TASK-10.1")
        tracker = _make_tracker(created_issues=[child])
        tracker.fetch_issue_detail.return_value = child

        _create_backport_child(tracker, source, entry)

        meta_calls = [
            c for c in tracker.set_metadata_field.call_args_list
            if c.args[1] == "oompah.backport_of"
        ]
        assert len(meta_calls) == 1
        assert meta_calls[0].args[0] == "TASK-10.1"
        value = meta_calls[0].args[2]
        assert value["source"] == "TASK-10"

    def test_sets_target_branch_metadata(self):
        source = _issue(identifier="TASK-10", title="Fix bug")
        entry = BackportEntry(branch="release/1.0")
        child = _issue(identifier="TASK-10.1")
        tracker = _make_tracker(created_issues=[child])
        tracker.fetch_issue_detail.return_value = child

        _create_backport_child(tracker, source, entry)

        meta_calls = [
            c for c in tracker.set_metadata_field.call_args_list
            if c.args[1] == "oompah.target_branch"
        ]
        assert len(meta_calls) == 1
        assert meta_calls[0].args[2] == "release/1.0"

    def test_returns_refreshed_issue_when_available(self):
        source = _issue(identifier="TASK-10", title="Fix bug")
        entry = BackportEntry(branch="release/1.0")
        child = _issue(identifier="TASK-10.1")
        refreshed = _issue(identifier="TASK-10.1", title="Backport Fix bug to release/1.0")
        tracker = _make_tracker(created_issues=[child])
        tracker.fetch_issue_detail.return_value = refreshed

        result = _create_backport_child(tracker, source, entry)

        assert result is refreshed

    def test_returns_original_child_when_refresh_returns_none(self):
        source = _issue(identifier="TASK-10", title="Fix bug")
        entry = BackportEntry(branch="release/1.0")
        child = _issue(identifier="TASK-10.1")
        tracker = _make_tracker(created_issues=[child])
        tracker.fetch_issue_detail.return_value = None

        result = _create_backport_child(tracker, source, entry)

        assert result is child


# ---------------------------------------------------------------------------
# reconcile_release_picks — no backports
# ---------------------------------------------------------------------------


class TestReconcileNoBackports:
    def test_returns_empty_result_when_no_issues(self):
        tracker = _make_tracker()
        result = reconcile_release_picks(tracker)
        assert result.scanned == 0
        assert result.advanced == 0
        assert result.created == 0
        assert result.errors == 0

    def test_returns_empty_result_when_no_backport_metadata(self):
        issues = [_issue("TASK-1"), _issue("TASK-2")]
        tracker = _make_tracker(all_issues=issues, metadata_map={})
        result = reconcile_release_picks(tracker)
        assert result.scanned == 0

    def test_skips_issues_with_empty_backports(self):
        source = _issue("TASK-1")
        tracker = _make_tracker(
            all_issues=[source],
            metadata_map={"TASK-1": {"oompah.backports": []}},
        )
        result = reconcile_release_picks(tracker)
        assert result.scanned == 0

    def test_handles_fetch_all_issues_failure(self):
        tracker = MagicMock()
        tracker.fetch_all_issues.side_effect = RuntimeError("db down")
        result = reconcile_release_picks(tracker)
        assert result.errors == 1
        assert result.scanned == 0


# ---------------------------------------------------------------------------
# reconcile_release_picks — waiting → task_created (create child)
# ---------------------------------------------------------------------------


class TestReconcileWaitingCreateChild:
    def test_creates_child_for_waiting_entry(self):
        source = _issue("TASK-1", title="My Feature", state=MERGED)
        child = _issue("TASK-1.1", target_branch="release/1.0")
        tracker = _make_tracker(
            all_issues=[source],
            metadata_map={
                "TASK-1": {
                    "oompah.backports": [
                        {"branch": "release/1.0", "status": "waiting"}
                    ]
                }
            },
            created_issues=[child],
        )
        tracker.fetch_issue_detail.return_value = child

        result = reconcile_release_picks(tracker)

        assert result.scanned == 1
        assert result.created == 1
        assert result.advanced == 1
        tracker.create_issue.assert_called_once()

    def test_writes_backports_metadata_after_creation(self):
        source = _issue("TASK-1", title="Feature", state=MERGED)
        child = _issue("TASK-1.1", target_branch="release/1.0")
        tracker = _make_tracker(
            all_issues=[source],
            metadata_map={
                "TASK-1": {"oompah.backports": "release/1.0"},
            },
            created_issues=[child],
        )
        tracker.fetch_issue_detail.return_value = child

        reconcile_release_picks(tracker)

        # set_metadata_field called for child (backport_of, target_branch)
        # and for source (backports update)
        source_backports_calls = [
            c for c in tracker.set_metadata_field.call_args_list
            if c.args[0] == "TASK-1" and c.args[1] == "oompah.backports"
        ]
        assert len(source_backports_calls) == 1
        written_raw = source_backports_calls[0].args[2]
        # The entry should now carry task_created status and the child id
        written_entries = parse_backports(written_raw)
        assert len(written_entries) == 1
        assert written_entries[0].status == ReleasePick.TASK_CREATED
        assert written_entries[0].task_id == "TASK-1.1"

    def test_multiple_waiting_entries_creates_multiple_children(self):
        source = _issue("TASK-1", title="Feature", state=DONE)
        child1 = _issue("TASK-1.1", target_branch="release/1.0")
        child2 = _issue("TASK-1.2", target_branch="release/2.0")
        tracker = _make_tracker(
            all_issues=[source],
            metadata_map={
                "TASK-1": {
                    "oompah.backports": [
                        {"branch": "release/1.0", "status": "waiting"},
                        {"branch": "release/2.0", "status": "waiting"},
                    ]
                }
            },
            created_issues=[child1, child2],
        )
        tracker.fetch_issue_detail.side_effect = [child1, child2]

        result = reconcile_release_picks(tracker)

        assert result.created == 2
        assert result.advanced == 2

    def test_create_failure_increments_errors_does_not_raise(self):
        source = _issue("TASK-1", state=MERGED)
        tracker = _make_tracker(
            all_issues=[source],
            metadata_map={
                "TASK-1": {"oompah.backports": "release/1.0"}
            },
        )
        tracker.create_issue.side_effect = RuntimeError("tracker down")

        result = reconcile_release_picks(tracker)

        assert result.errors == 1
        assert result.created == 0

    def test_does_not_create_child_for_non_waiting_entry(self):
        source = _issue("TASK-1", state=MERGED)
        tracker = _make_tracker(
            all_issues=[source],
            metadata_map={
                "TASK-1": {
                    "oompah.backports": [
                        {"branch": "release/1.0", "status": "task_created", "task_id": "TASK-1.1"}
                    ]
                }
            },
        )

        result = reconcile_release_picks(tracker)

        assert result.created == 0
        tracker.create_issue.assert_not_called()


# ---------------------------------------------------------------------------
# reconcile_release_picks — waiting → task_created (heal stale)
# ---------------------------------------------------------------------------


class TestReconcileWaitingHealStale:
    def test_heals_waiting_when_child_already_exists(self):
        source = _issue("TASK-1", state=MERGED)
        child = _issue("TASK-1.1", target_branch="release/1.0")
        tracker = _make_tracker(
            all_issues=[source, child],
            metadata_map={
                "TASK-1": {
                    "oompah.backports": [
                        {"branch": "release/1.0", "status": "waiting"},
                    ]
                },
                "TASK-1.1": {"oompah.backport_of": {"source": "TASK-1", "status": "task_created"}},
            },
        )

        result = reconcile_release_picks(tracker)

        assert result.advanced == 1
        assert result.created == 0
        tracker.create_issue.assert_not_called()

    def test_healed_entry_carries_existing_child_id(self):
        source = _issue("TASK-1", state=MERGED)
        child = _issue("TASK-1.1", target_branch="release/1.0")
        tracker = _make_tracker(
            all_issues=[source, child],
            metadata_map={
                "TASK-1": {"oompah.backports": "release/1.0"},
                "TASK-1.1": {"oompah.backport_of": "TASK-1"},
            },
        )

        reconcile_release_picks(tracker)

        source_calls = [
            c for c in tracker.set_metadata_field.call_args_list
            if c.args[0] == "TASK-1" and c.args[1] == "oompah.backports"
        ]
        assert source_calls
        written_entries = parse_backports(source_calls[0].args[2])
        assert written_entries[0].task_id == "TASK-1.1"
        assert written_entries[0].status == ReleasePick.TASK_CREATED


# ---------------------------------------------------------------------------
# reconcile_release_picks — terminal child → advance parent entry
# ---------------------------------------------------------------------------


class TestReconcileTerminalChild:
    def test_advances_to_merged_when_child_is_merged(self):
        source = _issue("TASK-1", state=MERGED)
        child = _issue("TASK-1.1", target_branch="release/1.0", state=MERGED)
        tracker = _make_tracker(
            all_issues=[source, child],
            metadata_map={
                "TASK-1": {
                    "oompah.backports": [
                        {"branch": "release/1.0", "status": "pr_open", "task_id": "TASK-1.1"}
                    ]
                },
                "TASK-1.1": {"oompah.backport_of": {"source": "TASK-1", "status": "pr_open"}},
            },
        )

        result = reconcile_release_picks(tracker)

        assert result.advanced == 1
        assert result.created == 0
        source_calls = [
            c for c in tracker.set_metadata_field.call_args_list
            if c.args[0] == "TASK-1" and c.args[1] == "oompah.backports"
        ]
        written_entries = parse_backports(source_calls[0].args[2])
        assert written_entries[0].status == ReleasePick.MERGED

    def test_advances_to_archived_when_child_is_archived(self):
        source = _issue("TASK-1", state=MERGED)
        child = _issue("TASK-1.1", target_branch="release/1.0", state=ARCHIVED)
        tracker = _make_tracker(
            all_issues=[source, child],
            metadata_map={
                "TASK-1": {
                    "oompah.backports": [
                        {"branch": "release/1.0", "status": "cherry_picking", "task_id": "TASK-1.1"}
                    ]
                },
                "TASK-1.1": {"oompah.backport_of": {"source": "TASK-1", "status": "cherry_picking"}},
            },
        )

        result = reconcile_release_picks(tracker)

        source_calls = [
            c for c in tracker.set_metadata_field.call_args_list
            if c.args[0] == "TASK-1" and c.args[1] == "oompah.backports"
        ]
        written_entries = parse_backports(source_calls[0].args[2])
        assert written_entries[0].status == ReleasePick.ARCHIVED

    def test_advances_to_merged_when_child_is_done(self):
        """Done is treated as merged (not archived)."""
        source = _issue("TASK-1", state=MERGED)
        child = _issue("TASK-1.1", target_branch="release/1.0", state=DONE)
        tracker = _make_tracker(
            all_issues=[source, child],
            metadata_map={
                "TASK-1": {
                    "oompah.backports": [
                        {"branch": "release/1.0", "status": "pr_open", "task_id": "TASK-1.1"}
                    ]
                },
                "TASK-1.1": {"oompah.backport_of": "TASK-1"},
            },
        )

        result = reconcile_release_picks(tracker)

        source_calls = [
            c for c in tracker.set_metadata_field.call_args_list
            if c.args[0] == "TASK-1" and c.args[1] == "oompah.backports"
        ]
        written_entries = parse_backports(source_calls[0].args[2])
        assert written_entries[0].status == ReleasePick.MERGED

    def test_no_write_when_entry_already_merged(self):
        """Already-terminal entries are not re-written."""
        source = _issue("TASK-1", state=MERGED)
        child = _issue("TASK-1.1", target_branch="release/1.0", state=MERGED)
        tracker = _make_tracker(
            all_issues=[source, child],
            metadata_map={
                "TASK-1": {
                    "oompah.backports": [
                        {"branch": "release/1.0", "status": "merged", "task_id": "TASK-1.1"}
                    ]
                },
                "TASK-1.1": {"oompah.backport_of": "TASK-1"},
            },
        )

        result = reconcile_release_picks(tracker)

        assert result.advanced == 0
        assert result.scanned == 1  # still scanned
        # No writes for already-terminal entries
        source_backports_calls = [
            c for c in tracker.set_metadata_field.call_args_list
            if c.args[0] == "TASK-1" and c.args[1] == "oompah.backports"
        ]
        assert len(source_backports_calls) == 0

    def test_preserves_pr_url_when_advancing(self):
        source = _issue("TASK-1", state=MERGED)
        child = _issue("TASK-1.1", target_branch="release/1.0", state=MERGED)
        tracker = _make_tracker(
            all_issues=[source, child],
            metadata_map={
                "TASK-1": {
                    "oompah.backports": [
                        {
                            "branch": "release/1.0",
                            "status": "pr_open",
                            "task_id": "TASK-1.1",
                            "pr_url": "https://github.com/org/repo/pull/42",
                        }
                    ]
                },
                "TASK-1.1": {"oompah.backport_of": "TASK-1"},
            },
        )

        reconcile_release_picks(tracker)

        source_calls = [
            c for c in tracker.set_metadata_field.call_args_list
            if c.args[0] == "TASK-1" and c.args[1] == "oompah.backports"
        ]
        written_entries = parse_backports(source_calls[0].args[2])
        assert written_entries[0].pr_url == "https://github.com/org/repo/pull/42"


# ---------------------------------------------------------------------------
# reconcile_release_picks — idempotency
# ---------------------------------------------------------------------------


class TestReconcileIdempotency:
    def test_second_pass_produces_no_changes(self):
        """Running the reconciler twice on an already-reconciled state is a no-op."""
        source = _issue("TASK-1", state=MERGED)
        child = _issue("TASK-1.1", target_branch="release/1.0")

        # Already advanced to task_created with child task
        tracker = _make_tracker(
            all_issues=[source, child],
            metadata_map={
                "TASK-1": {
                    "oompah.backports": [
                        {
                            "branch": "release/1.0",
                            "status": "task_created",
                            "task_id": "TASK-1.1",
                        }
                    ]
                },
                "TASK-1.1": {
                    "oompah.backport_of": {"source": "TASK-1", "status": "task_created"}
                },
            },
        )

        result = reconcile_release_picks(tracker)

        assert result.advanced == 0
        assert result.created == 0

    def test_same_branch_not_doubled_within_one_pass(self):
        """Two entries for the same (source, branch) → only one child created."""
        source = _issue("TASK-1", state=MERGED)
        # Duplicate backports entries for same branch
        child = _issue("TASK-1.1", target_branch="release/1.0")
        tracker = _make_tracker(
            all_issues=[source],
            metadata_map={
                "TASK-1": {
                    "oompah.backports": [
                        {"branch": "release/1.0", "status": "waiting"},
                        {"branch": "release/1.0", "status": "waiting"},
                    ]
                }
            },
            created_issues=[child],
        )
        tracker.fetch_issue_detail.return_value = child

        result = reconcile_release_picks(tracker)

        # First entry creates child; second entry heals against the same child
        assert result.created == 1
        assert result.advanced == 2


# ---------------------------------------------------------------------------
# reconcile_release_picks — bad metadata resilience
# ---------------------------------------------------------------------------


class TestReconcileBadMetadata:
    def test_skips_unparseable_backports_increments_errors(self):
        source = _issue("TASK-1", state=MERGED)
        tracker = _make_tracker(
            all_issues=[source],
            metadata_map={
                "TASK-1": {
                    # Malformed: dict without 'branch' key
                    "oompah.backports": [{"status": "waiting"}]
                }
            },
        )

        result = reconcile_release_picks(tracker)

        assert result.errors >= 1

    def test_metadata_write_failure_increments_errors(self):
        source = _issue("TASK-1", state=MERGED)
        child = _issue("TASK-1.1", target_branch="release/1.0")
        tracker = _make_tracker(
            all_issues=[source],
            metadata_map={
                "TASK-1": {"oompah.backports": "release/1.0"}
            },
            created_issues=[child],
        )
        tracker.fetch_issue_detail.return_value = child
        # The call for child's metadata should succeed, source backports should fail
        set_meta_call_count = [0]

        def _set_meta(ident, key, value):
            set_meta_call_count[0] += 1
            if ident == "TASK-1" and key == "oompah.backports":
                raise RuntimeError("write failed")

        tracker.set_metadata_field.side_effect = _set_meta

        result = reconcile_release_picks(tracker)

        assert result.errors == 1

    def test_bad_backport_of_on_child_does_not_include_in_index(self):
        source = _issue("TASK-1", state=MERGED)
        malformed_child = _issue("TASK-1.1", target_branch="release/1.0")
        tracker = _make_tracker(
            all_issues=[source, malformed_child],
            metadata_map={
                "TASK-1": {"oompah.backports": "release/1.0"},
                # Missing 'source' key — parse_backport_of raises ValueError
                "TASK-1.1": {"oompah.backport_of": {"status": "waiting"}},
            },
            created_issues=[_issue("TASK-1.2", target_branch="release/1.0")],
        )
        tracker.fetch_issue_detail.return_value = _issue("TASK-1.2")

        # Malformed child is not indexed, so we still create a new child
        result = reconcile_release_picks(tracker)

        assert result.created == 1


# ---------------------------------------------------------------------------
# Orchestrator._reconcile_release_picks_pass
# ---------------------------------------------------------------------------


class TestOrchestratorReconcileReleasePicksPass:
    """_reconcile_release_picks_pass delegates to reconcile_release_picks."""

    def _make_orch(self, tmp_path, projects=None):
        from oompah.config import ServiceConfig
        from oompah.orchestrator import Orchestrator
        from oompah.roles import RoleStore

        all_projects = list(projects or [])
        project_store = MagicMock()
        project_store.list_all.return_value = all_projects
        role_store = RoleStore(path=str(tmp_path / "roles.json"))
        orch = Orchestrator(
            config=ServiceConfig(),
            workflow_path="WORKFLOW.md",
            project_store=project_store,
            role_store=role_store,
            state_path=str(tmp_path / "state.json"),
        )
        orch._fetch_in_progress_issues = MagicMock(return_value=[])
        return orch

    def test_called_by_do_merged_labels(self, tmp_path):
        """_reconcile_release_picks_pass is invoked by _do_merged_labels.

        TASK-466.2 moved release-pick reconciliation from _handle_yolo_review
        into the maintenance lane (_do_merged_labels) to avoid blocking
        dispatch-critical tick latency.
        """
        orch = self._make_orch(tmp_path)
        orch._label_merged_issues = MagicMock()
        orch._label_merged_epics = MagicMock()
        orch._reconcile_stale_in_review_tasks = MagicMock()
        orch._reconcile_release_picks_pass = MagicMock()

        orch._do_merged_labels()

        orch._reconcile_release_picks_pass.assert_called_once()

    def test_skips_when_no_projects(self, tmp_path):
        """With no configured projects, the pass is a no-op (no legacy fallback)."""
        orch = self._make_orch(tmp_path, projects=[])

        called_with = []

        def _fake_reconcile(tracker, **kwargs):
            called_with.append(tracker)
            return ReconcileResult()

        with patch(
            "oompah.release_pick_reconciler.reconcile_release_picks",
            side_effect=_fake_reconcile,
        ):
            orch._reconcile_release_picks_pass()

        # Should not call reconcile when there are no projects
        assert len(called_with) == 0

    def test_calls_reconcile_for_each_project(self, tmp_path):
        """With multiple projects, reconcile is called once per project."""
        p1 = MagicMock()
        p1.id = "proj-1"
        p1.name = "proj-1"
        p2 = MagicMock()
        p2.id = "proj-2"
        p2.name = "proj-2"
        orch = self._make_orch(tmp_path, projects=[p1, p2])

        # Stub out _tracker_for_project
        mock_tracker1 = MagicMock()
        mock_tracker2 = MagicMock()

        def _get_tracker(pid):
            return mock_tracker1 if pid == "proj-1" else mock_tracker2

        orch._tracker_for_project = MagicMock(side_effect=_get_tracker)

        called_trackers = []

        def _fake_reconcile(tracker, **kwargs):
            called_trackers.append(tracker)
            return ReconcileResult()

        with patch(
            "oompah.release_pick_reconciler.reconcile_release_picks",
            side_effect=_fake_reconcile,
        ):
            orch._reconcile_release_picks_pass()

        assert mock_tracker1 in called_trackers
        assert mock_tracker2 in called_trackers
        assert len(called_trackers) == 2

    def test_calls_reconcile_with_project_store_and_id(self, tmp_path):
        """Reconcile is called with project_store and project_id kwargs."""
        p1 = MagicMock()
        p1.id = "proj-1"
        p1.name = "proj-1"
        orch = self._make_orch(tmp_path, projects=[p1])
        orch._tracker_for_project = MagicMock(return_value=MagicMock())

        captured_kwargs: list[dict] = []

        def _fake_reconcile(tracker, **kwargs):
            captured_kwargs.append(kwargs)
            return ReconcileResult()

        with patch(
            "oompah.release_pick_reconciler.reconcile_release_picks",
            side_effect=_fake_reconcile,
        ):
            orch._reconcile_release_picks_pass()

        assert len(captured_kwargs) == 1
        assert "project_store" in captured_kwargs[0]
        assert "project_id" in captured_kwargs[0]
        assert captured_kwargs[0]["project_id"] == "proj-1"

    def test_continues_on_project_failure(self, tmp_path):
        """A failure for one project does not prevent processing others."""
        p1 = MagicMock()
        p1.id = "proj-1"
        p1.name = "proj-1"
        p2 = MagicMock()
        p2.id = "proj-2"
        p2.name = "proj-2"
        orch = self._make_orch(tmp_path, projects=[p1, p2])

        call_count = [0]

        def _tracker(pid):
            t = MagicMock()
            return t

        orch._tracker_for_project = MagicMock(side_effect=_tracker)

        def _reconcile(tracker, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("first project broken")
            return ReconcileResult()

        with patch(
            "oompah.release_pick_reconciler.reconcile_release_picks",
            side_effect=_reconcile,
        ):
            # Should not raise
            orch._reconcile_release_picks_pass()

        # Both projects attempted
        assert call_count[0] == 2

    def test_project_exception_does_not_raise(self, tmp_path):
        """Exception from one project's reconcile is swallowed."""
        p1 = MagicMock()
        p1.id = "proj-x"
        p1.name = "proj-x"
        orch = self._make_orch(tmp_path, projects=[p1])
        orch._tracker_for_project = MagicMock(return_value=MagicMock())

        with patch(
            "oompah.release_pick_reconciler.reconcile_release_picks",
            side_effect=RuntimeError("broken"),
        ):
            # Should not raise
            orch._reconcile_release_picks_pass()

    def test_passes_scm_and_repo_to_reconcile(self, tmp_path):
        """reconcile_release_picks receives scm and repo kwargs from orchestrator."""
        p1 = MagicMock()
        p1.id = "proj-1"
        p1.name = "proj-1"
        p1.repo_url = "https://github.com/org/repo.git"
        p1.access_token = "tok"
        orch = self._make_orch(tmp_path, projects=[p1])
        orch._tracker_for_project = MagicMock(return_value=MagicMock())

        mock_provider = MagicMock()
        captured_kwargs: list[dict] = []

        def _fake_reconcile(tracker, **kwargs):
            captured_kwargs.append(kwargs)
            return ReconcileResult()

        # The pass does a local import, so we patch at oompah.scm to intercept
        with (
            patch(
                "oompah.release_pick_reconciler.reconcile_release_picks",
                side_effect=_fake_reconcile,
            ),
            patch("oompah.scm.detect_provider", return_value=mock_provider),
            patch("oompah.scm.extract_repo_slug", return_value="org/repo"),
        ):
            orch._reconcile_release_picks_pass()

        assert len(captured_kwargs) == 1
        assert captured_kwargs[0].get("scm") is mock_provider
        assert captured_kwargs[0].get("repo") == "org/repo"

    def test_scm_detection_failure_does_not_prevent_reconcile(self, tmp_path):
        """If SCM detection fails, reconcile still runs (without scm/repo)."""
        p1 = MagicMock()
        p1.id = "proj-1"
        p1.name = "proj-1"
        p1.repo_url = "https://github.com/org/repo.git"
        orch = self._make_orch(tmp_path, projects=[p1])
        orch._tracker_for_project = MagicMock(return_value=MagicMock())

        captured_kwargs: list[dict] = []

        def _fake_reconcile(tracker, **kwargs):
            captured_kwargs.append(kwargs)
            return ReconcileResult()

        # Patch at oompah.scm since the pass does a local import
        with (
            patch(
                "oompah.release_pick_reconciler.reconcile_release_picks",
                side_effect=_fake_reconcile,
            ),
            patch(
                "oompah.scm.detect_provider",
                side_effect=RuntimeError("no token"),
            ),
        ):
            # Should not raise
            orch._reconcile_release_picks_pass()

        assert len(captured_kwargs) == 1
        # scm should be None when detection fails
        assert captured_kwargs[0].get("scm") is None


# ---------------------------------------------------------------------------
# _create_backport_worktree (TASK-455.3)
# ---------------------------------------------------------------------------


class TestCreateBackportWorktree:
    """Tests for the target-branch worktree helper function."""

    def test_calls_create_worktree_with_correct_args(self):
        """create_worktree is called with the child identifier and target branch."""
        child = _issue(identifier="TASK-10.1")
        entry = BackportEntry(branch="release/1.0")
        project_store = MagicMock()

        _create_backport_worktree(child, entry, project_store, "proj-1")

        project_store.create_worktree.assert_called_once_with(
            "proj-1",
            "TASK-10.1",
            base_branch="release/1.0",
        )

    def test_uses_entry_branch_as_base_branch(self):
        """base_branch kwarg is taken from entry.branch."""
        child = _issue(identifier="TASK-5.1")
        entry = BackportEntry(branch="maint/2.x")
        project_store = MagicMock()

        _create_backport_worktree(child, entry, project_store, "my-proj")

        call_kwargs = project_store.create_worktree.call_args
        assert call_kwargs.kwargs.get("base_branch") == "maint/2.x"

    def test_propagates_project_error(self):
        """ProjectError from create_worktree propagates to the caller."""
        from oompah.projects import ProjectError

        child = _issue(identifier="TASK-10.1")
        entry = BackportEntry(branch="release/2.0")
        project_store = MagicMock()
        project_store.create_worktree.side_effect = ProjectError("git failed")

        with pytest.raises(ProjectError):
            _create_backport_worktree(child, entry, project_store, "proj-1")


# ---------------------------------------------------------------------------
# reconcile_release_picks — worktree integration (TASK-455.3)
# ---------------------------------------------------------------------------


class TestReconcileWorktreeIntegration:
    """Verify worktree creation is wired through the reconcile pass."""

    def test_worktree_created_for_new_waiting_entry(self):
        """A 'waiting' entry that gets a new child also gets a worktree."""
        source = _issue(identifier="TASK-1", title="Bug fix")
        entries_raw = backports_to_raw(
            [BackportEntry(branch="release/3.0", status=ReleasePick.WAITING)]
        )
        child = _issue(identifier="TASK-1.1")
        tracker = _make_tracker(
            all_issues=[source],
            metadata_map={"TASK-1": {"oompah.backports": entries_raw}},
            created_issues=[child],
        )
        tracker.fetch_issue_detail.return_value = child

        project_store = MagicMock()
        result = reconcile_release_picks(
            tracker,
            project_store=project_store,
            project_id="proj-abc",
        )

        assert result.created == 1
        project_store.create_worktree.assert_called_once_with(
            "proj-abc",
            "TASK-1.1",
            base_branch="release/3.0",
        )

    def test_no_worktree_when_no_project_store(self):
        """Without project_store, no worktrees are created (backward-compat)."""
        source = _issue(identifier="TASK-2", title="Other fix")
        entries_raw = backports_to_raw(
            [BackportEntry(branch="release/1.0", status=ReleasePick.WAITING)]
        )
        child = _issue(identifier="TASK-2.1")
        tracker = _make_tracker(
            all_issues=[source],
            metadata_map={"TASK-2": {"oompah.backports": entries_raw}},
            created_issues=[child],
        )
        tracker.fetch_issue_detail.return_value = child

        # No project_store — reconcile without worktree creation
        result = reconcile_release_picks(tracker)

        assert result.created == 1  # child task is still created

    def test_worktree_failure_counted_in_errors(self):
        """A worktree creation failure increments errors in the result."""
        from oompah.projects import ProjectError

        source = _issue(identifier="TASK-3", title="Security fix")
        entries_raw = backports_to_raw(
            [BackportEntry(branch="stable/4.0", status=ReleasePick.WAITING)]
        )
        child = _issue(identifier="TASK-3.1")
        tracker = _make_tracker(
            all_issues=[source],
            metadata_map={"TASK-3": {"oompah.backports": entries_raw}},
            created_issues=[child],
        )
        tracker.fetch_issue_detail.return_value = child

        project_store = MagicMock()
        project_store.create_worktree.side_effect = ProjectError("no git")

        result = reconcile_release_picks(
            tracker,
            project_store=project_store,
            project_id="proj-1",
        )

        # Child task was still created
        assert result.created == 1
        # Error from worktree failure was recorded
        assert result.errors >= 1

    def test_no_worktree_for_healed_stale_entry(self):
        """A stale 'waiting' entry that's healed (child already exists) gets no new worktree."""
        child = _issue(identifier="TASK-4.1", target_branch="release/1.0")
        source = _issue(identifier="TASK-4", title="Already done fix")
        entries_raw = backports_to_raw(
            [BackportEntry(branch="release/1.0", status=ReleasePick.WAITING)]
        )
        tracker = _make_tracker(
            all_issues=[source, child],
            metadata_map={
                "TASK-4": {"oompah.backports": entries_raw},
                "TASK-4.1": {"oompah.backport_of": {"source": "TASK-4", "status": "task_created"}},
            },
        )

        project_store = MagicMock()
        result = reconcile_release_picks(
            tracker,
            project_store=project_store,
            project_id="proj-1",
        )

        # Entry healed (advanced) but no new task created
        assert result.advanced == 1
        assert result.created == 0
        # No worktree created for heal path (child already exists)
        project_store.create_worktree.assert_not_called()


# ---------------------------------------------------------------------------
# _check_pr_outcome — unit tests (TASK-455.6)
# ---------------------------------------------------------------------------


def _make_review_request(
    state: str,
    *,
    pr_id: str = "42",
    url: str = "https://github.com/org/repo/pull/42",
    source_branch: str = "TASK-1.1",
    target_branch: str = "release/1.0",
) -> ReviewRequest:
    """Build a minimal ReviewRequest suitable for testing."""
    return ReviewRequest(
        id=pr_id,
        title="Backport fix to release/1.0",
        url=url,
        author="bot",
        state=state,
        source_branch=source_branch,
        target_branch=target_branch,
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )


class TestCheckPrOutcome:
    """Unit tests for _check_pr_outcome (TASK-455.6).

    Covers all four PR states (merged, closed, open, not-found) plus error
    paths.
    """

    def _setup(
        self,
        *,
        entry_status: ReleasePick = ReleasePick.PR_OPEN,
        child_state: str = OPEN,
        child_target_branch: str = "release/1.0",
        pr_state: str | None = "open",
        scm_raises: bool = False,
        entry_pr_url: str | None = None,
        entry_task_id: str = "TASK-1.1",
        child_backport_of_raw=None,
    ):
        """Return (tracker, source, entry, children, scm, repo) ready for testing."""
        source = _issue("TASK-1", title="Fix bug", state=MERGED)
        child = _issue(
            "TASK-1.1",
            target_branch=child_target_branch,
            state=child_state,
        )
        entry = BackportEntry(
            branch="release/1.0",
            status=entry_status,
            task_id=entry_task_id,
            pr_url=entry_pr_url,
        )
        children = [child]

        meta_child = {}
        if child_backport_of_raw is not None:
            meta_child["oompah.backport_of"] = child_backport_of_raw
        else:
            meta_child["oompah.backport_of"] = {
                "source": "TASK-1",
                "status": entry_status.value,
            }

        tracker = _make_tracker(
            all_issues=[source, child],
            metadata_map={"TASK-1.1": meta_child},
        )

        scm = MagicMock()
        if scm_raises:
            scm.find_pr_for_branch.side_effect = RuntimeError("SCM unavailable")
        elif pr_state is None:
            scm.find_pr_for_branch.return_value = None
        else:
            pr = _make_review_request(
                pr_state,
                source_branch=child_target_branch,
            )
            scm.find_pr_for_branch.return_value = pr

        return tracker, source, entry, children, scm, "org/repo"

    # --- PR merged ---

    def test_merged_pr_advances_entry_to_merged(self):
        tracker, source, entry, children, scm, repo = self._setup(pr_state="merged")

        result = _check_pr_outcome(tracker, source, entry, children, scm=scm, repo=repo)

        assert result.status == ReleasePick.MERGED

    def test_merged_pr_marks_child_task_merged(self):
        tracker, source, entry, children, scm, repo = self._setup(pr_state="merged")

        _check_pr_outcome(tracker, source, entry, children, scm=scm, repo=repo)

        tracker.update_issue.assert_called_once_with("TASK-1.1", status=MERGED)

    def test_merged_pr_does_not_re_mark_already_merged_child(self):
        """If child is already Merged, update_issue should NOT be called again."""
        tracker, source, entry, children, scm, repo = self._setup(
            pr_state="merged", child_state=MERGED
        )

        _check_pr_outcome(tracker, source, entry, children, scm=scm, repo=repo)

        tracker.update_issue.assert_not_called()

    def test_merged_pr_updates_child_backport_of_to_merged(self):
        tracker, source, entry, children, scm, repo = self._setup(pr_state="merged")

        _check_pr_outcome(tracker, source, entry, children, scm=scm, repo=repo)

        bof_calls = [
            c for c in tracker.set_metadata_field.call_args_list
            if c.args[0] == "TASK-1.1" and c.args[1] == "oompah.backport_of"
        ]
        assert len(bof_calls) == 1
        written_value = bof_calls[0].args[2]
        from oompah.release_pick_schema import BackportOf
        bof = BackportOf.from_raw(written_value)
        assert bof.status == ReleasePick.MERGED

    def test_merged_pr_sets_pr_url_from_pr_when_entry_has_none(self):
        tracker, source, entry, children, scm, repo = self._setup(
            pr_state="merged", entry_pr_url=None
        )

        result = _check_pr_outcome(tracker, source, entry, children, scm=scm, repo=repo)

        assert result.pr_url == "https://github.com/org/repo/pull/42"

    def test_merged_pr_preserves_existing_entry_pr_url(self):
        """When entry already has a pr_url, it is preserved over the PR url."""
        original_url = "https://github.com/org/repo/pull/99"
        tracker, source, entry, children, scm, repo = self._setup(
            pr_state="merged", entry_pr_url=original_url
        )

        result = _check_pr_outcome(tracker, source, entry, children, scm=scm, repo=repo)

        assert result.pr_url == original_url

    def test_merged_pr_case_insensitive_state(self):
        """State check is case-insensitive — 'MERGED' should be treated as merged."""
        tracker, source, entry, children, scm, repo = self._setup(pr_state="MERGED")

        result = _check_pr_outcome(tracker, source, entry, children, scm=scm, repo=repo)

        assert result.status == ReleasePick.MERGED

    def test_merged_pr_preserves_task_id(self):
        tracker, source, entry, children, scm, repo = self._setup(pr_state="merged")

        result = _check_pr_outcome(tracker, source, entry, children, scm=scm, repo=repo)

        assert result.task_id == "TASK-1.1"

    # --- PR closed (unmerged) ---

    def test_closed_pr_advances_entry_to_needs_human(self):
        tracker, source, entry, children, scm, repo = self._setup(pr_state="closed")

        result = _check_pr_outcome(tracker, source, entry, children, scm=scm, repo=repo)

        assert result.status == ReleasePick.NEEDS_HUMAN

    def test_closed_pr_posts_actionable_comment_on_source(self):
        tracker, source, entry, children, scm, repo = self._setup(pr_state="closed")

        _check_pr_outcome(tracker, source, entry, children, scm=scm, repo=repo)

        tracker.add_comment.assert_called_once()
        comment_call = tracker.add_comment.call_args
        # Comment is posted on the source task
        assert comment_call.args[0] == "TASK-1"
        # Comment mentions the PR URL
        comment_body = comment_call.args[1]
        assert "https://github.com/org/repo/pull/42" in comment_body

    def test_closed_pr_comment_author_is_oompah(self):
        tracker, source, entry, children, scm, repo = self._setup(pr_state="closed")

        _check_pr_outcome(tracker, source, entry, children, scm=scm, repo=repo)

        comment_call = tracker.add_comment.call_args
        assert comment_call.kwargs.get("author") == "oompah"

    def test_closed_pr_updates_child_backport_of_to_needs_human(self):
        tracker, source, entry, children, scm, repo = self._setup(pr_state="closed")

        _check_pr_outcome(tracker, source, entry, children, scm=scm, repo=repo)

        bof_calls = [
            c for c in tracker.set_metadata_field.call_args_list
            if c.args[0] == "TASK-1.1" and c.args[1] == "oompah.backport_of"
        ]
        assert len(bof_calls) == 1
        written_value = bof_calls[0].args[2]
        from oompah.release_pick_schema import BackportOf
        bof = BackportOf.from_raw(written_value)
        assert bof.status == ReleasePick.NEEDS_HUMAN

    def test_closed_pr_sets_pr_url_from_pr(self):
        tracker, source, entry, children, scm, repo = self._setup(
            pr_state="closed", entry_pr_url=None
        )

        result = _check_pr_outcome(tracker, source, entry, children, scm=scm, repo=repo)

        assert result.pr_url == "https://github.com/org/repo/pull/42"

    def test_closed_pr_comment_failure_does_not_prevent_status_advance(self):
        """If add_comment fails, entry should still advance to needs_human."""
        tracker, source, entry, children, scm, repo = self._setup(pr_state="closed")
        tracker.add_comment.side_effect = RuntimeError("comment failed")

        result = _check_pr_outcome(tracker, source, entry, children, scm=scm, repo=repo)

        assert result.status == ReleasePick.NEEDS_HUMAN

    # --- PR still open ---

    def test_open_pr_returns_unchanged_entry(self):
        tracker, source, entry, children, scm, repo = self._setup(pr_state="open")

        result = _check_pr_outcome(tracker, source, entry, children, scm=scm, repo=repo)

        assert result is entry

    def test_open_pr_does_not_update_child(self):
        tracker, source, entry, children, scm, repo = self._setup(pr_state="open")

        _check_pr_outcome(tracker, source, entry, children, scm=scm, repo=repo)

        tracker.update_issue.assert_not_called()
        tracker.add_comment.assert_not_called()

    # --- PR not found ---

    def test_no_pr_found_returns_unchanged_entry(self):
        tracker, source, entry, children, scm, repo = self._setup(pr_state=None)

        result = _check_pr_outcome(tracker, source, entry, children, scm=scm, repo=repo)

        assert result is entry

    def test_no_pr_found_does_not_write_anything(self):
        tracker, source, entry, children, scm, repo = self._setup(pr_state=None)

        _check_pr_outcome(tracker, source, entry, children, scm=scm, repo=repo)

        tracker.update_issue.assert_not_called()
        tracker.add_comment.assert_not_called()

    # --- SCM error ---

    def test_scm_exception_returns_unchanged_entry(self):
        tracker, source, entry, children, scm, repo = self._setup(scm_raises=True)

        result = _check_pr_outcome(tracker, source, entry, children, scm=scm, repo=repo)

        assert result is entry

    def test_scm_exception_does_not_update_child(self):
        tracker, source, entry, children, scm, repo = self._setup(scm_raises=True)

        _check_pr_outcome(tracker, source, entry, children, scm=scm, repo=repo)

        tracker.update_issue.assert_not_called()
        tracker.add_comment.assert_not_called()

    # --- No live child ---

    def test_no_live_child_returns_unchanged_entry(self):
        """When there are no children at all, the entry is returned unchanged."""
        source = _issue("TASK-1", state=MERGED)
        entry = BackportEntry(
            branch="release/1.0",
            status=ReleasePick.PR_OPEN,
            task_id="TASK-1.1",
        )
        tracker = MagicMock()
        scm = MagicMock()

        result = _check_pr_outcome(tracker, source, entry, [], scm=scm, repo="org/repo")

        assert result is entry
        scm.find_pr_for_branch.assert_not_called()

    # --- Branch name resolution ---

    def test_uses_child_target_branch_as_branch_name(self):
        """The SCM lookup uses the child target_branch, not its identifier."""
        tracker, source, entry, children, scm, repo = self._setup(
            child_target_branch="release/1.0", pr_state="open"
        )

        _check_pr_outcome(tracker, source, entry, children, scm=scm, repo=repo)

        scm.find_pr_for_branch.assert_called_once_with(repo, "release/1.0")

    def test_falls_back_to_child_identifier_when_no_target_branch(self):
        """Without target_branch, the child identifier is used as the branch name."""
        source = _issue("TASK-1", state=MERGED)
        child = _issue("TASK-1.1", target_branch=None, state=OPEN)
        entry = BackportEntry(
            branch="release/1.0",
            status=ReleasePick.PR_OPEN,
            task_id="TASK-1.1",
        )
        scm = MagicMock()
        scm.find_pr_for_branch.return_value = None
        tracker = _make_tracker(
            all_issues=[source, child],
            metadata_map={
                "TASK-1.1": {
                    "oompah.backport_of": {"source": "TASK-1", "status": "pr_open"}
                }
            },
        )

        _check_pr_outcome(tracker, source, entry, [child], scm=scm, repo="org/repo")

        scm.find_pr_for_branch.assert_called_once_with("org/repo", "TASK-1.1")

    def test_finds_child_by_task_id_when_all_terminal(self):
        """When _best_live_child returns None but task_id matches a child, use that."""
        source = _issue("TASK-1", state=MERGED)
        child = _issue("TASK-1.1", target_branch="release/1.0", state=MERGED)
        entry = BackportEntry(
            branch="release/1.0",
            status=ReleasePick.PR_OPEN,
            task_id="TASK-1.1",
        )
        pr = _make_review_request("merged", source_branch="release/1.0")
        scm = MagicMock()
        scm.find_pr_for_branch.return_value = pr
        tracker = _make_tracker(
            all_issues=[source, child],
            metadata_map={
                "TASK-1.1": {
                    "oompah.backport_of": {"source": "TASK-1", "status": "pr_open"}
                }
            },
        )

        result = _check_pr_outcome(tracker, source, entry, [child], scm=scm, repo="org/repo")

        # Child found by task_id, PR was merged — entry advances
        assert result.status == ReleasePick.MERGED

    # --- cherry_picking entry ---

    def test_cherry_picking_entry_with_merged_pr_advances_to_merged(self):
        """cherry_picking entries also respond to merged PR checks."""
        tracker, source, entry, children, scm, repo = self._setup(
            entry_status=ReleasePick.CHERRY_PICKING,
            pr_state="merged",
        )

        result = _check_pr_outcome(tracker, source, entry, children, scm=scm, repo=repo)

        assert result.status == ReleasePick.MERGED


# ---------------------------------------------------------------------------
# reconcile_release_picks — PR outcome integration (TASK-455.6)
# ---------------------------------------------------------------------------


class TestReconcilePrOutcomeIntegration:
    """Integration tests: full reconcile_release_picks with pr_open entries."""

    def _source_with_pr_open(self, task_id="TASK-1", child_id="TASK-1.1", branch="release/1.0"):
        source = _issue(task_id, state=MERGED)
        child = _issue(child_id, target_branch=branch, state=OPEN)
        return source, child

    def test_merged_pr_advances_entry_in_full_pass(self):
        """A pr_open entry whose PR has merged advances to merged via full reconcile."""
        source, child = self._source_with_pr_open()
        pr = _make_review_request("merged", source_branch="release/1.0")

        tracker = _make_tracker(
            all_issues=[source, child],
            metadata_map={
                "TASK-1": {
                    "oompah.backports": [
                        {"branch": "release/1.0", "status": "pr_open", "task_id": "TASK-1.1"}
                    ]
                },
                "TASK-1.1": {"oompah.backport_of": {"source": "TASK-1", "status": "pr_open"}},
            },
        )
        scm = MagicMock()
        scm.find_pr_for_branch.return_value = pr

        result = reconcile_release_picks(tracker, scm=scm, repo="org/repo")

        assert result.advanced == 1
        assert result.scanned == 1
        source_backports_calls = [
            c for c in tracker.set_metadata_field.call_args_list
            if c.args[0] == "TASK-1" and c.args[1] == "oompah.backports"
        ]
        assert len(source_backports_calls) == 1
        written_entries = parse_backports(source_backports_calls[0].args[2])
        assert written_entries[0].status == ReleasePick.MERGED

    def test_cherry_picking_entry_merged_pr_advances_in_full_pass(self):
        """cherry_picking entries are also checked for PR outcomes."""
        source = _issue("TASK-2", state=MERGED)
        child = _issue("TASK-2.1", target_branch="release/1.0", state=OPEN)
        pr = _make_review_request("merged", source_branch="release/1.0")

        tracker = _make_tracker(
            all_issues=[source, child],
            metadata_map={
                "TASK-2": {
                    "oompah.backports": [
                        {"branch": "release/1.0", "status": "cherry_picking", "task_id": "TASK-2.1"}
                    ]
                },
                "TASK-2.1": {
                    "oompah.backport_of": {"source": "TASK-2", "status": "cherry_picking"}
                },
            },
        )
        scm = MagicMock()
        scm.find_pr_for_branch.return_value = pr

        result = reconcile_release_picks(tracker, scm=scm, repo="org/repo")

        assert result.advanced == 1
        source_calls = [
            c for c in tracker.set_metadata_field.call_args_list
            if c.args[0] == "TASK-2" and c.args[1] == "oompah.backports"
        ]
        written_entries = parse_backports(source_calls[0].args[2])
        assert written_entries[0].status == ReleasePick.MERGED

    def test_closed_pr_escalates_to_needs_human_in_full_pass(self):
        """A pr_open entry whose PR closed unmerged escalates to needs_human."""
        source, child = self._source_with_pr_open()
        pr = _make_review_request("closed", source_branch="release/1.0")

        tracker = _make_tracker(
            all_issues=[source, child],
            metadata_map={
                "TASK-1": {
                    "oompah.backports": [
                        {"branch": "release/1.0", "status": "pr_open", "task_id": "TASK-1.1"}
                    ]
                },
                "TASK-1.1": {"oompah.backport_of": {"source": "TASK-1", "status": "pr_open"}},
            },
        )
        scm = MagicMock()
        scm.find_pr_for_branch.return_value = pr

        result = reconcile_release_picks(tracker, scm=scm, repo="org/repo")

        assert result.advanced == 1
        tracker.add_comment.assert_called()
        comment_call = tracker.add_comment.call_args
        assert comment_call.args[0] == "TASK-1"

        source_calls = [
            c for c in tracker.set_metadata_field.call_args_list
            if c.args[0] == "TASK-1" and c.args[1] == "oompah.backports"
        ]
        written_entries = parse_backports(source_calls[0].args[2])
        assert written_entries[0].status == ReleasePick.NEEDS_HUMAN

    def test_open_pr_does_not_advance_entry(self):
        """An open PR causes no advancement in the reconcile pass."""
        source, child = self._source_with_pr_open()
        pr = _make_review_request("open", source_branch="release/1.0")

        tracker = _make_tracker(
            all_issues=[source, child],
            metadata_map={
                "TASK-1": {
                    "oompah.backports": [
                        {"branch": "release/1.0", "status": "pr_open", "task_id": "TASK-1.1"}
                    ]
                },
                "TASK-1.1": {"oompah.backport_of": {"source": "TASK-1", "status": "pr_open"}},
            },
        )
        scm = MagicMock()
        scm.find_pr_for_branch.return_value = pr

        result = reconcile_release_picks(tracker, scm=scm, repo="org/repo")

        assert result.advanced == 0

    def test_no_scm_skips_pr_outcome_for_pr_open_entries(self):
        """Without an SCM provider, pr_open entries are not checked."""
        source, child = self._source_with_pr_open()

        tracker = _make_tracker(
            all_issues=[source, child],
            metadata_map={
                "TASK-1": {
                    "oompah.backports": [
                        {"branch": "release/1.0", "status": "pr_open", "task_id": "TASK-1.1"}
                    ]
                },
                "TASK-1.1": {"oompah.backport_of": {"source": "TASK-1", "status": "pr_open"}},
            },
        )

        result = reconcile_release_picks(tracker)  # no scm

        assert result.advanced == 0

    def test_scm_exception_entry_unchanged_pass_continues(self):
        """SCM exception during PR check is absorbed; entry stays pr_open."""
        source, child = self._source_with_pr_open()

        tracker = _make_tracker(
            all_issues=[source, child],
            metadata_map={
                "TASK-1": {
                    "oompah.backports": [
                        {"branch": "release/1.0", "status": "pr_open", "task_id": "TASK-1.1"}
                    ]
                },
                "TASK-1.1": {"oompah.backport_of": {"source": "TASK-1", "status": "pr_open"}},
            },
        )
        scm = MagicMock()
        scm.find_pr_for_branch.side_effect = RuntimeError("SCM down")

        # Should not raise
        result = reconcile_release_picks(tracker, scm=scm, repo="org/repo")

        assert result.advanced == 0
        source_calls = [
            c for c in tracker.set_metadata_field.call_args_list
            if c.args[0] == "TASK-1" and c.args[1] == "oompah.backports"
        ]
        assert len(source_calls) == 0

    def test_merged_pr_child_task_updated_to_merged(self):
        """When PR merges, the child task status is updated to Merged."""
        source, child = self._source_with_pr_open()
        pr = _make_review_request("merged", source_branch="release/1.0")

        tracker = _make_tracker(
            all_issues=[source, child],
            metadata_map={
                "TASK-1": {
                    "oompah.backports": [
                        {"branch": "release/1.0", "status": "pr_open", "task_id": "TASK-1.1"}
                    ]
                },
                "TASK-1.1": {"oompah.backport_of": {"source": "TASK-1", "status": "pr_open"}},
            },
        )
        scm = MagicMock()
        scm.find_pr_for_branch.return_value = pr

        reconcile_release_picks(tracker, scm=scm, repo="org/repo")

        tracker.update_issue.assert_called_once_with("TASK-1.1", status=MERGED)

    def test_pr_outcome_idempotent_for_already_merged_entry(self):
        """A source entry already at merged is not re-processed (terminal)."""
        source = _issue("TASK-1", state=MERGED)
        child = _issue("TASK-1.1", target_branch="release/1.0", state=MERGED)
        pr = _make_review_request("merged", source_branch="release/1.0")

        tracker = _make_tracker(
            all_issues=[source, child],
            metadata_map={
                "TASK-1": {
                    "oompah.backports": [
                        {"branch": "release/1.0", "status": "merged", "task_id": "TASK-1.1"}
                    ]
                },
                "TASK-1.1": {"oompah.backport_of": {"source": "TASK-1", "status": "merged"}},
            },
        )
        scm = MagicMock()
        scm.find_pr_for_branch.return_value = pr

        result = reconcile_release_picks(tracker, scm=scm, repo="org/repo")

        assert result.advanced == 0
        scm.find_pr_for_branch.assert_not_called()

    def test_multiple_branches_only_merged_pr_advances(self):
        """Multiple backport entries: only the one with a merged PR advances."""
        source = _issue("TASK-5", state=MERGED)
        child1 = _issue("TASK-5.1", target_branch="release/1.0", state=OPEN)
        child2 = _issue("TASK-5.2", target_branch="release/2.0", state=OPEN)

        tracker = _make_tracker(
            all_issues=[source, child1, child2],
            metadata_map={
                "TASK-5": {
                    "oompah.backports": [
                        {"branch": "release/1.0", "status": "pr_open", "task_id": "TASK-5.1"},
                        {"branch": "release/2.0", "status": "pr_open", "task_id": "TASK-5.2"},
                    ]
                },
                "TASK-5.1": {
                    "oompah.backport_of": {"source": "TASK-5", "status": "pr_open"}
                },
                "TASK-5.2": {
                    "oompah.backport_of": {"source": "TASK-5", "status": "pr_open"}
                },
            },
        )

        def _pr_for_branch(repo, branch):
            if branch == "release/1.0":
                return _make_review_request("merged", source_branch="release/1.0")
            return _make_review_request("open", source_branch="release/2.0")

        scm = MagicMock()
        scm.find_pr_for_branch.side_effect = _pr_for_branch

        result = reconcile_release_picks(tracker, scm=scm, repo="org/repo")

        assert result.advanced == 1
        source_calls = [
            c for c in tracker.set_metadata_field.call_args_list
            if c.args[0] == "TASK-5" and c.args[1] == "oompah.backports"
        ]
        written_entries = parse_backports(source_calls[0].args[2])
        statuses = {e.branch: e.status for e in written_entries}
        assert statuses["release/1.0"] == ReleasePick.MERGED
        assert statuses["release/2.0"] == ReleasePick.PR_OPEN
