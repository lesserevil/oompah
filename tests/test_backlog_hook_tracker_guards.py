"""Tests for tracker-aware Backlog hook installation guards (TASK-463.4).

Verifies that GitHub-backed projects (tracker_kind == "github_issues") are
skipped by:
  - ensure_backlog_webhooks() (startup bulk install)
  - _install_backlog_hook_for_project() (project create / update)
  - POST /api/v1/webhooks/backlog (webhook receipt handler)

Legacy Backlog projects (tracker_kind is None or any non-github value) must
continue to install and process hooks idempotently.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import subprocess
from unittest.mock import MagicMock, call, patch

import pytest
from fastapi.testclient import TestClient

from oompah.backlog_webhooks import ensure_backlog_webhooks
from oompah.models import Project


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_project(
    project_id: str = "proj-1",
    name: str = "test-repo",
    repo_path: str = "/tmp/repos/test",
    tracker_kind: str | None = None,
    webhook_secret: str | None = None,
) -> Project:
    """Build a minimal Project for testing."""
    return Project(
        id=project_id,
        name=name,
        repo_url="https://github.com/org/repo.git",
        repo_path=repo_path,
        webhook_secret=webhook_secret,
        tracker_kind=tracker_kind,
    )


def _make_mock_project_store(projects: list[Project]):
    """Wrap a list of projects in a mock store."""
    store = MagicMock()
    store.list_all.return_value = projects
    store.get = MagicMock(
        side_effect=lambda pid: next((p for p in projects if p.id == pid), None)
    )
    return store


def _make_git_repo(tmp_path):
    """Create a real git repo for integration-style tests."""
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=str(repo), capture_output=True, check=True)
    return repo


def _backlog_payload(project_id="proj-1", event="task_changed"):
    return {
        "project_id": project_id,
        "event": event,
        "files": ["backlog/tasks/task-1 - Test.md"],
    }


def _backlog_signature(body_bytes: bytes, secret: str) -> str:
    mac = hmac.new(secret.encode(), body_bytes, hashlib.sha256)
    return f"sha256={mac.hexdigest()}"


# ---------------------------------------------------------------------------
# Project.tracker_kind model tests
# ---------------------------------------------------------------------------


class TestProjectTrackerKindField:
    """tracker_kind field round-trips through Project dataclass."""

    def test_default_tracker_kind_is_none(self):
        project = Project(
            id="p1", name="test", repo_url="https://github.com/x/y.git", repo_path="/tmp/p"
        )
        assert project.tracker_kind is None

    def test_github_issues_tracker_kind(self):
        project = _make_project(tracker_kind="github_issues")
        assert project.tracker_kind == "github_issues"

    def test_tracker_kind_emitted_in_to_dict_when_set(self):
        project = _make_project(tracker_kind="github_issues")
        d = project.to_dict()
        assert d.get("tracker_kind") == "github_issues"

    def test_tracker_kind_absent_in_to_dict_when_none(self):
        project = _make_project(tracker_kind=None)
        d = project.to_dict()
        assert "tracker_kind" not in d

    def test_from_dict_parses_tracker_kind(self):
        d = {
            "id": "p1",
            "name": "test",
            "repo_url": "https://github.com/x/y.git",
            "repo_path": "/tmp/p",
            "tracker_kind": "github_issues",
        }
        project = Project.from_dict(d)
        assert project.tracker_kind == "github_issues"

    def test_from_dict_tracker_kind_none_when_absent(self):
        d = {
            "id": "p1",
            "name": "test",
            "repo_url": "https://github.com/x/y.git",
            "repo_path": "/tmp/p",
        }
        project = Project.from_dict(d)
        assert project.tracker_kind is None

    def test_from_dict_strips_whitespace(self):
        d = {
            "id": "p1",
            "name": "test",
            "repo_url": "https://github.com/x/y.git",
            "repo_path": "/tmp/p",
            "tracker_kind": "  github_issues  ",
        }
        project = Project.from_dict(d)
        assert project.tracker_kind == "github_issues"

    def test_from_dict_empty_string_becomes_none(self):
        d = {
            "id": "p1",
            "name": "test",
            "repo_url": "https://github.com/x/y.git",
            "repo_path": "/tmp/p",
            "tracker_kind": "",
        }
        project = Project.from_dict(d)
        assert project.tracker_kind is None

    def test_roundtrip_github_issues(self):
        project = _make_project(tracker_kind="github_issues")
        d = project.to_dict()
        project2 = Project.from_dict(d)
        assert project2.tracker_kind == "github_issues"

    def test_to_safe_dict_includes_tracker_kind(self):
        project = _make_project(tracker_kind="github_issues")
        d = project.to_safe_dict()
        assert d.get("tracker_kind") == "github_issues"


# ---------------------------------------------------------------------------
# ensure_backlog_webhooks — tracker-aware guards
# ---------------------------------------------------------------------------


class TestEnsureBacklogWebhooksTrackerGuard:
    """ensure_backlog_webhooks skips github_issues projects."""

    def test_github_backed_project_skipped(self, tmp_path):
        """A project with tracker_kind='github_issues' must be skipped."""
        project = _make_project(
            project_id="gh-proj",
            repo_path=str(tmp_path),
            tracker_kind="github_issues",
        )
        store = _make_mock_project_store([project])

        with patch("oompah.backlog_webhooks.install_backlog_webhook_hook") as mock_install:
            results = ensure_backlog_webhooks(store, server_base_url="http://localhost:8080")

        assert results["gh-proj"] == "skipped: github_issues tracker"
        mock_install.assert_not_called()

    def test_legacy_backlog_project_installs_hook(self, tmp_path):
        """A project with tracker_kind=None (legacy) must still attempt installation."""
        repo = _make_git_repo(tmp_path)
        project = _make_project(
            project_id="bg-proj",
            repo_path=str(repo),
            tracker_kind=None,
        )
        store = _make_mock_project_store([project])

        with patch("oompah.backlog_webhooks.install_backlog_webhook_hook", return_value=True) as mock_install:
            results = ensure_backlog_webhooks(store, server_base_url="http://localhost:8080")

        assert results["bg-proj"] == "ok"
        mock_install.assert_called_once()

    def test_mixed_projects_only_backlog_installs(self, tmp_path):
        """GitHub-backed projects are skipped; Backlog ones get hooks."""
        repo = _make_git_repo(tmp_path)
        gh_project = _make_project(
            project_id="gh-proj",
            repo_path=str(repo),
            tracker_kind="github_issues",
        )
        bg_project = _make_project(
            project_id="bg-proj",
            repo_path=str(repo),
            tracker_kind=None,
        )
        store = _make_mock_project_store([gh_project, bg_project])

        with patch("oompah.backlog_webhooks.install_backlog_webhook_hook", return_value=True) as mock_install:
            results = ensure_backlog_webhooks(store, server_base_url="http://localhost:8080")

        assert results["gh-proj"] == "skipped: github_issues tracker"
        assert results["bg-proj"] == "ok"
        # install called only for the Backlog project
        assert mock_install.call_count == 1
        called_project_id = mock_install.call_args[1]["project_id"]
        assert called_project_id == "bg-proj"

    def test_github_project_skipped_before_git_directory_check(self, tmp_path):
        """GitHub projects are skipped before the .git directory check so that
        a migrated project without a local clone doesn't produce an error."""
        project = _make_project(
            project_id="gh-proj-no-git",
            repo_path="/nonexistent/path",
            tracker_kind="github_issues",
        )
        store = _make_mock_project_store([project])

        results = ensure_backlog_webhooks(store, server_base_url="http://localhost:8080")

        assert results["gh-proj-no-git"] == "skipped: github_issues tracker"

    def test_empty_tracker_kind_installs_hook(self, tmp_path):
        """tracker_kind='' (empty string, treated as None) still installs."""
        repo = _make_git_repo(tmp_path)
        # Create project with None (which is what an empty string parses to)
        project = _make_project(
            project_id="empty-kind",
            repo_path=str(repo),
            tracker_kind=None,
        )
        store = _make_mock_project_store([project])

        with patch("oompah.backlog_webhooks.install_backlog_webhook_hook", return_value=True) as mock_install:
            results = ensure_backlog_webhooks(store, server_base_url="http://localhost:8080")

        assert results["empty-kind"] == "ok"
        mock_install.assert_called_once()


# ---------------------------------------------------------------------------
# _install_backlog_hook_for_project (server) — tracker-aware guards
# ---------------------------------------------------------------------------


class TestInstallBacklogHookForProjectTrackerGuard:
    """_install_backlog_hook_for_project skips github_issues projects."""

    def _call_install(self, project):
        from oompah.server import _install_backlog_hook_for_project
        _install_backlog_hook_for_project(project)

    def test_github_backed_skips_installation(self):
        """No hook install attempt for tracker_kind='github_issues'."""
        project = _make_project(tracker_kind="github_issues")

        with patch("oompah.backlog_webhooks.install_backlog_webhook_hook") as mock_install:
            self._call_install(project)

        mock_install.assert_not_called()

    def test_legacy_backlog_calls_install(self):
        """tracker_kind=None triggers install attempt."""
        project = _make_project(tracker_kind=None)

        with patch("oompah.backlog_webhooks.install_backlog_webhook_hook") as mock_install:
            self._call_install(project)

        mock_install.assert_called_once()

    def test_github_backed_no_exception_raised(self):
        """Guard returns cleanly without raising for GitHub-backed projects."""
        project = _make_project(tracker_kind="github_issues")
        # Should not raise
        self._call_install(project)

    def test_mock_project_without_tracker_kind_attribute(self):
        """Projects without a tracker_kind attribute (e.g. old mock objects)
        default to installing the hook (safe fallback via getattr default=None)."""
        # MagicMock(spec=[]) has no allowed attributes; accessing .tracker_kind
        # raises AttributeError.  _install_backlog_hook_for_project uses getattr
        # with a None default, so it should NOT raise and should fall back to
        # attempting installation.
        project = MagicMock(spec=[])  # no attributes at all
        project.configure_mock(id="mock-proj")

        # Confirm getattr gives None (not AttributeError) on the raw object:
        import pytest as _pytest
        with _pytest.raises(AttributeError):
            _ = project.tracker_kind  # direct access raises…

        # …but _install_backlog_hook_for_project uses getattr(project, "tracker_kind", None)
        with patch("oompah.backlog_webhooks.install_backlog_webhook_hook") as mock_install:
            self._call_install(project)

        # Fallback: should attempt install (not skip)
        mock_install.assert_called_once()


# ---------------------------------------------------------------------------
# POST /api/v1/webhooks/backlog — GitHub-backed project receives "ignored"
# ---------------------------------------------------------------------------


@pytest.fixture
def client_github_project():
    """TestClient with a GitHub-backed project (tracker_kind='github_issues')."""
    from oompah.server import app, _api_cache

    project = _make_project(
        project_id="gh-proj",
        tracker_kind="github_issues",
        webhook_secret=None,
    )
    orch = MagicMock()
    orch.request_refresh = MagicMock()
    orch.project_store = MagicMock()
    orch.project_store.get = MagicMock(return_value=project)
    orch.project_store.sync_project_sources = MagicMock(
        return_value={"git": "ok", "backlog": "ok"}
    )

    with patch("oompah.server._orchestrator", orch):
        _api_cache.invalidate("issues:all")
        yield TestClient(app), orch


@pytest.fixture
def client_github_project_with_secret():
    """TestClient with a GitHub-backed project that has a webhook_secret set."""
    from oompah.server import app, _api_cache

    project = _make_project(
        project_id="gh-proj-secret",
        tracker_kind="github_issues",
        webhook_secret="super-secret",
    )
    orch = MagicMock()
    orch.request_refresh = MagicMock()
    orch.project_store = MagicMock()
    orch.project_store.get = MagicMock(return_value=project)
    orch.project_store.sync_project_sources = MagicMock(
        return_value={"git": "ok"}
    )

    with patch("oompah.server._orchestrator", orch):
        _api_cache.invalidate("issues:all")
        yield TestClient(app), orch


class TestBacklogWebhookGitHubBackedIgnored:
    """Backlog webhook receipts for GitHub-backed projects return ignored."""

    def test_github_backed_returns_200_ignored(self, client_github_project):
        client, orch = client_github_project
        payload = _backlog_payload(project_id="gh-proj")
        resp = client.post(
            "/api/v1/webhooks/backlog",
            json=payload,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["action"] == "ignored"
        assert body["reason"] == "github_issues tracker"
        assert body["project_id"] == "gh-proj"

    def test_github_backed_does_not_trigger_refresh(self, client_github_project):
        """request_refresh must NOT be called for GitHub-backed webhooks."""
        client, orch = client_github_project
        payload = _backlog_payload(project_id="gh-proj")
        client.post("/api/v1/webhooks/backlog", json=payload)
        orch.request_refresh.assert_not_called()

    def test_github_backed_does_not_trigger_sync(self, client_github_project):
        """No background sync thread for GitHub-backed webhook receipts."""
        client, orch = client_github_project
        payload = _backlog_payload(project_id="gh-proj")
        with patch("threading.Thread") as mock_thread:
            client.post("/api/v1/webhooks/backlog", json=payload)
        mock_thread.assert_not_called()

    def test_github_backed_does_not_invalidate_cache(self, client_github_project):
        """Cache must NOT be invalidated for GitHub-backed webhook receipts."""
        from oompah.server import _api_cache
        client, orch = client_github_project
        payload = _backlog_payload(project_id="gh-proj")
        with patch.object(_api_cache, "invalidate") as mock_inv, \
             patch.object(_api_cache, "invalidate_prefix") as mock_pfx:
            client.post("/api/v1/webhooks/backlog", json=payload)
        mock_inv.assert_not_called()
        mock_pfx.assert_not_called()

    def test_github_backed_with_secret_returns_ignored_before_auth(
        self, client_github_project_with_secret
    ):
        """The ignored guard fires before HMAC validation so stale hooks
        that don't carry a signature still receive a clean 200 response."""
        client, orch = client_github_project_with_secret
        payload = _backlog_payload(project_id="gh-proj-secret")
        # Send without any signature header — would normally fail HMAC check.
        resp = client.post("/api/v1/webhooks/backlog", json=payload)
        assert resp.status_code == 200
        assert resp.json()["action"] == "ignored"

    def test_legacy_backlog_project_still_processed(self):
        """Sanity check: a non-GitHub project still goes through normal flow."""
        from oompah.server import app, _api_cache

        project = _make_project(
            project_id="bg-proj",
            tracker_kind=None,
            webhook_secret=None,
        )
        orch = MagicMock()
        orch.request_refresh = MagicMock()
        orch.project_store = MagicMock()
        orch.project_store.get = MagicMock(return_value=project)
        orch.project_store.sync_project_sources = MagicMock(
            return_value={"git": "ok", "backlog": "ok"}
        )

        with patch("oompah.server._orchestrator", orch):
            _api_cache.invalidate("issues:all")
            client = TestClient(app)
            payload = _backlog_payload(project_id="bg-proj")
            resp = client.post("/api/v1/webhooks/backlog", json=payload)

        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        # Normal flow returns "processed", not "ignored"
        assert body["action"] == "processed"
        orch.request_refresh.assert_called_once()
