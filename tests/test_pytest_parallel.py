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
    _WORKER_HOME_ROOT_ENV,
    _worker_home_path,
    build_worker_environment,
    pytest_collection_modifyitems,
    pytest_runtest_setup,
    pytest_unconfigure,
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

    assert "test-serial: test-setup" in text
    assert "scripts/run-tests.sh serial" in text
    assert "test-serial" in text[text.index("help:") : text.index("setup:")]


def test_runner_keeps_pytest_and_bytecode_caches_in_disposable_tree():
    text = RUNNER.read_text(encoding="utf-8")

    assert 'export PYTHONPYCACHEPREFIX="${test_run_root}/pycache"' in text
    assert '"cache_dir=${test_run_root}/pytest-cache"' in text
    assert '--basetemp "${test_run_root}/basetemp"' in text
    assert '"${test_python}" -m pytest "${pytest_args[@]}"' in text
    assert "uv run pytest" not in text


def test_runner_bounds_worker_restart_to_prevent_scheduler_replacement_crash():
    """The parallel gate must not restart a lost worker (OOMPAH-675).

    pytest-xdist's LoadScopeScheduling / LoadGroupScheduling replaces a crashed
    worker via ``_clone_node`` and later processes messages from the newly
    added replacement.  If any of those late messages arrive for a controller
    whose scheduler bookkeeping has already been popped, the run aborts with a
    KeyError inside the scheduler and the original crash identity is lost.
    With ``timeout_method = "signal"`` an intentional timeout no longer tears
    down its worker, so ``--max-worker-restart=0`` fails fast only on a genuine
    crash while still surfacing the responsible test in xdist's ``crashitem``
    handling.
    """
    text = RUNNER.read_text(encoding="utf-8")

    assert "--max-worker-restart=0" in text
    assert "--dist loadgroup" in text


def test_dotenv_documents_conservative_default():
    text = ENV_EXAMPLE.read_text(encoding="utf-8")

    assert "OOMPAH_PYTEST_WORKERS=4" in text
    assert "Accepted range: 1-16" in text


def test_runner_expands_tilde_temp_root_under_home(tmp_path: Path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_python = fake_bin / "python"
    fake_python.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    fake_python.chmod(0o755)
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    env = os.environ.copy()
    env.pop(_WORKER_HOME_ROOT_ENV, None)
    env.pop("OOMPAH_PYTEST_TRUSTED_HOME_ROOT", None)
    env["HOME"] = str(fake_home)
    env["OOMPAH_TEST_PYTHON"] = str(fake_python)
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


def test_quality_gate_worker_home_stays_outside_task_writable_tmp():
    """An xdist worker must preserve the gate's trusted HOME boundary."""

    worker_root = Path("/oompah-gate/tmp/pytest/run.ABC/popen-gw3")
    current = {
        "OOMPAH_PYTEST_GATE": "1",
        "HOME": "/oompah-gate-trusted",
        "OOMPAH_PYTEST_TRUSTED_HOME_ROOT": "/oompah-gate-trusted",
        "OOMPAH_PYTEST_CANDIDATE_RUN_ROOT": "/oompah-gate",
        "TMPDIR": "/oompah-gate/tmp",
        "TMP": "/oompah-gate/tmp",
        "TEMP": "/oompah-gate/tmp",
        "OOMPAH_TEMP_ROOT": "/oompah-gate/tmp",
        "OOMPAH_PYTEST_TEMP_ROOT": "/oompah-gate/tmp",
        "OOMPAH_PYTEST_RUN_ROOT": "/oompah-gate/tmp/pytest/run.ABC",
        _WORKER_HOME_ROOT_ENV: "/oompah-gate-trusted/pytest-workers/session",
    }

    home = _worker_home_path(worker_root, current)

    assert home == Path("/oompah-gate-trusted/pytest-workers/session/popen-gw3")
    runtime_parent = home / ".oompah" / "native-validation-guards"
    for untrusted in (
        Path("/tmp"),
        Path("/var/tmp"),
        Path(current["OOMPAH_PYTEST_CANDIDATE_RUN_ROOT"]),
        Path(current["TMPDIR"]),
        worker_root,
    ):
        assert runtime_parent != untrusted
        assert untrusted not in runtime_parent.parents


def test_quality_gate_rejects_home_outside_server_owned_capability():
    current = {
        "OOMPAH_PYTEST_GATE": "1",
        "HOME": "/oompah-gate/home",
        "OOMPAH_PYTEST_TRUSTED_HOME_ROOT": "/oompah-gate-trusted",
        "OOMPAH_PYTEST_CANDIDATE_RUN_ROOT": "/oompah-gate",
    }

    with pytest.raises(RuntimeError, match="launcher-provided capability"):
        _worker_home_path(
            Path("/oompah-gate/tmp/pytest/run.ABC/popen-gw2"),
            current,
        )


@pytest.mark.parametrize(
    "configured_home",
    [
        "/tmp/oompah-gate/home",
        "/var/tmp/oompah-gate/home",
        "/tmp/oompah-gate/pytest/run.ABC/home",
    ],
)
def test_quality_gate_worker_home_fails_closed_inside_untrusted_tmp(
    configured_home: str,
):
    current = {
        "OOMPAH_PYTEST_GATE": "1",
        "HOME": configured_home,
        "TMPDIR": "/tmp/oompah-gate",
        "OOMPAH_PYTEST_RUN_ROOT": "/tmp/oompah-gate/pytest/run.ABC",
    }

    with pytest.raises(
        RuntimeError,
        match="overlaps task-writable temporary state",
    ):
        _worker_home_path(
            Path("/tmp/oompah-gate/pytest/run.ABC/popen-gw2"),
            current,
        )


def test_quality_gate_validates_candidate_home_not_only_base_home():
    current = {
        "OOMPAH_PYTEST_GATE": "1",
        "HOME": "/home/oompah",
        "OOMPAH_TEMP_ROOT": "/home/oompah/pytest-workers",
        "OOMPAH_PYTEST_RUN_ROOT": "/tmp/oompah-gate/pytest/run.ABC",
        _WORKER_HOME_ROOT_ENV: "/home/oompah/pytest-workers/run.ABC",
    }

    with pytest.raises(
        RuntimeError,
        match="overlaps task-writable temporary state",
    ):
        _worker_home_path(
            Path("/tmp/oompah-gate/pytest/run.ABC/popen-gw2"),
            current,
        )


@pytest.mark.parametrize(
    "root_name",
    [
        "TMPDIR",
        "TMP",
        "TEMP",
        "OOMPAH_TEMP_ROOT",
        "OOMPAH_PYTEST_TEMP_ROOT",
        "OOMPAH_PYTEST_RUN_ROOT",
    ],
)
def test_quality_gate_resolves_relative_untrusted_root_against_worker_cwd(
    root_name: str,
):
    current = {
        "OOMPAH_PYTEST_GATE": "1",
        "HOME": "/home/oompah",
        root_name: "../pytest-workers",
        _WORKER_HOME_ROOT_ENV: "/home/oompah/pytest-workers/run.ABC",
    }

    with pytest.raises(
        RuntimeError,
        match="overlaps task-writable temporary state",
    ):
        _worker_home_path(
            Path("/srv/project/pytest/run.ABC/popen-gw2"),
            current,
            working_directory=Path("/home/oompah/project"),
        )


def test_quality_gate_rejects_symlinked_worker_home_parent(tmp_path: Path):
    home = tmp_path / "home"
    escape = tmp_path / "escape"
    home.mkdir()
    escape.mkdir()
    (home / "pytest-workers").symlink_to(escape, target_is_directory=True)

    with pytest.raises(RuntimeError, match="symlink escape"):
        _worker_home_path(
            tmp_path / "run" / "popen-gw2",
            {
                "OOMPAH_PYTEST_GATE": "1",
                "HOME": str(home),
                "OOMPAH_PYTEST_RUN_ROOT": str(tmp_path / "run"),
            },
            working_directory=tmp_path,
        )


def test_worker_unconfigure_removes_external_gate_home(
    monkeypatch,
    tmp_path: Path,
):
    trusted_home = (tmp_path / "trusted-home").resolve()
    session_root = trusted_home / "pytest-workers" / "run.ABC"
    worker_home = session_root / "popen-gw1"
    worker_root = tmp_path / "pytest" / "run.ABC" / "popen-gw1"
    worker_home.mkdir(parents=True)
    worker_root.mkdir(parents=True)
    (worker_home / "guard-state").write_text("retired", encoding="utf-8")
    (worker_root / "test-state").write_text("retired", encoding="utf-8")
    config = SimpleNamespace(
        _oompah_worker_root=worker_root,
        _oompah_worker_home=worker_home,
        _oompah_saved_environment={
            "HOME": str(trusted_home),
            _WORKER_HOME_ROOT_ENV: str(session_root),
        },
        _oompah_saved_tempdir=None,
    )
    monkeypatch.setenv("HOME", str(worker_home))

    pytest_unconfigure(config)  # type: ignore[arg-type]

    assert not worker_home.exists()
    assert not worker_root.exists()
    assert not session_root.exists()
    assert os.environ["HOME"] == str(trusted_home)


@pytest.mark.parametrize("partial_name", ["crashed-gw0", "config-failed-gw1"])
def test_controller_unconfigure_removes_abandoned_worker_homes(
    monkeypatch,
    tmp_path: Path,
    partial_name: str,
):
    parent = tmp_path / "trusted-home" / "pytest-workers"
    session_root = parent / "run.ABC"
    abandoned_home = session_root / partial_name
    abandoned_home.mkdir(parents=True)
    (abandoned_home / "partial-state").write_text("leftover", encoding="utf-8")
    config = SimpleNamespace(
        _oompah_gate_worker_home_root=session_root,
        _oompah_gate_worker_home_parent=parent,
        _oompah_saved_worker_home_root=None,
    )
    monkeypatch.setenv(_WORKER_HOME_ROOT_ENV, str(session_root))

    pytest_unconfigure(config)  # type: ignore[arg-type]

    assert not session_root.exists()
    assert not parent.exists()
    assert _WORKER_HOME_ROOT_ENV not in os.environ


def _run_runner_with_fake_pytest(
    tmp_path: Path,
    *,
    pytest_action: str,
) -> tuple[subprocess.CompletedProcess[str], Path]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_python = fake_bin / "python"
    fake_python.write_text(
        "#!/usr/bin/env bash\n"
        "set -eu\n"
        "if [[ \"${1-}\" == \"-c\" ]]; then\n"
        "  echo 32123\n"
        "  exit 0\n"
        "fi\n"
        'mkdir -p "${OOMPAH_PYTEST_WORKER_HOME_ROOT}/popen-gw0"\n'
        'touch "${OOMPAH_PYTEST_WORKER_HOME_ROOT}/popen-gw0/partial"\n'
        f"{pytest_action}\n",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    env = os.environ.copy()
    env.pop(_WORKER_HOME_ROOT_ENV, None)
    env.pop("OOMPAH_PYTEST_TRUSTED_HOME_ROOT", None)
    env.update(
        {
            "HOME": str(fake_home),
            "OOMPAH_TEST_PYTHON": str(fake_python),
            "OOMPAH_PYTEST_TEMP_ROOT": str(tmp_path / "gate-temp"),
        }
    )

    result = subprocess.run(
        [str(RUNNER), "parallel", "tests/not-run-by-fake-python.py"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return result, fake_home / "pytest-workers"


def test_runner_removes_worker_home_after_xdist_process_is_killed(tmp_path: Path):
    result, worker_parent = _run_runner_with_fake_pytest(
        tmp_path,
        pytest_action='kill -KILL "$$"',
    )

    assert result.returncode == 137
    assert not worker_parent.exists()


def test_runner_removes_worker_home_after_configuration_failure(tmp_path: Path):
    result, worker_parent = _run_runner_with_fake_pytest(
        tmp_path,
        pytest_action="exit 4",
    )

    assert result.returncode == 4
    assert not worker_parent.exists()


def test_runner_rejects_symlinked_worker_home_parent(tmp_path: Path):
    fake_home = tmp_path / "home"
    escape = tmp_path / "escape"
    fake_home.mkdir()
    escape.mkdir()
    (fake_home / "pytest-workers").symlink_to(escape, target_is_directory=True)
    env = os.environ.copy()
    env.pop(_WORKER_HOME_ROOT_ENV, None)
    env.pop("OOMPAH_PYTEST_TRUSTED_HOME_ROOT", None)
    env.update(
        {
            "HOME": str(fake_home),
            "OOMPAH_PYTEST_TEMP_ROOT": str(tmp_path / "gate-temp"),
        }
    )

    result = subprocess.run(
        [str(RUNNER), "serial", "tests/not-run.py"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "refusing symlinked quality-gate worker HOME parent" in result.stderr
    assert not tuple(escape.iterdir())


def test_runner_rejects_invalid_preallocated_home_before_allocating(tmp_path: Path):
    fake_home = tmp_path / "home"
    invalid_root = tmp_path / "outside" / "session"
    gate_temp = tmp_path / "gate-temp"
    fake_home.mkdir()
    invalid_root.mkdir(parents=True)
    env = os.environ.copy()
    env.pop("OOMPAH_PYTEST_TRUSTED_HOME_ROOT", None)
    env.update(
        {
            "HOME": str(fake_home),
            "OOMPAH_PYTEST_TEMP_ROOT": str(gate_temp),
            _WORKER_HOME_ROOT_ENV: str(invalid_root),
        }
    )

    result = subprocess.run(
        [str(RUNNER), "serial", "tests/not-run.py"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "worker HOME root must be below" in result.stderr
    assert not gate_temp.exists()
    assert not (fake_home / "pytest-workers").exists()


def test_worker_environment_is_restored_before_each_test(monkeypatch, tmp_path: Path):
    current = dict(os.environ)
    current.pop("OOMPAH_PYTEST_GATE", None)
    current.pop(_WORKER_HOME_ROOT_ENV, None)
    isolated = build_worker_environment(tmp_path / "gw2", current)
    config = SimpleNamespace(
        _oompah_isolated_environment={
            key: isolated[key]
            for key in (
                "HOME",
                "TMPDIR",
                "TMP",
                "TEMP",
                "XDG_CACHE_HOME",
                "XDG_CONFIG_HOME",
                "XDG_DATA_HOME",
            )
        },
        _oompah_runner_environment={
            "OOMPAH_PYTEST_RUN_ROOT": str(tmp_path / "run")
        },
    )
    item = SimpleNamespace(config=config)
    monkeypatch.setenv("HOME", "/contaminated")
    monkeypatch.setenv("TMPDIR", "/contaminated")
    monkeypatch.delenv("OOMPAH_PYTEST_RUN_ROOT", raising=False)

    pytest_runtest_setup(item)  # type: ignore[arg-type]

    assert os.environ["HOME"] == isolated["HOME"]
    assert os.environ["TMPDIR"] == isolated["TMPDIR"]
    assert os.environ["OOMPAH_PYTEST_RUN_ROOT"] == str(tmp_path / "run")


def test_active_xdist_worker_uses_its_private_run_tree():
    """Exercise the installed plugin when this test runs through xdist."""
    worker_id = os.environ.get("PYTEST_XDIST_WORKER")
    if worker_id is None:
        return

    run_root = Path(os.environ["OOMPAH_PYTEST_RUN_ROOT"])
    for key in (
        "TMPDIR",
        "TMP",
        "TEMP",
        "XDG_CACHE_HOME",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
    ):
        assert Path(os.environ[key]).is_relative_to(run_root)
    home = Path(os.environ["HOME"])
    if os.environ.get("OOMPAH_PYTEST_GATE") in {"1", "true", "yes"}:
        assert not home.is_relative_to(run_root)
        assert home.parent == Path(os.environ[_WORKER_HOME_ROOT_ENV])
        assert home.parent.parent.name == "pytest-workers"
    else:
        assert home.is_relative_to(run_root)


def test_process_owning_modules_share_one_xdist_group():
    assert {
        "test_acp_codex_backend.py",
        "test_native_validation_guard.py",
    }.issubset(_PROCESS_GLOBAL_MODULES)

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
