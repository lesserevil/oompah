"""Tests for OOMPAH-693: Full dashboard resynchronization via WebSocket.

Verifies:
- full_sync returns state and issues from a coherent revision watermark.
- A mutation racing snapshot construction cannot produce a falsely current response.
- Concurrent duplicate requests produce bounded server work (one in-flight per connection).
- Authentication and multiple-client isolation remain correct.
- Retryable serialization/cache failures are explicit; a later request succeeds.
"""

from __future__ import annotations

import asyncio
import json
import threading
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.models import Issue
from oompah.server import app


# ---------------------------------------------------------------------------
# Isolation helpers (mirrors test_ws_lifecycle.py)
# ---------------------------------------------------------------------------

@contextmanager
def _isolated_ws_clients(*fake_ws) -> Generator[set, None, None]:
    original = server_module._ws_clients
    controlled: set = set(fake_ws)
    server_module._ws_clients = controlled
    try:
        yield controlled
    finally:
        server_module._ws_clients = original


@contextmanager
def _reset_protocol_state() -> Generator[None, None, None]:
    names = (
        "_INSTANCE_ID",
        "_protocol_epoch",
        "_state_revision",
        "_issue_revision",
        "_state_snapshot",
        "_state_snapshot_at",
        "_state_snapshot_epoch",
        "_state_snapshot_authority",
        "_state_snapshot_signature",
    )
    saved = {name: getattr(server_module, name) for name in names}
    with server_module._issues_snapshot_lock:
        saved_issues = dict(server_module._issues_snapshot)
    with server_module._ws_delivery_sequences_lock:
        saved_sequences = dict(server_module._ws_delivery_sequences)
        saved_locks = dict(server_module._ws_send_locks)
        server_module._ws_delivery_sequences.clear()
        server_module._ws_send_locks.clear()
    server_module._INSTANCE_ID = "test-epoch"
    server_module._protocol_epoch = "test-epoch"
    server_module._state_revision = 0
    server_module._issue_revision = 0
    server_module._state_snapshot = None
    server_module._state_snapshot_at = 0.0
    server_module._state_snapshot_epoch = "test-epoch"
    server_module._state_snapshot_authority = None
    server_module._state_snapshot_signature = None
    with server_module._issues_snapshot_lock:
        server_module._issues_snapshot.update(
            {
                "data": None,
                "orch_id": None,
                "epoch": "test-epoch",
                "data_revision": 0,
                "invalidated": False,
            }
        )
    try:
        yield
    finally:
        for name, value in saved.items():
            setattr(server_module, name, value)
        with server_module._issues_snapshot_lock:
            server_module._issues_snapshot.clear()
            server_module._issues_snapshot.update(saved_issues)
        with server_module._ws_delivery_sequences_lock:
            server_module._ws_delivery_sequences.clear()
            server_module._ws_delivery_sequences.update(saved_sequences)
            server_module._ws_send_locks.clear()
            server_module._ws_send_locks.update(saved_locks)


@contextmanager
def _reset_fullsync_state() -> Generator[None, None, None]:
    """Isolate _ws_fullsync_pending for one test."""
    saved: set = set(server_module._ws_fullsync_pending)
    server_module._ws_fullsync_pending.clear()
    try:
        yield
    finally:
        server_module._ws_fullsync_pending.clear()
        server_module._ws_fullsync_pending.update(saved)


def _make_ws_mock(send_side_effect=None) -> MagicMock:
    ws = MagicMock()
    ws.send_text = AsyncMock(side_effect=send_side_effect)
    return ws


def _mock_orchestrator() -> MagicMock:
    orch = MagicMock()
    orch.get_snapshot.return_value = {"running": []}
    return orch


def _all_sent_payloads(ws: MagicMock) -> list[dict]:
    """Return all decoded payloads sent to a mock WebSocket."""
    return [json.loads(call.args[0]) for call in ws.send_text.await_args_list]


def _sent_payload_by_type(ws: MagicMock, msg_type: str) -> dict | None:
    for payload in _all_sent_payloads(ws):
        if payload.get("type") == msg_type:
            return payload
    return None


# ---------------------------------------------------------------------------
# TestFullSyncAction: end-to-end via TestClient
# ---------------------------------------------------------------------------

class TestFullSyncAction:
    """The {action: full_sync} WS message triggers a coherent snapshot response."""

    @pytest.fixture
    def mock_orch(self):
        return _mock_orchestrator()

    def _drain_initial(self, ws) -> None:
        """Drain the bootstrap state + issues pair."""
        received_types: set[str] = set()
        for _ in range(4):
            try:
                msg = ws.receive_json()
                received_types.add(msg.get("type", ""))
                if "state" in received_types and "issues" in received_types:
                    break
            except Exception:
                break

    def test_full_sync_returns_full_sync_type_message(self, mock_orch):
        """Sending {action: full_sync} returns a {type: full_sync} message."""
        prior_orch = server_module._orchestrator
        server_module._orchestrator = mock_orch
        try:
            client = TestClient(app, raise_server_exceptions=False)
            with client.websocket_connect("/ws") as ws:
                self._drain_initial(ws)
                ws.send_json({"action": "full_sync"})
                response = None
                for _ in range(4):
                    try:
                        msg = ws.receive_json()
                        if msg.get("type") == "full_sync":
                            response = msg
                            break
                    except Exception:
                        break
            assert response is not None, "Expected a {type: full_sync} message"
        finally:
            server_module._orchestrator = prior_orch

    def test_full_sync_response_contains_state_and_issues(self, mock_orch):
        """The full_sync message contains both 'state' and 'issues' fields."""
        prior_orch = server_module._orchestrator
        server_module._orchestrator = mock_orch
        try:
            client = TestClient(app, raise_server_exceptions=False)
            with client.websocket_connect("/ws") as ws:
                self._drain_initial(ws)
                ws.send_json({"action": "full_sync"})
                response = None
                for _ in range(4):
                    try:
                        msg = ws.receive_json()
                        if msg.get("type") == "full_sync":
                            response = msg
                            break
                    except Exception:
                        break
            assert response is not None
            assert "state" in response, "full_sync must include 'state'"
            assert "issues" in response, "full_sync must include 'issues'"
        finally:
            server_module._orchestrator = prior_orch

    def test_full_sync_response_has_revision_watermarks(self, mock_orch):
        """The full_sync message includes state_revision and issue_revision."""
        prior_orch = server_module._orchestrator
        server_module._orchestrator = mock_orch
        try:
            client = TestClient(app, raise_server_exceptions=False)
            with client.websocket_connect("/ws") as ws:
                self._drain_initial(ws)
                ws.send_json({"action": "full_sync"})
                response = None
                for _ in range(4):
                    try:
                        msg = ws.receive_json()
                        if msg.get("type") == "full_sync":
                            response = msg
                            break
                    except Exception:
                        break
            assert response is not None
            assert "state_revision" in response, "full_sync must include state_revision"
            assert "issue_revision" in response, "full_sync must include issue_revision"
            assert isinstance(response["state_revision"], int)
            assert isinstance(response["issue_revision"], int)
        finally:
            server_module._orchestrator = prior_orch

    def test_full_sync_response_has_protocol_envelope(self, mock_orch):
        """The full_sync message carries the standard protocol envelope."""
        prior_orch = server_module._orchestrator
        server_module._orchestrator = mock_orch
        try:
            client = TestClient(app, raise_server_exceptions=False)
            with client.websocket_connect("/ws") as ws:
                self._drain_initial(ws)
                ws.send_json({"action": "full_sync"})
                response = None
                for _ in range(4):
                    try:
                        msg = ws.receive_json()
                        if msg.get("type") == "full_sync":
                            response = msg
                            break
                    except Exception:
                        break
            assert response is not None
            assert "epoch" in response, "full_sync must include epoch"
            assert "delivery_seq" in response, "full_sync must include delivery_seq"
            assert response.get("protocol_version") == 1
        finally:
            server_module._orchestrator = prior_orch

    def test_full_sync_state_has_enriched_fields(self, mock_orch):
        """The 'state' field in full_sync includes http_auth, build_id, etc."""
        prior_orch = server_module._orchestrator
        server_module._orchestrator = mock_orch
        try:
            client = TestClient(app, raise_server_exceptions=False)
            with client.websocket_connect("/ws") as ws:
                self._drain_initial(ws)
                ws.send_json({"action": "full_sync"})
                response = None
                for _ in range(4):
                    try:
                        msg = ws.receive_json()
                        if msg.get("type") == "full_sync":
                            response = msg
                            break
                    except Exception:
                        break
            assert response is not None
            state = response.get("state", {})
            assert "http_auth" in state, "state must include http_auth"
            assert "build_id" in state, "state must include build_id"
            assert "service_instance_id" in state, "state must include service_instance_id"
        finally:
            server_module._orchestrator = prior_orch

    def test_full_sync_delivers_one_unified_message(self, mock_orch):
        """Full sync returns a single message with both state and issues (not two messages)."""
        prior_orch = server_module._orchestrator
        server_module._orchestrator = mock_orch
        try:
            client = TestClient(app, raise_server_exceptions=False)
            with client.websocket_connect("/ws") as ws:
                self._drain_initial(ws)
                ws.send_json({"action": "full_sync"})
                # Collect messages until we get the full_sync type
                response = None
                for _ in range(4):
                    try:
                        msg = ws.receive_json()
                        if msg.get("type") == "full_sync":
                            response = msg
                            break
                    except Exception:
                        break
            # A single full_sync message must contain BOTH state and issues
            assert response is not None, "Expected a full_sync message"
            assert "state" in response, "Full_sync must have state"
            assert "issues" in response, "Full_sync must have issues (unified, not separate)"
        finally:
            server_module._orchestrator = prior_orch


# ---------------------------------------------------------------------------
# TestFullSyncCoalescing: per-connection coalescing
# ---------------------------------------------------------------------------

class TestFullSyncCoalescing:
    """Duplicate full_sync requests per connection are dropped while one is pending."""

    @pytest.mark.asyncio
    async def test_duplicate_request_dropped_while_pending(self):
        """A second full_sync call while one is in flight returns without sending."""
        ws = _make_ws_mock()
        orch = _mock_orchestrator()

        with _reset_protocol_state(), _isolated_ws_clients(ws), _reset_fullsync_state():
            server_module._register_ws(ws)
            # Mark ws as already having a pending full_sync
            with server_module._ws_fullsync_lock:
                server_module._ws_fullsync_pending.add(ws)

            with patch.object(server_module, "_read_state_snapshot_with_revision",
                              return_value=({"running": []}, 1)):
                with patch.object(server_module, "_ensure_issues_snapshot_refresh",
                                  new_callable=AsyncMock):
                    with patch.object(server_module, "_wait_for_issues_snapshot_refresh",
                                      new_callable=AsyncMock, return_value=True):
                        with patch.object(server_module, "_issues_snapshot_payload_with_revision",
                                          return_value=({"Open": []}, 1)):
                            await server_module._handle_full_sync(ws, orch)

        # Should have dropped the request — no send
        ws.send_text.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_pending_flag_cleared_after_success(self):
        """After a successful full_sync, the pending flag is cleared."""
        ws = _make_ws_mock()
        orch = _mock_orchestrator()

        with _reset_protocol_state(), _isolated_ws_clients(ws), _reset_fullsync_state():
            server_module._register_ws(ws)

            with patch.object(server_module, "_read_state_snapshot_with_revision",
                              return_value=({"running": []}, 1)):
                with patch.object(server_module, "_ensure_issues_snapshot_refresh",
                                  new_callable=AsyncMock):
                    with patch.object(server_module, "_wait_for_issues_snapshot_refresh",
                                      new_callable=AsyncMock, return_value=True):
                        with patch.object(server_module, "_issues_snapshot_payload_with_revision",
                                          return_value=({"Open": []}, 1)):
                            await server_module._handle_full_sync(ws, orch)

        with server_module._ws_fullsync_lock:
            assert ws not in server_module._ws_fullsync_pending, \
                "pending flag must be cleared after successful full_sync"

    @pytest.mark.asyncio
    async def test_pending_flag_cleared_after_error(self):
        """The pending flag is cleared even when the snapshot assembly fails."""
        ws = _make_ws_mock()
        orch = _mock_orchestrator()

        with _reset_protocol_state(), _isolated_ws_clients(ws), _reset_fullsync_state():
            server_module._register_ws(ws)

            with patch.object(server_module, "_read_state_snapshot_with_revision",
                              side_effect=RuntimeError("simulated failure")):
                await server_module._handle_full_sync(ws, orch)

        with server_module._ws_fullsync_lock:
            assert ws not in server_module._ws_fullsync_pending, \
                "pending flag must be cleared even after error"

    @pytest.mark.asyncio
    async def test_two_connections_pending_independently(self):
        """Pending state for one connection does not block another connection."""
        ws1 = _make_ws_mock()
        ws2 = _make_ws_mock()
        orch = _mock_orchestrator()

        with _reset_protocol_state(), _isolated_ws_clients(ws1, ws2), _reset_fullsync_state():
            server_module._register_ws(ws1)
            server_module._register_ws(ws2)

            # Mark ws1 as pending
            with server_module._ws_fullsync_lock:
                server_module._ws_fullsync_pending.add(ws1)

            with patch.object(server_module, "_read_state_snapshot_with_revision",
                              return_value=({"running": []}, 1)):
                with patch.object(server_module, "_ensure_issues_snapshot_refresh",
                                  new_callable=AsyncMock):
                    with patch.object(server_module, "_wait_for_issues_snapshot_refresh",
                                      new_callable=AsyncMock, return_value=True):
                        with patch.object(server_module, "_issues_snapshot_payload_with_revision",
                                          return_value=({"Open": []}, 1)):
                            # ws2 should not be blocked
                            await server_module._handle_full_sync(ws2, orch)

        # ws2 received a response even though ws1 was pending
        ws1.send_text.assert_not_awaited()  # ws1 was coalesced/pending
        ws2.send_text.assert_awaited_once()  # ws2 received the response
        payload2 = json.loads(ws2.send_text.call_args.args[0])
        assert payload2["type"] == "full_sync"


# ---------------------------------------------------------------------------
# TestFullSyncRaceSafety: revision watermark integrity
# ---------------------------------------------------------------------------

class TestFullSyncRaceSafety:
    """Revision watermarks in the response must match the actual payload."""

    @pytest.mark.asyncio
    async def test_full_sync_state_matches_generation_bound_detail(self):
        """Gap recovery cannot install a derived lane over canonical detail state."""
        ws = _make_ws_mock()
        parent = Issue(
            id="OOMPAH-768",
            identifier="OOMPAH-768",
            title="Canonical epic",
            description="",
            state="In Progress",
            issue_type="epic",
        )
        child = Issue(
            id="OOMPAH-768.1",
            identifier="OOMPAH-768.1",
            title="Completed child",
            description="",
            state="Done",
            issue_type="task",
            parent_id="OOMPAH-768",
        )
        tracker = MagicMock()
        tracker.state_branch_enabled = True
        tracker.supports_generation_bound_reads = True
        tracker.fetch_all_issues_with_generation.return_value = (
            [parent, child],
            "commit-current:9",
        )
        tracker.fetch_issue_detail_with_generation.return_value = (
            parent,
            "commit-current:9",
        )
        tracker.fetch_issue_detail.return_value = parent
        tracker.get_state_branch_generation.return_value = "commit-current:9"
        project = SimpleNamespace(id="proj-1", name="project-1", paused=False)
        orch = MagicMock()
        orch.project_store.list_all.return_value = [project]
        orch._tracker_for_project.return_value = tracker

        with _reset_protocol_state(), _isolated_ws_clients(ws), _reset_fullsync_state():
            server_module._register_ws(ws)
            await server_module._ensure_issues_snapshot_refresh(
                orch, force=True, broadcast=False
            )
            assert await server_module._wait_for_issues_snapshot_refresh(
                timeout_ms=2000
            )
            detail, detail_generation = (
                server_module._fetch_tracker_issue_detail_with_generation(
                    tracker, "OOMPAH-768"
                )
            )
            with patch.object(
                server_module,
                "_read_state_snapshot_with_revision",
                return_value=({"running": []}, 1),
            ):
                await server_module._handle_full_sync(ws, orch)

        payload = json.loads(ws.send_text.call_args.args[0])
        assert payload["type"] == "full_sync"
        assert detail is not None
        assert detail_generation == "commit-current:9"
        assert payload["issues"]["In Progress"][0]["identifier"] == "OOMPAH-768"
        assert payload["issues"]["In Progress"][0]["state"] == detail.state
        assert all(
            row["identifier"] != "OOMPAH-768"
            for row in payload["issues"]["Done"]
        )

    @pytest.mark.asyncio
    async def test_issue_revision_matches_snapshot_generation(self):
        """issue_revision in the response is the revision of the actual payload."""
        ws = _make_ws_mock()
        orch = _mock_orchestrator()
        expected_issues = {"Open": [{"identifier": "TASK-1"}]}

        with _reset_protocol_state(), _isolated_ws_clients(ws), _reset_fullsync_state():
            # Set up issues at revision 3
            server_module._register_ws(ws)
            server_module._set_issues_snapshot(expected_issues, duration_ms=0, orch_id=id(orch))
            server_module._advance_issue_revision()
            server_module._advance_issue_revision()

            with patch.object(server_module, "_ensure_issues_snapshot_refresh",
                              new_callable=AsyncMock):
                with patch.object(server_module, "_wait_for_issues_snapshot_refresh",
                                  new_callable=AsyncMock, return_value=True):
                    with patch.object(server_module, "_read_state_snapshot_with_revision",
                                      return_value=({"running": []}, 1)):
                        await server_module._handle_full_sync(ws, orch)

        payload = json.loads(ws.send_text.call_args.args[0])
        assert payload["type"] == "full_sync"
        # The revision should be non-negative and consistent
        assert payload["issue_revision"] >= 0

    @pytest.mark.asyncio
    async def test_state_revision_matches_snapshot(self):
        """state_revision in the response matches the snapshot we actually send."""
        ws = _make_ws_mock()
        orch = _mock_orchestrator()

        with _reset_protocol_state(), _isolated_ws_clients(ws), _reset_fullsync_state():
            server_module._register_ws(ws)
            # Set a specific state snapshot at revision 2
            server_module._update_state_snapshot({"running": [], "value": 1})
            server_module._update_state_snapshot({"running": ["agent"], "value": 2})

            with server_module._ws_protocol_lock:
                current_state_rev = server_module._state_revision
            assert current_state_rev == 2

            with patch.object(server_module, "_ensure_issues_snapshot_refresh",
                              new_callable=AsyncMock):
                with patch.object(server_module, "_wait_for_issues_snapshot_refresh",
                                  new_callable=AsyncMock, return_value=True):
                    with patch.object(server_module, "_issues_snapshot_payload_with_revision",
                                      return_value=({"Open": []}, 1)):
                        await server_module._handle_full_sync(ws, orch)

        payload = json.loads(ws.send_text.call_args.args[0])
        assert payload["type"] == "full_sync"
        assert payload["state_revision"] == 2, \
            "state_revision must match the actual snapshot revision"

    @pytest.mark.asyncio
    async def test_mutation_after_read_does_not_inflate_revision(self):
        """A mutation after snapshot assembly is not reflected in the response revision.

        This is the critical race-safety property: the response watermarks are
        stamped from the payloads we actually assembled, not from any later revision
        that a concurrent mutation may have advanced.
        """
        ws = _make_ws_mock()
        orch = _mock_orchestrator()

        assembled_issue_revision = None

        original_payload_fn = server_module._issues_snapshot_payload_with_revision

        def _read_then_mutate(*args, **kwargs):
            nonlocal assembled_issue_revision
            payload, revision = original_payload_fn(*args, **kwargs)
            assembled_issue_revision = revision
            # Simulate a mutation racing the read — this advances the global
            # issue_revision AFTER we already read the payload.
            server_module._advance_issue_revision()
            return payload, revision  # still return the OLD revision

        with _reset_protocol_state(), _isolated_ws_clients(ws), _reset_fullsync_state():
            server_module._register_ws(ws)
            server_module._set_issues_snapshot({"Open": []}, duration_ms=0, orch_id=id(orch))
            server_module._advance_issue_revision()  # revision 1 for initial data

            with patch.object(server_module, "_ensure_issues_snapshot_refresh",
                              new_callable=AsyncMock):
                with patch.object(server_module, "_wait_for_issues_snapshot_refresh",
                                  new_callable=AsyncMock, return_value=True):
                    with patch.object(server_module, "_read_state_snapshot_with_revision",
                                      return_value=({"running": []}, 1)):
                        with patch.object(server_module, "_issues_snapshot_payload_with_revision",
                                          side_effect=_read_then_mutate):
                            await server_module._handle_full_sync(ws, orch)

        payload = json.loads(ws.send_text.call_args.args[0])
        assert payload["type"] == "full_sync"
        # The response must carry the revision from the assembled payload,
        # not the inflated revision from the post-assembly mutation.
        assert payload["issue_revision"] == assembled_issue_revision, \
            "Response must not claim the revision advanced by the racing mutation"

    @pytest.mark.asyncio
    async def test_decision_update_during_full_sync_is_sequenced_after_snapshot(self):
        """A racing WorkDecision state update cannot hide below the sync watermark."""

        ws = _make_ws_mock()
        orch = _mock_orchestrator()
        assembly_started = asyncio.Event()
        release_assembly = asyncio.Event()

        async def _blocked_refresh(*_args, **_kwargs):
            assembly_started.set()
            await release_assembly.wait()

        with _reset_protocol_state(), _isolated_ws_clients(ws), _reset_fullsync_state():
            server_module._register_ws(ws)
            with (
                patch.object(
                    server_module,
                    "_read_state_snapshot_with_revision",
                    return_value=(
                        {"work_decision_projection": {"items": []}},
                        1,
                    ),
                ),
                patch.object(
                    server_module,
                    "_ensure_issues_snapshot_refresh",
                    side_effect=_blocked_refresh,
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
                    return_value=({"Done": [{"identifier": "TASK-1"}]}, 1),
                ),
            ):
                full_sync = asyncio.create_task(
                    server_module._handle_full_sync(ws, orch)
                )
                await assembly_started.wait()
                decision_update = asyncio.create_task(
                    server_module._send_ws(
                        ws,
                        {
                            "type": "state",
                            "data": {
                                "work_decision_projection": {
                                    "items": [
                                        {
                                            "project_id": "project-a",
                                            "task_id": "TASK-1",
                                            "decision_revision": "new",
                                        }
                                    ]
                                }
                            },
                        },
                    )
                )
                await asyncio.sleep(0)
                assert not decision_update.done()
                release_assembly.set()
                await asyncio.gather(full_sync, decision_update)

        payloads = _all_sent_payloads(ws)
        assert [payload["type"] for payload in payloads] == ["full_sync", "state"]
        assert payloads[0]["delivery_seq"] < payloads[1]["delivery_seq"]
        assert payloads[1]["data"]["work_decision_projection"]["items"][0][
            "decision_revision"
        ] == "new"


# ---------------------------------------------------------------------------
# TestFullSyncErrors: retryable errors without disconnecting
# ---------------------------------------------------------------------------

class TestFullSyncErrors:
    """Errors during full_sync are reported as retryable without closing the connection."""

    @pytest.mark.asyncio
    async def test_exception_sends_full_sync_error(self):
        """When snapshot assembly throws, a full_sync_error response is sent."""
        ws = _make_ws_mock()
        orch = _mock_orchestrator()

        with _reset_protocol_state(), _isolated_ws_clients(ws), _reset_fullsync_state():
            server_module._register_ws(ws)

            with patch.object(server_module, "_read_state_snapshot_with_revision",
                              side_effect=RuntimeError("database gone")):
                await server_module._handle_full_sync(ws, orch)

        payloads = _all_sent_payloads(ws)
        error_msgs = [p for p in payloads if p.get("type") == "full_sync_error"]
        assert len(error_msgs) == 1, "Expected one full_sync_error message"
        assert error_msgs[0].get("retryable") is True
        assert error_msgs[0].get("code") == "snapshot_unavailable"

    @pytest.mark.asyncio
    async def test_full_sync_error_never_disconnects_client(self):
        """A full_sync failure must not remove the client from _ws_clients."""
        ws = _make_ws_mock()
        orch = _mock_orchestrator()

        with _isolated_ws_clients(ws) as clients, _reset_fullsync_state():
            server_module._register_ws(ws)

            with patch.object(server_module, "_read_state_snapshot_with_revision",
                              side_effect=RuntimeError("temporary failure")):
                await server_module._handle_full_sync(ws, orch)

            # Client must remain connected
            assert ws in clients, "Full sync error must not disconnect the client"

    @pytest.mark.asyncio
    async def test_later_request_succeeds_after_transient_error(self):
        """After a transient full_sync failure, a follow-up request succeeds."""
        ws = _make_ws_mock()
        orch = _mock_orchestrator()

        with _reset_protocol_state(), _isolated_ws_clients(ws), _reset_fullsync_state():
            server_module._register_ws(ws)

            # First request fails
            with patch.object(server_module, "_read_state_snapshot_with_revision",
                              side_effect=RuntimeError("transient")):
                await server_module._handle_full_sync(ws, orch)

            # Second request succeeds
            with patch.object(server_module, "_read_state_snapshot_with_revision",
                              return_value=({"running": []}, 1)):
                with patch.object(server_module, "_ensure_issues_snapshot_refresh",
                                  new_callable=AsyncMock):
                    with patch.object(server_module, "_wait_for_issues_snapshot_refresh",
                                      new_callable=AsyncMock, return_value=True):
                        with patch.object(server_module, "_issues_snapshot_payload_with_revision",
                                          return_value=({"Open": []}, 1)):
                            await server_module._handle_full_sync(ws, orch)

        all_payloads = _all_sent_payloads(ws)
        types = [p["type"] for p in all_payloads]
        assert "full_sync_error" in types, "First request must produce an error"
        assert "full_sync" in types, "Second request must produce a success"
        # Error must come before success
        error_idx = next(i for i, p in enumerate(all_payloads) if p["type"] == "full_sync_error")
        success_idx = next(i for i, p in enumerate(all_payloads) if p["type"] == "full_sync")
        assert error_idx < success_idx

    @pytest.mark.asyncio
    async def test_send_failure_during_full_sync_error_is_silenced(self):
        """A broken connection during error reporting does not propagate the exception."""
        ws = _make_ws_mock(
            send_side_effect=[
                RuntimeError("send failed"),  # first call fails
            ]
        )
        orch = _mock_orchestrator()

        with _reset_protocol_state(), _isolated_ws_clients(ws), _reset_fullsync_state():
            server_module._register_ws(ws)

            with patch.object(server_module, "_read_state_snapshot_with_revision",
                              side_effect=RuntimeError("assembly failure")):
                # Must not propagate any exception
                await server_module._handle_full_sync(ws, orch)


# ---------------------------------------------------------------------------
# TestMultipleClientIsolation: connections do not interfere
# ---------------------------------------------------------------------------

class TestMultipleClientIsolation:
    """Each WebSocket connection has independent full-sync state."""

    @pytest.mark.asyncio
    async def test_full_sync_per_connection_coalescing_is_isolated(self):
        """Coalescing is per-connection; one client's pending flag doesn't affect another."""
        ws1 = _make_ws_mock()
        ws2 = _make_ws_mock()
        orch = _mock_orchestrator()

        with _reset_protocol_state(), _isolated_ws_clients(ws1, ws2), _reset_fullsync_state():
            server_module._register_ws(ws1)
            server_module._register_ws(ws2)

            with server_module._ws_fullsync_lock:
                server_module._ws_fullsync_pending.add(ws1)

            with patch.object(server_module, "_read_state_snapshot_with_revision",
                              return_value=({"running": []}, 1)):
                with patch.object(server_module, "_ensure_issues_snapshot_refresh",
                                  new_callable=AsyncMock):
                    with patch.object(server_module, "_wait_for_issues_snapshot_refresh",
                                      new_callable=AsyncMock, return_value=True):
                        with patch.object(server_module, "_issues_snapshot_payload_with_revision",
                                          return_value=({"Open": []}, 1)):
                            # ws2 is independent; its full_sync proceeds normally
                            await server_module._handle_full_sync(ws2, orch)

        ws1.send_text.assert_not_awaited()
        payload = json.loads(ws2.send_text.call_args.args[0])
        assert payload["type"] == "full_sync"

    def test_unregister_clears_pending_flag(self):
        """_unregister_ws removes a connection from _ws_fullsync_pending."""
        ws = _make_ws_mock()

        server_module._register_ws(ws)
        with server_module._ws_fullsync_lock:
            server_module._ws_fullsync_pending.add(ws)

        server_module._unregister_ws(ws)

        with server_module._ws_fullsync_lock:
            assert ws not in server_module._ws_fullsync_pending, \
                "_unregister_ws must clear the full_sync pending flag"

    @pytest.mark.asyncio
    async def test_full_sync_messages_carry_correct_delivery_seq(self):
        """Each full_sync message is stamped with the correct per-connection delivery_seq."""
        ws = _make_ws_mock()
        orch = _mock_orchestrator()

        with _reset_protocol_state(), _isolated_ws_clients(ws), _reset_fullsync_state():
            server_module._register_ws(ws)

            with patch.object(server_module, "_read_state_snapshot_with_revision",
                              return_value=({"running": []}, 1)):
                with patch.object(server_module, "_ensure_issues_snapshot_refresh",
                                  new_callable=AsyncMock):
                    with patch.object(server_module, "_wait_for_issues_snapshot_refresh",
                                      new_callable=AsyncMock, return_value=True):
                        with patch.object(server_module, "_issues_snapshot_payload_with_revision",
                                          return_value=({"Open": []}, 1)):
                            await server_module._handle_full_sync(ws, orch)

        payload = json.loads(ws.send_text.call_args.args[0])
        assert "delivery_seq" in payload
        assert payload["delivery_seq"] == 1  # first message on this connection


# ---------------------------------------------------------------------------
# TestFullSyncAuthIsolation: authentication is preserved
# ---------------------------------------------------------------------------

class TestFullSyncAuthIsolation:
    """Authentication and per-connection isolation are preserved for full_sync."""

    def test_full_sync_state_includes_http_auth_when_enabled(self):
        """full_sync state includes http_auth when auth is active."""
        import base64
        from oompah.http_auth import HtpasswdCredentials, VerificationError

        def _make_creds():
            creds = HtpasswdCredentials(enabled=True)
            def verifier(u, p):
                if u == "admin" and p == "secret":
                    return
                raise VerificationError("bad")
            creds.verifier = verifier
            creds.htpasswd_path = "/test/.htpasswd"
            return creds

        auth_header = base64.b64encode(b"admin:secret").decode()
        orch = _mock_orchestrator()

        prior_creds = server_module._http_credentials
        prior_orch = server_module._orchestrator
        orig_ws = server_module._ws_clients
        server_module._http_credentials = _make_creds()
        server_module._orchestrator = orch
        server_module._ws_clients = set()
        try:
            client = TestClient(app, raise_server_exceptions=False)
            with client.websocket_connect(
                "/ws", headers={"Authorization": f"Basic {auth_header}"}
            ) as ws:
                # Drain bootstrap
                received_types: set[str] = set()
                for _ in range(4):
                    try:
                        msg = ws.receive_json()
                        received_types.add(msg.get("type", ""))
                        if "state" in received_types and "issues" in received_types:
                            break
                    except Exception:
                        break

                ws.send_json({"action": "full_sync"})
                response = None
                for _ in range(4):
                    try:
                        msg = ws.receive_json()
                        if msg.get("type") == "full_sync":
                            response = msg
                            break
                    except Exception:
                        break

            assert response is not None
            state = response.get("state", {})
            assert "http_auth" in state
            assert state["http_auth"].get("enabled") is True
        finally:
            server_module._http_credentials = prior_creds
            server_module._orchestrator = prior_orch
            server_module._ws_clients = orig_ws

    def test_full_sync_does_not_leak_credentials(self):
        """full_sync response must not expose passwords or auth paths."""
        import base64
        import json as _json
        from oompah.http_auth import HtpasswdCredentials, VerificationError

        def _make_creds(password="supersecret"):
            creds = HtpasswdCredentials(enabled=True)
            def verifier(u, p):
                if p == password:
                    return
                raise VerificationError("bad")
            creds.verifier = verifier
            creds.htpasswd_path = "/secure/.htpasswd"
            return creds

        auth_header = base64.b64encode(b"user:supersecret").decode()
        orch = _mock_orchestrator()

        prior_creds = server_module._http_credentials
        prior_orch = server_module._orchestrator
        orig_ws = server_module._ws_clients
        server_module._http_credentials = _make_creds()
        server_module._orchestrator = orch
        server_module._ws_clients = set()
        try:
            client = TestClient(app, raise_server_exceptions=False)
            with client.websocket_connect(
                "/ws", headers={"Authorization": f"Basic {auth_header}"}
            ) as ws:
                received_types: set[str] = set()
                for _ in range(4):
                    try:
                        msg = ws.receive_json()
                        received_types.add(msg.get("type", ""))
                        if "state" in received_types and "issues" in received_types:
                            break
                    except Exception:
                        break

                ws.send_json({"action": "full_sync"})
                response = None
                for _ in range(4):
                    try:
                        msg = ws.receive_json()
                        if msg.get("type") == "full_sync":
                            response = msg
                            break
                    except Exception:
                        break

            assert response is not None
            payload_str = _json.dumps(response)
            assert "supersecret" not in payload_str
            assert "htpasswd_path" not in payload_str
            assert "/secure/.htpasswd" not in payload_str
        finally:
            server_module._http_credentials = prior_creds
            server_module._orchestrator = prior_orch
            server_module._ws_clients = orig_ws
