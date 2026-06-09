"""Regression tests for TASK-495: manual dispatch endpoint fails inside
running event loop.

When POST /api/v1/orchestrator/dispatch/{identifier} is called from the live
FastAPI process, it runs inside an already-running event loop.  The old code
called orch._fetch_all_candidates() directly from the async route handler.
That method uses asyncio.run() internally (to drive its async per-project
fetch), so calling it from within a running event loop raised:

    RuntimeError: asyncio.run() cannot be called from a running event loop

The fix: wrap the call in asyncio.to_thread() so _fetch_all_candidates() runs
in a worker thread that has no running event loop, matching the pattern used
by the tick loop (loop.run_in_executor(self._tick_pool, ...)).
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

import oompah.server as server_module
from oompah.models import Issue


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_issue(identifier: str = "TASK-42") -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title="Test issue",
        state="open",
    )


def _make_orch_with_fetch_using_asyncio_run(issues: list[Issue]) -> MagicMock:
    """Return a mock orchestrator whose _fetch_all_candidates uses asyncio.run()
    internally — exactly like the real implementation.

    This is the critical piece of the regression test: if the dispatch handler
    calls _fetch_all_candidates() synchronously from the async route context,
    the asyncio.run() inside will raise RuntimeError.  If the handler correctly
    offloads to a thread (via asyncio.to_thread), this runs fine.
    """

    def _fetch_candidates_with_asyncio_run():
        async def _inner():
            return list(issues)

        # asyncio.run() creates a new event loop in the calling thread.  When
        # the calling thread already has a running loop (the FastAPI/uvicorn
        # loop), this raises RuntimeError.  The fix wraps this call in
        # asyncio.to_thread() so it runs in a fresh thread with no loop.
        return asyncio.run(_inner())

    mock_orch = MagicMock()
    mock_orch._fetch_all_candidates = _fetch_candidates_with_asyncio_run
    mock_orch._dispatch = AsyncMock()
    return mock_orch


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDispatchEndpointInsideEventLoop:
    """Verify api_orchestrator_dispatch works when called from a running loop."""

    @pytest.mark.asyncio
    async def test_dispatch_found_issue_no_event_loop_error(self):
        """Dispatch a known issue: must not raise 'asyncio.run() cannot be called
        from a running event loop' and must return {ok: true, dispatched: ...}.
        """
        issue = _make_issue("TASK-42")
        mock_orch = _make_orch_with_fetch_using_asyncio_run([issue])

        original_orch = server_module._orchestrator
        original_ipc = server_module._ipc
        try:
            server_module._orchestrator = mock_orch
            server_module._ipc = None

            # Calling from within the async test means we ARE inside a running
            # event loop — this is exactly the scenario that triggered the bug.
            response = await server_module.api_orchestrator_dispatch("TASK-42")
            data = json.loads(response.body)

            assert data.get("ok") is True, f"expected ok=true, got: {data}"
            assert data.get("dispatched") == "TASK-42"
            mock_orch._dispatch.assert_called_once_with(issue, attempt=None)
        finally:
            server_module._orchestrator = original_orch
            server_module._ipc = original_ipc

    @pytest.mark.asyncio
    async def test_dispatch_unknown_issue_returns_404_no_event_loop_error(self):
        """When the requested issue is not a candidate, return 404 without
        raising 'asyncio.run() cannot be called from a running event loop'.
        """
        mock_orch = _make_orch_with_fetch_using_asyncio_run([])  # no candidates

        original_orch = server_module._orchestrator
        original_ipc = server_module._ipc
        try:
            server_module._orchestrator = mock_orch
            server_module._ipc = None

            response = await server_module.api_orchestrator_dispatch("TASK-999")
            data = json.loads(response.body)

            assert response.status_code == 404
            assert "not found" in data.get("error", "").lower()
            # _dispatch must not have been called
            mock_orch._dispatch.assert_not_called()
        finally:
            server_module._orchestrator = original_orch
            server_module._ipc = original_ipc

    @pytest.mark.asyncio
    async def test_dispatch_error_body_is_not_event_loop_error(self):
        """If something goes wrong in the route, the error message must not be
        the nested-event-loop error (regression guard).
        """
        issue = _make_issue("TASK-42")
        mock_orch = _make_orch_with_fetch_using_asyncio_run([issue])
        # Make _dispatch raise to trigger the except branch
        mock_orch._dispatch = AsyncMock(side_effect=RuntimeError("dispatch failed for testing"))

        original_orch = server_module._orchestrator
        original_ipc = server_module._ipc
        try:
            server_module._orchestrator = mock_orch
            server_module._ipc = None

            response = await server_module.api_orchestrator_dispatch("TASK-42")
            data = json.loads(response.body)

            # Must not be the nested event-loop error
            error_msg = data.get("error", "")
            assert "running event loop" not in error_msg, (
                f"Got the event-loop nesting error instead of the real error: {error_msg!r}"
            )
            # Must report the actual error
            assert "dispatch failed for testing" in error_msg
        finally:
            server_module._orchestrator = original_orch
            server_module._ipc = original_ipc

    @pytest.mark.asyncio
    async def test_dispatch_fetch_called_off_event_loop(self):
        """_fetch_all_candidates must be called from a worker thread (off the
        event loop), not from the FastAPI event loop thread itself.

        This verifies the asyncio.to_thread() fix rather than just testing the
        symptom.
        """
        import threading

        called_from_thread: list[threading.Thread] = []
        main_thread = threading.current_thread()
        event_loop_thread: list[threading.Thread] = []

        def _fetch_candidates():
            called_from_thread.append(threading.current_thread())
            return []

        mock_orch = MagicMock()
        mock_orch._fetch_all_candidates = _fetch_candidates
        mock_orch._dispatch = AsyncMock()

        # Capture which thread runs the event loop
        event_loop_thread.append(threading.current_thread())

        original_orch = server_module._orchestrator
        original_ipc = server_module._ipc
        try:
            server_module._orchestrator = mock_orch
            server_module._ipc = None

            await server_module.api_orchestrator_dispatch("TASK-missing")

            assert called_from_thread, "_fetch_all_candidates was never called"
            fetch_thread = called_from_thread[0]
            # asyncio.to_thread() runs the callable in a ThreadPoolExecutor
            # worker — a different thread from the event loop's thread.
            assert fetch_thread is not event_loop_thread[0], (
                "_fetch_all_candidates ran on the event-loop thread; it must run "
                "off the event loop via asyncio.to_thread()"
            )
        finally:
            server_module._orchestrator = original_orch
            server_module._ipc = original_ipc
