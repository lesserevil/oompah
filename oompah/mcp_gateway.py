"""Embedded, fail-closed OpenAPI-to-MCP gateway.

The gateway deliberately derives its catalogue from the running FastAPI
application's OpenAPI schema, but only registers operations approved by
``mcp_exposure_policy``.  This keeps new API routes private until they have
an explicit policy classification.
"""

from __future__ import annotations

import re
import os
from collections.abc import Callable
from typing import Any
from urllib.parse import quote

import httpx
from fastapi import FastAPI
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from oompah.mcp_exposure_policy import (
    MCP_DISCOVERY_PATH,
    MCP_ENDPOINT_PATH,
    is_route_exposed,
)

_PATH_PARAMETER_RE = re.compile(r"\{([^}:]+)(?::[^}]+)?\}")
_TOOL_NAME_RE = re.compile(r"[^a-zA-Z0-9_]")
_MCP_ALLOW_NETWORK_ENV = "OOMPAH_MCP_ALLOW_NETWORK"


class _InternalMcpDispatch:
    """Attach a server-private capability to one synthetic ASGI request.

    The capability is an object used as both the scope key and value.  HTTP
    clients can supply header strings, but cannot create this object identity.
    """

    def __init__(self, app: FastAPI, capability: object) -> None:
        self._app = app
        self._capability = capability

    async def __call__(self, scope, receive, send) -> None:  # noqa: ANN001
        internal_scope = dict(scope)
        internal_scope[self._capability] = self._capability
        await self._app(internal_scope, receive, send)


def mcp_network_access_enabled() -> bool:
    """Return whether the operator explicitly enabled network MCP access."""
    return os.environ.get(_MCP_ALLOW_NETWORK_ENV, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def mcp_transport_security_settings() -> TransportSecuritySettings:
    """Build transport protection for the configured MCP exposure scope.

    FastMCP's DNS-rebinding check validates exact Host headers.  That is right
    for the default local endpoint, but cannot enumerate every interface or
    DNS name when an operator explicitly exposes MCP on the network.
    """
    if mcp_network_access_enabled():
        return TransportSecuritySettings(enable_dns_rebinding_protection=False)
    return TransportSecuritySettings(
        allowed_hosts=["127.0.0.1", "127.0.0.1:*", "localhost", "localhost:*"]
    )


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


async def _dispatch_api_call(
    api_app: FastAPI,
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
    internal_dispatch_capability: object | None = None,
) -> httpx.Response:
    """Send one request to *api_app* via its ASGI interface and return the raw response.

    Uses :class:`httpx.ASGITransport` so no real network socket is opened.
    The synthetic ``base_url`` (``http://oompah.local``) never leaves the
    process.

    ``internal_dispatch_capability`` is a server-private object identity used
    only after an authenticated MCP tool invocation.  It is attached directly
    to the synthetic ASGI scope, never serialised into a header or response.
    """
    dispatch_app = (
        _InternalMcpDispatch(api_app, internal_dispatch_capability)
        if internal_dispatch_capability is not None
        else api_app
    )
    transport = httpx.ASGITransport(app=dispatch_app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://oompah.local"
    ) as client:
        return await client.request(method.upper(), path, params=params, json=body)


def _has_mcp_authentication_capability(
    context: Context,
    capability: object | None,
) -> bool:
    """Return whether *context* originated from a verified MCP HTTP request."""
    if capability is None:
        return False
    try:
        request = context.request_context.request
        scope = getattr(request, "scope", None)
    except ValueError:
        return False
    return isinstance(scope, dict) and scope.get(capability) is capability


def build_mcp_gateway(
    api_app: FastAPI,
    *,
    mcp_authentication_capability: object | None = None,
    internal_dispatch_capability: object | None = None,
    authentication_enabled: Callable[[], bool] | None = None,
) -> FastMCP:
    """Build the MCP server from allowed operations in ``api_app.openapi()``.

    Requests are dispatched through FastAPI's ASGI interface rather than an
    externally supplied URL.  This is the same local service boundary, does
    not propagate client credentials, and works for both uvicorn and tests.

    When Basic authentication is active, the caller supplies two distinct
    private object identities.  The first must be present on the source MCP
    request before a tool can make an API call; the second marks only the
    resulting in-process ASGI dispatch.  Neither capability is representable
    by an HTTP header or MCP tool argument.
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
        transport_security=mcp_transport_security_settings(),
    )
    schema = api_app.openapi()
    names: set[str] = set()
    is_authentication_enabled = authentication_enabled or (lambda: False)

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
                    context: Context | None = None,
                ) -> dict[str, Any]:
                    dispatch_capability: object | None = None
                    if is_authentication_enabled():
                        if (
                            context is None
                            or internal_dispatch_capability is None
                            or not _has_mcp_authentication_capability(
                                context, mcp_authentication_capability
                            )
                        ):
                            # The public transport normally rejects this
                            # request first.  Keep the tool fail-closed if it
                            # is ever invoked without that transport context.
                            return {"status_code": 401, "body": "Unauthorized"}
                        dispatch_capability = internal_dispatch_capability
                    rendered_path = _render_path(request_path, path_params or {})
                    response = await _dispatch_api_call(
                        api_app,
                        request_method,
                        rendered_path,
                        params=query,
                        body=body,
                        internal_dispatch_capability=dispatch_capability,
                    )
                    return _response_payload(response)

                return invoke

            gateway.add_tool(make_operation(method, path), name=name, description=description)

    return gateway


def discovery_document(*, authentication_enabled: bool = False) -> dict[str, Any]:
    """Return MCP discovery metadata for the effective authentication mode."""
    return {
        "name": "oompah",
        "version": "v1",
        "transport": "streamable-http",
        "mcp_endpoint": MCP_ENDPOINT_PATH,
        "discovery_path": MCP_DISCOVERY_PATH,
        "authentication": (
            "http-basic"
            if authentication_enabled
            else "none; local service access only"
        ),
    }
