"""Two-phase listener cutover regressions for OOMPAH-1097."""

from __future__ import annotations

import asyncio
import json
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import WebSocketDisconnect
from starlette.requests import Request
from starlette.responses import JSONResponse

from oompah import server


def _request(method: str, path: str) -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 1),
            "server": ("127.0.0.1", 8090),
        }
    )


@pytest.mark.asyncio
async def test_active_gate_drains_before_webhooks_and_listener_cutover() -> None:
    """A retained standalone gate cannot take the listener down early."""

    order: list[str] = []
    drain_started = asyncio.Event()
    release_gate = asyncio.Event()

    class _Orchestrator:
        wants_restart = True
        _stopping = True

        def stop_threadsafe(self):
            return None

        async def stop_until_safe(self) -> None:
            order.append("safe-stop-started")
            drain_started.set()
            await release_gate.wait()
            order.append("safe-stop-finished")

        def check_and_recover_dispatch_loop(self) -> None:
            raise AssertionError("restart was already requested")

    class _Transport:
        def __init__(self, name: str) -> None:
            self.name = name
            self.stop_calls = 0

        async def stop(self) -> None:
            self.stop_calls += 1
            order.append(self.name)

    webhook = _Transport("webhook-stop")
    gitlab = _Transport("gitlab-stop")
    orchestrator = _Orchestrator()
    cutover = server._ListenerCutoverCoordinator(
        orchestrator,
        webhook,
        gitlab,
    )
    listener = SimpleNamespace(
        closed=False,
        websocket_connected=True,
        health_requests=0,
        state_requests=0,
    )

    def close_listener(restart_requested: bool) -> None:
        assert restart_requested is True
        listener.closed = True
        listener.websocket_connected = False
        order.append("listener-close")

    thread = MagicMock()
    thread.is_alive.return_value = True
    supervisor = asyncio.create_task(
        server._supervise_listener_cutover(
            orchestrator,
            thread,
            cutover,
            close_listener=close_listener,
            poll_interval_seconds=0,
        )
    )

    await asyncio.wait_for(drain_started.wait(), timeout=1)
    # Health, state, and the established WebSocket are all represented by the
    # still-open listener while the exact standalone operation owns drain.
    listener.health_requests += 1
    listener.state_requests += 1
    health = await server.healthz()
    assert health.status_code == 200
    assert json.loads(bytes(health.body))["status"] == "ok"
    assert listener.closed is False
    assert listener.websocket_connected is True
    assert webhook.stop_calls == 0
    assert gitlab.stop_calls == 0

    release_gate.set()
    await asyncio.wait_for(supervisor, timeout=1)

    assert order == [
        "safe-stop-started",
        "safe-stop-finished",
        "webhook-stop",
        "gitlab-stop",
        "listener-close",
    ]
    assert listener.health_requests == 1
    assert listener.state_requests == 1
    assert listener.closed is True
    assert listener.websocket_connected is False

    # Lifespan/finally cleanup reuses the same exact owner.
    await cutover.prepare()
    assert webhook.stop_calls == 1
    assert gitlab.stop_calls == 1


@pytest.mark.asyncio
async def test_restart_drain_serves_reads_and_rejects_new_mutations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The old listener becomes observability-only during retained drain."""

    monkeypatch.setattr(
        server,
        "_orchestrator",
        SimpleNamespace(wants_restart=True, _stopping=True),
    )
    downstream = AsyncMock(return_value=JSONResponse({"ok": True}))

    blocked = await server._restart_drain_mutation_fence(
        _request("POST", "/api/v1/issues"),
        downstream,
    )
    assert blocked.status_code == 503
    assert blocked.headers["retry-after"] == "1"
    assert json.loads(bytes(blocked.body))["error"]["code"] == "restart_draining"
    downstream.assert_not_awaited()

    lifecycle_mutation = await server._restart_drain_mutation_fence(
        _request("POST", "/api/v1/orchestrator/resume"),
        downstream,
    )
    assert lifecycle_mutation.status_code == 503
    downstream.assert_not_awaited()

    for method, path in (
        ("GET", "/healthz"),
        ("GET", "/api/v1/state"),
        ("GET", "/api/v1/issues"),
        ("POST", "/api/v1/orchestrator/restart"),
        ("POST", "/api/v1/webhooks/github"),
    ):
        response = await server._restart_drain_mutation_fence(
            _request(method, path),
            downstream,
        )
        assert response.status_code == 200

    assert downstream.await_count == 5


@pytest.mark.asyncio
async def test_mutations_are_unfenced_before_restart_cutover(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        server,
        "_orchestrator",
        SimpleNamespace(wants_restart=False, _stopping=False),
    )
    downstream = AsyncMock(return_value=JSONResponse({"ok": True}))

    response = await server._restart_drain_mutation_fence(
        _request("PATCH", "/api/v1/issues/OOMPAH-1097"),
        downstream,
    )

    assert response.status_code == 200
    downstream.assert_awaited_once()


@pytest.mark.asyncio
async def test_restart_drain_rejects_console_input_before_session_send(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: retained WebSockets cannot start a new ACP turn."""

    orchestrator = SimpleNamespace(wants_restart=True, _stopping=True)
    manager = MagicMock()
    session = MagicMock()
    session.send = AsyncMock()
    manager.get.return_value = session
    send_ws = AsyncMock()
    monkeypatch.setattr(server, "_orchestrator", orchestrator)
    monkeypatch.setattr(server, "_console_manager", manager)
    monkeypatch.setattr(server, "_send_ws", send_ws)

    await server._handle_console_input(
        MagicMock(),
        {
            "type": "console_input",
            "project_id": "project-1",
            "text": "start a new provider turn",
        },
    )

    manager.get.assert_not_called()
    session.send.assert_not_awaited()
    rejection = send_ws.await_args.args[1]
    assert rejection["type"] == "console_event"
    assert rejection["event"]["code"] == "restart_draining"
    assert rejection["event"]["retryable"] is True


@pytest.mark.asyncio
async def test_console_input_rechecks_drain_after_session_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A drain winning during lookup is fenced before queue admission."""

    orchestrator = SimpleNamespace(
        wants_restart=False,
        _stopping=False,
        project_store=SimpleNamespace(get=lambda _project_id: object()),
    )
    session = SimpleNamespace(send=AsyncMock())
    manager = MagicMock()

    def _start_drain(_project_id: str):
        orchestrator.wants_restart = True
        orchestrator._stopping = True
        return session

    manager.get.side_effect = _start_drain
    send_ws = AsyncMock()
    monkeypatch.setattr(server, "_orchestrator", orchestrator)
    monkeypatch.setattr(server, "_console_manager", manager)
    monkeypatch.setattr(server, "_send_ws", send_ws)

    await server._handle_console_input(
        MagicMock(),
        {
            "type": "console_input",
            "project_id": "project-1",
            "text": "race restart",
        },
    )

    session.send.assert_not_awaited()
    assert send_ws.await_args.args[1]["event"]["code"] == "restart_draining"


def test_console_turn_admission_uses_exact_provider_lifecycle_fence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orchestrator = SimpleNamespace(
        wants_restart=False,
        _stopping=False,
        _provider_admission_lock=threading.RLock(),
    )
    monkeypatch.setattr(server, "_orchestrator", orchestrator)

    assert server._console_turn_admission_error(orchestrator) is None
    with orchestrator._provider_admission_lock:
        orchestrator.wants_restart = True
        orchestrator._stopping = True
    assert "draining for restart" in str(
        server._console_turn_admission_error(orchestrator)
    )

    monkeypatch.setattr(server, "_orchestrator", SimpleNamespace())
    assert (
        server._console_turn_admission_error(orchestrator)
        == "console provider admission owner changed"
    )


@pytest.mark.asyncio
async def test_retained_websocket_keeps_read_only_messages_during_drain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ping, refresh, and full_sync remain usable while mutations reject."""

    class _WebSocket:
        def __init__(self) -> None:
            self.messages = iter(
                (
                    {"action": "ping"},
                    {"action": "refresh"},
                    {"action": "full_sync"},
                    {
                        "type": "console_input",
                        "project_id": "project-1",
                        "text": "must reject",
                    },
                )
            )

        async def accept(self) -> None:
            return None

        async def receive_text(self) -> str:
            try:
                return json.dumps(next(self.messages))
            except StopIteration as exc:
                raise WebSocketDisconnect() from exc

    orchestrator = SimpleNamespace(wants_restart=True, _stopping=True)
    ws = _WebSocket()
    send_ws = AsyncMock()
    broadcast = AsyncMock()
    full_sync = AsyncMock()
    console_input = AsyncMock()
    monkeypatch.setattr(server, "_orchestrator", orchestrator)
    monkeypatch.setattr(server, "_ws_clients", set())
    monkeypatch.setattr(server, "_send_ws", send_ws)
    monkeypatch.setattr(
        server,
        "_current_state_message",
        MagicMock(return_value={"type": "state", "data": {}}),
    )
    monkeypatch.setattr(
        server,
        "_run_api_io",
        AsyncMock(return_value=({"issues": []}, 1)),
    )
    monkeypatch.setattr(
        server,
        "_ensure_issues_snapshot_refresh",
        AsyncMock(),
    )
    monkeypatch.setattr(server, "broadcast_issues", broadcast)
    monkeypatch.setattr(server, "_handle_full_sync", full_sync)
    monkeypatch.setattr(server, "_handle_console_input", console_input)

    await server.websocket_endpoint(ws)

    sent = [call.args[1] for call in send_ws.await_args_list]
    assert any(message.get("type") == "pong" for message in sent)
    assert broadcast.await_count == 1
    full_sync.assert_awaited_once_with(ws, orchestrator)
    console_input.assert_not_awaited()
    rejection = next(
        message
        for message in sent
        if message.get("type") == "console_event"
        and (message.get("event") or {}).get("code") == "restart_draining"
    )
    assert rejection["project_id"] == "project-1"


@pytest.mark.asyncio
async def test_unexpected_orchestrator_exit_also_prepares_before_close() -> None:
    """An abnormal scheduler exit retains the same fail-closed ordering."""

    order: list[str] = []
    orchestrator = SimpleNamespace(
        wants_restart=False,
        stop_threadsafe=lambda: None,
        stop_until_safe=AsyncMock(side_effect=lambda: order.append("safe-stop")),
        check_and_recover_dispatch_loop=MagicMock(),
    )
    webhook = SimpleNamespace(
        stop=AsyncMock(side_effect=lambda: order.append("webhook-stop"))
    )
    gitlab = SimpleNamespace(
        stop=AsyncMock(side_effect=lambda: order.append("gitlab-stop"))
    )
    cutover = server._ListenerCutoverCoordinator(orchestrator, webhook, gitlab)
    thread = MagicMock()
    thread.is_alive.return_value = False

    await server._supervise_listener_cutover(
        orchestrator,
        thread,
        cutover,
        close_listener=lambda restart: order.append(f"listener-close:{restart}"),
        unexpected_exit=lambda: order.append("unexpected-exit"),
        poll_interval_seconds=0,
    )

    assert order == [
        "unexpected-exit",
        "safe-stop",
        "webhook-stop",
        "gitlab-stop",
        "listener-close:False",
    ]


@pytest.mark.asyncio
async def test_uvicorn_entrypoint_keeps_listener_open_until_cutover(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The default entry point asks Uvicorn to exit only after preparation."""

    from oompah import __main__ as main_module
    import uvicorn
    import watchfiles

    order: list[str] = []
    drain_started = asyncio.Event()
    release_gate = asyncio.Event()
    run_finished = threading.Event()
    server_started = asyncio.Event()

    class _Orchestrator:
        wants_restart = True
        _stopping = True

        async def run(self) -> None:
            await asyncio.to_thread(run_finished.wait)

        def stop_threadsafe(self):
            return None

        async def stop_until_safe(self) -> None:
            order.append("safe-stop-started")
            drain_started.set()
            await release_gate.wait()
            order.append("safe-stop-finished")
            run_finished.set()

        def check_and_recover_dispatch_loop(self) -> None:
            raise AssertionError("restart was already requested")

    class _Transport:
        async def start(self) -> None:
            return None

        async def stop(self) -> None:
            order.append(self.name)

        def __init__(self, name: str) -> None:
            self.name = name

    class _Server:
        instances: list["_Server"] = []

        def __init__(self, _config) -> None:
            self.should_exit = False
            self.instances.append(self)

        async def serve(self) -> None:
            server_started.set()
            while not self.should_exit:
                await asyncio.sleep(0)
            order.append("listener-close")

    async def _idle_watch(*_args, **_kwargs):
        while True:
            await asyncio.sleep(3600)
            yield set()

    orchestrator = _Orchestrator()
    services = SimpleNamespace(
        port=8090,
        orchestrator=orchestrator,
        webhook_forwarder=_Transport("webhook-stop"),
        gitlab_hook_manager=_Transport("gitlab-stop"),
        http_credentials=None,
        actor_map=None,
    )

    async def _setup_services(*_args, **_kwargs):
        return services

    monkeypatch.setattr("oompah.bootstrap.setup_services", _setup_services)
    monkeypatch.setattr(uvicorn, "Server", _Server)
    monkeypatch.setattr(watchfiles, "awatch", _idle_watch)
    monkeypatch.setattr("oompah.server.set_orchestrator", MagicMock())
    monkeypatch.setattr("oompah.server.set_gitlab_hook_manager", MagicMock())
    monkeypatch.setattr("oompah.server.set_http_credentials", MagicMock())
    monkeypatch.setattr("oompah.server.set_actor_map", MagicMock())
    monkeypatch.setattr("oompah.server.set_api_event_loop", MagicMock())

    run_task = asyncio.create_task(main_module._run("WORKFLOW.md", None))
    await asyncio.wait_for(server_started.wait(), timeout=1)
    await asyncio.wait_for(drain_started.wait(), timeout=1)

    assert _Server.instances[0].should_exit is False
    assert "listener-close" not in order
    health = await server.healthz()
    assert health.status_code == 200

    release_gate.set()
    assert await asyncio.wait_for(run_task, timeout=2) is True
    assert order == [
        "safe-stop-started",
        "safe-stop-finished",
        "webhook-stop",
        "gitlab-stop",
        "listener-close",
    ]


@pytest.mark.asyncio
async def test_granian_signals_parent_only_after_listener_cutover_preparation(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The embedded Granian lifecycle uses the same two-phase boundary."""

    import watchfiles

    order: list[str] = []
    drain_started = asyncio.Event()
    release_gate = asyncio.Event()
    parent_signalled = asyncio.Event()
    run_finished = threading.Event()

    class _Orchestrator:
        wants_restart = True
        _stopping = True

        async def run(self) -> None:
            await asyncio.to_thread(run_finished.wait)

        def stop_threadsafe(self):
            return None

        async def stop_until_safe(self) -> None:
            order.append("safe-stop-started")
            drain_started.set()
            await release_gate.wait()
            order.append("safe-stop-finished")
            run_finished.set()

        def check_and_recover_dispatch_loop(self) -> None:
            raise AssertionError("restart was already requested")

    class _Transport:
        def __init__(self, name: str) -> None:
            self.name = name

        async def start(self) -> None:
            return None

        async def stop(self) -> None:
            order.append(self.name)

    async def _idle_watch(*_args, **_kwargs):
        while True:
            await asyncio.sleep(3600)
            yield set()

    services = SimpleNamespace(
        orchestrator=_Orchestrator(),
        webhook_forwarder=_Transport("webhook-stop"),
        gitlab_hook_manager=_Transport("gitlab-stop"),
        http_credentials=None,
        actor_map=None,
    )

    async def _setup_services(*_args, **_kwargs):
        return services

    def _signal_parent(_pid: int, _signal: int) -> None:
        order.append("listener-close-signal")
        parent_signalled.set()

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OOMPAH_EMBED_ORCHESTRATOR", "1")
    monkeypatch.setattr("oompah.bootstrap.setup_services", _setup_services)
    monkeypatch.setattr(
        "oompah.bootstrap.attach_webhook_forwarder_alerts", MagicMock()
    )
    monkeypatch.setattr(watchfiles, "awatch", _idle_watch)
    monkeypatch.setattr(server, "set_orchestrator", MagicMock())
    monkeypatch.setattr(server, "set_gitlab_hook_manager", MagicMock())
    monkeypatch.setattr(server, "set_http_credentials", MagicMock())
    monkeypatch.setattr(server, "set_actor_map", MagicMock())
    monkeypatch.setattr(server.os, "kill", _signal_parent)

    async with server._service_lifespan(server.app):
        await asyncio.wait_for(drain_started.wait(), timeout=1)
        assert parent_signalled.is_set() is False
        assert order == ["safe-stop-started"]
        release_gate.set()
        await asyncio.wait_for(parent_signalled.wait(), timeout=2)
        assert order == [
            "safe-stop-started",
            "safe-stop-finished",
            "webhook-stop",
            "gitlab-stop",
            "listener-close-signal",
        ]

    assert (tmp_path / server._GRANIAN_RESTART_SENTINEL).is_file()
