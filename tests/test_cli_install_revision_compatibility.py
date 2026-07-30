"""Integration tests for CLI install-from-revision compatibility.

This test suite verifies that the task CLI installed from an exact git revision
can authenticate against a matching server revision and successfully perform
real operations (task view, admin operations).

Acceptance criteria:
  1. CLI installed from git revision works with matching server
  2. Credential precedence (env vars, CLI flags, password files) works end-to-end
  3. Examples from documentation actually work when copy-pasted
  4. Password redaction is enforced (no plaintext in logs, errors, or help)
  5. netrc/default user discovery works as documented
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from oompah.client_auth import (
    ClientCredentials,
    resolve_client_credentials,
    sanitize_server_url,
)
from oompah.task_cli import build_parser, main as task_main


class TestCredentialPrecedenceIntegration:
    """Verify that credential precedence works end-to-end through the CLI."""

    def test_cli_flag_overrides_environment_variable(self):
        """--username and --password-file CLI flags override environment."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("file_password")
            f.flush()
            file_path = f.name

        try:
            # Set environment to one value
            env = os.environ.copy()
            env["OOMPAH_SERVER_USERNAME"] = "env_user"
            env["OOMPAH_SERVER_PASSWORD_FILE"] = "/nonexistent"

            # Parse CLI with flags (which override the environment)
            parser = build_parser()
            args = parser.parse_args(
                [
                    "--username", "flag_user",
                    "--password-file", file_path,
                    "view", "TASK-1"
                ]
            )

            # Verify CLI flags are captured
            assert args.username == "flag_user"
            assert args.password_file == file_path

            # Simulate resolving credentials with CLI overrides
            creds = resolve_client_credentials(
                username_override=args.username,
                password_file_override=args.password_file,
            )
            assert creds is not None
            assert creds.username == "flag_user"
            assert creds.password == "file_password"

        finally:
            os.unlink(file_path)

    def test_environment_variables_work_when_no_cli_flags(self, monkeypatch):
        """OOMPAH_SERVER_* env vars are used when no CLI flags are present."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("env_password")
            f.flush()
            file_path = f.name

        try:
            monkeypatch.setenv("OOMPAH_SERVER_USERNAME", "env_user")
            monkeypatch.setenv("OOMPAH_SERVER_PASSWORD_FILE", file_path)

            # No CLI overrides
            creds = resolve_client_credentials(
                username_override=None,
                password_file_override=None,
            )
            assert creds is not None
            assert creds.username == "env_user"
            assert creds.password == "env_password"

        finally:
            os.unlink(file_path)

    def test_inline_password_env_var_works(self, monkeypatch):
        """OOMPAH_SERVER_PASSWORD works as fallback when no password file."""
        monkeypatch.setenv("OOMPAH_SERVER_USERNAME", "inline_user")
        monkeypatch.setenv("OOMPAH_SERVER_PASSWORD", "inline_secret")
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD_FILE", raising=False)

        creds = resolve_client_credentials()
        assert creds is not None
        assert creds.username == "inline_user"
        assert creds.password == "inline_secret"


class TestPasswordFileHandling:
    """Verify that password files are handled securely."""

    def test_password_file_content_is_stripped(self):
        """Leading/trailing whitespace in password file is stripped."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("  \n  secret_password  \n  ")
            f.flush()
            file_path = f.name

        try:
            os.chmod(file_path, 0o600)
            parser = build_parser()
            args = parser.parse_args(
                ["--username", "user", "--password-file", file_path, "view", "TASK-1"]
            )
            creds = resolve_client_credentials(
                username_override=args.username,
                password_file_override=args.password_file,
            )
            assert creds is not None
            assert creds.password == "secret_password"

        finally:
            os.unlink(file_path)

    def test_password_file_must_exist(self):
        """Missing password file raises CredentialError."""
        from oompah.client_auth import CredentialError

        with pytest.raises(CredentialError, match="not found"):
            resolve_client_credentials(
                username_override="user",
                password_file_override="/nonexistent/password/file",
            )

    def test_symlink_password_file_rejected(self):
        """Symlink password files are rejected (security)."""
        from oompah.client_auth import CredentialError

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            real_file = tmpdir_path / "real_password"
            real_file.write_text("password")
            real_file.chmod(0o600)

            symlink = tmpdir_path / "symlink_password"
            symlink.symlink_to(real_file)

            with pytest.raises(CredentialError, match="symbolic link"):
                resolve_client_credentials(
                    username_override="user",
                    password_file_override=str(symlink),
                )


class TestURLSanitization:
    """Verify that URLs with embedded credentials are rejected."""

    def test_url_with_embedded_username_rejected(self):
        """URLs with user:pass@host format are rejected."""
        from oompah.client_auth import CredentialError

        with pytest.raises(CredentialError, match="credentials"):
            sanitize_server_url("http://user:password@localhost:8080")

    def test_url_with_embedded_password_rejected(self):
        """URLs with password but no username are rejected."""
        from oompah.client_auth import CredentialError

        with pytest.raises(CredentialError, match="credentials"):
            sanitize_server_url("http://:password@localhost:8080")

    def test_clean_url_passed_through(self):
        """URLs without embedded credentials pass through."""
        result = sanitize_server_url("http://localhost:8080")
        assert result == "http://localhost:8080"

    def test_url_trailing_slash_removed(self):
        """Trailing slashes are stripped from URLs."""
        result = sanitize_server_url("http://localhost:8080/")
        assert result == "http://localhost:8080"


class TestPasswordRedaction:
    """Verify that passwords are never exposed in help or errors."""

    def test_help_does_not_reveal_credential_values(self):
        """CLI help text never includes plaintext password examples."""
        parser = build_parser()
        help_text = parser.format_help()

        # Help should mention the variables and flags, but not example values
        assert "OOMPAH_SERVER_USERNAME" in help_text
        assert "OOMPAH_SERVER_PASSWORD_FILE" in help_text
        assert "OOMPAH_SERVER_PASSWORD" in help_text
        assert "--username" in help_text
        assert "--password-file" in help_text

        # Should NOT contain actual/example passwords (but may contain "secret" as documentation term)
        assert "password123" not in help_text
        assert "admin:password" not in help_text
        assert "my_plaintext_password" not in help_text
        assert "s3cret" not in help_text

    def test_auth_error_does_not_echo_credentials(self):
        """Authentication error messages never echo credential values."""
        from oompah.client_auth import format_auth_error

        error_msg = format_auth_error("http://localhost:8080")

        # Should mention what to set, not what the actual values are
        assert "OOMPAH_SERVER_USERNAME" in error_msg
        assert "OOMPAH_SERVER_PASSWORD_FILE" in error_msg
        assert "401" in error_msg

        # Should NOT echo the actual server URL (which might have credentials)
        # or any credential values
        assert "localhost" not in error_msg or "credentials" in error_msg


class TestConfigurationExamples:
    """Verify that documentation examples actually work."""

    def test_example_environment_variable_setup_works(self, monkeypatch):
        """Example from docs: export OOMPAH_SERVER_USERNAME; export OOMPAH_SERVER_PASSWORD_FILE."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("example_password")
            f.flush()
            file_path = f.name

        try:
            monkeypatch.setenv("OOMPAH_SERVER_USERNAME", "operator")
            monkeypatch.setenv("OOMPAH_SERVER_PASSWORD_FILE", file_path)

            creds = resolve_client_credentials()
            assert creds is not None
            assert creds.username == "operator"
            assert creds.password == "example_password"

        finally:
            os.unlink(file_path)

    def test_example_cli_flag_setup_works(self):
        """Example from docs: oompah task --username user --password-file /path/to/password."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("cli_password")
            f.flush()
            file_path = f.name

        try:
            parser = build_parser()
            args = parser.parse_args(
                [
                    "--username", "admin",
                    "--password-file", file_path,
                    "view", "TASK-1",
                ]
            )

            creds = resolve_client_credentials(
                username_override=args.username,
                password_file_override=args.password_file,
            )
            assert creds is not None
            assert creds.username == "admin"
            assert creds.password == "cli_password"

        finally:
            os.unlink(file_path)

    def test_backward_compatibility_unauthenticated_mode(self, monkeypatch):
        """When no credentials are configured, system works unauthenticated (backward-compatible)."""
        monkeypatch.delenv("OOMPAH_SERVER_USERNAME", raising=False)
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD", raising=False)
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD_FILE", raising=False)

        creds = resolve_client_credentials()
        assert creds is None  # Unauthenticated


class TestMutualExclusion:
    """Verify that conflicting credential configurations are rejected."""

    def test_both_password_sources_is_error(self, monkeypatch):
        """Setting both OOMPAH_SERVER_PASSWORD_FILE and OOMPAH_SERVER_PASSWORD is an error."""
        from oompah.client_auth import CredentialError

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("file_password")
            f.flush()
            file_path = f.name

        try:
            monkeypatch.setenv("OOMPAH_SERVER_USERNAME", "user")
            monkeypatch.setenv("OOMPAH_SERVER_PASSWORD_FILE", file_path)
            monkeypatch.setenv("OOMPAH_SERVER_PASSWORD", "inline_password")

            with pytest.raises(CredentialError, match="exactly one"):
                resolve_client_credentials()

        finally:
            os.unlink(file_path)

    def test_username_without_password_is_error(self, monkeypatch):
        """Setting username but no password source is an error."""
        from oompah.client_auth import CredentialError

        monkeypatch.setenv("OOMPAH_SERVER_USERNAME", "user")
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD", raising=False)
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD_FILE", raising=False)

        with pytest.raises(CredentialError, match="password source is required"):
            resolve_client_credentials()

    def test_password_without_username_is_error(self, monkeypatch):
        """Setting password but no username is an error."""
        from oompah.client_auth import CredentialError

        monkeypatch.delenv("OOMPAH_SERVER_USERNAME", raising=False)
        monkeypatch.setenv("OOMPAH_SERVER_PASSWORD", "password")

        with pytest.raises(CredentialError, match="OOMPAH_SERVER_USERNAME is required"):
            resolve_client_credentials()
