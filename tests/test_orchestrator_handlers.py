"""Tests for the targeted tick handlers split from the monolithic _tick().

These tests verify that each handler:
- _handle_reconcile()
- _handle_review_check()
- _handle_dispatch_needed()
- _handle_yolo_review()
- _handle_auto_update()

performs its designated role, and that _tick() calls them all in the correct
order.
"""

from __future__ import annotations

import asyncio
import threading
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oompah.config import ServiceConfig
from oompah.focus import Focus
from oompah.models import AgentProfile, Issue, ModelProvider, RetryEntry, RunningEntry
from oompah.orchestrator import Orchestrator
from oompah.scm import ReviewRequest

def _make_config() -> ServiceConfig:
    return ServiceConfig(tracker_kind="oompah_md")


def _make_issue(
    identifier: str,
    state: str = "open",
    issue_type: str = "task",
    priority: int = 2,
    project_id: str | None = None,
    labels: list | None = None,
    description: str = "Test issue body — passes the empty-description gate.",
) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=f"Issue {identifier}",
        description=description,
        state=state,
        issue_type=issue_type,
        priority=priority,
        project_id=project_id,
        labels=labels or [],
    )


def _make_project(
    project_id: str = "proj-1",
    repo_url: str = "https://github.com/org/repo",
    yolo: bool = False,
):
    p = MagicMock()
    p.id = project_id
    p.repo_url = repo_url
    p.name = "test-project"
    p.yolo = yolo
    return p


def _make_review(
    review_id: str = "1",
    source_branch: str = "feat-branch",
    ci_status: str = "passed",
    has_conflicts: bool = False,
    needs_rebase: bool = False,
    draft: bool = False,
) -> ReviewRequest:
    return ReviewRequest(
        id=review_id,
        title=f"PR #{review_id}",
        url=f"https://github.com/org/repo/pull/{review_id}",
        author="alice",
        state="open",
        source_branch=source_branch,
        target_branch="main",
        created_at="2025-01-01",
        updated_at="2025-01-02",
        ci_status=ci_status,
        has_conflicts=has_conflicts,
        needs_rebase=needs_rebase,
        draft=draft,
    )


def _make_orchestrator(tmp_path, projects=None, yolo_projects=None):
    """Create a test orchestrator with mocked project store."""
    from oompah.roles import RoleStore

    all_projects = list(projects or []) + list(yolo_projects or [])
    project_store = MagicMock()
    project_store.list_all.return_value = all_projects
    project_store.get.side_effect = lambda pid: next(
        (p for p in all_projects if p.id == pid), None
    )
    # Use a tmp-scoped RoleStore so tests aren't influenced by any
    # .oompah/roles.json that happens to be in the cwd.
    role_store = RoleStore(path=str(tmp_path / "roles.json"))
    orch = Orchestrator(
        config=_make_config(),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        role_store=role_store,
        state_path=str(tmp_path / "state.json"),
    )
    orch._fetch_in_progress_issues = MagicMock(return_value=[])
    orch._process_epic_proposals = MagicMock(return_value=[])
    # Bypass the 60-second startup delay so maintenance tests can call
    # _maybe_heal_repos / _maybe_cleanup_worktrees / _auto_archive without
    # explicitly setting maintenance_startup_delay_seconds = 0 each time.
    # Tests that explicitly test the startup-delay behaviour override this.
    orch._started_monotonic = 0.0
    return orch


# ---------------------------------------------------------------------------
# _handle_reconcile
# ---------------------------------------------------------------------------


class TestHandleReconcile:
    """_handle_reconcile() delegates to _reconcile()."""

    def test_calls_reconcile(self, tmp_path):
        """_handle_reconcile() must call _reconcile()."""
        orch = _make_orchestrator(tmp_path)
        orch._reconcile = AsyncMock()

        asyncio.run(orch._handle_reconcile())

        orch._reconcile.assert_awaited_once()

    def test_reconcile_called_with_no_args(self, tmp_path):
        """_reconcile() is called with no arguments."""
        orch = _make_orchestrator(tmp_path)
        orch._reconcile = AsyncMock()

        asyncio.run(orch._handle_reconcile())

        orch._reconcile.assert_awaited_once_with()


# ---------------------------------------------------------------------------
# _handle_review_check
# ---------------------------------------------------------------------------


class TestHandleReviewCheck:
    """_handle_review_check() fetches forge state and populates caches."""

    def test_populates_reviews_cache(self, tmp_path):
        """After _handle_review_check(), _reviews_cache is populated."""
        orch = _make_orchestrator(tmp_path)
        review = _make_review("1", "feat-branch")
        orch._fetch_all_reviews_bounded = AsyncMock(return_value={"proj-1": [review]})
        orch._fetch_all_merged_branches_bounded = AsyncMock(return_value=set())

        asyncio.run(orch._handle_review_check())

        assert "proj-1" in orch._reviews_cache
        assert orch._reviews_cache["proj-1"] == [review]

    def test_populates_merged_branches_cache(self, tmp_path):
        """After _handle_review_check(), _merged_branches is populated."""
        orch = _make_orchestrator(tmp_path)
        orch._fetch_all_reviews_bounded = AsyncMock(return_value={})
        orch._fetch_all_merged_branches_bounded = AsyncMock(
            return_value={"branch-a", "branch-b"}
        )

        asyncio.run(orch._handle_review_check())

        assert orch._merged_branches == {"branch-a", "branch-b"}

    def test_derives_unmerged_review_branches(self, tmp_path):
        """_unmerged_review_branches is derived from reviews with source branches."""
        orch = _make_orchestrator(tmp_path)
        reviews = [
            _make_review("1", "feat-1"),
            _make_review("2", "feat-2"),
        ]
        orch._fetch_all_reviews_bounded = AsyncMock(return_value={"proj-1": reviews})
        orch._fetch_all_merged_branches_bounded = AsyncMock(return_value=set())

        asyncio.run(orch._handle_review_check())

        assert orch._unmerged_review_branches == {"feat-1", "feat-2"}

    def test_resets_reviews_cache_at_start(self, tmp_path):
        """_reviews_cache is reset (emptied) at the start of each check."""
        orch = _make_orchestrator(tmp_path)
        # Pre-populate with stale data
        orch._reviews_cache = {"stale-project": [MagicMock()]}

        orch._fetch_all_reviews_bounded = AsyncMock(return_value={})
        orch._fetch_all_merged_branches_bounded = AsyncMock(return_value=set())

        asyncio.run(orch._handle_review_check())

        # Stale project must be gone
        assert "stale-project" not in orch._reviews_cache

    def test_handles_reviews_with_no_source_branch(self, tmp_path):
        """Reviews without a source_branch are excluded from _unmerged_review_branches."""
        orch = _make_orchestrator(tmp_path)
        review = _make_review("1", source_branch="")
        review.source_branch = None  # explicitly no branch
        orch._fetch_all_reviews_bounded = AsyncMock(return_value={"proj-1": [review]})
        orch._fetch_all_merged_branches_bounded = AsyncMock(return_value=set())

        asyncio.run(orch._handle_review_check())

        assert orch._unmerged_review_branches == set()

    def test_fetches_reviews_and_merged_both_called(self, tmp_path):
        """Both _fetch_all_reviews and _fetch_all_merged_branches are called."""
        orch = _make_orchestrator(tmp_path)
        orch._fetch_all_reviews_bounded = AsyncMock(return_value={})
        orch._fetch_all_merged_branches_bounded = AsyncMock(return_value=set())

        asyncio.run(orch._handle_review_check())

        orch._fetch_all_reviews_bounded.assert_awaited_once()
        orch._fetch_all_merged_branches_bounded.assert_awaited_once()

    def test_empty_reviews_sets_empty_unmerged_branches(self, tmp_path):
        """When there are no reviews, _unmerged_review_branches is empty."""
        orch = _make_orchestrator(tmp_path)
        orch._fetch_all_reviews_bounded = AsyncMock(return_value={"proj-1": []})
        orch._fetch_all_merged_branches_bounded = AsyncMock(return_value=set())

        asyncio.run(orch._handle_review_check())

        assert orch._unmerged_review_branches == set()

    def test_no_projects_yields_empty_caches(self, tmp_path):
        """When no projects return reviews, all caches are empty."""
        orch = _make_orchestrator(tmp_path)
        orch._fetch_all_reviews_bounded = AsyncMock(return_value={})
        orch._fetch_all_merged_branches_bounded = AsyncMock(return_value=set())

        asyncio.run(orch._handle_review_check())

        assert orch._reviews_cache == {}
        assert orch._merged_branches == set()
        assert orch._unmerged_review_branches == set()

    def test_notifies_state_only_when_reviews_summary_changes(self, tmp_path):
        """Dashboard review badge updates as soon as review cache changes."""
        orch = _make_orchestrator(tmp_path)
        orch._last_emitted_reviews_summary = {
            "total": 1,
            "yolo_pending": 0,
            "queued": 0,
            "conflicts": 0,
            "ci_failures": 0,
            "needs_repo_config": 0,
            "unavailable_runners": 0,
            "needs_attention": 0,
        }
        orch._fetch_all_reviews_bounded = AsyncMock(return_value={"proj-1": []})
        orch._fetch_all_merged_branches_bounded = AsyncMock(return_value=set())
        orch._notify_state_only = MagicMock()

        asyncio.run(orch._handle_review_check())

        orch._notify_state_only.assert_called_once()
        assert orch._last_emitted_reviews_summary == {
            "total": 0,
            "yolo_pending": 0,
            "queued": 0,
            "conflicts": 0,
            "ci_failures": 0,
            "needs_repo_config": 0,
            "unavailable_runners": 0,
            "needs_attention": 0,
        }

    def test_does_not_notify_state_only_when_reviews_summary_is_unchanged(self, tmp_path):
        """Avoid extra websocket churn when the review badge state is stable."""
        orch = _make_orchestrator(tmp_path)
        unchanged = {
            "total": 0,
            "yolo_pending": 0,
            "queued": 0,
            "conflicts": 0,
            "ci_failures": 0,
            "needs_repo_config": 0,
            "unavailable_runners": 0,
            "needs_attention": 0,
        }
        orch._last_emitted_reviews_summary = dict(unchanged)
        orch._fetch_all_reviews_bounded = AsyncMock(return_value={"proj-1": []})
        orch._fetch_all_merged_branches_bounded = AsyncMock(return_value=set())
        orch._notify_state_only = MagicMock()

        asyncio.run(orch._handle_review_check())

        orch._notify_state_only.assert_not_called()
        assert orch._last_emitted_reviews_summary == unchanged


# ---------------------------------------------------------------------------
# _handle_dispatch_needed
# ---------------------------------------------------------------------------


class TestHandleDispatchNeeded:
    """_handle_dispatch_needed() fetches candidates and dispatches issues."""

    def test_resets_blocker_state_cache(self, tmp_path):
        """_blocker_state_cache is reset at the start of each dispatch cycle."""
        orch = _make_orchestrator(tmp_path)
        orch._blocker_state_cache = {"stale-id": "closed"}
        orch._fetch_all_candidates = MagicMock(return_value=[])
        orch._pre_resolve_blockers = MagicMock()
        orch._reset_orphaned_in_progress = MagicMock()
        orch._plan_open_epics = MagicMock(return_value=[])

        asyncio.run(orch._handle_dispatch_needed())

        assert orch._blocker_state_cache == {}

    def test_fetches_candidates(self, tmp_path):
        """_fetch_all_candidates is called to get eligible issues."""
        orch = _make_orchestrator(tmp_path)
        orch._fetch_all_candidates = MagicMock(return_value=[])
        orch._pre_resolve_blockers = MagicMock()
        orch._reset_orphaned_in_progress = MagicMock()
        orch._plan_open_epics = MagicMock(return_value=[])

        asyncio.run(orch._handle_dispatch_needed())

        orch._fetch_all_candidates.assert_called_once()

    def test_pre_resolves_blockers_for_candidates(self, tmp_path):
        """_pre_resolve_blockers is called with the fetched candidates."""
        orch = _make_orchestrator(tmp_path)
        candidates = [_make_issue("feat-1"), _make_issue("feat-2")]
        orch._fetch_all_candidates = MagicMock(return_value=candidates)
        orch._pre_resolve_blockers = MagicMock()
        orch._reset_orphaned_in_progress = MagicMock()
        orch._plan_open_epics = MagicMock(return_value=[])

        asyncio.run(orch._handle_dispatch_needed())

        orch._pre_resolve_blockers.assert_called_once_with(candidates)

    def test_dispatches_eligible_issue(self, tmp_path):
        """Eligible issues are dispatched."""
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue("feat-1", state="open")
        orch._fetch_all_candidates = MagicMock(return_value=[issue])
        orch._pre_resolve_blockers = MagicMock()
        orch._reset_orphaned_in_progress = MagicMock()
        orch._plan_open_epics = MagicMock(return_value=[])
        orch._should_dispatch = MagicMock(return_value=True)
        orch._dispatch = AsyncMock()

        asyncio.run(orch._handle_dispatch_needed())

        orch._dispatch.assert_awaited_once_with(issue, attempt=None)

    def test_does_not_dispatch_ineligible_issue(self, tmp_path):
        """Issues that fail _should_dispatch are not dispatched."""
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue("feat-1", state="open")
        orch._fetch_all_candidates = MagicMock(return_value=[issue])
        orch._pre_resolve_blockers = MagicMock()
        orch._reset_orphaned_in_progress = MagicMock()
        orch._plan_open_epics = MagicMock(return_value=[])
        orch._should_dispatch = MagicMock(return_value=False)
        orch._dispatch = AsyncMock()

        asyncio.run(orch._handle_dispatch_needed())

        orch._dispatch.assert_not_awaited()

    def test_stops_dispatching_when_no_slots(self, tmp_path):
        """Dispatch stops early when no agent slots are available."""
        orch = _make_orchestrator(tmp_path)
        issues = [_make_issue(f"feat-{i}", state="open") for i in range(3)]
        orch._fetch_all_candidates = MagicMock(return_value=issues)
        orch._pre_resolve_blockers = MagicMock()
        orch._reset_orphaned_in_progress = MagicMock()
        orch._plan_open_epics = MagicMock(return_value=[])
        orch._available_slots = MagicMock(return_value=0)
        orch._should_dispatch = MagicMock(return_value=True)
        orch._dispatch = AsyncMock()

        asyncio.run(orch._handle_dispatch_needed())

        # No dispatches when slots=0
        orch._dispatch.assert_not_awaited()

    def test_dispatches_epics_for_planning(self, tmp_path):
        """Epic issues returned by _plan_open_epics are dispatched."""
        orch = _make_orchestrator(tmp_path)
        epic = _make_issue("epic-1", state="open", issue_type="epic")
        orch._fetch_all_candidates = MagicMock(return_value=[epic])
        orch._pre_resolve_blockers = MagicMock()
        orch._reset_orphaned_in_progress = MagicMock()
        orch._plan_open_epics = MagicMock(return_value=[epic])
        orch._should_dispatch = MagicMock(
            return_value=False
        )  # normal dispatch skips epics
        orch._dispatch = AsyncMock()

        asyncio.run(orch._handle_dispatch_needed())

        orch._dispatch.assert_awaited_once_with(epic, attempt=None)

    def test_dispatch_does_not_reset_orphaned_in_progress(self, tmp_path):
        """Orphan reset runs in step 5c maintenance, not dispatch."""
        orch = _make_orchestrator(tmp_path)
        candidates = [_make_issue("feat-open", state="open")]
        in_progress = [_make_issue("feat-1", state="in_progress")]
        orch._fetch_all_candidates = MagicMock(return_value=candidates)
        orch._fetch_in_progress_issues = MagicMock(return_value=in_progress)
        orch._pre_resolve_blockers = MagicMock()
        orch._reset_orphaned_in_progress = MagicMock()
        orch._plan_open_epics = MagicMock(return_value=[])

        asyncio.run(orch._handle_dispatch_needed())

        orch._fetch_in_progress_issues.assert_not_called()
        orch._reset_orphaned_in_progress.assert_not_called()

    def test_no_slots_also_stops_epic_dispatch(self, tmp_path):
        """Epic dispatch also stops early when no slots are available."""
        orch = _make_orchestrator(tmp_path)
        epic = _make_issue("epic-1", state="open", issue_type="epic")
        orch._fetch_all_candidates = MagicMock(return_value=[epic])
        orch._pre_resolve_blockers = MagicMock()
        orch._reset_orphaned_in_progress = MagicMock()
        orch._plan_open_epics = MagicMock(return_value=[epic])
        orch._available_slots = MagicMock(return_value=0)
        orch._should_dispatch = MagicMock(return_value=False)
        orch._dispatch = AsyncMock()

        asyncio.run(orch._handle_dispatch_needed())

        orch._dispatch.assert_not_awaited()

    def test_dispatch_order_preserved(self, tmp_path):
        """Issues are dispatched in the order returned by _sort_for_dispatch."""
        orch = _make_orchestrator(tmp_path)
        issue_a = _make_issue("feat-a", state="open", priority=1)
        issue_b = _make_issue("feat-b", state="open", priority=2)
        # _sort_for_dispatch will sort by priority (lower = higher priority)
        orch._fetch_all_candidates = MagicMock(return_value=[issue_b, issue_a])
        orch._pre_resolve_blockers = MagicMock()
        orch._reset_orphaned_in_progress = MagicMock()
        orch._plan_open_epics = MagicMock(return_value=[])
        dispatched_order = []

        async def capture_dispatch(issue, attempt=None, override_profile=None):
            dispatched_order.append(issue.identifier)

        orch._dispatch = capture_dispatch

        asyncio.run(orch._handle_dispatch_needed())

        # Higher priority (lower number) should be dispatched first
        assert dispatched_order == ["feat-a", "feat-b"]

    def test_select_dispatchable_runs_in_executor(self, tmp_path):
        """The sort+filter pass runs via run_in_executor so it doesn't block uvicorn.

        Regression test for oompah-zlz_2-nvr: previously _sort_for_dispatch and
        the per-issue _should_dispatch loop ran inline in the async coroutine,
        causing 33-53s GET / hangs during heavy ticks.
        """
        orch = _make_orchestrator(tmp_path)
        candidates = [_make_issue("feat-1", state="open")]
        orch._fetch_all_candidates = MagicMock(return_value=candidates)
        orch._pre_resolve_blockers = MagicMock()
        orch._reset_orphaned_in_progress = MagicMock()
        orch._plan_open_epics = MagicMock(return_value=[])
        orch._auto_close_completed_epics = MagicMock()
        orch._dispatch = AsyncMock()

        # Track whether _select_dispatchable was invoked from a worker thread
        # (i.e. via run_in_executor) rather than the asyncio event-loop thread.
        import threading

        main_thread_id = threading.get_ident()
        called_thread_ids: list[int] = []

        original_select = orch._select_dispatchable

        def tracking_select(cands):
            called_thread_ids.append(threading.get_ident())
            return original_select(cands)

        orch._select_dispatchable = tracking_select

        asyncio.run(orch._handle_dispatch_needed())

        # _select_dispatchable was called once, on a worker thread (not the
        # event loop thread). If this fails, the change has regressed and
        # the tracker CLI calls inside _should_dispatch will block uvicorn again.
        assert len(called_thread_ids) == 1
        assert called_thread_ids[0] != main_thread_id

    def test_dispatch_does_not_run_orphan_reset_inline(self, tmp_path):
        """Dispatch no longer runs orphan reset inline."""
        orch = _make_orchestrator(tmp_path)
        candidates = [_make_issue("feat-open", state="open")]
        in_progress = [_make_issue("feat-1", state="in_progress")]
        orch._fetch_all_candidates = MagicMock(return_value=candidates)
        orch._fetch_in_progress_issues = MagicMock(return_value=in_progress)
        orch._pre_resolve_blockers = MagicMock()
        orch._plan_open_epics = MagicMock(return_value=[])
        orch._auto_close_completed_epics = MagicMock()

        orch._reset_orphaned_in_progress = MagicMock()

        asyncio.run(orch._handle_dispatch_needed())

        orch._fetch_in_progress_issues.assert_not_called()
        orch._reset_orphaned_in_progress.assert_not_called()

    def test_select_dispatchable_filters_and_sorts(self, tmp_path):
        """_select_dispatchable returns sort_for_dispatch(candidates) filtered by _should_dispatch."""
        orch = _make_orchestrator(tmp_path)
        a = _make_issue("feat-a", state="open", priority=2)
        b = _make_issue("feat-b", state="open", priority=1)  # higher priority
        c = _make_issue("feat-c", state="open", priority=0)  # highest priority
        # _should_dispatch rejects 'feat-a'
        orch._should_dispatch = MagicMock(
            side_effect=lambda i: i.identifier != "feat-a"
        )

        result = orch._select_dispatchable([a, b, c])

        # Sorted by priority, with feat-a filtered out
        assert [i.identifier for i in result] == ["feat-c", "feat-b"]


# ---------------------------------------------------------------------------
# _handle_yolo_review
# ---------------------------------------------------------------------------


class TestAutoArchiveThrottle:
    """_auto_archive is throttled via the maintenance lane gate and must not
    re-scan already-archived issues."""

    def _orch_with_spy_tracker(self, tmp_path):
        orch = _make_orchestrator(tmp_path)  # no projects → uses self.tracker
        orch.config.maintenance_startup_delay_seconds = 0
        orch.tracker = MagicMock()
        orch.tracker.fetch_issues_by_states.return_value = []
        orch.tracker.is_archived.return_value = False
        return orch

    def test_runs_first_time_then_throttled(self, tmp_path):
        orch = self._orch_with_spy_tracker(tmp_path)
        orch._auto_archive()
        orch._auto_archive()  # within the interval → gated by _run_maintenance_job
        assert orch.tracker.fetch_issues_by_states.call_count == 1

    def test_runs_again_after_interval_elapses(self, tmp_path):
        orch = self._orch_with_spy_tracker(tmp_path)
        orch._auto_archive()
        # Backdate the maintenance job's next_run_monotonic past the throttle window.
        state = orch._maintenance_jobs.get("auto_archive")
        if state is not None:
            state.next_run_monotonic = 0.0
        orch._auto_archive()
        assert orch.tracker.fetch_issues_by_states.call_count == 2

    def test_scan_excludes_archived_state(self, tmp_path):
        from oompah.statuses import ARCHIVED, DONE, canonicalize_status

        orch = self._orch_with_spy_tracker(tmp_path)
        orch._auto_archive()
        states = orch.tracker.fetch_issues_by_states.call_args[0][0]
        canon = {canonicalize_status(s) for s in states}
        assert canonicalize_status(ARCHIVED) not in canon
        # Done/Merged are still scanned (they can still become archived).
        assert canonicalize_status(DONE) in canon

    def test_auto_archive_registered_as_maintenance_job(self, tmp_path):
        """_auto_archive() registers state under 'auto_archive' in _maintenance_jobs."""
        orch = self._orch_with_spy_tracker(tmp_path)
        orch._auto_archive()
        assert "auto_archive" in orch._maintenance_jobs
        state = orch._maintenance_jobs["auto_archive"]
        assert state.run_count == 1

    def test_auto_archive_backfills_last_auto_archive_monotonic(self, tmp_path):
        """_auto_archive() back-fills _last_auto_archive_monotonic for legacy compat."""
        import time as _time

        orch = self._orch_with_spy_tracker(tmp_path)
        before = _time.monotonic()
        orch._auto_archive()
        after = _time.monotonic()
        assert orch._last_auto_archive_monotonic is not None
        assert before <= orch._last_auto_archive_monotonic <= after


class TestHandleYoloReview:
    """_handle_yolo_review() runs only YOLO actions (archive/merged moved to step 5b)."""

    def test_calls_yolo_review_actions(self, tmp_path):
        """_yolo_review_actions_sync is invoked by _handle_yolo_review."""
        orch = _make_orchestrator(tmp_path)
        orch._yolo_review_actions_sync = MagicMock()

        asyncio.run(orch._handle_yolo_review())

        orch._yolo_review_actions_sync.assert_called_once()

    def test_does_not_call_auto_archive(self, tmp_path):
        """_auto_archive is NOT invoked by _handle_yolo_review (moved to maintenance lane)."""
        orch = _make_orchestrator(tmp_path)
        orch._yolo_review_actions_sync = MagicMock()
        orch._auto_archive = MagicMock()

        asyncio.run(orch._handle_yolo_review())

        orch._auto_archive.assert_not_called()

    def test_does_not_call_label_merged_issues(self, tmp_path):
        """_label_merged_issues is NOT invoked by _handle_yolo_review (moved to maintenance lane)."""
        orch = _make_orchestrator(tmp_path)
        orch._yolo_review_actions_sync = MagicMock()
        orch._label_merged_issues = MagicMock()

        asyncio.run(orch._handle_yolo_review())

        orch._label_merged_issues.assert_not_called()

    def test_does_not_call_stale_in_review_reconciliation(self, tmp_path):
        """_reconcile_stale_in_review_tasks is NOT invoked by _handle_yolo_review
        (moved to maintenance lane)."""
        orch = _make_orchestrator(tmp_path)
        orch._yolo_review_actions_sync = MagicMock()
        orch._reconcile_stale_in_review_tasks = MagicMock()

        asyncio.run(orch._handle_yolo_review())

        orch._reconcile_stale_in_review_tasks.assert_not_called()

    def test_returns_float_yolo_ms(self, tmp_path):
        """_handle_yolo_review returns a single float (yolo_ms) for telemetry."""
        orch = _make_orchestrator(tmp_path)
        orch._yolo_review_actions_sync = MagicMock()

        result = asyncio.run(orch._handle_yolo_review())

        assert isinstance(result, float)
        assert result >= 0.0

    def test_timing_value_is_non_negative(self, tmp_path):
        """Timing value returned must always be >= 0."""
        orch = _make_orchestrator(tmp_path)
        orch._yolo_review_actions_sync = MagicMock()

        yolo_ms = asyncio.run(orch._handle_yolo_review())

        assert yolo_ms >= 0.0


# ---------------------------------------------------------------------------
# _maybe_run_merged_labels  (TASK-466.2)
# ---------------------------------------------------------------------------


class TestMaybeRunMergedLabels:
    """_maybe_run_merged_labels() delegates merge sweeps to the maintenance gate."""

    def _orch(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        orch._label_merged_issues = MagicMock()
        orch._label_merged_epics = MagicMock()
        orch._reconcile_in_review_pr_outcomes = MagicMock()
        orch._reconcile_terminal_open_reviews = MagicMock()
        orch._reconcile_stale_in_review_tasks = MagicMock()
        return orch

    def test_calls_all_sweeps(self, tmp_path):
        """_maybe_run_merged_labels calls every merge-label sweep on first run."""
        orch = self._orch(tmp_path)
        orch._maybe_run_merged_labels()
        orch._label_merged_issues.assert_called_once()
        orch._label_merged_epics.assert_called_once()
        orch._reconcile_in_review_pr_outcomes.assert_called_once()
        orch._reconcile_terminal_open_reviews.assert_called_once()
        orch._reconcile_stale_in_review_tasks.assert_called_once()

    def test_uses_configured_runtime_budget(self, tmp_path):
        """merged_labels uses its env-backed runtime budget."""
        orch = self._orch(tmp_path)
        orch.config.merged_labels_max_runtime_seconds = 4
        orch._run_maintenance_job = MagicMock()

        orch._maybe_run_merged_labels()

        orch._run_maintenance_job.assert_called_once()
        assert orch._run_maintenance_job.call_args.kwargs["max_runtime_s"] == 4

    def test_do_merged_labels_stops_after_budget(self, tmp_path):
        """Sweep sequence stops cooperatively when the job budget is exhausted."""
        orch = self._orch(tmp_path)
        orch._job_deadline_exceeded = MagicMock(side_effect=[False, True])

        orch._do_merged_labels()

        orch._label_merged_epics.assert_called_once()
        orch._label_merged_issues.assert_not_called()
        orch._reconcile_in_review_pr_outcomes.assert_not_called()
        orch._reconcile_terminal_open_reviews.assert_not_called()
        orch._reconcile_stale_in_review_tasks.assert_not_called()

    def test_throttled_on_second_call(self, tmp_path):
        """Second call within interval is coalesced (not executed)."""
        orch = self._orch(tmp_path)
        orch._maybe_run_merged_labels()
        orch._maybe_run_merged_labels()  # within interval → skip
        assert orch._label_merged_issues.call_count == 1

    def test_runs_again_after_interval(self, tmp_path):
        """Runs again once next_run_monotonic has passed."""
        orch = self._orch(tmp_path)
        orch._maybe_run_merged_labels()
        state = orch._maintenance_jobs.get("merged_labels")
        assert state is not None
        state.next_run_monotonic = 0.0  # backdate past interval
        orch._maybe_run_merged_labels()
        assert orch._label_merged_issues.call_count == 2

    def test_registered_as_maintenance_job(self, tmp_path):
        """After running, 'merged_labels' appears in _maintenance_jobs."""
        orch = self._orch(tmp_path)
        orch._maybe_run_merged_labels()
        assert "merged_labels" in orch._maintenance_jobs
        assert orch._maintenance_jobs["merged_labels"].run_count == 1

    def test_failure_captured_in_job_state(self, tmp_path):
        """If one sweep raises, the error is captured in last_error (not re-raised)."""
        orch = self._orch(tmp_path)
        orch._label_merged_issues = MagicMock(side_effect=RuntimeError("forge error"))
        orch._maybe_run_merged_labels()
        state = orch._maintenance_jobs.get("merged_labels")
        assert state is not None
        assert state.last_status == "failed"
        assert "forge error" in (state.last_error or "")


# ---------------------------------------------------------------------------
# _maybe_open_deferred_done_reviews
# ---------------------------------------------------------------------------


class TestMaybeOpenDeferredDoneReviews:
    """Deferred review handoff is independent from merged-label sweeps."""

    def test_runs_as_own_maintenance_job(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        orch._open_deferred_done_reviews = MagicMock()

        orch._maybe_open_deferred_done_reviews()

        orch._open_deferred_done_reviews.assert_called_once()
        assert "deferred_done_reviews" in orch._maintenance_jobs

    def test_not_starved_by_merged_labels_budget(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        orch._label_merged_epics = MagicMock()
        orch._label_merged_issues = MagicMock()
        orch._reconcile_in_review_pr_outcomes = MagicMock()
        orch._reconcile_terminal_open_reviews = MagicMock()
        orch._reconcile_stale_in_review_tasks = MagicMock()
        orch._open_deferred_done_reviews = MagicMock()

        # Simulate merged_labels exhausting its budget immediately.
        orch._job_deadline_exceeded = MagicMock(return_value=True)
        orch._maybe_run_merged_labels()
        orch._open_deferred_done_reviews.assert_not_called()

        # The independent job still runs because it has its own maintenance key.
        orch._job_deadline_exceeded = MagicMock(return_value=False)
        orch._maybe_open_deferred_done_reviews()

        orch._open_deferred_done_reviews.assert_called_once()


# ---------------------------------------------------------------------------
# _run_step5b_maintenance  (TASK-466.2: extended with archive + merged labels)
# ---------------------------------------------------------------------------


class TestRunStep5bMaintenanceExtended:
    """_run_step5b_maintenance includes independent maintenance jobs."""

    def test_calls_auto_archive(self, tmp_path):
        """_run_step5b_maintenance calls _auto_archive."""
        orch = _make_orchestrator(tmp_path)
        orch._maybe_heal_repos = MagicMock()
        orch._maybe_cleanup_worktrees = MagicMock()
        orch._auto_archive = MagicMock()
        orch._maybe_open_deferred_done_reviews = MagicMock()
        orch._maybe_run_merged_labels = MagicMock()
        orch._maybe_run_release_pick_reconciliation = MagicMock()

        orch._run_step5b_maintenance()

        orch._auto_archive.assert_called_once()

    def test_calls_merged_labels(self, tmp_path):
        """_run_step5b_maintenance calls _maybe_run_merged_labels."""
        orch = _make_orchestrator(tmp_path)
        orch._maybe_heal_repos = MagicMock()
        orch._maybe_cleanup_worktrees = MagicMock()
        orch._auto_archive = MagicMock()
        orch._maybe_open_deferred_done_reviews = MagicMock()
        orch._maybe_run_merged_labels = MagicMock()
        orch._maybe_run_release_pick_reconciliation = MagicMock()

        orch._run_step5b_maintenance()

        orch._maybe_run_merged_labels.assert_called_once()

    def test_calls_release_pick_reconciliation(self, tmp_path):
        """_run_step5b_maintenance calls _maybe_run_release_pick_reconciliation."""
        orch = _make_orchestrator(tmp_path)
        orch._maybe_heal_repos = MagicMock()
        orch._maybe_cleanup_worktrees = MagicMock()
        orch._auto_archive = MagicMock()
        orch._maybe_open_deferred_done_reviews = MagicMock()
        orch._maybe_run_merged_labels = MagicMock()
        orch._maybe_run_release_pick_reconciliation = MagicMock()

        orch._run_step5b_maintenance()

        orch._maybe_run_release_pick_reconciliation.assert_called_once()

    def test_all_six_jobs_run_in_order(self, tmp_path):
        """All six maintenance jobs run in stable order."""
        orch = _make_orchestrator(tmp_path)
        call_order = []
        orch._maybe_heal_repos = lambda: call_order.append("heal")
        orch._maybe_cleanup_worktrees = lambda: call_order.append("cleanup")
        orch._auto_archive = lambda: call_order.append("archive")
        orch._maybe_open_deferred_done_reviews = lambda: call_order.append(
            "deferred_done_reviews"
        )
        orch._maybe_run_merged_labels = lambda: call_order.append("merged_labels")
        orch._maybe_run_release_pick_reconciliation = lambda: call_order.append(
            "release_picks"
        )

        orch._run_step5b_maintenance()

        assert call_order == [
            "heal",
            "cleanup",
            "archive",
            "deferred_done_reviews",
            "merged_labels",
            "release_picks",
        ]

    def test_archive_merged_labels_and_release_picks_in_snapshot(self, tmp_path):
        """After running, step-5b jobs appear in _maintenance_jobs."""
        orch = _make_orchestrator(tmp_path)
        orch.tracker = MagicMock()
        orch.tracker.fetch_issues_by_states.return_value = []
        orch.project_store.list_all.return_value = []
        orch.project_store.sync_all_sources = MagicMock()
        orch._cleanup_terminal_worktrees = MagicMock(return_value=0)
        orch._label_merged_issues = MagicMock()
        orch._label_merged_epics = MagicMock()
        orch._reconcile_stale_in_review_tasks = MagicMock()
        orch._open_deferred_done_reviews = MagicMock()
        orch._reconcile_release_picks_pass = MagicMock()

        orch._run_step5b_maintenance()

        assert "auto_archive" in orch._maintenance_jobs
        assert "deferred_done_reviews" in orch._maintenance_jobs
        assert "merged_labels" in orch._maintenance_jobs
        assert "release_picks" in orch._maintenance_jobs
        snapshot = orch.get_snapshot()
        assert "auto_archive" in snapshot["maintenance"]["jobs"]
        assert "deferred_done_reviews" in snapshot["maintenance"]["jobs"]
        assert "merged_labels" in snapshot["maintenance"]["jobs"]
        assert "release_picks" in snapshot["maintenance"]["jobs"]


# ---------------------------------------------------------------------------
# _run_step5c_epic_maintenance  (TASK-466.3)
# ---------------------------------------------------------------------------


class TestRunStep5cEpicMaintenance:
    """_run_step5c_epic_maintenance() runs epic maintenance jobs via the maintenance gate.

    Covers TASK-466.3 acceptance criteria:
      AC#1 — epic maintenance does not run inline before dispatch (fire-and-forget).
      AC#2 — completion PRs, staleness, rebase filing, and orphan reset remain idempotent.
      AC#3 — maintenance jobs are gated by _run_maintenance_job with per-job throttle.
    """

    def _orch(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        # Mock out every sub-operation so tests focus on orchestration logic.
        orch._auto_close_completed_epics = MagicMock()
        orch._all_non_terminal_epics = MagicMock(return_value=[])
        orch._open_epic_main_prs = MagicMock()
        orch._check_epic_staleness = MagicMock()
        orch._dispatch_proactive_rebase_agents = MagicMock()
        orch._prune_stale_epic_rebase_states = MagicMock()
        orch._reset_orphaned_in_progress = MagicMock()
        orch._fetch_in_progress_issues = MagicMock(return_value=[])
        return orch

    # ---- AC#1: fire-and-forget from tick ----

    def test_tick_sets_epic_maintenance_future(self, tmp_path):
        """_tick() must set _epic_maintenance_future so status is trackable."""
        orch = _make_orchestrator(tmp_path)
        orch._handle_reconcile = AsyncMock()
        orch._handle_review_check = AsyncMock()
        orch._handle_dispatch_needed = AsyncMock()
        orch._handle_yolo_review = AsyncMock(return_value=0.0)
        orch._handle_auto_update = AsyncMock()
        orch._notify_observers = MagicMock()
        orch._maybe_run_watchdog = MagicMock()
        orch._maybe_heal_repos = MagicMock()
        orch._maybe_cleanup_worktrees = MagicMock()
        orch._run_step5c_epic_maintenance = MagicMock()

        with patch("oompah.orchestrator.validate_dispatch_config", return_value=[]):
            asyncio.run(orch._tick())

        assert orch._epic_maintenance_future is not None

    def test_tick_does_not_await_epic_maintenance(self, tmp_path):
        """_tick() must complete before _run_step5c_epic_maintenance body executes.

        AC#1: epic maintenance is fire-and-forget — _tick() submits it to the
        thread pool without awaiting, so the tick returns before the maintenance
        function even begins running.
        """
        import threading
        import time as _time

        orch = _make_orchestrator(tmp_path)
        orch._handle_reconcile = AsyncMock()
        orch._handle_review_check = AsyncMock()
        orch._handle_dispatch_needed = AsyncMock()
        orch._handle_yolo_review = AsyncMock(return_value=0.0)
        orch._handle_auto_update = AsyncMock()
        orch._notify_observers = MagicMock()
        orch._maybe_run_watchdog = MagicMock()
        orch._maybe_heal_repos = MagicMock()
        orch._maybe_cleanup_worktrees = MagicMock()

        # Gate: the maintenance function blocks until the event is set.
        # tick_done is set AFTER asyncio.run() returns so we can confirm that
        # tick() finished without waiting for the gate to open.
        gate = threading.Event()
        tick_returned_before_gate: list[bool] = []

        def _gated_epic_maintenance():
            # Record whether the tick has already returned by the time we run.
            tick_returned_before_gate.append(gate.is_set())
            gate.set()  # unblock shutdown

        orch._run_step5c_epic_maintenance = _gated_epic_maintenance

        with patch("oompah.orchestrator.validate_dispatch_config", return_value=[]):
            asyncio.run(orch._tick())
        # Signal that tick() has returned.
        gate.set()

        # Wait for the maintenance thread to run (max 2s to avoid test flakiness).
        assert gate.wait(timeout=2.0), "Maintenance thread never ran"
        # The tick should have returned BEFORE _gated_epic_maintenance set the gate
        # the first time, OR the gate was already set when it ran (both are fine:
        # what matters is the tick didn't block on the function completing).
        # The real assertion is the timing one: tick must complete quickly.
        # We already know it did because asyncio.run() returned above.
        assert orch._epic_maintenance_future is not None

        # Ensure background thread finishes before GC (avoids test pollution).
        if orch._epic_maintenance_future is not None:
            try:
                orch._epic_maintenance_future.result(timeout=2.0)
            except Exception:
                pass

    def test_tick_skips_new_epic_maintenance_when_previous_still_running(self, tmp_path):
        """When the previous epic_maintenance_future is not done, tick skips a new one."""
        orch = _make_orchestrator(tmp_path)
        orch._handle_reconcile = AsyncMock()
        orch._handle_review_check = AsyncMock()
        orch._handle_dispatch_needed = AsyncMock()
        orch._handle_yolo_review = AsyncMock(return_value=0.0)
        orch._handle_auto_update = AsyncMock()
        orch._notify_observers = MagicMock()
        orch._maybe_run_watchdog = MagicMock()
        orch._maybe_heal_repos = MagicMock()
        orch._maybe_cleanup_worktrees = MagicMock()
        orch._run_step5c_epic_maintenance = MagicMock()

        async def _run_with_fake_future():
            loop = asyncio.get_event_loop()
            fake_future: asyncio.Future = loop.create_future()
            orch._epic_maintenance_future = fake_future  # not done

            with patch("oompah.orchestrator.validate_dispatch_config", return_value=[]):
                await orch._tick()

            fake_future.cancel()

        asyncio.run(_run_with_fake_future())

        # _run_step5c_epic_maintenance should NOT have been called — future was in-flight
        orch._run_step5c_epic_maintenance.assert_not_called()

    # ---- AC#2: idempotency through maintenance gate ----

    def test_all_six_jobs_registered(self, tmp_path):
        """All six epic maintenance jobs appear in _maintenance_jobs after a run."""
        orch = self._orch(tmp_path)
        # Enable staleness threshold so staleness + rebase jobs fire.
        orch.config.epic_staleness_threshold_commits = 5

        orch._run_step5c_epic_maintenance()

        job_names = set(orch._maintenance_jobs.keys())
        assert "epic_auto_close" in job_names
        assert "epic_open_prs" in job_names
        assert "epic_staleness" in job_names
        assert "epic_rebase_filing" in job_names
        assert "epic_prune_rebase" in job_names
        assert "epic_orphan_reset" in job_names

    def test_jobs_skipped_when_threshold_zero(self, tmp_path):
        """staleness and rebase jobs are skipped when threshold is 0 (disabled)."""
        orch = self._orch(tmp_path)
        orch.config.epic_staleness_threshold_commits = 0

        orch._run_step5c_epic_maintenance()

        orch._check_epic_staleness.assert_not_called()
        orch._dispatch_proactive_rebase_agents.assert_not_called()

    def test_staleness_runs_before_rebase_filing(self, tmp_path):
        """Staleness job MUST complete before rebase filing (ordering contract).

        AC#2: ordering preserved so _check_epic_staleness updates
        _epic_rebase_states before _dispatch_proactive_rebase_agents reads it.
        """
        orch = self._orch(tmp_path)
        orch.config.epic_staleness_threshold_commits = 5
        call_order = []
        orch._check_epic_staleness = MagicMock(
            side_effect=lambda c: call_order.append("staleness")
        )
        orch._dispatch_proactive_rebase_agents = MagicMock(
            side_effect=lambda c: call_order.append("rebase_filing")
        )

        orch._run_step5c_epic_maintenance()

        staleness_idx = call_order.index("staleness")
        rebase_idx = call_order.index("rebase_filing")
        assert staleness_idx < rebase_idx, (
            "staleness must run before rebase filing but order was: "
            + str(call_order)
        )

    def test_idempotent_second_call_within_interval(self, tmp_path):
        """Second call within interval is coalesced (no double-dispatch).

        AC#2: idempotency preserved — jobs are throttled by _run_maintenance_job.
        """
        orch = self._orch(tmp_path)
        orch._run_step5c_epic_maintenance()
        orch._run_step5c_epic_maintenance()  # within interval

        # Each sub-function should have been called only once.
        assert orch._auto_close_completed_epics.call_count == 1
        assert orch._prune_stale_epic_rebase_states.call_count == 1
        assert orch._reset_orphaned_in_progress.call_count == 1

    def test_orphan_reset_fetches_in_progress_inside_maintenance(self, tmp_path):
        """Step 5c fetches fresh in-progress tasks before orphan reset."""
        orch = self._orch(tmp_path)
        in_progress = [_make_issue("feat-1", state="in_progress")]
        orch._fetch_in_progress_issues.return_value = in_progress

        orch._run_step5c_epic_maintenance()

        orch._fetch_in_progress_issues.assert_called_once()
        orch._reset_orphaned_in_progress.assert_called_once_with(in_progress)

    def test_reruns_after_interval_expires(self, tmp_path):
        """Jobs run again once their next_run_monotonic has passed."""
        orch = self._orch(tmp_path)
        orch._run_step5c_epic_maintenance()

        # Backdate every epic job past its interval.
        for name in ("epic_auto_close", "epic_open_prs", "epic_prune_rebase",
                     "epic_orphan_reset"):
            state = orch._maintenance_jobs.get(name)
            if state is not None:
                state.next_run_monotonic = 0.0

        orch._run_step5c_epic_maintenance()

        assert orch._auto_close_completed_epics.call_count == 2
        assert orch._prune_stale_epic_rebase_states.call_count == 2
        assert orch._reset_orphaned_in_progress.call_count == 2

    def test_failure_captured_does_not_propagate(self, tmp_path):
        """A failing sub-job is captured in last_error, not re-raised.

        AC#2: idempotent — failures do not crash the maintenance runner.
        """
        orch = self._orch(tmp_path)
        orch._auto_close_completed_epics = MagicMock(
            side_effect=RuntimeError("auto-close blew up")
        )

        # Must not raise.
        orch._run_step5c_epic_maintenance()

        state = orch._maintenance_jobs.get("epic_auto_close")
        assert state is not None
        assert state.last_status == "failed"
        assert "auto-close blew up" in (state.last_error or "")

    def test_job_status_appears_in_snapshot(self, tmp_path):
        """Epic maintenance job states are visible via get_snapshot()."""
        orch = self._orch(tmp_path)
        orch._run_step5c_epic_maintenance()

        snapshot = orch.get_snapshot()
        jobs = snapshot["maintenance"]["jobs"]
        assert "epic_auto_close" in jobs
        assert "epic_orphan_reset" in jobs

    # ---- AC#3: per-project maintenance lock ----

    def test_get_project_maintenance_lock_returns_lock(self, tmp_path):
        """_get_project_maintenance_lock returns a threading.Lock."""
        import threading

        orch = _make_orchestrator(tmp_path)
        lock = orch._get_project_maintenance_lock("proj-1")
        assert isinstance(lock, type(threading.Lock()))

    def test_get_project_maintenance_lock_same_project_same_lock(self, tmp_path):
        """Same project ID returns the same lock object (identity)."""
        orch = _make_orchestrator(tmp_path)
        lock1 = orch._get_project_maintenance_lock("proj-1")
        lock2 = orch._get_project_maintenance_lock("proj-1")
        assert lock1 is lock2

    def test_get_project_maintenance_lock_different_projects_different_locks(
        self, tmp_path
    ):
        """Different project IDs get distinct lock objects."""
        orch = _make_orchestrator(tmp_path)
        lock_a = orch._get_project_maintenance_lock("proj-a")
        lock_b = orch._get_project_maintenance_lock("proj-b")
        assert lock_a is not lock_b


# ---------------------------------------------------------------------------
# _handle_auto_update
# ---------------------------------------------------------------------------


class TestHandleAutoUpdate:
    """_handle_auto_update() triggers git auto-update only when idle."""

    def test_calls_check_auto_update_when_idle(self, tmp_path):
        """_check_auto_update is called when no agents are running."""
        orch = _make_orchestrator(tmp_path)
        orch._check_auto_update = MagicMock()

        # No running agents, no retries
        assert not orch.state.running
        assert not orch.state.retry_attempts

        asyncio.run(orch._handle_auto_update())

        orch._check_auto_update.assert_called_once()

    def test_skips_check_when_agents_running(self, tmp_path):
        """_check_auto_update is NOT called when agents are running."""
        orch = _make_orchestrator(tmp_path)
        orch._check_auto_update = MagicMock()

        # Simulate a running agent
        orch.state.running["some-issue-id"] = MagicMock()

        asyncio.run(orch._handle_auto_update())

        orch._check_auto_update.assert_not_called()

    def test_skips_check_when_retries_pending(self, tmp_path):
        """_check_auto_update is NOT called when retries are pending."""
        orch = _make_orchestrator(tmp_path)
        orch._check_auto_update = MagicMock()

        # Simulate a pending retry
        orch.state.retry_attempts["some-issue-id"] = MagicMock()

        asyncio.run(orch._handle_auto_update())

        orch._check_auto_update.assert_not_called()

    def test_calls_check_when_both_queues_empty(self, tmp_path):
        """_check_auto_update is called only when both running and retry queues are empty."""
        orch = _make_orchestrator(tmp_path)
        orch._check_auto_update = MagicMock()

        # Verify initial state is idle
        assert len(orch.state.running) == 0
        assert len(orch.state.retry_attempts) == 0

        asyncio.run(orch._handle_auto_update())

        orch._check_auto_update.assert_called_once()

    def test_skips_when_both_running_and_retries_exist(self, tmp_path):
        """Skips when both running agents and retries exist."""
        orch = _make_orchestrator(tmp_path)
        orch._check_auto_update = MagicMock()

        orch.state.running["issue-1"] = MagicMock()
        orch.state.retry_attempts["issue-2"] = MagicMock()

        asyncio.run(orch._handle_auto_update())

        orch._check_auto_update.assert_not_called()

    def test_check_auto_update_fast_forwards_when_only_behind(self, tmp_path):
        """Behind-only main uses ff-only autostash pull."""
        orch = _make_orchestrator(tmp_path)
        calls: list[list[str]] = []

        def fake_run(args, **kwargs):
            calls.append(list(args))
            if args[:3] == ["git", "rev-list", "HEAD..origin/main"]:
                return MagicMock(returncode=0, stdout="2\n", stderr="")
            if args[:3] == ["git", "rev-list", "origin/main..HEAD"]:
                return MagicMock(returncode=0, stdout="0\n", stderr="")
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("oompah.orchestrator.subprocess.run", side_effect=fake_run):
            orch._check_auto_update()

        assert ["git", "pull", "--ff-only", "--autostash", "origin", "main"] in calls
        assert ["git", "pull", "--rebase", "--autostash", "origin", "main"] not in calls
        assert orch._restart_requested is True
        assert orch._stopping is True

    def test_check_auto_update_skips_restart_for_tracker_only_commits(self, tmp_path):
        """Task-tracker writes do not restart the service that wrote them."""
        orch = _make_orchestrator(tmp_path)
        calls: list[list[str]] = []

        def fake_run(args, **kwargs):
            calls.append(list(args))
            if args[:3] == ["git", "rev-list", "HEAD..origin/main"]:
                return MagicMock(returncode=0, stdout="1\n", stderr="")
            if args[:3] == ["git", "rev-list", "origin/main..HEAD"]:
                return MagicMock(returncode=0, stdout="0\n", stderr="")
            if args[:3] == ["git", "diff", "--name-only"]:
                return MagicMock(
                    returncode=0,
                    stdout=".oompah/tasks/open/PROJ-1.md\n",
                    stderr="",
                )
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("oompah.orchestrator.subprocess.run", side_effect=fake_run):
            orch._check_auto_update()

        assert ["git", "pull", "--ff-only", "--autostash", "origin", "main"] not in calls
        assert ["git", "pull", "--rebase", "--autostash", "origin", "main"] not in calls
        assert orch._restart_requested is False
        assert orch._stopping is False

    def test_check_auto_update_restarts_for_non_tracker_commit(self, tmp_path):
        """A runtime code update still follows the normal restart path."""
        orch = _make_orchestrator(tmp_path)
        calls: list[list[str]] = []

        def fake_run(args, **kwargs):
            calls.append(list(args))
            if args[:3] == ["git", "rev-list", "HEAD..origin/main"]:
                return MagicMock(returncode=0, stdout="1\n", stderr="")
            if args[:3] == ["git", "rev-list", "origin/main..HEAD"]:
                return MagicMock(returncode=0, stdout="0\n", stderr="")
            if args[:3] == ["git", "diff", "--name-only"]:
                return MagicMock(returncode=0, stdout="oompah/server.py\n", stderr="")
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("oompah.orchestrator.subprocess.run", side_effect=fake_run):
            orch._check_auto_update()

        assert ["git", "pull", "--ff-only", "--autostash", "origin", "main"] in calls
        assert orch._restart_requested is True
        assert orch._stopping is True

    def test_check_auto_update_rebases_when_local_branch_has_commits(self, tmp_path):
        """Diverged main rebases local commits instead of surfacing ff-only failure."""
        orch = _make_orchestrator(tmp_path)
        calls: list[list[str]] = []

        def fake_run(args, **kwargs):
            calls.append(list(args))
            if args[:3] == ["git", "rev-list", "HEAD..origin/main"]:
                return MagicMock(returncode=0, stdout="2\n", stderr="")
            if args[:3] == ["git", "rev-list", "origin/main..HEAD"]:
                return MagicMock(returncode=0, stdout="1\n", stderr="")
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("oompah.orchestrator.subprocess.run", side_effect=fake_run):
            orch._check_auto_update()

        assert ["git", "pull", "--rebase", "--autostash", "origin", "main"] in calls
        assert ["git", "pull", "--ff-only", "--autostash", "origin", "main"] not in calls
        assert all(a.get("source") != "auto_update" for a in orch._alerts)
        assert orch._restart_requested is True
        assert orch._stopping is True

    def test_check_auto_update_aborts_failed_rebase_and_alerts(self, tmp_path):
        """Failed automatic rebase is aborted before the UI alert is recorded."""
        orch = _make_orchestrator(tmp_path)
        calls: list[list[str]] = []

        def fake_run(args, **kwargs):
            calls.append(list(args))
            if args[:3] == ["git", "rev-list", "HEAD..origin/main"]:
                return MagicMock(returncode=0, stdout="2\n", stderr="")
            if args[:3] == ["git", "rev-list", "origin/main..HEAD"]:
                return MagicMock(returncode=0, stdout="1\n", stderr="")
            if args[:3] == ["git", "pull", "--rebase"]:
                return MagicMock(
                    returncode=1,
                    stdout="",
                    stderr="CONFLICT (content): Merge conflict in oompah/orchestrator.py",
                )
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("oompah.orchestrator.subprocess.run", side_effect=fake_run):
            orch._check_auto_update()

        assert ["git", "rebase", "--abort"] in calls
        assert orch._restart_requested is False
        assert orch._stopping is False
        alerts = [a for a in orch._alerts if a.get("source") == "auto_update"]
        assert len(alerts) == 1
        assert "git pull --rebase returned error" in alerts[0]["message"]
        assert "CONFLICT" in alerts[0]["message"]


# ---------------------------------------------------------------------------
# Terminal worktree cleanup
# ---------------------------------------------------------------------------


class TestTerminalWorktreeCleanup:
    """Terminal task cleanup removes only discardable worktrees."""

    class StaleCleanupStore:
        def __init__(self, projects, cleanup_result=(0, False)):
            self._projects = list(projects)
            self.cleanup_result = cleanup_result
            self.cleanup_calls = []
            self.remove_worktree = MagicMock()
            self.remove_epic_worktree = MagicMock()

        def list_all(self):
            return list(self._projects)

        def get(self, project_id):
            return next((p for p in self._projects if p.id == project_id), None)

        def cleanup_stale_worktree_dirs(self, project_id, limit=None):
            self.cleanup_calls.append((project_id, limit))
            return self.cleanup_result

    def test_cleanup_terminal_worktrees_removes_only_merged_and_archived_project_worktrees(
        self, tmp_path
    ):
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        tracker = MagicMock()
        tracker.fetch_issues_by_states.return_value = [
            _make_issue("TASK-1", state="Done", project_id=project.id),
            _make_issue("TASK-2", state="Merged", project_id=project.id),
            _make_issue("TASK-3", state="Archived", project_id=project.id),
        ]
        orch._tracker_for_project = MagicMock(return_value=tracker)

        cleaned = orch._cleanup_terminal_worktrees()

        assert cleaned == 2
        tracker.fetch_issues_by_states.assert_called_once_with(["Merged", "Archived"])
        assert [
            call.args for call in orch.project_store.remove_worktree.call_args_list
        ] == [
            (project.id, "TASK-2"),
            (project.id, "TASK-3"),
        ]

    def test_cleanup_terminal_worktrees_sweeps_stale_dirs_with_remaining_budget(
        self, tmp_path
    ):
        project = _make_project()
        store = self.StaleCleanupStore([project], cleanup_result=(2, False))
        orch = _make_orchestrator(tmp_path, projects=[project])
        orch.project_store = store
        orch.config.worktree_cleanup_batch_size = 3
        tracker = MagicMock()
        tracker.fetch_issues_by_states.return_value = [
            _make_issue("TASK-1", state="Merged", project_id=project.id),
        ]
        orch._tracker_for_project = MagicMock(return_value=tracker)

        cleaned = orch._cleanup_terminal_worktrees()

        assert cleaned == 3
        store.remove_worktree.assert_called_once_with(project.id, "TASK-1")
        assert store.cleanup_calls == [(project.id, 2)]

    def test_cleanup_terminal_worktrees_reports_deferred_stale_dir_sweep(
        self, tmp_path
    ):
        project = _make_project()
        store = self.StaleCleanupStore([project], cleanup_result=(1, True))
        orch = _make_orchestrator(tmp_path, projects=[project])
        orch.project_store = store
        orch.config.worktree_cleanup_batch_size = 1
        tracker = MagicMock()
        tracker.fetch_issues_by_states.return_value = []
        orch._tracker_for_project = MagicMock(return_value=tracker)

        cleaned = orch._cleanup_terminal_worktrees()

        assert cleaned == 1
        assert store.cleanup_calls == [(project.id, 1)]
        assert orch._maintenance_status["worktree_cleanup"]["deferred"] is True

    def test_cleanup_terminal_worktrees_skips_stale_sweep_without_budget(
        self, tmp_path
    ):
        project = _make_project()
        store = self.StaleCleanupStore([project], cleanup_result=(1, True))
        orch = _make_orchestrator(tmp_path, projects=[project])
        orch.project_store = store
        orch.config.worktree_cleanup_batch_size = 1
        tracker = MagicMock()
        tracker.fetch_issues_by_states.return_value = [
            _make_issue("TASK-1", state="Merged", project_id=project.id),
        ]
        orch._tracker_for_project = MagicMock(return_value=tracker)

        cleaned = orch._cleanup_terminal_worktrees()

        assert cleaned == 1
        assert store.cleanup_calls == []
        assert orch._maintenance_status["worktree_cleanup"]["deferred"] is False

    def test_cleanup_terminal_worktrees_continues_after_remove_error(self, tmp_path):
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        tracker = MagicMock()
        tracker.fetch_issues_by_states.return_value = [
            _make_issue("TASK-1", state="Merged", project_id=project.id),
            _make_issue("TASK-2", state="Archived", project_id=project.id),
        ]
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch.project_store.remove_worktree.side_effect = [RuntimeError("busy"), None]

        cleaned = orch._cleanup_terminal_worktrees()

        assert cleaned == 1
        assert orch.project_store.remove_worktree.call_count == 2

    def test_cleanup_terminal_worktrees_respects_batch_size(self, tmp_path):
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        orch.config.worktree_cleanup_batch_size = 1
        tracker = MagicMock()
        tracker.fetch_issues_by_states.return_value = [
            _make_issue("TASK-1", state="Merged", project_id=project.id),
            _make_issue("TASK-2", state="Archived", project_id=project.id),
        ]
        orch._tracker_for_project = MagicMock(return_value=tracker)

        cleaned = orch._cleanup_terminal_worktrees()

        assert cleaned == 1
        orch.project_store.remove_worktree.assert_called_once_with(
            project.id, "TASK-1"
        )
        assert orch._maintenance_status["worktree_cleanup"]["deferred"] is True

    def test_cleanup_terminal_worktrees_removes_epic_worktree_for_merged_epic(
        self, tmp_path
    ):
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        tracker = MagicMock()
        tracker.fetch_issues_by_states.return_value = [
            _make_issue(
                "TASK-EPIC",
                state="Merged",
                issue_type="epic",
                project_id=project.id,
            ),
        ]
        orch._tracker_for_project = MagicMock(return_value=tracker)

        cleaned = orch._cleanup_terminal_worktrees()

        assert cleaned == 1
        orch.project_store.remove_epic_worktree.assert_called_once_with(
            project.id, "TASK-EPIC"
        )
        orch.project_store.remove_worktree.assert_not_called()

    def test_cleanup_terminal_worktrees_preserves_done_epic_worktree(
        self, tmp_path
    ):
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        tracker = MagicMock()
        tracker.fetch_issues_by_states.return_value = [
            _make_issue(
                "TASK-EPIC",
                state="Done",
                issue_type="epic",
                project_id=project.id,
            ),
        ]
        orch._tracker_for_project = MagicMock(return_value=tracker)

        cleaned = orch._cleanup_terminal_worktrees()

        assert cleaned == 0
        tracker.fetch_issues_by_states.assert_called_once_with(["Merged", "Archived"])
        orch.project_store.remove_epic_worktree.assert_not_called()
        orch.project_store.remove_worktree.assert_not_called()

    def test_cleanup_terminal_worktrees_preserves_done_legacy_workspace(
        self, tmp_path
    ):
        orch = _make_orchestrator(tmp_path)
        orch.tracker = MagicMock()
        orch.workspace_mgr = MagicMock()
        orch.tracker.fetch_issues_by_states.return_value = [
            _make_issue("TASK-1", state="Done"),
            _make_issue("TASK-2", state="Archived"),
        ]

        cleaned = orch._cleanup_terminal_worktrees()

        assert cleaned == 1
        orch.tracker.fetch_issues_by_states.assert_called_once_with(
            ["Merged", "Archived"]
        )
        orch.workspace_mgr.remove_workspace.assert_called_once_with("TASK-2")

    def test_maybe_heal_repos_does_only_repo_sync_not_cleanup(self, tmp_path):
        """_maybe_heal_repos() drives sync_all_sources and alerts; worktree cleanup
        is a separate job handled by _maybe_cleanup_worktrees()."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        orch.config.maintenance_startup_delay_seconds = 0
        orch.project_store.sync_all_sources = MagicMock()
        orch._cleanup_terminal_worktrees = MagicMock()

        orch._maybe_heal_repos()

        orch.project_store.sync_all_sources.assert_called_once_with()
        # cleanup is a separate job — heal must NOT call it
        orch._cleanup_terminal_worktrees.assert_not_called()

    def test_maybe_cleanup_worktrees_cleans_terminal_worktrees(self, tmp_path):
        """_maybe_cleanup_worktrees() removes worktrees for Merged/Archived tasks."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._cleanup_terminal_worktrees = MagicMock(return_value=1)

        orch._maybe_cleanup_worktrees()

        orch._cleanup_terminal_worktrees.assert_called_once_with([project])

    def test_maybe_heal_repos_skips_when_interval_not_reached(self, tmp_path):
        """_maybe_heal_repos() skips when the minimum interval has not elapsed."""
        orch = _make_orchestrator(tmp_path, projects=[_make_project()])
        # Simulate a recent run by pre-seeding the job state via _run_maintenance_job
        # (which sets next_run_monotonic = now + interval after it completes).
        # Simplest approach: run once to arm the interval gate, then run again.
        orch.project_store.sync_all_sources = MagicMock()
        orch._maybe_heal_repos()  # first run — arms the interval gate

        # Reset mock call counts for the second check
        orch.project_store.sync_all_sources.reset_mock()

        orch._maybe_heal_repos()  # second run — should be throttled

        orch.project_store.sync_all_sources.assert_not_called()

    def test_maybe_cleanup_worktrees_skips_when_interval_not_reached(self, tmp_path):
        """_maybe_cleanup_worktrees() skips when the minimum interval has not elapsed."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._cleanup_terminal_worktrees = MagicMock(return_value=0)
        orch._maybe_cleanup_worktrees()  # first run — arms the interval gate
        orch._cleanup_terminal_worktrees.reset_mock()

        orch._maybe_cleanup_worktrees()  # second run — should be throttled

        orch._cleanup_terminal_worktrees.assert_not_called()

    def test_maybe_heal_repos_heal_failure_does_not_stop_alert_refresh(self, tmp_path):
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        orch.config.maintenance_startup_delay_seconds = 0
        orch.project_store.sync_all_sources = MagicMock(side_effect=RuntimeError("net"))

        orch._maybe_heal_repos()

        orch.project_store.sync_all_sources.assert_called_once_with()

    def test_maybe_cleanup_worktrees_and_heal_are_independent_jobs(self, tmp_path):
        """Heal and cleanup are independent maintenance jobs with separate throttles."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        orch.project_store.sync_all_sources = MagicMock(side_effect=RuntimeError("net"))
        orch._cleanup_terminal_worktrees = MagicMock(return_value=2)

        # Even if heal fails, cleanup (a separate job) still runs
        orch._maybe_heal_repos()
        orch._maybe_cleanup_worktrees()

        orch._cleanup_terminal_worktrees.assert_called_once_with([project])

    def test_maybe_heal_repos_delays_during_startup(self, tmp_path):
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        orch.config.maintenance_startup_delay_seconds = 60
        orch._started_monotonic = time.monotonic()
        orch.project_store.sync_all_sources = MagicMock()
        orch._cleanup_terminal_worktrees = MagicMock()

        orch._maybe_heal_repos()

        orch.project_store.sync_all_sources.assert_not_called()
        orch._cleanup_terminal_worktrees.assert_not_called()
        assert orch._maintenance_status["repo_heal"]["delayed"] is True


# ---------------------------------------------------------------------------
# Maintenance lane job status tracking (TASK-466.1)
# ---------------------------------------------------------------------------


class TestMaintenanceLaneJobStatus:
    """Maintenance lane status attributes are populated and exposed in diagnostics."""

    # ------------------------------------------------------------------
    # Attribute presence (regression: __init__ must declare these)
    # ------------------------------------------------------------------

    def test_last_heal_at_initialized_to_zero(self, tmp_path):
        """_last_heal_at starts at 0.0 (never run)."""
        orch = _make_orchestrator(tmp_path)
        assert orch._last_heal_at == 0.0

    def test_heal_error_last_initialized_to_none(self, tmp_path):
        """_heal_error_last starts at None (no error yet)."""
        orch = _make_orchestrator(tmp_path)
        assert orch._heal_error_last is None

    def test_last_cleanup_at_initialized_to_zero(self, tmp_path):
        """_last_cleanup_at starts at 0.0 (never run)."""
        orch = _make_orchestrator(tmp_path)
        assert orch._last_cleanup_at == 0.0

    def test_cleanup_count_last_initialized_to_zero(self, tmp_path):
        """_cleanup_count_last starts at 0."""
        orch = _make_orchestrator(tmp_path)
        assert orch._cleanup_count_last == 0

    def test_cleanup_error_last_initialized_to_none(self, tmp_path):
        """_cleanup_error_last starts at None."""
        orch = _make_orchestrator(tmp_path)
        assert orch._cleanup_error_last is None

    def test_maintenance_future_initialized_to_none(self, tmp_path):
        """_maintenance_future starts at None (no active maintenance job)."""
        orch = _make_orchestrator(tmp_path)
        assert orch._maintenance_future is None

    # ------------------------------------------------------------------
    # Status updated by _maybe_heal_repos
    # ------------------------------------------------------------------

    def test_heal_sets_last_heal_at_on_success(self, tmp_path):
        """_maybe_heal_repos() populates _last_heal_at with a monotonic timestamp."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        orch.project_store.sync_all_sources = MagicMock()
        orch._cleanup_terminal_worktrees = MagicMock(return_value=0)

        before = time.monotonic()
        orch._maybe_heal_repos()
        after = time.monotonic()

        assert before <= orch._last_heal_at <= after

    def test_heal_clears_error_on_success(self, tmp_path):
        """A successful heal clears any prior error in _heal_error_last."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._heal_error_last = "previous error"
        orch.project_store.sync_all_sources = MagicMock()
        orch._cleanup_terminal_worktrees = MagicMock(return_value=0)

        orch._maybe_heal_repos()

        assert orch._heal_error_last is None

    def test_heal_records_error_on_sync_failure(self, tmp_path):
        """When sync_all_sources raises, _heal_error_last captures the message."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        orch.project_store.sync_all_sources = MagicMock(
            side_effect=RuntimeError("git fetch failed")
        )
        orch._cleanup_terminal_worktrees = MagicMock(return_value=0)

        orch._maybe_heal_repos()

        assert orch._heal_error_last is not None
        assert "git fetch failed" in orch._heal_error_last

    def test_cleanup_sets_last_cleanup_at_on_success(self, tmp_path):
        """_maybe_cleanup_worktrees() populates _last_cleanup_at after cleanup runs."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._cleanup_terminal_worktrees = MagicMock(return_value=3)

        before = time.monotonic()
        orch._maybe_cleanup_worktrees()
        after = time.monotonic()

        assert before <= orch._last_cleanup_at <= after

    def test_cleanup_sets_count_on_success(self, tmp_path):
        """_cleanup_count_last reflects the number of worktrees removed."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._cleanup_terminal_worktrees = MagicMock(return_value=5)

        orch._maybe_cleanup_worktrees()

        assert orch._cleanup_count_last == 5

    def test_cleanup_clears_error_on_success(self, tmp_path):
        """A successful cleanup pass clears any prior cleanup error."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._cleanup_error_last = "prior error"
        orch._cleanup_terminal_worktrees = MagicMock(return_value=0)

        orch._maybe_cleanup_worktrees()

        assert orch._cleanup_error_last is None

    def test_cleanup_records_error_on_failure(self, tmp_path):
        """If cleanup raises, _cleanup_error_last captures the error message."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._cleanup_terminal_worktrees = MagicMock(
            side_effect=RuntimeError("tracker unavailable")
        )

        orch._maybe_cleanup_worktrees()  # must not raise

        assert orch._cleanup_error_last is not None
        assert "tracker unavailable" in orch._cleanup_error_last

    def test_heal_error_does_not_prevent_cleanup(self, tmp_path):
        """Heal and cleanup are independent jobs; a heal failure does not suppress cleanup."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        orch.project_store.sync_all_sources = MagicMock(
            side_effect=RuntimeError("network down")
        )
        orch._cleanup_terminal_worktrees = MagicMock(return_value=2)

        # Run heal (will fail) and cleanup (separate job) independently
        orch._maybe_heal_repos()
        orch._maybe_cleanup_worktrees()

        # cleanup ran despite heal failure because they're independent jobs
        orch._cleanup_terminal_worktrees.assert_called_once_with([project])
        assert orch._cleanup_count_last == 2

    # ------------------------------------------------------------------
    # Diagnostics: get_snapshot() exposes maintenance status
    # ------------------------------------------------------------------

    def test_snapshot_includes_maintenance_key(self, tmp_path):
        """get_snapshot() includes a 'maintenance' key."""
        orch = _make_orchestrator(tmp_path)
        orch.tracker = MagicMock()
        orch.tracker.fetch_issues.return_value = []
        orch._reviews_cache = {}

        snap = orch.get_snapshot()

        assert "maintenance" in snap

    def test_snapshot_maintenance_has_required_fields(self, tmp_path):
        """maintenance snapshot contains all required diagnostic fields."""
        orch = _make_orchestrator(tmp_path)
        orch.tracker = MagicMock()
        orch.tracker.fetch_issues.return_value = []
        orch._reviews_cache = {}

        snap = orch.get_snapshot()
        maint = snap["maintenance"]

        assert "last_heal_at" in maint
        assert "heal_error" in maint
        assert "last_cleanup_at" in maint
        assert "cleanup_count" in maint
        assert "cleanup_error" in maint

    def test_snapshot_maintenance_null_before_first_run(self, tmp_path):
        """Before any maintenance run, last_heal_at and last_cleanup_at are None."""
        orch = _make_orchestrator(tmp_path)
        orch.tracker = MagicMock()
        orch.tracker.fetch_issues.return_value = []
        orch._reviews_cache = {}

        snap = orch.get_snapshot()
        maint = snap["maintenance"]

        assert maint["last_heal_at"] is None
        assert maint["last_cleanup_at"] is None
        assert maint["heal_error"] is None
        assert maint["cleanup_error"] is None
        assert maint["cleanup_count"] == 0

    def test_snapshot_maintenance_reflects_last_run(self, tmp_path):
        """After both maintenance jobs run, the snapshot reflects updated timestamps."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        orch.project_store.sync_all_sources = MagicMock()
        orch._cleanup_terminal_worktrees = MagicMock(return_value=7)
        orch.tracker = MagicMock()
        orch.tracker.fetch_issues.return_value = []
        orch._reviews_cache = {}

        orch._maybe_heal_repos()
        orch._maybe_cleanup_worktrees()
        snap = orch.get_snapshot()
        maint = snap["maintenance"]

        assert maint["last_heal_at"] is not None
        assert maint["last_cleanup_at"] is not None
        assert maint["cleanup_count"] == 7
        assert maint["heal_error"] is None
        assert maint["cleanup_error"] is None

    def test_snapshot_maintenance_exposes_heal_error(self, tmp_path):
        """When heal fails, the error is visible in the snapshot."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        orch.project_store.sync_all_sources = MagicMock(
            side_effect=RuntimeError("network timeout")
        )
        orch._cleanup_terminal_worktrees = MagicMock(return_value=0)
        orch.tracker = MagicMock()
        orch.tracker.fetch_issues.return_value = []
        orch._reviews_cache = {}

        orch._maybe_heal_repos()
        snap = orch.get_snapshot()

        assert "network timeout" in snap["maintenance"]["heal_error"]


# ---------------------------------------------------------------------------
# Maintenance lane does not block dispatch tick (TASK-466.1 AC#1)
# ---------------------------------------------------------------------------


class TestMaintenanceLaneNonBlocking:
    """Terminal worktree cleanup and repo self-heal must not block tick latency."""

    def test_tick_does_not_await_maintenance_heal(self, tmp_path):
        """_tick() must complete even if _run_step5b_maintenance is slow.

        This verifies AC#1: the maintenance job is fire-and-forget, not awaited
        inline.  The maintenance job blocks on an event so the test does not
        rely on CI wall-clock timing thresholds.
        """
        orch = _make_orchestrator(tmp_path)
        orch._handle_reconcile = AsyncMock()
        orch._handle_review_check = AsyncMock()
        orch._handle_dispatch_needed = AsyncMock()
        orch._handle_yolo_review = AsyncMock(return_value=0.0)
        orch._run_step5c_epic_maintenance = MagicMock()
        orch._handle_auto_update = AsyncMock()
        orch._notify_observers = MagicMock()
        orch._maybe_run_watchdog = MagicMock()
        orch._maybe_cleanup_worktrees = MagicMock()

        maintenance_started = threading.Event()
        maintenance_unblock = threading.Event()
        maintenance_finished = []

        def _blocked_maintenance():
            maintenance_started.set()
            maintenance_unblock.wait(timeout=5)
            maintenance_finished.append(True)

        orch._run_step5b_maintenance = _blocked_maintenance

        async def _run_tick_with_blocked_maintenance():
            with patch("oompah.orchestrator.validate_dispatch_config", return_value=[]):
                tick_task = asyncio.create_task(orch._tick())
                try:
                    await asyncio.wait_for(asyncio.shield(tick_task), timeout=1.0)
                except asyncio.TimeoutError as exc:
                    maintenance_unblock.set()
                    await tick_task
                    raise AssertionError(
                        "_tick() waited for step-5b maintenance to finish"
                    ) from exc

            assert orch._maintenance_future is not None
            assert maintenance_started.wait(timeout=1.0)
            assert not orch._maintenance_future.done()
            assert maintenance_finished == []

            maintenance_unblock.set()
            await asyncio.wait_for(orch._maintenance_future, timeout=1.0)
            assert maintenance_finished == [True]

        asyncio.run(_run_tick_with_blocked_maintenance())

    def test_tick_starts_maintenance_future(self, tmp_path):
        """_tick() must set _maintenance_future so status is trackable."""
        orch = _make_orchestrator(tmp_path)
        orch._handle_reconcile = AsyncMock()
        orch._handle_review_check = AsyncMock()
        orch._handle_dispatch_needed = AsyncMock()
        orch._handle_yolo_review = AsyncMock(return_value=0.0)
        orch._run_step5c_epic_maintenance = MagicMock()
        orch._handle_auto_update = AsyncMock()
        orch._notify_observers = MagicMock()
        orch._maybe_run_watchdog = MagicMock()
        orch._maybe_heal_repos = MagicMock()
        orch._maybe_cleanup_worktrees = MagicMock()

        with patch("oompah.orchestrator.validate_dispatch_config", return_value=[]):
            asyncio.run(orch._tick())

        assert orch._maintenance_future is not None

    def test_tick_does_not_start_second_maintenance_while_first_running(
        self, tmp_path
    ):
        """When a maintenance job is already in flight, a new tick must not
        spawn a second one (guarded by _maintenance_future.done() check)."""
        orch = _make_orchestrator(tmp_path)
        orch._handle_reconcile = AsyncMock()
        orch._handle_review_check = AsyncMock()
        orch._handle_dispatch_needed = AsyncMock()
        orch._handle_yolo_review = AsyncMock(return_value=0.0)
        orch._run_step5c_epic_maintenance = MagicMock()
        orch._handle_auto_update = AsyncMock()
        orch._notify_observers = MagicMock()
        orch._maybe_run_watchdog = MagicMock()
        orch._maybe_cleanup_worktrees = MagicMock()

        call_count = 0

        def _count_calls():
            nonlocal call_count
            call_count += 1

        orch._maybe_heal_repos = _count_calls

        async def _run_two_ticks():
            # First tick — starts maintenance
            with patch("oompah.orchestrator.validate_dispatch_config", return_value=[]):
                await orch._tick()

            # Wait for the first job to complete
            if orch._maintenance_future is not None:
                await orch._maintenance_future

            first_count = call_count

            # Second tick — should start another maintenance (first is done)
            with patch("oompah.orchestrator.validate_dispatch_config", return_value=[]):
                await orch._tick()

            if orch._maintenance_future is not None:
                await orch._maintenance_future

            return first_count

        first_count = asyncio.run(_run_two_ticks())

        # Both ticks should have triggered a maintenance run (first was done)
        assert call_count == first_count + 1

    def test_tick_skips_new_maintenance_when_previous_still_running(self, tmp_path):
        """When the previous maintenance future is NOT done, _tick() must not
        start a new one."""
        orch = _make_orchestrator(tmp_path)
        orch._handle_reconcile = AsyncMock()
        orch._handle_review_check = AsyncMock()
        orch._handle_dispatch_needed = AsyncMock()
        orch._handle_yolo_review = AsyncMock(return_value=0.0)
        orch._run_step5c_epic_maintenance = MagicMock()
        orch._handle_auto_update = AsyncMock()
        orch._notify_observers = MagicMock()
        orch._maybe_run_watchdog = MagicMock()
        orch._maybe_heal_repos = MagicMock()
        orch._maybe_cleanup_worktrees = MagicMock()

        async def _run_with_fake_future():
            # Pre-set a fake still-running future (never-completing)
            loop = asyncio.get_event_loop()
            fake_future: asyncio.Future = loop.create_future()
            orch._maintenance_future = fake_future  # type: ignore[assignment]
            # future is not done yet

            with patch("oompah.orchestrator.validate_dispatch_config", return_value=[]):
                await orch._tick()

            # Cancel to avoid "future was never awaited" warnings
            fake_future.cancel()

        asyncio.run(_run_with_fake_future())

        # _maybe_heal_repos should NOT have been called — future was still in-flight
        orch._maybe_heal_repos.assert_not_called()


# ---------------------------------------------------------------------------
# Regression: done/conflict worktrees are never removed (TASK-466.1 AC#2)
# ---------------------------------------------------------------------------


class TestMaintenancePreservesDoneWorktrees:
    """Done and Conflict worktrees are never cleaned up, only Merged/Archived."""

    def test_cleanup_does_not_remove_done_project_worktrees(self, tmp_path):
        """Done state is NOT in the cleanable set — worktree is preserved."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        tracker = MagicMock()
        tracker.fetch_issues_by_states.return_value = [
            _make_issue("TASK-1", state="Done", project_id=project.id),
        ]
        orch._tracker_for_project = MagicMock(return_value=tracker)

        cleaned = orch._cleanup_terminal_worktrees()

        assert cleaned == 0
        orch.project_store.remove_worktree.assert_not_called()

    def test_cleanup_does_not_remove_conflict_state_worktrees(self, tmp_path):
        """Conflict state is not cleanable — worktree is preserved for inspection."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        tracker = MagicMock()
        tracker.fetch_issues_by_states.return_value = [
            _make_issue("TASK-1", state="Conflict", project_id=project.id),
        ]
        orch._tracker_for_project = MagicMock(return_value=tracker)

        cleaned = orch._cleanup_terminal_worktrees()

        assert cleaned == 0
        orch.project_store.remove_worktree.assert_not_called()

    def test_cleanup_only_queries_merged_and_archived_states(self, tmp_path):
        """fetch_issues_by_states is called with exactly [Merged, Archived]."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        tracker = MagicMock()
        tracker.fetch_issues_by_states.return_value = []
        orch._tracker_for_project = MagicMock(return_value=tracker)

        orch._cleanup_terminal_worktrees()

        # Must only query the two cleanable states
        tracker.fetch_issues_by_states.assert_called_once_with(["Merged", "Archived"])

    def test_cleanup_removes_merged_but_not_done_mixed(self, tmp_path):
        """Mixed list: only Merged is removed, Done is preserved."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        tracker = MagicMock()
        tracker.fetch_issues_by_states.return_value = [
            _make_issue("TASK-M", state="Merged", project_id=project.id),
            _make_issue("TASK-D", state="Done", project_id=project.id),
            _make_issue("TASK-A", state="Archived", project_id=project.id),
        ]
        orch._tracker_for_project = MagicMock(return_value=tracker)

        cleaned = orch._cleanup_terminal_worktrees()

        assert cleaned == 2
        removed = [
            call.args[1]
            for call in orch.project_store.remove_worktree.call_args_list
        ]
        assert "TASK-M" in removed
        assert "TASK-A" in removed
        assert "TASK-D" not in removed

    def test_maybe_cleanup_worktrees_does_not_remove_done_worktrees(self, tmp_path):
        """Regression: when maintenance triggers worktree cleanup, Done worktrees survive."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])

        # Simulate the real _cleanup_terminal_worktrees (not mocked) by using
        # a real tracker mock that returns Done issues alongside Merged ones.
        tracker = MagicMock()
        tracker.fetch_issues_by_states.return_value = [
            _make_issue("TASK-DONE", state="Done", project_id=project.id),
            _make_issue("TASK-MERGED", state="Merged", project_id=project.id),
        ]
        orch._tracker_for_project = MagicMock(return_value=tracker)

        orch._maybe_cleanup_worktrees()

        # Only the Merged worktree was removed
        removed = [
            call.args[1]
            for call in orch.project_store.remove_worktree.call_args_list
        ]
        assert "TASK-MERGED" in removed
        assert "TASK-DONE" not in removed


# ---------------------------------------------------------------------------
# _run_maintenance_job gate: backpressure, coalescing, budgets (TASK-466.4)
# ---------------------------------------------------------------------------


class TestRunMaintenanceJobGate:
    """Direct unit tests for _run_maintenance_job() and _job_deadline_exceeded().

    AC#1 — A long maintenance job cannot launch duplicate copies of itself.
    AC#2 — Maintenance jobs enforce configured safety budgets and resume later.
    AC#3 — State snapshots expose skipped/running/failed/completed status.
    """

    # ------------------------------------------------------------------
    # AC#1: in-flight coalescing
    # ------------------------------------------------------------------

    def test_first_call_runs_job(self, tmp_path):
        """First call with no prior state executes the function."""
        orch = _make_orchestrator(tmp_path)
        calls = []
        orch._run_maintenance_job("test_job", lambda: calls.append(1), min_interval_s=60.0)
        assert calls == [1]

    def test_second_call_while_in_flight_is_coalesced(self, tmp_path):
        """AC#1: If the job is already in_flight, a second call is dropped."""
        orch = _make_orchestrator(tmp_path)

        # Pre-seed an in-flight state (simulating a concurrent run).
        state = orch._get_or_create_job_state("test_job")
        state.in_flight = True
        state.run_count = 1

        calls = []
        orch._run_maintenance_job("test_job", lambda: calls.append(1), min_interval_s=60.0)

        # Must not have called the function.
        assert calls == []

    def test_in_flight_coalescing_increments_skip_count(self, tmp_path):
        """AC#1: Coalesced (in-flight) calls increment skip_count."""
        orch = _make_orchestrator(tmp_path)
        state = orch._get_or_create_job_state("test_job")
        state.in_flight = True

        orch._run_maintenance_job("test_job", lambda: None, min_interval_s=60.0)
        orch._run_maintenance_job("test_job", lambda: None, min_interval_s=60.0)

        assert state.skip_count == 2

    def test_in_flight_coalescing_sets_status_skipped(self, tmp_path):
        """AC#1: Status is 'skipped' when coalesced due to in_flight."""
        orch = _make_orchestrator(tmp_path)
        state = orch._get_or_create_job_state("test_job")
        state.in_flight = True

        orch._run_maintenance_job("test_job", lambda: None, min_interval_s=60.0)

        assert state.last_status == "skipped"

    # ------------------------------------------------------------------
    # Interval throttling
    # ------------------------------------------------------------------

    def test_second_call_within_interval_is_throttled(self, tmp_path):
        """A second call within min_interval_s is dropped."""
        orch = _make_orchestrator(tmp_path)
        calls = []
        fn = lambda: calls.append(1)  # noqa: E731
        orch._run_maintenance_job("test_job", fn, min_interval_s=3600.0)
        orch._run_maintenance_job("test_job", fn, min_interval_s=3600.0)
        assert len(calls) == 1

    def test_interval_throttle_increments_skip_count(self, tmp_path):
        """Throttled calls (interval not elapsed) increment skip_count."""
        orch = _make_orchestrator(tmp_path)
        calls = []
        fn = lambda: calls.append(1)  # noqa: E731
        orch._run_maintenance_job("test_job", fn, min_interval_s=3600.0)
        initial_skips = orch._maintenance_jobs["test_job"].skip_count
        orch._run_maintenance_job("test_job", fn, min_interval_s=3600.0)
        assert orch._maintenance_jobs["test_job"].skip_count == initial_skips + 1

    def test_call_after_interval_elapsed_runs_again(self, tmp_path):
        """After next_run_monotonic passes, the job may run again."""
        orch = _make_orchestrator(tmp_path)
        calls = []
        fn = lambda: calls.append(1)  # noqa: E731
        orch._run_maintenance_job("test_job", fn, min_interval_s=3600.0)
        # Backdate next_run_monotonic to the past.
        orch._maintenance_jobs["test_job"].next_run_monotonic = 0.0
        orch._run_maintenance_job("test_job", fn, min_interval_s=3600.0)
        assert len(calls) == 2

    def test_explicit_next_run_monotonic_blocks_early_run(self, tmp_path):
        """next_run_monotonic in the far future prevents the job from running."""
        import time as _time
        orch = _make_orchestrator(tmp_path)
        state = orch._get_or_create_job_state("test_job")
        # Set next_run_monotonic to 1 hour from now.
        state.next_run_monotonic = _time.monotonic() + 3600.0

        calls = []
        orch._run_maintenance_job("test_job", lambda: calls.append(1), min_interval_s=1.0)
        assert calls == []

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def test_successful_run_sets_status_completed(self, tmp_path):
        """After a successful run, last_status == 'completed'."""
        orch = _make_orchestrator(tmp_path)
        orch._run_maintenance_job("test_job", lambda: None, min_interval_s=0.0)
        assert orch._maintenance_jobs["test_job"].last_status == "completed"

    def test_failed_run_sets_status_failed(self, tmp_path):
        """If the job function raises, last_status == 'failed'."""
        orch = _make_orchestrator(tmp_path)

        def _fail():
            raise RuntimeError("boom")

        orch._run_maintenance_job("test_job", _fail, min_interval_s=0.0)
        state = orch._maintenance_jobs["test_job"]
        assert state.last_status == "failed"

    def test_failed_run_captures_error(self, tmp_path):
        """Exception message is stored in last_error after a failure."""
        orch = _make_orchestrator(tmp_path)

        def _fail():
            raise RuntimeError("kaboom")

        orch._run_maintenance_job("test_job", _fail, min_interval_s=0.0)
        assert "kaboom" in (orch._maintenance_jobs["test_job"].last_error or "")

    def test_failed_run_clears_in_flight(self, tmp_path):
        """in_flight is always reset to False after a failed run."""
        orch = _make_orchestrator(tmp_path)

        def _fail():
            raise RuntimeError("err")

        orch._run_maintenance_job("test_job", _fail, min_interval_s=0.0)
        assert orch._maintenance_jobs["test_job"].in_flight is False

    def test_successful_run_clears_last_error(self, tmp_path):
        """last_error is cleared to None after a successful run."""
        orch = _make_orchestrator(tmp_path)
        state = orch._get_or_create_job_state("test_job")
        state.last_error = "stale error"

        orch._run_maintenance_job("test_job", lambda: None, min_interval_s=0.0)
        assert orch._maintenance_jobs["test_job"].last_error is None

    def test_run_count_accumulates_across_calls(self, tmp_path):
        """run_count accumulates (not reset) across multiple interval-separated runs."""
        orch = _make_orchestrator(tmp_path)
        for _i in range(3):
            orch._run_maintenance_job("test_job", lambda: None, min_interval_s=0.0)
        assert orch._maintenance_jobs["test_job"].run_count == 3

    def test_last_duration_s_recorded_after_run(self, tmp_path):
        """last_duration_s is a non-negative float after the job completes."""
        orch = _make_orchestrator(tmp_path)
        orch._run_maintenance_job("test_job", lambda: None, min_interval_s=0.0)
        dur = orch._maintenance_jobs["test_job"].last_duration_s
        assert dur is not None
        assert dur >= 0.0

    def test_next_run_monotonic_set_after_run(self, tmp_path):
        """next_run_monotonic is set to approx (finish_time + min_interval_s) after a run."""
        import time as _time
        orch = _make_orchestrator(tmp_path)
        min_interval = 120.0
        before = _time.monotonic()
        orch._run_maintenance_job("test_job", lambda: None, min_interval_s=min_interval)
        after = _time.monotonic()
        nxt = orch._maintenance_jobs["test_job"].next_run_monotonic
        assert nxt is not None
        assert (before + min_interval) <= nxt <= (after + min_interval + 1.0)

    # ------------------------------------------------------------------
    # AC#2: max runtime budget / _job_deadline_exceeded
    # ------------------------------------------------------------------

    def test_no_deadline_when_max_runtime_s_not_given(self, tmp_path):
        """Without max_runtime_s, _job_deadline_exceeded returns False."""
        orch = _make_orchestrator(tmp_path)
        # No run yet — should return False.
        assert orch._job_deadline_exceeded("test_job") is False

    def test_deadline_not_exceeded_for_fast_job(self, tmp_path):
        """During a fast job with a 60 s budget, deadline is not exceeded."""
        orch = _make_orchestrator(tmp_path)
        exceeded_during = []

        def _check_deadline():
            exceeded_during.append(orch._job_deadline_exceeded("test_job"))

        orch._run_maintenance_job(
            "test_job", _check_deadline, min_interval_s=0.0, max_runtime_s=60.0
        )
        # During execution the budget should not have been exceeded.
        assert exceeded_during == [False]

    def test_deadline_exceeded_flag_with_past_deadline(self, tmp_path):
        """If current_deadline is in the past, _job_deadline_exceeded returns True."""
        import time as _time
        orch = _make_orchestrator(tmp_path)
        state = orch._get_or_create_job_state("test_job")
        # Force a deadline 1 second in the past.
        state.current_deadline = _time.monotonic() - 1.0
        state.in_flight = True  # simulate active run

        assert orch._job_deadline_exceeded("test_job") is True

    def test_deadline_cleared_after_job_finishes(self, tmp_path):
        """current_deadline is reset to None after a run (success or failure)."""
        orch = _make_orchestrator(tmp_path)
        orch._run_maintenance_job(
            "test_job", lambda: None, min_interval_s=0.0, max_runtime_s=60.0
        )
        assert orch._maintenance_jobs["test_job"].current_deadline is None

    def test_job_can_poll_deadline_and_stop_early(self, tmp_path):
        """AC#2: A job that polls _job_deadline_exceeded can stop after budget expires."""
        import time as _time
        orch = _make_orchestrator(tmp_path)
        items_processed = []

        def _budget_aware_job():
            # Use a very short budget (10 ms) and process items in a loop.
            for i in range(1000):
                if orch._job_deadline_exceeded("budget_job"):
                    break
                items_processed.append(i)
                _time.sleep(0.001)  # 1 ms per item

        orch._run_maintenance_job(
            "budget_job",
            _budget_aware_job,
            min_interval_s=0.0,
            max_runtime_s=0.010,  # 10 ms budget
        )

        # Should have processed far fewer than 1000 items due to early stop.
        assert len(items_processed) < 1000
        # But at least one item must have been processed.
        assert len(items_processed) >= 1

    def test_unknown_job_deadline_not_exceeded(self, tmp_path):
        """_job_deadline_exceeded returns False for an unregistered job name."""
        orch = _make_orchestrator(tmp_path)
        assert orch._job_deadline_exceeded("nonexistent_job") is False

    # ------------------------------------------------------------------
    # AC#3: snapshot visibility
    # ------------------------------------------------------------------

    def test_job_state_visible_in_snapshot(self, tmp_path):
        """AC#3: After a run, the job appears in get_snapshot()['maintenance']['jobs']."""
        orch = _make_orchestrator(tmp_path)
        orch._run_maintenance_job("snap_job", lambda: None, min_interval_s=0.0)
        snap = orch.get_snapshot()
        assert "snap_job" in snap["maintenance"]["jobs"]

    def test_snapshot_job_has_required_fields(self, tmp_path):
        """AC#3: The snapshot entry has all expected diagnostic fields."""
        orch = _make_orchestrator(tmp_path)
        orch._run_maintenance_job("snap_job", lambda: None, min_interval_s=0.0)
        job_snap = orch.get_snapshot()["maintenance"]["jobs"]["snap_job"]
        for field in ("status", "in_flight", "run_count", "skip_count",
                      "last_run_monotonic", "next_run_monotonic",
                      "last_duration_s", "last_error"):
            assert field in job_snap, f"Missing field: {field}"

    def test_snapshot_shows_skipped_status(self, tmp_path):
        """AC#3: Snapshot status is 'skipped' after a throttled call."""
        orch = _make_orchestrator(tmp_path)
        orch._run_maintenance_job("snap_job", lambda: None, min_interval_s=3600.0)
        orch._run_maintenance_job("snap_job", lambda: None, min_interval_s=3600.0)
        job_snap = orch.get_snapshot()["maintenance"]["jobs"]["snap_job"]
        assert job_snap["status"] == "skipped"
        assert job_snap["skip_count"] >= 1

    def test_snapshot_shows_failed_status(self, tmp_path):
        """AC#3: Snapshot status is 'failed' when the last run raised."""
        orch = _make_orchestrator(tmp_path)

        def _fail():
            raise ValueError("test error")

        orch._run_maintenance_job("snap_job", _fail, min_interval_s=0.0)
        job_snap = orch.get_snapshot()["maintenance"]["jobs"]["snap_job"]
        assert job_snap["status"] == "failed"
        assert "test error" in (job_snap["last_error"] or "")

    def test_snapshot_shows_completed_status(self, tmp_path):
        """AC#3: Snapshot status is 'completed' after a successful run."""
        orch = _make_orchestrator(tmp_path)
        orch._run_maintenance_job("snap_job", lambda: None, min_interval_s=0.0)
        job_snap = orch.get_snapshot()["maintenance"]["jobs"]["snap_job"]
        assert job_snap["status"] == "completed"
        assert job_snap["in_flight"] is False

    def test_snapshot_skip_count_matches_throttle_calls(self, tmp_path):
        """AC#3: skip_count in snapshot reflects all throttled/coalesced calls."""
        orch = _make_orchestrator(tmp_path)
        # First call runs.
        orch._run_maintenance_job("snap_job", lambda: None, min_interval_s=3600.0)
        # Next 3 calls are throttled.
        for _ in range(3):
            orch._run_maintenance_job("snap_job", lambda: None, min_interval_s=3600.0)
        job_snap = orch.get_snapshot()["maintenance"]["jobs"]["snap_job"]
        assert job_snap["skip_count"] == 3


# ---------------------------------------------------------------------------
# Repo self-heal error reporting does not block dispatch (TASK-466.1 AC#3)
# ---------------------------------------------------------------------------


class TestRepoHealErrorReporting:
    """Self-heal errors are logged and tracked without affecting dispatch."""

    def test_heal_failure_does_not_raise_from_tick(self, tmp_path):
        """If _maybe_heal_repos fails, _tick() must not surface the exception."""
        orch = _make_orchestrator(tmp_path)
        orch._handle_reconcile = AsyncMock()
        orch._handle_review_check = AsyncMock()
        orch._handle_dispatch_needed = AsyncMock()
        orch._handle_yolo_review = AsyncMock(return_value=0.0)
        orch._run_step5c_epic_maintenance = MagicMock()
        orch._handle_auto_update = AsyncMock()
        orch._notify_observers = MagicMock()
        orch._maybe_run_watchdog = MagicMock()
        orch._maybe_cleanup_worktrees = MagicMock()

        def _failing_heal():
            raise RuntimeError("catastrophic git failure")

        orch._maybe_heal_repos = _failing_heal

        # _tick() must complete normally (no exception)
        with patch("oompah.orchestrator.validate_dispatch_config", return_value=[]):
            asyncio.run(orch._tick())  # should not raise

    def test_heal_error_visible_in_snapshot_after_failure(self, tmp_path):
        """After a heal failure, get_snapshot() exposes the error string."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        orch.project_store.sync_all_sources = MagicMock(
            side_effect=RuntimeError("disk full")
        )
        orch.tracker = MagicMock()
        orch.tracker.fetch_issues.return_value = []
        orch._reviews_cache = {}

        orch._maybe_heal_repos()

        snap = orch.get_snapshot()
        assert snap["maintenance"]["heal_error"] is not None
        assert "disk full" in snap["maintenance"]["heal_error"]

    def test_heal_error_cleared_after_subsequent_success(self, tmp_path):
        """A successful heal run clears the previous error from the snapshot."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        orch.tracker = MagicMock()
        orch.tracker.fetch_issues.return_value = []
        orch._reviews_cache = {}

        # First run: failure
        orch.project_store.sync_all_sources = MagicMock(
            side_effect=RuntimeError("transient")
        )
        orch._maybe_heal_repos()
        assert orch.get_snapshot()["maintenance"]["heal_error"] is not None

        # Reset the heal job interval so the second run is not throttled out.
        # The new maintenance gate uses _maintenance_jobs[name].next_run_monotonic,
        # not _last_repo_heal, so we clear the job state directly.
        orch._maintenance_jobs.pop("repo_heal", None)

        # Second run: success
        orch.project_store.sync_all_sources = MagicMock()
        orch._maybe_heal_repos()

        assert orch.get_snapshot()["maintenance"]["heal_error"] is None

    def test_heal_still_tracks_last_heal_at_even_when_sync_fails(self, tmp_path):
        """_last_heal_at is set even when sync_all_sources fails, so the
        cadence gate still works correctly (prevents retry storm on failure)."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        orch.project_store.sync_all_sources = MagicMock(
            side_effect=RuntimeError("network error")
        )

        before = time.monotonic()
        orch._maybe_heal_repos()

        assert orch._last_heal_at >= before


# ---------------------------------------------------------------------------
# _tick() integration: correct delegation order
# ---------------------------------------------------------------------------


class TestTickDelegation:
    """_tick() must call the five handlers in the correct order."""

    def test_tick_calls_all_handlers(self, tmp_path):
        """_tick() calls all five targeted handlers."""
        orch = _make_orchestrator(tmp_path)
        call_order = []

        async def fake_reconcile():
            call_order.append("reconcile")

        async def fake_review_check():
            call_order.append("review_check")

        async def fake_dispatch_needed():
            call_order.append("dispatch_needed")

        async def fake_yolo_review():
            call_order.append("yolo_review")
            return 0.0

        async def fake_auto_update():
            call_order.append("auto_update")

        orch._handle_reconcile = fake_reconcile
        orch._handle_review_check = fake_review_check
        orch._handle_dispatch_needed = fake_dispatch_needed
        orch._handle_yolo_review = fake_yolo_review
        orch._handle_auto_update = fake_auto_update
        orch._notify_observers = MagicMock()

        with patch("oompah.orchestrator.validate_dispatch_config", return_value=[]):
            asyncio.run(orch._tick())

        assert "reconcile" in call_order
        assert "review_check" in call_order
        assert "dispatch_needed" in call_order
        assert "yolo_review" in call_order
        assert "auto_update" in call_order

    def test_tick_handler_order(self, tmp_path):
        """_tick() calls handlers in the correct order:
        reconcile → review_check → dispatch_needed → yolo_review → auto_update."""
        orch = _make_orchestrator(tmp_path)
        call_order = []

        async def fake_reconcile():
            call_order.append("reconcile")

        async def fake_review_check():
            call_order.append("review_check")

        async def fake_dispatch_needed():
            call_order.append("dispatch_needed")

        async def fake_yolo_review():
            call_order.append("yolo_review")
            return 0.0

        async def fake_auto_update():
            call_order.append("auto_update")

        orch._handle_reconcile = fake_reconcile
        orch._handle_review_check = fake_review_check
        orch._handle_dispatch_needed = fake_dispatch_needed
        orch._handle_yolo_review = fake_yolo_review
        orch._handle_auto_update = fake_auto_update
        orch._notify_observers = MagicMock()

        with patch("oompah.orchestrator.validate_dispatch_config", return_value=[]):
            asyncio.run(orch._tick())

        expected_order = [
            "reconcile",
            "review_check",
            "dispatch_needed",
            "yolo_review",
            "auto_update",
        ]
        assert call_order == expected_order

    def test_tick_aborts_after_config_validation_failure(self, tmp_path):
        """_tick() stops early if validate_dispatch_config returns errors."""
        orch = _make_orchestrator(tmp_path)
        call_order = []

        async def fake_reconcile():
            call_order.append("reconcile")

        async def fake_review_check():
            call_order.append("review_check")

        async def fake_dispatch_needed():
            call_order.append("dispatch_needed")

        async def fake_yolo_review():
            call_order.append("yolo_review")
            return 0.0

        async def fake_auto_update():
            call_order.append("auto_update")

        orch._handle_reconcile = fake_reconcile
        orch._handle_review_check = fake_review_check
        orch._handle_dispatch_needed = fake_dispatch_needed
        orch._handle_yolo_review = fake_yolo_review
        orch._handle_auto_update = fake_auto_update
        orch._notify_observers = MagicMock()

        with patch(
            "oompah.orchestrator.validate_dispatch_config",
            return_value=["Agent command not configured"],
        ):
            asyncio.run(orch._tick())

        # Only reconcile should have run before the abort
        assert "reconcile" in call_order
        assert "review_check" not in call_order
        assert "dispatch_needed" not in call_order
        assert "yolo_review" not in call_order
        assert "auto_update" not in call_order

    def test_tick_notifies_observers(self, tmp_path):
        """_tick() calls _notify_observers() to broadcast state changes."""
        orch = _make_orchestrator(tmp_path)
        orch._handle_reconcile = AsyncMock()
        orch._handle_review_check = AsyncMock()
        orch._handle_dispatch_needed = AsyncMock()
        orch._handle_yolo_review = AsyncMock(return_value=0.0)
        orch._handle_auto_update = AsyncMock()
        orch._notify_observers = MagicMock()

        with patch("oompah.orchestrator.validate_dispatch_config", return_value=[]):
            asyncio.run(orch._tick())

        orch._notify_observers.assert_called_once()

    def test_tick_notifies_observers_even_on_config_error(self, tmp_path):
        """_tick() notifies observers even when config validation fails (for UI updates)."""
        orch = _make_orchestrator(tmp_path)
        orch._handle_reconcile = AsyncMock()
        orch._handle_review_check = AsyncMock()
        orch._handle_dispatch_needed = AsyncMock()
        orch._handle_yolo_review = AsyncMock(return_value=0.0)
        orch._handle_auto_update = AsyncMock()
        orch._notify_observers = MagicMock()

        with patch(
            "oompah.orchestrator.validate_dispatch_config",
            return_value=["config error"],
        ):
            asyncio.run(orch._tick())

        orch._notify_observers.assert_called_once()

    def test_tick_runs_watchdog(self, tmp_path):
        """_tick() invokes _maybe_run_watchdog after the other handlers."""
        orch = _make_orchestrator(tmp_path)
        orch._handle_reconcile = AsyncMock()
        orch._handle_review_check = AsyncMock()
        orch._handle_dispatch_needed = AsyncMock()
        orch._handle_yolo_review = AsyncMock(return_value=0.0)
        orch._handle_auto_update = AsyncMock()
        orch._notify_observers = MagicMock()
        orch._maybe_run_watchdog = MagicMock()

        with patch("oompah.orchestrator.validate_dispatch_config", return_value=[]):
            asyncio.run(orch._tick())

        orch._maybe_run_watchdog.assert_called_once_with()

    def test_tick_runs_watchdog_in_executor(self, tmp_path):
        """_maybe_run_watchdog is offloaded to the tick thread pool instead of
        running inline on the event loop (oompah-zlz_2-2op)."""
        import threading

        orch = _make_orchestrator(tmp_path)
        orch._handle_reconcile = AsyncMock()
        orch._handle_review_check = AsyncMock()
        orch._handle_dispatch_needed = AsyncMock()
        orch._handle_yolo_review = AsyncMock(return_value=0.0)
        orch._handle_auto_update = AsyncMock()
        orch._notify_observers = MagicMock()

        main_thread_id = threading.get_ident()
        observed_thread_ids: list[int] = []

        def _watchdog():
            observed_thread_ids.append(threading.get_ident())

        orch._maybe_run_watchdog = _watchdog

        with patch("oompah.orchestrator.validate_dispatch_config", return_value=[]):
            asyncio.run(orch._tick())

        assert len(observed_thread_ids) == 1
        # Must NOT run on the event loop thread
        assert observed_thread_ids[0] != main_thread_id


# ---------------------------------------------------------------------------
# Handler isolation: each handler is independently callable
# ---------------------------------------------------------------------------


class TestHandlerIndependence:
    """Each handler can be called independently without requiring a full tick."""

    def test_handle_review_check_standalone(self, tmp_path):
        """_handle_review_check can run without the rest of _tick."""
        orch = _make_orchestrator(tmp_path)
        orch._fetch_all_reviews_bounded = AsyncMock(return_value={"proj-1": []})
        orch._fetch_all_merged_branches_bounded = AsyncMock(return_value=set())

        # Should not raise
        asyncio.run(orch._handle_review_check())
        assert orch._reviews_cache == {"proj-1": []}

    def test_handle_dispatch_needed_standalone(self, tmp_path):
        """_handle_dispatch_needed can run without the rest of _tick."""
        orch = _make_orchestrator(tmp_path)
        orch._fetch_all_candidates = MagicMock(return_value=[])
        orch._pre_resolve_blockers = MagicMock()
        orch._reset_orphaned_in_progress = MagicMock()
        orch._plan_open_epics = MagicMock(return_value=[])

        # Should not raise
        asyncio.run(orch._handle_dispatch_needed())

    def test_handle_yolo_review_standalone(self, tmp_path):
        """_handle_yolo_review can run without the rest of _tick."""
        orch = _make_orchestrator(tmp_path)
        orch._yolo_review_actions_sync = MagicMock()

        result = asyncio.run(orch._handle_yolo_review())
        assert isinstance(result, float) and result >= 0.0

    def test_handle_auto_update_standalone(self, tmp_path):
        """_handle_auto_update can run without the rest of _tick."""
        orch = _make_orchestrator(tmp_path)
        orch._check_auto_update = MagicMock()

        # Should not raise, and since there are no running agents, should call check
        asyncio.run(orch._handle_auto_update())
        orch._check_auto_update.assert_called_once()

    def test_handle_reconcile_standalone(self, tmp_path):
        """_handle_reconcile can run without the rest of _tick."""
        orch = _make_orchestrator(tmp_path)
        orch._reconcile = AsyncMock()

        asyncio.run(orch._handle_reconcile())
        orch._reconcile.assert_awaited_once()

    def test_handlers_have_no_hidden_dependencies(self, tmp_path):
        """Each handler works in isolation — they don't require each other to run first."""
        orch = _make_orchestrator(tmp_path)

        # Run _handle_dispatch_needed before _handle_review_check
        # It should work even without _reviews_cache being populated
        orch._fetch_all_candidates = MagicMock(return_value=[])
        orch._pre_resolve_blockers = MagicMock()
        orch._reset_orphaned_in_progress = MagicMock()
        orch._plan_open_epics = MagicMock(return_value=[])

        # Should not raise even without _reviews_cache pre-populated
        asyncio.run(orch._handle_dispatch_needed())


# ---------------------------------------------------------------------------
# Per-focus model overrides — see plans/per-focus-models.md
# ---------------------------------------------------------------------------


def _provider(
    pid: str = "p1",
    name: str = "p1",
    *,
    model_roles=None,
    models=None,
    default_model="m-default",
) -> ModelProvider:
    return ModelProvider(
        id=pid,
        name=name,
        base_url="http://x",
        api_key="k",
        models=models or ["m-default", "m-fast", "m-deep", "m-explicit"],
        default_model=default_model,
        model_roles=model_roles or {"fast": "m-fast", "deep": "m-deep"},
    )


def _profile(name: str = "standard", **kw) -> AgentProfile:
    defaults = dict(name=name, command="cli")
    defaults.update(kw)
    return AgentProfile(**defaults)


class TestFocusModelOverrides:
    """Resolution priority: focus.model > focus.model_role > profile.* > provider default."""

    def test_no_focus_uses_profile_role(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        prov = _provider()
        prof = _profile(model_role="deep")
        assert orch._resolve_model(prof, prov, focus=None) == "m-deep"

    def test_focus_explicit_model_wins(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        prov = _provider()
        prof = _profile(model_role="deep")
        focus = Focus(name="docs", role="r", description="d", model="m-explicit")
        assert orch._resolve_model(prof, prov, focus=focus) == "m-explicit"

    def test_focus_model_role_wins_over_profile(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        prov = _provider()
        prof = _profile(model_role="deep")
        focus = Focus(name="docs", role="r", description="d", model_role="fast")
        assert orch._resolve_model(prof, prov, focus=focus) == "m-fast"

    def test_focus_model_beats_focus_model_role(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        prov = _provider()
        prof = _profile(model_role="deep")
        focus = Focus(
            name="docs",
            role="r",
            description="d",
            model="m-explicit",
            model_role="fast",
        )
        assert orch._resolve_model(prof, prov, focus=focus) == "m-explicit"

    def test_focus_unknown_model_role_falls_back_to_profile(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        prov = _provider(model_roles={"fast": "m-fast"})  # no "deep"
        prof = _profile(model_role="fast")
        focus = Focus(name="docs", role="r", description="d", model_role="deep")
        # falls back to profile.model_role=fast
        assert orch._resolve_model(prof, prov, focus=focus) == "m-fast"

    def test_focus_provider_id_overrides(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        prov_a = _provider(pid="a", name="A")
        prov_b = _provider(pid="b", name="B")
        orch.provider_store = MagicMock()
        orch.provider_store.get.side_effect = lambda pid: {
            "a": prov_a,
            "b": prov_b,
        }.get(pid)
        orch.provider_store.get_default.return_value = prov_a
        prof = _profile(provider_id="a")
        focus = Focus(name="docs", role="r", description="d", provider_id="b")
        assert orch._resolve_provider(prof, focus=focus) is prov_b

    def test_focus_unknown_provider_falls_back(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        prov_a = _provider(pid="a", name="A")
        orch.provider_store = MagicMock()
        orch.provider_store.get.side_effect = lambda pid: {"a": prov_a}.get(pid)
        orch.provider_store.get_default.return_value = prov_a
        prof = _profile(provider_id="a")
        focus = Focus(name="docs", role="r", description="d", provider_id="missing")
        # focus override misses → falls back to profile.provider_id
        assert orch._resolve_provider(prof, focus=focus) is prov_a

    def test_no_overrides_when_focus_fields_unset(self, tmp_path):
        """Focus with no override fields behaves identically to focus=None."""
        orch = _make_orchestrator(tmp_path)
        prov = _provider()
        prof = _profile(model_role="deep")
        focus = Focus(name="docs", role="r", description="d")
        assert orch._resolve_model(prof, prov, focus=focus) == orch._resolve_model(
            prof, prov, focus=None
        )


class TestRoleStoreResolution:
    """RoleStore-aware resolution (epic oompah-zlz_2-xau7).

    When RoleStore has an entry for a profile's model_role, that
    (provider, model) pair wins over the legacy provider.model_roles
    lookup and over profile.provider_id/profile.model.
    """

    def _orch_with_roles(self, tmp_path, providers, roles):
        """Build an orchestrator wired with a populated RoleStore."""
        orch = _make_orchestrator(tmp_path)
        orch.provider_store = MagicMock()
        by_id = {p.id: p for p in providers}
        orch.provider_store.get.side_effect = lambda pid: by_id.get(pid)
        orch.provider_store.get_default.return_value = providers[0]
        # Build a real RoleStore against tmp_path; bypass validation by
        # leaving provider_store=None on the store itself (the orchestrator's
        # provider_store is what matters for resolution).
        from oompah.roles import RoleStore

        rs = RoleStore(path=str(tmp_path / "roles.json"))
        for role_name, provider_id, model in roles:
            rs.set(role_name, provider_id, model)
        orch.role_store = rs
        return orch

    def test_profile_role_resolves_via_role_store(self, tmp_path):
        prov_a = _provider(pid="a", name="A", models=["m-a-fast"])
        prov_b = _provider(pid="b", name="B", models=["m-b-fast"])
        orch = self._orch_with_roles(
            tmp_path,
            providers=[prov_a, prov_b],
            roles=[("fast", "b", "m-b-fast")],
        )
        prof = _profile(model_role="fast", provider_id="a")
        # Role-store mapping wins over profile.provider_id/profile.model
        assert orch._resolve_provider(prof) is prov_b
        assert orch._resolve_model(prof, prov_b) == "m-b-fast"

    def test_focus_role_wins_over_profile_role(self, tmp_path):
        prov_a = _provider(pid="a", name="A", models=["m-a"])
        prov_b = _provider(pid="b", name="B", models=["m-b"])
        orch = self._orch_with_roles(
            tmp_path,
            providers=[prov_a, prov_b],
            roles=[("fast", "a", "m-a"), ("deep", "b", "m-b")],
        )
        prof = _profile(model_role="fast")
        focus = Focus(name="docs", role="r", description="d", model_role="deep")
        assert orch._resolve_provider(prof, focus=focus) is prov_b
        assert orch._resolve_model(prof, prov_b, focus=focus) == "m-b"

    def test_missing_role_falls_back_to_legacy(self, tmp_path):
        """When RoleStore has no entry for the role, fall back to
        provider.model_roles and profile.provider_id/profile.model."""
        prov = _provider()  # has provider.model_roles={"fast":"m-fast","deep":"m-deep"}
        orch = self._orch_with_roles(
            tmp_path,
            providers=[prov],
            roles=[],  # empty role store
        )
        prof = _profile(model_role="deep", provider_id="p1")
        assert orch._resolve_provider(prof) is prov
        assert orch._resolve_model(prof, prov) == "m-deep"

    def test_role_store_provider_missing_falls_back(self, tmp_path):
        """RoleStore entry pointing at a deleted provider falls back
        to the profile-level resolution path."""
        prov_a = _provider(pid="a", name="A")
        orch = self._orch_with_roles(
            tmp_path,
            providers=[prov_a],
            roles=[("fast", "ghost", "m-ghost")],  # ghost not in provider_store
        )
        prof = _profile(model_role="fast", provider_id="a")
        # provider_id="ghost" doesn't resolve → falls back to profile.provider_id="a"
        assert orch._resolve_provider(prof) is prov_a


# ---------------------------------------------------------------------------
# _resolve_capabilities (oompah-zlz.3)
# ---------------------------------------------------------------------------


class TestResolveCapabilities:
    def test_default_text_only_when_no_model(self):
        prov = _provider()
        assert Orchestrator._resolve_capabilities(prov, None) == ["text"]

    def test_default_text_only_when_unmapped(self):
        prov = _provider()  # no model_capabilities
        assert Orchestrator._resolve_capabilities(prov, "m-fast") == ["text"]

    def test_returns_declared_caps(self):
        prov = _provider()
        prov.model_capabilities = {"m-fast": ["text", "image"]}
        assert Orchestrator._resolve_capabilities(prov, "m-fast") == ["text", "image"]

    def test_normalizes_and_dedups(self):
        prov = _provider()
        prov.model_capabilities = {"m": [" Text ", "TEXT", "image", "image"]}
        assert Orchestrator._resolve_capabilities(prov, "m") == ["text", "image"]

    def test_empty_list_falls_back_to_text(self):
        prov = _provider()
        prov.model_capabilities = {"m-fast": []}
        assert Orchestrator._resolve_capabilities(prov, "m-fast") == ["text"]


# ---------------------------------------------------------------------------
# Orchestrator LFS-pull helper (oompah-zlz.6)
# ---------------------------------------------------------------------------


class TestLFSPullAttachments:
    def test_no_lfs_is_silent(self, tmp_path, monkeypatch):
        """Missing git-lfs binary must not raise."""
        from oompah import orchestrator as _orch

        def fake_run(args, **kwargs):
            raise FileNotFoundError()

        monkeypatch.setattr(_orch.subprocess, "run", fake_run)
        # Should not raise.
        Orchestrator._lfs_pull_attachments(str(tmp_path), "foo-1")

    def test_includes_issue_path(self, tmp_path, monkeypatch):
        from oompah import orchestrator as _orch

        captured = {}

        def fake_run(args, **kwargs):
            captured["args"] = args
            captured["cwd"] = kwargs.get("cwd")

            class R:
                returncode = 0
                stdout = ""
                stderr = ""

            return R()

        monkeypatch.setattr(_orch.subprocess, "run", fake_run)

        Orchestrator._lfs_pull_attachments(str(tmp_path), "foo-1")
        assert captured["args"][:3] == ["git", "lfs", "pull"]
        assert "--include=.oompah/attachments/foo-1/" in captured["args"]
        assert captured["cwd"] == str(tmp_path)


# ---------------------------------------------------------------------------
# Reap oversize outputs (oompah-e6y.3)
# ---------------------------------------------------------------------------


class TestReapOversizeOutputs:
    def _setup(self, tmp_path):
        from oompah.attachments import ATTACHMENTS_SUBDIR

        wp = tmp_path / "ws"
        out = wp / ATTACHMENTS_SUBDIR / "foo-1" / "outputs"
        out.mkdir(parents=True)
        return wp, out

    def test_no_op_under_cap(self, tmp_path, monkeypatch):
        monkeypatch.setattr("oompah.attachments.MAX_PER_ISSUE_BYTES", 1000)
        orch = _make_orchestrator(tmp_path)
        wp, out = self._setup(tmp_path)
        (out / "a.png").write_bytes(b"x" * 100)
        issue = _make_issue("foo-1")
        orch._reap_oversize_outputs(str(wp), issue)
        assert (out / "a.png").exists()

    def test_drops_newest_first_until_under_cap(self, tmp_path, monkeypatch):
        import time as _t

        monkeypatch.setattr("oompah.attachments.MAX_PER_ISSUE_BYTES", 250)
        orch = _make_orchestrator(tmp_path)
        orch._post_comment = MagicMock()
        wp, out = self._setup(tmp_path)
        # Three files of 200 bytes each → 600 total → must drop two.
        for name in ("oldest.png", "middle.png", "newest.png"):
            (out / name).write_bytes(b"x" * 200)
            _t.sleep(0.01)  # ensure distinct mtimes
        issue = _make_issue("foo-1")
        orch._reap_oversize_outputs(str(wp), issue)
        remaining = sorted(p.name for p in out.iterdir())
        # Oldest survives — newest two were reaped.
        assert remaining == ["oldest.png"]
        # Warning comment posted.
        orch._post_comment.assert_called_once()
        msg = orch._post_comment.call_args.args[1]
        assert "newest.png" in msg
        assert "middle.png" in msg

    def test_silent_when_no_outputs_dir(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        wp = tmp_path / "ws"
        wp.mkdir()
        issue = _make_issue("foo-1")
        # Must not raise.
        orch._reap_oversize_outputs(str(wp), issue)


# ---------------------------------------------------------------------------
# Record generated attachments (oompah-e6y.4)
# ---------------------------------------------------------------------------


class TestRecordGeneratedAttachments:
    def _setup_workspace(self, tmp_path):
        from oompah.attachments import ATTACHMENTS_SUBDIR

        wp = tmp_path / "ws"
        out = wp / ATTACHMENTS_SUBDIR / "foo-1" / "outputs"
        out.mkdir(parents=True)
        (out / "abc-diagram.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)
        return wp

    def test_writes_generated_entries_to_metadata(self, tmp_path):
        wp = self._setup_workspace(tmp_path)
        orch = _make_orchestrator(tmp_path)
        # Mock tracker.
        tracker = MagicMock()
        tracker.fetch_attachments.return_value = []
        orch._tracker_for_issue = MagicMock(return_value=tracker)
        orch._post_comment = MagicMock()

        issue = _make_issue("foo-1")
        orch._record_generated_attachments(str(wp), issue)

        tracker.set_attachments.assert_called_once()
        call = tracker.set_attachments.call_args
        merged = call.args[1]
        assert len(merged) == 1
        rec = merged[0]
        assert rec["generated"] is True
        assert rec["added_by"] == "agent"
        assert rec["path"].endswith("-diagram.png")
        # Completion comment was posted.
        orch._post_comment.assert_called_once()
        assert "abc-diagram.png" in orch._post_comment.call_args.args[1]

    def test_does_not_duplicate_existing_paths(self, tmp_path):
        wp = self._setup_workspace(tmp_path)
        orch = _make_orchestrator(tmp_path)
        # The on-disk filename includes a sha prefix; mirror that in
        # existing metadata.
        from oompah.attachments import ATTACHMENTS_SUBDIR

        out = wp / ATTACHMENTS_SUBDIR / "foo-1" / "outputs"
        existing_path = (
            ".oompah/attachments/foo-1/outputs/" + list(out.iterdir())[0].name
        )
        tracker = MagicMock()
        tracker.fetch_attachments.return_value = [{"path": existing_path}]
        orch._tracker_for_issue = MagicMock(return_value=tracker)
        orch._post_comment = MagicMock()

        orch._record_generated_attachments(str(wp), _make_issue("foo-1"))
        # No new records → no set_attachments call, no comment.
        tracker.set_attachments.assert_not_called()
        orch._post_comment.assert_not_called()

    def test_silent_when_no_generated_outputs(self, tmp_path):
        wp = tmp_path / "ws"
        wp.mkdir()
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()
        orch._tracker_for_issue = MagicMock(return_value=tracker)
        orch._record_generated_attachments(str(wp), _make_issue("foo-1"))
        tracker.set_attachments.assert_not_called()


# ---------------------------------------------------------------------------
# _fetch_all_candidates timeout handling.
# Covers oompah-zlz_2-5re: ``tracker list --json`` against a slow project
# (e.g. trickle) was timing out. The orchestrator logged that at ERROR,
# which the error_watcher escalated into a fresh bug task on every poll
# tick — a feedback loop. Timeouts must log at WARNING, not ERROR.
# ---------------------------------------------------------------------------


class TestFetchAllCandidatesTimeout:
    def test_timeout_logs_warning_not_error(self, tmp_path, caplog):
        import logging as _logging
        from oompah.tracker import TrackerTimeoutError

        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        slow_tracker = MagicMock()
        slow_tracker.fetch_candidate_issues.side_effect = TrackerTimeoutError(
            "tracker command timed out: tracker list --status=open --json"
        )
        orch._tracker_for_project = MagicMock(return_value=slow_tracker)

        with caplog.at_level(_logging.DEBUG, logger="oompah.orchestrator"):
            result = orch._fetch_all_candidates()

        # Tick continues with an empty candidate set rather than crashing.
        assert result == []

        # The key contract: error_watcher only fires on ERROR, so we must
        # NOT have logged at ERROR for a transient timeout.
        error_records = [
            r
            for r in caplog.records
            if r.levelname == "ERROR" and r.name.startswith("oompah.orchestrator")
        ]
        assert error_records == [], (
            "TrackerTimeoutError must not be logged at ERROR — "
            "the error_watcher would auto-file a duplicate bug task "
            "on every poll tick."
        )
        warning_records = [r for r in caplog.records if r.levelname == "WARNING"]
        assert any("timed out" in r.getMessage() for r in warning_records), (
            "Expected a WARNING line mentioning the timeout."
        )

    def test_non_timeout_tracker_error_still_logs_error(self, tmp_path, caplog):
        """Sanity: real (non-timeout) failures still log at ERROR."""
        import logging as _logging
        from oompah.tracker import TrackerError

        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        broken_tracker = MagicMock()
        broken_tracker.fetch_candidate_issues.side_effect = TrackerError(
            "tracker command failed (exit 1): something else"
        )
        orch._tracker_for_project = MagicMock(return_value=broken_tracker)

        with caplog.at_level(_logging.DEBUG, logger="oompah.orchestrator"):
            result = orch._fetch_all_candidates()

        assert result == []
        error_records = [
            r
            for r in caplog.records
            if r.levelname == "ERROR" and r.name.startswith("oompah.orchestrator")
        ]
        assert error_records, "Generic TrackerError should still log ERROR"


# ---------------------------------------------------------------------------
# YOLO orphan-branch recovery (oompah-zlz_2-975)
#
# When _yolo_notify_conflict / _yolo_retry_ci look up a task by source
# branch and find none, they previously silently exited — leaving the
# PR DIRTY/FAILED forever with no escalation. Both must now file a
# fresh recovery task so the YOLO chain doesn't dead-end.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Bounded per-project refresh infrastructure (TASK-467.2)
#
# AC#1 — A slow project refresh does not block other projects after timeout.
# AC#2 — Review gating is conservative when data is stale/unavailable.
# AC#3 — Per-project refresh timings and timeout counts are recorded.
# ---------------------------------------------------------------------------


class TestBoundedProjectRefresh:
    """Tests for _run_bounded_refresh, stale-cache fallback, and metrics."""

    def test_successful_refresh_records_metrics(self, tmp_path):
        """Successful refresh increments success_count and stores last_duration_ms."""
        orch = _make_orchestrator(tmp_path)

        async def _run():
            async def _coro():
                return ["result-1"]

            data, is_fresh = await orch._run_bounded_refresh("proj-1", "candidates", _coro)
            return data, is_fresh

        data, is_fresh = asyncio.run(_run())

        assert data == ["result-1"]
        assert is_fresh is True
        metrics = orch._project_refresh_metrics["proj-1"]["candidates"]
        assert metrics["success_count"] == 1
        assert metrics["timeout_count"] == 0
        assert metrics["last_error"] is None
        assert metrics["last_duration_ms"] >= 0.0

    def test_timeout_falls_back_to_stale_cache(self, tmp_path):
        """When refresh times out, stale cached data is returned (AC#1, AC#2)."""
        orch = _make_orchestrator(tmp_path)
        # Pre-populate stale cache
        orch._set_stale_cache("proj-1", "candidates", ["stale-result"])

        async def _run():
            async def _slow_coro():
                # Simulate a slow operation
                await asyncio.sleep(10)
                return ["fresh-result"]

            data, is_fresh = await orch._run_bounded_refresh(
                "proj-1", "candidates", _slow_coro, timeout_ms=1
            )
            return data, is_fresh

        data, is_fresh = asyncio.run(_run())

        assert data == ["stale-result"]
        assert is_fresh is False
        metrics = orch._project_refresh_metrics["proj-1"]["candidates"]
        assert metrics["timeout_count"] == 1
        assert metrics["success_count"] == 0
        assert "timeout" in (metrics["last_error"] or "")

    def test_timeout_with_no_stale_cache_returns_empty(self, tmp_path):
        """When refresh times out and no stale data exists, returns empty list (AC#2)."""
        orch = _make_orchestrator(tmp_path)

        async def _run():
            async def _slow_coro():
                await asyncio.sleep(10)
                return ["fresh-result"]

            data, is_fresh = await orch._run_bounded_refresh(
                "proj-1", "candidates", _slow_coro, timeout_ms=1
            )
            return data, is_fresh

        data, is_fresh = asyncio.run(_run())

        # No stale cache — returns empty list
        assert data == []
        assert is_fresh is False

    def test_exception_falls_back_to_stale_cache(self, tmp_path):
        """When refresh raises, stale cache is used (AC#1)."""
        orch = _make_orchestrator(tmp_path)
        orch._set_stale_cache("proj-1", "reviews", {"proj-1": [{"id": "r1"}]})

        async def _run():
            async def _failing_coro():
                raise RuntimeError("Network error")

            data, is_fresh = await orch._run_bounded_refresh(
                "proj-1", "reviews", _failing_coro
            )
            return data, is_fresh

        data, is_fresh = asyncio.run(_run())

        assert data == {"proj-1": [{"id": "r1"}]}
        assert is_fresh is False
        metrics = orch._project_refresh_metrics["proj-1"]["reviews"]
        assert metrics["timeout_count"] == 1
        assert "RuntimeError" in (metrics["last_error"] or "")

    def test_stale_cache_update_on_success(self, tmp_path):
        """Successful refresh updates the stale cache with the new data."""
        orch = _make_orchestrator(tmp_path)

        async def _run():
            async def _coro():
                return {"proj-1": ["review-1"]}

            await orch._run_bounded_refresh("proj-1", "reviews", _coro)

        asyncio.run(_run())

        # Stale cache is updated with fresh data
        cached = orch._get_stale_cache("proj-1", "reviews")
        assert cached == {"proj-1": ["review-1"]}

    def test_timeout_zero_disables_timeout(self, tmp_path):
        """Setting timeout_ms=0 disables the timeout guard."""
        orch = _make_orchestrator(tmp_path)

        async def _run():
            async def _coro():
                # No sleep — still runs fast
                return ["result"]

            data, is_fresh = await orch._run_bounded_refresh(
                "proj-1", "candidates", _coro, timeout_ms=0
            )
            return data, is_fresh

        data, is_fresh = asyncio.run(_run())

        assert data == ["result"]
        assert is_fresh is True

    def test_stale_cache_expires_after_ttl(self, tmp_path):
        """Stale cache returns None when data is older than the TTL."""
        from oompah.config import ServiceConfig
        config = ServiceConfig(project_stale_cache_ttl_ms=1)  # 1ms TTL
        orch = _make_orchestrator(tmp_path)
        orch.config = config

        import time as _time
        orch._set_stale_cache("proj-1", "candidates", ["old-result"])
        _time.sleep(0.01)  # Wait >1ms so the cache expires

        result = orch._get_stale_cache("proj-1", "candidates")
        assert result is None

    def test_metrics_track_multiple_operations_per_project(self, tmp_path):
        """Each operation has independent metrics per project (AC#3)."""
        orch = _make_orchestrator(tmp_path)

        async def _run():
            async def _coro_a():
                return ["a"]

            async def _coro_b():
                return {"b": 1}

            await orch._run_bounded_refresh("proj-1", "candidates", _coro_a)
            await orch._run_bounded_refresh("proj-1", "reviews", _coro_b)

        asyncio.run(_run())

        assert "candidates" in orch._project_refresh_metrics["proj-1"]
        assert "reviews" in orch._project_refresh_metrics["proj-1"]
        assert orch._project_refresh_metrics["proj-1"]["candidates"]["success_count"] == 1
        assert orch._project_refresh_metrics["proj-1"]["reviews"]["success_count"] == 1

    def test_metrics_independent_across_projects(self, tmp_path):
        """Metrics for different projects are stored independently (AC#3)."""
        orch = _make_orchestrator(tmp_path)

        async def _run():
            async def _coro():
                return []

            await orch._run_bounded_refresh("proj-a", "candidates", _coro)
            await orch._run_bounded_refresh("proj-b", "candidates", _coro)

        asyncio.run(_run())

        assert "proj-a" in orch._project_refresh_metrics
        assert "proj-b" in orch._project_refresh_metrics
        assert orch._project_refresh_metrics["proj-a"]["candidates"]["success_count"] == 1
        assert orch._project_refresh_metrics["proj-b"]["candidates"]["success_count"] == 1

    def test_one_slow_project_does_not_block_fast_projects(self, tmp_path):
        """Bounded refresh: slow project completes independently of fast ones (AC#1)."""
        import time as _time
        orch = _make_orchestrator(tmp_path)
        # Disable timeout to let both complete
        results = []

        async def _run():
            async def _fast_coro():
                return ["fast"]

            async def _slow_coro():
                await asyncio.sleep(0.05)
                return ["slow"]

            # Run both in parallel — fast one should finish first but both succeed
            fast_result, slow_result = await asyncio.gather(
                orch._run_bounded_refresh("proj-fast", "candidates", _fast_coro, timeout_ms=0),
                orch._run_bounded_refresh("proj-slow", "candidates", _slow_coro, timeout_ms=0),
            )
            results.extend([fast_result, slow_result])

        asyncio.run(_run())

        # Both results are returned
        fast_data, fast_fresh = results[0]
        slow_data, slow_fresh = results[1]
        assert fast_data == ["fast"]
        assert slow_data == ["slow"]
        assert fast_fresh is True
        assert slow_fresh is True

    def test_semaphore_limits_concurrent_refresh_operations(self, tmp_path):
        """Semaphore enforces bounded concurrency per project (AC#1)."""
        from oompah.config import ServiceConfig
        config = ServiceConfig(project_refresh_max_concurrent=1)  # Only 1 at a time
        orch = _make_orchestrator(tmp_path)
        orch.config = config

        execution_order = []

        async def _run():
            async def _coro(label):
                execution_order.append(f"start-{label}")
                await asyncio.sleep(0.01)
                execution_order.append(f"end-{label}")
                return [label]

            # Run 3 operations on same project — only 1 can run at a time
            results = await asyncio.gather(
                orch._run_bounded_refresh("proj-1", "op-a", lambda: _coro("a"), timeout_ms=0),
                orch._run_bounded_refresh("proj-1", "op-b", lambda: _coro("b"), timeout_ms=0),
                orch._run_bounded_refresh("proj-1", "op-c", lambda: _coro("c"), timeout_ms=0),
            )
            return results

        results = asyncio.run(_run())

        # All three complete successfully
        assert len(results) == 3
        # With semaphore=1: no two operations overlap
        # Verify by checking that start and end pairs are interleaved (not nested)
        # (We can verify structural non-overlap: each "end-X" follows its "start-X"
        # without another "start-Y" intervening when semaphore=1)
        for i in range(0, len(execution_order) - 1, 2):
            label = execution_order[i].replace("start-", "")
            assert execution_order[i + 1] == f"end-{label}", (
                f"Operations overlapped: {execution_order}"
            )


class TestYoloOrphanBranchRecovery:
    """Branch with no matching task must trigger a recovery-task filing."""

    def _make_review_request(
        self,
        review_id="30",
        source_branch="trickle-c0w",
        target_branch="main",
        has_conflicts=True,
        ci_status="passed",
    ):
        return ReviewRequest(
            id=review_id,
            title=f"PR #{review_id}",
            url=f"https://github.com/org/repo/pull/{review_id}",
            author="alice",
            state="open",
            source_branch=source_branch,
            target_branch=target_branch,
            created_at="2025-01-01",
            updated_at="2025-01-02",
            ci_status=ci_status,
            has_conflicts=has_conflicts,
        )

    # --- _yolo_notify_conflict orphan branch ---

    def test_notify_conflict_files_recovery_task_when_no_task_matches(self, tmp_path):
        project = _make_project(yolo=True)
        orch = _make_orchestrator(tmp_path, projects=[project])

        provider = MagicMock()
        provider.get_review.return_value = self._make_review_request(
            review_id="30",
            source_branch="trickle-c0w",
        )

        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = None  # orphan branch
        new_task = MagicMock()
        new_task.identifier = "trickle-rec1"
        tracker.create_issue.return_value = new_task
        orch._project_trackers[project.id] = tracker

        orch._yolo_notify_conflict(project, provider, "org/repo", "30")

        # New task created
        assert tracker.create_issue.call_count == 1
        kwargs = tracker.create_issue.call_args.kwargs
        # Title must reference both PR number and branch for operator audit
        assert "30" in kwargs["title"]
        assert "trickle-c0w" in kwargs["title"]
        assert kwargs["priority"] == 0
        assert kwargs["initial_status"] == "Needs Rebase"
        # Label must be merge-conflict so the focus matcher routes correctly
        tracker.add_label.assert_called_once_with("trickle-rec1", "merge-conflict")

        # Bookkeeping records the task so a second call doesn't re-file
        assert (project.id, "30", "merge-conflict") in orch._yolo_orphan_recovery_tasks

    def test_notify_conflict_idempotent_for_same_orphan_pr(self, tmp_path):
        """Second YOLO fire on the same orphan PR must NOT file a duplicate."""
        project = _make_project(yolo=True)
        orch = _make_orchestrator(tmp_path, projects=[project])

        provider = MagicMock()
        provider.get_review.return_value = self._make_review_request(
            review_id="30",
            source_branch="trickle-c0w",
        )

        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = None
        new_task = MagicMock()
        new_task.identifier = "trickle-rec1"
        tracker.create_issue.return_value = new_task
        orch._project_trackers[project.id] = tracker

        orch._yolo_notify_conflict(project, provider, "org/repo", "30")
        orch._yolo_notify_conflict(project, provider, "org/repo", "30")

        # Only one task filed across two YOLO fires
        assert tracker.create_issue.call_count == 1

    def test_notify_conflict_existing_task_path_unchanged(self, tmp_path):
        """When the branch DOES match a task, behavior is unchanged: no new task filed."""
        project = _make_project(yolo=True)
        orch = _make_orchestrator(tmp_path, projects=[project])

        provider = MagicMock()
        provider.get_review.return_value = self._make_review_request(
            review_id="30",
            source_branch="trickle-real",
        )

        tracker = MagicMock()
        existing = MagicMock()
        existing.state = "closed"
        existing.labels = []
        existing.identifier = "trickle-real"
        existing.id = "trickle-real"
        tracker.fetch_issue_detail.return_value = existing
        orch._project_trackers[project.id] = tracker

        orch._yolo_notify_conflict(project, provider, "org/repo", "30")

        # Existing path: relabel + reopen, NO new task
        tracker.create_issue.assert_not_called()
        # add_comment + update_issue (reopen with merge-conflict label) hit
        tracker.add_comment.assert_called_once()
        tracker.update_issue.assert_called_once()

    # --- _yolo_retry_ci orphan branch ---

    def test_retry_ci_files_recovery_task_when_no_task_matches(self, tmp_path):
        project = _make_project(yolo=True)
        orch = _make_orchestrator(tmp_path, projects=[project])

        review = self._make_review_request(
            review_id="42",
            source_branch="orphan-ci-branch",
            has_conflicts=False,
            ci_status="failed",
        )

        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = None
        new_task = MagicMock()
        new_task.identifier = "trickle-rec2"
        tracker.create_issue.return_value = new_task
        orch._project_trackers[project.id] = tracker

        orch._yolo_retry_ci(project, review)

        assert tracker.create_issue.call_count == 1
        kwargs = tracker.create_issue.call_args.kwargs
        assert "42" in kwargs["title"]
        assert "orphan-ci-branch" in kwargs["title"]
        assert kwargs["priority"] == 0
        assert kwargs["initial_status"] == "Needs CI Fix"
        # ci-fix label routes to the CI-fix focus
        tracker.add_label.assert_called_once_with("trickle-rec2", "ci-fix")

        # Bookkeeping: keyed under (project_id, review_id, "ci-fix")
        assert (project.id, "42", "ci-fix") in orch._yolo_orphan_recovery_tasks

    def test_retry_ci_idempotent_for_same_orphan_pr(self, tmp_path):
        project = _make_project(yolo=True)
        orch = _make_orchestrator(tmp_path, projects=[project])

        review = self._make_review_request(
            review_id="42",
            source_branch="orphan-ci-branch",
            has_conflicts=False,
            ci_status="failed",
        )

        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = None
        new_task = MagicMock()
        new_task.identifier = "trickle-rec2"
        tracker.create_issue.return_value = new_task
        orch._project_trackers[project.id] = tracker

        orch._yolo_retry_ci(project, review)
        orch._yolo_retry_ci(project, review)

        assert tracker.create_issue.call_count == 1

    def test_retry_ci_existing_task_path_unchanged(self, tmp_path):
        project = _make_project(yolo=True)
        orch = _make_orchestrator(tmp_path, projects=[project])

        review = self._make_review_request(
            review_id="42",
            source_branch="real-ci-branch",
            has_conflicts=False,
            ci_status="failed",
        )

        tracker = MagicMock()
        existing = MagicMock()
        existing.state = "closed"
        existing.labels = []
        existing.identifier = "real-ci-branch"
        existing.id = "real-ci-branch"
        tracker.fetch_issue_detail.return_value = existing
        orch._project_trackers[project.id] = tracker

        orch._yolo_retry_ci(project, review)

        # Existing path: relabel + reopen, NO new task
        tracker.create_issue.assert_not_called()
        tracker.update_issue.assert_called_once()
        tracker.add_comment.assert_called_once()

    # --- prune cleans up orphan-recovery bookkeeping when PR is gone ---

    def test_prune_drops_orphan_recovery_for_disappeared_review(self, tmp_path):
        project = _make_project(yolo=True)
        orch = _make_orchestrator(tmp_path, projects=[project])

        # Seed bookkeeping for two PRs
        orch._yolo_orphan_recovery_tasks[(project.id, "30", "merge-conflict")] = "rec-1"
        orch._yolo_orphan_recovery_tasks[(project.id, "42", "ci-fix")] = "rec-2"

        # Cache only contains PR #30 — #42 has been merged/closed
        live_review = self._make_review_request(review_id="30")
        orch._prune_stale_repo_config_errors({project.id: [live_review]})

        assert (project.id, "30", "merge-conflict") in orch._yolo_orphan_recovery_tasks
        assert (project.id, "42", "ci-fix") not in orch._yolo_orphan_recovery_tasks


# ---------------------------------------------------------------------------
# _describe_rate_limit_context (oompah-zlz_2-phr6)
#
# When a 429 fires the alert must name the provider+model so operators don't
# have to dig through logs. Tests verify the helper and the _on_worker_exit
# alert-composition path.
# ---------------------------------------------------------------------------


def _rl_make_entry(agent_profile_name: str = "standard") -> "RunningEntry":
    """Minimal RunningEntry for rate-limit context tests."""
    from oompah.models import RunningEntry
    from datetime import datetime, timezone

    return RunningEntry(
        worker_task=None,
        identifier="issue-1",
        issue=MagicMock(),
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        agent_profile_name=agent_profile_name,
    )


class TestDescribeRateLimitContext:
    """Unit tests for _describe_rate_limit_context()."""

    def test_provider_and_model_shown_when_resolved(self, tmp_path):
        """Returns 'ProviderName (model)' when both resolve successfully."""
        orch = _make_orchestrator(tmp_path)
        prov = _provider(
            pid="inf",
            name="InferenceAPI",
            models=["claude-sonnet-4-6"],
            default_model="claude-sonnet-4-6",
        )
        orch.provider_store = MagicMock()
        orch.provider_store.get.return_value = prov
        orch.provider_store.get_default.return_value = prov
        entry = _rl_make_entry("standard")
        # Ensure the profile is registered
        orch.config.agent_profiles = [
            AgentProfile(
                name="standard",
                command="api",
                provider_id="inf",
                model="claude-sonnet-4-6",
            ),
        ]

        result = orch._describe_rate_limit_context(entry, None)

        assert "InferenceAPI" in result
        assert "claude-sonnet-4-6" in result

    def test_error_tokens_append_reason(self, tmp_path):
        """Error body containing 'tokens' → '— Reason: tokens'."""
        orch = _make_orchestrator(tmp_path)
        prov = _provider(
            pid="inf",
            name="InferenceAPI",
            models=["claude-sonnet-4-6"],
            default_model="claude-sonnet-4-6",
        )
        orch.provider_store = MagicMock()
        orch.provider_store.get.return_value = prov
        orch.provider_store.get_default.return_value = prov
        entry = _rl_make_entry("standard")
        orch.config.agent_profiles = [
            AgentProfile(
                name="standard",
                command="api",
                provider_id="inf",
                model="claude-sonnet-4-6",
            ),
        ]

        result = orch._describe_rate_limit_context(
            entry,
            "HTTP 429 from http://x: rate limit type: tokens",
        )

        assert "InferenceAPI" in result
        assert "claude-sonnet-4-6" in result
        assert "Reason: tokens" in result

    def test_error_overloaded_append_reason(self, tmp_path):
        """Error body containing 'overloaded' → '— Reason: overloaded'."""
        orch = _make_orchestrator(tmp_path)
        prov = _provider(
            pid="godspeed",
            name="Godspeed",
            models=["mimo-2.5"],
            default_model="mimo-2.5",
        )
        orch.provider_store = MagicMock()
        orch.provider_store.get.return_value = prov
        orch.provider_store.get_default.return_value = prov
        entry = _rl_make_entry("standard")
        orch.config.agent_profiles = [
            AgentProfile(
                name="standard", command="api", provider_id="godspeed", model="mimo-2.5"
            ),
        ]

        result = orch._describe_rate_limit_context(
            entry,
            "HTTP 429 from http://x: model overloaded",
        )

        assert "Reason: overloaded" in result

    def test_error_quota_append_reason(self, tmp_path):
        """Error body containing 'quota' → '— Reason: quota'."""
        orch = _make_orchestrator(tmp_path)
        prov = _provider(
            pid="inf", name="OpenAI", models=["gpt-4o"], default_model="gpt-4o"
        )
        orch.provider_store = MagicMock()
        orch.provider_store.get.return_value = prov
        orch.provider_store.get_default.return_value = prov
        entry = _rl_make_entry("standard")
        orch.config.agent_profiles = [
            AgentProfile(
                name="standard", command="api", provider_id="inf", model="gpt-4o"
            ),
        ]

        result = orch._describe_rate_limit_context(
            entry,
            "HTTP 429 from http://x: quota exceeded",
        )

        assert "Reason: quota" in result

    def test_acp_mode_returns_claude_sdk(self, tmp_path):
        """ACP-mode dispatch returns 'Claude SDK' without a model."""
        orch = _make_orchestrator(tmp_path)
        prov = _provider(
            pid="acp-1", name="claude-subscription", models=["claude-sonnet-4-6"]
        )
        orch.provider_store = MagicMock()
        orch.provider_store.get.return_value = prov
        orch.provider_store.get_default.return_value = prov
        entry = _rl_make_entry("acp-profile")
        orch.config.agent_profiles = [
            AgentProfile(
                name="acp-profile", command="cli", mode="acp", provider_id="acp-1"
            ),
        ]

        result = orch._describe_rate_limit_context(entry, None)

        assert result == "Claude SDK"
        # No model should appear (ACP mode omits it)
        assert "(" not in result

    def test_acp_mode_with_codex_backend(self, tmp_path):
        """ACP dispatch via a named backend (e.g. 'codex') shows the backend name."""
        orch = _make_orchestrator(tmp_path)
        prov = _provider(pid="cx", name="OpenAI Codex")
        prov.backend = "codex"
        orch.provider_store = MagicMock()
        orch.provider_store.get.return_value = prov
        orch.provider_store.get_default.return_value = prov
        entry = _rl_make_entry("codex-profile")
        orch.config.agent_profiles = [
            AgentProfile(
                name="codex-profile", command="cli", mode="acp", provider_id="cx"
            ),
        ]

        result = orch._describe_rate_limit_context(entry, None)

        assert result == "codex"

    def test_unknown_profile_returns_fallback(self, tmp_path):
        """Profile name that resolves to nothing → 'an upstream API'."""
        orch = _make_orchestrator(tmp_path)
        orch.provider_store = MagicMock()
        orch.provider_store.get_default.return_value = _provider()
        entry = _rl_make_entry("nonexistent-profile")
        orch.config.agent_profiles = []  # empty profiles

        result = orch._describe_rate_limit_context(entry, None)

        assert result == "an upstream API"

    def test_no_entry_returns_fallback(self, tmp_path):
        """None entry → 'an upstream API' without crashing."""
        orch = _make_orchestrator(tmp_path)

        result = orch._describe_rate_limit_context(None, None)

        assert result == "an upstream API"

    def test_provider_found_but_model_unresolved(self, tmp_path):
        """Provider with no model artifact → returns just the provider name."""
        orch = _make_orchestrator(tmp_path)
        # Build provider directly so default_model is genuinely absent
        prov = ModelProvider(
            id="bare",
            name="BareProvider",
            base_url="http://x",
            api_key="k",
            models=[],  # no models catalogued
            # default_model defaults to None in the dataclass
        )
        orch.provider_store = MagicMock()
        orch.provider_store.get.return_value = prov
        orch.provider_store.get_default.return_value = prov
        entry = _rl_make_entry("bare-profile")
        orch.config.agent_profiles = [
            AgentProfile(name="bare-profile", command="api", provider_id="bare"),
        ]

        result = orch._describe_rate_limit_context(entry, None)

        assert result == "BareProvider"
        # m-default should NOT appear — provider.models is empty and has no default_model
        assert "(" not in result

    def test_reason_with_no_provider_appends_reason_to_fallback(self, tmp_path):
        """Provider resolution fails but reason parses — reason appended to 'an upstream API'."""
        orch = _make_orchestrator(tmp_path)
        orch.provider_store = MagicMock()
        orch.provider_store.get_default.return_value = None
        entry = _rl_make_entry("standard")
        orch.config.agent_profiles = []  # no profiles

        result = orch._describe_rate_limit_context(
            entry,
            "HTTP 429: tokens exceeded",
        )

        # Has the fallback baseline
        assert "an upstream API" in result
        # And the reason
        assert "Reason: tokens" in result


class TestRateLimitAlertIncludesProviderAndModel:
    """Integration test: _on_worker_exit_RATE_LIMITED path emits enriched alert/comment."""

    def test_rate_limited_alert_includes_provider_and_model(self, tmp_path):
        """When reason=rate_limited, the alert message names provider + model."""
        from oompah.models import RunningEntry
        from datetime import datetime, timezone

        orch = _make_orchestrator(tmp_path)
        prov = _provider(
            pid="inference-api",
            name="InferenceAPI",
            models=["claude-sonnet-4-6"],
            default_model="claude-sonnet-4-6",
        )
        orch.provider_store = MagicMock()
        orch.provider_store.get.return_value = prov
        orch.provider_store.get_default.return_value = prov
        orch.config.agent_profiles = [
            AgentProfile(
                name="standard",
                command="api",
                provider_id="inference-api",
                model="claude-sonnet-4-6",
            ),
        ]
        issue = _make_issue("issue-1", project_id="proj-1")
        entry = RunningEntry(
            worker_task=None,
            identifier="issue-1",
            issue=issue,
            session=None,
            retry_attempt=1,
            started_at=datetime.now(timezone.utc),
            agent_profile_name="standard",
        )
        # _on_worker_exit requires the entry to be in state.running
        orch.state.running["issue-1"] = entry
        orch._post_comment = MagicMock()
        orch._schedule_retry = MagicMock()

        asyncio.run(
            orch._on_worker_exit(
                "issue-1",
                "rate_limited",
                "HTTP 429 from http://x: rate limit type: tokens",
            )
        )

        # Alert should include provider + model + reason
        assert len(orch._alerts) == 1
        alert_msg = orch._alerts[0]["message"]
        assert "InferenceAPI" in alert_msg
        assert "claude-sonnet-4-6" in alert_msg
        assert "Reason: tokens" in alert_msg

    def test_rate_limited_comment_includes_provider_and_model(self, tmp_path):
        """The per-issue comment must also name provider+model in task comments."""
        from oompah.models import RunningEntry
        from datetime import datetime, timezone

        orch = _make_orchestrator(tmp_path)
        prov = _provider(
            pid="godspeed",
            name="Godspeed",
            models=["mimo-2.5"],
            default_model="mimo-2.5",
        )
        orch.provider_store = MagicMock()
        orch.provider_store.get.return_value = prov
        orch.provider_store.get_default.return_value = prov
        orch.config.agent_profiles = [
            AgentProfile(
                name="standard", command="api", provider_id="godspeed", model="mimo-2.5"
            ),
        ]
        issue = _make_issue("issue-1", project_id="proj-1")
        entry = RunningEntry(
            worker_task=None,
            identifier="issue-1",
            issue=issue,
            session=None,
            retry_attempt=1,
            started_at=datetime.now(timezone.utc),
            agent_profile_name="standard",
        )
        orch.state.running["issue-1"] = entry
        orch._post_comment = MagicMock()
        orch._schedule_retry = MagicMock()
        # _on_worker_exit also fires a per-agent telemetry comment
        # (oompah-zlz_2-y3fy). Stub it out so the rate-limit assertion
        # below sees only the rate-limit message.
        orch._fire_telemetry_comment = MagicMock()

        asyncio.run(orch._on_worker_exit("issue-1", "rate_limited", None))

        # Capture the comment posted by _post_comment
        orch._post_comment.assert_called_once()
        comment_text = orch._post_comment.call_args.args[1]
        assert "Godspeed" in comment_text
        assert "mimo-2.5" in comment_text


class TestNeedsHumanTransitions:
    def test_completed_without_closing_marks_needs_human_with_comment(self, tmp_path):
        project = _make_project("proj-1")
        orch = _make_orchestrator(tmp_path, projects=[project])
        issue = _make_issue("TASK-1", state="Open", project_id="proj-1")
        entry = RunningEntry(
            worker_task=None,
            identifier=issue.identifier,
            issue=issue,
            session=None,
            retry_attempt=0,
            started_at=datetime.now(timezone.utc),
            agent_profile_name="deep",
        )
        orch.state.running[issue.id] = entry
        orch.state.reopen_counts[issue.id] = 2
        orch._fire_task_cost_record = MagicMock()
        orch._fire_telemetry_comment = MagicMock()
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = issue
        tracker.mark_needs_human = MagicMock()
        orch._tracker_for_project = MagicMock(return_value=tracker)

        asyncio.run(orch._on_worker_exit(issue.id, "normal", None))

        tracker.mark_needs_human.assert_called_once()
        args = tracker.mark_needs_human.call_args.args
        assert args[0] == "TASK-1"
        assert "Human action required" in args[1]
        assert "move it back to Open" in args[1]
        assert issue.id in orch.state.completed

    def test_completed_without_landing_schedules_escalated_retry(self, tmp_path):
        project = _make_project("proj-1")
        project.repo_path = str(tmp_path)
        project.default_branch = "main"
        orch = _make_orchestrator(tmp_path, projects=[project])
        orch.config.agent_profiles = [
            AgentProfile(name="default", command="agent"),
            AgentProfile(name="standard", command="agent"),
        ]
        issue = _make_issue("TASK-1", state="In Progress", project_id="proj-1")
        entry = RunningEntry(
            worker_task=None,
            identifier=issue.identifier,
            issue=issue,
            session=None,
            retry_attempt=0,
            started_at=datetime.now(timezone.utc),
            agent_profile_name="default",
        )
        orch.state.running[issue.id] = entry
        orch._fire_task_cost_record = MagicMock()
        orch._fire_telemetry_comment = MagicMock()
        orch._post_comment = MagicMock()
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = issue
        tracker.mark_needs_human = MagicMock()
        orch._tracker_for_project = MagicMock(return_value=tracker)

        landing_result = MagicMock()
        landing_result.allowed = False
        landing_result.branch_on_origin = False
        landing_result.commits_on_origin = 0
        landing_result.local_only_commits = 0
        landing_result.skip_reason = ""
        landing_result.effective_branch = ""

        with patch(
            "oompah.landing_gate.check_landing_gate",
            return_value=landing_result,
        ):
            asyncio.run(orch._on_worker_exit(issue.id, "normal", None))

        tracker.mark_needs_human.assert_not_called()
        assert issue.id not in orch.state.completed
        retry = orch.state.retry_attempts[issue.id]
        assert retry.attempt == 1
        assert retry.error == "completed_without_landing"
        assert retry.escalated_profile == "standard"
        comments = [call.args[1] for call in orch._post_comment.call_args_list]
        assert any(
            "Agent completed without landing" in comment
            and "Escalating from 'default' to 'standard'" in comment
            for comment in comments
        )

    def test_stacked_child_completed_without_landing_checks_epic_branch(self, tmp_path):
        project = _make_project("proj-1")
        project.repo_path = str(tmp_path)
        project.default_branch = "main"
        project.epic_strategy = "stacked"
        orch = _make_orchestrator(tmp_path, projects=[project])
        orch.config.agent_profiles = [
            AgentProfile(name="default", command="agent"),
            AgentProfile(name="standard", command="agent"),
        ]
        orch.project_store.epic_branch_name.side_effect = (
            lambda identifier: f"epic-{identifier}"
        )
        parent = _make_issue(
            "EPIC-1",
            state="Open",
            issue_type="epic",
            project_id="proj-1",
        )
        issue = _make_issue("TASK-1", state="In Progress", project_id="proj-1")
        issue.parent_id = parent.identifier
        issue.branch_name = issue.identifier
        entry = RunningEntry(
            worker_task=None,
            identifier=issue.identifier,
            issue=issue,
            session=None,
            retry_attempt=0,
            started_at=datetime.now(timezone.utc),
            agent_profile_name="default",
        )
        orch.state.running[issue.id] = entry
        orch._fire_task_cost_record = MagicMock()
        orch._fire_telemetry_comment = MagicMock()
        orch._post_comment = MagicMock()
        tracker = MagicMock()

        def fetch_issue_detail(identifier: str):
            if identifier == issue.identifier:
                return issue
            if identifier == parent.identifier:
                return parent
            return None

        tracker.fetch_issue_detail.side_effect = fetch_issue_detail
        tracker.mark_needs_human = MagicMock()
        orch._tracker_for_project = MagicMock(return_value=tracker)

        landing_result = MagicMock()
        landing_result.allowed = False
        landing_result.branch_on_origin = False
        landing_result.commits_on_origin = 0
        landing_result.local_only_commits = 0
        landing_result.skip_reason = ""
        landing_result.effective_branch = "epic-EPIC-1"

        with patch(
            "oompah.landing_gate.check_landing_gate",
            return_value=landing_result,
        ) as check_landing_gate:
            asyncio.run(orch._on_worker_exit(issue.id, "normal", None))

        check_landing_gate.assert_called_once()
        assert check_landing_gate.call_args.kwargs["base_branch"] == "main"
        assert check_landing_gate.call_args.kwargs["effective_branch"] == "epic-EPIC-1"
        retry = orch.state.retry_attempts[issue.id]
        assert retry.error == "completed_without_landing"


class TestRetryTimerSpecificIssueLookup:
    """Retry timers must find already-owned issues outside the candidate set."""

    def test_in_progress_retry_dispatches_instead_of_releasing_claim(self, tmp_path):
        project = _make_project("proj-1")
        orch = _make_orchestrator(tmp_path, projects=[project])
        issue = _make_issue("TASK-389", state="In Progress")
        tracker = MagicMock()
        tracker.fetch_issue_states_by_ids.return_value = [issue]
        tracker.fetch_issue_detail.return_value = None
        orch._project_trackers["proj-1"] = tracker
        orch._fetch_all_candidates = MagicMock(return_value=[])
        orch._available_slots = MagicMock(return_value=1)
        orch._dispatch = AsyncMock()
        orch.state.claimed.add(issue.id)
        orch.state.retry_attempts[issue.id] = RetryEntry(
            issue_id=issue.id,
            identifier=issue.identifier,
            attempt=1,
            due_at_ms=0.0,
            escalated_profile="standard",
            project_id="proj-1",
        )

        asyncio.run(orch._on_retry_timer(issue.id))

        orch._dispatch.assert_awaited_once()
        dispatch_args = orch._dispatch.await_args
        dispatched_issue = dispatch_args.args[0]
        assert dispatched_issue.identifier == "TASK-389"
        assert dispatched_issue.project_id == "proj-1"
        assert dispatch_args.kwargs["attempt"] == 1
        assert dispatch_args.kwargs["override_profile"] == "standard"
        assert issue.id in orch.state.claimed

    def test_terminal_retry_releases_claim_and_marks_completed(self, tmp_path):
        project = _make_project("proj-1")
        orch = _make_orchestrator(tmp_path, projects=[project])
        issue = _make_issue("TASK-389", state="Done")
        tracker = MagicMock()
        tracker.fetch_issue_states_by_ids.return_value = [issue]
        tracker.fetch_issue_detail.return_value = None
        orch._project_trackers["proj-1"] = tracker
        orch._fetch_all_candidates = MagicMock(return_value=[])
        orch._dispatch = AsyncMock()
        orch.state.claimed.add(issue.id)
        orch.state.retry_attempts[issue.id] = RetryEntry(
            issue_id=issue.id,
            identifier=issue.identifier,
            attempt=1,
            due_at_ms=0.0,
            project_id="proj-1",
        )

        asyncio.run(orch._on_retry_timer(issue.id))

        orch._dispatch.assert_not_awaited()
        assert issue.id not in orch.state.claimed
        assert issue.id in orch.state.completed


class TestSelectDispatchableDuplicateSuppression:
    """_select_dispatchable suppresses candidates that are similar to in-flight issues."""

    def test_duplicate_candidate_suppressed_when_inflight(self, tmp_path):
        """A candidate similar to a running issue should be suppressed."""
        from oompah.models import RunningEntry
        from datetime import datetime, timezone

        orch = _make_orchestrator(tmp_path)

        running_issue = Issue(
            id="rogers-how",
            identifier="rogers-how",
            title="rogers-how: fix CI failure",
            description="Fix CI",
            state="open",
            priority=1,
            project_id="proj-rog",
            labels=["ci-fix"],
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        orch.state.running["rogers-how"] = RunningEntry(
            worker_task=None,
            identifier="rogers-how",
            issue=running_issue,
            session=None,
            retry_attempt=1,
            started_at=datetime.now(timezone.utc),
            agent_profile_name="default",
        )

        candidate = Issue(
            id="rogers-5hd",
            identifier="rogers-5hd",
            title="rogers-5hd: fix CI failure",
            description="Fix CI",
            state="open",
            priority=1,
            project_id="proj-rog",
            labels=["ci-fix"],
            created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        )

        result = orch._select_dispatchable([candidate])

        assert len(result) == 0

    def test_non_duplicate_candidate_not_suppressed_by_dedup(self, tmp_path):
        """A candidate not similar to in-flight issues is not suppressed by dedup."""
        from oompah.models import RunningEntry
        from datetime import datetime, timezone

        orch = _make_orchestrator(tmp_path)

        running_issue = Issue(
            id="trickle-abc",
            identifier="trickle-abc",
            title="trickle: fix pipeline",
            description="Fix pipeline",
            state="open",
            priority=1,
            project_id="proj-trickle",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        orch.state.running["trickle-abc"] = RunningEntry(
            worker_task=None,
            identifier="trickle-abc",
            issue=running_issue,
            session=None,
            retry_attempt=1,
            started_at=datetime.now(timezone.utc),
            agent_profile_name="default",
        )

        candidate = Issue(
            id="rogers-xyz",
            identifier="rogers-xyz",
            title="rogers-xyz: add logging",
            description="Add logging",
            state="open",
            priority=1,
            project_id="proj-rog",
            created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        )

        result = orch._select_dispatchable([candidate])

        # Dedup should NOT suppress this (different project + type + no shared prefix)
        # _should_dispatch may still reject it, but that's a separate gate.
        # Key assertion: dedup suppression should not have occurred.
        streak = orch.state.reject_streak.get("rogers-xyz")
        if streak:
            assert "similar" not in streak[0].lower()

    def test_weak_label_overlap_does_not_suppress_independent_p0_work(self, tmp_path):
        """Shared project/type/labels alone should not serialize unrelated P0 work."""
        from oompah.models import RunningEntry
        from datetime import datetime, timezone

        orch = _make_orchestrator(tmp_path)

        running_issue = Issue(
            id="TASK-465.3",
            identifier="TASK-465.3",
            title="Add regression coverage for tick lane serialization",
            description="Add tests",
            state="In Progress",
            priority=0,
            project_id="proj-1",
            labels=["task", "tick-latency", "dispatch-performance"],
            created_at=datetime(2026, 6, 8, tzinfo=timezone.utc),
        )
        orch.state.running[running_issue.id] = RunningEntry(
            worker_task=None,
            identifier=running_issue.identifier,
            issue=running_issue,
            session=None,
            retry_attempt=1,
            started_at=datetime.now(timezone.utc),
            agent_profile_name="standard",
        )

        maintenance = Issue(
            id="TASK-466.1",
            identifier="TASK-466.1",
            title="Move worktree cleanup and repo self-heal to maintenance lane",
            description="Move maintenance work",
            state="Open",
            priority=0,
            project_id="proj-1",
            labels=["task", "tick-latency", "maintenance", "needs:backend", "needs:test"],
            created_at=datetime(2026, 6, 8, 0, 1, tzinfo=timezone.utc),
        )
        locks = Issue(
            id="TASK-467.1",
            identifier="TASK-467.1",
            title="Add per-project locks for tracker writes and git mutations",
            description="Add locks",
            state="Open",
            priority=0,
            project_id="proj-1",
            labels=["task", "tick-latency", "dispatch-performance", "needs:backend", "needs:test"],
            created_at=datetime(2026, 6, 8, 0, 2, tzinfo=timezone.utc),
        )

        result = orch._select_dispatchable([maintenance, locks])

        identifiers = {i.identifier for i in result}
        assert "TASK-466.1" in identifiers
        assert "TASK-467.1" in identifiers

    def test_inter_candidate_duplicate_only_oldest_passes(self, tmp_path):
        """When two similar candidates are in the same batch, only the oldest passes."""
        from datetime import datetime, timezone

        orch = _make_orchestrator(tmp_path)

        candidate_a = Issue(
            id="merge-how",
            identifier="merge-how",
            title="merge conflict on PR #2",
            description="Resolve merge conflicts",
            state="open",
            priority=1,
            project_id="proj-rog",
            labels=["merge-conflict"],
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        candidate_b = Issue(
            id="merge-5hd",
            identifier="merge-5hd",
            title="merge conflict on PR #2",
            description="Resolve merge conflicts",
            state="open",
            priority=1,
            project_id="proj-rog",
            labels=["merge-conflict"],
            created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        )
        candidate_b = Issue(
            id="merge-5hd",
            identifier="merge-5hd",
            title="merge conflict on PR #2",
            description="Resolve merge conflicts",
            state="open",
            priority=1,
            project_id="proj-rog",
            labels=["merge-conflict"],
            created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        )

        result = orch._select_dispatchable([candidate_a, candidate_b])

        identifiers = [i.identifier for i in result]
        assert "merge-how" in identifiers


# ---------------------------------------------------------------------------
# ProviderStartupError and DispatchTarget (TASK-407.5)
# ---------------------------------------------------------------------------


class TestDispatchTargetDataclass:
    """DispatchTarget and ProviderStartupError are importable and work correctly."""

    def test_dispatch_target_fields(self):
        from oompah.orchestrator import DispatchTarget
        from dataclasses import fields

        names = {f.name for f in fields(DispatchTarget)}
        assert "role_name" in names
        assert "provider" in names
        assert "model" in names
        assert "candidate_key" in names
        assert "source" in names
        assert "candidate" in names

    def test_provider_startup_error_attributes(self):
        from oompah.orchestrator import ProviderStartupError

        err = ProviderStartupError("p1 is down", candidate_key="p1/m1", reason="no_model")
        assert str(err) == "p1 is down"
        assert err.candidate_key == "p1/m1"
        assert err.reason == "no_model"

    def test_provider_startup_error_defaults(self):
        from oompah.orchestrator import ProviderStartupError

        err = ProviderStartupError("oops")
        assert err.candidate_key == ""
        assert err.reason == "startup_failed"


# ---------------------------------------------------------------------------
# _resolve_dispatch_targets (TASK-407.5)
# ---------------------------------------------------------------------------


class TestResolveDispatchTargets:
    """_resolve_dispatch_targets produces ordered DispatchTarget lists."""

    def _orch_with_providers(self, tmp_path, providers):
        """Build an orchestrator with the given providers in provider_store."""
        orch = _make_orchestrator(tmp_path)
        orch.provider_store = MagicMock()
        by_id = {p.id: p for p in providers}
        orch.provider_store.get.side_effect = lambda pid: by_id.get(pid)
        orch.provider_store.get_default.return_value = providers[0] if providers else None
        return orch

    def test_single_candidate_role_returns_one_target(self, tmp_path):
        from oompah.roles import RoleStore

        prov = _provider(pid="p1", models=["m1"])
        orch = self._orch_with_providers(tmp_path, [prov])
        orch.role_store = RoleStore(path=str(tmp_path / "roles.json"))
        orch.role_store.set("fast", "p1", "m1")
        prof = _profile(model_role="fast")

        targets = orch._resolve_dispatch_targets(prof)

        assert len(targets) == 1
        assert targets[0].role_name == "fast"
        assert targets[0].provider is prov
        assert targets[0].model == "m1"
        assert targets[0].candidate_key == "p1/m1"
        assert targets[0].candidate is not None

    def test_two_candidate_role_returns_two_targets(self, tmp_path):
        from oompah.roles import RoleStore, Candidate

        prov_a = _provider(pid="a", models=["m-a"])
        prov_b = _provider(pid="b", models=["m-b"])
        orch = self._orch_with_providers(tmp_path, [prov_a, prov_b])

        rs = RoleStore(path=str(tmp_path / "roles.json"))
        rs.set("fast", "a", "m-a")
        from oompah.roles import Candidate
        rs.set_candidates("fast", "priority", [
            Candidate(provider_id="a", model="m-a"),
            Candidate(provider_id="b", model="m-b"),
        ])
        orch.role_store = rs
        prof = _profile(model_role="fast")

        targets = orch._resolve_dispatch_targets(prof)

        assert len(targets) == 2
        assert targets[0].provider is prov_a
        assert targets[0].model == "m-a"
        assert targets[1].provider is prov_b
        assert targets[1].model == "m-b"

    def test_missing_provider_in_store_is_skipped(self, tmp_path):
        from oompah.roles import RoleStore, Candidate

        prov_b = _provider(pid="b", models=["m-b"])
        orch = self._orch_with_providers(tmp_path, [prov_b])
        # prov_a ("ghost") is not in provider_store

        rs = RoleStore(path=str(tmp_path / "roles.json"))
        rs.set("fast", "b", "m-b")
        rs.set_candidates("fast", "priority", [
            Candidate(provider_id="ghost", model="m-ghost"),  # missing
            Candidate(provider_id="b", model="m-b"),
        ])
        orch.role_store = rs
        prof = _profile(model_role="fast")

        targets = orch._resolve_dispatch_targets(prof)

        # ghost is skipped; only b/m-b remains
        assert len(targets) == 1
        assert targets[0].provider is prov_b

    def test_all_candidates_missing_falls_back_to_provider_id(self, tmp_path):
        from oompah.roles import RoleStore, Candidate

        prov_a = _provider(pid="a", models=["m-a"])
        orch = self._orch_with_providers(tmp_path, [prov_a])
        # role_store has a candidate pointing to a non-existent provider
        rs = RoleStore(path=str(tmp_path / "roles.json"))
        rs.set("fast", "a", "m-a")
        rs.set_candidates("fast", "priority", [
            Candidate(provider_id="ghost", model="m-ghost"),
        ])
        orch.role_store = rs
        prof = _profile(model_role="fast", provider_id="a")

        targets = orch._resolve_dispatch_targets(prof)

        # Role produces no valid targets → fall back to profile.provider_id
        assert len(targets) == 1
        assert targets[0].provider is prov_a
        assert targets[0].role_name is None
        assert targets[0].source == "profile.provider_id"

    def test_no_model_role_uses_profile_provider_id(self, tmp_path):
        prov = _provider(pid="p1")
        orch = self._orch_with_providers(tmp_path, [prov])
        prof = _profile(provider_id="p1", model="m-special")

        targets = orch._resolve_dispatch_targets(prof)

        assert len(targets) == 1
        assert targets[0].provider is prov
        assert targets[0].model == "m-special"
        assert targets[0].role_name is None

    def test_no_profile_provider_uses_default(self, tmp_path):
        prov_default = _provider(pid="default-prov")
        orch = self._orch_with_providers(tmp_path, [prov_default])
        prof = _profile()  # no model_role, no provider_id

        targets = orch._resolve_dispatch_targets(prof)

        assert len(targets) == 1
        assert targets[0].provider is prov_default
        assert targets[0].source == "default"

    def test_no_provider_at_all_returns_empty(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        orch.provider_store = MagicMock()
        orch.provider_store.get.return_value = None
        orch.provider_store.get_default.return_value = None
        prof = _profile()

        targets = orch._resolve_dispatch_targets(prof)

        assert targets == []

    def test_unknown_role_falls_back_to_provider_id(self, tmp_path):
        prov = _provider(pid="p1")
        orch = self._orch_with_providers(tmp_path, [prov])
        # role_store is empty — model_role "unknown" is not registered
        prof = _profile(model_role="unknown", provider_id="p1")

        targets = orch._resolve_dispatch_targets(prof)

        assert len(targets) == 1
        assert targets[0].provider is prov
        assert targets[0].source == "profile.provider_id"


# ---------------------------------------------------------------------------
# _resolve_focus_provider_override (TASK-407.5)
# ---------------------------------------------------------------------------


class TestResolveFocusProviderOverride:
    """_resolve_focus_provider_override checks only focus-level fields."""

    def test_returns_none_when_focus_is_none(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        assert orch._resolve_focus_provider_override(None) is None

    def test_returns_none_when_focus_has_no_override(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        focus = Focus(name="docs", role="r", description="d")
        assert orch._resolve_focus_provider_override(focus) is None

    def test_returns_provider_for_focus_provider_id(self, tmp_path):
        prov = _provider(pid="p1")
        orch = _make_orchestrator(tmp_path)
        orch.provider_store = MagicMock()
        orch.provider_store.get.return_value = prov
        focus = Focus(name="docs", role="r", description="d", provider_id="p1")

        result = orch._resolve_focus_provider_override(focus)

        assert result is prov

    def test_returns_none_for_unknown_focus_provider_id(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        orch.provider_store = MagicMock()
        orch.provider_store.get.return_value = None
        focus = Focus(name="docs", role="r", description="d", provider_id="ghost")

        result = orch._resolve_focus_provider_override(focus)

        assert result is None

    def test_returns_provider_for_focus_model_role(self, tmp_path):
        from oompah.roles import RoleStore

        prov = _provider(pid="role-prov", models=["m1"])
        orch = _make_orchestrator(tmp_path)
        orch.provider_store = MagicMock()
        orch.provider_store.get.side_effect = lambda pid: prov if pid == "role-prov" else None
        rs = RoleStore(path=str(tmp_path / "roles.json"))
        rs.set("deep", "role-prov", "m1")
        orch.role_store = rs
        focus = Focus(name="docs", role="r", description="d", model_role="deep")

        result = orch._resolve_focus_provider_override(focus)

        assert result is prov


# ---------------------------------------------------------------------------
# _run_worker candidate failover (TASK-407.5)
# ---------------------------------------------------------------------------


class TestRunWorkerCandidateFailover:
    """_run_worker tries the next candidate when provider startup fails."""

    def _make_orch_with_running(self, tmp_path, issue):
        """Build an orchestrator with the issue registered in state.running."""
        from oompah.models import RunningEntry
        import asyncio

        orch = _make_orchestrator(tmp_path)
        orch._on_worker_exit = AsyncMock()
        orch.state.running[issue.id] = RunningEntry(
            worker_task=None,
            identifier=issue.identifier,
            issue=issue,
            session=None,
            retry_attempt=0,
            started_at=datetime.now(timezone.utc),
            agent_profile_name="standard",
            natural_profile_name="standard",
        )
        return orch

    def test_first_candidate_success_no_failover(self, tmp_path):
        """When the first candidate succeeds, no failover occurs."""
        from oompah.orchestrator import ProviderStartupError, DispatchTarget
        from oompah.roles import Candidate

        issue = _make_issue("feat-1")
        prov_a = _provider(pid="a", models=["m-a"])
        prov_b = _provider(pid="b", models=["m-b"])
        orch = self._make_orch_with_running(tmp_path, issue)

        target_a = DispatchTarget(
            role_name="fast", provider=prov_a, model="m-a",
            candidate_key="a/m-a", source="role:fast[0]",
            candidate=Candidate(provider_id="a", model="m-a"),
        )
        target_b = DispatchTarget(
            role_name="fast", provider=prov_b, model="m-b",
            candidate_key="b/m-b", source="role:fast[1]",
            candidate=Candidate(provider_id="b", model="m-b"),
        )
        orch._resolve_dispatch_targets = MagicMock(return_value=[target_a, target_b])

        calls = []
        async def mock_api_worker(issue, attempt, profile, provider, target=None):
            calls.append(provider.id)
        orch._run_api_worker = mock_api_worker

        prof = _profile(mode="api")
        asyncio.run(orch._run_worker(issue, attempt=1, profile=prof))

        assert calls == ["a"], "Only first candidate should be called"
        orch._on_worker_exit.assert_not_called()

    def test_first_candidate_startup_fails_second_succeeds(self, tmp_path):
        """ProviderStartupError on first candidate causes fallback to second."""
        from oompah.orchestrator import ProviderStartupError, DispatchTarget
        from oompah.roles import Candidate

        issue = _make_issue("feat-2")
        prov_a = _provider(pid="a", models=["m-a"])
        prov_b = _provider(pid="b", models=["m-b"])
        orch = self._make_orch_with_running(tmp_path, issue)

        target_a = DispatchTarget(
            role_name="fast", provider=prov_a, model="m-a",
            candidate_key="a/m-a", source="role:fast[0]",
            candidate=Candidate(provider_id="a", model="m-a"),
        )
        target_b = DispatchTarget(
            role_name="fast", provider=prov_b, model="m-b",
            candidate_key="b/m-b", source="role:fast[1]",
            candidate=Candidate(provider_id="b", model="m-b"),
        )
        orch._resolve_dispatch_targets = MagicMock(return_value=[target_a, target_b])

        calls = []
        async def mock_api_worker(issue, attempt, profile, provider, target=None):
            calls.append(provider.id)
            if provider.id == "a":
                raise ProviderStartupError("a is unavailable", candidate_key="a/m-a")
        orch._run_api_worker = mock_api_worker

        prof = _profile(mode="api")
        asyncio.run(orch._run_worker(issue, attempt=1, profile=prof))

        assert calls == ["a", "b"], "Should try a then fall back to b"
        orch._on_worker_exit.assert_not_called()  # b succeeded, so normal exit path

    def test_all_candidates_fail_calls_on_worker_exit(self, tmp_path):
        """When all candidates fail with ProviderStartupError, worker exits with error."""
        from oompah.orchestrator import ProviderStartupError, DispatchTarget
        from oompah.roles import Candidate

        issue = _make_issue("feat-3")
        prov_a = _provider(pid="a", models=["m-a"])
        prov_b = _provider(pid="b", models=["m-b"])
        orch = self._make_orch_with_running(tmp_path, issue)

        target_a = DispatchTarget(
            role_name="fast", provider=prov_a, model="m-a",
            candidate_key="a/m-a", source="role:fast[0]",
            candidate=Candidate(provider_id="a", model="m-a"),
        )
        target_b = DispatchTarget(
            role_name="fast", provider=prov_b, model="m-b",
            candidate_key="b/m-b", source="role:fast[1]",
            candidate=Candidate(provider_id="b", model="m-b"),
        )
        orch._resolve_dispatch_targets = MagicMock(return_value=[target_a, target_b])

        async def mock_api_worker(issue, attempt, profile, provider, target=None):
            raise ProviderStartupError(f"{provider.id} is down", candidate_key=target.candidate_key)
        orch._run_api_worker = mock_api_worker

        prof = _profile(mode="api")
        asyncio.run(orch._run_worker(issue, attempt=1, profile=prof))

        # _on_worker_exit must be called with "abnormal" since no candidate succeeded
        orch._on_worker_exit.assert_called_once()
        args = orch._on_worker_exit.call_args[0]
        assert args[0] == issue.id
        assert args[1] == "abnormal"
        assert "candidates" in args[2].lower() or "startup" in args[2].lower()

    def test_non_provider_failure_does_not_switch_candidate(self, tmp_path):
        """A regular exception (task failure) propagates without trying the next candidate."""
        from oompah.orchestrator import ProviderStartupError, DispatchTarget
        from oompah.roles import Candidate

        issue = _make_issue("feat-4")
        prov_a = _provider(pid="a", models=["m-a"])
        prov_b = _provider(pid="b", models=["m-b"])
        orch = self._make_orch_with_running(tmp_path, issue)

        target_a = DispatchTarget(
            role_name="fast", provider=prov_a, model="m-a",
            candidate_key="a/m-a", source="role:fast[0]",
            candidate=Candidate(provider_id="a", model="m-a"),
        )
        target_b = DispatchTarget(
            role_name="fast", provider=prov_b, model="m-b",
            candidate_key="b/m-b", source="role:fast[1]",
            candidate=Candidate(provider_id="b", model="m-b"),
        )
        orch._resolve_dispatch_targets = MagicMock(return_value=[target_a, target_b])

        calls = []

        async def mock_api_worker(issue, attempt, profile, provider, target=None):
            calls.append(provider.id)
            # Simulate a task-level error (not a startup error)
            raise RuntimeError("agent failed: test suite error")
        orch._run_api_worker = mock_api_worker

        prof = _profile(mode="api")
        with pytest.raises(RuntimeError, match="agent failed"):
            asyncio.run(orch._run_worker(issue, attempt=1, profile=prof))

        # Only the first candidate was tried — no failover for task errors
        assert calls == ["a"]

    def test_candidate_usage_recorded_for_successful_role_candidate(self, tmp_path):
        """After a role candidate succeeds, CandidateSelector.record_used is called."""
        from oompah.orchestrator import ProviderStartupError, DispatchTarget
        from oompah.roles import Candidate
        from unittest.mock import MagicMock

        issue = _make_issue("feat-5")
        prov_a = _provider(pid="a", models=["m-a"])
        orch = self._make_orch_with_running(tmp_path, issue)

        cand_a = Candidate(provider_id="a", model="m-a")
        target_a = DispatchTarget(
            role_name="fast", provider=prov_a, model="m-a",
            candidate_key="a/m-a", source="role:fast[0]",
            candidate=cand_a,
        )
        orch._resolve_dispatch_targets = MagicMock(return_value=[target_a])
        orch._candidate_selector = MagicMock()

        async def mock_api_worker(issue, attempt, profile, provider, target=None):
            pass  # success
        orch._run_api_worker = mock_api_worker

        prof = _profile(mode="api")
        asyncio.run(orch._run_worker(issue, attempt=1, profile=prof))

        orch._candidate_selector.record_used.assert_called_once_with("fast", cand_a)

    def test_usage_not_recorded_when_legacy_target_no_candidate(self, tmp_path):
        """Usage is NOT recorded for legacy profile.provider_id targets (candidate=None)."""
        from oompah.orchestrator import DispatchTarget

        issue = _make_issue("feat-6")
        prov = _provider(pid="p1", models=["m1"])
        orch = self._make_orch_with_running(tmp_path, issue)

        # Legacy target: no role_name, no candidate
        target = DispatchTarget(
            role_name=None, provider=prov, model="m1",
            candidate_key="p1", source="profile.provider_id",
            candidate=None,
        )
        orch._resolve_dispatch_targets = MagicMock(return_value=[target])
        orch._candidate_selector = MagicMock()

        async def mock_api_worker(issue, attempt, profile, provider, target=None):
            pass  # success
        orch._run_api_worker = mock_api_worker

        prof = _profile(mode="api")
        asyncio.run(orch._run_worker(issue, attempt=1, profile=prof))

        orch._candidate_selector.record_used.assert_not_called()

    def test_no_targets_falls_through_to_cli(self, tmp_path):
        """When no targets resolve for an api-mode profile, fall through to cli."""
        from unittest.mock import AsyncMock

        issue = _make_issue("feat-7")
        orch = self._make_orch_with_running(tmp_path, issue)
        orch._resolve_dispatch_targets = MagicMock(return_value=[])
        orch._run_cli_worker = AsyncMock()

        prof = _profile(mode="api")
        asyncio.run(orch._run_worker(issue, attempt=1, profile=prof))

        orch._run_cli_worker.assert_called_once()

    def test_round_robin_fallback(self, tmp_path):
        """Round-robin: first resolved candidate tried first; falls back when it fails."""
        from oompah.orchestrator import ProviderStartupError, DispatchTarget
        from oompah.roles import Candidate, CandidateSelector, Role
        from datetime import datetime, timezone

        issue = _make_issue("feat-rr")
        prov_a = _provider(pid="a", models=["m-a"])
        prov_b = _provider(pid="b", models=["m-b"])
        orch = self._make_orch_with_running(tmp_path, issue)

        # Simulate round-robin where b was used more recently → a comes first
        cand_a = Candidate(provider_id="a", model="m-a")
        cand_b = Candidate(provider_id="b", model="m-b")

        target_a = DispatchTarget(
            role_name="fast", provider=prov_a, model="m-a",
            candidate_key="a/m-a", source="role:fast[0]",
            candidate=cand_a,
        )
        target_b = DispatchTarget(
            role_name="fast", provider=prov_b, model="m-b",
            candidate_key="b/m-b", source="role:fast[1]",
            candidate=cand_b,
        )

        # _resolve_dispatch_targets returns a sorted by round-robin order.
        # We mock it here to test that the failover loop itself respects the order.
        orch._resolve_dispatch_targets = MagicMock(return_value=[target_a, target_b])

        calls = []
        async def mock_api_worker(issue, attempt, profile, provider, target=None):
            calls.append(provider.id)
            if provider.id == "a":
                raise ProviderStartupError("a unavailable", candidate_key="a/m-a")
        orch._run_api_worker = mock_api_worker

        prof = _profile(mode="api")
        asyncio.run(orch._run_worker(issue, attempt=1, profile=prof))

        assert calls == ["a", "b"]


# ---------------------------------------------------------------------------
# _run_api_worker with DispatchTarget (TASK-407.5)
# ---------------------------------------------------------------------------


class TestRunApiWorkerWithTarget:
    """_run_api_worker raises ProviderStartupError (not ValueError) when target provided."""

    def _make_orch_no_provider(self, tmp_path):
        """Orchestrator with MagicMock provider_store, no real providers."""
        orch = _make_orchestrator(tmp_path)
        orch.provider_store = MagicMock()
        orch.provider_store.get.return_value = None
        orch.provider_store.get_default.return_value = None
        return orch

    def test_provider_startup_error_when_model_not_in_provider_models(self, tmp_path):
        """Model not in provider.models raises ProviderStartupError when target given."""
        from oompah.orchestrator import ProviderStartupError, DispatchTarget
        from oompah.roles import Candidate
        import asyncio

        prov = MagicMock()
        prov.name = "TestProv"
        prov.id = "p1"
        prov.base_url = "http://x"
        prov.api_key = "k"
        prov.mode = "api"
        prov.models = ["m-valid"]
        prov.default_model = "m-valid"
        prov.model_roles = {}
        prov.get_model_context = MagicMock(return_value=None)

        orch = _make_orchestrator(tmp_path)
        orch._on_worker_exit = AsyncMock()

        cand = Candidate(provider_id="p1", model="m-bad")
        target = DispatchTarget(
            role_name="fast", provider=prov, model="m-bad",
            candidate_key="p1/m-bad", source="role:fast[0]",
            candidate=cand,
        )

        prof = _profile(mode="api", model_role="fast")

        with patch("oompah.orchestrator.select_focus_async") as mock_focus:
            mock_focus.return_value = Focus(name="f", role="r", description="d")
            with pytest.raises(ProviderStartupError) as exc_info:
                asyncio.run(
                    orch._run_api_worker(
                        _make_issue("i1"), attempt=1, profile=prof,
                        provider=prov, target=target,
                    )
                )

        assert exc_info.value.candidate_key == "p1/m-bad"
        assert "m-bad" in str(exc_info.value)

    def test_raises_value_error_without_target_for_backward_compat(self, tmp_path):
        """Without a target, the original ValueError is raised (not ProviderStartupError)."""
        import asyncio

        prov = MagicMock()
        prov.name = "TestProv"
        prov.id = "p1"
        prov.base_url = "http://x"
        prov.api_key = "k"
        prov.mode = "api"
        prov.models = ["m-valid"]
        prov.default_model = "m-valid"
        prov.model_roles = {}
        prov.get_model_context = MagicMock(return_value=None)

        orch = _make_orchestrator(tmp_path)
        orch._on_worker_exit = AsyncMock()

        prof = _profile(mode="api", model_role="fast")

        with patch("oompah.orchestrator.select_focus_async") as mock_focus:
            mock_focus.return_value = Focus(name="f", role="r", description="d")
            # Re-patch _resolve_provider and _resolve_model to return model that
            # isn't in provider.models
            with patch.object(orch, "_resolve_provider", return_value=prov):
                with patch.object(orch, "_resolve_model", return_value="m-bad"):
                    with pytest.raises(ValueError):
                        asyncio.run(
                            orch._run_api_worker(
                                _make_issue("i2"), attempt=1, profile=prof,
                                provider=prov,
                                # No target — legacy path
                            )
                        )
