"""API contracts for coalesced, configurable graceful restarts (OOMPAH-507)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from oompah import server
from oompah.server import app


def _fake_orchestrator(timeout: int = 3600):
    return SimpleNamespace(
        config=SimpleNamespace(restart_drain_timeout_seconds=timeout),
        state=SimpleNamespace(running={}),
        _restart_in_progress=False,
        _restart_request_id=None,
        _restart_requested_at=None,
        _restart_initial_running=0,
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
