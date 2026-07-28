"""Integration coverage for the embedded streamable-HTTP MCP gateway."""

from __future__ import annotations

import asyncio

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from oompah.mcp_gateway import _dispatch_api_call, mcp_transport_security_settings
from oompah.mcp_exposure_policy import MCP_DISCOVERY_PATH, MCP_ENDPOINT_PATH
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


def test_mcp_discovery_advertises_the_mounted_streamable_http_endpoint():
    client = TestClient(app)
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


def test_mcp_defaults_to_loopback_host_protection(monkeypatch):
    monkeypatch.delenv("OOMPAH_MCP_ALLOW_NETWORK", raising=False)

    settings = mcp_transport_security_settings()

    assert settings.enable_dns_rebinding_protection is True
    assert "127.0.0.1:*" in settings.allowed_hosts


def test_mcp_can_be_explicitly_enabled_for_network_hosts(monkeypatch):
    monkeypatch.setenv("OOMPAH_MCP_ALLOW_NETWORK", "true")

    settings = mcp_transport_security_settings()

    assert settings.enable_dns_rebinding_protection is False


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
