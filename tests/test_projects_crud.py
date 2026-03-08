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
        self.store = ProjectStore(path=path, repos_root=str(tmp_path / "repos"),
                                   worktree_root=str(tmp_path / "wt"))
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
        updated = self.store.update("proj-abc", repo_url="https://github.com/org/other.git")
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
        self.store = ProjectStore(path=path, repos_root=str(tmp_path / "repos"),
                                   worktree_root=str(tmp_path / "wt"))
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
        self.store = ProjectStore(path=path, repos_root=str(tmp_path / "repos"),
                                   worktree_root=str(tmp_path / "wt"))
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
                id=f"proj-list{i}", name=f"list{i}",
                repo_url=f"https://x/{i}", repo_path=f"/tmp/{i}",
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


class TestProjectStoreUpdatableFields:
    """Verify the UPDATABLE_FIELDS constant matches expected set."""

    def test_updatable_fields_are_correct(self):
        expected = {"name", "repo_url", "branch", "git_user_name",
                    "git_user_email", "yolo", "log_path", "webhook_secret"}
        assert ProjectStore.UPDATABLE_FIELDS == expected

    def test_id_is_not_updatable(self):
        assert "id" not in ProjectStore.UPDATABLE_FIELDS

    def test_repo_path_is_not_updatable(self):
        assert "repo_path" not in ProjectStore.UPDATABLE_FIELDS
