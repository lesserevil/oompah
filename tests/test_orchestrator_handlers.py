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
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oompah.config import ServiceConfig
from oompah.models import Issue
from oompah.orchestrator import Orchestrator
from oompah.scm import ReviewRequest


def _make_config() -> ServiceConfig:
    return ServiceConfig()


def _make_issue(identifier: str, state: str = "open", issue_type: str = "task",
                priority: int = 2, project_id: str | None = None,
                labels: list | None = None) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=f"Issue {identifier}",
        state=state,
        issue_type=issue_type,
        priority=priority,
        project_id=project_id,
        labels=labels or [],
    )


def _make_project(project_id: str = "proj-1", repo_url: str = "https://github.com/org/repo",
                  yolo: bool = False):
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
    all_projects = list(projects or []) + list(yolo_projects or [])
    project_store = MagicMock()
    project_store.list_all.return_value = all_projects
    project_store.get.side_effect = lambda pid: next(
        (p for p in all_projects if p.id == pid), None
    )
    return Orchestrator(
        config=_make_config(),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        state_path=str(tmp_path / "state.json"),
    )


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
        orch._fetch_all_reviews = MagicMock(return_value={"proj-1": [review]})
        orch._fetch_all_merged_branches = MagicMock(return_value=set())

        asyncio.run(orch._handle_review_check())

        assert "proj-1" in orch._reviews_cache
        assert orch._reviews_cache["proj-1"] == [review]

    def test_populates_merged_branches_cache(self, tmp_path):
        """After _handle_review_check(), _merged_branches is populated."""
        orch = _make_orchestrator(tmp_path)
        orch._fetch_all_reviews = MagicMock(return_value={})
        orch._fetch_all_merged_branches = MagicMock(return_value={"branch-a", "branch-b"})

        asyncio.run(orch._handle_review_check())

        assert orch._merged_branches == {"branch-a", "branch-b"}

    def test_derives_unmerged_review_branches(self, tmp_path):
        """_unmerged_review_branches is derived from reviews with source branches."""
        orch = _make_orchestrator(tmp_path)
        reviews = [
            _make_review("1", "feat-1"),
            _make_review("2", "feat-2"),
        ]
        orch._fetch_all_reviews = MagicMock(return_value={"proj-1": reviews})
        orch._fetch_all_merged_branches = MagicMock(return_value=set())

        asyncio.run(orch._handle_review_check())

        assert orch._unmerged_review_branches == {"feat-1", "feat-2"}

    def test_resets_reviews_cache_at_start(self, tmp_path):
        """_reviews_cache is reset (emptied) at the start of each check."""
        orch = _make_orchestrator(tmp_path)
        # Pre-populate with stale data
        orch._reviews_cache = {"stale-project": [MagicMock()]}

        orch._fetch_all_reviews = MagicMock(return_value={})
        orch._fetch_all_merged_branches = MagicMock(return_value=set())

        asyncio.run(orch._handle_review_check())

        # Stale project must be gone
        assert "stale-project" not in orch._reviews_cache

    def test_handles_reviews_with_no_source_branch(self, tmp_path):
        """Reviews without a source_branch are excluded from _unmerged_review_branches."""
        orch = _make_orchestrator(tmp_path)
        review = _make_review("1", source_branch="")
        review.source_branch = None  # explicitly no branch
        orch._fetch_all_reviews = MagicMock(return_value={"proj-1": [review]})
        orch._fetch_all_merged_branches = MagicMock(return_value=set())

        asyncio.run(orch._handle_review_check())

        assert orch._unmerged_review_branches == set()

    def test_fetches_reviews_and_merged_both_called(self, tmp_path):
        """Both _fetch_all_reviews and _fetch_all_merged_branches are called."""
        orch = _make_orchestrator(tmp_path)
        orch._fetch_all_reviews = MagicMock(return_value={})
        orch._fetch_all_merged_branches = MagicMock(return_value=set())

        asyncio.run(orch._handle_review_check())

        orch._fetch_all_reviews.assert_called_once()
        orch._fetch_all_merged_branches.assert_called_once()

    def test_empty_reviews_sets_empty_unmerged_branches(self, tmp_path):
        """When there are no reviews, _unmerged_review_branches is empty."""
        orch = _make_orchestrator(tmp_path)
        orch._fetch_all_reviews = MagicMock(return_value={"proj-1": []})
        orch._fetch_all_merged_branches = MagicMock(return_value=set())

        asyncio.run(orch._handle_review_check())

        assert orch._unmerged_review_branches == set()

    def test_no_projects_yields_empty_caches(self, tmp_path):
        """When no projects return reviews, all caches are empty."""
        orch = _make_orchestrator(tmp_path)
        orch._fetch_all_reviews = MagicMock(return_value={})
        orch._fetch_all_merged_branches = MagicMock(return_value=set())

        asyncio.run(orch._handle_review_check())

        assert orch._reviews_cache == {}
        assert orch._merged_branches == set()
        assert orch._unmerged_review_branches == set()


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
        orch._should_dispatch = MagicMock(return_value=False)  # normal dispatch skips epics
        orch._dispatch = AsyncMock()

        asyncio.run(orch._handle_dispatch_needed())

        orch._dispatch.assert_awaited_once_with(epic, attempt=None)

    def test_resets_orphaned_in_progress(self, tmp_path):
        """_reset_orphaned_in_progress is called with the fetched candidates."""
        orch = _make_orchestrator(tmp_path)
        candidates = [_make_issue("feat-1", state="in_progress")]
        orch._fetch_all_candidates = MagicMock(return_value=candidates)
        orch._pre_resolve_blockers = MagicMock()
        orch._reset_orphaned_in_progress = MagicMock()
        orch._plan_open_epics = MagicMock(return_value=[])

        asyncio.run(orch._handle_dispatch_needed())

        orch._reset_orphaned_in_progress.assert_called_once_with(candidates)

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


# ---------------------------------------------------------------------------
# _handle_yolo_review
# ---------------------------------------------------------------------------

class TestHandleYoloReview:
    """_handle_yolo_review() runs YOLO actions, auto-archive, and merged-labeling."""

    def test_calls_yolo_review_actions(self, tmp_path):
        """_yolo_review_actions_sync is invoked by _handle_yolo_review."""
        orch = _make_orchestrator(tmp_path)
        orch._yolo_review_actions_sync = MagicMock()
        orch._auto_archive = MagicMock()
        orch._label_merged_issues = MagicMock()

        asyncio.run(orch._handle_yolo_review())

        orch._yolo_review_actions_sync.assert_called_once()

    def test_calls_auto_archive(self, tmp_path):
        """_auto_archive is invoked by _handle_yolo_review."""
        orch = _make_orchestrator(tmp_path)
        orch._yolo_review_actions_sync = MagicMock()
        orch._auto_archive = MagicMock()
        orch._label_merged_issues = MagicMock()

        asyncio.run(orch._handle_yolo_review())

        orch._auto_archive.assert_called_once()

    def test_calls_label_merged_issues(self, tmp_path):
        """_label_merged_issues is invoked by _handle_yolo_review."""
        orch = _make_orchestrator(tmp_path)
        orch._yolo_review_actions_sync = MagicMock()
        orch._auto_archive = MagicMock()
        orch._label_merged_issues = MagicMock()

        asyncio.run(orch._handle_yolo_review())

        orch._label_merged_issues.assert_called_once()

    def test_returns_timing_tuple(self, tmp_path):
        """_handle_yolo_review returns a (yolo_ms, archive_ms, merged_ms) tuple."""
        orch = _make_orchestrator(tmp_path)
        orch._yolo_review_actions_sync = MagicMock()
        orch._auto_archive = MagicMock()
        orch._label_merged_issues = MagicMock()

        result = asyncio.run(orch._handle_yolo_review())

        assert isinstance(result, tuple)
        assert len(result) == 3
        yolo_ms, archive_ms, merged_ms = result
        assert isinstance(yolo_ms, float)
        assert isinstance(archive_ms, float)
        assert isinstance(merged_ms, float)
        assert yolo_ms >= 0
        assert archive_ms >= 0
        assert merged_ms >= 0

    def test_all_three_operations_run(self, tmp_path):
        """All three operations run (yolo, archive, merged-labels)."""
        orch = _make_orchestrator(tmp_path)
        call_order = []

        def yolo():
            call_order.append("yolo")

        def archive():
            call_order.append("archive")

        def merged():
            call_order.append("merged")

        orch._yolo_review_actions_sync = yolo
        orch._auto_archive = archive
        orch._label_merged_issues = merged

        asyncio.run(orch._handle_yolo_review())

        assert set(call_order) == {"yolo", "archive", "merged"}

    def test_timing_values_are_non_negative(self, tmp_path):
        """Timing values returned must always be >= 0."""
        orch = _make_orchestrator(tmp_path)
        orch._yolo_review_actions_sync = MagicMock()
        orch._auto_archive = MagicMock()
        orch._label_merged_issues = MagicMock()

        yolo_ms, archive_ms, merged_ms = asyncio.run(orch._handle_yolo_review())

        assert yolo_ms >= 0.0
        assert archive_ms >= 0.0
        assert merged_ms >= 0.0


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
            return (0.0, 0.0, 0.0)

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
            return (0.0, 0.0, 0.0)

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

        expected_order = ["reconcile", "review_check", "dispatch_needed", "yolo_review", "auto_update"]
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
            return (0.0, 0.0, 0.0)

        async def fake_auto_update():
            call_order.append("auto_update")

        orch._handle_reconcile = fake_reconcile
        orch._handle_review_check = fake_review_check
        orch._handle_dispatch_needed = fake_dispatch_needed
        orch._handle_yolo_review = fake_yolo_review
        orch._handle_auto_update = fake_auto_update
        orch._notify_observers = MagicMock()

        with patch("oompah.orchestrator.validate_dispatch_config",
                   return_value=["Agent command not configured"]):
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
        orch._handle_yolo_review = AsyncMock(return_value=(0.0, 0.0, 0.0))
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
        orch._handle_yolo_review = AsyncMock(return_value=(0.0, 0.0, 0.0))
        orch._handle_auto_update = AsyncMock()
        orch._notify_observers = MagicMock()

        with patch("oompah.orchestrator.validate_dispatch_config",
                   return_value=["config error"]):
            asyncio.run(orch._tick())

        orch._notify_observers.assert_called_once()


# ---------------------------------------------------------------------------
# Handler isolation: each handler is independently callable
# ---------------------------------------------------------------------------

class TestHandlerIndependence:
    """Each handler can be called independently without requiring a full tick."""

    def test_handle_review_check_standalone(self, tmp_path):
        """_handle_review_check can run without the rest of _tick."""
        orch = _make_orchestrator(tmp_path)
        orch._fetch_all_reviews = MagicMock(return_value={"proj-1": []})
        orch._fetch_all_merged_branches = MagicMock(return_value=set())

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
        orch._auto_archive = MagicMock()
        orch._label_merged_issues = MagicMock()

        result = asyncio.run(orch._handle_yolo_review())
        assert isinstance(result, tuple) and len(result) == 3

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
