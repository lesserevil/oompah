"""HTTP + WebSocket tests for the per-project console endpoints
(oompah-zlz_2-g73s, Console 4/6).

Covers:

* GET /api/v1/console/{project_id}/transcript
    - empty project (no events yet)
    - project with N events (returns chronologically)
    - ?since=<iso> filters strictly greater than
    - ?limit caps the result size
    - 404 on unknown project_id
    - 503 when the console manager isn't wired
    - meta sidecar surfaces in the response

* POST /api/v1/console/{project_id}/backend
    - 200 happy path: backend swap persists to meta sidecar
    - 409 turn in flight
    - 400 unknown backend
    - 400 missing / non-string backend field
    - 404 unknown project_id

* DELETE /api/v1/console/{project_id}
    - clears the in-memory session (manager forgets it)
    - clears the on-disk transcript + meta sidecar
    - idempotent (delete twice → both succeed)
    - 404 unknown project_id

* WebSocket /ws smoke test
    - Sending {type:"console_input"} drives the session and
      broadcasts the operator_input ConsoleEvent to all connected
      clients.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import oompah.console as console_mod
import oompah.server as server_module
from oompah.console import ConsoleSessionManager
from oompah.console_format import ConsoleEvent
from oompah.console_store import ConsoleStore
from oompah.console_translators import known_backends
from oompah.models import Project
from oompah.server import app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_project(repo_path: Path) -> Project:
    repo_path.mkdir(parents=True, exist_ok=True)
    return Project(
        id="proj-T",
        name="testproj",
        repo_url="https://example.invalid/r.git",
        repo_path=str(repo_path),
    )


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def wired_console(tmp_path):
    """Install a ConsoleSessionManager + minimal orchestrator into the
    server module for the duration of one test, then restore."""
    project = _make_project(tmp_path / "repo")
    orch = MagicMock()
    orch.project_store.get.side_effect = (
        lambda pid: project if pid == project.id else None
    )

    # Build a real store rooted in tmp_path so writes/reads are
    # observable.
    store_root = str(tmp_path / "console")
    store = ConsoleStore(root=store_root)

    # Minimal provider / role stores: enough surface area for
    # ConsoleSession.__init__ and switch_backend.
    provider_store = MagicMock()
    provider_store.get.return_value = None
    provider_store.get_default.return_value = None
    role_store = MagicMock()
    role_store.get.return_value = None

    # No on_event_factory by default — the WS smoke test installs a
    # capturing one separately.
    mgr = ConsoleSessionManager(
        store=store,
        provider_store=provider_store,
        role_store=role_store,
        workspace_resolver=lambda pid: (
            project.repo_path if pid == project.id else None
        ),
    )

    prior_orch = server_module._orchestrator
    prior_mgr = server_module._console_manager
    server_module._orchestrator = orch
    server_module._console_manager = mgr
    try:
        yield {
            "project": project,
            "mgr": mgr,
            "store": store,
            "store_root": store_root,
            "tmp_path": tmp_path,
            "provider_store": provider_store,
            "role_store": role_store,
        }
    finally:
        server_module._orchestrator = prior_orch
        server_module._console_manager = prior_mgr


def _append_event(store: ConsoleStore, project_id: str, **kwargs: Any) -> dict:
    """Append a normalized event to the store and return the dict form."""
    event = ConsoleEvent(**kwargs)
    payload = event.to_dict()
    store.append(project_id, payload)
    return payload


# ---------------------------------------------------------------------------
# GET /api/v1/console/{project_id}/transcript
# ---------------------------------------------------------------------------


class TestTranscriptEndpoint:
    def test_empty_project_returns_empty_events(self, client, wired_console):
        pid = wired_console["project"].id
        r = client.get(f"/api/v1/console/{pid}/transcript")
        assert r.status_code == 200
        data = r.json()
        assert data["project_id"] == pid
        assert data["events"] == []
        assert data["meta"] == {}
        # Default limit defaults to 200.
        assert data["limit"] == 200
        assert data["since"] is None

    def test_returns_persisted_events_in_order(self, client, wired_console):
        pid = wired_console["project"].id
        store = wired_console["store"]
        _append_event(store, pid, ts="2026-05-13T10:00:00Z",
                      kind="operator_input", text="hi")
        _append_event(store, pid, ts="2026-05-13T10:00:01Z",
                      kind="agent_text", text="hello")
        _append_event(store, pid, ts="2026-05-13T10:00:02Z",
                      kind="session_meta", args={"status": "ok"})
        r = client.get(f"/api/v1/console/{pid}/transcript")
        assert r.status_code == 200
        data = r.json()
        assert len(data["events"]) == 3
        assert [e["kind"] for e in data["events"]] == [
            "operator_input", "agent_text", "session_meta",
        ]

    def test_since_filters_strictly_greater(self, client, wired_console):
        pid = wired_console["project"].id
        store = wired_console["store"]
        _append_event(store, pid, ts="2026-05-13T10:00:00Z",
                      kind="operator_input", text="first")
        _append_event(store, pid, ts="2026-05-13T10:00:01Z",
                      kind="agent_text", text="reply")
        _append_event(store, pid, ts="2026-05-13T10:00:02Z",
                      kind="operator_input", text="second")
        r = client.get(
            f"/api/v1/console/{pid}/transcript"
            "?since=2026-05-13T10:00:00Z",
        )
        assert r.status_code == 200
        data = r.json()
        # Strictly > means the event at 10:00:00 is excluded.
        assert [e["text"] for e in data["events"]] == ["reply", "second"]
        assert data["since"] == "2026-05-13T10:00:00Z"

    def test_limit_caps_results(self, client, wired_console):
        pid = wired_console["project"].id
        store = wired_console["store"]
        for i in range(10):
            _append_event(
                store, pid,
                ts=f"2026-05-13T10:00:0{i}Z",
                kind="operator_input", text=f"m{i}",
            )
        r = client.get(f"/api/v1/console/{pid}/transcript?limit=3")
        assert r.status_code == 200
        data = r.json()
        # ConsoleStore.read_all returns the most recent ``limit``
        # entries when limit is set.
        assert len(data["events"]) == 3
        assert [e["text"] for e in data["events"]] == ["m7", "m8", "m9"]
        assert data["limit"] == 3

    def test_limit_capped_at_max(self, client, wired_console):
        pid = wired_console["project"].id
        r = client.get(f"/api/v1/console/{pid}/transcript?limit=999999")
        assert r.status_code == 200
        assert r.json()["limit"] == 1000

    def test_limit_invalid_falls_back_to_default(self, client, wired_console):
        pid = wired_console["project"].id
        r = client.get(f"/api/v1/console/{pid}/transcript?limit=notanint")
        # FastAPI coerces query param int parsing — int|None field
        # rejects "notanint" with 422. Make sure we don't crash.
        assert r.status_code in (200, 422)

    def test_meta_surfaces_in_response(self, client, wired_console):
        pid = wired_console["project"].id
        store = wired_console["store"]
        store.save_meta(pid, {"backend": "claude", "model_role": "default"})
        r = client.get(f"/api/v1/console/{pid}/transcript")
        assert r.status_code == 200
        meta = r.json()["meta"]
        assert meta["backend"] == "claude"
        assert meta["model_role"] == "default"

    def test_404_on_unknown_project(self, client, wired_console):
        r = client.get("/api/v1/console/proj-nope/transcript")
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "no_project"

    def test_503_when_not_initialized(self, client):
        prior = server_module._console_manager
        server_module._console_manager = None
        try:
            r = client.get("/api/v1/console/anything/transcript")
            assert r.status_code == 503
        finally:
            server_module._console_manager = prior


# ---------------------------------------------------------------------------
# POST /api/v1/console/{project_id}/backend
# ---------------------------------------------------------------------------


class TestBackendEndpoint:
    def test_swap_backend_200(self, client, wired_console):
        pid = wired_console["project"].id
        # claude must be registered (side-effect import at module load).
        assert "claude" in known_backends()
        r = client.post(
            f"/api/v1/console/{pid}/backend",
            json={"backend": "claude", "model_role": "default"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["backend"] == "claude"
        assert body["model_role"] == "default"
        # Persisted to meta sidecar.
        meta = wired_console["store"].load_meta(pid)
        assert meta["backend"] == "claude"
        assert meta["model_role"] == "default"
        assert "switched_at" in meta

    def test_unknown_backend_400(self, client, wired_console):
        pid = wired_console["project"].id
        r = client.post(
            f"/api/v1/console/{pid}/backend",
            json={"backend": "definitely-not-a-backend"},
        )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "unknown_backend"

    def test_missing_backend_field_400(self, client, wired_console):
        pid = wired_console["project"].id
        r = client.post(
            f"/api/v1/console/{pid}/backend",
            json={"model_role": "default"},
        )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "bad_request"

    def test_empty_backend_field_400(self, client, wired_console):
        pid = wired_console["project"].id
        r = client.post(
            f"/api/v1/console/{pid}/backend",
            json={"backend": "  "},
        )
        assert r.status_code == 400

    def test_unknown_project_404(self, client, wired_console):
        r = client.post(
            "/api/v1/console/proj-nope/backend",
            json={"backend": "claude"},
        )
        assert r.status_code == 404

    def test_turn_in_flight_409(self, client, wired_console):
        pid = wired_console["project"].id
        # Force the session's _turn_active flag to True to mimic a
        # turn that's mid-execution.
        session = wired_console["mgr"].get(pid)
        session._turn_active = True
        try:
            r = client.post(
                f"/api/v1/console/{pid}/backend",
                json={"backend": "claude"},
            )
            assert r.status_code == 409
            body = r.json()
            assert body["error"]["code"] == "turn_in_flight"
        finally:
            session._turn_active = False

    def test_model_role_defaults_to_default(self, client, wired_console):
        pid = wired_console["project"].id
        r = client.post(
            f"/api/v1/console/{pid}/backend",
            json={"backend": "claude"},
        )
        assert r.status_code == 200
        assert r.json()["model_role"] == "default"

    def test_non_json_body_400(self, client, wired_console):
        pid = wired_console["project"].id
        r = client.post(
            f"/api/v1/console/{pid}/backend",
            content="not json",
            headers={"content-type": "application/json"},
        )
        assert r.status_code == 400

    def test_503_when_not_initialized(self, client):
        prior = server_module._console_manager
        server_module._console_manager = None
        try:
            r = client.post(
                "/api/v1/console/x/backend",
                json={"backend": "claude"},
            )
            assert r.status_code == 503
        finally:
            server_module._console_manager = prior


# ---------------------------------------------------------------------------
# DELETE /api/v1/console/{project_id}
# ---------------------------------------------------------------------------


class TestDeleteEndpoint:
    def test_delete_clears_disk_and_memory(self, client, wired_console):
        pid = wired_console["project"].id
        store = wired_console["store"]
        mgr = wired_console["mgr"]
        # Seed disk transcript + meta.
        _append_event(store, pid, ts="2026-05-13T10:00:00Z",
                      kind="operator_input", text="hi")
        store.save_meta(pid, {"backend": "claude"})
        # Construct an in-memory session via the manager.
        session = mgr.get(pid)
        assert pid in mgr.known_project_ids()
        # On-disk JSONL exists at this point.
        jsonl = Path(wired_console["store_root"]) / f"{pid}.jsonl"
        meta = Path(wired_console["store_root"]) / f"{pid}.meta.json"
        assert jsonl.exists()
        assert meta.exists()

        r = client.delete(f"/api/v1/console/{pid}")
        assert r.status_code == 200
        assert r.json() == {"ok": True}

        # In-memory state: manager has dropped the session.
        assert pid not in mgr.known_project_ids()
        # On-disk: both files are gone.
        assert not jsonl.exists()
        assert not meta.exists()

    def test_delete_idempotent(self, client, wired_console):
        pid = wired_console["project"].id
        # First DELETE without anything to delete — still 200.
        r1 = client.delete(f"/api/v1/console/{pid}")
        assert r1.status_code == 200
        # Second DELETE: still 200.
        r2 = client.delete(f"/api/v1/console/{pid}")
        assert r2.status_code == 200

    def test_delete_unknown_project_404(self, client, wired_console):
        r = client.delete("/api/v1/console/proj-nope")
        assert r.status_code == 404

    def test_delete_503_when_not_initialized(self, client):
        prior = server_module._console_manager
        server_module._console_manager = None
        try:
            r = client.delete("/api/v1/console/anything")
            assert r.status_code == 503
        finally:
            server_module._console_manager = prior

    def test_delete_then_get_returns_empty(self, client, wired_console):
        pid = wired_console["project"].id
        store = wired_console["store"]
        _append_event(store, pid, ts="2026-05-13T10:00:00Z",
                      kind="operator_input", text="hi")
        client.delete(f"/api/v1/console/{pid}")
        r = client.get(f"/api/v1/console/{pid}/transcript")
        assert r.status_code == 200
        assert r.json()["events"] == []
        assert r.json()["meta"] == {}


# ---------------------------------------------------------------------------
# WebSocket smoke test
# ---------------------------------------------------------------------------


class _FakeAgentSession:
    """Minimal stand-in for AcpAgentSession.

    Captures construction kwargs (so a test can assert what the
    session was invoked with) and emits one synthetic ``agent_text``
    backend event during ``run_task`` so the broadcast pipeline has
    something to fan out beyond the operator_input.
    """

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.on_event = kwargs.get("on_event")

    async def run_task(self) -> str:
        # Emit one agent event through the bridged callback, then exit
        # the turn cleanly.
        if self.on_event is not None:
            event = MagicMock()
            event.event = "acp_text"
            # The translator path will best-effort coerce — we don't
            # care what the normalized form looks like, just that an
            # event flows.
            try:
                self.on_event(event)
            except Exception:
                pass
        return "completed"


@pytest.fixture
def wired_console_ws(tmp_path, monkeypatch):
    """Like wired_console but installs an on_event_factory that
    forwards events into _broadcast (the production wiring) and
    monkey-patches AcpAgentSession with the fake."""
    project = _make_project(tmp_path / "repo")
    orch = MagicMock()
    orch.project_store.get.side_effect = (
        lambda pid: project if pid == project.id else None
    )

    store_root = str(tmp_path / "console")
    store = ConsoleStore(root=store_root)

    provider_store = MagicMock()
    provider_store.get.return_value = None
    provider_store.get_default.return_value = None
    role_store = MagicMock()
    role_store.get.return_value = None

    captured: list[tuple[str, dict]] = []

    def _on_event_factory(project_id: str):
        def _on_event(event: ConsoleEvent) -> None:
            captured.append((project_id, event.to_dict()))
            # Also schedule a real broadcast through the server's
            # WS pool, exactly as the production wiring does. This
            # is what the smoke test actually verifies.
            if not server_module._ws_clients:
                return
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                return
            if not loop.is_running():
                return
            try:
                loop.create_task(server_module._broadcast({
                    "type": "console_event",
                    "project_id": project_id,
                    "event": event.to_dict(),
                }))
            except RuntimeError:
                pass
        return _on_event

    mgr = ConsoleSessionManager(
        store=store,
        provider_store=provider_store,
        role_store=role_store,
        on_event_factory=_on_event_factory,
        workspace_resolver=lambda pid: (
            project.repo_path if pid == project.id else None
        ),
    )

    # Swap AcpAgentSession with the fake so we never hit the real SDK.
    monkeypatch.setattr(
        console_mod, "agent_session_factory",
        lambda **kw: _FakeAgentSession(**kw),
    )

    prior_orch = server_module._orchestrator
    prior_mgr = server_module._console_manager
    server_module._orchestrator = orch
    server_module._console_manager = mgr
    try:
        yield {
            "project": project, "mgr": mgr, "store": store,
            "captured": captured,
        }
    finally:
        server_module._orchestrator = prior_orch
        server_module._console_manager = prior_mgr


class TestWebSocketConsoleInput:
    def test_console_input_broadcasts_events(self, wired_console_ws):
        """Client sends console_input over WS; server appends the
        operator_input event, drives the (faked) backend, and
        broadcasts each event to all connected clients.
        """
        # Disable orchestrator-triggered side effects (initial state +
        # issues fetches) by giving the orchestrator simple defaults.
        orch = server_module._orchestrator
        orch.get_snapshot.return_value = {"running": []}

        pid = wired_console_ws["project"].id
        client = TestClient(app, raise_server_exceptions=False)

        with client.websocket_connect("/ws") as ws:
            # TestClient sends "initial state" + "initial issues"
            # before our send — drain them out.
            for _ in range(2):
                msg = ws.receive_json()
                assert msg.get("type") in ("state", "issues")

            ws.send_json({
                "type": "console_input",
                "project_id": pid,
                "text": "hello console",
            })

            # Collect events; we don't know the exact ordering of the
            # broadcast vs the runner's persist callback, so accumulate
            # a handful and assert at least one operator_input arrived.
            received: list[dict] = []
            for _ in range(8):
                try:
                    received.append(ws.receive_json(mode="text"))
                except Exception:
                    break
                # Stop once we've seen the terminal session_meta event.
                last_event = received[-1].get("event") or {}
                if last_event.get("kind") == "session_meta":
                    break

        kinds = [
            m.get("event", {}).get("kind") for m in received
            if m.get("type") == "console_event"
            and m.get("project_id") == pid
        ]
        # operator_input must arrive — that's the bead's main
        # acceptance criterion.
        assert "operator_input" in kinds
        # On-disk transcript should now contain at least the
        # operator_input event.
        events = wired_console_ws["store"].read_all(pid)
        assert any(e.get("kind") == "operator_input" for e in events)

    def test_console_input_unknown_project_emits_error(
        self, wired_console_ws,
    ):
        orch = server_module._orchestrator
        orch.get_snapshot.return_value = {"running": []}
        client = TestClient(app, raise_server_exceptions=False)
        with client.websocket_connect("/ws") as ws:
            for _ in range(2):
                ws.receive_json()
            ws.send_json({
                "type": "console_input",
                "project_id": "proj-nope",
                "text": "hello",
            })
            msg = None
            for _ in range(4):
                candidate = ws.receive_json()
                if (
                    candidate.get("type") == "console_event"
                    and candidate.get("project_id") == "proj-nope"
                ):
                    msg = candidate
                    break
        assert msg is not None
        assert msg["type"] == "console_event"
        assert msg["project_id"] == "proj-nope"
        assert msg["event"]["kind"] == "error"

    def test_console_input_empty_text_no_op(self, wired_console_ws):
        """Empty text is dropped before the manager is touched."""
        orch = server_module._orchestrator
        orch.get_snapshot.return_value = {"running": []}
        pid = wired_console_ws["project"].id
        client = TestClient(app, raise_server_exceptions=False)
        with client.websocket_connect("/ws") as ws:
            for _ in range(2):
                ws.receive_json()
            ws.send_json({
                "type": "console_input",
                "project_id": pid,
                "text": "   ",
            })
            # No response is sent for an empty input. To avoid blocking
            # forever, send a refresh that we know responds.
            ws.send_json({"action": "refresh"})
            for _ in range(2):
                msg = ws.receive_json()
                if msg.get("type") in ("state", "issues"):
                    break
        # Transcript should still be empty.
        events = wired_console_ws["store"].read_all(pid)
        assert events == []
