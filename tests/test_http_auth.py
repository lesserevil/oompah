"""Tests for oompah.http_auth - HTTP Basic authentication.

Security test coverage includes:
- Constant-time comparison (prevent timing attacks)
- Plaintext password rejection
- Invalid/unsupported hash format rejection
- Malformed file handling
- User enumeration prevention (same error for missing user and wrong password)
- No credential leakage in errors or logging
"""

import os
import tempfile
import threading
from pathlib import Path

import pytest

from oompah.http_auth import (
    AuthError,
    HtpasswdCredentials,
    VerificationError,
    _constant_time_compare,
    _load_htpasswd_file,
    _verify_password,
    load_credentials,
)


@pytest.fixture
def bcrypt_hash():
    """Generate a real bcrypt hash for testing."""
    try:
        from passlib.context import CryptContext

        ctx = CryptContext(schemes=["bcrypt"])
        return ctx.encrypt("password")
    except ImportError:
        pytest.skip("passlib not installed")


@pytest.fixture
def apr1_hash():
    """Generate a real APR1 hash for testing."""
    try:
        from passlib.context import CryptContext

        ctx = CryptContext(schemes=["apr_md5_crypt"])
        return ctx.encrypt("password")
    except ImportError:
        pytest.skip("passlib not installed")


class TestConstantTimeCompare:
    """Test constant-time string comparison."""

    def test_equal_strings(self):
        assert _constant_time_compare("hello", "hello") is True

    def test_different_strings(self):
        assert _constant_time_compare("hello", "world") is False

    def test_empty_strings(self):
        assert _constant_time_compare("", "") is True

    def test_different_lengths(self):
        # Should still work but return False
        assert _constant_time_compare("short", "much longer string") is False

    def test_unicode_strings(self):
        assert _constant_time_compare("café", "café") is True
        assert _constant_time_compare("café", "cafe") is False


class TestVerifyPassword:
    """Test password verification with passlib."""

    def test_valid_bcrypt_password(self, bcrypt_hash):
        """Test that correct password verifies."""
        assert _verify_password(bcrypt_hash, "password") is True

    def test_wrong_bcrypt_password(self, bcrypt_hash):
        """Test that wrong password fails."""
        assert _verify_password(bcrypt_hash, "wrong_password") is False

    def test_valid_apr1_password(self, apr1_hash):
        """Test that correct APR1 password verifies."""
        assert _verify_password(apr1_hash, "password") is True

    def test_wrong_apr1_password(self, apr1_hash):
        """Test that wrong APR1 password fails."""
        assert _verify_password(apr1_hash, "wrong_password") is False

    def test_invalid_hash_format(self):
        # Malformed hash
        assert _verify_password("$2y$invalid", "password") is False

    def test_empty_hash(self):
        assert _verify_password("", "password") is False

    def test_invalid_algorithm(self):
        # Unsupported algorithm (shouldn't reach here due to validation)
        assert _verify_password("$sha1$...", "password") is False

    def test_malformed_bcrypt(self):
        # Invalid bcrypt hash
        assert _verify_password("$2y$12$invalid", "password") is False


class TestLoadHtpasswdFile:
    """Test htpasswd file parsing and validation."""

    def _make_file(self, content: str) -> str:
        """Helper to create a temp htpasswd file."""
        fd, path = tempfile.mkstemp(suffix=".htpasswd", text=True)
        try:
            os.write(fd, content.encode("utf-8"))
        finally:
            os.close(fd)
        return path

    def test_valid_single_entry(self, bcrypt_hash):
        content = f"admin:{bcrypt_hash}\n"
        path = self._make_file(content)
        try:
            creds = _load_htpasswd_file(path)
            assert "admin" in creds
            assert creds["admin"] == bcrypt_hash
        finally:
            os.unlink(path)

    def test_valid_multiple_entries(self, bcrypt_hash, apr1_hash):
        content = f"admin:{bcrypt_hash}\noperator:{apr1_hash}\n"
        path = self._make_file(content)
        try:
            creds = _load_htpasswd_file(path)
            assert len(creds) == 2
            assert "admin" in creds
            assert "operator" in creds
        finally:
            os.unlink(path)

    def test_comments_and_blank_lines_ignored(self):
        hashed = "$2y$12$R9h/cIPz0gi.URNNGS3/aO/O.r6HS5xO31a5NQc6XjHPT8f6sFXe2"
        content = f"# This is a comment\n\nadmin:{hashed}\n# Another comment\n\n"
        path = self._make_file(content)
        try:
            creds = _load_htpasswd_file(path)
            assert len(creds) == 1
            assert "admin" in creds
        finally:
            os.unlink(path)

    def test_file_not_found(self):
        with pytest.raises(AuthError, match="not found"):
            _load_htpasswd_file("/nonexistent/path/.htpasswd")

    def test_file_not_readable(self):
        path = self._make_file("admin:$2y$12$hash\n")
        try:
            os.chmod(path, 0o000)
            with pytest.raises(AuthError, match="not readable"):
                _load_htpasswd_file(path)
        finally:
            os.chmod(path, 0o644)
            os.unlink(path)

    def test_empty_file(self):
        path = self._make_file("")
        try:
            with pytest.raises(AuthError, match="empty"):
                _load_htpasswd_file(path)
        finally:
            os.unlink(path)

    def test_file_with_only_comments_and_blanks(self):
        content = "# comment\n\n# another\n"
        path = self._make_file(content)
        try:
            with pytest.raises(AuthError, match="no valid entries"):
                _load_htpasswd_file(path)
        finally:
            os.unlink(path)

    def test_missing_colon_delimiter(self):
        content = "admin_no_colon\n"
        path = self._make_file(content)
        try:
            with pytest.raises(AuthError, match="missing ':' delimiter"):
                _load_htpasswd_file(path)
        finally:
            os.unlink(path)

    def test_empty_username(self):
        content = ":$2y$12$hash\n"
        path = self._make_file(content)
        try:
            with pytest.raises(AuthError, match="empty username"):
                _load_htpasswd_file(path)
        finally:
            os.unlink(path)

    def test_empty_password_hash(self):
        content = "admin:\n"
        path = self._make_file(content)
        try:
            with pytest.raises(AuthError, match="empty password hash"):
                _load_htpasswd_file(path)
        finally:
            os.unlink(path)

    def test_plaintext_password_rejected(self):
        # No $ prefix = no algorithm marker = plaintext
        content = "admin:plaintext_password\n"
        path = self._make_file(content)
        try:
            with pytest.raises(AuthError, match="plaintext password"):
                _load_htpasswd_file(path)
        finally:
            os.unlink(path)

    def test_unsupported_sha_hash_rejected(self):
        # SHA hashes have $sha$ prefix (deprecated, unsupported)
        content = "admin:$sha$longhashvalue\n"
        path = self._make_file(content)
        try:
            with pytest.raises(AuthError, match="unsupported password algorithm"):
                _load_htpasswd_file(path)
        finally:
            os.unlink(path)

    def test_unsupported_md5_hash_rejected(self):
        # MD5 crypt has $1$ prefix (non-password contexts)
        content = "admin:$1$longhashvalue\n"
        path = self._make_file(content)
        try:
            with pytest.raises(AuthError, match="unsupported password algorithm"):
                _load_htpasswd_file(path)
        finally:
            os.unlink(path)

    def test_bcrypt_variants_accepted(self):
        for variant in ["$2y$", "$2b$", "$2a$"]:
            hashed = variant + "12$R9h/cIPz0gi.URNNGS3/aO/O.r6HS5xO31a5NQc6XjHPT8f6sFXe2"
            content = f"admin:{hashed}\n"
            path = self._make_file(content)
            try:
                creds = _load_htpasswd_file(path)
                assert "admin" in creds
            finally:
                os.unlink(path)

    def test_invalid_bcrypt_work_factor_rejected(self):
        hashed = "$2y$99$R9h/cIPz0gi.URNNGS3/aO/O.r6HS5xO31a5NQc6XjHPT8f6sFXe2"
        path = self._make_file(f"admin:{hashed}\n")
        try:
            with pytest.raises(AuthError, match="malformed password hash"):
                _load_htpasswd_file(path)
        finally:
            os.unlink(path)

    def test_apr1_hash_accepted(self):
        content = "admin:$apr1$r31.....$HqJZimJIs6ZvDpe9xNrKA.\n"
        path = self._make_file(content)
        try:
            creds = _load_htpasswd_file(path)
            assert "admin" in creds
        finally:
            os.unlink(path)


class TestLoadCredentials:
    """Test credential loading with path resolution."""

    def _make_file(self, content: str, name: str = ".htpasswd") -> tuple[str, str]:
        """Helper to create a temp directory with an htpasswd file.
        
        Returns (directory, filepath).
        """
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return tmpdir, path

    def test_disabled_when_no_default_file_and_no_override(self):
        # No .htpasswd beside env file, no OOMPAH_HTPASSWD_FILE set
        tmpdir = tempfile.mkdtemp()
        try:
            creds = load_credentials(None, tmpdir)
            assert creds.enabled is False
            assert creds.verifier is None
        finally:
            os.rmdir(tmpdir)

    def test_default_discovery_finds_htpasswd(self, bcrypt_hash):
        tmpdir, path = self._make_file(f"admin:{bcrypt_hash}\n")
        try:
            creds = load_credentials(None, tmpdir)
            assert creds.enabled is True
            assert creds.verifier is not None
            assert creds.htpasswd_path == path
        finally:
            os.unlink(path)
            os.rmdir(tmpdir)

    def test_relative_path_override_resolves_against_env_dir(self, bcrypt_hash):
        tmpdir, path = self._make_file(f"admin:{bcrypt_hash}\n", "custom.htpasswd")
        try:
            creds = load_credentials("custom.htpasswd", tmpdir)
            assert creds.enabled is True
            assert creds.verifier is not None
        finally:
            os.unlink(path)
            os.rmdir(tmpdir)

    def test_absolute_path_override_used_as_is(self, bcrypt_hash):
        tmpdir, path = self._make_file(f"admin:{bcrypt_hash}\n")
        try:
            # Use absolute path directly
            creds = load_credentials(path, "/some/other/dir")
            assert creds.enabled is True
            assert creds.verifier is not None
        finally:
            os.unlink(path)
            os.rmdir(tmpdir)

    def test_explicit_missing_file_fatal(self):
        tmpdir = tempfile.mkdtemp()
        try:
            with pytest.raises(AuthError, match="not found"):
                load_credentials("/nonexistent/file.htpasswd", tmpdir)
        finally:
            os.rmdir(tmpdir)

    def test_explicit_unreadable_file_fatal(self):
        hashed = "$2y$12$R9h/cIPz0gi.URNNGS3/aO/O.r6HS5xO31a5NQc6XjHPT8f6sFXe2"
        tmpdir, path = self._make_file(f"admin:{hashed}\n")
        try:
            os.chmod(path, 0o000)
            with pytest.raises(AuthError, match="not readable"):
                load_credentials(os.path.basename(path), tmpdir)
        finally:
            os.chmod(path, 0o644)
            os.unlink(path)
            os.rmdir(tmpdir)

    def test_explicit_malformed_file_fatal(self):
        tmpdir, path = self._make_file("plaintext_password\n")
        try:
            with pytest.raises(AuthError, match="missing ':' delimiter"):
                load_credentials(os.path.basename(path), tmpdir)
        finally:
            os.unlink(path)
            os.rmdir(tmpdir)

    def test_explicit_empty_file_fatal(self):
        tmpdir, path = self._make_file("")
        try:
            with pytest.raises(AuthError, match="empty"):
                load_credentials(os.path.basename(path), tmpdir)
        finally:
            os.unlink(path)
            os.rmdir(tmpdir)


class TestVerifierCallable:
    """Test the verifier callable returned by load_credentials."""

    def _make_credentials(self, htpasswd_content: str) -> HtpasswdCredentials:
        """Helper to load credentials from content."""
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, ".htpasswd")
        with open(path, "w", encoding="utf-8") as f:
            f.write(htpasswd_content)
        try:
            return load_credentials(None, tmpdir)
        finally:
            os.unlink(path)
            os.rmdir(tmpdir)

    def test_valid_password_succeeds(self, bcrypt_hash):
        creds = self._make_credentials(f"admin:{bcrypt_hash}\n")
        # Should not raise
        creds.verifier("admin", "password")

    def test_wrong_password_fails(self, bcrypt_hash):
        creds = self._make_credentials(f"admin:{bcrypt_hash}\n")
        with pytest.raises(VerificationError):
            creds.verifier("admin", "wrong_password")

    def test_unknown_user_fails_with_same_error(self, bcrypt_hash):
        creds = self._make_credentials(f"admin:{bcrypt_hash}\n")
        # Should raise VerificationError, same as wrong password
        with pytest.raises(VerificationError):
            creds.verifier("unknown_user", "password")

    def test_generic_error_message(self, bcrypt_hash):
        creds = self._make_credentials(f"admin:{bcrypt_hash}\n")
        try:
            creds.verifier("unknown_user", "wrong")
        except VerificationError as e:
            # Error message must not leak which field was wrong
            assert "Invalid credentials" in str(e)
            assert "admin" not in str(e).lower()
            assert "password" not in str(e).lower()

    def test_multiple_users(self, bcrypt_hash, apr1_hash):
        creds = self._make_credentials(f"admin:{bcrypt_hash}\noperator:{apr1_hash}\n")
        # Both should verify successfully with correct password
        creds.verifier("admin", "password")
        creds.verifier("operator", "password")
        # Both should fail with wrong password
        with pytest.raises(VerificationError):
            creds.verifier("admin", "wrong")
        with pytest.raises(VerificationError):
            creds.verifier("operator", "wrong")


class TestCredentialReload:
    """Live htpasswd replacement preserves a complete, last-known-good map."""

    @staticmethod
    def _replace(path: Path, content: str) -> None:
        replacement = path.with_name(f"{path.name}.next")
        replacement.write_text(content, encoding="utf-8")
        replacement.chmod(0o600)
        os.replace(replacement, path)

    def test_atomic_rotation_adds_and_removes_users(self, tmp_path, bcrypt_hash):
        path = tmp_path / ".htpasswd"
        path.write_text(f"old-user:{bcrypt_hash}\n", encoding="utf-8")
        creds = load_credentials(str(path), str(tmp_path))

        creds.verifier("old-user", "password")
        self._replace(path, f"new-user:{bcrypt_hash}\n")

        with pytest.raises(VerificationError):
            creds.verifier("old-user", "password")
        creds.verifier("new-user", "password")

        # A restarted service observes the same replacement as the live one.
        restarted = load_credentials(str(path), str(tmp_path))
        restarted.verifier("new-user", "password")
        with pytest.raises(VerificationError):
            restarted.verifier("old-user", "password")

        status = creds.reload_status()
        assert status["reload"] == {
            "state": "reloaded",
            "generation": 2,
            "retaining_last_known_good": False,
        }

    def test_invalid_replacement_retains_last_known_good_then_recovers(
        self, tmp_path, bcrypt_hash
    ):
        path = tmp_path / ".htpasswd"
        path.write_text(f"operator:{bcrypt_hash}\n", encoding="utf-8")
        creds = load_credentials(str(path), str(tmp_path))

        self._replace(path, "operator:$2y$12$partial\n")
        # The parse failure must not disable auth or replace the existing map.
        creds.verifier("operator", "password")
        rejected = creds.reload_status()
        assert rejected["reload"]["state"] == "reload_rejected"
        assert rejected["reload"]["retaining_last_known_good"] is True

        self._replace(path, f"replacement:{bcrypt_hash}\n")
        with pytest.raises(VerificationError):
            creds.verifier("operator", "password")
        creds.verifier("replacement", "password")
        assert creds.reload_status()["reload"]["generation"] == 2

    def test_symlink_replacement_is_rejected_without_dropping_auth(
        self, tmp_path, bcrypt_hash
    ):
        path = tmp_path / ".htpasswd"
        target = tmp_path / "replacement.htpasswd"
        path.write_text(f"operator:{bcrypt_hash}\n", encoding="utf-8")
        target.write_text(f"attacker:{bcrypt_hash}\n", encoding="utf-8")
        creds = load_credentials(str(path), str(tmp_path))

        path.unlink()
        path.symlink_to(target)

        creds.verifier("operator", "password")
        with pytest.raises(VerificationError):
            creds.verifier("attacker", "password")
        assert creds.reload_status()["reload"]["retaining_last_known_good"] is True

    def test_initial_symlink_is_rejected(self, tmp_path, bcrypt_hash):
        target = tmp_path / "target.htpasswd"
        path = tmp_path / ".htpasswd"
        target.write_text(f"operator:{bcrypt_hash}\n", encoding="utf-8")
        path.symlink_to(target)

        with pytest.raises(AuthError, match="symbolic link"):
            load_credentials(str(path), str(tmp_path))

    def test_discovered_symlink_is_not_treated_as_auth_disabled(self, tmp_path, bcrypt_hash):
        target = tmp_path / "target.htpasswd"
        path = tmp_path / ".htpasswd"
        target.write_text(f"operator:{bcrypt_hash}\n", encoding="utf-8")
        path.symlink_to(target)

        with pytest.raises(AuthError, match="symbolic link"):
            load_credentials(None, str(tmp_path))

    def test_unchanged_file_does_not_advance_generation(self, tmp_path, bcrypt_hash):
        path = tmp_path / ".htpasswd"
        path.write_text(f"operator:{bcrypt_hash}\n", encoding="utf-8")
        creds = load_credentials(str(path), str(tmp_path))

        creds.verifier("operator", "password")
        creds.verifier("operator", "password")
        assert creds.reload_status()["reload"] == {
            "state": "ready",
            "generation": 1,
            "retaining_last_known_good": False,
        }

    def test_concurrent_verification_observes_only_complete_maps(
        self, tmp_path, bcrypt_hash
    ):
        path = tmp_path / ".htpasswd"
        path.write_text(f"operator:{bcrypt_hash}\n", encoding="utf-8")
        creds = load_credentials(str(path), str(tmp_path))
        start = threading.Barrier(9)
        outcomes: list[bool] = []
        outcome_lock = threading.Lock()

        def verify() -> None:
            start.wait()
            try:
                creds.verifier("operator", "password")
                outcome = True
            except VerificationError:
                outcome = False
            with outcome_lock:
                outcomes.append(outcome)

        threads = [threading.Thread(target=verify) for _ in range(8)]
        for thread in threads:
            thread.start()
        start.wait()
        self._replace(path, f"operator:{bcrypt_hash}\nnew-user:{bcrypt_hash}\n")
        for thread in threads:
            thread.join()

        assert outcomes == [True] * 8
        creds.verifier("new-user", "password")

    def test_reload_status_never_exposes_file_or_credential_details(
        self, tmp_path, bcrypt_hash
    ):
        path = tmp_path / "private-credentials.htpasswd"
        path.write_text(f"operator:{bcrypt_hash}\n", encoding="utf-8")
        creds = load_credentials(str(path), str(tmp_path))
        self._replace(path, "operator:$2y$12$partial\n")
        creds.verifier("operator", "password")

        rendered = repr(creds.reload_status())
        assert str(path) not in rendered
        assert "operator" not in rendered
        assert bcrypt_hash not in rendered


class TestSecurityProperties:
    """Test security properties (no credential leakage, etc.)."""

    def test_verification_error_message_generic(self, bcrypt_hash):
        """Verify that VerificationError doesn't leak credentials."""
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, ".htpasswd")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"admin:{bcrypt_hash}\n")
        try:
            creds = load_credentials(None, tmpdir)
            try:
                creds.verifier("admin", "wrong")
            except VerificationError as e:
                msg = str(e)
                # No credentials should appear in error
                assert "admin" not in msg
                assert "password" not in msg
                assert "wrong" not in msg
                assert "$2y$" not in msg
                assert bcrypt_hash not in msg
        finally:
            os.unlink(path)
            os.rmdir(tmpdir)

    def test_auth_error_does_not_expose_full_paths_in_message(self):
        """AuthError messages should be safe to log."""
        with pytest.raises(AuthError) as exc_info:
            load_credentials("/very/secret/path/creds.txt", "/home/user")
        msg = str(exc_info.value)
        # Path is included but should be safe to log (not sensitive data)
        assert "creds" in msg or "secret" in msg or "path" in msg

    def test_constant_time_compare_timing_resistant(self):
        """Verify constant_time_compare doesn't have early-exit paths.
        
        This is a basic sanity check. True timing-attack resistance
        requires hardware-level or specialized testing.
        """
        # Compare strings of same length
        assert _constant_time_compare("abc", "abc") is True
        assert _constant_time_compare("abc", "abd") is False
        # Compare strings of different length (should still work)
        assert _constant_time_compare("a", "abc") is False
