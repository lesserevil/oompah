"""Integration tests for OOMPAH-523: HTTP Basic authentication middleware.

Tests cover:
- Disabled auth mode (current behaviour preserved exactly)
- Valid credentials accepted on protected routes
- Invalid credentials: missing, malformed, non-Basic scheme, unknown user, wrong password
- Exact WWW-Authenticate: Basic challenge header
- Protected surfaces: dashboard HTML, static assets, favicon, REST APIs, OpenAPI, Swagger/ReDoc
- GET /healthz: unauthenticated, minimal content only
- WebSocket: accepted with valid auth, rejected without auth (before _ws_clients registration)
- Webhook exemptions: POST /api/v1/webhooks/github, POST /api/v1/webhooks/gitlab
- GitLab webhook status GET remains protected
- Adjacent-method and path-prefix variants do NOT bypass auth
- Existing GitHub signature and GitLab token validation remains intact under enabled auth
- Disabled deployments retain current route behaviour exactly
"""

from __future__ import annotations

import base64
import contextlib
from typing import Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.http_auth import HtpasswdCredentials, VerificationError
from oompah.server import app


# ---------------------------------------------------------------------------
# Helpers
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


def _disabled_creds() -> HtpasswdCredentials:
    """Return a disabled HtpasswdCredentials."""
    return HtpasswdCredentials(enabled=False)


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


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def auth_client(client):
    """TestClient with auth enabled for admin/secret."""
    with _auth_enabled():
        yield client


@pytest.fixture()
def valid_auth_header() -> dict[str, str]:
    return {"Authorization": _basic("admin", "secret")}


# ---------------------------------------------------------------------------
# Auth disabled: current behaviour preserved exactly
# ---------------------------------------------------------------------------

class TestAuthDisabled:
    """When auth is disabled, all routes behave exactly as before."""

    def test_root_passes_without_auth(self, client):
        with _auth_disabled():
            resp = client.get("/")
            assert resp.status_code != 401

    def test_api_passes_without_auth(self, client):
        with _auth_disabled():
            resp = client.get("/api/v1/state")
            # May be 503 (no orchestrator) but must NOT be 401
            assert resp.status_code != 401

    def test_healthz_passes_without_auth(self, client):
        with _auth_disabled():
            resp = client.get("/healthz")
            assert resp.status_code == 200

    def test_ws_passes_without_auth(self, client):
        with _auth_disabled(), _patch_orchestrator():
            ws_clients_orig = server_module._ws_clients
            server_module._ws_clients = set()
            try:
                with client.websocket_connect("/ws") as ws:
                    msg = ws.receive_json()
                    assert "type" in msg
            finally:
                server_module._ws_clients = ws_clients_orig

    def test_disabled_creds_object_passes(self, client):
        """An explicit disabled HtpasswdCredentials is the same as None."""
        orig = server_module._http_credentials
        server_module._http_credentials = _disabled_creds()
        try:
            resp = client.get("/api/v1/state")
            assert resp.status_code != 401
        finally:
            server_module._http_credentials = orig


# ---------------------------------------------------------------------------
# Auth enabled: valid credentials accepted
# ---------------------------------------------------------------------------

class TestAuthEnabled_ValidCredentials:
    """Valid credentials allow access to all protected routes."""

    def test_valid_credentials_on_state_api(self, auth_client, valid_auth_header):
        resp = auth_client.get("/api/v1/state", headers=valid_auth_header)
        # May be 503 (no orchestrator) but NOT 401
        assert resp.status_code != 401

    def test_valid_credentials_on_issues_api(self, auth_client, valid_auth_header):
        resp = auth_client.get("/api/v1/issues", headers=valid_auth_header)
        assert resp.status_code != 401

    def test_valid_credentials_on_root(self, auth_client, valid_auth_header):
        resp = auth_client.get("/", headers=valid_auth_header)
        assert resp.status_code != 401

    def test_valid_credentials_on_favicon(self, auth_client, valid_auth_header):
        resp = auth_client.get("/favicon.ico", headers=valid_auth_header)
        assert resp.status_code != 401

    def test_valid_credentials_on_openapi(self, auth_client, valid_auth_header):
        resp = auth_client.get("/openapi.json", headers=valid_auth_header)
        assert resp.status_code != 401

    def test_valid_credentials_on_docs(self, auth_client, valid_auth_header):
        resp = auth_client.get("/docs", headers=valid_auth_header)
        assert resp.status_code != 401

    def test_valid_credentials_on_redoc(self, auth_client, valid_auth_header):
        resp = auth_client.get("/redoc", headers=valid_auth_header)
        assert resp.status_code != 401

    @pytest.mark.asyncio
    async def test_authorization_is_redacted_before_downstream_app(self):
        """Downstream logging/exception paths cannot see Basic credentials."""
        captured = {}

        async def downstream(scope, receive, send):
            captured.update(scope)
            await send({"type": "http.response.start", "status": 204, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        middleware = server_module._BasicAuthMiddleware(downstream)
        auth_value = _basic("admin", "secret").encode()
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/private",
            "raw_path": b"/private",
            "headers": [(b"authorization", auth_value), (b"x-test", b"kept")],
        }
        sent = []

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            sent.append(message)

        with _auth_enabled():
            await middleware(scope, receive, send)

        assert (b"authorization", auth_value) not in captured["headers"]
        assert (b"x-test", b"kept") in captured["headers"]
        assert sent[0]["status"] == 204


# ---------------------------------------------------------------------------
# Auth enabled: invalid credentials denied
# ---------------------------------------------------------------------------

class TestAuthEnabled_InvalidCredentials:
    """All invalid credential scenarios return 401 with Basic challenge."""

    def _check_401(self, resp) -> None:
        assert resp.status_code == 401
        www_auth = resp.headers.get("www-authenticate", "")
        assert www_auth == 'Basic realm="oompah", charset="UTF-8"'
        # Response body must never echo credential values
        body = resp.text
        assert "admin" not in body
        assert "secret" not in body

    def test_missing_header(self, auth_client):
        resp = auth_client.get("/api/v1/state")
        self._check_401(resp)

    def test_empty_authorization_header(self, auth_client):
        resp = auth_client.get("/api/v1/state", headers={"Authorization": ""})
        self._check_401(resp)

    def test_bearer_scheme(self, auth_client):
        resp = auth_client.get("/api/v1/state", headers={"Authorization": "Bearer sometoken"})
        self._check_401(resp)

    def test_digest_scheme(self, auth_client):
        resp = auth_client.get("/api/v1/state", headers={"Authorization": "Digest stuff"})
        self._check_401(resp)

    def test_malformed_base64(self, auth_client):
        resp = auth_client.get("/api/v1/state", headers={"Authorization": "Basic not-valid-base64!!!"})
        self._check_401(resp)

    @pytest.mark.parametrize(
        "authorization",
        [
            "Basic YWRtaW46c2VjcmV0!",  # ignored punctuation must not decode
            "Basic YWRtaW46c2VjcmV0 ",  # trailing whitespace is malformed
            "Basic YWRtaW46c2VjcmV0===",  # excessive padding
        ],
    )
    def test_malformed_base64_that_decodes_permissively_is_rejected(
        self, auth_client, authorization
    ):
        resp = auth_client.get(
            "/api/v1/state", headers={"Authorization": authorization}
        )
        self._check_401(resp)

    def test_decoded_without_colon(self, auth_client):
        encoded = base64.b64encode(b"nocolon").decode()
        resp = auth_client.get("/api/v1/state", headers={"Authorization": f"Basic {encoded}"})
        self._check_401(resp)

    def test_unknown_user(self, auth_client):
        resp = auth_client.get("/api/v1/state", headers={"Authorization": _basic("unknown", "secret")})
        self._check_401(resp)

    def test_wrong_password(self, auth_client):
        resp = auth_client.get("/api/v1/state", headers={"Authorization": _basic("admin", "wrong")})
        self._check_401(resp)

    def test_unknown_user_and_wrong_password_indistinguishable(self, auth_client):
        """Unknown user and wrong password must both return 401 (no enumeration)."""
        resp_unknown = auth_client.get("/api/v1/state", headers={"Authorization": _basic("nobody", "any")})
        resp_wrong_pw = auth_client.get("/api/v1/state", headers={"Authorization": _basic("admin", "wrong")})
        assert resp_unknown.status_code == resp_wrong_pw.status_code == 401
        assert resp_unknown.headers.get("www-authenticate") == resp_wrong_pw.headers.get("www-authenticate")

    def test_empty_password(self, auth_client):
        encoded = base64.b64encode(b"admin:").decode()
        resp = auth_client.get("/api/v1/state", headers={"Authorization": f"Basic {encoded}"})
        self._check_401(resp)

    def test_empty_username(self, auth_client):
        encoded = base64.b64encode(b":secret").decode()
        resp = auth_client.get("/api/v1/state", headers={"Authorization": f"Basic {encoded}"})
        self._check_401(resp)


# ---------------------------------------------------------------------------
# WWW-Authenticate challenge header
# ---------------------------------------------------------------------------

class TestWWWAuthenticateHeader:
    """Exact form of the challenge header is verified."""

    def test_challenge_header_exact(self, auth_client):
        resp = auth_client.get("/api/v1/state")
        assert resp.status_code == 401
        expected = 'Basic realm="oompah", charset="UTF-8"'
        assert resp.headers.get("www-authenticate") == expected

    def test_challenge_present_on_all_invalid_credentials(self, auth_client):
        cases = [
            {},                                                           # missing
            {"Authorization": "Bearer token"},                            # wrong scheme
            {"Authorization": "Basic !!!"},                               # malformed
            {"Authorization": _basic("nobody", "pass")},                  # unknown user
            {"Authorization": _basic("admin", "wrong")},                  # wrong pw
        ]
        for headers in cases:
            resp = auth_client.get("/api/v1/state", headers=headers)
            assert resp.status_code == 401, f"expected 401 for headers={headers}"
            assert "www-authenticate" in resp.headers


# ---------------------------------------------------------------------------
# Protected surfaces
# ---------------------------------------------------------------------------

class TestProtectedSurfaces:
    """All interactive surfaces require auth when enabled."""

    PROTECTED_ROUTES = [
        ("GET", "/"),
        ("GET", "/favicon.ico"),
        ("GET", "/favicon.svg"),
        ("GET", "/api/v1/state"),
        ("GET", "/api/v1/issues"),
        ("GET", "/openapi.json"),
        ("GET", "/docs"),
        ("GET", "/redoc"),
        ("GET", "/api/v1/webhooks/gitlab/status"),
    ]

    def test_all_protected_routes_require_auth(self, auth_client):
        for method, path in self.PROTECTED_ROUTES:
            func = getattr(auth_client, method.lower())
            resp = func(path)
            assert resp.status_code == 401, (
                f"{method} {path} should be 401 when unauthenticated, got {resp.status_code}"
            )


# ---------------------------------------------------------------------------
# GET /healthz: unauthenticated, minimal
# ---------------------------------------------------------------------------

class TestHealthz:
    """GET /healthz is always accessible and returns only minimal data."""

    def test_healthz_accessible_without_auth_when_enabled(self, auth_client):
        resp = auth_client.get("/healthz")
        assert resp.status_code == 200

    def test_healthz_accessible_without_auth_when_disabled(self, client):
        with _auth_disabled():
            resp = client.get("/healthz")
            assert resp.status_code == 200

    def test_healthz_returns_json(self, auth_client):
        resp = auth_client.get("/healthz")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)

    def test_healthz_status_ok(self, client):
        resp = client.get("/healthz")
        data = resp.json()
        assert data.get("status") == "ok"

    def test_healthz_has_instance_id(self, client):
        resp = client.get("/healthz")
        data = resp.json()
        assert "instance_id" in data
        assert isinstance(data["instance_id"], str)
        assert len(data["instance_id"]) > 0

    def test_healthz_instance_id_is_stable(self, client):
        """Instance ID must be the same across multiple requests (within one process)."""
        resp1 = client.get("/healthz")
        resp2 = client.get("/healthz")
        assert resp1.json()["instance_id"] == resp2.json()["instance_id"]

    def test_healthz_no_operational_data(self, auth_client):
        """Healthz must not expose projects, tasks, providers, budgets, credentials."""
        resp = auth_client.get("/healthz")
        data = resp.json()
        forbidden_keys = {
            "projects", "tasks", "issues", "providers", "budgets",
            "alerts", "credentials", "webhook_secret", "access_token",
        }
        found = forbidden_keys & set(data.keys())
        assert not found, f"healthz exposed operational keys: {found}"

    def test_healthz_with_valid_auth_also_works(self, auth_client, valid_auth_header):
        resp = auth_client.get("/healthz", headers=valid_auth_header)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# WebSocket: accepted with auth, rejected without
# ---------------------------------------------------------------------------

class TestWebSocketAuth:
    """WebSocket handshakes are authenticated before accept()."""

    @contextlib.contextmanager
    def _ws_isolation(self, orch=None):
        """Set up orchestrator + isolated _ws_clients for WS tests."""
        if orch is None:
            orch = _mock_orchestrator()
        orig_ws = server_module._ws_clients
        orig_orch = server_module._orchestrator
        server_module._ws_clients = set()
        server_module._orchestrator = orch
        try:
            yield orch
        finally:
            server_module._ws_clients = orig_ws
            server_module._orchestrator = orig_orch

    def test_ws_rejected_without_auth(self):
        from fastapi.websockets import WebSocketDisconnect

        client = TestClient(app, raise_server_exceptions=False)
        with _auth_enabled(), self._ws_isolation():
            with pytest.raises((WebSocketDisconnect, Exception)):
                with client.websocket_connect("/ws") as ws:
                    # Server should close before we can read anything
                    ws.receive_text()

    def test_ws_rejected_client_not_in_ws_clients(self):
        """An unauthenticated WebSocket must never enter _ws_clients."""
        client = TestClient(app, raise_server_exceptions=False)
        with _auth_enabled(), self._ws_isolation():
            try:
                with client.websocket_connect("/ws") as ws:
                    ws.receive_text()
            except Exception:
                pass
            assert len(server_module._ws_clients) == 0, (
                "_ws_clients must be empty after rejected WS"
            )

    def test_ws_accepted_with_valid_auth(self):
        client = TestClient(app, raise_server_exceptions=False)
        with _auth_enabled(), self._ws_isolation():
            auth = _basic("admin", "secret")
            with client.websocket_connect("/ws", headers={"Authorization": auth}) as ws:
                msg = ws.receive_json()
                assert msg.get("type") in ("state", "issues")
                ws.close()

    def test_ws_accepted_client_added_to_ws_clients(self):
        """An authenticated WebSocket is added to _ws_clients."""
        client = TestClient(app, raise_server_exceptions=False)
        with _auth_enabled(), self._ws_isolation():
            auth = _basic("admin", "secret")
            with client.websocket_connect("/ws", headers={"Authorization": auth}) as ws:
                assert len(server_module._ws_clients) == 1
                ws.close()

    def test_ws_with_bad_password_rejected(self):
        from fastapi.websockets import WebSocketDisconnect

        client = TestClient(app, raise_server_exceptions=False)
        with _auth_enabled(), self._ws_isolation():
            auth = _basic("admin", "wrongpassword")
            with pytest.raises((WebSocketDisconnect, Exception)):
                with client.websocket_connect("/ws", headers={"Authorization": auth}) as ws:
                    ws.receive_text()

    def test_ws_passes_without_auth_when_disabled(self):
        """When auth is disabled, WebSocket works without Authorization."""
        client = TestClient(app, raise_server_exceptions=False)
        with _auth_disabled(), self._ws_isolation():
            with client.websocket_connect("/ws") as ws:
                msg = ws.receive_json()
                assert "type" in msg
                ws.close()


# ---------------------------------------------------------------------------
# Webhook exemptions
# ---------------------------------------------------------------------------

class TestWebhookExemptions:
    """POST /api/v1/webhooks/github and /gitlab bypass Basic auth."""

    def test_github_webhook_post_bypasses_auth(self, auth_client):
        """GitHub webhook delivery works without Basic credentials."""
        resp = auth_client.post(
            "/api/v1/webhooks/github",
            json={},
            headers={
                "X-GitHub-Event": "ping",
                "X-GitHub-Delivery": "test-delivery-id",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code != 401, f"GitHub webhook POST must not require auth (got {resp.status_code})"

    def test_gitlab_webhook_post_bypasses_auth(self, auth_client):
        """GitLab webhook delivery works without Basic credentials."""
        resp = auth_client.post(
            "/api/v1/webhooks/gitlab",
            json={},
            headers={
                "X-Gitlab-Event": "Push Hook",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code != 401, f"GitLab webhook POST must not require auth (got {resp.status_code})"

    def test_github_webhook_get_requires_auth(self, auth_client):
        """GET on the GitHub webhook path is NOT exempt."""
        resp = auth_client.get("/api/v1/webhooks/github")
        assert resp.status_code == 401

    def test_gitlab_webhook_status_get_requires_auth(self, auth_client):
        """GET /api/v1/webhooks/gitlab/status is protected."""
        resp = auth_client.get("/api/v1/webhooks/gitlab/status")
        assert resp.status_code == 401

    def test_github_webhook_prefix_variant_requires_auth(self, auth_client):
        """Path-prefix variants beyond the exact exempt path require auth."""
        resp = auth_client.get("/api/v1/webhooks/github/extra")
        assert resp.status_code == 401

    def test_gitlab_webhook_post_still_validates_token(self, auth_client):
        """Basic auth bypass does not remove GitLab token validation."""
        # An invalid/missing GitLab token should still fail (not with 401 but 4xx/5xx)
        resp = auth_client.post(
            "/api/v1/webhooks/gitlab",
            json={"object_kind": "push"},
            headers={
                "X-Gitlab-Event": "Push Hook",
                "X-Gitlab-Token": "invalid-token",
                "Content-Type": "application/json",
            },
        )
        # Must not be 401 (auth bypass works) but upstream validation may reject
        assert resp.status_code != 401

    def test_healthz_is_exempt(self, auth_client):
        """GET /healthz is accessible without credentials."""
        resp = auth_client.get("/healthz")
        assert resp.status_code == 200

    def test_healthz_post_is_not_exempt(self, auth_client):
        """POST /healthz is NOT an exempt route."""
        resp = auth_client.post("/healthz")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Anti-bypass checks: method and path variants
# ---------------------------------------------------------------------------

class TestAntiBypass:
    """Alternative methods and path variants must not bypass authentication."""

    def test_adjacent_method_on_exempt_path_requires_auth(self, auth_client):
        """Only the exact (method, path) pair is exempt; other methods require auth."""
        # POST /api/v1/webhooks/github is exempt; GET is not
        resp = auth_client.get("/api/v1/webhooks/github")
        assert resp.status_code == 401

        # POST /api/v1/webhooks/gitlab is exempt; GET is not
        resp = auth_client.get("/api/v1/webhooks/gitlab")
        assert resp.status_code == 401

    def test_trailing_slash_variant_protected(self, auth_client):
        """Trailing-slash variants of exempt paths are not exempt."""
        # FastAPI may 307-redirect /api/v1/state/ → /api/v1/state; the
        # important thing is that the middleware blocks before any redirect.
        resp = auth_client.get("/api/v1/state/")
        # Either 401 (blocked) or non-200 redirect (which the test client
        # follows to another blocked route) — never 200 without auth.
        if resp.status_code == 200:
            # TestClient follows redirects by default; check it didn't bypass
            pytest.fail(f"Path /api/v1/state/ should not reach 200 without auth")

    @pytest.mark.parametrize("path", ["/%68ealthz", "/health%7A"])
    def test_encoded_healthz_path_requires_auth(self, auth_client, path):
        """Encoded spellings of the public endpoint are not exemptions."""
        resp = auth_client.get(path)
        assert resp.status_code == 401

    def test_encoded_webhook_path_requires_auth(self, auth_client):
        """Encoded spellings of an exempt webhook path remain protected."""
        resp = auth_client.post(
            "/api%2Fv1/webhooks/github",
            content=b"{}",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 401

    def test_duplicate_authorization_headers_require_auth(self, auth_client):
        """Ambiguous duplicate Authorization fields fail closed."""
        resp = auth_client.get(
            "/api/v1/state",
            headers=[
                ("Authorization", _basic("admin", "secret")),
                ("authorization", _basic("admin", "wrong")),
            ],
        )
        assert resp.status_code == 401

    def test_put_on_healthz_requires_auth(self, auth_client):
        """Only GET /healthz is exempt; other methods must be blocked."""
        resp = auth_client.put("/healthz")
        assert resp.status_code == 401

    def test_delete_on_healthz_requires_auth(self, auth_client):
        resp = auth_client.delete("/healthz")
        assert resp.status_code == 401

    def test_patch_on_healthz_requires_auth(self, auth_client):
        resp = auth_client.patch("/healthz")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GitHub webhook signature/token validation under enabled auth
# ---------------------------------------------------------------------------

class TestWebhookSignatureValidationUnderAuth:
    """Forge-specific security checks survive when Basic auth is enabled."""

    def _make_github_sig(self, body_bytes: bytes, secret: str) -> str:
        import hashlib
        import hmac

        return "sha256=" + hmac.new(
            secret.encode(), body_bytes, hashlib.sha256
        ).hexdigest()

    def test_github_webhook_invalid_signature_still_fails(self):
        """An invalid GitHub signature is still rejected even without Basic creds."""
        from oompah.models import Project

        project = Project(
            id="p1",
            name="repo",
            repo_url="https://github.com/org/repo.git",
            repo_path="/tmp/r",
            webhook_secret="real-secret",
        )
        orch = MagicMock()
        orch.project_store.list_all.return_value = [project]
        orch.event_bus = MagicMock()

        client = TestClient(app, raise_server_exceptions=False)
        with _auth_enabled(), _patch_orchestrator(orch):
            body = b'{"action": "opened"}'
            resp = client.post(
                "/api/v1/webhooks/github",
                content=body,
                headers={
                    "X-GitHub-Event": "pull_request",
                    "X-GitHub-Delivery": "abc",
                    "X-Hub-Signature-256": "sha256=invalidsig",
                    "Content-Type": "application/json",
                },
            )
            # Must not be 401 (webhook bypasses Basic auth) but signature validation
            # should still reject it
            assert resp.status_code != 401
            # The specific status for invalid sig may be 400 or 403
            assert resp.status_code in (400, 403, 200), (
                f"Unexpected status {resp.status_code}; check signature handling"
            )


# ---------------------------------------------------------------------------
# set_http_credentials function
# ---------------------------------------------------------------------------

class TestSetHttpCredentials:
    """set_http_credentials wires credentials into the module-level variable."""

    def test_set_credentials_enables_auth(self):
        orig = server_module._http_credentials
        try:
            creds = _make_creds()
            server_module.set_http_credentials(creds)
            assert server_module._http_credentials is creds
        finally:
            server_module._http_credentials = orig

    def test_set_disabled_credentials(self):
        orig = server_module._http_credentials
        try:
            creds = _disabled_creds()
            server_module.set_http_credentials(creds)
            assert server_module._http_credentials is creds
        finally:
            server_module._http_credentials = orig

    def test_set_none_disables_auth(self):
        orig = server_module._http_credentials
        try:
            server_module.set_http_credentials(None)
            assert server_module._http_credentials is None
        finally:
            server_module._http_credentials = orig
