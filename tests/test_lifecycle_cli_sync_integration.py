"""Integration tests for CLI synchronization during lifecycle operations.

These tests verify the critical invariant: CLI and server must never become
mismatched when lifecycle operations (start, restart, force-restart) are
performed. They specifically test scenarios with a running old server to ensure
the safe point is respected (sync only after old service is stopped/drained).

Acceptance criteria:
  1. make start with no running service: syncs CLI before starting new service
  2. make start with running service: reports no-op without modifying CLI
  3. make restart: drains, stages, and atomically activates before server exec
  4. make restart after drain timeout: recovers only the still-running worker
  5. make force-restart: uses the same transaction while skipping agent drain
  6. Pre-restart failure: rolls back to the known-good CLI and resumes the service
  7. CLI/server build_id equality verified after successful lifecycle operations
  8. Post-restart probes prove a pair or quarantine the exact owned service
"""

from __future__ import annotations

import json
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path

import pytest

import scripts.sync_canonical_cli as sync_cli
from scripts.canonical_cli_cutover import (
    CutoverError,
    CutoverUncertainError,
    _capture_owned_service,
    _quarantine_owned_service,
    graceful_cutover,
    verify_pair,
)
from scripts.process_identity import read_identity
from scripts.sync_canonical_cli import StagedCLI, SyncError, synchronize


REPO_ROOT = Path(__file__).resolve().parents[1]
_MATCHING_STATE_INSTANCE = object()


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

    def __init__(
        self,
        *,
        running: int = 0,
        new_health: bool = True,
        reported_new_revision: str | None = None,
        restart_drops: bool = False,
        restart_drops_before_accept: bool = False,
        initially_paused: bool = False,
        complete_after_quiesce_polls: int | None = None,
        old_state_instance: object = _MATCHING_STATE_INSTANCE,
        new_state_instance: object = _MATCHING_STATE_INSTANCE,
        resume_error: Exception | None = None,
    ):
        self.old_revision = "a" * 40
        self.new_revision = "b" * 40
        self.old_instance = "old-instance"
        self.new_instance = "new-instance"
        self.running = running
        self.new_health = new_health
        self.reported_new_revision = reported_new_revision or self.new_revision
        self.restart_drops = restart_drops
        self.restart_drops_before_accept = restart_drops_before_accept
        self.paused = initially_paused
        self.quiesced = False
        self.complete_after_quiesce_polls = complete_after_quiesce_polls
        self.old_state_instance = old_state_instance
        self.new_state_instance = new_state_instance
        self.resume_error = resume_error
        self.committed = False
        self.resumed = False
        self.stopped = False
        self.quarantine_reason: str | None = None
        self.restart_recovery: list[str] = []
        self.calls: list[tuple[str, str]] = []

    def __call__(self, method, path, body):
        self.calls.append((method, path))
        if self.stopped:
            raise ConnectionError("service is quarantined")
        if path == "/healthz":
            if self.committed and not self.new_health:
                raise ConnectionError("new service health is unavailable")
            instance = self.new_instance if self.committed else self.old_instance
            revision = (
                self.reported_new_revision if self.committed else self.old_revision
            )
            return {
                "status": "ok",
                "instance_id": instance,
                "build_id": {"revision": revision},
            }
        if path == "/api/v1/state" and method == "GET":
            if self.committed and not self.new_health:
                raise ConnectionError("new service state is unavailable")
            if (
                not self.committed
                and self.quiesced
                and self.complete_after_quiesce_polls is not None
            ):
                self.complete_after_quiesce_polls -= 1
                if self.complete_after_quiesce_polls <= 0:
                    # Model a natural worker exit, not a termination caused
                    # by the lifecycle request.
                    self.running = 0
            instance = self.new_instance if self.committed else self.old_instance
            revision = (
                self.reported_new_revision if self.committed else self.old_revision
            )
            state_instance = (
                self.new_state_instance if self.committed else self.old_state_instance
            )
            if state_instance is _MATCHING_STATE_INSTANCE:
                state_instance = instance
            return {
                "paused": self.paused,
                "quiesced": self.quiesced,
                "counts": {"running": self.running},
                "service_instance_id": state_instance,
                "build_id": {"revision": revision},
                "restart": {"in_progress": False},
            }
        if path == "/api/v1/orchestrator/pause":
            self.paused = True
            return {"ok": True, "paused": True}
        if path == "/api/v1/orchestrator/quiesce":
            self.quiesced = True
            return {"ok": True, "quiesced": True}
        if path == "/api/v1/orchestrator/resume":
            self.paused = False
            self.quiesced = False
            self.resumed = True
            if self.resume_error is not None:
                raise self.resume_error
            return {"ok": True, "paused": False, "quiesced": False}
        if path == "/api/v1/orchestrator/restart":
            if self.restart_drops_before_accept:
                raise ConnectionError("simulated drop before restart acceptance")
            if self.running:
                self.restart_recovery = [
                    f"running-worker-{number}" for number in range(self.running)
                ]
                # The old process terminates these after the restart drain
                # reaches its deadline.
                self.running = 0
            self.committed = True
            if self.restart_drops:
                raise ConnectionError("simulated connection drop during exec")
            return {"ok": True}
        raise AssertionError(f"unexpected request: {method} {path}")

    def quarantine(self, reason: str) -> None:
        self.quarantine_reason = reason
        self.stopped = True


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
        quarantine=kwargs.pop("quarantine", server.quarantine),
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


def test_restart_activates_only_after_natural_drain_before_restart(tmp_path):
    """Verify activation happens only after drain and before the restart request.

    The sequence is:
    1. Verify old service is healthy
    2. Quiesce and wait for drain
    3. Stage and atomically activate the CLI
    4. Request restart
    5. Verify the new instance and matching build identity
    """
    server = _LiveOldServer()
    revision, activation = _run_cutover(tmp_path, server)
    assert revision == server.new_revision
    assert activation.commit_count == 1
    assert activation.rollback_count == 0
    assert server.calls.index(("POST", "/api/v1/orchestrator/quiesce")) < server.calls.index(
        ("POST", "/api/v1/orchestrator/restart")
    )
    assert server.calls[-1] == ("POST", "/api/v1/orchestrator/resume")


def test_restart_drain_completion_is_not_requeued(tmp_path):
    """A worker that exits during quiesced drain is absent from recovery."""
    server = _LiveOldServer(running=1, complete_after_quiesce_polls=1)

    revision, activation = _run_cutover(tmp_path, server)

    assert revision == server.new_revision
    assert activation.commit_count == 1
    assert server.restart_recovery == []
    assert server.quiesced is False


def test_cutover_and_install_cli_share_one_transaction_lock(tmp_path, monkeypatch):
    server = _LiveOldServer()
    canonical = _canonical(tmp_path, server.old_revision)
    tool_dir = tmp_path / "home" / ".local" / "share" / "uv" / "tools"
    env = {"PATH": str(canonical.parent), "HOME": str(tmp_path / "home")}
    cutover_in_stage = threading.Event()
    release_cutover = threading.Event()
    install_thread_started = threading.Event()
    install_selected = threading.Event()
    errors: list[BaseException] = []
    results: dict[str, object] = {}
    install_revision = server.new_revision
    activation = _FakeActivation()

    def blocking_cutover_stage(**kwargs):
        cutover_in_stage.set()
        if not release_cutover.wait(timeout=5):
            raise TimeoutError("test did not release the cutover")
        return _stager(tmp_path, server.new_revision)(**kwargs)

    def selected_revision(_repo):
        install_selected.set()
        return install_revision

    def install_stage(**kwargs):  # pragma: no cover - a post-lock no-op is required
        raise AssertionError("the serialized install must observe the completed cutover")

    def activate_cutover(staged, **kwargs):
        replacement = canonical.parent / ".cutover-launcher"
        replacement.write_bytes(staged.launcher.read_bytes())
        replacement.chmod(staged.launcher.stat().st_mode & 0o777)
        replacement.replace(canonical)
        return activation

    monkeypatch.setattr(sync_cli, "selected_revision", selected_revision)
    monkeypatch.setattr(sync_cli, "stage_candidate", install_stage)

    def run_cutover():
        try:
            results["cutover"] = graceful_cutover(
                repo=REPO_ROOT,
                canonical=canonical,
                url="http://127.0.0.1:8090",
                environ=env,
                request=server,
                stage=blocking_cutover_stage,
                activate=activate_cutover,
                timeout=1,
                health_timeout=1,
                sleep=lambda _: None,
                quarantine=server.quarantine,
            )
        except BaseException as exc:  # pragma: no cover - assertion reports it
            errors.append(exc)

    def run_install():
        install_thread_started.set()
        try:
            results["install"] = synchronize(
                repo=REPO_ROOT,
                canonical=canonical,
                tool_dir=tool_dir,
                bin_dir=canonical.parent,
                environ=env,
            )
        except BaseException as exc:  # pragma: no cover - assertion reports it
            errors.append(exc)

    cutover_thread = threading.Thread(target=run_cutover)
    install_thread = threading.Thread(target=run_install)
    cutover_thread.start()
    assert cutover_in_stage.wait(timeout=5)
    install_thread.start()
    assert install_thread_started.wait(timeout=5)
    try:
        assert not install_selected.wait(timeout=0.2)
        assert install_thread.is_alive(), "install-cli must wait for restart resolution"
    finally:
        release_cutover.set()
        cutover_thread.join(timeout=5)
        install_thread.join(timeout=5)

    assert not cutover_thread.is_alive()
    assert not install_thread.is_alive()
    assert errors == []
    assert results == {"cutover": server.new_revision, "install": False}
    assert activation.commit_count == 1
    assert activation.rollback_count == 0
    assert install_revision in subprocess.check_output(
        [str(canonical), "--version"], text=True
    )
    assert not list(canonical.parent.glob(".oompah-cli-activation-*"))


def test_restart_timeout_recovers_only_undrained_worker(tmp_path):
    """A drain timeout crosses restart once and recovers the live worker."""
    server = _LiveOldServer(running=1)
    revision, activation = _run_cutover(tmp_path, server, timeout=0.001)

    assert revision == server.new_revision
    assert activation.commit_count == 1
    assert server.committed is True
    assert server.restart_recovery == ["running-worker-0"]
    assert server.calls.count(("POST", "/api/v1/orchestrator/restart")) == 1
    assert server.resumed is True


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


def test_force_restart_uses_transaction_without_agent_drain(tmp_path):
    """Force restart shares the cutover transaction and only skips drain wait."""
    makefile = (REPO_ROOT / "Makefile").read_text()
    restart = makefile[makefile.index("\nrestart:") : makefile.index("\ngraceful:")]
    force = makefile[
        makefile.index("\nforce-restart:") : makefile.index(
            "\n# Run oompah", makefile.index("\nforce-restart:")
        )
    ]
    assert '--pid-file "$(PID_FILE)"' in restart
    assert '--pid-meta-file "$(PID_META_FILE)"' in restart
    assert "canonical_cli_cutover.py" in force
    assert "--force" in force
    assert '--pid-file "$(PID_FILE)"' in force
    assert '--pid-meta-file "$(PID_META_FILE)"' in force


def test_cli_server_build_id_equality_after_start(tmp_path):
    """Verify CLI and server report the same revision after successful start."""
    server = _LiveOldServer()
    server.committed = True
    canonical = _canonical(tmp_path, server.new_revision)
    operator_path = str(canonical.parent)
    shadow_dir = tmp_path / "project" / ".venv" / "bin"
    shadow_dir.mkdir(parents=True)
    shadow = shadow_dir / "oompah"
    shadow.write_text("#!/bin/sh\necho 'oompah shadow'\n", encoding="utf-8")
    shadow.chmod(0o755)
    environ = {
        "PATH": f"{shadow_dir}:{operator_path}",
        "HOME": str(tmp_path / "home"),
    }
    revision = verify_pair(
        repo=REPO_ROOT,
        canonical=canonical,
        url="http://127.0.0.1:8090",
        environ=environ,
        operator_path=operator_path,
        request=server,
    )
    assert revision == server.new_revision


@pytest.mark.parametrize("state_instance", [None, "different-instance"])
def test_verify_pair_requires_matching_non_null_service_instances(
    tmp_path, state_instance
):
    server = _LiveOldServer(new_state_instance=state_instance)
    server.committed = True
    canonical = _canonical(tmp_path, server.new_revision)

    with pytest.raises(CutoverError, match="same non-null service instance"):
        verify_pair(
            repo=REPO_ROOT,
            canonical=canonical,
            url="http://127.0.0.1:8090",
            environ={"PATH": str(canonical.parent), "HOME": str(tmp_path / "home")},
            request=server,
        )


def test_cutover_refuses_unpaired_initial_identity_before_quiesce(tmp_path):
    server = _LiveOldServer(old_state_instance=None)

    with pytest.raises(CutoverError, match="same non-null service instance"):
        _run_cutover(tmp_path, server)

    assert ("POST", "/api/v1/orchestrator/quiesce") not in server.calls


@pytest.mark.parametrize("state_instance", [None, "different-instance"])
def test_candidate_equality_requires_matching_state_instance(tmp_path, state_instance):
    server = _LiveOldServer(new_state_instance=state_instance)
    activation = _FakeActivation()

    with pytest.raises(CutoverUncertainError, match="stopped.*candidate CLI"):
        _run_cutover(
            tmp_path,
            server,
            activate=lambda *args, **kwargs: activation,
            health_timeout=0.001,
        )

    assert server.stopped is True
    assert activation.rollback_count == 0
    assert activation.commit_count == 1


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


def test_restart_refuses_to_activate_without_quarantine_identity(tmp_path):
    server = _LiveOldServer()
    canonical = _canonical(tmp_path, server.old_revision)

    with pytest.raises(CutoverError, match="requires both --pid-file"):
        graceful_cutover(
            repo=REPO_ROOT,
            canonical=canonical,
            url="http://127.0.0.1:8090",
            environ={"PATH": str(canonical.parent), "HOME": str(tmp_path / "home")},
            request=server,
            stage=_stager(tmp_path, server.new_revision),
            timeout=1,
            health_timeout=1,
            sleep=lambda _: None,
        )

    assert ("POST", "/api/v1/orchestrator/quiesce") not in server.calls


def test_accepted_restart_health_timeout_quarantines_service(tmp_path):
    server = _LiveOldServer(new_health=False)
    activation = _FakeActivation()

    with pytest.raises(
        CutoverUncertainError, match="stopped.*candidate CLI was retained"
    ):
        _run_cutover(
            tmp_path,
            server,
            activate=lambda *args, **kwargs: activation,
            health_timeout=0.001,
        )
    assert server.committed is True
    assert server.resumed is False
    assert server.stopped is True
    assert activation.rollback_count == 0
    assert activation.commit_count == 1


def test_accepted_restart_connection_drop_proves_candidate_pair(tmp_path):
    server = _LiveOldServer(restart_drops=True)
    activation = _FakeActivation()

    revision, _ = _run_cutover(
        tmp_path,
        server,
        activate=lambda *args, **kwargs: activation,
    )
    assert revision == server.new_revision
    assert server.committed is True
    assert server.resumed is True
    assert server.stopped is False
    assert activation.rollback_count == 0
    assert activation.commit_count == 1


def test_candidate_resume_timeout_does_not_false_fail_cutover(tmp_path):
    """A proven candidate remains authoritative while migration delays resume."""
    server = _LiveOldServer(resume_error=TimeoutError("migration still draining"))
    activation = _FakeActivation()

    revision, _ = _run_cutover(
        tmp_path,
        server,
        activate=lambda *args, **kwargs: activation,
    )

    assert revision == server.new_revision
    assert server.committed is True
    assert server.stopped is False
    assert server.resumed is True
    assert activation.rollback_count == 0
    assert activation.commit_count == 1


def test_connection_drop_with_old_instance_still_live_restores_old_pair(tmp_path):
    server = _LiveOldServer(restart_drops_before_accept=True)
    activation = _FakeActivation()

    with pytest.raises(CutoverError, match="drop before.*old service and CLI pair"):
        _run_cutover(
            tmp_path,
            server,
            activate=lambda *args, **kwargs: activation,
            health_timeout=0.001,
        )
    assert server.committed is False
    assert server.resumed is True
    assert server.stopped is False
    assert activation.rollback_count == 1
    assert activation.commit_count == 0


def test_new_server_wrong_build_is_quarantined(tmp_path):
    server = _LiveOldServer(reported_new_revision="c" * 40)
    activation = _FakeActivation()

    with pytest.raises(
        CutoverUncertainError, match="stopped.*candidate CLI was retained"
    ):
        _run_cutover(
            tmp_path,
            server,
            activate=lambda *args, **kwargs: activation,
            health_timeout=0.001,
        )
    assert server.committed is True
    assert server.resumed is False
    assert server.stopped is True
    assert activation.rollback_count == 0
    assert activation.commit_count == 1


def test_previously_paused_service_remains_paused_after_success(tmp_path):
    server = _LiveOldServer(initially_paused=True)

    revision, _ = _run_cutover(tmp_path, server)

    assert revision == server.new_revision
    assert server.paused is True
    assert server.resumed is False
    assert ("POST", "/api/v1/orchestrator/quiesce") not in server.calls
    assert ("POST", "/api/v1/orchestrator/resume") not in server.calls


def test_previously_paused_service_remains_paused_after_activation_failure(tmp_path):
    server = _LiveOldServer(initially_paused=True)

    with pytest.raises(CutoverError, match="activation failure"):
        _run_cutover(
            tmp_path,
            server,
            activate=lambda *args, **kwargs: (_ for _ in ()).throw(
                SyncError("simulated activation failure")
            ),
        )

    assert server.paused is True
    assert server.resumed is False
    assert ("POST", "/api/v1/orchestrator/resume") not in server.calls


def test_quarantine_stops_only_the_captured_owned_process(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    pid_file = tmp_path / "oompah.pid"
    meta_file = tmp_path / "oompah.pid.meta"
    process = subprocess.Popen(
        ["sleep", "60"],
        cwd=workspace,
        start_new_session=True,
    )
    try:
        identity = read_identity(process.pid)
        assert identity is not None
        pid_file.write_text(f"{process.pid}\n", encoding="utf-8")
        meta_file.write_text(json.dumps(identity), encoding="utf-8")
        owned = _capture_owned_service(
            repo=workspace,
            pid_file=pid_file,
            pid_meta_file=meta_file,
        )

        _quarantine_owned_service(owned, timeout=2)

        assert read_identity(process.pid) is None
        assert not pid_file.exists()
        assert not meta_file.exists()
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=2)


def test_quarantine_capture_refuses_stale_process_identity(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    pid_file = tmp_path / "oompah.pid"
    meta_file = tmp_path / "oompah.pid.meta"
    process = subprocess.Popen(
        ["sleep", "60"],
        cwd=workspace,
        start_new_session=True,
    )
    try:
        identity = read_identity(process.pid)
        assert identity is not None
        identity["start_time"] += 1
        pid_file.write_text(f"{process.pid}\n", encoding="utf-8")
        meta_file.write_text(json.dumps(identity), encoding="utf-8")

        with pytest.raises(CutoverError, match="does not match"):
            _capture_owned_service(
                repo=workspace,
                pid_file=pid_file,
                pid_meta_file=meta_file,
            )
        assert process.poll() is None
    finally:
        process.terminate()
        process.wait(timeout=2)
