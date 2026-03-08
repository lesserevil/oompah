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
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oompah.config import ServiceConfig
from oompah.models import WorkflowDefinition
from oompah.orchestrator import Orchestrator


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
        """When not specified in workflow, default is used."""
        wf = WorkflowDefinition(config={}, prompt_template="test")
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.full_sync_interval_ms == 300_000

    def test_from_workflow_custom(self):
        """full_sync_interval_ms can be set via polling section."""
        wf = WorkflowDefinition(
            config={"polling": {"interval_ms": 5000, "full_sync_interval_ms": 600_000}},
            prompt_template="test",
        )
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.full_sync_interval_ms == 600_000

    def test_from_workflow_string_value(self):
        """Handles string values (YAML may parse numbers as strings)."""
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
        from oompah.orchestrator import DispatchEvent, DispatchEventType

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
        orch.startup_cleanup = AsyncMock()
        orch._recover_restart_issues = AsyncMock()

        assert orch._last_full_sync == 0.0
        asyncio.run(orch.run())
        assert orch._last_full_sync > 0.0

    def test_run_logs_safety_net_message(self, tmp_path, caplog):
        """run() logs an info message when the safety-net interval elapses.

        With the event-driven loop, the second tick only fires when a queue
        event arrives, so we post one after the first tick.
        """
        import logging
        from oompah.orchestrator import DispatchEvent, DispatchEventType

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
        orch.startup_cleanup = AsyncMock()
        orch._recover_restart_issues = AsyncMock()

        # Simulate an already-elapsed interval (last sync was long ago)
        orch._last_full_sync = time.monotonic() - 2.0

        with caplog.at_level(logging.INFO, logger="oompah.orchestrator"):
            asyncio.run(orch.run())

        assert any("Safety-net full sync triggered" in r.message for r in caplog.records)


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
        orch._last_full_sync = time.monotonic() - elapsed_s
        assert orch._full_sync_due() is expected
