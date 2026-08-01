"""Regression coverage for the repository-wide per-test timeout."""

import tomllib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _pyproject() -> dict:
    return tomllib.loads(
        (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )


def test_pytest_timeout_is_installed_for_ci_and_local_test_runs():
    config = _pyproject()
    optional_dev = config["project"]["optional-dependencies"]["dev"]
    dependency_group = config["dependency-groups"]["dev"]

    assert any(item.startswith("pytest-timeout") for item in optional_dev)
    assert any(item.startswith("pytest-timeout") for item in dependency_group)


def test_every_test_has_a_five_second_signal_timeout():
    """The signal method keeps the xdist worker alive when a test times out.

    The thread method calls ``os._exit(1)`` from a timer thread, terminating
    the pytest-xdist worker without a clean shutdown message.  The controller
    then reports "Not properly terminated", spawns a replacement worker, and
    LoadScopeScheduling / LoadGroupScheduling can crash with a KeyError when
    a late worker-report message arrives for the replaced node — the exact
    failure mode tracked by OOMPAH-675.  The signal method raises
    ``pytest.Failed`` inside the worker's main thread, so the responsible test
    is reported and the worker survives to run the remaining scope's tests.
    """
    pytest_config = _pyproject()["tool"]["pytest"]["ini_options"]

    assert pytest_config["timeout"] == 5
    assert pytest_config["timeout_method"] == "signal"
