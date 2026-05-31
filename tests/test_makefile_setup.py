"""Tests for developer setup Makefile behavior."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAKEFILE = ROOT / "Makefile"


def _makefile_text() -> str:
    return MAKEFILE.read_text(encoding="utf-8")


def test_setup_depends_on_backlog_cli_check():
    """make setup must verify the Backlog.md CLI, not just Python deps."""
    text = _makefile_text()

    assert "setup: $(VENV)/.uv-setup ensure-backlog" in text
    assert ".PHONY: help setup ensure-backlog" in text


def test_ensure_backlog_installs_lesserevil_backlog_repo():
    """The setup helper installs the Lesserevil Backlog.md repo."""
    text = _makefile_text()

    assert (
        "BACKLOG_NPM_PACKAGE := https://github.com/lesserevil/backlog.md/archive/HEAD.tar.gz"
        in text
    )
    assert "BACKLOG_CLI := $(VENV)/bin/backlog" in text
    assert "ensure-backlog: $(BACKLOG_CLI)" in text
    assert "npm install --global --prefix" in text
    assert "--ignore-scripts" in text
    assert "$(BACKLOG_NPM_PACKAGE)" in text
    assert "$(BACKLOG_CLI): $(VENV)/.uv-setup Makefile" in text


def test_make_targets_export_venv_bin_on_path():
    """Runtime make targets should find the venv-local backlog binary."""
    text = _makefile_text()

    assert "export PATH := $(abspath $(VENV)/bin):$(PATH)" in text
