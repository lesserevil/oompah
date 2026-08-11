"""Tests for developer setup Makefile behavior."""

from __future__ import annotations

import os
from pathlib import Path
import shlex
import shutil
import subprocess
import venv


ROOT = Path(__file__).resolve().parents[1]
MAKEFILE = ROOT / "Makefile"


def _makefile_text() -> str:
    return MAKEFILE.read_text(encoding="utf-8")


def _editable_test_venv(
    tmp_path: Path,
    editable_checkout: Path,
    *,
    runtime_name: str = ".venv",
) -> tuple[Path, Path]:
    """Create a small real venv whose oompah import comes from one checkout."""
    runtime = tmp_path / runtime_name
    venv.EnvBuilder(with_pip=False).create(runtime)
    result = subprocess.run(
        [
            str(runtime / "bin" / "python"),
            "-c",
            "import site; print(site.getsitepackages()[0])",
        ],
        cwd=runtime,
        capture_output=True,
        text=True,
        check=True,
    )
    editable_path = Path(result.stdout.strip()) / "_editable_impl_oompah.pth"
    editable_path.write_text(f"{editable_checkout}\n", encoding="utf-8")
    (runtime / ".uv-setup").touch()
    return runtime, editable_path


def _non_gate_environment(fake_bin: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment["OOMPAH_PYTEST_GATE"] = "0"
    environment["PATH"] = f"{fake_bin}:/usr/bin:/bin"
    # Setup must inspect the installed editable path, not import the invoking
    # checkout just because an operator happens to expose it through PYTHONPATH.
    environment["PYTHONPATH"] = str(ROOT)
    return environment


def _copy_setup_surface(checkout: Path) -> None:
    """Create the minimal source surface exercised by the Make setup guard."""
    checkout.mkdir(parents=True, exist_ok=True)
    (checkout / "Makefile").write_text(_makefile_text(), encoding="utf-8")
    (checkout / "pyproject.toml").write_text(
        "[project]\nname = 'oompah'\nversion = '0'\n",
        encoding="utf-8",
    )
    package = checkout / "oompah"
    package.mkdir(exist_ok=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    shutil.copyfile(ROOT / "oompah" / "venv_safety.py", package / "venv_safety.py")


def _linked_setup_checkouts(tmp_path: Path, *task_names: str) -> tuple[Path, ...]:
    """Build a minimal primary checkout plus linked-worktree metadata."""
    service = tmp_path / "service"
    _copy_setup_surface(service)
    common = service / ".git"
    common.mkdir()
    checkouts = [service]
    for name in task_names:
        task = tmp_path / name
        _copy_setup_surface(task)
        worktree_git = common / "worktrees" / name
        worktree_git.mkdir(parents=True)
        (worktree_git / "commondir").write_text("../..\n", encoding="utf-8")
        (task / ".git").write_text(
            f"gitdir: {worktree_git}\n",
            encoding="utf-8",
        )
        checkouts.append(task)
    return tuple(checkouts)


def _make_setup(
    checkout: Path,
    *,
    environment: dict[str, str],
    task_venv_argument: str | None = None,
    service_checkout_argument: str | None = None,
    service_venv_argument: str | None = None,
    target: str = "setup",
) -> subprocess.CompletedProcess[str]:
    command = ["/usr/bin/make", "--no-print-directory"]
    if task_venv_argument is not None:
        command.append(f"OOMPAH_TASK_VENV={task_venv_argument}")
    if service_checkout_argument is not None:
        command.append(f"OOMPAH_SERVICE_CHECKOUT={service_checkout_argument}")
    if service_venv_argument is not None:
        command.append(f"OOMPAH_SERVICE_VENV={service_venv_argument}")
    command.append(target)
    return subprocess.run(
        command,
        cwd=checkout,
        env=environment,
        capture_output=True,
        text=True,
    )


def test_setup_installs_server_dependencies_only():
    """make setup installs Python dependencies without tracker-specific setup."""
    text = _makefile_text()

    assert "python3 -m oompah.venv_safety ensure" in text
    assert '--checkout "$(CURDIR)" --venv "$(VENV)"' in text
    assert '--uv "$(UV)" --extra server' in text
    assert "start: setup" in text
    assert "ensure-" not in text


def test_test_targets_install_complete_dev_dependencies():
    """Fresh test worktrees must install every dependency exercised by tests."""
    text = _makefile_text()

    assert "test-setup: setup" in text
    assert '--uv "$(UV)" --extra dev' in text
    assert ".PHONY: help setup test-setup" in text
    assert "test: test-setup" in text
    assert "test-serial: test-setup" in text


def test_quality_gate_uses_trusted_runtime_without_uv(tmp_path):
    """Gate mode validates the projected venv without trying to mutate it."""
    venv = tmp_path / "read-only-venv"
    python = venv / "bin" / "python"
    runtime_checkout = tmp_path / "trusted-install" / "oompah"
    launcher = venv / "bin" / "oompah"
    python.parent.mkdir(parents=True)
    python.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    python.chmod(0o555)
    launcher.write_text(
        f"#!{runtime_checkout}/.venv/bin/python3\nraise SystemExit(0)\n",
        encoding="utf-8",
    )
    launcher.chmod(0o555)
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
    assert runtime_checkout.is_symlink()
    assert runtime_checkout.resolve() == ROOT


def test_quality_gate_rejects_cli_alias_to_non_candidate_checkout(tmp_path):
    """An existing trusted-launcher path cannot redirect imports elsewhere."""
    venv = tmp_path / "read-only-venv"
    python = venv / "bin" / "python"
    runtime_checkout = tmp_path / "wrong-checkout"
    launcher = venv / "bin" / "oompah"
    python.parent.mkdir(parents=True)
    python.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    python.chmod(0o755)
    runtime_checkout.mkdir()
    launcher.write_text(
        f"#!{runtime_checkout}/.venv/bin/python3\nraise SystemExit(0)\n",
        encoding="utf-8",
    )
    launcher.chmod(0o755)

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
    assert "CLI source alias is not the candidate snapshot" in result.stderr


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
    environment = os.environ.copy()
    # The assertion below deliberately covers the developer default, rather
    # than a managed worker's task-private override.
    environment.pop("OOMPAH_TASK_VENV", None)
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
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "oompah.venv_safety ensure" in result.stdout
    assert '--venv ".venv"' in result.stdout
    assert "--extra server" in result.stdout
    assert "--extra dev" in result.stdout


def test_task_worktree_rejects_explicit_absolute_service_venv(tmp_path):
    """A command-line task override cannot retarget the live service runtime."""
    service, task = _linked_setup_checkouts(tmp_path, "task")
    service_venv, editable_path = _editable_test_venv(service, service)
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    uv_called = tmp_path / "uv-called"
    (fake_bin / "uv").write_text(
        f"#!/bin/sh\ntouch {shlex.quote(str(uv_called))}\n",
        encoding="utf-8",
    )
    (fake_bin / "uv").chmod(0o755)

    result = _make_setup(
        task,
        environment=_non_gate_environment(fake_bin),
        task_venv_argument=str(service_venv),
    )

    assert result.returncode != 0
    assert "resolves to the live service virtualenv" in result.stderr
    assert not uv_called.exists()
    assert editable_path.read_text(encoding="utf-8").strip() == str(service)


def test_task_worktree_rejects_falsified_command_line_service_markers(tmp_path):
    """Make overrides cannot erase Git-derived service runtime authority."""
    service, task = _linked_setup_checkouts(tmp_path, "task")
    service_venv, editable_path = _editable_test_venv(service, service)
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    uv_called = tmp_path / "uv-called"
    (fake_bin / "uv").write_text(
        "#!/bin/sh\n"
        f"touch {shlex.quote(str(uv_called))}\n"
        f"printf '%s\\n' {shlex.quote(str(task))} > "
        f"{shlex.quote(str(editable_path))}\n",
        encoding="utf-8",
    )
    (fake_bin / "uv").chmod(0o755)
    environment = _non_gate_environment(fake_bin)
    false_service_venv = task / ".oompah" / "task-venv"

    false_checkout = _make_setup(
        task,
        environment=environment,
        task_venv_argument=str(service_venv),
        service_checkout_argument=str(task),
        service_venv_argument=str(false_service_venv),
    )
    false_venv = _make_setup(
        task,
        environment=environment,
        task_venv_argument=str(service_venv),
        service_checkout_argument=str(service),
        service_venv_argument=str(false_service_venv),
    )

    assert false_checkout.returncode != 0
    assert "conflicts with Git-derived primary checkout" in false_checkout.stderr
    assert false_venv.returncode != 0
    assert "resolves to the live service virtualenv" in false_venv.stderr
    assert not uv_called.exists()
    assert editable_path.read_text(encoding="utf-8").strip() == str(service)


def test_task_worktree_rejects_inherited_service_venv(tmp_path):
    """A worker cannot inherit the service runtime as its task selector."""
    service, task = _linked_setup_checkouts(tmp_path, "task")
    service_venv, editable_path = _editable_test_venv(service, service)
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    uv_called = tmp_path / "uv-called"
    (fake_bin / "uv").write_text(
        f"#!/bin/sh\ntouch {shlex.quote(str(uv_called))}\n",
        encoding="utf-8",
    )
    (fake_bin / "uv").chmod(0o755)
    environment = _non_gate_environment(fake_bin)
    environment["OOMPAH_TASK_VENV"] = str(service_venv)

    result = _make_setup(task, environment=environment)

    assert result.returncode != 0
    assert "resolves to the live service virtualenv" in result.stderr
    assert not uv_called.exists()
    assert editable_path.read_text(encoding="utf-8").strip() == str(service)


def test_service_runtime_marker_protects_across_repository_boundaries(tmp_path):
    """Worker-provided service identity protects the runtime in another repo."""
    service = tmp_path / "service"
    task = tmp_path / "unrelated-task"
    _copy_setup_surface(service)
    _copy_setup_surface(task)
    (service / ".git").mkdir()
    (task / ".git").mkdir()
    service_venv, editable_path = _editable_test_venv(service, service)
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    uv_called = tmp_path / "uv-called"
    (fake_bin / "uv").write_text(
        f"#!/bin/sh\ntouch {shlex.quote(str(uv_called))}\n",
        encoding="utf-8",
    )
    (fake_bin / "uv").chmod(0o755)
    environment = _non_gate_environment(fake_bin)
    environment.update(
        {
            "OOMPAH_TASK_VENV": str(service_venv),
            "OOMPAH_SERVICE_CHECKOUT": str(service),
            "OOMPAH_SERVICE_VENV": str(service_venv),
        }
    )

    result = _make_setup(task, environment=environment)

    assert result.returncode != 0
    assert "resolves to the live service virtualenv" in result.stderr
    assert not uv_called.exists()
    assert editable_path.read_text(encoding="utf-8").strip() == str(service)


def test_task_worktree_rejects_relative_and_symlink_service_venv_aliases(tmp_path):
    """Lexical aliases are compared by resolution and filesystem identity."""
    service, task = _linked_setup_checkouts(tmp_path, "task")
    service_venv, editable_path = _editable_test_venv(service, service)
    alias = tmp_path / "service-venv-alias"
    alias.symlink_to(service_venv, target_is_directory=True)
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    uv_called = tmp_path / "uv-called"
    (fake_bin / "uv").write_text(
        f"#!/bin/sh\ntouch {shlex.quote(str(uv_called))}\n",
        encoding="utf-8",
    )
    (fake_bin / "uv").chmod(0o755)
    environment = _non_gate_environment(fake_bin)

    relative = os.path.relpath(service_venv, task)
    relative_result = _make_setup(
        task,
        environment=environment,
        task_venv_argument=relative,
    )
    alias_result = _make_setup(
        task,
        environment=environment,
        task_venv_argument=str(alias),
    )

    assert relative_result.returncode != 0
    assert alias_result.returncode != 0
    assert "live service virtualenv" in relative_result.stderr
    assert "live service virtualenv" in alias_result.stderr
    assert not uv_called.exists()
    assert editable_path.read_text(encoding="utf-8").strip() == str(service)


def test_concurrent_task_worktrees_cannot_race_service_editable_mapping(tmp_path):
    """The shared Git lock and alias guard protect one trusted mapping."""
    service, task_a, task_b = _linked_setup_checkouts(
        tmp_path,
        "task-a",
        "task-b",
    )
    service_venv, editable_path = _editable_test_venv(service, service)
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    uv_called = tmp_path / "uv-called"
    (fake_bin / "uv").write_text(
        f"#!/bin/sh\ntouch {shlex.quote(str(uv_called))}\nsleep 1\n",
        encoding="utf-8",
    )
    (fake_bin / "uv").chmod(0o755)
    environment = _non_gate_environment(fake_bin)
    command = [
        "/usr/bin/make",
        "--no-print-directory",
        f"OOMPAH_TASK_VENV={service_venv}",
        "setup",
    ]

    first = subprocess.Popen(
        command,
        cwd=task_a,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    second = subprocess.Popen(
        command,
        cwd=task_b,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    first_output = first.communicate(timeout=5)
    second_output = second.communicate(timeout=5)

    assert first.returncode != 0, first_output
    assert second.returncode != 0, second_output
    assert not uv_called.exists()
    assert editable_path.read_text(encoding="utf-8").strip() == str(service)


def test_canonical_service_setup_repairs_its_own_editable_mapping(tmp_path):
    """The primary checkout retains authority to repair its live runtime."""
    service, task = _linked_setup_checkouts(tmp_path, "task")
    service_venv, editable_path = _editable_test_venv(service, task)
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    uv_called = tmp_path / "uv-called"
    (fake_bin / "uv").write_text(
        "#!/bin/sh\n"
        f"touch {shlex.quote(str(uv_called))}\n"
        f"printf '%s\\n' {shlex.quote(str(service))} > "
        f"{shlex.quote(str(editable_path))}\n",
        encoding="utf-8",
    )
    (fake_bin / "uv").chmod(0o755)

    result = _make_setup(
        service,
        environment=_non_gate_environment(fake_bin),
        task_venv_argument=str(service_venv),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert uv_called.exists()
    assert editable_path.read_text(encoding="utf-8").strip() == str(service)


def test_task_private_venv_remains_a_valid_test_setup_target(tmp_path):
    """A managed worktree can validate through its isolated runtime."""
    _service, task = _linked_setup_checkouts(tmp_path, "task")
    private_root = task / ".oompah"
    private_root.mkdir()
    private_venv, _editable_path = _editable_test_venv(
        private_root,
        task,
        runtime_name="task-venv",
    )
    (private_venv / ".uv-test-setup").touch()
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    uv_called = tmp_path / "uv-called"
    (fake_bin / "uv").write_text(
        f"#!/bin/sh\ntouch {shlex.quote(str(uv_called))}\nexit 91\n",
        encoding="utf-8",
    )
    (fake_bin / "uv").chmod(0o755)
    environment = _non_gate_environment(fake_bin)
    environment["OOMPAH_TASK_VENV"] = str(private_venv)

    result = _make_setup(task, environment=environment, target="test-setup")

    assert result.returncode == 0, result.stdout + result.stderr
    assert not uv_called.exists()


def test_setup_refreshes_a_fresh_stamp_with_a_stale_editable_checkout(tmp_path):
    """A current sentinel must not preserve an install from another worktree."""
    stale_checkout = tmp_path / "retired-worktree"
    stale_package = stale_checkout / "oompah"
    stale_package.mkdir(parents=True)
    (stale_package / "__init__.py").write_text("", encoding="utf-8")
    runtime, editable_path = _editable_test_venv(tmp_path, stale_checkout)

    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    uv_called = tmp_path / "uv-called"
    fake_uv = fake_bin / "uv"
    fake_uv.write_text(
        "#!/bin/sh\n"
        f"touch {shlex.quote(str(uv_called))}\n"
        f"printf '%s\\n' {shlex.quote(str(ROOT))} > "
        f"{shlex.quote(str(editable_path))}\n",
        encoding="utf-8",
    )
    fake_uv.chmod(0o755)

    result = subprocess.run(
        [
            "/usr/bin/make",
            "--no-print-directory",
            f"VENV={runtime}",
            "setup",
        ],
        cwd=ROOT,
        env=_non_gate_environment(fake_bin),
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert uv_called.exists(), "the stale editable install was not refreshed"
    assert editable_path.read_text(encoding="utf-8").strip() == str(ROOT)


def test_setup_does_not_accept_or_stamp_a_partial_failed_refresh(tmp_path):
    """Mutated editable metadata cannot turn a failed uv refresh into success."""
    stale_checkout = tmp_path / "stale-worktree"
    stale_package = stale_checkout / "oompah"
    stale_package.mkdir(parents=True)
    (stale_package / "__init__.py").write_text("", encoding="utf-8")
    runtime, editable_path = _editable_test_venv(tmp_path, stale_checkout)
    setup_stamp = runtime / ".uv-setup"
    setup_stamp.write_text("original setup stamp\n", encoding="utf-8")
    original_mtime_ns = setup_stamp.stat().st_mtime_ns

    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    touch_called = tmp_path / "touch-called"
    fake_touch = fake_bin / "touch"
    fake_touch.write_text(
        "#!/bin/sh\n"
        f"printf '%s\\n' \"$@\" > {shlex.quote(str(touch_called))}\n"
        "exec /usr/bin/touch \"$@\"\n",
        encoding="utf-8",
    )
    fake_touch.chmod(0o755)
    fake_uv = fake_bin / "uv"
    fake_uv.write_text(
        "#!/bin/sh\n"
        f"printf '%s\\n' {shlex.quote(str(ROOT))} > "
        f"{shlex.quote(str(editable_path))}\n"
        "exit 73\n",
        encoding="utf-8",
    )
    fake_uv.chmod(0o755)

    result = subprocess.run(
        [
            "/usr/bin/make",
            "--no-print-directory",
            f"VENV={runtime}",
            "setup",
        ],
        cwd=ROOT,
        env=_non_gate_environment(fake_bin),
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "failed to refresh editable oompah install" in result.stderr
    assert editable_path.read_text(encoding="utf-8").strip() == str(ROOT)
    assert setup_stamp.read_text(encoding="utf-8") == "original setup stamp\n"
    assert setup_stamp.stat().st_mtime_ns == original_mtime_ns
    assert not touch_called.exists()


def test_setup_keeps_a_fresh_correct_editable_checkout_idempotent(tmp_path):
    """The normal current install takes the fast path without invoking uv."""
    runtime, _editable_path = _editable_test_venv(tmp_path, ROOT)

    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    uv_called = tmp_path / "uv-called"
    fake_uv = fake_bin / "uv"
    fake_uv.write_text(
        "#!/bin/sh\n"
        f"touch {shlex.quote(str(uv_called))}\n"
        "exit 91\n",
        encoding="utf-8",
    )
    fake_uv.chmod(0o755)

    result = subprocess.run(
        [
            "/usr/bin/make",
            "--no-print-directory",
            f"VENV={runtime}",
            "setup",
        ],
        cwd=ROOT,
        env=_non_gate_environment(fake_bin),
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert not uv_called.exists(), "an already-correct editable install reran uv"


def test_non_gate_setup_rejects_a_thin_venv_wrapper_before_uv(tmp_path):
    """A task checkout cannot use a wrapper that points at the service venv."""
    venv = tmp_path / ".venv"
    python = venv / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text(
        "#!/bin/sh\nexec /operator/service/.venv/bin/python \"$@\"\n",
        encoding="utf-8",
    )
    python.chmod(0o755)
    (venv / ".uv-setup").touch()

    fake_uv = tmp_path / "uv"
    fake_uv.write_text(
        "#!/bin/sh\n"
        f"touch {tmp_path / 'uv-used'}\n"
        "exit 0\n",
        encoding="utf-8",
    )
    fake_uv.chmod(0o755)
    environment = os.environ.copy()
    # This fixture verifies the normal setup branch even when pytest itself is
    # running inside a quality gate, whose environment enables gate mode.
    environment["OOMPAH_PYTEST_GATE"] = "0"
    environment["PATH"] = f"{tmp_path}:/usr/bin:/bin"
    result = subprocess.run(
        [
            "/usr/bin/make",
            "--no-print-directory",
            f"VENV={venv}",
            "setup",
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "not a real task-private virtualenv" in result.stderr
    assert not (tmp_path / "uv-used").exists()


def test_non_gate_setup_rejects_a_symlinked_service_venv_before_uv(tmp_path):
    """A symlinked .venv cannot make the service runtime the install target."""
    service_venv = tmp_path / "service" / ".venv"
    service_venv.mkdir(parents=True)
    (service_venv / "pyvenv.cfg").write_text("home = /operator/python\n", encoding="utf-8")
    (service_venv / ".uv-setup").touch()
    worktree_venv = tmp_path / "worktree" / ".venv"
    worktree_venv.parent.mkdir()
    worktree_venv.symlink_to(service_venv, target_is_directory=True)

    fake_uv = tmp_path / "uv"
    fake_uv.write_text(
        "#!/bin/sh\n"
        f"touch {tmp_path / 'uv-used'}\n"
        "exit 0\n",
        encoding="utf-8",
    )
    fake_uv.chmod(0o755)
    environment = os.environ.copy()
    # Keep this explicitly non-gate test independent of its outer runner.
    environment["OOMPAH_PYTEST_GATE"] = "0"
    environment["PATH"] = f"{tmp_path}:/usr/bin:/bin"
    result = subprocess.run(
        [
            "/usr/bin/make",
            "--no-print-directory",
            f"VENV={worktree_venv}",
            "setup",
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "not a real task-private virtualenv" in result.stderr
    assert not (tmp_path / "uv-used").exists()


def test_fresh_setup_stamp_cannot_mask_a_non_private_interpreter(tmp_path):
    """The interpreter-prefix guard still runs on the idempotent setup path."""
    runtime = tmp_path / ".venv"
    python = runtime / "bin" / "python"
    python.parent.mkdir(parents=True)
    (runtime / "pyvenv.cfg").write_text("home = /operator/python\n", encoding="utf-8")
    (runtime / ".uv-setup").touch()
    python.write_text(
        "#!/bin/sh\n"
        "printf '%s\\n' /operator/service/.venv\n",
        encoding="utf-8",
    )
    python.chmod(0o755)

    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    uv_called = tmp_path / "uv-called"
    fake_uv = fake_bin / "uv"
    fake_uv.write_text(
        "#!/bin/sh\n"
        f"touch {shlex.quote(str(uv_called))}\n",
        encoding="utf-8",
    )
    fake_uv.chmod(0o755)

    result = subprocess.run(
        [
            "/usr/bin/make",
            "--no-print-directory",
            f"VENV={runtime}",
            "setup",
        ],
        cwd=ROOT,
        env=_non_gate_environment(fake_bin),
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "interpreter resolves to /operator/service/.venv" in result.stderr
    assert not uv_called.exists()


def test_setup_does_not_install_external_tracker_cli():
    """The setup helper should not install external tracker CLIs."""
    text = _makefile_text()

    assert "npm install --global --prefix" not in text
    assert "--ignore-scripts" not in text


def test_make_targets_export_venv_bin_on_path():
    """Runtime make targets should find venv-local commands."""
    text = _makefile_text()

    assert "export PATH := $(abspath $(VENV)/bin):$(PATH)" in text
    assert "OPERATOR_PATH := $(if $(OOMPAH_OPERATOR_PATH),$(OOMPAH_OPERATOR_PATH),$(PATH))" in text
    assert "export OOMPAH_OPERATOR_PATH := $(OPERATOR_PATH)" in text
    assert '--operator-path "$(OPERATOR_PATH)"' in text


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
