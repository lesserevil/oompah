"""Regression tests for OOMPAH-303 private temporary-root handling."""

from __future__ import annotations

import os
import stat
import subprocess
import tempfile

import pytest

from oompah.config import ServiceConfig, load_workflow
from oompah.temp_root import TempRootError, configure_temp_root, resolve_temp_root


def test_configure_temp_root_exports_private_environment(tmp_path, monkeypatch):
    old_tempdir = tempfile.tempdir
    monkeypatch.delenv("TMPDIR", raising=False)
    monkeypatch.delenv("TMP", raising=False)
    monkeypatch.delenv("TEMP", raising=False)
    root = tmp_path / "oompah tmp"
    try:
        configured = configure_temp_root(str(root))
        assert configured == str(root.resolve())
        assert {os.environ[key] for key in ("TMPDIR", "TMP", "TEMP")} == {configured}
        assert stat.S_IMODE(root.stat().st_mode) == 0o700
        child = subprocess.run(
            ["sh", "-c", "test \"$TMPDIR\" = \"$TMP\" && test \"$TMP\" = \"$TEMP\""],
            check=False,
        )
        assert child.returncode == 0
    finally:
        tempfile.tempdir = old_tempdir


def test_temp_root_rejects_relative_path():
    with pytest.raises(TempRootError, match="absolute"):
        resolve_temp_root("relative/tmp")


def test_service_config_defaults_to_oompah_home(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    config = ServiceConfig()
    assert config.temp_root == str(tmp_path / ".oompah" / "tmp")
    assert config.workspace_root == str(tmp_path / ".oompah" / "workspaces")


def test_workflow_config_honors_temp_root_environment(monkeypatch, tmp_path):
    workflow = tmp_path / "WORKFLOW.md"
    workflow.write_text("agent: {}\n", encoding="utf-8")
    monkeypatch.setenv("OOMPAH_TEMP_ROOT", str(tmp_path / "private-tmp"))
    config = ServiceConfig.from_workflow(load_workflow(str(workflow)))
    assert config.temp_root == str((tmp_path / "private-tmp").resolve())
