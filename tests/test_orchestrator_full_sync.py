"""Tests for the safety-net full sync feature (oompah-k3d.5).

Verifies that:
- full_sync_interval_ms is configurable via ServiceConfig / workflow front matter
- _last_full_sync is initialised to 0.0 and updated after each tick
- _full_sync_due() returns True when the interval has elapsed or on startup
- reload_config() resets _last_full_sync so the new interval takes effect
- run() logs the safety-net message when the interval elapses
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oompah.config import ServiceConfig
from oompah.epic_workflow_adapter import EpicWorkflowEventRouter
from oompah.events import EventType
from oompah.models import Issue, WorkflowDefinition
from oompah.orchestrator import DispatchEvent, DispatchEventType, Orchestrator
from oompah.workflow_runtime import WorkflowRuntime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(**kwargs) -> ServiceConfig:
    """Return a minimal ServiceConfig, optionally overriding fields."""
    cfg = ServiceConfig()
    for k, v in kwargs.items():
        setattr(cfg, k, v)
    return cfg


def _make_orchestrator(tmp_path, **config_kwargs) -> Orchestrator:
    cfg = _make_config(**config_kwargs)
    return Orchestrator(
        config=cfg,
        workflow_path="WORKFLOW.md",
        state_path=str(tmp_path / "state.json"),
    )


def _stub_unrelated_run_startup(orch: Orchestrator) -> None:
    """Keep run-loop tests out of tracker-backed startup reconciliation."""

    orch._run_terminal_audit_enforcement = MagicMock()
    orch._reconcile_owner_duplicate_resolution_boundaries = MagicMock()
    orch._ensure_integration_audit_lane = MagicMock()
    orch._schedule_terminal_lifecycle_reconciliation = MagicMock()
    orch.startup_cleanup = AsyncMock()
    orch._reconcile_pending_recovery_publications = MagicMock()
    orch._recover_restart_issues = AsyncMock(return_value=True)
    orch._restore_persisted_retries = AsyncMock()
    orch._wake_integration_lane = MagicMock()
    orch.workflow_controller.recover_startup = MagicMock()


# ---------------------------------------------------------------------------
# ServiceConfig: full_sync_interval_ms
# ---------------------------------------------------------------------------

class TestFullSyncIntervalConfig:
    """full_sync_interval_ms defaults and workflow parsing."""

    def test_default_is_300_000ms(self):
        """Default full_sync_interval_ms is 5 minutes (300 000 ms)."""
        cfg = ServiceConfig()
        assert cfg.full_sync_interval_ms == 300_000

    def test_custom_value(self):
        cfg = ServiceConfig(full_sync_interval_ms=600_000)
        assert cfg.full_sync_interval_ms == 600_000

    def test_from_workflow_default(self):
        """When not specified in workflow, from_workflow fallback is 300_000 (5 min)."""
        wf = WorkflowDefinition(config={}, prompt_template="test")
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.full_sync_interval_ms == 300_000

    def test_from_workflow_custom(self, monkeypatch):
        """full_sync_interval_ms can be set via polling section."""
        # Clear the env var so it cannot override the YAML value in the server env.
        monkeypatch.delenv("OOMPAH_FULL_SYNC_INTERVAL_MS", raising=False)
        wf = WorkflowDefinition(
            config={"polling": {"interval_ms": 5000, "full_sync_interval_ms": 600_000}},
            prompt_template="test",
        )
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.full_sync_interval_ms == 600_000

    def test_from_workflow_string_value(self, monkeypatch):
        """Handles string values (YAML may parse numbers as strings)."""
        # Clear the env var so it cannot override the YAML string value in the server env.
        monkeypatch.delenv("OOMPAH_FULL_SYNC_INTERVAL_MS", raising=False)
        wf = WorkflowDefinition(
            config={"polling": {"full_sync_interval_ms": "900000"}},
            prompt_template="test",
        )
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.full_sync_interval_ms == 900_000


# ---------------------------------------------------------------------------
# Orchestrator: _last_full_sync initialisation
# ---------------------------------------------------------------------------

class TestLastFullSyncInit:
    """_last_full_sync starts at 0.0 (never synced)."""

    def test_initial_value_is_zero(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        assert orch._last_full_sync == 0.0


# ---------------------------------------------------------------------------
# Orchestrator: _full_sync_due()
# ---------------------------------------------------------------------------

class TestFullSyncDue:
    """_full_sync_due() returns True/False based on elapsed time."""

    def test_due_on_startup_never_synced(self, tmp_path):
        """First call always returns True (never synced)."""
        orch = _make_orchestrator(tmp_path, full_sync_interval_ms=300_000)
        assert orch._full_sync_due() is True

    def test_not_due_immediately_after_sync(self, tmp_path):
        """Immediately after a full sync the interval hasn't elapsed."""
        orch = _make_orchestrator(tmp_path, full_sync_interval_ms=300_000)
        orch._last_full_sync = time.monotonic()
        assert orch._full_sync_due() is False

    def test_due_after_interval_elapsed(self, tmp_path):
        """Returns True when the interval has fully elapsed."""
        orch = _make_orchestrator(tmp_path, full_sync_interval_ms=300_000)
        # Backdate the last sync by more than the interval
        orch._last_full_sync = time.monotonic() - 301.0  # 301 seconds ago
        assert orch._full_sync_due() is True

    def test_not_due_just_before_interval(self, tmp_path):
        """Returns False just before the interval elapses."""
        orch = _make_orchestrator(tmp_path, full_sync_interval_ms=300_000)
        orch._last_full_sync = time.monotonic() - 299.0  # 299 seconds ago
        assert orch._full_sync_due() is False

    def test_due_exactly_at_interval_boundary(self, tmp_path):
        """Returns True exactly at the interval boundary."""
        orch = _make_orchestrator(tmp_path, full_sync_interval_ms=300_000)
        orch._last_full_sync = time.monotonic() - 300.0  # exactly 300 seconds ago
        assert orch._full_sync_due() is True

    def test_short_interval_respected(self, tmp_path):
        """A very short interval (e.g. 1s) becomes due almost immediately."""
        orch = _make_orchestrator(tmp_path, full_sync_interval_ms=1_000)
        orch._last_full_sync = time.monotonic() - 2.0  # 2 seconds ago
        assert orch._full_sync_due() is True


# ---------------------------------------------------------------------------
# Orchestrator: reload_config() resets _last_full_sync
# ---------------------------------------------------------------------------

class TestReloadConfigResetsSyncTime:
    """reload_config() must reset _last_full_sync so the new interval applies."""

    def test_reload_resets_last_full_sync(self, tmp_path):
        orch = _make_orchestrator(tmp_path, full_sync_interval_ms=300_000)
        # Simulate a recent sync
        orch._last_full_sync = time.monotonic()
        assert orch._full_sync_due() is False  # sanity check

        # Reload with a short interval
        new_cfg = _make_config(full_sync_interval_ms=1_000)
        orch.reload_config(new_cfg, "new template")

        # _last_full_sync reset → sync is due immediately
        assert orch._last_full_sync == 0.0
        assert orch._full_sync_due() is True


# ---------------------------------------------------------------------------
# Orchestrator: run() updates _last_full_sync after each tick
# ---------------------------------------------------------------------------

class TestRunLoopUpdatesSyncTime:
    """run() must set _last_full_sync after every _tick() call."""

    def test_run_updates_last_full_sync(self, tmp_path):
        """After the first tick, _last_full_sync is set to a nonzero value.

        With the event-driven loop, the second tick only fires when a queue
        event arrives, so we post a REFRESH_REQUESTED event after the first
        tick to trigger it.
        """
        orch = _make_orchestrator(tmp_path, poll_interval_ms=50)

        tick_count = 0

        async def _fake_tick():
            nonlocal tick_count
            tick_count += 1
            if tick_count == 1:
                # Post an event so the queue loop fires a second tick
                orch._post_event(DispatchEvent(
                    event_type=DispatchEventType.REFRESH_REQUESTED))
            if tick_count >= 2:
                orch._stopping = True

        orch._tick = _fake_tick
        _stub_unrelated_run_startup(orch)

        assert orch._last_full_sync == 0.0
        asyncio.run(orch.run())
        assert orch._last_full_sync > 0.0

    def test_run_logs_safety_net_message(self, tmp_path, caplog):
        """run() logs an info message when the safety-net interval elapses.

        With the event-driven loop, the second tick only fires when a queue
        event arrives, so we post one after the first tick.
        """
        import logging
        orch = _make_orchestrator(tmp_path, poll_interval_ms=50, full_sync_interval_ms=1_000)

        tick_count = 0

        async def _fake_tick():
            nonlocal tick_count
            tick_count += 1
            if tick_count == 1:
                # Post an event so the queue loop fires a second tick
                orch._post_event(DispatchEvent(
                    event_type=DispatchEventType.REFRESH_REQUESTED))
            if tick_count >= 2:
                orch._stopping = True

        orch._tick = _fake_tick
        _stub_unrelated_run_startup(orch)

        # Simulate an already-elapsed interval (last sync was long ago)
        orch._last_full_sync = time.monotonic() - 2.0

        with caplog.at_level(logging.INFO, logger="oompah.orchestrator"):
            asyncio.run(orch.run())

        assert any("Safety-net full sync triggered" in r.message for r in caplog.records)

    @pytest.mark.parametrize("suffix_processed", (0, 1))
    def test_saturated_runtime_batch_continues_without_full_sync(
        self,
        tmp_path,
        suffix_processed,
    ):
        """The real dispatch loop consumes one coalesced continuation edge."""

        orch = _make_orchestrator(tmp_path, full_sync_interval_ms=600_000)
        async def continue_admission_async():
            orch._stopping = True
            return {
                "admission_only": True,
                "requires_reconcile": False,
                "worker": {
                    "processed": suffix_processed,
                    "batch_saturated": False,
                },
            }

        runtime = SimpleNamespace(
            started=True,
            start=AsyncMock(),
            reconcile_async=AsyncMock(
                return_value={
                    "worker": {"processed": 2, "batch_saturated": True}
                }
            ),
            continue_admission_async=AsyncMock(
                side_effect=continue_admission_async
            ),
            worker=SimpleNamespace(accepting=True, active_count=0),
            pending_operation_count=0,
            drain=AsyncMock(return_value=True),
            close=MagicMock(),
        )
        orch.workflow_runtime = runtime
        _stub_unrelated_run_startup(orch)
        orch._dispatch_audit_lane = AsyncMock(return_value={"pending": 0})
        orch._run_non_lifecycle_housekeeping = MagicMock()
        orch._handle_auto_update = AsyncMock()
        orch._notify_observers = MagicMock()

        asyncio.run(orch.run())

        assert runtime.reconcile_async.await_count == 1
        runtime.continue_admission_async.assert_awaited_once_with()
        assert orch._last_tick_metrics["workflow_admission_only"] is True
        assert orch._dispatch_queue.empty()

    def test_admission_runs_while_ordinary_reconciliation_is_in_flight(
        self, tmp_path
    ):
        """Continuous ordinary traffic cannot strand newly free worker slots."""

        orch = _make_orchestrator(tmp_path, full_sync_interval_ms=600_000)
        reconcile_count = 0
        full_tick_started = asyncio.Event()
        release_full_tick = asyncio.Event()
        admission_ran = asyncio.Event()

        async def reconcile_async():
            nonlocal reconcile_count
            reconcile_count += 1
            if reconcile_count == 1:
                orch._post_event(
                    DispatchEvent(
                        event_type=DispatchEventType.REFRESH_REQUESTED,
                    )
                )
            elif reconcile_count == 2:
                full_tick_started.set()
                await release_full_tick.wait()
            else:
                orch._stopping = True
            return {"worker": {"processed": 0, "batch_saturated": False}}

        async def continue_admission_async():
            admission_ran.set()
            return {
                "admission_only": True,
                "requires_reconcile": False,
                "worker": {"processed": 1, "batch_saturated": False},
            }

        runtime = SimpleNamespace(
            started=True,
            start=AsyncMock(),
            reconcile_async=AsyncMock(side_effect=reconcile_async),
            continue_admission_async=AsyncMock(
                side_effect=continue_admission_async
            ),
            worker=SimpleNamespace(accepting=True, active_count=0),
            pending_operation_count=0,
            drain=AsyncMock(return_value=True),
            close=MagicMock(),
        )
        orch.workflow_runtime = runtime
        _stub_unrelated_run_startup(orch)
        orch._dispatch_audit_lane = AsyncMock(return_value={"pending": 0})
        orch._run_non_lifecycle_housekeeping = MagicMock()
        orch._handle_auto_update = AsyncMock()
        orch._notify_observers = MagicMock()

        async def scenario():
            run_task = asyncio.create_task(orch.run())
            await asyncio.wait_for(full_tick_started.wait(), timeout=2.0)

            # Model ordinary refresh traffic arriving throughout the slow
            # world scan, then an effect completion freeing shared capacity.
            for _ in range(4):
                orch._post_event(
                    DispatchEvent(
                        event_type=DispatchEventType.REFRESH_REQUESTED,
                    )
                )
            assert orch._request_workflow_batch_continuation(
                reason="workflow_effect_completed"
            )

            await asyncio.wait_for(admission_ran.wait(), timeout=2.0)
            assert not release_full_tick.is_set()
            release_full_tick.set()
            await asyncio.wait_for(run_task, timeout=2.0)

        asyncio.run(scenario())

        # The queued ordinary edge still receives a fair full reconciliation
        # after the blocked scan, while admission did not wait for either.
        assert runtime.reconcile_async.await_count == 3
        runtime.continue_admission_async.assert_awaited_once_with()
        assert orch._last_coalesced_event_count == 3
        assert orch._dispatch_queue.empty()

    def test_admission_lane_coalesces_wake_burst_under_one_owner(
        self, tmp_path
    ):
        orch = _make_orchestrator(tmp_path, full_sync_interval_ms=600_000)
        first_admission_started = asyncio.Event()
        release_first_admission = asyncio.Event()
        calls = 0
        active = 0
        maximum_active = 0

        async def continue_admission_async():
            nonlocal active, calls, maximum_active
            calls += 1
            active += 1
            maximum_active = max(maximum_active, active)
            if calls == 1:
                first_admission_started.set()
                await release_first_admission.wait()
            active -= 1
            return {
                "admission_only": True,
                "requires_reconcile": False,
                "worker": {"processed": 0, "batch_saturated": False},
            }

        runtime = SimpleNamespace(
            continue_admission_async=AsyncMock(
                side_effect=continue_admission_async
            ),
            worker=SimpleNamespace(accepting=True, active_count=0),
        )
        orch.workflow_runtime = runtime
        orch._notify_observers = MagicMock()

        async def scenario():
            orch._dispatch_loop = asyncio.get_running_loop()
            orch._wake_workflow_admission_lane_on_loop()
            first_owner = orch._workflow_admission_future
            await asyncio.wait_for(first_admission_started.wait(), timeout=2.0)

            for _ in range(10):
                orch._wake_workflow_admission_lane_on_loop()
                assert orch._workflow_admission_future is first_owner

            release_first_admission.set()
            assert first_owner is not None
            await asyncio.wait_for(first_owner, timeout=2.0)

        asyncio.run(scenario())

        assert calls == 2
        assert maximum_active == 1

    def test_completion_wake_survives_admission_owner_exit_and_claims_suffix(
        self, tmp_path
    ):
        """A wake retained by an exiting owner starts exactly one successor."""

        orch = _make_orchestrator(tmp_path, full_sync_interval_ms=600_000)
        first_owner_started = asyncio.Event()
        release_first_owner = asyncio.Event()
        current_job_claimed = asyncio.Event()
        queued = ["CURRENT-JOB"]
        claims = []

        async def continue_admission_async():
            if queued:
                claims.append(queued.pop(0))
                current_job_claimed.set()
            return {
                "admission_only": True,
                "requires_reconcile": False,
                "worker": {"processed": len(claims), "batch_saturated": False},
            }

        runtime = SimpleNamespace(
            continue_admission_async=AsyncMock(
                side_effect=continue_admission_async
            ),
            worker=SimpleNamespace(accepting=True, active_count=0),
        )
        orch.workflow_runtime = runtime
        orch._notify_observers = MagicMock()
        production_lane = orch._run_workflow_admission_lane

        async def owner_already_exiting():
            first_owner_started.set()
            await release_first_owner.wait()

        async def scenario():
            orch._dispatch_loop = asyncio.get_running_loop()
            orch._run_workflow_admission_lane = owner_already_exiting
            orch._wake_workflow_admission_lane_on_loop()
            first_owner = orch._workflow_admission_future
            assert first_owner is not None
            await asyncio.wait_for(first_owner_started.wait(), timeout=2.0)

            # Model a superseded invocation completing after this owner chose
            # its exit path but before its Task became observably done.
            for _ in range(8):
                orch._wake_workflow_admission_lane_on_loop()
            assert orch._workflow_admission_future is first_owner
            assert orch._workflow_admission_wake_pending is True

            orch._run_workflow_admission_lane = production_lane
            release_first_owner.set()
            await asyncio.wait_for(current_job_claimed.wait(), timeout=2.0)
            successor = orch._workflow_admission_future
            if successor is not None:
                await asyncio.wait_for(asyncio.shield(successor), timeout=2.0)
            await asyncio.sleep(0)

        asyncio.run(scenario())

        assert claims == ["CURRENT-JOB"]
        assert runtime.continue_admission_async.await_count == 1
        assert orch._workflow_admission_future is None
        assert orch._workflow_admission_wake_pending is False

    def test_stale_admission_owner_callback_cannot_clear_new_owner(
        self, tmp_path, caplog
    ):
        orch = _make_orchestrator(tmp_path, full_sync_interval_ms=600_000)

        async def scenario():
            release_new_owner = asyncio.Event()

            async def failed_old_owner():
                raise RuntimeError("stale admission owner failed")

            old_owner = asyncio.create_task(failed_old_owner())
            await asyncio.sleep(0)
            assert old_owner.done()
            new_owner = asyncio.create_task(release_new_owner.wait())
            orch._workflow_admission_future = new_owner

            with caplog.at_level(logging.ERROR, logger="oompah.orchestrator"):
                orch._workflow_admission_lane_finished(old_owner)

            assert orch._workflow_admission_future is new_owner
            release_new_owner.set()
            await new_owner

        asyncio.run(scenario())

        assert any(
            "Durable workflow admission lane failed" in record.message
            and record.exc_info is not None
            and isinstance(record.exc_info[1], RuntimeError)
            for record in caplog.records
        )

    def test_foreign_thread_completion_wake_claims_one_current_job(
        self, tmp_path
    ):
        orch = _make_orchestrator(tmp_path, full_sync_interval_ms=600_000)
        claimed = asyncio.Event()
        calls = 0

        async def continue_admission_async():
            nonlocal calls
            calls += 1
            claimed.set()
            return {
                "admission_only": True,
                "requires_reconcile": False,
                "worker": {"processed": 1, "batch_saturated": False},
            }

        runtime = SimpleNamespace(
            continue_admission_async=AsyncMock(
                side_effect=continue_admission_async
            ),
            worker=SimpleNamespace(accepting=True, active_count=0),
        )
        orch.workflow_runtime = runtime
        orch._notify_observers = MagicMock()

        async def scenario():
            orch._dispatch_loop = asyncio.get_running_loop()
            wake = threading.Thread(target=orch._wake_workflow_admission_lane)
            wake.start()
            await asyncio.to_thread(wake.join, 2)
            assert not wake.is_alive()
            await asyncio.wait_for(claimed.wait(), timeout=2.0)
            owner = orch._workflow_admission_future
            if owner is not None:
                await asyncio.wait_for(asyncio.shield(owner), timeout=2.0)
            await asyncio.sleep(0)

        asyncio.run(scenario())

        assert calls == 1
        assert orch._workflow_admission_future is None
        assert orch._workflow_admission_wake_pending is False

    @pytest.mark.parametrize("fence", ("_paused", "_quiesced"))
    def test_completion_wake_handoff_respects_lifecycle_fence(
        self, tmp_path, fence
    ):
        orch = _make_orchestrator(tmp_path, full_sync_interval_ms=600_000)
        owner_started = asyncio.Event()
        release_owner = asyncio.Event()
        runtime = SimpleNamespace(
            continue_admission_async=AsyncMock(),
            worker=SimpleNamespace(accepting=True, active_count=0),
        )
        orch.workflow_runtime = runtime

        async def owner_already_exiting():
            owner_started.set()
            await release_owner.wait()

        async def scenario():
            orch._dispatch_loop = asyncio.get_running_loop()
            orch._run_workflow_admission_lane = owner_already_exiting
            orch._wake_workflow_admission_lane_on_loop()
            owner = orch._workflow_admission_future
            assert owner is not None
            await asyncio.wait_for(owner_started.wait(), timeout=2.0)
            orch._wake_workflow_admission_lane_on_loop()
            setattr(orch, fence, True)
            release_owner.set()
            await asyncio.wait_for(asyncio.shield(owner), timeout=2.0)
            await asyncio.sleep(0)

        asyncio.run(scenario())

        runtime.continue_admission_async.assert_not_awaited()
        assert orch._workflow_admission_future is None
        assert orch._workflow_admission_wake_pending is False

    @pytest.mark.parametrize("fence", ("_paused", "_quiesced"))
    def test_admission_lane_respects_pause_and_quiesce_fences(
        self, tmp_path, fence
    ):
        orch = _make_orchestrator(tmp_path, full_sync_interval_ms=600_000)
        runtime = SimpleNamespace(
            continue_admission_async=AsyncMock(),
            worker=SimpleNamespace(accepting=True, active_count=0),
        )
        orch.workflow_runtime = runtime
        setattr(orch, fence, True)

        async def scenario():
            orch._dispatch_loop = asyncio.get_running_loop()
            orch._wake_workflow_admission_lane_on_loop()
            await asyncio.sleep(0)

        asyncio.run(scenario())

        assert orch._workflow_admission_future is None
        runtime.continue_admission_async.assert_not_awaited()

    @pytest.mark.parametrize("fence", ("_paused", "_quiesced", "draining"))
    def test_effect_exit_refreshes_state_while_admission_is_fenced(
        self, tmp_path, fence
    ):
        orch = _make_orchestrator(tmp_path, full_sync_interval_ms=600_000)
        production_runtime = WorkflowRuntime.from_orchestrator(
            orch,
            state_dir=tmp_path / f"completion-state-{fence}",
        )
        orch.workflow_runtime = production_runtime
        orch._notify_state_only = MagicMock()
        continuation = MagicMock(
            wraps=orch._request_workflow_batch_continuation
        )
        orch._request_workflow_batch_continuation = continuation
        if fence == "draining":
            production_runtime._draining = True
            production_runtime.worker._accepting = False
        else:
            setattr(orch, fence, True)

        async def completed_result():
            return SimpleNamespace(job_id="completed-while-fenced")

        async def scenario():
            effect = asyncio.create_task(completed_result())
            with production_runtime._lock:
                production_runtime._effect_tasks[effect] = "shared"
            effect.add_done_callback(production_runtime._effect_finished)
            await effect
            await asyncio.sleep(0)

        asyncio.run(scenario())

        orch._notify_state_only.assert_called_once_with()
        continuation.assert_called_once_with(reason="workflow_effect_completed")
        assert orch._workflow_admission_future is None
        assert production_runtime.health_snapshot()["worker"]["retained"] == 0
        production_runtime.close()

    def test_state_refresh_failure_cannot_suppress_completion_wake(
        self, tmp_path
    ):
        orch = _make_orchestrator(tmp_path, full_sync_interval_ms=600_000)
        production_runtime = WorkflowRuntime.from_orchestrator(
            orch,
            state_dir=tmp_path / "completion-state-failure",
        )
        orch.workflow_runtime = production_runtime
        orch._notify_state_only = MagicMock(
            side_effect=RuntimeError("state publication failed")
        )
        continuation = MagicMock(return_value=True)
        orch._request_workflow_batch_continuation = continuation

        async def completed_result():
            return SimpleNamespace(job_id="completed-after-state-failure")

        async def scenario():
            effect = asyncio.create_task(completed_result())
            with production_runtime._lock:
                production_runtime._effect_tasks[effect] = "shared"
            effect.add_done_callback(production_runtime._effect_finished)
            await effect
            await asyncio.sleep(0)

        asyncio.run(scenario())

        orch._notify_state_only.assert_called_once_with()
        continuation.assert_called_once_with(reason="workflow_effect_completed")
        assert production_runtime.health_snapshot()["worker"]["retained"] == 0
        production_runtime.close()

    def test_transition_completions_keep_fast_admission_until_empty(
        self, tmp_path
    ):
        """Production transition/completion callbacks share one fast wake."""

        orch = _make_orchestrator(tmp_path, full_sync_interval_ms=600_000)
        production_runtime = WorkflowRuntime.from_orchestrator(
            orch,
            state_dir=tmp_path / "production-callbacks",
        )
        orch.request_refresh = MagicMock()
        request_continuation = MagicMock(
            wraps=orch._request_workflow_batch_continuation
        )
        orch._request_workflow_batch_continuation = request_continuation
        observed_events = []

        def observe_event(event, payload):
            observed_events.append((event, dict(payload)))

        parent = Issue(
            id="EPIC-1",
            identifier="EPIC-1",
            title="epic",
            description="fixture",
            state="In Progress",
            issue_type="epic",
            project_id="legacy",
        )
        children = [
            Issue(
                id=f"TASK-{index}",
                identifier=f"TASK-{index}",
                title="child",
                description="fixture",
                state="Done",
                issue_type="task",
                project_id="legacy",
                parent_id=parent.identifier,
            )
            for index in (1, 2)
        ]

        class TransitionTracker:
            issues = {
                issue.identifier: issue for issue in (parent, *children)
            }

            def fetch_issue_detail(self, identifier):
                return self.issues.get(identifier)

        epic_controller = MagicMock()
        epic_controller.scheduler = MagicMock()
        router_runtime = SimpleNamespace(
            enforce=True,
            project_bindings={
                "legacy": SimpleNamespace(
                    tracker=TransitionTracker(),
                    epic_controller=epic_controller,
                )
            },
        )
        event_router = EpicWorkflowEventRouter(orch, router_runtime)
        event_router._schedule_current_decision = MagicMock(return_value=0)
        orch.event_bus.subscribe(EventType.ISSUE_STATE_CHANGED, observe_event)
        orch.event_bus.subscribe(
            EventType.ISSUE_STATE_CHANGED,
            event_router.on_issue_changed,
        )
        reconcile_count = 0
        admission_count = 0

        async def reconcile_async():
            nonlocal reconcile_count
            reconcile_count += 1
            if reconcile_count == 2:
                orch._stopping = True
            return {
                "worker": {
                    "processed": 2 if reconcile_count == 1 else 0,
                    "batch_saturated": reconcile_count == 1,
                }
            }

        async def completed_result(job_id):
            return SimpleNamespace(job_id=job_id)

        async def continue_admission_async():
            nonlocal admission_count
            admission_count += 1
            if admission_count <= 2:
                job = SimpleNamespace(
                    job_id=f"job-{admission_count}",
                    project_id="legacy",
                    task_id=f"TASK-{admission_count}",
                    action="implementation_dispatch",
                )
                production_runtime.record_event("transition_applied", job)
                event_router.drain_events(timeout=5.0)
                await asyncio.sleep(0)
                completion = asyncio.create_task(completed_result(job.job_id))
                with production_runtime._lock:
                    production_runtime._effect_tasks[completion] = "shared"
                await completion
                production_runtime._effect_finished(completion)
                return {
                    "admission_only": True,
                    "requires_reconcile": False,
                    "worker": {
                        "processed": 1,
                        "batch_saturated": False,
                    },
                }
            return {
                "admission_only": True,
                "requires_reconcile": True,
                "reason": "published workflow queue drained",
            }

        runtime = SimpleNamespace(
            started=True,
            start=AsyncMock(),
            reconcile_async=AsyncMock(side_effect=reconcile_async),
            continue_admission_async=AsyncMock(
                side_effect=continue_admission_async
            ),
            worker=SimpleNamespace(accepting=True, active_count=0),
            pending_operation_count=0,
            drain=AsyncMock(return_value=True),
            close=MagicMock(),
        )
        orch.workflow_runtime = runtime
        _stub_unrelated_run_startup(orch)
        orch._dispatch_audit_lane = AsyncMock(return_value={"pending": 0})
        orch._run_non_lifecycle_housekeeping = MagicMock()
        orch._handle_auto_update = AsyncMock()
        orch._notify_observers = MagicMock()
        retained_at_state_refresh = []
        orch._notify_state_only = lambda: retained_at_state_refresh.append(
            production_runtime.health_snapshot()["worker"]["retained"]
        )

        try:
            asyncio.run(orch.run())
        finally:
            event_router.close()
            production_runtime.close()

        assert runtime.reconcile_async.await_count == 2
        assert runtime.continue_admission_async.await_count == 3
        assert retained_at_state_refresh == [0, 0]
        assert observed_events == [
            (
                EventType.ISSUE_STATE_CHANGED,
                {
                    "project_id": "legacy",
                    "identifier": f"TASK-{index}",
                    "change": "durable-workflow-transition-applied",
                },
            )
            for index in (1, 2)
        ]
        assert orch.request_refresh.call_count == 0
        continuation_reasons = [
            call.kwargs.get("reason")
            for call in request_continuation.call_args_list
        ]
        assert continuation_reasons.count(None) == 1
        assert continuation_reasons.count("workflow_transition_applied") == 2
        assert continuation_reasons.count("workflow_effect_completed") == 2
        assert (
            continuation_reasons.count(
                "epic_workflow_event:issue-state-changed"
            )
            == 4
        )
        assert epic_controller.schedule_action.call_count == 4
        # Completion/transition wake bursts coalesce on the independent lane;
        # they do not inflate or occupy the ordinary dispatch-event queue.
        assert orch._dispatch_events_coalesced == 0
        assert orch._last_coalesced_event_count == 0
        assert orch._dispatch_queue.empty()

    def test_stale_admission_cut_falls_back_to_one_world_reconcile(
        self, tmp_path
    ):
        orch = _make_orchestrator(tmp_path, full_sync_interval_ms=600_000)
        reconcile_count = 0

        async def reconcile_async():
            nonlocal reconcile_count
            reconcile_count += 1
            if reconcile_count == 2:
                orch._stopping = True
            return {
                "worker": {
                    "processed": 2 if reconcile_count == 1 else 0,
                    "batch_saturated": reconcile_count == 1,
                }
            }

        runtime = SimpleNamespace(
            started=True,
            start=AsyncMock(),
            reconcile_async=AsyncMock(side_effect=reconcile_async),
            continue_admission_async=AsyncMock(
                return_value={
                    "admission_only": True,
                    "requires_reconcile": True,
                    "reason": "workflow admission cut is stale",
                }
            ),
            worker=SimpleNamespace(accepting=True, active_count=0),
            pending_operation_count=0,
            drain=AsyncMock(return_value=True),
            close=MagicMock(),
        )
        orch.workflow_runtime = runtime
        _stub_unrelated_run_startup(orch)
        orch._dispatch_audit_lane = AsyncMock(return_value={"pending": 0})
        orch._run_non_lifecycle_housekeeping = MagicMock()
        orch._handle_auto_update = AsyncMock()
        orch._notify_observers = MagicMock()

        asyncio.run(orch.run())

        runtime.continue_admission_async.assert_awaited_once_with()
        assert runtime.reconcile_async.await_count == 2
        assert orch._dispatch_queue.empty()


# ---------------------------------------------------------------------------
# Orchestrator: _full_sync_due() with various interval values
# ---------------------------------------------------------------------------

class TestFullSyncDueIntervalVariants:
    """Parametrised checks for _full_sync_due() with different intervals."""

    @pytest.mark.parametrize("interval_ms,elapsed_s,expected", [
        (300_000, 0.0, False),       # just synced, not due
        (300_000, 299.9, False),     # just under 5 min
        (300_000, 300.0, True),      # exactly at 5 min
        (300_000, 400.0, True),      # over 5 min
        (600_000, 300.0, False),     # 10 min interval, only 5 min elapsed
        (600_000, 600.0, True),      # 10 min interval, exactly elapsed
        (60_000,  59.9, False),      # 1 min interval, just under
        (60_000,  60.0, True),       # 1 min interval, exactly elapsed
    ])
    def test_parametrised(self, tmp_path, interval_ms, elapsed_s, expected):
        orch = _make_orchestrator(tmp_path, full_sync_interval_ms=interval_ms)
        now = 1_000.0
        orch._last_full_sync = now - elapsed_s
        with patch("oompah.orchestrator.time.monotonic", return_value=now):
            assert orch._full_sync_due() is expected
