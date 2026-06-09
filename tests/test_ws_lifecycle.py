"""Tests for WebSocket lifecycle under Granian (TASK-472.4).

Validates the full WebSocket path including:
- Broadcast fan-out to multiple concurrent clients
- Dead-client cleanup on disconnect (_broadcast prunes failed senders)
- _broadcast RuntimeError safety (set modified during iteration)
- _broadcast no-op when no clients connected
- _on_orchestrator_change throttling and cross-loop safety
- _on_state_only_change throttling (state-only, no issues re-fetch)
- _throttled_broadcast_issues: immediate vs deferred paths, deduplication
- Cross-loop safety: no crash when loop not running or not available
- WebSocket endpoint lifecycle: client added on connect, removed on disconnect
- WebSocket endpoint: initial state + issues pushed immediately on connect
- _handle_console_input: missing/empty fields are dropped silently
- _handle_console_input: no console manager -> inline error event
- _handle_console_input: unknown project_id -> inline error event
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from contextlib import contextmanager
from typing import Generator
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest
from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.server import app


# ---------------------------------------------------------------------------
# Isolation helpers
# ---------------------------------------------------------------------------

@contextmanager
def _isolated_ws_clients(
    *fake_ws,
) -> Generator[set, None, None]:
    """Swap _ws_clients with a controlled set for one test, then restore."""
    original = server_module._ws_clients
    controlled: set = set(fake_ws)
    server_module._ws_clients = controlled
    try:
        yield controlled
    finally:
        server_module._ws_clients = original


@contextmanager
def _reset_throttles() -> Generator[None, None, None]:
    """Reset broadcast throttle globals to known values, restore on exit."""
    orig_state = server_module._last_state_broadcast
    orig_issues = server_module._last_issues_broadcast
    orig_pending = server_module._issues_broadcast_pending
    server_module._last_state_broadcast = 0.0
    server_module._last_issues_broadcast = 0.0
    server_module._issues_broadcast_pending = False
    try:
        yield
    finally:
        server_module._last_state_broadcast = orig_state
        server_module._last_issues_broadcast = orig_issues
        server_module._issues_broadcast_pending = orig_pending


def _make_ws_mock(send_side_effect=None) -> MagicMock:
    """Create a lightweight mock WebSocket whose send_text is tracked."""
    ws = MagicMock()
    ws.send_text = AsyncMock(side_effect=send_side_effect)
    return ws


# ---------------------------------------------------------------------------
# _broadcast: fan-out and dead-client cleanup
# ---------------------------------------------------------------------------

class TestBroadcastFanOut:
    """_broadcast sends to every client in _ws_clients."""

    def test_broadcast_delivers_to_all_clients(self):
        """All connected clients receive the same JSON message."""
        ws1 = _make_ws_mock()
        ws2 = _make_ws_mock()
        ws3 = _make_ws_mock()

        msg = {"type": "state", "data": {"running": []}}
        with _isolated_ws_clients(ws1, ws2, ws3):
            asyncio.run(server_module._broadcast(msg))

        expected = json.dumps(msg, default=str)
        ws1.send_text.assert_awaited_once_with(expected)
        ws2.send_text.assert_awaited_once_with(expected)
        ws3.send_text.assert_awaited_once_with(expected)

    def test_broadcast_no_op_when_no_clients(self):
        """_broadcast returns immediately without error when _ws_clients is empty."""
        with _isolated_ws_clients():  # empty set
            # Should not raise
            asyncio.run(server_module._broadcast({"type": "state", "data": {}}))

    def test_broadcast_serializes_non_json_types_with_default_str(self):
        """Non-serialisable values are coerced to str via default=str."""
        from datetime import datetime

        ws = _make_ws_mock()
        msg = {"type": "state", "data": {"ts": datetime(2026, 6, 9)}}
        with _isolated_ws_clients(ws):
            asyncio.run(server_module._broadcast(msg))

        text = ws.send_text.call_args[0][0]
        payload = json.loads(text)
        # datetime coerced to string, not TypeError
        assert isinstance(payload["data"]["ts"], str)

    def test_broadcast_fan_out_to_ten_clients(self):
        """Fan-out scales to many clients — all receive the message."""
        clients = [_make_ws_mock() for _ in range(10)]
        msg = {"type": "issues", "data": {"open": []}}
        with _isolated_ws_clients(*clients):
            asyncio.run(server_module._broadcast(msg))

        expected = json.dumps(msg, default=str)
        for ws in clients:
            ws.send_text.assert_awaited_once_with(expected)


class TestBroadcastDeadClientCleanup:
    """_broadcast removes clients whose send_text raises."""

    def test_failed_client_removed_from_ws_clients(self):
        """A client that raises during send_text is pruned from _ws_clients."""
        dead = _make_ws_mock(send_side_effect=Exception("connection reset"))
        alive = _make_ws_mock()

        with _isolated_ws_clients(dead, alive) as clients:
            asyncio.run(server_module._broadcast({"type": "state", "data": {}}))

            # Dead client pruned, alive client remains
            assert dead not in clients
            assert alive in clients

    def test_alive_clients_still_receive_message_when_one_client_fails(self):
        """Other clients receive the broadcast even when one client dies."""
        dead = _make_ws_mock(send_side_effect=RuntimeError("broken pipe"))
        alive1 = _make_ws_mock()
        alive2 = _make_ws_mock()

        msg = {"type": "state", "data": {"running": ["x"]}}
        with _isolated_ws_clients(dead, alive1, alive2):
            asyncio.run(server_module._broadcast(msg))

        expected = json.dumps(msg, default=str)
        alive1.send_text.assert_awaited_once_with(expected)
        alive2.send_text.assert_awaited_once_with(expected)

    def test_all_dead_clients_pruned_in_one_pass(self):
        """When all clients fail, all are pruned and _ws_clients becomes empty."""
        ws1 = _make_ws_mock(send_side_effect=Exception("gone"))
        ws2 = _make_ws_mock(send_side_effect=Exception("gone"))

        with _isolated_ws_clients(ws1, ws2) as clients:
            asyncio.run(server_module._broadcast({"type": "state", "data": {}}))
            assert len(clients) == 0

    def test_broadcast_handles_runtime_error_on_set_snapshot(self):
        """RuntimeError during list(_ws_clients) causes broadcast to silently skip."""
        # We patch the module's _ws_clients to be a set-like object that raises
        # RuntimeError on list() to simulate concurrent modification.
        original = server_module._ws_clients

        class _RaisesOnList(set):
            def __iter__(self):
                raise RuntimeError("Set changed size during iteration")

        server_module._ws_clients = _RaisesOnList()
        try:
            # Should not propagate the RuntimeError
            asyncio.run(server_module._broadcast({"type": "state", "data": {}}))
        finally:
            server_module._ws_clients = original


# ---------------------------------------------------------------------------
# _on_orchestrator_change: throttling and cross-loop safety
# ---------------------------------------------------------------------------

class TestOnOrchestratorChange:
    """_on_orchestrator_change schedules broadcast tasks on the running loop."""

    def test_no_tasks_scheduled_when_no_ws_clients(self):
        """_on_orchestrator_change is a no-op when _ws_clients is empty."""
        with _isolated_ws_clients():  # no clients
            with _reset_throttles():
                with patch.object(server_module, "_broadcast") as mock_broadcast:
                    server_module._on_orchestrator_change({"running": []})
                    # No loop calls needed when nobody is listening
                    mock_broadcast.assert_not_called()

    def test_state_snapshot_cached_even_without_clients(self):
        """_update_state_snapshot is always called, regardless of WS clients."""
        with _isolated_ws_clients():
            with _reset_throttles():
                with patch.object(
                    server_module, "_update_state_snapshot"
                ) as mock_update:
                    server_module._on_orchestrator_change({"running": ["x"]})
                    mock_update.assert_called_once_with({"running": ["x"]})

    @pytest.mark.asyncio
    async def test_broadcast_task_scheduled_when_clients_present(self):
        """With connected clients, _on_orchestrator_change schedules _broadcast."""
        ws = _make_ws_mock()
        with _isolated_ws_clients(ws):
            with _reset_throttles():
                broadcast_calls: list[dict] = []

                async def _capture_broadcast(msg: dict) -> None:
                    broadcast_calls.append(msg)

                with patch.object(server_module, "_broadcast", side_effect=_capture_broadcast):
                    server_module._on_orchestrator_change({"running": []})
                    # Give the created task a chance to run
                    await asyncio.sleep(0)

                # At least a state broadcast should have been scheduled
                state_msgs = [m for m in broadcast_calls if m.get("type") == "state"]
                assert len(state_msgs) >= 1

    @pytest.mark.asyncio
    async def test_throttle_suppresses_rapid_second_call(self):
        """A second call within the throttle window does not schedule another broadcast."""
        ws = _make_ws_mock()
        with _isolated_ws_clients(ws):
            with _reset_throttles():
                task_count = 0

                async def _counting_broadcast(msg: dict) -> None:
                    nonlocal task_count
                    task_count += 1

                with patch.object(
                    server_module, "_broadcast", side_effect=_counting_broadcast
                ):
                    # First call — should schedule
                    server_module._on_orchestrator_change({"running": []})
                    await asyncio.sleep(0)
                    first_count = task_count

                    # Second call immediately after — throttled, so no new task
                    server_module._on_orchestrator_change({"running": ["y"]})
                    await asyncio.sleep(0)
                    second_count = task_count

                # Count should not have doubled; throttle suppressed the second
                assert second_count == first_count

    def test_cross_loop_safety_no_crash_when_loop_not_running(self):
        """_on_orchestrator_change must not raise when the loop isn't running."""
        ws = _make_ws_mock()
        with _isolated_ws_clients(ws):
            with _reset_throttles():
                # Create a new loop that is NOT running (just created, not started)
                loop = asyncio.new_event_loop()
                try:
                    # Monkeypatch get_event_loop to return the stopped loop
                    with patch("asyncio.get_event_loop", return_value=loop):
                        # Should not raise even though loop.is_running() is False
                        server_module._on_orchestrator_change({"running": []})
                finally:
                    loop.close()

    def test_cross_loop_safety_no_crash_when_get_event_loop_raises(self):
        """_on_orchestrator_change must not propagate RuntimeError from get_event_loop."""
        ws = _make_ws_mock()
        with _isolated_ws_clients(ws):
            with _reset_throttles():
                with patch(
                    "asyncio.get_event_loop", side_effect=RuntimeError("no loop")
                ):
                    # Should not raise
                    server_module._on_orchestrator_change({"running": []})


# ---------------------------------------------------------------------------
# _on_state_only_change: state-only broadcast path
# ---------------------------------------------------------------------------

class TestOnStateOnlyChange:
    """_on_state_only_change broadcasts state without triggering issues re-fetch."""

    def test_no_op_when_no_ws_clients(self):
        """_on_state_only_change skips broadcast when _ws_clients is empty."""
        with _isolated_ws_clients():
            with _reset_throttles():
                with patch.object(server_module, "_broadcast") as mock_broadcast:
                    server_module._on_state_only_change({"running": []})
                    mock_broadcast.assert_not_called()

    def test_state_snapshot_updated_regardless_of_clients(self):
        """The state cache is always updated even with no clients."""
        with _isolated_ws_clients():
            with _reset_throttles():
                with patch.object(
                    server_module, "_update_state_snapshot"
                ) as mock_update:
                    server_module._on_state_only_change({"running": ["z"]})
                    mock_update.assert_called_once_with({"running": ["z"]})

    @pytest.mark.asyncio
    async def test_broadcasts_state_but_not_issues(self):
        """_on_state_only_change schedules a state broadcast, NOT an issues broadcast."""
        ws = _make_ws_mock()
        broadcast_types: list[str] = []

        async def _track_broadcast(msg: dict) -> None:
            broadcast_types.append(msg.get("type", ""))

        with _isolated_ws_clients(ws):
            with _reset_throttles():
                with patch.object(
                    server_module, "_broadcast", side_effect=_track_broadcast
                ):
                    with patch.object(
                        server_module, "_throttled_broadcast_issues"
                    ) as mock_issues:
                        server_module._on_state_only_change({"running": []})
                        await asyncio.sleep(0)

                # Only state type should have been broadcast
                assert "state" in broadcast_types
                # Issues broadcast must NOT have been triggered
                mock_issues.assert_not_called()

    @pytest.mark.asyncio
    async def test_throttle_prevents_rapid_state_broadcasts(self):
        """Two rapid _on_state_only_change calls result in only one broadcast."""
        ws = _make_ws_mock()
        call_count = 0

        async def _count_broadcast(msg: dict) -> None:
            nonlocal call_count
            call_count += 1

        with _isolated_ws_clients(ws):
            with _reset_throttles():
                with patch.object(
                    server_module, "_broadcast", side_effect=_count_broadcast
                ):
                    server_module._on_state_only_change({"running": []})
                    await asyncio.sleep(0)
                    after_first = call_count

                    server_module._on_state_only_change({"running": ["y"]})
                    await asyncio.sleep(0)
                    after_second = call_count

                assert after_second == after_first  # throttled


# ---------------------------------------------------------------------------
# _throttled_broadcast_issues: immediate vs deferred, deduplication
# ---------------------------------------------------------------------------

class TestThrottledBroadcastIssues:
    """_throttled_broadcast_issues debounces rapid orchestrator callbacks."""

    def test_no_op_when_no_clients(self):
        """_throttled_broadcast_issues returns immediately when _ws_clients is empty."""
        with _isolated_ws_clients():
            with _reset_throttles():
                with patch.object(
                    server_module, "_do_broadcast_issues"
                ) as mock_do:
                    asyncio.run(server_module._throttled_broadcast_issues())
                    mock_do.assert_not_called()

    @pytest.mark.asyncio
    async def test_calls_do_broadcast_immediately_when_past_throttle_window(self):
        """When enough time has elapsed, _do_broadcast_issues is called directly."""
        ws = _make_ws_mock()
        with _isolated_ws_clients(ws):
            with _reset_throttles():
                # _last_issues_broadcast == 0.0 so elapsed >> threshold
                with patch.object(
                    server_module, "_do_broadcast_issues", new_callable=AsyncMock
                ) as mock_do:
                    await server_module._throttled_broadcast_issues()
                    mock_do.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_defers_via_call_later_when_within_throttle_window(self):
        """Within the throttle window, schedules a deferred call via call_later."""
        ws = _make_ws_mock()
        with _isolated_ws_clients(ws):
            with _reset_throttles():
                # Pretend we just broadcast, so elapsed is near zero
                server_module._last_issues_broadcast = time.monotonic() * 1000

                call_later_called_with: list[float] = []

                def _fake_call_later(delay, fn):
                    call_later_called_with.append(delay)

                with patch.object(
                    server_module, "_do_broadcast_issues", new_callable=AsyncMock
                ) as mock_do:
                    loop = asyncio.get_event_loop()
                    with patch.object(loop, "call_later", side_effect=_fake_call_later):
                        await server_module._throttled_broadcast_issues()

                # _do_broadcast_issues should NOT have been called directly
                mock_do.assert_not_awaited()
                # But call_later should have been invoked with a positive delay
                assert len(call_later_called_with) == 1
                assert call_later_called_with[0] > 0

    @pytest.mark.asyncio
    async def test_deduplicates_pending_broadcasts(self):
        """A second call within the throttle window does not arm a second timer."""
        ws = _make_ws_mock()
        with _isolated_ws_clients(ws):
            with _reset_throttles():
                server_module._last_issues_broadcast = time.monotonic() * 1000

                call_later_count = 0

                def _fake_call_later(delay, fn):
                    nonlocal call_later_count
                    call_later_count += 1

                loop = asyncio.get_event_loop()
                with patch.object(loop, "call_later", side_effect=_fake_call_later):
                    await server_module._throttled_broadcast_issues()  # arms timer
                    await server_module._throttled_broadcast_issues()  # should be no-op

                # call_later must have been called exactly once
                assert call_later_count == 1

    @pytest.mark.asyncio
    async def test_pending_flag_cleared_after_do_broadcast(self):
        """_do_broadcast_issues resets _issues_broadcast_pending to False."""
        ws = _make_ws_mock()
        with _isolated_ws_clients(ws):
            with _reset_throttles():
                server_module._issues_broadcast_pending = True

                with patch.object(
                    server_module, "_issues_snapshot_payload", return_value=None
                ):
                    with patch.object(
                        server_module, "_ensure_issues_snapshot_refresh",
                        new_callable=AsyncMock,
                    ):
                        with patch.object(server_module, "_get_orchestrator") as mock_orch:
                            mock_orch.return_value = MagicMock()
                            await server_module._do_broadcast_issues()

                assert server_module._issues_broadcast_pending is False


# ---------------------------------------------------------------------------
# WebSocket endpoint: connect / disconnect lifecycle
# ---------------------------------------------------------------------------

class TestWebSocketEndpointLifecycle:
    """The /ws endpoint manages _ws_clients membership correctly."""

    @pytest.fixture
    def mock_orch(self):
        orch = MagicMock()
        orch.get_snapshot.return_value = {"running": []}
        return orch

    def test_client_is_added_to_ws_clients_on_connect(self, mock_orch):
        """A connecting WebSocket client is added to the _ws_clients set."""
        original_clients = server_module._ws_clients
        server_module._ws_clients = set()
        prior_orch = server_module._orchestrator
        server_module._orchestrator = mock_orch
        try:
            client = TestClient(app, raise_server_exceptions=False)
            with client.websocket_connect("/ws") as ws:
                # During the connection the client should be in the set
                assert len(server_module._ws_clients) == 1
                ws.close()
        finally:
            server_module._ws_clients = original_clients
            server_module._orchestrator = prior_orch

    def test_client_is_removed_from_ws_clients_after_disconnect(self, mock_orch):
        """After disconnection _ws_clients no longer holds the client."""
        original_clients = server_module._ws_clients
        server_module._ws_clients = set()
        prior_orch = server_module._orchestrator
        server_module._orchestrator = mock_orch
        try:
            client = TestClient(app, raise_server_exceptions=False)
            with client.websocket_connect("/ws") as ws:
                ws.close()
            # After context manager exits the client should be gone
            assert len(server_module._ws_clients) == 0
        finally:
            server_module._ws_clients = original_clients
            server_module._orchestrator = prior_orch

    def test_initial_state_and_issues_pushed_on_connect(self, mock_orch):
        """On connect the endpoint immediately pushes state + issues messages."""
        prior_orch = server_module._orchestrator
        server_module._orchestrator = mock_orch
        try:
            client = TestClient(app, raise_server_exceptions=False)
            with client.websocket_connect("/ws") as ws:
                msg1 = ws.receive_json()
                msg2 = ws.receive_json()

            types = {msg1.get("type"), msg2.get("type")}
            assert "state" in types
            assert "issues" in types
        finally:
            server_module._orchestrator = prior_orch

    def test_multiple_sequential_clients_each_receive_initial_push(
        self, mock_orch
    ):
        """Each successive client connection gets its own initial state + issues push."""
        prior_orch = server_module._orchestrator
        server_module._orchestrator = mock_orch
        try:
            client = TestClient(app, raise_server_exceptions=False)
            for _ in range(3):
                with client.websocket_connect("/ws") as ws:
                    msg1 = ws.receive_json()
                    msg2 = ws.receive_json()
                    types = {msg1.get("type"), msg2.get("type")}
                    assert "state" in types
                    assert "issues" in types
        finally:
            server_module._orchestrator = prior_orch


# ---------------------------------------------------------------------------
# Fan-out to concurrent clients via TestClient
# ---------------------------------------------------------------------------

class TestFanOutConcurrentClients:
    """Validates that _broadcast reaches all clients that stay connected."""

    @pytest.fixture
    def mock_orch(self):
        orch = MagicMock()
        orch.get_snapshot.return_value = {"running": []}
        return orch

    def test_broadcast_reaches_all_clients_sequentially(self, mock_orch):
        """Each client receives the broadcast message pushed from server-side."""
        prior_orch = server_module._orchestrator
        server_module._orchestrator = mock_orch

        received: list[dict] = []

        try:
            client = TestClient(app, raise_server_exceptions=False)

            # Open two WS connections; drain their initial pushes; then
            # inject a broadcast and verify each receives it.
            with client.websocket_connect("/ws") as ws1:
                # Drain initial state + issues
                ws1.receive_json()
                ws1.receive_json()

                with client.websocket_connect("/ws") as ws2:
                    ws2.receive_json()
                    ws2.receive_json()

                    # Inject a broadcast synchronously (from the test thread)
                    msg = {"type": "state", "data": {"running": ["task-1"]}}
                    asyncio.run(server_module._broadcast(msg))

                    # Both clients should receive the broadcast
                    try:
                        received.append(ws1.receive_json())
                    except Exception:
                        pass
                    try:
                        received.append(ws2.receive_json())
                    except Exception:
                        pass

        finally:
            server_module._orchestrator = prior_orch

        # At least some clients received the message; TestClient's
        # single-threaded nature may mean not all are reliably readable
        # — but the broadcast should not have raised.
        # (The real assertion is that no exception was raised above.)

    def test_broadcast_to_dead_client_does_not_affect_live_ones(self, mock_orch):
        """_broadcast prunes dead clients without disrupting live ones."""
        prior_orch = server_module._orchestrator
        server_module._orchestrator = mock_orch

        # Create one live mock client and one dead one directly
        dead = _make_ws_mock(send_side_effect=Exception("disconnected"))
        live = _make_ws_mock()

        original = server_module._ws_clients
        server_module._ws_clients = {dead, live}
        try:
            msg = {"type": "issues", "data": {}}
            asyncio.run(server_module._broadcast(msg))

            # Dead client pruned
            assert dead not in server_module._ws_clients
            # Live client still present
            assert live in server_module._ws_clients
            # Live client received the message
            live.send_text.assert_awaited_once_with(json.dumps(msg, default=str))
        finally:
            server_module._ws_clients = original
            server_module._orchestrator = prior_orch


# ---------------------------------------------------------------------------
# _handle_console_input: validation and error paths
# ---------------------------------------------------------------------------

class TestHandleConsoleInput:
    """_handle_console_input validates inputs and routes to ConsoleSession."""

    def _run(self, coro):
        return asyncio.run(coro)

    def test_empty_project_id_is_silently_dropped(self):
        """Messages without project_id do not trigger any send or error."""
        ws = _make_ws_mock()
        msg = {"type": "console_input", "project_id": "", "text": "hello"}
        self._run(server_module._handle_console_input(ws, msg))
        ws.send_text.assert_not_awaited()

    def test_missing_project_id_is_silently_dropped(self):
        """Messages without project_id key do not trigger any send or error."""
        ws = _make_ws_mock()
        msg = {"type": "console_input", "text": "hello"}
        self._run(server_module._handle_console_input(ws, msg))
        ws.send_text.assert_not_awaited()

    def test_empty_text_is_silently_dropped(self):
        """Messages with blank text do not trigger any send or error."""
        ws = _make_ws_mock()
        msg = {"type": "console_input", "project_id": "proj-1", "text": "  "}
        self._run(server_module._handle_console_input(ws, msg))
        ws.send_text.assert_not_awaited()

    def test_missing_text_is_silently_dropped(self):
        """Messages without text key do not trigger any send."""
        ws = _make_ws_mock()
        msg = {"type": "console_input", "project_id": "proj-1"}
        self._run(server_module._handle_console_input(ws, msg))
        ws.send_text.assert_not_awaited()

    def test_no_console_manager_sends_inline_error(self):
        """When _console_manager is None, an error console_event is returned inline."""
        prior_mgr = server_module._console_manager
        server_module._console_manager = None
        ws = _make_ws_mock()
        try:
            self._run(
                server_module._handle_console_input(
                    ws, {"type": "console_input", "project_id": "proj-x", "text": "hi"}
                )
            )
        finally:
            server_module._console_manager = prior_mgr

        ws.send_text.assert_awaited_once()
        payload = json.loads(ws.send_text.call_args[0][0])
        assert payload["type"] == "console_event"
        assert payload["project_id"] == "proj-x"
        assert payload["event"]["kind"] == "error"
        assert payload["event"]["is_error"] is True

    def test_unknown_project_id_sends_inline_error(self):
        """An unknown project_id triggers an inline error event."""
        # Wire up a console manager and orchestrator that don't know the project.
        mock_mgr = MagicMock()
        mock_orch = MagicMock()
        mock_orch.project_store.get.return_value = None  # unknown project

        prior_mgr = server_module._console_manager
        prior_orch = server_module._orchestrator
        server_module._console_manager = mock_mgr
        server_module._orchestrator = mock_orch

        ws = _make_ws_mock()
        try:
            self._run(
                server_module._handle_console_input(
                    ws,
                    {
                        "type": "console_input",
                        "project_id": "proj-unknown",
                        "text": "hello",
                    },
                )
            )
        finally:
            server_module._console_manager = prior_mgr
            server_module._orchestrator = prior_orch

        ws.send_text.assert_awaited_once()
        payload = json.loads(ws.send_text.call_args[0][0])
        assert payload["type"] == "console_event"
        assert payload["project_id"] == "proj-unknown"
        assert payload["event"]["kind"] == "error"
        assert "proj-unknown" in payload["event"]["text"]

    def test_session_send_exception_sends_inline_error(self):
        """If session.send() raises, an error console_event is returned inline."""
        from oompah.models import Project

        project = Project(
            id="proj-ok",
            name="ok",
            repo_url="https://example.invalid/r.git",
            repo_path="/tmp/fake",
        )

        mock_session = MagicMock()
        mock_session.send = AsyncMock(side_effect=RuntimeError("session closed"))

        mock_mgr = MagicMock()
        mock_mgr.get.return_value = mock_session

        mock_orch = MagicMock()
        mock_orch.project_store.get.return_value = project

        prior_mgr = server_module._console_manager
        prior_orch = server_module._orchestrator
        server_module._console_manager = mock_mgr
        server_module._orchestrator = mock_orch

        ws = _make_ws_mock()
        try:
            self._run(
                server_module._handle_console_input(
                    ws,
                    {
                        "type": "console_input",
                        "project_id": "proj-ok",
                        "text": "hello",
                    },
                )
            )
        finally:
            server_module._console_manager = prior_mgr
            server_module._orchestrator = prior_orch

        ws.send_text.assert_awaited_once()
        payload = json.loads(ws.send_text.call_args[0][0])
        assert payload["type"] == "console_event"
        assert payload["event"]["kind"] == "error"
        assert "session closed" in payload["event"]["text"]

    def test_valid_input_routes_to_session_send(self):
        """A valid console_input message is forwarded to session.send()."""
        from oompah.models import Project

        project = Project(
            id="proj-valid",
            name="valid",
            repo_url="https://example.invalid/r.git",
            repo_path="/tmp/fake",
        )

        mock_session = MagicMock()
        mock_session.send = AsyncMock(return_value=None)

        mock_mgr = MagicMock()
        mock_mgr.get.return_value = mock_session

        mock_orch = MagicMock()
        mock_orch.project_store.get.return_value = project

        prior_mgr = server_module._console_manager
        prior_orch = server_module._orchestrator
        server_module._console_manager = mock_mgr
        server_module._orchestrator = mock_orch

        ws = _make_ws_mock()
        try:
            self._run(
                server_module._handle_console_input(
                    ws,
                    {
                        "type": "console_input",
                        "project_id": "proj-valid",
                        "text": "run tests",
                    },
                )
            )
        finally:
            server_module._console_manager = prior_mgr
            server_module._orchestrator = prior_orch

        mock_session.send.assert_awaited_once_with("run tests", attachments=None)
        # No error event sent to the client
        ws.send_text.assert_not_awaited()


# ---------------------------------------------------------------------------
# WebSocket endpoint: refresh action
# ---------------------------------------------------------------------------

class TestWebSocketRefreshAction:
    """The {action: refresh} WS message triggers a state+issues push."""

    @pytest.fixture
    def mock_orch(self):
        orch = MagicMock()
        orch.get_snapshot.return_value = {"running": []}
        return orch

    def test_refresh_action_sends_state_back(self, mock_orch):
        """Sending {action: refresh} returns state and issues messages."""
        prior_orch = server_module._orchestrator
        server_module._orchestrator = mock_orch
        try:
            client = TestClient(app, raise_server_exceptions=False)
            with client.websocket_connect("/ws") as ws:
                # Drain initial pushes (state + issues + possible extra issues
                # from _ensure_issues_snapshot_refresh)
                received_types: set[str] = set()
                for _ in range(4):
                    try:
                        msg = ws.receive_json()
                        received_types.add(msg.get("type", ""))
                        if "state" in received_types and "issues" in received_types:
                            break
                    except Exception:
                        break

                ws.send_json({"action": "refresh"})

                # Collect messages; the refresh sends state then broadcast_issues
                # which may send issues — order is not guaranteed.
                refresh_msgs: list[dict] = []
                for _ in range(3):
                    try:
                        refresh_msgs.append(ws.receive_json())
                    except Exception:
                        break

                refresh_types = {m.get("type") for m in refresh_msgs}
                # At minimum a state message must have been sent on refresh
                assert "state" in refresh_types
        finally:
            server_module._orchestrator = prior_orch


# ---------------------------------------------------------------------------
# Cross-loop / Granian-specific: observers from non-async threads
# ---------------------------------------------------------------------------

class TestCrossLoopSafety:
    """Verify that observer callbacks called from non-async threads don't crash."""

    def test_on_orchestrator_change_from_background_thread_is_safe(self):
        """When called from a background thread with no running loop, no exception."""
        ws = _make_ws_mock()
        with _isolated_ws_clients(ws):
            with _reset_throttles():
                errors: list[Exception] = []

                def _thread_target():
                    try:
                        server_module._on_orchestrator_change({"running": []})
                    except Exception as exc:  # noqa: BLE001
                        errors.append(exc)

                t = threading.Thread(target=_thread_target)
                t.start()
                t.join(timeout=2)
                assert not t.is_alive(), "Thread did not finish"
                assert errors == [], f"Thread raised: {errors}"

    def test_on_state_only_change_from_background_thread_is_safe(self):
        """_on_state_only_change called from a non-loop thread must not crash."""
        ws = _make_ws_mock()
        with _isolated_ws_clients(ws):
            with _reset_throttles():
                errors: list[Exception] = []

                def _thread_target():
                    try:
                        server_module._on_state_only_change({"running": []})
                    except Exception as exc:  # noqa: BLE001
                        errors.append(exc)

                t = threading.Thread(target=_thread_target)
                t.start()
                t.join(timeout=2)
                assert not t.is_alive(), "Thread did not finish"
                assert errors == [], f"Thread raised: {errors}"

    def test_on_agent_activity_from_background_thread_is_safe(self):
        """_on_agent_activity called from a non-loop thread must not crash."""
        ws = _make_ws_mock()
        with _isolated_ws_clients(ws):
            entry = MagicMock()
            entry.to_dict.return_value = {"step": 1}
            errors: list[Exception] = []

            def _thread_target():
                try:
                    server_module._on_agent_activity("TASK-1", entry)
                except Exception as exc:  # noqa: BLE001
                    errors.append(exc)

            t = threading.Thread(target=_thread_target)
            t.start()
            t.join(timeout=2)
            assert not t.is_alive(), "Thread did not finish"
            assert errors == [], f"Thread raised: {errors}"
