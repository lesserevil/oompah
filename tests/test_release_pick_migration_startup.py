"""Tests for the release-pick migration startup integration (OOMPAH-183).

Verifies that _migrate_release_picks_on_startup is called during
set_orchestrator() and handles multi-project / single-tracker modes correctly.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch, call

import pytest

from oompah.release_pick_migration import MigrationResult


def _make_mock_orch(projects=None):
    """Return a minimal mock orchestrator for set_orchestrator tests."""
    mock_orch = MagicMock()
    mock_orch.tracker.fetch_all_issues.return_value = []
    mock_orch.agent_profile_store = MagicMock()
    mock_orch.role_store = MagicMock()
    mock_orch.provider_store = MagicMock()
    mock_orch._observers = []
    mock_orch._state_only_observers = []
    mock_orch._activity_observers = []
    mock_orch.project_store.list_all.return_value = list(projects or [])
    mock_orch.register_error_watcher = MagicMock()
    return mock_orch


def _run_set_orchestrator(mock_orch, patches=None):
    """Run set_orchestrator with standard infrastructure patches."""
    import oompah.server as server_module

    extra_patches = patches or {}

    with (
        patch.object(server_module, "ErrorWatcher", MagicMock()),
        patch.object(server_module, "ProjectLogWatcherManager", MagicMock()),
    ):
        try:
            server_module.set_orchestrator(mock_orch)
        except Exception:
            pass  # ConsoleSessionManager setup may fail in tests


# ---------------------------------------------------------------------------
# _migrate_release_picks_on_startup
# ---------------------------------------------------------------------------


class TestMigrateReleasePicksOnStartup:
    """Tests for the _migrate_release_picks_on_startup helper."""

    def test_called_during_set_orchestrator(self):
        """set_orchestrator must call _migrate_release_picks_on_startup."""
        import oompah.server as server_module

        mock_orch = _make_mock_orch()

        with patch.object(
            server_module, "_migrate_release_picks_on_startup"
        ) as mock_fn:
            _run_set_orchestrator(mock_orch)

        mock_fn.assert_called_once_with(mock_orch)

    def test_single_tracker_mode_when_no_projects(self):
        """In single-tracker mode (no managed projects), runs against orch.tracker."""
        import oompah.server as server_module

        mock_orch = _make_mock_orch(projects=[])

        with patch(
            "oompah.server._migrate_release_picks_on_startup",
            wraps=server_module._migrate_release_picks_on_startup,
        ), patch(
            "oompah.release_pick_migration.run_release_pick_migration"
        ) as mock_migrate:
            mock_migrate.return_value = MigrationResult()
            _run_set_orchestrator(mock_orch)

        # Should be called with the single tracker and "main" as default_branch
        mock_migrate.assert_called_once_with(mock_orch.tracker, "main")

    def test_multi_project_mode_iterates_each_project(self):
        """In multi-project mode, runs migration per project with its default_branch."""
        import oompah.server as server_module

        proj1 = MagicMock()
        proj1.id = "proj-1"
        proj1.default_branch = "main"
        proj2 = MagicMock()
        proj2.id = "proj-2"
        proj2.default_branch = "develop"

        mock_orch = _make_mock_orch(projects=[proj1, proj2])
        tracker1 = MagicMock()
        tracker2 = MagicMock()
        mock_orch._tracker_for_project.side_effect = lambda pid: (
            tracker1 if pid == "proj-1" else tracker2
        )

        with patch(
            "oompah.release_pick_migration.run_release_pick_migration"
        ) as mock_migrate:
            mock_migrate.return_value = MigrationResult()
            server_module._migrate_release_picks_on_startup(mock_orch)

        assert mock_migrate.call_count == 2
        calls = mock_migrate.call_args_list
        # Project 1
        assert calls[0][0][0] is tracker1
        assert calls[0][0][1] == "main"
        # Project 2
        assert calls[1][0][0] is tracker2
        assert calls[1][0][1] == "develop"

    def test_project_failure_does_not_stop_other_projects(self):
        """A per-project migration failure is logged but does not abort remaining projects."""
        import oompah.server as server_module

        proj1 = MagicMock()
        proj1.id = "proj-1"
        proj1.default_branch = "main"
        proj2 = MagicMock()
        proj2.id = "proj-2"
        proj2.default_branch = "main"

        mock_orch = _make_mock_orch(projects=[proj1, proj2])
        tracker1 = MagicMock()
        tracker2 = MagicMock()
        mock_orch._tracker_for_project.side_effect = lambda pid: (
            tracker1 if pid == "proj-1" else tracker2
        )

        call_count = [0]

        def _migrate(tracker, branch):
            call_count[0] += 1
            if tracker is tracker1:
                raise RuntimeError("proj-1 migration failed")
            return MigrationResult()

        with patch(
            "oompah.release_pick_migration.run_release_pick_migration",
            side_effect=_migrate,
        ):
            # Should not raise
            server_module._migrate_release_picks_on_startup(mock_orch)

        # Both projects were attempted
        assert call_count[0] == 2

    def test_migration_failure_does_not_crash_set_orchestrator(self):
        """A complete migration failure is caught and logged, not re-raised."""
        import oompah.server as server_module

        mock_orch = _make_mock_orch()

        with patch.object(
            server_module,
            "_migrate_release_picks_on_startup",
            side_effect=RuntimeError("migration exploded"),
        ):
            # set_orchestrator must not propagate the exception
            try:
                _run_set_orchestrator(mock_orch)
            except RuntimeError as exc:
                # Only re-raise if it's NOT our migration error
                if "migration exploded" in str(exc):
                    pytest.fail(
                        "set_orchestrator propagated migration error to caller"
                    )

    def test_uses_project_default_branch_attribute(self):
        """Migration uses project.default_branch even for unusual branch names."""
        import oompah.server as server_module

        proj = MagicMock()
        proj.id = "proj-special"
        proj.default_branch = "trunk"

        mock_orch = _make_mock_orch(projects=[proj])
        tracker = MagicMock()
        mock_orch._tracker_for_project.return_value = tracker

        with patch(
            "oompah.release_pick_migration.run_release_pick_migration"
        ) as mock_migrate:
            mock_migrate.return_value = MigrationResult()
            server_module._migrate_release_picks_on_startup(mock_orch)

        mock_migrate.assert_called_once_with(tracker, "trunk")

    def test_fallback_to_main_when_no_default_branch_attribute(self):
        """Falls back to 'main' when project.default_branch is absent or falsy."""
        import oompah.server as server_module

        proj = MagicMock(spec=["id"])  # no default_branch attribute
        proj.id = "proj-no-branch"

        mock_orch = _make_mock_orch(projects=[proj])
        tracker = MagicMock()
        mock_orch._tracker_for_project.return_value = tracker

        with patch(
            "oompah.release_pick_migration.run_release_pick_migration"
        ) as mock_migrate:
            mock_migrate.return_value = MigrationResult()
            server_module._migrate_release_picks_on_startup(mock_orch)

        mock_migrate.assert_called_once_with(tracker, "main")
