"""Focused tests for authenticated HTTP requests from ``oompah admin``."""

from __future__ import annotations

import base64
import io
import json
import urllib.error
import urllib.request

import pytest

from oompah import admin_cli
from oompah.client_auth import ClientCredentials


class _Response:
    status = 200

    def __init__(self, payload: dict):
        self._body = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, *args):
        return self._body


def test_api_sends_basic_auth_header(monkeypatch):
    captured: list[urllib.request.Request] = []

    def fake_urlopen(request, timeout):
        captured.append(request)
        return _Response({"ok": True})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(
        admin_cli, "_session_auth", ClientCredentials("operator", "secret")
    )

    status, payload = admin_cli._api("GET", "/api/v1/projects/example")

    assert status == 200
    assert payload == {"ok": True}
    authorization = captured[0].get_header("Authorization")
    assert authorization == "Basic " + base64.b64encode(b"operator:secret").decode()
    assert "secret" not in captured[0].full_url


def test_api_preserves_unauthenticated_mode(monkeypatch):
    captured: list[urllib.request.Request] = []

    def fake_urlopen(request, timeout):
        captured.append(request)
        return _Response({"ok": True})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(admin_cli, "_session_auth", None)

    status, payload = admin_cli._api("GET", "/api/v1/projects/example")

    assert status == 200
    assert payload == {"ok": True}
    assert captured[0].get_header("Authorization") is None


def test_api_401_has_safe_remediation(monkeypatch):
    def fake_urlopen(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url,
            401,
            "Unauthorized",
            {},
            io.BytesIO(b"Authorization: Basic c2VjcmV0"),
        )

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(
        admin_cli, "_session_auth", ClientCredentials("operator", "secret")
    )

    with pytest.raises(SystemExit) as exc_info:
        admin_cli._api("GET", "/api/v1/projects/example")

    message = str(exc_info.value)
    assert "401" in message
    assert "OOMPAH_SERVER_PASSWORD_FILE" in message
    assert "secret" not in message
    assert "Authorization: Basic" not in message


def test_server_url_with_userinfo_is_rejected_without_secret(monkeypatch):
    monkeypatch.setenv("OOMPAH_SERVER_URL", "http://operator:secret@example.test:8080")

    with pytest.raises(SystemExit) as exc_info:
        admin_cli._server_url()

    message = str(exc_info.value)
    assert "must not contain credentials" in message
    assert "secret" not in message


def test_parser_exposes_non_secret_auth_options():
    args = admin_cli.build_parser().parse_args(
        [
            "--username",
            "operator",
            "--password-file",
            "/run/secrets/pass",
            "state-branch-status",
            "p",
        ]
    )
    assert args.username == "operator"
    assert args.password_file == "/run/secrets/pass"
