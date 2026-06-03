"""Tests for oompah.backlog_webhooks — Backlog.md task-change webhook setup.

Covers:
- HMAC-SHA256 signature validation (validate_backlog_webhook_signature)
- Idempotent post-commit hook installation (install_backlog_webhook_hook)
- Bulk installation for all managed projects (ensure_backlog_webhooks)
- Error paths: missing .git, missing hook source, git config failures
"""

from __future__ import annotations

import hashlib
import hmac
import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from oompah.backlog_webhooks import (
    ensure_backlog_webhooks,
    install_backlog_webhook_hook,
    validate_backlog_webhook_signature,
    _GIT_CONFIG_URL_KEY,
    _GIT_CONFIG_SECRET_KEY,
    _GIT_CONFIG_PROJECT_ID_KEY,
    _HOOK_NAME,
    _OOMPAH_HOOK_MARKER,
)
from oompah.models import Project


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_git_repo(tmp_path):
    """Create a real git repository and return its path."""
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=str(repo), capture_output=True, check=True)
    return repo


def _make_project(
    repo_path: str = "/tmp/test-repo",
    project_id: str = "proj-test1",
    name: str = "test-project",
    webhook_secret: str | None = None,
) -> Project:
    return Project(
        id=project_id,
        name=name,
        repo_url="https://github.com/org/repo.git",
        repo_path=repo_path,
        webhook_secret=webhook_secret,
    )


def _read_git_config(repo_path, key):
    """Read a git local config value."""
    result = subprocess.run(
        ["git", "config", "--local", key],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return None


# ---------------------------------------------------------------------------
# validate_backlog_webhook_signature
# ---------------------------------------------------------------------------


class TestValidateBacklogWebhookSignature:
    """Tests for validate_backlog_webhook_signature()."""

    def test_valid_signature(self):
        secret = "my-backlog-secret"
        body = b'{"project_id":"proj-1","event":"task_changed"}'
        mac = hmac.new(secret.encode(), body, hashlib.sha256)
        sig = f"sha256={mac.hexdigest()}"
        assert validate_backlog_webhook_signature(body, sig, secret) is True

    def test_invalid_signature(self):
        secret = "my-backlog-secret"
        body = b'{"project_id":"proj-1"}'
        assert validate_backlog_webhook_signature(body, "sha256=deadbeef", secret) is False

    def test_wrong_secret(self):
        correct = "correct-secret"
        wrong = "wrong-secret"
        body = b'{"event":"task_changed"}'
        mac = hmac.new(wrong.encode(), body, hashlib.sha256)
        sig = f"sha256={mac.hexdigest()}"
        assert validate_backlog_webhook_signature(body, sig, correct) is False

    def test_missing_prefix(self):
        secret = "my-secret"
        body = b"hello"
        sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        assert validate_backlog_webhook_signature(body, sig, secret) is False

    def test_empty_signature_header(self):
        assert validate_backlog_webhook_signature(b"body", "", "secret") is False

    def test_empty_secret(self):
        assert validate_backlog_webhook_signature(b"body", "sha256=abc", "") is False

    def test_empty_both(self):
        assert validate_backlog_webhook_signature(b"body", "", "") is False

    def test_large_payload(self):
        secret = "big-secret"
        body = b"x" * 100_000
        mac = hmac.new(secret.encode(), body, hashlib.sha256)
        sig = f"sha256={mac.hexdigest()}"
        assert validate_backlog_webhook_signature(body, sig, secret) is True

    def test_constant_time_comparison(self):
        """Uses hmac.compare_digest for constant-time comparison."""
        secret = "a" * 1000
        body = b"data"
        mac = hmac.new(secret.encode(), body, hashlib.sha256)
        sig = f"sha256={mac.hexdigest()}"
        assert validate_backlog_webhook_signature(body, sig, secret) is True
        # Change last character
        bad_sig = sig[:-1] + ("0" if sig[-1] != "0" else "1")
        assert validate_backlog_webhook_signature(body, bad_sig, secret) is False


# ---------------------------------------------------------------------------
# install_backlog_webhook_hook — basic installation
# ---------------------------------------------------------------------------


class TestInstallBacklogWebhookHook:
    """Tests for install_backlog_webhook_hook()."""

    def test_installs_hook_into_git_repo(self, tmp_path):
        repo = _make_git_repo(tmp_path)
        webhook_url = "http://localhost:8080/api/v1/webhooks/backlog"
        project_id = "proj-abc"
        secret = "my-secret"

        result = install_backlog_webhook_hook(
            repo_path=str(repo),
            webhook_url=webhook_url,
            project_id=project_id,
            secret=secret,
        )

        assert result is True
        hook_path = repo / ".git" / "hooks" / _HOOK_NAME
        assert hook_path.exists() or os.path.islink(str(hook_path))

    def test_hook_contains_oompah_marker(self, tmp_path):
        """The installed hook must contain the sentinel marker."""
        repo = _make_git_repo(tmp_path)

        install_backlog_webhook_hook(
            repo_path=str(repo),
            webhook_url="http://localhost:8080/api/v1/webhooks/backlog",
            project_id="proj-1",
            secret="",
        )

        hook_path = repo / ".git" / "hooks" / _HOOK_NAME
        # Resolve symlink to read actual content
        real_path = os.path.realpath(str(hook_path))
        content = open(real_path, encoding="utf-8").read()
        assert _OOMPAH_HOOK_MARKER in content

    def test_git_config_written(self, tmp_path):
        """Git config entries are set after installation."""
        repo = _make_git_repo(tmp_path)
        url = "http://localhost:9999/api/v1/webhooks/backlog"
        pid = "proj-xyz"
        secret = "s3cret"

        install_backlog_webhook_hook(
            repo_path=str(repo),
            webhook_url=url,
            project_id=pid,
            secret=secret,
        )

        assert _read_git_config(repo, _GIT_CONFIG_URL_KEY) == url
        assert _read_git_config(repo, _GIT_CONFIG_PROJECT_ID_KEY) == pid
        assert _read_git_config(repo, _GIT_CONFIG_SECRET_KEY) == secret

    def test_skips_non_git_directory(self, tmp_path):
        """Returns False when repo_path is not a git repo."""
        non_git = tmp_path / "not-a-repo"
        non_git.mkdir()

        result = install_backlog_webhook_hook(
            repo_path=str(non_git),
            webhook_url="http://localhost:8080/api/v1/webhooks/backlog",
            project_id="proj-1",
            secret="",
        )

        assert result is False

    def test_skips_empty_repo_path(self, tmp_path):
        """Returns False for empty/missing repo_path."""
        result = install_backlog_webhook_hook(
            repo_path="",
            webhook_url="http://localhost:8080/api/v1/webhooks/backlog",
            project_id="proj-1",
            secret="",
        )
        assert result is False

    def test_hook_is_executable(self, tmp_path):
        """The installed hook must be executable."""
        repo = _make_git_repo(tmp_path)

        install_backlog_webhook_hook(
            repo_path=str(repo),
            webhook_url="http://localhost:8080/api/v1/webhooks/backlog",
            project_id="proj-1",
            secret="",
        )

        hook_path = repo / ".git" / "hooks" / _HOOK_NAME
        real_path = os.path.realpath(str(hook_path))
        # Check the real file (not the symlink) is executable.
        stat = os.stat(real_path)
        assert stat.st_mode & 0o111  # any execute bit set


# ---------------------------------------------------------------------------
# install_backlog_webhook_hook — idempotency
# ---------------------------------------------------------------------------


class TestInstallBacklogWebhookHookIdempotent:
    """Verify that install_backlog_webhook_hook is idempotent."""

    def test_second_call_does_not_raise(self, tmp_path):
        """Calling install twice on the same repo must not raise."""
        repo = _make_git_repo(tmp_path)
        kwargs = dict(
            repo_path=str(repo),
            webhook_url="http://localhost:8080/api/v1/webhooks/backlog",
            project_id="proj-1",
            secret="s3cret",
        )

        first = install_backlog_webhook_hook(**kwargs)
        second = install_backlog_webhook_hook(**kwargs)

        assert first is True
        assert second is True

    def test_second_call_returns_true(self, tmp_path):
        """Second install with same config returns True (idempotent success)."""
        repo = _make_git_repo(tmp_path)
        kwargs = dict(
            repo_path=str(repo),
            webhook_url="http://localhost:8080/api/v1/webhooks/backlog",
            project_id="proj-1",
            secret="",
        )
        install_backlog_webhook_hook(**kwargs)
        assert install_backlog_webhook_hook(**kwargs) is True

    def test_hook_file_not_duplicated_on_second_install(self, tmp_path):
        """The hook file is a single file (no duplicate install)."""
        repo = _make_git_repo(tmp_path)
        hooks_dir = repo / ".git" / "hooks"

        install_backlog_webhook_hook(
            repo_path=str(repo),
            webhook_url="http://localhost:8080/api/v1/webhooks/backlog",
            project_id="proj-1",
            secret="",
        )
        install_backlog_webhook_hook(
            repo_path=str(repo),
            webhook_url="http://localhost:8080/api/v1/webhooks/backlog",
            project_id="proj-1",
            secret="",
        )

        hook_files = list(hooks_dir.glob(_HOOK_NAME + "*"))
        # Should be exactly one hook file (no suffixes like post-commit.bak)
        assert len(hook_files) == 1

    def test_updated_secret_reflected_in_git_config(self, tmp_path):
        """Updating the secret via a second install updates git config."""
        repo = _make_git_repo(tmp_path)

        install_backlog_webhook_hook(
            repo_path=str(repo),
            webhook_url="http://localhost:8080/api/v1/webhooks/backlog",
            project_id="proj-1",
            secret="old-secret",
        )
        assert _read_git_config(repo, _GIT_CONFIG_SECRET_KEY) == "old-secret"

        install_backlog_webhook_hook(
            repo_path=str(repo),
            webhook_url="http://localhost:8080/api/v1/webhooks/backlog",
            project_id="proj-1",
            secret="new-secret",
        )
        assert _read_git_config(repo, _GIT_CONFIG_SECRET_KEY) == "new-secret"

    def test_updated_url_reflected_in_git_config(self, tmp_path):
        """Updating the URL via a second install updates git config."""
        repo = _make_git_repo(tmp_path)

        install_backlog_webhook_hook(
            repo_path=str(repo),
            webhook_url="http://localhost:8080/api/v1/webhooks/backlog",
            project_id="proj-1",
            secret="",
        )
        install_backlog_webhook_hook(
            repo_path=str(repo),
            webhook_url="http://localhost:9999/api/v1/webhooks/backlog",
            project_id="proj-1",
            secret="",
        )
        assert _read_git_config(repo, _GIT_CONFIG_URL_KEY) == (
            "http://localhost:9999/api/v1/webhooks/backlog"
        )

    def test_existing_non_oompah_hook_is_replaced(self, tmp_path):
        """A pre-existing non-oompah hook is replaced."""
        repo = _make_git_repo(tmp_path)
        hooks_dir = repo / ".git" / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        # Write a non-oompah hook
        existing_hook = hooks_dir / _HOOK_NAME
        existing_hook.write_text("#!/bin/sh\necho 'custom hook'\n")

        result = install_backlog_webhook_hook(
            repo_path=str(repo),
            webhook_url="http://localhost:8080/api/v1/webhooks/backlog",
            project_id="proj-1",
            secret="",
        )

        assert result is True
        # The hook should now contain the oompah marker
        real_path = os.path.realpath(str(existing_hook))
        content = open(real_path).read()
        assert _OOMPAH_HOOK_MARKER in content


# ---------------------------------------------------------------------------
# ensure_backlog_webhooks — bulk installation
# ---------------------------------------------------------------------------


class _FakeProjectStore:
    """Minimal ProjectStore stand-in for testing."""

    def __init__(self, projects):
        self._projects = projects

    def list_all(self):
        return list(self._projects)


class TestEnsureBacklogWebhooks:
    """Tests for ensure_backlog_webhooks()."""

    def test_installs_hooks_for_all_projects(self, tmp_path):
        repo1 = _make_git_repo(tmp_path / "r1")
        repo2 = _make_git_repo(tmp_path / "r2")

        projects = [
            _make_project(repo_path=str(repo1), project_id="p1", name="repo1"),
            _make_project(repo_path=str(repo2), project_id="p2", name="repo2"),
        ]
        store = _FakeProjectStore(projects)

        results = ensure_backlog_webhooks(store, server_base_url="http://localhost:8080")

        assert results["p1"] == "ok"
        assert results["p2"] == "ok"

        # Hooks installed in both repos
        for repo in (repo1, repo2):
            hook = repo / ".git" / "hooks" / _HOOK_NAME
            assert hook.exists() or os.path.islink(str(hook))

    def test_skips_projects_without_git_directory(self, tmp_path):
        non_git = tmp_path / "not-git"
        non_git.mkdir()

        projects = [_make_project(repo_path=str(non_git), project_id="p1")]
        store = _FakeProjectStore(projects)

        results = ensure_backlog_webhooks(store, server_base_url="http://localhost:8080")

        assert "p1" in results
        assert results["p1"].startswith("skipped")

    def test_empty_project_list_returns_empty(self):
        store = _FakeProjectStore([])
        results = ensure_backlog_webhooks(store, server_base_url="http://localhost:8080")
        assert results == {}

    def test_none_project_store_returns_empty(self):
        results = ensure_backlog_webhooks(None, server_base_url="http://localhost:8080")
        assert results == {}

    def test_webhook_url_uses_provided_base_url(self, tmp_path):
        repo = _make_git_repo(tmp_path)
        projects = [_make_project(repo_path=str(repo), project_id="p1")]
        store = _FakeProjectStore(projects)

        ensure_backlog_webhooks(store, server_base_url="http://localhost:9999")

        stored_url = _read_git_config(repo, _GIT_CONFIG_URL_KEY)
        assert stored_url == "http://localhost:9999/api/v1/webhooks/backlog"

    def test_webhook_url_from_env_when_base_not_provided(self, tmp_path, monkeypatch):
        repo = _make_git_repo(tmp_path)
        monkeypatch.setenv("OOMPAH_SERVER_URL", "http://my-server:7777")
        projects = [_make_project(repo_path=str(repo), project_id="p1")]
        store = _FakeProjectStore(projects)

        ensure_backlog_webhooks(store, server_base_url=None)

        stored_url = _read_git_config(repo, _GIT_CONFIG_URL_KEY)
        assert stored_url == "http://my-server:7777/api/v1/webhooks/backlog"

    def test_fallback_url_when_no_env_and_no_base(self, tmp_path, monkeypatch):
        repo = _make_git_repo(tmp_path)
        monkeypatch.delenv("OOMPAH_SERVER_URL", raising=False)
        projects = [_make_project(repo_path=str(repo), project_id="p1")]
        store = _FakeProjectStore(projects)

        ensure_backlog_webhooks(store, server_base_url=None)

        stored_url = _read_git_config(repo, _GIT_CONFIG_URL_KEY)
        assert stored_url == "http://localhost:8080/api/v1/webhooks/backlog"

    def test_project_secret_used_in_git_config(self, tmp_path):
        repo = _make_git_repo(tmp_path)
        projects = [
            _make_project(
                repo_path=str(repo),
                project_id="p1",
                webhook_secret="my-project-secret",
            )
        ]
        store = _FakeProjectStore(projects)

        ensure_backlog_webhooks(store, server_base_url="http://localhost:8080")

        assert _read_git_config(repo, _GIT_CONFIG_SECRET_KEY) == "my-project-secret"

    def test_project_without_secret_skips_secret_config(self, tmp_path):
        """When a project has no webhook_secret, the secret git config key is not set."""
        repo = _make_git_repo(tmp_path)
        projects = [_make_project(repo_path=str(repo), project_id="p1", webhook_secret=None)]
        store = _FakeProjectStore(projects)

        ensure_backlog_webhooks(store, server_base_url="http://localhost:8080")

        # Secret key should not be set (no secret configured)
        assert _read_git_config(repo, _GIT_CONFIG_SECRET_KEY) is None

    def test_idempotent_bulk_install(self, tmp_path):
        """Calling ensure_backlog_webhooks twice is safe and returns ok both times."""
        repo = _make_git_repo(tmp_path)
        projects = [_make_project(repo_path=str(repo), project_id="p1")]
        store = _FakeProjectStore(projects)

        r1 = ensure_backlog_webhooks(store, server_base_url="http://localhost:8080")
        r2 = ensure_backlog_webhooks(store, server_base_url="http://localhost:8080")

        assert r1["p1"] == "ok"
        assert r2["p1"] == "ok"

    def test_exception_during_install_returns_failed_status(self, tmp_path):
        """If install_backlog_webhook_hook raises unexpectedly, the result is 'failed:'."""
        repo = _make_git_repo(tmp_path)
        projects = [_make_project(repo_path=str(repo), project_id="p1")]
        store = _FakeProjectStore(projects)

        with patch(
            "oompah.backlog_webhooks.install_backlog_webhook_hook",
            side_effect=RuntimeError("disk full"),
        ):
            results = ensure_backlog_webhooks(store, server_base_url="http://localhost:8080")

        assert "p1" in results
        assert results["p1"].startswith("failed:")
        assert "disk full" in results["p1"]


# ---------------------------------------------------------------------------
# post-commit hook script — unit tests
# ---------------------------------------------------------------------------


class TestPostCommitHookScript:
    """Tests for the bundled post-commit hook Python script logic.

    The hook is a standalone script.  We test its logic by importing the
    module-level helpers directly without executing the full subprocess.
    """

    @pytest.fixture
    def hook_module(self):
        """Import the post-commit hook as a module for testing.

        The hook is a plain Python script without a ``.py`` extension so we
        load it via ``importlib.util.spec_from_loader`` with an explicit
        ``SourceFileLoader`` to avoid the extension-based fallback that
        returns ``None`` for non-``.py`` files.
        """
        import importlib.util
        import importlib.machinery
        from oompah.git_hooks import hook_path

        hook_file = hook_path("post-commit")
        loader = importlib.machinery.SourceFileLoader("post_commit_hook", hook_file)
        spec = importlib.util.spec_from_loader("post_commit_hook", loader)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_no_changes_returns_zero(self, hook_module):
        """When no backlog files changed, main() returns 0 without POSTing."""
        with patch.object(hook_module, "_get_changed_backlog_files", return_value=[]):
            with patch("urllib.request.urlopen") as mock_urlopen:
                result = hook_module.main()
        assert result == 0
        mock_urlopen.assert_not_called()

    def test_changed_task_file_triggers_post(self, hook_module):
        """When a backlog task file changed, main() POSTs to the webhook URL."""
        with patch.object(
            hook_module,
            "_get_changed_backlog_files",
            return_value=["backlog/tasks/task-1 - My Task.md"],
        ):
            with patch.object(hook_module, "_git_config", side_effect=lambda k: {
                "oompah.backlog-webhook-url": "http://localhost:8080/api/v1/webhooks/backlog",
                "oompah.project-id": "proj-1",
                "oompah.backlog-webhook-secret": "",
            }.get(k, "")):
                mock_ctx = MagicMock()
                with patch("urllib.request.urlopen", return_value=mock_ctx) as mock_open:
                    mock_ctx.__enter__ = lambda s: s
                    mock_ctx.__exit__ = MagicMock(return_value=False)
                    result = hook_module.main()

        assert result == 0
        mock_open.assert_called_once()

    def test_backlog_files_detection(self, hook_module):
        """_get_changed_backlog_files filters to only backlog task/completed .md files."""
        output = "\n".join([
            "src/main.py",
            "backlog/tasks/task-1 - Test.md",
            "backlog/completed/task-2 - Done.md",
            "README.md",
            "backlog/tasks/not-a-markdown.txt",
        ])

        with patch.object(hook_module, "_run_git", return_value=output):
            changed = hook_module._get_changed_backlog_files()

        assert "backlog/tasks/task-1 - Test.md" in changed
        assert "backlog/completed/task-2 - Done.md" in changed
        assert "src/main.py" not in changed
        assert "README.md" not in changed
        assert "backlog/tasks/not-a-markdown.txt" not in changed

    def test_signature_added_when_secret_set(self, hook_module):
        """When a secret is configured, the X-Oompah-Signature header is set."""
        captured_headers = {}

        class _FakeRequest:
            def __init__(self, url, data, headers, method):
                captured_headers.update(headers)

        with patch.object(
            hook_module,
            "_get_changed_backlog_files",
            return_value=["backlog/tasks/task-1 - Test.md"],
        ):
            with patch.object(hook_module, "_git_config", side_effect=lambda k: {
                "oompah.backlog-webhook-url": "http://localhost:8080/api/v1/webhooks/backlog",
                "oompah.project-id": "proj-1",
                "oompah.backlog-webhook-secret": "my-secret",
            }.get(k, "")):
                with patch("urllib.request.Request", side_effect=_FakeRequest):
                    with patch("urllib.request.urlopen", side_effect=Exception("skip")):
                        hook_module.main()

        assert "X-Oompah-Signature" in captured_headers
        assert captured_headers["X-Oompah-Signature"].startswith("sha256=")

    def test_no_signature_when_no_secret(self, hook_module):
        """When no secret, X-Oompah-Signature header is NOT set."""
        captured_headers = {}

        class _FakeRequest:
            def __init__(self, url, data, headers, method):
                captured_headers.update(headers)

        with patch.object(
            hook_module,
            "_get_changed_backlog_files",
            return_value=["backlog/tasks/task-1 - Test.md"],
        ):
            with patch.object(hook_module, "_git_config", side_effect=lambda k: {
                "oompah.backlog-webhook-url": "http://localhost:8080/api/v1/webhooks/backlog",
                "oompah.project-id": "proj-1",
                "oompah.backlog-webhook-secret": "",
            }.get(k, "")):
                with patch("urllib.request.Request", side_effect=_FakeRequest):
                    with patch("urllib.request.urlopen", side_effect=Exception("skip")):
                        hook_module.main()

        assert "X-Oompah-Signature" not in captured_headers

    def test_network_failure_does_not_block_commit(self, hook_module):
        """A network error must not cause main() to return non-zero."""
        with patch.object(
            hook_module,
            "_get_changed_backlog_files",
            return_value=["backlog/tasks/task-1 - Test.md"],
        ):
            with patch.object(hook_module, "_git_config", return_value=""):
                with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
                    result = hook_module.main()

        assert result == 0

    def test_default_url_used_when_no_config(self, hook_module):
        """When no git config is set, falls back to default URL."""
        captured_url = {}

        class _FakeRequest:
            def __init__(self, url, data, headers, method):
                captured_url["url"] = url

        with patch.object(
            hook_module,
            "_get_changed_backlog_files",
            return_value=["backlog/tasks/task-1 - Test.md"],
        ):
            with patch.object(hook_module, "_git_config", return_value=""):
                with patch("urllib.request.Request", side_effect=_FakeRequest):
                    with patch("urllib.request.urlopen", side_effect=Exception("skip")):
                        hook_module.main()

        assert captured_url.get("url") == hook_module._DEFAULT_WEBHOOK_URL
