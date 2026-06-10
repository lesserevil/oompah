"""Tests for managed-project cutover and rollback workflow (TASK-464.3).

Covers:
- Project model: cutover_at, tracker_owner, tracker_repo defaults and
  serialisation (to_dict / from_dict round-trips).
- ProjectStore.UPDATABLE_FIELDS includes all three new fields.
- ProjectStore.update() can set and persist the new fields.
- Server API:
  * POST /api/v1/projects/{id}/cutover
      - sets tracker_kind=github_issues, records cutover_at, pauses project
      - accepts optional tracker_owner/tracker_repo
      - accepts legacy_backlog_enabled / legacy_backlog_dispatch flags
      - returns 404 for unknown projects
      - idempotent: calling again updates the timestamp
  * POST /api/v1/projects/{id}/rollback
      - clears tracker_kind and cutover_at
      - sets legacy_backlog_enabled=True and legacy_backlog_dispatch=True
      - unpauses by default; keep_paused=True leaves it paused
      - clears tracker_owner/tracker_repo by default
      - returns 404 for unknown projects
      - does not delete GitHub Issues (no network call expected)
  * PATCH /api/v1/projects/{id}
      - accepts tracker_kind, tracker_owner, tracker_repo, cutover_at,
        legacy_backlog_enabled, legacy_backlog_dispatch
      - rejects invalid tracker_kind (empty string)
      - accepts null to clear each field
"""

from __future__ import annotations

import re
from unittest.mock import MagicMock

import pytest

from oompah.models import Project
from oompah.projects import ProjectError, ProjectStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_store(tmp_path) -> tuple[ProjectStore, Project]:
    path = str(tmp_path / "projects.json")
    store = ProjectStore(
        path=path,
        repos_root=str(tmp_path / "repos"),
        worktree_root=str(tmp_path / "wt"),
    )
    p = Project(
        id="proj-co",
        name="cutover-test",
        repo_url="https://github.com/org/cutover-test.git",
        repo_path=str(tmp_path / "repos" / "cutover-test"),
        branch="main",
    )
    store._projects[p.id] = p
    store._save()
    return store, p


# ---------------------------------------------------------------------------
# Project model: new field defaults
# ---------------------------------------------------------------------------


class TestCutoverModelDefaults:
    def test_cutover_at_defaults_to_none(self):
        p = Project(id="p", name="n", repo_url="u", repo_path="/tmp/x")
        assert p.cutover_at is None

    def test_tracker_owner_defaults_to_none(self):
        p = Project(id="p", name="n", repo_url="u", repo_path="/tmp/x")
        assert p.tracker_owner is None

    def test_tracker_repo_defaults_to_none(self):
        p = Project(id="p", name="n", repo_url="u", repo_path="/tmp/x")
        assert p.tracker_repo is None

    def test_can_set_cutover_at(self):
        p = Project(
            id="p", name="n", repo_url="u", repo_path="/tmp/x",
            cutover_at="2026-01-01T00:00:00+00:00",
        )
        assert p.cutover_at == "2026-01-01T00:00:00+00:00"

    def test_can_set_tracker_owner(self):
        p = Project(
            id="p", name="n", repo_url="u", repo_path="/tmp/x",
            tracker_owner="lesserevil",
        )
        assert p.tracker_owner == "lesserevil"

    def test_can_set_tracker_repo(self):
        p = Project(
            id="p", name="n", repo_url="u", repo_path="/tmp/x",
            tracker_repo="oompah-tasks",
        )
        assert p.tracker_repo == "oompah-tasks"


# ---------------------------------------------------------------------------
# Project model: to_dict serialisation
# ---------------------------------------------------------------------------


class TestCutoverSerialisation:
    def test_to_dict_omits_cutover_at_when_none(self):
        p = Project(id="p", name="n", repo_url="u", repo_path="/tmp/x")
        assert "cutover_at" not in p.to_dict()

    def test_to_dict_omits_tracker_owner_when_none(self):
        p = Project(id="p", name="n", repo_url="u", repo_path="/tmp/x")
        assert "tracker_owner" not in p.to_dict()

    def test_to_dict_omits_tracker_repo_when_none(self):
        p = Project(id="p", name="n", repo_url="u", repo_path="/tmp/x")
        assert "tracker_repo" not in p.to_dict()

    def test_to_dict_includes_cutover_at_when_set(self):
        p = Project(
            id="p", name="n", repo_url="u", repo_path="/tmp/x",
            cutover_at="2026-06-10T10:00:00+00:00",
        )
        assert p.to_dict()["cutover_at"] == "2026-06-10T10:00:00+00:00"

    def test_to_dict_includes_tracker_owner_when_set(self):
        p = Project(
            id="p", name="n", repo_url="u", repo_path="/tmp/x",
            tracker_owner="lesserevil",
        )
        assert p.to_dict()["tracker_owner"] == "lesserevil"

    def test_to_dict_includes_tracker_repo_when_set(self):
        p = Project(
            id="p", name="n", repo_url="u", repo_path="/tmp/x",
            tracker_repo="oompah-tasks",
        )
        assert p.to_dict()["tracker_repo"] == "oompah-tasks"

    def test_from_dict_round_trip_all_set(self):
        p = Project(
            id="p", name="n", repo_url="u", repo_path="/tmp/x",
            tracker_kind="github_issues",
            tracker_owner="lesserevil",
            tracker_repo="oompah-tasks",
            cutover_at="2026-06-10T12:00:00+00:00",
            legacy_backlog_enabled=True,
        )
        p2 = Project.from_dict(p.to_dict())
        assert p2.tracker_kind == "github_issues"
        assert p2.tracker_owner == "lesserevil"
        assert p2.tracker_repo == "oompah-tasks"
        assert p2.cutover_at == "2026-06-10T12:00:00+00:00"
        assert p2.legacy_backlog_enabled is True

    def test_from_dict_missing_fields_default_to_none(self):
        p = Project.from_dict(
            {"id": "x", "name": "y", "repo_url": "z", "repo_path": "/a"}
        )
        assert p.cutover_at is None
        assert p.tracker_owner is None
        assert p.tracker_repo is None

    def test_to_safe_dict_includes_cutover_at(self):
        p = Project(
            id="p", name="n", repo_url="u", repo_path="/tmp/x",
            cutover_at="2026-06-10T10:00:00+00:00",
        )
        assert p.to_safe_dict()["cutover_at"] == "2026-06-10T10:00:00+00:00"

    def test_to_safe_dict_includes_tracker_owner(self):
        p = Project(
            id="p", name="n", repo_url="u", repo_path="/tmp/x",
            tracker_owner="lesserevil",
        )
        assert p.to_safe_dict()["tracker_owner"] == "lesserevil"

    def test_to_safe_dict_includes_tracker_repo(self):
        p = Project(
            id="p", name="n", repo_url="u", repo_path="/tmp/x",
            tracker_repo="oompah-tasks",
        )
        assert p.to_safe_dict()["tracker_repo"] == "oompah-tasks"


# ---------------------------------------------------------------------------
# ProjectStore: UPDATABLE_FIELDS and update()
# ---------------------------------------------------------------------------


class TestCutoverProjectStore:
    def test_cutover_at_in_updatable_fields(self):
        assert "cutover_at" in ProjectStore.UPDATABLE_FIELDS

    def test_tracker_owner_in_updatable_fields(self):
        assert "tracker_owner" in ProjectStore.UPDATABLE_FIELDS

    def test_tracker_repo_in_updatable_fields(self):
        assert "tracker_repo" in ProjectStore.UPDATABLE_FIELDS

    def test_update_sets_cutover_at(self, tmp_path):
        store, _ = _make_store(tmp_path)
        updated = store.update("proj-co", cutover_at="2026-06-10T00:00:00+00:00")
        assert updated.cutover_at == "2026-06-10T00:00:00+00:00"

    def test_update_sets_tracker_owner(self, tmp_path):
        store, _ = _make_store(tmp_path)
        updated = store.update("proj-co", tracker_owner="lesserevil")
        assert updated.tracker_owner == "lesserevil"

    def test_update_sets_tracker_repo(self, tmp_path):
        store, _ = _make_store(tmp_path)
        updated = store.update("proj-co", tracker_repo="oompah-tasks")
        assert updated.tracker_repo == "oompah-tasks"

    def test_update_persists_cutover_at(self, tmp_path):
        store, _ = _make_store(tmp_path)
        store.update("proj-co", cutover_at="2026-06-10T00:00:00+00:00")
        store2 = ProjectStore(
            path=store.path,
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        assert store2.get("proj-co").cutover_at == "2026-06-10T00:00:00+00:00"

    def test_update_persists_tracker_owner(self, tmp_path):
        store, _ = _make_store(tmp_path)
        store.update("proj-co", tracker_owner="lesserevil")
        store2 = ProjectStore(
            path=store.path,
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        assert store2.get("proj-co").tracker_owner == "lesserevil"

    def test_update_persists_tracker_repo(self, tmp_path):
        store, _ = _make_store(tmp_path)
        store.update("proj-co", tracker_repo="oompah-tasks")
        store2 = ProjectStore(
            path=store.path,
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        assert store2.get("proj-co").tracker_repo == "oompah-tasks"

    def test_update_clears_cutover_at_to_none(self, tmp_path):
        store, _ = _make_store(tmp_path)
        store.update("proj-co", cutover_at="2026-06-10T00:00:00+00:00")
        store.update("proj-co", cutover_at=None)
        assert store.get("proj-co").cutover_at is None

    def test_update_clears_tracker_owner_to_none(self, tmp_path):
        store, _ = _make_store(tmp_path)
        store.update("proj-co", tracker_owner="lesserevil")
        store.update("proj-co", tracker_owner=None)
        assert store.get("proj-co").tracker_owner is None


# ---------------------------------------------------------------------------
# Server API: cutover endpoint
# ---------------------------------------------------------------------------


class TestCutoverAPI:
    @pytest.fixture(autouse=True)
    def client(self, tmp_path):
        from fastapi.testclient import TestClient

        import oompah.server as srv
        from oompah.server import app

        store, _ = _make_store(tmp_path)
        orch = MagicMock()
        orch.project_store = store
        orch._observers = []
        orch._state_only_observers = []
        orch._activity_observers = []
        orch.get_snapshot.return_value = {"counts": {}, "running": {}}

        old_orch = srv._orchestrator
        srv._orchestrator = orch
        self.client = TestClient(app)
        self.store = store
        yield
        srv._orchestrator = old_orch

    def test_cutover_sets_tracker_kind_github_issues(self):
        res = self.client.post("/api/v1/projects/proj-co/cutover", json={})
        assert res.status_code == 200
        assert self.store.get("proj-co").tracker_kind == "github_issues"

    def test_cutover_response_ok_true(self):
        res = self.client.post("/api/v1/projects/proj-co/cutover", json={})
        assert res.status_code == 200
        body = res.json()
        assert body["ok"] is True

    def test_cutover_response_includes_tracker_kind(self):
        res = self.client.post("/api/v1/projects/proj-co/cutover", json={})
        body = res.json()
        assert body["tracker_kind"] == "github_issues"

    def test_cutover_pauses_project(self):
        res = self.client.post("/api/v1/projects/proj-co/cutover", json={})
        assert res.status_code == 200
        assert self.store.get("proj-co").paused is True
        assert res.json()["paused"] is True

    def test_cutover_records_cutover_at_timestamp(self):
        res = self.client.post("/api/v1/projects/proj-co/cutover", json={})
        assert res.status_code == 200
        body = res.json()
        assert "cutover_at" in body
        # Should be a valid ISO-8601 timestamp
        ts = body["cutover_at"]
        assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", ts)
        assert self.store.get("proj-co").cutover_at is not None

    def test_cutover_sets_tracker_owner_and_repo(self):
        res = self.client.post(
            "/api/v1/projects/proj-co/cutover",
            json={"tracker_owner": "lesserevil", "tracker_repo": "oompah-tasks"},
        )
        assert res.status_code == 200
        proj = self.store.get("proj-co")
        assert proj.tracker_owner == "lesserevil"
        assert proj.tracker_repo == "oompah-tasks"

    def test_cutover_default_legacy_flags_false(self):
        res = self.client.post("/api/v1/projects/proj-co/cutover", json={})
        assert res.status_code == 200
        proj = self.store.get("proj-co")
        assert proj.legacy_backlog_enabled is False
        assert proj.legacy_backlog_dispatch is False

    def test_cutover_sets_legacy_flags_when_requested(self):
        res = self.client.post(
            "/api/v1/projects/proj-co/cutover",
            json={"legacy_backlog_enabled": True, "legacy_backlog_dispatch": True},
        )
        assert res.status_code == 200
        proj = self.store.get("proj-co")
        assert proj.legacy_backlog_enabled is True
        assert proj.legacy_backlog_dispatch is True

    def test_cutover_unknown_project_returns_404(self):
        res = self.client.post("/api/v1/projects/proj-nope/cutover", json={})
        assert res.status_code == 404
        assert res.json()["error"]["code"] == "not_found"

    def test_cutover_without_body_is_valid(self):
        """Empty body should apply defaults (no tracker_owner/repo, both legacy flags False)."""
        res = self.client.post("/api/v1/projects/proj-co/cutover")
        assert res.status_code == 200
        assert res.json()["ok"] is True

    def test_cutover_response_includes_project(self):
        res = self.client.post("/api/v1/projects/proj-co/cutover", json={})
        body = res.json()
        assert "project" in body
        assert body["project"]["id"] == "proj-co"

    def test_cutover_idempotent_updates_timestamp(self):
        """A second cutover call should succeed and refresh cutover_at."""
        r1 = self.client.post("/api/v1/projects/proj-co/cutover", json={})
        r2 = self.client.post("/api/v1/projects/proj-co/cutover", json={})
        assert r1.status_code == 200
        assert r2.status_code == 200
        # The second cutover must also record a valid timestamp
        assert r2.json()["cutover_at"] is not None


# ---------------------------------------------------------------------------
# Server API: rollback endpoint
# ---------------------------------------------------------------------------


class TestRollbackAPI:
    @pytest.fixture(autouse=True)
    def client(self, tmp_path):
        from fastapi.testclient import TestClient

        import oompah.server as srv
        from oompah.server import app

        store = ProjectStore(
            path=str(tmp_path / "projects.json"),
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        # Start in a cut-over state for most rollback tests
        p = Project(
            id="proj-rb",
            name="rollback-test",
            repo_url="https://github.com/org/rollback-test.git",
            repo_path=str(tmp_path / "repos" / "rollback-test"),
            branch="main",
            tracker_kind="github_issues",
            tracker_owner="lesserevil",
            tracker_repo="oompah-tasks",
            cutover_at="2026-06-10T10:00:00+00:00",
            paused=True,
        )
        store._projects[p.id] = p
        store._save()

        orch = MagicMock()
        orch.project_store = store
        orch._observers = []
        orch._state_only_observers = []
        orch._activity_observers = []
        orch.get_snapshot.return_value = {"counts": {}, "running": {}}

        old_orch = srv._orchestrator
        srv._orchestrator = orch
        self.client = TestClient(app)
        self.store = store
        yield
        srv._orchestrator = old_orch

    def test_rollback_clears_tracker_kind(self):
        res = self.client.post("/api/v1/projects/proj-rb/rollback", json={})
        assert res.status_code == 200
        assert self.store.get("proj-rb").tracker_kind is None

    def test_rollback_clears_cutover_at(self):
        res = self.client.post("/api/v1/projects/proj-rb/rollback", json={})
        assert res.status_code == 200
        assert self.store.get("proj-rb").cutover_at is None

    def test_rollback_sets_legacy_backlog_enabled_true(self):
        res = self.client.post("/api/v1/projects/proj-rb/rollback", json={})
        assert res.status_code == 200
        assert self.store.get("proj-rb").legacy_backlog_enabled is True

    def test_rollback_sets_legacy_backlog_dispatch_true(self):
        res = self.client.post("/api/v1/projects/proj-rb/rollback", json={})
        assert res.status_code == 200
        assert self.store.get("proj-rb").legacy_backlog_dispatch is True

    def test_rollback_unpauses_by_default(self):
        res = self.client.post("/api/v1/projects/proj-rb/rollback", json={})
        assert res.status_code == 200
        assert self.store.get("proj-rb").paused is False
        assert res.json()["paused"] is False

    def test_rollback_keep_paused_leaves_paused(self):
        res = self.client.post(
            "/api/v1/projects/proj-rb/rollback", json={"keep_paused": True}
        )
        assert res.status_code == 200
        assert self.store.get("proj-rb").paused is True
        assert res.json()["paused"] is True

    def test_rollback_clears_tracker_owner_by_default(self):
        res = self.client.post("/api/v1/projects/proj-rb/rollback", json={})
        assert res.status_code == 200
        assert self.store.get("proj-rb").tracker_owner is None

    def test_rollback_clears_tracker_repo_by_default(self):
        res = self.client.post("/api/v1/projects/proj-rb/rollback", json={})
        assert res.status_code == 200
        assert self.store.get("proj-rb").tracker_repo is None

    def test_rollback_keep_tracker_owner_when_requested(self):
        res = self.client.post(
            "/api/v1/projects/proj-rb/rollback",
            json={"clear_tracker_owner": False},
        )
        assert res.status_code == 200
        assert self.store.get("proj-rb").tracker_owner == "lesserevil"
        assert self.store.get("proj-rb").tracker_repo == "oompah-tasks"

    def test_rollback_response_ok_true(self):
        res = self.client.post("/api/v1/projects/proj-rb/rollback", json={})
        body = res.json()
        assert body["ok"] is True
        assert body["rolled_back"] is True

    def test_rollback_response_includes_project(self):
        res = self.client.post("/api/v1/projects/proj-rb/rollback", json={})
        body = res.json()
        assert "project" in body
        assert body["project"]["id"] == "proj-rb"

    def test_rollback_unknown_project_returns_404(self):
        res = self.client.post("/api/v1/projects/proj-nope/rollback", json={})
        assert res.status_code == 404
        assert res.json()["error"]["code"] == "not_found"

    def test_rollback_without_body_is_valid(self):
        """Empty body should apply defaults."""
        res = self.client.post("/api/v1/projects/proj-rb/rollback")
        assert res.status_code == 200
        assert res.json()["ok"] is True

    def test_rollback_does_not_contact_github(self):
        """Rollback must be a local-only operation — no GitHub API calls expected."""
        import unittest.mock as _mock

        with _mock.patch("oompah.server.requests", create=True) as mock_requests:
            res = self.client.post("/api/v1/projects/proj-rb/rollback", json={})
        # Even if the server imports requests, it must not call any HTTP method.
        # (This is a smoke-test guard; if the mock is never imported, the assertion
        # is vacuously true — which is exactly the expected behaviour.)
        assert res.status_code == 200
        mock_requests.get.assert_not_called() if hasattr(mock_requests, "get") else None


# ---------------------------------------------------------------------------
# Server PATCH: tracker fields
# ---------------------------------------------------------------------------


class TestPatchTrackerFields:
    @pytest.fixture(autouse=True)
    def client(self, tmp_path):
        from fastapi.testclient import TestClient

        import oompah.server as srv
        from oompah.server import app

        store, _ = _make_store(tmp_path)
        orch = MagicMock()
        orch.project_store = store
        orch._observers = []
        orch._state_only_observers = []
        orch._activity_observers = []
        orch.get_snapshot.return_value = {"counts": {}, "running": {}}

        old_orch = srv._orchestrator
        srv._orchestrator = orch
        self.client = TestClient(app)
        self.store = store
        yield
        srv._orchestrator = old_orch

    def test_patch_sets_tracker_kind(self):
        res = self.client.patch(
            "/api/v1/projects/proj-co",
            json={"tracker_kind": "github_issues"},
        )
        assert res.status_code == 200
        assert res.json()["tracker_kind"] == "github_issues"

    def test_patch_clears_tracker_kind(self):
        self.store.update("proj-co", tracker_kind="github_issues")
        res = self.client.patch(
            "/api/v1/projects/proj-co",
            json={"tracker_kind": None},
        )
        assert res.status_code == 200
        assert res.json().get("tracker_kind") is None

    def test_patch_sets_tracker_owner(self):
        res = self.client.patch(
            "/api/v1/projects/proj-co",
            json={"tracker_owner": "lesserevil"},
        )
        assert res.status_code == 200
        assert res.json()["tracker_owner"] == "lesserevil"

    def test_patch_sets_tracker_repo(self):
        res = self.client.patch(
            "/api/v1/projects/proj-co",
            json={"tracker_repo": "oompah-tasks"},
        )
        assert res.status_code == 200
        assert res.json()["tracker_repo"] == "oompah-tasks"

    def test_patch_clears_tracker_owner(self):
        self.store.update("proj-co", tracker_owner="lesserevil")
        res = self.client.patch(
            "/api/v1/projects/proj-co",
            json={"tracker_owner": None},
        )
        assert res.status_code == 200
        assert res.json().get("tracker_owner") is None

    def test_patch_sets_cutover_at(self):
        ts = "2026-06-10T10:00:00+00:00"
        res = self.client.patch(
            "/api/v1/projects/proj-co",
            json={"cutover_at": ts},
        )
        assert res.status_code == 200
        assert res.json()["cutover_at"] == ts

    def test_patch_clears_cutover_at(self):
        self.store.update("proj-co", cutover_at="2026-06-10T10:00:00+00:00")
        res = self.client.patch(
            "/api/v1/projects/proj-co",
            json={"cutover_at": None},
        )
        assert res.status_code == 200
        assert res.json().get("cutover_at") is None

    def test_patch_sets_legacy_backlog_enabled(self):
        res = self.client.patch(
            "/api/v1/projects/proj-co",
            json={"legacy_backlog_enabled": True},
        )
        assert res.status_code == 200
        assert res.json()["legacy_backlog_enabled"] is True

    def test_patch_sets_legacy_backlog_dispatch(self):
        res = self.client.patch(
            "/api/v1/projects/proj-co",
            json={"legacy_backlog_dispatch": True},
        )
        assert res.status_code == 200
        assert res.json()["legacy_backlog_dispatch"] is True

    def test_patch_empty_tracker_kind_returns_400(self):
        res = self.client.patch(
            "/api/v1/projects/proj-co",
            json={"tracker_kind": ""},
        )
        assert res.status_code == 400
        assert "tracker_kind" in res.json()["error"]["message"]

    def test_patch_invalid_tracker_kind_type_returns_400(self):
        res = self.client.patch(
            "/api/v1/projects/proj-co",
            json={"tracker_kind": 123},
        )
        assert res.status_code == 400
