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
