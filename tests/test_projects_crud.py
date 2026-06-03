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
            "access_token",
            "last_webhook_received_at",
            "max_in_flight_prs",
            "merge_queue_enabled",
            "paused",
            "test_command",
            "test_command_full",
            "test_skip_paths",
            "epic_strategy",
            "provider_whitelist",
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
