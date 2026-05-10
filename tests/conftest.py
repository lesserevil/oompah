"""Pytest fixtures shared across the test suite.

Currently this only contains an autouse fixture that redirects the
default agent_profiles.json store path to a tmp directory so the
WORKFLOW.md → JSON one-shot migration (oompah-zlz_2-2y7) does not
write to the real .oompah/ directory during unit tests, and so the
once-per-process WARN cache resets between tests.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolate_agent_profile_store(tmp_path, monkeypatch):
    """Redirect agent profile store to a per-test tmp file and reset state.

    Without this, ServiceConfig.from_workflow(wf) — when wf has
    agent.profiles[] — would migrate to the *real* .oompah/agent_profiles.json
    in the cwd of the test runner, leaking state across runs and causing
    later tests to load JSON profiles instead of YAML.
    """
    from oompah import agent_profile_store as aps

    # Per-test default path
    test_path = str(tmp_path / "_test_agent_profiles.json")
    monkeypatch.setattr(aps, "DEFAULT_AGENT_PROFILES_PATH", test_path)

    # Clear once-per-process WARN cache so tests in the same module that
    # both touch resolve_agent_profiles each get a fresh chance to WARN.
    aps.reset_warning_state()

    yield

    aps.reset_warning_state()
