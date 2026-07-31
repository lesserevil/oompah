"""Tests for the CLI/server build identity contract."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest


def test_version_command_is_human_readable_and_contains_revision():
    result = subprocess.run(
        [sys.executable, "-m", "oompah", "--version"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.startswith("oompah 0.1.0 (revision ")
    assert len(result.stdout.strip().rsplit(" ", 1)[-1].rstrip(")")) >= 7


@pytest.mark.asyncio
async def test_health_and_state_report_same_build_id():
    from oompah import server

    health = json.loads((await server.healthz()).body)
    old_orchestrator = server._orchestrator
    old_ipc = server._ipc
    old_snapshot = server._state_snapshot
    old_snapshot_at = server._state_snapshot_at
    try:
        server._orchestrator = object()
        server._ipc = None
        server._state_snapshot = {"counts": {"running": 0}}
        server._state_snapshot_at = 0.0
        state = json.loads((await server.api_state()).body)
    finally:
        server._orchestrator = old_orchestrator
        server._ipc = old_ipc
        server._state_snapshot = old_snapshot
        server._state_snapshot_at = old_snapshot_at

    assert health["build_id"]["revision"]
    assert state["build_id"] == health["build_id"]
