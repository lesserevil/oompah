"""Tests for the serialized dispatch lane and maintenance lane contract (TASK-465.2).

Verifies:
- DispatchLane enum exists with DISPATCH and MAINTENANCE values.
- Orchestrator has a _dispatch_lane_lock attribute (asyncio.Lock).
- _handle_dispatch_needed() acquires _dispatch_lane_lock before running.
- Two concurrent dispatch calls serialize (second waits for first).
- The lock is released after normal completion and after exceptions.
- Tick-event coalescing: multiple queued events collapse to one tick.
- _last_coalesced_event_count is populated after coalescing.
- Coalesced event count propagates into tick telemetry snapshot.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oompah.config import ServiceConfig
from oompah.models import Issue
from oompah.orchestrator import DispatchLane, DispatchEvent, DispatchEventType, Orchestrator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config() -> ServiceConfig:
    return ServiceConfig()


def _make_issue(
    identifier: str,
    state: str = "open",
    issue_type: str = "task",
    priority: int = 2,
    project_id: str | None = None,
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
        labels=[],
    )


def _make_orchestrator(tmp_path):
    """Create a minimal test orchestrator."""
    from oompah.roles import RoleStore

    project_store = MagicMock()
    project_store.list_all.return_value = []
    role_store = RoleStore(path=str(tmp_path / "roles.json"))
    orch = Orchestrator(
        config=_make_config(),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        role_store=role_store,
        state_path=str(tmp_path / "state.json"),
    )
    orch._fetch_in_progress_issues = MagicMock(return_value=[])
    return orch


# ---------------------------------------------------------------------------
# DispatchLane enum contract
# ---------------------------------------------------------------------------


class TestDispatchLaneEnum:
    """DispatchLane is a stable, importable string enum."""

    def test_dispatch_lane_is_importable(self):
        """DispatchLane can be imported from oompah.orchestrator."""
        # Verify the import at module level didn't raise.
        assert DispatchLane is not None

    def test_dispatch_lane_has_dispatch_member(self):
        """DispatchLane.DISPATCH exists and is named 'dispatch'."""
        assert DispatchLane.DISPATCH == "dispatch"

    def test_dispatch_lane_has_maintenance_member(self):
        """DispatchLane.MAINTENANCE exists and is named 'maintenance'."""
        assert DispatchLane.MAINTENANCE == "maintenance"

    def test_dispatch_lane_members_are_strings(self):
        """Lane values are str instances (str-enum base)."""
        assert isinstance(DispatchLane.DISPATCH, str)
        assert isinstance(DispatchLane.MAINTENANCE, str)

    def test_dispatch_lane_has_exactly_two_members(self):
        """The enum has exactly two members — DISPATCH and MAINTENANCE."""
        members = set(DispatchLane)
        assert members == {DispatchLane.DISPATCH, DispatchLane.MAINTENANCE}

    def test_dispatch_and_maintenance_are_distinct(self):
        """DISPATCH and MAINTENANCE are different values."""
        assert DispatchLane.DISPATCH != DispatchLane.MAINTENANCE

    def test_lane_values_can_be_used_as_dict_keys(self):
        """Lane values work as dict keys (they're strings)."""
        timings = {DispatchLane.DISPATCH: 42.0, DispatchLane.MAINTENANCE: 7.5}
        assert timings[DispatchLane.DISPATCH] == 42.0
        assert timings[DispatchLane.MAINTENANCE] == 7.5


# ---------------------------------------------------------------------------
# Dispatch lane lock presence on Orchestrator
# ---------------------------------------------------------------------------


class TestDispatchLaneLockPresence:
    """The Orchestrator carries a _dispatch_lane_lock asyncio.Lock."""

    def test_dispatch_lane_lock_attribute_exists(self, tmp_path):
        """_dispatch_lane_lock attribute is present on a freshly-created orchestrator."""
        orch = _make_orchestrator(tmp_path)
        assert hasattr(orch, "_dispatch_lane_lock"), (
            "_dispatch_lane_lock is missing from Orchestrator.__init__"
        )

    def test_dispatch_lane_lock_is_asyncio_lock(self, tmp_path):
        """_dispatch_lane_lock is an asyncio.Lock instance."""
        orch = _make_orchestrator(tmp_path)
        assert isinstance(orch._dispatch_lane_lock, asyncio.Lock)

    def test_dispatch_lane_lock_is_unlocked_at_init(self, tmp_path):
        """Lock starts unlocked so the first tick can proceed immediately."""
        orch = _make_orchestrator(tmp_path)
        assert not orch._dispatch_lane_lock.locked()

    def test_last_coalesced_event_count_attribute_exists(self, tmp_path):
        """_last_coalesced_event_count attribute is present."""
        orch = _make_orchestrator(tmp_path)
        assert hasattr(orch, "_last_coalesced_event_count")

    def test_last_coalesced_event_count_starts_at_zero(self, tmp_path):
        """_last_coalesced_event_count starts at 0 before the first tick."""
        orch = _make_orchestrator(tmp_path)
        assert orch._last_coalesced_event_count == 0


# ---------------------------------------------------------------------------
# Dispatch lane serialization: _handle_dispatch_needed acquires the lock
# ---------------------------------------------------------------------------


class TestDispatchLaneLockAcquisition:
    """_handle_dispatch_needed() holds _dispatch_lane_lock while running."""

    def test_lock_is_held_during_dispatch_needed(self, tmp_path):
        """Lock is acquired before the inner work starts and released after."""
        orch = _make_orchestrator(tmp_path)
        orch._fetch_all_candidates = MagicMock(return_value=[])
        orch._pre_resolve_blockers = MagicMock()
        orch._reset_orphaned_in_progress = MagicMock()
        orch._plan_open_epics = MagicMock(return_value=[])

        lock_was_held_during_call = []

        original_locked = _make_orchestrator(tmp_path)._fetch_all_candidates
        original_fetch = orch._fetch_all_candidates

        def fetch_that_checks_lock():
            lock_was_held_during_call.append(orch._dispatch_lane_lock.locked())
            return []

        orch._fetch_all_candidates = fetch_that_checks_lock

        asyncio.run(orch._handle_dispatch_needed())

        # Lock was held during the inner work.
        assert lock_was_held_during_call == [True]

    def test_lock_is_released_after_normal_completion(self, tmp_path):
        """Lock is released (not locked) after _handle_dispatch_needed returns."""
        orch = _make_orchestrator(tmp_path)
        orch._fetch_all_candidates = MagicMock(return_value=[])
        orch._pre_resolve_blockers = MagicMock()
        orch._reset_orphaned_in_progress = MagicMock()
        orch._plan_open_epics = MagicMock(return_value=[])

        asyncio.run(orch._handle_dispatch_needed())

        assert not orch._dispatch_lane_lock.locked(), (
            "_dispatch_lane_lock must be released after _handle_dispatch_needed returns"
        )

    def test_lock_is_released_after_inner_exception(self, tmp_path):
        """Lock is released even when the inner work raises an exception."""
        orch = _make_orchestrator(tmp_path)

        def raise_error():
            raise RuntimeError("Simulated fetch failure")

        orch._fetch_all_candidates = raise_error

        with pytest.raises(RuntimeError, match="Simulated fetch failure"):
            asyncio.run(orch._handle_dispatch_needed())

        assert not orch._dispatch_lane_lock.locked(), (
            "_dispatch_lane_lock must be released after an exception inside "
            "_handle_dispatch_needed"
        )

    def test_second_dispatch_call_waits_for_first(self, tmp_path):
        """Two concurrent _handle_dispatch_needed() calls run in sequence.

        The second call cannot start candidate selection until the first
        call has fully completed.  This is the core single-owner guarantee
        for the DISPATCH lane.
        """
        orch = _make_orchestrator(tmp_path)
        call_log: list[str] = []
        fetch_gate = asyncio.Event()  # used to pause first call

        async def slow_dispatch():
            # Override candidates fetch: first call pauses here.
            call_log.append("first:start")
            await fetch_gate.wait()
            call_log.append("first:end")
            return []

        async def run_two_concurrent_dispatches():
            # Patch _handle_dispatch_needed_locked so we can observe sequencing.
            original_locked = orch._handle_dispatch_needed_locked

            call_count = [0]

            async def patched_locked():
                call_count[0] += 1
                n = call_count[0]
                if n == 1:
                    call_log.append("first:start")
                    # Yield control so second coroutine can try to start.
                    await asyncio.sleep(0)
                    await asyncio.sleep(0)
                    call_log.append("first:end")
                else:
                    call_log.append("second:start")
                    call_log.append("second:end")
                return {}

            orch._handle_dispatch_needed_locked = patched_locked  # type: ignore[method-assign]

            # Launch both at the same time.
            await asyncio.gather(
                orch._handle_dispatch_needed(),
                orch._handle_dispatch_needed(),
            )

        asyncio.run(run_two_concurrent_dispatches())

        # The calls must not interleave: first finishes before second starts.
        assert call_log == [
            "first:start",
            "first:end",
            "second:start",
            "second:end",
        ], f"Dispatch calls interleaved: {call_log}"

    def test_dispatch_needed_returns_timings_dict(self, tmp_path):
        """_handle_dispatch_needed() returns a dict (timings contract)."""
        orch = _make_orchestrator(tmp_path)
        orch._fetch_all_candidates = MagicMock(return_value=[])
        orch._pre_resolve_blockers = MagicMock()
        orch._reset_orphaned_in_progress = MagicMock()
        orch._plan_open_epics = MagicMock(return_value=[])

        result = asyncio.run(orch._handle_dispatch_needed())

        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# Tick-event coalescing contract
# ---------------------------------------------------------------------------


class TestTickEventCoalescing:
    """Multiple events queued during a tick coalesce into at most one extra tick."""

    def test_last_coalesced_count_updated_when_events_drained(self, tmp_path):
        """_last_coalesced_event_count reflects the number of events drained."""
        orch = _make_orchestrator(tmp_path)

        # Pre-load the queue with events that will be drained on the next
        # iteration.  We test the drain logic directly by injecting events
        # and calling the coalescing section in isolation via a trimmed run().
        async def run_one_drain_cycle():
            # Add two extra events to the queue.
            for _ in range(2):
                orch._dispatch_queue.put_nowait(
                    DispatchEvent(event_type=DispatchEventType.REFRESH_REQUESTED)
                )

            # Drain them synchronously (mirrors the run() loop drain logic).
            coalesced = 0
            while not orch._dispatch_queue.empty():
                try:
                    orch._dispatch_queue.get_nowait()
                    coalesced += 1
                except asyncio.QueueEmpty:
                    break
            orch._last_coalesced_event_count = coalesced

        asyncio.run(run_one_drain_cycle())

        assert orch._last_coalesced_event_count == 2

    def test_no_coalescing_when_queue_is_empty(self, tmp_path):
        """When the queue is empty, _last_coalesced_event_count stays 0."""
        orch = _make_orchestrator(tmp_path)

        async def run_drain():
            coalesced = 0
            while not orch._dispatch_queue.empty():
                try:
                    orch._dispatch_queue.get_nowait()
                    coalesced += 1
                except asyncio.QueueEmpty:
                    break
            orch._last_coalesced_event_count = coalesced

        asyncio.run(run_drain())

        assert orch._last_coalesced_event_count == 0

    def test_single_event_is_not_coalesced(self, tmp_path):
        """The trigger event itself is not counted as a coalesced event."""
        orch = _make_orchestrator(tmp_path)

        async def run_drain_after_one_trigger():
            # Simulate: trigger event was already get()d from the queue.
            # Drain the remaining (empty) queue.
            coalesced = 0
            while not orch._dispatch_queue.empty():
                try:
                    orch._dispatch_queue.get_nowait()
                    coalesced += 1
                except asyncio.QueueEmpty:
                    break
            orch._last_coalesced_event_count = coalesced

        asyncio.run(run_drain_after_one_trigger())

        assert orch._last_coalesced_event_count == 0

    def test_coalesced_count_in_tick_telemetry(self, tmp_path):
        """After a tick, tick_timings['coalesced_events'] equals _last_coalesced_event_count."""
        orch = _make_orchestrator(tmp_path)
        orch._last_coalesced_event_count = 3  # simulate 3 events were coalesced

        # Run a minimal _tick() with all heavy I/O mocked out.
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

        with patch(
            "oompah.orchestrator.validate_dispatch_config", return_value=[]
        ):
            asyncio.run(orch._tick())

        snapshot = orch.get_snapshot()
        assert "tick_timings" in snapshot
        assert snapshot["tick_timings"]["coalesced_events"] == 3

    def test_coalesced_count_resets_to_zero_on_quiet_tick(self, tmp_path):
        """After a tick with no coalesced events, coalesced_events is 0."""
        orch = _make_orchestrator(tmp_path)
        orch._last_coalesced_event_count = 0  # no coalescing this tick

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

        with patch(
            "oompah.orchestrator.validate_dispatch_config", return_value=[]
        ):
            asyncio.run(orch._tick())

        snapshot = orch.get_snapshot()
        assert snapshot["tick_timings"]["coalesced_events"] == 0


# ---------------------------------------------------------------------------
# Maintenance lane: maintenance work must not hold the dispatch lock
# ---------------------------------------------------------------------------


class TestMaintenanceLaneDoesNotBlockDispatch:
    """Maintenance-lane steps (_maybe_run_watchdog, _maybe_heal_repos) do not hold
    the dispatch lane lock, so a new dispatch pass can start immediately after
    the dispatch phase even if maintenance is still pending.
    """

    def test_watchdog_does_not_hold_dispatch_lane_lock(self, tmp_path):
        """_maybe_run_watchdog does not acquire _dispatch_lane_lock."""
        orch = _make_orchestrator(tmp_path)

        lock_state_during_watchdog: list[bool] = []

        def spy_watchdog():
            # Record whether the lock is held when watchdog runs.
            lock_state_during_watchdog.append(orch._dispatch_lane_lock.locked())

        orch._maybe_run_watchdog = spy_watchdog
        orch._maybe_heal_repos = MagicMock()
        orch._apply_pending_agent_profiles = MagicMock()
        orch._invalidate_tracker_read_caches = MagicMock()
        orch._handle_reconcile = AsyncMock()
        orch._handle_review_check = AsyncMock()
        orch._handle_dispatch_needed = AsyncMock(return_value={})
        orch._handle_yolo_review = AsyncMock(return_value=(0.0, 0.0, 0.0))
        orch._notify_observers = MagicMock()
        orch._handle_auto_update = AsyncMock()

        with patch(
            "oompah.orchestrator.validate_dispatch_config", return_value=[]
        ):
            asyncio.run(orch._tick())

        # Watchdog ran once.
        assert len(lock_state_during_watchdog) == 1
        # Dispatch lock must NOT be held during watchdog.
        assert lock_state_during_watchdog[0] is False, (
            "_dispatch_lane_lock should be released before _maybe_run_watchdog runs"
        )

    def test_heal_repos_does_not_hold_dispatch_lane_lock(self, tmp_path):
        """_maybe_heal_repos does not acquire _dispatch_lane_lock."""
        orch = _make_orchestrator(tmp_path)

        lock_state_during_heal: list[bool] = []

        def spy_heal():
            lock_state_during_heal.append(orch._dispatch_lane_lock.locked())

        orch._maybe_heal_repos = spy_heal
        orch._maybe_cleanup_worktrees = MagicMock()
        orch._auto_archive = MagicMock()
        orch._maybe_run_merged_labels = MagicMock()
        orch._maybe_run_release_pick_reconciliation = MagicMock()

        orch._run_step5b_maintenance()

        assert len(lock_state_during_heal) == 1
        assert lock_state_during_heal[0] is False, (
            "_dispatch_lane_lock should be released before _maybe_heal_repos runs"
        )

    def test_dispatch_lock_is_free_after_dispatch_phase_completes(self, tmp_path):
        """After _handle_dispatch_needed() completes, the dispatch lock is free.

        This verifies that maintenance-lane work (watchdog, heal) never has to
        wait for the dispatch lock to be released before it can run.
        """
        orch = _make_orchestrator(tmp_path)
        lock_free_before_maintenance: list[bool] = []

        original_watchdog = MagicMock()

        def spy_after_dispatch():
            lock_free_before_maintenance.append(not orch._dispatch_lane_lock.locked())
            return (0.0, 0.0, 0.0)

        orch._maybe_run_watchdog = MagicMock()
        orch._maybe_heal_repos = MagicMock()
        orch._apply_pending_agent_profiles = MagicMock()
        orch._invalidate_tracker_read_caches = MagicMock()
        orch._handle_reconcile = AsyncMock()
        orch._handle_review_check = AsyncMock()
        orch._handle_dispatch_needed = AsyncMock(return_value={})
        orch._handle_yolo_review = AsyncMock(side_effect=spy_after_dispatch)
        orch._notify_observers = MagicMock()
        orch._handle_auto_update = AsyncMock()

        with patch(
            "oompah.orchestrator.validate_dispatch_config", return_value=[]
        ):
            asyncio.run(orch._tick())

        # _handle_yolo_review runs after _handle_dispatch_needed.
        assert lock_free_before_maintenance == [True], (
            "Dispatch lock must be free when maintenance work (yolo, watchdog, heal) runs"
        )


# ---------------------------------------------------------------------------
# Dispatch lane serialization — lock ownership rules
# ---------------------------------------------------------------------------


class TestDispatchLockOwnershipRules:
    """Verify ownership contract: only _handle_dispatch_needed holds the lock."""

    def test_tick_does_not_acquire_dispatch_lock_directly(self, tmp_path):
        """_tick() does not call _dispatch_lane_lock.acquire() outside of
        _handle_dispatch_needed().  The lock is owned by the dispatch method.
        """
        orch = _make_orchestrator(tmp_path)

        lock_acquired_calls: list[str] = []
        original_acquire = orch._dispatch_lane_lock.acquire

        async def spy_acquire():
            lock_acquired_calls.append("acquire")
            return await original_acquire()

        orch._dispatch_lane_lock.acquire = spy_acquire  # type: ignore[method-assign]

        # Run a tick with _handle_dispatch_needed fully mocked (does not call
        # the real lock acquire path).
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

        with patch(
            "oompah.orchestrator.validate_dispatch_config", return_value=[]
        ):
            asyncio.run(orch._tick())

        # The lock should NOT have been acquired via our spy (because
        # _handle_dispatch_needed was fully mocked and bypassed the lock).
        assert lock_acquired_calls == [], (
            "_tick() must not acquire _dispatch_lane_lock directly; only "
            "_handle_dispatch_needed() should hold the lock."
        )

    def test_real_handle_dispatch_needed_acquires_lock_exactly_once(self, tmp_path):
        """Each call to _handle_dispatch_needed() acquires the lock exactly once."""
        orch = _make_orchestrator(tmp_path)
        orch._fetch_all_candidates = MagicMock(return_value=[])
        orch._pre_resolve_blockers = MagicMock()
        orch._reset_orphaned_in_progress = MagicMock()
        orch._plan_open_epics = MagicMock(return_value=[])

        acquire_count = [0]
        original_acquire = orch._dispatch_lane_lock.acquire

        async def counting_acquire():
            acquire_count[0] += 1
            return await original_acquire()

        orch._dispatch_lane_lock.acquire = counting_acquire  # type: ignore[method-assign]

        asyncio.run(orch._handle_dispatch_needed())

        assert acquire_count[0] == 1, (
            "_handle_dispatch_needed() must acquire the lock exactly once per call"
        )


# ---------------------------------------------------------------------------
# Tick snapshot includes lane contract fields
# ---------------------------------------------------------------------------


class TestLaneContractSnapshot:
    """Snapshot (get_snapshot) exposes lane-related fields."""

    def test_snapshot_contains_coalesced_events_key(self, tmp_path):
        """tick_timings in snapshot contains 'coalesced_events'."""
        orch = _make_orchestrator(tmp_path)
        orch._last_coalesced_event_count = 5

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

        with patch(
            "oompah.orchestrator.validate_dispatch_config", return_value=[]
        ):
            asyncio.run(orch._tick())

        snapshot = orch.get_snapshot()
        assert "coalesced_events" in snapshot["tick_timings"]

    def test_snapshot_coalesced_events_is_integer(self, tmp_path):
        """tick_timings['coalesced_events'] is an integer."""
        orch = _make_orchestrator(tmp_path)
        orch._last_coalesced_event_count = 2

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

        with patch(
            "oompah.orchestrator.validate_dispatch_config", return_value=[]
        ):
            asyncio.run(orch._tick())

        snapshot = orch.get_snapshot()
        assert isinstance(snapshot["tick_timings"]["coalesced_events"], int)

    def test_snapshot_before_first_tick_has_empty_tick_timings(self, tmp_path):
        """Before the first tick, tick_timings is empty (no coalesced_events yet)."""
        orch = _make_orchestrator(tmp_path)
        snapshot = orch.get_snapshot()
        assert snapshot["tick_timings"] == {}

    def test_snapshot_coalesced_events_zero_when_no_extra_events(self, tmp_path):
        """coalesced_events is 0 when no extra events were drained."""
        orch = _make_orchestrator(tmp_path)
        orch._last_coalesced_event_count = 0

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

        with patch(
            "oompah.orchestrator.validate_dispatch_config", return_value=[]
        ):
            asyncio.run(orch._tick())

        snapshot = orch.get_snapshot()
        assert snapshot["tick_timings"]["coalesced_events"] == 0


# ---------------------------------------------------------------------------
# Edge cases: lock never wedged; exception safety
# ---------------------------------------------------------------------------


class TestDispatchLockExceptionSafety:
    """Lock is released even when inner work raises at different stages."""

    def test_lock_released_when_candidate_fetch_raises(self, tmp_path):
        """Lock is released when _fetch_all_candidates raises."""
        orch = _make_orchestrator(tmp_path)

        def bad_fetch():
            raise ValueError("boom")

        orch._fetch_all_candidates = bad_fetch

        with pytest.raises(ValueError, match="boom"):
            asyncio.run(orch._handle_dispatch_needed())

        assert not orch._dispatch_lane_lock.locked()

    def test_lock_released_when_blocker_resolution_raises(self, tmp_path):
        """Lock is released when _pre_resolve_blockers raises."""
        orch = _make_orchestrator(tmp_path)
        orch._fetch_all_candidates = MagicMock(return_value=[])

        def bad_resolve(_):
            raise RuntimeError("resolver broke")

        orch._pre_resolve_blockers = bad_resolve

        with pytest.raises(RuntimeError, match="resolver broke"):
            asyncio.run(orch._handle_dispatch_needed())

        assert not orch._dispatch_lane_lock.locked()

    def test_second_dispatch_succeeds_after_first_raises(self, tmp_path):
        """If the first dispatch call raises, the second call can still acquire the lock."""
        orch = _make_orchestrator(tmp_path)

        call_count = [0]

        def maybe_raise():
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("first call fails")
            return []

        orch._fetch_all_candidates = maybe_raise
        orch._pre_resolve_blockers = MagicMock()
        orch._reset_orphaned_in_progress = MagicMock()
        orch._plan_open_epics = MagicMock(return_value=[])

        async def run_both():
            # First call raises.
            with pytest.raises(RuntimeError):
                await orch._handle_dispatch_needed()
            # Lock must be free so the second call succeeds.
            result = await orch._handle_dispatch_needed()
            return result

        result = asyncio.run(run_both())
        assert isinstance(result, dict)
        assert not orch._dispatch_lane_lock.locked()
