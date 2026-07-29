"""Test synchronization of duplicate screening state between /api/v1/state and /api/v1/issues."""

from __future__ import annotations

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from oompah.duplicate_screening import (
    DETECTOR_VERSION,
    ScreeningState,
    ScreeningVerdict,
    complete_claim_record,
    new_claim_record,
)
from oompah.models import Issue, OrchestratorState, RunningEntry
from oompah.statuses import OPEN
from datetime import datetime, timezone


@pytest.fixture
def mock_orch():
    """Create a mock orchestrator for testing."""
    orch = MagicMock()
    orch.state = OrchestratorState(max_concurrent_agents=3)
    orch.config = MagicMock()
    orch.config.duplicate_preflight_max_agents = 1
    return orch


@pytest.fixture
def test_issue():
    """Create a test issue."""
    return Issue(
        id="TASK-1",
        identifier="TASK-1",
        title="Implement feature",
        description="Test description",
        state=OPEN,
        issue_type="task",
        project_id="project-1",
        priority=2,
        tracker_kind="test",
    )


@pytest.mark.asyncio
async def test_issues_snapshot_refreshes_before_broadcast(mock_orch, test_issue):
    """Test that _do_broadcast_issues refreshes snapshot before broadcasting.
    
    This is critical for duplicate-screening sync: the snapshot MUST be refreshed
    before any broadcast to prevent stale payloads from overwriting newer state.
    """
    from oompah import server
    
    # Track the order of operations
    operations = []
    
    original_ensure_refresh = server._ensure_issues_snapshot_refresh
    original_broadcast = server._broadcast
    
    async def track_ensure_refresh(*args, **kwargs):
        operations.append("refresh_started")
        await original_ensure_refresh(*args, **kwargs)
        operations.append("refresh_queued")
    
    async def track_broadcast(msg):
        operations.append("broadcast")
        await original_broadcast(msg)
    
    with patch.object(server, "_ensure_issues_snapshot_refresh", track_ensure_refresh):
        with patch.object(server, "_broadcast", track_broadcast):
            with patch.object(server, "_get_orchestrator", return_value=mock_orch):
                with patch.object(server, "_issues_snapshot_payload", return_value={"data": []}):
                    server._ws_clients.add(MagicMock())  # Add a mock client
                    try:
                        await server._do_broadcast_issues()
                    finally:
                        server._ws_clients.clear()
    
    # Verify that refresh is started before broadcast
    assert "refresh_started" in operations
    assert "broadcast" in operations
    refresh_idx = operations.index("refresh_started")
    broadcast_idx = operations.index("broadcast")
    assert refresh_idx < broadcast_idx, "Refresh must be started before broadcast"


@pytest.mark.asyncio
async def test_wait_for_issues_snapshot_refresh_returns_completion_status():
    """Test that _wait_for_issues_snapshot_refresh returns True when refresh completes."""
    from oompah import server
    
    # Create a mock refresh task that completes immediately
    async def completed_task():
        return {"data": []}
    
    with patch.object(server, "_issues_refresh_task", asyncio.create_task(completed_task())):
        result = await server._wait_for_issues_snapshot_refresh(timeout_ms=1000)
        assert result is True, "Should return True when refresh completes"


@pytest.mark.asyncio
async def test_wait_for_issues_snapshot_refresh_returns_false_on_timeout():
    """Test that _wait_for_issues_snapshot_refresh returns False on timeout."""
    from oompah import server
    
    # Create a mock refresh task that never completes
    async def never_completes():
        await asyncio.sleep(10)
        return {"data": []}
    
    with patch.object(server, "_issues_refresh_task", asyncio.create_task(never_completes())):
        result = await server._wait_for_issues_snapshot_refresh(timeout_ms=10)
        assert result is False, "Should return False when refresh times out"
        # Clean up the task
        await server._issues_refresh_task


@pytest.mark.asyncio
async def test_do_broadcast_issues_skips_broadcast_on_timeout(mock_orch):
    """Test that _do_broadcast_issues doesn't broadcast if refresh times out.
    
    This prevents stale payloads from overwriting newer state.
    """
    from oompah import server
    
    broadcast_called = False
    
    async def never_completes():
        await asyncio.sleep(10)
        return {"data": []}
    
    async def track_broadcast(msg):
        nonlocal broadcast_called
        broadcast_called = True
    
    with patch.object(server, "_ensure_issues_snapshot_refresh") as mock_ensure:
        mock_ensure.return_value = None
        with patch.object(server, "_issues_refresh_task", asyncio.create_task(never_completes())):
            with patch.object(server, "_broadcast", track_broadcast):
                with patch.object(server, "_get_orchestrator", return_value=mock_orch):
                    server._ws_clients.add(MagicMock())  # Add a mock client
                    try:
                        await server._do_broadcast_issues()
                    finally:
                        server._ws_clients.clear()
                        # Clean up the task
                        if server._issues_refresh_task:
                            server._issues_refresh_task.cancel()
                            try:
                                await server._issues_refresh_task
                            except asyncio.CancelledError:
                                pass
    
    assert not broadcast_called, "Should not broadcast if refresh times out"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
