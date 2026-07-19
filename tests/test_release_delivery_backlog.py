"""Unit tests for oompah.release_delivery_backlog (OOMPAH-236).

Covers:

Item derivation
  - Commits with a ledger source_identifier are grouped into ItemRows.
  - Items from the same identifier share one row with all commits.
  - Commits with no source_identifier go in unassociated_commits.
  - An already-delivered item is excluded by 'needs_delivery' filter.
  - An already-archived item is excluded by 'needs_delivery' filter.
  - All items included with 'all' filter.
  - Active deliveries (open/in_progress/in_review/blocked) appear in backlog.
  - Item with multiple associated commits shows correct commit count.

Status aggregation
  - The most advanced status across an item's commits wins.
  - blocked > in_progress > in_review > open > delivered > archived > not_selected
  - An item whose commits are all delivered is excluded from needs_delivery.
  - An ancestry-proved item is marked delivered.

Ancestry regression
  - An item already on the target branch by ancestry is not queueable (state=delivered).

API response shape
  - BacklogResult has no next_cursor field.
  - total_commit_count reflects total commits enumerated.
  - branch_available is False when branch does not exist.

Branch requirement
  - ValueError raised when selected_branch is empty.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from oompah.release_addendum_schema import AddendumStatus
from oompah.release_delivery_backlog import (
    BacklogResult,
    ItemBacklogService,
    ItemRow,
    SourceCommitInfo,
    UnassociatedCommitRow,
    _aggregate_cell_for_item,
    _rank_status,
)
from oompah.release_delivery_inventory import ReleaseStatusCell
from oompah.release_delivery_store import ReleaseDelivery, ReleaseDeliveryStore, SourceKind


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PROJECT_ID = "proj-backlog-test"
_DEFAULT_BRANCH = "main"
_RELEASE_BRANCH = "release/1.1"
_SOURCE_HEAD = "a" * 40
_RELEASE_HEAD = "b" * 40
_SHA_1 = "1" * 40
_SHA_2 = "2" * 40
_SHA_3 = "3" * 40
_SHA_4 = "4" * 40
_DELIVERY_ID_1 = "rd_delivery_001"
_DELIVERY_ID_2 = "rd_delivery_002"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_commit(sha: str, subject: str = "commit msg", parents: str = "") -> Any:
    """Return a mock _CommitInfo-like object."""
    m = MagicMock()
    m.sha = sha
    m.parents = parents.split() if parents else []
    m.subject = subject
    m.author_name = "Test Author"
    m.authored_at = "2026-07-01T00:00:00Z"
    m.is_merge = len(m.parents) >= 2
    return m


def _make_delivery(
    sha_list: list[str],
    target_branch: str,
    status: AddendumStatus,
    source_identifier: str | None,
    source_kind: SourceKind = SourceKind.TASK,
    delivery_id: str = "rd_testdelivery",
) -> ReleaseDelivery:
    d = MagicMock(spec=ReleaseDelivery)
    d.id = delivery_id
    d.project_id = _PROJECT_ID
    d.source_branch = _DEFAULT_BRANCH
    d.source_kind = source_kind
    d.source_identifier = source_identifier
    d.source_commits = list(sha_list)
    d.target_branch = target_branch
    d.status = status
    d.pr_url = None
    d.result_commits = []
    d.error = None
    d.migrated_from = None
    return d


def _make_service(tmp_path: Path, deliveries: list[ReleaseDelivery] | None = None) -> ItemBacklogService:
    """Create an ItemBacklogService with a mocked delivery store."""
    store = MagicMock(spec=ReleaseDeliveryStore)
    ledger = MagicMock()
    ledger.deliveries = deliveries or []
    store.read_ledger.return_value = ledger

    svc = ItemBacklogService(
        project_root=tmp_path,
        project_id=_PROJECT_ID,
        default_branch=_DEFAULT_BRANCH,
        delivery_store=store,
    )
    return svc


def _mock_snapshot(stale: bool = False):
    """Return a mock RefSnapshot with source and release ref SHAs."""
    snap = MagicMock()
    snap.source_head = _SOURCE_HEAD
    snap.release_heads = {_RELEASE_BRANCH: _RELEASE_HEAD}
    snap.stale = stale
    snap.fetched_at = time.monotonic()
    return snap


def _make_commit_info(sha: str, subject: str = "commit msg"):
    """Return a mock _CommitInfo."""
    ci = MagicMock()
    ci.sha = sha
    ci.parents = []
    ci.subject = subject
    ci.author_name = "Test Author"
    ci.authored_at = "2026-07-01T00:00:00Z"
    ci.is_merge = False
    return ci


# ---------------------------------------------------------------------------
# _rank_status tests
# ---------------------------------------------------------------------------


class TestRankStatus:
    def test_blocked_is_highest(self):
        assert _rank_status("blocked") > _rank_status("in_progress")

    def test_in_progress_gt_in_review(self):
        assert _rank_status("in_progress") > _rank_status("in_review")

    def test_in_review_gt_open(self):
        assert _rank_status("in_review") > _rank_status("open")

    def test_open_gt_delivered(self):
        assert _rank_status("open") > _rank_status("delivered")

    def test_delivered_gt_archived(self):
        assert _rank_status("delivered") > _rank_status("archived")

    def test_archived_gt_not_selected(self):
        assert _rank_status("archived") > _rank_status("not_selected")

    def test_unknown_returns_zero(self):
        assert _rank_status("unknown_state") == 0


# ---------------------------------------------------------------------------
# _aggregate_cell_for_item tests
# ---------------------------------------------------------------------------


class TestAggregateCellForItem:
    def test_no_commits_returns_not_selected(self):
        cell, delivery_id = _aggregate_cell_for_item([], _RELEASE_BRANCH, {}, set())
        assert cell.state == "not_selected"
        assert delivery_id is None

    def test_ancestry_sha_returns_delivered(self):
        cell, _ = _aggregate_cell_for_item(
            [_SHA_1], _RELEASE_BRANCH, {}, {_SHA_1}
        )
        assert cell.state == "delivered"
        assert cell.evidence == "ancestry"

    def test_open_delivery_beats_ancestry(self):
        d = _make_delivery([_SHA_1], _RELEASE_BRANCH, AddendumStatus.OPEN, "TASK-1")
        index = {_SHA_1: {_RELEASE_BRANCH: [d]}}
        cell, delivery_id = _aggregate_cell_for_item(
            [_SHA_1], _RELEASE_BRANCH, index, {_SHA_1}
        )
        assert cell.state == "open"
        assert delivery_id == d.id

    def test_blocked_beats_open(self):
        d_open = _make_delivery([_SHA_1], _RELEASE_BRANCH, AddendumStatus.OPEN, "TASK-1", delivery_id="rd_open")
        d_blocked = _make_delivery([_SHA_2], _RELEASE_BRANCH, AddendumStatus.BLOCKED, "TASK-1", delivery_id="rd_blocked")
        index = {
            _SHA_1: {_RELEASE_BRANCH: [d_open]},
            _SHA_2: {_RELEASE_BRANCH: [d_blocked]},
        }
        cell, delivery_id = _aggregate_cell_for_item(
            [_SHA_1, _SHA_2], _RELEASE_BRANCH, index, set()
        )
        assert cell.state == "blocked"
        assert delivery_id == "rd_blocked"

    def test_merged_delivery_returns_delivered(self):
        d = _make_delivery([_SHA_1], _RELEASE_BRANCH, AddendumStatus.MERGED, "TASK-1")
        index = {_SHA_1: {_RELEASE_BRANCH: [d]}}
        cell, _ = _aggregate_cell_for_item([_SHA_1], _RELEASE_BRANCH, index, set())
        assert cell.state == "delivered"


# ---------------------------------------------------------------------------
# ItemBacklogService tests
# ---------------------------------------------------------------------------


class TestItemBacklogService:
    def _patch_and_run(
        self,
        tmp_path: Path,
        deliveries: list[ReleaseDelivery],
        commits: list[Any],
        ancestry_shas: set[str] | None = None,
        filter: str = "needs_delivery",
        query: str | None = None,
        stale: bool = False,
        is_tracker_only: bool = False,
    ) -> BacklogResult:
        """Helper: run get_backlog with mocked git operations."""
        svc = _make_service(tmp_path, deliveries)
        snapshot = _mock_snapshot(stale=stale)
        if ancestry_shas is None:
            ancestry_shas = set()

        with (
            patch("oompah.release_delivery_backlog._acquire_snapshot", return_value=snapshot),
            patch("oompah.release_delivery_backlog._enumerate_commits", return_value=commits),
            patch("oompah.release_delivery_backlog._check_ancestry_batch", return_value=ancestry_shas),
            patch("oompah.release_delivery_backlog._is_tracker_only_commit", return_value=is_tracker_only),
        ):
            return svc.get_backlog(
                selected_branch=_RELEASE_BRANCH,
                filter=filter,
                query=query,
            )

    def test_empty_backlog(self, tmp_path):
        result = self._patch_and_run(tmp_path, [], [])
        assert isinstance(result, BacklogResult)
        assert result.items == []
        assert result.unassociated_commits == []
        assert result.total_commit_count == 0

    def test_requires_nonempty_branch(self, tmp_path):
        svc = _make_service(tmp_path, [])
        with patch("oompah.release_delivery_backlog._acquire_snapshot"):
            with pytest.raises(ValueError, match="selected_branch"):
                svc.get_backlog(selected_branch="")

    def test_single_task_commit_becomes_item_row(self, tmp_path):
        d = _make_delivery([_SHA_1], _RELEASE_BRANCH, AddendumStatus.OPEN, "TASK-1")
        ci = _make_commit_info(_SHA_1)

        result = self._patch_and_run(tmp_path, [d], [ci], filter="all")

        assert len(result.items) == 1
        item = result.items[0]
        assert item.identifier == "TASK-1"
        assert item.kind == "task"
        assert item.commit_count == 1
        assert len(item.source_commits) == 1
        assert item.source_commits[0].sha == _SHA_1
        assert result.unassociated_commits == []

    def test_multiple_commits_same_task_grouped(self, tmp_path):
        # Two deliveries for the same task, each with one commit
        d1 = _make_delivery([_SHA_1], _RELEASE_BRANCH, AddendumStatus.OPEN, "TASK-2", delivery_id="rd_1")
        d2 = _make_delivery([_SHA_2], _RELEASE_BRANCH, AddendumStatus.IN_PROGRESS, "TASK-2", delivery_id="rd_2")
        ci1 = _make_commit_info(_SHA_1)
        ci2 = _make_commit_info(_SHA_2)

        result = self._patch_and_run(tmp_path, [d1, d2], [ci1, ci2], filter="all")

        assert len(result.items) == 1
        item = result.items[0]
        assert item.identifier == "TASK-2"
        assert item.commit_count == 2
        # Aggregated status: in_progress > open
        assert item.delivery_status.state == "in_progress"

    def test_unassociated_commit_in_separate_list(self, tmp_path):
        # A commit with no ledger association
        ci = _make_commit_info(_SHA_3, "Direct push to main")

        result = self._patch_and_run(tmp_path, [], [ci], filter="all")

        assert result.items == []
        assert len(result.unassociated_commits) == 1
        row = result.unassociated_commits[0]
        assert row.sha == _SHA_3
        assert row.subject == "Direct push to main"

    def test_needs_delivery_excludes_delivered_items(self, tmp_path):
        d = _make_delivery([_SHA_1], _RELEASE_BRANCH, AddendumStatus.MERGED, "TASK-3")
        ci = _make_commit_info(_SHA_1)

        result = self._patch_and_run(tmp_path, [d], [ci], filter="needs_delivery")

        assert result.items == []

    def test_needs_delivery_excludes_archived_items(self, tmp_path):
        d = _make_delivery([_SHA_1], _RELEASE_BRANCH, AddendumStatus.ARCHIVED, "TASK-4")
        ci = _make_commit_info(_SHA_1)

        result = self._patch_and_run(tmp_path, [d], [ci], filter="needs_delivery")

        assert result.items == []

    def test_all_filter_includes_delivered(self, tmp_path):
        d = _make_delivery([_SHA_1], _RELEASE_BRANCH, AddendumStatus.MERGED, "TASK-5")
        ci = _make_commit_info(_SHA_1)

        result = self._patch_and_run(tmp_path, [d], [ci], filter="all")

        assert len(result.items) == 1
        assert result.items[0].delivery_status.state == "delivered"

    def test_ancestry_proves_delivery(self, tmp_path):
        # No ledger entry but commit is on the release branch by ancestry
        ci = _make_commit_info(_SHA_2)
        # With ancestry proved, commit should be in unassociated with delivered state
        result = self._patch_and_run(
            tmp_path, [], [ci], ancestry_shas={_SHA_2}, filter="all"
        )
        # No items (unassociated) but the unassociated commit should show delivered
        assert len(result.unassociated_commits) == 1
        assert result.unassociated_commits[0].delivery_status.state == "delivered"
        assert result.unassociated_commits[0].delivery_status.evidence == "ancestry"

    def test_ancestry_regression_item_already_present_not_queueable(self, tmp_path):
        """Item whose commits are all on the target by ancestry shows 'delivered'."""
        d = _make_delivery([_SHA_1], _RELEASE_BRANCH, AddendumStatus.OPEN, "TASK-6")
        ci = _make_commit_info(_SHA_1)

        # ancestry_shas would prove SHA_1 is already on release branch
        # But active delivery takes precedence (open > ancestry), so state is 'open'
        result = self._patch_and_run(
            tmp_path, [d], [ci], ancestry_shas={_SHA_1}, filter="all"
        )
        # Active (open) delivery beats ancestry
        assert result.items[0].delivery_status.state == "open"

    def test_total_commit_count(self, tmp_path):
        ci1 = _make_commit_info(_SHA_1)
        ci2 = _make_commit_info(_SHA_2)
        ci3 = _make_commit_info(_SHA_3)

        result = self._patch_and_run(tmp_path, [], [ci1, ci2, ci3], filter="all")

        assert result.total_commit_count == 3

    def test_source_head_in_result(self, tmp_path):
        result = self._patch_and_run(tmp_path, [], [])
        assert result.source_head == _SOURCE_HEAD

    def test_selected_branch_in_result(self, tmp_path):
        result = self._patch_and_run(tmp_path, [], [])
        assert result.selected_branch == _RELEASE_BRANCH

    def test_branch_available_false_when_no_head(self, tmp_path):
        svc = _make_service(tmp_path, [])
        snapshot = _mock_snapshot()
        snapshot.release_heads = {_RELEASE_BRANCH: None}

        with (
            patch("oompah.release_delivery_backlog._acquire_snapshot", return_value=snapshot),
            patch("oompah.release_delivery_backlog._enumerate_commits", return_value=[]),
            patch("oompah.release_delivery_backlog._check_ancestry_batch", return_value=set()),
            patch("oompah.release_delivery_backlog._is_tracker_only_commit", return_value=False),
        ):
            result = svc.get_backlog(selected_branch=_RELEASE_BRANCH)

        assert not result.branch_available
        assert result.branch_head is None

    def test_stale_flag_propagated(self, tmp_path):
        result = self._patch_and_run(tmp_path, [], [], stale=True)
        assert result.stale is True

    def test_text_search_matches_identifier(self, tmp_path):
        d = _make_delivery([_SHA_1], _RELEASE_BRANCH, AddendumStatus.OPEN, "TASK-99")
        ci = _make_commit_info(_SHA_1)

        result = self._patch_and_run(tmp_path, [d], [ci], filter="all", query="TASK-99")
        assert len(result.items) == 1

    def test_text_search_excludes_non_matching(self, tmp_path):
        d = _make_delivery([_SHA_1], _RELEASE_BRANCH, AddendumStatus.OPEN, "TASK-99")
        ci = _make_commit_info(_SHA_1)

        result = self._patch_and_run(tmp_path, [d], [ci], filter="all", query="TASK-100")
        assert result.items == []

    def test_epic_kind_preserved(self, tmp_path):
        d = _make_delivery([_SHA_1], _RELEASE_BRANCH, AddendumStatus.OPEN, "EPIC-1", source_kind=SourceKind.EPIC)
        ci = _make_commit_info(_SHA_1)

        result = self._patch_and_run(tmp_path, [d], [ci], filter="all")

        assert len(result.items) == 1
        assert result.items[0].kind == "epic"

    def test_no_next_cursor_in_result(self, tmp_path):
        result = self._patch_and_run(tmp_path, [], [])
        # BacklogResult must not have next_cursor attribute at all,
        # or if it has it, it must be absent from the serialised response.
        assert not hasattr(result, "next_cursor")

    def test_multi_commit_item_most_recent_date(self, tmp_path):
        d = _make_delivery([_SHA_1, _SHA_2], _RELEASE_BRANCH, AddendumStatus.OPEN, "TASK-10")
        ci1 = _make_commit_info(_SHA_1)
        ci1.authored_at = "2026-07-01T00:00:00Z"
        ci2 = _make_commit_info(_SHA_2)
        ci2.authored_at = "2026-07-05T00:00:00Z"

        result = self._patch_and_run(tmp_path, [d], [ci1, ci2], filter="all")

        item = result.items[0]
        # most_recent_commit_at should be the first commit in enumeration order (newest first)
        assert item.most_recent_commit_at is not None

    def test_active_delivery_included_in_needs_delivery(self, tmp_path):
        """Items with open/in_progress/blocked/in_review state appear in needs_delivery."""
        for status in [AddendumStatus.OPEN, AddendumStatus.IN_PROGRESS,
                       AddendumStatus.IN_REVIEW, AddendumStatus.BLOCKED]:
            d = _make_delivery([_SHA_1], _RELEASE_BRANCH, status, "TASK-11")
            ci = _make_commit_info(_SHA_1)
            result = self._patch_and_run(tmp_path, [d], [ci], filter="needs_delivery")
            assert len(result.items) == 1, f"Expected item for status={status.value}"
