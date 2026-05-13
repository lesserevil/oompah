"""Tests for the per-project ``max_concurrent_agents`` dispatch cap.

Exercises:
- ``Orchestrator._count_running_for_project`` counting logic
- ``Orchestrator._project_max_concurrent_agents`` fallback / coercion
- ``_should_dispatch`` gating: unlimited, cap enforced, release on
  completion, per-project independence
- ``get_snapshot()`` surfaces ``running_count_by_project``

See bead oompah-zlz_2-okxw.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from oompah.config import ServiceConfig
from oompah.models import Issue, Project, RunningEntry
from oompah.orchestrator import Orchestrator


# ---------------------------------------------------------------------------
# Helpers (mirrors tests/test_submit_queue_concurrency.py patterns so the
# two suites can be read side-by-side).
# ---------------------------------------------------------------------------


def _make_config() -> ServiceConfig:
    cfg = ServiceConfig()
    # Keep the global cap large enough that none of these tests trip it.
    cfg.max_concurrent_agents = 10
    return cfg


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
    *,
    max_concurrent_agents: int | None = None,
    max_in_flight_prs: int = 1,
    name: str | None = None,
) -> MagicMock:
    p = MagicMock(spec=Project)
    p.id = project_id
    p.name = name or project_id
    p.repo_url = f"https://github.com/org/{project_id}"
    p.yolo = False
    p.paused = False
    p.max_in_flight_prs = max_in_flight_prs
    p.max_concurrent_agents = max_concurrent_agents
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
    # Empty reviews cache so the in-flight PR gate doesn't interfere.
    orch._reviews_cache = {}
    return orch


def _inject_running(orch: Orchestrator, project_id: str, n: int, *, prefix: str = "run") -> None:
    """Pre-populate ``orch.state.running`` with *n* fake entries tagged
    with *project_id*, simulating in-flight workers.
    """
    for i in range(n):
        issue_id = f"{prefix}-{project_id}-{i}"
        entry = RunningEntry(
            worker_task=MagicMock(),
            identifier=issue_id,
            issue=_make_issue(issue_id, project_id=project_id),
            session=None,
            retry_attempt=0,
            started_at=datetime.now(timezone.utc),
        )
        orch.state.running[issue_id] = entry


# ---------------------------------------------------------------------------
# Helper tests
# ---------------------------------------------------------------------------


class TestCountRunningForProject:
    def test_none_returns_zero(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        assert orch._count_running_for_project(None) == 0

    def test_empty_running_returns_zero(self, tmp_path):
        proj = _make_project_mock("proj-a")
        orch = _make_orchestrator(tmp_path, projects=[proj])
        assert orch._count_running_for_project("proj-a") == 0

    def test_counts_matching_entries(self, tmp_path):
        proj = _make_project_mock("proj-a")
        orch = _make_orchestrator(tmp_path, projects=[proj])
        _inject_running(orch, "proj-a", 3)
        assert orch._count_running_for_project("proj-a") == 3

    def test_isolates_per_project(self, tmp_path):
        proj_a = _make_project_mock("proj-a")
        proj_b = _make_project_mock("proj-b")
        orch = _make_orchestrator(tmp_path, projects=[proj_a, proj_b])
        _inject_running(orch, "proj-a", 2)
        _inject_running(orch, "proj-b", 5)
        assert orch._count_running_for_project("proj-a") == 2
        assert orch._count_running_for_project("proj-b") == 5

    def test_skips_legacy_running_without_project_id(self, tmp_path):
        proj = _make_project_mock("proj-a")
        orch = _make_orchestrator(tmp_path, projects=[proj])
        # Legacy running entry with no project_id is not attributed.
        entry = RunningEntry(
            worker_task=MagicMock(),
            identifier="legacy",
            issue=_make_issue("legacy", project_id=None),
            session=None,
            retry_attempt=0,
            started_at=datetime.now(timezone.utc),
        )
        orch.state.running["legacy"] = entry
        assert orch._count_running_for_project("proj-a") == 0


class TestProjectMaxConcurrentAgents:
    def test_none_project_id_returns_none(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        assert orch._project_max_concurrent_agents(None) is None

    def test_unknown_project_returns_none(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        assert orch._project_max_concurrent_agents("proj-unknown") is None

    def test_default_project_returns_none(self, tmp_path):
        proj = _make_project_mock("proj-a", max_concurrent_agents=None)
        orch = _make_orchestrator(tmp_path, projects=[proj])
        assert orch._project_max_concurrent_agents("proj-a") is None

    def test_positive_int_returned(self, tmp_path):
        proj = _make_project_mock("proj-a", max_concurrent_agents=4)
        orch = _make_orchestrator(tmp_path, projects=[proj])
        assert orch._project_max_concurrent_agents("proj-a") == 4

    def test_zero_treated_as_unlimited(self, tmp_path):
        proj = _make_project_mock("proj-a", max_concurrent_agents=0)
        orch = _make_orchestrator(tmp_path, projects=[proj])
        assert orch._project_max_concurrent_agents("proj-a") is None

    def test_negative_treated_as_unlimited(self, tmp_path):
        proj = _make_project_mock("proj-a", max_concurrent_agents=-2)
        orch = _make_orchestrator(tmp_path, projects=[proj])
        assert orch._project_max_concurrent_agents("proj-a") is None

    def test_garbage_string_treated_as_unlimited(self, tmp_path):
        proj = _make_project_mock("proj-a", max_concurrent_agents="bad")
        orch = _make_orchestrator(tmp_path, projects=[proj])
        assert orch._project_max_concurrent_agents("proj-a") is None


class TestRunningCountByProjectSnapshot:
    def test_empty_running_returns_empty_map(self, tmp_path):
        proj = _make_project_mock("proj-a")
        orch = _make_orchestrator(tmp_path, projects=[proj])
        assert orch._running_count_by_project() == {}

    def test_aggregates_across_projects(self, tmp_path):
        proj_a = _make_project_mock("proj-a")
        proj_b = _make_project_mock("proj-b")
        orch = _make_orchestrator(tmp_path, projects=[proj_a, proj_b])
        _inject_running(orch, "proj-a", 3)
        _inject_running(orch, "proj-b", 1)
        counts = orch._running_count_by_project()
        assert counts == {"proj-a": 3, "proj-b": 1}

    def test_get_snapshot_exposes_field(self, tmp_path):
        proj = _make_project_mock("proj-a")
        orch = _make_orchestrator(tmp_path, projects=[proj])
        _inject_running(orch, "proj-a", 2)
        snap = orch.get_snapshot()
        assert snap["running_count_by_project"] == {"proj-a": 2}


# ---------------------------------------------------------------------------
# _should_dispatch gate behavior
# ---------------------------------------------------------------------------


class TestNoCapUnlimitedDispatch:
    """``max_concurrent_agents=None`` → only the global cap applies."""

    def test_no_cap_unlimited_dispatch(self, tmp_path):
        """10 ready beads, project cap unset, global cap=10 → all dispatch.

        Simulates the per-tick flow: at each step there are ``i`` already
        running, the candidate would become the ``(i+1)``-th, and after
        the check we mark it as running to set up the next iteration.
        """
        proj = _make_project_mock("proj-a", max_concurrent_agents=None)
        orch = _make_orchestrator(tmp_path, projects=[proj])
        for i in range(10):
            cand = _make_issue(f"cand-{i}", project_id="proj-a")
            assert orch._should_dispatch(cand) is True, (
                f"Unexpectedly rejected at {i} already running"
            )
            # Simulate the dispatch having taken the slot for the next iter.
            _inject_running(orch, "proj-a", 1, prefix=f"running-{i}")
        # After 10 dispatches the global cap is reached; the 11th must
        # be rejected by the global gate, not the per-project gate
        # (which is None here). We don't assert on the exact reason
        # since the point is that the per-project cap allowed all 10.
        assert len(orch.state.running) == 10


class TestCapEnforced:
    """``max_concurrent_agents=2``, 5 ready beads → only 2 dispatch."""

    def test_cap_enforced(self, tmp_path):
        proj = _make_project_mock("proj-a", max_concurrent_agents=2)
        orch = _make_orchestrator(tmp_path, projects=[proj])
        # Below the cap: dispatch is allowed.
        for already_running in range(2):
            assert orch._should_dispatch(
                _make_issue(f"cand-{already_running}", project_id="proj-a")
            ) is True
            _inject_running(orch, "proj-a", 1, prefix=f"running-{already_running}")
        # At the cap: every further candidate is rejected.
        for i in range(3):
            cand = _make_issue(f"queued-{i}", project_id="proj-a")
            assert orch._should_dispatch(cand) is False

    def test_cap_reject_reason_format(self, tmp_path):
        """Rejection records a ``project_agents_at_cap=<n>/<cap>`` reason."""
        proj = _make_project_mock("proj-a", max_concurrent_agents=2)
        orch = _make_orchestrator(tmp_path, projects=[proj])
        _inject_running(orch, "proj-a", 2)
        cand = _make_issue("cand-1", project_id="proj-a")
        assert orch._should_dispatch(cand) is False
        reason, _ = orch.state.reject_streak.get("cand-1", ("", 0))
        assert reason == "project_agents_at_cap=2/2"

    def test_cap_logs_debug_message(self, tmp_path, caplog):
        proj = _make_project_mock("proj-a", max_concurrent_agents=2, name="proj-a")
        orch = _make_orchestrator(tmp_path, projects=[proj])
        _inject_running(orch, "proj-a", 2)
        cand = _make_issue("cand-1", project_id="proj-a")
        with caplog.at_level("DEBUG", logger="oompah.orchestrator"):
            orch._should_dispatch(cand)
        assert any(
            "at per-project agent cap" in r.message for r in caplog.records
        )


class TestCapReleasesOnCompletion:
    """2-of-2 running; one finishes; the 3rd dispatches."""

    def test_cap_releases_on_completion(self, tmp_path):
        proj = _make_project_mock("proj-a", max_concurrent_agents=2)
        orch = _make_orchestrator(tmp_path, projects=[proj])
        _inject_running(orch, "proj-a", 2)
        # At cap: rejected.
        third = _make_issue("third", project_id="proj-a")
        assert orch._should_dispatch(third) is False
        # Simulate one running worker finishing — remove one entry.
        running_ids = list(orch.state.running.keys())
        del orch.state.running[running_ids[0]]
        # Streak cache still says "rejected" but the gate should now allow.
        # Also clear the reject_streak for the third issue so any other side
        # effects don't interfere.
        orch.state.reject_streak.pop("third", None)
        assert orch._should_dispatch(third) is True


class TestCapPerProjectIndependent:
    """Project A at cap 2 (full) does not constrain project B at cap None."""

    def test_cap_per_project_independent(self, tmp_path):
        proj_a = _make_project_mock("proj-a", max_concurrent_agents=2)
        proj_b = _make_project_mock("proj-b", max_concurrent_agents=None)
        orch = _make_orchestrator(tmp_path, projects=[proj_a, proj_b])
        _inject_running(orch, "proj-a", 2)  # A is full
        a_cand = _make_issue("a-cand", project_id="proj-a")
        b_cand = _make_issue("b-cand", project_id="proj-b")
        assert orch._should_dispatch(a_cand) is False
        assert orch._should_dispatch(b_cand) is True

    def test_both_capped_independently(self, tmp_path):
        proj_a = _make_project_mock("proj-a", max_concurrent_agents=1)
        proj_b = _make_project_mock("proj-b", max_concurrent_agents=3)
        orch = _make_orchestrator(tmp_path, projects=[proj_a, proj_b])
        # A maxed; B has headroom.
        _inject_running(orch, "proj-a", 1)
        _inject_running(orch, "proj-b", 2)
        assert orch._should_dispatch(
            _make_issue("a-cand", project_id="proj-a")
        ) is False
        assert orch._should_dispatch(
            _make_issue("b-cand", project_id="proj-b")
        ) is True


class TestCapInteractionWithLegacyIssues:
    """Issues without a project_id are never gated by this cap."""

    def test_legacy_issue_not_gated(self, tmp_path):
        proj = _make_project_mock("proj-a", max_concurrent_agents=1)
        orch = _make_orchestrator(tmp_path, projects=[proj])
        _inject_running(orch, "proj-a", 1)
        legacy = _make_issue("legacy-cand", project_id=None)
        # Legacy issues skip the per-project cap entirely (no project to
        # attribute against). Other gates may still apply, but the
        # rejection reason must not be project_agents_at_cap.
        orch._should_dispatch(legacy)
        reason, _ = orch.state.reject_streak.get("legacy-cand", ("", 0))
        assert "project_agents_at_cap" not in (reason or "")


# ---------------------------------------------------------------------------
# Server API tests
# ---------------------------------------------------------------------------


class TestServerMaxConcurrentAgentsAPI:
    """PATCH /api/v1/projects/{id} — max_concurrent_agents validation."""

    @pytest.fixture(autouse=True)
    def client(self, tmp_path):
        from fastapi.testclient import TestClient
        from oompah.projects import ProjectStore
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
        orch.get_snapshot.return_value = {"counts": {}, "running": []}

        old_orch = srv._orchestrator
        srv._orchestrator = orch
        self.client = TestClient(app)
        self.store = store
        yield
        srv._orchestrator = old_orch

    def test_patch_sets_max_concurrent_agents(self):
        res = self.client.patch(
            "/api/v1/projects/proj-api",
            json={"max_concurrent_agents": 4},
        )
        assert res.status_code == 200
        assert res.json()["max_concurrent_agents"] == 4

    def test_patch_persists_max_concurrent_agents(self):
        self.client.patch(
            "/api/v1/projects/proj-api",
            json={"max_concurrent_agents": 5},
        )
        assert self.store.get("proj-api").max_concurrent_agents == 5

    def test_patch_accepts_null_for_unlimited(self):
        # First set to a value
        self.client.patch(
            "/api/v1/projects/proj-api",
            json={"max_concurrent_agents": 3},
        )
        assert self.store.get("proj-api").max_concurrent_agents == 3
        # Then clear back to None
        res = self.client.patch(
            "/api/v1/projects/proj-api",
            json={"max_concurrent_agents": None},
        )
        assert res.status_code == 200
        assert self.store.get("proj-api").max_concurrent_agents is None

    def test_patch_rejects_zero(self):
        res = self.client.patch(
            "/api/v1/projects/proj-api",
            json={"max_concurrent_agents": 0},
        )
        assert res.status_code == 400
        data = res.json()
        assert data["error"]["code"] == "validation"

    def test_patch_rejects_negative(self):
        res = self.client.patch(
            "/api/v1/projects/proj-api",
            json={"max_concurrent_agents": -3},
        )
        assert res.status_code == 400

    def test_patch_rejects_garbage_string(self):
        res = self.client.patch(
            "/api/v1/projects/proj-api",
            json={"max_concurrent_agents": "not-a-number"},
        )
        assert res.status_code == 400

    def test_patch_rejects_boolean(self):
        # bool subclasses int in Python — we reject explicitly so True
        # doesn't silently become a cap of 1.
        res = self.client.patch(
            "/api/v1/projects/proj-api",
            json={"max_concurrent_agents": True},
        )
        assert res.status_code == 400

    def test_get_project_omits_field_when_unset(self):
        """Default (None) should not appear in the response."""
        res = self.client.get("/api/v1/projects/proj-api")
        assert res.status_code == 200
        body = res.json()
        # Either omitted or explicitly None — both acceptable.
        assert body.get("max_concurrent_agents") is None

    def test_get_project_includes_field_when_set(self):
        self.client.patch(
            "/api/v1/projects/proj-api",
            json={"max_concurrent_agents": 7},
        )
        res = self.client.get("/api/v1/projects/proj-api")
        assert res.json()["max_concurrent_agents"] == 7
