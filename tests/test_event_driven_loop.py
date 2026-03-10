"""Tests for the event-driven dispatch loop (oompah-k3d.3).

Covers:
- DispatchEventType enum and DispatchEvent dataclass
- _post_event() puts events onto the queue
- run() loop processes events and calls _tick()
- run() starts a full-sync background task
- Worker exit posts a WORKER_EXIT event
- request_refresh() posts a REFRESH_REQUESTED event
- unpause() posts a REFRESH_REQUESTED event
- _on_retry_timer() posts a RETRY_FIRED event
- full_sync_interval_ms config field (default 30000)
- from_workflow parses full_sync_interval_ms
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch, call
import pytest

from oompah.config import ServiceConfig, load_workflow, WorkflowDefinition
from oompah.orchestrator import (
    DispatchEvent,
    DispatchEventType,
    Orchestrator,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(**overrides) -> ServiceConfig:
    """Minimal ServiceConfig for testing."""
    cfg = ServiceConfig()
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


def _make_orchestrator(tmp_path, config=None) -> Orchestrator:
    orch = Orchestrator(
        config=config or _make_config(),
        workflow_path="WORKFLOW.md",
        state_path=str(tmp_path / "state.json"),
    )
    return orch


# ---------------------------------------------------------------------------
# DispatchEventType enum
# ---------------------------------------------------------------------------

class TestDispatchEventType:
    """DispatchEventType is a str enum with the expected values."""

    def test_worker_exit_value(self):
        assert DispatchEventType.WORKER_EXIT == "worker_exit"

    def test_refresh_requested_value(self):
        assert DispatchEventType.REFRESH_REQUESTED == "refresh_requested"

    def test_retry_fired_value(self):
        assert DispatchEventType.RETRY_FIRED == "retry_fired"

    def test_full_sync_value(self):
        assert DispatchEventType.FULL_SYNC == "full_sync"

    def test_is_str_subclass(self):
        assert isinstance(DispatchEventType.WORKER_EXIT, str)


# ---------------------------------------------------------------------------
# DispatchEvent dataclass
# ---------------------------------------------------------------------------

class TestDispatchEvent:
    """DispatchEvent dataclass stores event type, optional issue_id, and payload."""

    def test_basic_construction(self):
        evt = DispatchEvent(event_type=DispatchEventType.WORKER_EXIT)
        assert evt.event_type == DispatchEventType.WORKER_EXIT
        assert evt.issue_id is None
        assert evt.payload == {}

    def test_with_issue_id(self):
        evt = DispatchEvent(
            event_type=DispatchEventType.RETRY_FIRED,
            issue_id="abc-123",
        )
        assert evt.issue_id == "abc-123"

    def test_with_payload(self):
        evt = DispatchEvent(
            event_type=DispatchEventType.WORKER_EXIT,
            issue_id="x-1",
            payload={"reason": "normal"},
        )
        assert evt.payload == {"reason": "normal"}

    def test_payload_defaults_to_empty_dict_not_shared(self):
        """Each DispatchEvent gets its own payload dict (dataclass field default_factory)."""
        evt1 = DispatchEvent(event_type=DispatchEventType.FULL_SYNC)
        evt2 = DispatchEvent(event_type=DispatchEventType.FULL_SYNC)
        evt1.payload["x"] = 1
        assert "x" not in evt2.payload


# ---------------------------------------------------------------------------
# ServiceConfig.full_sync_interval_ms
# ---------------------------------------------------------------------------

class TestFullSyncIntervalConfig:
    """full_sync_interval_ms has a sensible default and can be configured."""

    def test_default_is_30000(self):
        cfg = ServiceConfig()
        assert cfg.full_sync_interval_ms == 30000

    def test_from_workflow_default(self):
        wf = WorkflowDefinition(config={}, prompt_template="")
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.full_sync_interval_ms == 30000

    def test_from_workflow_custom(self):
        wf = WorkflowDefinition(
            config={"polling": {"full_sync_interval_ms": 600000}},
            prompt_template="",
        )
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.full_sync_interval_ms == 600000

    def test_from_workflow_zero_is_accepted(self):
        """Zero is a valid (if unusual) value — no coercion to default."""
        wf = WorkflowDefinition(
            config={"polling": {"full_sync_interval_ms": 0}},
            prompt_template="",
        )
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.full_sync_interval_ms == 0


# ---------------------------------------------------------------------------
# _post_event()
# ---------------------------------------------------------------------------

class TestPostEvent:
    """_post_event() puts a DispatchEvent onto the internal dispatch queue."""

    def test_event_enqueued(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        evt = DispatchEvent(event_type=DispatchEventType.FULL_SYNC)
        orch._post_event(evt)
        assert orch._dispatch_queue.qsize() == 1

    def test_event_retrieved_in_order(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        e1 = DispatchEvent(event_type=DispatchEventType.REFRESH_REQUESTED)
        e2 = DispatchEvent(event_type=DispatchEventType.WORKER_EXIT, issue_id="a")
        orch._post_event(e1)
        orch._post_event(e2)

        got1 = orch._dispatch_queue.get_nowait()
        got2 = orch._dispatch_queue.get_nowait()
        assert got1.event_type == DispatchEventType.REFRESH_REQUESTED
        assert got2.event_type == DispatchEventType.WORKER_EXIT

    def test_multiple_events_accumulate(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        for _ in range(5):
            orch._post_event(DispatchEvent(event_type=DispatchEventType.FULL_SYNC))
        assert orch._dispatch_queue.qsize() == 5


# ---------------------------------------------------------------------------
# request_refresh() posts an event
# ---------------------------------------------------------------------------

class TestRequestRefreshPostsEvent:
    """request_refresh() wakes the dispatch loop via the queue."""

    def test_posts_refresh_requested_event(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        orch.request_refresh()
        assert orch._dispatch_queue.qsize() == 1
        evt = orch._dispatch_queue.get_nowait()
        assert evt.event_type == DispatchEventType.REFRESH_REQUESTED

    def test_also_sets_legacy_event(self, tmp_path):
        """Legacy _refresh_requested asyncio.Event is still set for backward compat."""
        orch = _make_orchestrator(tmp_path)
        orch.request_refresh()
        assert orch._refresh_requested.is_set()


# ---------------------------------------------------------------------------
# unpause() posts an event
# ---------------------------------------------------------------------------

class TestUnpausePostsEvent:
    """unpause() wakes the dispatch loop via the queue."""

    @pytest.fixture
    def event_loop(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        yield loop
        loop.close()
        asyncio.set_event_loop(None)

    def test_posts_refresh_requested_event(self, tmp_path, event_loop):
        orch = _make_orchestrator(tmp_path)
        orch._paused = True
        orch.unpause()
        # One event should be in the queue
        assert orch._dispatch_queue.qsize() == 1
        evt = orch._dispatch_queue.get_nowait()
        assert evt.event_type == DispatchEventType.REFRESH_REQUESTED
        assert evt.payload.get("reason") == "unpaused"

    def test_also_sets_legacy_event(self, tmp_path, event_loop):
        """Legacy _refresh_requested asyncio.Event is still set for backward compat."""
        orch = _make_orchestrator(tmp_path)
        orch._paused = True
        orch.unpause()
        assert orch._refresh_requested.is_set()


# ---------------------------------------------------------------------------
# Worker exit posts an event
# ---------------------------------------------------------------------------

class TestWorkerExitPostsEvent:
    """_on_worker_exit() posts a WORKER_EXIT event to the dispatch queue."""

    @pytest.fixture
    def event_loop(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        yield loop
        loop.close()
        asyncio.set_event_loop(None)

    def _make_running_entry(self, issue_id: str = "issue-1") -> Any:
        from oompah.models import RunningEntry, Issue
        from datetime import datetime, timezone
        issue = Issue(
            id=issue_id,
            identifier=issue_id,
            title="Test Issue",
            state="in_progress",
        )
        entry = RunningEntry(
            worker_task=MagicMock(),
            identifier=issue_id,
            issue=issue,
            session=None,
            retry_attempt=0,
            started_at=datetime.now(timezone.utc),
            agent_profile_name="default",
        )
        return entry

    def test_worker_exit_posts_event(self, tmp_path, event_loop):
        orch = _make_orchestrator(tmp_path)
        issue_id = "issue-1"
        orch.state.running[issue_id] = self._make_running_entry(issue_id)

        event_loop.run_until_complete(
            orch._on_worker_exit(issue_id, "normal", None)
        )

        # At least one WORKER_EXIT event should be in the queue
        events = []
        while not orch._dispatch_queue.empty():
            events.append(orch._dispatch_queue.get_nowait())

        worker_exit_events = [
            e for e in events if e.event_type == DispatchEventType.WORKER_EXIT
        ]
        assert len(worker_exit_events) == 1
        assert worker_exit_events[0].issue_id == issue_id
        assert worker_exit_events[0].payload["reason"] == "normal"

    def test_worker_exit_posts_event_on_failure(self, tmp_path, event_loop):
        orch = _make_orchestrator(tmp_path)
        issue_id = "issue-2"
        orch.state.running[issue_id] = self._make_running_entry(issue_id)

        event_loop.run_until_complete(
            orch._on_worker_exit(issue_id, "abnormal", "something went wrong")
        )

        events = []
        while not orch._dispatch_queue.empty():
            events.append(orch._dispatch_queue.get_nowait())

        worker_exit_events = [
            e for e in events if e.event_type == DispatchEventType.WORKER_EXIT
        ]
        assert len(worker_exit_events) == 1
        assert worker_exit_events[0].payload["reason"] == "abnormal"


# ---------------------------------------------------------------------------
# _on_retry_timer() posts an event
# ---------------------------------------------------------------------------

class TestRetryTimerPostsEvent:
    """_on_retry_timer() posts a RETRY_FIRED event to the dispatch queue."""

    @pytest.fixture
    def event_loop(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        yield loop
        loop.close()
        asyncio.set_event_loop(None)

    def test_retry_fired_event_posted(self, tmp_path, event_loop):
        orch = _make_orchestrator(tmp_path)
        issue_id = "retry-issue-1"

        # Stub _fetch_all_candidates to return nothing (so dispatch isn't attempted)
        orch._fetch_all_candidates = MagicMock(return_value=[])

        # Pre-populate a retry entry
        from oompah.models import RetryEntry
        import time
        orch.state.retry_attempts[issue_id] = RetryEntry(
            issue_id=issue_id,
            identifier=issue_id,
            attempt=1,
            due_at_ms=time.monotonic() * 1000,
            timer_handle=None,
            error=None,
        )

        event_loop.run_until_complete(orch._on_retry_timer(issue_id))

        events = []
        while not orch._dispatch_queue.empty():
            events.append(orch._dispatch_queue.get_nowait())

        retry_events = [
            e for e in events if e.event_type == DispatchEventType.RETRY_FIRED
        ]
        assert len(retry_events) == 1
        assert retry_events[0].issue_id == issue_id

    def test_no_retry_entry_does_not_post(self, tmp_path, event_loop):
        """If there's no pending retry for the issue, no event is posted."""
        orch = _make_orchestrator(tmp_path)
        issue_id = "nonexistent-issue"

        event_loop.run_until_complete(orch._on_retry_timer(issue_id))

        # Queue should be empty since there was no retry entry to process
        assert orch._dispatch_queue.empty()


# ---------------------------------------------------------------------------
# run() loop: event-driven behavior
# ---------------------------------------------------------------------------

class TestRunEventDrivenLoop:
    """The run() loop blocks on the dispatch queue and calls _tick() per event."""

    @pytest.fixture
    def event_loop(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        yield loop
        loop.close()
        asyncio.set_event_loop(None)

    def _make_orch_with_mocked_tick(self, tmp_path):
        """Create an orchestrator where _tick() and startup are no-ops."""
        orch = _make_orchestrator(tmp_path, config=_make_config(full_sync_interval_ms=600000))
        orch._tick = AsyncMock()
        orch.startup_cleanup = AsyncMock()
        orch._recover_restart_issues = AsyncMock()
        return orch

    def test_run_calls_tick_on_startup(self, tmp_path, event_loop):
        """run() runs an initial _tick() before entering the queue loop."""
        orch = self._make_orch_with_mocked_tick(tmp_path)

        async def _run_and_stop():
            # Post a stop signal after a very short delay
            async def _stop():
                await asyncio.sleep(0.01)
                orch._stopping = True
                # Post a dummy event to unblock the queue.get()
                orch._post_event(DispatchEvent(event_type=DispatchEventType.FULL_SYNC))

            await asyncio.gather(orch.run(), _stop())

        event_loop.run_until_complete(_run_and_stop())
        # At minimum the startup tick should have been called
        assert orch._tick.call_count >= 1

    def test_run_calls_tick_per_queue_event(self, tmp_path, event_loop):
        """run() calls _tick() for each event dequeued."""
        orch = self._make_orch_with_mocked_tick(tmp_path)

        async def _run_and_stop():
            async def _feed_events():
                # Wait for loop to start
                await asyncio.sleep(0.01)
                # Post two events then stop
                orch._post_event(DispatchEvent(event_type=DispatchEventType.REFRESH_REQUESTED))
                orch._post_event(DispatchEvent(event_type=DispatchEventType.WORKER_EXIT))
                await asyncio.sleep(0.05)
                orch._stopping = True
                # Unblock queue.get()
                orch._post_event(DispatchEvent(event_type=DispatchEventType.FULL_SYNC))

            await asyncio.gather(orch.run(), _feed_events())

        event_loop.run_until_complete(_run_and_stop())
        # Startup tick + at least 2 event ticks (REFRESH_REQUESTED, WORKER_EXIT)
        assert orch._tick.call_count >= 3

    def test_run_stops_when_stopping_is_set(self, tmp_path, event_loop):
        """run() exits cleanly when _stopping is set."""
        orch = self._make_orch_with_mocked_tick(tmp_path)

        async def _run():
            async def _stop():
                await asyncio.sleep(0.02)
                orch._stopping = True
                orch._post_event(DispatchEvent(event_type=DispatchEventType.FULL_SYNC))

            await asyncio.gather(orch.run(), _stop())

        # Should complete without hanging
        event_loop.run_until_complete(asyncio.wait_for(_run(), timeout=5.0))

    def test_full_sync_loop_posts_full_sync_events(self, tmp_path, event_loop):
        """_full_sync_loop() posts FULL_SYNC events at the configured interval."""
        # Use a very short interval so the test doesn't take long
        orch = _make_orchestrator(tmp_path, config=_make_config(full_sync_interval_ms=50))
        orch._stopping = False

        async def _run_for_a_bit():
            task = asyncio.create_task(orch._full_sync_loop())
            await asyncio.sleep(0.2)
            orch._stopping = True
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

        event_loop.run_until_complete(_run_for_a_bit())

        # Should have received at least 2 FULL_SYNC events (50ms interval, 200ms wait)
        events = []
        while not orch._dispatch_queue.empty():
            events.append(orch._dispatch_queue.get_nowait())

        full_sync_events = [e for e in events if e.event_type == DispatchEventType.FULL_SYNC]
        assert len(full_sync_events) >= 2

    def test_full_sync_loop_stops_when_stopping(self, tmp_path, event_loop):
        """_full_sync_loop() exits when _stopping is set."""
        orch = _make_orchestrator(tmp_path, config=_make_config(full_sync_interval_ms=10000))

        async def _run():
            task = asyncio.create_task(orch._full_sync_loop())
            await asyncio.sleep(0.05)
            orch._stopping = True
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

        event_loop.run_until_complete(_run())
        # No events should have been posted (interval is 10s, we only waited 50ms)
        assert orch._dispatch_queue.empty()

    def test_run_does_not_poll_at_old_interval(self, tmp_path, event_loop):
        """The old poll_interval_ms sleep is gone — run() only wakes on queue events."""
        # Configure a short poll_interval_ms but a very long full_sync_interval_ms.
        # The loop should NOT fire ticks at poll_interval_ms cadence any more.
        orch = _make_orchestrator(tmp_path, config=_make_config(
            poll_interval_ms=50,          # old interval (should be ignored now)
            full_sync_interval_ms=600000, # new interval (won't fire in test)
        ))
        orch._tick = AsyncMock()
        orch.startup_cleanup = AsyncMock()
        orch._recover_restart_issues = AsyncMock()

        async def _run_briefly():
            run_task = asyncio.create_task(orch.run())
            # Wait long enough that old 50ms poll would have fired multiple times
            await asyncio.sleep(0.3)
            orch._stopping = True
            orch._post_event(DispatchEvent(event_type=DispatchEventType.FULL_SYNC))
            await asyncio.wait_for(run_task, timeout=2.0)

        event_loop.run_until_complete(_run_briefly())
        # Only the startup tick should have fired (no queue events besides the stop one)
        # The old poll-based loop would have fired ~6 times in 300ms at 50ms interval.
        # Event-driven loop fires exactly once (startup) + once (the FULL_SYNC we sent to stop).
        # Allow up to 3 to be safe (e.g., if the stop event itself triggers a tick).
        assert orch._tick.call_count <= 3, (
            f"Expected event-driven loop (max 3 ticks), but got {orch._tick.call_count}. "
            "The old poll loop may still be active."
        )


# ---------------------------------------------------------------------------
# Dispatch queue: orchestrator has a queue attribute
# ---------------------------------------------------------------------------

class TestDispatchQueueAttribute:
    """The orchestrator exposes _dispatch_queue as an asyncio.Queue."""

    def test_dispatch_queue_exists(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        assert hasattr(orch, "_dispatch_queue")
        assert isinstance(orch._dispatch_queue, asyncio.Queue)

    def test_dispatch_queue_starts_empty(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        assert orch._dispatch_queue.empty()
