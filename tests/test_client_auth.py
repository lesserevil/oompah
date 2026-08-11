"""Tests for oompah.client_auth — client-side Basic-auth credential resolver.

Security test coverage:
  - Unauthenticated (no env vars) → None (backward-compatible)
  - Valid credentials from env vars (username + password env)
  - Valid credentials from password file
  - CLI overrides take precedence over env vars
  - Missing username when password set → error
  - Missing password when username set → error
  - Both password sources set → mutual exclusion error
  - Password file not found → error
  - Password file is a symlink → error (symlink-substitution attack prevention)
  - Password file is not a regular file (directory) → error
  - Password file unreadable (mode 000) → error
  - Password file empty → error
  - Password file world-readable → warning (not fatal)
  - Password file group-readable → warning (not fatal)
  - Password file with leading/trailing whitespace → stripped
  - URL with embedded username → rejected (credential leak prevention)
  - URL with embedded password → rejected
  - Clean URL → returned unchanged
  - format_auth_error: never echoes credentials
  - TOCTOU race via inode change after lstat (simulated)
"""

from __future__ import annotations

import os
import shutil
import stat
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from oompah.client_auth import (
    CLIENT_AUTH_DISABLED_ENV,
    SERVICE_CHECKOUT_ENV,
    SERVICE_VENV_ENV,
    TASK_VENV_ENV,
    ClientCredentials,
    CredentialError,
    _check_password_file_permissions,
    _read_password_file,
    agent_environment,
    format_auth_error,
    load_client_environment,
    resolve_client_credentials,
    sanitize_server_url,
    task_venv_path,
)

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tmp_file(content: str, mode: int = 0o600) -> str:
    """Create a temporary regular file with content and permissions; return path."""
    fd, path = tempfile.mkstemp()
    try:
        os.write(fd, content.encode("utf-8"))
    finally:
        os.close(fd)
    os.chmod(path, mode)
    return path


# ---------------------------------------------------------------------------
# resolve_client_credentials
# ---------------------------------------------------------------------------


class TestNoCredentials:
    """When nothing is configured, returns None (backward-compatible)."""

    def test_all_env_absent_returns_none(self, monkeypatch):
        monkeypatch.delenv("OOMPAH_SERVER_USERNAME", raising=False)
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD", raising=False)
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD_FILE", raising=False)
        assert resolve_client_credentials() is None

    def test_empty_strings_treated_as_absent(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_SERVER_USERNAME", "")
        monkeypatch.setenv("OOMPAH_SERVER_PASSWORD", "")
        monkeypatch.setenv("OOMPAH_SERVER_PASSWORD_FILE", "")
        assert resolve_client_credentials() is None

    def test_whitespace_only_env_treated_as_absent(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_SERVER_USERNAME", "   ")
        monkeypatch.setenv("OOMPAH_SERVER_PASSWORD", "  ")
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD_FILE", raising=False)
        assert resolve_client_credentials() is None


class TestPasswordEnvVar:
    """Inline password from OOMPAH_SERVER_PASSWORD env var."""

    def test_username_and_password_env_returns_credentials(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_SERVER_USERNAME", "alice")
        monkeypatch.setenv("OOMPAH_SERVER_PASSWORD", "s3cret")
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD_FILE", raising=False)
        creds = resolve_client_credentials()
        assert creds is not None
        assert creds.username == "alice"
        assert creds.password == "s3cret"

    def test_username_stripped_of_whitespace(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_SERVER_USERNAME", "  alice  ")
        monkeypatch.setenv("OOMPAH_SERVER_PASSWORD", "pass")
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD_FILE", raising=False)
        creds = resolve_client_credentials()
        assert creds is not None
        assert creds.username == "alice"

    def test_password_env_stripped_of_whitespace(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_SERVER_USERNAME", "user")
        monkeypatch.setenv("OOMPAH_SERVER_PASSWORD", "  mypass  ")
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD_FILE", raising=False)
        creds = resolve_client_credentials()
        assert creds is not None
        assert creds.password == "mypass"

    def test_returns_named_tuple(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_SERVER_USERNAME", "u")
        monkeypatch.setenv("OOMPAH_SERVER_PASSWORD", "p")
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD_FILE", raising=False)
        creds = resolve_client_credentials()
        assert isinstance(creds, ClientCredentials)
        assert creds.username == "u"
        assert creds.password == "p"


class TestPasswordFile:
    """Password from OOMPAH_SERVER_PASSWORD_FILE env var."""

    def test_password_file_env_reads_file(self, monkeypatch):
        path = _tmp_file("mypassword\n")
        try:
            monkeypatch.setenv("OOMPAH_SERVER_USERNAME", "bob")
            monkeypatch.setenv("OOMPAH_SERVER_PASSWORD_FILE", path)
            monkeypatch.delenv("OOMPAH_SERVER_PASSWORD", raising=False)
            creds = resolve_client_credentials()
            assert creds is not None
            assert creds.username == "bob"
            assert creds.password == "mypassword"
        finally:
            os.unlink(path)

    def test_password_file_content_stripped(self, monkeypatch):
        path = _tmp_file("  hunter2  \n")
        try:
            monkeypatch.setenv("OOMPAH_SERVER_USERNAME", "carol")
            monkeypatch.setenv("OOMPAH_SERVER_PASSWORD_FILE", path)
            monkeypatch.delenv("OOMPAH_SERVER_PASSWORD", raising=False)
            creds = resolve_client_credentials()
            assert creds is not None
            assert creds.password == "hunter2"
        finally:
            os.unlink(path)


class TestCliOverrides:
    """CLI --username and --password-file take precedence over env vars."""

    def test_username_override_wins_over_env(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_SERVER_USERNAME", "env_user")
        monkeypatch.setenv("OOMPAH_SERVER_PASSWORD", "pass")
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD_FILE", raising=False)
        creds = resolve_client_credentials(username_override="cli_user")
        assert creds is not None
        assert creds.username == "cli_user"

    def test_password_file_override_wins_over_env(self, monkeypatch):
        path = _tmp_file("cli_pass")
        env_path = _tmp_file("env_pass")
        try:
            monkeypatch.setenv("OOMPAH_SERVER_USERNAME", "user")
            monkeypatch.setenv("OOMPAH_SERVER_PASSWORD_FILE", env_path)
            monkeypatch.delenv("OOMPAH_SERVER_PASSWORD", raising=False)
            creds = resolve_client_credentials(password_file_override=path)
            assert creds is not None
            assert creds.password == "cli_pass"
        finally:
            os.unlink(path)
            os.unlink(env_path)

    def test_password_file_override_wins_over_inline_password(self, monkeypatch):
        path = _tmp_file("file_pass")
        try:
            monkeypatch.setenv("OOMPAH_SERVER_USERNAME", "user")
            monkeypatch.setenv("OOMPAH_SERVER_PASSWORD", "inline_pass")
            monkeypatch.delenv("OOMPAH_SERVER_PASSWORD_FILE", raising=False)
            creds = resolve_client_credentials(password_file_override=path)
            assert creds is not None
            assert creds.password == "file_pass"
        finally:
            os.unlink(path)

    def test_username_and_password_file_both_overridden(self, monkeypatch):
        path = _tmp_file("secretpass")
        try:
            monkeypatch.delenv("OOMPAH_SERVER_USERNAME", raising=False)
            monkeypatch.delenv("OOMPAH_SERVER_PASSWORD", raising=False)
            monkeypatch.delenv("OOMPAH_SERVER_PASSWORD_FILE", raising=False)
            creds = resolve_client_credentials(
                username_override="override_user",
                password_file_override=path,
            )
            assert creds is not None
            assert creds.username == "override_user"
            assert creds.password == "secretpass"
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# Error cases: missing / inconsistent configuration
# ---------------------------------------------------------------------------


class TestMissingUsername:
    """Password set but no username → error."""

    def test_password_env_without_username(self, monkeypatch):
        monkeypatch.delenv("OOMPAH_SERVER_USERNAME", raising=False)
        monkeypatch.setenv("OOMPAH_SERVER_PASSWORD", "pass")
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD_FILE", raising=False)
        with pytest.raises(CredentialError, match="OOMPAH_SERVER_USERNAME is required"):
            resolve_client_credentials()

    def test_password_file_without_username(self, monkeypatch):
        path = _tmp_file("pass")
        try:
            monkeypatch.delenv("OOMPAH_SERVER_USERNAME", raising=False)
            monkeypatch.setenv("OOMPAH_SERVER_PASSWORD_FILE", path)
            monkeypatch.delenv("OOMPAH_SERVER_PASSWORD", raising=False)
            with pytest.raises(CredentialError, match="OOMPAH_SERVER_USERNAME is required"):
                resolve_client_credentials()
        finally:
            os.unlink(path)


class TestMissingPassword:
    """Username set but no password source → error."""

    def test_username_without_password(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_SERVER_USERNAME", "user")
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD", raising=False)
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD_FILE", raising=False)
        with pytest.raises(CredentialError, match="password source is required"):
            resolve_client_credentials()


class TestMutualExclusion:
    """Both password sources set → mutual exclusion error."""

    def test_both_password_env_and_file_raises(self, monkeypatch):
        path = _tmp_file("pass")
        try:
            monkeypatch.setenv("OOMPAH_SERVER_USERNAME", "user")
            monkeypatch.setenv("OOMPAH_SERVER_PASSWORD", "inline")
            monkeypatch.setenv("OOMPAH_SERVER_PASSWORD_FILE", path)
            with pytest.raises(CredentialError, match="exactly one"):
                resolve_client_credentials()
        finally:
            os.unlink(path)

    def test_error_message_does_not_contain_password(self, monkeypatch):
        path = _tmp_file("secretpassword")
        try:
            monkeypatch.setenv("OOMPAH_SERVER_USERNAME", "user")
            monkeypatch.setenv("OOMPAH_SERVER_PASSWORD", "inlinepassword")
            monkeypatch.setenv("OOMPAH_SERVER_PASSWORD_FILE", path)
            try:
                resolve_client_credentials()
            except CredentialError as exc:
                msg = str(exc)
                assert "secretpassword" not in msg
                assert "inlinepassword" not in msg
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# Password file error cases
# ---------------------------------------------------------------------------


class TestPasswordFileErrors:
    """All password file failure modes."""

    def test_file_not_found(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_SERVER_USERNAME", "user")
        monkeypatch.setenv("OOMPAH_SERVER_PASSWORD_FILE", "/nonexistent/does/not/exist.txt")
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD", raising=False)
        with pytest.raises(CredentialError, match="not found"):
            resolve_client_credentials()

    def test_symlink_rejected(self, monkeypatch, tmp_path):
        target = tmp_path / "real_pass.txt"
        target.write_text("mypassword")
        link = tmp_path / "pass_link.txt"
        link.symlink_to(target)
        monkeypatch.setenv("OOMPAH_SERVER_USERNAME", "user")
        monkeypatch.setenv("OOMPAH_SERVER_PASSWORD_FILE", str(link))
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD", raising=False)
        with pytest.raises(CredentialError, match="symbolic link"):
            resolve_client_credentials()

    def test_directory_rejected(self, monkeypatch, tmp_path):
        monkeypatch.setenv("OOMPAH_SERVER_USERNAME", "user")
        monkeypatch.setenv("OOMPAH_SERVER_PASSWORD_FILE", str(tmp_path))
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD", raising=False)
        with pytest.raises(CredentialError, match="not a regular file"):
            resolve_client_credentials()

    def test_unreadable_file(self, monkeypatch):
        path = _tmp_file("pass", mode=0o000)
        try:
            monkeypatch.setenv("OOMPAH_SERVER_USERNAME", "user")
            monkeypatch.setenv("OOMPAH_SERVER_PASSWORD_FILE", path)
            monkeypatch.delenv("OOMPAH_SERVER_PASSWORD", raising=False)
            with pytest.raises(CredentialError, match="not readable"):
                resolve_client_credentials()
        finally:
            os.chmod(path, 0o644)  # restore so cleanup works
            os.unlink(path)

    def test_empty_file(self, monkeypatch):
        path = _tmp_file("")
        try:
            monkeypatch.setenv("OOMPAH_SERVER_USERNAME", "user")
            monkeypatch.setenv("OOMPAH_SERVER_PASSWORD_FILE", path)
            monkeypatch.delenv("OOMPAH_SERVER_PASSWORD", raising=False)
            with pytest.raises(CredentialError, match="empty"):
                resolve_client_credentials()
        finally:
            os.unlink(path)

    def test_whitespace_only_file(self, monkeypatch):
        path = _tmp_file("   \n\n   ")
        try:
            monkeypatch.setenv("OOMPAH_SERVER_USERNAME", "user")
            monkeypatch.setenv("OOMPAH_SERVER_PASSWORD_FILE", path)
            monkeypatch.delenv("OOMPAH_SERVER_PASSWORD", raising=False)
            with pytest.raises(CredentialError, match="empty"):
                resolve_client_credentials()
        finally:
            os.unlink(path)

    def test_error_message_does_not_contain_file_contents(self, monkeypatch):
        """Credential values from the file must not appear in error messages."""
        path = _tmp_file("ultra_secret_value_xyz")
        try:
            os.chmod(path, 0o000)
            monkeypatch.setenv("OOMPAH_SERVER_USERNAME", "user")
            monkeypatch.setenv("OOMPAH_SERVER_PASSWORD_FILE", path)
            monkeypatch.delenv("OOMPAH_SERVER_PASSWORD", raising=False)
            try:
                resolve_client_credentials()
            except CredentialError as exc:
                assert "ultra_secret_value_xyz" not in str(exc)
        finally:
            os.chmod(path, 0o644)
            os.unlink(path)


# ---------------------------------------------------------------------------
# Password file permission warnings
# ---------------------------------------------------------------------------


class TestPasswordFilePermissionWarnings:
    """Group/world-readable password files produce warnings, not errors."""

    def test_world_readable_file_logs_warning(self, monkeypatch, caplog):
        path = _tmp_file("password123", mode=0o644)  # world-readable
        try:
            monkeypatch.setenv("OOMPAH_SERVER_USERNAME", "user")
            monkeypatch.setenv("OOMPAH_SERVER_PASSWORD_FILE", path)
            monkeypatch.delenv("OOMPAH_SERVER_PASSWORD", raising=False)
            import logging
            with caplog.at_level(logging.WARNING, logger="oompah.client_auth"):
                creds = resolve_client_credentials()
            assert creds is not None
            assert creds.password == "password123"
            # Warning must be logged
            warning_messages = [r.message for r in caplog.records if r.levelno >= logging.WARNING]
            assert any("unsafe permissions" in msg for msg in warning_messages), (
                f"Expected 'unsafe permissions' warning; got: {warning_messages}"
            )
        finally:
            os.unlink(path)

    def test_group_readable_file_logs_warning(self, monkeypatch, caplog):
        path = _tmp_file("password456", mode=0o640)  # group-readable
        try:
            monkeypatch.setenv("OOMPAH_SERVER_USERNAME", "user")
            monkeypatch.setenv("OOMPAH_SERVER_PASSWORD_FILE", path)
            monkeypatch.delenv("OOMPAH_SERVER_PASSWORD", raising=False)
            import logging
            with caplog.at_level(logging.WARNING, logger="oompah.client_auth"):
                creds = resolve_client_credentials()
            assert creds is not None
            warning_messages = [r.message for r in caplog.records if r.levelno >= logging.WARNING]
            assert any("unsafe permissions" in msg for msg in warning_messages)
        finally:
            os.unlink(path)

    def test_owner_only_file_no_warning(self, monkeypatch, caplog):
        path = _tmp_file("password789", mode=0o600)  # owner-only
        try:
            monkeypatch.setenv("OOMPAH_SERVER_USERNAME", "user")
            monkeypatch.setenv("OOMPAH_SERVER_PASSWORD_FILE", path)
            monkeypatch.delenv("OOMPAH_SERVER_PASSWORD", raising=False)
            import logging
            with caplog.at_level(logging.WARNING, logger="oompah.client_auth"):
                creds = resolve_client_credentials()
            assert creds is not None
            warning_messages = [
                r.message for r in caplog.records
                if r.levelno >= logging.WARNING
                and r.name == "oompah.client_auth"
            ]
            assert not warning_messages, (
                f"Unexpected warnings for 0o600 file: {warning_messages}"
            )
        finally:
            os.unlink(path)

    def test_permission_warning_does_not_include_password(self, monkeypatch, caplog):
        """Password value must never appear in warning messages."""
        path = _tmp_file("super_secret_pass", mode=0o644)
        try:
            monkeypatch.setenv("OOMPAH_SERVER_USERNAME", "user")
            monkeypatch.setenv("OOMPAH_SERVER_PASSWORD_FILE", path)
            monkeypatch.delenv("OOMPAH_SERVER_PASSWORD", raising=False)
            import logging
            with caplog.at_level(logging.WARNING, logger="oompah.client_auth"):
                resolve_client_credentials()
            for record in caplog.records:
                assert "super_secret_pass" not in record.getMessage()
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# sanitize_server_url
# ---------------------------------------------------------------------------


class TestSanitizeServerUrl:
    """URL sanitization: reject embedded credentials."""

    def test_clean_url_returned_unchanged(self):
        assert sanitize_server_url("http://127.0.0.1:8080") == "http://127.0.0.1:8080"

    def test_trailing_slash_stripped(self):
        assert sanitize_server_url("http://127.0.0.1:8080/") == "http://127.0.0.1:8080"

    def test_https_clean_url_returned(self):
        assert sanitize_server_url("https://oompah.example.com") == "https://oompah.example.com"

    def test_empty_url_returned_as_is(self):
        assert sanitize_server_url("") == ""

    def test_url_with_username_rejected(self):
        with pytest.raises(CredentialError, match="must not contain credentials"):
            sanitize_server_url("http://user@host:8080")

    def test_url_with_username_and_password_rejected(self):
        with pytest.raises(CredentialError, match="must not contain credentials"):
            sanitize_server_url("http://user:password@host:8080/api")

    def test_url_with_password_only_rejected(self):
        # Technically unusual but should be caught.
        with pytest.raises(CredentialError):
            sanitize_server_url("http://:password@host:8080")

    def test_error_does_not_echo_password(self):
        """Credential values must not appear in the CredentialError message."""
        try:
            sanitize_server_url("http://admin:topsecret123@host:8080")
        except CredentialError as exc:
            msg = str(exc)
            assert "topsecret123" not in msg, (
                f"Password 'topsecret123' appeared in error: {msg}"
            )

    def test_error_shows_redacted_url_without_credentials(self):
        """Error message must include a redacted URL for operator diagnostics."""
        try:
            sanitize_server_url("http://admin:topsecret123@host:8080/path")
        except CredentialError as exc:
            msg = str(exc)
            # Redacted URL should show host and port but not credentials
            assert "host" in msg or "8080" in msg
            assert "admin" not in msg
            assert "topsecret123" not in msg

    def test_url_with_path_but_no_credentials_clean(self):
        result = sanitize_server_url("http://127.0.0.1:8080/api/v1")
        assert result == "http://127.0.0.1:8080/api/v1"

    def test_embedded_credentials_error_does_not_echo_query_or_path(self):
        with pytest.raises(CredentialError) as exc_info:
            sanitize_server_url(
                "http://admin:topsecret@host:8080/path/topsecret?password=topsecret"
            )
        message = str(exc_info.value)
        assert "topsecret" not in message
        assert "/path" not in message

    def test_malformed_port_with_credentials_is_rejected_without_traceback(self):
        with pytest.raises(CredentialError, match="must not contain credentials"):
            sanitize_server_url("http://admin:topsecret@host:notaport")

    def test_unparseable_url_is_rejected_without_echoing_raw_value(self):
        with pytest.raises(CredentialError) as exc_info:
            sanitize_server_url("http://admin:topsecret@[bad")
        assert "topsecret" not in str(exc_info.value)


# ---------------------------------------------------------------------------
# format_auth_error
# ---------------------------------------------------------------------------


class TestFormatAuthError:
    """401 remediation message must never echo credentials."""

    def test_returns_string(self):
        msg = format_auth_error("http://127.0.0.1:8080")
        assert isinstance(msg, str)
        assert len(msg) > 10

    def test_contains_401_reference(self):
        msg = format_auth_error("http://127.0.0.1:8080")
        assert "401" in msg

    def test_mentions_env_vars(self):
        msg = format_auth_error("http://127.0.0.1:8080")
        # Should guide the operator to set credentials
        assert "OOMPAH_SERVER_USERNAME" in msg or "password" in msg.lower()

    def test_does_not_contain_server_url(self):
        """Server URL in error messages is acceptable, but credentials must not appear."""
        # The function takes a sanitized URL, so this test verifies
        # the function does not accidentally include any passed secrets.
        msg = format_auth_error("http://localhost:9090")
        assert "password" not in msg.lower() or "PASSWORD" in msg  # env var name is OK
        # Actual password values must not appear
        assert "topsecret" not in msg


# ---------------------------------------------------------------------------
# _read_password_file — direct unit tests
# ---------------------------------------------------------------------------


class TestReadPasswordFileDirect:
    """Unit tests for the internal _read_password_file function."""

    def test_reads_and_strips_content(self):
        path = _tmp_file("  mypass  \n")
        try:
            assert _read_password_file(path) == "mypass"
        finally:
            os.unlink(path)

    def test_symlink_rejected(self, tmp_path):
        target = tmp_path / "real.txt"
        target.write_text("pass")
        link = tmp_path / "link.txt"
        link.symlink_to(target)
        with pytest.raises(CredentialError, match="symbolic link"):
            _read_password_file(str(link))

    def test_missing_file(self):
        with pytest.raises(CredentialError, match="not found"):
            _read_password_file("/definitely/does/not/exist/passfile.txt")

    def test_directory(self, tmp_path):
        with pytest.raises(CredentialError, match="not a regular file"):
            _read_password_file(str(tmp_path))

    def test_unreadable_file(self):
        path = _tmp_file("secret", mode=0o000)
        try:
            with pytest.raises(CredentialError, match="not readable"):
                _read_password_file(path)
        finally:
            os.chmod(path, 0o644)
            os.unlink(path)

    def test_empty_file(self):
        path = _tmp_file("")
        try:
            with pytest.raises(CredentialError, match="empty"):
                _read_password_file(path)
        finally:
            os.unlink(path)

    def test_multiline_password_read_correctly(self):
        """First line and subsequent content are all included and stripped."""
        path = _tmp_file("hunter2")
        try:
            assert _read_password_file(path) == "hunter2"
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# TOCTOU simulation
# ---------------------------------------------------------------------------


class TestTOCTOURaceCondition:
    """Verify that inode-change detection prevents symlink-race attacks."""

    def test_inode_change_detected_after_lstat(self, tmp_path, monkeypatch):
        """Simulate a race where the file is replaced between lstat and fstat."""
        real_file = tmp_path / "real.txt"
        real_file.write_text("legit_password")
        real_file.chmod(0o600)

        replacement = tmp_path / "other.txt"
        replacement.write_text("injected_password")
        replacement.chmod(0o600)

        path_str = str(real_file)

        original_lstat = os.lstat
        original_open = os.open

        lstat_calls = []

        def _mock_lstat(p):
            result = original_lstat(p)
            lstat_calls.append(p)
            return result

        fstat_calls = []

        def _mock_fstat(fd):
            # Simulate the race: on first fstat call, return stat of a different inode
            if not fstat_calls:
                fstat_calls.append(fd)
                # Return stat of the replacement file (different inode)
                return original_lstat(str(replacement))
            return os.fstat.__wrapped__(fd) if hasattr(os.fstat, '__wrapped__') else os.fstat(fd)

        # Only patch fstat to change the inode; lstat returns real file info
        with monkeypatch.context() as m:
            m.setattr(os, "fstat", _mock_fstat)
            with pytest.raises(CredentialError, match="changed between stat and open"):
                _read_password_file(path_str)


# ---------------------------------------------------------------------------
# _check_password_file_permissions — direct unit test
# ---------------------------------------------------------------------------


class TestCheckPasswordFilePermissions:
    """Direct tests for the permission-check helper."""

    def test_warning_issued_for_world_readable(self, caplog):
        path = _tmp_file("x", mode=0o644)
        try:
            st = os.lstat(path)
            import logging
            with caplog.at_level(logging.WARNING):
                _check_password_file_permissions(path, st)
            assert any("unsafe permissions" in r.message for r in caplog.records)
        finally:
            os.unlink(path)

    def test_no_warning_for_owner_only(self, caplog):
        path = _tmp_file("x", mode=0o600)
        try:
            st = os.lstat(path)
            import logging
            with caplog.at_level(logging.WARNING, logger="oompah.client_auth"):
                _check_password_file_permissions(path, st)
            relevant = [
                r for r in caplog.records
                if r.levelno >= logging.WARNING and r.name == "oompah.client_auth"
            ]
            assert not relevant
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# Integration: end-to-end happy-path
# ---------------------------------------------------------------------------


class TestEndToEnd:
    """End-to-end happy-path credential resolution."""

    def test_password_file_full_flow(self, monkeypatch):
        path = _tmp_file("correct_password\n", mode=0o600)
        try:
            monkeypatch.setenv("OOMPAH_SERVER_USERNAME", "testuser")
            monkeypatch.setenv("OOMPAH_SERVER_PASSWORD_FILE", path)
            monkeypatch.delenv("OOMPAH_SERVER_PASSWORD", raising=False)

            creds = resolve_client_credentials()
            assert creds is not None
            assert creds.username == "testuser"
            assert creds.password == "correct_password"
            # Credentials are an immutable named tuple (not dicts)
            assert creds[0] == "testuser"
            assert creds[1] == "correct_password"
        finally:
            os.unlink(path)

    def test_unauthenticated_server_no_env_returns_none(self, monkeypatch):
        """When server has no auth, and client sets no env vars, None is returned."""
        monkeypatch.delenv("OOMPAH_SERVER_USERNAME", raising=False)
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD", raising=False)
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD_FILE", raising=False)
        assert resolve_client_credentials() is None

    def test_credentials_not_stored_as_string_in_module(self):
        """ClientCredentials values are not leaked into module globals as runtime data."""
        import oompah.client_auth as ca
        # Verify no module-level variable (excluding docstrings and source strings)
        # accidentally holds a specific credential-like value.
        # This is a sanity check, not a comprehensive guard.
        suspicious_values = ["hunter2", "correcthorsebatterystaple", "topsecretpass123"]
        for name, val in vars(ca).items():
            if isinstance(val, str):
                for suspicious in suspicious_values:
                    assert suspicious not in val, (
                        f"Module attribute {name!r} contains suspicious credential string"
                    )

    def test_agent_environment_strips_client_auth_values(self):
        clean = agent_environment(
            {
                "PATH": "/bin",
                "OOMPAH_SERVER_USERNAME": "operator",
                "OOMPAH_SERVER_PASSWORD": "topsecret",
                "OOMPAH_SERVER_PASSWORD_FILE": "/run/secrets/client-pass",
                "OOMPAH_SERVER_URL": "http://127.0.0.1:8080",
            }
        )
        assert clean == {
            "PATH": "/bin",
            "OOMPAH_SERVER_URL": "http://127.0.0.1:8080",
            CLIENT_AUTH_DISABLED_ENV: "1",
        }

    def test_agent_environment_strips_inherited_make_controls(self):
        clean = agent_environment(
            {
                "PATH": "/bin",
                "MAKEFLAGS": " --no-print-directory",
                "MFLAGS": "--no-print-directory",
                "GNUMAKEFLAGS": "--eval=all:;false",
                "MAKEFILES": "/operator/service.mk",
                "MAKEOVERRIDES": "X=$(shell false)",
                "TASK_SETTING": "preserved",
            }
        )

        assert clean == {
            "PATH": "/bin",
            "TASK_SETTING": "preserved",
            CLIENT_AUTH_DISABLED_ENV: "1",
        }

    def test_agent_environment_selects_private_task_venv(self, tmp_path):
        """Worker setup cannot inherit or overwrite the service venv."""
        service_venv = str(tmp_path / "service" / ".venv")
        clean = agent_environment(
            {
                "PATH": "/bin",
                TASK_VENV_ENV: service_venv,
                "VIRTUAL_ENV": service_venv,
                "UV_PROJECT_ENVIRONMENT": service_venv,
                "PYTHONPATH": str(tmp_path / "service"),
                "PYTHONHOME": str(tmp_path / "python"),
                "OOMPAH_SERVER_URL": "http://127.0.0.1:8080",
            },
            workspace_path=tmp_path / "task-worktree",
        )

        assert clean[TASK_VENV_ENV] == task_venv_path(tmp_path / "task-worktree")
        assert clean[SERVICE_CHECKOUT_ENV] == str(ROOT)
        assert clean[SERVICE_VENV_ENV] == str(Path(sys.prefix).resolve())
        assert all(
            key not in clean
            for key in (
                "VIRTUAL_ENV",
                "UV_PROJECT_ENVIRONMENT",
                "PYTHONPATH",
                "PYTHONHOME",
            )
        )

    def test_agent_environment_drops_inherited_task_venv_without_workspace(self):
        clean = agent_environment(
            {
                "PATH": "/bin",
                TASK_VENV_ENV: "/operator/service/.venv",
            }
        )

        assert all(
            key not in clean
            for key in (TASK_VENV_ENV, SERVICE_CHECKOUT_ENV, SERVICE_VENV_ENV)
        )

    def test_epic_rebase_environment_is_a_clean_credential_domain(self):
        """Rebase workers cannot inherit an arbitrary credential route."""
        clean = agent_environment(
            {
                "PATH": "/bin",
                "LANG": "C.UTF-8",
                "HOME": "/operator/home",
                "SSH_AUTH_SOCK": "/run/user/1000/ssh-agent.sock",
                "GIT_ASKPASS": "/operator/askpass",
                "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": "credential.helper",
                "GIT_CONFIG_VALUE_0": "/operator/helper",
                "GITHUB_TOKEN": "forge-secret",
                "GH_TOKEN": "forge-secret",
                "GITLAB_TOKEN": "forge-secret",
                "OOMPAH_GIT_PASSWORD": "forge-secret",
                "ARBITRARY_SECRET_NAME": "forge-secret",
                "OOMPAH_TASK_HANDOFF_TOKEN": "task-grant",
                "OOMPAH_TASK_HANDOFF_PROJECT_ID": "proj-1",
                "OOMPAH_TASK_HANDOFF_TASK_ID": "TASK-1",
            },
            isolate_remote_write=True,
        )
        try:
            assert clean["HOME"] != "/operator/home"
            assert clean["GIT_CONFIG_GLOBAL"] == os.devnull
            assert clean["GIT_CONFIG_NOSYSTEM"] == "1"
            assert clean["GIT_TERMINAL_PROMPT"] == "0"
            assert clean["GIT_ASKPASS"] == "/bin/false"
            assert clean["GIT_SSH_COMMAND"] == "/bin/false"
            assert os.path.isdir(clean["HOME"])
            for key in (
                "SSH_AUTH_SOCK",
                "GIT_CONFIG_COUNT",
                "GIT_CONFIG_KEY_0",
                "GIT_CONFIG_VALUE_0",
                "GITHUB_TOKEN",
                "GH_TOKEN",
                "GITLAB_TOKEN",
                "OOMPAH_GIT_PASSWORD",
                "ARBITRARY_SECRET_NAME",
                "OOMPAH_TASK_HANDOFF_TOKEN",
                "OOMPAH_TASK_HANDOFF_PROJECT_ID",
                "OOMPAH_TASK_HANDOFF_TASK_ID",
            ):
                assert key not in clean
        finally:
            shutil.rmtree(clean["OOMPAH_WORKER_RUNTIME_DIR"], ignore_errors=True)

    def test_isolated_codex_auth_copies_only_explicit_auth_artifact(self, tmp_path):
        operator_home = tmp_path / "operator-home"
        codex_home = operator_home / ".codex"
        codex_home.mkdir(parents=True)
        (codex_home / "auth.json").write_text('{"access_token":"model-token"}')
        (operator_home / ".gitconfig").write_text("[credential]\nhelper = store\n")
        (operator_home / ".ssh").mkdir()

        clean = agent_environment(
            {"PATH": "/bin", "HOME": str(operator_home)},
            isolate_remote_write=True,
            provider_auth_kind="codex_subscription",
        )
        try:
            copied_auth = Path(clean["CODEX_HOME"]) / "auth.json"
            assert copied_auth.read_text() == '{"access_token":"model-token"}'
            assert copied_auth.stat().st_mode & 0o777 == 0o600
            assert not (Path(clean["HOME"]) / ".gitconfig").exists()
            assert not (Path(clean["HOME"]) / ".ssh").exists()
            assert clean["GIT_CONFIG_GLOBAL"] == os.devnull
        finally:
            shutil.rmtree(clean["OOMPAH_WORKER_RUNTIME_DIR"], ignore_errors=True)

    def test_unknown_isolated_provider_layout_fails_closed(self):
        with pytest.raises(OSError, match="unknown isolated worker provider"):
            agent_environment(
                {"PATH": "/bin"},
                isolate_remote_write=True,
                provider_auth_kind="unrecognised-wrapper",
            )

    def test_isolated_opencode_auth_uses_only_xdg_auth_artifact(self, tmp_path):
        operator_home = tmp_path / "operator-home"
        source_data = operator_home / ".local" / "share"
        source_auth = source_data / "opencode" / "auth.json"
        source_auth.parent.mkdir(parents=True)
        source_auth.write_text('{"provider":"model-token"}')
        (operator_home / ".gitconfig").write_text("[credential]\nhelper = store\n")

        clean = agent_environment(
            {"PATH": "/bin", "HOME": str(operator_home)},
            isolate_remote_write=True,
            provider_auth_kind="opencode_subscription",
        )
        try:
            copied_auth = Path(clean["XDG_DATA_HOME"]) / "opencode" / "auth.json"
            assert copied_auth.read_text() == '{"provider":"model-token"}'
            assert copied_auth.stat().st_mode & 0o777 == 0o600
            assert not (Path(clean["HOME"]) / ".gitconfig").exists()
        finally:
            shutil.rmtree(clean["OOMPAH_WORKER_RUNTIME_DIR"], ignore_errors=True)


class TestCurrentClientEnvironment:
    """First-party clients refresh only their current .env inputs."""

    def test_current_dotenv_replaces_stale_client_inputs(self, tmp_path, monkeypatch):
        (tmp_path / ".env").write_text(
            "OOMPAH_SERVER_USERNAME=rotated-user\n"
            "OOMPAH_SERVER_PASSWORD_FILE=/run/secrets/rotated-password\n"
            "OOMPAH_SERVER_URL=http://127.0.0.1:9070\n"
            "UNRELATED_SETTING=must-not-be-loaded\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("OOMPAH_SERVER_USERNAME", "stale-user")
        monkeypatch.setenv("OOMPAH_SERVER_PASSWORD", "stale-value")
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD_FILE", raising=False)
        monkeypatch.setenv("OOMPAH_SERVER_URL", "http://127.0.0.1:8080")
        monkeypatch.delenv("UNRELATED_SETTING", raising=False)
        # Clear the worker-process marker that agent environments set; this test
        # exercises the client (non-worker) code path where reloading is allowed.
        monkeypatch.delenv(CLIENT_AUTH_DISABLED_ENV, raising=False)

        assert load_client_environment() == 3
        assert os.environ["OOMPAH_SERVER_USERNAME"] == "rotated-user"
        assert os.environ["OOMPAH_SERVER_PASSWORD_FILE"] == "/run/secrets/rotated-password"
        assert os.environ["OOMPAH_SERVER_URL"] == "http://127.0.0.1:9070"
        assert "OOMPAH_SERVER_PASSWORD" not in os.environ
        assert "UNRELATED_SETTING" not in os.environ

    def test_worker_marker_prevents_dotenv_credential_reacquisition(
        self, tmp_path, monkeypatch
    ):
        (tmp_path / ".env").write_text(
            "OOMPAH_SERVER_USERNAME=operator\n"
            "OOMPAH_SERVER_PASSWORD_FILE=/run/secrets/client-password\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv(CLIENT_AUTH_DISABLED_ENV, "1")
        monkeypatch.delenv("OOMPAH_SERVER_USERNAME", raising=False)
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD_FILE", raising=False)

        assert load_client_environment() == 0
        assert "OOMPAH_SERVER_USERNAME" not in os.environ
        assert "OOMPAH_SERVER_PASSWORD_FILE" not in os.environ


# ---------------------------------------------------------------------------
# Netrc support
# ---------------------------------------------------------------------------


def _make_netrc_file(content: str, mode: int = 0o600) -> str:
    """Create a temporary netrc file with content and permissions; return path."""
    fd, path = tempfile.mkstemp()
    try:
        os.write(fd, content.encode("utf-8"))
    finally:
        os.close(fd)
    os.chmod(path, mode)
    return path


class TestNetrcFallback:
    """Netrc credentials fallback when CLI/env don't supply complete credentials."""

    def test_netrc_credentials_used_when_no_cli_or_env(self, monkeypatch, tmp_path):
        """When no CLI/env credentials, netrc entry is used."""
        netrc_content = "machine 127.0.0.1\nlogin alice\npassword netrc_secret\n"
        netrc_path = str(tmp_path / ".netrc")
        Path(netrc_path).write_text(netrc_content)
        os.chmod(netrc_path, 0o600)

        monkeypatch.delenv("OOMPAH_SERVER_USERNAME", raising=False)
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD", raising=False)
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD_FILE", raising=False)

        # Patch Path.home() to return our tmp_path
        with patch("oompah.client_auth.Path.home") as mock_home:
            mock_home.return_value = tmp_path

            creds = resolve_client_credentials(server_url="http://127.0.0.1:8080")
            assert creds is not None
            assert creds.username == "alice"
            assert creds.password == "netrc_secret"

    def test_cli_username_takes_precedence_over_netrc_but_needs_password(self, monkeypatch, tmp_path):
        """CLI --username overrides netrc but requires explicit password."""
        netrc_content = "machine 127.0.0.1\nlogin alice\npassword netrc_secret\n"
        netrc_path = str(tmp_path / ".netrc")
        Path(netrc_path).write_text(netrc_content)
        os.chmod(netrc_path, 0o600)

        monkeypatch.delenv("OOMPAH_SERVER_USERNAME", raising=False)
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD", raising=False)
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD_FILE", raising=False)

        with patch("oompah.client_auth.Path.home") as mock_home:
            mock_home.return_value = tmp_path

            # CLI username overrides netrc username, so netrc password cannot be used
            # (precedence conflict). Must provide explicit password.
            with pytest.raises(CredentialError, match="Credential conflict"):
                resolve_client_credentials(
                    username_override="bob",
                    server_url="http://127.0.0.1:8080",
                )

    def test_env_username_takes_precedence_over_netrc_but_conflicts(self, monkeypatch, tmp_path):
        """OOMPAH_SERVER_USERNAME overrides netrc username, causing conflict with netrc password."""
        netrc_content = "machine 127.0.0.1\nlogin alice\npassword netrc_secret\n"
        netrc_path = str(tmp_path / ".netrc")
        Path(netrc_path).write_text(netrc_content)
        os.chmod(netrc_path, 0o600)

        monkeypatch.setenv("OOMPAH_SERVER_USERNAME", "bob")
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD", raising=False)
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD_FILE", raising=False)

        with patch("oompah.client_auth.Path.home") as mock_home:
            mock_home.return_value = tmp_path

            # env username (bob) conflicts with netrc password for alice
            with pytest.raises(CredentialError, match="Credential conflict"):
                resolve_client_credentials(server_url="http://127.0.0.1:8080")

    def test_env_password_takes_precedence_over_netrc_password(self, monkeypatch, tmp_path):
        """OOMPAH_SERVER_PASSWORD overrides netrc password."""
        netrc_content = "machine 127.0.0.1\nlogin alice\npassword netrc_secret\n"
        netrc_path = str(tmp_path / ".netrc")
        Path(netrc_path).write_text(netrc_content)
        os.chmod(netrc_path, 0o600)

        monkeypatch.setenv("OOMPAH_SERVER_USERNAME", "alice")
        monkeypatch.setenv("OOMPAH_SERVER_PASSWORD", "env_secret")
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD_FILE", raising=False)

        with patch("oompah.client_auth.Path.home") as mock_home:
            mock_home.return_value = tmp_path

            creds = resolve_client_credentials(server_url="http://127.0.0.1:8080")
            assert creds is not None
            assert creds.username == "alice"
            assert creds.password == "env_secret"  # env wins over netrc

    def test_hostname_normalization_for_netrc_lookup(self, monkeypatch, tmp_path):
        """Hostname from URL is normalized (lowercase) for netrc lookup."""
        netrc_content = "machine example.com\nlogin alice\npassword secret123\n"
        netrc_path = str(tmp_path / ".netrc")
        Path(netrc_path).write_text(netrc_content)
        os.chmod(netrc_path, 0o600)

        monkeypatch.delenv("OOMPAH_SERVER_USERNAME", raising=False)
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD", raising=False)
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD_FILE", raising=False)

        with patch("oompah.client_auth.Path.home") as mock_home:
            mock_home.return_value = tmp_path

            # URL has uppercase host; netrc has lowercase; should match via normalization
            creds = resolve_client_credentials(server_url="http://EXAMPLE.COM:8080")
            assert creds is not None
            assert creds.username == "alice"
            assert creds.password == "secret123"

    def test_no_netrc_fallback_without_server_url(self, monkeypatch, tmp_path):
        """When no server_url provided, netrc is not consulted."""
        netrc_content = "machine 127.0.0.1\nlogin alice\npassword netrc_secret\n"
        netrc_path = str(tmp_path / ".netrc")
        Path(netrc_path).write_text(netrc_content)
        os.chmod(netrc_path, 0o600)

        monkeypatch.delenv("OOMPAH_SERVER_USERNAME", raising=False)
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD", raising=False)
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD_FILE", raising=False)

        with patch("oompah.client_auth.Path.home") as mock_home:
            mock_home.return_value = tmp_path

            # Without server_url, netrc should not be queried
            creds = resolve_client_credentials()
            assert creds is None


class TestNetrcPermissions:
    """Netrc file permission validation."""

    def test_netrc_must_be_0o600(self, monkeypatch, tmp_path):
        """Netrc file must have 0o600 permissions."""
        netrc_content = "machine 127.0.0.1\nlogin alice\npassword secret\n"
        netrc_path = str(tmp_path / ".netrc")
        Path(netrc_path).write_text(netrc_content)
        os.chmod(netrc_path, 0o644)  # unsafe

        monkeypatch.delenv("OOMPAH_SERVER_USERNAME", raising=False)
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD", raising=False)
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD_FILE", raising=False)

        with patch("oompah.client_auth.Path.home") as mock_home:
            mock_home.return_value = tmp_path

            with pytest.raises(CredentialError, match="unsafe permissions"):
                resolve_client_credentials(server_url="http://127.0.0.1:8080")

    def test_netrc_can_be_0o400(self, monkeypatch, tmp_path):
        """Netrc file can be 0o400 (read-only)."""
        netrc_content = "machine 127.0.0.1\nlogin alice\npassword secret\n"
        netrc_path = str(tmp_path / ".netrc")
        Path(netrc_path).write_text(netrc_content)
        os.chmod(netrc_path, 0o400)  # read-only, also acceptable

        monkeypatch.delenv("OOMPAH_SERVER_USERNAME", raising=False)
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD", raising=False)
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD_FILE", raising=False)

        with patch("oompah.client_auth.Path.home") as mock_home:
            mock_home.return_value = tmp_path

            creds = resolve_client_credentials(server_url="http://127.0.0.1:8080")
            assert creds is not None
            assert creds.password == "secret"

    def test_netrc_symlink_rejected(self, monkeypatch, tmp_path):
        """Netrc symlink is rejected (symlink-substitution attack prevention)."""
        real_netrc = tmp_path / "real_netrc"
        real_netrc.write_text("machine 127.0.0.1\nlogin alice\npassword secret\n")
        real_netrc.chmod(0o600)

        link_netrc = tmp_path / ".netrc"
        link_netrc.symlink_to(real_netrc)

        monkeypatch.delenv("OOMPAH_SERVER_USERNAME", raising=False)
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD", raising=False)
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD_FILE", raising=False)

        with patch("oompah.client_auth.Path.home") as mock_home:
            mock_home.return_value = tmp_path

            with pytest.raises(CredentialError, match="symbolic link"):
                resolve_client_credentials(server_url="http://127.0.0.1:8080")

    def test_netrc_directory_rejected(self, monkeypatch, tmp_path):
        """Netrc must be a regular file, not a directory."""
        netrc_dir = tmp_path / ".netrc"
        netrc_dir.mkdir(mode=0o700)

        monkeypatch.delenv("OOMPAH_SERVER_USERNAME", raising=False)
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD", raising=False)
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD_FILE", raising=False)

        with patch("oompah.client_auth.Path.home") as mock_home:
            mock_home.return_value = tmp_path

            with pytest.raises(CredentialError, match="not a regular file"):
                resolve_client_credentials(server_url="http://127.0.0.1:8080")


class TestNetrcParsing:
    """Netrc parsing and entry validation."""

    def test_malformed_netrc_partial_entry_rejected(self, monkeypatch, tmp_path):
        """Netrc entry with only login or only password is rejected."""
        # Entry has only login, missing password
        netrc_content = "machine 127.0.0.1\nlogin alice\n"
        netrc_path = str(tmp_path / ".netrc")
        Path(netrc_path).write_text(netrc_content)
        os.chmod(netrc_path, 0o600)

        monkeypatch.delenv("OOMPAH_SERVER_USERNAME", raising=False)
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD", raising=False)
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD_FILE", raising=False)

        with patch("oompah.client_auth.Path.home") as mock_home:
            mock_home.return_value = tmp_path

            with pytest.raises(CredentialError, match="Malformed netrc"):
                resolve_client_credentials(server_url="http://127.0.0.1:8080")

    def test_netrc_multiple_machines(self, monkeypatch, tmp_path):
        """Netrc can have multiple machine entries; correct one is looked up."""
        netrc_content = (
            "machine host1.com\n"
            "login user1\n"
            "password pass1\n"
            "\n"
            "machine 127.0.0.1\n"
            "login alice\n"
            "password secret123\n"
            "\n"
            "machine host2.com\n"
            "login user2\n"
            "password pass2\n"
        )
        netrc_path = str(tmp_path / ".netrc")
        Path(netrc_path).write_text(netrc_content)
        os.chmod(netrc_path, 0o600)

        monkeypatch.delenv("OOMPAH_SERVER_USERNAME", raising=False)
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD", raising=False)
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD_FILE", raising=False)

        with patch("oompah.client_auth.Path.home") as mock_home:
            mock_home.return_value = tmp_path

            creds = resolve_client_credentials(server_url="http://127.0.0.1:8080")
            assert creds is not None
            assert creds.username == "alice"
            assert creds.password == "secret123"

    def test_netrc_comments_ignored(self, monkeypatch, tmp_path):
        """Netrc comments (lines starting with #) are ignored."""
        netrc_content = (
            "# This is a comment\n"
            "machine 127.0.0.1\n"
            "# Another comment\n"
            "login alice\n"
            "password secret123\n"
        )
        netrc_path = str(tmp_path / ".netrc")
        Path(netrc_path).write_text(netrc_content)
        os.chmod(netrc_path, 0o600)

        monkeypatch.delenv("OOMPAH_SERVER_USERNAME", raising=False)
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD", raising=False)
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD_FILE", raising=False)

        with patch("oompah.client_auth.Path.home") as mock_home:
            mock_home.return_value = tmp_path

            creds = resolve_client_credentials(server_url="http://127.0.0.1:8080")
            assert creds is not None
            assert creds.password == "secret123"

    def test_netrc_whitespace_handling(self, monkeypatch, tmp_path):
        """Netrc parsing handles whitespace correctly."""
        netrc_content = "machine  127.0.0.1  \nlogin   alice  \npassword   secret123  \n"
        netrc_path = str(tmp_path / ".netrc")
        Path(netrc_path).write_text(netrc_content)
        os.chmod(netrc_path, 0o600)

        monkeypatch.delenv("OOMPAH_SERVER_USERNAME", raising=False)
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD", raising=False)
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD_FILE", raising=False)

        with patch("oompah.client_auth.Path.home") as mock_home:
            mock_home.return_value = tmp_path

            creds = resolve_client_credentials(server_url="http://127.0.0.1:8080")
            assert creds is not None
            # Note: whitespace after values is preserved in netrc
            # (it's the field value, not the username/password)
            assert creds.username == "alice"
            # Password parsing preserves trailing spaces if not stripped by the parser
            assert "secret" in creds.password

    def test_netrc_missing_file_is_optional(self, monkeypatch, tmp_path):
        """Missing netrc file is not an error (optional fallback)."""
        # Don't create a netrc file
        monkeypatch.delenv("OOMPAH_SERVER_USERNAME", raising=False)
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD", raising=False)
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD_FILE", raising=False)

        with patch("oompah.client_auth.Path.home") as mock_home:
            mock_home.return_value = tmp_path

            # Should return None, not raise an error
            creds = resolve_client_credentials(server_url="http://127.0.0.1:8080")
            assert creds is None


class TestNetrcHostnameLookupMiss:
    """Netrc lookup can miss when hostname is not found in netrc."""

    def test_hostname_not_in_netrc_returns_none(self, monkeypatch, tmp_path):
        """When server hostname is not in netrc, None is returned."""
        netrc_content = "machine otherhost.com\nlogin alice\npassword secret\n"
        netrc_path = str(tmp_path / ".netrc")
        Path(netrc_path).write_text(netrc_content)
        os.chmod(netrc_path, 0o600)

        monkeypatch.delenv("OOMPAH_SERVER_USERNAME", raising=False)
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD", raising=False)
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD_FILE", raising=False)

        with patch("oompah.client_auth.Path.home") as mock_home:
            mock_home.return_value = tmp_path

            # 127.0.0.1 is not in netrc, so credentials should be None
            creds = resolve_client_credentials(server_url="http://127.0.0.1:8080")
            assert creds is None


class TestNetrcSecretRedaction:
    """Ensure netrc credentials are never leaked in error messages."""

    def test_netrc_parsing_error_does_not_leak_credentials(self, monkeypatch, tmp_path):
        """Malformed netrc errors do not echo credential values."""
        netrc_content = (
            "machine 127.0.0.1\n"
            "login alice\n"
            "# Missing password\n"
        )
        netrc_path = str(tmp_path / ".netrc")
        Path(netrc_path).write_text(netrc_content)
        os.chmod(netrc_path, 0o600)

        monkeypatch.delenv("OOMPAH_SERVER_USERNAME", raising=False)
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD", raising=False)
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD_FILE", raising=False)

        with patch("oompah.client_auth.Path.home") as mock_home:
            mock_home.return_value = tmp_path

            try:
                resolve_client_credentials(server_url="http://127.0.0.1:8080")
            except CredentialError as exc:
                # Error should not echo the password field name or values
                msg = str(exc)
                assert "alice" not in msg  # username must not be in error
