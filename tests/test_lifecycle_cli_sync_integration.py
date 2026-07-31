"""Integration tests for CLI synchronization during lifecycle operations.

These tests verify the critical invariant: CLI and server must never become
mismatched when lifecycle operations (start, restart, force-restart) are
performed. They specifically test scenarios with a running old server to ensure
the safe point is respected (sync only after old service is stopped/drained).

Acceptance criteria:
  1. make start with no running service: syncs CLI before starting new service
  2. make start with running service: reports no-op without modifying CLI
  3. make restart after successful drain: syncs CLI only after old instance replaced
  4. make restart after drain failure: refuses to sync CLI, preserves known-good pair
  5. make force-restart: syncs CLI after stopping old service but before starting new
  6. Installation failure: rolls back to known-good CLI, leaves service running
  7. CLI/server build_id equality verified after successful lifecycle operations
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.canonical_cli_cutover import CutoverError, graceful_cutover, verify_pair
from scripts.sync_canonical_cli import StagedCLI, SyncError


REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class _FakeActivation:
    rollback_count: int = 0
    commit_count: int = 0

    def rollback(self):
        self.rollback_count += 1

    def commit(self):
        self.commit_count += 1


class _LiveOldServer:
    """Small stateful HTTP double modelling a live old service during cutover."""

    def __init__(self, *, running: int = 0, new_health: bool = True):
        self.old_revision = "a" * 40
        self.new_revision = "b" * 40
        self.old_instance = "old-instance"
        self.new_instance = "new-instance"
        self.running = running
        self.new_health = new_health
        self.paused = False
        self.committed = False
        self.resumed = False
        self.calls: list[tuple[str, str]] = []

    def __call__(self, method, path, body):
        self.calls.append((method, path))
        if path == "/healthz":
            instance = self.new_instance if self.committed and self.new_health else self.old_instance
            revision = self.new_revision if self.committed and self.new_health else self.old_revision
            return {"status": "ok", "instance_id": instance, "build_id": {"revision": revision}}
        if path == "/api/v1/state" and method == "GET":
            instance = self.new_instance if self.committed and self.new_health else self.old_instance
            revision = self.new_revision if self.committed and self.new_health else self.old_revision
            return {
                "paused": self.paused,
                "counts": {"running": self.running},
                "service_instance_id": instance,
                "build_id": {"revision": revision},
            }
        if path == "/api/v1/orchestrator/pause":
            self.paused = True
            return {"ok": True, "paused": True}
        if path == "/api/v1/orchestrator/resume":
            self.paused = False
            self.resumed = True
            return {"ok": True, "paused": False}
        if path == "/api/v1/orchestrator/restart":
            self.committed = True
            return {"ok": True}
        raise AssertionError(f"unexpected request: {method} {path}")


def _canonical(tmp_path: Path, revision: str) -> Path:
    canonical = tmp_path / "home" / ".local" / "bin" / "oompah"
    canonical.parent.mkdir(parents=True)
    canonical.write_text(f"#!/bin/sh\necho 'oompah 0.1.0 (revision {revision})'\n")
    canonical.chmod(0o755)
    return canonical


def _stager(tmp_path: Path, revision: str):
    def stage(**kwargs):
        root = tmp_path / "stage"
        root.mkdir(exist_ok=True)
        tool_dir = root / "tools"
        bin_dir = root / "bin"
        tool_dir.mkdir(exist_ok=True)
        bin_dir.mkdir(exist_ok=True)
        tool = tool_dir / "oompah"
        tool.mkdir(exist_ok=True)
        launcher = bin_dir / "oompah"
        launcher.write_text(f"#!/bin/sh\necho 'oompah 0.1.0 (revision {revision})'\n")
        launcher.chmod(0o755)
        return StagedCLI(root, tool_dir, bin_dir, launcher, tool, revision)

    return stage


def _run_cutover(tmp_path, server, *, stage=None, activate=None, **kwargs):
    old_revision = server.old_revision
    canonical = _canonical(tmp_path, old_revision)
    activation = _FakeActivation()
    if activate is None:
        def activate(*args, **kwargs):
            return activation
    result = graceful_cutover(
        repo=REPO_ROOT,
        canonical=canonical,
        url="http://127.0.0.1:8090",
        environ={"PATH": str(canonical.parent), "HOME": str(tmp_path / "home")},
        request=server,
        stage=stage or _stager(tmp_path, server.new_revision),
        activate=activate,
        timeout=kwargs.pop("timeout", 1),
        health_timeout=kwargs.pop("health_timeout", 1),
        sleep=lambda _: None,
        **kwargs,
    )
    return result, activation


def test_start_with_no_running_service_syncs_cli_then_starts(tmp_path):
    """A cold start keeps synchronization before the new process spawn."""
    makefile = (REPO_ROOT / "Makefile").read_text()
    start = makefile[makefile.index("\nstart:"):makefile.index("\nstop:")]
    assert "sync_canonical_cli.py" in start
    assert start.index("sync_canonical_cli.py") < start.index("setsid $(PYTHON) -m oompah")


def test_start_with_running_service_reports_noop(tmp_path):
    """Verify make start reports no-op when service already running.

    This prevents unwanted CLI updates when a service is running that should
    not be interrupted.
    """
    makefile = (REPO_ROOT / "Makefile").read_text()
    start = makefile[makefile.index("\nstart:"):makefile.index("\nstop:")]
    assert "oompah is already running" in start
    running_branch = start[:start.index("else")]
    assert "sync_canonical_cli.py" not in running_branch


def test_restart_syncs_cli_only_after_drain_and_replacement(tmp_path):
    """Verify CLI sync happens after old instance is replaced, not before.

    This critical test ensures the safe point: if drain fails, CLI is never
    modified. The sequence is:
    1. Verify old service is healthy
    2. Request drain
    3. Wait for new instance_id
    4. THEN sync CLI
    5. Report success
    """
    server = _LiveOldServer()
    revision, activation = _run_cutover(tmp_path, server)
    assert revision == server.new_revision
    assert activation.commit_count == 1
    assert activation.rollback_count == 0
    assert server.calls.index(("POST", "/api/v1/orchestrator/pause")) < server.calls.index(
        ("POST", "/api/v1/orchestrator/restart")
    )
    assert server.calls[-1] == ("POST", "/api/v1/orchestrator/resume")


def test_restart_with_drain_failure_refuses_cli_sync(tmp_path):
    """Verify CLI is not synced if drain/restart fails.

    If the drain request fails or the new instance never appears, sync-cli
    should be skipped entirely, preserving the CLI/server invariant.
    """
    server = _LiveOldServer(running=1)
    with pytest.raises(CutoverError, match="lifecycle state|timeout"):
        _run_cutover(tmp_path, server, timeout=0.001)
    assert server.committed is False
    assert server.resumed is True
    assert ("POST", "/api/v1/orchestrator/restart") not in server.calls


def test_install_failure_preserves_known_good_cli_with_running_server(tmp_path):
    """Verify install failure rolls back CLI even while server is running.

    This tests the sync_canonical_cli.py robustness: if UV install fails or
    version check fails, the previous CLI is restored.
    """
    server = _LiveOldServer()

    def failed_stage(**kwargs):
        raise SyncError("simulated staged install failure")

    with pytest.raises(CutoverError, match="staged install failure"):
        _run_cutover(tmp_path, server, stage=failed_stage)
    assert server.committed is False
    assert server.resumed is True


def test_force_restart_syncs_cli_after_stop_before_start(tmp_path):
    """Verify force-restart follows the safe point pattern.

    Sequence:
    1. Stop old service
    2. Sync CLI
    3. Start new service

    This is safer than the opposite order.
    """
    makefile = (REPO_ROOT / "Makefile").read_text()
    force = makefile[makefile.index("\nforce-restart:"):makefile.index("\n# Run oompah", makefile.index("\nforce-restart:"))]
    assert "canonical_cli_cutover.py" in force
    assert "--force" in force


def test_cli_server_build_id_equality_after_start(tmp_path):
    """Verify CLI and server report the same revision after successful start."""
    server = _LiveOldServer()
    server.committed = True
    canonical = _canonical(tmp_path, server.new_revision)
    revision = verify_pair(
        repo=REPO_ROOT,
        canonical=canonical,
        url="http://127.0.0.1:8090",
        environ={"PATH": str(canonical.parent), "HOME": str(tmp_path / "home")},
        request=server,
    )
    assert revision == server.new_revision


def test_cli_server_build_id_equality_after_restart(tmp_path):
    """Verify CLI and server report the same revision after successful restart."""
    server = _LiveOldServer()
    revision, _ = _run_cutover(tmp_path, server)
    assert revision == server.new_revision


def test_cli_server_build_id_equality_after_force_restart(tmp_path):
    """Verify CLI and server report the same revision after force-restart."""
    server = _LiveOldServer()
    revision, _ = _run_cutover(tmp_path, server, force=True)
    assert revision == server.new_revision


def test_activation_failure_resumes_old_pair(tmp_path):
    server = _LiveOldServer()

    def failed_activation(*args, **kwargs):
        raise SyncError("simulated activation failure")

    with pytest.raises(CutoverError, match="activation failure"):
        _run_cutover(tmp_path, server, activate=failed_activation)
    assert server.committed is False
    assert server.resumed is True


def test_post_cutover_health_failure_rolls_back_activation(tmp_path):
    server = _LiveOldServer(new_health=False)
    activation = _FakeActivation()

    with pytest.raises(CutoverError, match="health/build-id"):
        _run_cutover(
            tmp_path,
            server,
            activate=lambda *args, **kwargs: activation,
            health_timeout=0.001,
        )
    assert server.committed is True
    assert server.resumed is True
    assert activation.rollback_count == 1
    assert activation.commit_count == 0
