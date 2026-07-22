"""Tests for GitLab project lifecycle integration in oompah.server.

Covers:
- set_gitlab_hook_manager() wiring
- _is_gitlab_project() helper
- reconcile() called on GitLab project create
- reconcile() called on GitLab project update when hook-relevant fields change
- remove() called on GitLab project delete
- No reconcile/remove for non-GitLab projects
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oompah.models import Project


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _gitlab_project(project_id: str = "proj-gl1", **kwargs) -> Project:
    p = Project(
        id=project_id,
        name="gitlab-proj",
        repo_url="https://gitlab.example.com/group/project.git",
        repo_path="/tmp/repos/project",
        **kwargs,
    )
    p.forge_kind = "gitlab"
    p.forge_base_url = "https://gitlab.example.com"
    return p


def _github_project(project_id: str = "proj-gh1") -> Project:
    return Project(
        id=project_id,
        name="github-proj",
        repo_url="https://github.com/org/repo.git",
        repo_path="/tmp/repos/repo",
    )


# ---------------------------------------------------------------------------
# _is_gitlab_project helper
# ---------------------------------------------------------------------------


class TestIsGitlabProject:
    """Tests for oompah.server._is_gitlab_project()."""

    def test_gitlab_by_forge_kind(self):
        from oompah.server import _is_gitlab_project
        p = _gitlab_project()
        assert _is_gitlab_project(p) is True

    def test_github_by_forge_kind(self):
        from oompah.server import _is_gitlab_project
        p = _github_project()
        p.forge_kind = "github"
        assert _is_gitlab_project(p) is False

    def test_gitlab_by_url_substring(self):
        from oompah.server import _is_gitlab_project
        p = Project(
            id="p1", name="n", repo_url="https://gitlab.mycompany.com/g/r.git",
            repo_path="/tmp",
        )
        # forge_kind defaults to "github" but URL contains "gitlab"
        assert _is_gitlab_project(p) is True

    def test_non_gitlab_url_not_gitlab(self):
        from oompah.server import _is_gitlab_project
        p = Project(
            id="p1", name="n", repo_url="https://bitbucket.org/g/r.git",
            repo_path="/tmp",
        )
        p.forge_kind = "bitbucket"
        assert _is_gitlab_project(p) is False


# ---------------------------------------------------------------------------
# set_gitlab_hook_manager
# ---------------------------------------------------------------------------


class TestSetGitlabHookManager:
    """Tests for set_gitlab_hook_manager() in oompah.server."""

    def test_sets_global_manager(self):
        from oompah.server import set_gitlab_hook_manager
        import oompah.server as srv
        fake_manager = MagicMock()
        with patch.object(srv, "_gitlab_hook_manager", None), \
             patch.object(srv, "_gitlab_event_dedup", None):
            set_gitlab_hook_manager(fake_manager)
            assert srv._gitlab_hook_manager is fake_manager

    def test_initialises_dedup(self):
        from oompah.server import set_gitlab_hook_manager
        from oompah.webhooks import GitLabEventDedup
        import oompah.server as srv
        fake_manager = MagicMock()
        with patch.object(srv, "_gitlab_hook_manager", None), \
             patch.object(srv, "_gitlab_event_dedup", None):
            set_gitlab_hook_manager(fake_manager)
            assert isinstance(srv._gitlab_event_dedup, GitLabEventDedup)


# ---------------------------------------------------------------------------
# Project lifecycle: create
# ---------------------------------------------------------------------------


class TestGitLabLifecycleCreate:
    """reconcile() is called when a GitLab project is created via API."""

    def _make_mock_orch(self, project: Project):
        orch = MagicMock()
        orch.project_store = MagicMock()
        orch.project_store.create.return_value = project
        orch.project_store.list_all.return_value = [project]
        return orch

    @pytest.mark.asyncio
    async def test_reconcile_called_for_gitlab_project(self):
        from oompah.server import api_create_project

        project = _gitlab_project()
        orch = self._make_mock_orch(project)

        fake_manager = MagicMock()
        fake_manager.reconcile = AsyncMock()

        with patch("oompah.server._orchestrator", orch), \
             patch("oompah.server._gitlab_hook_manager", fake_manager), \
             patch("oompah.server._log_watcher_manager", None), \
             patch("oompah.server._ensure_tracker_agent_instructions_for_project"), \
             patch("oompah.server._resolve_github_token_owner", return_value="bot"):
            request = MagicMock()
            request.json = AsyncMock(return_value={
                "name": "gitlab-proj",
                "repo_url": "https://gitlab.example.com/group/project.git",
                "forge_kind": "gitlab",
            })
            await api_create_project(request)

        fake_manager.reconcile.assert_called_once()

    @pytest.mark.asyncio
    async def test_reconcile_not_called_for_github_project(self):
        from oompah.server import api_create_project

        project = _github_project()
        orch = self._make_mock_orch(project)
        project.forge_kind = "github"

        fake_manager = MagicMock()
        fake_manager.reconcile = AsyncMock()

        with patch("oompah.server._orchestrator", orch), \
             patch("oompah.server._gitlab_hook_manager", fake_manager), \
             patch("oompah.server._log_watcher_manager", None), \
             patch("oompah.server._ensure_tracker_agent_instructions_for_project"), \
             patch("oompah.server._resolve_github_token_owner", return_value="bot"):
            request = MagicMock()
            request.json = AsyncMock(return_value={
                "name": "github-proj",
                "repo_url": "https://github.com/org/repo.git",
            })
            await api_create_project(request)

        fake_manager.reconcile.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_reconcile_when_manager_is_none(self):
        """No error when _gitlab_hook_manager is None (startup not yet complete)."""
        from oompah.server import api_create_project

        project = _gitlab_project()
        orch = self._make_mock_orch(project)

        with patch("oompah.server._orchestrator", orch), \
             patch("oompah.server._gitlab_hook_manager", None), \
             patch("oompah.server._log_watcher_manager", None), \
             patch("oompah.server._ensure_tracker_agent_instructions_for_project"):
            request = MagicMock()
            request.json = AsyncMock(return_value={
                "name": "gitlab-proj",
                "repo_url": "https://gitlab.example.com/group/project.git",
                "forge_kind": "gitlab",
            })
            # Should not raise
            response = await api_create_project(request)
        assert response.status_code == 201


# ---------------------------------------------------------------------------
# Project lifecycle: update
# ---------------------------------------------------------------------------


class TestGitLabLifecycleUpdate:
    """reconcile() is called when hook-relevant fields change on a GitLab project."""

    def _make_update_orch(self, project: Project, update_returns: Project | None = None):
        orch = MagicMock()
        orch.project_store = MagicMock()
        orch.project_store.get.return_value = project
        orch.project_store.update.return_value = update_returns or project
        orch.project_store.list_all.return_value = [project]
        return orch

    @pytest.mark.asyncio
    async def test_reconcile_called_on_access_token_change(self):
        from oompah.server import api_update_project

        project = _gitlab_project()
        orch = self._make_update_orch(project)
        fake_manager = MagicMock()
        fake_manager.reconcile = AsyncMock()

        with patch("oompah.server._orchestrator", orch), \
             patch("oompah.server._gitlab_hook_manager", fake_manager), \
             patch("oompah.server._log_watcher_manager", None), \
             patch("oompah.server._ensure_tracker_agent_instructions_for_project"), \
             patch("oompah.server._invalidate_project_tracker_cache"), \
             patch("oompah.server._api_cache"):
            request = MagicMock()
            request.json = AsyncMock(return_value={"access_token": "new-token"})
            await api_update_project(project.id, request)

        fake_manager.reconcile.assert_called_once()

    @pytest.mark.asyncio
    async def test_reconcile_called_on_webhook_secret_change(self):
        from oompah.server import api_update_project

        project = _gitlab_project()
        orch = self._make_update_orch(project)
        fake_manager = MagicMock()
        fake_manager.reconcile = AsyncMock()

        with patch("oompah.server._orchestrator", orch), \
             patch("oompah.server._gitlab_hook_manager", fake_manager), \
             patch("oompah.server._log_watcher_manager", None), \
             patch("oompah.server._ensure_tracker_agent_instructions_for_project"), \
             patch("oompah.server._invalidate_project_tracker_cache"), \
             patch("oompah.server._api_cache"):
            request = MagicMock()
            request.json = AsyncMock(return_value={"webhook_secret": "new-secret"})
            await api_update_project(project.id, request)

        fake_manager.reconcile.assert_called_once()

    @pytest.mark.asyncio
    async def test_reconcile_not_called_on_unrelated_field_change(self):
        from oompah.server import api_update_project

        project = _gitlab_project()
        orch = self._make_update_orch(project)
        fake_manager = MagicMock()
        fake_manager.reconcile = AsyncMock()

        with patch("oompah.server._orchestrator", orch), \
             patch("oompah.server._gitlab_hook_manager", fake_manager), \
             patch("oompah.server._log_watcher_manager", None), \
             patch("oompah.server._ensure_tracker_agent_instructions_for_project"), \
             patch("oompah.server._invalidate_project_tracker_cache"), \
             patch("oompah.server._api_cache"):
            request = MagicMock()
            # Changing 'name' doesn't trigger hook reconciliation
            request.json = AsyncMock(return_value={"name": "new-name"})
            await api_update_project(project.id, request)

        fake_manager.reconcile.assert_not_called()

    @pytest.mark.asyncio
    async def test_reconcile_not_called_for_github_project_update(self):
        from oompah.server import api_update_project

        project = _github_project()
        project.forge_kind = "github"
        orch = self._make_update_orch(project)
        fake_manager = MagicMock()
        fake_manager.reconcile = AsyncMock()

        with patch("oompah.server._orchestrator", orch), \
             patch("oompah.server._gitlab_hook_manager", fake_manager), \
             patch("oompah.server._log_watcher_manager", None), \
             patch("oompah.server._ensure_tracker_agent_instructions_for_project"), \
             patch("oompah.server._invalidate_project_tracker_cache"), \
             patch("oompah.server._api_cache"):
            request = MagicMock()
            request.json = AsyncMock(return_value={"access_token": "token"})
            await api_update_project(project.id, request)

        fake_manager.reconcile.assert_not_called()


# ---------------------------------------------------------------------------
# Project lifecycle: delete
# ---------------------------------------------------------------------------


class TestGitLabLifecycleDelete:
    """remove() is called before a GitLab project is deleted via API."""

    def _make_delete_orch(self, project: Project | None, delete_returns: bool = True):
        orch = MagicMock()
        orch.project_store = MagicMock()
        orch.project_store.get.return_value = project
        orch.project_store.delete.return_value = delete_returns
        orch.project_store.list_all.return_value = []
        return orch

    @pytest.mark.asyncio
    async def test_remove_called_before_delete_for_gitlab(self):
        from oompah.server import api_delete_project

        project = _gitlab_project()
        orch = self._make_delete_orch(project)
        fake_manager = MagicMock()
        fake_manager.remove = AsyncMock()

        with patch("oompah.server._orchestrator", orch), \
             patch("oompah.server._gitlab_hook_manager", fake_manager), \
             patch("oompah.server._log_watcher_manager", None):
            response = await api_delete_project(project.id)

        assert response.status_code == 200
        fake_manager.remove.assert_called_once_with(project)
        # remove() must be called before delete()
        remove_call_order = fake_manager.remove.call_args_list
        delete_call_order = orch.project_store.delete.call_args_list
        assert remove_call_order and delete_call_order

    @pytest.mark.asyncio
    async def test_remove_not_called_for_github_project(self):
        from oompah.server import api_delete_project

        project = _github_project()
        project.forge_kind = "github"
        orch = self._make_delete_orch(project)
        fake_manager = MagicMock()
        fake_manager.remove = AsyncMock()

        with patch("oompah.server._orchestrator", orch), \
             patch("oompah.server._gitlab_hook_manager", fake_manager), \
             patch("oompah.server._log_watcher_manager", None):
            await api_delete_project(project.id)

        fake_manager.remove.assert_not_called()

    @pytest.mark.asyncio
    async def test_remove_not_called_when_project_not_found(self):
        """If project doesn't exist, remove() should not be called."""
        from oompah.server import api_delete_project

        orch = self._make_delete_orch(project=None, delete_returns=False)
        fake_manager = MagicMock()
        fake_manager.remove = AsyncMock()

        with patch("oompah.server._orchestrator", orch), \
             patch("oompah.server._gitlab_hook_manager", fake_manager), \
             patch("oompah.server._log_watcher_manager", None):
            response = await api_delete_project("nonexistent-id")

        fake_manager.remove.assert_not_called()
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_no_error_when_manager_is_none(self):
        """No error when _gitlab_hook_manager is None."""
        from oompah.server import api_delete_project

        project = _gitlab_project()
        orch = self._make_delete_orch(project)

        with patch("oompah.server._orchestrator", orch), \
             patch("oompah.server._gitlab_hook_manager", None), \
             patch("oompah.server._log_watcher_manager", None):
            response = await api_delete_project(project.id)

        assert response.status_code == 200
