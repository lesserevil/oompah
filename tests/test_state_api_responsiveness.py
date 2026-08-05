"""Tests for TASK-467.3: State API and WebSocket responsiveness during background jobs.

Covers:
  (1) Project.to_safe_dict() removes access_token and webhook_secret
  (2) Project.to_safe_dict() adds has_access_token and has_webhook_secret flags
  (3) get_snapshot() does not expose raw access_token or webhook_secret in projects
  (4) get_snapshot() uses to_safe_dict() (not to_dict()) for projects
  (5) api_state() serves from cached snapshot in combined mode
  (6) api_state() avoids live get_snapshot() when cache is empty or stale
  (7) Observer callbacks update the state snapshot cache
  (8) WebSocket state broadcasts include maintenance status
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import oompah.server as server_module
from oompah.models import Project


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_project(
    project_id: str = "proj-1",
    access_token: str | None = None,
    webhook_secret: str | None = None,
) -> Project:
    return Project(
        id=project_id,
        name="test-project",
        repo_url="https://github.com/org/repo.git",
        repo_path="/tmp/repos/repo",
        branch="main",
        access_token=access_token,
        webhook_secret=webhook_secret,
    )


def _make_mock_orchestrator(projects=None) -> MagicMock:
    mock_orch = MagicMock()
    mock_orch.project_store.list_all.return_value = projects or []
    mock_orch.get_snapshot.return_value = {
        "paused": False,
        "projects": [p.to_safe_dict() for p in (projects or [])],
        "counts": {"running": 0, "retrying": 0},
        "running": [],
        "retrying": [],
    }
    return mock_orch


# ---------------------------------------------------------------------------
# (1-2) to_safe_dict() secret redaction
# ---------------------------------------------------------------------------

class TestProjectToSafeDict:
    """Project.to_safe_dict() must not expose access_token or webhook_secret."""

    def test_access_token_is_removed(self):
        p = _make_project(access_token="ghp_supersecrettoken")
        d = p.to_safe_dict()
        assert "access_token" not in d

    def test_webhook_secret_is_removed(self):
        p = _make_project(webhook_secret="whsec_supersecretvalue")
        d = p.to_safe_dict()
        assert "webhook_secret" not in d

    def test_has_access_token_true_when_set(self):
        p = _make_project(access_token="ghp_supersecrettoken")
        d = p.to_safe_dict()
        assert d["has_access_token"] is True

    def test_has_access_token_false_when_unset(self):
        p = _make_project(access_token=None)
        d = p.to_safe_dict()
        assert d["has_access_token"] is False

    def test_has_webhook_secret_true_when_set(self):
        p = _make_project(webhook_secret="whsec_value")
        d = p.to_safe_dict()
        assert d["has_webhook_secret"] is True

    def test_has_webhook_secret_false_when_unset(self):
        p = _make_project(webhook_secret=None)
        d = p.to_safe_dict()
        assert d["has_webhook_secret"] is False

    def test_access_token_masked_present_when_set(self):
        p = _make_project(access_token="ghp_abcdefghij1234567890")
        d = p.to_safe_dict()
        assert "access_token_masked" in d
        # Should show first and last 4 chars
        assert d["access_token_masked"].startswith("ghp_")
        assert d["access_token_masked"].endswith("7890")

    def test_access_token_masked_empty_when_unset(self):
        p = _make_project(access_token=None)
        d = p.to_safe_dict()
        assert d["access_token_masked"] == ""

    def test_non_secret_fields_preserved(self):
        p = _make_project(project_id="proj-1")
        d = p.to_safe_dict()
        assert d["id"] == "proj-1"
        assert d["name"] == "test-project"
        assert d["repo_url"] == "https://github.com/org/repo.git"


# ---------------------------------------------------------------------------
# (3-4) get_snapshot() secret safety
# ---------------------------------------------------------------------------

class TestGetSnapshotSecretSafe:
    """get_snapshot() must not expose raw secrets in the projects list."""

    def test_access_token_not_in_projects(self, tmp_path):
        from oompah.orchestrator import Orchestrator
        from oompah.config import ServiceConfig
        from oompah.projects import ProjectStore

        proj = _make_project(access_token="ghp_supersecrettoken1234567890")
        store = ProjectStore(
            path=str(tmp_path / "projects.json"),
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        store._projects[proj.id] = proj
        store._save()

        store2 = ProjectStore(
            path=str(tmp_path / "projects.json"),
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        orch = Orchestrator(
            config=ServiceConfig(),
            workflow_path="WORKFLOW.md",
            project_store=store2,
            state_path=str(tmp_path / "state.json"),
        )
        snapshot = orch.get_snapshot()
        for p in snapshot["projects"]:
            assert "access_token" not in p, "access_token must not appear in state snapshot projects"

    def test_webhook_secret_not_in_projects(self, tmp_path):
        from oompah.orchestrator import Orchestrator
        from oompah.config import ServiceConfig
        from oompah.projects import ProjectStore

        proj = _make_project(webhook_secret="whsec_super_secret_webhook_value")
        store = ProjectStore(
            path=str(tmp_path / "projects.json"),
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        store._projects[proj.id] = proj
        store._save()

        store2 = ProjectStore(
            path=str(tmp_path / "projects.json"),
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        orch = Orchestrator(
            config=ServiceConfig(),
            workflow_path="WORKFLOW.md",
            project_store=store2,
            state_path=str(tmp_path / "state.json"),
        )
        snapshot = orch.get_snapshot()
        for p in snapshot["projects"]:
            assert "webhook_secret" not in p, "webhook_secret must not appear in state snapshot projects"

    def test_has_access_token_present_in_projects(self, tmp_path):
        from oompah.orchestrator import Orchestrator
        from oompah.config import ServiceConfig
        from oompah.projects import ProjectStore

        proj = _make_project(access_token="ghp_supersecrettoken1234567890")
        store = ProjectStore(
            path=str(tmp_path / "projects.json"),
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        store._projects[proj.id] = proj
        store._save()

        store2 = ProjectStore(
            path=str(tmp_path / "projects.json"),
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        orch = Orchestrator(
            config=ServiceConfig(),
            workflow_path="WORKFLOW.md",
            project_store=store2,
            state_path=str(tmp_path / "state.json"),
        )
        snapshot = orch.get_snapshot()
        # has_access_token presence flag should be surfaced
        assert any(p.get("has_access_token") is True for p in snapshot["projects"])


# ---------------------------------------------------------------------------
# (5-6) api_state() uses cached snapshot in combined mode
# ---------------------------------------------------------------------------

class TestApiStateCachingCombinedMode:
    """api_state() must prefer the server-side cached snapshot over calling get_snapshot()."""

    @pytest.mark.asyncio
    async def test_serves_from_cache_when_available(self):
        """api_state() returns the cached snapshot without calling get_snapshot()."""
        cached = {
            "paused": False,
            "counts": {"running": 1, "retrying": 0},
            "running": [{"issue_id": "test-1"}],
            "retrying": [],
        }

        mock_orch = MagicMock()
        mock_orch.get_snapshot.return_value = {"paused": True, "counts": {"running": 0}}

        original_orch = server_module._orchestrator
        original_ipc = server_module._ipc
        try:
            server_module._orchestrator = mock_orch
            server_module._ipc = None
            # Pre-populate the cache
            server_module._update_state_snapshot(cached)

            import json
            response = await server_module.api_state()
            data = json.loads(response.body)

            # Should return cached data (running=1), not live data (running=0)
            assert data["counts"]["running"] == 1
            # get_snapshot() should NOT have been called
            mock_orch.get_snapshot.assert_not_called()
        finally:
            server_module._orchestrator = original_orch
            server_module._ipc = original_ipc
            # Reset cache
            server_module._state_snapshot = None
            server_module._state_snapshot_at = 0.0

    @pytest.mark.asyncio
    async def test_returns_unavailable_when_cache_empty(self):
        """api_state() returns a placeholder without calling get_snapshot()."""
        live_snapshot = {
            "paused": False,
            "counts": {"running": 2, "retrying": 0},
            "running": [],
            "retrying": [],
        }
        mock_orch = MagicMock()
        mock_orch.get_snapshot.return_value = live_snapshot

        original_orch = server_module._orchestrator
        original_ipc = server_module._ipc
        original_snapshot = server_module._state_snapshot
        original_at = server_module._state_snapshot_at
        try:
            server_module._orchestrator = mock_orch
            server_module._ipc = None
            server_module._state_snapshot = None
            server_module._state_snapshot_at = 0.0

            import json
            response = await server_module.api_state()
            data = json.loads(response.body)

            assert data["counts"]["running"] == 0
            assert data["state_snapshot_unavailable"] is True
            assert data["alerts"][0]["source"] == "state_snapshot"
            mock_orch.get_snapshot.assert_not_called()
        finally:
            server_module._orchestrator = original_orch
            server_module._ipc = original_ipc
            server_module._state_snapshot = original_snapshot
            server_module._state_snapshot_at = original_at

    @pytest.mark.asyncio
    async def test_serves_stale_cache_after_max_age(self):
        """api_state() serves stale cache without calling get_snapshot()."""
        old_snapshot = {
            "paused": False,
            "counts": {"running": 5, "retrying": 0},
            "running": [],
            "retrying": [],
        }
        fresh_snapshot = {
            "paused": False,
            "counts": {"running": 0, "retrying": 0},
            "running": [],
            "retrying": [],
        }
        mock_orch = MagicMock()
        mock_orch.get_snapshot.return_value = fresh_snapshot

        original_orch = server_module._orchestrator
        original_ipc = server_module._ipc
        original_snapshot = server_module._state_snapshot
        original_at = server_module._state_snapshot_at
        try:
            server_module._orchestrator = mock_orch
            server_module._ipc = None
            # Set an expired cache (monotonic time far in the past)
            server_module._state_snapshot = old_snapshot
            server_module._state_snapshot_at = time.monotonic() - (
                server_module._STATE_SNAPSHOT_MAX_AGE_S + 10
            )

            import json
            response = await server_module.api_state()
            data = json.loads(response.body)

            assert data["counts"]["running"] == 5
            assert data["state_snapshot_stale"] is True
            assert (
                data["state_snapshot_age_seconds"]
                >= server_module._STATE_SNAPSHOT_MAX_AGE_S
            )
            mock_orch.get_snapshot.assert_not_called()
        finally:
            server_module._orchestrator = original_orch
            server_module._ipc = original_ipc
            server_module._state_snapshot = original_snapshot
            server_module._state_snapshot_at = original_at

    @pytest.mark.asyncio
    async def test_large_lifecycle_state_writes_do_not_block_state_endpoint(self):
        """Repeated 850 KiB lifecycle checkpoints stay off the API read path."""

        from oompah.models import Issue
        from oompah.terminal_audit_enforcement import TerminalAuditEnforcement

        class Tracker:
            def __init__(self):
                self.issue = Issue(
                    id="CHILD-LARGE-STATE",
                    identifier="CHILD-LARGE-STATE",
                    title="large state lifecycle regression",
                    state="Merged",
                    project_id="project-a",
                )

            def fetch_all_issues_enriched(self):
                return [self.issue]

            def get_metadata(self, _identifier):
                return {}

        persisted = {"large_unrelated_state": "x" * 850_000}
        save_calls = 0
        serialized_sizes = []
        save_blocked = threading.Event()
        release_save = threading.Event()

        def load_state():
            return deepcopy(persisted)

        def save_state(update):
            nonlocal save_calls
            candidate = deepcopy(persisted)
            candidate.update(deepcopy(update))
            serialized_sizes.append(len(json.dumps(candidate)))
            persisted.clear()
            persisted.update(candidate)
            save_calls += 1
            if save_calls == 3:
                save_blocked.set()
                assert release_save.wait(timeout=2)

        def unavailable_validator(*_args):
            raise RuntimeError("transient validator outage")

        tracker = Tracker()
        enforcer = TerminalAuditEnforcement(
            service_state_path="unused.json",
            load_state=load_state,
            save_state=save_state,
            validate_terminal_transition=unavailable_validator,
        )
        base = datetime(2026, 8, 5, tzinfo=timezone.utc)

        def lifecycle_worker():
            for offset in (0, 1, 3):
                enforcer.reconcile_lifecycle_batch(
                    [("project-a", tracker)],
                    max_attempts=10,
                    retry_backoff_seconds=1,
                    retry_max_backoff_seconds=8,
                    now=base + timedelta(seconds=offset),
                )

        worker = threading.Thread(target=lifecycle_worker)
        original_orch = server_module._orchestrator
        original_ipc = server_module._ipc
        original_snapshot = server_module._state_snapshot
        original_at = server_module._state_snapshot_at
        try:
            server_module._orchestrator = MagicMock()
            server_module._ipc = None
            server_module._update_state_snapshot(
                {
                    "paused": False,
                    "counts": {"running": 0, "retrying": 0},
                    "running": [],
                    "retrying": [],
                    "orchestrator_metrics": {
                        "maintenance": {
                            "terminal_lifecycle_reconciliation": {
                                "status": "degraded",
                                "retry_pending": 1,
                            }
                        }
                    },
                }
            )
            worker.start()
            assert await asyncio.to_thread(save_blocked.wait, 1)

            started = time.monotonic()
            response = await asyncio.wait_for(server_module.api_state(), timeout=0.25)
            elapsed = time.monotonic() - started
            data = json.loads(response.body)

            assert response.status_code == 200
            assert elapsed < 0.25
            assert data["counts"]["running"] == 0
            assert save_calls == 3
            assert min(serialized_sizes) > 800_000
            assert worker.is_alive(), "endpoint waited for the blocked lifecycle writer"
        finally:
            release_save.set()
            worker.join(timeout=2)
            server_module._orchestrator = original_orch
            server_module._ipc = original_ipc
            server_module._state_snapshot = original_snapshot
            server_module._state_snapshot_at = original_at
        assert not worker.is_alive()


# ---------------------------------------------------------------------------
# (7) Observer callbacks update the snapshot cache
# ---------------------------------------------------------------------------

class TestObserverCallbacksUpdateCache:
    """Observer callbacks must update the state snapshot cache."""

    def test_on_orchestrator_change_updates_cache(self):
        """_on_orchestrator_change() stores the snapshot in the server cache."""
        snapshot = {"paused": False, "counts": {"running": 3}}

        original_snapshot = server_module._state_snapshot
        original_at = server_module._state_snapshot_at
        try:
            server_module._state_snapshot = None
            server_module._state_snapshot_at = 0.0

            server_module._on_orchestrator_change(snapshot)

            cached = server_module._read_state_snapshot()
            assert cached is not None
            assert cached["counts"]["running"] == 3
        finally:
            server_module._state_snapshot = original_snapshot
            server_module._state_snapshot_at = original_at

    def test_on_state_only_change_updates_cache(self):
        """_on_state_only_change() stores the snapshot in the server cache."""
        snapshot = {"paused": True, "counts": {"running": 0}}

        original_snapshot = server_module._state_snapshot
        original_at = server_module._state_snapshot_at
        try:
            server_module._state_snapshot = None
            server_module._state_snapshot_at = 0.0

            server_module._on_state_only_change(snapshot)

            cached = server_module._read_state_snapshot()
            assert cached is not None
            assert cached["paused"] is True
        finally:
            server_module._state_snapshot = original_snapshot
            server_module._state_snapshot_at = original_at


# ---------------------------------------------------------------------------
# (8) WebSocket state broadcast includes maintenance status
# ---------------------------------------------------------------------------

class TestWebSocketBroadcastMaintenanceStatus:
    """State broadcasts should include maintenance status from get_snapshot()."""

    def test_get_snapshot_includes_maintenance_status(self, tmp_path):
        from oompah.orchestrator import Orchestrator
        from oompah.config import ServiceConfig
        from oompah.projects import ProjectStore

        store = ProjectStore(
            path=str(tmp_path / "projects.json"),
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        orch = Orchestrator(
            config=ServiceConfig(),
            workflow_path="WORKFLOW.md",
            project_store=store,
            state_path=str(tmp_path / "state.json"),
        )
        snapshot = orch.get_snapshot()
        assert "orchestrator_metrics" in snapshot
        assert "maintenance" in snapshot["orchestrator_metrics"]

    def test_maintenance_status_in_broadcast_snapshot(self):
        """_on_orchestrator_change receives and caches a snapshot with maintenance info."""
        snapshot_with_maintenance = {
            "paused": False,
            "counts": {"running": 0},
            "orchestrator_metrics": {
                "maintenance": {
                    "auto_archive": {
                        "last_run_at": "2026-06-09T00:00:00+00:00",
                        "cleaned": 5,
                        "deferred": False,
                    }
                }
            },
        }

        original_snapshot = server_module._state_snapshot
        original_at = server_module._state_snapshot_at
        try:
            server_module._state_snapshot = None

            server_module._on_orchestrator_change(snapshot_with_maintenance)

            cached = server_module._read_state_snapshot()
            assert cached is not None
            assert "orchestrator_metrics" in cached
            assert "maintenance" in cached["orchestrator_metrics"]
            assert "auto_archive" in cached["orchestrator_metrics"]["maintenance"]
        finally:
            server_module._state_snapshot = original_snapshot
            server_module._state_snapshot_at = original_at
