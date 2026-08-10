"""API contracts for coalesced, configurable graceful restarts (OOMPAH-507)."""

import asyncio
import json
import threading
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from oompah import server
from oompah.server import app


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
    fake.quiesce.assert_called_once_with()


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
