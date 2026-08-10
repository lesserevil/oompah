"""Tests for OOMPAH-674: WebSocket bootstrap includes authenticated state.

Verifies that the WebSocket endpoint sends HTTP auth, build, and metrics metadata
in the initial state snapshot, consistent with the REST /api/v1/state endpoint.

Tests cover:
- WebSocket initial state includes http_auth.enabled field
- WebSocket refresh state includes http_auth.enabled field
- Authenticated WebSocket bootstrap has http_auth.enabled = True
- Unauthenticated deployments preserve backward compatibility
- REST and WebSocket expose consistent http_auth metadata
- No credentials or secret material enters the payload
"""

from __future__ import annotations

import base64
import contextlib
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.http_auth import HtpasswdCredentials, VerificationError
from oompah.server import app


_SERVER_STATE_CACHE_FIELDS = (
    "_state_snapshot",
    "_state_snapshot_at",
    "_state_snapshot_epoch",
    "_state_snapshot_authority",
    "_state_snapshot_signature",
    "_protocol_epoch",
    "_state_revision",
    "_issue_revision",
)


def _swap_server_state_cache(values: tuple[object, ...]) -> tuple[object, ...]:
    """Atomically replace and return the complete state-cache protocol tuple."""
    with server_module._state_snapshot_lock, server_module._ws_protocol_lock:
        original = tuple(
            getattr(server_module, field) for field in _SERVER_STATE_CACHE_FIELDS
        )
        for field, value in zip(_SERVER_STATE_CACHE_FIELDS, values, strict=True):
            setattr(server_module, field, value)
        return original


def _unavailable_server_state_cache() -> tuple[object, ...]:
    """Return a coherent cache tuple representing no published state yet."""
    return (
        None,
        0.0,
        server_module._INSTANCE_ID,
        None,
        None,
        server_module._INSTANCE_ID,
        0,
        0,
    )


# ---------------------------------------------------------------------------
# Helpers (reused from test_server_auth.py)
# ---------------------------------------------------------------------------

def _make_creds(username: str = "admin", password: str = "secret") -> HtpasswdCredentials:
    """Return an enabled HtpasswdCredentials with a single user."""
    creds = HtpasswdCredentials(enabled=True)

    def verifier(u: str, p: str) -> None:
        if u == username and p == password:
            return
        raise VerificationError("Invalid credentials")

    creds.verifier = verifier
    creds.htpasswd_path = "/test/.htpasswd"
    return creds


def _basic(username: str, password: str) -> str:
    """Return an Authorization: Basic header value."""
    encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {encoded}"


def _mock_orchestrator() -> MagicMock:
    """Return a minimal mock orchestrator sufficient for most routes."""
    orch = MagicMock()
    orch.project_store.list_all.return_value = []
    orch.event_bus = MagicMock()
    orch.event_bus.subscribe = MagicMock()
    return orch


@contextlib.contextmanager
def _auth_enabled(
    username: str = "admin",
    password: str = "secret",
) -> Generator[HtpasswdCredentials, None, None]:
    """Context manager: enable auth with a single test user, restore on exit."""
    creds = _make_creds(username, password)
    orig = server_module._http_credentials
    server_module._http_credentials = creds
    try:
        yield creds
    finally:
        server_module._http_credentials = orig


@contextlib.contextmanager
def _auth_disabled() -> Generator[None, None, None]:
    """Context manager: ensure auth is disabled (credentials=None)."""
    orig = server_module._http_credentials
    server_module._http_credentials = None
    try:
        yield
    finally:
        server_module._http_credentials = orig


@contextlib.contextmanager
def _patch_orchestrator(orch=None):
    """Context manager: temporarily replace _orchestrator."""
    if orch is None:
        orch = _mock_orchestrator()
    orig = server_module._orchestrator
    server_module._orchestrator = orch
    try:
        yield orch
    finally:
        server_module._orchestrator = orig


@contextlib.contextmanager
def _ws_isolation(orch=None):
    """Set up isolated WebSocket clients and an unavailable state cache."""
    if orch is None:
        orch = _mock_orchestrator()
    orig_ws = server_module._ws_clients
    orig_orch = server_module._orchestrator
    orig_state_cache = _swap_server_state_cache(_unavailable_server_state_cache())
    server_module._ws_clients = set()
    server_module._orchestrator = orch
    try:
        yield orch
    finally:
        server_module._ws_clients = orig_ws
        server_module._orchestrator = orig_orch
        _swap_server_state_cache(orig_state_cache)


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# WebSocket Initial State Bootstrap
# ---------------------------------------------------------------------------

class TestWebSocketBootstrapIncludesAuth:
    """WebSocket initial state includes HTTP auth metadata."""

    def test_ws_bootstrap_includes_http_auth_when_auth_enabled(self):
        """WebSocket bootstrap state includes http_auth.enabled when auth is enabled."""
        client = TestClient(app, raise_server_exceptions=False)
        with _auth_enabled(), _ws_isolation():
            auth = _basic("admin", "secret")
            with client.websocket_connect("/ws", headers={"Authorization": auth}) as ws:
                msg = ws.receive_json()
                assert msg.get("type") == "state", f"Expected 'state' message, got: {msg}"
                data = msg.get("data", {})
                assert "http_auth" in data, "state.data must include http_auth"
                assert data["http_auth"].get("enabled") is True, \
                    f"http_auth.enabled should be True when auth is enabled, got: {data['http_auth']}"

    def test_ws_bootstrap_http_auth_has_reload_status(self):
        """WebSocket bootstrap http_auth includes reload status."""
        client = TestClient(app, raise_server_exceptions=False)
        with _auth_enabled(), _ws_isolation():
            auth = _basic("admin", "secret")
            with client.websocket_connect("/ws", headers={"Authorization": auth}) as ws:
                msg = ws.receive_json()
                data = msg.get("data", {})
                http_auth = data.get("http_auth", {})
                assert "reload" in http_auth, "http_auth must include reload status"
                reload = http_auth["reload"]
                assert "state" in reload
                assert "generation" in reload
                assert "retaining_last_known_good" in reload

    def test_ws_bootstrap_includes_build_id(self):
        """WebSocket bootstrap state includes build_id."""
        client = TestClient(app, raise_server_exceptions=False)
        with _auth_disabled(), _ws_isolation():
            with client.websocket_connect("/ws") as ws:
                msg = ws.receive_json()
                data = msg.get("data", {})
                assert "build_id" in data, "state.data must include build_id"
                assert isinstance(data["build_id"], dict), "build_id must be a dict"

    def test_ws_bootstrap_includes_service_instance_id(self):
        """WebSocket bootstrap state includes service_instance_id."""
        client = TestClient(app, raise_server_exceptions=False)
        with _auth_disabled(), _ws_isolation():
            with client.websocket_connect("/ws") as ws:
                msg = ws.receive_json()
                data = msg.get("data", {})
                assert "service_instance_id" in data, "state.data must include service_instance_id"
                assert isinstance(data["service_instance_id"], str), "service_instance_id must be a string"

    def test_ws_bootstrap_includes_api_metrics(self):
        """WebSocket bootstrap state includes api_metrics."""
        client = TestClient(app, raise_server_exceptions=False)
        with _auth_disabled(), _ws_isolation():
            with client.websocket_connect("/ws") as ws:
                msg = ws.receive_json()
                data = msg.get("data", {})
                assert "api_metrics" in data, "state.data must include api_metrics"
                assert isinstance(data["api_metrics"], dict), "api_metrics must be a dict"

    def test_ws_bootstrap_auth_disabled_shows_false(self):
        """WebSocket bootstrap shows http_auth.enabled = False when auth is disabled."""
        client = TestClient(app, raise_server_exceptions=False)
        with _auth_disabled(), _ws_isolation():
            with client.websocket_connect("/ws") as ws:
                msg = ws.receive_json()
                data = msg.get("data", {})
                assert "http_auth" in data
                assert data["http_auth"].get("enabled") is False, \
                    "http_auth.enabled should be False when auth is disabled"


# ---------------------------------------------------------------------------
# WebSocket Refresh State
# ---------------------------------------------------------------------------

class TestWebSocketRefreshIncludesAuth:
    """WebSocket refresh state includes HTTP auth metadata."""

    def test_ws_refresh_includes_http_auth(self):
        """WebSocket refresh response includes http_auth."""
        client = TestClient(app, raise_server_exceptions=False)
        with _auth_enabled(), _ws_isolation():
            auth = _basic("admin", "secret")
            with client.websocket_connect("/ws", headers={"Authorization": auth}) as ws:
                # Receive initial state
                ws.receive_json()
                # Receive issues
                ws.receive_json()
                # Send refresh request
                ws.send_json({"action": "refresh"})
                # Receive refreshed state and issues (order may vary)
                msg1 = ws.receive_json()
                msg2 = ws.receive_json()

                # Find the state message
                state_msg = None
                for msg in [msg1, msg2]:
                    if msg.get("type") == "state":
                        state_msg = msg
                        break

                assert state_msg is not None, f"Expected at least one 'state' message in {[msg1, msg2]}"
                data = state_msg.get("data", {})
                assert "http_auth" in data, "refreshed state must include http_auth"
                assert data["http_auth"].get("enabled") is True


# ---------------------------------------------------------------------------
# Consistency Between REST and WebSocket
# ---------------------------------------------------------------------------

class TestRESTWebSocketConsistency:
    """REST and WebSocket endpoints expose consistent metadata."""

    def test_rest_and_ws_both_include_http_auth_when_enabled(self):
        """Both REST and WebSocket include http_auth when auth is enabled."""
        client = TestClient(app, raise_server_exceptions=False)
        with _auth_enabled(), _ws_isolation():
            auth_header = {"Authorization": _basic("admin", "secret")}

            # Get REST state
            rest_resp = client.get("/api/v1/state", headers=auth_header)
            assert rest_resp.status_code == 200
            rest_data = rest_resp.json()
            rest_http_auth = rest_data.get("http_auth")

            # Get WebSocket state
            auth = _basic("admin", "secret")
            with client.websocket_connect("/ws", headers={"Authorization": auth}) as ws:
                ws_msg = ws.receive_json()
                ws_data = ws_msg.get("data", {})
                ws_http_auth = ws_data.get("http_auth")

            # Both should have http_auth
            assert rest_http_auth is not None, "REST must include http_auth"
            assert ws_http_auth is not None, "WebSocket must include http_auth"

            # Both should have enabled = True
            assert rest_http_auth.get("enabled") is True
            assert ws_http_auth.get("enabled") is True

    def test_rest_and_ws_both_include_build_id(self):
        """Both REST and WebSocket include build_id."""
        client = TestClient(app, raise_server_exceptions=False)
        with _auth_disabled(), _ws_isolation():
            # Get REST state
            rest_resp = client.get("/api/v1/state")
            assert rest_resp.status_code == 200
            rest_data = rest_resp.json()
            rest_build_id = rest_data.get("build_id")

            # Get WebSocket state
            with client.websocket_connect("/ws") as ws:
                ws_msg = ws.receive_json()
                ws_data = ws_msg.get("data", {})
                ws_build_id = ws_data.get("build_id")

            # Both should have build_id
            assert rest_build_id is not None
            assert ws_build_id is not None
            # build_id should be a dict in both
            assert isinstance(rest_build_id, dict)
            assert isinstance(ws_build_id, dict)

    def test_rest_and_ws_both_include_service_instance_id(self):
        """Both REST and WebSocket include service_instance_id."""
        client = TestClient(app, raise_server_exceptions=False)
        with _auth_disabled(), _ws_isolation():
            # Get REST state
            rest_resp = client.get("/api/v1/state")
            rest_data = rest_resp.json()
            rest_instance_id = rest_data.get("service_instance_id")

            # Get WebSocket state
            with client.websocket_connect("/ws") as ws:
                ws_msg = ws.receive_json()
                ws_data = ws_msg.get("data", {})
                ws_instance_id = ws_data.get("service_instance_id")

            # Both should have service_instance_id
            assert rest_instance_id is not None
            assert ws_instance_id is not None
            # service_instance_id should be a string in both
            assert isinstance(rest_instance_id, str)
            assert isinstance(ws_instance_id, str)
            # Should be the same (same instance)
            assert rest_instance_id == ws_instance_id


# ---------------------------------------------------------------------------
# Security: No Credentials in Payload
# ---------------------------------------------------------------------------

class TestWebSocketCredentialsRedaction:
    """WebSocket payloads never contain credentials or secret material."""

    def test_ws_bootstrap_does_not_leak_credentials(self):
        """WebSocket bootstrap must not contain passwords or htpasswd paths."""
        client = TestClient(app, raise_server_exceptions=False)
        with _auth_enabled("testuser", "testsecret"), _ws_isolation():
            auth = _basic("testuser", "testsecret")
            with client.websocket_connect("/ws", headers={"Authorization": auth}) as ws:
                msg = ws.receive_json()
                import json
                payload_str = json.dumps(msg)

                # Must not leak any credential material
                assert "testsecret" not in payload_str, "Password must not appear in payload"
                assert "testuser" not in payload_str, "Username must not appear in payload"
                assert ".htpasswd" not in payload_str, "htpasswd path must not appear in payload"
                assert "htpasswd_path" not in payload_str

    def test_ws_refresh_does_not_leak_credentials(self):
        """WebSocket refresh response must not contain credentials."""
        client = TestClient(app, raise_server_exceptions=False)
        username = "credential-user-8f3a"
        password = "credential-password-91bd"
        with _auth_enabled(username, password), _ws_isolation():
            # OOMPAH-873 deliberately declines to emit an unavailable/stale
            # issue bootstrap.  Seed the authoritative empty generation this
            # security test expects rather than depending on global snapshot
            # state left by another test.
            with patch.object(
                server_module,
                "_issues_snapshot_payload_with_revision",
                return_value=(server_module._empty_issue_board(), 1),
            ):
                auth = _basic(username, password)
                with client.websocket_connect("/ws", headers={"Authorization": auth}) as ws:
                    ws.receive_json()  # initial state
                    ws.receive_json()  # issues
                    ws.send_json({"action": "refresh"})
                    msg = ws.receive_json()

                import json
                payload_str = json.dumps(msg)
                assert password not in payload_str
                assert username not in payload_str
                assert ".htpasswd" not in payload_str


# ---------------------------------------------------------------------------
# Backward Compatibility: Unauthenticated Deployments
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:
    """Unauthenticated deployments preserve existing behavior."""

    def test_ws_works_without_auth_when_disabled(self):
        """WebSocket connects without credentials when auth is disabled."""
        client = TestClient(app, raise_server_exceptions=False)
        with _auth_disabled(), _ws_isolation():
            with client.websocket_connect("/ws") as ws:
                msg = ws.receive_json()
                assert msg.get("type") == "state"
                data = msg.get("data", {})
                # Must have http_auth even when auth is disabled
                assert "http_auth" in data
                # Must show enabled = False
                assert data["http_auth"].get("enabled") is False

    def test_ws_bootstrap_structure_preserved(self):
        """WebSocket bootstrap message structure is preserved."""
        client = TestClient(app, raise_server_exceptions=False)
        with _auth_disabled(), _ws_isolation():
            with client.websocket_connect("/ws") as ws:
                msg = ws.receive_json()
                # Must have "type" and "data" fields
                assert "type" in msg
                assert "data" in msg
                # Type should be "state"
                assert msg["type"] == "state"
                # Data should be a dict
                assert isinstance(msg["data"], dict)
                # Original fields should still be present
                data = msg["data"]
                # These are from _cached_state_snapshot_or_unavailable
                assert any(key in data for key in ["paused", "running", "retrying", "counts"]), \
                    "Original snapshot fields must be preserved"

    def test_ws_isolation_rejects_poisoned_partial_cache(self):
        """A prior test's partial snapshot cannot replace bootstrap defaults."""
        poisoned = (
            {"source": "prior-test"},
            123.5,
            server_module._INSTANCE_ID,
            "poison-authority",
            "poison-signature",
            server_module._INSTANCE_ID,
            37,
            41,
        )
        original = _swap_server_state_cache(poisoned)
        client = TestClient(app, raise_server_exceptions=False)
        try:
            with _auth_disabled(), _ws_isolation():
                with client.websocket_connect("/ws") as ws:
                    data = ws.receive_json()["data"]
                    assert data["state_snapshot_unavailable"] is True
                    assert data["counts"] == {"running": 0, "retrying": 0}
                    assert data["running"] == []
                    assert data["retrying"] == []
        finally:
            _swap_server_state_cache(original)

    def test_ws_isolation_restores_exact_state_cache_tuple(self):
        """WebSocket isolation restores every cache and protocol sentinel."""
        sentinel_snapshot = {"source": "sentinel"}
        sentinel = (
            sentinel_snapshot,
            987.25,
            "sentinel-state-epoch",
            "sentinel-authority",
            "sentinel-signature",
            "sentinel-protocol-epoch",
            73,
            79,
        )
        original = _swap_server_state_cache(sentinel)
        try:
            with _ws_isolation():
                current = _swap_server_state_cache(
                    _unavailable_server_state_cache()
                )
                assert current == _unavailable_server_state_cache()
            restored = _swap_server_state_cache(sentinel)
            assert restored == sentinel
            assert restored[0] is sentinel_snapshot
        finally:
            _swap_server_state_cache(original)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
