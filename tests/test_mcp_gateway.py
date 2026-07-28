"""Integration coverage for the embedded streamable-HTTP MCP gateway."""

from __future__ import annotations

import asyncio
import base64
import contextlib
from collections.abc import Generator

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from oompah.mcp_gateway import _dispatch_api_call, mcp_transport_security_settings
from oompah.mcp_exposure_policy import MCP_DISCOVERY_PATH, MCP_ENDPOINT_PATH
from oompah.http_auth import HtpasswdCredentials, VerificationError
import oompah.server as server_module
from oompah.server import app


def _asgi_mcp_client(
    headers: dict[str, str] | None = None,
    timeout: httpx.Timeout | None = None,
    auth: httpx.Auth | None = None,
) -> httpx.AsyncClient:
    """Return an MCP client that exercises the mounted gateway in-process."""
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://127.0.0.1",
        headers=headers,
        timeout=timeout,
        auth=auth,
    )


def _basic(username: str, password: str) -> str:
    """Return an HTTP Basic header value for MCP transport tests."""
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {token}"


@contextlib.contextmanager
def _mcp_basic_auth_enabled() -> Generator[None, None, None]:
    """Enable an in-memory htpasswd verifier for one MCP test."""
    credentials = HtpasswdCredentials(enabled=True)

    def verifier(username: str, password: str) -> None:
        if username == "admin" and password == "secret":
            return
        raise VerificationError("Invalid credentials")

    credentials.verifier = verifier
    original = server_module._http_credentials
    server_module._http_credentials = credentials
    try:
        yield
    finally:
        server_module._http_credentials = original


@contextlib.contextmanager
def _mcp_basic_auth_disabled() -> Generator[None, None, None]:
    """Disable server authentication for backward-compatibility coverage."""
    original = server_module._http_credentials
    server_module._http_credentials = None
    try:
        yield
    finally:
        server_module._http_credentials = original


def test_mcp_discovery_advertises_the_mounted_streamable_http_endpoint():
    with _mcp_basic_auth_disabled(), TestClient(app) as client:
        response = client.get(MCP_DISCOVERY_PATH)

    assert response.status_code == 200
    assert response.json() == {
        "name": "oompah",
        "version": "v1",
        "transport": "streamable-http",
        "mcp_endpoint": MCP_ENDPOINT_PATH,
        "discovery_path": MCP_DISCOVERY_PATH,
        "authentication": "none; local service access only",
    }


def test_mcp_discovery_requires_basic_auth_and_reports_it_when_enabled():
    with _mcp_basic_auth_enabled(), TestClient(app) as client:
        missing = client.get(MCP_DISCOVERY_PATH)
        invalid = client.get(
            MCP_DISCOVERY_PATH,
            headers={"Authorization": _basic("admin", "wrong")},
        )
        response = client.get(
            MCP_DISCOVERY_PATH,
            headers={"Authorization": _basic("admin", "secret")},
        )

    for denied in (missing, invalid):
        assert denied.status_code == 401
        assert denied.headers["www-authenticate"] == (
            'Basic realm="oompah", charset="UTF-8"'
        )
    assert response.status_code == 200
    assert response.json()["authentication"] == "http-basic"


def test_mcp_defaults_to_loopback_host_protection(monkeypatch):
    monkeypatch.delenv("OOMPAH_MCP_ALLOW_NETWORK", raising=False)

    settings = mcp_transport_security_settings()

    assert settings.enable_dns_rebinding_protection is True
    assert "127.0.0.1:*" in settings.allowed_hosts


def test_mcp_can_be_explicitly_enabled_for_network_hosts(monkeypatch):
    monkeypatch.setenv("OOMPAH_MCP_ALLOW_NETWORK", "true")

    settings = mcp_transport_security_settings()

    assert settings.enable_dns_rebinding_protection is False


def test_network_enabled_mcp_transport_still_challenges_missing_basic_auth(monkeypatch):
    monkeypatch.setenv("OOMPAH_MCP_ALLOW_NETWORK", "true")

    with _mcp_basic_auth_enabled(), TestClient(
        app, base_url="http://mcp.example"
    ) as client:
        response = client.post(f"{MCP_ENDPOINT_PATH}/", json={})

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == (
        'Basic realm="oompah", charset="UTF-8"'
    )


def test_mcp_client_can_initialize_list_allowed_tools_and_call_state():
    async def exercise_gateway() -> tuple[set[str], int]:
        async with streamablehttp_client(
            f"http://127.0.0.1{MCP_ENDPOINT_PATH}/",
            httpx_client_factory=_asgi_mcp_client,
        ) as streams:
            async with ClientSession(*streams[:2]) as session:
                initialized = await session.initialize()
                tools = await session.list_tools()
                result = await session.call_tool("api_state_api_v1_state_get", {})

        assert initialized.serverInfo.name == "oompah"
        assert result.isError is False
        assert result.structuredContent["status_code"] == 200
        return {tool.name for tool in tools.tools}, result.structuredContent["status_code"]

    with TestClient(app):
        tool_names, status_code = asyncio.run(exercise_gateway())

    assert status_code == 200
    assert "api_state_api_v1_state_get" in tool_names
    assert "api_orchestrator_restart_api_v1_orchestrator_restart_post" not in tool_names
    assert "api_webhook_github_api_v1_webhooks_github_post" not in tool_names


def test_authenticated_mcp_client_can_initialize_list_and_call_protected_api():
    def authenticated_client(
        headers: dict[str, str] | None = None,
        timeout: httpx.Timeout | None = None,
        auth: httpx.Auth | None = None,
    ) -> httpx.AsyncClient:
        return _asgi_mcp_client(
            headers=headers,
            timeout=timeout,
            auth=auth or httpx.BasicAuth("admin", "secret"),
        )

    async def exercise_gateway() -> tuple[set[str], int, str, str]:
        async with streamablehttp_client(
            f"http://127.0.0.1{MCP_ENDPOINT_PATH}/",
            httpx_client_factory=authenticated_client,
        ) as streams:
            async with ClientSession(*streams[:2]) as session:
                initialized = await session.initialize()
                tools = await session.list_tools()
                result = await session.call_tool("api_state_api_v1_state_get", {})

        assert initialized.serverInfo.name == "oompah"
        assert result.isError is False
        assert result.structuredContent["status_code"] == 200
        return (
            {tool.name for tool in tools.tools},
            result.structuredContent["status_code"],
            str(result),
            str([tool.inputSchema for tool in tools.tools]),
        )

    with _mcp_basic_auth_enabled(), TestClient(app):
        tool_names, status_code, result_text, tool_schemas = asyncio.run(
            exercise_gateway()
        )

    assert status_code == 200
    assert "api_state_api_v1_state_get" in tool_names
    assert "api_orchestrator_restart_api_v1_orchestrator_restart_post" not in tool_names
    assert "api_webhook_github_api_v1_webhooks_github_post" not in tool_names
    assert "authorization" not in result_text.lower()
    assert "secret" not in result_text
    assert "authorization" not in tool_schemas.lower()
    assert "secret" not in tool_schemas


def test_mcp_transport_rejects_missing_or_invalid_credentials_before_dispatch():
    with _mcp_basic_auth_enabled(), TestClient(app) as client:
        missing = client.post(f"{MCP_ENDPOINT_PATH}/", json={})
        invalid = client.post(
            f"{MCP_ENDPOINT_PATH}/",
            json={},
            headers={"Authorization": _basic("admin", "wrong")},
        )
        # Streamable HTTP's session cleanup is also a protected request.
        cleanup = client.delete(
            f"{MCP_ENDPOINT_PATH}/",
            headers={"Authorization": _basic("admin", "secret")},
        )

    for denied in (missing, invalid):
        assert denied.status_code == 401
        assert denied.headers["www-authenticate"] == (
            'Basic realm="oompah", charset="UTF-8"'
        )
    assert cleanup.status_code != 401


def test_external_internal_marker_headers_cannot_bypass_rest_authentication():
    """Only an in-memory identity from an MCP tool can bypass the inner check."""
    spoofed_headers = {
        "Host": "oompah.local",
        "X-Oompah-Mcp-Authenticated": "true",
        "X-Oompah-Internal-Dispatch": "true",
    }

    with _mcp_basic_auth_enabled(), TestClient(app) as client:
        response = client.get("/api/v1/state", headers=spoofed_headers)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == (
        'Basic realm="oompah", charset="UTF-8"'
    )


# ---------------------------------------------------------------------------
# Unit tests for _dispatch_api_call
# ---------------------------------------------------------------------------


def _minimal_echo_app() -> FastAPI:
    """Return a tiny FastAPI application for dispatch tests.

    Routes:
        GET /echo  → 200 {"method": "GET", "params": ...}
        POST /echo → 201 {"method": "POST", "body": ...}
    """
    mini = FastAPI()

    @mini.get("/echo")
    async def echo_get(q: str | None = None):
        return {"method": "GET", "q": q}

    @mini.post("/echo", status_code=201)
    async def echo_post(payload: dict | None = None):
        return {"method": "POST", "payload": payload}

    return mini


@pytest.mark.asyncio
async def test_dispatch_api_call_get_returns_response():
    """_dispatch_api_call forwards GET requests and returns the raw response."""
    mini = _minimal_echo_app()

    response = await _dispatch_api_call(mini, "GET", "/echo")

    assert response.status_code == 200
    assert response.json() == {"method": "GET", "q": None}


@pytest.mark.asyncio
async def test_dispatch_api_call_get_with_query_params():
    """_dispatch_api_call propagates query-string parameters."""
    mini = _minimal_echo_app()

    response = await _dispatch_api_call(mini, "GET", "/echo", params={"q": "hello"})

    assert response.status_code == 200
    assert response.json()["q"] == "hello"


@pytest.mark.asyncio
async def test_dispatch_api_call_post_with_body():
    """_dispatch_api_call serialises a JSON body for POST requests."""
    mini = _minimal_echo_app()

    response = await _dispatch_api_call(mini, "POST", "/echo", body={"key": "value"})

    assert response.status_code == 201
    assert response.json()["method"] == "POST"


@pytest.mark.asyncio
async def test_dispatch_api_call_method_is_case_insensitive():
    """_dispatch_api_call accepts lower- or mixed-case HTTP methods."""
    mini = _minimal_echo_app()

    response = await _dispatch_api_call(mini, "get", "/echo")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_dispatch_api_call_unknown_path_returns_404():
    """_dispatch_api_call propagates 404 for routes not in *api_app*."""
    mini = _minimal_echo_app()

    response = await _dispatch_api_call(mini, "GET", "/does-not-exist")

    assert response.status_code == 404
