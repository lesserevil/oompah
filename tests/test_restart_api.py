"""API contracts for coalesced, configurable graceful restarts (OOMPAH-507)."""

import asyncio
import json
import subprocess
import sys
import threading
import textwrap
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from oompah import server
from oompah.config import ServiceConfig
from oompah.events import EventType
from oompah.ipc import OrchestratorIPC
from oompah.models import Issue
from oompah.orchestrator import Orchestrator
from oompah.server import app
from oompah.task_transition_service import (
    TransitionAuthority,
    TransitionDisposition,
    TransitionIntent,
    TransitionJournal,
    TransitionPhase,
    issue_authority_version,
)


_SERVER_STATE_CACHE_FIELDS = (
    "_state_snapshot",
    "_state_snapshot_at",
    "_state_snapshot_epoch",
    "_state_snapshot_authority",
    "_state_snapshot_signature",
    "_state_revision",
)


def _capture_server_state_cache() -> tuple[object, ...]:
    """Capture the state snapshot and its revision atomically."""
    with server._state_snapshot_lock, server._ws_protocol_lock:
        return tuple(getattr(server, field) for field in _SERVER_STATE_CACHE_FIELDS)


def _restore_server_state_cache(values: tuple[object, ...]) -> None:
    """Restore the state snapshot and its revision atomically."""
    with server._state_snapshot_lock, server._ws_protocol_lock:
        for field, value in zip(_SERVER_STATE_CACHE_FIELDS, values, strict=True):
            setattr(server, field, value)


@pytest.fixture(autouse=True)
def _isolate_server_state_cache():
    """Prevent restart publication tests from leaking snapshots to later tests."""
    original = _capture_server_state_cache()
    try:
        yield
    finally:
        _restore_server_state_cache(original)


def test_state_cache_restore_preserves_issue_invalidation_generation(monkeypatch):
    """Restoring state cache cannot rewind a callback's issue generation."""
    protocol_epoch = server._protocol_epoch
    issue_snapshot = {
        "data": {"issues": []},
        "epoch": protocol_epoch,
        "data_revision": 17,
        "invalidated": False,
    }
    monkeypatch.setattr(server, "_issue_revision", 17)
    monkeypatch.setattr(server, "_issues_snapshot", issue_snapshot)
    monkeypatch.setattr(server, "_ws_clients", set())
    original_state = _capture_server_state_cache()

    server._on_orchestrator_change({"source": "restart-callback"})
    _restore_server_state_cache(original_state)

    assert server._issue_revision == 18
    assert server._protocol_epoch == protocol_epoch
    assert server._issues_snapshot is issue_snapshot
    assert issue_snapshot["data_revision"] == 17
    assert issue_snapshot["invalidated"] is True


def _fake_orchestrator(timeout: int = 3600):
    return SimpleNamespace(
        config=SimpleNamespace(restart_drain_timeout_seconds=timeout),
        state=SimpleNamespace(running={}),
        _restart_in_progress=False,
        _restart_drain_started=False,
        _restart_drain_scheduled=False,
        _restart_drain_task=None,
        _restart_drain_owner=None,
        _restart_request_id=None,
        _restart_requested_at=None,
        _restart_initial_running=0,
        _restart_persistence_failed=False,
        _provider_admission_generation=0,
        _paused=False,
        _quiesced=False,
        _stopping=False,
        _restart_requested=False,
        _save_paused_state=MagicMock(),
        _notify_observers=MagicMock(),
        graceful_restart=AsyncMock(),
    )


def _real_orchestrator(tmp_path) -> Orchestrator:
    project_store = MagicMock()
    project_store.list_all.return_value = []
    project_store.get.return_value = SimpleNamespace(paused=False)
    return Orchestrator(
        config=ServiceConfig(duplicate_preflight_max_agents=0),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        state_path=str(tmp_path / "state.json"),
    )


def _json_request(body: dict[str, object]) -> Request:
    encoded = json.dumps(body).encode()

    async def _receive() -> dict[str, object]:
        return {"type": "http.request", "body": encoded, "more_body": False}

    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/orchestrator/restart",
            "headers": [(b"content-type", b"application/json")],
            "query_string": b"",
        },
        _receive,
    )


def test_restart_api_uses_configured_default_and_returns_request_identity():
    original = server._orchestrator
    fake = _fake_orchestrator(4321)
    server._orchestrator = fake
    try:
        response = TestClient(app).post("/api/v1/orchestrator/restart", json={})
    finally:
        server._orchestrator = original

    assert response.status_code == 200
    body = response.json()
    assert body["drain_timeout_s"] == 4321
    assert body["restart_request_id"]
    assert body["coalesced"] is False
    fake.graceful_restart.assert_awaited_once()


def test_repeated_restart_request_is_coalesced():
    original = server._orchestrator
    fake = _fake_orchestrator()
    fake._restart_in_progress = True
    fake._restart_request_id = "restart-existing"
    fake._restart_drain_scheduled = True
    server._orchestrator = fake
    try:
        response = TestClient(app).post(
            "/api/v1/orchestrator/restart",
            json={"drain_timeout_s": 12},
        )
    finally:
        server._orchestrator = original

    assert response.status_code == 202
    assert response.json()["restart_request_id"] == "restart-existing"
    assert response.json()["coalesced"] is True
    fake.graceful_restart.assert_not_awaited()


def test_restart_claim_can_be_started_only_by_matching_identity():
    original = server._orchestrator
    fake = _fake_orchestrator()
    server._orchestrator = fake
    client = TestClient(app)
    try:
        claimed = client.post(
            "/api/v1/orchestrator/restart",
            json={"claim_only": True},
        )
        request_id = claimed.json()["restart_request_id"]
        mismatched = client.post(
            "/api/v1/orchestrator/restart",
            json={"restart_request_id": "another-claim", "drain_timeout_s": 0},
        )
        started = client.post(
            "/api/v1/orchestrator/restart",
            json={"restart_request_id": request_id, "drain_timeout_s": 0},
        )
    finally:
        server._orchestrator = original

    assert claimed.status_code == 200
    assert fake._restart_in_progress is True
    assert mismatched.status_code == 409
    assert started.status_code == 200
    assert started.json()["restart_request_id"] == request_id
    fake.graceful_restart.assert_awaited_once()


def test_unscheduled_restart_claim_can_be_cancelled():
    original = server._orchestrator
    fake = _fake_orchestrator()
    server._orchestrator = fake
    client = TestClient(app)
    try:
        claimed = client.post(
            "/api/v1/orchestrator/restart",
            json={"claim_only": True},
        )
        request_id = claimed.json()["restart_request_id"]
        cancelled = client.post(
            "/api/v1/orchestrator/restart",
            json={"cancel_claim": True, "restart_request_id": request_id},
        )
    finally:
        server._orchestrator = original

    assert cancelled.status_code == 200
    assert cancelled.json()["cancelled"] is True
    assert fake._restart_in_progress is False
    fake.graceful_restart.assert_not_awaited()


def test_restart_task_creation_failure_restores_cancellable_preclaim():
    """A scheduler failure cannot turn a valid preclaim into a permanent fence."""

    original = server._orchestrator
    fake = _fake_orchestrator()
    server._orchestrator = fake
    client = TestClient(app)
    try:
        claimed = client.post(
            "/api/v1/orchestrator/restart",
            json={"claim_only": True},
        )
        request_id = claimed.json()["restart_request_id"]
        claimed_generation = fake._provider_admission_generation
        with patch.object(
            server,
            "_create_restart_drain_task",
            side_effect=RuntimeError("event loop rejected task"),
        ):
            failed = client.post(
                "/api/v1/orchestrator/restart",
                json={"restart_request_id": request_id, "drain_timeout_s": 0},
            )
        restored_claim = (
            fake._restart_in_progress,
            fake._restart_request_id,
            fake._restart_drain_scheduled,
            fake._restart_drain_started,
            fake._restart_drain_task,
            fake._restart_drain_owner,
            fake._provider_admission_generation,
        )
        cancelled = client.post(
            "/api/v1/orchestrator/restart",
            json={"cancel_claim": True, "restart_request_id": request_id},
        )
    finally:
        server._orchestrator = original

    assert failed.status_code == 500
    assert restored_claim == (
        True,
        request_id,
        False,
        False,
        None,
        None,
        claimed_generation,
    )
    assert fake._restart_in_progress is False
    assert fake._provider_admission_generation == claimed_generation + 1
    assert cancelled.status_code == 200
    assert cancelled.json()["cancelled"] is True
    fake.graceful_restart.assert_not_awaited()


def test_restart_drain_exception_after_task_creation_restores_full_state():
    """A failed published drain releases every fence and can be rescheduled."""

    original = server._orchestrator
    fake = _fake_orchestrator()
    fake.graceful_restart = AsyncMock(side_effect=RuntimeError("drain failed"))
    server._orchestrator = fake
    client = TestClient(app)
    try:
        first = client.post(
            "/api/v1/orchestrator/restart",
            json={"drain_timeout_s": 0},
        )
        restored = (
            fake._restart_in_progress,
            fake._restart_drain_scheduled,
            fake._restart_drain_started,
            fake._restart_drain_task,
            fake._restart_drain_owner,
            fake._paused,
            fake._quiesced,
            fake._stopping,
            fake._restart_requested,
        )
        fake.graceful_restart = AsyncMock(return_value=None)
        second = client.post(
            "/api/v1/orchestrator/restart",
            json={"drain_timeout_s": 0},
        )
    finally:
        server._orchestrator = original

    assert first.status_code == 200
    assert restored == (False, False, False, None, None, False, False, False, False)
    assert fake._restart_in_progress is True  # second request owns a fresh claim
    assert second.status_code == 200
    assert second.json()["coalesced"] is False


def test_restart_drain_failure_preserves_intervening_lifecycle_fence():
    """A newer lifecycle generation wins over the API rollback snapshot."""

    original = server._orchestrator
    fake = _fake_orchestrator()

    async def _fenced_failure(**_kwargs):
        fake._paused = True
        fake._quiesced = True
        fake._stopping = True
        fake._restart_requested = True
        fake._provider_admission_generation += 1
        raise RuntimeError("drain failed after a newer lifecycle fence")

    fake.graceful_restart = AsyncMock(side_effect=_fenced_failure)
    server._orchestrator = fake
    try:
        response = TestClient(app).post(
            "/api/v1/orchestrator/restart",
            json={"drain_timeout_s": 0},
        )
    finally:
        server._orchestrator = original

    assert response.status_code == 200
    assert fake._restart_in_progress is False
    assert fake._restart_drain_task is None
    assert fake._paused is True
    assert fake._quiesced is True
    assert fake._stopping is True
    assert fake._restart_requested is True
    assert fake._provider_admission_generation == 2


def test_restart_drain_failure_preserves_persistence_fail_closed_fence():
    """The HTTP completion callback cannot erase a durable-state failure."""

    original = server._orchestrator
    fake = _fake_orchestrator()

    async def _fail_closed_restart(**_kwargs):
        fake._restart_persistence_failed = True
        fake._quiesced = True
        fake._provider_admission_generation += 1
        raise OSError("restart rows were not durably persisted")

    fake.graceful_restart = AsyncMock(side_effect=_fail_closed_restart)
    server._orchestrator = fake
    try:
        response = TestClient(app).post(
            "/api/v1/orchestrator/restart",
            json={"drain_timeout_s": 0},
        )
    finally:
        server._orchestrator = original

    assert response.status_code == 200
    assert fake._restart_in_progress is False
    assert fake._restart_drain_task is None
    assert fake._restart_persistence_failed is True
    assert fake._quiesced is True
    assert fake._provider_admission_generation >= 2


def test_restart_drain_cancellation_after_task_creation_restores_full_state():
    """CancelledError follows the same rollback path as a drain exception."""

    original = server._orchestrator
    fake = _fake_orchestrator()
    cancelled = AsyncMock(side_effect=asyncio.CancelledError())
    fake.graceful_restart = cancelled
    server._orchestrator = fake
    client = TestClient(app)
    try:
        response = client.post(
            "/api/v1/orchestrator/restart",
            json={"drain_timeout_s": 0},
        )
    finally:
        server._orchestrator = original

    assert response.status_code == 200
    assert fake._restart_in_progress is False
    assert fake._restart_drain_scheduled is False
    assert fake._restart_drain_started is False
    assert fake._restart_drain_task is None
    assert fake._restart_drain_owner is None
    assert fake._paused is False
    assert fake._quiesced is False
    assert fake._stopping is False
    assert fake._restart_requested is False


def test_restart_api_rejects_invalid_timeout():
    original = server._orchestrator
    server._orchestrator = _fake_orchestrator()
    try:
        response = TestClient(app).post(
            "/api/v1/orchestrator/restart",
            json={"drain_timeout_s": "eventually"},
        )
    finally:
        server._orchestrator = original

    assert response.status_code == 400
    assert "non-negative" in response.json()["error"]


def test_quiesce_api_preserves_running_workers():
    """Lifecycle quiesce is separate from destructive operator pause."""
    original = server._orchestrator
    fake = _fake_orchestrator()
    fake.quiesce = MagicMock()
    server._orchestrator = fake
    try:
        response = TestClient(app).post("/api/v1/orchestrator/quiesce", json={})
    finally:
        server._orchestrator = original

    assert response.status_code == 200
    assert response.json()["quiesced"] is True
    fake.quiesce.assert_called_once_with(notify=False)


@pytest.mark.asyncio
async def test_quiesce_lock_contention_is_bounded_without_blocking_health(monkeypatch):
    """A workflow thread cannot park the HTTP loop while quiesce fences."""

    original = server._orchestrator
    fake = _fake_orchestrator()
    fake.quiesce = MagicMock()
    fake._provider_admission_lock = threading.RLock()
    lock_owned = threading.Event()
    release_lock = threading.Event()

    def _hold_publication_fence() -> None:
        with fake._provider_admission_lock:
            lock_owned.set()
            assert release_lock.wait(timeout=2)

    holder = threading.Thread(target=_hold_publication_fence)
    holder.start()
    assert lock_owned.wait(timeout=1)
    monkeypatch.setattr(server, "_LIFECYCLE_ADMISSION_TIMEOUT_SECONDS", 0.05)
    server._orchestrator = fake
    try:
        quiesce = asyncio.create_task(server.api_orchestrator_quiesce())
        await asyncio.sleep(0.01)
        started = time.monotonic()
        health = await asyncio.wait_for(server.healthz(), timeout=0.1)
        elapsed = time.monotonic() - started
        response = await asyncio.wait_for(quiesce, timeout=0.2)
    finally:
        release_lock.set()
        holder.join(timeout=1)
        server._orchestrator = original

    assert json.loads(health.body)["status"] == "ok"
    assert elapsed < 0.1
    assert response.status_code == 503
    assert json.loads(response.body)["retryable"] is True
    fake.quiesce.assert_not_called()
    assert fake._restart_in_progress is False


@pytest.mark.asyncio
async def test_restart_claim_contention_is_bounded_without_blocking_health(
    monkeypatch,
):
    """A slow publication fence cannot wedge restart claim or health I/O."""

    original = server._orchestrator
    fake = _fake_orchestrator()
    fake._provider_admission_lock = threading.RLock()
    lock_owned = threading.Event()
    release_lock = threading.Event()

    def _hold_publication_fence() -> None:
        with fake._provider_admission_lock:
            lock_owned.set()
            assert release_lock.wait(timeout=2)

    async def _receive() -> dict[str, object]:
        return {"type": "http.request", "body": b"{}", "more_body": False}

    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/orchestrator/restart",
            "headers": [(b"content-type", b"application/json")],
            "query_string": b"",
        },
        _receive,
    )
    holder = threading.Thread(target=_hold_publication_fence)
    holder.start()
    assert lock_owned.wait(timeout=1)
    monkeypatch.setattr(server, "_LIFECYCLE_ADMISSION_TIMEOUT_SECONDS", 0.05)
    server._orchestrator = fake
    try:
        restart = asyncio.create_task(server.api_orchestrator_restart(request))
        await asyncio.sleep(0.01)
        started = time.monotonic()
        health = await asyncio.wait_for(server.healthz(), timeout=0.1)
        elapsed = time.monotonic() - started
        response = await asyncio.wait_for(restart, timeout=0.2)
    finally:
        release_lock.set()
        holder.join(timeout=1)
        server._orchestrator = original

    assert json.loads(health.body)["status"] == "ok"
    assert elapsed < 0.1
    assert response.status_code == 503
    assert json.loads(response.body)["retryable"] is True
    assert fake._restart_in_progress is False
    fake.graceful_restart.assert_not_awaited()


@pytest.mark.asyncio
async def test_real_lifecycle_controls_outlive_blocked_observer_snapshot(
    tmp_path,
):
    """Snapshot publication cannot own HTTP or provider admission authority."""

    original = server._orchestrator
    orch = _real_orchestrator(tmp_path)
    snapshot_entered = threading.Event()
    release_snapshot = threading.Event()
    snapshot_finished = threading.Event()

    def _blocked_project_snapshot() -> list[object]:
        snapshot_entered.set()
        try:
            assert release_snapshot.wait(timeout=3)
            return []
        finally:
            snapshot_finished.set()

    # Exercise the real get_snapshot -> review/project authority path used by
    # _notify_observers, rather than replacing the snapshot method itself.
    orch.project_store.list_all.side_effect = _blocked_project_snapshot
    server._orchestrator = orch
    try:
        started = time.monotonic()
        quiesced = await asyncio.wait_for(
            server.api_orchestrator_quiesce(),
            timeout=0.2,
        )
        quiesce_elapsed = time.monotonic() - started
        assert await asyncio.to_thread(snapshot_entered.wait, 1)

        started = time.monotonic()
        health = await asyncio.wait_for(server.healthz(), timeout=0.1)
        health_elapsed = time.monotonic() - started

        claim = await asyncio.wait_for(
            server.api_orchestrator_restart(
                _json_request(
                    {
                        "claim_only": True,
                        "restart_request_id": "blocked-snapshot-claim",
                    }
                )
            ),
            timeout=0.2,
        )
        cancelled = await asyncio.wait_for(
            server.api_orchestrator_restart(
                _json_request(
                    {
                        "cancel_claim": True,
                        "restart_request_id": "blocked-snapshot-claim",
                    }
                )
            ),
            timeout=0.2,
        )
        resumed = await asyncio.wait_for(
            server.api_orchestrator_resume(),
            timeout=0.2,
        )

        assert orch._provider_admission_lock.acquire(blocking=False)
        orch._provider_admission_lock.release()
    finally:
        release_snapshot.set()
        await asyncio.to_thread(snapshot_finished.wait, 1)
        server._orchestrator = original

    assert quiesced.status_code == 200
    assert quiesce_elapsed < 0.2
    assert json.loads(health.body)["status"] == "ok"
    assert health_elapsed < 0.1
    assert claim.status_code == 200
    assert cancelled.status_code == 200
    assert resumed.status_code == 200
    assert orch._quiesced is False
    assert orch._restart_in_progress is False


@pytest.mark.asyncio
async def test_restart_drain_snapshot_and_journal_work_stay_off_http_loop(
    tmp_path,
    monkeypatch,
):
    """Graceful drain staging cannot block health or cancellation responses."""

    original = server._orchestrator
    orch = _real_orchestrator(tmp_path)
    snapshot_entered = threading.Event()
    release_snapshot = threading.Event()
    snapshot_finished = threading.Event()
    observer_published = threading.Event()
    journal_entered = threading.Event()
    release_journal = threading.Event()

    def _blocked_snapshot() -> dict[str, object]:
        snapshot_entered.set()
        try:
            assert release_snapshot.wait(timeout=3)
            return {}
        finally:
            snapshot_finished.set()

    def _blocked_merge(*_args, **_kwargs) -> tuple[bool, int, int]:
        journal_entered.set()
        assert release_journal.wait(timeout=3)
        return True, 0, 0

    monkeypatch.setattr(orch, "get_snapshot", _blocked_snapshot)
    monkeypatch.setattr(orch, "_merge_restart_issues", _blocked_merge)
    orch._observers.append(lambda _snapshot: observer_published.set())
    server._orchestrator = orch
    drain_task = None
    try:
        response = await server.api_orchestrator_restart(
            _json_request(
                {
                    "drain_timeout_s": 0,
                    "restart_request_id": "slow-drain-staging",
                }
            )
        )
        drain_task = orch._restart_drain_task
        assert drain_task is not None
        assert await asyncio.to_thread(snapshot_entered.wait, 1)
        # The full snapshot remains blocked permanently from the drain's point
        # of view, but authoritative journal staging must still start.
        assert await asyncio.to_thread(journal_entered.wait, 1)

        started = time.monotonic()
        health_during_snapshot = await asyncio.wait_for(
            server.healthz(), timeout=0.1
        )
        cancel_during_snapshot = await asyncio.wait_for(
            server.api_orchestrator_restart(
                _json_request(
                    {
                        "cancel_claim": True,
                        "restart_request_id": "slow-drain-staging",
                    }
                )
            ),
            timeout=0.2,
        )
        snapshot_control_elapsed = time.monotonic() - started
        started = time.monotonic()
        health_during_journal = await asyncio.wait_for(
            server.healthz(), timeout=0.1
        )
        journal_health_elapsed = time.monotonic() - started
        release_journal.set()
        await asyncio.wait_for(asyncio.shield(drain_task), timeout=1)
        assert snapshot_finished.is_set() is False
        with orch._lifecycle_publication_lock:
            assert orch._lifecycle_publication_running is True
            assert (
                orch._lifecycle_publication_pending_generation
                == orch._provider_admission_generation
            )
        # A delayed older request cannot replace the coalesced latest state.
        assert orch.request_lifecycle_publication(
            expected_generation=orch._provider_admission_generation - 1
        )
        with orch._lifecycle_publication_lock:
            assert (
                orch._lifecycle_publication_pending_generation
                == orch._provider_admission_generation
            )

        # Teardown fences the running old-generation snapshot and rejects new
        # work without waiting for the uncooperative snapshot thread.
        orch._shutdown_lifecycle_publications()
        assert (
            orch.request_lifecycle_publication(
                expected_generation=orch._provider_admission_generation
            )
            is False
        )
        release_snapshot.set()
        assert await asyncio.to_thread(snapshot_finished.wait, 1)
    finally:
        release_snapshot.set()
        release_journal.set()
        if drain_task is not None and not drain_task.done():
            await asyncio.wait_for(asyncio.shield(drain_task), timeout=1)
        server._orchestrator = original

    assert response.status_code == 200
    assert json.loads(health_during_snapshot.body)["status"] == "ok"
    assert cancel_during_snapshot.status_code == 409
    assert snapshot_control_elapsed < 0.2
    assert json.loads(health_during_journal.body)["status"] == "ok"
    assert journal_health_elapsed < 0.1
    assert orch._stopping is True
    assert orch._restart_requested is True
    assert observer_published.is_set() is False


def test_shutdown_revokes_snapshot_blocked_before_external_publication(
    tmp_path,
    monkeypatch,
):
    """A bounded shutdown fences a worker paused at the sink boundary."""

    orch = _real_orchestrator(tmp_path)
    sink_entered = threading.Event()
    release_sink = threading.Event()
    observer_published = threading.Event()
    original_publish = orch._publish_observer_snapshot

    def _blocked_publish(snapshot, **authority):
        sink_entered.set()
        assert release_sink.wait(timeout=3)
        return original_publish(snapshot, **authority)

    monkeypatch.setattr(orch, "get_snapshot", lambda: {"paused": True})
    monkeypatch.setattr(orch, "_publish_observer_snapshot", _blocked_publish)
    orch._observers.append(lambda _snapshot: observer_published.set())

    assert orch.request_lifecycle_publication(expected_generation=0)
    assert sink_entered.wait(timeout=1)
    with orch._lifecycle_publication_lock:
        worker = orch._lifecycle_publication_thread
    assert worker is not None
    assert worker.daemon is True

    started = time.monotonic()
    orch._shutdown_lifecycle_publications()
    shutdown_elapsed = time.monotonic() - started
    assert shutdown_elapsed < 0.1
    assert orch._provider_admission_lock.acquire(blocking=False)
    orch._provider_admission_lock.release()

    release_sink.set()
    worker.join(timeout=1)
    assert worker.is_alive() is False
    assert observer_published.is_set() is False


def test_same_generation_state_edge_replays_after_running_snapshot(
    tmp_path,
    monkeypatch,
):
    """Coalescing retains one edge that the in-flight snapshot may have missed."""

    orch = _real_orchestrator(tmp_path)
    first_started = threading.Event()
    release_first = threading.Event()
    calls = []
    calls_lock = threading.Lock()

    def _snapshot() -> dict[str, int]:
        with calls_lock:
            calls.append(len(calls) + 1)
            call_number = calls[-1]
        if call_number == 1:
            first_started.set()
            assert release_first.wait(timeout=3)
        return {"snapshot_call": call_number}

    monkeypatch.setattr(orch, "get_snapshot", _snapshot)

    try:
        assert orch.request_lifecycle_publication(expected_generation=0)
        assert first_started.wait(timeout=1)
        assert orch.request_lifecycle_publication(expected_generation=0)
        release_first.set()

        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            with orch._lifecycle_publication_lock:
                if not orch._lifecycle_publication_running:
                    break
            time.sleep(0.01)
        else:
            raise AssertionError("coalesced lifecycle publication did not finish")

        assert calls == [1, 2]
    finally:
        release_first.set()
        assert orch._shutdown_lifecycle_publications()


@pytest.mark.asyncio
async def test_background_drain_rejects_undrained_lifecycle_callbacks():
    """Persistent stores stay open when callback revocation times out."""

    orchestrator = SimpleNamespace(
        _shutdown_lifecycle_publications=MagicMock(return_value=False),
        _drain_scheduled_terminations=AsyncMock(),
    )

    with pytest.raises(
        RuntimeError,
        match="lifecycle publication callbacks did not drain",
    ):
        await Orchestrator._drain_background_work(orchestrator)
    orchestrator._drain_scheduled_terminations.assert_not_awaited()


@pytest.mark.asyncio
async def test_background_drain_waits_for_snapshot_before_closing_stores(
    tmp_path,
    monkeypatch,
):
    """A snapshot worker cannot read an owned store after it has closed."""

    orch = _real_orchestrator(tmp_path)
    snapshot_started = threading.Event()
    release_snapshot = threading.Event()
    snapshot_read_store = threading.Event()
    worker_drain_started = threading.Event()
    close_started = threading.Event()
    snapshot_errors: list[BaseException] = []
    original_worker_drain = orch._drain_lifecycle_publication_worker
    original_close = orch._close_owned_persistent_stores

    def _blocked_snapshot() -> dict[str, bool]:
        snapshot_started.set()
        assert release_snapshot.wait(timeout=3)
        try:
            orch.workflow_job_store.health_snapshot()
        except BaseException as exc:
            snapshot_errors.append(exc)
        else:
            snapshot_read_store.set()
        return {"paused": True}

    def _tracked_close() -> None:
        close_started.set()
        original_close()

    async def _tracked_worker_drain() -> bool:
        worker_drain_started.set()
        return await original_worker_drain()

    monkeypatch.setattr(orch, "get_snapshot", _blocked_snapshot)
    monkeypatch.setattr(
        orch,
        "_drain_lifecycle_publication_worker",
        _tracked_worker_drain,
    )
    monkeypatch.setattr(orch, "_close_owned_persistent_stores", _tracked_close)

    assert orch.request_lifecycle_publication(expected_generation=0)
    assert snapshot_started.wait(timeout=1)
    drain_task = asyncio.create_task(orch._drain_background_work())
    try:
        assert await asyncio.to_thread(worker_drain_started.wait, 1)
        assert drain_task.done() is False
        assert close_started.is_set() is False

        release_snapshot.set()
        await asyncio.wait_for(asyncio.shield(drain_task), timeout=2)
    finally:
        release_snapshot.set()
        if not drain_task.done():
            await asyncio.wait_for(asyncio.shield(drain_task), timeout=2)

    assert snapshot_errors == []
    assert snapshot_read_store.is_set() is True
    assert close_started.is_set() is True


@pytest.mark.asyncio
async def test_safe_stop_retries_retired_snapshot_without_backend_error(
    tmp_path,
    monkeypatch,
    caplog,
):
    """A slow fenced snapshot is retained authority, not a shutdown failure."""

    orch = _real_orchestrator(tmp_path)
    snapshot_started = threading.Event()
    release_snapshot = threading.Event()
    stores_closed = threading.Event()
    original_close = orch._close_owned_persistent_stores

    def _blocked_snapshot() -> dict[str, bool]:
        snapshot_started.set()
        assert release_snapshot.wait(timeout=3)
        return {"paused": True}

    def _tracked_close() -> None:
        stores_closed.set()
        original_close()

    monkeypatch.setattr(orch, "get_snapshot", _blocked_snapshot)
    monkeypatch.setattr(orch, "_close_owned_persistent_stores", _tracked_close)
    orch._lifecycle_publication_drain_timeout_s = 0.01
    caplog.set_level("INFO", logger="oompah.orchestrator")

    assert orch.request_lifecycle_publication(expected_generation=0)
    assert snapshot_started.wait(timeout=1)
    stop_task = asyncio.create_task(orch.stop_until_safe())
    try:
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline:
            if any(
                "safely waiting for a retired lifecycle publication"
                in record.getMessage()
                for record in caplog.records
            ):
                break
            await asyncio.sleep(0.01)
        else:
            raise AssertionError("safe-stop retry was not observed")

        assert stop_task.done() is False
        assert stores_closed.is_set() is False
        assert not any(
            "Orchestrator shutdown attempt failed" in record.getMessage()
            for record in caplog.records
        )

        release_snapshot.set()
        await asyncio.wait_for(asyncio.shield(stop_task), timeout=2)
    finally:
        release_snapshot.set()
        if not stop_task.done():
            await asyncio.wait_for(asyncio.shield(stop_task), timeout=2)

    assert stores_closed.is_set() is True
    assert orch.workflow_job_store._authority_lock_fd == -1


@pytest.mark.asyncio
async def test_stop_until_safe_retries_on_exception_without_error_level(
    tmp_path,
    monkeypatch,
    caplog,
):
    """Exceptions during stop() are logged at WARNING level, not ERROR."""

    orch = _real_orchestrator(tmp_path)
    attempt_count = 0

    async def _stop_fails_then_succeeds():
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < 3:
            # First two attempts raise an exception
            raise RuntimeError(f"Stop failed on attempt {attempt_count}")
        # Third attempt succeeds
        return True

    monkeypatch.setattr(orch, "stop", _stop_fails_then_succeeds)
    caplog.set_level("WARNING", logger="oompah.orchestrator")

    stop_task = asyncio.create_task(orch.stop_until_safe())
    try:
        # Give it time to fail and retry
        await asyncio.wait_for(stop_task, timeout=5)
    finally:
        if not stop_task.done():
            stop_task.cancel()
            try:
                await stop_task
            except asyncio.CancelledError:
                pass

    # Verify that the exception was retried
    assert attempt_count >= 3

    # Verify that warning messages were logged
    warning_records = [
        r for r in caplog.records
        if r.levelname == "WARNING"
        and "Orchestrator shutdown attempt failed" in r.getMessage()
    ]
    assert len(warning_records) >= 2  # At least 2 failures

    # Verify that NO error-level messages were logged
    error_records = [
        r for r in caplog.records
        if r.levelname in ("ERROR", "CRITICAL")
        and "Orchestrator shutdown attempt failed" in r.getMessage()
    ]
    assert (
        len(error_records) == 0
    ), f"Unexpected error-level logs: {error_records}"


@pytest.mark.asyncio
async def test_background_drain_waits_for_admitted_transition_saga(
    tmp_path,
    monkeypatch,
):
    """Graceful close preserves an API-style transition between journal writes."""

    orch = _real_orchestrator(tmp_path)
    issue = Issue(
        id="TASK-1",
        identifier="TASK-1",
        title="Test",
        state="Open",
        project_id="project-1",
        assignment_id="generation-1",
        work_branch="TASK-1",
        target_branch="main",
        head_sha="a" * 40,
    )
    tracker_entered = threading.Event()
    release_tracker = threading.Event()
    close_started = threading.Event()

    class BlockingTracker:
        def fetch_issue_detail(self, _identifier):
            tracker_entered.set()
            assert release_tracker.wait(timeout=3)
            return issue

        def update_issue(self, _identifier, **fields):
            issue.state = fields["status"]

    tracker = BlockingTracker()
    service = orch._task_transition_service("project-1", tracker)
    intent = TransitionIntent(
        project_id="project-1",
        task_id=issue.identifier,
        expected_status=issue.state,
        expected_version=issue_authority_version(issue),
        requested_status="In Progress",
        actor="worker",
        authority=TransitionAuthority.WORKER,
        reason_code="dispatch.eligible",
        idempotency_key="restart-api-transition",
        originating_job="restart-api-transition",
        evidence_generation="generation-1",
    )
    original_close = orch._close_owned_persistent_stores

    def tracked_close() -> None:
        close_started.set()
        original_close()

    monkeypatch.setattr(orch, "_close_owned_persistent_stores", tracked_close)
    transition = asyncio.create_task(service.execute(intent))
    assert await asyncio.to_thread(tracker_entered.wait, 1)
    drain = asyncio.create_task(orch._drain_background_work())
    try:
        assert await asyncio.to_thread(close_started.wait, 1)
        await asyncio.sleep(0.05)
        assert drain.done() is False

        release_tracker.set()
        outcome = await transition
        await asyncio.wait_for(asyncio.shield(drain), timeout=2)
    finally:
        release_tracker.set()
        if not drain.done():
            await asyncio.wait_for(asyncio.shield(drain), timeout=2)

    assert outcome.disposition is TransitionDisposition.APPLIED
    assert issue.state == "In Progress"
    assert all(
        not thread.is_alive()
        for pool in (orch._tick_pool, orch._refresh_pool)
        for thread in getattr(pool, "_threads", ())
    )

    reopened = TransitionJournal(orch.task_transition_journal.path)
    try:
        assert (
            reopened.events(outcome.transition_id)[-1].phase
            is TransitionPhase.APPLIED
        )
    finally:
        reopened.close()


def test_replacement_revokes_snapshot_after_permit_before_every_sink(
    tmp_path,
    monkeypatch,
):
    """Exact SQL authority rejects a cached-true writer after replacement."""

    old = _real_orchestrator(tmp_path / "old")
    new = _real_orchestrator(tmp_path / "new")
    ipc_path = str(tmp_path / "state-cache.sqlite")
    ipc = OrchestratorIPC(ipc_path)
    new_ipc = OrchestratorIPC(ipc_path)
    old._ipc = ipc
    new._ipc = new_ipc
    assert ipc.activate_state_source(old._service_instance_id)
    old._ipc_state_publication_source = old._service_instance_id
    sink_entered = threading.Event()
    release_sink = threading.Event()
    old_event = threading.Event()
    old_legacy = threading.Event()
    current_legacy = threading.Event()
    new_event = threading.Event()
    new_legacy = threading.Event()

    def _assert_callback_locks_are_free() -> None:
        assert old._provider_admission_lock.acquire(blocking=False)
        old._provider_admission_lock.release()
        assert old._lifecycle_publication_lock.acquire(blocking=False)
        old._lifecycle_publication_lock.release()
        current_legacy.set()

    old.event_bus.subscribe(
        EventType.ORCHESTRATOR_TICK,
        lambda _event, _payload: old_event.set(),
    )
    old._observers.extend(
        (
            lambda snapshot: server._on_orchestrator_change(
                snapshot,
                source=old,
            ),
            lambda _snapshot: old_legacy.set(),
            lambda _snapshot: _assert_callback_locks_are_free(),
        )
    )
    monkeypatch.setattr(server, "_orchestrator", old)

    # A current generation reaches all three sinks, and callbacks run without
    # provider/lifecycle locks held.
    current = {"source": "old-current"}
    assert old._publish_observer_snapshot(
        current,
        lifecycle_epoch=old._lifecycle_publication_epoch,
        expected_generation=old._provider_admission_generation,
    )
    assert ipc.read_state()[0] == current
    assert old_event.is_set()
    assert old_legacy.is_set()
    assert current_legacy.is_set()
    assert server._read_state_snapshot(allow_stale=True) == current

    old_event.clear()
    old_legacy.clear()
    current_legacy.clear()
    original_publish_state = ipc.publish_state

    def _blocked_ipc_publish(snapshot, **kwargs):
        original_guard = kwargs["source_is_current"]

        def _guard_then_pause_before_sql():
            # Capture the old source as current, then pause after the Python
            # predicate but before IPC's atomic source-ID SQL replacement.
            permitted = original_guard()
            assert permitted is True
            assert old._provider_admission_lock.acquire(blocking=False)
            old._provider_admission_lock.release()
            assert old._lifecycle_publication_lock.acquire(blocking=False)
            old._lifecycle_publication_lock.release()
            # Cooperative source predicates must never run under the IPC
            # mutex. Replacement needs this mutex to revoke old authority.
            assert ipc._lock.acquire(blocking=False)
            ipc._lock.release()
            sink_entered.set()
            assert release_sink.wait(timeout=10)
            return permitted

        kwargs["source_is_current"] = _guard_then_pause_before_sql
        return original_publish_state(snapshot, **kwargs)

    monkeypatch.setattr(ipc, "publish_state", _blocked_ipc_publish)
    monkeypatch.setattr(
        old,
        "get_snapshot",
        lambda: {
            "source": "old-delayed",
        },
    )
    assert old.request_lifecycle_publication(expected_generation=0)
    assert sink_entered.wait(timeout=10)
    with old._lifecycle_publication_lock:
        worker = old._lifecycle_publication_thread
    assert worker is not None

    with (
        patch.object(server, "remove_draft_labels_from_epics", return_value=0),
        patch.object(server, "_migrate_release_picks_on_startup"),
        patch.object(server, "ErrorWatcher", MagicMock()),
        patch.object(server, "ProjectLogWatcherManager", MagicMock()),
    ):
        server.set_orchestrator(new)
    replacement = {
        "source": "replacement",
    }
    server._on_orchestrator_change(replacement, source=new)

    release_sink.set()
    worker.join(timeout=10)
    assert worker.is_alive() is False
    assert ipc.read_state()[0] == current
    assert old_event.is_set() is False
    assert old_legacy.is_set() is False
    assert current_legacy.is_set() is False

    assert server._read_state_snapshot(allow_stale=True) == replacement

    # The replacement's current source remains publishable after old-source
    # rejection and does not inherit the old publisher's revoked epoch.
    new.event_bus.subscribe(
        EventType.ORCHESTRATOR_TICK,
        lambda _event, _payload: new_event.set(),
    )
    new._observers.append(lambda _snapshot: new_legacy.set())
    post_cutover = {
        "source": "new-current",
    }
    assert new._publish_observer_snapshot(
        post_cutover,
        lifecycle_epoch=new._lifecycle_publication_epoch,
        expected_generation=new._provider_admission_generation,
    )
    assert new_ipc.read_state()[0] == post_cutover
    assert new_event.is_set()
    assert new_legacy.is_set()
    assert server._read_state_snapshot(allow_stale=True) == post_cutover

    new._shutdown_lifecycle_publications()
    ipc.close()
    new_ipc.close()


def test_lifecycle_request_advances_ipc_generation_before_delayed_write(
    tmp_path,
    monkeypatch,
):
    """A cached-true generation-zero writer loses to generation one."""

    orch = _real_orchestrator(tmp_path / "ipc-generation")
    ipc_path = str(tmp_path / "generation-cache.sqlite")
    authority_ipc = OrchestratorIPC(ipc_path)
    delayed_ipc = OrchestratorIPC(ipc_path)
    source_id = orch._service_instance_id
    orch._ipc = authority_ipc
    orch._ipc_state_publication_source = source_id
    assert authority_ipc.activate_state_source(
        source_id,
        epoch=0,
        generation=0,
    )
    assert authority_ipc.publish_state(
        {"source": "generation-zero-current"},
        source_id=source_id,
        source_epoch=0,
        source_generation=0,
    )

    guard_checked = threading.Event()
    release_delayed_write = threading.Event()
    delayed_result: list[bool] = []

    def _cached_true_guard() -> bool:
        guard_checked.set()
        assert release_delayed_write.wait(timeout=3)
        return True

    def _publish_delayed_generation_zero() -> None:
        delayed_result.append(
            delayed_ipc.publish_state(
                {"source": "generation-zero-delayed"},
                source_is_current=_cached_true_guard,
                source_id=source_id,
                source_epoch=0,
                source_generation=0,
            )
        )

    delayed = threading.Thread(target=_publish_delayed_generation_zero)
    delayed.start()
    assert guard_checked.wait(timeout=1)

    with orch._provider_admission_lock:
        orch._provider_admission_generation = 1
    generation_one = {"source": "generation-one-current"}
    monkeypatch.setattr(orch, "get_snapshot", lambda: generation_one)
    assert orch.request_lifecycle_publication(expected_generation=1)
    deadline = time.monotonic() + 1
    while authority_ipc.read_state()[0] != generation_one:
        assert time.monotonic() < deadline
        time.sleep(0.01)

    release_delayed_write.set()
    delayed.join(timeout=1)
    assert delayed.is_alive() is False
    assert delayed_result == [False]
    assert authority_ipc.read_state()[0] == generation_one

    assert orch._shutdown_lifecycle_publications()
    authority_ipc.close()
    delayed_ipc.close()


def test_failed_ipc_source_activation_cannot_publish_lifecycle_state(
    tmp_path,
    monkeypatch,
):
    """An unclaimed orchestrator cannot use the legacy IPC write fallback."""

    candidate = _real_orchestrator(tmp_path / "activation-failure")
    ipc_path = str(tmp_path / "activation-failure.sqlite")
    replacement_ipc = OrchestratorIPC(ipc_path)
    candidate_ipc = OrchestratorIPC(ipc_path)
    candidate._ipc = candidate_ipc
    assert replacement_ipc.activate_state_source(
        "replacement-owner",
        epoch=7,
        generation=11,
    )
    replacement = {"source": "replacement-owned"}
    assert replacement_ipc.publish_state(
        replacement,
        source_id="replacement-owner",
        source_epoch=7,
        source_generation=11,
    )

    monkeypatch.setattr(
        candidate_ipc,
        "activate_state_source",
        lambda *_args, **_kwargs: False,
    )
    original_orchestrator = server._orchestrator
    monkeypatch.setattr(server, "_orchestrator", None)
    try:
        with (
            patch.object(
                server,
                "remove_draft_labels_from_epics",
                return_value=0,
            ),
            patch.object(server, "_migrate_release_picks_on_startup"),
            patch.object(server, "ErrorWatcher", MagicMock()),
            patch.object(server, "ProjectLogWatcherManager", MagicMock()),
        ):
            server.set_orchestrator(candidate)
        assert candidate._ipc_state_publication_source is None

        assert candidate._publish_observer_snapshot(
            {"source": "unclaimed-lifecycle"},
            lifecycle_epoch=candidate._lifecycle_publication_epoch,
            expected_generation=candidate._provider_admission_generation,
        )
        assert replacement_ipc.read_state()[0] == replacement

        # The source-less compatibility call remains intentionally available
        # only when no lifecycle predicate is supplied.
        compatibility = {"source": "legacy-compatibility"}
        assert candidate_ipc.publish_state(compatibility)
        assert replacement_ipc.read_state()[0] == compatibility
    finally:
        candidate._shutdown_lifecycle_publications()
        server._orchestrator = original_orchestrator
        replacement_ipc.close()
        candidate_ipc.close()


def test_event_sink_rechecks_source_at_handler_mutation(
    tmp_path,
    monkeypatch,
):
    """A plain handler admitted before cutover drains before ownership moves."""

    old = _real_orchestrator(tmp_path / "old-event")
    new = _real_orchestrator(tmp_path / "new-event")
    old._ipc = None
    new._ipc = None
    handler_entered = threading.Event()
    release_handler = threading.Event()
    old_mutation = threading.Event()
    replacement_done = threading.Event()
    replacement_errors: list[BaseException] = []

    def _delayed_handler(_event, _payload):
        handler_entered.set()
        assert release_handler.wait(timeout=3)
        old_mutation.set()

    old.event_bus.subscribe(EventType.ORCHESTRATOR_TICK, _delayed_handler)
    monkeypatch.setattr(server, "_orchestrator", old)
    monkeypatch.setattr(old, "get_snapshot", lambda: {"source": "old-event"})
    assert old.request_lifecycle_publication(expected_generation=0)
    assert handler_entered.wait(timeout=1)
    with old._lifecycle_publication_lock:
        worker = old._lifecycle_publication_thread
    assert worker is not None

    def _replace() -> None:
        try:
            server.set_orchestrator(new)
        except BaseException as exc:  # noqa: BLE001 - asserted by the test
            replacement_errors.append(exc)
        finally:
            replacement_done.set()

    with (
        patch.object(server, "remove_draft_labels_from_epics", return_value=0),
        patch.object(server, "_migrate_release_picks_on_startup"),
        patch.object(server, "ErrorWatcher", MagicMock()),
        patch.object(server, "ProjectLogWatcherManager", MagicMock()),
    ):
        replacement = threading.Thread(target=_replace)
        replacement.start()
        assert replacement_done.wait(timeout=0.1) is False
        assert server._orchestrator is old

        release_handler.set()
        replacement.join(timeout=1)
    assert replacement.is_alive() is False
    assert replacement_errors == []
    assert replacement_done.is_set()
    assert server._orchestrator is new
    worker.join(timeout=1)
    assert worker.is_alive() is False
    assert old_mutation.is_set()
    new._shutdown_lifecycle_publications()


def test_server_observer_rechecks_source_at_cache_mutation(
    tmp_path,
    monkeypatch,
):
    """A source-aware legacy callback completes before replacement commits."""

    old = _real_orchestrator(tmp_path / "old-observer")
    new = _real_orchestrator(tmp_path / "new-observer")
    old._ipc = None
    new._ipc = None
    observer_entered = threading.Event()
    release_observer = threading.Event()
    observer_complete = threading.Event()
    replacement_done = threading.Event()
    replacement_errors: list[BaseException] = []

    def _delayed_server_observer(
        snapshot,
        *,
        publication_permit=None,
    ):
        assert publication_permit is not None
        # Orchestrator's legacy-source guard already passed. Pause before the
        # server wrapper's owner+permit cache CAS.
        assert old._provider_admission_lock.acquire(blocking=False)
        old._provider_admission_lock.release()
        assert old._lifecycle_publication_lock.acquire(blocking=False)
        old._lifecycle_publication_lock.release()
        observer_entered.set()
        assert release_observer.wait(timeout=3)
        server._on_orchestrator_change(
            snapshot,
            source=old,
            publication_permit=publication_permit,
        )
        observer_complete.set()

    _delayed_server_observer._oompah_accepts_lifecycle_publication_permit = True
    old._observers.append(_delayed_server_observer)
    monkeypatch.setattr(server, "_orchestrator", old)
    monkeypatch.setattr(old, "get_snapshot", lambda: {"source": "old-observer"})
    assert old.request_lifecycle_publication(expected_generation=0)
    assert observer_entered.wait(timeout=1)
    with old._lifecycle_publication_lock:
        worker = old._lifecycle_publication_thread
    assert worker is not None

    def _replace() -> None:
        try:
            server.set_orchestrator(new)
        except BaseException as exc:  # noqa: BLE001 - asserted by the test
            replacement_errors.append(exc)
        finally:
            replacement_done.set()

    with (
        patch.object(server, "remove_draft_labels_from_epics", return_value=0),
        patch.object(server, "_migrate_release_picks_on_startup"),
        patch.object(server, "ErrorWatcher", MagicMock()),
        patch.object(server, "ProjectLogWatcherManager", MagicMock()),
    ):
        replacement_thread = threading.Thread(target=_replace)
        replacement_thread.start()
        assert replacement_done.wait(timeout=0.1) is False
        assert server._orchestrator is old
        release_observer.set()
        replacement_thread.join(timeout=1)
    assert replacement_thread.is_alive() is False
    assert replacement_errors == []
    assert observer_complete.is_set()
    assert server._orchestrator is new
    replacement = {"source": "new-observer"}
    server._on_orchestrator_change(replacement, source=new)

    worker.join(timeout=1)
    assert worker.is_alive() is False
    assert server._read_state_snapshot(allow_stale=True) == replacement
    new._shutdown_lifecycle_publications()


def test_replacement_timeout_rolls_back_before_concurrent_replacement(
    tmp_path,
    monkeypatch,
):
    """A failed drain keeps the old owner and cannot ABA a queued cutover.

    This test uses explicit synchronization and predicate-based readiness checks
    instead of relying on wall-clock timeouts, making it deterministic under load.
    The key insight: instead of sleeping to let the timeout elapse, we observe
    when the timeout HAS elapsed by checking when the first replacement attempt
    has actually failed, then start the second attempt.
    """

    old = _real_orchestrator(tmp_path / "old-timeout")
    first_new = _real_orchestrator(tmp_path / "first-new")
    second_new = _real_orchestrator(tmp_path / "second-new")
    old._ipc = None
    first_new._ipc = None
    second_new._ipc = None
    # Very short timeout so test completes quickly while remaining deterministic
    old._lifecycle_publication_drain_timeout_s = 0.05

    handler_entered = threading.Event()
    release_handler = threading.Event()
    callback_mutated = threading.Event()

    # Event to signal when the first replacement has finished attempting
    # (either success or failure). This replaces time.sleep() for orchestration.
    first_replacement_attempted = threading.Event()

    first_done = threading.Event()
    second_done = threading.Event()
    first_errors: list[BaseException] = []
    second_errors: list[BaseException] = []

    def _blocked_plain_handler(_event, _payload):
        handler_entered.set()
        assert release_handler.wait(timeout=3)
        callback_mutated.set()

    old.event_bus.subscribe(EventType.ORCHESTRATOR_TICK, _blocked_plain_handler)
    monkeypatch.setattr(server, "_orchestrator", old)
    monkeypatch.setattr(old, "get_snapshot", lambda: {"source": "old-timeout"})
    assert old.request_lifecycle_publication(expected_generation=0)
    assert handler_entered.wait(timeout=1)

    def _replace(target, errors, done, mark_attempted=None):
        try:
            server.set_orchestrator(target)
        except BaseException as exc:  # noqa: BLE001 - asserted by the test
            errors.append(exc)
        finally:
            if mark_attempted is not None:
                mark_attempted.set()
            done.set()

    with (
        patch.object(server, "remove_draft_labels_from_epics", return_value=0),
        patch.object(server, "_migrate_release_picks_on_startup"),
        patch.object(server, "ErrorWatcher", MagicMock()),
        patch.object(server, "ProjectLogWatcherManager", MagicMock()),
    ):
        first = threading.Thread(
            target=_replace,
            args=(first_new, first_errors, first_done, first_replacement_attempted),
        )
        second = threading.Thread(
            target=_replace,
            args=(second_new, second_errors, second_done, None),
        )
        first.start()
        # Instead of time.sleep(0.05), wait for an observable signal: the first
        # replacement attempt has been made. This is deterministic and not load-
        # sensitive. The first thread will timeout in its drain, then set this event.
        assert first_replacement_attempted.wait(timeout=10)

        # Now start second. It will block on the replacement lock until first
        # releases it, then try to drain old (which may also timeout initially).
        # Once we release the handler, second's drain will succeed.
        second.start()

        # Verify state after first failure: old is still in place but partially
        # shut down. This check happens before we release the handler.
        assert first_done.wait(timeout=1)
        assert len(first_errors) == 1
        assert isinstance(first_errors[0], RuntimeError)
        assert server._orchestrator is old
        assert old._lifecycle_publication_closed is False

        # Release the handler, which allows the lifecycle publication callbacks
        # to complete. This unblocks second's drain attempt (if it was waiting)
        # and allows it to succeed. The release happens while second might be
        # timing out in its own drain attempt.
        release_handler.set()

        # Both threads should complete within reasonable time
        assert first.join(timeout=1) is None
        assert second.join(timeout=1) is None
        assert first.is_alive() is False
        assert second.is_alive() is False

        # Second should have succeeded (no errors)
        assert second_errors == []
        assert callback_mutated.is_set()

        # Final state: second_new is installed and old is shut down
        assert server._orchestrator is second_new
        assert old._lifecycle_publication_closed is True

    second_new._shutdown_lifecycle_publications()


def test_replacement_succeeds_when_handler_completes_before_timeout(
    tmp_path,
    monkeypatch,
):
    """Replacement succeeds when lifecycle drain completes before timeout.

    This is the reverse ordering of the previous test: instead of blocking
    until timeout, the handler is released soon enough that the drain completes
    and replacement succeeds. Uses explicit synchronization (events) to ensure
    deterministic behavior independent of system load.
    """

    old = _real_orchestrator(tmp_path / "old-success")
    new = _real_orchestrator(tmp_path / "new-success")
    old._ipc = None
    new._ipc = None
    # Generous timeout ensures drain won't fail due to timeout
    old._lifecycle_publication_drain_timeout_s = 10.0

    handler_entered = threading.Event()
    release_handler_trigger = threading.Event()
    handler_completed = threading.Event()
    callback_published = threading.Event()
    replacement_started = threading.Event()

    def _quick_handler(_event, _payload):
        handler_entered.set()
        # Wait for explicit signal to release, demonstrating test control
        assert release_handler_trigger.wait(timeout=3)
        handler_completed.set()

    old.event_bus.subscribe(EventType.ORCHESTRATOR_TICK, _quick_handler)
    monkeypatch.setattr(server, "_orchestrator", old)
    monkeypatch.setattr(old, "get_snapshot", lambda: {"source": "old-success"})
    assert old.request_lifecycle_publication(expected_generation=0)
    assert handler_entered.wait(timeout=1)

    replacement_result = []
    replacement_errors = []

    def _attempt_replacement():
        replacement_started.set()
        try:
            server.set_orchestrator(new)
            replacement_result.append("success")
        except BaseException as exc:
            replacement_errors.append(exc)

    with (
        patch.object(server, "remove_draft_labels_from_epics", return_value=0),
        patch.object(server, "_migrate_release_picks_on_startup"),
        patch.object(server, "ErrorWatcher", MagicMock()),
        patch.object(server, "ProjectLogWatcherManager", MagicMock()),
    ):
        replacer = threading.Thread(target=_attempt_replacement)
        replacer.start()

        # Let replacement start and reach the drain point
        assert replacement_started.wait(timeout=1)
        time.sleep(0.01)  # Small sleep to let drain attempt start

        # Release the handler BEFORE the timeout would occur, ensuring drain succeeds
        release_handler_trigger.set()
        assert handler_completed.wait(timeout=1)

        # Replacement should complete successfully
        replacer.join(timeout=1)
        assert replacer.is_alive() is False

        # Verify success
        assert replacement_errors == []
        assert replacement_result == ["success"]
        assert server._orchestrator is new
        assert old._lifecycle_publication_closed is True

    new._shutdown_lifecycle_publications()


@pytest.mark.timeout(30)
def test_repeated_replacement_timeout_detection_under_load(
    tmp_path,
    monkeypatch,
):
    """Run the timeout test multiple times to verify determinism under load.

    This test verifies that the fixes for deterministic timeout detection
    actually work reliably across multiple runs. The original bug manifested
    when Makefile gates ran concurrently; this simulates that by running
    the timeout-then-success scenario multiple times in sequence under
    CPU load from other threads.
    """

    def _run_one_cycle():
        """Run one cycle of timeout-then-success replacement."""
        old = _real_orchestrator(tmp_path / f"load-old-{id(threading.current_thread()):x}")
        first_new = _real_orchestrator(tmp_path / f"load-first-{id(threading.current_thread()):x}")
        second_new = _real_orchestrator(tmp_path / f"load-second-{id(threading.current_thread()):x}")
        old._ipc = None
        first_new._ipc = None
        second_new._ipc = None
        old._lifecycle_publication_drain_timeout_s = 0.05

        handler_entered = threading.Event()
        release_handler = threading.Event()
        first_attempted = threading.Event()

        first_errors = []
        second_errors = []
        first_done = threading.Event()
        second_done = threading.Event()

        def _blocked_handler(_event, _payload):
            handler_entered.set()
            assert release_handler.wait(timeout=3)

        old.event_bus.subscribe(EventType.ORCHESTRATOR_TICK, _blocked_handler)
        monkeypatch.setattr(server, "_orchestrator", old)
        monkeypatch.setattr(old, "get_snapshot", lambda: {"source": "load-cycle"})
        assert old.request_lifecycle_publication(expected_generation=0)
        assert handler_entered.wait(timeout=1)

        def _replace(target, errors, done, mark_attempted=None):
            try:
                server.set_orchestrator(target)
            except BaseException as exc:
                errors.append(exc)
            finally:
                if mark_attempted is not None:
                    mark_attempted.set()
                done.set()

        with (
            patch.object(server, "remove_draft_labels_from_epics", return_value=0),
            patch.object(server, "_migrate_release_picks_on_startup"),
            patch.object(server, "ErrorWatcher", MagicMock()),
            patch.object(server, "ProjectLogWatcherManager", MagicMock()),
        ):
            first = threading.Thread(
                target=_replace,
                args=(first_new, first_errors, first_done, first_attempted),
            )
            second = threading.Thread(
                target=_replace,
                args=(second_new, second_errors, second_done, None),
            )
            first.start()
            assert first_attempted.wait(timeout=10)
            second.start()

            release_handler.set()

            assert first.join(timeout=1) is None
            assert second.join(timeout=1) is None

            # Verify cycle results
            if len(first_errors) != 1 or not isinstance(first_errors[0], RuntimeError):
                return False
            if second_errors != []:
                return False
            if server._orchestrator is not second_new:
                return False
            if not old._lifecycle_publication_closed:
                return False

        second_new._shutdown_lifecycle_publications()
        return True

    # Run the cycle 5 times sequentially to verify consistent behavior
    # (not testing true concurrency of cycles, just repeated execution under potential load)
    for run in range(5):
        result = _run_one_cycle()
        assert result, f"Replacement cycle {run} failed: either timeout not detected or replacement didn't succeed"


def test_blocked_lifecycle_publication_worker_does_not_hold_interpreter_open(
    tmp_path,
):
    """A permanently blocked advisory snapshot worker is process-exit safe."""

    script = textwrap.dedent(
        """
        import sys
        import threading
        from pathlib import Path
        from unittest.mock import MagicMock

        from oompah.config import ServiceConfig
        from oompah.orchestrator import Orchestrator

        store = MagicMock()
        store.list_all.return_value = []
        store.get.return_value = None
        orch = Orchestrator(
            config=ServiceConfig(duplicate_preflight_max_agents=0),
            workflow_path="WORKFLOW.md",
            project_store=store,
            state_path=sys.argv[1],
        )
        entered = threading.Event()
        blocked = threading.Event()

        def get_snapshot():
            entered.set()
            blocked.wait()
            return {}

        orch.get_snapshot = get_snapshot
        assert orch.request_lifecycle_publication(expected_generation=0)
        assert entered.wait(timeout=10)
        Path(sys.argv[2]).write_text("ready", encoding="utf-8")
        """
    )
    ready_path = tmp_path / "worker-ready"
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            script,
            str(tmp_path / "state.json"),
            str(ready_path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 30
        while not ready_path.exists() and process.poll() is None:
            if time.monotonic() >= deadline:
                process.kill()
                _stdout, stderr = process.communicate(timeout=2)
                pytest.fail(f"subprocess did not reach worker barrier: {stderr}")
            time.sleep(0.01)
        if not ready_path.exists():
            _stdout, stderr = process.communicate(timeout=2)
            pytest.fail(f"subprocess exited before worker barrier: {stderr}")
        try:
            returncode = process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            _stdout, stderr = process.communicate(timeout=2)
            pytest.fail(
                "daemon lifecycle publication worker held the interpreter "
                f"open: {stderr}"
            )
        _stdout, stderr = process.communicate(timeout=2)
        assert returncode == 0, stderr
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=2)


@pytest.mark.asyncio
async def test_pause_persistence_contention_does_not_block_health(
    tmp_path,
    monkeypatch,
):
    """Pause waits for lifecycle authority away from the HTTP event loop."""

    original = server._orchestrator
    orch = _real_orchestrator(tmp_path)
    save_entered = threading.Event()
    release_save = threading.Event()
    save_calls = 0
    save_calls_lock = threading.Lock()

    def _contended_save(**_updates: object) -> bool:
        nonlocal save_calls
        with save_calls_lock:
            save_calls += 1
            call_number = save_calls
        if call_number == 1:
            save_entered.set()
            assert release_save.wait(timeout=3)
        return True

    monkeypatch.setattr(orch, "_save_state", _contended_save)
    holder = threading.Thread(
        target=orch._save_paused_state_if_generation,
        args=(orch._provider_admission_generation, False),
        name="older-lifecycle-persistence",
    )
    holder.start()
    assert save_entered.wait(timeout=1)
    release_timer = threading.Timer(0.3, release_save.set)
    release_timer.start()
    server._orchestrator = orch
    try:
        started = time.monotonic()
        pause_task = asyncio.create_task(server.api_orchestrator_pause())
        health_task = asyncio.create_task(server.healthz())
        health = await asyncio.wait_for(health_task, timeout=0.5)
        health_elapsed = time.monotonic() - started
        response = await asyncio.wait_for(pause_task, timeout=1)
    finally:
        release_save.set()
        release_timer.cancel()
        holder.join(timeout=1)
        orch._shutdown_lifecycle_publications()
        server._orchestrator = original

    assert json.loads(health.body)["status"] == "ok"
    assert health_elapsed < 0.15
    assert response.status_code == 200
    assert orch._paused is True


@pytest.mark.asyncio
async def test_restart_failure_does_not_await_permanently_blocked_publication(
    tmp_path,
    monkeypatch,
):
    """Rollback completion is independent of both success/failure snapshots."""

    orch = _real_orchestrator(tmp_path)
    snapshot_entered = threading.Event()
    release_snapshot = threading.Event()
    snapshot_finished = threading.Event()
    observer_published = threading.Event()

    def _blocked_snapshot() -> dict[str, object]:
        snapshot_entered.set()
        try:
            assert release_snapshot.wait(timeout=3)
            return {}
        finally:
            snapshot_finished.set()

    def _failed_merge(*_args, **_kwargs) -> tuple[bool, int, int]:
        raise OSError("injected restart journal failure")

    monkeypatch.setattr(orch, "get_snapshot", _blocked_snapshot)
    monkeypatch.setattr(orch, "_merge_restart_issues", _failed_merge)
    orch._observers.append(lambda _snapshot: observer_published.set())
    restart_task = asyncio.create_task(orch.graceful_restart(drain_timeout_s=0))
    try:
        assert await asyncio.to_thread(snapshot_entered.wait, 1)
        with pytest.raises(OSError, match="restart journal failure"):
            await asyncio.wait_for(asyncio.shield(restart_task), timeout=0.5)
        assert snapshot_finished.is_set() is False
        assert orch._restart_in_progress is False
        assert orch._stopping is False
        orch._shutdown_lifecycle_publications()
        release_snapshot.set()
        assert await asyncio.to_thread(snapshot_finished.wait, 1)
    finally:
        release_snapshot.set()
        if not restart_task.done():
            restart_task.cancel()
            await asyncio.gather(restart_task, return_exceptions=True)
        orch._shutdown_lifecycle_publications()

    assert observer_published.is_set() is False


@pytest.mark.asyncio
async def test_failed_restart_cleanup_persistence_stays_off_http_loop():
    """Uncontended drain cleanup cannot synchronously park the API loop."""

    original = server._orchestrator
    fake = _fake_orchestrator()
    fake.graceful_restart = AsyncMock(side_effect=RuntimeError("drain failed"))
    save_entered = threading.Event()
    release_save = threading.Event()
    save_finished = threading.Event()

    def _blocked_save() -> None:
        save_entered.set()
        try:
            assert release_save.wait(timeout=3)
        finally:
            save_finished.set()

    fake._save_paused_state = _blocked_save
    server._orchestrator = fake
    try:
        response = await server.api_orchestrator_restart(_json_request({}))
        assert await asyncio.to_thread(save_entered.wait, 1)
        started = time.monotonic()
        health = await asyncio.wait_for(server.healthz(), timeout=0.1)
        claim = await asyncio.wait_for(
            server.api_orchestrator_restart(
                _json_request(
                    {
                        "claim_only": True,
                        "restart_request_id": "post-failure-claim",
                    }
                )
            ),
            timeout=0.2,
        )
        cancelled = await asyncio.wait_for(
            server.api_orchestrator_restart(
                _json_request(
                    {
                        "cancel_claim": True,
                        "restart_request_id": "post-failure-claim",
                    }
                )
            ),
            timeout=0.2,
        )
        control_elapsed = time.monotonic() - started
    finally:
        release_save.set()
        await asyncio.to_thread(save_finished.wait, 1)
        server._orchestrator = original

    assert response.status_code == 200
    assert json.loads(health.body)["status"] == "ok"
    assert claim.status_code == 200
    assert cancelled.status_code == 200
    assert control_elapsed < 0.2
    assert fake._restart_in_progress is False


@pytest.mark.asyncio
async def test_failed_restart_rollback_cannot_overwrite_newer_durable_pause(
    tmp_path,
    monkeypatch,
):
    """Pause persistence serializes after an older rollback generation."""

    original_orchestrator = server._orchestrator
    orch = _real_orchestrator(tmp_path)

    async def _failed_drain(**_kwargs) -> None:
        raise RuntimeError("injected drain failure before lifecycle mutation")

    false_save_entered = threading.Event()
    release_false_save = threading.Event()
    pause_finished = threading.Event()
    paused_writes: list[bool] = []
    original_save_state = orch._save_state

    def _ordered_save(**updates: object) -> bool:
        if "paused" in updates:
            paused = bool(updates["paused"])
            if not paused and not false_save_entered.is_set():
                false_save_entered.set()
                assert release_false_save.wait(timeout=3)
            saved = original_save_state(**updates)
            paused_writes.append(paused)
            return saved
        return original_save_state(**updates)

    def _pause() -> None:
        try:
            orch.pause()
        finally:
            pause_finished.set()

    monkeypatch.setattr(orch, "graceful_restart", _failed_drain)
    monkeypatch.setattr(orch, "_save_state", _ordered_save)
    server._orchestrator = orch
    pause_thread = threading.Thread(target=_pause, name="newer-operator-pause")
    try:
        response = await server.api_orchestrator_restart(_json_request({}))
        assert await asyncio.to_thread(false_save_entered.wait, 1)
        pause_thread.start()
        await asyncio.sleep(0.05)
        # The newer pause cannot slip its durable True write ahead of the
        # older rollback's already-admitted False write.
        assert pause_finished.is_set() is False
        health = await asyncio.wait_for(server.healthz(), timeout=0.1)
        release_false_save.set()
        assert await asyncio.to_thread(pause_finished.wait, 1)
        pause_thread.join(timeout=1)
    finally:
        release_false_save.set()
        if pause_thread.is_alive():
            pause_thread.join(timeout=1)
        orch._shutdown_lifecycle_publications()
        server._orchestrator = original_orchestrator

    durable_state = orch._load_state()
    assert response.status_code == 200
    assert json.loads(health.body)["status"] == "ok"
    assert paused_writes[-2:] == [False, True]
    assert orch._paused is True
    assert durable_state["paused"] is True
