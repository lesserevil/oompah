"""Tests for orchestrator integration with ErrorWatcher auto-close
(oompah-zlz_2-0nc).

Verifies the wiring between Orchestrator._on_worker_exit and
ErrorWatcher.auto_close_for_issue:

* Successful retry (attempt > 0) → triggers auto-close.
* First-dispatch success (attempt == 0 or None) → does NOT auto-close.
* register_error_watcher() routes to the right watcher per project.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from oompah.config import ServiceConfig
from oompah.error_watcher import ErrorWatcher
from oompah.models import Issue, RunningEntry
from oompah.orchestrator import Orchestrator


def _make_issue(
    issue_id: str = "iss-1",
    identifier: str = "test-001",
    project_id: str | None = None,
) -> Issue:
    return Issue(
        id=issue_id,
        identifier=identifier,
        title="Some issue",
        description="x" * 50,
        state="in_progress",
        labels=[],
        priority=2,
        issue_type="task",
        project_id=project_id,
    )


def _make_running_entry(
    issue: Issue,
    *,
    retry_attempt: int = 0,
) -> RunningEntry:
    return RunningEntry(
        worker_task=None,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=retry_attempt,
        started_at=datetime.now(timezone.utc),
        agent_profile_name="default",
    )


def _make_orch(tmp_path) -> Orchestrator:
    config = ServiceConfig()
    return Orchestrator(
        config=config,
        workflow_path="WORKFLOW.md",
        state_path=str(tmp_path / "state.json"),
    )


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()
    asyncio.set_event_loop(None)


class TestOrchestratorAutoCloseHook:
    """Verify the orchestrator triggers ErrorWatcher.auto_close_for_issue."""

    def test_register_error_watcher_routes_by_project_id(self, tmp_path):
        orch = _make_orch(tmp_path)
        global_w = MagicMock(spec=ErrorWatcher)
        proj_w = MagicMock(spec=ErrorWatcher)
        orch.register_error_watcher(global_w, project_id=None)
        orch.register_error_watcher(proj_w, project_id="proj-A")

        # Project-scoped + global both come back for proj-A.
        out_a = orch._error_watchers_for_project("proj-A")
        assert proj_w in out_a and global_w in out_a
        # Project-scoped first.
        assert out_a[0] is proj_w

        # Unscoped issue uses only the global watcher.
        out_none = orch._error_watchers_for_project(None)
        assert out_none == [global_w]

        # Unknown project: still gets the global watcher.
        out_other = orch._error_watchers_for_project("proj-Z")
        assert out_other == [global_w]

    def test_retry_success_triggers_auto_close(self, tmp_path, event_loop):
        """retry_attempt > 0 + reason='normal' → auto_close_for_issue."""
        orch = _make_orch(tmp_path)

        watcher = MagicMock(spec=ErrorWatcher)
        watcher.auto_close_for_issue.return_value = ["oompah-task-1"]
        orch.register_error_watcher(watcher, project_id=None)

        issue = _make_issue(issue_id="iss-X", identifier="oompah-iss-X")
        entry = _make_running_entry(issue, retry_attempt=2)
        orch.state.running[issue.id] = entry

        # Stub trackers so the rest of _on_worker_exit doesn't fail.
        mock_tracker = MagicMock()
        mock_tracker.fetch_issue_detail.return_value = None  # closed-by-agent path
        orch.tracker = mock_tracker

        event_loop.run_until_complete(
            orch._on_worker_exit(issue.id, "normal", None)
        )

        watcher.auto_close_for_issue.assert_called_once()
        kwargs = watcher.auto_close_for_issue.call_args.kwargs
        args = watcher.auto_close_for_issue.call_args.args
        # First positional is issue_id
        assert args[0] == "iss-X"
        # Identifier is wired through for log/comment text
        assert kwargs.get("issue_identifier") == "oompah-iss-X"

    def test_first_dispatch_success_does_not_auto_close(
        self, tmp_path, event_loop
    ):
        """retry_attempt == 0 → auto_close not called (no retry happened)."""
        orch = _make_orch(tmp_path)

        watcher = MagicMock(spec=ErrorWatcher)
        orch.register_error_watcher(watcher, project_id=None)

        issue = _make_issue(issue_id="iss-Y", identifier="oompah-iss-Y")
        entry = _make_running_entry(issue, retry_attempt=0)
        orch.state.running[issue.id] = entry

        mock_tracker = MagicMock()
        mock_tracker.fetch_issue_detail.return_value = None
        orch.tracker = mock_tracker

        event_loop.run_until_complete(
            orch._on_worker_exit(issue.id, "normal", None)
        )

        watcher.auto_close_for_issue.assert_not_called()

    def test_failed_run_does_not_auto_close(self, tmp_path, event_loop):
        """reason != 'normal' must never auto-close."""
        orch = _make_orch(tmp_path)
        watcher = MagicMock(spec=ErrorWatcher)
        orch.register_error_watcher(watcher, project_id=None)

        issue = _make_issue(issue_id="iss-Z", identifier="oompah-iss-Z")
        entry = _make_running_entry(issue, retry_attempt=2)
        orch.state.running[issue.id] = entry

        mock_tracker = MagicMock()
        orch.tracker = mock_tracker

        # max_turns / abnormal / stalled — none should call auto_close.
        for reason in ("abnormal", "max_turns", "stalled"):
            orch.state.running[issue.id] = _make_running_entry(
                issue, retry_attempt=2
            )
            event_loop.run_until_complete(
                orch._on_worker_exit(issue.id, reason, "boom")
            )

        watcher.auto_close_for_issue.assert_not_called()

    def test_auto_close_failures_do_not_break_worker_exit(
        self, tmp_path, event_loop
    ):
        """If the watcher itself raises, the worker-exit path keeps going."""
        orch = _make_orch(tmp_path)

        watcher = MagicMock(spec=ErrorWatcher)
        watcher.auto_close_for_issue.side_effect = RuntimeError("watcher boom")
        orch.register_error_watcher(watcher, project_id=None)

        issue = _make_issue(issue_id="iss-W", identifier="oompah-iss-W")
        entry = _make_running_entry(issue, retry_attempt=3)
        orch.state.running[issue.id] = entry

        mock_tracker = MagicMock()
        mock_tracker.fetch_issue_detail.return_value = None
        orch.tracker = mock_tracker

        # Should NOT raise.
        event_loop.run_until_complete(
            orch._on_worker_exit(issue.id, "normal", None)
        )
        watcher.auto_close_for_issue.assert_called_once()
