"""Contract tests for the operator HTTP Basic-authentication documentation.

The authentication guide is a security boundary: examples must remain
copy-safe, configuration names must match the client/server surfaces, and the
documented public-route exception list must not drift from the middleware.
"""

from __future__ import annotations

import re
from pathlib import Path

from oompah import admin_cli, task_cli
from oompah.mcp_gateway import discovery_document
from oompah.server import _BasicAuthMiddleware


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
AUTH_DOC = DOCS / "authentication.md"


def _read(path: Path) -> str:
    assert path.is_file(), f"expected documentation file: {path}"
    return path.read_text(encoding="utf-8")


def test_authentication_guide_covers_the_security_and_operations_contract():
    text = _read(AUTH_DOC)

    required_fragments = (
        "OOMPAH_HTPASSWD_FILE",
        "OOMPAH_SERVER_USERNAME",
        "OOMPAH_SERVER_PASSWORD_FILE",
        "OOMPAH_SERVER_PASSWORD",
        "OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL",
        "HTTPS",
        "TLS",
        "reverse proxy",
        "htpasswd -B",
        "chmod 600",
        "make restart",
        "make status",
        "make graceful",
        "/.well-known/mcp",
        "/api/mcp/v1",
        "401",
        "lockout",
        "rollback",
        "bcrypt",
        "APR1",
    )
    lowered = text.lower()
    missing = [fragment for fragment in required_fragments if fragment.lower() not in lowered]
    assert not missing, f"authentication guide is missing: {missing}"


def test_only_exact_public_routes_are_documented_as_basic_auth_exempt():
    text = _read(AUTH_DOC)
    expected = {
        ("GET", "/healthz"),
        ("POST", "/api/v1/webhooks/github"),
        ("POST", "/api/v1/webhooks/gitlab"),
    }

    assert _BasicAuthMiddleware._AUTH_EXEMPT == frozenset(expected)
    for method, path in expected:
        assert f"`{method} {path}`" in text

    for protected in (
        "/api/v1/webhooks/gitlab/status",
        "/openapi.json",
        "/ws",
        "/api/mcp/v1",
        "/.well-known/mcp",
    ):
        assert protected in text
    assert "Every other route is protected" in text


def test_authentication_examples_do_not_put_passwords_in_commands_or_hashes():
    text = _read(AUTH_DOC)

    # A password-bearing --user argument is visible to shell history/process
    # inspection. The guide may use the safe ``"$USER:"`` prompt form only.
    assert "curl -u " not in text
    assert not re.search(r"curl[^\n`]*--user\s+[^\n`]*:[A-Za-z][A-Za-z0-9_-]*", text)
    assert "cat $OOMPAH_SERVER_PASSWORD_FILE" not in text
    assert "admin:password" not in text
    assert "my_plaintext_password" not in text

    # Prefixes are documentation, but a complete-looking generated hash is
    # not. This prevents a real/disposable credential from becoming a fixture.
    assert not re.search(r"\$2[aby]\$\d{2}\$[A-Za-z0-9./]{20,}", text)
    assert not re.search(r"\$apr1\$[^`\s]{20,}", text)


def test_documentation_links_and_env_example_are_present():
    auth = _read(AUTH_DOC)
    env = _read(ROOT / ".env.example")
    runbook = _read(DOCS / "operator-runbook.md")
    cli = _read(DOCS / "cli-install.md")
    bootstrap = _read(DOCS / "project-bootstrap.md")
    index = _read(DOCS / "README.md")

    assert "authentication.md" in runbook
    assert "authentication.md" in cli
    assert "authentication.md" in bootstrap
    assert "authentication.md" in index
    assert "docs/authentication.md" in env
    assert "OOMPAH_HTPASSWD_FILE" in auth and "OOMPAH_HTPASSWD_FILE" in env
    assert "OOMPAH_SERVER_USERNAME" in auth and "OOMPAH_SERVER_USERNAME" in cli
    assert "OOMPAH_SERVER_PASSWORD_FILE" in auth and "OOMPAH_SERVER_PASSWORD_FILE" in cli
    assert "OOMPAH_SERVER_PASSWORD" in env


def test_cli_help_and_mcp_discovery_match_documented_auth_configuration():
    task_help = task_cli.build_parser().format_help()
    admin_help = admin_cli.build_parser().format_help()
    auth = _read(AUTH_DOC)

    for help_text in (task_help, admin_help):
        assert "OOMPAH_SERVER_USERNAME" in help_text
        assert "OOMPAH_SERVER_PASSWORD_FILE" in help_text
        assert "OOMPAH_SERVER_PASSWORD" in help_text
        assert "--password" in help_text
        assert "Never put credentials" in help_text

    enabled = discovery_document(authentication_enabled=True)
    assert enabled["authentication"] == "http-basic"
    assert enabled["mcp_endpoint"] == "/api/mcp/v1"
    assert enabled["discovery_path"] == "/.well-known/mcp"
    assert 'authentication: "http-basic"' in auth
