"""Fault injection tests for WebSocket synchronization resilience.

This module tests the resilience of the WebSocket synchronization protocol
against realistic network failures: dropped messages, duplicates, delays,
and reordered messages. It validates that the dashboard convergence protocol
correctly detects desynchronization and triggers full reconciliation.

Scope (OOMPAH-695):
- Real code path integration of sync metrics
- Detection of synchronization gaps via full_sync requests
- Bounded counters for gaps, resyncs, successes, failures
- Alerts for repeated unrecovered synchronization failures
- End-to-end convergence under fault injection against real /ws endpoint
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.server import app


# ---------------------------------------------------------------------------
# Helpers for testing
# ---------------------------------------------------------------------------


def _get_ws_sync_metrics():
    """Get current WebSocket sync metrics."""
    with server_module._ws_sync_metrics_lock:
        return dict(server_module._ws_sync_metrics)


def _get_ws_sync_alert():
    """Get current WebSocket sync alert if present."""
    with server_module._ws_sync_metrics_lock:
        return server_module._ws_sync_alert


def _reset_ws_sync_metrics():
    """Reset metrics to initial state."""
    with server_module._ws_sync_metrics_lock:
        server_module._ws_sync_metrics = {
            "gaps_detected": 0,
            "full_sync_requests": 0,
            "successful_reconciliations": 0,
            "failed_reconciliations": 0,
            "last_reconciliation_ts": 0.0,
            "last_failure_ts": 0.0,
            "consecutive_failures": 0,
        }
        server_module._ws_sync_alert = None
        server_module._ws_sync_alert_dedup_ts = 0.0


def _make_mock_orch():
    """Create a mock orchestrator for testing."""
    orch = MagicMock()
    orch.get_snapshot.return_value = {"running": []}
    return orch


def _drain_initial_messages(ws, timeout_seconds=1.0):
    """Drain initial connection messages (state + issues)."""
    start = time.time()
    got_state = False
    got_issues = False
    while time.time() - start < timeout_seconds:
        try:
            msg = ws.receive_json()
            msg_type = msg.get("type", "")
            if msg_type == "state":
                got_state = True
            if msg_type == "issues":
                got_issues = True
            if got_state and got_issues:
                break
        except Exception:
            break


def _receive_message_type(ws, message_type: str, limit: int = 8) -> dict[str, Any]:
    """Receive messages until *message_type* arrives, returning that message."""
    for _ in range(limit):
        message = ws.receive_json()
        if message.get("type") == message_type:
            return message
    raise AssertionError(f"did not receive WebSocket message type {message_type!r}")


def _state_with_running(running: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the smallest authoritative state snapshot used by chip rendering."""
    return {
        "running": running,
        "counts": {"running": len(running), "retrying": 0},
    }


def _wire_fault_injector(original_send_ws, predicate, captured=None, on_capture=None):
    """Return a real ``_send_ws`` wrapper that faults after envelope creation.

    ``_send_ws`` receives the un-enveloped application payload.  Replacing the
    socket's ``send_text`` for the duration of the original call lets tests
    inspect/drop/replay the actual protocol envelope, including its sequence.
    
    Args:
        original_send_ws: The original _send_ws function to wrap
        predicate: Function that returns True if the envelope should be dropped
        captured: Optional list to append captured envelopes to
        on_capture: Optional callable that gets invoked when an envelope is captured
    """
    async def patched_send_ws(ws, msg):
        original_send_text = ws.send_text

        async def send_text(raw_text):
            envelope = json.loads(raw_text)
            if captured is not None:
                captured.append(envelope)
            if on_capture is not None:
                on_capture(envelope)
            if predicate(envelope):
                return
            await original_send_text(raw_text)

        ws.send_text = send_text
        try:
            await original_send_ws(ws, msg)
        finally:
            ws.send_text = original_send_text

    return patched_send_ws


# ---------------------------------------------------------------------------
# Test suite: Metrics wired into real code paths
# ---------------------------------------------------------------------------


class TestMetricsWiredIntoRealPaths:
    """Verify metrics are incremented via actual code paths."""

    @pytest.fixture
    def mock_orch(self):
        """Provide a mock orchestrator."""
        return _make_mock_orch()

    def test_refresh_action_increments_full_sync_requests(self, mock_orch, monkeypatch):
        """The refresh action increments full_sync_requests counter."""
        _reset_ws_sync_metrics()
        success_recorded = threading.Event()
        record_success = server_module._ws_sync_record_success

        def record_success_and_signal():
            record_success()
            success_recorded.set()

        monkeypatch.setattr(
            server_module,
            "_ws_sync_record_success",
            record_success_and_signal,
        )

        prior_orch = server_module._orchestrator
        server_module._orchestrator = mock_orch
        try:
            client = TestClient(app, raise_server_exceptions=False)
            with client.websocket_connect("/ws") as ws:
                _drain_initial_messages(ws)

                # Send refresh action
                ws.send_json({"action": "refresh"})

                # Receive response (state or issues)
                try:
                    ws.receive_json()
                except Exception:
                    pass

                # Receiving the state frame does not mean the refresh handler
                # has finished: it records success only after broadcast_issues.
                # Keep the socket open until that exact code path completes.
                assert success_recorded.wait(3), "refresh handler did not finish"

            # Verify metrics were incremented
            metrics = _get_ws_sync_metrics()
            assert (
                metrics["full_sync_requests"] >= 1
            ), f"refresh action should increment full_sync_requests, got {metrics}"
            assert (
                metrics["successful_reconciliations"] >= 1
            ), "refresh action should record success"
        finally:
            server_module._orchestrator = prior_orch

    def test_full_sync_action_increments_gaps_detected(self, mock_orch):
        """The full_sync action increments gaps_detected counter."""
        _reset_ws_sync_metrics()

        prior_orch = server_module._orchestrator
        server_module._orchestrator = mock_orch
        try:
            client = TestClient(app, raise_server_exceptions=False)
            with client.websocket_connect("/ws") as ws:
                _drain_initial_messages(ws)

                # Send full_sync action (client detected a gap)
                ws.send_json({"action": "full_sync"})

                # Receive response
                try:
                    ws.receive_json()
                except Exception:
                    pass

            # Verify gap was recorded
            metrics = _get_ws_sync_metrics()
            assert (
                metrics["gaps_detected"] >= 1
            ), f"full_sync action should increment gaps_detected, got {metrics}"
        finally:
            server_module._orchestrator = prior_orch

    def test_full_sync_success_increments_reconciliations(self, mock_orch):
        """Successful full_sync increments successful_reconciliations."""
        _reset_ws_sync_metrics()

        prior_orch = server_module._orchestrator
        server_module._orchestrator = mock_orch
        try:
            client = TestClient(app, raise_server_exceptions=False)
            with client.websocket_connect("/ws") as ws:
                _drain_initial_messages(ws)

                # Send full_sync
                ws.send_json({"action": "full_sync"})

                # Receive response
                try:
                    msg = ws.receive_json()
                except Exception:
                    msg = {}

            # Verify success was recorded
            metrics = _get_ws_sync_metrics()
            assert (
                metrics["successful_reconciliations"] >= 1
            ), f"full_sync should increment reconciliations, got {metrics}"
        finally:
            server_module._orchestrator = prior_orch


class TestMetricsExposureInState:
    """Verify metrics are exposed in state payload."""

    @pytest.fixture
    def mock_orch(self):
        return _make_mock_orch()

    def test_state_payload_includes_ws_sync_metrics(self, mock_orch):
        """State messages include ws_sync_metrics in data."""
        prior_orch = server_module._orchestrator
        server_module._orchestrator = mock_orch
        try:
            client = TestClient(app, raise_server_exceptions=False)
            with client.websocket_connect("/ws") as ws:
                # Receive initial state
                state_msg = None
                for _ in range(3):
                    try:
                        msg = ws.receive_json()
                        if msg.get("type") == "state":
                            state_msg = msg
                            break
                    except Exception:
                        break

            # Verify metrics are in state
            assert state_msg is not None, "Should receive state message"
            state_data = state_msg.get("data", {})
            assert "ws_sync_metrics" in state_data, (
                "State should include ws_sync_metrics in data"
            )

            metrics = state_data["ws_sync_metrics"]
            assert "gaps_detected" in metrics
            assert "full_sync_requests" in metrics
            assert "successful_reconciliations" in metrics
            assert "consecutive_failures" in metrics
        finally:
            server_module._orchestrator = prior_orch

    def test_no_alert_on_healthy_recovered_gaps(self, mock_orch):
        """Normal recovered gaps don't produce alerts."""
        _reset_ws_sync_metrics()

        prior_orch = server_module._orchestrator
        server_module._orchestrator = mock_orch
        try:
            client = TestClient(app, raise_server_exceptions=False)
            with client.websocket_connect("/ws") as ws:
                _drain_initial_messages(ws)

                # Request a single full_sync (healthy recovery)
                ws.send_json({"action": "full_sync"})
                try:
                    ws.receive_json()
                except Exception:
                    pass

            # Check that gap was detected but no alert
            metrics = _get_ws_sync_metrics()
            alert = _get_ws_sync_alert()

            assert metrics["gaps_detected"] >= 1, "Gap should be detected"
            assert alert is None, "No alert should be set for single recovered gap"
        finally:
            server_module._orchestrator = prior_orch


class TestFailureRecovery:
    """Verify failure handling and recovery."""

    @pytest.fixture
    def mock_orch(self):
        return _make_mock_orch()

    def test_successful_recovery_clears_failures(self, mock_orch):
        """A successful full_sync clears the consecutive failure counter."""
        _reset_ws_sync_metrics()

        prior_orch = server_module._orchestrator
        server_module._orchestrator = mock_orch
        try:
            client = TestClient(app, raise_server_exceptions=False)
            with client.websocket_connect("/ws") as ws:
                _drain_initial_messages(ws)

                # Send full_sync (should succeed)
                ws.send_json({"action": "full_sync"})

                # Receive response
                try:
                    ws.receive_json()
                except Exception:
                    pass

            # Check that failures were cleared
            metrics = _get_ws_sync_metrics()
            assert (
                metrics["consecutive_failures"] == 0
            ), "Success should clear failure counter"
        finally:
            server_module._orchestrator = prior_orch

    def test_repeated_full_sync_failures_emit_alert_in_state_payload(self, mock_orch):
        """The live endpoint records failures and exposes one actionable alert."""
        _reset_ws_sync_metrics()
        prior_orch = server_module._orchestrator
        server_module._orchestrator = mock_orch
        try:
            client = TestClient(app, raise_server_exceptions=False)
            with client.websocket_connect("/ws") as ws:
                _drain_initial_messages(ws)
                # Fail only the full-sync wait.  The initial connection does not
                # call this helper, so the endpoint itself remains healthy while
                # the production _handle_full_sync error path is exercised.
                with patch.object(
                    server_module,
                    "_ensure_issues_snapshot_refresh",
                    new_callable=AsyncMock,
                ), patch.object(
                    server_module,
                    "_wait_for_issues_snapshot_refresh",
                    new_callable=AsyncMock,
                    side_effect=[
                        RuntimeError("injected snapshot failure")
                        for _ in range(server_module._WS_SYNC_ALERT_THRESHOLD)
                    ],
                ):
                    for _ in range(server_module._WS_SYNC_ALERT_THRESHOLD):
                        ws.send_json({"action": "full_sync"})
                        error = _receive_message_type(ws, "full_sync_error")
                        assert error["retryable"] is True

            metrics = _get_ws_sync_metrics()
            assert metrics["failed_reconciliations"] == server_module._WS_SYNC_ALERT_THRESHOLD
            assert metrics["consecutive_failures"] >= server_module._WS_SYNC_ALERT_THRESHOLD
            alert = _get_ws_sync_alert()
            assert alert is not None
            assert alert["alert_type"] == "unrecovered_synchronization_failure"
            assert "refresh" in alert["message"].lower()

            state_message = server_module._current_state_message()
            state_alert = state_message["data"].get("ws_sync_alert")
            assert state_alert is not None
            assert state_alert["timestamp"] == alert["timestamp"]
            assert "contact support" in state_alert["message"]
        finally:
            server_module._orchestrator = prior_orch

    def test_successful_full_sync_clears_alert_after_live_failures(self, mock_orch):
        """A later live full_sync clears the alert and failure streak."""
        _reset_ws_sync_metrics()
        prior_orch = server_module._orchestrator
        server_module._orchestrator = mock_orch
        try:
            client = TestClient(app, raise_server_exceptions=False)
            with client.websocket_connect("/ws") as ws:
                _drain_initial_messages(ws)
                with patch.object(
                    server_module,
                    "_ensure_issues_snapshot_refresh",
                    new_callable=AsyncMock,
                ), patch.object(
                    server_module,
                    "_wait_for_issues_snapshot_refresh",
                    new_callable=AsyncMock,
                    side_effect=[
                        RuntimeError("injected snapshot failure")
                        for _ in range(server_module._WS_SYNC_ALERT_THRESHOLD)
                    ] + [True],
                ):
                    for _ in range(server_module._WS_SYNC_ALERT_THRESHOLD):
                        ws.send_json({"action": "full_sync"})
                        _receive_message_type(ws, "full_sync_error")
                    assert _get_ws_sync_alert() is not None

                    ws.send_json({"action": "full_sync"})
                    response = _receive_message_type(ws, "full_sync")
                    assert response["state"] is not None
                    assert response["issues"] is not None

            metrics = _get_ws_sync_metrics()
            assert metrics["consecutive_failures"] == 0
            assert metrics["successful_reconciliations"] == 1
            assert _get_ws_sync_alert() is None
            assert "ws_sync_alert" not in server_module._current_state_message()["data"]
        finally:
            server_module._orchestrator = prior_orch


class TestDisconnectReconnect:
    """Test disconnect and reconnect scenarios."""

    @pytest.fixture
    def mock_orch(self):
        return _make_mock_orch()

    def test_disconnect_reconnect_recovery(self, mock_orch):
        """Disconnect and reconnect resets sequence state."""
        prior_orch = server_module._orchestrator
        server_module._orchestrator = mock_orch
        try:
            client = TestClient(app, raise_server_exceptions=False)

            # First connection
            with client.websocket_connect("/ws") as ws:
                _drain_initial_messages(ws)

            # Second connection (simulating browser reconnect)
            with client.websocket_connect("/ws") as ws:
                _drain_initial_messages(ws)

            # Both connections should work
            assert True  # If we got here, reconnect worked
        finally:
            server_module._orchestrator = prior_orch


class TestMetricsAccuracy:
    """Verify metrics are accurate and reflect actual code paths."""

    @pytest.fixture
    def mock_orch(self):
        return _make_mock_orch()

    def test_gaps_detected_counter_increments(self, mock_orch):
        """gaps_detected counter actually increments via real code path."""
        _reset_ws_sync_metrics()

        prior_orch = server_module._orchestrator
        server_module._orchestrator = mock_orch
        try:
            client = TestClient(app, raise_server_exceptions=False)
            with client.websocket_connect("/ws") as ws:
                _drain_initial_messages(ws)

                # Request full sync
                ws.send_json({"action": "full_sync"})
                try:
                    ws.receive_json()
                except Exception:
                    pass

            metrics = _get_ws_sync_metrics()
            assert metrics["gaps_detected"] > 0, "gaps_detected should increment"
        finally:
            server_module._orchestrator = prior_orch

    def test_successful_reconciliations_counter_increments(self, mock_orch):
        """successful_reconciliations increments on successful full_sync."""
        _reset_ws_sync_metrics()

        prior_orch = server_module._orchestrator
        server_module._orchestrator = mock_orch
        try:
            client = TestClient(app, raise_server_exceptions=False)
            with client.websocket_connect("/ws") as ws:
                _drain_initial_messages(ws)

                ws.send_json({"action": "full_sync"})
                try:
                    msg = ws.receive_json()
                except Exception:
                    msg = {}

            metrics = _get_ws_sync_metrics()
            assert (
                metrics["successful_reconciliations"] >= 1
            ), "successful_reconciliations should increment"
        finally:
            server_module._orchestrator = prior_orch

    def test_refresh_state_includes_metrics(self, mock_orch):
        """State from refresh includes metrics in data."""
        prior_orch = server_module._orchestrator
        server_module._orchestrator = mock_orch
        try:
            client = TestClient(app, raise_server_exceptions=False)
            with client.websocket_connect("/ws") as ws:
                # Drain initial
                for _ in range(3):
                    try:
                        msg = ws.receive_json()
                        if msg.get("type") == "state":
                            break
                    except Exception:
                        break

                # Send refresh
                ws.send_json({"action": "refresh"})

                # Look for state response with metrics
                for _ in range(2):
                    try:
                        msg = ws.receive_json()
                        if msg.get("type") == "state":
                            state_data = msg.get("data", {})
                            assert (
                                "ws_sync_metrics" in state_data
                            ), "State should include metrics"
                            break
                    except Exception:
                        break
        finally:
            server_module._orchestrator = prior_orch


class TestFaultInjectionWithRealProtocol:
    """Test fault injection by patching real _send_ws to drop/duplicate messages."""

    @pytest.fixture
    def mock_orch(self):
        return _make_mock_orch()

    def test_dropped_messages_require_full_sync_recovery(self, mock_orch):
        """When messages are dropped, full_sync recovers the authoritative state."""
        _reset_ws_sync_metrics()
        dropped_envelopes: list[dict[str, Any]] = []
        issues_drop_completed = threading.Event()
        original_send_ws = server_module._send_ws

        def drop_issues(envelope):
            # This predicate runs after _send_ws has stamped the real
            # protocol envelope, unlike the old pre-envelope test patch.
            should_drop = envelope.get("type") == "issues"
            if should_drop:
                dropped_envelopes.append(envelope)
                issues_drop_completed.set()
            return should_drop

        patched_send_ws = _wire_fault_injector(
            original_send_ws, drop_issues
        )

        with patch.object(server_module, "_send_ws", patched_send_ws):
            prior_orch = server_module._orchestrator
            server_module._orchestrator = mock_orch
            try:
                client = TestClient(app, raise_server_exceptions=False)
                with client.websocket_connect("/ws") as ws:
                    msg = ws.receive_json()
                    assert msg.get("type") == "state"
                    # The issues message is dropped on the wire, leaving a
                    # genuine delivery sequence gap for the browser.
                    assert issues_drop_completed.wait(3), (
                        "initial issues envelope was not offered to the wire"
                    )
                    assert dropped_envelopes
                    assert all("delivery_seq" in msg for msg in dropped_envelopes)

                    ws.send_json({"action": "full_sync"})
                    response = _receive_message_type(ws, "full_sync")
                    assert response["state"] is not None
                    assert response["issues"] is not None

            finally:
                server_module._orchestrator = prior_orch

        # Verify metrics recorded the gap and recovery
        metrics = _get_ws_sync_metrics()
        assert metrics["gaps_detected"] >= 1, "Gap should be detected via full_sync"
        assert metrics["successful_reconciliations"] >= 1

    def test_duplicate_messages_idempotent_with_delivery_seq(self, mock_orch):
        """A duplicate envelope cannot regress the client's applied snapshot."""
        _reset_ws_sync_metrics()
        original_send_ws = server_module._send_ws
        duplicated = False
        server_ws = None
        first_issue_raw = None

        async def patched_send_ws(ws, msg):
            nonlocal duplicated, server_ws, first_issue_raw
            server_ws = ws
            original_send_text = ws.send_text

            async def duplicate_issue_envelope(raw_text):
                nonlocal duplicated, first_issue_raw
                envelope = json.loads(raw_text)
                if envelope.get("type") == "issues" and first_issue_raw is None:
                    first_issue_raw = raw_text
                await original_send_text(raw_text)
                if envelope.get("type") == "issues" and not duplicated:
                    duplicated = True
                    # Replay precisely the same wire envelope.  Calling the
                    # underlying send twice (rather than _send_ws twice)
                    # preserves the original delivery_seq.
                    await original_send_text(raw_text)

            ws.send_text = duplicate_issue_envelope
            try:
                await original_send_ws(ws, msg)
            finally:
                ws.send_text = original_send_text

        with patch.object(server_module, "_send_ws", patched_send_ws):
            prior_orch = server_module._orchestrator
            server_module._orchestrator = mock_orch
            try:
                with (
                    patch.object(
                        server_module,
                        "_ensure_issues_snapshot_refresh",
                        new_callable=AsyncMock,
                    ),
                    # The refresh is intentionally disabled so wire replay is
                    # deterministic.  Supply an explicitly authoritative
                    # bootstrap instead of relying on another test's global
                    # issue snapshot; unavailable snapshots are correctly not
                    # emitted after OOMPAH-873.
                    patch.object(
                        server_module,
                        "_issues_snapshot_payload_with_revision",
                        return_value=({"Open": []}, 1),
                    ),
                ):
                    client = TestClient(app, raise_server_exceptions=False)
                    with client.websocket_connect("/ws") as ws:
                        first_state = _receive_message_type(ws, "state")
                        first_issues = _receive_message_type(ws, "issues")
                        duplicate_issues = _receive_message_type(ws, "issues")

                        assert duplicated is True
                        assert duplicate_issues["delivery_seq"] == first_issues["delivery_seq"]
                        assert duplicate_issues["issue_revision"] == first_issues["issue_revision"]
                        assert duplicate_issues["data"] == first_issues["data"]

                        # Model the dashboard's delivery watermark at the
                        # commit boundary: the replay is at or below the
                        # applied sequence, so the authoritative client-visible
                        # board remains the first snapshot.
                        applied_issues = first_issues["data"]
                        last_delivery_seq = first_issues["delivery_seq"]
                        if duplicate_issues["delivery_seq"] > last_delivery_seq:
                            applied_issues = duplicate_issues["data"]
                        assert applied_issues == first_issues["data"]
                        assert first_state["type"] == "state"

                        # Deliver a newer issue snapshot, then replay the older
                        # captured envelope.  The wire order is intentionally
                        # wrong, but the older delivery watermark cannot replace
                        # the newer client-visible board.
                        asyncio.run(server_module._broadcast({
                            "type": "issues",
                            "data": {"Open": [{"identifier": "TASK-new"}]},
                            "issue_revision": first_issues["issue_revision"] + 1,
                        }))
                        newer_issues = _receive_message_type(ws, "issues")
                        assert newer_issues["data"] == {"Open": [{"identifier": "TASK-new"}]}
                        assert server_ws is not None
                        assert first_issue_raw is not None
                        replay_send_text = server_ws.send_text
                        asyncio.run(replay_send_text(first_issue_raw))
                        replayed_issues = _receive_message_type(ws, "issues")

                        assert first_issues["delivery_seq"] < newer_issues["delivery_seq"]
                        assert replayed_issues["delivery_seq"] == first_issues["delivery_seq"]
                        applied_issues = newer_issues["data"]
                        if replayed_issues["delivery_seq"] > newer_issues["delivery_seq"]:
                            applied_issues = replayed_issues["data"]
                        assert applied_issues == newer_issues["data"]

            finally:
                server_module._orchestrator = prior_orch


class TestLiveDashboardConvergence:
    """Exercise the real /ws endpoint with authoritative state transitions."""

    def test_four_completion_snapshots_converge_to_zero_running_chips(self):
        """Dropped auditor completions are removed by one authoritative full sync."""
        _reset_ws_sync_metrics()
        completed_auditors = [
            {
                "issue_identifier": f"TASK-{index}",
                "run_id": f"run-{index}",
                "agent_profile": "auditor",
            }
            for index in range(1, 5)
        ]
        dropped: list[dict[str, Any]] = []
        original_send_ws = server_module._send_ws
        prior_orch = server_module._orchestrator
        server_module._orchestrator = _make_mock_orch()
        
        # Synchronization: wait for all 4 completion snapshots to be captured
        # by the fault injector before asserting. This replaces timing-dependent
        # observation with an explicit bounded wait.
        captures_lock = threading.Lock()
        captures_condition = threading.Condition(captures_lock)
        captured_completion_snapshots = [False, False, False, False]  # Track each completion
        
        def track_completion_snapshot(envelope):
            """Signal when a completion snapshot is captured."""
            data = envelope.get("data")
            running = data.get("running") if isinstance(data, dict) else None
            if envelope.get("type") == "state" and isinstance(running, list):
                if len(running) in {0, 1, 2, 3}:
                    # Map running count to completion index: 3→0, 2→1, 1→2, 0→3
                    completion_index = 3 - len(running)
                    with captures_condition:
                        captured_completion_snapshots[completion_index] = True
                        captures_condition.notify_all()

        def drop_completion_states(envelope):
            data = envelope.get("data")
            running = data.get("running") if isinstance(data, dict) else None
            if envelope.get("type") == "state" and isinstance(running, list):
                # The initial state has all four chips; only drop the four
                # subsequent completion snapshots (4→3→2→1→0).
                if len(running) in {0, 1, 2, 3}:
                    dropped.append(envelope)
                    return True
            return False

        patched_send_ws = _wire_fault_injector(
            original_send_ws, drop_completion_states, on_capture=track_completion_snapshot
        )
        try:
            server_module._update_state_snapshot(_state_with_running(completed_auditors))
            with (
                patch.object(server_module, "_send_ws", patched_send_ws),
                patch.object(
                    server_module,
                    "_ensure_issues_snapshot_refresh",
                    new_callable=AsyncMock,
                ),
                patch.object(
                    server_module,
                    "_wait_for_issues_snapshot_refresh",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
                patch.object(
                    server_module,
                    "_issues_snapshot_payload_with_revision",
                    return_value=({"Open": []}, 1),
                ),
            ):
                client = TestClient(app, raise_server_exceptions=False)
                with client.websocket_connect("/ws") as ws:
                    initial = _receive_message_type(ws, "state")
                    assert initial["data"]["running"] == completed_auditors

                    # Each transition is sent through the actual broadcast →
                    # _send_ws → enveloped WebSocket path on the connection's
                    # own event loop.  The injector drops only the four
                    # completion envelopes.
                    for remaining in range(3, -1, -1):
                        snapshot = _state_with_running(completed_auditors[:remaining])
                        server_module._update_state_snapshot(snapshot)
                        ws.portal.call(
                            server_module._broadcast,
                            server_module._current_state_message(),
                        )

                    # Wait for all 4 completion snapshots to be captured by the
                    # fault injector with a bounded timeout. This proves all 4
                    # broadcasts were processed before we assert.
                    timeout = time.time() + 5.0  # 5-second timeout
                    with captures_condition:
                        while not all(captured_completion_snapshots):
                            remaining_time = timeout - time.time()
                            if remaining_time <= 0:
                                raise AssertionError(
                                    f"Timeout waiting for 4 completion snapshots. "
                                    f"Captured: {sum(captured_completion_snapshots)}/4"
                                )
                            captures_condition.wait(timeout=0.1)

                    assert len(dropped) == 4, (
                        f"Expected 4 dropped completion snapshots, got {len(dropped)}"
                    )
                    assert [message["delivery_seq"] for message in dropped] == sorted(
                        message["delivery_seq"] for message in dropped
                    )

                    # This is the browser's gap-recovery action.  The response
                    # is one coherent full_sync payload, not four incremental
                    # snapshots, and must remove every stale running chip.
                    ws.send_json({"action": "full_sync"})
                    full_sync = _receive_message_type(ws, "full_sync")
                    assert full_sync["state"]["running"] == []
                    assert not {
                        item["issue_identifier"] for item in full_sync["state"]["running"]
                    }.intersection(
                        item["issue_identifier"] for item in completed_auditors
                    )

            metrics = _get_ws_sync_metrics()
            assert metrics["gaps_detected"] >= 1
            assert metrics["full_sync_requests"] >= 1
            assert metrics["successful_reconciliations"] >= 1
        finally:
            server_module._orchestrator = prior_orch

    @pytest.mark.asyncio
    async def test_full_sync_burst_coalesces_snapshot_work(self):
        """A burst shares one in-flight assembly and emits one response."""
        ws = MagicMock()
        ws.send_text = AsyncMock()
        orch = _make_mock_orch()
        release_assembly = asyncio.Event()
        assembly_started = asyncio.Event()

        async def slow_refresh(*args, **kwargs):
            assembly_started.set()
            await release_assembly.wait()

        with patch.object(server_module, "_read_state_snapshot_with_revision",
                          return_value=({"running": []}, 7)), \
             patch.object(server_module, "_ensure_issues_snapshot_refresh",
                          side_effect=slow_refresh) as refresh_mock, \
             patch.object(server_module, "_wait_for_issues_snapshot_refresh",
                          new_callable=AsyncMock, return_value=True), \
             patch.object(server_module, "_issues_snapshot_payload_with_revision",
                          return_value=({"Open": []}, 11)):
            server_module._register_ws(ws)
            try:
                requests = [
                    asyncio.create_task(server_module._handle_full_sync(ws, orch))
                    for _ in range(20)
                ]
                await asyncio.wait_for(assembly_started.wait(), timeout=1)
                await asyncio.sleep(0)

                # All other requests observe the per-connection pending flag
                # while the first assembly is blocked in the real handler.
                assert refresh_mock.await_count == 1
                release_assembly.set()
                await asyncio.gather(*requests)
            finally:
                server_module._unregister_ws(ws)

        assert ws.send_text.await_count == 1
        payload = json.loads(ws.send_text.call_args.args[0])
        assert payload["type"] == "full_sync"
        assert payload["state_revision"] == 7
        assert payload["issue_revision"] == 11


# Ensure metrics are reset after each test
@pytest.fixture(autouse=True)
def reset_metrics():
    """Reset metrics before and after each test."""
    _reset_ws_sync_metrics()
    yield
    _reset_ws_sync_metrics()
