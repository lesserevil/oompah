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
import threading
from concurrent.futures import ThreadPoolExecutor
from functools import wraps

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

    # The managed agent process carries a short-lived task-handoff capability
    # in its environment. Unit tests should exercise ordinary CLI behavior by
    # default; handoff tests opt in explicitly with monkeypatch.setenv().
    monkeypatch.delenv("OOMPAH_TASK_HANDOFF_TOKEN", raising=False)
    monkeypatch.delenv("OOMPAH_TASK_HANDOFF_PROJECT_ID", raising=False)
    monkeypatch.delenv("OOMPAH_TASK_HANDOFF_TASK_ID", raising=False)

    yield

    aps.reset_warning_state()


@pytest.fixture(autouse=True)
def _isolate_registered_secrets():
    """Reset the process-local registered-secret registry between tests.

    Several unit tests exercise :func:`oompah.secrets.register_secret`
    (directly or via credential resolvers that register at load time).
    The registry is process-local by design, so an unrelated test that
    registers a short value like ``"p"`` would otherwise cause any log
    assertion in a later test to redact substrings of ordinary words
    (``permissions``/``group``/``oompah``). Clearing on entry AND exit
    keeps every test's registry state deterministic without requiring
    each test to remember cleanup.
    """
    from oompah.secrets import clear_registered_secrets

    clear_registered_secrets()
    yield
    clear_registered_secrets()


class _OompahTestResourceRegistry:
    """Own real per-test orchestrator pools and persistent SQLite stores."""

    def __init__(self) -> None:
        self._orchestrators: list[dict[str, object]] = []
        self._stores: list[object] = []
        self._lock = threading.RLock()
        self._close_lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._constructor_context = threading.local()
        self._active_constructors = 0
        self._seal_event = threading.Event()
        self._closing = False
        self._closed = False

    def begin_constructor(self, resource_type: str) -> None:
        """Admit one constructor before teardown seals the test boundary."""

        with self._condition:
            nested = bool(getattr(self._constructor_context, "depth", 0))
            if (self._closing or self._closed) and not nested:
                raise RuntimeError(
                    f"{resource_type} constructed after test resource boundary sealed"
                )
            self._active_constructors += 1
            self._constructor_context.depth = (
                getattr(self._constructor_context, "depth", 0) + 1
            )

    def end_constructor(self) -> None:
        with self._condition:
            self._constructor_context.depth -= 1
            self._active_constructors -= 1
            self._condition.notify_all()

    def register_orchestrator(self, orchestrator: object) -> None:
        with self._lock:
            self._orchestrators.append({"orchestrator": orchestrator, "pools": []})

    def capture_pools(self, orchestrator: object) -> None:
        with self._lock:
            for record in reversed(self._orchestrators):
                if record["orchestrator"] is not orchestrator:
                    continue
                pools = record["pools"]
                assert isinstance(pools, list)
                for name in ("_tick_pool", "_refresh_pool", "_integration_pool"):
                    pool = getattr(orchestrator, name, None)
                    if isinstance(pool, ThreadPoolExecutor) and all(
                        existing is not pool for existing in pools
                    ):
                        pools.append(pool)
                return

    def register_store(self, store: object) -> None:
        with self._lock:
            self._stores.append(store)

    def close_all(self) -> None:
        """Drain pools before stores and report every cleanup failure."""

        with self._close_lock:
            self._close_all()

    def _close_all(self) -> None:
        """Serialized implementation of :meth:`close_all`."""

        with self._condition:
            if self._closed:
                return
            self._closing = True
            self._seal_event.set()
            while self._active_constructors:
                self._condition.wait()
            orchestrators = list(self._orchestrators)

        failures: list[str] = []
        seen_pools: set[int] = set()
        for record in reversed(orchestrators):
            orchestrator = record["orchestrator"]
            self.capture_pools(orchestrator)
            pools = record["pools"]
            assert isinstance(pools, list)
            for pool in reversed(pools):
                if not isinstance(pool, ThreadPoolExecutor) or id(pool) in seen_pools:
                    continue
                seen_pools.add(id(pool))
                try:
                    pool.shutdown(wait=True, cancel_futures=False)
                except Exception as exc:  # noqa: BLE001 - drain every owner
                    failures.append(f"executor shutdown failed: {exc!r}")
                live_threads = [
                    thread.name
                    for thread in getattr(pool, "_threads", ())
                    if thread.is_alive()
                ]
                if live_threads:
                    failures.append(
                        "executor retained live threads: " + ", ".join(live_threads)
                    )

        # Exercise the same once-only close boundary as production.  Raw
        # store tracking remains necessary for stores constructed directly by
        # tests, but must not double-close orchestrator-owned resources.
        owned_resource_ids: set[int] = set()
        for record in reversed(orchestrators):
            orchestrator = record["orchestrator"]
            for name in (
                "workflow_runtime",
                "_implementation_receipt_store",
                "coordination_store",
                "integration_queue",
                "review_capacity_store",
                "workflow_job_store",
                "task_transition_journal",
            ):
                resource = getattr(orchestrator, name, None)
                if resource is not None:
                    owned_resource_ids.add(id(resource))
                    if name == "workflow_runtime":
                        owned_resource_ids.update(
                            id(journal)
                            for journal in getattr(resource, "journals", {}).values()
                        )
            close_owned = getattr(orchestrator, "_close_owned_persistent_stores", None)
            if not callable(close_owned):
                continue
            try:
                close_owned()
            except Exception as exc:  # noqa: BLE001 - close every owner
                failures.append(
                    f"{type(orchestrator).__name__} resource close failed: {exc!r}"
                )

        with self._lock:
            stores = list(self._stores)
        seen_stores: set[int] = set()
        for store in reversed(stores):
            if id(store) in seen_stores or id(store) in owned_resource_ids:
                continue
            seen_stores.add(id(store))
            close = getattr(store, "close", None)
            if close is None:
                continue
            try:
                close()
            except Exception as exc:  # noqa: BLE001 - close every owner
                failures.append(
                    f"{type(store).__name__} close failed: {exc!r}"
                )

        with self._lock:
            if not failures:
                self._orchestrators.clear()
                self._stores.clear()
                self._closed = True
                self._closing = False

        if failures:
            raise AssertionError("owned test resource cleanup failed: " + "; ".join(failures))


@pytest.fixture(autouse=True)
def _close_owned_oompah_resources(monkeypatch):
    """Keep real Oompah stores and executor pools inside one test boundary."""

    from oompah.coordination import CoordinationStore
    from oompah.implementation_workflow_adapter import ImplementationReceiptStore
    from oompah.integration_queue import IntegrationQueueStore
    from oompah.orchestrator import Orchestrator
    from oompah.review_capacity import ReviewCapacityStore
    from oompah.task_transition_service import TransitionJournal
    from oompah.workflow_jobs import WorkflowJobStore

    registry = _OompahTestResourceRegistry()

    def tracked_store_init(original):
        @wraps(original)
        def initialize(store, *args, **kwargs):
            registry.begin_constructor(type(store).__name__)
            try:
                original(store, *args, **kwargs)
            except BaseException:
                close = getattr(store, "close", None)
                if callable(close):
                    try:
                        close()
                    except BaseException:
                        pass
                raise
            else:
                registry.register_store(store)
            finally:
                registry.end_constructor()

        return initialize

    for store_class in (
        CoordinationStore,
        ImplementationReceiptStore,
        IntegrationQueueStore,
        ReviewCapacityStore,
        WorkflowJobStore,
        TransitionJournal,
    ):
        monkeypatch.setattr(
            store_class,
            "__init__",
            tracked_store_init(store_class.__init__),
        )

    original_orchestrator_init = Orchestrator.__init__

    @wraps(original_orchestrator_init)
    def tracked_orchestrator_init(orchestrator, *args, **kwargs):
        registry.begin_constructor("orchestrator")
        try:
            registry.register_orchestrator(orchestrator)
            try:
                original_orchestrator_init(orchestrator, *args, **kwargs)
            finally:
                registry.capture_pools(orchestrator)
        finally:
            registry.end_constructor()

    monkeypatch.setattr(Orchestrator, "__init__", tracked_orchestrator_init)

    yield registry

    try:
        registry.close_all()
    except AssertionError as exc:
        pytest.fail(str(exc))
