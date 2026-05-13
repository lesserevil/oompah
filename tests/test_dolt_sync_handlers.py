"""Tests for _dolt_sync_all_sync handler — specifically the ghost-state
prune introduced by oompah-zlz_2-k7zt.

Background: ``_dolt_sync_state`` is keyed by project_id and accumulates
entries on every tick via ``_dolt_get_or_create_state``. Without active
pruning, deleting a project from ``projects.json`` mid-session leaves a
"ghost" entry behind — the watchdog keeps trying to sync it, the
``no beads database found`` error surfaces as a dashboard alert, and
``/api/v1/orchestrator/dolt-sync`` keeps reporting it.

These tests verify the prune contract directly: invoke
``_dolt_sync_all_sync`` once with a partially-stale state and assert
that ghosts (project_id not present in ``project_store.list_all()``)
are removed while live entries are preserved.
"""

from __future__ import annotations

from unittest.mock import patch

from oompah.config import ServiceConfig
from oompah.dolt_sync import DoltSyncResult, DoltSyncState
from oompah.models import Project
from oompah.orchestrator import Orchestrator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_project(pid: str, name: str | None = None) -> Project:
    return Project(
        id=pid,
        name=name or pid,
        repo_url=f"https://example.com/{pid}.git",
        repo_path=f"/tmp/{pid}",
        branch="main",
        paused=False,
    )


class _StaticProjectStore:
    """Minimal project store stub for the handler tests."""

    def __init__(self, projects: list[Project]):
        self._projects = list(projects)

    def list_all(self) -> list[Project]:
        return list(self._projects)


def _make_orchestrator(projects: list[Project]) -> Orchestrator:
    """Build a bare Orchestrator instance suitable for hitting
    ``_dolt_sync_all_sync`` directly. Mirrors the
    ``Orchestrator.__new__(Orchestrator)`` pattern already used in
    tests/test_dashboard_dolt_alert.py.
    """
    orch = Orchestrator.__new__(Orchestrator)
    orch.project_store = _StaticProjectStore(projects)
    orch.config = ServiceConfig()
    orch._dolt_sync_state = {}
    orch._dolt_sync_last_results = {}
    orch._alerts = []
    return orch


def _no_op_sync(project, state, *, full_sync_interval_s):
    """Stub for ``sync_project_dolt`` — preserves the existing state
    object the orchestrator passed in (so live entries persist across a
    tick) and returns a skipped result."""
    return DoltSyncResult(
        project_id=project.id,
        skipped_reason="stub-no-op",
    )


# ===========================================================================
# 1. Ghost state pruning
# ===========================================================================


class TestGhostStatePruning:
    """oompah-zlz_2-k7zt acceptance criteria."""

    def test_ghost_state_pruned_when_project_deleted(self):
        """Pre-populate _dolt_sync_state with a project_id that is NOT
        in project_store.list_all(); after one tick the ghost entry
        must be gone."""
        live = _make_project("proj-live")
        orch = _make_orchestrator([live])

        # Ghost: state exists, project does not.
        orch._dolt_sync_state["proj-ghost"] = DoltSyncState(
            project_id="proj-ghost",
            last_error="no beads database found",
            consecutive_errors=5,
        )
        orch._dolt_sync_last_results["proj-ghost"] = DoltSyncResult(
            project_id="proj-ghost",
            error="no beads database found",
        )

        with patch(
            "oompah.orchestrator.sync_project_dolt", side_effect=_no_op_sync
        ):
            orch._dolt_sync_all_sync()

        assert "proj-ghost" not in orch._dolt_sync_state
        assert "proj-ghost" not in orch._dolt_sync_last_results

    def test_live_project_state_preserved(self):
        """Pre-populate with a live project_id; one tick later it must
        still be present."""
        live = _make_project("proj-live")
        orch = _make_orchestrator([live])

        seeded = DoltSyncState(
            project_id="proj-live",
            consecutive_errors=1,
            last_error="transient blip",
        )
        orch._dolt_sync_state["proj-live"] = seeded

        with patch(
            "oompah.orchestrator.sync_project_dolt", side_effect=_no_op_sync
        ):
            orch._dolt_sync_all_sync()

        # The state object must still be there. _dolt_get_or_create_state
        # only creates a new state when one is absent, so the seeded
        # object is also the same instance the sync was called with.
        assert "proj-live" in orch._dolt_sync_state
        assert orch._dolt_sync_state["proj-live"] is seeded

    def test_mixed_live_and_ghost_state(self):
        """When both live and ghost entries exist, only ghosts are
        pruned and live entries continue to receive sync results."""
        live = _make_project("proj-live")
        orch = _make_orchestrator([live])

        orch._dolt_sync_state["proj-live"] = DoltSyncState(
            project_id="proj-live"
        )
        orch._dolt_sync_state["ghost-a"] = DoltSyncState(project_id="ghost-a")
        orch._dolt_sync_state["ghost-b"] = DoltSyncState(
            project_id="ghost-b", divergent=True,
        )

        with patch(
            "oompah.orchestrator.sync_project_dolt", side_effect=_no_op_sync
        ):
            orch._dolt_sync_all_sync()

        assert set(orch._dolt_sync_state.keys()) == {"proj-live"}
        # _dolt_sync_last_results is rebuilt every tick from the live
        # iteration loop, so it naturally only carries live keys.
        assert set(orch._dolt_sync_last_results.keys()) == {"proj-live"}

    def test_ghost_alert_pruned_pre_loop(self):
        """If a stale dolt_sync alert is sitting in ``_alerts`` and the
        underlying project has been deleted, the prune step must drop
        it. (The rebuild at the bottom of the function also clears all
        dolt_sync alerts, but the pre-loop prune guarantees mid-tick
        observers never see ghosts.)"""
        live = _make_project("proj-live")
        orch = _make_orchestrator([live])
        # Seed a ghost alert that the prune step (not the rebuild)
        # is responsible for removing. We don't seed _dolt_sync_state,
        # so the bottom rebuild would emit nothing for ghost-a anyway —
        # the assertion is just that ghost-a's alert vanishes.
        orch._alerts = [
            {
                "level": "error",
                "source": "dolt_sync",
                "project_id": "ghost-a",
                "message": "stale ghost alert",
            },
            {
                "level": "warning",
                "source": "auto_update",
                "message": "unrelated alert",
            },
        ]

        with patch(
            "oompah.orchestrator.sync_project_dolt", side_effect=_no_op_sync
        ):
            orch._dolt_sync_all_sync()

        # Ghost dolt_sync alert removed; the unrelated auto_update
        # alert is untouched.
        sources = [a.get("source") for a in orch._alerts]
        assert "dolt_sync" not in sources or all(
            a.get("project_id") in {"proj-live"}
            for a in orch._alerts if a.get("source") == "dolt_sync"
        )
        assert "auto_update" in sources

    def test_empty_project_store_early_returns(self):
        """When project_store.list_all() is empty, the function must
        early-return without touching state — preserves today's
        documented no-op behavior for the no-projects-configured case.
        """
        orch = _make_orchestrator([])
        orch._dolt_sync_state["proj-x"] = DoltSyncState(project_id="proj-x")

        with patch(
            "oompah.orchestrator.sync_project_dolt", side_effect=_no_op_sync
        ) as m:
            orch._dolt_sync_all_sync()

        # Early-return: sync_project_dolt was never called.
        assert m.call_count == 0
        # State for a hypothetical project is preserved when there are
        # no live projects to compare against (we can't tell ghosts
        # from "store hasn't loaded yet" in this branch).
        assert "proj-x" in orch._dolt_sync_state
