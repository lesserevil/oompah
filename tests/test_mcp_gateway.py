"""Integration coverage for the embedded streamable-HTTP MCP gateway."""

from __future__ import annotations

import asyncio

import httpx
from fastapi.testclient import TestClient
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

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
