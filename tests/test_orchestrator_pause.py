"""Tests for orchestrator paused state persistence across restarts."""

import asyncio
import json
import os
import threading

import pytest
from starlette.requests import Request

from oompah.config import ServiceConfig
from oompah.orchestrator import Orchestrator
from oompah import server
from oompah.server import (
    AuthenticatedPrincipal,
    _AUTH_PRINCIPAL_SCOPE_CAPABILITY,
)


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

    def test_authenticated_pause_provenance_survives_restart(
        self, tmp_path, event_loop
    ):
        state_path = str(tmp_path / "service_state.json")
        orch = Orchestrator(
            config=_make_config(),
            workflow_path="WORKFLOW.md",
            state_path=state_path,
        )

        orch.pause(
            actor="project-owner",
            source="ui",
            request_id="request-123",
        )
        restarted = Orchestrator(
            config=_make_config(),
            workflow_path="WORKFLOW.md",
            state_path=state_path,
        )

        record = restarted.get_snapshot()["scheduling_control_history"][0]
        assert record == {
            "version": 1,
            "recorded_at": record["recorded_at"],
            "scope": "orchestrator",
            "action": "pause",
            "previous_paused": False,
            "new_paused": True,
            "changed": True,
            "actor": "project-owner",
            "source": "ui",
            "request_id": "request-123",
        }

    def test_pause_provenance_sanitizes_credentials(self, tmp_path, event_loop):
        state_path = str(tmp_path / "service_state.json")
        orch = Orchestrator(
            config=_make_config(),
            workflow_path="WORKFLOW.md",
            state_path=state_path,
        )

        orch.pause(
            actor="owner bearer secret-token",
            source="api\nAuthorization: secret-token",
            request_id="req secret-token",
        )

        persisted = (tmp_path / "service_state.json").read_text(encoding="utf-8")
        assert "secret-token" not in persisted
        record = orch.get_snapshot()["scheduling_control_history"][0]
        assert "secret-token" not in record["actor"]
        assert "secret-token" not in record["source"]
        assert "secret-token" not in record["request_id"]

    def test_global_pause_endpoint_uses_authenticated_principal(
        self, tmp_path, event_loop
    ):
        state_path = str(tmp_path / "service_state.json")
        orch = Orchestrator(
            config=_make_config(),
            workflow_path="WORKFLOW.md",
            state_path=state_path,
        )
        principal = AuthenticatedPrincipal(
            username="http-operator",
            actor_login="project-owner",
            source="basic",
        )
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/orchestrator/pause",
            "headers": [
                (b"x-oompah-request-source", b"ui"),
                (b"x-request-id", b"pause-request-1"),
            ],
            _AUTH_PRINCIPAL_SCOPE_CAPABILITY: principal,
        }
        request = Request(scope)
        original = server._orchestrator
        server._orchestrator = orch
        try:
            response = event_loop.run_until_complete(
                server.api_orchestrator_pause(request)
            )
        finally:
            server._orchestrator = original

        assert response.status_code == 200
        record = orch.get_snapshot()["scheduling_control_history"][0]
        assert record["actor"] == "project-owner"
        assert record["source"] == "ui"
        assert record["request_id"] == "pause-request-1"

    def test_quiesce_does_not_persist_operator_pause_or_terminate_workers(
        self, tmp_path
    ):
        """Cutover quiesce preserves active workers and explicit pause state."""
        from datetime import datetime, timezone

        from oompah.models import Issue, RunningEntry

        state_path = str(tmp_path / "service_state.json")
        orch = Orchestrator(
            config=_make_config(),
            workflow_path="WORKFLOW.md",
            state_path=state_path,
        )
        issue_id = "quiesced-worker"
        orch.state.running[issue_id] = RunningEntry(
            worker_task=None,
            identifier=issue_id,
            issue=Issue(
                id=issue_id,
                identifier=issue_id,
                title="Drain me naturally",
                state="In Progress",
            ),
            session=None,
            retry_attempt=0,
            started_at=datetime.now(timezone.utc),
        )

        orch.quiesce()

        assert orch._quiesced is True
        assert orch.is_paused is False
        assert issue_id in orch.state.running
        assert orch._load_state().get("paused", False) is False

    def test_explicit_pause_still_marks_operator_pause(self, tmp_path, event_loop):
        """The destructive operator pause contract remains unchanged."""
        from unittest.mock import AsyncMock

        orch = Orchestrator(
            config=_make_config(),
            workflow_path="WORKFLOW.md",
            state_path=str(tmp_path / "service_state.json"),
        )
        terminate = AsyncMock()
        orch._terminate_all_running = terminate

        async def invoke_pause():
            orch.pause()
            await asyncio.sleep(0)

        event_loop.run_until_complete(invoke_pause())

        assert orch.is_paused is True
        terminate.assert_awaited_once_with()

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

    def test_corrupt_state_file_is_not_overwritten(self, tmp_path, caplog):
        """A later state update must preserve unreadable evidence for recovery."""
        state_path = tmp_path / "service_state.json"
        corrupt = b'{"paused": tru'
        state_path.write_bytes(corrupt)
        orch = Orchestrator(
            config=_make_config(),
            workflow_path="WORKFLOW.md",
            state_path=str(state_path),
        )

        orch._save_state(maintenance_cursors={"cleanup": "TASK-1"})

        assert state_path.read_bytes() == corrupt
        assert "Refusing to overwrite unreadable service state" in caplog.text

    def test_terminal_audit_load_detects_corruption_after_startup(self, tmp_path):
        state_path = tmp_path / "service_state.json"
        state_path.write_text("{}\n", encoding="utf-8")
        orch = Orchestrator(
            config=_make_config(),
            workflow_path="WORKFLOW.md",
            state_path=str(state_path),
        )
        state_path.write_text("not-json", encoding="utf-8")

        with pytest.raises(ValueError, match="service state is unreadable"):
            orch._load_state_for_terminal_audit()

        assert orch._state_load_failed is True

    def test_concurrent_state_updates_are_serialized_and_merged(
        self, tmp_path, monkeypatch
    ):
        """Concurrent writers cannot observe or publish a partial document."""
        state_path = tmp_path / "service_state.json"
        state_path.write_text("{}\n", encoding="utf-8")
        orch = Orchestrator(
            config=_make_config(),
            workflow_path="WORKFLOW.md",
            state_path=str(state_path),
        )
        real_dump = json.dump
        first_dump_entered = threading.Event()
        second_dump_entered = threading.Event()
        release_first_dump = threading.Event()
        dump_calls = 0
        dump_calls_lock = threading.Lock()

        def controlled_dump(data, handle, *args, **kwargs):
            nonlocal dump_calls
            with dump_calls_lock:
                dump_calls += 1
                call_number = dump_calls
            if call_number == 1:
                first_dump_entered.set()
                assert release_first_dump.wait(timeout=2)
            else:
                second_dump_entered.set()
            return real_dump(data, handle, *args, **kwargs)

        monkeypatch.setattr("oompah.orchestrator.json.dump", controlled_dump)
        errors: list[BaseException] = []

        def write(key: str) -> None:
            try:
                orch._save_state(**{key: True})
            except BaseException as exc:  # pragma: no cover - asserted below
                errors.append(exc)

        first = threading.Thread(target=write, args=("first",))
        second = threading.Thread(target=write, args=("second",))
        first.start()
        assert first_dump_entered.wait(timeout=2)
        second.start()
        serialized = not second_dump_entered.wait(timeout=0.25)
        release_first_dump.set()
        first.join(timeout=2)
        second.join(timeout=2)

        assert serialized, "second writer entered while the first write was incomplete"
        assert not first.is_alive()
        assert not second.is_alive()
        assert errors == []
        assert json.loads(state_path.read_text(encoding="utf-8")) == {
            "first": True,
            "second": True,
        }
        assert list(tmp_path.glob(".service_state.json.*.tmp")) == []

    def test_serialization_failure_preserves_last_valid_state(self, tmp_path):
        state_path = tmp_path / "service_state.json"
        original = '{"paused": true}\n'
        state_path.write_text(original, encoding="utf-8")
        orch = Orchestrator(
            config=_make_config(),
            workflow_path="WORKFLOW.md",
            state_path=str(state_path),
        )

        orch._save_state(unserializable=object())

        assert state_path.read_text(encoding="utf-8") == original
        assert list(tmp_path.glob(".service_state.json.*.tmp")) == []

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


# ---------------------------------------------------------------------------
# Graceful-restart pause preservation. Covers oompah-zlz_2-znn / zcu trust
# concern: graceful_restart used to unconditionally write paused=False to
# the state file, silently undoing a user-set pause.
# ---------------------------------------------------------------------------

class TestGracefulRestartPreservesUserPause:
    def test_user_pause_survives_graceful_restart(self, tmp_path):
        """If the user paused before triggering graceful_restart, the new
        boot must still be paused."""
        state_path = str(tmp_path / "service_state.json")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            orch = Orchestrator(
                config=_make_config(),
                workflow_path="WORKFLOW.md",
                state_path=state_path,
            )
            orch.pause()  # User pauses
            assert orch.is_paused is True

            # Now trigger graceful_restart — drain budget tiny so it returns fast.
            loop.run_until_complete(orch.graceful_restart(drain_timeout_s=0.1))
        finally:
            loop.close()
            asyncio.set_event_loop(None)

        # Persisted state must still report paused=True so the new boot
        # picks it up.
        with open(state_path) as f:
            data = json.load(f)
        assert data["paused"] is True, (
            "graceful_restart silently overwrote a user-set pause"
        )

    def test_unpaused_user_stays_unpaused_through_graceful_restart(self, tmp_path):
        """If the user was NOT paused, graceful_restart should still write
        paused=False so the new boot can dispatch normally."""
        state_path = str(tmp_path / "service_state.json")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            orch = Orchestrator(
                config=_make_config(),
                workflow_path="WORKFLOW.md",
                state_path=state_path,
            )
            assert orch.is_paused is False
            loop.run_until_complete(orch.graceful_restart(drain_timeout_s=0.1))
        finally:
            loop.close()
            asyncio.set_event_loop(None)

        with open(state_path) as f:
            data = json.load(f)
        assert data["paused"] is False
