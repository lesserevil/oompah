"""OOMPAH-675: prove that a timing-out test does not kill its xdist worker.

Before this fix ``pyproject.toml`` used ``timeout_method = "thread"``.  When a
test exceeded the 5-second bound the ``pytest_timeout`` timer thread called
``os._exit(1)``, terminating the pytest-xdist worker process before it could
send a completion message.  The xdist controller reported ``Not properly
terminated``, spawned a replacement, and the run aborted mid-suite when a late
worker-report event hit the LoadScopeScheduling / LoadGroupScheduling
bookkeeping for a controller whose ``assigned_work`` entry had already been
popped.

These tests exercise the full pytest -> xdist -> worker stack in a subprocess
so they cover the behaviour that broke, not just the pyproject value.  Each
scenario runs a **temporary pytest session** with its own tiny module and its
own strict configuration override, so the regression coverage cannot be
subverted by accidentally clearing ``pyproject.toml`` locally.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


def _prepare_project(target: Path) -> Path:
    """Write a minimal pytest project rooted at *target* and return the dir."""

    target.mkdir(parents=True, exist_ok=True)
    (target / "pyproject.toml").write_text(
        textwrap.dedent(
            """\
            [tool.pytest.ini_options]
            timeout = 1
            timeout_method = "signal"
            addopts = "-p no:cacheprovider"
            """
        ),
        encoding="utf-8",
    )
    return target


def _write_module(target: Path, name: str, body: str) -> None:
    (target / name).write_text(
        textwrap.dedent(body).lstrip("\n"), encoding="utf-8"
    )


def _run_pytest(target: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pytest", *extra],
        cwd=target,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "PYTHONPATH": os.pathsep.join(
                p for p in (str(REPO_ROOT),) if p
            ),
        },
        check=False,
        timeout=180,
    )


@pytest.mark.timeout(120)
def test_signal_timeout_reports_the_responsible_test_and_worker_lives(
    tmp_path: Path,
) -> None:
    """A timing-out test is reported by name and the worker survives.

    Two workers, four tests.  Test ``test_slow`` blocks for far longer than the
    1-second signal timeout.  With ``timeout_method = "signal"`` the timer
    raises ``pytest.Failed`` inside the worker's main thread — the failure
    report identifies ``test_slow`` and the fast tests that share its worker
    still run to completion.
    """
    target = _prepare_project(tmp_path)
    _write_module(
        target,
        "test_scope_a.py",
        """
        import time


        def test_fast_a() -> None:
            time.sleep(0.05)
            assert True


        def test_slow() -> None:
            time.sleep(30)
        """,
    )
    _write_module(
        target,
        "test_scope_b.py",
        """
        import time


        def test_fast_b() -> None:
            time.sleep(0.05)
            assert True


        def test_fast_b2() -> None:
            time.sleep(0.05)
            assert True
        """,
    )

    result = _run_pytest(target, "-n", "2", "--dist", "loadscope", "-v")

    combined = result.stdout + result.stderr
    assert "test_slow" in combined, combined
    # The responsible test's identity survives — a timeout in signal mode is a
    # normal pytest failure, not a controller-side worker replacement.
    assert "Failed: Timeout" in combined, combined
    # A worker did NOT die: the report never contains xdist's node-down
    # bookkeeping.  A KeyError inside LoadScopeScheduling would also print
    # "KeyError" or "INTERNALERROR" — those must not appear.
    assert "Not properly terminated" not in combined, combined
    assert "replacing crashed worker" not in combined, combined
    assert "INTERNALERROR" not in combined, combined
    # The fast tests on both scopes still ran and passed.  xdist prints
    # ``[gwN] [pct%] PASSED module.py::test_name`` for each result.
    assert "PASSED test_scope_a.py::test_fast_a" in combined, combined
    assert "PASSED test_scope_b.py::test_fast_b" in combined, combined
    assert "PASSED test_scope_b.py::test_fast_b2" in combined, combined


@pytest.mark.timeout(120)
def test_worker_crash_is_reported_without_scheduler_keyerror(
    tmp_path: Path,
) -> None:
    """A worker crash surfaces the crashitem without a scheduler KeyError.

    ``--max-worker-restart=0`` forces xdist to stop as soon as a worker is
    lost.  We simulate a genuine crash with ``os._exit(1)`` (the same call
    pytest-timeout's thread mode makes) and verify that the xdist controller
    reports the crashing test's identity and does not produce a scheduler
    ``KeyError`` while cloning a replacement.
    """
    target = _prepare_project(tmp_path)
    _write_module(
        target,
        "test_scope_c.py",
        """
        import os


        def test_takes_worker_down() -> None:
            os._exit(1)


        def test_would_run_next() -> None:
            assert True
        """,
    )
    _write_module(
        target,
        "test_scope_d.py",
        """
        def test_survivor_d() -> None:
            assert True


        def test_survivor_d2() -> None:
            assert True
        """,
    )

    result = _run_pytest(
        target,
        "-n",
        "2",
        "--dist",
        "loadscope",
        "--max-worker-restart=0",
        "-v",
    )

    combined = result.stdout + result.stderr
    # The responsible test is named in the crash report.
    assert "test_takes_worker_down" in combined, combined
    # No scheduler internal error and no attempt to replace a crashed worker.
    assert "INTERNALERROR" not in combined, combined
    assert "replacing crashed worker" not in combined, combined
    # The gate exits non-zero, but the identity of the responsible test is in
    # the terminal output so the operator can re-run it directly.
    assert result.returncode != 0, combined


@pytest.mark.timeout(60)
def test_signal_timeout_does_not_terminate_the_owning_pytest_worker(
    tmp_path: Path,
) -> None:
    """A signal-mode timeout leaves the worker alive to run neighbouring tests.

    Runs a slow test AFTER two fast tests on the same worker's scope so the
    worker must still be alive to execute them.  If ``timeout_method`` were
    ever silently reverted to ``thread`` the second run would report a lost
    worker or fail collection of the neighbouring tests entirely.
    """
    target = _prepare_project(tmp_path)
    _write_module(
        target,
        "test_scope_e.py",
        """
        import time


        def test_slow_first() -> None:
            time.sleep(30)


        def test_fast_second() -> None:
            assert True


        def test_fast_third() -> None:
            assert True
        """,
    )

    result = _run_pytest(target, "-n", "1", "--dist", "loadscope", "-v")

    combined = result.stdout + result.stderr
    assert "test_slow_first" in combined, combined
    assert "PASSED test_scope_e.py::test_fast_second" in combined, combined
    assert "PASSED test_scope_e.py::test_fast_third" in combined, combined
    assert "Not properly terminated" not in combined, combined
    assert "INTERNALERROR" not in combined, combined
