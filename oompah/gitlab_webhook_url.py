"""Resolve the callback URL used for managed GitLab project hooks.

An explicit ``OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL`` remains the preferred
deployment option for reverse proxies, TLS termination, NAT, and public
GitLab instances.  Self-managed GitLab installations often share a private
network with Oompah, though.  When no explicit URL is configured, this module
asks the operating system which local source address it would use to reach the
GitLab server and builds an HTTP callback URL from that address and Oompah's
active server port.

Route discovery uses a UDP socket. ``connect()`` selects a route and local
address in the kernel without sending an application payload.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlsplit

GITLAB_WEBHOOK_PATH = "/api/v1/webhooks/gitlab"

RouteSourceResolver = Callable[[str, int], str]


@dataclass(frozen=True)
class GitLabWebhookURLResolution:
    """Result of resolving one GitLab project's webhook callback URL."""

    url: str = ""
    source: str = ""
    error: str = ""

    @property
    def ok(self) -> bool:
        return bool(self.url) and not self.error


def _server_port(value: int | str | None) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        port = int(str(value).strip()) if value is not None else None
    except (TypeError, ValueError):
        return None
    if port is None or not 1 <= port <= 65535:
        return None
    return port


def _gitlab_destination(forge_url: str) -> tuple[str, int]:
    """Return the hostname and network port used to reach a GitLab server."""

    raw = str(forge_url or "").strip()
    if raw.startswith("git@") and ":" in raw:
        host = raw.split("@", 1)[1].split(":", 1)[0].strip()
        if not host:
            raise ValueError("GitLab repository URL has no hostname")
        return host, 22

    parsed = urlsplit(raw)
    if not parsed.hostname:
        raise ValueError("GitLab forge URL has no hostname")
    try:
        explicit_port = parsed.port
    except ValueError as exc:
        raise ValueError("GitLab forge URL has an invalid port") from exc
    if explicit_port is not None:
        return parsed.hostname, explicit_port
    if parsed.scheme == "http":
        return parsed.hostname, 80
    if parsed.scheme == "ssh":
        return parsed.hostname, 22
    return parsed.hostname, 443


def route_source_address(host: str, port: int) -> str:
    """Return the local IP selected by the OS route to ``host`` and ``port``.

    ``SOCK_DGRAM`` is intentional: connecting a UDP socket records a peer and
    selects the outbound route, but does not establish a connection or send
    application data.
    """

    errors: list[str] = []
    try:
        candidates = socket.getaddrinfo(
            host,
            port,
            type=socket.SOCK_DGRAM,
        )
    except OSError as exc:
        raise OSError(f"cannot resolve GitLab host {host!r}: {exc}") from exc

    for family, socktype, protocol, _canonical_name, sockaddr in candidates:
        if family not in {socket.AF_INET, socket.AF_INET6}:
            continue
        try:
            with socket.socket(family, socktype, protocol) as route_socket:
                route_socket.connect(sockaddr)
                local_address = str(route_socket.getsockname()[0]).strip()
            address = ipaddress.ip_address(local_address.split("%", 1)[0])
            if address.is_unspecified:
                errors.append(f"{family}: route selected an unspecified address")
                continue
            return str(address)
        except (OSError, ValueError) as exc:
            errors.append(f"{family}: {exc}")

    detail = "; ".join(errors) if errors else "no IPv4 or IPv6 route candidates"
    raise OSError(f"cannot select a local route to GitLab host {host!r}: {detail}")


def _callback_host(address: str) -> str:
    parsed = ipaddress.ip_address(address.split("%", 1)[0])
    return f"[{parsed}]" if parsed.version == 6 else str(parsed)


def resolve_gitlab_webhook_url(
    *,
    forge_url: str,
    explicit_public_url: str | None,
    server_port: int | str | None,
    route_resolver: RouteSourceResolver = route_source_address,
) -> GitLabWebhookURLResolution:
    """Resolve the effective callback URL for one GitLab project.

    Explicit URLs are validated as public HTTPS base URLs and always take
    precedence.  Without one, the callback uses the route-selected local IP
    and Oompah's active HTTP server port.
    """

    explicit = str(explicit_public_url or "").strip().rstrip("/")
    if explicit:
        try:
            parsed = urlsplit(explicit)
            parsed.port
            valid_explicit = (
                parsed.scheme == "https"
                and bool(parsed.hostname)
                and parsed.username is None
                and parsed.password is None
            )
        except ValueError:
            valid_explicit = False
        if not valid_explicit:
            return GitLabWebhookURLResolution(
                source="explicit",
                error=(
                    "OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL must be a public HTTPS "
                    "base URL with a hostname and no embedded credentials"
                ),
            )
        return GitLabWebhookURLResolution(
            url=f"{explicit}{GITLAB_WEBHOOK_PATH}",
            source="explicit",
        )

    port = _server_port(server_port)
    if port is None:
        return GitLabWebhookURLResolution(
            source="route",
            error=(
                "cannot derive the GitLab webhook callback URL because the "
                "Oompah server port is disabled or invalid"
            ),
        )

    try:
        host, destination_port = _gitlab_destination(forge_url)
        local_address = route_resolver(host, destination_port)
        callback_host = _callback_host(local_address)
    except (OSError, ValueError) as exc:
        return GitLabWebhookURLResolution(
            source="route",
            error=f"cannot derive the GitLab webhook callback URL: {exc}",
        )

    return GitLabWebhookURLResolution(
        url=f"http://{callback_host}:{port}{GITLAB_WEBHOOK_PATH}",
        source="route",
    )
