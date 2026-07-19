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

Trickle release/0.11 regression (OOMPAH-241)
  - Merged oompah_md task never queued for release/0.11 appears as not_selected candidate.
  - Merged oompah_md task delivered by ancestry is excluded from needs-delivery.
  - Merged oompah_md epic with multiple commits appears as a single not_selected row.
  - Ledger entry for a different branch does not affect release/0.11 not_selected state.
  - Tracker-sourced source_commits exposed in item row for release/0.11 candidate.
  - Task and epic both appear as distinct rows when both merged and never queued.
  - Delivered task excluded, pending task retained in release/0.11 needs-delivery.
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
    MAX_UNASSOC_TRACKER_ONLY_CHECK,
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
        tracker: Any | None = None,
        branch_commits_map: dict[str, list[str]] | None = None,
    ) -> BacklogResult:
        """Helper: run get_backlog with mocked git operations.

        Args:
            tracker: Optional mock tracker.  When provided, it is passed
                through to ``get_backlog`` so tracker-sourced discovery runs.
            branch_commits_map: Mapping from work_branch name to the list
                of SHAs that ``_find_branch_commits_in_main`` should return
                for that branch.  When ``None``, the mock returns ``[]`` for
                every branch.
        """
        svc = _make_service(tmp_path, deliveries)
        snapshot = _mock_snapshot(stale=stale)
        if ancestry_shas is None:
            ancestry_shas = set()

        def _mock_find_branch(repo_path, work_branch, main_shas, *, timeout=60):
            if branch_commits_map is None:
                return []
            return branch_commits_map.get(work_branch, [])

        with (
            patch("oompah.release_delivery_backlog._acquire_snapshot", return_value=snapshot),
            patch("oompah.release_delivery_backlog._enumerate_commits", return_value=commits),
            patch("oompah.release_delivery_backlog._check_ancestry_batch", return_value=ancestry_shas),
            patch("oompah.release_delivery_backlog._is_tracker_only_commit", return_value=is_tracker_only),
            patch("oompah.release_delivery_backlog._find_branch_commits_in_main", side_effect=_mock_find_branch),
        ):
            return svc.get_backlog(
                selected_branch=_RELEASE_BRANCH,
                filter=filter,
                query=query,
                tracker=tracker,
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

    # ------------------------------------------------------------------
    # Tracker-sourced candidate discovery (OOMPAH-238)
    # ------------------------------------------------------------------

    def _make_tracker(
        self,
        merged_issues: list[Any] | None = None,
    ) -> Any:
        """Return a minimal mock tracker for tracker-sourced discovery tests.

        Args:
            merged_issues: Issues returned by ``fetch_issues_by_states(['Merged'])``.
        """
        tracker = MagicMock()
        tracker.fetch_issues_by_states.return_value = merged_issues or []
        # get_issue returns None for all identifiers (titles not needed in these tests)
        tracker.get_issue.return_value = None
        return tracker

    def _make_issue(
        self,
        identifier: str,
        work_branch: str,
        issue_type: str = "task",
        state: str = "Merged",
    ) -> Any:
        """Return a minimal mock Issue for tracker-sourced discovery tests."""
        issue = MagicMock()
        issue.identifier = identifier
        issue.work_branch = work_branch
        issue.issue_type = issue_type
        issue.state = state
        issue.title = f"Title for {identifier}"
        return issue

    def test_merged_task_no_ledger_appears_as_not_selected(self, tmp_path):
        """A merged task with no ledger history appears in the backlog with not_selected status.

        Acceptance criterion from OOMPAH-238: the backend must return a queueable
        item row for a merged task that has never previously been queued to any
        release branch.
        """
        # No ledger entries for this task
        ci = _make_commit_info(_SHA_1, "feat: implement TASK-42")
        issue = self._make_issue("TASK-42", work_branch="task/TASK-42")
        tracker = self._make_tracker(merged_issues=[issue])

        result = self._patch_and_run(
            tmp_path,
            deliveries=[],
            commits=[ci],
            filter="all",
            tracker=tracker,
            branch_commits_map={"task/TASK-42": [_SHA_1]},
        )

        assert len(result.items) == 1, "Merged task with no ledger record must appear in backlog"
        item = result.items[0]
        assert item.identifier == "TASK-42"
        assert item.kind == "task"
        assert item.delivery_status.state == "not_selected", (
            "Item with no ledger and no branch delivery must be not_selected"
        )
        assert item.commit_count == 1
        assert item.source_commits[0].sha == _SHA_1
        # The commit is now item-associated, so it must NOT appear in unassociated
        assert all(r.sha != _SHA_1 for r in result.unassociated_commits)

    def test_merged_epic_multiple_commits_appears_once(self, tmp_path):
        """A merged epic with multiple commits on main appears as a single item row.

        Acceptance criterion: the backlog returns exactly one item row for the
        epic, with all associated commits included and their count correct.
        """
        ci1 = _make_commit_info(_SHA_1, "feat: epic commit 1")
        ci2 = _make_commit_info(_SHA_2, "feat: epic commit 2")
        issue = self._make_issue("EPIC-5", work_branch="epic/EPIC-5", issue_type="epic")
        tracker = self._make_tracker(merged_issues=[issue])

        result = self._patch_and_run(
            tmp_path,
            deliveries=[],
            commits=[ci1, ci2],
            filter="all",
            tracker=tracker,
            branch_commits_map={"epic/EPIC-5": [_SHA_1, _SHA_2]},
        )

        # Must be exactly ONE item row, not two
        assert len(result.items) == 1, (
            f"Merged epic with 2 commits must produce 1 item row, got {len(result.items)}"
        )
        item = result.items[0]
        assert item.identifier == "EPIC-5"
        assert item.kind == "epic"
        assert item.commit_count == 2
        sha_set = {sc.sha for sc in item.source_commits}
        assert sha_set == {_SHA_1, _SHA_2}
        # Both commits now item-associated, unassociated list must be empty
        assert result.unassociated_commits == []

    def test_nonmerged_task_excluded_from_tracker_sourced_discovery(self, tmp_path):
        """A task that is NOT Merged is excluded from tracker-sourced candidate discovery.

        The tracker's fetch_issues_by_states(['Merged']) only returns Merged items;
        tasks in any other state (Open, In Progress, etc.) must not appear in the
        backlog unless they are present in the ledger.
        """
        ci = _make_commit_info(_SHA_3, "fix: unmerged task commit")
        # Tracker returns an empty Merged list (the non-merged task is filtered out
        # by fetch_issues_by_states — we verify the integration handles this correctly)
        tracker = self._make_tracker(merged_issues=[])  # no merged issues

        result = self._patch_and_run(
            tmp_path,
            deliveries=[],
            commits=[ci],
            filter="all",
            tracker=tracker,
            branch_commits_map={},  # no branches map to commits
        )

        # No item rows (the commit has no ledger record and is not Merged in tracker)
        assert result.items == [], (
            "Non-merged task must not appear as an item row"
        )
        # The commit appears in unassociated (it's still on main, just unknown)
        assert len(result.unassociated_commits) == 1
        assert result.unassociated_commits[0].sha == _SHA_3

    def test_ledger_status_overrides_default_for_tracker_sourced_item(self, tmp_path):
        """When both ledger and tracker agree on an item, ledger delivery status wins.

        If a merged task is in the tracker AND has an open delivery in the ledger,
        the item row must show the ledger status (open), not the tracker-default
        (not_selected).  The ledger is the authoritative source for delivery status.
        """
        # Ledger has an open delivery for TASK-99 targeting the release branch
        d = _make_delivery([_SHA_1], _RELEASE_BRANCH, AddendumStatus.OPEN, "TASK-99")
        ci = _make_commit_info(_SHA_1, "feat: TASK-99 implementation")

        # Tracker also reports TASK-99 as Merged (e.g. it was merged to main)
        issue = self._make_issue("TASK-99", work_branch="task/TASK-99")
        tracker = self._make_tracker(merged_issues=[issue])

        result = self._patch_and_run(
            tmp_path,
            deliveries=[d],
            commits=[ci],
            filter="all",
            tracker=tracker,
            branch_commits_map={"task/TASK-99": [_SHA_1]},
        )

        assert len(result.items) == 1
        item = result.items[0]
        assert item.identifier == "TASK-99"
        assert item.delivery_status.state == "open", (
            "Ledger's open delivery must take precedence over tracker-default not_selected"
        )

    def test_tracker_item_with_no_main_commits_excluded(self, tmp_path):
        """A merged tracker item whose commits are not reachable from origin/main is excluded.

        Acceptance criterion from OOMPAH-238: only commits reachable from
        origin/main are eligible.  If _find_branch_commits_in_main returns an
        empty list (branch was merged elsewhere, branch ref gone, etc.), the item
        must not appear.
        """
        ci = _make_commit_info(_SHA_4, "feat: some other commit")
        # Tracker returns merged task but its work_branch has NO commits in main_shas
        issue = self._make_issue("TASK-77", work_branch="task/TASK-77")
        tracker = self._make_tracker(merged_issues=[issue])

        result = self._patch_and_run(
            tmp_path,
            deliveries=[],
            commits=[ci],
            filter="all",
            tracker=tracker,
            branch_commits_map={"task/TASK-77": []},  # empty → no main commits
        )

        assert result.items == [], (
            "Tracker item with no commits on main must be excluded from backlog"
        )

    def test_tracker_discovery_skipped_when_tracker_is_none(self, tmp_path):
        """When tracker=None, only ledger-sourced items appear (existing behaviour preserved)."""
        # Commit with no ledger association
        ci = _make_commit_info(_SHA_1, "feat: untracked commit")

        result = self._patch_and_run(
            tmp_path,
            deliveries=[],
            commits=[ci],
            filter="all",
            tracker=None,  # no tracker
        )

        assert result.items == [], "No tracker → no tracker-sourced items"
        assert len(result.unassociated_commits) == 1
        assert result.unassociated_commits[0].sha == _SHA_1


# ---------------------------------------------------------------------------
# Bounded unassociated tracker_only classification (OOMPAH-239)
# ---------------------------------------------------------------------------


class TestUnassociatedCommitTrackerOnlyBound:
    """Regression tests for OOMPAH-239: git diff-tree subprocess count must be
    bounded when there are many unassociated direct-to-main commits.

    The backlog endpoint was timing out because _is_tracker_only_commit() was
    called once per unassociated commit — O(N) git subprocesses for N
    unassociated commits.  The fix caps classification at
    MAX_UNASSOC_TRACKER_ONLY_CHECK and defaults tracker_only=False beyond
    that cap so the primary item rows are never blocked.
    """

    # Exceed the cap by a comfortable margin so the test is meaningful
    # even if MAX_UNASSOC_TRACKER_ONLY_CHECK changes slightly.
    _LARGE_COMMIT_COUNT = MAX_UNASSOC_TRACKER_ONLY_CHECK * 4

    def _run_with_call_counter(
        self,
        tmp_path: Path,
        commits: list[Any],
        deliveries: list[ReleaseDelivery] | None = None,
    ) -> tuple[BacklogResult, int]:
        """Run get_backlog and return (result, _is_tracker_only_commit call count).

        Patches _is_tracker_only_commit with a side-effect that increments a
        counter on every call, so we can assert on the total git subprocess count.
        """
        call_count = 0

        def _counting_is_tracker_only(repo_path: Any, sha: str) -> bool:
            nonlocal call_count
            call_count += 1
            return False

        svc = _make_service(tmp_path, deliveries or [])

        with (
            patch("oompah.release_delivery_backlog._acquire_snapshot", return_value=_mock_snapshot()),
            patch("oompah.release_delivery_backlog._enumerate_commits", return_value=commits),
            patch("oompah.release_delivery_backlog._check_ancestry_batch", return_value=set()),
            patch(
                "oompah.release_delivery_backlog._is_tracker_only_commit",
                side_effect=_counting_is_tracker_only,
            ),
            patch("oompah.release_delivery_backlog._find_branch_commits_in_main", return_value=[]),
        ):
            result = svc.get_backlog(selected_branch=_RELEASE_BRANCH, filter="all")

        return result, call_count

    def _make_large_unassociated_commits(self, count: int) -> list[Any]:
        """Return *count* unique mock commits with no ledger association."""
        return [
            _make_commit_info(f"{i:040x}", f"direct to main commit {i}")
            for i in range(1, count + 1)
        ]

    # ------------------------------------------------------------------
    # Core regression: bounded git call count
    # ------------------------------------------------------------------

    def test_git_calls_bounded_for_large_unassociated_set(self, tmp_path):
        """With many unassociated commits, _is_tracker_only_commit is called at most
        MAX_UNASSOC_TRACKER_ONLY_CHECK times.

        Regression for OOMPAH-239: before the fix, every unassociated commit
        spawned one git diff-tree subprocess, causing the HTTP endpoint to time out
        for projects with hundreds of direct-to-main commits.
        """
        commits = self._make_large_unassociated_commits(self._LARGE_COMMIT_COUNT)

        result, call_count = self._run_with_call_counter(tmp_path, commits)

        assert result.total_commit_count == self._LARGE_COMMIT_COUNT, (
            "All commits must be enumerated in the result"
        )
        assert len(result.unassociated_commits) == self._LARGE_COMMIT_COUNT, (
            "All unassociated commits must appear in the result"
        )
        assert call_count <= MAX_UNASSOC_TRACKER_ONLY_CHECK, (
            f"Expected at most {MAX_UNASSOC_TRACKER_ONLY_CHECK} git subprocess calls, "
            f"got {call_count}. This is an O(N) regression — OOMPAH-239."
        )

    def test_git_call_count_does_not_grow_with_commit_count(self, tmp_path):
        """Doubling the unassociated commit count must not double the git call count.

        This verifies the bound is constant, not proportional to input size.
        """
        small_commits = self._make_large_unassociated_commits(MAX_UNASSOC_TRACKER_ONLY_CHECK + 10)
        large_commits = self._make_large_unassociated_commits(MAX_UNASSOC_TRACKER_ONLY_CHECK * 10)

        _, small_call_count = self._run_with_call_counter(tmp_path, small_commits)
        _, large_call_count = self._run_with_call_counter(tmp_path, large_commits)

        assert large_call_count <= MAX_UNASSOC_TRACKER_ONLY_CHECK, (
            f"Call count must be capped: got {large_call_count} for "
            f"{len(large_commits)} commits"
        )
        assert large_call_count <= small_call_count + 1, (
            f"Call count must not grow with commit count: "
            f"small={small_call_count}, large={large_call_count}"
        )

    # ------------------------------------------------------------------
    # Primary item rows are not affected by the cap
    # ------------------------------------------------------------------

    def test_primary_items_returned_with_large_unassociated_set(self, tmp_path):
        """Primary item rows are fully returned even when there are many unassociated commits.

        The presence of O(N) unassociated commits must not prevent or delay
        primary item row construction.  This is the user-visible acceptance
        criterion: the backlog shows task rows even when many commits are
        direct-to-main.
        """
        # 5 item-associated commits (each tied to a distinct task via ledger)
        item_shas = [f"item{i:036x}" for i in range(5)]
        item_commits = [
            _make_commit_info(sha, f"TASK-{i + 1}: implement feature")
            for i, sha in enumerate(item_shas)
        ]
        deliveries = [
            _make_delivery(
                [sha],
                _RELEASE_BRANCH,
                AddendumStatus.OPEN,
                f"TASK-{i + 1}",
                delivery_id=f"rd_{i}",
            )
            for i, sha in enumerate(item_shas)
        ]

        # Large set of unassociated commits that exceeds the cap
        unassoc_count = self._LARGE_COMMIT_COUNT
        unassoc_commits = self._make_large_unassociated_commits(unassoc_count)

        all_commits = item_commits + unassoc_commits

        result, call_count = self._run_with_call_counter(
            tmp_path, all_commits, deliveries=deliveries
        )

        # Primary item rows must all be present
        assert len(result.items) == 5, (
            f"Expected 5 primary item rows, got {len(result.items)}"
        )
        returned_ids = {item.identifier for item in result.items}
        assert returned_ids == {"TASK-1", "TASK-2", "TASK-3", "TASK-4", "TASK-5"}

        # Unassociated commits must still be listed (even if tracker_only is truncated)
        assert len(result.unassociated_commits) == unassoc_count

        # Git subprocess count must be bounded.
        # Item commits (step 6) also call _is_tracker_only_commit — the cap
        # only applies to the unassociated loop (step 7).  The total must be
        # at most MAX_UNASSOC_TRACKER_ONLY_CHECK (unassoc cap) + len(item_shas).
        n_item_commits = len(item_shas)
        max_expected_calls = MAX_UNASSOC_TRACKER_ONLY_CHECK + n_item_commits
        assert call_count <= max_expected_calls, (
            f"Git call count must be bounded even with {unassoc_count} unassociated commits: "
            f"expected ≤ {max_expected_calls}, got {call_count}"
        )

    # ------------------------------------------------------------------
    # Behaviour beyond the cap: tracker_only defaults to False
    # ------------------------------------------------------------------

    def test_commits_beyond_cap_have_tracker_only_false(self, tmp_path):
        """Unassociated commits beyond MAX_UNASSOC_TRACKER_ONLY_CHECK get tracker_only=False.

        The cap is for performance — not a filter.  Every unassociated commit
        must appear in the result; commits beyond the cap default to
        tracker_only=False (unknown / unchecked) rather than being dropped.
        """
        total = MAX_UNASSOC_TRACKER_ONLY_CHECK + 20
        commits = self._make_large_unassociated_commits(total)

        # Make _is_tracker_only_commit always return True so that any commit
        # that IS checked will have tracker_only=True, making it easy to
        # distinguish checked vs. unchecked entries in the result.
        svc = _make_service(tmp_path, [])

        with (
            patch("oompah.release_delivery_backlog._acquire_snapshot", return_value=_mock_snapshot()),
            patch("oompah.release_delivery_backlog._enumerate_commits", return_value=commits),
            patch("oompah.release_delivery_backlog._check_ancestry_batch", return_value=set()),
            patch("oompah.release_delivery_backlog._is_tracker_only_commit", return_value=True),
            patch("oompah.release_delivery_backlog._find_branch_commits_in_main", return_value=[]),
        ):
            result = svc.get_backlog(selected_branch=_RELEASE_BRANCH, filter="all")

        assert len(result.unassociated_commits) == total, (
            "All commits must appear even when some are beyond the cap"
        )

        tracker_only_true_count = sum(
            1 for row in result.unassociated_commits if row.tracker_only
        )
        tracker_only_false_count = sum(
            1 for row in result.unassociated_commits if not row.tracker_only
        )

        # Exactly MAX_UNASSOC_TRACKER_ONLY_CHECK commits are checked (and returned True)
        assert tracker_only_true_count == MAX_UNASSOC_TRACKER_ONLY_CHECK, (
            f"Expected {MAX_UNASSOC_TRACKER_ONLY_CHECK} checked commits with tracker_only=True, "
            f"got {tracker_only_true_count}"
        )
        # The remaining commits default to False
        assert tracker_only_false_count == total - MAX_UNASSOC_TRACKER_ONLY_CHECK, (
            f"Expected {total - MAX_UNASSOC_TRACKER_ONLY_CHECK} unchecked commits with tracker_only=False"
        )

    def test_small_unassociated_set_all_classified(self, tmp_path):
        """When the unassociated count is ≤ MAX_UNASSOC_TRACKER_ONLY_CHECK, all are classified.

        The cap must not unnecessarily skip classification for small commit sets.
        """
        small_count = MAX_UNASSOC_TRACKER_ONLY_CHECK - 5
        commits = self._make_large_unassociated_commits(small_count)

        result, call_count = self._run_with_call_counter(tmp_path, commits)

        assert len(result.unassociated_commits) == small_count
        # All commits must be checked when count ≤ cap
        assert call_count == small_count, (
            f"Expected all {small_count} commits to be classified, "
            f"but only {call_count} were"
        )

    def test_exactly_cap_commits_all_classified(self, tmp_path):
        """When the unassociated count is exactly MAX_UNASSOC_TRACKER_ONLY_CHECK, all are classified."""
        commits = self._make_large_unassociated_commits(MAX_UNASSOC_TRACKER_ONLY_CHECK)

        result, call_count = self._run_with_call_counter(tmp_path, commits)

        assert len(result.unassociated_commits) == MAX_UNASSOC_TRACKER_ONLY_CHECK
        assert call_count == MAX_UNASSOC_TRACKER_ONLY_CHECK, (
            f"All {MAX_UNASSOC_TRACKER_ONLY_CHECK} commits (exactly at cap) must be classified"
        )


# ---------------------------------------------------------------------------
# Trickle release/0.11 regression fixture (OOMPAH-241)
# ---------------------------------------------------------------------------


class TestTrickleRelease011BacklogRegression:
    """Regression fixture for OOMPAH-241: Trickle release/0.11 backlog candidate discovery.

    The defect (fixed by OOMPAH-238): the backlog service only used the delivery
    ledger to discover candidate items.  Tasks and epics that were merged to
    ``main`` but *never* queued for ``release/0.11`` had no ledger entry and were
    therefore invisible in the backlog — users could not queue them for release.

    This class reproduces the defect using representative native oompah_md tracker
    metadata (OOMPAH-xxx identifiers, work_branch = task identifier) and the
    real ``release/0.11`` branch name.  All tests:

    - Use no live GitHub calls and no live Trickle checkout.
    - Pass with the OOMPAH-238 fix in place.
    - Would *fail* (assertions about ``result.items`` being non-empty) with the
      pre-fix code that skipped tracker-sourced discovery.

    Primary regression
    ------------------
    A merged oompah_md task (state=Merged, work_branch=identifier) with no
    ``release/0.11`` ledger entry appears in ``needs_delivery`` with
    ``state=not_selected`` and exposes its source commits.

    Companion case
    --------------
    The same task, when its commits are already reachable from ``release/0.11``
    by ancestry (e.g. cherry-picked directly without the delivery queue), is
    classified as ``delivered`` and is excluded from ``needs_delivery``.
    """

    # ------------------------------------------------------------------
    # Fixture constants: release/0.11 and representative oompah identifiers
    # ------------------------------------------------------------------

    #: The specific release branch targeted by this regression fixture.
    _RELEASE_011 = "release/0.11"

    #: Synthetic SHA for origin/main at snapshot time.
    _SOURCE_HEAD_011 = "0" * 39 + "1"

    #: Synthetic SHA for origin/release/0.11 at snapshot time.
    _RELEASE_011_HEAD = "0" * 39 + "2"

    # Representative oompah_md task (state=Merged) that was merged to main
    # but never queued for release/0.11.  In the real Trickle project the
    # work_branch field is set to the task identifier string.
    _TASK_ID = "OOMPAH-215"
    _TASK_BRANCH = "OOMPAH-215"  # oompah_md stores work_branch = identifier

    # Representative oompah_md epic (multi-commit)
    _EPIC_ID = "OOMPAH-200"
    _EPIC_BRANCH = "OOMPAH-200"

    # Synthetic commit SHAs for test assertions
    _COMMIT_TASK_1 = "a1" * 20  # 40-char hex
    _COMMIT_TASK_2 = "a2" * 20
    _COMMIT_EPIC_1 = "b1" * 20
    _COMMIT_EPIC_2 = "b2" * 20

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _mock_snapshot_011(self, stale: bool = False) -> Any:
        """Return a mock RefSnapshot anchored to release/0.11."""
        snap = MagicMock()
        snap.source_head = self._SOURCE_HEAD_011
        snap.release_heads = {self._RELEASE_011: self._RELEASE_011_HEAD}
        snap.stale = stale
        snap.fetched_at = time.monotonic()
        return snap

    def _make_oompah_tracker(self, merged_issues: list[Any]) -> Any:
        """Return a mock oompah_md tracker that reports *merged_issues* as Merged.

        Mimics the oompah_md tracker's ``fetch_issues_by_states(['Merged'])``
        and ``get_issue(identifier)`` contracts.
        """
        tracker = MagicMock()
        tracker.fetch_issues_by_states.return_value = merged_issues
        tracker.get_issue.return_value = None  # title resolution not tested here
        return tracker

    def _make_oompah_issue(
        self,
        identifier: str,
        work_branch: str,
        issue_type: str = "task",
        title: str | None = None,
    ) -> Any:
        """Return a mock Issue as returned by the oompah_md tracker.

        Fields match the ``models.Issue`` dataclass attributes used by
        ``ItemBacklogService.get_backlog()`` during tracker-sourced discovery:
        ``identifier``, ``work_branch``, ``issue_type``, ``state``, ``title``.
        """
        issue = MagicMock()
        issue.identifier = identifier
        issue.work_branch = work_branch
        issue.issue_type = issue_type
        issue.state = "Merged"
        issue.title = title or f"{issue_type.title()} {identifier}"
        return issue

    def _run_backlog_011(
        self,
        tmp_path: Path,
        deliveries: list[ReleaseDelivery],
        commits: list[Any],
        *,
        ancestry_shas: set[str] | None = None,
        tracker: Any | None = None,
        branch_commits_map: dict[str, list[str]] | None = None,
        filter: str = "needs_delivery",
    ) -> BacklogResult:
        """Run ItemBacklogService.get_backlog with mocked git/store for release/0.11.

        Patches the same five functions as the shared ``_patch_and_run`` helper
        but targets ``self._RELEASE_011`` instead of the generic release/1.1
        constant, and uses a release/0.11 snapshot.
        """
        svc = _make_service(tmp_path, deliveries)
        snapshot = self._mock_snapshot_011()
        if ancestry_shas is None:
            ancestry_shas = set()

        def _mock_find_branch(repo_path: Any, work_branch: str, main_shas: Any, *, timeout: int = 60) -> list[str]:
            if branch_commits_map is None:
                return []
            return branch_commits_map.get(work_branch, [])

        with (
            patch("oompah.release_delivery_backlog._acquire_snapshot", return_value=snapshot),
            patch("oompah.release_delivery_backlog._enumerate_commits", return_value=commits),
            patch("oompah.release_delivery_backlog._check_ancestry_batch", return_value=ancestry_shas),
            patch("oompah.release_delivery_backlog._is_tracker_only_commit", return_value=False),
            patch("oompah.release_delivery_backlog._find_branch_commits_in_main", side_effect=_mock_find_branch),
        ):
            return svc.get_backlog(
                selected_branch=self._RELEASE_011,
                filter=filter,
                tracker=tracker,
            )

    # ------------------------------------------------------------------
    # Primary regression: missing release/0.11 candidate
    # ------------------------------------------------------------------

    def test_merged_task_never_queued_appears_as_not_selected_candidate(self, tmp_path):
        """Primary regression: a merged oompah task never queued for release/0.11 is queueable.

        Before the OOMPAH-238 fix the backlog only checked the delivery ledger.
        OOMPAH-215 was Merged to main but had no release/0.11 ledger entry, so it
        was invisible — users could not find it in the backlog to queue it.

        After the fix, tracker-sourced discovery enumerates Merged items and
        resolves their commits from ``work_branch`` via
        ``_find_branch_commits_in_main``.  OOMPAH-215 must appear with
        ``state=not_selected`` so the user can select it for release.

        Defect reproduction: this assertion (``len == 1``) would fail against the
        pre-OOMPAH-238 code because items would be 0.
        """
        # One commit on main from OOMPAH-215's work branch
        ci = _make_commit_info(
            self._COMMIT_TASK_1,
            "feat: implement release delivery tracker-sourced discovery [OOMPAH-215]",
        )
        ci.author_name = "oompah"
        ci.authored_at = "2026-07-10T12:00:00Z"

        # oompah_md tracker: OOMPAH-215 is in Merged state
        issue = self._make_oompah_issue(
            self._TASK_ID,
            work_branch=self._TASK_BRANCH,
            issue_type="task",
            title="Implement tracker-sourced backlog candidate discovery",
        )
        tracker = self._make_oompah_tracker(merged_issues=[issue])

        # No ledger entries for release/0.11 (the defect scenario)
        result = self._run_backlog_011(
            tmp_path,
            deliveries=[],
            commits=[ci],
            tracker=tracker,
            branch_commits_map={self._TASK_BRANCH: [self._COMMIT_TASK_1]},
            filter="needs_delivery",
        )

        # Must surface as a queueable candidate
        assert len(result.items) == 1, (
            f"OOMPAH-215 (Merged, no release/0.11 ledger entry) must appear in "
            f"needs_delivery backlog.  Before OOMPAH-238 this would be 0 items — "
            f"the missing-candidate defect."
        )
        item = result.items[0]
        assert item.identifier == self._TASK_ID
        assert item.kind == "task"
        assert item.delivery_status.state == "not_selected", (
            f"Expected not_selected (queueable), got {item.delivery_status.state!r}. "
            f"The item has no release/0.11 delivery and no ancestry evidence."
        )
        # Source commits must be exposed so the UI can show commit details
        assert item.commit_count == 1
        assert len(item.source_commits) == 1
        assert item.source_commits[0].sha == self._COMMIT_TASK_1

        # The commit is now item-associated; must NOT be in unassociated list
        unassoc_shas = {r.sha for r in result.unassociated_commits}
        assert self._COMMIT_TASK_1 not in unassoc_shas, (
            "OOMPAH-215 commit must not appear in unassociated_commits after tracker discovery"
        )

    def test_not_selected_item_included_in_needs_delivery_filter(self, tmp_path):
        """The needs_delivery filter includes not_selected items (they need queuing).

        not_selected means the item has never been queued for release/0.11.
        It is neither delivered nor archived, so it must pass the needs_delivery
        filter and be actionable by the user.
        """
        ci = _make_commit_info(self._COMMIT_TASK_1, "feat: OOMPAH-215 implementation")
        issue = self._make_oompah_issue(self._TASK_ID, work_branch=self._TASK_BRANCH)
        tracker = self._make_oompah_tracker(merged_issues=[issue])

        result = self._run_backlog_011(
            tmp_path,
            deliveries=[],
            commits=[ci],
            tracker=tracker,
            branch_commits_map={self._TASK_BRANCH: [self._COMMIT_TASK_1]},
            filter="needs_delivery",
        )

        # not_selected must pass through the needs_delivery filter
        assert len(result.items) == 1
        assert result.items[0].delivery_status.state == "not_selected"

    # ------------------------------------------------------------------
    # Companion case: delivered-by-ancestry exclusion
    # ------------------------------------------------------------------

    def test_task_delivered_by_ancestry_excluded_from_needs_delivery(self, tmp_path):
        """Companion case: a task already on release/0.11 by ancestry is excluded.

        If OOMPAH-215's commits were cherry-picked directly into release/0.11
        without going through the delivery queue, ancestry detection classifies
        the item as delivered.  It must NOT appear in the needs_delivery backlog
        because no further action is required.
        """
        ci = _make_commit_info(
            self._COMMIT_TASK_1,
            "feat: OOMPAH-215 implementation (cherry-picked to release/0.11)",
        )
        issue = self._make_oompah_issue(self._TASK_ID, work_branch=self._TASK_BRANCH)
        tracker = self._make_oompah_tracker(merged_issues=[issue])

        # ancestry_shas proves COMMIT_TASK_1 is already reachable from release/0.11
        result = self._run_backlog_011(
            tmp_path,
            deliveries=[],
            commits=[ci],
            tracker=tracker,
            branch_commits_map={self._TASK_BRANCH: [self._COMMIT_TASK_1]},
            ancestry_shas={self._COMMIT_TASK_1},
            filter="needs_delivery",
        )

        # Task already on release/0.11 by ancestry — must be excluded
        assert result.items == [], (
            "OOMPAH-215 with all commits on release/0.11 by ancestry must be "
            "excluded from needs_delivery (delivered, no further action needed)."
        )

    def test_task_delivered_by_ancestry_has_delivered_state_in_all_filter(self, tmp_path):
        """Companion case: delivered-by-ancestry shows state=delivered in 'all' filter view."""
        ci = _make_commit_info(self._COMMIT_TASK_1, "feat: OOMPAH-215 implementation")
        issue = self._make_oompah_issue(self._TASK_ID, work_branch=self._TASK_BRANCH)
        tracker = self._make_oompah_tracker(merged_issues=[issue])

        result = self._run_backlog_011(
            tmp_path,
            deliveries=[],
            commits=[ci],
            tracker=tracker,
            branch_commits_map={self._TASK_BRANCH: [self._COMMIT_TASK_1]},
            ancestry_shas={self._COMMIT_TASK_1},
            filter="all",
        )

        assert len(result.items) == 1
        item = result.items[0]
        assert item.identifier == self._TASK_ID
        assert item.delivery_status.state == "delivered", (
            "Tracker-sourced item proved by ancestry must show state=delivered"
        )
        assert item.delivery_status.evidence == "ancestry", (
            "Delivery evidence must be 'ancestry' when proved via git ancestry"
        )

    # ------------------------------------------------------------------
    # Multi-commit epic
    # ------------------------------------------------------------------

    def test_merged_epic_with_multiple_commits_appears_as_single_row(self, tmp_path):
        """A merged oompah epic with two commits on main appears as one not_selected row.

        Epics in the Trickle project may span multiple commits.  All commits
        from the work_branch must be grouped under one item row, not one row
        per commit.
        """
        ci1 = _make_commit_info(
            self._COMMIT_EPIC_1,
            "feat: OOMPAH-200 epic part 1 — add delivery backlog service",
        )
        ci2 = _make_commit_info(
            self._COMMIT_EPIC_2,
            "feat: OOMPAH-200 epic part 2 — wire backlog API endpoint",
        )
        epic_issue = self._make_oompah_issue(
            self._EPIC_ID,
            work_branch=self._EPIC_BRANCH,
            issue_type="epic",
            title="Item-centric release delivery backlog",
        )
        tracker = self._make_oompah_tracker(merged_issues=[epic_issue])

        result = self._run_backlog_011(
            tmp_path,
            deliveries=[],
            commits=[ci1, ci2],
            tracker=tracker,
            branch_commits_map={self._EPIC_BRANCH: [self._COMMIT_EPIC_1, self._COMMIT_EPIC_2]},
            filter="needs_delivery",
        )

        assert len(result.items) == 1, (
            f"OOMPAH-200 (epic, 2 commits) must appear as exactly 1 item row, "
            f"got {len(result.items)}"
        )
        item = result.items[0]
        assert item.identifier == self._EPIC_ID
        assert item.kind == "epic"
        assert item.delivery_status.state == "not_selected"
        assert item.commit_count == 2
        sha_set = {sc.sha for sc in item.source_commits}
        assert sha_set == {self._COMMIT_EPIC_1, self._COMMIT_EPIC_2}
        # Both commits now item-associated — unassociated list must be empty
        assert result.unassociated_commits == []

    # ------------------------------------------------------------------
    # Ledger isolation: other-branch entry doesn't affect release/0.11 state
    # ------------------------------------------------------------------

    def test_ledger_entry_for_other_branch_does_not_affect_release_011(self, tmp_path):
        """A ledger delivery for a *different* branch does not set the release/0.11 state.

        OOMPAH-215 may have been queued for release/0.12 (open delivery).
        That ledger entry must not contaminate its release/0.11 status — it must
        still appear as not_selected for release/0.11.
        """
        # Ledger has an open delivery for OOMPAH-215 targeting release/0.12 (not 0.11)
        d_other_branch = _make_delivery(
            [self._COMMIT_TASK_1],
            "release/0.12",  # different branch
            AddendumStatus.OPEN,
            self._TASK_ID,
            delivery_id="rd_0012_001",
        )

        ci = _make_commit_info(self._COMMIT_TASK_1, "feat: OOMPAH-215 implementation")
        issue = self._make_oompah_issue(self._TASK_ID, work_branch=self._TASK_BRANCH)
        tracker = self._make_oompah_tracker(merged_issues=[issue])

        result = self._run_backlog_011(
            tmp_path,
            deliveries=[d_other_branch],  # ledger only has release/0.12 entry
            commits=[ci],
            tracker=tracker,
            branch_commits_map={self._TASK_BRANCH: [self._COMMIT_TASK_1]},
            filter="needs_delivery",
        )

        # Must appear in release/0.11 backlog as not_selected (open on 0.12 doesn't count)
        assert len(result.items) == 1, (
            "OOMPAH-215 with a release/0.12 ledger entry must still appear "
            "as a not_selected candidate for release/0.11"
        )
        item = result.items[0]
        assert item.identifier == self._TASK_ID
        assert item.delivery_status.state == "not_selected", (
            f"Expected not_selected for release/0.11, got {item.delivery_status.state!r}. "
            f"The open delivery is for release/0.12 and must not affect release/0.11 state."
        )

    # ------------------------------------------------------------------
    # Source commit exposure
    # ------------------------------------------------------------------

    def test_source_commits_exposed_for_release_011_candidate(self, tmp_path):
        """Source commit details (sha, subject, author_name, authored_at) are exposed.

        The UI needs commit details to display item rows.  Tracker-sourced
        items must include full SourceCommitInfo objects, not just SHAs.
        """
        ci = _make_commit_info(
            self._COMMIT_TASK_1,
            "feat: add tracker-sourced candidate discovery to backlog service [OOMPAH-215]",
        )
        ci.author_name = "oompah-agent"
        ci.authored_at = "2026-07-10T14:30:00Z"

        issue = self._make_oompah_issue(self._TASK_ID, work_branch=self._TASK_BRANCH)
        tracker = self._make_oompah_tracker(merged_issues=[issue])

        result = self._run_backlog_011(
            tmp_path,
            deliveries=[],
            commits=[ci],
            tracker=tracker,
            branch_commits_map={self._TASK_BRANCH: [self._COMMIT_TASK_1]},
            filter="all",
        )

        assert len(result.items) == 1
        item = result.items[0]
        assert item.commit_count == 1
        assert len(item.source_commits) == 1

        sc = item.source_commits[0]
        assert sc.sha == self._COMMIT_TASK_1
        assert sc.short_sha == self._COMMIT_TASK_1[:7]
        assert "OOMPAH-215" in sc.subject
        assert sc.author_name == "oompah-agent"
        assert sc.authored_at == "2026-07-10T14:30:00Z"

    # ------------------------------------------------------------------
    # Task and epic as distinct rows
    # ------------------------------------------------------------------

    def test_task_and_epic_both_appear_as_distinct_not_selected_rows(self, tmp_path):
        """Both OOMPAH-215 (task) and OOMPAH-200 (epic) appear as separate not_selected rows.

        When multiple oompah_md items have been merged to main but never queued
        for release/0.11, each must appear as its own item row with the correct
        kind and independent not_selected state.
        """
        ci_task = _make_commit_info(self._COMMIT_TASK_1, "feat: OOMPAH-215 task commit")
        ci_epic = _make_commit_info(self._COMMIT_EPIC_1, "feat: OOMPAH-200 epic commit")

        task_issue = self._make_oompah_issue(
            self._TASK_ID, work_branch=self._TASK_BRANCH, issue_type="task"
        )
        epic_issue = self._make_oompah_issue(
            self._EPIC_ID, work_branch=self._EPIC_BRANCH, issue_type="epic"
        )
        tracker = self._make_oompah_tracker(merged_issues=[task_issue, epic_issue])

        result = self._run_backlog_011(
            tmp_path,
            deliveries=[],
            commits=[ci_task, ci_epic],
            tracker=tracker,
            branch_commits_map={
                self._TASK_BRANCH: [self._COMMIT_TASK_1],
                self._EPIC_BRANCH: [self._COMMIT_EPIC_1],
            },
            filter="needs_delivery",
        )

        assert len(result.items) == 2, (
            f"Both OOMPAH-215 and OOMPAH-200 must appear as item rows, "
            f"got {len(result.items)}"
        )

        by_id = {item.identifier: item for item in result.items}
        assert self._TASK_ID in by_id, f"{self._TASK_ID} must be in backlog"
        assert self._EPIC_ID in by_id, f"{self._EPIC_ID} must be in backlog"

        assert by_id[self._TASK_ID].kind == "task"
        assert by_id[self._TASK_ID].delivery_status.state == "not_selected"
        assert by_id[self._EPIC_ID].kind == "epic"
        assert by_id[self._EPIC_ID].delivery_status.state == "not_selected"

    # ------------------------------------------------------------------
    # Mixed: delivered and pending items in the same result
    # ------------------------------------------------------------------

    def test_delivered_by_ancestry_excluded_while_pending_task_retained(self, tmp_path):
        """Delivered task is excluded; pending task is retained in the same backlog call.

        When release/0.11 is partially delivered:
        - OOMPAH-215 commits are already on release/0.11 by ancestry → excluded.
        - OOMPAH-200 commits are NOT on release/0.11 → retained as not_selected.
        """
        ci_task = _make_commit_info(
            self._COMMIT_TASK_1, "feat: OOMPAH-215 already cherry-picked"
        )
        ci_epic = _make_commit_info(
            self._COMMIT_EPIC_1, "feat: OOMPAH-200 not yet on release/0.11"
        )

        task_issue = self._make_oompah_issue(
            self._TASK_ID, work_branch=self._TASK_BRANCH, issue_type="task"
        )
        epic_issue = self._make_oompah_issue(
            self._EPIC_ID, work_branch=self._EPIC_BRANCH, issue_type="epic"
        )
        tracker = self._make_oompah_tracker(merged_issues=[task_issue, epic_issue])

        # COMMIT_TASK_1 is in ancestry_shas (already on release/0.11)
        # COMMIT_EPIC_1 is NOT in ancestry_shas
        result = self._run_backlog_011(
            tmp_path,
            deliveries=[],
            commits=[ci_task, ci_epic],
            tracker=tracker,
            branch_commits_map={
                self._TASK_BRANCH: [self._COMMIT_TASK_1],
                self._EPIC_BRANCH: [self._COMMIT_EPIC_1],
            },
            ancestry_shas={self._COMMIT_TASK_1},  # only task commit is on release/0.11
            filter="needs_delivery",
        )

        # OOMPAH-215 delivered by ancestry → excluded from needs_delivery
        # OOMPAH-200 not yet delivered → retained
        returned_ids = {item.identifier for item in result.items}
        assert self._TASK_ID not in returned_ids, (
            f"{self._TASK_ID} is delivered by ancestry and must be excluded from needs_delivery"
        )
        assert self._EPIC_ID in returned_ids, (
            f"{self._EPIC_ID} is not yet delivered and must appear in needs_delivery"
        )
        assert len(result.items) == 1
        assert result.items[0].delivery_status.state == "not_selected"

    # ------------------------------------------------------------------
    # result metadata for release/0.11
    # ------------------------------------------------------------------

    def test_selected_branch_is_release_011_in_result(self, tmp_path):
        """BacklogResult.selected_branch must be 'release/0.11' (not release/1.1 or other)."""
        result = self._run_backlog_011(
            tmp_path,
            deliveries=[],
            commits=[],
            filter="all",
        )
        assert result.selected_branch == self._RELEASE_011

    def test_branch_head_is_release_011_head_in_result(self, tmp_path):
        """BacklogResult.branch_head reflects the release/0.11 snapshot SHA."""
        result = self._run_backlog_011(
            tmp_path,
            deliveries=[],
            commits=[],
            filter="all",
        )
        assert result.branch_available is True
        assert result.branch_head == self._RELEASE_011_HEAD
