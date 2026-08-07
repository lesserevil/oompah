#!/usr/bin/env python3
"""Tests for listener startup timeout configuration (OOMPAH-899).

These tests verify that:
  1. OOMPAH_LISTENER_STARTUP_TIMEOUT_SECONDS is configurable and bounded
  2. Slow startups that exceed the configured wait but later listen are handled safely
  3. Late listeners retain their lifecycle identity (not orphaned)
  4. Genuine startup failures still fail closed
  5. PID/metadata is only deleted after confirming process exit or identity change
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

from tests.process_lifecycle import start_owned_process, stop_owned_process
from scripts.listener_startup_timeout import (
    DEFAULT_SECONDS,
    ENVIRONMENT_KEY,
    MAXIMUM_SECONDS,
    MINIMUM_SECONDS,
    resolve_listener_startup_timeout,
)

ROOT = Path(__file__).resolve().parents[1]
MAKEFILE = ROOT / "Makefile"


# ---------------------------------------------------------------------------
# 1. Configuration validation tests
# ---------------------------------------------------------------------------

class TestListenerStartupTimeoutConfiguration:
    """Verify the configuration variable is properly defined and bounded."""

    def test_makefile_resolves_timeout_with_validating_helper(self):
        makefile_text = MAKEFILE.read_text(encoding="utf-8")
        assert "scripts/listener_startup_timeout.py --env-file .env" in makefile_text
        assert "_ENV_LISTENER_STARTUP_TIMEOUT" not in makefile_text

    def test_listener_startup_timeout_defined_in_env_example(self):
        """OOMPAH_LISTENER_STARTUP_TIMEOUT_SECONDS must be documented in .env.example."""
        env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
        assert "OOMPAH_LISTENER_STARTUP_TIMEOUT_SECONDS" in env_example
        assert "10" in env_example  # default value

    def test_listener_startup_timeout_has_bounded_range_doc(self):
        env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
        timeout_section = env_example[
            env_example.find("OOMPAH_LISTENER_STARTUP_TIMEOUT_SECONDS")
            - 200 :
        ]
        assert "5" in timeout_section or "range" in timeout_section.lower()
        assert "120" in timeout_section or "range" in timeout_section.lower()

    def test_default_and_inclusive_bounds(self, tmp_path, monkeypatch):
        monkeypatch.delenv(ENVIRONMENT_KEY, raising=False)
        assert resolve_listener_startup_timeout(tmp_path / "missing") == DEFAULT_SECONDS
        for value in (MINIMUM_SECONDS, MAXIMUM_SECONDS):
            monkeypatch.setenv(ENVIRONMENT_KEY, str(value))
            assert resolve_listener_startup_timeout(tmp_path / "missing") == value

    @pytest.mark.parametrize("value", ["", "4", "121", "0", "-1", "1.5", "bad"])
    def test_invalid_values_fail_closed(self, tmp_path, monkeypatch, value):
        monkeypatch.setenv(ENVIRONMENT_KEY, value)
        with pytest.raises(ValueError, match=ENVIRONMENT_KEY):
            resolve_listener_startup_timeout(tmp_path / "missing")

    def test_exported_environment_precedes_dotenv(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text(f"{ENVIRONMENT_KEY}=30\n", encoding="utf-8")
        monkeypatch.setenv(ENVIRONMENT_KEY, "20")
        assert resolve_listener_startup_timeout(env_file) == 20

    def test_dotenv_value_is_used_when_environment_is_absent(
        self,
        tmp_path,
        monkeypatch,
    ):
        env_file = tmp_path / ".env"
        env_file.write_text(f"{ENVIRONMENT_KEY}=30\n", encoding="utf-8")
        monkeypatch.delenv(ENVIRONMENT_KEY, raising=False)
        assert resolve_listener_startup_timeout(env_file) == 30


# ---------------------------------------------------------------------------
# 2. Late listener scenario: process exists + identity matches after timeout
# ---------------------------------------------------------------------------

class TestLateListenerScenario:
    """Verify that processes that bind the listener after timeout are handled safely."""

    @pytest.mark.timeout(60)
    @pytest.mark.skipif(
        os.name != "posix" or not Path("/proc").is_dir(),
        reason="requires POSIX procfs for identity verification",
    )
    def test_late_listener_identity_is_preserved(self, tmp_path):
        """A long-lived process retains its identity over time (late listener scenario)."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        meta_file = workspace / ".oompah.pid.meta"

        # Start a process that runs for a while (simulates slow startup)
        sentinel = start_owned_process(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            workspace=workspace,
            env=os.environ.copy(),
        )
        pid_val = sentinel.identity.pid
        try:
            # Capture and store the identity
            identity = {
                "pid": sentinel.identity.pid,
                "start_time": sentinel.identity.starttime,
                "process_group": sentinel.identity.process_group,
                "session": sentinel.identity.session,
                "cwd": sentinel.identity.cwd,
            }
            meta_file.write_text(json.dumps(identity), encoding="utf-8")

            # Verify identity immediately — should pass
            verify_result = subprocess.run(
                [
                    sys.executable,
                    "scripts/process_identity.py",
                    "verify",
                    str(pid_val),
                    str(workspace),
                    str(meta_file),
                ],
                cwd=ROOT,
                capture_output=True,
            )
            assert verify_result.returncode == 0, (
                "Process identity should match immediately after capture"
            )

            # Wait a bit (simulating the time that would pass while the Makefile
            # waits for a listener timeout)
            time.sleep(3)
            assert sentinel.process.poll() is None, "process should still be alive"

            # Verify identity again — should still match (process is unchanged)
            verify_result = subprocess.run(
                [
                    sys.executable,
                    "scripts/process_identity.py",
                    "verify",
                    str(pid_val),
                    str(workspace),
                    str(meta_file),
                ],
                cwd=ROOT,
                capture_output=True,
            )
            assert verify_result.returncode == 0, (
                "Process identity should still match after waiting (late listener scenario)"
            )

            # The metadata file should still exist (not deleted)
            assert meta_file.is_file(), "Metadata file must be preserved for late listeners"

        finally:
            survivors = stop_owned_process(sentinel, timeout_s=2)
            assert survivors == set(), "Sentinel should have been stopped cleanly"


# ---------------------------------------------------------------------------
# 3. Genuine startup failure: fail-closed behavior
# ---------------------------------------------------------------------------

class TestGenuineStartupFailure:
    """Verify that processes that don't start are handled fail-closed."""

    def test_nonexistent_process_fails_closed(self, tmp_path):
        """A PID that doesn't exist should cause startup to fail."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        pid_file = workspace / ".oompah.pid"
        meta_file = workspace / ".oompah.pid.meta"

        # Write a fake PID (shouldn't exist)
        fake_pid = 999999999
        pid_file.write_text(f"{fake_pid}\n", encoding="utf-8")
        identity = {
            "pid": fake_pid,
            "start_time": 0,
            "process_group": fake_pid,
            "session": fake_pid,
            "cwd": str(workspace),
        }
        meta_file.write_text(json.dumps(identity), encoding="utf-8")

        # Verify should fail
        verify_result = subprocess.run(
            [
                sys.executable,
                "scripts/process_identity.py",
                "verify",
                str(fake_pid),
                str(workspace),
                str(meta_file),
            ],
            cwd=ROOT,
            capture_output=True,
        )
        assert verify_result.returncode != 0, (
            "Verification should fail for non-existent PID"
        )

    @pytest.mark.skipif(
        os.name != "posix" or not Path("/proc").is_dir(),
        reason="requires POSIX procfs for identity verification",
    )
    def test_pid_reuse_fails_closed(self, tmp_path):
        """If a PID is reused by a different process, identity check should fail."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        meta_file = workspace / ".oompah.pid.meta"

        # Start a process and capture its identity
        sentinel = start_owned_process(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            workspace=workspace,
            env=os.environ.copy(),
        )
        original_pid = sentinel.identity.pid
        original_start_time = sentinel.identity.starttime
        stopped = False

        try:
            # Store the original identity
            original_identity = {
                "pid": original_pid,
                "start_time": original_start_time,
                "process_group": sentinel.identity.process_group,
                "session": sentinel.identity.session,
                "cwd": sentinel.identity.cwd,
            }
            meta_file.write_text(json.dumps(original_identity), encoding="utf-8")

            # Verify it passes
            verify_result = subprocess.run(
                [
                    sys.executable,
                    "scripts/process_identity.py",
                    "verify",
                    str(original_pid),
                    str(workspace),
                    str(meta_file),
                ],
                cwd=ROOT,
                capture_output=True,
            )
            assert verify_result.returncode == 0

            # Now stop the process and create a fake identity with different start_time
            # (simulating PID reuse)
            survivors = stop_owned_process(sentinel, timeout_s=2)
            assert survivors == set(), "Sentinel should have stopped"
            stopped = True

            fake_identity = original_identity.copy()
            fake_identity["start_time"] = original_start_time + 1000  # Different start time
            meta_file.write_text(json.dumps(fake_identity), encoding="utf-8")

            verify_result = subprocess.run(
                [
                    sys.executable,
                    "scripts/process_identity.py",
                    "verify",
                    str(original_pid),
                    str(workspace),
                    str(meta_file),
                ],
                cwd=ROOT,
                capture_output=True,
            )
            assert verify_result.returncode != 0

        finally:
            if not stopped:
                survivors = stop_owned_process(sentinel, timeout_s=2)
                assert survivors == set(), "Sentinel should have stopped"


# ---------------------------------------------------------------------------
# 4. Makefile start target behavior with timeout variable
# ---------------------------------------------------------------------------

class TestMakefileStartTimeout:
    """Verify that make start uses the configurable timeout."""

    def test_makefile_start_uses_resolved_listener_startup_timeout(self):
        makefile_text = MAKEFILE.read_text(encoding="utf-8")
        # Find the start recipe
        start_idx = makefile_text.find("\nstart: setup")
        assert start_idx != -1, "start target not found"
        stop_idx = makefile_text.find("\nstop:", start_idx)
        start_recipe = makefile_text[start_idx:stop_idx]

        assert "$$LISTENER_STARTUP_TIMEOUT" in start_recipe
        assert start_recipe.index("listener_startup_timeout.py") < start_recipe.index(
            "setsid $(PYTHON) -m oompah server"
        )

        # Must NOT have hard-coded `[ 10 ]` timeout check
        import re
        hard_coded_10 = re.search(r"\[\s*\$\$ELAPSED\s*-ge\s*10\s*\]", start_recipe)
        assert hard_coded_10 is None, (
            "start target must not have hard-coded 10-second timeout"
        )

    def test_makefile_start_re_verifies_identity_after_timeout(self):
        """The start target must re-verify process identity after timeout."""
        makefile_text = MAKEFILE.read_text(encoding="utf-8")
        start_idx = makefile_text.find("\nstart: setup")
        stop_idx = makefile_text.find("\nstop:", start_idx)
        start_recipe = makefile_text[start_idx:stop_idx]

        # Must call process_identity.py verify after timeout
        assert "process_identity.py verify" in start_recipe, (
            "start target must re-verify identity after listener timeout"
        )

    def test_verified_timeout_branch_never_deletes_lifecycle_evidence(self):
        makefile_text = MAKEFILE.read_text(encoding="utf-8")
        start_idx = makefile_text.find("\nstart: setup")
        stop_idx = makefile_text.find("\nstop:", start_idx)
        start_recipe = makefile_text[start_idx:stop_idx]

        verified = start_recipe.index("elif $(PYTHON) scripts/process_identity.py verify")
        mismatch = start_recipe.index("else", verified)
        verified_branch = start_recipe[verified:mismatch]
        assert "retaining $(PID_FILE) and $(PID_META_FILE)" in verified_branch
        assert "rm -f" not in verified_branch


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _port_is_open(port: int) -> bool:
    with socket.socket() as probe:
        probe.settimeout(0.1)
        return probe.connect_ex(("127.0.0.1", port)) == 0


@pytest.mark.timeout(30)
@pytest.mark.skipif(os.name != "posix", reason="requires POSIX lifecycle signals")
def test_make_start_retains_and_later_manages_exact_late_listener(tmp_path):
    """Exercise the real Make recipe across timeout, late bind, start, and stop."""

    fake_venv = tmp_path / "fake-venv"
    fake_bin = fake_venv / "bin"
    fake_bin.mkdir(parents=True)
    fake_python = fake_bin / "python"
    fake_python.write_text(
        "#!" + sys.executable + "\n" + textwrap.dedent(
            """
            import os, socket, sys, time

            arguments = sys.argv[1:]
            if arguments[:3] == ["-m", "oompah", "server"]:
                time.sleep(float(os.environ["OOMPAH_FAKE_LISTEN_DELAY"]))
                listener = socket.socket()
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                listener.bind(("127.0.0.1", int(os.environ["OOMPAH_TEST_SERVER_PORT"])))
                listener.listen(1)
                while True:
                    time.sleep(1)
            if arguments and (
                arguments[0].endswith("process_identity.py")
                or arguments[0].endswith("listener_startup_timeout.py")
            ):
                os.execv(sys.executable, [sys.executable, *arguments])
            if arguments and (
                arguments[0].endswith("sync_canonical_cli.py")
                or arguments[0].endswith("canonical_cli_cutover.py")
            ):
                raise SystemExit(0)
            raise SystemExit(f"unexpected fake-python arguments: {arguments!r}")
            """
        ),
        encoding="utf-8",
    )
    fake_python.chmod(0o755)
    fake_ss = fake_bin / "ss"
    fake_ss.write_text(
        "#!" + sys.executable + "\n" + textwrap.dedent(
            """
            import os, socket

            port = int(os.environ["OOMPAH_TEST_SERVER_PORT"])
            with socket.socket() as probe:
                probe.settimeout(0.1)
                if probe.connect_ex(("127.0.0.1", port)) == 0:
                    print("LISTEN")
            """
        ),
        encoding="utf-8",
    )
    fake_ss.chmod(0o755)

    port = _free_port()
    pid_file = tmp_path / "service.pid"
    meta_file = tmp_path / "service.pid.meta"
    log_file = tmp_path / "service.log"
    environment = {
        **os.environ,
        "OOMPAH_PYTEST_GATE": "1",
        "OOMPAH_PYTEST_RUN_ROOT": str(tmp_path / "gate"),
        "OOMPAH_TEST_PID_FILE": str(pid_file),
        "OOMPAH_TEST_PID_META_FILE": str(meta_file),
        "OOMPAH_TEST_SERVER_PORT": str(port),
        ENVIRONMENT_KEY: str(MINIMUM_SECONDS),
        "OOMPAH_FAKE_LISTEN_DELAY": str(MINIMUM_SECONDS + 1),
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
    }
    make_command = [
        "make",
        "--no-print-directory",
        "start",
        f"VENV={fake_venv}",
        f"LOG_FILE={log_file}",
    ]

    first = subprocess.run(
        make_command,
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert first.returncode != 0
    assert "retaining" in (first.stdout + first.stderr)
    assert pid_file.is_file()
    assert meta_file.is_file()
    owned_pid = int(pid_file.read_text())
    try:
        deadline = time.monotonic() + 5
        while not _port_is_open(port) and time.monotonic() < deadline:
            time.sleep(0.05)
        assert _port_is_open(port)

        second = subprocess.run(
            make_command,
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert second.returncode == 0, second
        assert f"already running (pid {owned_pid})" in second.stdout
    finally:
        stopped = subprocess.run(
            [
                "make",
                "--no-print-directory",
                "stop",
                f"VENV={fake_venv}",
                f"LOG_FILE={log_file}",
            ],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert stopped.returncode == 0, stopped
    assert not pid_file.exists()
    assert not meta_file.exists()
    assert not _port_is_open(port)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
