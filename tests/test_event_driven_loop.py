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
- full_sync_interval_ms config field (default 300000)
- from_workflow parses full_sync_interval_ms
"""

from __future__ import annotations

import asyncio
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from types import SimpleNamespace
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

_OWNED_ORCHESTRATOR_RESOURCES: list[
    tuple[tuple[tuple[str, Any], ...], tuple[tuple[str, Any], ...]]
] = []


def _remember_orchestrator_resources(orch: Orchestrator) -> None:
    """Retain the exact pools and stores opened by a test orchestrator."""

    stores = tuple(
        (name, store)
        for name in (
            "coordination_store",
            "integration_queue",
            "review_capacity_store",
            "workflow_job_store",
            "task_transition_journal",
        )
        if (store := getattr(orch, name, None)) is not None
    )
    _OWNED_ORCHESTRATOR_RESOURCES.append(
        (
            (
                ("_tick_pool", orch._tick_pool),
                ("_refresh_pool", orch._refresh_pool),
            ),
            stores,
        )
    )


@pytest.fixture(autouse=True)
def _close_owned_orchestrator_resources():
    """Close every helper-owned resource and report all cleanup failures."""

    first_owned = len(_OWNED_ORCHESTRATOR_RESOURCES)
    try:
        yield
    finally:
        owned = _OWNED_ORCHESTRATOR_RESOURCES[first_owned:]
        del _OWNED_ORCHESTRATOR_RESOURCES[first_owned:]
        cleanup_errors: list[str] = []
        for owner_index, (pools, stores) in enumerate(reversed(owned), start=1):
            for resource_name, pool in pools:
                try:
                    pool.shutdown(wait=True, cancel_futures=False)
                except Exception as exc:  # noqa: BLE001 - close every resource
                    cleanup_errors.append(
                        f"orchestrator {owner_index} {resource_name} shutdown "
                        f"failed: {exc!r}"
                    )
                live_threads = [
                    thread.name
                    for thread in getattr(pool, "_threads", ())
                    if thread.is_alive()
                ]
                if live_threads:
                    cleanup_errors.append(
                        f"orchestrator {owner_index} {resource_name} retained "
                        f"live threads: {', '.join(live_threads)}"
                    )
            for resource_name, store in stores:
                try:
                    store.close()
                except Exception as exc:  # noqa: BLE001 - close every resource
                    cleanup_errors.append(
                        f"orchestrator {owner_index} {resource_name} close "
                        f"failed: {exc!r}"
                    )
        if cleanup_errors:
            pytest.fail("helper-owned resource leakage: " + "; ".join(cleanup_errors))


def _close_event_loop_and_executor(loop: asyncio.AbstractEventLoop) -> None:
    """Drain loop-owned tasks and join its default executor before close."""

    cleanup_errors: list[str] = []
    executor = getattr(loop, "_default_executor", None)
    pending = [task for task in asyncio.all_tasks(loop) if not task.done()]
    if pending:
        for task in pending:
            task.cancel()
        try:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception as exc:  # noqa: BLE001 - continue executor cleanup
            cleanup_errors.append(f"pending task drain failed: {exc!r}")
        cleanup_errors.append(
            "event loop retained pending tasks: "
            + ", ".join(sorted(task.get_name() for task in pending))
        )
    try:
        loop.run_until_complete(loop.shutdown_asyncgens())
    except Exception as exc:  # noqa: BLE001 - continue executor cleanup
        cleanup_errors.append(f"async-generator shutdown failed: {exc!r}")
    try:
        loop.run_until_complete(loop.shutdown_default_executor())
    except Exception as exc:  # noqa: BLE001 - loop close must still run
        cleanup_errors.append(f"default-executor shutdown failed: {exc!r}")
    if executor is not None:
        live_threads = [
            thread.name
            for thread in getattr(executor, "_threads", ())
            if thread.is_alive()
        ]
        if live_threads:
            cleanup_errors.append(
                "default executor retained live threads: "
                + ", ".join(live_threads)
            )
    loop.close()
    asyncio.set_event_loop(None)
    if cleanup_errors:
        pytest.fail("event-loop resource leakage: " + "; ".join(cleanup_errors))


def _make_config(**overrides) -> ServiceConfig:
    """Minimal ServiceConfig for testing."""
    cfg = ServiceConfig(tracker_kind="oompah_md")
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


def _make_orchestrator(tmp_path, config=None, project_store=None) -> Orchestrator:
    orch = Orchestrator(
        config=config or _make_config(),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        state_path=str(tmp_path / "state.json"),
    )
    _remember_orchestrator_resources(orch)
    return orch


def _stub_unrelated_run_startup(
    orch: Orchestrator,
    *,
    retain_restart_recovery: bool = False,
) -> None:
    """Keep loop tests out of tracker-backed startup reconciliation lanes."""

    # These startup owners publish or reconcile workflow work, but none is
    # part of the event-loop contract exercised by their callers.  Leaving
    # even one live makes a directly constructed fixture discover the
    # checkout's configured projects and turns a scheduler test into an
    # integration test.
    orch._run_terminal_audit_enforcement = MagicMock()
    orch._reconcile_owner_duplicate_resolution_boundaries = MagicMock()
    orch._ensure_integration_audit_lane = MagicMock()
    orch._schedule_terminal_lifecycle_reconciliation = MagicMock()
    orch.startup_cleanup = AsyncMock()
    orch._reconcile_pending_recovery_publications = MagicMock()
    orch._restore_persisted_retries = AsyncMock()
    orch._wake_integration_lane = MagicMock()
    orch.workflow_controller.recover_startup = MagicMock()
    if not retain_restart_recovery:
        orch._recover_restart_issues = AsyncMock(return_value=True)


# ---------------------------------------------------------------------------
# DispatchEventType enum
# ---------------------------------------------------------------------------

class TestDispatchEventType:
    """DispatchEventType is a str enum with the expected values."""

    def test_worker_exit_value(self):
        assert DispatchEventType.WORKER_EXIT == "worker_exit"

    def test_refresh_requested_value(self):
        assert DispatchEventType.REFRESH_REQUESTED == "refresh_requested"

    def test_workflow_admission_value(self):
        assert DispatchEventType.WORKFLOW_ADMISSION == "workflow_admission"

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

    @pytest.fixture(autouse=True)
    def _clear_service_override(self, monkeypatch):
        """Exercise workflow precedence without the service's gate environment."""
        monkeypatch.delenv("OOMPAH_FULL_SYNC_INTERVAL_MS", raising=False)

    def test_default_is_300000(self):
        cfg = ServiceConfig()
        assert cfg.full_sync_interval_ms == 300000

    def test_from_workflow_default(self):
        wf = WorkflowDefinition(config={}, prompt_template="")
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.full_sync_interval_ms == 300000

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


class TestWorktreeCleanupConfig:
    """Branch/worktree cleanup has an independent, aggressive cadence."""

    def test_defaults(self):
        cfg = ServiceConfig()
        assert cfg.worktree_cleanup_interval_seconds == 60
        assert cfg.worktree_cleanup_batch_size == 100

    def test_environment_overrides(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_WORKTREE_CLEANUP_INTERVAL_SECONDS", "15")
        monkeypatch.setenv("OOMPAH_WORKTREE_CLEANUP_BATCH_SIZE", "250")

        cfg = ServiceConfig.from_workflow(
            WorkflowDefinition(config={}, prompt_template="")
        )

        assert cfg.worktree_cleanup_interval_seconds == 15
        assert cfg.worktree_cleanup_batch_size == 250

    def test_interval_is_clamped_positive(self):
        cfg = ServiceConfig(worktree_cleanup_interval_seconds=0)
        assert cfg.worktree_cleanup_interval_seconds == 1


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

    def test_worker_event_does_not_duplicate_capacity_release_wake(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        evt = DispatchEvent(
            event_type=DispatchEventType.WORKER_EXIT,
            issue_id="worker-a",
        )
        with patch.object(
            orch,
            "_wake_terminal_audit_continuation_lane",
        ) as wake:
            orch._post_event(evt)

        assert orch._dispatch_queue.qsize() == 1
        wake.assert_not_called()

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

    def test_duplicate_events_coalesce(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        for _ in range(5):
            orch._post_event(DispatchEvent(event_type=DispatchEventType.FULL_SYNC))
        assert orch._dispatch_queue.qsize() == 1
        assert orch._dispatch_events_coalesced == 4

    def test_duplicate_event_count_is_returned_when_trigger_dequeued(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        for _ in range(5):
            orch._post_event(DispatchEvent(event_type=DispatchEventType.FULL_SYNC))

        trigger = orch._dispatch_queue.get_nowait()
        assert orch._mark_dispatch_event_dequeued(trigger) == 4
        assert DispatchEventType.FULL_SYNC not in orch._dispatch_pending_event_keys
        assert not orch._dispatch_pending_coalesced_counts

    def test_post_event_from_other_loop_uses_threadsafe_owner_loop(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        owner_loop = MagicMock()
        owner_loop.is_running.return_value = True
        orch._dispatch_loop = owner_loop
        evt = DispatchEvent(event_type=DispatchEventType.FULL_SYNC)

        orch._post_event(evt)

        owner_loop.call_soon_threadsafe.assert_called_once_with(
            orch._post_event_on_loop,
            evt,
        )
        assert orch._dispatch_queue.qsize() == 0


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

    def test_posts_to_owner_loop_from_other_loop(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        owner_loop = MagicMock()
        owner_loop.is_running.return_value = True
        orch._dispatch_loop = owner_loop

        orch.request_refresh()

        calls = owner_loop.call_soon_threadsafe.call_args_list
        assert calls[0].args == (orch._refresh_requested.set,)
        assert calls[1].args[0] == orch._post_event_on_loop
        assert calls[1].args[1].event_type == DispatchEventType.REFRESH_REQUESTED
        assert orch._dispatch_queue.qsize() == 0


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
        _close_event_loop_and_executor(loop)

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

    def test_cross_loop_resume_waits_for_failed_task_publication(
        self, tmp_path, event_loop
    ):
        """Resume cannot report success before its recovery owner exists."""

        orch = _make_orchestrator(tmp_path)
        entry = {
            "issue_id": "TASK-cross-loop",
            "identifier": "TASK-cross-loop",
            "project_id": "proj-test",
        }
        orch._save_state(restart_issues=[entry])
        orch._paused = True
        orch._quiesced = True
        owner_loop = MagicMock()
        owner_loop.is_running.return_value = True
        owner_loop.create_task.side_effect = RuntimeError("event loop is closing")
        orch._dispatch_loop = owner_loop

        callback_enqueued = threading.Event()
        release_callback = threading.Event()
        callback_threads = []

        def _enqueue(callback):
            def _delayed_callback():
                assert release_callback.wait(timeout=3)
                callback()

            callback_thread = threading.Thread(target=_delayed_callback)
            callback_threads.append(callback_thread)
            callback_thread.start()
            callback_enqueued.set()

        owner_loop.call_soon_threadsafe.side_effect = _enqueue
        results = []
        resume_thread = threading.Thread(
            target=lambda: results.append(orch.unpause())
        )
        resume_thread.start()

        assert callback_enqueued.wait(timeout=1)
        assert resume_thread.is_alive()
        assert results == []

        release_callback.set()
        resume_thread.join(timeout=3)
        callback_threads[0].join(timeout=3)

        assert not resume_thread.is_alive()
        assert results == [False]
        assert orch._restart_recovery_task is None
        assert orch._restart_issue_snapshot() == [entry]
        assert orch._quiesced is True

    def test_cross_loop_resume_fails_closed_when_loop_rejects_callback(
        self, tmp_path, event_loop
    ):
        """A closing owner loop retains both the durable row and the fence."""

        orch = _make_orchestrator(tmp_path)
        entry = {
            "issue_id": "TASK-closed-loop",
            "identifier": "TASK-closed-loop",
            "project_id": "proj-test",
        }
        orch._save_state(restart_issues=[entry])
        orch._paused = True
        orch._quiesced = True
        owner_loop = MagicMock()
        owner_loop.is_running.return_value = True
        owner_loop.call_soon_threadsafe.side_effect = RuntimeError("loop closed")
        orch._dispatch_loop = owner_loop

        assert orch.unpause() is False

        assert orch._restart_recovery_task is None
        assert orch._restart_issue_snapshot() == [entry]
        assert orch._quiesced is True


# ---------------------------------------------------------------------------
# Worker exit posts an event
# ---------------------------------------------------------------------------

class TestWorkerExitPostsEvent:
    """_on_worker_exit() posts a WORKER_EXIT event to the dispatch queue.

    Each running entry carries a test project ID ("proj-test") so the
    worker-exit path routes through _tracker_for_project (which is
    replaced by a MagicMock) rather than falling back to the checkout's
    live orch.tracker.  Telemetry and completion side-effects are mocked
    out so only event publication is exercised.
    """

    @pytest.fixture
    def event_loop(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        yield loop
        _close_event_loop_and_executor(loop)

    def _make_running_entry(self, issue_id: str = "issue-1") -> Any:
        from oompah.models import RunningEntry, Issue
        from datetime import datetime, timezone
        issue = Issue(
            id=issue_id,
            identifier=issue_id,
            title="Test Issue",
            state="in_progress",
            # Give every entry a test project ID so the worker-exit
            # path calls _tracker_for_project instead of falling back
            # to the live tracker.
            project_id="proj-test",
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

    @staticmethod
    def _fail_on_git_push(*args, **kwargs):
        """Fail-fast guard: raise if any subprocess call issues a git push."""
        cmd = args[0] if args else kwargs.get("args", [])
        if isinstance(cmd, (list, tuple)) and "push" in cmd:
            raise AssertionError(f"Test must not invoke git push: {cmd}")
        return MagicMock(returncode=0, stdout=b"", stderr=b"")

    def _inject_isolation_mocks(self, orch: Any, issue_id: str) -> Any:
        """Inject a mock tracker and mute unrelated side-effect methods.

        Returns the mock tracker so callers can assert its interactions.
        The tracker's fetch_issue_detail returns a terminal 'Done' issue
        so the normal-exit path treats the task as successfully closed
        without re-opening or scheduling retries.
        """
        from oompah.models import Issue as _Issue
        mock_tracker = MagicMock()
        mock_tracker.fetch_issue_detail.return_value = _Issue(
            id=issue_id,
            identifier=issue_id,
            title="Test Issue",
            state="Done",
        )
        mock_tracker.fetch_comments.return_value = []
        orch._tracker_for_project = MagicMock(return_value=mock_tracker)
        # Silence fire-and-forget telemetry so no background threads escape.
        orch._fire_task_cost_record = MagicMock()
        orch._fire_telemetry_comment = MagicMock()
        # Silence comment posting (not the target of these tests).
        orch._post_comment = MagicMock()
        # Silence completion-side-effects: review creation, epic close,
        # focus analysis.  These are orthogonal to event publication and
        # may otherwise trigger git or network I/O.
        orch._ensure_review_exists = MagicMock(return_value=True)
        orch._maybe_auto_close_parent_epic = MagicMock()
        orch._analyze_focus_fit = MagicMock()
        # Silence retry scheduling for abnormal exits (prevents asyncio timers).
        orch._schedule_retry = MagicMock()
        return mock_tracker

    def test_worker_exit_posts_event(self, tmp_path, event_loop):
        """Normal exit posts exactly one WORKER_EXIT event with reason='normal'."""
        # Disable close gates so _run_close_gate / _run_unpushed_gate return
        # True immediately without touching git.
        orch = _make_orchestrator(tmp_path, config=_make_config(close_gate_enabled=False))
        issue_id = "issue-1"
        orch.state.running[issue_id] = self._make_running_entry(issue_id)
        mock_tracker = self._inject_isolation_mocks(orch, issue_id)

        with patch("subprocess.run", side_effect=self._fail_on_git_push), \
             patch("subprocess.Popen", side_effect=self._fail_on_git_push):
            event_loop.run_until_complete(
                orch._on_worker_exit(issue_id, "normal", None)
            )

        # Verify the project-scoped mock tracker was used, not the live one.
        orch._tracker_for_project.assert_called_with("proj-test")

        # At least one WORKER_EXIT event should be in the queue.
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
        """Abnormal exit posts exactly one WORKER_EXIT event with reason='abnormal'."""
        orch = _make_orchestrator(tmp_path, config=_make_config(close_gate_enabled=False))
        issue_id = "issue-2"
        orch.state.running[issue_id] = self._make_running_entry(issue_id)
        self._inject_isolation_mocks(orch, issue_id)

        with patch("subprocess.run", side_effect=self._fail_on_git_push), \
             patch("subprocess.Popen", side_effect=self._fail_on_git_push):
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
        _close_event_loop_and_executor(loop)

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

    def test_retry_issue_fetch_runs_off_event_loop(self, tmp_path, event_loop):
        """Retry lookup may call asyncio.run internally and must run in a thread."""
        import threading
        import time

        from oompah.models import Issue, RetryEntry

        orch = _make_orchestrator(tmp_path)
        issue_id = "retry-issue-thread"
        event_loop_thread = threading.current_thread()
        fetch_threads: list[threading.Thread] = []

        def _fetch_retry_issue(_retry):
            fetch_threads.append(threading.current_thread())

            async def _inner():
                return Issue(
                    id=issue_id,
                    identifier=issue_id,
                    title="Retry issue",
                    state="Open",
                )

            return asyncio.run(_inner())

        orch._fetch_retry_issue = _fetch_retry_issue
        orch._dispatch = AsyncMock()
        orch.state.retry_attempts[issue_id] = RetryEntry(
            issue_id=issue_id,
            identifier=issue_id,
            attempt=1,
            due_at_ms=time.monotonic() * 1000,
            timer_handle=None,
            error=None,
        )

        event_loop.run_until_complete(orch._on_retry_timer(issue_id))

        assert fetch_threads, "_fetch_retry_issue was never called"
        assert fetch_threads[0] is not event_loop_thread
        orch._dispatch.assert_awaited_once()

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
        _close_event_loop_and_executor(loop)

    def _make_orch_with_mocked_tick(self, tmp_path, *, config=None):
        """Create an orchestrator with only the event-loop behavior left live."""
        orch = _make_orchestrator(
            tmp_path,
            config=config
            or _make_config(full_sync_interval_ms=600000),
        )
        orch._tick = AsyncMock()
        _stub_unrelated_run_startup(orch)
        return orch

    def test_run_calls_tick_on_startup(self, tmp_path, event_loop):
        """run() runs an initial _tick() before entering the queue loop."""
        orch = self._make_orch_with_mocked_tick(tmp_path)
        tick_started = asyncio.Event()

        async def _tick():
            tick_started.set()

        orch._tick = AsyncMock(side_effect=_tick)

        async def _run_and_stop():
            async def _stop():
                await asyncio.wait_for(tick_started.wait(), timeout=2.0)
                orch._stopping = True
                # Post a dummy event to unblock the queue.get()
                orch._post_event(DispatchEvent(event_type=DispatchEventType.FULL_SYNC))

            await asyncio.gather(orch.run(), _stop())

        event_loop.run_until_complete(_run_and_stop())
        # At minimum the startup tick should have been called
        assert orch._tick.call_count >= 1

    def test_startup_tracker_outage_keeps_dispatch_fenced_until_recovery(
        self, tmp_path, event_loop
    ):
        """A retained restart row owns retry and blocks the first dispatch."""

        from oompah.models import Issue

        orch = _make_orchestrator(
            tmp_path,
            config=_make_config(
                poll_interval_ms=10,
                full_sync_interval_ms=600000,
            ),
        )
        entry = {
            "issue_id": "TASK-startup-outage",
            "identifier": "TASK-startup-outage",
            "project_id": "proj-test",
        }
        orch._save_state(restart_issues=[entry])
        tracker_state = {"value": "In Progress"}
        fetch_count = 0
        tracker = MagicMock()

        def _fetch(_issue_ids):
            nonlocal fetch_count
            fetch_count += 1
            if fetch_count == 1:
                raise RuntimeError("tracker unavailable during startup")
            return [
                Issue(
                    id=entry["issue_id"],
                    identifier=entry["identifier"],
                    title="Interrupted implementation",
                    state=tracker_state["value"],
                    project_id=entry["project_id"],
                )
            ]

        tracker.fetch_issue_states_by_ids.side_effect = _fetch
        tracker.update_issue.side_effect = (
            lambda _identifier, *, status: tracker_state.update(value=status)
        )
        orch._tracker_for_project = MagicMock(return_value=tracker)
        _stub_unrelated_run_startup(orch, retain_restart_recovery=True)
        initial_tick_fences = []

        async def _tick():
            initial_tick_fences.append(orch._quiesced)
            while orch._quiesced:
                await asyncio.sleep(0.001)
            orch._stopping = True

        orch._tick = AsyncMock(side_effect=_tick)

        event_loop.run_until_complete(
            asyncio.wait_for(orch.run(), timeout=3.0)
        )

        assert initial_tick_fences == [True]
        assert fetch_count >= 2
        tracker.update_issue.assert_called_once_with(
            entry["identifier"], status="Open"
        )
        assert tracker_state["value"] == "Open"
        assert orch._restart_issue_snapshot() == []
        assert orch._quiesced is False

    def test_run_calls_tick_for_queued_events(self, tmp_path, event_loop):
        """run() calls _tick() for queued events.

        Events posted synchronously (without yielding) may be coalesced:
        two simultaneous events result in at least one event tick, not
        necessarily two separate ticks.  See TASK-465.2 for the coalescing
        contract.
        """
        orch = self._make_orch_with_mocked_tick(tmp_path)
        startup_tick_completed = asyncio.Event()
        queued_event_tick_completed = asyncio.Event()
        tick_count = 0
        original_tick = orch._tick

        async def _tracked_tick():
            nonlocal tick_count
            tick_count += 1
            await original_tick()
            if tick_count == 1:
                startup_tick_completed.set()
            else:
                queued_event_tick_completed.set()

        orch._tick = _tracked_tick

        async def _run_and_stop():
            async def _feed_events():
                # Do not assume a fixed delay is enough for startup under a
                # saturated test worker.  The queued-event assertion is only
                # meaningful after the initial tick has completed.
                await asyncio.wait_for(startup_tick_completed.wait(), timeout=2.0)
                # Post two events back-to-back (no yield between them).
                # With coalescing they may merge into a single dispatch pass.
                orch._post_event(DispatchEvent(event_type=DispatchEventType.REFRESH_REQUESTED))
                orch._post_event(DispatchEvent(event_type=DispatchEventType.WORKER_EXIT))
                # Shutdown refuses to start another tick after the stop fence
                # is raised, so wait for the queued event tick to complete
                # before setting that fence instead of racing a fixed sleep.
                await asyncio.wait_for(queued_event_tick_completed.wait(), timeout=2.0)
                orch._stopping = True
                # Unblock queue.get()
                orch._post_event(DispatchEvent(event_type=DispatchEventType.FULL_SYNC))

            await asyncio.gather(orch.run(), _feed_events())

        event_loop.run_until_complete(_run_and_stop())
        # Startup tick + at least 1 event tick (2 events may coalesce into 1).
        assert tick_count >= 2

    def test_run_coalesces_burst_events_into_fewer_ticks(self, tmp_path, event_loop):
        """Events posted synchronously (no yield between them) coalesce into one tick.

        This verifies TASK-465.2 acceptance criterion #3: repeated tick requests
        coalesce instead of piling up unbounded full-tick work.  Five events
        posted without yielding should result in fewer than 5+1=6 ticks.
        """
        orch = self._make_orch_with_mocked_tick(tmp_path)
        burst_processed = asyncio.Event()
        tick_count = [0]

        # Wrap _tick to track when the burst has been processed.
        original_tick = orch._tick

        async def _tracked_tick():
            tick_count[0] += 1
            await original_tick()
            # After at least one tick following the burst, signal completion.
            # We expect: 1 (startup) + 1-2 (burst + any additional) ticks.
            if tick_count[0] >= 2:
                burst_processed.set()

        orch._tick = _tracked_tick

        async def _run_and_stop():
            async def _feed_burst():
                # Wait for loop to start and run startup tick.
                await asyncio.sleep(0.01)
                # Post 5 events without yielding between them.
                for _ in range(5):
                    orch._post_event(
                        DispatchEvent(event_type=DispatchEventType.REFRESH_REQUESTED)
                    )
                # Wait for burst to be processed instead of using fixed sleep.
                # Timeout after 2 seconds to catch hung loops.
                try:
                    await asyncio.wait_for(burst_processed.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    pass  # Proceed to shutdown even if burst didn't complete
                orch._stopping = True
                orch._post_event(DispatchEvent(event_type=DispatchEventType.FULL_SYNC))

            await asyncio.gather(orch.run(), _feed_burst())

        event_loop.run_until_complete(_run_and_stop())
        # Without coalescing we'd expect 1 (startup) + 5 (individual events) = 6.
        # With coalescing the burst collapses: expect at most 3 total ticks.
        assert tick_count[0] < 6, (
            f"Expected coalescing to reduce tick count below 6, got {tick_count[0]}"
        )
        # But the loop must have run at least once (startup + some event tick).
        assert tick_count[0] >= 2


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

    def test_run_drains_background_work_before_releasing_owner_loop(
        self,
        tmp_path,
        event_loop,
    ):
        """Scheduler-owned futures are drained before asyncio.run closes its loop."""
        orch = self._make_orch_with_mocked_tick(tmp_path)
        orch._drain_background_work = AsyncMock()

        async def _run():
            async def _stop():
                await asyncio.sleep(0.01)
                orch._stopping = True
                orch._post_event(
                    DispatchEvent(event_type=DispatchEventType.SHUTDOWN)
                )

            await asyncio.gather(orch.run(), _stop())

        event_loop.run_until_complete(_run())

        orch._drain_background_work.assert_awaited_once()
        assert orch._dispatch_loop is None

    def test_graceful_stop_keeps_workflow_store_open_for_active_tick(
        self,
        tmp_path,
        event_loop,
    ):
        """A reconcile tick retains its store authority through shutdown."""

        orch = self._make_orch_with_mocked_tick(tmp_path)
        tick_started = asyncio.Event()
        release_tick = asyncio.Event()

        async def _blocked_tick():
            tick_started.set()
            await release_tick.wait()
            # This is the mutation boundary that used to race store closure
            # during a graceful restart.
            orch.workflow_job_store.integrity_check()

        orch._tick = _blocked_tick
        tick_drain_entered = asyncio.Event()
        original_drain_active_tick = orch._drain_active_tick

        async def _observed_drain_active_tick():
            tick_drain_entered.set()
            await original_drain_active_tick()

        orch._drain_active_tick = _observed_drain_active_tick

        async def _run_and_stop():
            run_task = asyncio.create_task(orch.run())
            await asyncio.wait_for(tick_started.wait(), timeout=2.0)

            stop_task = asyncio.create_task(orch.stop())
            await asyncio.wait_for(tick_drain_entered.wait(), timeout=2.0)

            assert stop_task.done() is False
            assert orch.workflow_job_store._authority_lock_fd >= 0

            release_tick.set()
            assert await asyncio.wait_for(stop_task, timeout=5.0) is True
            await asyncio.wait_for(run_task, timeout=5.0)

        event_loop.run_until_complete(_run_and_stop())
        assert orch.workflow_job_store._authority_lock_fd == -1

    def test_graceful_stop_retries_slow_workflow_drain_without_critical_alert(
        self,
        tmp_path,
        event_loop,
        caplog,
    ):
        """A retained runtime owner is normal graceful-drain progress."""

        orch = self._make_orch_with_mocked_tick(tmp_path)
        runtime = SimpleNamespace(
            drain=AsyncMock(side_effect=[False, True]),
            pending_operation_count=1,
        )
        orch.workflow_runtime = runtime
        orch._notify_observers = MagicMock()

        async def _exercise():
            with caplog.at_level(logging.INFO, logger="oompah.orchestrator"):
                assert await orch.stop() is False
                assert orch.workflow_job_store._authority_lock_fd >= 0
                runtime.pending_operation_count = 0
                assert await orch.stop() is True

        event_loop.run_until_complete(_exercise())

        assert runtime.drain.await_args_list == [
            call(timeout_seconds=10.0),
            call(timeout_seconds=10.0),
        ]
        assert any(
            "safely waiting for workflow runtime operations to drain"
            in record.getMessage()
            for record in caplog.records
        )
        assert not any(record.levelno >= logging.ERROR for record in caplog.records)
        assert orch.workflow_job_store._authority_lock_fd == -1

    def test_graceful_stop_keeps_real_persistence_failure_critical(
        self,
        tmp_path,
        event_loop,
        caplog,
    ):
        """A failed durable journal remains operator-actionable."""

        orch = self._make_orch_with_mocked_tick(tmp_path)
        runtime = SimpleNamespace(
            drain=AsyncMock(side_effect=[False, True]),
            pending_operation_count=1,
        )
        orch.workflow_runtime = runtime
        orch._notify_observers = MagicMock()
        orch._retry_persistence_failed = True
        orch._persist_retry_entries = MagicMock()

        async def _exercise():
            with caplog.at_level(logging.INFO, logger="oompah.orchestrator"):
                assert await orch.stop() is False
                assert orch.workflow_job_store._authority_lock_fd >= 0
                orch._retry_persistence_failed = False
                runtime.pending_operation_count = 0
                assert await orch.stop() is True

        event_loop.run_until_complete(_exercise())

        critical = [
            record.getMessage()
            for record in caplog.records
            if record.levelno >= logging.CRITICAL
        ]
        assert any("implementation retry" in message for message in critical)
        assert orch.workflow_job_store._authority_lock_fd == -1

    def test_graceful_stop_keeps_store_open_during_scheduler_startup(
        self,
        tmp_path,
        event_loop,
    ):
        """The run-task barrier also covers work before the initial tick."""

        orch = self._make_orch_with_mocked_tick(tmp_path)
        startup_entered = asyncio.Event()
        release_startup = asyncio.Event()

        async def _blocked_startup_cleanup():
            startup_entered.set()
            await release_startup.wait()
            orch.workflow_job_store.integrity_check()

        orch.startup_cleanup = _blocked_startup_cleanup
        startup_drain_entered = asyncio.Event()
        original_drain_scheduler_startup = orch._drain_scheduler_startup

        async def _observed_drain_scheduler_startup():
            startup_drain_entered.set()
            await original_drain_scheduler_startup()

        orch._drain_scheduler_startup = _observed_drain_scheduler_startup

        async def _run_and_stop():
            run_task = asyncio.create_task(orch.run())
            await asyncio.wait_for(startup_entered.wait(), timeout=2.0)

            stop_task = asyncio.create_task(orch.stop())
            await asyncio.wait_for(startup_drain_entered.wait(), timeout=2.0)

            assert stop_task.done() is False
            assert orch.workflow_job_store._authority_lock_fd >= 0

            release_startup.set()
            assert await asyncio.wait_for(stop_task, timeout=5.0) is True
            await asyncio.wait_for(run_task, timeout=5.0)

        event_loop.run_until_complete(_run_and_stop())
        assert orch.workflow_job_store._authority_lock_fd == -1

    def test_run_declines_startup_after_stop_wins_admission(
        self,
        tmp_path,
        event_loop,
    ):
        """A scheduler that loses the stop fence never touches closed stores."""

        orch = self._make_orch_with_mocked_tick(tmp_path)
        orch.startup_cleanup = AsyncMock(
            side_effect=AssertionError("startup ran after shutdown")
        )

        async def _stop_then_run():
            assert await orch.stop() is True
            await orch.run()

        event_loop.run_until_complete(_stop_then_run())
        orch.startup_cleanup.assert_not_awaited()
        assert orch.workflow_job_store._authority_lock_fd == -1

    def test_threadsafe_stop_acknowledges_before_scheduler_loop_exits(
        self,
        tmp_path,
    ):
        """The injected safe-stop task is not cancelled with asyncio.run()."""

        orch = self._make_orch_with_mocked_tick(tmp_path)
        tick_entered = threading.Event()
        stop_drain_entered = threading.Event()
        release_stop_drain = threading.Event()
        thread_errors = []

        async def _brief_tick():
            tick_entered.set()
            await asyncio.sleep(0.05)

        orch._tick = _brief_tick
        original_drain_background_work = orch._drain_background_work

        async def _blocked_stop_drain():
            stop_drain_entered.set()
            await asyncio.to_thread(release_stop_drain.wait)
            await original_drain_background_work()

        orch._drain_background_work = _blocked_stop_drain

        def _run_scheduler():
            try:
                async def _main():
                    asyncio.get_running_loop().set_default_executor(
                        ThreadPoolExecutor(max_workers=1)
                    )
                    await orch.run()

                asyncio.run(_main())
            except BaseException as exc:  # pragma: no cover - asserted below
                thread_errors.append(exc)

        scheduler_thread = threading.Thread(
            target=_run_scheduler,
            name="test-orchestrator-loop",
        )
        scheduler_thread.start()
        try:
            assert tick_entered.wait(2)

            stop_future = orch.stop_threadsafe()
            assert stop_future is not None
            assert stop_drain_entered.wait(2)
            assert stop_future.done() is False
            assert scheduler_thread.is_alive() is True

            release_stop_drain.set()
            stop_future.result(timeout=5)
            scheduler_thread.join(timeout=5)

            assert scheduler_thread.is_alive() is False
            assert stop_future.cancelled() is False
            assert thread_errors == []
            assert orch.workflow_job_store._authority_lock_fd == -1
        finally:
            release_stop_drain.set()
            if scheduler_thread.is_alive():
                future = orch.stop_threadsafe()
                if future is not None:
                    future.result(timeout=5)
                scheduler_thread.join(timeout=5)

    def test_full_sync_loop_posts_full_sync_events(self, tmp_path, event_loop):
        """_full_sync_loop() posts FULL_SYNC events at the configured interval."""
        # The test must wait for the event itself rather than for an elapsed
        # interval.  A busy xdist worker can delay the producer past a fixed
        # sleep even though the loop is behaving correctly.
        orch = _make_orchestrator(tmp_path, config=_make_config(full_sync_interval_ms=50))
        orch._stopping = False

        async def _run_until_events_are_posted():
            sleep_started = asyncio.Event()
            release_sleep = asyncio.Event()
            second_full_sync_posted = asyncio.Event()
            sleep_calls = 0
            full_sync_posts = 0

            async def _delayed_sleep(_interval_s):
                """Hold the producer at its timer until the test releases it."""
                nonlocal sleep_calls
                sleep_calls += 1
                sleep_started.set()
                await release_sleep.wait()
                release_sleep.clear()
                sleep_started.clear()

            original_post_event = orch._post_event

            def _record_full_sync_post(event):
                nonlocal full_sync_posts
                original_post_event(event)
                if event.event_type == DispatchEventType.FULL_SYNC:
                    full_sync_posts += 1
                    if full_sync_posts == 2:
                        second_full_sync_posted.set()

            orch._post_event = _record_full_sync_post
            producer_task = None
            event_task = None
            try:
                # Deliberately delay timer completion so a wall-clock based
                # assertion would run before the producer emits anything.
                with patch(
                    "oompah.orchestrator.asyncio.sleep",
                    new=_delayed_sleep,
                ):
                    producer_task = asyncio.create_task(orch._full_sync_loop())
                    await asyncio.wait_for(sleep_started.wait(), timeout=1.0)

                    event_task = asyncio.create_task(orch._dispatch_queue.get())
                    assert not event_task.done()

                    release_sleep.set()
                    first_event = await asyncio.wait_for(event_task, timeout=1.0)
                    assert first_event.event_type == DispatchEventType.FULL_SYNC

                    # Release one more delayed interval and observe the
                    # second exact emission.  It must coalesce in the queue
                    # because the first event remains pending for dispatch.
                    await asyncio.wait_for(sleep_started.wait(), timeout=1.0)
                    release_sleep.set()
                    await asyncio.wait_for(
                        second_full_sync_posted.wait(),
                        timeout=1.0,
                    )

                assert sleep_calls >= 2
                assert full_sync_posts == 2
                assert orch._dispatch_events_coalesced >= 1
                assert orch._dispatch_queue.empty()
            finally:
                orch._stopping = True
                release_sleep.set()
                if producer_task is not None:
                    producer_task.cancel()
                    await asyncio.gather(producer_task, return_exceptions=True)
                if event_task is not None and not event_task.done():
                    event_task.cancel()
                if event_task is not None:
                    await asyncio.gather(event_task, return_exceptions=True)

        event_loop.run_until_complete(_run_until_events_are_posted())

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
        orch = self._make_orch_with_mocked_tick(
            tmp_path,
            config=_make_config(
                poll_interval_ms=50,  # old interval (should be ignored now)
                full_sync_interval_ms=600000,  # new interval (won't fire in test)
            ),
        )

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
# Shutdown cleanup: executor Futures remain bound to their scheduler loop
# ---------------------------------------------------------------------------

class TestDrainBackgroundWork:
    """Restart cleanup never awaits an asyncio Future from the wrong loop."""

    @pytest.fixture
    def event_loop(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        yield loop
        _close_event_loop_and_executor(loop)

    def _mock_pools(self, orch):
        orch._tick_pool = MagicMock()
        orch._refresh_pool = MagicMock()

    def test_awaits_pending_futures_on_current_loop(self, tmp_path, event_loop):
        orch = _make_orchestrator(tmp_path)
        self._mock_pools(orch)

        async def _drain():
            future = event_loop.create_future()
            orch._maintenance_future = future
            orch._epic_maintenance_future = None
            event_loop.call_soon(future.set_result, None)
            await orch._drain_background_work()

        event_loop.run_until_complete(_drain())

        orch._tick_pool.shutdown.assert_called_once_with(
            wait=True,
            cancel_futures=False,
        )
        orch._refresh_pool.shutdown.assert_called_once_with(
            wait=True,
            cancel_futures=False,
        )

    def test_closed_foreign_loop_future_does_not_block_restart(
        self,
        tmp_path,
        event_loop,
        caplog,
    ):
        orch = _make_orchestrator(tmp_path)
        self._mock_pools(orch)
        foreign_loop = asyncio.new_event_loop()
        foreign_future = foreign_loop.create_future()
        foreign_loop.close()
        orch._maintenance_future = foreign_future
        orch._epic_maintenance_future = None

        event_loop.run_until_complete(orch._drain_background_work())

        assert "closed foreign loop" in caplog.text
        orch._tick_pool.shutdown.assert_called_once_with(
            wait=True,
            cancel_futures=False,
        )
        orch._refresh_pool.shutdown.assert_called_once_with(
            wait=True,
            cancel_futures=False,
        )

    def test_stop_awaits_foreign_restart_recovery_before_retry_mutation(
        self,
        tmp_path,
        event_loop,
    ):
        """Shutdown cancels a sleeping recovery on its owner loop."""

        from oompah.models import Issue

        orch = _make_orchestrator(
            tmp_path,
            config=_make_config(poll_interval_ms=1000),
        )
        self._mock_pools(orch)
        entry = {
            "issue_id": "TASK-stop-recovery",
            "identifier": "TASK-stop-recovery",
            "project_id": "proj-test",
        }
        orch._save_state(restart_issues=[entry])
        orch._quiesced = True
        tracker = MagicMock()
        fetch_count = 0

        def _fetch(_issue_ids):
            nonlocal fetch_count
            fetch_count += 1
            if fetch_count == 1:
                raise RuntimeError("tracker temporarily unavailable")
            return [
                Issue(
                    id=entry["issue_id"],
                    identifier=entry["identifier"],
                    title="Interrupted implementation",
                    state="In Progress",
                    project_id=entry["project_id"],
                )
            ]

        tracker.fetch_issue_states_by_ids.side_effect = _fetch
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch._activate_unpaused_dispatch = MagicMock()
        retry_sleep_started = threading.Event()
        original_sleep = asyncio.sleep

        async def _blocked_retry_sleep(_delay):
            retry_sleep_started.set()
            await original_sleep(60)

        owner_loop = asyncio.new_event_loop()
        owner_loop_started = threading.Event()

        def _run_owner_loop():
            asyncio.set_event_loop(owner_loop)
            owner_loop_started.set()
            try:
                owner_loop.run_forever()
            finally:
                owner_loop.close()

        owner_thread = threading.Thread(target=_run_owner_loop)
        owner_thread.start()
        assert owner_loop_started.wait(timeout=1)

        async def _publish_recovery():
            task = asyncio.create_task(
                orch._recover_restart_issues_for_resume(),
                name="foreign-restart-recovery",
            )
            orch._restart_recovery_task = task
            return task

        foreign_task = None
        try:
            with patch(
                "oompah.orchestrator.asyncio.sleep",
                new=_blocked_retry_sleep,
            ):
                publication = asyncio.run_coroutine_threadsafe(
                    _publish_recovery(),
                    owner_loop,
                )
                foreign_task = publication.result(timeout=3)
                assert retry_sleep_started.wait(timeout=3)
                with orch._provider_admission_lock:
                    orch._stopping = True
                    orch._provider_admission_generation += 1
                event_loop.run_until_complete(orch._drain_background_work())
        finally:
            if owner_loop.is_running():
                owner_loop.call_soon_threadsafe(owner_loop.stop)
            owner_thread.join(timeout=3)

        assert not owner_thread.is_alive()
        assert foreign_task is not None
        assert foreign_task.cancelled()
        assert orch._restart_recovery_task is None
        assert fetch_count == 1
        tracker.update_issue.assert_not_called()
        assert orch._restart_issue_snapshot() == [entry]
        assert orch._quiesced is True
        orch._activate_unpaused_dispatch.assert_not_called()


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


# ---------------------------------------------------------------------------
# Graceful restart: SHUTDOWN event wakes the dispatch loop
# ---------------------------------------------------------------------------

class TestGracefulRestartShutdownEvent:
    """graceful_restart() posts a SHUTDOWN event to wake the idle dispatch loop.

    Regression test for TASK-465.4: When the dispatch queue is idle (no events
    pending), graceful_restart() must still wake the loop so it can check
    _stopping and exit cleanly. Without the SHUTDOWN event, the loop would
    block forever on _dispatch_queue.get() and the old process would not exit.
    """

    @pytest.fixture
    def event_loop(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        yield loop
        _close_event_loop_and_executor(loop)

    def test_shutdown_event_type_exists(self):
        """SHUTDOWN event type is defined in DispatchEventType."""
        assert DispatchEventType.SHUTDOWN == "shutdown"

    def test_graceful_restart_posts_shutdown_event(self, tmp_path, event_loop):
        """graceful_restart() posts a SHUTDOWN event after setting _stopping=True."""
        orch = _make_orchestrator(tmp_path)
        orch._paused = True  # So no agents are started during drain

        event_loop.run_until_complete(
            orch.graceful_restart(drain_timeout_s=1)
        )

        # Check that _stopping and _restart_requested are set
        assert orch._stopping is True
        assert orch._restart_requested is True

        # Check that a SHUTDOWN event was posted to the queue
        events = []
        while not orch._dispatch_queue.empty():
            events.append(orch._dispatch_queue.get_nowait())

        shutdown_events = [
            e for e in events if e.event_type == DispatchEventType.SHUTDOWN
        ]
        assert len(shutdown_events) == 1, (
            f"Expected exactly 1 SHUTDOWN event, got {len(shutdown_events)}"
        )

    def test_run_loop_exits_after_shutdown_event_and_safe_stop_ack(
        self, tmp_path, event_loop
    ):
        """SHUTDOWN wakes an idle loop; safe-stop acknowledgment releases it.

        This is the core regression test: the dispatch loop must not block
        forever on _dispatch_queue.get() when graceful_restart() is called
        while the queue is empty. It also must not exit before the safe-stop
        owner has completed the final resource drain.
        """
        orch = _make_orchestrator(tmp_path, config=_make_config(full_sync_interval_ms=600000))
        orch._tick = AsyncMock()
        _stub_unrelated_run_startup(orch)
        tick_started = asyncio.Event()

        async def _tick():
            tick_started.set()

        orch._tick = AsyncMock(side_effect=_tick)

        async def _run_and_graceful_restart():
            async def _trigger_restart():
                await asyncio.wait_for(tick_started.wait(), timeout=2.0)
                # Call graceful_restart with an undrained running task
                # (simulating a task that didn't finish before the drain timeout)
                await orch.graceful_restart(drain_timeout_s=1)
                await orch.stop_until_safe()

            run_task = asyncio.create_task(orch.run())
            await asyncio.gather(run_task, _trigger_restart())
            return orch._tick.call_count

        tick_count = event_loop.run_until_complete(
            asyncio.wait_for(_run_and_graceful_restart(), timeout=5.0)
        )

        # The loop should have run the startup tick and exited cleanly
        assert tick_count >= 1, "Expected at least startup tick to run"
        # wants_restart should be True after graceful_restart
        assert orch.wants_restart is True, "Expected wants_restart=True after graceful restart"

    def test_graceful_restart_with_undrained_task_persists_once(
        self, tmp_path, event_loop
    ):
        """Undrained tasks are persisted for restart recovery exactly once.

        When graceful_restart() is called with running agents that don't
        finish before the drain timeout, their issue IDs should be saved
        to state for re-dispatch after restart. Calling graceful_restart
        multiple times should not duplicate the persisted entries.
        """
        from oompah.models import RunningEntry, Issue
        from datetime import datetime, timezone

        orch = _make_orchestrator(tmp_path)

        # Add a running task that won't finish
        issue_id = "undrained-issue"
        issue = Issue(
            id=issue_id,
            identifier=issue_id,
            title="Undrained Task",
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
        orch.state.running[issue_id] = entry

        # First graceful_restart call
        event_loop.run_until_complete(
            orch.graceful_restart(drain_timeout_s=0.01)
        )

        # Check state was saved
        state = orch._load_state()
        restart_issues = state.get("restart_issues", [])
        assert len(restart_issues) == 1
        assert restart_issues[0]["issue_id"] == issue_id

        # Clear running state but keep the saved restart_issues
        orch.state.running.clear()

        # Second graceful_restart call (simulating a restart attempt)
        event_loop.run_until_complete(
            orch.graceful_restart(drain_timeout_s=0.01)
        )

        # Check state still has exactly one entry (no duplication)
        state = orch._load_state()
        restart_issues = state.get("restart_issues", [])
        assert len(restart_issues) == 1, (
            f"Expected restart_issues to have exactly 1 entry after second call, "
            f"got {len(restart_issues)}"
        )
        assert restart_issues[0]["issue_id"] == issue_id

    def test_graceful_restart_refuses_replacement_when_state_save_fails(
        self, tmp_path, event_loop
    ):
        """A restart cannot cross the process boundary without durable state."""

        orch = _make_orchestrator(tmp_path)
        with patch.object(orch, "_save_state", return_value=False):
            with pytest.raises(OSError, match="not durably persisted"):
                event_loop.run_until_complete(
                    orch.graceful_restart(drain_timeout_s=0)
                )

        assert orch.wants_restart is False
        assert orch._stopping is False
        assert orch._restart_in_progress is False
        assert orch._quiesced is True

    def test_failed_cutover_unpause_recovers_setup_only_ordinary_worker(
        self, tmp_path, event_loop
    ):
        """The old server owns and reopens work fenced before provider start."""

        from datetime import datetime, timezone
        from oompah.models import Issue, RunningEntry

        orch = _make_orchestrator(tmp_path)
        issue = Issue(
            id="setup-only",
            identifier="TASK-setup-only",
            title="Interrupted ordinary setup",
            state="In Progress",
            project_id="proj-test",
        )
        worker_task = MagicMock()
        worker_task.done.return_value = False
        entry = RunningEntry(
            worker_task=worker_task,
            identifier=issue.identifier,
            issue=issue,
            session=None,
            retry_attempt=0,
            started_at=datetime.now(timezone.utc),
            run_id="ordinary-setup-run",
        )
        orch.state.running[issue.id] = entry
        orch.state.claimed.add(issue.id)
        orch.state.claimed_issues[issue.id] = issue
        tracker_state = {"state": "In Progress"}
        tracker = MagicMock()
        tracker.fetch_issue_states_by_ids.side_effect = lambda _ids: [
            Issue(
                id=issue.id,
                identifier=issue.identifier,
                title=issue.title,
                state=tracker_state["state"],
                project_id=issue.project_id,
            )
        ]
        tracker.update_issue.side_effect = (
            lambda _identifier, *, status: tracker_state.update(state=status)
        )
        orch._tracker_for_project = MagicMock(return_value=tracker)

        orch.quiesce()
        assert orch._provider_launch_blocked(issue, entry.run_id) is True
        assert entry.is_auditor is False
        assert entry.provider_started is False
        assert orch._restart_issue_snapshot()[0]["issue_id"] == issue.id
        real_save_state = orch._save_state

        def fail_cutover_stage(**updates):
            if "paused" in updates and "restart_issues" in updates:
                return False
            return real_save_state(**updates)

        with patch.object(
            orch,
            "_save_state",
            side_effect=fail_cutover_stage,
        ):
            with pytest.raises(OSError, match="not durably persisted"):
                event_loop.run_until_complete(
                    orch.graceful_restart(drain_timeout_s=0)
                )

        async def _resume_and_wait():
            assert orch.unpause() is True
            recovery_owner = orch._restart_recovery_task
            assert recovery_owner is not None
            assert orch._quiesced is True
            await recovery_owner

        event_loop.run_until_complete(_resume_and_wait())

        assert tracker_state["state"] == "Open"
        assert orch._restart_issue_snapshot() == []
        assert orch._quiesced is False
        assert orch.wants_restart is False
        assert entry.authority_revoked is True

    def test_restart_recovery_reopens_only_interrupted_implementation(
        self, tmp_path, event_loop
    ):
        """A genuine In Progress worker is reopened once after restart."""
        from oompah.models import Issue

        orch = _make_orchestrator(tmp_path)
        issue_id = "TASK-restart"
        interrupted = Issue(
            id=issue_id,
            identifier=issue_id,
            title="Interrupted implementation",
            state="In Progress",
        )
        tracker = MagicMock()
        tracker.fetch_issue_states_by_ids.return_value = [interrupted]
        tracker.fetch_issue_detail.return_value = interrupted
        tracker.update_issue.side_effect = lambda _identifier, **fields: setattr(
            interrupted, "state", fields["status"]
        )
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch._save_state(
            restart_issues=[
                {
                    "issue_id": issue_id,
                    "identifier": issue_id,
                    "project_id": "proj-test",
                }
            ]
        )

        event_loop.run_until_complete(orch._recover_restart_issues())
        event_loop.run_until_complete(orch._recover_restart_issues())

        tracker.update_issue.assert_called_once_with(issue_id, status="Open")
        assert orch._load_state().get("restart_issues") == []

    def test_enforce_restart_recovery_uses_durable_single_writer(
        self, tmp_path, event_loop
    ):
        """Enforce startup publishes recovery instead of writing Open directly."""
        from oompah.models import Issue
        from oompah.task_transition_service import issue_authority_version

        orch = _make_orchestrator(tmp_path)
        issue_id = "TASK-durable-restart"
        interrupted = Issue(
            id=issue_id,
            identifier=issue_id,
            title="Interrupted durable implementation",
            state="In Progress",
            project_id="proj-test",
            work_branch=issue_id,
            head_sha="a" * 40,
        )
        tracker = MagicMock()
        tracker.fetch_issue_states_by_ids.return_value = [
            Issue(
                id=issue_id,
                identifier=issue_id,
                title="Interrupted implementation state",
                state="In Progress",
            )
        ]
        tracker.fetch_issue_detail.return_value = interrupted
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch.workflow_runtime = SimpleNamespace(enforce=True)
        orch._schedule_implementation_workflow_event = MagicMock(
            return_value=SimpleNamespace(job_id="recovery-job")
        )
        orch._save_state(
            restart_issues=[
                {
                    "issue_id": issue_id,
                    "identifier": issue_id,
                    "project_id": "proj-test",
                }
            ]
        )

        event_loop.run_until_complete(orch._recover_restart_issues())

        tracker.update_issue.assert_not_called()
        scheduled = orch._schedule_implementation_workflow_event.call_args.kwargs
        assert scheduled["project_id"] == "proj-test"
        assert scheduled["identifier"] == issue_id
        assert scheduled["action"] == "implementation_recovery"
        assert scheduled["payload"]["expected_status"] == "In Progress"
        assert scheduled["expected_evidence_revision"] == issue_authority_version(
            interrupted
        )
        assert scheduled["expected_head_sha"] == "a" * 40
        assert orch._load_state().get("restart_issues") == []

    def test_enforce_restart_recovery_prefers_accepted_submission(
        self, tmp_path, event_loop
    ):
        """Accepted work outranks a generic interrupted-worker recovery."""
        from oompah.models import Issue

        orch = _make_orchestrator(tmp_path)
        issue_id = "TASK-accepted-restart"
        interrupted = Issue(
            id=issue_id,
            identifier=issue_id,
            title="Accepted durable submission",
            state="In Progress",
            project_id="proj-test",
            work_branch=issue_id,
            head_sha="a" * 40,
        )
        tracker = MagicMock()
        tracker.fetch_issue_states_by_ids.return_value = [interrupted]
        tracker.fetch_issue_detail.return_value = interrupted
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch.workflow_runtime = SimpleNamespace(enforce=True)
        accepted_payload = {
            "head_sha": "a" * 40,
            "expected_status": "In Progress",
            "reason": "recover accepted validation submission",
        }
        orch._durable_accepted_implementation_handoff = MagicMock(
            return_value=("validation_submission", accepted_payload)
        )
        orch._schedule_implementation_workflow_event = MagicMock(
            return_value=SimpleNamespace(job_id="submission-job")
        )
        orch._save_state(
            restart_issues=[
                {
                    "issue_id": issue_id,
                    "identifier": issue_id,
                    "project_id": "proj-test",
                }
            ]
        )

        event_loop.run_until_complete(orch._recover_restart_issues())

        scheduled = orch._schedule_implementation_workflow_event.call_args.kwargs
        assert scheduled["action"] == "validation_submission"
        assert scheduled["payload"] == accepted_payload
        assert scheduled["expected_head_sha"] == "a" * 40
        assert orch._load_state().get("restart_issues") == []

    def test_enforce_restart_marker_survives_event_publication_failure(
        self, tmp_path, event_loop
    ):
        from oompah.models import Issue

        orch = _make_orchestrator(tmp_path)
        issue_id = "TASK-recovery-publish-failure"
        tracker = MagicMock()
        detailed = Issue(
            id=issue_id,
            identifier=issue_id,
            title="Interrupted durable implementation",
            state="In Progress",
            project_id="proj-test",
        )
        tracker.fetch_issue_states_by_ids.return_value = [
            Issue(
                id=issue_id,
                identifier=issue_id,
                title="Interrupted implementation state",
                state="In Progress",
            )
        ]
        tracker.fetch_issue_detail.return_value = detailed
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch.workflow_runtime = SimpleNamespace(enforce=True)
        orch._schedule_implementation_workflow_event = MagicMock(
            side_effect=RuntimeError("ledger unavailable")
        )
        marker = {
            "issue_id": issue_id,
            "identifier": issue_id,
            "project_id": "proj-test",
        }
        orch._save_state(restart_issues=[marker])

        event_loop.run_until_complete(orch._recover_restart_issues())

        tracker.update_issue.assert_not_called()
        assert orch._load_state().get("restart_issues") == [marker]

    def test_enforce_legacy_restart_recovery_uses_legacy_project_binding(
        self, tmp_path, event_loop
    ):
        from oompah.models import Issue

        orch = _make_orchestrator(tmp_path)
        issue_id = "TASK-legacy-restart"
        sparse = Issue(
            id=issue_id,
            identifier=issue_id,
            title="Interrupted legacy state",
            state="In Progress",
        )
        detailed = Issue(
            id=issue_id,
            identifier=issue_id,
            title="Interrupted legacy implementation",
            state="In Progress",
        )
        tracker = MagicMock()
        tracker.fetch_issue_states_by_ids.return_value = [sparse]
        tracker.fetch_issue_detail.return_value = detailed
        orch.tracker = tracker
        orch.workflow_runtime = SimpleNamespace(enforce=True)
        orch._schedule_implementation_workflow_event = MagicMock(
            return_value=SimpleNamespace(job_id="legacy-recovery")
        )
        orch._save_state(
            restart_issues=[
                {
                    "issue_id": issue_id,
                    "identifier": issue_id,
                    "project_id": None,
                }
            ]
        )

        event_loop.run_until_complete(orch._recover_restart_issues())

        scheduled = orch._schedule_implementation_workflow_event.call_args.kwargs
        assert scheduled["project_id"] == "legacy"
        assert detailed.project_id == "legacy"
        tracker.update_issue.assert_not_called()
        assert orch._load_state().get("restart_issues") == []

    # Keep real storage, transition-lock, and asyncio.to_thread coverage while
    # allowing bounded scheduler headroom under the saturated xdist gate.
    @pytest.mark.timeout(20)
    @pytest.mark.parametrize(
        "superseding_state",
        ["Merged", "Archived", "In Validation", "Needs Human"],
    )
    @pytest.mark.timeout(20)
    def test_restart_recovery_preserves_superseding_state(
        self, tmp_path, event_loop, superseding_state
    ):
        """Terminal and audit-owned states supersede an old worker record."""
        from oompah.models import Issue

        orch = _make_orchestrator(tmp_path)
        issue_id = "TASK-superseded"
        tracker = MagicMock()
        tracker.fetch_issue_states_by_ids.return_value = [
            Issue(
                id=issue_id,
                identifier=issue_id,
                title="Superseded implementation",
                state=superseding_state,
            )
        ]
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch._save_state(
            restart_issues=[
                {
                    "issue_id": issue_id,
                    "identifier": issue_id,
                    "project_id": "proj-test",
                }
            ]
        )

        event_loop.run_until_complete(orch._recover_restart_issues())

        tracker.update_issue.assert_not_called()
        assert orch._load_state().get("restart_issues") == []

    def test_durable_restart_migration_acks_detailed_superseding_state(
        self, tmp_path, event_loop
    ):
        """A sparse stale row cannot preserve a superseded restart marker."""
        from oompah.models import Issue

        orch = _make_orchestrator(tmp_path)
        issue_id = "TASK-detailed-superseded"
        tracker = MagicMock()
        tracker.fetch_issue_states_by_ids.return_value = [
            Issue(
                id=issue_id,
                identifier=issue_id,
                title="Sparse interrupted implementation",
                state="In Progress",
            )
        ]
        tracker.fetch_issue_detail.return_value = Issue(
            id=issue_id,
            identifier=issue_id,
            title="Superseded detailed implementation",
            state="In Validation",
            project_id="proj-test",
        )
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch.workflow_runtime = SimpleNamespace(mode="shadow")
        orch._schedule_implementation_workflow_event = MagicMock()
        orch._save_state(
            restart_issues=[
                {
                    "issue_id": issue_id,
                    "identifier": issue_id,
                    "project_id": "proj-test",
                }
            ]
        )

        assert event_loop.run_until_complete(orch._recover_restart_issues()) is True

        tracker.update_issue.assert_not_called()
        orch._schedule_implementation_workflow_event.assert_not_called()
        assert orch._load_state().get("restart_issues") == []

    def test_terminal_transition_wins_restart_recovery_lock_race(
        self, tmp_path, event_loop
    ):
        """A terminal write landing before recovery's fenced read wins."""
        from oompah.models import Issue

        orch = _make_orchestrator(tmp_path)
        issue_id = "TASK-race"
        tracker = MagicMock()
        current_state = {"value": "In Progress"}

        def _fetch(_issue_ids):
            return [
                Issue(
                    id=issue_id,
                    identifier=issue_id,
                    title="Racing implementation",
                    state=current_state["value"],
                )
            ]

        tracker.fetch_issue_states_by_ids.side_effect = _fetch
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch._save_state(
            restart_issues=[
                {
                    "issue_id": issue_id,
                    "identifier": issue_id,
                    "project_id": "proj-test",
                }
            ]
        )

        async def _race():
            transition_lock = orch.issue_transition_lock(issue_id)
            await transition_lock.acquire()
            recovery = asyncio.create_task(orch._recover_restart_issues())
            await asyncio.sleep(0)
            current_state["value"] = "Merged"
            transition_lock.release()
            await recovery

        event_loop.run_until_complete(_race())

        tracker.update_issue.assert_not_called()
        assert orch._load_state().get("restart_issues") == []

    def test_restart_recovery_cancellation_keeps_unprocessed_suffix(
        self, tmp_path, event_loop
    ):
        """Each successful row is acked without pre-clearing later rows."""

        from oompah.models import Issue

        orch = _make_orchestrator(tmp_path)
        entries = [
            {
                "issue_id": f"TASK-{number}",
                "identifier": f"TASK-{number}",
                "project_id": "proj-test",
            }
            for number in (1, 2)
        ]
        orch._save_state(restart_issues=entries)
        second_refresh_started = threading.Event()
        release_second_refresh = threading.Event()
        tracker = MagicMock()
        current: dict[str, Issue] = {}

        def fetch(issue_ids):
            issue_id = issue_ids[0]
            if issue_id == "TASK-2":
                second_refresh_started.set()
                assert release_second_refresh.wait(timeout=3)
            return [
                current.setdefault(
                    issue_id,
                    Issue(
                    id=issue_id,
                    identifier=issue_id,
                    title="Interrupted implementation",
                    state="In Progress",
                    project_id="proj-test",
                    ),
                )
            ]

        tracker.fetch_issue_states_by_ids.side_effect = fetch
        tracker.fetch_issue_detail.side_effect = lambda identifier: current.get(
            str(identifier)
        )
        tracker.update_issue.side_effect = lambda identifier, **fields: setattr(
            current[str(identifier)], "state", fields["status"]
        )
        orch._tracker_for_project = MagicMock(return_value=tracker)

        async def cancel_during_second_row():
            recovery = asyncio.create_task(orch._recover_restart_issues())
            await asyncio.to_thread(second_refresh_started.wait)
            recovery.cancel()
            release_second_refresh.set()
            with pytest.raises(asyncio.CancelledError):
                await recovery

        event_loop.run_until_complete(cancel_during_second_row())

        tracker.update_issue.assert_called_once_with("TASK-1", status="Open")
        assert orch._restart_issue_snapshot() == [entries[1]]

    def test_restart_recovery_ack_failure_retains_row_and_quiesces(
        self, tmp_path, event_loop
    ):
        """A successful tracker repair is replayable until its ack commits."""

        from oompah.models import Issue

        orch = _make_orchestrator(tmp_path)
        entry = {
            "issue_id": "TASK-ack",
            "identifier": "TASK-ack",
            "project_id": "proj-test",
        }
        orch._save_state(restart_issues=[entry])
        tracker = MagicMock()
        tracker.fetch_issue_states_by_ids.return_value = [
            Issue(
                id="TASK-ack",
                identifier="TASK-ack",
                title="Already recovered implementation",
                state="Open",
                project_id="proj-test",
            )
        ]
        orch._tracker_for_project = MagicMock(return_value=tracker)

        with patch.object(orch, "_save_state", return_value=False):
            recovered = event_loop.run_until_complete(
                orch._recover_restart_issues()
            )

        assert recovered is False
        assert orch._restart_issue_snapshot() == [entry]
        assert orch._restart_persistence_failed is True
        assert orch._quiesced is True

    def test_running_agents_that_complete_during_drain_are_not_requeued(
        self, tmp_path, event_loop
    ):
        from datetime import datetime, timezone
        from oompah.models import Issue, RunningEntry

        orch = _make_orchestrator(tmp_path)
        for number in range(2):
            issue_id = f"finishes-{number}"
            issue = Issue(
                id=issue_id,
                identifier=issue_id,
                title="Finishes while draining",
                state="In Progress",
            )
            orch.state.running[issue_id] = RunningEntry(
                worker_task=MagicMock(),
                identifier=issue_id,
                issue=issue,
                session=None,
                retry_attempt=0,
                started_at=datetime.now(timezone.utc),
            )

        async def finish_agents(_delay):
            orch.state.running.clear()

        with patch("oompah.orchestrator.asyncio.sleep", side_effect=finish_agents):
            event_loop.run_until_complete(
                orch.graceful_restart(drain_timeout_s=30)
            )

        assert orch._load_state().get("restart_issues", []) == []
        assert orch.wants_restart is True
        assert orch._paused is True


# ---------------------------------------------------------------------------
# _on_retry_timer() resets stale In Progress after retry-claim release
# ---------------------------------------------------------------------------

class TestRetryTimerResetsInProgressOnRelease:
    """TASK-409 regression coverage for retry release cleanup."""

    @pytest.fixture
    def event_loop(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        yield loop
        _close_event_loop_and_executor(loop)

    def _make_retry_orch(self, tmp_path):
        project_store = MagicMock()
        project_store.list_all.return_value = []
        return _make_orchestrator(
            tmp_path,
            config=_make_config(),
            project_store=project_store,
        )

    def _make_retry_entry(self, issue_id: str):
        from oompah.models import RetryEntry
        import time

        return RetryEntry(
            issue_id=issue_id,
            identifier=issue_id,
            attempt=1,
            due_at_ms=time.monotonic() * 1000,
            timer_handle=None,
            error="completed_without_closing",
            escalated_profile="standard",
        )

    def test_resets_in_progress_task_to_open_on_no_longer_candidate(
        self, tmp_path, event_loop
    ):
        from oompah.models import Issue

        orch = self._make_retry_orch(tmp_path)
        issue_id = "TASK-389"
        orch._fetch_all_candidates = MagicMock(return_value=[])

        in_progress_issue = Issue(
            id=issue_id,
            identifier=issue_id,
            title="Observed repro issue",
            state="In Progress",
        )
        orch._fetch_retry_issue = MagicMock(
            return_value=Issue(
                id=issue_id,
                identifier=issue_id,
                title="Completed retry issue",
                state="Done",
            )
        )
        orch._fetch_issue_across_trackers = MagicMock(return_value=in_progress_issue)
        mock_tracker = MagicMock()
        mock_tracker.fetch_issue_detail.return_value = in_progress_issue
        mock_tracker.fetch_issue_states_by_ids.return_value = [in_progress_issue]
        mock_tracker.update_issue.side_effect = lambda _identifier, **fields: setattr(
            in_progress_issue, "state", fields["status"]
        )
        orch._tracker_for_issue = MagicMock(return_value=mock_tracker)

        orch.state.retry_attempts[issue_id] = self._make_retry_entry(issue_id)

        event_loop.run_until_complete(orch._on_retry_timer(issue_id))

        assert issue_id not in orch.state.claimed
        mock_tracker.update_issue.assert_called_once_with(issue_id, status="Open")

    def test_does_not_reset_when_running_agent_exists(
        self, tmp_path, event_loop
    ):
        from oompah.models import Issue

        orch = self._make_retry_orch(tmp_path)
        issue_id = "TASK-123"
        orch._fetch_all_candidates = MagicMock(return_value=[])
        orch._fetch_retry_issue = MagicMock(
            return_value=Issue(
                id=issue_id,
                identifier=issue_id,
                title="Completed retry issue",
                state="Done",
            )
        )
        orch._fetch_issue_across_trackers = MagicMock(
            return_value=Issue(
                id=issue_id,
                identifier=issue_id,
                title="Running issue",
                state="In Progress",
            )
        )
        mock_tracker = MagicMock()
        orch._tracker_for_issue = MagicMock(return_value=mock_tracker)
        running_entry = MagicMock()
        orch.state.running[issue_id] = running_entry
        orch._terminate_running = AsyncMock(return_value=True)
        orch.state.retry_attempts[issue_id] = self._make_retry_entry(issue_id)

        event_loop.run_until_complete(orch._on_retry_timer(issue_id))
        event_loop.run_until_complete(orch._drain_scheduled_terminations())

        mock_tracker.update_issue.assert_not_called()
        orch._terminate_running.assert_awaited_once_with(
            issue_id, False, expected_entry=running_entry
        )

    def test_does_not_reset_when_issue_already_open(
        self, tmp_path, event_loop
    ):
        from oompah.models import Issue

        orch = self._make_retry_orch(tmp_path)
        issue_id = "TASK-200"
        orch._fetch_all_candidates = MagicMock(return_value=[])
        orch._fetch_retry_issue = MagicMock(
            return_value=Issue(
                id=issue_id,
                identifier=issue_id,
                title="Completed retry issue",
                state="Done",
            )
        )
        orch._fetch_issue_across_trackers = MagicMock(
            return_value=Issue(
                id=issue_id,
                identifier=issue_id,
                title="Already open",
                state="Open",
            )
        )
        mock_tracker = MagicMock()
        orch._tracker_for_issue = MagicMock(return_value=mock_tracker)
        orch.state.retry_attempts[issue_id] = self._make_retry_entry(issue_id)

        event_loop.run_until_complete(orch._on_retry_timer(issue_id))

        mock_tracker.update_issue.assert_not_called()

    def test_does_not_reset_when_issue_is_terminal(self, tmp_path, event_loop):
        from oompah.models import Issue

        orch = self._make_retry_orch(tmp_path)
        issue_id = "TASK-300"
        orch._fetch_all_candidates = MagicMock(return_value=[])
        orch._fetch_retry_issue = MagicMock(
            return_value=Issue(
                id=issue_id,
                identifier=issue_id,
                title="Completed retry issue",
                state="Done",
            )
        )
        orch._fetch_issue_across_trackers = MagicMock(
            return_value=Issue(
                id=issue_id,
                identifier=issue_id,
                title="Done issue",
                state="Done",
            )
        )
        mock_tracker = MagicMock()
        orch._tracker_for_issue = MagicMock(return_value=mock_tracker)
        orch.state.retry_attempts[issue_id] = self._make_retry_entry(issue_id)

        event_loop.run_until_complete(orch._on_retry_timer(issue_id))

        mock_tracker.update_issue.assert_not_called()

    def test_tolerates_tracker_error_on_reset(self, tmp_path, event_loop):
        from oompah.models import Issue
        from oompah.tracker import TrackerError

        orch = self._make_retry_orch(tmp_path)
        issue_id = "TASK-ERR"
        orch._fetch_all_candidates = MagicMock(return_value=[])
        orch._fetch_retry_issue = MagicMock(
            return_value=Issue(
                id=issue_id,
                identifier=issue_id,
                title="Completed retry issue",
                state="Done",
            )
        )
        orch._fetch_issue_across_trackers = MagicMock(
            return_value=Issue(
                id=issue_id,
                identifier=issue_id,
                title="Tracker error issue",
                state="In Progress",
            )
        )
        mock_tracker = MagicMock()
        mock_tracker.update_issue.side_effect = TrackerError("tracker boom")
        orch._tracker_for_issue = MagicMock(return_value=mock_tracker)
        orch.state.retry_attempts[issue_id] = self._make_retry_entry(issue_id)

        event_loop.run_until_complete(orch._on_retry_timer(issue_id))

        assert issue_id not in orch.state.claimed

    def test_does_not_reset_when_fetch_returns_none(self, tmp_path, event_loop):
        from oompah.models import Issue

        orch = self._make_retry_orch(tmp_path)
        issue_id = "TASK-GONE"
        orch._fetch_all_candidates = MagicMock(return_value=[])
        orch._fetch_retry_issue = MagicMock(
            return_value=Issue(
                id=issue_id,
                identifier=issue_id,
                title="Completed retry issue",
                state="Done",
            )
        )
        orch._fetch_issue_across_trackers = MagicMock(return_value=None)
        mock_tracker = MagicMock()
        orch._tracker_for_issue = MagicMock(return_value=mock_tracker)
        orch.state.retry_attempts[issue_id] = self._make_retry_entry(issue_id)

        event_loop.run_until_complete(orch._on_retry_timer(issue_id))

        mock_tracker.update_issue.assert_not_called()
