"""Tests for route-derived GitLab webhook callback URLs."""

from __future__ import annotations

import socket
from unittest.mock import MagicMock

from oompah.gitlab_webhook_url import (
    GITLAB_WEBHOOK_PATH,
    resolve_gitlab_webhook_url,
    route_source_address,
)


def test_explicit_public_url_wins_without_route_discovery():
    resolver = MagicMock(side_effect=AssertionError("route lookup must not run"))

    result = resolve_gitlab_webhook_url(
        forge_url="https://gitlab.internal.example",
        explicit_public_url="https://oompah.example.com/base/",
        server_port=None,
        route_resolver=resolver,
    )

    assert result.ok is True
    assert result.source == "explicit"
    assert result.url == (
        f"https://oompah.example.com/base{GITLAB_WEBHOOK_PATH}"
    )
    resolver.assert_not_called()


def test_route_fallback_uses_ipv4_source_and_active_server_port():
    resolver = MagicMock(return_value="10.24.8.19")

    result = resolve_gitlab_webhook_url(
        forge_url="https://gitlab.internal.example",
        explicit_public_url=None,
        server_port=8090,
        route_resolver=resolver,
    )

    assert result.ok is True
    assert result.source == "route"
    assert result.url == f"http://10.24.8.19:8090{GITLAB_WEBHOOK_PATH}"
    resolver.assert_called_once_with("gitlab.internal.example", 443)


def test_route_fallback_brackets_ipv6_source():
    resolver = MagicMock(return_value="2001:db8:1::20")

    result = resolve_gitlab_webhook_url(
        forge_url="https://[2001:db8:2::30]:8443",
        explicit_public_url="",
        server_port="8080",
        route_resolver=resolver,
    )

    assert result.url == f"http://[2001:db8:1::20]:8080{GITLAB_WEBHOOK_PATH}"
    resolver.assert_called_once_with("2001:db8:2::30", 8443)


def test_route_fallback_uses_http_and_ssh_destination_ports():
    resolver = MagicMock(return_value="192.0.2.20")

    http_result = resolve_gitlab_webhook_url(
        forge_url="http://gitlab.internal.example/group/project",
        explicit_public_url=None,
        server_port=8080,
        route_resolver=resolver,
    )
    ssh_result = resolve_gitlab_webhook_url(
        forge_url="git@gitlab.internal.example:group/project.git",
        explicit_public_url=None,
        server_port=8080,
        route_resolver=resolver,
    )

    assert http_result.ok is True
    assert ssh_result.ok is True
    assert resolver.call_args_list[0].args == ("gitlab.internal.example", 80)
    assert resolver.call_args_list[1].args == ("gitlab.internal.example", 22)


def test_route_failure_is_actionable_and_does_not_guess():
    resolver = MagicMock(side_effect=OSError("network is unreachable"))

    result = resolve_gitlab_webhook_url(
        forge_url="https://gitlab.internal.example",
        explicit_public_url=None,
        server_port=8080,
        route_resolver=resolver,
    )

    assert result.ok is False
    assert result.url == ""
    assert result.source == "route"
    assert "network is unreachable" in result.error


def test_invalid_server_port_fails_before_route_discovery():
    resolver = MagicMock(side_effect=AssertionError("route lookup must not run"))

    for port in (None, 0, 65536, "not-a-port"):
        result = resolve_gitlab_webhook_url(
            forge_url="https://gitlab.internal.example",
            explicit_public_url=None,
            server_port=port,
            route_resolver=resolver,
        )
        assert result.ok is False
        assert "server port" in result.error

    resolver.assert_not_called()


def test_invalid_explicit_url_fails_without_route_fallback():
    resolver = MagicMock(side_effect=AssertionError("route lookup must not run"))

    result = resolve_gitlab_webhook_url(
        forge_url="https://gitlab.internal.example",
        explicit_public_url="http://oompah.example.com",
        server_port=8080,
        route_resolver=resolver,
    )

    assert result.ok is False
    assert result.source == "explicit"
    assert "public HTTPS" in result.error
    resolver.assert_not_called()


def test_explicit_url_rejects_embedded_credentials():
    result = resolve_gitlab_webhook_url(
        forge_url="https://gitlab.internal.example",
        explicit_public_url="https://operator:secret@oompah.example.com",
        server_port=8080,
    )

    assert result.ok is False
    assert "no embedded credentials" in result.error
    assert "operator" not in result.error
    assert "secret" not in result.error


def test_route_source_address_selects_route_without_sending_data(monkeypatch):
    fake_socket = MagicMock()
    fake_socket.__enter__.return_value = fake_socket
    fake_socket.getsockname.return_value = ("10.4.3.2", 41234)
    socket_factory = MagicMock(return_value=fake_socket)
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        MagicMock(
            return_value=[
                (
                    socket.AF_INET,
                    socket.SOCK_DGRAM,
                    socket.IPPROTO_UDP,
                    "",
                    ("10.4.3.1", 443),
                )
            ]
        ),
    )
    monkeypatch.setattr(socket, "socket", socket_factory)

    assert route_source_address("gitlab.internal.example", 443) == "10.4.3.2"
    fake_socket.connect.assert_called_once_with(("10.4.3.1", 443))
    fake_socket.send.assert_not_called()
    fake_socket.sendto.assert_not_called()
