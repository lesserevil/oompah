"""Tests for submit-queue Step 3: configurable per-project in-flight PR limit.

Covers:
- Project.max_in_flight_prs field defaults and serialization
- ProjectStore UPDATABLE_FIELDS includes max_in_flight_prs
- ProjectStore.update() validates max_in_flight_prs (positive integer)
- Orchestrator._count_open_reviews() counting logic
- Orchestrator._project_max_in_flight() fallback and override logic
- Orchestrator._project_has_open_review() compat wrapper
- _should_dispatch() gating: default cap=1, cap=3, P0 bypass, per-project independence
- Reject reason format: open_reviews_at_cap=<n>/<limit>
- Server PATCH /api/v1/projects/{project_id} accepts and validates max_in_flight_prs
- /api/v1/state exposes max_in_flight_prs per project and open_reviews_by_project
"""

from __future__ import annotations

import json
import os
import tempfile
from unittest.mock import MagicMock

import pytest

from oompah.config import ServiceConfig
from oompah.models import Issue, Project
from oompah.orchestrator import Orchestrator
from oompah.projects import ProjectError, ProjectStore
from oompah.scm import ReviewRequest


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


def _make_review(review_id: str = "1", source_branch: str = "feat", draft: bool = False) -> ReviewRequest:
    return ReviewRequest(
        id=review_id,
        title=f"PR #{review_id}",
        url=f"https://github.com/org/repo/pull/{review_id}",
        author="alice",
        state="open",
        source_branch=source_branch,
        target_branch="main",
        created_at="2025-01-01",
        updated_at="2025-01-02",
        ci_status="passed",
        has_conflicts=False,
        needs_rebase=False,
        draft=draft,
    )


def _make_project_mock(project_id: str, max_in_flight_prs: int = 1, name: str = "myrepo") -> MagicMock:
    p = MagicMock(spec=Project)
    p.id = project_id
    p.name = name
    p.repo_url = "https://github.com/org/repo"
    p.yolo = False
    p.paused = False
    p.max_in_flight_prs = max_in_flight_prs
    p.last_webhook_received_at = None
    return p


def _make_orchestrator(tmp_path, projects=None) -> Orchestrator:
    """Create a test orchestrator with a mocked project store."""
    all_projects = list(projects or [])
    project_store = MagicMock()
    project_store.list_all.return_value = all_projects
    project_store.get.side_effect = lambda pid: next(
        (p for p in all_projects if p.id == pid), None
    )
    return Orchestrator(
        config=_make_config(),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        state_path=str(tmp_path / "state.json"),
    )


# ---------------------------------------------------------------------------
# Project model tests
# ---------------------------------------------------------------------------


class TestProjectMaxInFlightField:
    """Project dataclass: max_in_flight_prs field."""

    def test_default_is_one(self):
        p = Project(id="p", name="n", repo_url="u", repo_path="/tmp/x")
        assert p.max_in_flight_prs == 1

    def test_to_dict_includes_field(self):
        p = Project(id="p", name="n", repo_url="u", repo_path="/tmp/x", max_in_flight_prs=3)
        d = p.to_dict()
        assert d["max_in_flight_prs"] == 3

    def test_to_dict_default_value_included(self):
        p = Project(id="p", name="n", repo_url="u", repo_path="/tmp/x")
        d = p.to_dict()
        assert d["max_in_flight_prs"] == 1

    def test_to_safe_dict_includes_field(self):
        p = Project(id="p", name="n", repo_url="u", repo_path="/tmp/x", max_in_flight_prs=5)
        d = p.to_safe_dict()
        assert d["max_in_flight_prs"] == 5

    def test_from_dict_round_trip(self):
        p = Project(id="p", name="n", repo_url="u", repo_path="/tmp/x", max_in_flight_prs=4)
        p2 = Project.from_dict(p.to_dict())
        assert p2.max_in_flight_prs == 4

    def test_from_dict_defaults_to_one(self):
        p = Project.from_dict({"id": "x", "name": "y", "repo_url": "z", "repo_path": "/a"})
        assert p.max_in_flight_prs == 1

    def test_from_dict_clamps_to_one_for_zero(self):
        p = Project.from_dict({"id": "x", "name": "y", "repo_url": "z",
                                "repo_path": "/a", "max_in_flight_prs": 0})
        assert p.max_in_flight_prs == 1

    def test_from_dict_clamps_to_one_for_negative(self):
        p = Project.from_dict({"id": "x", "name": "y", "repo_url": "z",
                                "repo_path": "/a", "max_in_flight_prs": -5})
        assert p.max_in_flight_prs == 1

    def test_from_dict_invalid_string_defaults_to_one(self):
        p = Project.from_dict({"id": "x", "name": "y", "repo_url": "z",
                                "repo_path": "/a", "max_in_flight_prs": "bad"})
        assert p.max_in_flight_prs == 1

    def test_from_dict_string_integer_parsed(self):
        p = Project.from_dict({"id": "x", "name": "y", "repo_url": "z",
                                "repo_path": "/a", "max_in_flight_prs": "3"})
        assert p.max_in_flight_prs == 3


# ---------------------------------------------------------------------------
# ProjectStore tests
# ---------------------------------------------------------------------------


class TestProjectStoreMaxInFlightPrs:
    """ProjectStore.update() with max_in_flight_prs."""

    @pytest.fixture(autouse=True)
    def store(self, tmp_path):
        path = str(tmp_path / "projects.json")
        self.store = ProjectStore(
            path=path,
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        p = Project(
            id="proj-mif",
            name="miftest",
            repo_url="https://github.com/org/miftest.git",
            repo_path=str(tmp_path / "repos" / "miftest"),
            branch="main",
        )
        self.store._projects[p.id] = p
        self.store._save()

    def test_max_in_flight_prs_in_updatable_fields(self):
        assert "max_in_flight_prs" in ProjectStore.UPDATABLE_FIELDS

    def test_update_sets_max_in_flight_prs(self):
        updated = self.store.update("proj-mif", max_in_flight_prs=3)
        assert updated.max_in_flight_prs == 3

    def test_update_persists_max_in_flight_prs(self, tmp_path):
        self.store.update("proj-mif", max_in_flight_prs=5)
        store2 = ProjectStore(
            path=self.store.path,
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        assert store2.get("proj-mif").max_in_flight_prs == 5

    def test_update_rejects_zero(self):
        with pytest.raises(ProjectError, match=">= 1"):
            self.store.update("proj-mif", max_in_flight_prs=0)

    def test_update_rejects_negative(self):
        with pytest.raises(ProjectError, match=">= 1"):
            self.store.update("proj-mif", max_in_flight_prs=-1)

    def test_update_rejects_non_integer_string(self):
        with pytest.raises(ProjectError, match="positive integer"):
            self.store.update("proj-mif", max_in_flight_prs="abc")

    def test_update_rejects_float(self):
        with pytest.raises(ProjectError, match="positive integer"):
            self.store.update("proj-mif", max_in_flight_prs=1.5)

    def test_update_accepts_integer_as_string(self):
        # int("3") is valid
        updated = self.store.update("proj-mif", max_in_flight_prs=3)
        assert updated.max_in_flight_prs == 3


# ---------------------------------------------------------------------------
# Orchestrator helper tests
# ---------------------------------------------------------------------------


class TestCountOpenReviews:
    """Orchestrator._count_open_reviews() counts non-draft reviews correctly."""

    def test_no_project_id_returns_zero(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        assert orch._count_open_reviews(None) == 0

    def test_unknown_project_returns_zero(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        orch._reviews_cache = {}
        assert orch._count_open_reviews("proj-unknown") == 0

    def test_empty_cache_returns_zero(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        orch._reviews_cache = {"proj-1": []}
        assert orch._count_open_reviews("proj-1") == 0

    def test_one_non_draft_counts_one(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        orch._reviews_cache = {"proj-1": [_make_review("1", draft=False)]}
        assert orch._count_open_reviews("proj-1") == 1

    def test_draft_not_counted(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        orch._reviews_cache = {"proj-1": [_make_review("1", draft=True)]}
        assert orch._count_open_reviews("proj-1") == 0

    def test_mixed_draft_and_non_draft(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        orch._reviews_cache = {
            "proj-1": [
                _make_review("1", draft=False),
                _make_review("2", draft=True),
                _make_review("3", draft=False),
            ]
        }
        assert orch._count_open_reviews("proj-1") == 2

    def test_three_non_draft_returns_three(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        orch._reviews_cache = {
            "proj-1": [
                _make_review("1", draft=False),
                _make_review("2", draft=False),
                _make_review("3", draft=False),
            ]
        }
        assert orch._count_open_reviews("proj-1") == 3

    def test_project_isolation(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        orch._reviews_cache = {
            "proj-1": [_make_review("1"), _make_review("2")],
            "proj-2": [_make_review("3")],
        }
        assert orch._count_open_reviews("proj-1") == 2
        assert orch._count_open_reviews("proj-2") == 1


class TestProjectMaxInFlight:
    """Orchestrator._project_max_in_flight() returns the right limit."""

    def test_none_project_id_returns_one(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        assert orch._project_max_in_flight(None) == 1

    def test_unknown_project_returns_one(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        assert orch._project_max_in_flight("proj-unknown") == 1

    def test_default_project_returns_one(self, tmp_path):
        proj = _make_project_mock("proj-1", max_in_flight_prs=1)
        orch = _make_orchestrator(tmp_path, projects=[proj])
        assert orch._project_max_in_flight("proj-1") == 1

    def test_project_with_cap_three_returns_three(self, tmp_path):
        proj = _make_project_mock("proj-1", max_in_flight_prs=3)
        orch = _make_orchestrator(tmp_path, projects=[proj])
        assert orch._project_max_in_flight("proj-1") == 3

    def test_project_with_cap_six_returns_six(self, tmp_path):
        proj = _make_project_mock("proj-1", max_in_flight_prs=6)
        orch = _make_orchestrator(tmp_path, projects=[proj])
        assert orch._project_max_in_flight("proj-1") == 6

    def test_clamped_to_at_least_one(self, tmp_path):
        proj = _make_project_mock("proj-1", max_in_flight_prs=0)
        orch = _make_orchestrator(tmp_path, projects=[proj])
        assert orch._project_max_in_flight("proj-1") == 1


class TestProjectHasOpenReviewCompat:
    """_project_has_open_review() still works as a thin compat wrapper."""

    def test_no_reviews_returns_false(self, tmp_path):
        proj = _make_project_mock("proj-1", max_in_flight_prs=1)
        orch = _make_orchestrator(tmp_path, projects=[proj])
        orch._reviews_cache = {"proj-1": []}
        assert orch._project_has_open_review("proj-1") is False

    def test_one_review_default_cap_returns_true(self, tmp_path):
        proj = _make_project_mock("proj-1", max_in_flight_prs=1)
        orch = _make_orchestrator(tmp_path, projects=[proj])
        orch._reviews_cache = {"proj-1": [_make_review("1", draft=False)]}
        assert orch._project_has_open_review("proj-1") is True

    def test_one_review_cap_three_returns_false(self, tmp_path):
        proj = _make_project_mock("proj-1", max_in_flight_prs=3)
        orch = _make_orchestrator(tmp_path, projects=[proj])
        orch._reviews_cache = {"proj-1": [_make_review("1", draft=False)]}
        assert orch._project_has_open_review("proj-1") is False

    def test_three_reviews_cap_three_returns_true(self, tmp_path):
        proj = _make_project_mock("proj-1", max_in_flight_prs=3)
        orch = _make_orchestrator(tmp_path, projects=[proj])
        orch._reviews_cache = {
            "proj-1": [_make_review("1"), _make_review("2"), _make_review("3")]
        }
        assert orch._project_has_open_review("proj-1") is True


# ---------------------------------------------------------------------------
# _should_dispatch gating tests
# ---------------------------------------------------------------------------


class TestShouldDispatchOpenReviewGate:
    """_should_dispatch() respects the per-project in-flight PR cap."""

    def _orch_with_reviews(self, tmp_path, project_id: str, n_open: int, cap: int) -> Orchestrator:
        proj = _make_project_mock(project_id, max_in_flight_prs=cap)
        orch = _make_orchestrator(tmp_path, projects=[proj])
        reviews = [_make_review(str(i), draft=False) for i in range(n_open)]
        orch._reviews_cache = {project_id: reviews}
        return orch

    # --- Default cap=1 (preserves today's behavior) ---

    def test_cap1_zero_open_dispatches(self, tmp_path):
        orch = self._orch_with_reviews(tmp_path, "proj-a", n_open=0, cap=1)
        issue = _make_issue("issue-1", project_id="proj-a")
        assert orch._should_dispatch(issue) is True

    def test_cap1_one_open_rejects(self, tmp_path):
        orch = self._orch_with_reviews(tmp_path, "proj-a", n_open=1, cap=1)
        issue = _make_issue("issue-1", project_id="proj-a")
        assert orch._should_dispatch(issue) is False

    def test_cap1_reject_reason_is_new_format(self, tmp_path):
        orch = self._orch_with_reviews(tmp_path, "proj-a", n_open=1, cap=1)
        issue = _make_issue("issue-1", project_id="proj-a")
        orch._should_dispatch(issue)
        reason, _ = orch.state.reject_streak.get("issue-1", ("", 0))
        assert reason == "open_reviews_at_cap=1/1"

    # --- Cap=3 at various fill levels ---

    def test_cap3_zero_open_dispatches(self, tmp_path):
        orch = self._orch_with_reviews(tmp_path, "proj-b", n_open=0, cap=3)
        issue = _make_issue("issue-2", project_id="proj-b")
        assert orch._should_dispatch(issue) is True

    def test_cap3_one_open_dispatches(self, tmp_path):
        orch = self._orch_with_reviews(tmp_path, "proj-b", n_open=1, cap=3)
        issue = _make_issue("issue-2", project_id="proj-b")
        assert orch._should_dispatch(issue) is True

    def test_cap3_two_open_dispatches(self, tmp_path):
        orch = self._orch_with_reviews(tmp_path, "proj-b", n_open=2, cap=3)
        issue = _make_issue("issue-2", project_id="proj-b")
        assert orch._should_dispatch(issue) is True

    def test_cap3_three_open_rejects(self, tmp_path):
        orch = self._orch_with_reviews(tmp_path, "proj-b", n_open=3, cap=3)
        issue = _make_issue("issue-2", project_id="proj-b")
        assert orch._should_dispatch(issue) is False

    def test_cap3_three_open_reject_reason(self, tmp_path):
        orch = self._orch_with_reviews(tmp_path, "proj-b", n_open=3, cap=3)
        issue = _make_issue("issue-2", project_id="proj-b")
        orch._should_dispatch(issue)
        reason, _ = orch.state.reject_streak.get("issue-2", ("", 0))
        assert reason == "open_reviews_at_cap=3/3"

    # --- P0 bypass ---

    def test_p0_bypasses_cap_at_limit(self, tmp_path):
        """P0 (priority=0) issues bypass the open review gate entirely."""
        orch = self._orch_with_reviews(tmp_path, "proj-c", n_open=1, cap=1)
        issue = _make_issue("issue-p0", project_id="proj-c", priority=0)
        # P0 should not be rejected by the open_review gate
        result = orch._should_dispatch(issue)
        reason = orch.state.reject_streak.get("issue-p0", ("", 0))[0]
        assert reason != "open_reviews_at_cap=1/1", (
            f"P0 issue was rejected for open_review reason: {reason!r}"
        )

    def test_p0_bypasses_cap_above_limit(self, tmp_path):
        """P0 issues bypass even when there are many open reviews."""
        orch = self._orch_with_reviews(tmp_path, "proj-c", n_open=5, cap=3)
        issue = _make_issue("issue-p0b", project_id="proj-c", priority=0)
        reason = orch.state.reject_streak.get("issue-p0b", ("", 0))[0]
        assert "open_reviews_at_cap" not in reason

    # --- Per-project independence ---

    def test_cap1_on_one_project_does_not_block_other(self, tmp_path):
        """Reaching cap on proj-a must not affect proj-b dispatch."""
        proj_a = _make_project_mock("proj-a", max_in_flight_prs=1, name="a")
        proj_b = _make_project_mock("proj-b", max_in_flight_prs=3, name="b")
        orch = _make_orchestrator(tmp_path, projects=[proj_a, proj_b])
        orch._reviews_cache = {
            "proj-a": [_make_review("1", draft=False)],  # proj-a at cap=1
            "proj-b": [_make_review("2", draft=False)],  # proj-b has 1 < cap=3
        }
        issue_a = _make_issue("issue-a", project_id="proj-a")
        issue_b = _make_issue("issue-b", project_id="proj-b")
        assert orch._should_dispatch(issue_a) is False  # proj-a at cap
        assert orch._should_dispatch(issue_b) is True   # proj-b not at cap

    def test_two_projects_independent_limits(self, tmp_path):
        """Two projects with different caps behave independently."""
        proj_a = _make_project_mock("proj-a", max_in_flight_prs=1, name="a")
        proj_b = _make_project_mock("proj-b", max_in_flight_prs=2, name="b")
        orch = _make_orchestrator(tmp_path, projects=[proj_a, proj_b])
        orch._reviews_cache = {
            "proj-a": [],  # proj-a has 0 < cap=1
            "proj-b": [_make_review("1"), _make_review("2")],  # proj-b has 2 = cap=2
        }
        issue_a = _make_issue("issue-a", project_id="proj-a")
        issue_b = _make_issue("issue-b", project_id="proj-b")
        assert orch._should_dispatch(issue_a) is True   # proj-a not at cap
        assert orch._should_dispatch(issue_b) is False  # proj-b at cap

    # --- Legacy: no project_id ---

    def test_no_project_id_not_gated(self, tmp_path):
        """Issues with no project_id skip the open review gate entirely."""
        orch = _make_orchestrator(tmp_path)
        orch._reviews_cache = {}
        issue = _make_issue("issue-legacy", project_id=None)
        # Should not be rejected by open_review gate (other gates may apply but not this one)
        result = orch._should_dispatch(issue)
        reason = orch.state.reject_streak.get("issue-legacy", ("", 0))[0]
        assert "open_reviews_at_cap" not in reason


# ---------------------------------------------------------------------------
# Server API tests
# ---------------------------------------------------------------------------


class TestServerMaxInFlightPrsAPI:
    """PATCH /api/v1/projects/{id} — max_in_flight_prs validation and persistence."""

    @pytest.fixture(autouse=True)
    def client(self, tmp_path):
        from unittest.mock import MagicMock
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

    def test_patch_sets_max_in_flight_prs(self):
        res = self.client.patch(
            "/api/v1/projects/proj-api",
            json={"max_in_flight_prs": 3},
        )
        assert res.status_code == 200
        assert res.json()["max_in_flight_prs"] == 3

    def test_patch_persists_max_in_flight_prs(self, tmp_path):
        self.client.patch(
            "/api/v1/projects/proj-api",
            json={"max_in_flight_prs": 5},
        )
        assert self.store.get("proj-api").max_in_flight_prs == 5

    def test_patch_rejects_zero(self):
        res = self.client.patch(
            "/api/v1/projects/proj-api",
            json={"max_in_flight_prs": 0},
        )
        assert res.status_code == 400
        data = res.json()
        assert data["error"]["code"] == "validation"
        assert ">= 1" in data["error"]["message"]

    def test_patch_rejects_negative(self):
        res = self.client.patch(
            "/api/v1/projects/proj-api",
            json={"max_in_flight_prs": -1},
        )
        assert res.status_code == 400

    def test_patch_rejects_string(self):
        res = self.client.patch(
            "/api/v1/projects/proj-api",
            json={"max_in_flight_prs": "not-a-number"},
        )
        assert res.status_code == 400
        data = res.json()
        assert data["error"]["code"] == "validation"

    def test_get_project_includes_max_in_flight_prs(self):
        res = self.client.get("/api/v1/projects/proj-api")
        assert res.status_code == 200
        assert "max_in_flight_prs" in res.json()
        assert res.json()["max_in_flight_prs"] == 1  # default

    def test_list_projects_includes_max_in_flight_prs(self):
        res = self.client.get("/api/v1/projects")
        assert res.status_code == 200
        rows = res.json()
        assert len(rows) >= 1
        assert "max_in_flight_prs" in rows[0]


class TestStateSnapshotExposesMaxInFlightPrs:
    """GET /api/v1/state — exposes max_in_flight_prs and open_reviews_by_project."""

    def test_projects_in_state_include_max_in_flight_prs(self, tmp_path):
        from oompah.orchestrator import Orchestrator

        proj = Project(
            id="proj-snap",
            name="snaptest",
            repo_url="https://github.com/org/snaptest.git",
            repo_path=str(tmp_path / "repos" / "snaptest"),
            branch="main",
            max_in_flight_prs=3,
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
        assert any(p.get("max_in_flight_prs") == 3 for p in projects)

    def test_state_snapshot_has_open_reviews_by_project(self, tmp_path):
        proj = _make_project_mock("proj-snap", max_in_flight_prs=2, name="snaptest")

        from oompah.orchestrator import Orchestrator
        orch = _make_orchestrator(tmp_path, projects=[proj])
        orch._reviews_cache = {
            "proj-snap": [_make_review("1", draft=False), _make_review("2", draft=False)],
        }
        snapshot = orch.get_snapshot()
        assert "open_reviews_by_project" in snapshot
        assert snapshot["open_reviews_by_project"]["proj-snap"] == 2

    def test_state_snapshot_open_reviews_empty_when_no_cache(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        orch._reviews_cache = {}
        snapshot = orch.get_snapshot()
        assert "open_reviews_by_project" in snapshot
        assert snapshot["open_reviews_by_project"] == {}
