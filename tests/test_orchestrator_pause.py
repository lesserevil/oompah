"""Tests for orchestrator paused state persistence across restarts."""

import asyncio
import json
import os

import pytest

from oompah.config import ServiceConfig
from oompah.orchestrator import Orchestrator


def _make_config() -> ServiceConfig:
    """Create a minimal ServiceConfig for testing."""
    return ServiceConfig()


@pytest.fixture
def event_loop():
    """Provide an event loop for tests that call pause() (which uses asyncio.ensure_future)."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()
    asyncio.set_event_loop(None)


class TestPausedStatePersistence:
    """The paused setting must survive service restarts (umpah-co8)."""

    def test_new_orchestrator_starts_unpaused(self, tmp_path):
        """A fresh orchestrator with no persisted state starts unpaused."""
        state_path = str(tmp_path / "service_state.json")
        orch = Orchestrator(
            config=_make_config(),
            workflow_path="WORKFLOW.md",
            state_path=state_path,
        )
        assert orch.is_paused is False

    def test_pause_persists_to_disk(self, tmp_path, event_loop):
        """Calling pause() writes paused=True to the state file."""
        state_path = str(tmp_path / "service_state.json")
        orch = Orchestrator(
            config=_make_config(),
            workflow_path="WORKFLOW.md",
            state_path=state_path,
        )
        orch.pause()

        # Verify file was written
        assert os.path.exists(state_path)
        with open(state_path) as f:
            data = json.load(f)
        assert data["paused"] is True

    def test_unpause_persists_to_disk(self, tmp_path, event_loop):
        """Calling unpause() writes paused=False to the state file."""
        state_path = str(tmp_path / "service_state.json")
        orch = Orchestrator(
            config=_make_config(),
            workflow_path="WORKFLOW.md",
            state_path=state_path,
        )
        orch.pause()
        orch.unpause()

        with open(state_path) as f:
            data = json.load(f)
        assert data["paused"] is False

    def test_paused_state_survives_restart(self, tmp_path, event_loop):
        """Core bug test: if paused when stopped, must remain paused on restart."""
        state_path = str(tmp_path / "service_state.json")

        # First instance: pause it
        orch1 = Orchestrator(
            config=_make_config(),
            workflow_path="WORKFLOW.md",
            state_path=state_path,
        )
        orch1.pause()
        assert orch1.is_paused is True

        # Simulate restart: create a new Orchestrator with the same state_path
        orch2 = Orchestrator(
            config=_make_config(),
            workflow_path="WORKFLOW.md",
            state_path=state_path,
        )
        # This is the key assertion: paused state must survive the restart
        assert orch2.is_paused is True

    def test_unpaused_state_survives_restart(self, tmp_path, event_loop):
        """After unpausing and restarting, should remain unpaused."""
        state_path = str(tmp_path / "service_state.json")

        orch1 = Orchestrator(
            config=_make_config(),
            workflow_path="WORKFLOW.md",
            state_path=state_path,
        )
        orch1.pause()
        orch1.unpause()
        assert orch1.is_paused is False

        # Restart
        orch2 = Orchestrator(
            config=_make_config(),
            workflow_path="WORKFLOW.md",
            state_path=state_path,
        )
        assert orch2.is_paused is False

    def test_corrupt_state_file_defaults_to_unpaused(self, tmp_path):
        """If the state file is corrupt, default to unpaused (safe fallback)."""
        state_path = str(tmp_path / "service_state.json")
        os.makedirs(os.path.dirname(state_path), exist_ok=True)
        with open(state_path, "w") as f:
            f.write("{invalid json")

        orch = Orchestrator(
            config=_make_config(),
            workflow_path="WORKFLOW.md",
            state_path=state_path,
        )
        assert orch.is_paused is False

    def test_missing_state_file_defaults_to_unpaused(self, tmp_path):
        """If no state file exists, default to unpaused."""
        state_path = str(tmp_path / "nonexistent" / "service_state.json")
        orch = Orchestrator(
            config=_make_config(),
            workflow_path="WORKFLOW.md",
            state_path=state_path,
        )
        assert orch.is_paused is False

    def test_state_file_created_in_subdirectory(self, tmp_path, event_loop):
        """The state file should be created even if parent dirs don't exist."""
        state_path = str(tmp_path / "sub" / "dir" / "service_state.json")
        orch = Orchestrator(
            config=_make_config(),
            workflow_path="WORKFLOW.md",
            state_path=state_path,
        )
        orch.pause()
        assert os.path.exists(state_path)

    def test_snapshot_reflects_persisted_paused_state(self, tmp_path, event_loop):
        """get_snapshot() should reflect the persisted paused state after restart."""
        state_path = str(tmp_path / "service_state.json")

        orch1 = Orchestrator(
            config=_make_config(),
            workflow_path="WORKFLOW.md",
            state_path=state_path,
        )
        orch1.pause()

        # Restart
        orch2 = Orchestrator(
            config=_make_config(),
            workflow_path="WORKFLOW.md",
            state_path=state_path,
        )
        snapshot = orch2.get_snapshot()
        assert snapshot["paused"] is True
