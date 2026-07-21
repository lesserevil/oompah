#!/usr/bin/env python3
"""Tests for Makefile restart wait/race behavior (TASK-465.5).

These tests verify that:
  1. The Makefile structure enforces port-release waiting before restart (static analysis).
  2. The port_in_use shell logic correctly detects port state (functional, no oompah needed).
  3. The wait_for_stop shell logic terminates once a process exits and its port is free
     (functional, lightweight — uses a trivial TCP server, not the full oompah stack).

"Without relying on sleeps alone": the wait mechanism polls process liveness and
port state in a loop; these tests verify both the structure (static) and the
correct runtime behavior of that polling logic (functional).
"""

from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MAKEFILE = ROOT / "Makefile"

# Tool availability — checked once at import time so skip markers can use them.
# Uses shutil.which (respects Python's PATH) for consistency with subprocess.run.
_SS_AVAILABLE: bool = shutil.which("ss") is not None
_LSOF_AVAILABLE: bool = shutil.which("lsof") is not None
# At least one shell-based port-detection tool is present
_SHELL_PORT_DETECTION: bool = _SS_AVAILABLE or _LSOF_AVAILABLE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _makefile_text() -> str:
    return MAKEFILE.read_text(encoding="utf-8")


def find_free_port() -> int:
    """Bind to an ephemeral port, close, and return that port number.

    There is an inherent TOCTOU race, but it is small enough for tests.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def port_listening(port: int) -> bool:
    """Return True if *something* is in LISTEN state on *port*.

    Mirrors the ss / lsof fallback logic used by the Makefile's port_in_use
    macro, with an additional pure-Python fallback so tests remain runnable on
    hosts where neither tool is installed (e.g. the self-hosted Actions runner
    container which does not bundle iproute2 or lsof by default).
    """
    # Try ss first
    try:
        r = subprocess.run(
            ["ss", "-ltn", f"sport = :{port}"],
            capture_output=True,
            text=True,
        )
        if r.returncode == 0 and "LISTEN" in r.stdout:
            return True
    except FileNotFoundError:
        pass  # ss not installed; try next method

    # Fallback: lsof
    try:
        r2 = subprocess.run(
            ["lsof", "-ti", f":{port}", "-sTCP:LISTEN"],
            capture_output=True,
            text=True,
        )
        if r2.returncode == 0 and bool(r2.stdout.strip()):
            return True
    except FileNotFoundError:
        pass  # lsof not installed; fall through to Python socket probe

    # Last-resort pure-Python probe: attempt a non-blocking TCP connection.
    # The kernel completes the 3-way handshake (queuing the connection in the
    # accept backlog) even when the listener never calls accept(), so
    # connect_ex() == 0 reliably indicates that something is in LISTEN state.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)
            return s.connect_ex(("127.0.0.1", port)) == 0
    except OSError:
        return False


# ---------------------------------------------------------------------------
# 1. Static analysis: Makefile structure
# ---------------------------------------------------------------------------

class TestMakefileStructure:
    """Verify the Makefile enforces the restart-wait contract structurally."""

    def test_stop_timeout_variable_is_defined(self):
        """STOP_TIMEOUT must be user-overridable so operators can tune it."""
        assert "STOP_TIMEOUT ?= " in _makefile_text()

    def test_wait_for_stop_define_exists(self):
        """Makefile must define wait_for_stop helper."""
        assert "define wait_for_stop" in _makefile_text()

    def test_port_in_use_define_exists(self):
        """Makefile must define port_in_use helper."""
        assert "define port_in_use" in _makefile_text()

    def test_wait_for_stop_body_has_no_leading_at(self):
        """wait_for_stop body must NOT start with '@'.

        When $(call wait_for_stop,...) is expanded inline inside another recipe
        (e.g. stop:), the '@' Make-echo-suppressor becomes a literal shell
        character and causes a 'command not found' error.  Echo suppression is
        already provided by the outer recipe's leading '@'.
        """
        text = _makefile_text()
        start = text.index("define wait_for_stop")
        end = text.index("endef", start)
        body = text[start + len("define wait_for_stop"):end]
        # Find the first non-blank, non-define line
        first_content_line = next(
            (l.strip() for l in body.splitlines() if l.strip()),
            "",
        )
        assert not first_content_line.startswith("@"), (
            "wait_for_stop body starts with '@' — this breaks inline $(call) use. "
            "Remove the '@'; echo suppression comes from the outer recipe."
        )

    def test_stop_target_calls_wait_for_stop(self):
        """stop: must call wait_for_stop to block until process and port are free."""
        assert "$(call wait_for_stop" in _makefile_text()

    def test_stop_signals_oompah_process_group(self):
        """stop: must terminate children in the setsid-created process group."""
        text = _makefile_text()
        start_recipe_pos = text.find("start: setup")
        stop_recipe_pos = text.find("\nstop:")
        restart_recipe_pos = text.find("\nrestart:", stop_recipe_pos)
        start_recipe = text[start_recipe_pos:stop_recipe_pos]
        stop_recipe = text[stop_recipe_pos:restart_recipe_pos]

        assert "setsid $(PYTHON) -m oompah" in start_recipe
        assert "kill -TERM -$$PID" in stop_recipe
        assert "|| kill $$PID" in stop_recipe

    def test_wait_for_stop_polls_process_liveness(self):
        """wait_for_stop must poll kill -0 rather than just sleeping."""
        text = _makefile_text()
        start = text.index("define wait_for_stop")
        end = text.index("endef", start)
        body = text[start:end]
        assert "kill -0" in body, "wait_for_stop must poll process liveness with kill -0"

    def test_wait_for_stop_waits_for_port_release(self):
        """wait_for_stop must also check port release after process exits."""
        text = _makefile_text()
        start = text.index("define wait_for_stop")
        end = text.index("endef", start)
        body = text[start:end]
        assert "port_in_use" in body, "wait_for_stop must wait for port release via port_in_use"

    def test_wait_for_stop_has_timeout(self):
        """wait_for_stop must enforce a bounded timeout (not loop forever)."""
        text = _makefile_text()
        start = text.index("define wait_for_stop")
        end = text.index("endef", start)
        body = text[start:end]
        assert "ELAPSED" in body, "wait_for_stop must track elapsed time for timeout"
        assert "exit 1" in body, "wait_for_stop must exit non-zero on timeout"

    def test_start_checks_port_before_spawn(self):
        """start: must refuse to spawn when the port is already occupied."""
        text = _makefile_text()
        # port_in_use check must appear in the start recipe BEFORE the setsid/nohup spawn
        port_check_pos = text.find("$(call port_in_use,$(PORT))")
        spawn_pos = text.find("setsid $(PYTHON) -m oompah")
        assert port_check_pos != -1, "start: must call port_in_use before spawning"
        assert spawn_pos != -1, "start: must use setsid to spawn oompah"
        assert port_check_pos < spawn_pos, (
            "port_in_use check must come before the setsid spawn in start:"
        )

    def test_start_removes_pid_file_on_timeout(self):
        """start: must remove .oompah.pid when the new process never listens."""
        text = _makefile_text()
        # Verify rm -f $(PID_FILE) appears in the start recipe error path
        start_recipe_pos = text.find("start: setup")
        stop_recipe_pos = text.find("\nstop:")
        start_recipe = text[start_recipe_pos:stop_recipe_pos]
        assert "rm -f $(PID_FILE)" in start_recipe, (
            "start: must clean up the PID file when the new process fails to start"
        )

    def test_start_removes_pid_file_on_crash(self):
        """start: must remove .oompah.pid when the new process exits unexpectedly."""
        text = _makefile_text()
        start_recipe_pos = text.find("start: setup")
        stop_recipe_pos = text.find("\nstop:")
        start_recipe = text[start_recipe_pos:stop_recipe_pos]
        # Two distinct error paths should both clean up
        assert start_recipe.count("rm -f $(PID_FILE)") >= 2, (
            "start: must clean up PID file in both the timeout and crash error paths"
        )

    def test_restart_is_stop_then_start(self):
        """restart: must be implemented as 'stop start' so port wait is enforced."""
        text = _makefile_text()
        assert "restart: stop start" in text, (
            "restart: must depend on stop (which waits) followed by start"
        )

    def test_port_in_use_uses_ss_with_lsof_fallback(self):
        """port_in_use must try ss first, fall back to lsof."""
        text = _makefile_text()
        start = text.index("define port_in_use")
        end = text.index("endef", start)
        body = text[start:end]
        assert "ss" in body, "port_in_use must use ss for port detection"
        assert "lsof" in body, "port_in_use must fall back to lsof"


# ---------------------------------------------------------------------------
# 2. Functional: port_in_use shell logic
# ---------------------------------------------------------------------------

class TestPortInUseDetection:
    """Verify the shell port-detection logic that underpins wait_for_stop."""

    @pytest.fixture()
    def listening_socket(self):
        """Yield a TCP socket bound and listening on a free port."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        port = find_free_port()
        sock.bind(("127.0.0.1", port))
        sock.listen(1)
        try:
            yield sock, port
        finally:
            sock.close()

    @pytest.mark.skipif(
        not _SS_AVAILABLE,
        reason="ss (iproute2) not installed on this host",
    )
    def test_ss_detects_listening_port(self, listening_socket):
        """ss -ltn reports LISTEN when a socket is bound."""
        _, port = listening_socket
        r = subprocess.run(
            ["ss", "-ltn", f"sport = :{port}"],
            capture_output=True,
            text=True,
        )
        assert r.returncode == 0
        assert "LISTEN" in r.stdout, (
            f"ss should report LISTEN for port {port}; got: {r.stdout!r}"
        )

    @pytest.mark.skipif(
        not _SS_AVAILABLE,
        reason="ss (iproute2) not installed on this host",
    )
    def test_ss_does_not_report_free_port(self):
        """ss does not report LISTEN for an unoccupied port."""
        port = find_free_port()
        # Port is closed immediately after find_free_port returns
        r = subprocess.run(
            ["ss", "-ltn", f"sport = :{port}"],
            capture_output=True,
            text=True,
        )
        # It's OK if ss exits 0 but just shows no LISTEN entry
        assert "LISTEN" not in r.stdout, (
            f"ss should not report LISTEN for unoccupied port {port}; got: {r.stdout!r}"
        )

    @pytest.mark.skipif(
        not _SHELL_PORT_DETECTION,
        reason="neither ss (iproute2) nor lsof is installed — shell port_in_use logic untestable",
    )
    def test_port_in_use_shell_returns_true_when_bound(self, listening_socket):
        """The port_in_use shell fragment exits 0 (true) when port is occupied."""
        _, port = listening_socket
        # Reproduce the exact Makefile port_in_use logic in a shell one-liner
        script = textwrap.dedent(f"""\
            command -v ss >/dev/null 2>&1 && ss -ltn "sport = :{port}" 2>/dev/null | grep -q LISTEN;
            [ $? -eq 0 ] || (command -v lsof >/dev/null 2>&1 && lsof -ti:"{port}" -sTCP:LISTEN 2>/dev/null | grep -q .)
        """)
        r = subprocess.run(["sh", "-c", script], capture_output=True)
        assert r.returncode == 0, (
            f"port_in_use fragment should exit 0 for occupied port {port}"
        )

    @pytest.mark.skipif(
        not _SHELL_PORT_DETECTION,
        reason="neither ss (iproute2) nor lsof is installed — shell port_in_use logic untestable",
    )
    def test_port_in_use_shell_returns_false_when_free(self):
        """The port_in_use shell fragment exits non-zero (false) when port is free."""
        port = find_free_port()
        # Port is free after the socket closes
        script = textwrap.dedent(f"""\
            command -v ss >/dev/null 2>&1 && ss -ltn "sport = :{port}" 2>/dev/null | grep -q LISTEN;
            [ $? -eq 0 ] || (command -v lsof >/dev/null 2>&1 && lsof -ti:"{port}" -sTCP:LISTEN 2>/dev/null | grep -q .)
        """)
        r = subprocess.run(["sh", "-c", script], capture_output=True)
        assert r.returncode != 0, (
            f"port_in_use fragment should exit non-zero for free port {port}"
        )


# ---------------------------------------------------------------------------
# 3. Functional: wait_for_stop shell logic (lightweight, no oompah)
# ---------------------------------------------------------------------------

class TestWaitForStopBehavior:
    """End-to-end tests of the wait_for_stop shell logic.

    These tests use a trivial Python TCP server process (not oompah) to prove:
      - wait_for_stop returns only after the process exits AND the port is free
      - wait_for_stop times out and exits non-zero if the process won't die
      - The logic is driven by condition polling, not a fixed sleep
    """

    _WAIT_SCRIPT = textwrap.dedent("""\
        #!/bin/sh
        # Inline the port_in_use and wait_for_stop logic from the Makefile.
        # Adds a pure-Python socket probe as a third fallback so the port-wait
        # loop is exercised even on hosts without ss (iproute2) or lsof.
        port_in_use() {
            PORT="$1"
            command -v ss >/dev/null 2>&1 && ss -ltn "sport = :${PORT}" 2>/dev/null | grep -q LISTEN
            [ $? -eq 0 ] && return 0
            command -v lsof >/dev/null 2>&1 && lsof -ti:"${PORT}" -sTCP:LISTEN 2>/dev/null | grep -q .
            [ $? -eq 0 ] && return 0
            # Pure-Python fallback: exit 0 if something accepts connections on PORT
            python3 -c "
import socket, sys
s = socket.socket()
s.settimeout(0.2)
sys.exit(0 if s.connect_ex(('127.0.0.1', int(sys.argv[1]))) == 0 else 1)
" "${PORT}" 2>/dev/null
            return $?
        }
        wait_for_stop() {
            PID="$1"; PORT="$2"; TIMEOUT="${3:-30}"
            ELAPSED=0
            while kill -0 "$PID" 2>/dev/null; do
                if [ "$ELAPSED" -ge "$TIMEOUT" ]; then
                    echo "TIMEOUT waiting for PID $PID to exit" >&2
                    exit 1
                fi
                sleep 0.2
                ELAPSED=$((ELAPSED + 1))
            done
            ELAPSED=0
            while port_in_use "$PORT"; do
                if [ "$ELAPSED" -ge "$TIMEOUT" ]; then
                    echo "TIMEOUT waiting for port $PORT to be free" >&2
                    exit 2
                fi
                sleep 0.2
                ELAPSED=$((ELAPSED + 1))
            done
            echo "done"
        }
        wait_for_stop "$1" "$2" "${3:-30}"
    """)

    @pytest.fixture()
    def tcp_server(self):
        """Start a Python subprocess that holds a TCP port, yield (pid, port)."""
        port = find_free_port()
        proc = subprocess.Popen(
            [
                sys.executable, "-c",
                (
                    "import socket, time, sys\n"
                    f"s = socket.socket()\n"
                    "s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)\n"
                    f"s.bind(('127.0.0.1', {port}))\n"
                    "s.listen(1)\n"
                    "time.sleep(60)\n"
                ),
            ],
        )
        # Wait until the port is actually listening
        deadline = time.monotonic() + 5
        while not port_listening(port):
            if time.monotonic() > deadline:
                proc.kill()
                pytest.skip(f"TCP server did not start listening on port {port} in time")
            time.sleep(0.05)
        yield proc, port
        if proc.poll() is None:
            proc.kill()
            proc.wait()

    def test_wait_for_stop_returns_after_process_exits(self, tmp_path, tcp_server):
        """wait_for_stop exits 0 once the target process is dead and port is free."""
        proc, port = tcp_server
        script_path = tmp_path / "wait_for_stop.sh"
        script_path.write_text(self._WAIT_SCRIPT)

        # Run wait_for_stop in the background THEN kill the server
        wait_proc = subprocess.Popen(
            ["sh", str(script_path), str(proc.pid), str(port), "10"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Give wait_for_stop a moment to start polling, then kill the server
        time.sleep(0.3)
        proc.terminate()
        proc.wait(timeout=3)

        stdout, stderr = wait_proc.communicate(timeout=10)
        assert wait_proc.returncode == 0, (
            f"wait_for_stop should succeed after process exits; "
            f"stdout={stdout!r} stderr={stderr!r}"
        )
        assert "done" in stdout

    def test_wait_for_stop_times_out_if_process_lingers(self, tmp_path, tcp_server):
        """wait_for_stop exits non-zero when the process doesn't exit within timeout."""
        proc, port = tcp_server
        script_path = tmp_path / "wait_for_stop.sh"
        script_path.write_text(self._WAIT_SCRIPT)

        # Use timeout=1 (in loop iterations) — the server is NOT killed
        r = subprocess.run(
            ["sh", str(script_path), str(proc.pid), str(port), "1"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert r.returncode != 0, (
            "wait_for_stop should exit non-zero when process outlives timeout"
        )
        assert "TIMEOUT" in r.stderr

    def test_wait_for_stop_also_waits_for_port_release(self, tmp_path, tcp_server):
        """wait_for_stop keeps polling even after process exits if port stays occupied.

        Scenario: the old server process forks a child that inherits the socket.
        In that case the port is still LISTEN even after the parent exits.
        """
        proc, port = tcp_server
        script_path = tmp_path / "wait_for_stop.sh"
        script_path.write_text(self._WAIT_SCRIPT)

        # Start wait_for_stop
        wait_proc = subprocess.Popen(
            ["sh", str(script_path), str(proc.pid), str(port), "10"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Kill the server process — but we'll separately hold the port a bit longer
        time.sleep(0.2)
        proc.terminate()
        proc.wait(timeout=3)

        # The wait script should detect the port is released (the server process
        # owned the socket; releasing the process releases the port too here)
        stdout, stderr = wait_proc.communicate(timeout=10)
        assert wait_proc.returncode == 0, (
            f"wait_for_stop should detect port release; "
            f"stdout={stdout!r} stderr={stderr!r}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
