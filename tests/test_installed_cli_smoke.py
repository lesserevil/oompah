"""Smoke tests verifying the oompah console script entry point works after installation.

Two test classes cover different installation surfaces:

* TestCurrentInstallSmoke — exercises the entry point installed via the
  current editable ``pip install -e '.[dev]'`` that CI already performs.
  These tests always run and will fail fast if the console_scripts wiring
  in pyproject.toml is broken.

* TestIsolatedVenvSmoke — builds a fresh virtual environment, installs the
  wheel from ``dist/``, and verifies the entry point works end-to-end in an
  environment that mirrors a real end-user install.  Tests in this class are
  automatically skipped when no wheel exists in ``dist/`` so the normal
  development cycle (no wheel pre-built) is not disrupted.

Acceptance criteria verified here:
- Tests fail if the console script entry point is missing or broken.
- Tests fail if ``oompah task`` cannot be invoked after package installation.
- Tests fail if ``oompah project-bootstrap`` cannot be invoked after package
  installation.
- Server URL/port flag parsing is exercised without a live server.
"""

from __future__ import annotations

import subprocess
import sys
import venv
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = REPO_ROOT / "dist"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _current_scripts_dir() -> Path:
    """Return the scripts/bin directory of the running Python environment."""
    return Path(sys.executable).parent


def _current_oompah_bin() -> Path:
    """Return the path to the oompah entry point in the current environment."""
    scripts = _current_scripts_dir()
    candidates = [scripts / "oompah", scripts / "oompah.exe"]
    for c in candidates:
        if c.exists():
            return c
    # Fall back to the base path (will not exist, so tests will fail clearly)
    return scripts / "oompah"


def _find_wheel() -> Path | None:
    """Return the newest oompah wheel in ``dist/``, or *None* if absent."""
    wheels = sorted(DIST_DIR.glob("oompah-*.whl"))
    return wheels[-1] if wheels else None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def isolated_venv(tmp_path_factory):
    """Create a temporary venv with oompah installed from the dist/ wheel.

    Skips the entire module class if no wheel is found in ``dist/``.
    """
    wheel = _find_wheel()
    if wheel is None:
        pytest.skip(
            "No wheel found in dist/ -- build one with 'python -m build' "
            "or 'pip wheel . -w dist --no-deps' to enable isolated-venv smoke tests"
        )

    venv_dir = tmp_path_factory.mktemp("oompah_smoke_venv")
    venv.create(str(venv_dir), with_pip=True)

    if sys.platform == "win32":
        pip_bin = venv_dir / "Scripts" / "pip.exe"
        oompah_bin = venv_dir / "Scripts" / "oompah.exe"
    else:
        pip_bin = venv_dir / "bin" / "pip"
        oompah_bin = venv_dir / "bin" / "oompah"

    # Install the wheel together with its runtime dependencies so that
    # ``oompah --help`` can actually import the package.
    result = subprocess.run(
        [str(pip_bin), "install", "--quiet", str(wheel)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.fail(
            f"pip install of wheel failed (exit {result.returncode}):\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    return {"oompah": str(oompah_bin), "venv": str(venv_dir)}


# ---------------------------------------------------------------------------
# TestCurrentInstallSmoke
# ---------------------------------------------------------------------------


class TestCurrentInstallSmoke:
    """Verify the entry point works from the currently-installed editable install.

    These tests use the ``oompah`` binary that ``pip install -e '.[dev]'``
    places in the same ``bin/`` directory as the running Python interpreter.
    They run unconditionally as part of the standard pytest suite.
    """

    def test_entry_point_exists(self):
        """oompah binary must exist in the current Python environment's scripts dir."""
        oompah = _current_oompah_bin()
        assert oompah.exists(), (
            f"oompah entry point not found at {oompah}. "
            "Check that the package is installed with 'pip install -e .' and "
            "the [project.scripts] entry point in pyproject.toml is correct."
        )

    def test_oompah_help_exits_zero(self):
        """``oompah --help`` must exit 0 and print usage text."""
        oompah = str(_current_oompah_bin())
        result = subprocess.run(
            [oompah, "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"oompah --help exited {result.returncode}.\n"
            f"stderr: {result.stderr}\nstdout: {result.stdout}"
        )
        output = result.stdout + result.stderr
        assert "oompah" in output.lower(), (
            f"Expected 'oompah' in --help output, got: {output!r}"
        )

    def test_oompah_help_contains_usage(self):
        """``oompah --help`` output must contain the word 'usage'."""
        oompah = str(_current_oompah_bin())
        result = subprocess.run(
            [oompah, "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "usage" in (result.stdout + result.stderr).lower()

    def test_oompah_task_help_exits_zero(self):
        """``oompah task --help`` must exit 0 and list available subcommands."""
        oompah = str(_current_oompah_bin())
        result = subprocess.run(
            [oompah, "task", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"oompah task --help exited {result.returncode}.\n"
            f"stderr: {result.stderr}\nstdout: {result.stdout}"
        )
        output = result.stdout + result.stderr
        # The task subcommand help must mention at least one known subcommand
        assert any(sub in output for sub in ("view", "comment", "create", "set-status")), (
            f"Expected task subcommand names in 'oompah task --help' output, got: {output!r}"
        )

    def test_oompah_project_bootstrap_help_exits_zero(self):
        """``oompah project-bootstrap --help`` must exit 0 and list subcommands."""
        oompah = str(_current_oompah_bin())
        result = subprocess.run(
            [oompah, "project-bootstrap", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"oompah project-bootstrap --help exited {result.returncode}.\n"
            f"stderr: {result.stderr}\nstdout: {result.stdout}"
        )
        output = result.stdout + result.stderr
        assert all(sub in output for sub in ("status", "preview", "apply")), (
            "Expected project-bootstrap subcommand names in "
            f"'oompah project-bootstrap --help' output, got: {output!r}"
        )

    def test_oompah_task_view_help_exits_zero(self):
        """``oompah task view --help`` must exit 0."""
        oompah = str(_current_oompah_bin())
        result = subprocess.run(
            [oompah, "task", "view", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"oompah task view --help exited {result.returncode}.\n"
            f"stderr: {result.stderr}\nstdout: {result.stdout}"
        )

    def test_oompah_task_port_flag_help_exits_zero(self):
        """``oompah task --port PORT --help`` must parse the port flag and exit 0.

        This exercises the server URL/port parsing path without requiring a
        live oompah server.
        """
        oompah = str(_current_oompah_bin())
        result = subprocess.run(
            [oompah, "task", "--port", "19191", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"oompah task --port 19191 --help exited {result.returncode}.\n"
            f"stderr: {result.stderr}\nstdout: {result.stdout}"
        )

    def test_oompah_task_server_flag_help_exits_zero(self):
        """``oompah task --server URL --help`` must parse the server flag and exit 0.

        This exercises explicit server URL parsing without requiring a live server.
        """
        oompah = str(_current_oompah_bin())
        result = subprocess.run(
            [oompah, "task", "--server", "http://example.com:9999", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"oompah task --server http://example.com:9999 --help exited {result.returncode}.\n"
            f"stderr: {result.stderr}\nstdout: {result.stdout}"
        )

    def test_oompah_task_help_does_not_import_server_dependencies(self):
        """``oompah task`` must work from a CLI-only install without server deps."""
        code = """
import builtins
import sys

real_import = builtins.__import__

def guarded_import(name, *args, **kwargs):
    if name == "watchfiles" or name.startswith("watchfiles."):
        raise ImportError("blocked server-only dependency")
    return real_import(name, *args, **kwargs)

builtins.__import__ = guarded_import

from oompah.__main__ import main

sys.argv = ["oompah", "task", "--help"]
try:
    main()
except SystemExit as exc:
    raise SystemExit(exc.code)
"""
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            "oompah task --help imported a server-only dependency.\n"
            f"stderr: {result.stderr}\nstdout: {result.stdout}"
        )

    def test_oompah_help_does_not_import_server_dependencies(self):
        """Top-level help must work from a CLI-only install without server deps."""
        code = """
import builtins
import sys

real_import = builtins.__import__

def guarded_import(name, *args, **kwargs):
    if name == "watchfiles" or name.startswith("watchfiles."):
        raise ImportError("blocked server-only dependency")
    return real_import(name, *args, **kwargs)

builtins.__import__ = guarded_import

from oompah.__main__ import main

sys.argv = ["oompah", "--help"]
try:
    main()
except SystemExit as exc:
    raise SystemExit(exc.code)
"""
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            "oompah --help imported a server-only dependency.\n"
            f"stderr: {result.stderr}\nstdout: {result.stdout}"
        )

    def test_oompah_task_help_does_not_import_any_server_package(self):
        """``oompah task --help`` must not import any package from the server extra.

        This is a comprehensive boundary check: ALL packages listed in the
        ``[project.optional-dependencies.server]`` section of pyproject.toml
        (fastapi, uvicorn, jinja2, pyyaml/yaml, watchfiles, PyJWT/jwt,
        python-liquid/liquid, python-multipart/multipart) are blocked.  The
        test fails if any of them are imported at ``oompah task --help`` time,
        confirming the server extra boundary is intact for the CLI-only path.
        """
        code = """
import builtins
import sys

real_import = builtins.__import__

# All top-level import names for packages in the server extra.
_SERVER_PACKAGES = frozenset([
    "fastapi", "uvicorn", "jinja2", "yaml", "watchfiles", "jwt", "liquid", "multipart",
])

def guarded_import(name, *args, **kwargs):
    root = name.split(".")[0]
    if root in _SERVER_PACKAGES:
        raise ImportError(f"blocked server-only dependency: {name!r}")
    return real_import(name, *args, **kwargs)

builtins.__import__ = guarded_import

from oompah.__main__ import main

sys.argv = ["oompah", "task", "--help"]
try:
    main()
except SystemExit as exc:
    raise SystemExit(exc.code)
"""
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            "oompah task --help imported a server-only dependency from the "
            "server extra.  The CLI-only path must not pull in fastapi, uvicorn, "
            "jinja2, pyyaml, watchfiles, PyJWT, python-liquid, or "
            "python-multipart.\n"
            f"stderr: {result.stderr}\nstdout: {result.stdout}"
        )

    def test_oompah_project_bootstrap_help_does_not_import_any_server_package(self):
        """``oompah project-bootstrap --help`` must not import any server extra package.

        Mirrors the comprehensive server-boundary check for the project-bootstrap
        CLI path.  All packages from ``[project.optional-dependencies.server]``
        are blocked; the test fails if any of them are imported.
        """
        code = """
import builtins
import sys

real_import = builtins.__import__

_SERVER_PACKAGES = frozenset([
    "fastapi", "uvicorn", "jinja2", "yaml", "watchfiles", "jwt", "liquid", "multipart",
])

def guarded_import(name, *args, **kwargs):
    root = name.split(".")[0]
    if root in _SERVER_PACKAGES:
        raise ImportError(f"blocked server-only dependency: {name!r}")
    return real_import(name, *args, **kwargs)

builtins.__import__ = guarded_import

from oompah.__main__ import main

sys.argv = ["oompah", "project-bootstrap", "--help"]
try:
    main()
except SystemExit as exc:
    raise SystemExit(exc.code)
"""
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            "oompah project-bootstrap --help imported a server-only dependency "
            "from the server extra.  The CLI-only path must not pull in fastapi, "
            "uvicorn, jinja2, pyyaml, watchfiles, PyJWT, python-liquid, or "
            "python-multipart.\n"
            f"stderr: {result.stderr}\nstdout: {result.stdout}"
        )


# ---------------------------------------------------------------------------
# TestIsolatedVenvSmoke
# ---------------------------------------------------------------------------


class TestIsolatedVenvSmoke:
    """Verify the console script entry point works after wheel installation.

    These tests install the oompah wheel from ``dist/`` into an isolated
    temporary virtualenv, mirroring what an end-user would do with
    ``pip install oompah-*.whl``.  They are automatically skipped when no
    wheel is present in ``dist/``.
    """

    def test_entry_point_installed_in_isolated_venv(self, isolated_venv):
        """oompah binary must exist inside the isolated venv after wheel install."""
        oompah = Path(isolated_venv["oompah"])
        assert oompah.exists(), (
            f"oompah entry point not found at {oompah} after wheel installation. "
            "The [project.scripts] entry point in pyproject.toml may be missing "
            "or the wheel was built incorrectly."
        )

    def test_isolated_oompah_help_exits_zero(self, isolated_venv):
        """``oompah --help`` must exit 0 from the isolated venv install."""
        result = subprocess.run(
            [isolated_venv["oompah"], "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"oompah --help exited {result.returncode} in isolated venv.\n"
            f"stderr: {result.stderr}\nstdout: {result.stdout}"
        )
        output = result.stdout + result.stderr
        assert "oompah" in output.lower(), (
            f"Expected 'oompah' in --help output from isolated install, got: {output!r}"
        )

    def test_isolated_oompah_task_help_exits_zero(self, isolated_venv):
        """``oompah task --help`` must exit 0 from the isolated venv install."""
        result = subprocess.run(
            [isolated_venv["oompah"], "task", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"oompah task --help exited {result.returncode} in isolated venv.\n"
            f"stderr: {result.stderr}\nstdout: {result.stdout}"
        )
        output = result.stdout + result.stderr
        assert any(sub in output for sub in ("view", "comment", "create", "set-status")), (
            f"Expected task subcommand names in isolated 'oompah task --help' output, "
            f"got: {output!r}"
        )

    def test_isolated_oompah_project_bootstrap_help_exits_zero(self, isolated_venv):
        """``oompah project-bootstrap --help`` exits 0 from isolated venv install."""
        result = subprocess.run(
            [isolated_venv["oompah"], "project-bootstrap", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"oompah project-bootstrap --help exited {result.returncode} in isolated venv.\n"
            f"stderr: {result.stderr}\nstdout: {result.stdout}"
        )
        output = result.stdout + result.stderr
        assert all(sub in output for sub in ("status", "preview", "apply")), (
            "Expected project-bootstrap subcommand names in isolated "
            f"'oompah project-bootstrap --help' output, got: {output!r}"
        )

    def test_isolated_oompah_task_port_flag_help_exits_zero(self, isolated_venv):
        """``oompah task --port PORT --help`` exits 0 from isolated venv install."""
        result = subprocess.run(
            [isolated_venv["oompah"], "task", "--port", "19191", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"oompah task --port 19191 --help exited {result.returncode} in isolated venv.\n"
            f"stderr: {result.stderr}\nstdout: {result.stdout}"
        )

    def test_isolated_oompah_task_server_flag_help_exits_zero(self, isolated_venv):
        """``oompah task --server URL --help`` exits 0 from isolated venv install."""
        result = subprocess.run(
            [isolated_venv["oompah"], "task", "--server", "http://example.com:9999", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"oompah task --server http://example.com:9999 --help exited {result.returncode} "
            f"in isolated venv.\nstderr: {result.stderr}\nstdout: {result.stdout}"
        )
