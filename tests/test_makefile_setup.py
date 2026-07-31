"""Tests for developer setup Makefile behavior."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
MAKEFILE = ROOT / "Makefile"


def _makefile_text() -> str:
    return MAKEFILE.read_text(encoding="utf-8")


def test_setup_installs_server_dependencies_only():
    """make setup installs Python dependencies without tracker-specific setup."""
    text = _makefile_text()

    assert "setup: $(VENV)/.uv-setup" in text
    assert "$(VENV)/.uv-setup: pyproject.toml" in text
    assert "uv pip install -e '.[server]'" in text
    assert "start: setup" in text
    assert "ensure-" not in text


def test_test_targets_install_complete_dev_dependencies():
    """Fresh test worktrees must install every dependency exercised by tests."""
    text = _makefile_text()

    assert "test-setup: $(VENV)/.uv-test-setup" in text
    assert (
        "$(VENV)/.uv-test-setup: pyproject.toml $(VENV)/.uv-setup"
        in text
    )
    assert "uv pip install -e '.[dev]'" in text
    assert ".PHONY: help setup test-setup" in text
    assert "test: test-setup" in text
    assert "test-serial: test-setup" in text
    assert "@touch $@" in text


def test_quality_gate_uses_trusted_runtime_without_uv(tmp_path):
    """Gate mode validates the projected venv without trying to mutate it."""
    venv = tmp_path / "read-only-venv"
    python = venv / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    python.chmod(0o555)
    venv.chmod(0o555)
    try:
        environment = os.environ.copy()
        environment["PATH"] = "/usr/bin:/bin"
        result = subprocess.run(
            [
                "/usr/bin/make",
                "--no-print-directory",
                "OOMPAH_PYTEST_GATE=1",
                f"VENV={venv}",
                "test-setup",
            ],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
        )
    finally:
        venv.chmod(0o755)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "uv" not in result.stdout + result.stderr


def test_quality_gate_fails_closed_without_trusted_python(tmp_path):
    """A missing projected runtime fails before the candidate test command."""
    missing_venv = tmp_path / "missing-venv"
    result = subprocess.run(
        [
            "/usr/bin/make",
            "--no-print-directory",
            "OOMPAH_PYTEST_GATE=1",
            f"VENV={missing_venv}",
            "test-setup",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "trusted quality-gate Python is unavailable" in result.stderr
    assert not missing_venv.exists()


def test_quality_gate_fails_closed_with_incomplete_trusted_runtime(tmp_path):
    """A projected Python without the test modules is rejected explicitly."""
    venv = tmp_path / "incomplete-venv"
    python = venv / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    python.chmod(0o755)

    result = subprocess.run(
        [
            "/usr/bin/make",
            "--no-print-directory",
            "OOMPAH_PYTEST_GATE=1",
            f"VENV={venv}",
            "test-setup",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "trusted quality-gate test runtime is incomplete" in result.stderr


def test_non_gate_test_setup_still_installs_declared_dependencies():
    """Normal test setup retains the uv-managed dependency installation."""
    result = subprocess.run(
        [
            "/usr/bin/make",
            "--no-print-directory",
            "--always-make",
            "--dry-run",
            "OOMPAH_PYTEST_GATE=0",
            "test-setup",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "uv pip install -e '.[server]'" in result.stdout
    assert "uv pip install -e '.[dev]'" in result.stdout


def test_setup_does_not_install_external_tracker_cli():
    """The setup helper should not install external tracker CLIs."""
    text = _makefile_text()

    assert "npm install --global --prefix" not in text
    assert "--ignore-scripts" not in text


def test_make_targets_export_venv_bin_on_path():
    """Runtime make targets should find venv-local commands."""
    text = _makefile_text()

    assert "export PATH := $(abspath $(VENV)/bin):$(PATH)" in text


def test_make_start_does_not_force_default_port_flag():
    """make start must leave OOMPAH_SERVER_PORT/.env precedence to oompah."""
    text = _makefile_text()

    # PORT must be resolvable (checked more thoroughly by separate tests)
    assert "PORT ?= " in text
    # oompah is launched without a --port flag so OOMPAH_SERVER_PORT/.env take precedence
    assert "$(PYTHON) -m oompah --port $(PORT)" not in text


def test_make_start_uses_setsid_with_devnull_stdin():
    """make start must use setsid + /dev/null stdin for reliable detach.

    A bare '&' leaves the child in the parent's process group; the parent
    shell may send SIGHUP on exit (common in noninteractive automation
    shells), killing the child immediately after launch.  setsid creates a
    new session so the child is immune to the parent's terminal signals.
    Redirecting stdin from /dev/null prevents accidental reads from a
    potentially closed or absent tty.
    """
    text = _makefile_text()

    assert "setsid $(PYTHON) -m oompah server" in text
    assert "nohup $(PYTHON) -m oompah server" in text
    assert "</dev/null" in text


def test_port_reads_from_dotenv_file_as_fallback():
    """PORT must fall back to OOMPAH_SERVER_PORT from .env when the shell env var is absent.

    Without this, 'make status' and 'make graceful' report the wrong port
    when OOMPAH_SERVER_PORT is set in .env but not exported to the shell.
    """
    text = _makefile_text()

    # A shell-level grep extracts the value from .env
    assert "_ENV_PORT := $(shell grep" in text
    assert ".env" in text
    assert "OOMPAH_SERVER_PORT" in text
    # The PORT assignment must fall through env-var → .env → hard-coded default
    assert "$(_ENV_PORT)" in text
