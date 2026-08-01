"""Tests for OOMPAH-686: Worker container-runtime environment fallback.

This module tests the functionality that allows workers to run successfully
even when their sandbox provides a read-only XDG_RUNTIME_DIR, which would
cause podman and other container tools to fail with "chmod: read-only file
system" errors.

Test coverage:
- _is_xdg_runtime_dir_writable detects read-only/missing runtime dirs
- _create_worker_runtime_directory creates private temp directories
- agent_environment provides fallback XDG_RUNTIME_DIR when inherited is read-only
- Cleanup logic removes temporary directories after worker exits
- Credentials are not leaked in temporary directory paths
- No shared runtime directories are modified
"""

from __future__ import annotations

import os
import shutil
import stat
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from oompah.client_auth import (
    _create_worker_runtime_directory,
    _is_xdg_runtime_dir_writable,
    agent_environment,
)


class TestIsXdgRuntimeDirWritable:
    """Test detection of writable XDG_RUNTIME_DIR."""

    def test_nonexistent_directory_returns_false(self):
        """Nonexistent directory is not writable."""
        assert not _is_xdg_runtime_dir_writable("/nonexistent/path/that/does/not/exist")

    def test_empty_string_returns_false(self):
        """Empty XDG_RUNTIME_DIR is not writable."""
        assert not _is_xdg_runtime_dir_writable("")

    def test_none_returns_false(self):
        """None is not writable."""
        assert not _is_xdg_runtime_dir_writable(None)

    def test_writable_directory_returns_true(self, tmp_path):
        """Writable directory is detected as writable."""
        # Create a writable directory
        runtime_dir = tmp_path / "runtime"
        runtime_dir.mkdir(mode=0o700)
        assert _is_xdg_runtime_dir_writable(str(runtime_dir))

    def test_read_only_directory_returns_false(self, tmp_path):
        """Read-only directory is detected as not writable."""
        # Create a read-only directory
        runtime_dir = tmp_path / "runtime"
        runtime_dir.mkdir(mode=0o700)
        os.chmod(runtime_dir, 0o555)  # read-only
        try:
            assert not _is_xdg_runtime_dir_writable(str(runtime_dir))
        finally:
            # Restore permissions for cleanup
            os.chmod(runtime_dir, 0o755)

    def test_file_instead_of_directory_returns_false(self, tmp_path):
        """XDG_RUNTIME_DIR that is a file (not directory) is not writable."""
        # Create a file instead of a directory
        runtime_file = tmp_path / "runtime_file"
        runtime_file.write_text("not a directory")
        assert not _is_xdg_runtime_dir_writable(str(runtime_file))

    def test_permission_denied_returns_false(self, tmp_path):
        """Directory with permission denied on parent is not accessible."""
        # Create nested directory structure
        parent = tmp_path / "parent"
        parent.mkdir(mode=0o700)
        runtime_dir = parent / "runtime"
        runtime_dir.mkdir(mode=0o700)

        # Remove parent's search permissions (blocks access to children)
        os.chmod(parent, 0o000)
        try:
            assert not _is_xdg_runtime_dir_writable(str(runtime_dir))
        finally:
            # Restore permissions for cleanup
            os.chmod(parent, 0o755)


class TestCreateWorkerRuntimeDirectory:
    """Test creation of private worker runtime directories."""

    def test_creates_directory_with_secure_permissions(self):
        """Created directory has secure 0o700 permissions."""
        runtime_dir = _create_worker_runtime_directory()
        try:
            assert runtime_dir is not None
            assert os.path.isdir(runtime_dir)
            # Check permissions: should be 0o700 (owner only)
            mode = stat.S_IMODE(os.stat(runtime_dir).st_mode)
            assert mode == 0o700, f"Expected 0o700, got {oct(mode)}"
        finally:
            if runtime_dir:
                shutil.rmtree(runtime_dir, ignore_errors=True)

    def test_directory_name_includes_prefix(self):
        """Created directory name includes identifying prefix."""
        runtime_dir = _create_worker_runtime_directory()
        try:
            assert runtime_dir is not None
            assert "oompah-worker-runtime" in os.path.basename(runtime_dir)
        finally:
            if runtime_dir:
                shutil.rmtree(runtime_dir, ignore_errors=True)

    def test_directories_are_unique(self):
        """Each call creates a unique directory."""
        runtime_dir1 = _create_worker_runtime_directory()
        runtime_dir2 = _create_worker_runtime_directory()
        try:
            assert runtime_dir1 != runtime_dir2
            assert os.path.isdir(runtime_dir1)
            assert os.path.isdir(runtime_dir2)
        finally:
            for d in [runtime_dir1, runtime_dir2]:
                if d:
                    shutil.rmtree(d, ignore_errors=True)

    def test_respects_tmpdir_environment_variable(self, tmp_path, monkeypatch):
        """Created directory uses TMPDIR when set."""
        custom_tmp = tmp_path / "custom_tmp"
        custom_tmp.mkdir()
        monkeypatch.setenv("TMPDIR", str(custom_tmp))

        runtime_dir = _create_worker_runtime_directory()
        try:
            assert runtime_dir is not None
            # Verify it's under the custom TMPDIR
            assert str(runtime_dir).startswith(str(custom_tmp))
        finally:
            if runtime_dir:
                shutil.rmtree(runtime_dir, ignore_errors=True)

    def test_returns_none_on_failure(self, monkeypatch):
        """Returns None when directory creation fails."""
        # Make mkdtemp fail by passing invalid arguments
        def failing_mkdtemp(*args, **kwargs):
            raise OSError("Permission denied")

        with patch("oompah.client_auth.tempfile.mkdtemp", side_effect=failing_mkdtemp):
            result = _create_worker_runtime_directory()
            assert result is None


class TestAgentEnvironmentXdgRuntimeDir:
    """Test agent_environment's XDG_RUNTIME_DIR fallback (OOMPAH-686)."""

    def test_writable_xdg_runtime_dir_unchanged(self, tmp_path, monkeypatch):
        """Writable XDG_RUNTIME_DIR is passed through unchanged."""
        runtime_dir = tmp_path / "runtime"
        runtime_dir.mkdir(mode=0o700)

        base_env = {
            "PATH": "/usr/bin",
            "XDG_RUNTIME_DIR": str(runtime_dir),
        }
        result = agent_environment(base_env)

        # Should not create fallback when original is writable
        assert result["XDG_RUNTIME_DIR"] == str(runtime_dir)
        assert "OOMPAH_WORKER_RUNTIME_DIR" not in result

    def test_read_only_xdg_runtime_dir_gets_fallback(self, tmp_path):
        """Read-only XDG_RUNTIME_DIR triggers creation of fallback."""
        runtime_dir = tmp_path / "readonly_runtime"
        runtime_dir.mkdir(mode=0o700)
        os.chmod(runtime_dir, 0o555)  # make read-only

        try:
            base_env = {
                "PATH": "/usr/bin",
                "XDG_RUNTIME_DIR": str(runtime_dir),
            }
            result = agent_environment(base_env)

            # Should create fallback and mark it for cleanup
            assert "OOMPAH_WORKER_RUNTIME_DIR" in result
            fallback = result["OOMPAH_WORKER_RUNTIME_DIR"]
            assert fallback != str(runtime_dir)
            assert os.path.isdir(fallback)
            assert result["XDG_RUNTIME_DIR"] == fallback

            # Fallback should be writable
            assert os.access(fallback, os.W_OK)

            # Cleanup
            shutil.rmtree(fallback, ignore_errors=True)
        finally:
            os.chmod(runtime_dir, 0o755)

    def test_missing_xdg_runtime_dir_gets_fallback(self):
        """Missing XDG_RUNTIME_DIR triggers creation of fallback."""
        base_env = {
            "PATH": "/usr/bin",
            "XDG_RUNTIME_DIR": "/nonexistent/path",
        }
        result = agent_environment(base_env)

        # Should create fallback
        assert "OOMPAH_WORKER_RUNTIME_DIR" in result
        fallback = result["OOMPAH_WORKER_RUNTIME_DIR"]
        assert os.path.isdir(fallback)
        assert result["XDG_RUNTIME_DIR"] == fallback

        # Cleanup
        shutil.rmtree(fallback, ignore_errors=True)

    def test_unset_xdg_runtime_dir_not_modified(self):
        """Unset XDG_RUNTIME_DIR is not added."""
        base_env = {"PATH": "/usr/bin"}
        result = agent_environment(base_env)

        # Should not add XDG_RUNTIME_DIR if it wasn't there
        assert "XDG_RUNTIME_DIR" not in result
        assert "OOMPAH_WORKER_RUNTIME_DIR" not in result

    def test_fallback_is_marked_for_cleanup(self, tmp_path):
        """Fallback directory is marked with OOMPAH_WORKER_RUNTIME_DIR."""
        runtime_dir = tmp_path / "runtime"
        runtime_dir.mkdir(mode=0o700)
        os.chmod(runtime_dir, 0o555)

        try:
            base_env = {
                "XDG_RUNTIME_DIR": str(runtime_dir),
            }
            result = agent_environment(base_env)

            # Marker should be set so caller can clean up
            assert "OOMPAH_WORKER_RUNTIME_DIR" in result
            cleanup_path = result["OOMPAH_WORKER_RUNTIME_DIR"]
            assert cleanup_path == result["XDG_RUNTIME_DIR"]

            # Cleanup
            shutil.rmtree(cleanup_path, ignore_errors=True)
        finally:
            os.chmod(runtime_dir, 0o755)

    def test_preserves_client_auth_stripping(self, tmp_path):
        """XDG_RUNTIME_DIR fallback still strips client auth variables."""
        runtime_dir = tmp_path / "runtime"
        runtime_dir.mkdir(mode=0o700)
        os.chmod(runtime_dir, 0o555)

        try:
            base_env = {
                "XDG_RUNTIME_DIR": str(runtime_dir),
                "OOMPAH_SERVER_USERNAME": "secret_user",
                "OOMPAH_SERVER_PASSWORD": "secret_pass",
            }
            result = agent_environment(base_env)

            # Client auth should be stripped
            assert "OOMPAH_SERVER_USERNAME" not in result
            assert "OOMPAH_SERVER_PASSWORD" not in result
            # But fallback should still be provided
            assert "OOMPAH_WORKER_RUNTIME_DIR" in result

            # Cleanup
            cleanup_path = result["OOMPAH_WORKER_RUNTIME_DIR"]
            shutil.rmtree(cleanup_path, ignore_errors=True)
        finally:
            os.chmod(runtime_dir, 0o755)

    def test_no_secrets_leaked_in_fallback_path(self):
        """Fallback directory path doesn't contain any credentials."""
        base_env = {
            "XDG_RUNTIME_DIR": "/nonexistent",
            "OOMPAH_SERVER_PASSWORD": "supersecret123",
        }
        result = agent_environment(base_env)

        if "OOMPAH_WORKER_RUNTIME_DIR" in result:
            fallback = result["OOMPAH_WORKER_RUNTIME_DIR"]
            # Ensure no credential appears in the path
            assert "supersecret123" not in fallback
            assert "secret" not in fallback.lower()

            # Cleanup
            shutil.rmtree(fallback, ignore_errors=True)


class TestAgentEnvironmentBackwardCompatibility:
    """Test that XDG_RUNTIME_DIR changes don't break existing behavior."""

    def test_environment_dict_is_mutable_copy(self):
        """agent_environment returns a new dict that can be modified."""
        base_env = {
            "PATH": "/usr/bin",
            "XDG_RUNTIME_DIR": "/tmp/test",
        }
        result = agent_environment(base_env)

        # Modify result
        result["NEW_VAR"] = "value"

        # Original should not be modified
        assert "NEW_VAR" not in base_env

    def test_none_base_env_uses_os_environ(self, monkeypatch):
        """agent_environment(None) uses os.environ as base."""
        monkeypatch.setenv("TEST_VAR", "test_value")
        monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)

        result = agent_environment(None)
        assert result.get("TEST_VAR") == "test_value"

    def test_client_auth_disabled_flag_set(self):
        """CLIENT_AUTH_DISABLED_ENV is set in result."""
        from oompah.client_auth import CLIENT_AUTH_DISABLED_ENV

        result = agent_environment({})
        assert result[CLIENT_AUTH_DISABLED_ENV] == "1"

    def test_oompah_server_url_preserved(self):
        """OOMPAH_SERVER_URL is preserved (it's a locator, not credential)."""
        base_env = {
            "OOMPAH_SERVER_URL": "http://localhost:8090",
        }
        result = agent_environment(base_env)
        assert result["OOMPAH_SERVER_URL"] == "http://localhost:8090"
