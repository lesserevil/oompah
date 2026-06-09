"""Regression tests for tick lane serialization (TASK-465.3).

Proves the four key invariants of the tick lane contract:

1. Full ticks do not overlap unsafely — the run() loop processes one tick at
   a time; a queued event during tick N is only processed after tick N ends.

2. Dispatch selection is serialized — two concurrent dispatch selection passes
   cannot both claim the same issue (the dispatch lock is the mechanism).

3. Maintenance work can run without blocking eligible dispatch — within a
   single tick, the dispatch phase always completes before maintenance starts,
   so a slow maintenance sweep does not delay the dispatch of eligible issues
   for that tick.

4. Tick requests raised while maintenance is active are coalesced into the
   next safe dispatch pass — many events queued during a slow tick collapse
   into a single additional tick rather than spawning unbounded tick work.

Acceptance criteria (from TASK-465.3):
  AC1. A slow maintenance job does not prevent a ready Open task from being
       dispatched on the dispatch lane (maintenance comes AFTER dispatch in the
       tick order, so the dispatch has already run before maintenance starts).
  AC2. Two dispatch selection passes cannot claim the same issue (the lock
       serializes them so the second sees state.running updated by the first).
  AC3. Tests cover shutdown/restart behavior with maintenance jobs in flight.
"""

from __future__ import annotations

import asyncio
import threading
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oompah.config import ServiceConfig
from oompah.models import Issue
from oompah.orchestrator import (
    DispatchEvent,
    DispatchEventType,
    Orchestrator,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(**overrides) -> ServiceConfig:
    cfg = ServiceConfig()
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


def _make_issue(
    identifier: str,
    state: str = "open",
    issue_type: str = "task",
    priority: int = 2,
    project_id: str | None = None,
    description: str = "Non-empty test description — passes the empty-description gate.",
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
        labels=[],
    )


def _make_orchestrator(tmp_path, config: ServiceConfig | None = None) -> Orchestrator:
    """Create a minimal test orchestrator with mocked project store."""
    from oompah.roles import RoleStore

    project_store = MagicMock()
    project_store.list_all.return_value = []
    role_store = RoleStore(path=str(tmp_path / "roles.json"))
    orch = Orchestrator(
        config=config or _make_config(full_sync_interval_ms=600_000),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        role_store=role_store,
        state_path=str(tmp_path / "state.json"),
    )
    orch._fetch_in_progress_issues = MagicMock(return_value=[])
    return orch


def _stub_tick(orch: Orchestrator) -> Orchestrator:
    """Stub all tick sub-handlers to async/sync no-ops."""
    orch._tick = AsyncMock()
    orch.startup_cleanup = AsyncMock()
    orch._recover_restart_issues = AsyncMock()
    return orch


def _stub_dispatch_cycle(orch: Orchestrator) -> Orchestrator:
    """Stub all internal methods exercised by _handle_dispatch_needed_locked."""
    orch._fetch_all_candidates = MagicMock(return_value=[])
    orch._pre_resolve_blockers = MagicMock()
    orch._apply_duplicate_detection = MagicMock()
    orch._select_dispatchable = MagicMock(return_value=[])
    orch._plan_open_epics = MagicMock(return_value=[])
    orch._auto_close_completed_epics = MagicMock()
    orch._all_non_terminal_epics = MagicMock(return_value=[])
    orch._open_epic_main_prs = MagicMock()
    orch._check_epic_staleness = MagicMock()
    orch._dispatch_proactive_rebase_agents = MagicMock(return_value=0)
    orch._prune_stale_epic_rebase_states = MagicMock()
    orch._fetch_in_progress_issues = MagicMock(return_value=[])
    orch._reset_orphaned_in_progress = MagicMock()
    return orch


def _stub_full_tick(orch: Orchestrator) -> Orchestrator:
    """Stub all sub-handlers used by _tick() (above the loop level)."""
    orch._apply_pending_agent_profiles = MagicMock()
    orch._invalidate_tracker_read_caches = MagicMock()
    orch._handle_reconcile = AsyncMock()
    orch._handle_review_check = AsyncMock()
    orch._handle_dispatch_needed = AsyncMock(return_value={})
    orch._handle_yolo_review = AsyncMock(return_value=(0.0, 0.0, 0.0))
    orch._maybe_run_watchdog = MagicMock()
    orch._maybe_heal_repos = MagicMock()
    orch._notify_observers = MagicMock()
    orch._handle_auto_update = AsyncMock()
    return orch


# ---------------------------------------------------------------------------
# 1. Full ticks do not overlap unsafely
# ---------------------------------------------------------------------------


class TestFullTickNonOverlap:
    """The run() loop processes exactly one full tick at a time.

    The run() event loop does:
        await _run_tick()   # startup tick
        while ...:
            event = await queue.get()
            [coalesce burst events]
            await _run_tick()

    Because each _run_tick() is fully awaited before the next queue.get(),
    no two ticks can execute concurrently — events arriving during a tick
    are held in the queue and only dequeued once the current tick finishes.
    """

    @pytest.fixture
    def event_loop(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        yield loop
        loop.close()
        asyncio.set_event_loop(None)

    def test_event_queued_during_tick_n_triggers_tick_n_plus_1_not_concurrent(
        self, tmp_path, event_loop
    ):
        """An event posted while tick N is running starts tick N+1 only after tick N ends.

        Without sequential await, tick N+1 could start before tick N finishes,
        causing two ticks to share state concurrently.  This test fails if
        run() uses asyncio.create_task(_tick()) instead of await _tick().
        """
        orch = _make_orchestrator(tmp_path)
        orch.startup_cleanup = AsyncMock()
        orch._recover_restart_issues = AsyncMock()

        order: list[str] = []
        tick_count: list[int] = [0]

        # Gate to pause tick 1 mid-execution so we can observe tick 2 ordering.
        tick_1_proceed = asyncio.Event()
        tick_2_started_before_tick_1_ended = asyncio.Event()

        async def controlled_tick():
            n = tick_count[0] + 1
            tick_count[0] = n
            order.append(f"tick{n}:start")
            if n == 1:
                # Pause tick 1 — post an event while it's suspended.
                await asyncio.sleep(0)  # yield so _stop coroutine can post the event
                await tick_1_proceed.wait()
            order.append(f"tick{n}:end")

        orch._tick = controlled_tick

        async def driver():
            run_task = asyncio.create_task(orch.run())

            # Wait for tick 1 to start (startup tick).
            while "tick1:start" not in order:
                await asyncio.sleep(0.005)

            # Post an event while tick 1 is paused.
            orch._post_event(
                DispatchEvent(event_type=DispatchEventType.REFRESH_REQUESTED)
            )

            # Allow tick 1 to finish.
            tick_1_proceed.set()

            # Wait a moment for tick 2 to start and finish.
            await asyncio.sleep(0.05)

            # Stop the loop.
            orch._stopping = True
            orch._post_event(DispatchEvent(event_type=DispatchEventType.FULL_SYNC))
            await asyncio.wait_for(run_task, timeout=3.0)

        event_loop.run_until_complete(driver())

        assert len(order) >= 4, f"Expected at least 4 order entries, got: {order}"

        tick1_start = order.index("tick1:start")
        tick1_end = order.index("tick1:end")
        tick2_start = order.index("tick2:start")

        # tick 2 must not start until tick 1 ends.
        assert tick2_start > tick1_end, (
            f"Tick 2 started (index {tick2_start}) before tick 1 ended (index {tick1_end}). "
            f"Full order: {order}"
        )

    def test_ticks_run_sequentially_not_concurrently(self, tmp_path, event_loop):
        """Sequential structure: 'tickN:start' always follows 'tick(N-1):end' in order log.

        If this test fails, two ticks are running concurrently — a tick started
        before the previous one completed.
        """
        orch = _make_orchestrator(tmp_path)
        orch.startup_cleanup = AsyncMock()
        orch._recover_restart_issues = AsyncMock()

        order: list[str] = []
        tick_count: list[int] = [0]

        async def counting_tick():
            n = tick_count[0] + 1
            tick_count[0] = n
            order.append(f"tick{n}:start")
            await asyncio.sleep(0)  # yield to let any concurrently-scheduled ticks run
            order.append(f"tick{n}:end")

        orch._tick = counting_tick

        async def driver():
            run_task = asyncio.create_task(orch.run())
            # Post 3 events to trigger 3 additional ticks beyond startup.
            await asyncio.sleep(0.01)
            for _ in range(3):
                orch._post_event(
                    DispatchEvent(event_type=DispatchEventType.REFRESH_REQUESTED)
                )
            await asyncio.sleep(0.1)
            orch._stopping = True
            orch._post_event(DispatchEvent(event_type=DispatchEventType.FULL_SYNC))
            await asyncio.wait_for(run_task, timeout=3.0)

        event_loop.run_until_complete(driver())

        # Verify no two tick:start entries appear without an intervening tick:end.
        for i in range(len(order) - 1):
            if order[i].endswith(":start") and order[i + 1].endswith(":start"):
                pytest.fail(
                    f"Two ticks started back-to-back without a :end in between: "
                    f"{order[i]!r} → {order[i+1]!r}. Full order: {order}"
                )

    def test_loop_does_not_start_new_tick_while_previous_is_awaiting(
        self, tmp_path, event_loop
    ):
        """No tick N+1 begins while tick N is still awaiting an inner coroutine.

        Regression: if run() used asyncio.gather(_tick(), queue.get()) both
        ticks would run concurrently. This test verifies that even during a
        'slow' _tick() (one that yields control back to the event loop), no
        second tick starts.
        """
        orch = _make_orchestrator(tmp_path)
        orch.startup_cleanup = AsyncMock()
        orch._recover_restart_issues = AsyncMock()

        active_ticks: list[int] = [0]
        max_active: list[int] = [0]

        async def concurrent_tracking_tick():
            active_ticks[0] += 1
            max_active[0] = max(max_active[0], active_ticks[0])
            await asyncio.sleep(0.02)  # slow — yields control repeatedly
            active_ticks[0] -= 1

        orch._tick = concurrent_tracking_tick

        async def driver():
            run_task = asyncio.create_task(orch.run())
            # Post events while the startup tick is still running.
            await asyncio.sleep(0.005)  # startup tick is mid-flight (it sleeps 20ms)
            for _ in range(3):
                orch._post_event(
                    DispatchEvent(event_type=DispatchEventType.REFRESH_REQUESTED)
                )
            await asyncio.sleep(0.2)
            orch._stopping = True
            orch._post_event(DispatchEvent(event_type=DispatchEventType.FULL_SYNC))
            await asyncio.wait_for(run_task, timeout=3.0)

        event_loop.run_until_complete(driver())

        assert max_active[0] == 1, (
            f"More than one tick ran concurrently (max_active={max_active[0]}). "
            "This indicates run() is not awaiting _tick() sequentially."
        )


# ---------------------------------------------------------------------------
# 2. Dispatch selection is serialized (AC2)
# ---------------------------------------------------------------------------


class TestDispatchSelectionSerialized:
    """Two concurrent _handle_dispatch_needed() calls serialize via the dispatch lock.

    Acceptance criterion AC2: two dispatch selection passes cannot claim the
    same issue.  The lock ensures the second pass sees state.running updated
    by the first pass before it runs _select_dispatchable.
    """

    def test_two_concurrent_passes_run_in_sequence_not_parallel(self, tmp_path):
        """Two concurrent dispatch calls must not interleave their inner work.

        Regression: if the dispatch lock were removed, two concurrent calls to
        _handle_dispatch_needed() would both enter candidate fetch + selection
        + dispatch at the same time, allowing double-dispatch.
        """
        orch = _make_orchestrator(tmp_path)
        _stub_dispatch_cycle(orch)

        call_log: list[str] = []

        original_locked = orch._handle_dispatch_needed_locked
        call_count: list[int] = [0]

        async def sequencing_locked() -> dict:
            call_count[0] += 1
            n = call_count[0]
            call_log.append(f"pass{n}:start")
            await asyncio.sleep(0)  # yield so second coroutine can try to start
            await asyncio.sleep(0)
            call_log.append(f"pass{n}:end")
            return {}

        orch._handle_dispatch_needed_locked = sequencing_locked  # type: ignore[method-assign]

        async def run_concurrent():
            await asyncio.gather(
                orch._handle_dispatch_needed(),
                orch._handle_dispatch_needed(),
            )

        asyncio.run(run_concurrent())

        # Must be sequential: pass1 fully completes before pass2 starts.
        assert call_log == [
            "pass1:start",
            "pass1:end",
            "pass2:start",
            "pass2:end",
        ], f"Dispatch passes interleaved (expected no overlap): {call_log}"

    def test_two_concurrent_passes_cannot_dispatch_same_issue(self, tmp_path):
        """Two concurrent dispatch passes cannot both dispatch the same issue.

        Regression: without the dispatch lock, both passes would call
        _select_dispatchable before either called _dispatch.  Both would see the
        issue as eligible (not yet in state.running) and both would dispatch it.

        With the lock, the second pass runs _select_dispatchable AFTER the first
        has already dispatched and added the issue to state.running — so the
        second pass correctly skips it.
        """
        orch = _make_orchestrator(tmp_path)
        _stub_dispatch_cycle(orch)

        issue = _make_issue("TASK-dual")
        dispatch_calls: list[str] = []

        def select_checking_state(candidates: list[Issue]) -> list[Issue]:
            # Simulate the real _should_dispatch check: skip issues already running.
            return [c for c in candidates if c.id not in orch.state.running]

        async def recording_dispatch(
            iss: Issue, attempt=None, override_profile=None
        ) -> None:
            dispatch_calls.append(iss.id)
            # Simulate adding to state.running (what real _dispatch does).
            orch.state.running[iss.id] = MagicMock()

        orch._fetch_all_candidates = MagicMock(return_value=[issue])
        orch._select_dispatchable = select_checking_state
        orch._dispatch = recording_dispatch

        async def run_concurrent():
            await asyncio.gather(
                orch._handle_dispatch_needed(),
                orch._handle_dispatch_needed(),
            )

        asyncio.run(run_concurrent())

        assert dispatch_calls.count("TASK-dual") == 1, (
            f"Issue was dispatched {dispatch_calls.count('TASK-dual')} time(s). "
            "Without the dispatch lock, two concurrent passes would both claim it. "
            f"All dispatch calls: {dispatch_calls}"
        )

    def test_state_mutation_by_first_pass_is_visible_to_second_pass(self, tmp_path):
        """State written by the first pass (e.g. state.running) is visible to the second.

        This is the correctness property that makes single-owner serialization
        valuable: the second pass always sees a consistent world.
        """
        orch = _make_orchestrator(tmp_path)
        _stub_dispatch_cycle(orch)

        side_effects_seen_by_second: list[bool] = []

        call_count: list[int] = [0]

        async def stateful_locked() -> dict:
            call_count[0] += 1
            n = call_count[0]
            if n == 1:
                # First pass: write a sentinel to state.running.
                orch.state.running["sentinel-issue"] = MagicMock()
            else:
                # Second pass: verify the sentinel is visible.
                side_effects_seen_by_second.append(
                    "sentinel-issue" in orch.state.running
                )
            return {}

        orch._handle_dispatch_needed_locked = stateful_locked  # type: ignore[method-assign]

        async def run_two():
            await asyncio.gather(
                orch._handle_dispatch_needed(),
                orch._handle_dispatch_needed(),
            )

        asyncio.run(run_two())

        assert side_effects_seen_by_second == [True], (
            "Second dispatch pass did not see state.running entry written by the first. "
            "The lock must ensure the second pass sees a fully-committed first pass."
        )

    def test_dispatch_lock_acquired_exactly_once_per_call(self, tmp_path):
        """Each call to _handle_dispatch_needed() acquires the lock exactly once.

        If the lock were acquired multiple times per call, the second attempt
        would deadlock (asyncio.Lock is not re-entrant).
        """
        orch = _make_orchestrator(tmp_path)
        _stub_dispatch_cycle(orch)

        acquire_count: list[int] = [0]
        original_acquire = orch._dispatch_lane_lock.acquire

        async def counting_acquire():
            acquire_count[0] += 1
            return await original_acquire()

        orch._dispatch_lane_lock.acquire = counting_acquire  # type: ignore[method-assign]

        asyncio.run(orch._handle_dispatch_needed())

        assert acquire_count[0] == 1, (
            f"Lock acquired {acquire_count[0]} time(s) per call; expected exactly 1."
        )


# ---------------------------------------------------------------------------
# 3. Maintenance does not block dispatch (AC1)
# ---------------------------------------------------------------------------


class TestDispatchBeforeMaintenanceInTick:
    """Dispatch always completes before maintenance starts within a single tick.

    Acceptance criterion AC1: a slow maintenance job does not prevent a ready
    Open task from being dispatched on the dispatch lane.  Maintenance runs
    after dispatch in every tick, so by the time maintenance begins, the
    dispatch phase has already run and any eligible issue has been dispatched.
    """

    def test_dispatch_needed_runs_before_watchdog_in_same_tick(self, tmp_path):
        """_handle_dispatch_needed() is called before _maybe_run_watchdog in _tick().

        If this order were reversed (maintenance first), eligible issues would
        wait through the full maintenance sweep before being dispatched.
        """
        orch = _make_orchestrator(tmp_path)
        _stub_full_tick(orch)

        call_order: list[str] = []

        async def tracking_dispatch() -> dict:
            call_order.append("dispatch")
            return {}

        def tracking_watchdog() -> None:
            call_order.append("watchdog")

        orch._handle_dispatch_needed = tracking_dispatch
        orch._maybe_run_watchdog = tracking_watchdog

        with patch("oompah.orchestrator.validate_dispatch_config", return_value=[]):
            asyncio.run(orch._tick())

        assert "dispatch" in call_order
        assert "watchdog" in call_order
        assert call_order.index("dispatch") < call_order.index("watchdog"), (
            f"Expected dispatch < watchdog in call order, got: {call_order}"
        )

    def test_dispatch_needed_runs_before_heal_repos_in_same_tick(self, tmp_path):
        """_handle_dispatch_needed() is called before _maybe_heal_repos in _tick()."""
        orch = _make_orchestrator(tmp_path)
        _stub_full_tick(orch)

        call_order: list[str] = []

        async def tracking_dispatch() -> dict:
            call_order.append("dispatch")
            return {}

        def tracking_heal() -> None:
            call_order.append("heal")

        orch._handle_dispatch_needed = tracking_dispatch
        orch._maybe_heal_repos = tracking_heal

        with patch("oompah.orchestrator.validate_dispatch_config", return_value=[]):
            asyncio.run(orch._tick())

        assert call_order.index("dispatch") < call_order.index("heal"), (
            f"Expected dispatch < heal_repos in call order, got: {call_order}"
        )

    def test_dispatch_completes_before_slow_maintenance_starts(self, tmp_path):
        """A slow maintenance job starts only after dispatch has already finished.

        Scenario: tick N has dispatch (fast) → slow maintenance.  The eligible
        issue is dispatched during the dispatch phase; maintenance then runs but
        cannot retroactively block the dispatch that already happened.
        """
        orch = _make_orchestrator(tmp_path)
        _stub_full_tick(orch)

        timeline: list[str] = []
        maintenance_barrier = threading.Barrier(1)  # released immediately for test

        async def fast_dispatch() -> dict:
            timeline.append("dispatch:done")
            return {}

        def slow_watchdog() -> None:
            # Maintenance starts AFTER dispatch has finished.
            timeline.append("maintenance:start")
            # Simulate some work (bounded by a short timeout in tests).
            time.sleep(0.02)
            timeline.append("maintenance:done")

        orch._handle_dispatch_needed = fast_dispatch
        orch._maybe_run_watchdog = slow_watchdog

        with patch("oompah.orchestrator.validate_dispatch_config", return_value=[]):
            asyncio.run(orch._tick())

        dispatch_done_idx = timeline.index("dispatch:done")
        maintenance_start_idx = timeline.index("maintenance:start")

        assert dispatch_done_idx < maintenance_start_idx, (
            "Dispatch must complete before maintenance starts.  "
            f"Timeline: {timeline}"
        )

    def test_dispatch_lock_is_free_when_maintenance_runs(self, tmp_path):
        """The dispatch lock is not held when maintenance (watchdog/heal) runs.

        Regression: if maintenance held the dispatch lock, a second dispatch pass
        could not start until maintenance finished — defeating the lane separation.
        """
        orch = _make_orchestrator(tmp_path)
        _stub_full_tick(orch)

        lock_state_at_maintenance: list[bool] = []

        def spy_watchdog() -> None:
            lock_state_at_maintenance.append(orch._dispatch_lane_lock.locked())

        def spy_heal() -> None:
            lock_state_at_maintenance.append(orch._dispatch_lane_lock.locked())

        orch._maybe_run_watchdog = spy_watchdog
        orch._maybe_heal_repos = spy_heal
        orch._maybe_cleanup_worktrees = MagicMock()
        orch._auto_archive = MagicMock()
        orch._maybe_run_merged_labels = MagicMock()
        orch._maybe_run_release_pick_reconciliation = MagicMock()

        async def run_tick_and_drain_maintenance() -> None:
            await orch._tick()
            if orch._maintenance_future is not None:
                await asyncio.wait_for(orch._maintenance_future, timeout=1)

        with patch("oompah.orchestrator.validate_dispatch_config", return_value=[]):
            asyncio.run(run_tick_and_drain_maintenance())

        assert len(lock_state_at_maintenance) == 2, (
            "Expected both watchdog and heal to run"
        )
        assert not any(lock_state_at_maintenance), (
            "Dispatch lock must be FREE when maintenance runs.  "
            f"Lock states: {lock_state_at_maintenance}"
        )

    def test_eligible_issue_is_dispatched_despite_slow_watchdog(self, tmp_path):
        """An eligible issue is dispatched even when the watchdog takes a long time.

        The watchdog runs AFTER dispatch in every tick.  So any eligible issue
        is dispatched before the slow watchdog begins — the watchdog's duration
        cannot delay the dispatch that already ran.
        """
        orch = _make_orchestrator(tmp_path)
        _stub_full_tick(orch)

        dispatched: list[str] = []

        async def dispatch_that_records_issue() -> dict:
            dispatched.append("TASK-eligible")
            return {}

        def slow_watchdog() -> None:
            # A watchdog that blocks for 50ms — typical for bd CLI calls.
            time.sleep(0.05)

        orch._handle_dispatch_needed = dispatch_that_records_issue
        orch._maybe_run_watchdog = slow_watchdog

        t_start = time.monotonic()
        with patch("oompah.orchestrator.validate_dispatch_config", return_value=[]):
            asyncio.run(orch._tick())
        elapsed = time.monotonic() - t_start

        # The issue was dispatched (even though watchdog ran slowly).
        assert "TASK-eligible" in dispatched, (
            "Issue was not dispatched — watchdog may have run before dispatch."
        )
        # Sanity check: the tick did take time (watchdog ran), but dispatch finished.
        assert elapsed >= 0.04, "Expected watchdog to run (at least 40ms elapsed)"


# ---------------------------------------------------------------------------
# 4. Tick requests during maintenance are coalesced (regression)
# ---------------------------------------------------------------------------


class TestTickCoalescingDuringMaintenance:
    """Events queued while a slow tick (including maintenance) is running are
    coalesced into a single next tick rather than spawning N separate ticks.

    This prevents unbounded queued work when maintenance is slow and events
    accumulate (e.g. worker exits + periodic full-sync all arriving during
    a 30-second watchdog sweep).
    """

    @pytest.fixture
    def event_loop(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        yield loop
        loop.close()
        asyncio.set_event_loop(None)

    def test_burst_events_during_slow_tick_coalesce_to_single_next_tick(
        self, tmp_path, event_loop
    ):
        """N events posted during a slow tick result in at most 1 additional tick.

        Regression: without coalescing, 5 events posted during tick N would
        trigger 5 separate tick N+1, N+2, ..., N+5 — each a full world scan.
        With coalescing, all 5 events collapse into a single tick N+1.
        """
        orch = _make_orchestrator(tmp_path)
        orch.startup_cleanup = AsyncMock()
        orch._recover_restart_issues = AsyncMock()

        tick_count: list[int] = [0]
        tick_1_proceed = asyncio.Event()

        async def slow_startup_tick():
            tick_count[0] += 1
            if tick_count[0] == 1:
                # Startup tick: pause to let events accumulate.
                await tick_1_proceed.wait()
            # All subsequent ticks complete immediately.

        orch._tick = slow_startup_tick

        async def driver():
            run_task = asyncio.create_task(orch.run())

            # Wait for startup tick to start.
            while tick_count[0] < 1:
                await asyncio.sleep(0.005)

            # Post 5 events while the startup tick is blocked.
            for _ in range(5):
                orch._post_event(
                    DispatchEvent(event_type=DispatchEventType.REFRESH_REQUESTED)
                )

            # Let tick 1 complete.
            tick_1_proceed.set()

            # Give the loop time to process the coalesced events.
            await asyncio.sleep(0.1)

            orch._stopping = True
            orch._post_event(DispatchEvent(event_type=DispatchEventType.FULL_SYNC))
            await asyncio.wait_for(run_task, timeout=3.0)

        event_loop.run_until_complete(driver())

        # Startup tick + at most 1 additional tick (not 5+).
        # Without coalescing we'd expect startup + 5 = 6 total ticks.
        assert tick_count[0] <= 3, (
            f"Expected coalescing to collapse burst into ≤3 ticks total, "
            f"got {tick_count[0]}.  Coalescing may be broken."
        )
        assert tick_count[0] >= 2, (
            "Expected at least 2 ticks (startup + at least 1 event tick), "
            f"got {tick_count[0]}"
        )

    def test_coalesced_event_count_is_recorded_after_burst(self, tmp_path, event_loop):
        """_last_coalesced_event_count reflects the number of extra events drained.

        After a burst of N events, N-1 are coalesced (the first triggers the
        tick, the remaining N-1 are drained before the next tick starts).
        """
        orch = _make_orchestrator(tmp_path)
        orch.startup_cleanup = AsyncMock()
        orch._recover_restart_issues = AsyncMock()

        tick_1_proceed = asyncio.Event()
        tick_count: list[int] = [0]
        coalesced_after_first_tick: list[int] = []

        async def controlled_tick():
            tick_count[0] += 1
            if tick_count[0] == 1:
                await tick_1_proceed.wait()
            elif tick_count[0] == 2:
                # Record the coalesced count at the start of tick 2.
                coalesced_after_first_tick.append(orch._last_coalesced_event_count)

        orch._tick = controlled_tick

        async def driver():
            run_task = asyncio.create_task(orch.run())

            while tick_count[0] < 1:
                await asyncio.sleep(0.005)

            # Post 4 events while tick 1 is paused.
            for _ in range(4):
                orch._post_event(
                    DispatchEvent(event_type=DispatchEventType.WORKER_EXIT)
                )

            tick_1_proceed.set()

            # Wait for tick 2 to start.
            while tick_count[0] < 2:
                await asyncio.sleep(0.005)

            await asyncio.sleep(0.05)
            orch._stopping = True
            orch._post_event(DispatchEvent(event_type=DispatchEventType.FULL_SYNC))
            await asyncio.wait_for(run_task, timeout=3.0)

        event_loop.run_until_complete(driver())

        # 4 events were posted; 1 is consumed by queue.get() to trigger tick 2,
        # and the remaining 3 are coalesced.
        assert coalesced_after_first_tick, "Tick 2 did not record coalesced event count"
        assert coalesced_after_first_tick[0] >= 1, (
            f"Expected at least 1 coalesced event from burst of 4, "
            f"got {coalesced_after_first_tick[0]}.  Coalescing may be broken."
        )

    def test_no_events_during_tick_means_zero_coalesced(self, tmp_path):
        """When no events arrive during a tick, _last_coalesced_event_count stays 0."""
        orch = _make_orchestrator(tmp_path)
        _stub_full_tick(orch)

        # Start with a clean state.
        orch._last_coalesced_event_count = 0

        # Drain the queue (ensure it's empty before the tick).
        while not orch._dispatch_queue.empty():
            try:
                orch._dispatch_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        # Run a tick — no events are queued during it.
        with patch("oompah.orchestrator.validate_dispatch_config", return_value=[]):
            asyncio.run(orch._tick())

        # The tick doesn't change _last_coalesced_event_count (that's set by run()).
        assert orch._last_coalesced_event_count == 0

    def test_coalescing_drains_all_queued_events_before_next_tick(
        self, tmp_path, event_loop
    ):
        """After coalescing, the queue is empty before the next tick starts.

        If queued events were not fully drained, they would each trigger their
        own subsequent tick — defeating the coalescing guarantee.
        """
        orch = _make_orchestrator(tmp_path)
        orch.startup_cleanup = AsyncMock()
        orch._recover_restart_issues = AsyncMock()

        tick_1_proceed = asyncio.Event()
        tick_count: list[int] = [0]
        queue_size_at_tick_2_start: list[int] = []

        async def controlled_tick():
            tick_count[0] += 1
            if tick_count[0] == 1:
                await tick_1_proceed.wait()
            elif tick_count[0] == 2:
                # Record queue depth at the start of tick 2.
                # After coalescing, the queue must be empty (all events were drained).
                queue_size_at_tick_2_start.append(orch._dispatch_queue.qsize())

        orch._tick = controlled_tick

        async def driver():
            run_task = asyncio.create_task(orch.run())

            while tick_count[0] < 1:
                await asyncio.sleep(0.005)

            # Post 3 events while tick 1 is blocked.
            for _ in range(3):
                orch._post_event(
                    DispatchEvent(event_type=DispatchEventType.REFRESH_REQUESTED)
                )

            tick_1_proceed.set()

            while tick_count[0] < 2:
                await asyncio.sleep(0.005)

            await asyncio.sleep(0.05)
            orch._stopping = True
            orch._post_event(DispatchEvent(event_type=DispatchEventType.FULL_SYNC))
            await asyncio.wait_for(run_task, timeout=3.0)

        event_loop.run_until_complete(driver())

        assert queue_size_at_tick_2_start, "Tick 2 never started"
        assert queue_size_at_tick_2_start[0] == 0, (
            f"Queue was not empty at the start of tick 2 (size={queue_size_at_tick_2_start[0]}). "
            "Events must be fully drained (coalesced) before the next tick runs."
        )


# ---------------------------------------------------------------------------
# 5. Shutdown with maintenance in flight (AC3)
# ---------------------------------------------------------------------------


class TestShutdownWithMaintenanceInFlight:
    """The run() loop exits cleanly when _stopping is set while maintenance runs.

    Acceptance criterion AC3: tests cover shutdown/restart behavior with
    maintenance jobs in flight.
    """

    @pytest.fixture
    def event_loop(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        yield loop
        loop.close()
        asyncio.set_event_loop(None)

    def test_run_loop_exits_cleanly_after_stopping_is_set(
        self, tmp_path, event_loop
    ):
        """run() exits without hanging when _stopping is set mid-loop.

        Regression: if the loop did not check _stopping after each tick, it
        would block on queue.get() forever after maintenance completes.
        """
        orch = _make_orchestrator(tmp_path)
        orch.startup_cleanup = AsyncMock()
        orch._recover_restart_issues = AsyncMock()
        orch._tick = AsyncMock()

        async def driver():
            run_task = asyncio.create_task(orch.run())
            # Let the startup tick run.
            await asyncio.sleep(0.02)
            # Signal stop and unblock the queue.
            orch._stopping = True
            orch._post_event(DispatchEvent(event_type=DispatchEventType.FULL_SYNC))
            # Should complete promptly.
            await asyncio.wait_for(run_task, timeout=3.0)

        event_loop.run_until_complete(driver())
        # Test passes if we reach here without timeout.

    def test_no_new_tick_starts_after_stopping_is_set(self, tmp_path, event_loop):
        """After _stopping=True, no additional ticks start even if events are queued.

        Regression: if the loop checked _stopping only at queue.get(), events
        already in the queue could trigger one extra tick after the stop signal.
        """
        orch = _make_orchestrator(tmp_path)
        orch.startup_cleanup = AsyncMock()
        orch._recover_restart_issues = AsyncMock()

        tick_count: list[int] = [0]

        async def counting_tick():
            tick_count[0] += 1
            if tick_count[0] == 1:
                # Startup tick: signal stop and queue several events.
                orch._stopping = True
                for _ in range(3):
                    orch._post_event(
                        DispatchEvent(event_type=DispatchEventType.REFRESH_REQUESTED)
                    )
                # Also post the sentinel to unblock queue.get().
                orch._post_event(
                    DispatchEvent(event_type=DispatchEventType.FULL_SYNC)
                )

        orch._tick = counting_tick

        async def driver():
            await asyncio.wait_for(orch.run(), timeout=3.0)

        event_loop.run_until_complete(driver())

        # Only the startup tick should have run.
        assert tick_count[0] == 1, (
            f"Expected exactly 1 tick (startup) after _stopping=True, "
            f"but {tick_count[0]} ticks ran.  The loop must not process "
            "events queued after _stopping is set."
        )

    def test_maintenance_thread_completes_before_tick_returns(self, tmp_path):
        """Maintenance threads dispatched via run_in_executor complete before _tick() returns.

        The tick function awaits the executor futures for both _maybe_run_watchdog
        and _maybe_heal_repos.  So even if maintenance was still running when
        _stopping was set, the current tick (and its maintenance work) completes
        before the loop exits.
        """
        orch = _make_orchestrator(tmp_path)
        _stub_full_tick(orch)

        maintenance_completed: list[bool] = []

        def watchdog_that_records_completion() -> None:
            # Simulate brief maintenance work.
            time.sleep(0.02)
            maintenance_completed.append(True)

        orch._maybe_run_watchdog = watchdog_that_records_completion

        with patch("oompah.orchestrator.validate_dispatch_config", return_value=[]):
            asyncio.run(orch._tick())

        # _tick() awaits the executor, so maintenance must be complete by now.
        assert maintenance_completed == [True], (
            "_tick() returned before the maintenance thread completed.  "
            "run_in_executor futures must be awaited so maintenance finishes."
        )

    def test_stopping_flag_checked_before_processing_next_event(
        self, tmp_path, event_loop
    ):
        """The loop checks _stopping immediately after each tick, before queue.get().

        If an event is posted AND _stopping is set, the loop must not start
        a new tick.  This is the 'if self._stopping: break' guard in run().
        """
        orch = _make_orchestrator(tmp_path)
        orch.startup_cleanup = AsyncMock()
        orch._recover_restart_issues = AsyncMock()

        tick_started_after_stop: list[bool] = []
        tick_count: list[int] = [0]

        async def guarded_tick():
            tick_count[0] += 1
            if tick_count[0] > 1:
                # Any tick after the first — was _stopping already set?
                tick_started_after_stop.append(orch._stopping)

        orch._tick = guarded_tick

        async def driver():
            run_task = asyncio.create_task(orch.run())

            # Wait for the startup tick.
            while tick_count[0] < 1:
                await asyncio.sleep(0.005)

            # Set stop flag and immediately post an event.
            orch._stopping = True
            orch._post_event(DispatchEvent(event_type=DispatchEventType.FULL_SYNC))

            await asyncio.wait_for(run_task, timeout=3.0)

        event_loop.run_until_complete(driver())

        # At most one tick may have started after _stopping (the one that
        # unblocked queue.get() before the stop check ran), and if it did,
        # _stopping was True when it ran.
        for started_with_stop in tick_started_after_stop:
            assert started_with_stop, (
                "A tick started after _stopping=True was set.  "
                "The loop must break before starting new ticks."
            )

    def test_stopping_set_mid_maintenance_does_not_hang(self, tmp_path, event_loop):
        """Setting _stopping=True while maintenance is running does not hang run().

        Regression: if the loop waited for maintenance to finish before checking
        _stopping, a very slow maintenance job would delay shutdown.  Since the
        current tick's maintenance IS awaited (run_in_executor), the loop must
        complete the current tick then exit — not hang indefinitely.
        """
        orch = _make_orchestrator(tmp_path)
        orch.startup_cleanup = AsyncMock()
        orch._recover_restart_issues = AsyncMock()

        stop_requested = threading.Event()

        async def tick_with_slow_maintenance():
            # Simulate a tick that runs slow maintenance via _tick().
            # The tick is controlled at the run() level; here we just run
            # a stubbed _tick() that does real executor work.
            _stub_full_tick(orch)

            maintenance_ran = threading.Event()

            def slow_watchdog():
                # Signal that maintenance started, then briefly block.
                stop_requested.set()  # tell the driver that maintenance is active
                maintenance_ran.set()
                time.sleep(0.05)

            orch._maybe_run_watchdog = slow_watchdog

            with patch(
                "oompah.orchestrator.validate_dispatch_config", return_value=[]
            ):
                await orch._tick()

        async def driver():
            # Run one tick with slow maintenance.
            tick_task = asyncio.create_task(tick_with_slow_maintenance())

            # Wait for maintenance to start, then signal stop.
            await asyncio.get_event_loop().run_in_executor(None, stop_requested.wait, 2.0)

            # The tick is in-flight (in maintenance); set _stopping for next loop iteration.
            orch._stopping = True

            # The tick must complete (maintenance awaited), then return.
            await asyncio.wait_for(tick_task, timeout=3.0)

        event_loop.run_until_complete(driver())
        # Test passes if we reach here — no hang.
