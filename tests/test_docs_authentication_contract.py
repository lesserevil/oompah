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
CLI_INSTALL_DOC = DOCS / "cli-install.md"


def _read(path: Path) -> str:
    assert path.is_file(), f"expected documentation file: {path}"
    return path.read_text(encoding="utf-8")


def _credential_precedence_sections() -> tuple[str, str]:
    """Return the dedicated credential-precedence section from each guide."""
    authentication = _read(AUTH_DOC)
    cli_install = _read(CLI_INSTALL_DOC)
    return (
        authentication.split("### CLI Credential Precedence", 1)[1].split(
            "### CLI authentication", 1
        )[0],
        cli_install.split("#### Credential precedence", 1)[1].split(
            "## Upgrading", 1
        )[0],
    )


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


def test_cli_credential_precedence_is_documented():
    """Verify that credential precedence is explicitly documented."""
    text = _read(AUTH_DOC)
    cli_install = _read(CLI_INSTALL_DOC)

    # Precedence must be documented in both files.
    for doc_text, precedence in zip(
        (text, cli_install), _credential_precedence_sections(), strict=True
    ):
        # Must mention precedence or priority
        assert any(word in doc_text for word in ["precedence", "priority", "highest", "override"]), \
            "Authentication guide must document credential precedence"
        
        # Must document CLI flag overrides
        assert "--username" in doc_text
        assert "--password-file" in doc_text
        
        # Must document environment variable behavior
        assert "OOMPAH_SERVER_USERNAME" in doc_text
        assert "OOMPAH_SERVER_PASSWORD_FILE" in doc_text
        assert "OOMPAH_SERVER_PASSWORD" in doc_text
        # Netrc is the third source tier for both task and admin surfaces. It
        # must be in the precedence section, rather than unrelated curl text.
        assert "~/.netrc" in precedence
        assert "Tier 3" in precedence
    
    # Examples must cover all precedence tiers
    for doc_text in (text, cli_install):
        doc_lower = doc_text.lower()
        # CLI flags
        assert "flag" in doc_lower or "--username" in doc_text
        # Environment variables
        assert "environment" in doc_lower or "OOMPAH_" in doc_text
        # Password files vs inline password
        assert "password file" in doc_lower or "OOMPAH_SERVER_PASSWORD_FILE" in doc_text
        assert "~/.netrc" in doc_text


def test_netrc_hostname_selection_is_documented_for_both_cli_surfaces():
    """Netrc lookup must remain reproducible for DNS and IP server URLs."""
    for doc_text in (_read(AUTH_DOC), _read(CLI_INSTALL_DOC)):
        lowered = doc_text.lower()
        assert "hostname" in lowered
        assert "port" in lowered
        assert "lowercase" in lowered
        assert "ipv4" in lowered
        assert "ipv6" in lowered
        assert "without url brackets" in lowered


def test_examples_show_password_file_not_inline_password():
    """Verify that documentation recommends password files over inline passwords."""
    text = _read(AUTH_DOC)
    cli_install = _read(DOCS / "cli-install.md")

    for doc_text in (text, cli_install):
        # Count recommendations
        password_file_count = doc_text.count("OOMPAH_SERVER_PASSWORD_FILE") + doc_text.count("--password-file")
        inline_password_count = doc_text.count("OOMPAH_SERVER_PASSWORD=")
        
        # Password files should be recommended more than inline
        assert password_file_count > inline_password_count, \
            "Documentation should prefer password files over inline passwords"
        
        # Should explicitly say "preferred" for password file
        assert "preferred" in doc_text or "Prefer" in doc_text


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
    assert "docs/authentication.md#cli-credential-precedence" in env
    assert "~/.netrc" in env


def test_cli_help_and_mcp_discovery_match_documented_auth_configuration():
    task_help = task_cli.build_parser().format_help()
    admin_help = admin_cli.build_parser().format_help()
    auth = _read(AUTH_DOC)

    for help_text in (task_help, admin_help):
        assert "OOMPAH_SERVER_USERNAME" in help_text
        assert "OOMPAH_SERVER_PASSWORD_FILE" in help_text
        assert "OOMPAH_SERVER_PASSWORD" in help_text
        assert "~/.netrc" in help_text
        assert "--password" in help_text
        assert "Never put credentials" in help_text

    enabled = discovery_document(authentication_enabled=True)
    assert enabled["authentication"] == "http-basic"
    assert enabled["mcp_endpoint"] == "/api/mcp/v1"
    assert enabled["discovery_path"] == "/.well-known/mcp"
    assert 'authentication: "http-basic"' in auth
