"""Contracts for bounded parallel pytest execution."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.pytest_worker_isolation import (
    _PROCESS_GLOBAL_GROUP,
    _PROCESS_GLOBAL_MODULES,
    build_worker_environment,
    pytest_collection_modifyitems,
)


ROOT = Path(__file__).resolve().parents[1]
MAKEFILE = ROOT / "Makefile"
RUNNER = ROOT / "scripts" / "run-tests.sh"
ENV_EXAMPLE = ROOT / ".env.example"


def test_make_test_uses_bounded_configured_workers():
    text = MAKEFILE.read_text(encoding="utf-8")

    assert "_ENV_PYTEST_WORKERS := $(shell grep" in text
    assert "PYTEST_WORKERS ?=" in text
    assert "scripts/run-tests.sh parallel" in text
    assert 'OOMPAH_PYTEST_WORKERS="$(PYTEST_WORKERS)"' in text


def test_make_exposes_serial_diagnostic_target():
    text = MAKEFILE.read_text(encoding="utf-8")

    assert "test-serial: setup" in text
    assert "scripts/run-tests.sh serial" in text
    assert "test-serial" in text[text.index("help:") : text.index("setup:")]


def test_runner_keeps_pytest_and_bytecode_caches_in_disposable_tree():
    text = RUNNER.read_text(encoding="utf-8")

    assert 'export PYTHONPYCACHEPREFIX="${test_run_root}/pycache"' in text
    assert '"cache_dir=${test_run_root}/pytest-cache"' in text
    assert '--basetemp "${test_run_root}/basetemp"' in text


def test_dotenv_documents_conservative_default():
    text = ENV_EXAMPLE.read_text(encoding="utf-8")

    assert "OOMPAH_PYTEST_WORKERS=4" in text
    assert "Accepted range: 1-16" in text


def test_runner_expands_tilde_temp_root_under_home(tmp_path: Path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_uv = fake_bin / "uv"
    fake_uv.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    fake_uv.chmod(0o755)
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    env = os.environ.copy()
    env["HOME"] = str(fake_home)
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["OOMPAH_PYTEST_TEMP_ROOT"] = "~/.oompah/tmp"

    result = subprocess.run(
        [str(RUNNER), "serial", "tests/not-run-by-fake-uv.py"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    expected_parent = fake_home / ".oompah" / "tmp" / "pytest"
    assert result.returncode == 0
    assert f"under {expected_parent}/run." in result.stdout
    assert not (fake_home / "~").exists()


@pytest.mark.parametrize("workers", ["0", "17", "auto", "-1", ""])
def test_runner_rejects_unsafe_worker_counts(tmp_path: Path, workers: str):
    env = os.environ.copy()
    env["OOMPAH_PYTEST_WORKERS"] = workers
    env["OOMPAH_PYTEST_TEMP_ROOT"] = str(tmp_path)

    result = subprocess.run(
        [str(RUNNER), "parallel"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "integer from 1 through 16" in result.stderr


def test_worker_environment_isolates_home_temp_and_cache(tmp_path: Path):
    existing = {"HOME": "/operator", "CUSTOM": "preserved"}

    result = build_worker_environment(tmp_path / "gw3", existing)

    assert result["CUSTOM"] == "preserved"
    assert result["HOME"] == str(tmp_path / "gw3" / "home")
    assert result["TMPDIR"] == str(tmp_path / "gw3" / "tmp")
    assert result["TMP"] == result["TMPDIR"]
    assert result["TEMP"] == result["TMPDIR"]
    assert result["XDG_CACHE_HOME"] == str(tmp_path / "gw3" / "cache")
    assert result["XDG_CONFIG_HOME"] == str(tmp_path / "gw3" / "config")
    assert result["XDG_DATA_HOME"] == str(tmp_path / "gw3" / "data")
    for key in (
        "HOME",
        "TMPDIR",
        "XDG_CACHE_HOME",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
    ):
        assert Path(result[key]).is_dir()


def test_active_xdist_worker_uses_its_private_run_tree():
    """Exercise the installed plugin when this test runs through xdist."""
    worker_id = os.environ.get("PYTEST_XDIST_WORKER")
    if worker_id is None:
        return

    run_root = Path(os.environ["OOMPAH_PYTEST_RUN_ROOT"])
    for key in (
        "HOME",
        "TMPDIR",
        "TMP",
        "TEMP",
        "XDG_CACHE_HOME",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
    ):
        assert Path(os.environ[key]).is_relative_to(run_root)


def test_process_owning_modules_share_one_xdist_group():
    items = [
        SimpleNamespace(
            path=Path(module),
            markers=[],
            add_marker=lambda marker, module=module: items_by_module[module].append(
                marker
            ),
        )
        for module in sorted(_PROCESS_GLOBAL_MODULES)
    ]
    items_by_module = {str(item.path): item.markers for item in items}

    pytest_collection_modifyitems(items)  # type: ignore[arg-type]

    for item in items:
        assert len(item.markers) == 1
        assert item.markers[0].name == "xdist_group"
        assert item.markers[0].kwargs["name"] == _PROCESS_GLOBAL_GROUP
