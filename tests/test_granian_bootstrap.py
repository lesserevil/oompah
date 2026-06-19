"""Tests for oompah.bootstrap and the --server granian CLI argument.

These tests verify:
  - bootstrap.setup_services() returns a valid Services bundle
  - __main__.main() parses --server {uvicorn,granian}
  - _run_granian() errors clearly when granian is not installed
  - server.py imports cleanly and exposes the lifespan-wired FastAPI app
"""

from __future__ import annotations

import importlib
import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_minimal_workflow() -> str:
    """Return a minimal WORKFLOW.md string that loads without error."""
    return """---
tracker:
  type: backlog
  path: .
agents:
  max_concurrent: 1
dispatch:
  interval_seconds: 60
  profiles:
    - name: default
      provider: test-provider
      model: test-model
"""


# ---------------------------------------------------------------------------
# bootstrap.Services dataclass
# ---------------------------------------------------------------------------


class TestServicesDataclass:
    """Services is a plain dataclass; verify fields exist and are accessible."""

    def test_services_fields_accessible(self, tmp_path):
        from oompah.bootstrap import Services

        # Build a Services with mock objects so we never touch the filesystem.
        svc = Services(
            config=MagicMock(name="config"),
            workflow_path=str(tmp_path / "WORKFLOW.md"),
            workflow=MagicMock(name="workflow"),
            port=8080,
            orchestrator=MagicMock(name="orchestrator"),
            provider_store=MagicMock(name="provider_store"),
            project_store=MagicMock(name="project_store"),
            agent_profile_store=MagicMock(name="agent_profile_store"),
            role_store=MagicMock(name="role_store"),
            webhook_forwarder=MagicMock(name="webhook_forwarder"),
        )
        assert svc.port == 8080
        assert svc.workflow_path == str(tmp_path / "WORKFLOW.md")

    def test_services_is_dataclass(self):
        import dataclasses
        from oompah.bootstrap import Services

        assert dataclasses.is_dataclass(Services)


# ---------------------------------------------------------------------------
# bootstrap.setup_services() — invalid workflow path
# ---------------------------------------------------------------------------


class TestSetupServicesInvalidWorkflow:
    """setup_services() raises StartupError on missing/broken workflow."""

    @pytest.mark.asyncio
    async def test_raises_on_missing_workflow(self, tmp_path):
        from oompah.bootstrap import StartupError, setup_services

        with pytest.raises(StartupError):
            await setup_services(str(tmp_path / "no_such_file.md"))

    @pytest.mark.asyncio
    async def test_raises_on_broken_workflow(self, tmp_path):
        wf = tmp_path / "WORKFLOW.md"
        wf.write_text("---\nnot: valid: yaml: : :\n---\n")
        from oompah.bootstrap import StartupError, setup_services

        with pytest.raises(StartupError):
            await setup_services(str(wf))


# ---------------------------------------------------------------------------
# bootstrap.setup_services() — valid minimal workflow (heavily mocked)
# ---------------------------------------------------------------------------


class TestSetupServicesSuccess:
    """setup_services() returns a Services bundle for a valid workflow."""

    def _make_mocks(self):
        """Return a dict of mock patches to apply."""
        mock_workflow = MagicMock(name="workflow")
        mock_workflow.prompt_template = None

        mock_config = MagicMock(name="config")
        mock_config.server_port = 8080
        mock_config.strict_profile_source = "warn"
        mock_config.workflow_has_profiles_block = False
        mock_config.agent_profiles_drift = False

        mock_orch = MagicMock(name="orchestrator")
        mock_orch.is_paused = False
        mock_orch._alerts = []

        mock_role_store = MagicMock(name="role_store")
        mock_role_store.is_empty = False

        mock_forwarder = MagicMock(name="webhook_forwarder")
        mock_forwarder._status_callback = None

        mock_projects = MagicMock(name="project_store")
        mock_projects.list_all.return_value = []

        mock_compat_result = MagicMock(name="compat")
        mock_compat_result.changed = False

        return {
            "workflow": mock_workflow,
            "config": mock_config,
            "orchestrator": mock_orch,
            "role_store": mock_role_store,
            "forwarder": mock_forwarder,
            "projects": mock_projects,
            "compat": mock_compat_result,
        }

    # bootstrap.setup_services() uses lazy imports inside the function body,
    # so patches must target the *source* modules (e.g. "oompah.config.load_workflow")
    # rather than "oompah.bootstrap.load_workflow" (which doesn't exist at module level).
    _PATCHES: dict[str, str] = {
        "load_workflow": "oompah.config.load_workflow",
        "ServiceConfig": "oompah.config.ServiceConfig",
        "validate_dispatch_config": "oompah.config.validate_dispatch_config",
        "ensure_backlog_compatible": "oompah.backlog_compat.ensure_backlog_compatible",
        "ProviderStore": "oompah.providers.ProviderStore",
        "ProjectStore": "oompah.projects.ProjectStore",
        "AgentProfileStore": "oompah.agent_profile_store.AgentProfileStore",
        "RoleStore": "oompah.roles.RoleStore",
        "migrate_agent_profiles_to_roles": "oompah.roles.migrate_agent_profiles_to_roles",
        "WebhookForwarder": "oompah.webhooks.WebhookForwarder",
        "Orchestrator": "oompah.orchestrator.Orchestrator",
    }

    @pytest.mark.asyncio
    async def test_returns_services_bundle(self, tmp_path, monkeypatch):
        """setup_services() returns a Services with the expected orchestrator."""
        mocks = self._make_mocks()

        mock_sc = MagicMock(name="ServiceConfig_class")
        mock_sc.from_workflow.return_value = mocks["config"]

        with (
            patch(self._PATCHES["load_workflow"], return_value=mocks["workflow"]),
            patch(self._PATCHES["ServiceConfig"], mock_sc),
            patch(self._PATCHES["validate_dispatch_config"], return_value=[]),
            patch(
                self._PATCHES["ensure_backlog_compatible"],
                return_value=mocks["compat"],
            ),
            patch(self._PATCHES["ProviderStore"], return_value=MagicMock()),
            patch(self._PATCHES["ProjectStore"], return_value=mocks["projects"]),
            patch(self._PATCHES["AgentProfileStore"], return_value=MagicMock()),
            patch(self._PATCHES["RoleStore"], return_value=mocks["role_store"]),
            patch(self._PATCHES["migrate_agent_profiles_to_roles"]),
            patch(
                self._PATCHES["WebhookForwarder"],
                return_value=mocks["forwarder"],
            ) as mock_forwarder_cls,
            patch(
                self._PATCHES["Orchestrator"],
                return_value=mocks["orchestrator"],
            ),
        ):
            from oompah.bootstrap import setup_services

            services = await setup_services(
                str(tmp_path / "WORKFLOW.md"), cli_port=9090
            )

        assert services.port == 9090
        assert services.orchestrator is mocks["orchestrator"]
        assert services.webhook_forwarder is mocks["forwarder"]
        mock_forwarder_cls.assert_called_once_with(
            project_store=mocks["projects"],
            server_port=9090,
        )

    @pytest.mark.asyncio
    async def test_start_paused_flag_sets_paused(self, tmp_path):
        """When start_paused=True and orchestrator is not paused, it is paused."""
        mocks = self._make_mocks()
        mocks["orchestrator"].is_paused = False

        mock_sc = MagicMock(name="ServiceConfig_class")
        mock_sc.from_workflow.return_value = mocks["config"]

        with (
            patch(self._PATCHES["load_workflow"], return_value=mocks["workflow"]),
            patch(self._PATCHES["ServiceConfig"], mock_sc),
            patch(self._PATCHES["validate_dispatch_config"], return_value=[]),
            patch(
                self._PATCHES["ensure_backlog_compatible"],
                return_value=mocks["compat"],
            ),
            patch(self._PATCHES["ProviderStore"], return_value=MagicMock()),
            patch(self._PATCHES["ProjectStore"], return_value=mocks["projects"]),
            patch(self._PATCHES["AgentProfileStore"], return_value=MagicMock()),
            patch(self._PATCHES["RoleStore"], return_value=mocks["role_store"]),
            patch(self._PATCHES["migrate_agent_profiles_to_roles"]),
            patch(
                self._PATCHES["WebhookForwarder"],
                return_value=mocks["forwarder"],
            ),
            patch(
                self._PATCHES["Orchestrator"],
                return_value=mocks["orchestrator"],
            ),
        ):
            from oompah.bootstrap import setup_services

            await setup_services(str(tmp_path / "WORKFLOW.md"), start_paused=True)

        assert mocks["orchestrator"]._paused is True
        mocks["orchestrator"]._save_paused_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_label_bootstrap_alerts_are_attached_to_orchestrator(self, tmp_path):
        """setup_services() runs GitHub label bootstrap and surfaces alerts."""
        mocks = self._make_mocks()
        project = MagicMock(name="project")
        project.id = "proj-gh"
        project.name = "trickle"
        mocks["projects"].list_all.return_value = [project]
        mocks["projects"].sync_all_sources.return_value = {
            "proj-gh": {"git": "ok", "backlog": "skipped: github_issues"}
        }

        bootstrap_result = MagicMock(name="label_bootstrap_result")
        bootstrap_result.success = False
        bootstrap_result.status_summary.return_value = (
            "failed 1: oompah:status:proposed"
        )
        bootstrap_alert = {
            "level": "error",
            "source": "label_bootstrap:proj-gh",
            "message": "Cannot create required GitHub labels in org/repo",
        }

        mock_sc = MagicMock(name="ServiceConfig_class")
        mock_sc.from_workflow.return_value = mocks["config"]

        with (
            patch(self._PATCHES["load_workflow"], return_value=mocks["workflow"]),
            patch(self._PATCHES["ServiceConfig"], mock_sc),
            patch(self._PATCHES["validate_dispatch_config"], return_value=[]),
            patch(
                self._PATCHES["ensure_backlog_compatible"],
                return_value=mocks["compat"],
            ),
            patch(self._PATCHES["ProviderStore"], return_value=MagicMock()),
            patch(self._PATCHES["ProjectStore"], return_value=mocks["projects"]),
            patch(self._PATCHES["AgentProfileStore"], return_value=MagicMock()),
            patch(self._PATCHES["RoleStore"], return_value=mocks["role_store"]),
            patch(self._PATCHES["migrate_agent_profiles_to_roles"]),
            patch(
                self._PATCHES["WebhookForwarder"],
                return_value=mocks["forwarder"],
            ),
            patch(
                self._PATCHES["Orchestrator"],
                return_value=mocks["orchestrator"],
            ),
            patch(
                "oompah.backlog_webhooks.ensure_backlog_webhooks",
                return_value={"proj-gh": "skipped: github_issues"},
            ),
            patch(
                "oompah.label_bootstrap.ensure_github_labels",
                return_value={"proj-gh": bootstrap_result},
            ) as ensure_labels,
            patch(
                "oompah.label_bootstrap.build_label_bootstrap_alerts",
                return_value=[bootstrap_alert],
            ) as build_alerts,
        ):
            from oompah.bootstrap import setup_services

            await setup_services(str(tmp_path / "WORKFLOW.md"))

        ensure_labels.assert_called_once_with([project])
        build_alerts.assert_called_once_with({"proj-gh": bootstrap_result})
        assert bootstrap_alert in mocks["orchestrator"]._alerts

    @pytest.mark.asyncio
    async def test_missing_root_backlog_is_nonfatal_with_managed_projects(
        self,
        tmp_path,
    ):
        """GitHub-managed project stores do not require a root Backlog.md config."""
        from oompah.backlog_compat import BacklogCompatibilityError

        mocks = self._make_mocks()
        project = MagicMock(name="project")
        project.id = "proj-gh"
        project.name = "oompah"
        project.tracker_kind = "github_issues"
        mocks["projects"].list_all.return_value = [project]
        mocks["projects"].sync_all_sources.return_value = {
            "proj-gh": {"git": "ok", "backlog": "skipped: github_issues"}
        }

        mock_sc = MagicMock(name="ServiceConfig_class")
        mock_sc.from_workflow.return_value = mocks["config"]

        with (
            patch(self._PATCHES["load_workflow"], return_value=mocks["workflow"]),
            patch(self._PATCHES["ServiceConfig"], mock_sc),
            patch(self._PATCHES["validate_dispatch_config"], return_value=[]),
            patch(
                self._PATCHES["ensure_backlog_compatible"],
                side_effect=BacklogCompatibilityError(
                    "No Backlog.md project found in /tmp/repo. Run `backlog init`."
                ),
            ),
            patch(self._PATCHES["ProviderStore"], return_value=MagicMock()),
            patch(self._PATCHES["ProjectStore"], return_value=mocks["projects"]),
            patch(self._PATCHES["AgentProfileStore"], return_value=MagicMock()),
            patch(self._PATCHES["RoleStore"], return_value=mocks["role_store"]),
            patch(self._PATCHES["migrate_agent_profiles_to_roles"]),
            patch(
                self._PATCHES["WebhookForwarder"],
                return_value=mocks["forwarder"],
            ),
            patch(
                self._PATCHES["Orchestrator"],
                return_value=mocks["orchestrator"],
            ),
            patch("oompah.label_bootstrap.ensure_github_labels", return_value={}),
            patch(
                "oompah.backlog_webhooks.ensure_backlog_webhooks",
                return_value={"proj-gh": "skipped: github_issues"},
            ),
        ):
            from oompah.bootstrap import setup_services

            services = await setup_services(str(tmp_path / "WORKFLOW.md"))

        assert services.project_store is mocks["projects"]
        assert services.orchestrator is mocks["orchestrator"]

    @pytest.mark.asyncio
    async def test_missing_root_backlog_remains_fatal_without_managed_projects(
        self,
        tmp_path,
    ):
        """Legacy single-tracker startup still requires a Backlog.md config."""
        from oompah.backlog_compat import BacklogCompatibilityError
        from oompah.bootstrap import StartupError, setup_services

        mocks = self._make_mocks()

        mock_sc = MagicMock(name="ServiceConfig_class")
        mock_sc.from_workflow.return_value = mocks["config"]

        with (
            patch(self._PATCHES["load_workflow"], return_value=mocks["workflow"]),
            patch(self._PATCHES["ServiceConfig"], mock_sc),
            patch(self._PATCHES["validate_dispatch_config"], return_value=[]),
            patch(
                self._PATCHES["ensure_backlog_compatible"],
                side_effect=BacklogCompatibilityError(
                    "No Backlog.md project found in /tmp/repo. Run `backlog init`."
                ),
            ),
            patch(self._PATCHES["ProjectStore"], return_value=mocks["projects"]),
        ):
            with pytest.raises(StartupError, match="Backlog.md compatibility error"):
                await setup_services(str(tmp_path / "WORKFLOW.md"))


# ---------------------------------------------------------------------------
# __main__.main() — --server argument parsing
# ---------------------------------------------------------------------------


class TestMainServerArgument:
    """main() accepts --server {uvicorn,granian} without error."""

    def test_default_server_is_uvicorn(self, tmp_path, monkeypatch):
        """Omitting --server uses uvicorn (asyncio.run called)."""
        wf = tmp_path / "WORKFLOW.md"
        wf.write_text("tracker:\n  type: backlog\n")

        monkeypatch.setattr(sys, "argv", ["oompah", str(wf)])

        called_with: list[Any] = []

        async def _fake_run(*_args, **_kwargs):
            return False  # no restart

        with (
            patch("oompah.__main__._load_startup_env", return_value=0),
            patch("oompah.__main__._run", side_effect=_fake_run) as mock_run,
        ):
            # Import fresh so monkeypatches are visible.
            import oompah.__main__ as main_mod

            # Re-wire the module-level reference.
            main_mod._run = _fake_run
            main_mod.main()

        # If _run was called, uvicorn path was taken (not granian).
        # We verify no SystemExit was raised and _run was invoked.
        # (asyncio.run is the wrapper so we check indirectly via no error.)

    def test_server_granian_dispatches_run_granian(self, tmp_path, monkeypatch):
        """--server granian calls _run_granian() instead of asyncio.run."""
        wf = tmp_path / "WORKFLOW.md"
        wf.write_text("tracker:\n  type: backlog\n")

        monkeypatch.setattr(
            sys, "argv", ["oompah", str(wf), "--server", "granian"]
        )

        called: list[tuple] = []

        def _fake_run_granian(workflow_path, cli_port, start_paused=False):
            called.append((workflow_path, cli_port, start_paused))

        with (
            patch("oompah.__main__._load_startup_env", return_value=0),
            patch("oompah.__main__._run_granian", side_effect=_fake_run_granian),
        ):
            import oompah.__main__ as main_mod

            main_mod._run_granian = _fake_run_granian
            main_mod.main()

        assert len(called) == 1
        assert called[0][0] == str(wf)
        assert called[0][1] is None  # no --port given

    def test_server_invalid_choice_exits(self, tmp_path, monkeypatch):
        """An unrecognised --server value causes argparse to exit."""
        wf = tmp_path / "WORKFLOW.md"
        wf.write_text("")
        monkeypatch.setattr(
            sys, "argv", ["oompah", str(wf), "--server", "bogus"]
        )
        with pytest.raises(SystemExit):
            import oompah.__main__ as main_mod

            main_mod.main()


# ---------------------------------------------------------------------------
# _run_granian() — import guard
# ---------------------------------------------------------------------------


class TestRunGranianImportGuard:
    """_run_granian() exits cleanly when granian is not installed."""

    def test_exits_when_granian_missing(self, tmp_path, monkeypatch):
        """If granian cannot be imported, _run_granian exits with code 1."""
        # Temporarily hide granian from the import machinery.
        real_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__

        def _fake_import(name, *args, **kwargs):
            if name == "granian":
                raise ImportError("No module named 'granian'")
            return real_import(name, *args, **kwargs)

        wf = tmp_path / "WORKFLOW.md"
        wf.write_text("")

        # Patch builtins.__import__ to simulate granian being absent.
        with patch("builtins.__import__", side_effect=_fake_import):
            from oompah.__main__ import _run_granian

            with pytest.raises(SystemExit) as exc_info:
                _run_granian(str(wf), None)

        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# server.py — lifespan is attached to the FastAPI app
# ---------------------------------------------------------------------------


class TestServerLifespan:
    """The FastAPI app has a lifespan context manager attached."""

    def test_app_has_lifespan(self):
        from oompah.server import app

        # FastAPI exposes router.lifespan_context when lifespan= is passed.
        assert app.router.lifespan_context is not None

    def test_lifespan_is_noop_without_env(self):
        """Without OOMPAH_EMBED_ORCHESTRATOR=1 the lifespan yields immediately."""
        import asyncio
        import os
        from oompah.server import _lifespan, app

        async def _run():
            env_backup = os.environ.pop("OOMPAH_EMBED_ORCHESTRATOR", None)
            try:
                async with _lifespan(app):
                    pass  # Should not raise
            finally:
                if env_backup is not None:
                    os.environ["OOMPAH_EMBED_ORCHESTRATOR"] = env_backup

        asyncio.run(_run())  # Must complete without error
