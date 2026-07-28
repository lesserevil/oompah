"""Per-worker filesystem isolation and process-global xdist grouping."""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Mapping

import pytest


_ISOLATED_ENV_KEYS = (
    "HOME",
    "TMPDIR",
    "TMP",
    "TEMP",
    "XDG_CACHE_HOME",
    "XDG_CONFIG_HOME",
    "XDG_DATA_HOME",
)
_PROCESS_GLOBAL_MODULES = frozenset(
    {
        "test_agent.py",
        "test_granian_e2e.py",
        "test_granian_parity.py",
        "test_makefile_restart_wait.py",
    }
)
_PROCESS_GLOBAL_GROUP = "oompah_process_global"


def build_worker_environment(
    worker_root: Path,
    current: Mapping[str, str],
) -> dict[str, str]:
    """Return isolated HOME, temp, and XDG paths for one xdist worker."""
    home = worker_root / "home"
    temp = worker_root / "tmp"
    cache = worker_root / "cache"
    config = worker_root / "config"
    data = worker_root / "data"
    for path in (home, temp, cache, config, data):
        path.mkdir(parents=True, exist_ok=True)

    result = dict(current)
    result.update(
        {
            "HOME": str(home),
            "TMPDIR": str(temp),
            "TMP": str(temp),
            "TEMP": str(temp),
            "XDG_CACHE_HOME": str(cache),
            "XDG_CONFIG_HOME": str(config),
            "XDG_DATA_HOME": str(data),
        }
    )
    return result


def _safe_worker_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip(".-")
    return cleaned or "worker"


def _default_run_root() -> Path:
    configured = os.environ.get("OOMPAH_TEMP_ROOT")
    private_root = (
        Path(configured).expanduser()
        if configured
        else Path.home() / ".oompah" / "tmp"
    )
    return private_root / "pytest"


def pytest_configure(config: pytest.Config) -> None:
    """Give each xdist worker its own home, temp, and cache directories."""
    worker_input = getattr(config, "workerinput", None)
    if worker_input is None:
        return

    worker_id = _safe_worker_id(str(worker_input.get("workerid", "worker")))
    configured_run_root = os.environ.get("OOMPAH_PYTEST_RUN_ROOT")
    run_root = (
        Path(configured_run_root).expanduser()
        if configured_run_root
        else _default_run_root()
    )
    run_root.mkdir(parents=True, exist_ok=True)
    worker_root = Path(
        tempfile.mkdtemp(prefix=f"{worker_id}.", dir=str(run_root))
    )

    saved_environment = {key: os.environ.get(key) for key in _ISOLATED_ENV_KEYS}
    isolated = build_worker_environment(worker_root, os.environ)
    for key in _ISOLATED_ENV_KEYS:
        os.environ[key] = isolated[key]

    # Tests create local repositories; keep their commits deterministic without
    # depending on the operator's global Git configuration.
    (Path(isolated["HOME"]) / ".gitconfig").write_text(
        "[user]\n"
        "\tname = Oompah Test Worker\n"
        "\temail = oompah-test@example.invalid\n",
        encoding="utf-8",
    )

    config._oompah_worker_root = worker_root  # type: ignore[attr-defined]
    config._oompah_saved_environment = saved_environment  # type: ignore[attr-defined]
    config._oompah_saved_tempdir = tempfile.tempdir  # type: ignore[attr-defined]
    tempfile.tempdir = isolated["TMPDIR"]


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Serialize modules that own live processes or process-global ports."""
    marker = pytest.mark.xdist_group(name=_PROCESS_GLOBAL_GROUP)
    for item in items:
        if Path(str(item.path)).name in _PROCESS_GLOBAL_MODULES:
            item.add_marker(marker)


def pytest_unconfigure(config: pytest.Config) -> None:
    """Restore the worker process environment and remove its private root."""
    worker_root: Path | None = getattr(config, "_oompah_worker_root", None)
    saved: dict[str, str | None] | None = getattr(
        config, "_oompah_saved_environment", None
    )
    if worker_root is None or saved is None:
        return

    tempfile.tempdir = getattr(config, "_oompah_saved_tempdir", None)
    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    shutil.rmtree(worker_root, ignore_errors=True)
