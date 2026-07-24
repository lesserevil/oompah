"""Embedded, fail-closed OpenAPI-to-MCP gateway.

The gateway deliberately derives its catalogue from the running FastAPI
application's OpenAPI schema, but only registers operations approved by
``mcp_exposure_policy``.  This keeps new API routes private until they have
an explicit policy classification.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any
from urllib.parse import quote

import httpx
from fastapi import FastAPI
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from oompah.mcp_exposure_policy import (
    MCP_DISCOVERY_PATH,
    MCP_ENDPOINT_PATH,
    is_route_exposed,
)

_PATH_PARAMETER_RE = re.compile(r"\{([^}:]+)(?::[^}]+)?\}")
_TOOL_NAME_RE = re.compile(r"[^a-zA-Z0-9_]")


def _tool_name(method: str, path: str, operation: dict[str, Any]) -> str:
    """Return a stable MCP-safe name for an OpenAPI operation."""
    candidate = str(operation.get("operationId") or f"{method}_{path}")
    candidate = _TOOL_NAME_RE.sub("_", candidate).strip("_").lower()
    return candidate or f"{method.lower()}_operation"


def _render_path(path: str, path_params: dict[str, Any]) -> str:
    """Fill an OpenAPI path template, rejecting omitted parameters."""

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in path_params:
            raise ValueError(f"missing required path parameter: {name}")
        return quote(str(path_params[name]), safe="")

    return _PATH_PARAMETER_RE.sub(replace, path)


def _response_payload(response: httpx.Response) -> dict[str, Any]:
    """Return a JSON-safe, status-preserving API response for an MCP call."""
    try:
        content: Any = response.json()
    except ValueError:
        content = response.text
    return {"status_code": response.status_code, "body": content}


def build_mcp_gateway(api_app: FastAPI) -> FastMCP:
    """Build the MCP server from allowed operations in ``api_app.openapi()``.

    Requests are dispatched through FastAPI's ASGI interface rather than an
    externally supplied URL.  This is the same local service boundary, does
    not propagate client credentials, and works for both uvicorn and tests.
    """
    gateway = FastMCP(
        "oompah",
        instructions=(
            "Use these tools to inspect oompah and manage tasks. "
            "Administrative, credential, webhook, release, and orchestrator "
            "operations are intentionally unavailable."
        ),
        streamable_http_path="/",
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(
            allowed_hosts=["127.0.0.1", "127.0.0.1:*", "localhost", "localhost:*"]
        ),
    )
    schema = api_app.openapi()
    names: set[str] = set()

    for path, path_item in schema.get("paths", {}).items():
        for method, operation in path_item.items():
            if method.upper() not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                continue
            if not isinstance(operation, dict) or not is_route_exposed(method, path):
                continue

            name = _tool_name(method, path, operation)
            if name in names:
                name = f"{name}_{len(names)}"
            names.add(name)
            description = str(
                operation.get("description")
                or operation.get("summary")
                or f"{method.upper()} {path}"
            )

            def make_operation(
                request_method: str, request_path: str
            ) -> Callable[..., Any]:
                async def invoke(
                    path_params: dict[str, Any] | None = None,
                    query: dict[str, Any] | None = None,
                    body: dict[str, Any] | None = None,
                ) -> dict[str, Any]:
                    rendered_path = _render_path(request_path, path_params or {})
                    transport = httpx.ASGITransport(app=api_app)
                    async with httpx.AsyncClient(
                        transport=transport, base_url="http://oompah.local"
                    ) as client:
                        response = await client.request(
                            request_method.upper(),
                            rendered_path,
                            params=query,
                            json=body,
                        )
                    return _response_payload(response)

                return invoke

            gateway.add_tool(make_operation(method, path), name=name, description=description)

    return gateway


def discovery_document() -> dict[str, Any]:
    """Return static, credential-free MCP discovery metadata."""
    return {
        "name": "oompah",
        "version": "v1",
        "transport": "streamable-http",
        "mcp_endpoint": MCP_ENDPOINT_PATH,
        "discovery_path": MCP_DISCOVERY_PATH,
        "authentication": "none; local service access only",
    }
