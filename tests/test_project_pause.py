"""Tests for per-project pause (oompah-zlz_2-u7c).

Covers:
- Project model: paused field defaults, serialization, round-trip
- ProjectStore.update() accepts paused
- Orchestrator._is_project_paused() helper
- Orchestrator._should_dispatch() rejects paused-project issues with
  reason "project_paused"
- Orchestrator._should_dispatch_epic() blocks epic planning when the
  project is paused
- Composition with global pause
- Per-project independence (pausing one project does not affect another)
- Server endpoints: POST /api/v1/projects/{id}/pause, /resume
- /api/v1/state.projects[] surfaces the paused flag
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from oompah.config import ServiceConfig
from oompah.models import Issue, Project
from oompah.orchestrator import Orchestrator
from oompah.projects import ProjectError, ProjectStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config() -> ServiceConfig:
    return ServiceConfig()


def _make_issue(
    identifier: str,
    state: str = "open",
    issue_type: str = "task",
    priority: int = 2,
    project_id: str | None = None,
    description: str = "Non-empty description for dispatch gate.",
) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=f"Issue {identifier}",
        description=description,
        state=state,
        issue_type=issue_type,
        priority=priority,
        project_id=project_id,
        labels=[],
    )


def _make_project_mock(
    project_id: str,
    paused: bool = False,
    max_in_flight_prs: int = 1,
    name: str = "myrepo",
) -> MagicMock:
    p = MagicMock(spec=Project)
    p.id = project_id
    p.name = name
    p.repo_url = "https://github.com/org/repo"
    p.yolo = False
    p.paused = paused
    p.max_in_flight_prs = max_in_flight_prs
    p.last_webhook_received_at = None
    return p


def _make_orchestrator(tmp_path, projects=None) -> Orchestrator:
    all_projects = list(projects or [])
    project_store = MagicMock()
    project_store.list_all.return_value = all_projects
    project_store.get.side_effect = lambda pid: next(
        (p for p in all_projects if p.id == pid), None
    )
    orch = Orchestrator(
        config=_make_config(),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        state_path=str(tmp_path / "state.json"),
    )
    # Avoid being gated by the open-review cap (reviews cache empty).
    orch._reviews_cache = {}
    return orch


# ---------------------------------------------------------------------------
# Project model
# ---------------------------------------------------------------------------


class TestProjectPausedField:
    def test_default_is_false(self):
        p = Project(id="p", name="n", repo_url="u", repo_path="/tmp/x")
        assert p.paused is False

    def test_to_dict_includes_paused_when_false(self):
        p = Project(id="p", name="n", repo_url="u", repo_path="/tmp/x")
        d = p.to_dict()
        assert d["paused"] is False

    def test_to_dict_includes_paused_when_true(self):
        p = Project(id="p", name="n", repo_url="u", repo_path="/tmp/x", paused=True)
        d = p.to_dict()
        assert d["paused"] is True

    def test_to_safe_dict_includes_paused(self):
        p = Project(id="p", name="n", repo_url="u", repo_path="/tmp/x", paused=True)
        assert p.to_safe_dict()["paused"] is True

    def test_from_dict_round_trip_true(self):
        p = Project(id="p", name="n", repo_url="u", repo_path="/tmp/x", paused=True)
        p2 = Project.from_dict(p.to_dict())
        assert p2.paused is True

    def test_from_dict_round_trip_false(self):
        p = Project(id="p", name="n", repo_url="u", repo_path="/tmp/x", paused=False)
        p2 = Project.from_dict(p.to_dict())
        assert p2.paused is False

    def test_from_dict_missing_field_defaults_to_false(self):
        p = Project.from_dict(
            {"id": "x", "name": "y", "repo_url": "z", "repo_path": "/a"}
        )
        assert p.paused is False


# ---------------------------------------------------------------------------
# ProjectStore.update()
# ---------------------------------------------------------------------------


class TestProjectStorePaused:
    @pytest.fixture(autouse=True)
    def store(self, tmp_path):
        path = str(tmp_path / "projects.json")
        self.store = ProjectStore(
            path=path,
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        p = Project(
            id="proj-paused",
            name="paused-test",
            repo_url="https://github.com/org/paused-test.git",
            repo_path=str(tmp_path / "repos" / "paused-test"),
            branch="main",
        )
        self.store._projects[p.id] = p
        self.store._save()

    def test_paused_in_updatable_fields(self):
        assert "paused" in ProjectStore.UPDATABLE_FIELDS

    def test_update_sets_paused_true(self):
        updated = self.store.update("proj-paused", paused=True)
        assert updated.paused is True

    def test_update_sets_paused_false(self):
        self.store.update("proj-paused", paused=True)
        updated = self.store.update("proj-paused", paused=False)
        assert updated.paused is False

    def test_update_persists_paused(self, tmp_path):
        self.store.update("proj-paused", paused=True)
        store2 = ProjectStore(
            path=self.store.path,
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        assert store2.get("proj-paused").paused is True


# ---------------------------------------------------------------------------
# Orchestrator helper: _is_project_paused
# ---------------------------------------------------------------------------


class TestIsProjectPaused:
    def test_none_project_id_returns_false(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        assert orch._is_project_paused(None) is False

    def test_unknown_project_returns_false(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        assert orch._is_project_paused("proj-unknown") is False

    def test_unpaused_project_returns_false(self, tmp_path):
        proj = _make_project_mock("proj-1", paused=False)
        orch = _make_orchestrator(tmp_path, projects=[proj])
        assert orch._is_project_paused("proj-1") is False

    def test_paused_project_returns_true(self, tmp_path):
        proj = _make_project_mock("proj-1", paused=True)
        orch = _make_orchestrator(tmp_path, projects=[proj])
        assert orch._is_project_paused("proj-1") is True


# ---------------------------------------------------------------------------
# _should_dispatch gating
# ---------------------------------------------------------------------------


class TestShouldDispatchProjectPauseGate:
    def test_unpaused_project_dispatches(self, tmp_path):
        proj = _make_project_mock("proj-1", paused=False)
        orch = _make_orchestrator(tmp_path, projects=[proj])
        issue = _make_issue("issue-1", project_id="proj-1")
        assert orch._should_dispatch(issue) is True

    def test_paused_project_rejects(self, tmp_path):
        proj = _make_project_mock("proj-1", paused=True)
        orch = _make_orchestrator(tmp_path, projects=[proj])
        issue = _make_issue("issue-1", project_id="proj-1")
        assert orch._should_dispatch(issue) is False

    def test_paused_project_reject_reason_is_project_paused(self, tmp_path):
        proj = _make_project_mock("proj-1", paused=True)
        orch = _make_orchestrator(tmp_path, projects=[proj])
        issue = _make_issue("issue-1", project_id="proj-1")
        orch._should_dispatch(issue)
        reason, _ = orch.state.reject_streak.get("issue-1", ("", 0))
        assert reason == "project_paused"

    def test_pause_does_not_block_other_project(self, tmp_path):
        """Pausing proj-a must not affect proj-b dispatch."""
        proj_a = _make_project_mock("proj-a", paused=True)
        proj_b = _make_project_mock("proj-b", paused=False)
        orch = _make_orchestrator(tmp_path, projects=[proj_a, proj_b])
        issue_a = _make_issue("issue-a", project_id="proj-a")
        issue_b = _make_issue("issue-b", project_id="proj-b")
        assert orch._should_dispatch(issue_a) is False
        assert orch._should_dispatch(issue_b) is True

    def test_p0_does_not_bypass_project_pause(self, tmp_path):
        """A paused project should hold even P0 issues — operators
        explicitly took the project offline (forge down, CI offline,
        bead tracker corrupted) and don't want anything dispatched."""
        proj = _make_project_mock("proj-1", paused=True)
        orch = _make_orchestrator(tmp_path, projects=[proj])
        issue = _make_issue("issue-p0", project_id="proj-1", priority=0)
        assert orch._should_dispatch(issue) is False
        reason, _ = orch.state.reject_streak.get("issue-p0", ("", 0))
        assert reason == "project_paused"

    def test_no_project_id_not_gated(self, tmp_path):
        """Issues with no project_id skip the project-pause gate entirely."""
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue("issue-legacy", project_id=None)
        result = orch._should_dispatch(issue)
        reason, _ = orch.state.reject_streak.get("issue-legacy", ("", 0))
        assert reason != "project_paused"

    def test_global_pause_takes_precedence(self, tmp_path):
        """When both global and project paused, reason is global 'paused'
        (reflects the order: global pause checked first, since it is the
        broader, operator-set state)."""
        proj = _make_project_mock("proj-1", paused=True)
        orch = _make_orchestrator(tmp_path, projects=[proj])
        orch._paused = True
        issue = _make_issue("issue-1", project_id="proj-1")
        assert orch._should_dispatch(issue) is False
        reason, _ = orch.state.reject_streak.get("issue-1", ("", 0))
        assert reason == "paused"

    def test_unpaused_global_paused_project_rejects(self, tmp_path):
        """Composition: global is unpaused but project is paused → rejected."""
        proj = _make_project_mock("proj-1", paused=True)
        orch = _make_orchestrator(tmp_path, projects=[proj])
        assert orch._paused is False
        issue = _make_issue("issue-1", project_id="proj-1")
        assert orch._should_dispatch(issue) is False

    def test_unpaused_global_unpaused_project_dispatches(self, tmp_path):
        """Composition: both unpaused → dispatch allowed."""
        proj = _make_project_mock("proj-1", paused=False)
        orch = _make_orchestrator(tmp_path, projects=[proj])
        assert orch._paused is False
        issue = _make_issue("issue-1", project_id="proj-1")
        assert orch._should_dispatch(issue) is True


# ---------------------------------------------------------------------------
# Epic planning gate
# ---------------------------------------------------------------------------


class TestShouldDispatchEpicProjectPauseGate:
    def test_paused_project_blocks_epic(self, tmp_path):
        proj = _make_project_mock("proj-1", paused=True)
        orch = _make_orchestrator(tmp_path, projects=[proj])
        epic = _make_issue("epic-1", project_id="proj-1", issue_type="epic")
        assert orch._should_dispatch_epic(epic) is False


# ---------------------------------------------------------------------------
# Server API
# ---------------------------------------------------------------------------


class TestProjectPauseAPI:
    @pytest.fixture(autouse=True)
    def client(self, tmp_path):
        from fastapi.testclient import TestClient
        from oompah.server import app
        import oompah.server as srv

        store = ProjectStore(
            path=str(tmp_path / "projects.json"),
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        p = Project(
            id="proj-api",
            name="apitest",
            repo_url="https://github.com/org/apitest.git",
            repo_path=str(tmp_path / "repos" / "apitest"),
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

        old_orch = srv._orchestrator
        srv._orchestrator = orch
        self.client = TestClient(app)
        self.store = store
        yield
        srv._orchestrator = old_orch

    def test_pause_endpoint_sets_paused_true(self):
        res = self.client.post("/api/v1/projects/proj-api/pause")
        assert res.status_code == 200
        body = res.json()
        assert body["ok"] is True
        assert body["paused"] is True
        assert body["id"] == "proj-api"
        assert self.store.get("proj-api").paused is True

    def test_resume_endpoint_sets_paused_false(self):
        # First pause
        self.store.update("proj-api", paused=True)
        res = self.client.post("/api/v1/projects/proj-api/resume")
        assert res.status_code == 200
        body = res.json()
        assert body["ok"] is True
        assert body["paused"] is False
        assert self.store.get("proj-api").paused is False

    def test_pause_unknown_project_returns_404(self):
        res = self.client.post("/api/v1/projects/proj-nope/pause")
        assert res.status_code == 404
        assert res.json()["error"]["code"] == "not_found"

    def test_resume_unknown_project_returns_404(self):
        res = self.client.post("/api/v1/projects/proj-nope/resume")
        assert res.status_code == 404
        assert res.json()["error"]["code"] == "not_found"

    def test_pause_persists_to_disk(self, tmp_path):
        self.client.post("/api/v1/projects/proj-api/pause")
        # Reload the store from disk
        store2 = ProjectStore(
            path=self.store.path,
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        assert store2.get("proj-api").paused is True

    def test_get_project_includes_paused(self):
        res = self.client.get("/api/v1/projects/proj-api")
        assert res.status_code == 200
        assert res.json()["paused"] is False

    def test_list_projects_includes_paused(self):
        res = self.client.get("/api/v1/projects")
        assert res.status_code == 200
        rows = res.json()
        assert len(rows) >= 1
        assert "paused" in rows[0]

    def test_patch_project_can_set_paused(self):
        res = self.client.patch(
            "/api/v1/projects/proj-api",
            json={"paused": True},
        )
        assert res.status_code == 200
        assert res.json()["paused"] is True
        assert self.store.get("proj-api").paused is True


# ---------------------------------------------------------------------------
# State snapshot
# ---------------------------------------------------------------------------


class TestStateSnapshotExposesPaused:
    def test_projects_in_snapshot_include_paused(self, tmp_path):
        proj = Project(
            id="proj-snap",
            name="snaptest",
            repo_url="https://github.com/org/snaptest.git",
            repo_path=str(tmp_path / "repos" / "snaptest"),
            branch="main",
            paused=True,
        )
        store = ProjectStore(
            path=str(tmp_path / "projects.json"),
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        store._projects[proj.id] = proj
        store._save()

        # Reload so from_dict is exercised
        store2 = ProjectStore(
            path=str(tmp_path / "projects.json"),
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        orch = Orchestrator(
            config=_make_config(),
            workflow_path="WORKFLOW.md",
            project_store=store2,
            state_path=str(tmp_path / "state.json"),
        )
        snapshot = orch.get_snapshot()
        projects = snapshot["projects"]
        assert any(
            p.get("id") == "proj-snap" and p.get("paused") is True for p in projects
        )

    def test_unpaused_project_paused_flag_is_false(self, tmp_path):
        proj = Project(
            id="proj-snap2",
            name="snaptest2",
            repo_url="https://github.com/org/snaptest2.git",
            repo_path=str(tmp_path / "repos" / "snaptest2"),
            branch="main",
        )
        store = ProjectStore(
            path=str(tmp_path / "projects.json"),
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        store._projects[proj.id] = proj
        store._save()
        orch = Orchestrator(
            config=_make_config(),
            workflow_path="WORKFLOW.md",
            project_store=store,
            state_path=str(tmp_path / "state.json"),
        )
        snapshot = orch.get_snapshot()
        projects = snapshot["projects"]
        match = [p for p in projects if p.get("id") == "proj-snap2"]
        assert len(match) == 1
        assert match[0]["paused"] is False
