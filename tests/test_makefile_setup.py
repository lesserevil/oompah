"""Tests for developer setup Makefile behavior."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAKEFILE = ROOT / "Makefile"


def _makefile_text() -> str:
    return MAKEFILE.read_text(encoding="utf-8")


def test_setup_installs_server_dependencies_only():
    """make setup installs Python dependencies without tracker-specific setup."""
    text = _makefile_text()

    assert "setup: $(VENV)/.uv-setup" in text
    assert "ensure-" not in text


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
