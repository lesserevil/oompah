"""Tests for clean lifespan abort on startup-validation failure (TASK-472.2).

Covers:
- setup_services() raises StartupError (not sys.exit) on validation failures
- The Granian lifespan (_lifespan) catches StartupError cleanly:
  no exception escapes the context manager (avoids "Task exception was never
  retrieved") and os._exit(1) is called
- The uvicorn path (_run in __main__) converts StartupError → sys.exit(1)
  (preserving existing behaviour)
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# 1.  StartupError is raised (not sys.exit) by setup_services on failures
# ---------------------------------------------------------------------------


class TestSetupServicesRaisesStartupError:
    """setup_services() must raise StartupError, not call sys.exit()."""

    @pytest.mark.asyncio
    async def test_bad_workflow_path_raises_startup_error(self, tmp_path):
        """Missing WORKFLOW.md → StartupError."""
        from oompah.bootstrap import StartupError, setup_services

        with pytest.raises(StartupError, match="Failed to load workflow"):
            await setup_services(
                str(tmp_path / "nonexistent_WORKFLOW.md"),
            )

    @pytest.mark.asyncio
    async def test_config_validation_error_raises_startup_error(
        self, tmp_path,
    ):
        """validate_dispatch_config returning errors → StartupError."""
        from oompah.bootstrap import StartupError, setup_services
        from oompah.models import WorkflowDefinition

        fake_wf = WorkflowDefinition(config={}, prompt_template="")

        with (
            # Patch in the module that bootstrap imports them FROM at runtime
            patch("oompah.config.load_workflow", return_value=fake_wf),
            patch(
                "oompah.config.validate_dispatch_config",
                return_value=["tracker.kind is required"],
            ),
            patch(
                "oompah.config.ServiceConfig.from_workflow",
                return_value=MagicMock(
                    strict_profile_source="warn",
                    workflow_has_profiles_block=False,
                    agent_profiles_drift=False,
                    server_port=None,
                ),
            ),
            patch(
                "oompah.backlog_compat.ensure_backlog_compatible",
                return_value=MagicMock(changed=False),
            ),
        ):
            with pytest.raises(StartupError, match="Config validation failed"):
                await setup_services(str(tmp_path / "WORKFLOW.md"))

    @pytest.mark.asyncio
    async def test_backlog_compat_error_raises_startup_error(
        self, tmp_path,
    ):
        """BacklogCompatibilityError → StartupError."""
        from oompah.bootstrap import StartupError, setup_services
        from oompah.backlog_compat import BacklogCompatibilityError
        from oompah.models import WorkflowDefinition

        fake_wf = WorkflowDefinition(config={}, prompt_template="")

        with (
            patch("oompah.config.load_workflow", return_value=fake_wf),
            patch(
                "oompah.config.validate_dispatch_config", return_value=[],
            ),
            patch(
                "oompah.config.ServiceConfig.from_workflow",
                return_value=MagicMock(
                    strict_profile_source="warn",
                    workflow_has_profiles_block=False,
                    agent_profiles_drift=False,
                    server_port=None,
                ),
            ),
            patch(
                "oompah.backlog_compat.ensure_backlog_compatible",
                side_effect=BacklogCompatibilityError("boom"),
            ),
        ):
            with pytest.raises(StartupError, match="Backlog.md compatibility error"):
                await setup_services(str(tmp_path / "WORKFLOW.md"))

    @pytest.mark.asyncio
    async def test_strict_profile_source_raises_startup_error(
        self, tmp_path, monkeypatch,
    ):
        """Strict mode + profiles block present → StartupError."""
        from oompah.bootstrap import StartupError, setup_services
        from oompah.models import WorkflowDefinition

        fake_wf = WorkflowDefinition(config={}, prompt_template="")

        with (
            patch("oompah.config.load_workflow", return_value=fake_wf),
            patch(
                "oompah.config.validate_dispatch_config", return_value=[],
            ),
            patch(
                "oompah.config.ServiceConfig.from_workflow",
                return_value=MagicMock(
                    strict_profile_source="strict",
                    workflow_has_profiles_block=True,
                    agent_profiles_drift=False,
                    server_port=None,
                ),
            ),
            patch(
                "oompah.backlog_compat.ensure_backlog_compatible",
                return_value=MagicMock(changed=False),
            ),
        ):
            with pytest.raises(StartupError, match="Strict profile-source mode"):
                await setup_services(str(tmp_path / "WORKFLOW.md"))

    @pytest.mark.asyncio
    async def test_setup_services_does_not_call_sys_exit(self, tmp_path):
        """setup_services() must never call sys.exit() — it raises instead."""
        from oompah.bootstrap import StartupError, setup_services

        with patch("sys.exit") as mock_exit:
            with pytest.raises(StartupError):
                await setup_services(str(tmp_path / "no_such.md"))

            mock_exit.assert_not_called()


# ---------------------------------------------------------------------------
# 2.  Lifespan catches StartupError cleanly (no exception escape)
# ---------------------------------------------------------------------------


class TestLifespanCleanAbort:
    """The Granian lifespan must catch StartupError without letting any
    exception escape the context manager.

    The key invariant: when ``OOMPAH_EMBED_ORCHESTRATOR=1`` and
    ``setup_services()`` raises ``StartupError``, the lifespan coroutine
    must *not* re-raise the exception.  Instead it calls ``os._exit(1)``
    (which we mock) so the exception never reaches asyncio's task machinery.
    """

    @pytest.mark.asyncio
    async def test_startup_error_does_not_escape_lifespan(
        self, monkeypatch,
    ):
        """StartupError raised in setup_services → caught inside _lifespan.

        The context manager must not re-raise; os._exit must be called.
        When ``setup_services`` is patched via ``oompah.bootstrap``, the
        local import inside the lifespan function picks up the mock.
        """
        from oompah.bootstrap import StartupError
        import oompah.server as server_mod

        monkeypatch.setenv("OOMPAH_EMBED_ORCHESTRATOR", "1")
        monkeypatch.setenv("OOMPAH_WORKFLOW_PATH", "/nonexistent/WORKFLOW.md")

        os_exit_called_with: list[int] = []

        def fake_os_exit(code: int) -> None:
            # Raise SystemExit so we can assert _exit was called without
            # actually killing the test process.
            os_exit_called_with.append(code)
            raise SystemExit(code)

        # Patch setup_services in the bootstrap module; the lifespan's local
        # `from oompah.bootstrap import setup_services` will get the mock.
        with (
            patch(
                "oompah.bootstrap.setup_services",
                side_effect=StartupError("bad config"),
            ),
            patch("os._exit", side_effect=fake_os_exit),
            # Suppress the os.kill call to parent — not meaningful in tests.
            patch("os.kill"),
        ):
            # We expect SystemExit (from our fake_os_exit) rather than
            # StartupError escaping the lifespan.
            with pytest.raises(SystemExit) as exc_info:
                async with server_mod._lifespan(server_mod.app):
                    pass  # pragma: no cover — lifespan aborts before yield

        assert os_exit_called_with == [1], (
            "os._exit(1) must be called on StartupError"
        )
        assert exc_info.value.code == 1

    @pytest.mark.asyncio
    async def test_startup_error_not_leaked_as_task_exception(
        self, monkeypatch,
    ):
        """Verify the lifespan never re-raises StartupError.

        'Task exception was never retrieved' fires when a bare exception
        escapes a coroutine used as an asyncio Task.  We confirm here that
        when setup_services raises StartupError the lifespan catches it
        internally and only raises SystemExit (from our os._exit mock), not
        the original StartupError.  Using the lifespan directly (not via
        asyncio.create_task) avoids platform-specific Task + SystemExit
        interaction differences across Python versions.
        """
        from oompah.bootstrap import StartupError
        import oompah.server as server_mod

        monkeypatch.setenv("OOMPAH_EMBED_ORCHESTRATOR", "1")
        monkeypatch.setenv("OOMPAH_WORKFLOW_PATH", "/nonexistent/WORKFLOW.md")

        escaped_exception: list[BaseException] = []

        with (
            patch(
                "oompah.bootstrap.setup_services",
                side_effect=StartupError("validation failed"),
            ),
            patch("os._exit", side_effect=SystemExit(1)),
            patch("os.kill"),
        ):
            try:
                async with server_mod._lifespan(server_mod.app):
                    pass  # pragma: no cover
            except SystemExit:
                pass  # expected from our fake os._exit
            except BaseException as exc:  # noqa: BLE001
                # Any OTHER exception (especially StartupError) is a bug.
                escaped_exception.append(exc)

        assert escaped_exception == [], (
            f"Exception(s) escaped the lifespan unexpectedly: {escaped_exception}"
        )

    @pytest.mark.asyncio
    async def test_lifespan_noop_without_embed_flag(self, monkeypatch):
        """Without OOMPAH_EMBED_ORCHESTRATOR, the lifespan is a no-op."""
        import oompah.server as server_mod

        monkeypatch.delenv("OOMPAH_EMBED_ORCHESTRATOR", raising=False)

        # Must not raise or call setup_services.
        with patch("oompah.bootstrap.setup_services") as mock_setup:
            async with server_mod._lifespan(server_mod.app):
                pass

        mock_setup.assert_not_called()

    @pytest.mark.asyncio
    async def test_os_kill_sigterm_sent_to_parent_on_abort(
        self, monkeypatch,
    ):
        """On StartupError the lifespan signals the Granian supervisor via
        os.kill(os.getppid(), SIGTERM) before calling os._exit(1)."""
        from oompah.bootstrap import StartupError
        import oompah.server as server_mod

        monkeypatch.setenv("OOMPAH_EMBED_ORCHESTRATOR", "1")
        monkeypatch.setenv("OOMPAH_WORKFLOW_PATH", "/no/WORKFLOW.md")

        kill_calls: list[tuple] = []

        def fake_kill(pid: int, sig: int) -> None:
            kill_calls.append((pid, sig))

        with (
            patch(
                "oompah.bootstrap.setup_services",
                side_effect=StartupError("bad cfg"),
            ),
            patch("os._exit", side_effect=SystemExit(1)),
            patch("os.kill", side_effect=fake_kill),
            patch("os.getppid", return_value=99999),
        ):
            with pytest.raises(SystemExit):
                async with server_mod._lifespan(server_mod.app):
                    pass

        assert any(
            pid == 99999 and sig == signal.SIGTERM
            for pid, sig in kill_calls
        ), f"Expected os.kill(99999, SIGTERM), got {kill_calls}"


# ---------------------------------------------------------------------------
# 3.  Uvicorn path: StartupError → sys.exit(1) (preserved behaviour)
# ---------------------------------------------------------------------------


class TestUvicornPathPreservesExitBehavior:
    """In the uvicorn (_run) path, StartupError must convert to sys.exit(1)."""

    @pytest.mark.asyncio
    async def test_startup_error_becomes_sysexit_1(self, tmp_path):
        """_run() catches StartupError and calls sys.exit(1)."""
        from oompah.__main__ import _run
        from oompah.bootstrap import StartupError

        # Patch setup_services in bootstrap; _run()'s local import gets mock.
        with patch(
            "oompah.bootstrap.setup_services",
            side_effect=StartupError("bad"),
        ):
            with pytest.raises(SystemExit) as exc_info:
                await _run(str(tmp_path / "WORKFLOW.md"), cli_port=None)

        assert exc_info.value.code == 1

    @pytest.mark.asyncio
    async def test_sys_exit_not_os_exit_in_uvicorn_path(self, tmp_path):
        """_run() uses sys.exit, not os._exit (preserves asyncio cleanup)."""
        from oompah.__main__ import _run
        from oompah.bootstrap import StartupError

        os_exit_calls: list = []

        with (
            patch(
                "oompah.bootstrap.setup_services",
                side_effect=StartupError("x"),
            ),
            patch("os._exit", side_effect=lambda c: os_exit_calls.append(c)),
        ):
            with pytest.raises(SystemExit):
                await _run(str(tmp_path / "WORKFLOW.md"), cli_port=None)

        # os._exit should NOT be called in the uvicorn path.
        assert os_exit_calls == [], (
            f"os._exit must not be called in uvicorn path; calls: {os_exit_calls}"
        )
