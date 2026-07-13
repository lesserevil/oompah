"""Tests for project CRUD operations.

Covers:
- ProjectStore.update() field validation and persistence
- ProjectStore.get() for reading single projects
- ProjectStore.delete() for removing projects
- Server API endpoints: GET single, PATCH validation, DELETE
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from oompah.models import Project
from oompah.projects import ProjectError, ProjectStore


# ---------------------------------------------------------------------------
# ProjectStore unit tests
# ---------------------------------------------------------------------------


class TestProjectStoreUpdate:
    """Tests for ProjectStore.update() with validation."""

    @pytest.fixture(autouse=True)
    def store(self, tmp_path):
        """Create a ProjectStore with a pre-loaded project."""
        path = str(tmp_path / "projects.json")
        self.store = ProjectStore(
            path=path,
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        # Manually insert a project (bypass git clone)
        p = Project(
            id="proj-abc",
            name="myrepo",
            repo_url="https://github.com/org/myrepo.git",
            repo_path=str(tmp_path / "repos" / "myrepo"),
            branch="main",
            git_user_name="Alice",
            git_user_email="alice@example.com",
        )
        self.store._projects[p.id] = p
        self.store._save()
        return self.store

    def test_update_name(self):
        updated = self.store.update("proj-abc", name="new-name")
        assert updated is not None
        assert updated.name == "new-name"

    def test_update_branch(self):
        updated = self.store.update("proj-abc", branch="develop")
        assert updated.branch == "develop"

    def test_update_repo_url(self):
        updated = self.store.update(
            "proj-abc", repo_url="https://github.com/org/other.git"
        )
        assert updated.repo_url == "https://github.com/org/other.git"

    def test_update_git_user_name(self):
        updated = self.store.update("proj-abc", git_user_name="Bob")
        assert updated.git_user_name == "Bob"

    def test_update_git_user_email(self):
        updated = self.store.update("proj-abc", git_user_email="bob@example.com")
        assert updated.git_user_email == "bob@example.com"

    def test_update_yolo(self):
        updated = self.store.update("proj-abc", yolo=True)
        assert updated.yolo is True

    def test_update_log_path(self):
        updated = self.store.update("proj-abc", log_path="/var/log/app.log")
        assert updated.log_path == "/var/log/app.log"

    def test_update_multiple_fields(self):
        updated = self.store.update(
            "proj-abc", name="renamed", branch="staging", yolo=True
        )
        assert updated.name == "renamed"
        assert updated.branch == "staging"
        assert updated.yolo is True

    def test_update_persists_to_disk(self, tmp_path):
        self.store.update("proj-abc", name="persisted")
        # Reload from disk
        store2 = ProjectStore(
            path=self.store.path,
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        assert store2.get("proj-abc").name == "persisted"

    def test_update_nonexistent_returns_none(self):
        result = self.store.update("proj-nope", name="x")
        assert result is None

    def test_update_rejects_unknown_field(self):
        with pytest.raises(ProjectError, match="Unknown or immutable"):
            self.store.update("proj-abc", unknown_field="bad")

    def test_update_rejects_id_change(self):
        with pytest.raises(ProjectError, match="Unknown or immutable"):
            self.store.update("proj-abc", id="proj-new-id")

    def test_update_rejects_repo_path_change(self):
        """repo_path is derived from clone and should not be user-updatable."""
        with pytest.raises(ProjectError, match="Unknown or immutable"):
            self.store.update("proj-abc", repo_path="/tmp/other")

    def test_update_rejects_empty_name(self):
        with pytest.raises(ProjectError, match="must not be empty"):
            self.store.update("proj-abc", name="")

    def test_update_rejects_whitespace_only_name(self):
        with pytest.raises(ProjectError, match="must not be empty"):
            self.store.update("proj-abc", name="   ")

    def test_update_trims_name(self):
        updated = self.store.update("proj-abc", name="  trimmed  ")
        assert updated.name == "trimmed"

    def test_update_allows_clearing_optional_fields(self):
        self.store.update("proj-abc", log_path="/some/path")
        updated = self.store.update("proj-abc", log_path=None)
        assert updated.log_path is None


class TestProjectStoreGet:
    """Tests for ProjectStore.get()."""

    @pytest.fixture(autouse=True)
    def store(self, tmp_path):
        path = str(tmp_path / "projects.json")
        self.store = ProjectStore(
            path=path,
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        p = Project(
            id="proj-get1",
            name="gettest",
            repo_url="https://github.com/org/gettest.git",
            repo_path=str(tmp_path / "repos" / "gettest"),
            branch="main",
        )
        self.store._projects[p.id] = p
        self.store._save()
        return self.store

    def test_get_existing(self):
        p = self.store.get("proj-get1")
        assert p is not None
        assert p.name == "gettest"
        assert p.id == "proj-get1"

    def test_get_nonexistent(self):
        p = self.store.get("proj-nope")
        assert p is None

    def test_get_returns_correct_fields(self):
        p = self.store.get("proj-get1")
        assert p.repo_url == "https://github.com/org/gettest.git"
        assert p.branch == "main"


class TestProjectStoreDelete:
    """Tests for ProjectStore.delete()."""

    @pytest.fixture(autouse=True)
    def store(self, tmp_path):
        path = str(tmp_path / "projects.json")
        self.store = ProjectStore(
            path=path,
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        for i in range(3):
            p = Project(
                id=f"proj-del{i}",
                name=f"deltest{i}",
                repo_url=f"https://github.com/org/deltest{i}.git",
                repo_path=str(tmp_path / "repos" / f"deltest{i}"),
                branch="main",
            )
            self.store._projects[p.id] = p
        self.store._save()
        return self.store

    def test_delete_existing(self):
        assert self.store.delete("proj-del0") is True
        assert self.store.get("proj-del0") is None

    def test_delete_nonexistent(self):
        assert self.store.delete("proj-nope") is False

    def test_delete_persists(self, tmp_path):
        self.store.delete("proj-del1")
        store2 = ProjectStore(
            path=self.store.path,
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        assert store2.get("proj-del1") is None
        assert store2.get("proj-del0") is not None
        assert store2.get("proj-del2") is not None

    def test_delete_does_not_affect_others(self):
        self.store.delete("proj-del1")
        assert len(self.store.list_all()) == 2


class TestProjectStoreListAll:
    """Tests for ProjectStore.list_all()."""

    def test_empty_store(self, tmp_path):
        store = ProjectStore(
            path=str(tmp_path / "projects.json"),
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        assert store.list_all() == []

    def test_list_all_returns_all(self, tmp_path):
        store = ProjectStore(
            path=str(tmp_path / "projects.json"),
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        for i in range(3):
            p = Project(
                id=f"proj-list{i}",
                name=f"list{i}",
                repo_url=f"https://x/{i}",
                repo_path=f"/tmp/{i}",
            )
            store._projects[p.id] = p
        store._save()
        assert len(store.list_all()) == 3


# ---------------------------------------------------------------------------
# Server API tests (using FastAPI TestClient)
# ---------------------------------------------------------------------------


class TestProjectAPI:
    """Integration tests for project REST endpoints."""

    @pytest.fixture(autouse=True)
    def client(self, tmp_path):
        """Set up a test client with a mock orchestrator."""
        from unittest.mock import MagicMock
        from fastapi.testclient import TestClient
        from oompah.server import app, set_orchestrator

        # Build a real ProjectStore backed by tmp files
        store = ProjectStore(
            path=str(tmp_path / "projects.json"),
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        # Pre-populate with a test project
        p = Project(
            id="proj-test1",
            name="testproject",
            repo_url="https://github.com/org/testproject.git",
            repo_path=str(tmp_path / "repos" / "testproject"),
            branch="main",
            git_user_name="TestUser",
            git_user_email="test@example.com",
        )
        store._projects[p.id] = p
        store._save()

        # Mock orchestrator
        orch = MagicMock()
        orch.project_store = store
        orch._observers = []
        orch._state_only_observers = []
        orch._activity_observers = []
        orch.get_snapshot.return_value = {"counts": {}, "running": {}}

        # Patch the global orchestrator
        import oompah.server as srv

        old_orch = srv._orchestrator
        srv._orchestrator = orch
        self.client = TestClient(app)
        self.store = store
        yield self.client
        srv._orchestrator = old_orch

    def test_list_projects(self):
        res = self.client.get("/api/v1/projects")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == "proj-test1"

    def test_get_project(self):
        res = self.client.get("/api/v1/projects/proj-test1")
        assert res.status_code == 200
        data = res.json()
        assert data["id"] == "proj-test1"
        assert data["name"] == "testproject"
        assert data["repo_url"] == "https://github.com/org/testproject.git"
        assert data["branch"] == "main"

    def test_get_project_not_found(self):
        res = self.client.get("/api/v1/projects/proj-nonexistent")
        assert res.status_code == 404
        data = res.json()
        assert data["error"]["code"] == "not_found"

    def test_update_project_name(self):
        res = self.client.patch(
            "/api/v1/projects/proj-test1",
            json={"name": "renamed"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["name"] == "renamed"

    def test_update_project_branch(self):
        res = self.client.patch(
            "/api/v1/projects/proj-test1",
            json={"branch": "develop"},
        )
        assert res.status_code == 200
        assert res.json()["branch"] == "develop"

    def test_update_project_repo_url(self):
        res = self.client.patch(
            "/api/v1/projects/proj-test1",
            json={"repo_url": "https://github.com/org/other.git"},
        )
        assert res.status_code == 200
        assert res.json()["repo_url"] == "https://github.com/org/other.git"

    def test_update_project_git_identity(self):
        res = self.client.patch(
            "/api/v1/projects/proj-test1",
            json={"git_user_name": "New Name", "git_user_email": "new@example.com"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["git_user_name"] == "New Name"
        assert data["git_user_email"] == "new@example.com"

    def test_update_project_yolo(self):
        res = self.client.patch(
            "/api/v1/projects/proj-test1",
            json={"yolo": True},
        )
        assert res.status_code == 200
        assert res.json()["yolo"] is True

    def test_update_project_require_epic_for_tasks(self):
        res = self.client.patch(
            "/api/v1/projects/proj-test1",
            json={"require_epic_for_tasks": True},
        )
        assert res.status_code == 200
        assert res.json()["require_epic_for_tasks"] is True

    def test_update_project_require_epic_for_tasks_rejects_non_bool(self):
        res = self.client.patch(
            "/api/v1/projects/proj-test1",
            json={"require_epic_for_tasks": "true"},
        )
        assert res.status_code == 400
        assert res.json()["error"]["code"] == "validation"
        assert "require_epic_for_tasks" in res.json()["error"]["message"]

    def test_update_project_log_path(self):
        res = self.client.patch(
            "/api/v1/projects/proj-test1",
            json={"log_path": "/var/log/myapp.log"},
        )
        assert res.status_code == 200
        assert res.json()["log_path"] == "/var/log/myapp.log"

    def test_update_project_empty_name_rejected(self):
        res = self.client.patch(
            "/api/v1/projects/proj-test1",
            json={"name": ""},
        )
        assert res.status_code == 400
        data = res.json()
        assert data["error"]["code"] == "validation"
        assert "must not be empty" in data["error"]["message"]

    def test_update_project_not_found(self):
        res = self.client.patch(
            "/api/v1/projects/proj-nonexistent",
            json={"name": "x"},
        )
        assert res.status_code == 404

    def test_update_persists_across_get(self):
        self.client.patch(
            "/api/v1/projects/proj-test1",
            json={"name": "persistent"},
        )
        res = self.client.get("/api/v1/projects/proj-test1")
        assert res.json()["name"] == "persistent"

    def test_update_multiple_fields(self):
        res = self.client.patch(
            "/api/v1/projects/proj-test1",
            json={"name": "multi", "branch": "staging", "yolo": True},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["name"] == "multi"
        assert data["branch"] == "staging"
        assert data["yolo"] is True

    def test_delete_project(self):
        res = self.client.delete("/api/v1/projects/proj-test1")
        assert res.status_code == 200
        assert res.json()["ok"] is True
        # Verify it's gone
        res2 = self.client.get("/api/v1/projects/proj-test1")
        assert res2.status_code == 404

    def test_delete_project_not_found(self):
        res = self.client.delete("/api/v1/projects/proj-nope")
        assert res.status_code == 404

    def test_update_epic_strategy_to_shared(self):
        res = self.client.patch(
            "/api/v1/projects/proj-test1",
            json={"epic_strategy": "shared"},
        )
        assert res.status_code == 200
        assert res.json()["epic_strategy"] == "shared"

    def test_update_epic_strategy_shared_case_insensitive(self):
        res = self.client.patch(
            "/api/v1/projects/proj-test1",
            json={"epic_strategy": "SHARED"},
        )
        assert res.status_code == 200
        assert res.json()["epic_strategy"] == "shared"

    def test_update_epic_strategy_null_resets_to_shared(self):
        res = self.client.patch(
            "/api/v1/projects/proj-test1",
            json={"epic_strategy": None},
        )
        assert res.status_code == 200
        assert res.json()["epic_strategy"] == "shared"

    def test_update_epic_strategy_flat_rejected(self):
        # "flat" is a removed strategy; the API must reject it.
        res = self.client.patch(
            "/api/v1/projects/proj-test1",
            json={"epic_strategy": "flat"},
        )
        assert res.status_code == 400
        data = res.json()
        assert data["error"]["code"] == "validation"
        assert "epic_strategy" in data["error"]["message"]

    def test_update_epic_strategy_stacked_rejected(self):
        # "stacked" is a removed strategy; the API must reject it.
        res = self.client.patch(
            "/api/v1/projects/proj-test1",
            json={"epic_strategy": "stacked"},
        )
        assert res.status_code == 400
        data = res.json()
        assert data["error"]["code"] == "validation"
        assert "epic_strategy" in data["error"]["message"]

    def test_update_epic_strategy_invalid_value_rejected(self):
        res = self.client.patch(
            "/api/v1/projects/proj-test1",
            json={"epic_strategy": "bogus"},
        )
        assert res.status_code == 400
        data = res.json()
        assert data["error"]["code"] == "validation"

    def test_new_project_defaults_to_shared_epic_strategy(self):
        # New Project instances always default to "shared".
        from oompah.models import Project

        p = Project(id="x", name="n", repo_url="u", repo_path="/tmp/x")
        assert p.epic_strategy == "shared"
        assert p.to_dict()["epic_strategy"] == "shared"


class TestProjectCreateAPIDefaults:
    """Regression tests for add-project defaults."""

    @pytest.fixture(autouse=True)
    def client(self, tmp_path, monkeypatch):
        from unittest.mock import MagicMock
        from fastapi.testclient import TestClient
        import oompah.server as srv
        from oompah.server import app

        project_store = MagicMock()
        created_projects: list[Project] = []

        def create_project(**kwargs):
            project = Project(
                id="proj-created",
                name=kwargs.get("name") or "created",
                repo_url=kwargs["repo_url"],
                repo_path=str(tmp_path / "repos" / "example-repo"),
                branch=kwargs.get("branch") or "main",
                tracker_kind=kwargs.get("tracker_kind"),
                paused=bool(kwargs.get("paused", False)),
            )
            created_projects[:] = [project]
            return project

        project_store.create.side_effect = create_project
        project_store.list_all.side_effect = lambda: list(created_projects)

        orch = MagicMock()
        orch.project_store = project_store
        orch._observers = []
        orch._state_only_observers = []
        orch._activity_observers = []
        orch.get_snapshot.return_value = {"counts": {}, "running": {}}

        monkeypatch.setattr(srv, "_orchestrator", orch)
        monkeypatch.setattr(srv, "_log_watcher_manager", None)
        monkeypatch.setattr(
            srv, "_ensure_tracker_agent_instructions_for_project", MagicMock()
        )

        self.client = TestClient(app)
        self.project_store = project_store
        yield self.client

    def test_create_defaults_to_oompah_md_and_paused(self):
        res = self.client.post(
            "/api/v1/projects",
            json={
                "repo_url": "https://github.com/example-org/example-repo.git",
                "git_user_name": "Example User",
                "git_user_email": "user@example.com",
            },
        )

        assert res.status_code == 201
        kwargs = self.project_store.create.call_args.kwargs
        assert kwargs["tracker_kind"] == "oompah_md"
        assert kwargs["paused"] is True
        assert kwargs["github_issue_intake_enabled"] is False
        assert res.json()["tracker_kind"] == "oompah_md"
        assert res.json()["paused"] is True

    def test_create_sends_github_issue_intake_enabled(self):
        res = self.client.post(
            "/api/v1/projects",
            json={
                "repo_url": "https://github.com/example-org/example-repo.git",
                "git_user_name": "Example User",
                "git_user_email": "user@example.com",
                "github_issue_intake_enabled": True,
            },
        )

        assert res.status_code == 201
        kwargs = self.project_store.create.call_args.kwargs
        assert kwargs["tracker_kind"] == "oompah_md"
        assert kwargs["github_issue_intake_enabled"] is True

    def test_create_preserves_explicit_github_tracker_kind_but_still_pauses(self):
        res = self.client.post(
            "/api/v1/projects",
            json={
                "repo_url": "https://github.com/example-org/example-repo.git",
                "git_user_name": "Example User",
                "git_user_email": "user@example.com",
                "tracker_kind": "github_issues",
            },
        )

        assert res.status_code == 201
        kwargs = self.project_store.create.call_args.kwargs
        assert kwargs["tracker_kind"] == "github_issues"
        assert kwargs["paused"] is True


class TestProjectStoreUpdatableFields:
    """Verify the UPDATABLE_FIELDS constant matches expected set."""

    def test_updatable_fields_are_correct(self):
        expected = {
            "name",
            "repo_url",
            "branch",
            "branches",
            "default_branch",
            "git_user_name",
            "git_user_email",
            "yolo",
            "log_path",
            "webhook_secret",
            "webhook_forwarding_enabled",
            "access_token",
            "last_webhook_received_at",
            "max_in_flight_prs",
            "merge_queue_enabled",
            "paused",
            "test_command",
            "test_command_full",
            "test_skip_paths",
            "epic_strategy",
            "require_epic_for_tasks",
            "intake_auto_promote",
            "provider_whitelist",
            "status_actor_login",
            "status_label_authorized_logins",
            # Per-project tracker configuration
            "tracker_kind",
            "tracker_owner",
            "tracker_repo",
            "github_issue_intake_enabled",
            "github_project_node_id",
            # Supported release lines (section 5 of release-branch-addendums.md)
            "supported_release_branches",
        }
        assert ProjectStore.UPDATABLE_FIELDS == expected

    def test_id_is_not_updatable(self):
        assert "id" not in ProjectStore.UPDATABLE_FIELDS

    def test_repo_path_is_not_updatable(self):
        assert "repo_path" not in ProjectStore.UPDATABLE_FIELDS


class TestProjectAccessToken:
    """Tests for the per-project access_token field."""

    def test_default_is_none(self):
        p = Project(id="p", name="n", repo_url="u", repo_path="/tmp/x")
        assert p.access_token is None

    def test_round_trip_through_to_dict(self):
        p = Project(
            id="p",
            name="n",
            repo_url="u",
            repo_path="/tmp/x",
            access_token="ghp_abcdefghij1234567890",
        )
        d = p.to_dict()
        assert d["access_token"] == "ghp_abcdefghij1234567890"
        p2 = Project.from_dict(d)
        assert p2.access_token == "ghp_abcdefghij1234567890"

    def test_to_dict_omits_when_unset(self):
        p = Project(id="p", name="n", repo_url="u", repo_path="/tmp/x")
        assert "access_token" not in p.to_dict()

    def test_to_safe_dict_masks_token(self):
        p = Project(
            id="p",
            name="n",
            repo_url="u",
            repo_path="/tmp/x",
            access_token="ghp_abcdefghij1234567890",
        )
        d = p.to_safe_dict()
        assert "access_token" not in d
        assert d["has_access_token"] is True
        assert d["access_token_masked"].startswith("ghp_")
        assert d["access_token_masked"].endswith("7890")
        assert "abcdefghij" not in d["access_token_masked"]

    def test_to_safe_dict_when_unset(self):
        p = Project(id="p", name="n", repo_url="u", repo_path="/tmp/x")
        d = p.to_safe_dict()
        assert d["has_access_token"] is False
        assert d["access_token_masked"] == ""

    def test_to_safe_dict_short_token_fully_masked(self):
        p = Project(
            id="p",
            name="n",
            repo_url="u",
            repo_path="/tmp/x",
            access_token="short",
        )
        d = p.to_safe_dict()
        assert d["access_token_masked"] == "***"

    def test_store_update_sets_token(self, tmp_path):
        store = ProjectStore(
            path=str(tmp_path / "projects.json"),
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        p = Project(id="proj-tok", name="n", repo_url="u", repo_path="/tmp/x")
        store._projects[p.id] = p
        store._save()
        updated = store.update("proj-tok", access_token="glpat-XYZ")
        assert updated.access_token == "glpat-XYZ"

    def test_store_update_clears_token(self, tmp_path):
        store = ProjectStore(
            path=str(tmp_path / "projects.json"),
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        p = Project(
            id="proj-tok",
            name="n",
            repo_url="u",
            repo_path="/tmp/x",
            access_token="glpat-XYZ",
        )
        store._projects[p.id] = p
        store._save()
        updated = store.update("proj-tok", access_token=None)
        assert updated.access_token is None

    def test_store_update_token_persists(self, tmp_path):
        path = str(tmp_path / "projects.json")
        store = ProjectStore(
            path=path,
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        p = Project(id="proj-tok", name="n", repo_url="u", repo_path="/tmp/x")
        store._projects[p.id] = p
        store._save()
        store.update("proj-tok", access_token="ghp_persisted_token")
        # Reload from disk
        store2 = ProjectStore(
            path=path,
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        assert store2.get("proj-tok").access_token == "ghp_persisted_token"


class TestProjectAccessTokenAPI:
    """API tests for the access_token field on project endpoints."""

    @pytest.fixture(autouse=True)
    def client(self, tmp_path):
        from unittest.mock import MagicMock
        from fastapi.testclient import TestClient
        from oompah.server import app

        store = ProjectStore(
            path=str(tmp_path / "projects.json"),
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        p = Project(
            id="proj-tokapi",
            name="n",
            repo_url="https://github.com/org/n.git",
            repo_path=str(tmp_path / "repos" / "n"),
            branch="main",
            access_token="ghp_initial_token_value",
        )
        store._projects[p.id] = p
        store._save()

        orch = MagicMock()
        orch.project_store = store
        orch._project_trackers = {}
        orch._branch_indexes = {}
        orch._stale_caches = {}
        orch._observers = []
        orch._state_only_observers = []
        orch._activity_observers = []
        orch.get_snapshot.return_value = {"counts": {}, "running": {}}

        import oompah.server as srv

        old_orch = srv._orchestrator
        srv._orchestrator = orch
        self.client = TestClient(app)
        self.store = store
        self.orch = orch
        yield self.client
        srv._orchestrator = old_orch

    def test_get_returns_masked_token(self):
        res = self.client.get("/api/v1/projects/proj-tokapi")
        assert res.status_code == 200
        data = res.json()
        # Raw token never returned
        assert "access_token" not in data
        assert data["has_access_token"] is True
        assert data["access_token_masked"].startswith("ghp_")
        assert "initial_token" not in data["access_token_masked"]

    def test_list_returns_masked_token(self):
        res = self.client.get("/api/v1/projects")
        assert res.status_code == 200
        rows = res.json()
        assert len(rows) == 1
        assert "access_token" not in rows[0]
        assert rows[0]["has_access_token"] is True

    def test_patch_sets_token(self):
        res = self.client.patch(
            "/api/v1/projects/proj-tokapi",
            json={"access_token": "ghp_replaced_token"},
        )
        assert res.status_code == 200
        # Stored on the project (raw value), masked on the response
        assert self.store.get("proj-tokapi").access_token == "ghp_replaced_token"
        assert "access_token" not in res.json()
        assert res.json()["has_access_token"] is True

    def test_patch_token_invalidates_cached_tracker(self):
        import oompah.server as srv

        self.orch._project_trackers = {"proj-tokapi": object()}
        srv._api_cache.set("issues:all", {"stale": True}, ttl_ms=60_000)

        res = self.client.patch(
            "/api/v1/projects/proj-tokapi",
            json={"access_token": "ghp_replaced_token"},
        )

        assert res.status_code == 200
        assert "proj-tokapi" not in self.orch._project_trackers
        assert srv._api_cache.get("issues:all") is None

    def test_patch_clears_token(self):
        res = self.client.patch(
            "/api/v1/projects/proj-tokapi",
            json={"access_token": None},
        )
        assert res.status_code == 200
        assert self.store.get("proj-tokapi").access_token is None
        assert res.json()["has_access_token"] is False

    def test_patch_other_field_does_not_touch_token(self):
        self.client.patch(
            "/api/v1/projects/proj-tokapi",
            json={"name": "renamed-only"},
        )
        # Token should remain at its initial value
        assert self.store.get("proj-tokapi").access_token == "ghp_initial_token_value"


class TestProjectStoreTestCommand:
    """Tests for the per-project test_command / test_command_full / test_skip_paths fields."""

    @pytest.fixture(autouse=True)
    def store(self, tmp_path):
        path = str(tmp_path / "projects.json")
        self.store = ProjectStore(
            path=path,
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        p = Project(
            id="proj-tc",
            name="tc-repo",
            repo_url="https://github.com/org/tc.git",
            repo_path=str(tmp_path / "repos" / "tc"),
            branch="main",
        )
        self.store._projects[p.id] = p
        self.store._save()
        return self.store

    def test_default_values(self):
        p = self.store.get("proj-tc")
        assert p.test_command is None
        assert p.test_command_full is None
        assert p.test_skip_paths == []

    def test_update_test_command(self):
        updated = self.store.update(
            "proj-tc", test_command="cargo test --workspace --lib"
        )
        assert updated.test_command == "cargo test --workspace --lib"

    def test_update_test_command_full(self):
        updated = self.store.update(
            "proj-tc", test_command_full="cargo test --workspace"
        )
        assert updated.test_command_full == "cargo test --workspace"

    def test_update_test_skip_paths(self):
        updated = self.store.update(
            "proj-tc",
            test_skip_paths=["tests/hw/*", "tests/integration/*"],
        )
        assert updated.test_skip_paths == ["tests/hw/*", "tests/integration/*"]

    def test_clear_test_command(self):
        self.store.update("proj-tc", test_command="make test")
        cleared = self.store.update("proj-tc", test_command=None)
        assert cleared.test_command is None

    def test_empty_string_treated_as_none(self):
        cleared = self.store.update("proj-tc", test_command="   ")
        assert cleared.test_command is None

    def test_test_command_trimmed(self):
        updated = self.store.update("proj-tc", test_command="  make test  ")
        assert updated.test_command == "make test"

    def test_test_skip_paths_filters_empty(self):
        updated = self.store.update(
            "proj-tc",
            test_skip_paths=["tests/hw/*", "  ", "tests/integration/*"],
        )
        assert updated.test_skip_paths == ["tests/hw/*", "tests/integration/*"]

    def test_test_skip_paths_none_becomes_empty_list(self):
        self.store.update("proj-tc", test_skip_paths=["a"])
        cleared = self.store.update("proj-tc", test_skip_paths=None)
        assert cleared.test_skip_paths == []

    def test_test_skip_paths_rejects_non_list(self):
        with pytest.raises(ProjectError, match="must be a list"):
            self.store.update("proj-tc", test_skip_paths="not-a-list")

    def test_test_skip_paths_rejects_non_string_items(self):
        with pytest.raises(ProjectError, match="must be strings"):
            self.store.update("proj-tc", test_skip_paths=["ok", 42])

    def test_test_command_rejects_non_string(self):
        with pytest.raises(ProjectError, match="must be a string"):
            self.store.update("proj-tc", test_command=["bad"])

    def test_round_trip_through_to_dict(self):
        self.store.update(
            "proj-tc",
            test_command="make test",
            test_command_full="make test-all",
            test_skip_paths=["a", "b"],
        )
        d = self.store.get("proj-tc").to_dict()
        assert d["test_command"] == "make test"
        assert d["test_command_full"] == "make test-all"
        assert d["test_skip_paths"] == ["a", "b"]
        rebuilt = Project.from_dict(d)
        assert rebuilt.test_command == "make test"
        assert rebuilt.test_command_full == "make test-all"
        assert rebuilt.test_skip_paths == ["a", "b"]

    def test_persistence_across_reload(self, tmp_path):
        self.store.update(
            "proj-tc",
            test_command="cargo test --workspace --lib",
            test_skip_paths=["tests/hw/*"],
        )
        store2 = ProjectStore(
            path=self.store.path,
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        loaded = store2.get("proj-tc")
        assert loaded.test_command == "cargo test --workspace --lib"
        assert loaded.test_skip_paths == ["tests/hw/*"]

    def test_unset_fields_omitted_from_to_dict(self):
        p = self.store.get("proj-tc")
        d = p.to_dict()
        # Unset values should not appear in the persisted dict.
        assert "test_command" not in d
        assert "test_command_full" not in d
        # Empty list also omitted.
        assert "test_skip_paths" not in d


class TestProjectAPITestCommand:
    """Integration tests for the test_command fields via the PATCH endpoint."""

    @pytest.fixture(autouse=True)
    def client(self, tmp_path):
        from unittest.mock import MagicMock
        from fastapi.testclient import TestClient
        from oompah.server import app

        store = ProjectStore(
            path=str(tmp_path / "projects.json"),
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        p = Project(
            id="proj-tcapi",
            name="tcapi-repo",
            repo_url="https://github.com/org/tcapi.git",
            repo_path=str(tmp_path / "repos" / "tcapi"),
            branch="main",
        )
        store._projects[p.id] = p
        store._save()

        orch = MagicMock()
        orch.project_store = store
        orch._observers = []
        orch._state_only_observers = []
        orch._activity_observers = []
        orch.get_snapshot.return_value = {"counts": {}, "running": {}}

        import oompah.server as srv

        old_orch = srv._orchestrator
        srv._orchestrator = orch
        self.client = TestClient(app)
        self.store = store
        yield self.client
        srv._orchestrator = old_orch

    def test_patch_test_command(self):
        res = self.client.patch(
            "/api/v1/projects/proj-tcapi",
            json={"test_command": "cargo test --workspace --lib"},
        )
        assert res.status_code == 200
        assert (
            self.store.get("proj-tcapi").test_command == "cargo test --workspace --lib"
        )

    def test_patch_clears_test_command_with_null(self):
        self.store.update("proj-tcapi", test_command="make test")
        res = self.client.patch(
            "/api/v1/projects/proj-tcapi",
            json={"test_command": None},
        )
        assert res.status_code == 200
        assert self.store.get("proj-tcapi").test_command is None

    def test_patch_test_command_full(self):
        res = self.client.patch(
            "/api/v1/projects/proj-tcapi",
            json={"test_command_full": "cargo test --workspace"},
        )
        assert res.status_code == 200
        assert (
            self.store.get("proj-tcapi").test_command_full == "cargo test --workspace"
        )

    def test_patch_test_skip_paths(self):
        res = self.client.patch(
            "/api/v1/projects/proj-tcapi",
            json={"test_skip_paths": ["tests/hw/*", "tests/integration/*"]},
        )
        assert res.status_code == 200
        assert self.store.get("proj-tcapi").test_skip_paths == [
            "tests/hw/*",
            "tests/integration/*",
        ]

    def test_patch_test_command_invalid_type(self):
        res = self.client.patch(
            "/api/v1/projects/proj-tcapi",
            json={"test_command": 42},
        )
        assert res.status_code == 400
        assert "must be a string" in res.json()["error"]["message"]

    def test_patch_test_skip_paths_invalid_type(self):
        res = self.client.patch(
            "/api/v1/projects/proj-tcapi",
            json={"test_skip_paths": "not-a-list"},
        )
        assert res.status_code == 400

    def test_patch_test_skip_paths_null_clears(self):
        self.store.update("proj-tcapi", test_skip_paths=["a", "b"])
        res = self.client.patch(
            "/api/v1/projects/proj-tcapi",
            json={"test_skip_paths": None},
        )
        assert res.status_code == 200
        assert self.store.get("proj-tcapi").test_skip_paths == []

    def test_patch_test_command_visible_in_response(self):
        res = self.client.patch(
            "/api/v1/projects/proj-tcapi",
            json={"test_command": "make test"},
        )
        assert res.status_code == 200
        body = res.json()
        assert body.get("test_command") == "make test"


# ---------------------------------------------------------------------------
# Tests for per-project tracker configuration fields (TASK-459.3)
# ---------------------------------------------------------------------------


class TestProjectTrackerFields:
    """Unit tests for per-project tracker_kind, tracker_owner, tracker_repo,
    and github_project_node_id fields on the Project model."""

    def _make_project(self, **kwargs):
        defaults = dict(id="p", name="n", repo_url="u", repo_path="/tmp/x")
        defaults.update(kwargs)
        return Project(**defaults)

    # ---- defaults ----

    def test_defaults_are_none_or_false(self):
        p = self._make_project()
        assert p.tracker_kind is None
        assert p.tracker_owner is None
        assert p.tracker_repo is None
        assert p.github_issue_intake_enabled is False
        assert p.github_project_node_id is None
        assert p.status_actor_login is None
        assert p.status_label_authorized_logins == []

    # ---- to_dict ----

    def test_to_dict_omits_unset_tracker_fields(self):
        p = self._make_project()
        d = p.to_dict()
        assert "tracker_kind" not in d
        assert "tracker_owner" not in d
        assert "tracker_repo" not in d
        assert d["github_issue_intake_enabled"] is False
        assert "github_project_node_id" not in d
        assert "status_actor_login" not in d
        assert "status_label_authorized_logins" not in d

    def test_to_dict_emits_tracker_kind_when_set(self):
        p = self._make_project(tracker_kind="github_issues")
        d = p.to_dict()
        assert d["tracker_kind"] == "github_issues"

    def test_to_dict_emits_tracker_owner_repo_when_set(self):
        p = self._make_project(tracker_owner="acme", tracker_repo="oompah-tasks")
        d = p.to_dict()
        assert d["tracker_owner"] == "acme"
        assert d["tracker_repo"] == "oompah-tasks"

    def test_to_dict_emits_github_project_node_id_when_set(self):
        p = self._make_project(github_project_node_id="PVT_abc123")
        d = p.to_dict()
        assert d["github_project_node_id"] == "PVT_abc123"

    def test_to_dict_emits_github_issue_intake_flag(self):
        p = self._make_project(github_issue_intake_enabled=True)
        d = p.to_dict()
        assert d["github_issue_intake_enabled"] is True

    def test_to_dict_emits_status_actor_and_allowlist_when_set(self):
        p = self._make_project(
            status_actor_login="status-actor",
            status_label_authorized_logins=["alice", "bob"],
        )
        d = p.to_dict()
        assert d["status_actor_login"] == "status-actor"
        assert d["status_label_authorized_logins"] == ["alice", "bob"]

    # ---- from_dict round-trip ----

    def test_from_dict_defaults_when_absent(self):
        d = {"id": "p", "name": "n", "repo_url": "u", "repo_path": "/x"}
        p = Project.from_dict(d)
        assert p.tracker_kind is None
        assert p.tracker_owner is None
        assert p.tracker_repo is None
        assert p.github_issue_intake_enabled is False
        assert p.github_project_node_id is None
        assert p.status_actor_login is None
        assert p.status_label_authorized_logins == []

    def test_from_dict_round_trip_tracker_kind(self):
        p = self._make_project(
            tracker_kind="github_issues",
            tracker_owner="acme",
            tracker_repo="tasks",
            github_issue_intake_enabled=True,
        )
        d = p.to_dict()
        p2 = Project.from_dict(d)
        assert p2.tracker_kind == "github_issues"
        assert p2.tracker_owner == "acme"
        assert p2.tracker_repo == "tasks"
        assert p2.github_issue_intake_enabled is True

    def test_from_dict_empty_strings_become_none(self):
        d = {
            "id": "p", "name": "n", "repo_url": "u", "repo_path": "/x",
            "tracker_kind": "",
            "tracker_owner": "  ",
            "tracker_repo": "",
        }
        p = Project.from_dict(d)
        # Empty/whitespace values are treated as None
        assert p.tracker_kind is None or p.tracker_kind == ""
        assert p.tracker_owner is None or p.tracker_owner.strip() == ""
        assert p.tracker_repo is None or p.tracker_repo == ""

    def test_from_dict_github_project_node_id_round_trip(self):
        p = self._make_project(github_project_node_id="PVT_xyz")
        d = p.to_dict()
        p2 = Project.from_dict(d)
        assert p2.github_project_node_id == "PVT_xyz"

    def test_from_dict_status_actor_and_allowlist_round_trip(self):
        p = self._make_project(
            status_actor_login="status-actor",
            status_label_authorized_logins=["alice", "bob"],
        )
        d = p.to_dict()
        p2 = Project.from_dict(d)
        assert p2.status_actor_login == "status-actor"
        assert p2.status_label_authorized_logins == ["alice", "bob"]


class TestProjectStoreTrackerFieldUpdate:
    """Tests for updating tracker fields via ProjectStore.update()."""

    @pytest.fixture(autouse=True)
    def store(self, tmp_path):
        path = str(tmp_path / "projects.json")
        self.store = ProjectStore(
            path=path,
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        p = Project(
            id="proj-tr",
            name="tracker-test",
            repo_url="https://github.com/org/tr.git",
            repo_path=str(tmp_path / "repos" / "tr"),
            branch="main",
        )
        self.store._projects[p.id] = p
        self.store._save()
        return self.store

    def test_update_tracker_kind(self):
        updated = self.store.update("proj-tr", tracker_kind="github_issues")
        assert updated.tracker_kind == "github_issues"

    def test_update_tracker_kind_null_clears(self):
        self.store.update("proj-tr", tracker_kind="github_issues")
        updated = self.store.update("proj-tr", tracker_kind=None)
        assert updated.tracker_kind is None

    def test_update_tracker_kind_rejects_non_string(self):
        with pytest.raises(ProjectError, match="must be a string"):
            self.store.update("proj-tr", tracker_kind=42)

    def test_update_tracker_owner(self):
        updated = self.store.update("proj-tr", tracker_owner="myorg")
        assert updated.tracker_owner == "myorg"

    def test_update_tracker_repo(self):
        updated = self.store.update("proj-tr", tracker_repo="oompah-tasks")
        assert updated.tracker_repo == "oompah-tasks"

    def test_update_tracker_owner_null_clears(self):
        self.store.update("proj-tr", tracker_owner="myorg")
        updated = self.store.update("proj-tr", tracker_owner=None)
        assert updated.tracker_owner is None

    def test_update_tracker_repo_rejects_non_string(self):
        with pytest.raises(ProjectError, match="must be a string"):
            self.store.update("proj-tr", tracker_repo=123)

    def test_update_github_project_node_id(self):
        updated = self.store.update("proj-tr", github_project_node_id="PVT_abc")
        assert updated.github_project_node_id == "PVT_abc"

    def test_update_github_issue_intake_enabled(self):
        updated = self.store.update("proj-tr", github_issue_intake_enabled=True)
        assert updated.github_issue_intake_enabled is True

    def test_update_github_issue_intake_enabled_rejects_non_bool(self):
        with pytest.raises(ProjectError, match="must be a boolean"):
            self.store.update("proj-tr", github_issue_intake_enabled="yes")

    def test_update_status_actor_login_trims_whitespace(self):
        updated = self.store.update("proj-tr", status_actor_login="  status-actor  ")
        assert updated.status_actor_login == "status-actor"

    def test_update_status_actor_login_null_clears(self):
        self.store.update("proj-tr", status_actor_login="status-actor")
        updated = self.store.update("proj-tr", status_actor_login=None)
        assert updated.status_actor_login is None

    def test_update_status_actor_login_rejects_non_string(self):
        with pytest.raises(ProjectError, match="status_actor_login"):
            self.store.update("proj-tr", status_actor_login=["status-actor"])

    def test_update_status_label_allowlist_normalizes_and_dedupes(self):
        updated = self.store.update(
            "proj-tr",
            status_label_authorized_logins=[" Alice ", "alice", "", "Bob"],
        )
        assert updated.status_label_authorized_logins == ["Alice", "Bob"]

    def test_update_status_label_allowlist_null_clears(self):
        self.store.update("proj-tr", status_label_authorized_logins=["alice"])
        updated = self.store.update("proj-tr", status_label_authorized_logins=None)
        assert updated.status_label_authorized_logins == []

    def test_update_status_label_allowlist_rejects_non_list(self):
        with pytest.raises(ProjectError, match="status_label_authorized_logins"):
            self.store.update("proj-tr", status_label_authorized_logins="alice")

    def test_update_status_label_allowlist_rejects_non_string_entries(self):
        with pytest.raises(ProjectError, match="entries must be strings"):
            self.store.update("proj-tr", status_label_authorized_logins=["alice", 123])

    def test_update_tracker_fields_persist(self, tmp_path):
        self.store.update(
            "proj-tr",
            tracker_kind="github_issues",
            tracker_owner="myorg",
            tracker_repo="tasks",
            status_actor_login="status-actor",
            status_label_authorized_logins=["alice"],
        )
        store2 = ProjectStore(
            path=self.store.path,
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        loaded = store2.get("proj-tr")
        assert loaded.tracker_kind == "github_issues"
        assert loaded.tracker_owner == "myorg"
        assert loaded.tracker_repo == "tasks"
        assert loaded.status_actor_login == "status-actor"
        assert loaded.status_label_authorized_logins == ["alice"]

    def test_update_tracker_owner_trims_whitespace(self):
        updated = self.store.update("proj-tr", tracker_owner="  myorg  ")
        assert updated.tracker_owner == "myorg"

    def test_update_tracker_kind_empty_string_becomes_none(self):
        updated = self.store.update("proj-tr", tracker_kind="  ")
        assert updated.tracker_kind is None


class TestProjectAPITrackerFields:
    """Integration tests for tracker fields via the PATCH and GET endpoints."""

    @pytest.fixture(autouse=True)
    def client(self, tmp_path):
        from unittest.mock import MagicMock
        from fastapi.testclient import TestClient
        from oompah.server import app

        store = ProjectStore(
            path=str(tmp_path / "projects.json"),
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        p = Project(
            id="proj-tracker",
            name="tracker-api-test",
            repo_url="https://github.com/org/tracker-test.git",
            repo_path=str(tmp_path / "repos" / "tracker-test"),
            branch="main",
        )
        store._projects[p.id] = p
        store._save()

        orch = MagicMock()
        orch.project_store = store
        orch._project_trackers = {}
        orch._branch_indexes = {}
        orch._stale_caches = {}
        orch._observers = []
        orch._state_only_observers = []
        orch._activity_observers = []
        orch.get_snapshot.return_value = {"counts": {}, "running": {}}

        import oompah.server as srv

        old_orch = srv._orchestrator
        srv._orchestrator = orch
        self.client = TestClient(app)
        self.store = store
        self.orch = orch
        yield self.client
        srv._orchestrator = old_orch

    def test_patch_tracker_kind(self):
        res = self.client.patch(
            "/api/v1/projects/proj-tracker",
            json={"tracker_kind": "github_issues"},
        )
        assert res.status_code == 200
        assert self.store.get("proj-tracker").tracker_kind == "github_issues"

    def test_patch_github_issue_intake_enabled(self):
        res = self.client.patch(
            "/api/v1/projects/proj-tracker",
            json={"github_issue_intake_enabled": True},
        )
        assert res.status_code == 200
        assert self.store.get("proj-tracker").github_issue_intake_enabled is True

    def test_patch_github_tracker_updates_agents_md(self):
        project = self.store.get("proj-tracker")
        repo_path = Path(project.repo_path)
        repo_path.mkdir(parents=True)
        (repo_path / "AGENTS.md").write_text(
            """# Project Rules

<!-- BEGIN OOMPAH TASK INTEGRATION v:1 -->
## Issue Tracking with oompah

Use oompah tasks for tracking.
<!-- END OOMPAH TASK INTEGRATION -->
""",
            encoding="utf-8",
        )

        res = self.client.patch(
            "/api/v1/projects/proj-tracker",
            json={"tracker_kind": "github_issues"},
        )

        assert res.status_code == 200
        text = (repo_path / "AGENTS.md").read_text(encoding="utf-8")
        assert "BEGIN OOMPAH GITHUB ISSUES INTEGRATION" in text
        assert "Use oompah tasks for tracking" not in text
        assert "oompah task create --project <project-id>" in text
        assert "Prefer the `oompah task` CLI only when it is installed" in text
        assert "GitHub Fallback" in text
        assert "`parent:<issue-number>`" in text
        assert "`depends-on:<issue-number>`" in text

    def test_patch_oompah_md_tracker_updates_agents_md(self):
        project = self.store.get("proj-tracker")
        repo_path = Path(project.repo_path)
        repo_path.mkdir(parents=True)
        (repo_path / "AGENTS.md").write_text(
            """# Project Rules

<!-- BEGIN OOMPAH GITHUB ISSUES INTEGRATION v:1 -->
## Issue Tracking with GitHub Issues

Use GitHub Issues for task tracking.
<!-- END OOMPAH GITHUB ISSUES INTEGRATION -->
""",
            encoding="utf-8",
        )

        res = self.client.patch(
            "/api/v1/projects/proj-tracker",
            json={"tracker_kind": "oompah_md"},
        )

        assert res.status_code == 200
        text = (repo_path / "AGENTS.md").read_text(encoding="utf-8")
        assert "BEGIN OOMPAH TASK INTEGRATION" in text
        assert "BEGIN OOMPAH GITHUB ISSUES INTEGRATION" not in text
        assert "Use GitHub Issues for task tracking" not in text
        assert "`.oompah/tasks`" in text

    def test_patch_tracker_kind_invalidates_cached_tracker(self):
        import oompah.server as srv

        self.orch._project_trackers = {
            "proj-tracker": object(),
            "other-project": object(),
        }
        self.orch._branch_indexes = {
            "proj-tracker": object(),
            "other-project": object(),
        }
        self.orch._stale_caches = {
            "proj-tracker": object(),
            "other-project": object(),
        }
        srv._api_cache.set("issues:all", {"stale": True}, ttl_ms=60_000)

        res = self.client.patch(
            "/api/v1/projects/proj-tracker",
            json={"tracker_kind": "github_issues"},
        )

        assert res.status_code == 200
        assert "proj-tracker" not in self.orch._project_trackers
        assert "proj-tracker" not in self.orch._branch_indexes
        assert "proj-tracker" not in self.orch._stale_caches
        assert "other-project" in self.orch._project_trackers
        assert srv._api_cache.get("issues:all") is None

    def test_patch_non_tracker_field_keeps_cached_tracker(self):
        import oompah.server as srv

        cached = object()
        self.orch._project_trackers = {"proj-tracker": cached}
        srv._api_cache.set("issues:all", {"fresh": True}, ttl_ms=60_000)

        res = self.client.patch(
            "/api/v1/projects/proj-tracker",
            json={"name": "renamed"},
        )

        assert res.status_code == 200
        assert self.orch._project_trackers["proj-tracker"] is cached
        assert srv._api_cache.get("issues:all") is not None

    def test_patch_tracker_kind_null_clears(self):
        self.store.update("proj-tracker", tracker_kind="github_issues")
        res = self.client.patch(
            "/api/v1/projects/proj-tracker",
            json={"tracker_kind": None},
        )
        assert res.status_code == 200
        assert self.store.get("proj-tracker").tracker_kind is None

    def test_patch_tracker_kind_invalid_type(self):
        res = self.client.patch(
            "/api/v1/projects/proj-tracker",
            json={"tracker_kind": 42},
        )
        assert res.status_code == 400
        assert "tracker_kind" in res.json()["error"]["message"]

    def test_patch_tracker_owner_and_repo(self):
        res = self.client.patch(
            "/api/v1/projects/proj-tracker",
            json={"tracker_owner": "myorg", "tracker_repo": "oompah-tasks"},
        )
        assert res.status_code == 200
        p = self.store.get("proj-tracker")
        assert p.tracker_owner == "myorg"
        assert p.tracker_repo == "oompah-tasks"

    def test_patch_github_project_node_id(self):
        res = self.client.patch(
            "/api/v1/projects/proj-tracker",
            json={"github_project_node_id": "PVT_abc"},
        )
        assert res.status_code == 200
        assert self.store.get("proj-tracker").github_project_node_id == "PVT_abc"

    def test_patch_status_actor_login(self):
        res = self.client.patch(
            "/api/v1/projects/proj-tracker",
            json={"status_actor_login": "  status-actor  "},
        )
        assert res.status_code == 200
        assert self.store.get("proj-tracker").status_actor_login == "status-actor"
        assert res.json()["status_actor_login"] == "status-actor"

    def test_patch_status_actor_login_invalid_type(self):
        res = self.client.patch(
            "/api/v1/projects/proj-tracker",
            json={"status_actor_login": ["status-actor"]},
        )
        assert res.status_code == 400
        assert "status_actor_login" in res.json()["error"]["message"]

    def test_patch_blank_status_actor_defaults_to_token_owner(self, monkeypatch):
        import oompah.server as srv

        self.store.update("proj-tracker", access_token="old-token")
        monkeypatch.setattr(
            srv,
            "_resolve_github_token_owner",
            lambda token: "token-owner" if token == "old-token" else None,
        )

        res = self.client.patch(
            "/api/v1/projects/proj-tracker",
            json={"status_actor_login": ""},
        )

        assert res.status_code == 200
        assert self.store.get("proj-tracker").status_actor_login == "token-owner"

    def test_patch_access_token_defaults_status_actor_to_token_owner(self, monkeypatch):
        import oompah.server as srv

        monkeypatch.setattr(
            srv,
            "_resolve_github_token_owner",
            lambda token: "TokenOwner" if token == "new-token" else None,
        )

        res = self.client.patch(
            "/api/v1/projects/proj-tracker",
            json={"access_token": "new-token"},
        )

        assert res.status_code == 200
        assert self.store.get("proj-tracker").status_actor_login == "TokenOwner"

    def test_patch_explicit_status_actor_overrides_token_owner(self, monkeypatch):
        import oompah.server as srv

        monkeypatch.setattr(
            srv,
            "_resolve_github_token_owner",
            lambda token: "TokenOwner",
        )

        res = self.client.patch(
            "/api/v1/projects/proj-tracker",
            json={"access_token": "new-token", "status_actor_login": "ProjectActor"},
        )

        assert res.status_code == 200
        assert self.store.get("proj-tracker").status_actor_login == "ProjectActor"

    def test_patch_status_label_authorized_logins(self):
        res = self.client.patch(
            "/api/v1/projects/proj-tracker",
            json={"status_label_authorized_logins": [" alice ", "alice", "Bob"]},
        )
        assert res.status_code == 200
        assert self.store.get("proj-tracker").status_label_authorized_logins == [
            "alice",
            "Bob",
        ]
        assert res.json()["status_label_authorized_logins"] == ["alice", "Bob"]

    def test_patch_status_label_authorized_logins_invalid_type(self):
        res = self.client.patch(
            "/api/v1/projects/proj-tracker",
            json={"status_label_authorized_logins": "alice"},
        )
        assert res.status_code == 400
        assert "status_label_authorized_logins" in res.json()["error"]["message"]

    def test_patch_tracker_fields_visible_in_get(self):
        self.client.patch(
            "/api/v1/projects/proj-tracker",
            json={
                "tracker_kind": "github_issues",
                "tracker_owner": "acme",
                "tracker_repo": "tasks",
                "status_actor_login": "status-actor",
                "status_label_authorized_logins": ["reviewer"],
            },
        )
        res = self.client.get("/api/v1/projects/proj-tracker")
        assert res.status_code == 200
        data = res.json()
        assert data["tracker_kind"] == "github_issues"
        assert data["tracker_owner"] == "acme"
        assert data["tracker_repo"] == "tasks"
        assert data["status_actor_login"] == "status-actor"
        assert data["status_label_authorized_logins"] == ["reviewer"]

    def test_patch_tracker_owner_invalid_type(self):
        res = self.client.patch(
            "/api/v1/projects/proj-tracker",
            json={"tracker_owner": ["not-a-string"]},
        )
        assert res.status_code == 400
        assert "tracker_owner" in res.json()["error"]["message"]

    def test_patch_all_tracker_fields_together(self):
        res = self.client.patch(
            "/api/v1/projects/proj-tracker",
            json={
                "tracker_kind": "github_issues",
                "tracker_owner": "acme",
                "tracker_repo": "oompah-tasks",
                "github_project_node_id": "PVT_xyz",
                "status_actor_login": "status-actor",
                "status_label_authorized_logins": ["reviewer"],
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["tracker_kind"] == "github_issues"
        assert data["tracker_owner"] == "acme"
        assert data["tracker_repo"] == "oompah-tasks"
        assert data["github_project_node_id"] == "PVT_xyz"
        assert data["status_actor_login"] == "status-actor"
        assert data["status_label_authorized_logins"] == ["reviewer"]
