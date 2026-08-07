"""Per-worker filesystem isolation and process-global xdist grouping."""

from __future__ import annotations

import os
import re
import shutil
import socket
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
_RUNNER_ENV_KEYS = (
    "OOMPAH_PYTEST_RUN_ROOT",
    "OOMPAH_PYTEST_CANDIDATE_RUN_ROOT",
)
_WORKER_HOME_ROOT_ENV = "OOMPAH_PYTEST_WORKER_HOME_ROOT"
_TRUSTED_HOME_ROOT_ENV = "OOMPAH_PYTEST_TRUSTED_HOME_ROOT"
_GATE_ENV_KEYS = (
    "OOMPAH_PYTEST_GATE",
    _TRUSTED_HOME_ROOT_ENV,
    _WORKER_HOME_ROOT_ENV,
    "OOMPAH_TEST_SERVER_PORT",
    "OOMPAH_SERVER_PORT",
    "OOMPAH_TEST_PID_FILE",
    "OOMPAH_TEST_PID_META_FILE",
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


def _resolved_environment_path(value: str, working_directory: Path) -> Path:
    """Resolve an environment path using the subprocess's actual cwd."""

    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = working_directory / candidate
    return candidate.resolve(strict=False)


def _quality_gate_untrusted_roots(
    worker_root: Path,
    current: Mapping[str, str],
    *,
    working_directory: Path,
) -> tuple[Path, ...]:
    """Return every root writable by the gate's candidate pytest process."""

    candidates = [
        Path("/tmp"),
        Path("/var/tmp"),
        Path(tempfile.gettempdir()),
        working_directory,
        worker_root,
    ]
    for key in (
        "TMPDIR",
        "TMP",
        "TEMP",
        "OOMPAH_TEMP_ROOT",
        "OOMPAH_PYTEST_TEMP_ROOT",
        "OOMPAH_PYTEST_RUN_ROOT",
        "OOMPAH_PYTEST_CANDIDATE_RUN_ROOT",
    ):
        value = str(current.get(key, "")).strip()
        if value:
            candidates.append(Path(value).expanduser())

    roots: list[Path] = []
    for candidate in candidates:
        resolved = _resolved_environment_path(
            str(candidate),
            working_directory,
        )
        if resolved not in roots:
            roots.append(resolved)
    return tuple(roots)


def _gate_worker_home_parent(
    current: Mapping[str, str],
    *,
    working_directory: Path,
) -> Path:
    configured_home = str(current.get("HOME", "")).strip()
    if not configured_home:
        raise RuntimeError("quality-gate worker HOME is unavailable")
    raw_home = Path(configured_home).expanduser()
    if not raw_home.is_absolute():
        raise RuntimeError("quality-gate worker HOME must be absolute")

    resolved_home = raw_home.resolve(strict=False)
    configured_trusted_home = str(current.get(_TRUSTED_HOME_ROOT_ENV, "")).strip()
    if configured_trusted_home:
        trusted_home = _resolved_environment_path(
            configured_trusted_home,
            working_directory,
        )
        if resolved_home != trusted_home:
            raise RuntimeError(
                "quality-gate HOME does not match its launcher-provided capability"
            )
    parent = resolved_home / "pytest-workers"
    # The runner owns this exact directory.  Following a pre-existing symlink
    # would let candidate-controlled state redirect both guard creation and
    # later recursive cleanup outside the trusted HOME boundary.
    if parent.is_symlink() or parent.resolve(strict=False) != parent:
        raise RuntimeError("quality-gate worker HOME parent is a symlink escape")
    return parent


def _validate_gate_home_candidate(
    candidate: Path,
    *,
    untrusted_roots: tuple[Path, ...],
) -> Path:
    if candidate.is_symlink():
        raise RuntimeError("quality-gate worker HOME is a symlink escape")
    resolved = candidate.resolve(strict=False)
    if any(resolved == root or root in resolved.parents for root in untrusted_roots):
        raise RuntimeError(
            "quality-gate worker HOME overlaps task-writable temporary state"
        )
    return resolved


def _worker_home_path(
    worker_root: Path,
    current: Mapping[str, str],
    *,
    working_directory: Path | None = None,
) -> Path:
    """Choose a per-worker HOME without moving trusted gate state into /tmp.

    Parallel workers normally keep all of their state below ``worker_root``.
    An exact quality gate deliberately puts high-churn pytest state on a
    task-writable tmpfs, though, while its original HOME remains outside every
    root writable by a managed native CLI.  Nesting the worker HOME below that
    tmpfs would make the native validation guard reject its own trusted runtime
    before managed-Codex tests reach their intended assertions.
    """

    gate_enabled = str(current.get("OOMPAH_PYTEST_GATE", "")).strip().lower()
    if gate_enabled not in {"1", "true", "yes"}:
        return worker_root / "home"

    cwd = (working_directory or Path.cwd()).resolve(strict=False)
    parent = _gate_worker_home_parent(current, working_directory=cwd)
    configured_root = str(current.get(_WORKER_HOME_ROOT_ENV, "")).strip()
    if configured_root:
        session_root = _resolved_environment_path(configured_root, cwd)
        if session_root.is_symlink() or session_root.parent != parent:
            raise RuntimeError(
                "quality-gate worker HOME root escapes its runner-owned parent"
            )
    else:
        # Direct helper callers retain a bounded fallback.  A real xdist gate
        # always receives a unique controller/runner-owned session root.
        session_root = parent

    candidate = session_root / worker_root.name
    return _validate_gate_home_candidate(
        candidate,
        untrusted_roots=_quality_gate_untrusted_roots(
            worker_root,
            current,
            working_directory=cwd,
        ),
    )


def _prepare_gate_worker_home_root(
    current: Mapping[str, str],
    *,
    working_directory: Path,
) -> Path:
    """Create or validate one controller-owned external worker-HOME root."""

    cwd = working_directory.resolve(strict=False)
    parent = _gate_worker_home_parent(current, working_directory=cwd)
    configured_root = str(current.get(_WORKER_HOME_ROOT_ENV, "")).strip()
    if configured_root:
        root = _resolved_environment_path(configured_root, cwd)
        if root.is_symlink() or root.parent != parent:
            raise RuntimeError(
                "quality-gate worker HOME root escapes its runner-owned parent"
            )
    else:
        parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix="session.", dir=parent))

    try:
        validated = _validate_gate_home_candidate(
            root,
            untrusted_roots=_quality_gate_untrusted_roots(
                Path(str(current.get("OOMPAH_PYTEST_RUN_ROOT") or cwd)),
                current,
                working_directory=cwd,
            ),
        )
        validated.mkdir(mode=0o700, parents=True, exist_ok=True)
        validated.chmod(0o700)
        return validated
    except Exception:
        if root.parent == parent and root.name.startswith("session."):
            shutil.rmtree(root, ignore_errors=True)
        raise


def _remove_runner_owned_home(path: Path, *, expected_parent: Path) -> bool:
    """Remove one exact runner-owned directory without following symlinks."""

    if expected_parent.is_symlink() or path.is_symlink():
        return False
    parent = expected_parent.resolve(strict=False)
    resolved = path.resolve(strict=False)
    if path.parent.resolve(strict=False) != parent or resolved != path:
        return False
    # Delete through the checked lexical entry.  Using ``resolved`` here would
    # reintroduce a symlink-following cleanup primitive after validation.
    shutil.rmtree(path, ignore_errors=True)
    try:
        parent.rmdir()
    except OSError:
        pass
    return not path.exists()


def build_worker_environment(
    worker_root: Path,
    current: Mapping[str, str],
) -> dict[str, str]:
    """Return isolated HOME, temp, and XDG paths for one xdist worker."""
    home = _worker_home_path(worker_root, current)
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
    if result.get("OOMPAH_PYTEST_GATE") in {"1", "true", "yes"}:
        lifecycle = worker_root / "lifecycle"
        lifecycle.mkdir(parents=True, exist_ok=True)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            worker_port = str(sock.getsockname()[1])
        result["OOMPAH_TEST_SERVER_PORT"] = worker_port
        result["OOMPAH_SERVER_PORT"] = worker_port
        result["OOMPAH_TEST_PID_FILE"] = str(lifecycle / ".oompah.pid")
        result["OOMPAH_TEST_PID_META_FILE"] = str(
            lifecycle / ".oompah.pid.meta"
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
        if str(os.environ.get("OOMPAH_PYTEST_GATE", "")).strip().lower() in {
            "1",
            "true",
            "yes",
        }:
            saved_root = os.environ.get(_WORKER_HOME_ROOT_ENV)
            root = _prepare_gate_worker_home_root(
                os.environ,
                working_directory=Path.cwd(),
            )
            os.environ[_WORKER_HOME_ROOT_ENV] = str(root)
            config._oompah_gate_worker_home_root = root  # type: ignore[attr-defined]
            config._oompah_gate_worker_home_parent = root.parent  # type: ignore[attr-defined]
            config._oompah_saved_worker_home_root = saved_root  # type: ignore[attr-defined]
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

    saved_environment = {
        key: os.environ.get(key)
        for key in (*_ISOLATED_ENV_KEYS, *_GATE_ENV_KEYS)
    }
    isolated = build_worker_environment(worker_root, os.environ)
    for key in _ISOLATED_ENV_KEYS:
        os.environ[key] = isolated[key]
    for key in _GATE_ENV_KEYS:
        if key in isolated:
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
    config._oompah_worker_home = Path(isolated["HOME"])  # type: ignore[attr-defined]
    config._oompah_saved_environment = saved_environment  # type: ignore[attr-defined]
    config._oompah_isolated_environment = {  # type: ignore[attr-defined]
        key: isolated[key]
        for key in (*_ISOLATED_ENV_KEYS, *_GATE_ENV_KEYS)
        if key in isolated
    }
    config._oompah_runner_environment = {  # type: ignore[attr-defined]
        key: os.environ[key]
        for key in _RUNNER_ENV_KEYS
        if key in os.environ
    }
    config._oompah_saved_tempdir = tempfile.tempdir  # type: ignore[attr-defined]
    tempfile.tempdir = isolated["TMPDIR"]


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item: pytest.Item) -> None:
    """Restore the worker boundary before fixtures for every individual test."""
    isolated: dict[str, str] | None = getattr(
        item.config,
        "_oompah_isolated_environment",
        None,
    )
    if isolated is None:
        return
    for key, value in isolated.items():
        os.environ[key] = value
    runner_environment: dict[str, str] = getattr(
        item.config,
        "_oompah_runner_environment",
        {},
    )
    for key, value in runner_environment.items():
        os.environ[key] = value
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
    gate_root: Path | None = getattr(
        config,
        "_oompah_gate_worker_home_root",
        None,
    )
    gate_parent: Path | None = getattr(
        config,
        "_oompah_gate_worker_home_parent",
        None,
    )
    if gate_root is not None and gate_parent is not None:
        _remove_runner_owned_home(gate_root, expected_parent=gate_parent)
        saved_root: str | None = getattr(
            config,
            "_oompah_saved_worker_home_root",
            None,
        )
        if saved_root is None:
            os.environ.pop(_WORKER_HOME_ROOT_ENV, None)
        else:
            os.environ[_WORKER_HOME_ROOT_ENV] = saved_root

    worker_root: Path | None = getattr(config, "_oompah_worker_root", None)
    worker_home: Path | None = getattr(config, "_oompah_worker_home", None)
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
    if worker_home is not None and worker_home != worker_root / "home":
        saved_root = saved.get(_WORKER_HOME_ROOT_ENV)
        expected_parent = Path(saved_root).resolve(strict=False) if saved_root else None
        if expected_parent is not None and worker_home.parent == expected_parent:
            _remove_runner_owned_home(worker_home, expected_parent=expected_parent)
