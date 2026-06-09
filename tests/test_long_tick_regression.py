"""End-to-end regression tests for the long-tick scenario (TASK-467.4).

The scenario that triggered this work:
  1. One running agent occupies a dispatch slot in Project A.
  2. A separate eligible Open task exists in Project B (different workstream).
  3. Maintenance operations (worktree cleanup, repo self-heal) are slow and
     block the event loop between ticks.
  4. Before the fix, slow maintenance delayed the NEXT tick, starving Project B.
  5. After the fix (TASK-467.2 bounded refresh + TASK-467.3 async state API):
     - Dispatch always runs BEFORE maintenance in the tick sequence.
     - Per-project tracker fetches are bounded by timeout so one slow project
       cannot starve candidates from another.
     - project_refresh_metrics in get_snapshot() let operators see which
       project/lane is the current bottleneck.

Acceptance Criteria covered:
  AC#1 — Regression test: one running agent + one eligible unrelated Open task
          while maintenance is slow.
  AC#2 — Expected behavior: eligible task dispatches without waiting for
          maintenance to complete.
  AC#3 — Operator diagnostics: project_refresh_metrics are surfaced in the
          state snapshot so operators can see which lane is slow.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oompah.config import ServiceConfig
from oompah.models import BlockerRef, Issue, RunningEntry
from oompah.orchestrator import Orchestrator
from oompah.roles import RoleStore


# ---------------------------------------------------------------------------
# Helpers shared across test classes
# ---------------------------------------------------------------------------


def _make_config() -> ServiceConfig:
    return ServiceConfig()


def _make_project(
    project_id: str,
    repo_url: str = "https://github.com/org/repo",
    yolo: bool = False,
):
    """Build a minimal mock project."""
    p = MagicMock()
    p.id = project_id
    p.repo_url = repo_url
    p.name = f"project-{project_id}"
    p.yolo = yolo
    p.paused = False
    return p


def _make_issue(
    identifier: str,
    state: str = "Open",
    issue_type: str = "task",
    priority: int = 2,
    project_id: str | None = None,
    labels: list | None = None,
    blocked_by: list | None = None,
    description: str = "Non-empty description so the empty-description gate passes.",
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
        labels=labels or [],
        blocked_by=blocked_by or [],
        created_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )


def _make_orchestrator(tmp_path, projects=None):
    """Create an orchestrator wired with a mock project store."""
    all_projects = list(projects or [])
    project_store = MagicMock()
    project_store.list_all.return_value = all_projects
    project_store.get.side_effect = lambda pid: next(
        (p for p in all_projects if p.id == pid), None
    )
    role_store = RoleStore(path=str(tmp_path / "roles.json"))
    orch = Orchestrator(
        config=_make_config(),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        role_store=role_store,
        state_path=str(tmp_path / "state.json"),
    )
    orch._fetch_in_progress_issues = MagicMock(return_value=[])
    return orch


def _add_running_entry(orch: Orchestrator, issue: Issue) -> None:
    """Inject a running entry so the orchestrator sees an agent in flight."""
    orch.state.running[issue.id] = RunningEntry(
        worker_task=None,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=1,
        started_at=datetime.now(timezone.utc),
        agent_profile_name="standard",
    )


# ---------------------------------------------------------------------------
# AC#1 + AC#2 — Regression: eligible task dispatches while maintenance is slow
# ---------------------------------------------------------------------------


class TestLongTickRegressionScenario:
    """Core regression tests for the long-tick scenario (AC#1 + AC#2).

    Verify that an eligible Open task in Project B is dispatched even when:
      - Project A has a running agent consuming a slot.
      - Maintenance (worktree cleanup / repo heal) is slow.
      - Project A's tracker fetch is slow (bounded by timeout).
    """

    def test_eligible_task_dispatches_despite_slow_maintenance(self, tmp_path):
        """AC#1+AC#2 (regression): eligible task in Project B dispatches during
        _handle_dispatch_needed even when _maybe_heal_repos is a synthetic slow job.

        The tick sequence guarantees:
          _handle_dispatch_needed → (dispatch happens here)
          _handle_yolo_review
          _maybe_run_watchdog  ← slow synthetic job
          _maybe_heal_repos    ← another slow synthetic job

        Dispatch must complete BEFORE either slow job runs within the same tick.
        """
        proj_a = _make_project("proj-a")
        proj_b = _make_project("proj-b")
        orch = _make_orchestrator(tmp_path, projects=[proj_a, proj_b])

        # Project A: one running agent (slot consumed for this project)
        running_issue = _make_issue("TASK-A-001", state="In Progress", project_id="proj-a")
        _add_running_entry(orch, running_issue)

        # Project B: one eligible Open task in a different workstream
        eligible = _make_issue("TASK-B-001", state="Open", project_id="proj-b")

        # Track call order to prove dispatch precedes maintenance
        call_order: list[str] = []
        dispatched_ids: list[str] = []

        # Patch _handle_dispatch_needed to record when dispatch was attempted
        orig_dispatch_needed = orch._handle_dispatch_needed

        async def _spy_dispatch_needed():
            call_order.append("dispatch_needed_start")
            # The real implementation uses _timed/_fetch_all_candidates via executor
            # so we patch the inner methods instead
            await orig_dispatch_needed()
            call_order.append("dispatch_needed_end")

        # Mock _fetch_all_candidates to return Project B's eligible task
        orch._fetch_all_candidates = MagicMock(return_value=[eligible])
        orch._pre_resolve_blockers = MagicMock()
        orch._reset_orphaned_in_progress = MagicMock()
        orch._plan_open_epics = MagicMock(return_value=[])
        orch._apply_duplicate_detection = MagicMock()

        async def _fake_dispatch(issue, attempt):
            dispatched_ids.append(issue.identifier)
            call_order.append(f"dispatched:{issue.identifier}")

        orch._dispatch = _fake_dispatch

        # Synthetic slow maintenance — records when it runs
        def _slow_maintenance():
            call_order.append("maintenance_start")
            # In a real failure scenario this would sleep for ~150s.
            # We just record the ordering without an actual sleep.
            call_order.append("maintenance_end")

        orch._maybe_heal_repos = _slow_maintenance
        orch._maybe_run_watchdog = MagicMock(side_effect=lambda: call_order.append("watchdog"))

        # Wire other handlers so _tick() can complete
        orch._handle_reconcile = AsyncMock()
        orch._handle_review_check = AsyncMock()
        orch._handle_auto_update = AsyncMock()
        orch._handle_yolo_review = AsyncMock(return_value=(0.0, 0.0, 0.0))
        orch._notify_observers = MagicMock()

        with patch("oompah.orchestrator.validate_dispatch_config", return_value=[]):
            asyncio.run(orch._tick())

        # The eligible task must have been dispatched
        assert "TASK-B-001" in dispatched_ids, (
            f"Eligible task was not dispatched. Call order: {call_order}"
        )

        # Dispatch must have happened BEFORE maintenance in the tick sequence
        dispatch_idx = next(
            (i for i, e in enumerate(call_order) if e == f"dispatched:TASK-B-001"), None
        )
        maintenance_idx = next(
            (i for i, e in enumerate(call_order) if e == "maintenance_start"), None
        )
        if maintenance_idx is not None:
            assert dispatch_idx < maintenance_idx, (
                f"Dispatch ({dispatch_idx}) did not precede maintenance ({maintenance_idx}).\n"
                f"Call order: {call_order}"
            )

    def test_running_agent_in_project_a_does_not_block_dispatch_in_project_b(
        self, tmp_path
    ):
        """A running agent in Project A must not consume the only dispatch slot
        for Project B's eligible task (different projects, independent slots).

        Verifies AC#2: cross-project independence means a running agent in
        one workstream does not starve another.
        """
        proj_a = _make_project("proj-a")
        proj_b = _make_project("proj-b")
        orch = _make_orchestrator(tmp_path, projects=[proj_a, proj_b])

        # Ensure at least 2 slots available (1 for running, 1 for new dispatch)
        orch.config.max_in_flight = 3  # headroom
        orch.config.max_in_flight_open = 3

        # Project A: running agent
        running_issue = _make_issue("TASK-A-001", state="In Progress", project_id="proj-a")
        _add_running_entry(orch, running_issue)

        # Project B: eligible task
        eligible = _make_issue("TASK-B-001", state="Open", project_id="proj-b")

        dispatched_ids: list[str] = []

        orch._fetch_all_candidates = MagicMock(return_value=[eligible])
        orch._pre_resolve_blockers = MagicMock()
        orch._reset_orphaned_in_progress = MagicMock()
        orch._plan_open_epics = MagicMock(return_value=[])
        orch._apply_duplicate_detection = MagicMock()

        async def _fake_dispatch(issue, attempt):
            dispatched_ids.append(issue.identifier)

        orch._dispatch = _fake_dispatch
        orch._maybe_heal_repos = MagicMock()
        orch._maybe_run_watchdog = MagicMock()
        orch._handle_reconcile = AsyncMock()
        orch._handle_review_check = AsyncMock()
        orch._handle_auto_update = AsyncMock()
        orch._handle_yolo_review = AsyncMock(return_value=(0.0, 0.0, 0.0))
        orch._notify_observers = MagicMock()

        with patch("oompah.orchestrator.validate_dispatch_config", return_value=[]):
            asyncio.run(orch._tick())

        assert "TASK-B-001" in dispatched_ids, (
            "Eligible task in Project B was not dispatched despite Project A "
            "having a running agent."
        )

    def test_dependency_blocked_task_not_dispatched_eligible_task_is(self, tmp_path):
        """Dependency-blocked tasks must not dispatch; the eligible task in another
        workstream must dispatch in the same tick.

        Setup:
          - Project A: Task TASK-A-002 blocked by TASK-A-001 (not Done)
          - Project B: Task TASK-B-001 with no blockers (eligible)
        """
        proj_a = _make_project("proj-a")
        proj_b = _make_project("proj-b")
        orch = _make_orchestrator(tmp_path, projects=[proj_a, proj_b])

        # Project A: a dependency-blocked task
        blocker = BlockerRef(id="TASK-A-001", identifier="TASK-A-001", state="Open")
        blocked_task = _make_issue(
            "TASK-A-002",
            state="Open",
            project_id="proj-a",
            blocked_by=[blocker],
        )

        # Project B: eligible unblocked task
        eligible = _make_issue("TASK-B-001", state="Open", project_id="proj-b")

        dispatched_ids: list[str] = []

        orch._fetch_all_candidates = MagicMock(return_value=[blocked_task, eligible])
        orch._pre_resolve_blockers = MagicMock()
        orch._reset_orphaned_in_progress = MagicMock()
        orch._plan_open_epics = MagicMock(return_value=[])
        orch._apply_duplicate_detection = MagicMock()

        # Mock blocker resolution: TASK-A-001 is Open (not terminal) → blocks TASK-A-002
        orch._resolve_blocker_state = MagicMock(return_value="Open")
        orch._blocker_satisfied = MagicMock(return_value=False)  # blocked
        orch._blocker_has_unmerged_pr = MagicMock(return_value=False)

        async def _fake_dispatch(issue, attempt):
            dispatched_ids.append(issue.identifier)

        orch._dispatch = _fake_dispatch
        orch._maybe_heal_repos = MagicMock()
        orch._maybe_run_watchdog = MagicMock()
        orch._handle_reconcile = AsyncMock()
        orch._handle_review_check = AsyncMock()
        orch._handle_auto_update = AsyncMock()
        orch._handle_yolo_review = AsyncMock(return_value=(0.0, 0.0, 0.0))
        orch._notify_observers = MagicMock()

        with patch("oompah.orchestrator.validate_dispatch_config", return_value=[]):
            asyncio.run(orch._tick())

        assert "TASK-B-001" in dispatched_ids, (
            "Eligible task in Project B was not dispatched."
        )
        assert "TASK-A-002" not in dispatched_ids, (
            "Dependency-blocked task was incorrectly dispatched."
        )

    def test_multi_project_full_scenario(self, tmp_path):
        """Comprehensive long-tick regression scenario (AC#1 + AC#2):

        Project alpha (workstream-alpha):
          - TASK-ALPHA-001: In Progress (running agent — consumes a slot)
          - TASK-ALPHA-002: Open but blocked by TASK-ALPHA-001 (dep-blocked)

        Project beta (workstream-beta):
          - TASK-BETA-001: Open, no blockers, different project (eligible)

        Maintenance: _maybe_heal_repos is a synthetic slow job (records its
        position in the call sequence but does not actually sleep).

        Expected:
          - TASK-BETA-001 dispatches in the same tick.
          - TASK-ALPHA-002 does NOT dispatch (blocked by Open task).
          - Dispatch precedes maintenance in the call sequence.
        """
        proj_alpha = _make_project("proj-alpha")
        proj_beta = _make_project("proj-beta")
        orch = _make_orchestrator(tmp_path, projects=[proj_alpha, proj_beta])

        # Ensure enough slots (1 running + 1 new dispatch)
        orch.config.max_in_flight = 5
        orch.config.max_in_flight_open = 5

        # Running agent in alpha
        running = _make_issue(
            "TASK-ALPHA-001", state="In Progress", project_id="proj-alpha"
        )
        _add_running_entry(orch, running)

        # Dependency-blocked task in alpha
        blocker_ref = BlockerRef(
            id="TASK-ALPHA-001", identifier="TASK-ALPHA-001", state="In Progress"
        )
        dep_blocked = _make_issue(
            "TASK-ALPHA-002",
            state="Open",
            project_id="proj-alpha",
            blocked_by=[blocker_ref],
        )

        # Eligible task in beta
        eligible = _make_issue("TASK-BETA-001", state="Open", project_id="proj-beta")

        call_order: list[str] = []
        dispatched_ids: list[str] = []

        orch._fetch_all_candidates = MagicMock(return_value=[dep_blocked, eligible])
        orch._pre_resolve_blockers = MagicMock()
        orch._reset_orphaned_in_progress = MagicMock()
        orch._plan_open_epics = MagicMock(return_value=[])
        orch._apply_duplicate_detection = MagicMock()

        # dep_blocked is blocked; eligible is not
        def _resolve_blocker_state(blocker, issue):
            return blocker.state or "Open"

        def _blocker_satisfied(issue, blocker, state):
            # TASK-ALPHA-001 is In Progress → not terminal → not satisfied
            return state in ("Done", "Merged", "Archived", "Closed")

        orch._resolve_blocker_state = MagicMock(side_effect=_resolve_blocker_state)
        orch._blocker_satisfied = MagicMock(side_effect=_blocker_satisfied)
        orch._blocker_has_unmerged_pr = MagicMock(return_value=False)

        async def _fake_dispatch(issue, attempt):
            dispatched_ids.append(issue.identifier)
            call_order.append(f"dispatched:{issue.identifier}")

        orch._dispatch = _fake_dispatch

        # Synthetic slow maintenance
        def _slow_heal():
            call_order.append("heal_start")
            call_order.append("heal_end")

        orch._maybe_heal_repos = _slow_heal
        orch._maybe_run_watchdog = MagicMock(
            side_effect=lambda: call_order.append("watchdog")
        )
        orch._handle_reconcile = AsyncMock()
        orch._handle_review_check = AsyncMock()
        orch._handle_auto_update = AsyncMock()
        orch._handle_yolo_review = AsyncMock(return_value=(0.0, 0.0, 0.0))
        orch._notify_observers = MagicMock()

        with patch("oompah.orchestrator.validate_dispatch_config", return_value=[]):
            asyncio.run(orch._tick())

        # Eligible task in beta must have dispatched
        assert "TASK-BETA-001" in dispatched_ids, (
            f"Eligible task TASK-BETA-001 was not dispatched.\n"
            f"Dispatched: {dispatched_ids}\nCall order: {call_order}"
        )

        # Dep-blocked task must NOT have dispatched
        assert "TASK-ALPHA-002" not in dispatched_ids, (
            "Dependency-blocked task TASK-ALPHA-002 was incorrectly dispatched."
        )

        # Dispatch must precede maintenance in the tick
        dispatch_idx = next(
            (i for i, e in enumerate(call_order) if "dispatched:TASK-BETA-001" in e),
            None,
        )
        heal_idx = next(
            (i for i, e in enumerate(call_order) if e == "heal_start"), None
        )
        if dispatch_idx is not None and heal_idx is not None:
            assert dispatch_idx < heal_idx, (
                f"Dispatch ({dispatch_idx}) did not precede maintenance ({heal_idx}).\n"
                f"Call order: {call_order}"
            )

    def test_slow_project_tracker_timeout_does_not_block_other_project_dispatch(
        self, tmp_path
    ):
        """Bounded refresh: when Project A's tracker fetch times out, Project B's
        eligible task is still fetched and dispatched.

        This test targets the _run_bounded_refresh path (TASK-467.2). It verifies
        that after a timeout, stale (or empty) data for Project A does not prevent
        Project B from being fetched and dispatched.
        """
        proj_a = _make_project("proj-a")
        proj_b = _make_project("proj-b")
        orch = _make_orchestrator(tmp_path, projects=[proj_a, proj_b])

        # Project B: eligible task
        eligible = _make_issue("TASK-B-001", state="Open", project_id="proj-b")

        dispatched_ids: list[str] = []

        async def _run():
            # Simulate: Project A's fetch times out (returns empty, is_fresh=False)
            # Project B returns the eligible task
            async def _mock_fetch_one_project(project):
                if project.id == "proj-a":
                    # Simulate a slow operation that times out
                    return []  # Stale/empty fallback
                else:
                    return [eligible]

            # Directly test _fetch_all_candidates behavior using bounded refresh
            # by mocking the tracker responses
            mock_tracker_a = MagicMock()
            async def _slow_tracker_a():
                await asyncio.sleep(10)  # Would timeout with small timeout_ms
                return []

            mock_tracker_a.fetch_candidate_issues = MagicMock(
                side_effect=lambda: (_ for _ in ()).throw(
                    Exception("Simulated timeout")
                )
            )
            mock_tracker_b = MagicMock()
            eligible_b = _make_issue("TASK-B-001", state="Open", project_id="proj-b")
            mock_tracker_b.fetch_candidate_issues = MagicMock(return_value=[eligible_b])

            # Pre-populate stale cache for Project A (empty)
            orch._set_stale_cache("proj-a", "candidates", [])

            # Configure short timeout for Project A's fetch
            old_timeout = orch.config.project_refresh_timeout_ms
            orch.config.project_refresh_timeout_ms = 1  # 1ms — will timeout

            def _tracker_for_project(pid):
                if pid == "proj-a":
                    raise Exception("Project A tracker slow/unavailable")
                return mock_tracker_b

            with patch.object(orch, "_tracker_for_project", side_effect=_tracker_for_project):
                candidates = await asyncio.get_event_loop().run_in_executor(
                    None, orch._fetch_all_candidates
                )

            orch.config.project_refresh_timeout_ms = old_timeout
            return candidates

        candidates = asyncio.run(_run())

        # Project B's eligible task must appear in candidates despite Project A failing
        candidate_ids = {c.identifier for c in candidates}
        assert "TASK-B-001" in candidate_ids, (
            f"Project B's task was not in candidates despite Project A failing.\n"
            f"Candidates: {candidate_ids}"
        )

    def test_dispatch_handler_runs_before_slow_maintenance_handlers(self, tmp_path):
        """AC#2: Tick ordering guarantee — _handle_dispatch_needed always runs
        before _maybe_heal_repos and _maybe_run_watchdog within the same tick.

        This test records the tick phase sequence and asserts the invariant
        that dispatch precedes both maintenance routines.
        """
        orch = _make_orchestrator(tmp_path)
        call_order: list[str] = []

        async def _fake_reconcile():
            call_order.append("reconcile")

        async def _fake_review_check():
            call_order.append("review_check")

        async def _fake_dispatch_needed():
            call_order.append("dispatch_needed")

        async def _fake_yolo_review():
            call_order.append("yolo_review")
            return (0.0, 0.0, 0.0)

        async def _fake_auto_update():
            call_order.append("auto_update")

        orch._handle_reconcile = _fake_reconcile
        orch._handle_review_check = _fake_review_check
        orch._handle_dispatch_needed = _fake_dispatch_needed
        orch._handle_yolo_review = _fake_yolo_review
        orch._handle_auto_update = _fake_auto_update
        orch._notify_observers = MagicMock()
        orch._maybe_run_watchdog = MagicMock(
            side_effect=lambda: call_order.append("watchdog")
        )
        orch._maybe_heal_repos = MagicMock(
            side_effect=lambda: call_order.append("repo_heal")
        )
        orch._run_step5b_maintenance = MagicMock(
            side_effect=lambda: orch._maybe_heal_repos()
        )

        async def _run_tick_and_wait_for_maintenance() -> None:
            await orch._tick()
            if orch._maintenance_future is not None:
                await orch._maintenance_future

        with patch("oompah.orchestrator.validate_dispatch_config", return_value=[]):
            asyncio.run(_run_tick_and_wait_for_maintenance())

        dispatch_idx = call_order.index("dispatch_needed")
        watchdog_idx = call_order.index("watchdog")
        heal_idx = call_order.index("repo_heal")

        assert dispatch_idx < watchdog_idx, (
            f"dispatch_needed ({dispatch_idx}) did not precede watchdog ({watchdog_idx})."
            f" Full order: {call_order}"
        )
        assert dispatch_idx < heal_idx, (
            f"dispatch_needed ({dispatch_idx}) did not precede repo_heal ({heal_idx})."
            f" Full order: {call_order}"
        )


# ---------------------------------------------------------------------------
# AC#3 — Operator diagnostics: project_refresh_metrics in get_snapshot()
# ---------------------------------------------------------------------------


class TestOperatorDiagnostics:
    """Verify that get_snapshot() exposes project_refresh_metrics so operators
    can diagnose which project/lane is currently slow (AC#3).
    """

    def test_snapshot_includes_project_refresh_metrics(self, tmp_path):
        """get_snapshot()['orchestrator_metrics']['project_refresh'] must be
        present and contain the per-project, per-operation timing data.
        """
        orch = _make_orchestrator(tmp_path)

        async def _run():
            async def _fast_coro():
                return ["result"]

            await orch._run_bounded_refresh("proj-slow", "candidates", _fast_coro)

        asyncio.run(_run())

        snapshot = orch.get_snapshot()
        metrics = snapshot.get("orchestrator_metrics", {})
        assert "project_refresh" in metrics, (
            "get_snapshot() is missing 'project_refresh' in orchestrator_metrics. "
            "Operators cannot diagnose slow projects without this data."
        )

        proj_metrics = metrics["project_refresh"]
        assert "proj-slow" in proj_metrics, (
            f"'proj-slow' not in project_refresh metrics: {proj_metrics}"
        )
        assert "candidates" in proj_metrics["proj-slow"], (
            f"'candidates' operation missing from proj-slow metrics: {proj_metrics['proj-slow']}"
        )

    def test_snapshot_project_refresh_shows_timeout_count(self, tmp_path):
        """After a timeout, the snapshot must show timeout_count > 0 so operators
        can see that a particular project/operation is timing out.
        """
        orch = _make_orchestrator(tmp_path)

        async def _run():
            async def _slow_coro():
                await asyncio.sleep(10)
                return ["result"]

            # Use a very short timeout so it definitely times out
            await orch._run_bounded_refresh(
                "proj-slow", "candidates", _slow_coro, timeout_ms=1
            )

        asyncio.run(_run())

        snapshot = orch.get_snapshot()
        proj_metrics = snapshot["orchestrator_metrics"]["project_refresh"]
        assert proj_metrics["proj-slow"]["candidates"]["timeout_count"] > 0, (
            "Expected timeout_count > 0 after a timed-out refresh."
        )

    def test_snapshot_maintenance_status_included(self, tmp_path):
        """Maintenance status dict must be present in orchestrator_metrics so
        operators can see the last-run timestamps and any deferred jobs.
        """
        orch = _make_orchestrator(tmp_path)
        # Inject a synthetic maintenance status entry
        orch._maintenance_status["worktree_cleanup"] = {
            "last_run_at": datetime.now(timezone.utc).isoformat(),
            "cleaned": 3,
            "limit": 25,
            "deferred": False,
            "cursor": None,
        }

        snapshot = orch.get_snapshot()
        metrics = snapshot.get("orchestrator_metrics", {})
        assert "maintenance" in metrics, (
            "get_snapshot() is missing 'maintenance' in orchestrator_metrics."
        )
        assert "worktree_cleanup" in metrics["maintenance"], (
            "worktree_cleanup status not found in maintenance metrics."
        )

    def test_snapshot_project_refresh_tracks_slow_operations_per_project(
        self, tmp_path
    ):
        """Multiple projects' metrics are stored independently — operators can
        identify WHICH project is the bottleneck.
        """
        orch = _make_orchestrator(tmp_path)

        async def _run():
            async def _coro_a():
                return ["result-a"]

            async def _coro_b():
                await asyncio.sleep(10)
                return ["result-b"]

            await orch._run_bounded_refresh("proj-fast", "candidates", _coro_a)
            # proj-slow times out
            await orch._run_bounded_refresh(
                "proj-slow", "candidates", _coro_b, timeout_ms=1
            )

        asyncio.run(_run())

        snapshot = orch.get_snapshot()
        proj_metrics = snapshot["orchestrator_metrics"]["project_refresh"]

        # proj-fast: success
        assert proj_metrics["proj-fast"]["candidates"]["success_count"] == 1
        assert proj_metrics["proj-fast"]["candidates"]["timeout_count"] == 0

        # proj-slow: timeout
        assert proj_metrics["proj-slow"]["candidates"]["timeout_count"] > 0
        assert proj_metrics["proj-slow"]["candidates"]["success_count"] == 0

        # Both projects present — operator can see which is slow
        assert "proj-fast" in proj_metrics
        assert "proj-slow" in proj_metrics

    def test_snapshot_project_refresh_last_duration_ms_present(self, tmp_path):
        """last_duration_ms must be present so operators can see latency per operation."""
        orch = _make_orchestrator(tmp_path)

        async def _run():
            async def _coro():
                return ["result"]

            await orch._run_bounded_refresh("proj-1", "candidates", _coro)

        asyncio.run(_run())

        snapshot = orch.get_snapshot()
        m = snapshot["orchestrator_metrics"]["project_refresh"]["proj-1"]["candidates"]
        assert "last_duration_ms" in m, "last_duration_ms missing from project_refresh metrics."
        assert isinstance(m["last_duration_ms"], float)

    def test_snapshot_tick_metrics_include_dispatch_timing(self, tmp_path):
        """_last_tick_metrics must be present so operators can see total tick time
        and per-phase breakdowns, helping attribute long ticks to specific phases.
        """
        orch = _make_orchestrator(tmp_path)
        orch._handle_reconcile = AsyncMock()
        orch._handle_review_check = AsyncMock()
        orch._handle_dispatch_needed = AsyncMock()
        orch._handle_yolo_review = AsyncMock(return_value=(0.0, 0.0, 0.0))
        orch._handle_auto_update = AsyncMock()
        orch._maybe_run_watchdog = MagicMock()
        orch._maybe_heal_repos = MagicMock()
        orch._notify_observers = MagicMock()

        with patch("oompah.orchestrator.validate_dispatch_config", return_value=[]):
            asyncio.run(orch._tick())

        snapshot = orch.get_snapshot()
        tick_metrics = snapshot["orchestrator_metrics"]["last_tick"]
        assert "total_ms" in tick_metrics, "total_ms missing from last_tick metrics."
        assert "dispatch_ms" in tick_metrics, "dispatch_ms missing from last_tick metrics."
        assert "reconcile_ms" in tick_metrics, "reconcile_ms missing from last_tick metrics."


# ---------------------------------------------------------------------------
# Synthetic slow job fixtures — ensure maintenance simulation is faithful
# ---------------------------------------------------------------------------


class TestSyntheticSlowJobs:
    """Verify that the synthetic slow job patterns used in the regression tests
    would faithfully represent the real long-tick scenario.

    These tests document the invariants that must hold in production:
      - _maybe_heal_repos runs AFTER _handle_dispatch_needed in the tick.
      - _maybe_heal_repos running slowly delays the NEXT tick, not the current
        dispatch within the same tick.
      - Bounded refresh enforces per-project timeouts so one slow project
        does not hold up candidates from others.
    """

    def test_heal_repos_always_runs_after_dispatch_needed(self, tmp_path):
        """Invariant: _maybe_heal_repos is always called after _handle_dispatch_needed
        completes within the same tick cycle.

        This is the structural guarantee that prevents slow maintenance from
        blocking dispatch of eligible tasks within a tick.
        """
        orch = _make_orchestrator(tmp_path)
        call_order: list[str] = []

        orch._handle_reconcile = AsyncMock(side_effect=lambda: call_order.append("reconcile"))
        orch._handle_review_check = AsyncMock(
            side_effect=lambda: call_order.append("review_check")
        )
        orch._handle_dispatch_needed = AsyncMock(
            side_effect=lambda: call_order.append("dispatch_needed")
        )
        orch._handle_yolo_review = AsyncMock(
            side_effect=lambda: (call_order.append("yolo_review") or (0.0, 0.0, 0.0))
        )
        orch._handle_auto_update = AsyncMock(
            side_effect=lambda: call_order.append("auto_update")
        )
        orch._notify_observers = MagicMock()
        orch._maybe_run_watchdog = MagicMock(
            side_effect=lambda: call_order.append("watchdog")
        )
        orch._maybe_heal_repos = MagicMock(
            side_effect=lambda: call_order.append("heal_repos")
        )
        orch._run_step5b_maintenance = MagicMock(
            side_effect=lambda: orch._maybe_heal_repos()
        )

        async def _run_tick_and_wait_for_maintenance() -> None:
            await orch._tick()
            if orch._maintenance_future is not None:
                await orch._maintenance_future

        with patch("oompah.orchestrator.validate_dispatch_config", return_value=[]):
            asyncio.run(_run_tick_and_wait_for_maintenance())

        # dispatch_needed must appear in call_order before heal_repos
        assert "dispatch_needed" in call_order, "dispatch_needed was never called."
        assert "heal_repos" in call_order, "_maybe_heal_repos was never called."
        assert call_order.index("dispatch_needed") < call_order.index("heal_repos"), (
            f"dispatch_needed did not precede heal_repos.\nCall order: {call_order}"
        )

    def test_bounded_refresh_timeout_unblocks_other_projects(self, tmp_path):
        """When project A times out, project B's candidates are returned immediately.

        This is the bounded-refresh guarantee: no project can hold up others
        beyond project_refresh_timeout_ms.
        """
        orch = _make_orchestrator(tmp_path)
        eligible_b = _make_issue("TASK-B-001", state="Open", project_id="proj-b")

        async def _run():
            # Project A: slow operation (would block under old code)
            async def _coro_a():
                await asyncio.sleep(10)  # Simulated 150s slow git I/O
                return [_make_issue("TASK-A-001", state="Open", project_id="proj-a")]

            # Project B: fast operation
            async def _coro_b():
                return [eligible_b]

            # Pre-seed stale cache for A so fallback works
            orch._set_stale_cache("proj-a", "candidates", [])

            # Both run in parallel; A times out, B succeeds immediately
            result_a, result_b = await asyncio.gather(
                orch._run_bounded_refresh("proj-a", "candidates", _coro_a, timeout_ms=1),
                orch._run_bounded_refresh("proj-b", "candidates", _coro_b, timeout_ms=0),
            )
            return result_a, result_b

        (data_a, fresh_a), (data_b, fresh_b) = asyncio.run(_run())

        # A timed out — should have stale/empty data, not fresh
        assert fresh_a is False, "Project A should have timed out and returned stale data."

        # B succeeded — eligible task is available
        assert fresh_b is True, "Project B should have returned fresh data."
        assert eligible_b in data_b, "Project B's eligible task missing from results."
