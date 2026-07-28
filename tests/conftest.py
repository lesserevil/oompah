"""Pytest fixtures shared across the test suite.

Currently this contains:

1. An autouse fixture that redirects the default agent_profiles.json store
   path to a tmp directory so the WORKFLOW.md → JSON one-shot migration
   (oompah-zlz_2-2y7) does not write to the real .oompah/ directory during
   unit tests, and so the once-per-process WARN cache resets between tests.

2. A session-scoped autouse fixture that blocks all network Git remotes for
   the entire test session (OOMPAH-491).  See ``_block_network_git_remotes``
   for details.
"""

from __future__ import annotations

import os

import pytest


# ---------------------------------------------------------------------------
# Network Git remote barrier (OOMPAH-491)
# ---------------------------------------------------------------------------

#: Path prefix used as the redirect target for blocked network URL schemes.
#: It must not exist on the test host (/ is root-only on Linux, so this is
#: guaranteed).  The name is intentionally descriptive so it appears in git
#: error messages and makes the cause obvious.
_BARRIER_BASE = "/OOMPAH-TEST-NETWORK-BARRIER"

#: Rules that map a URL prefix (``insteadOf`` value) to a barrier base URL.
#: ``url.<base>.insteadOf = <prefix>`` tells git to rewrite any URL starting
#: with ``<prefix>`` so that ``<prefix>`` is replaced by ``<base>``.  Using
#: a nonexistent local path as ``<base>`` causes git to fail immediately with
#: a "does not exist" error rather than attempting a live network connection.
#:
#: Each scheme gets its own unique base URL so multiple rules can coexist
#: without git merging them.
_BARRIER_RULES: tuple[tuple[str, str], ...] = (
    # (git-config key, insteadOf value)
    (
        f"url.file://{_BARRIER_BASE}/https/.insteadOf",
        "https://",
    ),
    (
        f"url.file://{_BARRIER_BASE}/http/.insteadOf",
        "http://",
    ),
    (
        f"url.file://{_BARRIER_BASE}/ssh/.insteadOf",
        "ssh://",
    ),
    (
        f"url.file://{_BARRIER_BASE}/git/.insteadOf",
        "git://",
    ),
    # SCP-style remotes (e.g. git@github.com:user/repo) start with "git@".
    # Blocking this prefix catches the vast majority of SCP-style remotes.
    (
        f"url.file://{_BARRIER_BASE}/scp/.insteadOf",
        "git@",
    ),
)


def build_network_barrier_env(env: dict[str, str]) -> dict[str, str]:
    """Return a copy of *env* with the network Git remote barrier injected.

    Appends ``GIT_CONFIG_KEY_N`` / ``GIT_CONFIG_VALUE_N`` entries for each
    blocked URL scheme *after* any pre-existing numbered entries, then
    increments ``GIT_CONFIG_COUNT`` accordingly.  Pre-existing entries are
    never touched.

    This function is the single source of truth for the barrier logic so it
    can be tested independently of the pytest session fixture.

    Parameters
    ----------
    env:
        A mapping that looks like ``os.environ`` (str → str).

    Returns
    -------
    dict[str, str]
        A shallow copy with the barrier entries appended.
    """
    existing_count = int(env.get("GIT_CONFIG_COUNT", "0"))
    result: dict[str, str] = dict(env)

    for i, (cfg_key, cfg_value) in enumerate(_BARRIER_RULES):
        idx = existing_count + i
        result[f"GIT_CONFIG_KEY_{idx}"] = cfg_key
        result[f"GIT_CONFIG_VALUE_{idx}"] = cfg_value

    result["GIT_CONFIG_COUNT"] = str(existing_count + len(_BARRIER_RULES))
    return result


@pytest.fixture(scope="session", autouse=True)
def _block_network_git_remotes() -> None:  # type: ignore[return]
    """Block network Git remotes for the entire test session.

    Injects ``GIT_CONFIG_COUNT`` / ``GIT_CONFIG_KEY_N`` / ``GIT_CONFIG_VALUE_N``
    environment variables that redirect HTTP, HTTPS, SSH (``ssh://`` and
    SCP-style ``git@host:path``), and ``git://`` URLs to a nonexistent local
    path.  This prevents any unmocked ``git`` subprocess from contacting a
    public or private network remote.

    **What is NOT blocked:**

    * Absolute-path remotes (e.g. ``/tmp/foo/bare.git``)
    * ``file://`` remotes (e.g. ``file:///tmp/foo/bare.git``)

    These local transports remain fully usable because state-branch and
    migration tests depend on them.

    **Preserving pre-existing entries:**

    Any ``GIT_CONFIG_COUNT`` already set in the environment is respected.
    The barrier rules are appended *after* the existing numbered entries so
    they are not clobbered.

    **Opt-out:**

    A test that uses a local transport that the guard incorrectly classifies
    may temporarily extend the environment to un-redirect the relevant URL
    (e.g. via ``monkeypatch.setenv`` or a custom ``env=`` dict passed to
    ``subprocess.run``).  No test may opt out to access a public network
    remote.

    **Error messages:**

    When a blocked URL is accessed, git reports:

        fatal: '/OOMPAH-TEST-NETWORK-BARRIER/<scheme>/<rest-of-url>' does not
        appear to be a git repository

    The ``OOMPAH-TEST-NETWORK-BARRIER`` marker identifies the source of the
    failure.  Tests must inject a local bare remote or mock the git boundary
    instead of contacting a network remote.
    """
    # Save originals so we can restore them after the session.
    saved: dict[str, str | None] = {
        "GIT_CONFIG_COUNT": os.environ.get("GIT_CONFIG_COUNT"),
    }

    existing_count = int(os.environ.get("GIT_CONFIG_COUNT", "0"))

    for i, (cfg_key, cfg_value) in enumerate(_BARRIER_RULES):
        idx = existing_count + i
        k_env = f"GIT_CONFIG_KEY_{idx}"
        v_env = f"GIT_CONFIG_VALUE_{idx}"
        saved[k_env] = os.environ.get(k_env)
        saved[v_env] = os.environ.get(v_env)
        os.environ[k_env] = cfg_key
        os.environ[v_env] = cfg_value

    os.environ["GIT_CONFIG_COUNT"] = str(existing_count + len(_BARRIER_RULES))

    yield  # --- test session runs here ---

    # Restore the original environment exactly.
    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


# ---------------------------------------------------------------------------
# Agent profile store isolation
# ---------------------------------------------------------------------------


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
